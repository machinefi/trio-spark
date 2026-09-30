# Trio-Spark API reference

Trio-Spark v1.0 is a hosted Choice decision model. A request describes the
current state and 2–8 actions the application is allowed to take. The response
selects one action and returns a probability for every supplied choice.

The production API runs Trio-Spark directly. It does not call TypeSafe Jev or
another third-party decision model during inference.

## Endpoint

```text
POST https://platform.machinefi.com/api/spark/v1/decisions
```

Every request requires these headers:

```http
Authorization: Bearer tf_...
Content-Type: application/json
Idempotency-Key: 8-to-128-safe-ASCII-characters
```

Create or revoke keys in the [API Keys console](https://platform.machinefi.com/spark/keys).
Keep keys in a server-side secret store and never ship them in browser code.

`Idempotency-Key` may contain letters, digits, `.`, `_`, `:`, and `-`. Repeating
the same request with the same key returns the retained result without charging
again. Reusing a key for different input returns `409 idempotency_conflict`.

## Request

```json
{
  "model": "trio-spark-preview",
  "task": "Keep the machine safe while completing the operation.",
  "state": {
    "temperature_c": 84,
    "load_pct": 91,
    "vibration": "rising"
  },
  "choices": [
    {"id": "continue", "description": "Continue at the current speed"},
    {"id": "slow", "description": "Reduce speed and keep observing"},
    {"id": "stop", "description": "Stop the machine now"}
  ]
}
```

| Field | Type | Required | Contract |
|---|---|---:|---|
| `model` | string | yes | Must be `trio-spark-preview` |
| `task` | string | yes | Non-empty decision instruction |
| `state` | string or JSON object | yes | Current structured environment state |
| `choices` | array | yes | 2–8 unique choices in caller-defined order |
| `choices[].id` | string | yes | 1–64 letters, digits, `_`, or `-` |
| `choices[].description` | string | yes | Non-empty action description |

The tokenized model input may contain at most 1,024 tokens. The HTTP JSON body
may contain at most 65,536 bytes. Inputs above either limit are rejected rather
than silently truncated.

## Response

```json
{
  "request_id": "req_example",
  "model": "trio-spark-preview",
  "model_version": "trio-spark-v1.0",
  "choice_id": "slow",
  "probabilities": [
    {"choice_id": "continue", "probability": 0.08},
    {"choice_id": "slow", "probability": 0.79},
    {"choice_id": "stop", "probability": 0.13}
  ],
  "confidence": 0.79,
  "disposition": "decide",
  "usage": {"billed_input_tokens": 87},
  "billing": {
    "amount_nano_usd": "3654",
    "currency": "USD",
    "mode": "paid"
  },
  "latency_ms": 137
}
```

| Field | Meaning |
|---|---|
| `choice_id` | ID of the selected choice |
| `probabilities` | One probability per supplied choice, in request order |
| `confidence` | Probability assigned to the selected choice |
| `disposition` | `decide`, `review`, or `abstain` |
| `latency_ms` | Reported model service latency; client network time is additional |
| `usage.billed_input_tokens` | Input tokens used for billing |
| `billing.mode` | `trial` or `paid` |

Callers should handle `review` and `abstain` explicitly and validate the selected
action against the current legal action set before executing it.

## Errors

Errors use one JSON shape:

```json
{
  "error": {
    "code": "rate_limited",
    "message": "Request limit reached.",
    "retryable": true
  }
}
```

Some errors also include `request_id` or `new_request_required`.

| HTTP | Typical code | Meaning |
|---:|---|---|
| 400 | `invalid_input`, `invalid_idempotency_key` | Malformed JSON or request contract violation |
| 401 | `unauthenticated` | Missing, revoked, or invalid API key |
| 402 | `insufficient_balance` | Add credit before retrying |
| 409 | `idempotency_conflict`, `in_progress`, `result_expired` | Follow the message and idempotency guidance |
| 413 | `too_large` | HTTP request body exceeds the limit |
| 429 | `rate_limited` | Retry after the `Retry-After` interval |
| 503 | `unavailable` | Temporary service or capacity failure; retry with backoff |
| 504 | `timeout` | Request body or upstream operation timed out |

Do not automatically retry a response when `retryable` is `false`. If
`new_request_required` is `true`, generate a new idempotency key before retrying.

## Pricing and trial

- $0.042 per million billed input tokens
- No generated output-token charge
- 100 free decisions for a newly registered account

The account console is the source of truth for balances, usage, and current
commercial terms.

## Complete cURL example

```bash
curl https://platform.machinefi.com/api/spark/v1/decisions \
  -H "Authorization: Bearer $TRIO_SPARK_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "model": "trio-spark-preview",
    "task": "Choose the safest useful next move.",
    "state": {"temperature_c": 84, "load_pct": 91},
    "choices": [
      {"id": "continue", "description": "Continue unchanged"},
      {"id": "slow", "description": "Reduce speed and observe"},
      {"id": "stop", "description": "Stop immediately"}
    ]
  }'
```

The dependency-free [Python client](../clients/python/trio_spark.py) implements
the same contract.
