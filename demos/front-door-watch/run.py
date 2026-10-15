#!/usr/bin/env python3
"""Ask Trio-Spark about each Front Door Watch event, sampling the original stock clips.

Downloads the four clips credited in ATTRIBUTION.md (verified by SHA-256) on first run.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API_URL = "https://platform.machinefi.com/v1/systemone"
MODEL = "trio-spark-v1.3"
TASK = "You watch the front-door camera of a family home. Decide what is happening at the door."
STATE = "Camera: front door. Frames: a few seconds of video, oldest first."
CHOICES = {
    "family": "Someone from the household: walking up and opening the door to go in, or stepping out of the house",
    "delivery": "A delivery: a courier bringing a package to the door or leaving it there",
    "stranger": "An unknown person acting suspiciously: lurking, peering inside, or trying to get in",
    "clear": "Nobody at the door",
}
SOURCES = {
    "px6667264.mp4": ("https://videos.pexels.com/video-files/6667264/6667264-hd_1920_1080_25fps.mp4",
                      "bc3e62f4e629051857f76040dd4b94786221e1386d7825e7eb0b031cdcd30cf0"),
    "8729.mp4": ("https://assets.mixkit.co/videos/8729/8729-1080.mp4",
                 "f1c38ca876c486d4c8cd217d3b8affe151f859ae8eecc37dc4d3a6cdd0238e93"),
    "px6994430.mp4": ("https://videos.pexels.com/video-files/6994430/6994430-hd_1920_1080_30fps.mp4",
                      "45901e6597527284468b68755d04e71e642cce4d3384eb1ecef19efa7bbcbfd6"),
    "31375.mp4": ("https://assets.mixkit.co/videos/31375/31375-1080.mp4",
                  "b85f7abaecbf4fd74f20f65a8cb622a64b5353393b878f013a1d8a401b6fb634"),
}
# (clip file, trim start s, on-screen clock, expected answer)
EVENTS = [("px6667264.mp4", 0.0, "10:42 AM", "delivery"), ("8729.mp4", 1.5, "3:28 PM", "family"),
          ("px6994430.mp4", 1.0, "4:05 PM", "family"), ("31375.mp4", 1.0, "2:13 AM", "stranger")]
FRAME_OFFSETS_S = (2, 3, 4, 5)  # first seconds of motion in each event


class NoRedirect(urllib.request.HTTPRedirectHandler):
    # Keep the API key on the intended host even if a proxy redirects.
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def fetch(clip: Path) -> None:
    url, digest = SOURCES[clip.name]
    if not clip.is_file():
        clip.parent.mkdir(parents=True, exist_ok=True)
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Trio-Spark demo)"})
        with urllib.request.urlopen(request, timeout=120) as response:
            clip.write_bytes(response.read())
    if hashlib.sha256(clip.read_bytes()).hexdigest() != digest:
        raise SystemExit(f"{clip} does not match the recorded source; delete it and re-run.")


def frame(clip: Path, seconds: float, out: Path) -> bytes:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{seconds:.3f}", "-i", str(clip), "-frames:v", "1",
                    "-vf", "scale=512:288:force_original_aspect_ratio=increase,crop=512:288", "-q:v", "3", str(out)],
                   check=True)
    return out.read_bytes()


def decide(frames: list[tuple[int, bytes]], key: str) -> dict:
    question = {"type": "choice", "instructions": TASK, "criteria": CHOICES}
    media = {"type": "video", "frames": [{"mime_type": "image/jpeg", "data_base64": base64.b64encode(data).decode(),
                                          "timestamp_ms": ms} for ms, data in frames]}
    body = json.dumps({"model": MODEL, "state": STATE, "media": media, "questions": {"door": question}}).encode()
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "Idempotency-Key": str(uuid.uuid4())}
    for attempt in range(6):
        try:
            request = urllib.request.Request(API_URL, data=body, headers=headers, method="POST")
            with urllib.request.build_opener(NoRedirect()).open(request, timeout=60) as response:
                return json.load(response)
        except urllib.error.HTTPError as error:
            if error.code not in (429, 503) or attempt == 5:
                raise RuntimeError(f"{error.code}: {error.read().decode()[:200]}") from None
            time.sleep(1.5 * (attempt + 1))  # busy; retry with the same idempotency key


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clips", type=Path, default=Path("front-door-clips"), help="where source clips are kept")
    parser.add_argument("--out", type=Path, default=Path("front-door-watch-results.json"))
    args = parser.parse_args()
    key = os.environ.get("TRIO_SPARK_API_KEY")
    if not key:
        raise SystemExit("Set TRIO_SPARK_API_KEY first.")

    results = []
    with tempfile.TemporaryDirectory() as scratch:
        for index, (name, start, clock, expected) in enumerate(EVENTS):
            clip = args.clips / name
            fetch(clip)
            frames = [(offset * 1000, frame(clip, start + offset, Path(scratch) / f"{index}-{offset}.jpg"))
                      for offset in FRAME_OFFSETS_S]
            started = time.perf_counter()
            result = decide(frames, key)
            answer = result["answers"]["door"]
            results.append({"event": index, "clip": name, "clock_label": clock, "expected": expected,
                            "choice": answer["choice"], "probabilities": answer["probabilities"],
                            "input_tokens": result["usage"]["input_tokens"],
                            "wall_ms": round((time.perf_counter() - started) * 1000, 1)})
            p = answer["probabilities"][answer["choice"]]
            print(f"{clock:>8}  {answer['choice']:<9} {p:.2f}  (expected {expected})")
    args.out.write_text(json.dumps(results, indent=2) + "\n")
    print(f"{sum(r['choice'] == r['expected'] for r in results)}/{len(results)} as expected; saved {args.out}")


if __name__ == "__main__":
    main()
