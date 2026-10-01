from __future__ import annotations

import math
from collections import Counter


def summarize(rows: list[dict], expected_n: int | None = None) -> dict:
    valid = [r for r in rows if not r.get("error")]
    planned = expected_n if expected_n is not None else len(rows)
    if not valid:
        return {"n": len(rows), "n_planned": planned, "valid": 0,
                "valid_output_rate": 0.0, "coverage": 0.0,
                "comparable_overall": False}
    k = len(valid[0]["probabilities"])
    def scored_prediction(row):
        probabilities = row["probabilities"]
        if row.get("primitive") == "noul" and len(probabilities) == 2 \
                and probabilities[0] == probabilities[1]:
            return -1  # Jevals defines an exact 0.5 yes/no result as no pick.
        if row.get("primitive") == "score":
            peak = max(probabilities)
            return probabilities.index(peak)  # Ordered-score ties go lower.
        return row["prediction"]  # Choice ties use the model's returned pick.
    correct = [int(scored_prediction(r) == r["target"]) for r in valid]
    confidences = [max(r["probabilities"]) for r in valid]
    brier = []
    nll = []
    rps = []
    for r in valid:
        p, y = r["probabilities"], r["target"]
        brier.append(sum((pk - int(i == y)) ** 2 for i, pk in enumerate(p)))
        nll.append(-math.log(max(p[y], 1e-12)))
        if k > 1:
            rps.append(sum((sum(p[:i + 1]) - int(y <= i)) ** 2
                           for i in range(k - 1)) / (k - 1))
    ece = 0.0
    for bucket in range(10):
        # Jevals: min(9, floor(round(100*c) / 10)); avoid Python's
        # banker's-rounding behavior at exact half points.
        idx = [i for i, c in enumerate(confidences)
               if min(9, math.floor(math.floor(100 * c + 0.5) / 10)) == bucket]
        if idx:
            ece += len(idx) / len(valid) * abs(
                sum(correct[i] for i in idx) / len(idx)
                - sum(confidences[i] for i in idx) / len(idx))
    service_latencies = sorted(float(r["latency_ms"]) for r in valid
                               if r.get("latency_ms") is not None)
    wall_latencies = sorted(
        float((r.get("raw_response") or {}).get("benchmark_wall_ms",
                                                r.get("latency_ms")))
        for r in valid
        if (r.get("raw_response") or {}).get("benchmark_wall_ms",
                                             r.get("latency_ms")) is not None)
    def pct(values: list[float], q: float):
        if not values:
            return None
        # Nearest-rank percentile, matching Jevals methodology.
        return values[max(0, math.ceil(q * len(values)) - 1)]
    billed_nano = 0
    billed_tokens = 0
    billing_records = 0
    for r in valid:
        raw = r.get("raw_response") or {}
        try:
            billing = raw.get("billing")
            if isinstance(billing, dict) and "amount_nano_usd" in billing:
                billed_nano += int(billing["amount_nano_usd"])
                billing_records += 1
            billed_tokens += int(raw.get("usage", {}).get("billed_input_tokens", 0))
        except (TypeError, ValueError):
            pass
    by_item = {}
    for index, r in enumerate(valid):
        item_id = r.get("item_id", f"single-{index}")
        by_item.setdefault(item_id, {})[int(r.get("epoch", 0))] = scored_prediction(r)
    repeated = [epochs for epochs in by_item.values() if len(epochs) > 1]
    exact_pairs = [epochs for epochs in repeated if 0 in epochs and 1 in epochs]
    stability = None
    if repeated:
        stability = {
            "items_with_repeats": len(repeated),
            "any_answer_change_rate": sum(len(set(x.values())) > 1 for x in repeated) / len(repeated),
            "epoch_0_1_flip_rate": (
                sum(x[0] != x[1] for x in exact_pairs) / len(exact_pairs)
                if exact_pairs else None),
            "choice_order_flip_rate": (
                sum(len({x[e] for e in (0, 2, 3, 4)}) > 1
                    for x in repeated if all(e in x for e in (0, 2, 3, 4)))
                / sum(all(e in x for e in (0, 2, 3, 4)) for x in repeated)
                if valid[0].get("primitive") == "choice"
                and any(all(e in x for e in (0, 2, 3, 4)) for x in repeated)
                else None),
        }
    coverage = len(valid) / planned if planned else 0.0
    shared_threshold = {"noul": 0.91, "choice": 0.96}.get(
        valid[0].get("primitive"))
    shared_gate = None
    if shared_threshold is not None:
        gated = [i for i, confidence in enumerate(confidences)
                 if confidence >= shared_threshold]
        shared_gate = {
            "threshold": shared_threshold,
            "decisions": len(gated),
            "coverage": len(gated) / planned if planned else 0.0,
            "accuracy": (sum(correct[i] for i in gated) / len(gated)
                         if gated else None),
        }
    handoff = None
    for step in range(101):
        threshold = step / 100
        gated = [i for i, confidence in enumerate(confidences)
                 if confidence >= threshold]
        if len(gated) >= 100:
            gated_accuracy = sum(correct[i] for i in gated) / len(gated)
            if gated_accuracy >= 0.95:
                handoff = {"threshold": threshold, "decisions": len(gated),
                           "coverage": len(gated) / planned,
                           "accuracy": gated_accuracy}
                break
    return {
        "n": len(rows), "n_planned": planned, "valid": len(valid),
        "valid_output_rate": len(valid) / len(rows),
        "coverage": coverage,
        "comparable_overall": coverage == 1.0 and len(rows) == planned,
        "terminal_errors": dict(Counter(r.get("http_status", r.get("error", "unknown"))
                                        for r in rows if r.get("error"))),
        "accuracy": sum(correct) / len(valid),
        "ece_10_bin": ece,
        "ece_10_bin_points": ece * 100,
        "multiclass_brier": sum(brier) / len(brier),
        "nll": sum(nll) / len(nll),
        "ranked_probability_score": sum(rps) / len(rps) if rps else None,
        "latency_ms": {"basis": "harness_wall_including_transport_retries",
                       "p50": pct(wall_latencies, .5),
                       "p95": pct(wall_latencies, .95)},
        "service_reported_latency_ms": {"p50": pct(service_latencies, .5),
                                        "p95": pct(service_latencies, .95)},
        "model_versions": dict(Counter(str(r.get("model_version")) for r in valid)),
        "billing": {
            "records": billing_records,
            "total_billed_input_tokens": billed_tokens,
            "total_amount_nano_usd": billed_nano if billing_records else None,
            "total_cost_usd": billed_nano / 1_000_000_000 if billing_records else None,
            "cost_usd_per_1k_decisions": (
                billed_nano / 1_000_000_000 / billing_records * 1000
                if billing_records else None),
        },
        "repeat_stability": stability,
        "shared_confidence_gate": shared_gate,
        "handoff_at_95_accuracy": handoff,
    }


def decision_score(rows: list[dict], primitive: str) -> float | None:
    """Jevals 0.1.0 score: 100 * (1 - model loss / label-prior loss)."""
    valid = [r for r in rows if not r.get("error")]
    # Jevals counts malformed/refused requests. A valid-only score would be
    # optimistic, so do not emit Decision Score for an incomplete run.
    if not valid or len(valid) != len(rows):
        return None
    k = len(valid[0]["probabilities"])
    counts = Counter(r["target"] for r in valid)
    prior = [counts[i] / len(valid) for i in range(k)]
    def loss(p, y):
        if primitive == "score":
            return sum((sum(p[:i + 1]) - int(y <= i)) ** 2
                       for i in range(k - 1)) / (k - 1)
        return sum((pk - int(i == y)) ** 2 for i, pk in enumerate(p))
    model_loss = sum(loss(r["probabilities"], r["target"]) for r in valid) / len(valid)
    prior_loss = sum(loss(prior, r["target"]) for r in valid) / len(valid)
    return 100 * (1 - model_loss / prior_loss) if prior_loss else None
