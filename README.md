# bedrock-mantle-proxy

A lightweight local proxy that exposes an OpenAI-compatible API for AWS Bedrock via the `bedrock-mantle` endpoint. Handles SigV4 signing automatically so tools like Cline (VS Code) can talk to Bedrock models without native AWS support.

---

## Why this exists

AWS Bedrock's `bedrock-mantle` endpoint speaks OpenAI-compatible API, but requires AWS SigV4 request signing. Tools like Cline send a plain Bearer token — this proxy sits in between, strips the Bearer token, and re-signs every request with your AWS credentials.

```txt
Cline (VS Code) → localhost:8080 → [SigV4 signing] → bedrock-mantle.us-east-1.api.aws
```

---

## Requirements

- Python 3.10+
- AWS credentials configured (`~/.aws/config` or environment variables)
- IAM user with `AmazonBedrockFullAccess` + `AWSMarketplaceManageSubscriptions` policies

---

## Setup

```bash
# 1. Clone the repo
git clone https://github.com/yourname/bedrock-mantle-proxy
cd bedrock-mantle-proxy

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. (Optional) Override config
cp env.example .env
# Edit .env if you need to override region, port, or credentials
```

---

## Running

```bash
python main.py
```

The proxy starts on `http://localhost:8080` by default.

To change the port:

```bash
PORT=9000 python main.py
```

---

## Cline configuration

In VS Code, open Cline settings and set:

| Field | Value |
| --- | --- |
| API Provider | `OpenAI Compatible` |
| Base URL | `http://localhost:8080/v1` |
| API Key | `any-dummy-value` (ignored by proxy) |
| Model | `mistral.devstral-2-123b` |

---

## Endpoints

### `GET /health`

Check if the proxy is running.

```bash
curl http://localhost:8080/health
```

---

### `GET /v1/models`

List all models available via your AWS account on bedrock-mantle.

```bash
curl http://localhost:8080/v1/models
```

---

### `POST /v1/chat/completions`

Main proxy endpoint. Accepts the same request format as the OpenAI Chat Completions API. Supports streaming.

```bash
curl -s -X POST http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "mistral.devstral-2-123b",
    "messages": [{"role": "user", "content": "Hello!"}],
    "max_tokens": 100
  }'
```

---

### `POST /v1/test/{model_id}`

Test a specific model with a minimal prompt. Returns the response and latency in ms.

```bash
curl -X POST http://localhost:8080/v1/test/mistral.devstral-2-123b
```

Example response:

```json
{
  "model_id": "mistral.devstral-2-123b",
  "status": "ok",
  "latency_ms": 843.2,
  "response": "Yes",
  "error": null
}
```

---

### `GET /v1/test/all`

Pings all available models in parallel with a 1-token prompt. Useful to see which models are accessible before committing to one.

```bash
curl http://localhost:8080/v1/test/all
```

Example response:

```json
{
  "summary": { "total": 47, "ok": 45, "failed": 2 },
  "results": [
    { "model_id": "mistral.devstral-2-123b", "status": "ok", "latency_ms": 843.2, "response": "Yes", "error": null },
    { "model_id": "openai.gpt-5.5", "status": "error", "latency_ms": 201.0, "response": null, "error": "..." }
  ]
}
```

> **Cost note:** Each model is tested with `max_tokens=1`. With ~47 models, total cost is negligible (fractions of a cent).

---

## Environment variables

| Variable | Default | Description |
| --- | --- | --- |
| `AWS_REGION` | `us-east-1` | AWS region for bedrock-mantle |
| `AWS_ACCESS_KEY_ID` | from `~/.aws/config` | Override AWS access key |
| `AWS_SECRET_ACCESS_KEY` | from `~/.aws/config` | Override AWS secret key |
| `PORT` | `8080` | Local port to listen on |
| `LOG_LEVEL` | `INFO` | Logging verbosity |
| `TEST_MAX_TOKENS` | `1` | Max tokens used in test endpoints |

---

## Interactive API docs

FastAPI auto-generates docs at:

- Swagger UI: `http://localhost:8080/docs`
- ReDoc: `http://localhost:8080/redoc`

---

## License

MIT
