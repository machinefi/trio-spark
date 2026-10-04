# Crossing Phase — sampled video decisions

This demo asks Trio-Spark v1.1 which road users are visibly moving through the center of Shibuya Crossing. Six chronological decisions use four frames sampled across each 3-second window. The choices are mutually exclusive: motor vehicles only, pedestrians only, both, neither, or unclear.

The recorded run follows a pedestrian wave through five windows, then identifies both pedestrians and motor vehicles moving in the final window. Results appear only after the latest sampled frame plus the measured request time. The 30-second replay preserves those timings and holds the final frame for readability; it does not accelerate or backdate results.

[Watch the MP4](../../assets/demos/Trio-Spark-v1.1-Crossing-Phase.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.1-Crossing-Phase-poster.jpg) · [Evidence](evidence.json)

## Run it

Requirements: Python 3.11+, Pillow, OpenCV, `ffmpeg`, and `ffprobe`.

```bash
export TRIO_SPARK_API_KEY=tf_...
python3 demos/crossing-phase/run.py all
```

The runner downloads the attributed source, verifies its SHA-256, extracts the locked frames, makes six sequential API calls without retries, saves every outcome, and renders only a complete run. The API key is read from the environment and is never written to evidence or output.

The included recording was captured through the protected production inference origin, using the same deployed model, rather than the public customer API and wallet path. Its provenance is explicit in `evidence.json`. The reusable runner above targets the public customer API.

The recorded final run had a 3,533.5 ms median wall time and a 2,867.9–4,643.7 ms range. These are capture measurements, not a general latency claim.

## Scope and source

This is a sampled-window observation demo. Four frames cannot guarantee detection of brief events between samples. It is not continuous monitoring, traffic control, or a safety determination.

The source is **Shibuya Crossing, Tokyo, Japan (video)** by Basile Morin, from [Wikimedia Commons](https://commons.wikimedia.org/wiki/File:Shibuya_Crossing,_Tokyo,_Japan_(video).webm), licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Attribution is encoded in the video and documented in [ATTRIBUTION.md](ATTRIBUTION.md). The MP4 and poster are shared under CC BY-SA 4.0; demo code remains Apache-2.0.
