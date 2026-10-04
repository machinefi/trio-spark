# Prerecorded ASL experiment renderer

This renderer combines prerecorded source clips with previously captured Trio-Spark v1.1 evidence. It does not call an API. Each clip plays at 1× through its final sampled frame, inference begins after that frame, and the recorded result appears only after the evidence's measured request latency. A three-second final-frame hold keeps each result readable.

```bash
python3 demos/asl-recorded/render.py \
  --source-root /path/to/run \
  --evidence /path/to/run/hello1-result.json \
  --evidence /path/to/run/hello2-result.json \
  --output /path/to/Trio-Spark-v1.1-ASL-Experiment.mp4
```

Evidence may contain a recognized word, `no_sign`, `unclear`, or a mismatch. The renderer displays it unchanged. A score for a recognized word is labeled as conditional within the routed five-word bank. It is not presented as calibrated confidence across ten words.

This is a small prerecorded experiment. It does not establish ten-word accuracy, live-camera performance, full ASL translation, or language understanding.

## Attribution

The recorded source clips are by E5SUON on Wikimedia Commons and licensed [CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/). Rendered adaptations must retain that license and attribution. Source-specific URLs and hashes belong in the release evidence and attribution file accompanying the final media.

The first recorded artifact uses two independently sourced variants of the same word, **HELLO**. It demonstrates two correct outputs for those clips only; it is not a two-word or ten-word evaluation.
