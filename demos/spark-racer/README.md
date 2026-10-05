# Spark’s Little Road Trip

A small, earnest robot driver in a warm MachineFi toy world. Solid embossed coins, expressive coral neighbours, and a visible bonk when a collision happens.

[Watch the new recording](../../assets/demos/Trio-Spark-v1.1-Little-Road-Trip.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.1-Little-Road-Trip-poster.png) · [Recording evidence](recording-evidence-polished.json)

Re-recorded on the production Tesla T4 after the visual redesign: 21 applied model decisions, 4 coins, 1 collision. The protected production inference origin was used for recording; the runnable client below defaults to the customer API. The 45-second game is continuous. This is one illustrative run, not a benchmark.

A screenshot-driven arcade racer for Trio-Spark v1.1. The model picks an absolute lane from a JPEG of the road. The simulation continues while inference runs; steering interpolates toward the returned lane. No obstacle coordinates are sent to the model and there is no scripted avoidance fallback.

## Run locally

```sh
export TRIO_SPARK_API_KEY='your-server-side-key'
python3 demos/spark-racer/server.py
# Open http://127.0.0.1:8878 and click Let Spark drive.
```

Python 3.9+; standard library only. The key stays server-side. The server binds to loopback and checks browser origins. It is a local demo, not a public multi-user service.

Each race lasts 45 seconds. Three choices: left, center, right. Red cars are obstacles; gold rings are coins. A fixed course (`showcase-course-v1`) rotates the open lane through center, left, right, center, right, left. Waves spawn every 8.2 seconds independently of model predictions. Scores are illustrative gameplay, not an accuracy benchmark.

The default call budget is 100 per server process (`RACER_MAX_CALLS`). One request is in flight at a time, with 300 ms between responses and the next capture. Inference failure stops the run; there is no scripted fallback. A late result after the finish is not applied but may still complete and consume usage.

Frames, hashes, raw API responses and game outcomes are saved under `racer-evidence/` (`RACER_OUTPUT` overrides it). Keep logs private unless reviewed for publication. Do not commit credentials. Public client calls use the normal metered API; make sure the account has trial calls or balance.

## Recorded demonstration

The release recording is captured from a real browser running this game continuously. Its accompanying evidence notes identify the serving route, hardware, applied decisions and request timings. Screenshot encoding, network latency, server processing and browser scheduling all contribute to the control loop. This is a deliberately paced arcade scenario, not autonomous-driving validation.

All graphics are original Canvas drawings; no third-party game art or soundtrack is required.
