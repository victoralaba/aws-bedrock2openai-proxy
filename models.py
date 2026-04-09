import time

import config

MODEL_MAP = {
    "claude-sonnet": "global.anthropic.claude-sonnet-4-6-v1",
    "claude-sonnet-4": "global.anthropic.claude-sonnet-4-6-v1",
    "claude-haiku": "global.anthropic.claude-haiku-4-5-v1",
    "claude-opus": "global.anthropic.claude-opus-4-6-v1",
    "claude-opus-4": "global.anthropic.claude-opus-4-6-v1",
    "claude-3-5-sonnet": "global.anthropic.claude-3-5-sonnet-20241022-v1:0",
    "claude-3.5-sonnet": "global.anthropic.claude-3-5-sonnet-20241022-v1:0",
    "claude-3-5-haiku": "global.anthropic.claude-3-5-haiku-20241022-v1:0",
    "claude-3.5-haiku": "global.anthropic.claude-3-5-haiku-20241022-v1:0",
}


def resolve(model_name: str) -> str:
    if model_name in MODEL_MAP:
        return MODEL_MAP[model_name]
    if "anthropic.claude" in model_name:
        return model_name
    return config.DEFAULT_MODEL


def list_models() -> dict:
    now = int(time.time())
    models = []
    for alias, bedrock_id in MODEL_MAP.items():
        models.append(
            {
                "id": alias,
                "object": "model",
                "created": now,
                "owned_by": "anthropic",
                "permission": [],
                "root": bedrock_id,
                "parent": None,
            }
        )
    return {"object": "list", "data": models}
