import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from clients.python.trio_spark import TrioSparkError
from evals.metrics import decision_score, summarize
from evals.run import Item, _fnv1a, _jevals_shuffle, call, write_summary


class EvaluationTests(unittest.TestCase):
    def test_metrics_and_decision_score(self):
        rows = [
            {"item_id": "a", "target": 0, "prediction": 0,
             "probabilities": [0.9, 0.1], "latency_ms": 10,
             "primitive": "noul"},
            {"item_id": "b", "target": 1, "prediction": 1,
             "probabilities": [0.2, 0.8], "latency_ms": 20,
             "primitive": "noul"},
        ]
        result = summarize(rows, expected_n=2)
        self.assertEqual(result["accuracy"], 1)
        self.assertTrue(result["comparable_overall"])
        self.assertGreater(decision_score(rows, "noul"), 0)

    def test_incomplete_run_is_not_comparable(self):
        rows = [{"item_id": "a", "target": 0, "prediction": 0,
                 "probabilities": [0.8, 0.2], "primitive": "choice"}]
        result = summarize(rows, expected_n=2)
        self.assertFalse(result["comparable_overall"])
        self.assertEqual(result["coverage"], 0.5)

    def test_jevals_shuffle_matches_published_algorithm(self):
        self.assertEqual(_fnv1a("banking77-2:0"), 712669766)
        self.assertEqual(
            _jevals_shuffle(("a", "b", "c", "d"), "banking77-2", 0),
            ("d", "a", "b", "c"),
        )

    @mock.patch("evals.run.time.sleep")
    @mock.patch("evals.run.decide")
    def test_retry_reuses_idempotency_key(self, mocked_decide, _sleep):
        mocked_decide.side_effect = [
            TrioSparkError(status=503, code="unavailable", message="busy", retryable=True),
            {"choice_id": "c1", "probabilities": [
                {"choice_id": "c0", "probability": 0.25},
                {"choice_id": "c1", "probability": 0.75},
            ], "latency_ms": 10, "model_version": "test"},
        ]
        response, probabilities, prediction, events = call(
            Item("item", "choose", {}, ("a", "b"), 1), "run", 5, 2, 0)
        self.assertEqual(prediction, 1)
        self.assertEqual(probabilities, [0.25, 0.75])
        self.assertEqual(len(events), 1)
        first = mocked_decide.call_args_list[0].kwargs["idempotency_key"]
        second = mocked_decide.call_args_list[1].kwargs["idempotency_key"]
        self.assertEqual(first, second)
        self.assertEqual(response["model_version"], "test")

    @mock.patch("evals.run.time.sleep")
    @mock.patch("evals.run.decide")
    def test_transient_network_error_retries_with_same_request(self, mocked_decide, _sleep):
        mocked_decide.side_effect = [
            TimeoutError("timed out"),
            {"choice_id": "c0", "probabilities": [
                {"choice_id": "c0", "probability": 0.6},
                {"choice_id": "c1", "probability": 0.4},
            ]},
        ]
        _, _, _, events = call(
            Item("item", "choose", {}, ("a", "b"), 0), "run", 5, 1, 0)
        self.assertEqual(events[0]["code"], "TimeoutError")
        self.assertEqual(
            mocked_decide.call_args_list[0].kwargs["idempotency_key"],
            mocked_decide.call_args_list[1].kwargs["idempotency_key"],
        )

    @mock.patch("evals.run.decide")
    def test_invalid_probability_distribution_is_rejected(self, mocked_decide):
        mocked_decide.return_value = {
            "choice_id": "c0", "probabilities": [
                {"choice_id": "c0", "probability": 0.8},
                {"choice_id": "c1", "probability": 0.8},
            ],
        }
        with self.assertRaisesRegex(ValueError, "sum to one"):
            call(Item("item", "choose", {}, ("a", "b"), 0), "run", 5, 0, 0)

    def test_summary_is_written_without_secrets(self):
        records = {("a", 0): {
            "item_id": "a", "epoch": 0, "target": 0, "prediction": 0,
            "probabilities": [0.9, 0.1], "primitive": "choice",
            "latency_ms": 5, "model_version": "test",
            "raw_response": {"usage": {"billed_input_tokens": 3}},
        }}
        with tempfile.TemporaryDirectory() as directory:
            result = write_summary(records, 1, "sst2", Path(directory))
            saved = json.loads((Path(directory) / "summary.json").read_text())
        self.assertEqual(saved, result)
        self.assertNotIn("api_key", json.dumps(saved).lower())


if __name__ == "__main__":
    unittest.main()
