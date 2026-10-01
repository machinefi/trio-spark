# 2048

Trio-Spark received the board and legal moves on every turn. Each returned top
choice was executed directly, with no heuristic fallback or edited move.

**Recorded production run:** 39 seconds · 26 model calls · score 180 · max tile
32 · 0 API errors

[Watch the run](../../assets/demos/Trio-Spark-v1.0-2048.mp4) ·
[Evidence](evidence.json) · [Sanitized decisions](transcript.sanitized.json)

The environment is adapted from
[`ARCJ137442/jev-2048`](https://github.com/ARCJ137442/jev-2048). See
[`ATTRIBUTION.md`](ATTRIBUTION.md) and [`LICENSE`](LICENSE).
