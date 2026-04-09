import os
import sys

from dotenv import load_dotenv

load_dotenv()

BEDROCK_API_KEY = os.environ.get("BEDROCK_API_KEY", "")
BEDROCK_REGION = os.environ.get("BEDROCK_REGION", "us-east-1")
PROXY_PORT = int(os.environ.get("PROXY_PORT", "5000"))
DEFAULT_MODEL = os.environ.get(
    "DEFAULT_MODEL", "global.anthropic.claude-opus-4-6-v1"
)
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO")


def validate():
    if not BEDROCK_API_KEY:
        print("Error: BEDROCK_API_KEY is required. Set it in .env or environment.")
        sys.exit(1)
