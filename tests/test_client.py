import io
import json
import os
import unittest
import urllib.error
from unittest import mock

from clients.python.trio_spark import TrioSparkError, decide


class Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class ClientTests(unittest.TestCase):
    @mock.patch.dict(os.environ, {"TRIO_SPARK_API_KEY": "tf_test"}, clear=True)
    @mock.patch("urllib.request.urlopen")
    def test_session_and_idempotency_headers(self, urlopen):
        urlopen.return_value = Response(json.dumps({"choice_id": "slow"}).encode())

        result = decide(
            task="choose",
            state={"load": 9},
            choices={"slow": "Slow down", "stop": "Stop"},
            session_id="agent-loop:run_42",
            idempotency_key="request-42",
        )

        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("X-spark-session-id"), "agent-loop:run_42")
        self.assertEqual(request.get_header("Idempotency-key"), "request-42")
        self.assertEqual(result["choice_id"], "slow")
        self.assertIn("wall_latency_ms", result)

    @mock.patch.dict(os.environ, {"TRIO_SPARK_API_KEY": "tf_test"}, clear=True)
    def test_rejects_unsafe_session_id(self):
        with self.assertRaises(ValueError):
            decide(
                task="choose",
                state={},
                choices={"a": "A", "b": "B"},
                session_id="contains a space",
            )

    @mock.patch.dict(os.environ, {"TRIO_SPARK_API_KEY": "tf_test"}, clear=True)
    @mock.patch("urllib.request.urlopen")
    def test_structured_error(self, urlopen):
        body = json.dumps({
            "error": {
                "code": "overloaded",
                "message": "Try again shortly.",
                "retryable": True,
                "new_request_required": True,
                "request_id": "req_123",
            }
        }).encode()
        urlopen.side_effect = urllib.error.HTTPError(
            "https://example.test", 429, "Too Many Requests", {"Retry-After": "2"}, io.BytesIO(body)
        )

        with self.assertRaises(TrioSparkError) as caught:
            decide(task="choose", state={}, choices={"a": "A", "b": "B"})

        error = caught.exception
        self.assertEqual(error.status, 429)
        self.assertEqual(error.code, "overloaded")
        self.assertTrue(error.retryable)
        self.assertTrue(error.new_request_required)
        self.assertEqual(error.request_id, "req_123")
        self.assertEqual(error.retry_after, "2")


if __name__ == "__main__":
    unittest.main()
