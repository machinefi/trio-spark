#!/usr/bin/env python3
"""Moderate the Comment Bouncer sample through the public Trio-Spark API."""
from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API_URL = "https://platform.machinefi.com/v1/systemone"
MODEL = "trio-spark-v1.3"
PRICE_PER_INPUT_TOKEN = 0.042 / 1_000_000  # USD; output is not metered
DATA = Path(__file__).with_name("comments.json")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Keep the API key on the intended host even if a proxy redirects.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def p_hide(text: str, data: dict, key: str) -> tuple[float, int]:
    question = {"type": "choice", "instructions": data["task"],
                "criteria": {c["id"]: c["description"] for c in data["choices"]}}
    body = json.dumps({"model": MODEL, "state": text, "questions": {"moderation": question}}).encode()
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())}
    for attempt in range(6):
        try:
            request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                result = json.load(response)
            return result["answers"]["moderation"]["probabilities"]["hide"], result["usage"]["input_tokens"]
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == 5:
                raise RuntimeError(f"{error.code}: {error.read().decode()[:200]}") from None
            time.sleep(1.5 * (attempt + 1))  # busy; retry with the same idempotency key


def report(rows: list[dict], review_at: float, hide_at: float) -> str:
    toxic = [r for r in rows if r["human_label"] == "hide"]
    fine = [r for r in rows if r["human_label"] == "show"]
    hidden = [r for r in rows if r["p_hide"] >= hide_at]
    flagged = sum(r["p_hide"] >= review_at for r in toxic)
    agree = sum((r["p_hide"] >= 0.5) == (r["human_label"] == "hide") for r in rows)
    lines = [f"policy: review at {review_at:.2f}, auto-hide at {hide_at:.2f}",
             f"  hidden {len(hidden)}, to review {sum(review_at <= r['p_hide'] < hide_at for r in rows)}",
             f"  match human raters (hide vs. show at 0.5): {100 * agree / len(rows):.1f}%"]
    if toxic:
        lines.append(f"  toxic comments hidden or sent to review: {100 * flagged / len(toxic):.1f}%")
    if fine:
        lines.append(f"  fine comments wrongly auto-hidden: {100 * sum(r['p_hide'] >= hide_at for r in fine) / len(fine):.1f}%")
    if hidden:
        lines.append(f"  auto-hidden comments rated toxic by humans: {100 * sum(r['human_label'] == 'hide' for r in hidden) / len(hidden):.1f}%")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", type=int, default=600, help="number of comments (max 600)")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--review-at", type=float, default=0.30)
    parser.add_argument("--hide-at", type=float, default=0.70)
    parser.add_argument("--out", type=Path, default=Path("comment-bouncer-results.jsonl"))
    args = parser.parse_args()
    key = os.environ.get("TRIO_SPARK_API_KEY")
    if not key:
        raise SystemExit("Set TRIO_SPARK_API_KEY first.")

    data = json.loads(DATA.read_text())
    comments = data["comments"][: args.n]
    rows, tokens, started = [], 0, time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as pool, args.out.open("w") as out:
        for comment, (p, used) in zip(comments, pool.map(lambda c: p_hide(c["text"], data, key), comments)):
            rows.append({**comment, "p_hide": p})
            tokens += used
            out.write(json.dumps(rows[-1]) + "\n")
            print(f"{len(rows):4d}  P(hide)={p:.2f}  human={comment['human_label']:<4}  {comment['text'][:60]!r}")

    seconds = time.perf_counter() - started
    print(f"\n{len(rows)} comments, {len(rows) / seconds:.1f} per second, ${tokens * PRICE_PER_INPUT_TOKEN:.4f}")
    # The policy is applied to stored probabilities, so these re-sorts cost nothing.
    for review_at, hide_at in ((args.review_at, args.hide_at), (args.review_at, 0.40), (args.review_at, 0.95)):
        print(report(rows, min(review_at, hide_at), hide_at))


if __name__ == "__main__":
    main()
