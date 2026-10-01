#!/usr/bin/env python3
"""Dependency-free integrity checks for public demos and documentation."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def verify_evidence() -> None:
    required = {"demo", "production_api", "successful_calls", "api_errors"}
    evidence_files = sorted((ROOT / "demos").glob("*/evidence.json"))
    if not evidence_files:
        raise RuntimeError("no demo evidence files found")
    for path in evidence_files:
        payload = json.loads(path.read_text())
        missing = required - payload.keys()
        if missing:
            raise RuntimeError(f"{path.relative_to(ROOT)} missing {sorted(missing)}")
        if payload["production_api"] is not True:
            raise RuntimeError(f"{path.relative_to(ROOT)} is not a production API run")


def verify_assets() -> None:
    checksums = ROOT / "assets" / "demos" / "SHA256SUMS"
    declared: set[Path] = set()
    for line in checksums.read_text().splitlines():
        if not line.strip():
            continue
        expected, relative = line.split(maxsplit=1)
        path = ROOT / relative.strip()
        if not path.is_file():
            raise RuntimeError(f"missing asset {relative}")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"checksum mismatch for {relative}")
        declared.add(path.resolve())

    assets = {
        path.resolve()
        for path in (ROOT / "assets" / "demos").iterdir()
        if path.is_file() and path.name != "SHA256SUMS"
    }
    undeclared = assets - declared
    if undeclared:
        names = sorted(str(path.relative_to(ROOT)) for path in undeclared)
        raise RuntimeError(f"assets missing from SHA256SUMS: {names}")


def verify_local_markdown_links() -> None:
    link_pattern = re.compile(r"\[[^]]*\]\(([^)]+)\)")
    for markdown in sorted(ROOT.rglob("*.md")):
        if ".git" in markdown.parts:
            continue
        for target in link_pattern.findall(markdown.read_text()):
            target = target.split("#", 1)[0].strip()
            if not target or "://" in target or target.startswith("mailto:"):
                continue
            destination = (markdown.parent / target).resolve()
            if not destination.exists():
                raise RuntimeError(
                    f"{markdown.relative_to(ROOT)} links to missing path {target}"
                )


if __name__ == "__main__":
    verify_evidence()
    verify_assets()
    verify_local_markdown_links()
    print("public repository evidence and asset checks passed")
