#!/usr/bin/env python3
"""Recompute a completed run summary without making inference requests."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from evals.metrics import decision_score, summarize  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    manifest = json.loads((args.run_directory / "manifest.json").read_text())
    latest = {}
    with (args.run_directory / "raw.jsonl").open() as raw:
        for line in raw:
            row = json.loads(line)
            latest[(row["item_id"], int(row.get("epoch", 0)))] = row
    rows = list(latest.values())
    expected = int(manifest["planned_requests"])
    if len(rows) != expected:
        raise SystemExit(
            f"run has {len(rows)} unique records but planned {expected}; summary not written")
    result = summarize(rows, expected)
    if manifest["benchmark"] == "jevals":
        primitive = manifest["source"]["primitive"]
        result["decision_score"] = (
            decision_score(rows, primitive) if result["comparable_overall"] else None)
        result["decision_score_status"] = (
            "comparable" if result["comparable_overall"]
            else "not_comparable_incomplete_coverage")
    result["provenance"] = {
        "collection_git_commit": manifest["git_commit"],
        "scoring_git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "scored_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    (args.run_directory / "summary.json").write_text(
        json.dumps(result, indent=2) + "\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
