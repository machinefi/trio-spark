# Visual gestures — Trio-Spark v1.1

This 22-second recorded demo pairs four chronological frames from two reviewed, CC BY 4.0 IPN Hand class clips with real Trio-Spark v1.1 production probabilities. It demonstrates bounded visual choices; it is not an accuracy evaluation or a live-latency claim.

Requirements: Python 3.11+, Pillow, `ffmpeg` and `ffprobe`.

## Prepare licensed inputs

```bash
python3 demos/visual-gestures/prepare.py --output /private/tmp/trio-spark-ipn-hand-prepared
```

`prepare.py` downloads only two small official GIFs, verifies their pinned SHA-256 hashes, crops each frame to the photographic camera region so the embedded class caption cannot leak the answer, extracts the exact submitted JPEGs, and writes `requests.json`. The crop rectangle is frozen in `source_manifest.json`. Keep the generated base64 request pack outside Git.

## Record production responses

Send each request in `requests.json` once through one declared serving path. Save every success and error. A renderable capture has `complete: true`, `production_api: true`, an explicit `serving_path` (`production_inference_origin` or `public_customer_api`), `public_customer_api_verified`, and the exact successful response under the matching `case_id` in a top-level `cases` array.

`record_public.py` is the reproducible customer path. It reads `TRIO_SPARK_API_KEY` from the environment, uses each frozen idempotency key once, rejects redirects, retains every outcome, and refuses to retry or overwrite evidence. Private operator adapters and internal serving identities do not belong in this public repository.

Use the same key to recover an uncertain public API response. Never invent or hand-edit probabilities. Do not include secrets, wallet data, private URLs, or raw base64 media in the sanitized response file. A direct production-origin capture must remain labeled as such and must not claim public billing or public API verification.

```bash
export TRIO_SPARK_API_KEY=your_api_key
python3 demos/visual-gestures/record_public.py \
  --prepared /private/tmp/trio-spark-ipn-hand-prepared \
  --output /private/tmp/trio-spark-ipn-hand-responses.json
```

## Render

```bash
python3 demos/visual-gestures/render.py \
  --prepared /private/tmp/trio-spark-ipn-hand-prepared \
  --responses /private/tmp/trio-spark-ipn-hand-responses.json \
  --output assets/demos/Trio-Spark-v1.1-Visual-Gestures.mp4
```

The renderer requires all responses to use the same recorded serving identity. You can optionally pin it with `--expected-model-version`. The renderer rejects any other identity, extra or missing cases, the wrong choice IDs, a non-normalized or non-finite probability distribution, and an invalid selected choice. Source class labels are cropped out of both model inputs and playback. See [ATTRIBUTION.md](ATTRIBUTION.md).
