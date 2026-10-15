#!/usr/bin/env python3
"""Route the Ticket Rush support tickets through the public Trio-Spark API."""
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
TASK = "Route this customer support ticket to the right team queue."
REVIEW_BELOW = 0.6  # top-choice probability under this goes to a person
DATA = Path(__file__).with_name("tickets.json")


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Keep the API key on the intended host even if a proxy redirects.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def decide(text: str, queues: list[dict], key: str) -> dict:
    question = {"type": "choice", "instructions": TASK, "criteria": {q["id"]: q["description"] for q in queues}}
    body = json.dumps({"model": MODEL, "state": text, "questions": {"queue": question}}).encode()
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())}
    for attempt in range(6):
        started = time.perf_counter()
        try:
            request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                result = json.load(response)
            answer = result["answers"]["queue"]
            return {"choice": answer["choice"], "probabilities": answer["probabilities"],
                    "input_tokens": result["usage"]["input_tokens"],
                    "wall_ms": round((time.perf_counter() - started) * 1000, 1)}
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == 5:
                raise RuntimeError(f"{error.code}: {error.read().decode()[:200]}") from None
            time.sleep(1.5 * (attempt + 1))  # busy; retry with the same idempotency key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("-n", type=int, default=1000, help="number of tickets (max 1000)")
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--out", type=Path, default=Path("ticket-rush-results.jsonl"))
    args = parser.parse_args()
    key = os.environ.get("TRIO_SPARK_API_KEY")
    if not key:
        raise SystemExit("Set TRIO_SPARK_API_KEY first.")

    data = json.loads(DATA.read_text())
    tickets = data["tickets"][: args.n]
    done = agree = review = tokens = 0
    started = time.perf_counter()
    with ThreadPoolExecutor(args.concurrency) as pool, args.out.open("w") as out:
        for ticket, result in zip(tickets, pool.map(lambda t: decide(t["text"], data["queues"], key), tickets)):
            confidence = result["probabilities"][result["choice"]]
            done += 1
            agree += result["choice"] == ticket["gold"]
            review += confidence < REVIEW_BELOW
            tokens += result["input_tokens"]
            out.write(json.dumps({**ticket, **result, "needs_review": confidence < REVIEW_BELOW}) + "\n")
            print(f"{done:5d}  {result['choice']:<10} {confidence:.2f}  {ticket['text'][:70]}")

    seconds = time.perf_counter() - started
    print(f"\n{done} tickets in {seconds / 60:.1f} min · {100 * agree / done:.1f}% match the human label · "
          f"{review} to review · ${tokens * PRICE_PER_INPUT_TOKEN:.4f}")


if __name__ == "__main__":
    main()
