# Ticket Rush: routing support tickets

This demo has Trio-Spark v1.3 route 1,000 customer-support tickets into eight team queues, such as Orders, Refunds and Talk to a person. Each ticket gets one decision, and each decision returns a probability for every queue. If the top probability is below 0.6, the ticket goes to a human review queue.

In the recorded run, all 1,000 tickets were routed in 6 min 47 s. 94.7% matched the dataset's human label, 33 went to review, and the model cost was $0.0050. The video is a time-lapse of that run.

[Watch the MP4](../../assets/demos/Trio-Spark-v1.3-Ticket-Rush.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.3-Ticket-Rush-poster.jpg) · [Evidence](evidence.json)

## Run it

Requirements: Python 3.9 or later. No other packages are needed.

```bash
export TRIO_SPARK_API_KEY=tf_...
python3 demos/ticket-rush/run.py -n 100
```

The runner sends each ticket in [`tickets.json`](tickets.json) to the public System One endpoint (`trio-spark-v1.3`). It prints each routing and its confidence, then the totals. Every result is saved to `ticket-rush-results.jsonl`. Your API key is read from the environment and is never written to output.

Leave out `-n` to run all 1,000 tickets. At the published price of $0.042 per million input tokens, a full run costs about half a cent.

## How a ticket is asked

```json
{
  "model": "trio-spark-v1.3",
  "state": "i try to track purchase #90377",
  "questions": {
    "queue": {
      "type": "choice",
      "instructions": "Route this customer support ticket to the right team queue.",
      "criteria": {
        "account": "Account: sign-up, login, password, profile, deleting or switching accounts",
        "orders": "Orders: placing, changing, cancelling or tracking an order",
        "...": "six more queues, listed in tickets.json"
      }
    }
  }
}
```

## Scope and data

The recording was made through the protected production inference origin, using the same deployed model, rather than through the public customer API. A per-ticket log was not kept for that run, so [`evidence.json`](evidence.json) records the totals from its final screen. Running `run.py` gives you a full per-ticket log of your own.

Tickets come from the [Bitext customer-support dataset](https://huggingface.co/datasets/bitext/Bitext-customer-support-llm-chatbot-training-dataset), licensed [CDLA-Sharing-1.0](https://cdla.dev/sharing-1-0/). Its template placeholders, such as an order number, were filled with sample values. Its 11 categories were mapped onto 8 queues: for example, invoice, payment and cancellation-fee intents all go to Billing and payments. `tickets.json` is shared under CDLA-Sharing-1.0, as described in [ATTRIBUTION.md](ATTRIBUTION.md); the demo code is Apache-2.0.

This is a single demo run on synthetic-style tickets, not a benchmark. Real ticket traffic is messier, and the review threshold should be tuned on your own data.
