"""Small dependency-free client for the Trio-Spark decision API."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from typing import Any

API_URL = "https://platform.machinefi.com/api/spark/v1/decisions"
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:-]+$")


class TrioSparkError(RuntimeError):
    """Structured error returned by the Trio-Spark API."""

    def __init__(
        self,
        *,
        status: int,
        code: str,
        message: str,
        retryable: bool = False,
        new_request_required: bool = False,
        request_id: str | None = None,
        retry_after: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.retryable = retryable
        self.new_request_required = new_request_required
        self.request_id = request_id
        self.retry_after = retry_after


def _parse_http_error(error: urllib.error.HTTPError) -> TrioSparkError:
    payload: dict[str, Any] = {}
    try:
        decoded = json.load(error)
        if isinstance(decoded, dict) and isinstance(decoded.get("error"), dict):
            payload = decoded["error"]
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        pass

    code = payload.get("code")
    message = payload.get("message")
    return TrioSparkError(
        status=error.code,
        code=code if isinstance(code, str) else "http_error",
        message=message if isinstance(message, str) else f"Trio-Spark returned HTTP {error.code}",
        retryable=payload.get("retryable") is True,
        new_request_required=payload.get("new_request_required") is True,
        request_id=payload.get("request_id") if isinstance(payload.get("request_id"), str) else None,
        retry_after=error.headers.get("Retry-After") if error.headers else None,
    )


def decide(
    *,
    task: str,
    state: dict,
    choices: dict[str, str],
    timeout: float = 20,
    session_id: str | None = None,
    idempotency_key: str | None = None,
) -> dict:
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
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Idempotency-Key": idempotency_key or str(uuid.uuid4()),
        "User-Agent": "Trio-Spark-Python/1.0",
    }
    if session_id is not None:
        if not 1 <= len(session_id) <= 128 or SAFE_REQUEST_ID.fullmatch(session_id) is None:
            raise ValueError("session_id must contain 1 to 128 letters, digits, '.', '_', ':', or '-'")
        headers["X-Spark-Session-Id"] = session_id

    request = urllib.request.Request(
        API_URL,
        data=body,
        method="POST",
        headers=headers,
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as error:
        raise _parse_http_error(error) from None
    result["wall_latency_ms"] = round((time.perf_counter() - started) * 1000, 1)
    return result
