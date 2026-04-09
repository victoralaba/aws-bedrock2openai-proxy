# AWS Bedrock to OpenAI API Proxy

A lightweight Flask proxy that exposes AWS Bedrock's LLM models through an OpenAI-compatible API. Use it with any tool that supports the OpenAI API format — Cursor, Continue, ChatBox, OpenAI SDK, and more.

## Why

AWS Bedrock requires SigV4 signing or its own SDK. Most AI tools and clients only speak the OpenAI API protocol. This proxy bridges the gap — it accepts OpenAI-format requests and forwards them to Bedrock using a simple API key (Bearer Token).

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your Bedrock API key and region

# Run
python app.py
```

The proxy starts at `http://localhost:8000` (configurable via `PROXY_PORT`).

## Configuration

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `BEDROCK_API_KEY` | Yes | — | Bedrock API key (`ABSK...` format) |
| `BEDROCK_REGION` | No | `us-east-1` | AWS region for the Bedrock endpoint |
| `PROXY_PORT` | No | `8000` | Port the proxy listens on |
| `DEFAULT_MODEL` | No | `global.anthropic.claude-opus-4-6-v1` | Fallback model when unrecognized model name is requested |
| `LOG_LEVEL` | No | `INFO` | Logging level |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/v1/chat/completions` | POST | Chat completions (streaming & non-streaming) |
| `/v1/models` | GET | List available models |
| `/health` | GET | Health check |

## Model Aliases

Use short aliases instead of full Bedrock model IDs:

| Alias | Bedrock Model ID |
|-------|-----------------|
| `claude-opus` | `global.anthropic.claude-opus-4-6-v1` |
| `claude-sonnet` | `global.anthropic.claude-sonnet-4-6-v1` |
| `claude-haiku` | `global.anthropic.claude-haiku-4-5-v1` |
| `claude-3-5-sonnet` | `global.anthropic.claude-3-5-sonnet-20241022-v1:0` |
| `claude-3-5-haiku` | `global.anthropic.claude-3-5-haiku-20241022-v1:0` |

Full Bedrock model IDs (containing `anthropic.claude`) are also accepted and passed through directly.

## Usage

### Local access

Any OpenAI-compatible client can connect directly to the proxy:

- **Base URL**: `http://localhost:8000/v1`
- **API Key**: any non-empty string (e.g. `sk-placeholder`)
- **Model**: `claude-opus`, `claude-sonnet`, or any alias from the table above

Works with the OpenAI Python/JS SDK, curl, ChatBox, and other local tools.

### Remote access (Cursor, Continue, etc.)

Some tools (like Cursor) send API requests from their cloud servers and cannot reach localhost. Use [ngrok](https://ngrok.com/) to expose the proxy:

```bash
ngrok http 8000  # match your PROXY_PORT
```

Then configure the tool with the ngrok public URL:

- **Base URL**: `https://xxxx-xx-xx-xx-xx.ngrok-free.app/v1`
- **API Key**: any non-empty string
- **Model**: `claude-opus`, `claude-sonnet`, or any alias

> **Note**: Free ngrok URLs change on every restart. Paid plans support fixed domains.

## Test with curl

```bash
# Non-streaming
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus","messages":[{"role":"user","content":"hello"}]}'

# Streaming
curl http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"claude-opus","messages":[{"role":"user","content":"hello"}],"stream":true}'
```

## Region Latency Test

Find the fastest Bedrock region from your location:

```bash
python test_regions.py
```

Tests all 20 Bedrock-supported regions and reports latency.

## How It Works

```
Client (Cursor / curl / OpenAI SDK)
  │  OpenAI API format
  ▼
ngrok (public URL)          ← needed for Cursor
  │
  ▼
Flask Proxy (localhost)
  │  Bedrock Converse API (boto3 + Bearer Token)
  ▼
AWS Bedrock Runtime → Claude
```

The proxy converts between OpenAI and Bedrock Converse formats:
- Extracts `system` messages into Bedrock's top-level `system` field
- Maps `max_tokens`, `temperature`, `top_p`, `stop` to Bedrock's `inferenceConfig`
- Converts Bedrock's binary EventStream to OpenAI SSE for streaming
- Silently drops unsupported parameters (`n`, `presence_penalty`, etc.)

## License

MIT
