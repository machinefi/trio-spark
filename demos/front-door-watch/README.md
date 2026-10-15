# Front Door Watch: sampled video decisions

A front-door camera sees four events in one day: a package dropped off, a parent and child coming home, a boy stepping out to look at packages, and a hooded figure with a flashlight peering in at night. For each event, four frames from the first seconds of motion go to Trio-Spark, which returns a probability for four behaviour-based options: household member, delivery, unknown person acting suspiciously, or nobody at the door. A suspicious stranger raises an alert, a delivery sends a notification, and family gets a quiet "welcome home".

In the recorded run, all four decisions matched the intended label with confidence of 0.999 or higher, at about 2.5 s per decision. The video plays in real time; if a decision is still running when an event ends, the video waits for it.

[Watch the MP4](../../assets/demos/Trio-Spark-v1.1-Front-Door-Watch.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.1-Front-Door-Watch-poster.jpg) · [Evidence](evidence.json)

## Run it

Requirements: Python 3.9 or later and `ffmpeg`.

1. Download the four clips listed in [ATTRIBUTION.md](ATTRIBUTION.md) into one folder, using the file names given there.
2. Run:

   ```bash
   export TRIO_SPARK_API_KEY=tf_...
   python3 demos/front-door-watch/run.py --clips path/to/clips
   ```

The runner takes frames at 2, 3, 4 and 5 s into each trimmed event, scaled to 512×288. It sends them as one `media.type: "video"` request to the public System One endpoint and prints the decision next to the expected label. It makes four API calls in total and saves the results to `front-door-watch-results.json`.

The runner uses `trio-spark-v1.3`. The recording used the v1.1 visual model, so your probabilities may differ slightly from those in `evidence.json`.

## Scope and source

The recording was made through the protected production inference origin, using the same deployed model, rather than through the public customer API. [`evidence.json`](evidence.json) holds every decision as the origin returned it: the choice, the full probabilities, the billed input tokens and the wall time.

The four stock clips were hand-picked and trimmed. Four sampled frames cannot capture what happens between samples. This is a demo, not a benchmark, a security product or a substitute for a monitored alarm. Clip credits and licences are listed in [ATTRIBUTION.md](ATTRIBUTION.md).
