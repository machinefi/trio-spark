# Robot arm

Trio-Spark repeatedly chooses among the currently eligible manipulation skills. MuJoCo executes the selected move and supplies the next measured state. The physical success check and forbidden-contact guard are independent of the model.

## Reproduce

```bash
git clone https://github.com/FBddcz/embodied-jev.git
cd embodied-jev
git checkout f08de2e4e20d6cd69fea9c57ac1062c3ef510f1e
git apply ../trio-spark.patch
uv sync
export TRIO_SPARK_API_KEY=tf_...
export EMBODIED_LOCAL_URL=https://platform.machinefi.com/api/spark/v1/decisions
export EMBODIED_LOCAL_KEY="$TRIO_SPARK_API_KEY"
export EMBODIED_LOCAL_MODEL="Trio-Spark v1.0"
uv run embodied-jev benchmark --provider local --tasks transfer --seeds 0 \
  --control-mode skills --observation-mode privileged --threshold 0 \
  --max-cycles 15 --output runs/spark.json
```

The published run completed the transfer in 8 executed skills. The production API made 13 calls in 13.68 s. The final simulator state passed the physical success check with 0 forbidden contacts.
