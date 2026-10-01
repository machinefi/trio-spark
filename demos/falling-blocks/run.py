#!/usr/bin/env python3
"""Play Falling Blocks with real Trio-Spark production decisions."""

from __future__ import annotations

import argparse
import json
import os
import random
import statistics
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from clients.python.trio_spark import TrioSparkError, decide  # noqa: E402
from game import (  # noqa: E402
    HEIGHT, PIECES, WIDTH, apply, board_features, empty_board,
    legal_placements, rows, shape, shortlist,
)

TASK = (
    "Play Falling Blocks. Choose the best legal placement. Prioritize clearing "
    "lines, then avoid holes and tall or rough stacks."
)
LINE_POINTS = (0, 100, 300, 500, 800)


def seven_bag(rng: random.Random):
    while True:
        bag = list(PIECES)
        rng.shuffle(bag)
        yield from bag


def render(board, *, falling=None, piece=None, score=0, lines=0, turn=0):
    frame = [line[:] for line in board]
    if falling and piece:
        rotation, column, row = falling
        for dx, dy in shape(piece, rotation):
            y, x = row + dy, column + dx
            if 0 <= y < HEIGHT and 0 <= x < WIDTH:
                frame[y][x] = 2
    glyph = {0: "  ", 1: "██", 2: "▓▓"}
    print("\033[H\033[2J", end="")
    print(f"Trio-Spark Falling Blocks · turn {turn} · score {score} · lines {lines}")
    print("┌" + "──" * WIDTH + "┐")
    for line in frame:
        print("│" + "".join(glyph[value] for value in line) + "│")
    print("└" + "──" * WIDTH + "┘", flush=True)


def animate_drop(board, piece, placement, delay, **status):
    if delay <= 0 or not sys.stdout.isatty():
        return
    for row in range(0, placement.landing_row + 1):
        render(board, falling=(placement.rotation, placement.column, row),
               piece=piece, **status)
        time.sleep(delay)


def run(args) -> dict:
    if not os.environ.get("TRIO_SPARK_API_KEY"):
        raise SystemExit(
            "Set TRIO_SPARK_API_KEY from https://platform.machinefi.com/spark before running.")
    rng = random.Random(args.seed)
    pieces = seven_bag(rng)
    current, following = next(pieces), next(pieces)
    board = empty_board()
    score = cleared_total = successful = 0
    latencies = []
    run_id = uuid.uuid4().hex
    session_id = f"falling-blocks:{run_id}"
    started = time.time()
    output = args.output or Path("runs") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output.mkdir(parents=True, exist_ok=False)
    transcript_path = output / "decisions.jsonl"
    terminal_error = None
    interrupted = False

    try:
        with transcript_path.open("w") as transcript:
            for turn in range(1, args.pieces + 1):
                legal = legal_placements(board, current)
                candidates = shortlist(legal)
                if len(candidates) < 2:
                    break
                features = board_features(board)
                state = {
                    "board_top_to_bottom": rows(board),
                    "column_heights": features["column_heights"],
                    "holes": features["holes"],
                    "roughness": features["roughness"],
                    "current_piece": current,
                    "next_piece": following,
                    "score": score,
                    "lines": cleared_total,
                    "decision_number": turn,
                    "legal_placements": len(legal),
                    "shortlist_rule": "lines, holes, max height, roughness, aggregate height",
                }
                choices = {candidate.choice_id: candidate.description for candidate in candidates}
                result = decide(
                    task=TASK,
                    state=state,
                    choices=choices,
                    timeout=args.timeout,
                    session_id=session_id,
                    idempotency_key=str(uuid.uuid5(uuid.NAMESPACE_URL, f"{session_id}:{turn}")),
                )
                selected = next(
                    (candidate for candidate in candidates
                     if candidate.choice_id == result.get("choice_id")), None)
                if selected is None:
                    raise RuntimeError("Spark returned an action outside the legal shortlist")
                animate_drop(board, current, selected, args.delay, score=score,
                             lines=cleared_total, turn=turn)
                before = rows(board)
                board, cleared = apply(
                    board, shape(current, selected.rotation), selected.column,
                    selected.landing_row)
                cleared_total += cleared
                score += 4 + LINE_POINTS[cleared]
                successful += 1
                if result.get("latency_ms") is not None:
                    latencies.append(float(result["latency_ms"]))
                record = {
                    "turn": turn,
                    "piece": current,
                    "next_piece": following,
                    "board_before": before,
                    "legal_placements": len(legal),
                    "choices": [{"id": c.choice_id, "description": c.description}
                                for c in candidates],
                    "response": result,
                    "applied": {
                        "choice_id": selected.choice_id,
                        "rotation": selected.rotation,
                        "column": selected.column,
                        "landing_row": selected.landing_row,
                        "lines_cleared": cleared,
                        "score_after": score,
                        "board_after": rows(board),
                    },
                }
                transcript.write(json.dumps(record, separators=(",", ":")) + "\n")
                transcript.flush()
                render(board, score=score, lines=cleared_total, turn=turn)
                current, following = following, next(pieces)
    except TrioSparkError as exc:
        terminal_error = exc.code
        print(f"Trio-Spark error ({exc.code}): {exc}", file=sys.stderr)
    except KeyboardInterrupt:
        interrupted = True
        print("Stopped by user.", file=sys.stderr)

    duration = round(time.time() - started, 3)
    summary = {
        "demo": "falling-blocks",
        "production_api": True,
        "seed": args.seed,
        "requested_pieces": args.pieces,
        "successful_calls": successful,
        "lines_cleared": cleared_total,
        "score": score,
        "duration_seconds": duration,
        "status": (
            "api_error" if terminal_error else
            "interrupted" if interrupted else
            "completed"
        ),
        "terminal_error": terminal_error,
        "model_latency_ms": {
            "min": min(latencies) if latencies else None,
            "median": statistics.median(latencies) if latencies else None,
            "max": max(latencies) if latencies else None,
        },
        "transcript": transcript_path.name,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))
    if terminal_error:
        raise SystemExit(1)
    if interrupted:
        raise SystemExit(130)
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=61)
    parser.add_argument("--pieces", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.035,
                        help="seconds per falling animation frame; 0 disables animation")
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.pieces < 1:
        parser.error("--pieces must be positive")
    if args.delay < 0:
        parser.error("--delay must be non-negative")
    run(args)


if __name__ == "__main__":
    main()
