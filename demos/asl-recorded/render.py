#!/usr/bin/env python3
"""Render an honest prerecorded ASL experiment from source clips and evidence."""
from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from pathlib import Path

FPS = 30
WIDTH, HEIGHT = 1280, 720
FINAL_HOLD_SECONDS = 3.0


@dataclass(frozen=True)
class Case:
    evidence: Path
    source: Path
    expected: str
    actual: str
    score: float
    status: str
    sample_times_ms: tuple[int, ...]
    latency_ms: float

    @property
    def result_at_seconds(self) -> float:
        return self.sample_times_ms[-1] / 1000 + self.latency_ms / 1000

    @property
    def duration_seconds(self) -> float:
        return self.result_at_seconds + FINAL_HOLD_SECONDS


def load_case(evidence_path: Path, source_root: Path) -> Case:
    payload = json.loads(evidence_path.read_text())
    case, result = payload["case"], payload["result"]
    times = tuple(int(value) for value in case["times_ms"])
    if len(times) != 4 or times != tuple(sorted(times)) or len(set(times)) != 4:
        raise ValueError(f"{evidence_path}: expected four strictly increasing samples")
    latency = float(result["latency_ms"])
    score = float(result.get("score", 0))
    if latency < 0 or not 0 <= score <= 1:
        raise ValueError(f"{evidence_path}: invalid timing or score")
    source = source_root / case["file"]
    if not source.is_file():
        raise FileNotFoundError(source)
    return Case(evidence_path, source, str(case["expected"]).upper(),
                str(result.get("label", result.get("status", "unclear"))).upper(),
                score, str(result["status"]), times, latency)


def render(cases: list[Case], output: Path) -> None:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont

    regular_path = "/System/Library/Fonts/Supplemental/Arial.ttf"
    bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    regular = ImageFont.truetype(regular_path, 24)
    small = ImageFont.truetype(regular_path, 19)
    bold = ImageFont.truetype(bold_path, 34)
    title = ImageFont.truetype(bold_path, 43)
    temporary = output.with_suffix(".silent.mp4")
    output.parent.mkdir(parents=True, exist_ok=True)
    writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), FPS, (WIDTH, HEIGHT))

    for case_index, case in enumerate(cases, 1):
        capture = cv2.VideoCapture(str(case.source))
        source_fps = capture.get(cv2.CAP_PROP_FPS) or FPS
        cached = None
        frame_count = round(case.duration_seconds * FPS)
        for frame_index in range(frame_count):
            elapsed = frame_index / FPS
            source_time = min(elapsed, case.sample_times_ms[-1] / 1000)
            capture.set(cv2.CAP_PROP_POS_FRAMES, round(source_time * source_fps))
            ok, frame = capture.read()
            if ok:
                cached = frame
            frame = cached if cached is not None else np.zeros((240, 320, 3), dtype=np.uint8)
            frame = cv2.resize(frame, (720, 540), interpolation=cv2.INTER_CUBIC)
            canvas = Image.new("RGB", (WIDTH, HEIGHT), "#071018")
            canvas.paste(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), (24, 106))
            draw = ImageDraw.Draw(canvas)
            draw.text((26, 24), "TRIO-SPARK v1.1", font=title, fill="#f4fbff")
            draw.text((760, 26), "Recorded ASL experiment · real model outputs", font=small, fill="#84d8ff")
            draw.rounded_rectangle((770, 105, 1254, 646), 22, fill="#101d29", outline="#29485c", width=2)
            draw.text((806, 140), f"CLIP {case_index}/{len(cases)}", font=small, fill="#84d8ff")
            draw.text((806, 183), "Expected word", font=small, fill="#93a8b7")
            draw.text((806, 216), case.expected, font=bold, fill="#ffffff")
            draw.text((806, 286), "Four full-clip samples", font=regular, fill="#c5d2db")
            draw.text((806, 324), "Inference starts after last sample", font=small, fill="#93a8b7")
            if elapsed < case.sample_times_ms[-1] / 1000:
                status = "PLAYING SOURCE AT 1×"
                color = "#84d8ff"
            elif elapsed < case.result_at_seconds:
                status = "INFERENCE…"
                color = "#f3c969"
            else:
                status = "MODEL RESULT"
                color = "#63e6a5" if case.actual == case.expected else "#ffb86b"
            draw.text((806, 384), status, font=small, fill=color)
            if elapsed >= case.result_at_seconds:
                draw.text((806, 420), case.actual, font=title, fill=color)
                qualifier = "conditional within routed bank" if case.status == "recognized" else case.status.replace("_", " ")
                draw.text((806, 482), f"{case.score * 100:.1f}% · {qualifier}", font=small, fill="#dceaf2")
                draw.text((806, 523), f"Recorded request time: {case.latency_ms:.0f} ms", font=small, fill="#dceaf2")
                draw.text((806, 565), "FINAL FRAME · RECORDED REPLAY", font=small, fill="#84d8ff")
            else:
                remaining = max(0, case.result_at_seconds - elapsed)
                draw.text((806, 430), f"Result available in {remaining:.1f}s", font=regular, fill="#dceaf2")
            draw.text((26, 671), "E5SUON / Wikimedia Commons · CC BY-SA 3.0 · Prerecorded source", font=small, fill="#8197a5")
            writer.write(cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR))
        capture.release()
    writer.release()
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(temporary),
                    "-c:v", "libx264", "-crf", "21", "-preset", "medium", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", str(output)], check=True)
    temporary.unlink()
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", "8", "-i", str(output),
                    "-frames:v", "1", str(output.with_suffix(".jpg"))], check=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", type=Path, action="append", required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    render([load_case(path, args.source_root) for path in args.evidence], args.output)


if __name__ == "__main__":
    main()
