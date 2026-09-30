"""Small dependency-free client for the Trio-Spark decision API."""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
import uuid

API_URL = "https://platform.machinefi.com/api/spark/v1/decisions"


def decide(*, task: str, state: dict, choices: dict[str, str], timeout: float = 20) -> dict:
    """Return Spark's chosen ID, full distribution, confidence, and measured latency."""
    if not 2 <= len(choices) <= 8:
        raise ValueError("Trio-Spark accepts 2 to 8 choices")
    key = os.environ["TRIO_SPARK_API_KEY"]
    body = json.dumps({
        "model": "trio-spark-preview",
        "task": task,
        "state": state,
        "choices": [{"id": key, "description": value} for key, value in choices.items()],
    }).encode()
    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid4()),
            "User-Agent": "Trio-Spark-Python/1.0",
        },
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Trio-Spark returned HTTP {error.code}") from None
    result["wall_latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result
