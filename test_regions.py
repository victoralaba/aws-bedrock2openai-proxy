"""Test Bedrock API latency across regions."""

import os
import time

import boto3
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.environ.get("BEDROCK_API_KEY", "")
MODEL_ID = os.environ.get("DEFAULT_MODEL", "global.anthropic.claude-opus-4-6-v1")

REGIONS = [
    # US
    "us-east-1",       # N. Virginia
    "us-east-2",       # Ohio
    "us-west-2",       # Oregon
    # Europe
    "eu-west-1",       # Ireland
    "eu-west-2",       # London
    "eu-west-3",       # Paris
    "eu-central-1",    # Frankfurt
    "eu-central-2",    # Zurich
    "eu-north-1",      # Stockholm
    "eu-south-1",      # Milan
    "eu-south-2",      # Spain
    # Asia Pacific
    "ap-south-1",      # Mumbai
    "ap-south-2",      # Hyderabad
    "ap-northeast-1",  # Tokyo
    "ap-northeast-2",  # Seoul
    "ap-northeast-3",  # Osaka
    "ap-southeast-1",  # Singapore
    "ap-southeast-2",  # Sydney
    # Other
    "ca-central-1",    # Canada
    "sa-east-1",       # São Paulo
]

TEST_BODY = {
    "messages": [{"role": "user", "content": [{"text": "hi"}]}],
    "inferenceConfig": {"maxTokens": 1},
}


def test_region(region: str) -> dict:
    os.environ["AWS_BEARER_TOKEN_BEDROCK"] = API_KEY
    try:
        client = boto3.client("bedrock-runtime", region_name=region)

        start = time.time()
        client.converse(modelId=MODEL_ID, **TEST_BODY)
        latency = time.time() - start

        return {"region": region, "latency_ms": round(latency * 1000), "status": "ok"}
    except Exception as e:
        return {"region": region, "latency_ms": -1, "status": str(e)[:80]}


if __name__ == "__main__":
    if not API_KEY:
        print("Error: BEDROCK_API_KEY not set")
        exit(1)

    print(f"Model: {MODEL_ID}")
    print(f"Testing {len(REGIONS)} regions...\n")
    print(f"{'Region':<20} {'Latency':>10}  Status")
    print("-" * 55)

    results = []
    for region in REGIONS:
        result = test_region(region)
        results.append(result)
        if result["latency_ms"] > 0:
            print(f"{result['region']:<20} {result['latency_ms']:>8} ms  {result['status']}")
        else:
            print(f"{result['region']:<20}       N/A  {result['status']}")

    ok_results = [r for r in results if r["latency_ms"] > 0]
    if ok_results:
        best = min(ok_results, key=lambda r: r["latency_ms"])
        print(f"\nBest: {best['region']} ({best['latency_ms']} ms)")
