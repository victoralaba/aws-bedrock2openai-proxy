import os
import logging

import boto3

import config

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        os.environ["AWS_BEARER_TOKEN_BEDROCK"] = config.BEDROCK_API_KEY
        _client = boto3.client(
            "bedrock-runtime",
            region_name=config.BEDROCK_REGION,
        )
    return _client


def converse(model_id: str, body: dict) -> dict:
    client = _get_client()
    logger.info("Converse: model=%s", model_id)
    response = client.converse(modelId=model_id, **body)
    return response


def converse_stream(model_id: str, body: dict):
    client = _get_client()
    logger.info("ConverseStream: model=%s", model_id)
    response = client.converse_stream(modelId=model_id, **body)
    return response.get("stream")
