import logging

from flask import Flask, Response, jsonify, request

import bedrock_client
import config
import converter
import models
import streaming

app = Flask(__name__)


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


@app.route("/v1/models", methods=["GET"])
def list_models():
    return jsonify(models.list_models())


@app.route("/v1/chat/completions", methods=["POST"])
def chat_completions():
    data = request.json
    model_name = data.get("model", config.DEFAULT_MODEL)
    bedrock_model_id = models.resolve(model_name)
    is_stream = data.get("stream", False)

    bedrock_body = converter.openai_to_bedrock(data)

    try:
        if is_stream:
            stream = bedrock_client.converse_stream(bedrock_model_id, bedrock_body)
            return Response(
                streaming.stream_bedrock_to_openai_sse(stream, model_name),
                mimetype="text/event-stream",
                headers={
                    "Cache-Control": "no-cache",
                    "Connection": "keep-alive",
                    "X-Accel-Buffering": "no",
                },
            )
        else:
            result = bedrock_client.converse(bedrock_model_id, bedrock_body)
            return jsonify(converter.bedrock_to_openai(result, model_name))
    except Exception as e:
        logging.exception("Bedrock call failed")
        return (
            jsonify(
                {
                    "error": {
                        "message": str(e),
                        "type": "server_error",
                        "code": 500,
                    }
                }
            ),
            500,
        )


if __name__ == "__main__":
    config.validate()
    logging.basicConfig(level=getattr(logging, config.LOG_LEVEL, logging.INFO))
    app.run(host="0.0.0.0", port=config.PROXY_PORT, threaded=True)
