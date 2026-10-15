# Comment Bouncer: moderation with a policy you can move

Trio-Spark v1.3 reads 600 live-chat comments and returns `P(hide)` for each one. A two-line policy, *send to review* and *auto-hide*, sorts every comment into shown, review or hidden. The probabilities are stored, so moving either line re-sorts all 600 comments instantly, without calling the model again.

In the recorded run, with review set at 0.30 and auto-hide at 0.70:

- 100 comments were hidden and 54 went to review.
- 78.7% of the comments human raters marked toxic were hidden or sent to review.
- 2.7% of the fine comments were wrongly auto-hidden.
- 88.0% of the auto-hidden comments were rated toxic by humans.
- Hide versus show at 0.5 matched human raters on 88.3% of comments.
- The run moved at 1.1 comments per second, and the model cost was $0.0017.

The video is a time-lapse that ends with the policy being moved three times.

[Watch the MP4](../../assets/demos/Trio-Spark-v1.3-Comment-Bouncer.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.3-Comment-Bouncer-poster.jpg) · [Evidence](evidence.json)

## Run it

Requirements: Python 3.9 or later. No other packages are needed.

```bash
export TRIO_SPARK_API_KEY=tf_...
python3 demos/comment-bouncer/run.py -n 100
```

Each comment in [`comments.json`](comments.json) becomes one `choice` question with the options `show` and `hide`, sent to the public System One endpoint. The runner prints `P(hide)` next to the human label. It then reports the same agreement figures for three policies (0.70, 0.40 and 0.95 auto-hide) from the stored probabilities, at no extra cost. You can set `--review-at` and `--hide-at`. Results are saved to `comment-bouncer-results.jsonl`.

For an interactive version with sliders, see the AI Comment Moderation Agent Streamlit app ([proposed to awesome-llm-apps](https://github.com/Shubhamsaboo/awesome-llm-apps/pull/1242)), which uses the same request.

## Scope and data

The recording was made through the protected production inference origin, using the same deployed model, rather than through the public customer API. A per-comment log was not kept for that run, so [`evidence.json`](evidence.json) records the figures from its final screen.

Comments come from the test split of [Civil Comments](https://huggingface.co/datasets/google/civil_comments) ([CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)). The sample keeps comments of 12–140 characters. It excludes links and political, religious and identity topics, and it is 25% toxic, meaning a human toxicity score of 0.5 or higher. In the recording, the text of hidden comments is blurred and the usernames are invented. See [ATTRIBUTION.md](ATTRIBUTION.md).

This is one demo run, not a moderation benchmark. Treat the review band as the place where people make the call.
