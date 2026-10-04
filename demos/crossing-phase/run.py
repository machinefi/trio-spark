#!/usr/bin/env python3
"""Run and render the Trio-Spark v1.1 Crossing Phase production demo."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

SOURCE_URL = "https://commons.wikimedia.org/wiki/Special:Redirect/file/Shibuya_Crossing%2C_Tokyo%2C_Japan_%28video%29.webm"
SOURCE_PAGE = "https://commons.wikimedia.org/wiki/File:Shibuya_Crossing,_Tokyo,_Japan_(video).webm"
SOURCE_SHA256 = "b002bee56f416eddcc4dc3fb78079fe1ef4b13d47bf925930ee20a22a7487cde"
API_URL = "https://platform.machinefi.com/api/spark/v1/decisions"
WINDOW_END_MS = (37000, 41000, 45000, 49000, 53000, 57000)
WINDOWS = tuple((end - 3000, end - 2000, end - 1000, end) for end in WINDOW_END_MS)
SAMPLE_MS = tuple(sorted({value for window in WINDOWS for value in window}))
CHOICES = {
    "pedestrians_crossing": "Many pedestrians are actively occupying the central crossing.",
    "crossing_is_clearing": "Pedestrian occupancy is visibly thinning across the sampled window.",
    "crossing_mostly_clear": "The central crossing is mostly clear of pedestrians by the latest frame.",
    "vehicles_entering": "Road vehicles are visibly entering or moving through the central crossing.",
    "insufficient_evidence": "The sampled frames do not provide enough visual evidence to decide.",
}
TASK = "Which crossing phase is most clearly supported by this sampled video window?"
STATE = "Four frames sample one 3-second window in chronological order. Judge only visible movement and occupancy; do not infer traffic-signal state, intent, or safety."


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def download_source(path: Path) -> None:
    if path.exists() and sha256(path) == SOURCE_SHA256:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(SOURCE_URL, headers={"User-Agent": "Trio-Spark-Demo/1.1 (https://github.com/machinefi/trio-spark)"})
    temporary = path.with_suffix(path.suffix + ".part")
    with urllib.request.urlopen(request, timeout=60) as response, temporary.open("wb") as target:
        while chunk := response.read(1024 * 1024):
            target.write(chunk)
    if sha256(temporary) != SOURCE_SHA256:
        raise RuntimeError("source video checksum mismatch")
    temporary.replace(path)


def extract_inputs(source: Path, output: Path) -> list[Path]:
    output.mkdir(parents=True, exist_ok=True)
    frames = []
    for index, timestamp_ms in enumerate(SAMPLE_MS, 1):
        path = output / f"frame-{index}-{timestamp_ms}ms.jpg"
        run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp_ms / 1000:.3f}", "-i", str(source), "-frames:v", "1", "-vf", "scale=512:-2", "-q:v", "2", str(path)])
        frames.append(path)
    clip = output / "source-window.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-ss", "34", "-t", "24", "-i", str(source), "-an", "-vf", "scale=1280:-2", "-c:v", "libx264", "-crf", "20", "-pix_fmt", "yuv420p", str(clip)])
    return frames


def payload(frames: list[Path], timestamps: tuple[int, ...]) -> dict:
    values = []
    for path, timestamp_ms in zip(frames, timestamps):
        values.append({"mime_type": "image/jpeg", "data_base64": base64.b64encode(path.read_bytes()).decode(), "timestamp_ms": timestamp_ms})
    return {"model": "trio-spark-v1.1", "task": TASK, "state": STATE,
            "choices": [{"id": key, "description": description} for key, description in CHOICES.items()],
            "media": {"type": "video", "frames": values}}


def infer(frame_by_ms: dict[int, Path], output: Path) -> Path:
    key = os.environ.get("TRIO_SPARK_API_KEY", "")
    if not key:
        raise RuntimeError("TRIO_SPARK_API_KEY is required for a real production run")
    decisions = []
    errors = []
    for index, timestamps in enumerate(WINDOWS, 1):
        value = payload([frame_by_ms[ms] for ms in timestamps], timestamps)
        body = json.dumps(value, separators=(",", ":")).encode()
        request_id = str(uuid.uuid4())
        request = urllib.request.Request(API_URL, data=body, method="POST", headers={
            "Authorization": f"Bearer {key}", "Content-Type": "application/json",
            "Idempotency-Key": request_id, "User-Agent": "Trio-Spark-Demo/1.1",
        })
        started = time.perf_counter()
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                result = json.load(response)
            wall_ms = round((time.perf_counter() - started) * 1000, 1)
            probabilities = result.get("probabilities")
            if result.get("model") != "trio-spark-v1.1" or result.get("choice_id") not in CHOICES:
                raise RuntimeError("unexpected model or choice")
            if not isinstance(probabilities, list) or {item.get("choice_id") for item in probabilities} != set(CHOICES):
                raise RuntimeError("incomplete probabilities")
            values = [float(item["probability"]) for item in probabilities]
            if not all(math.isfinite(x) for x in values) or abs(sum(values) - 1.0) > 1e-5:
                raise RuntimeError("invalid probabilities")
            decisions.append({"window_index": index, "sample_times_ms": list(timestamps),
                              "choice_id": result["choice_id"], "confidence": result.get("confidence"),
                              "probabilities": probabilities, "wall_latency_ms": wall_ms,
                              "server_processing_ms": result.get("latency_ms") or result.get("server_processing_ms"),
                              "billed_input_tokens": result.get("billed_input_tokens"),
                              "request_id": result.get("request_id", request_id), "raw_response": result})
        except Exception as error:
            errors.append({"window_index": index, "sample_times_ms": list(timestamps),
                           "error_type": type(error).__name__, "message": str(error)[:500]})
    evidence = {
        "demo": "crossing-phase", "complete": len(decisions) == len(WINDOWS) and not errors,
        "production_api": True, "model": "trio-spark-v1.1",
        "successful_calls": len(decisions), "api_errors": len(errors), "errors": errors,
        "task": TASK, "state": STATE, "choices": CHOICES, "windows": [list(x) for x in WINDOWS],
        "decisions": decisions,
        "source": {"url": SOURCE_PAGE, "license": "CC BY-SA 4.0", "author": "Basile Morin", "sha256": SOURCE_SHA256},
        "frame_sha256": {str(ms): sha256(frame_by_ms[ms]) for ms in SAMPLE_MS},
        "serving_path": "public_customer_api", "public_customer_api_verified": True,
        "claim_scope": "Six calls over four sampled frames each; not continuous monitoring or a traffic-safety determination.",
    }
    output.mkdir(parents=True, exist_ok=True)
    path = output / "evidence.json"; temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n"); temporary.replace(path)
    if not evidence["complete"]:
        raise RuntimeError(f"production run incomplete: {len(decisions)} successes, {len(errors)} errors")
    return path


def render(source_clip: Path, evidence_path: Path, output: Path) -> None:
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    evidence = json.loads(evidence_path.read_text())
    if evidence.get("complete") is not True or evidence.get("production_api") is not True:
        raise RuntimeError("render requires complete real production evidence")
    decisions = evidence["decisions"]
    if len(decisions) != len(WINDOWS):
        raise RuntimeError("render requires every locked window")
    cap = cv2.VideoCapture(str(source_clip)); fps = 30; width, height = 1920, 1080
    temporary = output.with_suffix(".silent.mp4")
    writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
    font_path = "/System/Library/Fonts/Supplemental/Arial.ttf"; bold_path = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
    regular = ImageFont.truetype(font_path, 30); small = ImageFont.truetype(font_path, 23)
    bold = ImageFont.truetype(bold_path, 32); title = ImageFont.truetype(bold_path, 48)
    duration = 26.0; frames_total = int(duration * fps); source_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)); cached = None
    labels = {"pedestrians_crossing":"Pedestrians crossing", "crossing_is_clearing":"Crossing is clearing",
              "crossing_mostly_clear":"Crossing mostly clear", "vehicles_entering":"Vehicles entering",
              "insufficient_evidence":"Insufficient evidence"}
    for number in range(frames_total):
        t = number / fps
        ok, frame = cap.read()
        if not ok:
            cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, source_frames - 1)); ok, frame = cap.read()
        if ok: cached = frame
        frame = cached if cached is not None else np.zeros((720,1280,3),dtype=np.uint8)
        frame = cv2.resize(frame, (1240, 698))
        canvas = Image.new("RGB", (width,height), "#071018")
        canvas.paste(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)), (40,190))
        d=ImageDraw.Draw(canvas)
        d.text((42,38),"TRIO-SPARK v1.1",font=title,fill="#f4fbff")
        d.text((42,105),"Recorded production replay · 6 chronological decisions",font=regular,fill="#84d8ff")
        d.rounded_rectangle((1320,40,1880,1025),24,fill="#101d29",outline="#28455a",width=2)
        d.text((1360,78),"CROSSING PHASE",font=small,fill="#84d8ff")
        y=125
        for line in ("Which phase is most clearly", "supported by this sampled", "3-second video window?"):
            d.text((1360,y),line,font=bold,fill="white"); y+=40
        d.text((1360,275),"4 frames/window · no future frames",font=small,fill="#93a8b7")
        available = [item for item in decisions if t >= (item["sample_times_ms"][-1] - 34000) / 1000 + item["wall_latency_ms"] / 1000]
        current = available[-1] if available else None
        pending = next((item for item in decisions if t >= (item["sample_times_ms"][-1] - 34000) / 1000 and item not in available), None)
        result = current["choice_id"] if current else None
        probabilities = {item["choice_id"]: float(item["probability"]) for item in current["probabilities"]} if current else {}
        if pending:
            status=f"Window {pending['window_index']}/6 · inference…"; color="#f3c969"
        elif current:
            status=f"Window {current['window_index']}/6 · {current['wall_latency_ms']:.0f} ms wall"; color="#63e6a5"
        else:
            status="Sampling first window…"; color="#f3c969"
        d.text((1360,325),status,font=small,fill=color)
        y=375
        for key in CHOICES:
            chosen = current is not None and key == result; probability = probabilities.get(key, 0.0)
            d.rounded_rectangle((1350,y,1850,y+92),14,fill="#173040" if chosen else "#14232f",outline="#63e6a5" if chosen else "#294354",width=3 if chosen else 1)
            d.text((1370,y+13),labels[key],font=small,fill="white" if chosen else "#c5d2db")
            if current is not None:
                d.rectangle((1370,y+58,1815,y+68),fill="#263d4d")
                d.rectangle((1370,y+58,1370+int(445*probability),y+68),fill="#63e6a5" if chosen else "#5aa7d6")
                d.text((1785,y+12),f"{probability*100:4.1f}%",font=small,fill="#dceaf2")
            y+=112
        d.text((44,920),"Sampled frames — not continuous monitoring or a safety determination",font=small,fill="#aec0cc")
        d.text((44,962),"Basile Morin / Wikimedia Commons · CC BY-SA 4.0",font=small,fill="#718b9b")
        writer.write(cv2.cvtColor(np.asarray(canvas), cv2.COLOR_RGB2BGR))
    cap.release(); writer.release(); output.parent.mkdir(parents=True,exist_ok=True)
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-i",str(temporary),"-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-movflags","+faststart",str(output)])
    temporary.unlink()
    run(["ffmpeg","-y","-hide_banner","-loglevel","error","-ss","18","-i",str(output),"-frames:v","1",str(output.with_suffix(".jpg"))])


def main() -> None:
    parser=argparse.ArgumentParser(); parser.add_argument("command",choices=("prepare","infer","render","all")); parser.add_argument("--work",type=Path,default=Path("runs/crossing-phase")); args=parser.parse_args()
    source=args.work/"source.webm"; frames_dir=args.work/"inputs"
    if args.command in ("prepare","all"):
        download_source(source); extract_inputs(source,frames_dir)
        (args.work/"protocol.json").write_text(json.dumps({"source_url":SOURCE_PAGE,"source_sha256":SOURCE_SHA256,"windows":WINDOWS,"task":TASK,"state":STATE,"choices":CHOICES},indent=2)+"\n")
    frame_by_ms={ms: frames_dir/f"frame-{i}-{ms}ms.jpg" for i,ms in enumerate(SAMPLE_MS,1)}
    if args.command in ("infer","all"): infer(frame_by_ms,args.work)
    if args.command in ("render","all"): render(frames_dir/"source-window.mp4",args.work/"evidence.json",args.work/"Trio-Spark-v1.1-Crossing-Phase.mp4")

if __name__=="__main__": main()
