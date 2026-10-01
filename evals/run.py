#!/usr/bin/env python3
"""Run reproducible public benchmarks through the Trio-Spark production API."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import math
import os
import platform
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from clients.python.trio_spark import TrioSparkError, decide  # noqa: E402
from evals.metrics import decision_score, summarize  # noqa: E402

MODEL = "trio-spark-preview"
MAX_CHOICES = 8


@dataclass(frozen=True)
class Item:
    item_id: str
    task: str
    state: str | dict
    choices: tuple[str, ...]
    target: int
    primitive: str = "choice"
    epoch: int = 0


BENCHMARKS = {
    "sst2": {
        "dataset": "nyu-mll/glue", "config": "sst2", "split": "validation",
        "revision": "bcdcba79d07bc864c1c254ccfcedcce55bcc9a8c",
        "expected_rows": 872, "text": "sentence",
        "task": "Classify the sentiment of this sentence.",
        "choices": ("negative", "positive"),
    },
    "sst5": {
        "dataset": "SetFit/sst5", "config": None, "split": "test",
        "revision": "e51bdcd8cd3a30da231967c1a249ba59361279a3",
        "expected_rows": 2210, "text": "text",
        "task": "Classify the sentiment from very negative to very positive.",
        "choices": ("very negative", "negative", "neutral", "positive", "very positive"),
    },
    "ag-news": {
        "dataset": "fancyzhx/ag_news", "config": None, "split": "test",
        "revision": "eb185aade064a813bc0b7f42de02595523103ca4",
        "expected_rows": 7600, "text": "text",
        "task": "Classify the news topic.",
        "choices": ("World", "Sports", "Business", "Sci/Tech"),
    },
    "tweet-offensive": {
        "dataset": "cardiffnlp/tweet_eval", "config": "offensive", "split": "test",
        "revision": "b3a375baf0f409c77e6bc7aa35102b7b3534f8be",
        "expected_rows": 860, "text": "text",
        "task": "Classify whether this tweet is offensive.",
        "choices": ("not offensive", "offensive"),
    },
    "pubmedqa": {
        "dataset": "qiaojin/PubMedQA", "config": "pqa_labeled", "split": "train",
        "revision": "9001f2853fb87cab8d220904e0de81ac6973b318",
        "expected_rows": 1000,
        "task": "Given the biomedical abstract passages, what is the answer to the research question?",
        "choices": ("yes", "no", "maybe"),
    },
}


def _git_commit() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
            stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _nested(row: dict, path: str):
    value = row
    for part in path.split("."):
        value = value[part]
    return value


def _imul(a: int, b: int) -> int:
    return ((a & 0xFFFFFFFF) * (b & 0xFFFFFFFF)) & 0xFFFFFFFF


def _fnv1a(text: str) -> int:
    value = 0x811C9DC5
    encoded = text.encode("utf-16-le")
    for index in range(0, len(encoded), 2):
        value ^= int.from_bytes(encoded[index:index + 2], "little")
        value = _imul(value, 0x01000193)
    return value


def _mulberry32(seed: int):
    value = seed & 0xFFFFFFFF
    while True:
        value = (value + 0x6D2B79F5) & 0xFFFFFFFF
        mixed = value
        mixed = _imul(mixed ^ (mixed >> 15), mixed | 1)
        mixed ^= (mixed + _imul(mixed ^ (mixed >> 7), mixed | 61)) & 0xFFFFFFFF
        yield ((mixed ^ (mixed >> 14)) & 0xFFFFFFFF) / 4294967296


def _jevals_shuffle(values: tuple[str, ...], item_id: str, seed: int) -> tuple[str, ...]:
    shuffled = list(values)
    randoms = _mulberry32(_fnv1a(f"{item_id}:{seed}"))
    for index in range(len(shuffled) - 1, 0, -1):
        other = int(next(randoms) * (index + 1))
        shuffled[index], shuffled[other] = shuffled[other], shuffled[index]
    return tuple(shuffled)


def load_standard(name: str, limit: int | None):
    from datasets import load_dataset

    spec = BENCHMARKS[name]
    dataset = load_dataset(
        spec["dataset"], spec["config"], split=spec["split"],
        revision=spec["revision"],
    )
    if len(dataset) != spec["expected_rows"]:
        raise SystemExit(
            f"{name} expected {spec['expected_rows']} rows at the pinned revision, "
            f"found {len(dataset)}; refusing a drifted aggregate")
    selected = dataset.select(range(min(limit, len(dataset)))) if limit else dataset
    items = []
    for index, row in enumerate(selected):
        if name == "pubmedqa":
            state = {"question": row["question"], "context": row["context"]["contexts"]}
            target = spec["choices"].index(str(row["final_decision"]).lower())
        else:
            state = str(row[spec["text"]])
            target = int(row["label"])
        items.append(Item(f"{name}-{index}", spec["task"], state,
                          spec["choices"], target))
    source = {
        "dataset": spec["dataset"], "config": spec["config"],
        "split": spec["split"], "dataset_revision": spec["revision"],
        "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
        "expected_split_rows": spec["expected_rows"],
    }
    return items, source


def load_jevals(manifest: Path, limit: int | None, epochs: int):
    from datasets import load_dataset

    spec = json.loads(manifest.read_text())
    if len(spec["options"]) > MAX_CHOICES:
        raise SystemExit(
            f"{spec['id']} has {len(spec['options'])} choices; Trio-Spark accepts "
            f"at most {MAX_CHOICES}. No oracle shortlist will be used.")
    dataset = load_dataset(
        spec["dataset"], spec.get("config"), split=spec["split"],
        revision=spec["hf_revision"],
    )
    selected = spec["items"][:limit] if limit else spec["items"]
    items = []
    for epoch in range(epochs):
        for entry in selected:
            row = dataset[int(entry["row_idx"])]
            state = {field.split(".")[0]: _nested(row, field)
                     for field in spec["state_fields"]}
            canonical = json.dumps(state, ensure_ascii=False, separators=(",", ":"))
            if hashlib.sha256(canonical.encode()).hexdigest() != entry["state_sha256"]:
                raise SystemExit(f"state hash mismatch for {entry['item_id']}")
            choices = tuple(spec["options"])
            target_name = choices[int(entry["target"])]
            if spec["primitive"] == "choice":
                order_seed = 0 if epoch < 2 else epoch - 1
                choices = _jevals_shuffle(choices, entry["item_id"], order_seed)
            described = []
            for option in choices:
                criteria = spec.get("criteria")
                detail = criteria.get(option) if isinstance(criteria, dict) else None
                if isinstance(criteria, dict) and spec["primitive"] == "noul":
                    detail = criteria.get("true" if option == "yes" else "false")
                described.append(f"{option}: {detail}" if detail else option)
            items.append(Item(
                entry["item_id"], spec["instructions"], state, tuple(described),
                choices.index(target_name), spec["primitive"], epoch,
            ))
    return items, {
        "suite": "Jevals", "suite_version": spec["version"],
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest(),
        "dataset": spec["dataset"], "hf_revision": spec["hf_revision"],
        "dataset_fingerprint": getattr(dataset, "_fingerprint", None),
        "primitive": spec["primitive"], "epochs": epochs,
    }


def call(item: Item, run_id: str, timeout: float, retries: int, retry_base: float):
    choice_ids = tuple(f"c{index}" for index in range(len(item.choices)))
    choices = dict(zip(choice_ids, item.choices))
    idempotency = str(uuid.uuid5(
        uuid.NAMESPACE_URL, f"trio-spark-eval:{run_id}:{item.item_id}:{item.epoch}"))
    events = []
    started = time.perf_counter()
    for attempt in range(retries + 1):
        try:
            result = decide(
                task=item.task, state=item.state, choices=choices,
                timeout=timeout, session_id=f"eval:{run_id}",
                idempotency_key=idempotency,
            )
            break
        except TrioSparkError as error:
            if not error.retryable or attempt >= retries:
                error.retry_events = events
                raise
            if error.new_request_required:
                idempotency = str(uuid.uuid4())
            try:
                delay = min(60.0, max(0.0, float(error.retry_after)))
            except (TypeError, ValueError):
                delay = min(30.0, retry_base * (2 ** attempt))
            events.append({"attempt": attempt + 1, "code": error.code, "delay_s": delay})
            time.sleep(delay)
        except (OSError, TimeoutError) as error:
            if attempt >= retries:
                error.retry_events = events
                raise
            delay = min(30.0, retry_base * (2 ** attempt))
            events.append({
                "attempt": attempt + 1,
                "code": type(error).__name__,
                "delay_s": delay,
            })
            time.sleep(delay)
    else:
        raise RuntimeError("retry loop exhausted")
    probabilities_by_id = {
        entry["choice_id"]: float(entry["probability"])
        for entry in result["probabilities"]
    }
    if set(probabilities_by_id) != set(choice_ids):
        raise ValueError("response probabilities do not match the offered choices")
    probabilities = [probabilities_by_id[choice_id] for choice_id in choice_ids]
    if (any(not math.isfinite(value) or not 0 <= value <= 1
            for value in probabilities)
            or not math.isclose(sum(probabilities), 1.0, abs_tol=1e-3)):
        raise ValueError("response probabilities are invalid or do not sum to one")
    if result.get("choice_id") not in choice_ids:
        raise ValueError("response choice_id was not offered")
    prediction = choice_ids.index(result["choice_id"])
    result["benchmark_wall_ms"] = round((time.perf_counter() - started) * 1000, 2)
    return result, probabilities, prediction, events


def write_summary(records: dict, planned: int, benchmark: str, output: Path):
    rows = list(records.values())
    summary = summarize(rows, planned)
    if benchmark == "jevals":
        primitive = rows[0]["primitive"] if rows else "choice"
        summary["decision_score"] = (
            decision_score(rows, primitive) if summary["comparable_overall"] else None)
        summary["decision_score_status"] = (
            "comparable" if summary["comparable_overall"]
            else "not_comparable_incomplete_coverage")
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--benchmark", required=True,
                        choices=[*BENCHMARKS, "jevals"])
    parser.add_argument("--manifest", type=Path,
                        default=ROOT / "evals/manifests/jevals-0.1.0-pubmedqa.json")
    parser.add_argument("--epochs", type=int, default=5)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--pace", type=float, default=1.1,
                        help="seconds after each persisted response")
    parser.add_argument("--timeout", type=float, default=45)
    parser.add_argument("--retries", type=int, default=5)
    parser.add_argument("--retry-base", type=float, default=2.0)
    args = parser.parse_args()
    if not os.environ.get("TRIO_SPARK_API_KEY"):
        raise SystemExit("set TRIO_SPARK_API_KEY; it is read from the environment and never saved")
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    if args.pace < 0:
        parser.error("--pace must be non-negative")
    if args.timeout <= 0:
        parser.error("--timeout must be positive")
    if args.retries < 0:
        parser.error("--retries must be non-negative")
    if args.benchmark == "jevals":
        items, source = load_jevals(args.manifest, args.limit, args.epochs)
    else:
        items, source = load_standard(args.benchmark, args.limit)
    if any(not 2 <= len(item.choices) <= MAX_CHOICES for item in items):
        raise SystemExit("benchmark item violates the production 2–8 choice contract")

    args.output.mkdir(parents=True, exist_ok=True)
    raw_path = args.output / "raw.jsonl"
    manifest_path = args.output / "manifest.json"
    if raw_path.exists() and not manifest_path.exists():
        raise SystemExit("raw.jsonl exists without manifest.json; refusing an ambiguous resume")
    existing_manifest = (
        json.loads(manifest_path.read_text()) if manifest_path.exists() else None)
    if existing_manifest and not isinstance(existing_manifest.get("run_id"), str):
        raise SystemExit("manifest.json has no valid run_id; refusing an ambiguous resume")
    records = {}
    if raw_path.exists():
        for line in raw_path.read_text().splitlines():
            record = json.loads(line)
            records[(record["item_id"], int(record.get("epoch", 0)))] = record
    run_id = (
        existing_manifest.get("run_id") if existing_manifest
        else uuid.uuid4().hex[:12]
    )
    proposed_manifest = {
        "benchmark": args.benchmark, "source": source,
        "endpoint": "https://platform.machinefi.com/api/spark/v1/decisions",
        "model": MODEL, "planned_requests": len(items),
        "pace_s_after_response": args.pace,
        "timeout_s": args.timeout,
        "max_retries": args.retries,
        "retry_base_s": args.retry_base,
        "run_id": run_id,
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "git_commit": _git_commit(), "python": sys.version,
        "platform": platform.platform(),
        "datasets_version": importlib.metadata.version("datasets"),
    }
    if existing_manifest:
        manifest = existing_manifest
        contract = (
            "benchmark", "source", "endpoint", "model", "planned_requests",
            "pace_s_after_response", "timeout_s", "max_retries", "retry_base_s",
            "run_id",
        )
        changed = [key for key in contract if manifest.get(key) != proposed_manifest.get(key)]
        if changed:
            raise SystemExit(
                "resume contract differs from manifest.json for: " + ", ".join(changed))
    else:
        manifest = proposed_manifest
        manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    with raw_path.open("a") as raw_file:
        for position, item in enumerate(items, 1):
            key = (item.item_id, item.epoch)
            if key in records and not records[key].get("error"):
                continue
            record = {
                "item_id": item.item_id, "epoch": item.epoch,
                "target": item.target, "primitive": item.primitive,
                "n_choices": len(item.choices),
            }
            try:
                response, probabilities, prediction, retries = call(
                    item, run_id, args.timeout, args.retries, args.retry_base)
                record.update({
                    "prediction": prediction, "probabilities": probabilities,
                    "latency_ms": response.get("latency_ms"),
                    "model_version": response.get("model_version"),
                    "request_attempts": len(retries) + 1,
                    "retry_events": retries, "raw_response": response,
                })
            except TrioSparkError as error:
                record.update({
                    "error": f"TrioSparkError: {error.code}",
                    "http_status": error.status, "retryable": error.retryable,
                    "request_id": error.request_id,
                    "retry_events": getattr(error, "retry_events", []),
                })
            except (OSError, TimeoutError, ValueError, KeyError) as error:
                record["error"] = f"{type(error).__name__}: {error}"
                record["retry_events"] = getattr(error, "retry_events", [])
            if record.get("error"):
                record["request_attempts"] = len(record["retry_events"]) + 1
            raw_file.write(json.dumps(record, separators=(",", ":")) + "\n")
            raw_file.flush()
            records[key] = record
            write_summary(records, len(items), args.benchmark, args.output)
            if record.get("error"):
                raise SystemExit(
                    f"fail-stop at {item.item_id} epoch {item.epoch}: {record['error']}; "
                    "rerun the same command to resume")
            if position % 10 == 0:
                print(f"{position}/{len(items)}", flush=True)
            if args.pace:
                time.sleep(args.pace)
    summary = write_summary(records, len(items), args.benchmark, args.output)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
