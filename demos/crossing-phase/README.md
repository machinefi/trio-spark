# Crossing Phase — sampled video decision

This demo asks Trio-Spark v1.1 to identify the visible change across six chronological 3-second windows, each represented by four frames at Shibuya Crossing. It is a bounded observation demo. It is not continuous monitoring, a traffic-signal reading, or a traffic-safety system.

The source is **Shibuya Crossing, Tokyo, Japan (video)** by Basile Morin, licensed [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). See the [Wikimedia Commons source page](https://commons.wikimedia.org/wiki/File:Shibuya_Crossing,_Tokyo,_Japan_(video).webm). The runner verifies the original file SHA-256 before extracting any frames.

## Run

Requirements: Python 3.11+, Pillow, OpenCV, `ffmpeg`, and `ffprobe`.

```bash
export TRIO_SPARK_API_KEY=tf_...
python3 demos/crossing-phase/run.py all
```

The default output is `runs/crossing-phase/`. The runner saves source and frame hashes, the exact task and choices, raw production response, wall latency, model identities, billed tokens, a 26-second MP4, and its poster. It refuses to render without complete evidence from a real `trio-spark-v1.1` response.

Six production API calls are made without retries; every success or failure is retained. The key is read only from the environment and is never written to evidence or command output.

## Recorded production-origin run

The recorded replay contains six chronological decisions from the protected production inference origin. It does **not** verify the public customer API, wallet, or billing path. The first capture attempt made ten origin calls but the capture tool rejected their responses because it expected wrapper-only fields; those ten capture-tool errors are disclosed in `evidence.json` and are not labeled as API or model failures. No response from that attempt is used in the video.

The corrected attempt completed six calls without an origin API error. The model selected `pedestrians_crossing` for all six windows. That is plausible in the earlier windows, while the final sparse window makes the last classification a material qualitative error. The complete sequence is retained without retry or selection. Treat this artifact as an honest integration and latency replay, not an accuracy showcase.

[Watch the 26-second MP4](../../assets/demos/Trio-Spark-v1.1-Crossing-Phase.mp4) · [Poster](../../assets/demos/Trio-Spark-v1.1-Crossing-Phase-poster.jpg) · [Evidence](evidence.json)

The MP4 and poster are adaptations of the attributed source and are distributed under CC BY-SA 4.0. Demo code remains Apache-2.0.
