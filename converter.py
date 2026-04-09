import time
import uuid


def openai_to_bedrock(data: dict) -> dict:
    """Convert OpenAI chat completion request to Bedrock Converse format."""
    messages = data.get("messages", [])

    system_parts = []
    bedrock_messages = []

    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "system":
            system_parts.append({"text": _extract_text(content)})
            continue

        bedrock_messages.append(
            {"role": role, "content": _to_bedrock_content(content)}
        )

    body = {"messages": bedrock_messages}

    if system_parts:
        body["system"] = system_parts

    inference_config = {}
    if "max_tokens" in data:
        inference_config["maxTokens"] = data["max_tokens"]
    elif "max_completion_tokens" in data:
        inference_config["maxTokens"] = data["max_completion_tokens"]
    else:
        inference_config["maxTokens"] = 4096

    if "temperature" in data:
        inference_config["temperature"] = data["temperature"]
    if "top_p" in data:
        inference_config["topP"] = data["top_p"]
    if "stop" in data:
        stop = data["stop"]
        if isinstance(stop, str):
            stop = [stop]
        inference_config["stopSequences"] = stop

    if inference_config:
        body["inferenceConfig"] = inference_config

    return body


def bedrock_to_openai(result: dict, model: str) -> dict:
    """Convert Bedrock Converse response to OpenAI format."""
    output = result.get("output", {})
    message = output.get("message", {})
    content_blocks = message.get("content", [])

    text = ""
    for block in content_blocks:
        if "text" in block:
            text += block["text"]

    usage = result.get("usage", {})
    stop_reason = result.get("stopReason", "end_turn")

    return {
        "id": f"chatcmpl-{uuid.uuid4().hex[:12]}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": text},
                "finish_reason": _map_finish_reason(stop_reason),
            }
        ],
        "usage": {
            "prompt_tokens": usage.get("inputTokens", 0),
            "completion_tokens": usage.get("outputTokens", 0),
            "total_tokens": usage.get("totalTokens", 0),
        },
    }


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "\n".join(parts)
    return str(content)


def _to_bedrock_content(content) -> list:
    if isinstance(content, str):
        return [{"text": content}]
    if isinstance(content, list):
        blocks = []
        for item in content:
            if isinstance(item, dict):
                if item.get("type") == "text":
                    blocks.append({"text": item.get("text", "")})
        return blocks if blocks else [{"text": ""}]
    return [{"text": str(content)}]


def _map_finish_reason(stop_reason: str) -> str:
    mapping = {
        "end_turn": "stop",
        "max_tokens": "length",
        "stop_sequence": "stop",
        "tool_use": "tool_calls",
    }
    return mapping.get(stop_reason, "stop")
