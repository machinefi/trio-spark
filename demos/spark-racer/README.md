# Spark’s Little Road Trip

A small, earnest robot driver in a warm MachineFi toy world. Solid embossed coins, expressive coral neighbours, and a visible bonk when a collision happens.

[Watch the v1.1 recording](../../assets/demos/Trio-Spark-v1.1-Little-Road-Trip.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.1-Little-Road-Trip-poster.png) · [Recording evidence](recording-evidence-polished.json)

Re-recorded on the production Tesla T4 after the visual redesign: 19 applied model decisions, 4 coins, 1 collision. The protected production inference origin was used for recording; the runnable client below defaults to the customer API. The 45-second game is continuous. This is one illustrative run, not a benchmark.

A screenshot-driven arcade racer for Trio-Spark v1.1. The model picks an absolute lane from a JPEG of the road. The simulation continues while inference runs; steering interpolates toward the returned lane. No obstacle coordinates are sent to the model and there is no scripted avoidance fallback.

## Run locally

```sh
export TRIO_SPARK_API_KEY='your-server-side-key'
python3 demos/spark-racer/server.py
# Open http://127.0.0.1:8878 and click Let Spark drive.
```

Python 3.9+; standard library only. The key stays server-side. The server binds to loopback and checks browser origins. It is a local demo, not a public multi-user service.

Each race lasts 45 seconds. Three choices: left, center, right. Coral cars are obstacles; embossed gold coins are collectibles. A fixed course (`showcase-course-v1`) rotates the open lane through center, left, right, center, right, left. Waves spawn every 8.2 seconds independently of model predictions. Scores are illustrative gameplay, not an accuracy benchmark.

The default call budget is 100 per server process (`RACER_MAX_CALLS`). One request is in flight at a time, with 300 ms between responses and the next capture. Inference failure stops the run; there is no scripted fallback. A late result after the finish is not applied but may still complete and consume usage.

Frames, hashes, raw API responses and game outcomes are saved under `racer-evidence/` (`RACER_OUTPUT` overrides it). Keep logs private unless reviewed for publication. Do not commit credentials. Public client calls use the normal metered API; make sure the account has trial calls or balance.

## Recorded demonstration

The release recording is captured from a real browser running this game continuously. Its accompanying evidence notes identify the serving route, hardware, applied decisions and request timings. Screenshot encoding, network latency, server processing and browser scheduling all contribute to the control loop. This is a deliberately paced arcade scenario, not autonomous-driving validation.

All graphics are original Canvas drawings; no third-party game art or soundtrack is required.

## Recorded via the v1.2 API — October 8, 2026

[Watch the v1.2 recording](../../assets/demos/Trio-Spark-v1.2-Little-Road-Trip.mp4) · [GIF](../../assets/demos/Trio-Spark-v1.2-Little-Road-Trip.gif) · [Poster](../../assets/demos/Trio-Spark-v1.2-Little-Road-Trip-poster.png) · [Evidence](recording-evidence-v12.json)

This real public-API capture contains 35 seconds of continuous gameplay: 10 applied model decisions, 2 coins and 1 collision. Eleven requests succeeded; one result arrived after the game finished and was not applied. Screenshots were the only road input. The three raw model lane choices controlled steering, with no avoidance script or action override. The clip is one illustrative run, not a benchmark or a comparison.

The version-specific `index-v12.html`, `server_v12.py` and `record_public_v12.py` preserve the earlier artwork, course and physics. The recording uses explicit request-start spacing of at least 1.1 seconds, a 39-call replacement budget and 90-second total bound. Its unchanged visual route is pinned separately from the text model version. Actual captured source hashes are retained in the evidence; the later optional-import fix is identified separately.

The initial browser bootstrap made no API calls. A first capture received one valid visual response but stopped before applying it because the wrapper incorrectly checked the text version. That capture is retained in the private archive; the approved replacement shown here used the deployed visual version. No further gameplay run was selected or retried.

For a separately authorized recording, install neither a browser nor a model implicitly. Reuse an existing Playwright installation, local Chrome and its video encoder; set `RACER_BROWSER_EXECUTABLE` if necessary. Keep the API key in `TRIO_SPARK_API_KEY` on the server side. Recording performs metered requests and requires explicit approval; the command acknowledges that requirement:

```sh
python3 demos/spark-racer/record_public_v12.py \
  --ack-up-to-39-visual-calls --output /private/tmp/spark-v12-racer-your-run
```

CPU contract checks require no browser, Playwright package, model or API:

```sh
python3 -m unittest discover -s tests -p test_racer_v12.py -v
```

The historical v1.1 recording and its original evidence remain unchanged.
