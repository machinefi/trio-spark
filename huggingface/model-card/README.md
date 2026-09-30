---
tags:
- decision-model
- situated-world-model
- agents
- robotics
- world-model
- api
library_name: custom
pipeline_tag: text-classification
license: other
---

<p align="center">
  <img src="banner.svg" alt="Trio-Spark v1.0 — Fast judgment for the next move" width="100%">
</p>

# Trio-Spark v1.0

Trio-Spark is MachineFi's first **Situated World Model**: a fast decision model for agents acting inside a specific environment. Give it the current state and 2–8 allowed moves. One pass returns the selected move and a probability for every option.

Trio-Spark is available through a hosted API. Model weights and training code are not distributed from this repository.

[Try the playground](https://platform.machinefi.com/spark) · [API docs](https://platform.machinefi.com/spark/docs) · [Demos and clients](https://github.com/machinefi/trio-spark) · [Launch post](https://machinefi.com/blog/trio-spark-decisions-single-pass)

## What it does

```text
environment signals → structured state → Trio-Spark → next move → executor
                              ↑                         │
                              └──── fresh feedback ─────┘
```

Spark handles the bounded judgment step. Your application supplies the state, legal actions, executor, and safety controls. This pattern works across software agents, games, robots, and operational systems.

## API

Create an API key in the [Trio-Spark console](https://platform.machinefi.com/spark/keys).

```bash
curl https://platform.machinefi.com/api/spark/v1/decisions \
  -H "Authorization: Bearer $TRIO_SPARK_API_KEY" \
  -H "Content-Type: application/json" \
  -H "Idempotency-Key: $(uuidgen)" \
  -d '{
    "model": "trio-spark-preview",
    "task": "Keep the machine safe while completing the operation.",
    "state": {"temperature_c": 84, "load_pct": 91, "vibration": "rising"},
    "choices": [
      {"id": "continue", "description": "Continue at the current speed"},
      {"id": "slow", "description": "Reduce speed and keep observing"},
      {"id": "stop", "description": "Stop the machine now"}
    ]
  }'
```

The response contains `choice_id`, the complete probability distribution, confidence, usage, and latency. The public API model identifier remains `trio-spark-preview`; the product release is Trio-Spark v1.0.

## Measured examples

The public demo repository includes replayable evidence from production API runs.

| Environment | Result |
| --- | --- |
| Autonomous drone | 65 s, 25 calls, 75.7 m flown, 0 collisions, course completed |
| Browser agent | 4.002 s, 3 calls, requested item selected, autonomous `DONE` |
| Robot arm | 13.68 s, 13 calls, physical success, 0 forbidden contacts |

These demos send structured environment signals to Spark. They do not claim direct control from raw pixels.

## Evaluation snapshot

The launch evaluation measured the production API on four public classification datasets.

| Benchmark | Accuracy |
| --- | ---: |
| SST-2 | 92.89% |
| AG News | 88.46% |
| PubMedQA | 85.33% |
| TweetEval | 80.58% |

See the [launch post](https://machinefi.com/blog/trio-spark-decisions-single-pass) for the published context. A JevBench adapter and independent sealed-set evaluation request are maintained separately; no official JevBench score is claimed here until that evaluation is complete.

## Intended use

Trio-Spark is designed for frequent, low-latency decisions over an application-defined action set: routing, tool selection, GUI action choice, game moves, robot skills, and operational control.

It should sit behind application-level validation in safety-sensitive systems. The caller remains responsible for legal-action filtering, permissions, execution safeguards, and fallback behavior.

## Access and licensing

The API is a commercial hosted service. The [public Trio-Spark repository](https://github.com/machinefi/trio-spark) contains Apache-2.0 clients, demo integrations, and measured evidence. That code license does not grant access to model weights or training artifacts.
