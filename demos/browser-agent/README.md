# Browser agent

The agent turns the visible DOM into a bounded action set. A deterministic lexical shortlist keeps the decision within Spark's 8-choice contract; Spark selects the action. The executor rechecks page freshness before every click.

## Reproduce

```bash
git clone https://github.com/browser-use/jev-ultrafast.git
cd jev-ultrafast
git checkout 1231850a0bf1a0c0341fe408ef1668dbbfdfac46
git apply ../trio-spark.patch
uv sync
export TRIO_SPARK_API_KEY=tf_...
uv run python examples/run.py \
  --url https://books.toscrape.com/ \
  --goal "Open the Travel category, then open It's Only the Himalayas. Stop when its product page is visible."
```

The published run took 4.002 s end to end. Spark selected `Travel`, selected `It's Only the Himalayas`, then returned `DONE` after the product page became visible.
