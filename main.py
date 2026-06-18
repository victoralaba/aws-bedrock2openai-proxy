import asyncio
import json
import logging
import os
import time
from typing import AsyncGenerator, Optional

import boto3
import httpx
from aws_requests_auth.boto_utils import BotoAWSRequestsAuth
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config (all from env — no hardcoding)
# ---------------------------------------------------------------------------
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")
MANTLE_BASE = f"https://bedrock-mantle.{AWS_REGION}.api.aws/v1"
PORT = int(os.getenv("PORT", "8080"))
TEST_MAX_TOKENS = int(os.getenv("TEST_MAX_TOKENS", "1"))  # keep test costs minimal

# ---------------------------------------------------------------------------
# AWS auth — reads from ~/.aws/config, env vars, or IAM role automatically
# ---------------------------------------------------------------------------
def get_auth() -> BotoAWSRequestsAuth:
    session = boto3.Session(region_name=AWS_REGION)
    credentials = session.get_credentials().resolve()
    return BotoAWSRequestsAuth(
        aws_host=f"bedrock-mantle.{AWS_REGION}.api.aws",
        aws_region=AWS_REGION,
        aws_service="bedrock",
    )


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(
    title="Bedrock Mantle Proxy",
    description="Local OpenAI-compatible proxy for AWS Bedrock via the bedrock-mantle endpoint.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------
@app.get("/health", tags=["Meta"])
async def health():
    return {"status": "ok", "region": AWS_REGION, "mantle_base": MANTLE_BASE}


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
@app.get("/v1/models", tags=["Models"])
async def list_models():
    """List all models available via bedrock-mantle."""
    auth = get_auth()
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{MANTLE_BASE}/models", auth=auth)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail=resp.text)
    return resp.json()


# ---------------------------------------------------------------------------
# Chat completions proxy
# ---------------------------------------------------------------------------
async def _stream_mantle(body: dict, auth) -> AsyncGenerator[bytes, None]:
    """Forward a streaming request to mantle and yield SSE chunks."""
    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream(
            "POST",
            f"{MANTLE_BASE}/chat/completions",
            json=body,
            auth=auth,
            headers={"Content-Type": "application/json"},
        ) as resp:
            if resp.status_code != 200:
                error_body = await resp.aread()
                yield b"data: " + json.dumps({"error": error_body.decode()}).encode() + b"\n\n"
                return
            async for chunk in resp.aiter_bytes():
                yield chunk


@app.post("/v1/chat/completions", tags=["Proxy"])
async def chat_completions(request: Request):
    """
    Drop-in OpenAI-compatible chat completions endpoint.
    Strips the Bearer token from Cline and replaces with SigV4.
    Supports streaming.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    auth = get_auth()
    stream = body.get("stream", False)

    log.info("→ %s | stream=%s | tokens=%s", body.get("model"), stream, body.get("max_tokens"))

    if stream:
        return StreamingResponse(
            _stream_mantle(body, auth),
            media_type="text/event-stream",
        )

    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            f"{MANTLE_BASE}/chat/completions",
            json=body,
            auth=auth,
            headers={"Content-Type": "application/json"},
        )

    if resp.status_code != 200:
        log.warning("Mantle error %s: %s", resp.status_code, resp.text)
        raise HTTPException(status_code=resp.status_code, detail=resp.json())

    return resp.json()


# ---------------------------------------------------------------------------
# Test endpoints
# ---------------------------------------------------------------------------
class TestResult(BaseModel):
    model_id: str
    status: str          # "ok" | "error"
    latency_ms: Optional[float] = None
    response: Optional[str] = None
    error: Optional[str] = None


async def _test_model(model_id: str, auth) -> TestResult:
    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Hello, are you working?"}],
        "max_tokens": TEST_MAX_TOKENS,
    }
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"{MANTLE_BASE}/chat/completions",
                json=payload,
                auth=auth,
                headers={"Content-Type": "application/json"},
            )
        latency_ms = round((time.monotonic() - start) * 1000, 1)

        if resp.status_code == 200:
            data = resp.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return TestResult(
                model_id=model_id,
                status="ok",
                latency_ms=latency_ms,
                response=content,
            )
        else:
            return TestResult(
                model_id=model_id,
                status="error",
                latency_ms=latency_ms,
                error=resp.text,
            )
    except Exception as exc:
        latency_ms = round((time.monotonic() - start) * 1000, 1)
        return TestResult(model_id=model_id, status="error", latency_ms=latency_ms, error=str(exc))


@app.post("/v1/test/{model_id:path}", tags=["Testing"])
async def test_model(model_id: str):
    """
    Test a specific model with a minimal prompt.
    Returns the response and latency in ms.
    """
    auth = get_auth()
    result = await _test_model(model_id, auth)
    return result


@app.get("/v1/test/all", tags=["Testing"])
async def test_all_models():
    """
    Ping all available models with a 1-token prompt in parallel.
    Cost is minimal (max_tokens=1 per model).
    Returns ok/fail + latency for each.
    """
    auth = get_auth()

    # Fetch model list
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{MANTLE_BASE}/models", auth=auth)
    if resp.status_code != 200:
        raise HTTPException(status_code=resp.status_code, detail="Failed to fetch model list")

    models = [m["id"] for m in resp.json().get("data", [])]
    log.info("Testing %d models...", len(models))

    results = await asyncio.gather(*[_test_model(mid, auth) for mid in models])

    ok = [r for r in results if r.status == "ok"]
    fail = [r for r in results if r.status == "error"]

    return {
        "summary": {"total": len(results), "ok": len(ok), "failed": len(fail)},
        "results": [r.model_dump() for r in results],
    }


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)
