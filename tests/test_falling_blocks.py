import random
import importlib.util
import contextlib
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "demos/falling-blocks"))

from game import (  # noqa: E402
    HEIGHT, WIDTH, apply, board_features, empty_board, legal_placements,
    shape, shortlist,
)

RUN_PATH = Path(__file__).resolve().parents[1] / "demos/falling-blocks/run.py"
RUN_SPEC = importlib.util.spec_from_file_location("falling_blocks_run", RUN_PATH)
falling_blocks_run = importlib.util.module_from_spec(RUN_SPEC)
assert RUN_SPEC and RUN_SPEC.loader
RUN_SPEC.loader.exec_module(falling_blocks_run)


class FallingBlocksTests(unittest.TestCase):
    def test_empty_board_has_all_i_placements(self):
        placements = legal_placements(empty_board(), "I")
        self.assertEqual(len(placements), 17)
        self.assertEqual({p.rotation for p in placements}, {0, 1})

    def test_apply_clears_full_line(self):
        board = empty_board()
        board[-1][:6] = [1] * 6
        result, cleared = apply(board, shape("I", 0), 6, HEIGHT - 1)
        self.assertEqual(cleared, 1)
        self.assertEqual(result, empty_board())

    def test_shortlist_is_legal_deterministic_and_bounded(self):
        board = empty_board()
        first = shortlist(legal_placements(board, "T"))
        second = shortlist(legal_placements(board, "T"))
        self.assertEqual(first, second)
        self.assertEqual(len(first), 8)
        self.assertEqual(len({p.choice_id for p in first}), 8)

    def test_seeded_game_transitions_remain_valid(self):
        rng = random.Random(61)
        board = empty_board()
        for _ in range(40):
            piece = rng.choice(("I", "O", "T", "S", "Z", "J", "L"))
            choices = shortlist(legal_placements(board, piece))
            if not choices:
                break
            selected = choices[0]
            board = [list(row) for row in selected.board]
            self.assertEqual(len(board), HEIGHT)
            self.assertTrue(all(len(row) == WIDTH for row in board))
            self.assertGreaterEqual(board_features(board)["holes"], 0)

    @mock.patch.object(falling_blocks_run, "render")
    @mock.patch.object(falling_blocks_run, "decide")
    def test_runner_persists_a_complete_validated_run(self, mocked_decide, _render):
        mocked_decide.side_effect = lambda **kwargs: {
            "choice_id": next(iter(kwargs["choices"])),
            "probabilities": [
                {"choice_id": choice_id, "probability": 1 / len(kwargs["choices"])}
                for choice_id in kwargs["choices"]
            ],
            "latency_ms": 10,
        }
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ, {"TRIO_SPARK_API_KEY": "test-only"}
        ):
            output = Path(directory) / "run"
            with contextlib.redirect_stdout(io.StringIO()):
                summary = falling_blocks_run.run(SimpleNamespace(
                    seed=61, pieces=5, delay=0, timeout=5, output=output))
            transcript = (output / "decisions.jsonl").read_text().splitlines()
        self.assertEqual(summary["status"], "completed")
        self.assertEqual(summary["successful_calls"], 5)
        self.assertEqual(len(transcript), 5)


if __name__ == "__main__":
    unittest.main()
