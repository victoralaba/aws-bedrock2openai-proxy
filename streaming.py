import json
import time
import uuid


def stream_bedrock_to_openai_sse(bedrock_stream, model_name: str):
    """Generator: converts Bedrock EventStream to OpenAI SSE chunks."""
    chat_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    created = int(time.time())

    for event in bedrock_stream:
        if "messageStart" in event:
            yield _sse(
                _chunk(chat_id, created, model_name, delta={"role": "assistant"})
            )

        elif "contentBlockDelta" in event:
            delta = event["contentBlockDelta"].get("delta", {})
            text = delta.get("text", "")
            if text:
                yield _sse(
                    _chunk(chat_id, created, model_name, delta={"content": text})
                )

        elif "messageStop" in event:
            stop_reason = event["messageStop"].get("stopReason", "end_turn")
            finish_reason = _map_finish_reason(stop_reason)
            yield _sse(
                _chunk(
                    chat_id, created, model_name, delta={}, finish_reason=finish_reason
                )
            )

        elif "metadata" in event:
            usage = event["metadata"].get("usage", {})
            yield _sse(
                _chunk(
                    chat_id,
                    created,
                    model_name,
                    delta={},
                    usage={
                        "prompt_tokens": usage.get("inputTokens", 0),
                        "completion_tokens": usage.get("outputTokens", 0),
                        "total_tokens": usage.get("totalTokens", 0),
                    },
                )
            )

    yield "data: [DONE]\n\n"


def _chunk(
    chat_id: str,
    created: int,
    model: str,
    delta: dict,
    finish_reason: str = None,
    usage: dict = None,
) -> dict:
    chunk = {
        "id": chat_id,
        "object": "chat.completion.chunk",
        "created": created,
        "model": model,
        "choices": [
            {
                "index": 0,
                "delta": delta,
                "finish_reason": finish_reason,
            }
        ],
    }
    if usage:
        chunk["usage"] = usage
    return chunk


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


def _map_finish_reason(stop_reason: str) -> str:
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    return mapping.get(stop_reason, "stop")
