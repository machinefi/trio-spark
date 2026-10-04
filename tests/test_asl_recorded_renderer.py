import importlib.util
import json
import sys
from pathlib import Path

PATH = Path(__file__).parents[1] / "demos" / "asl-recorded" / "render.py"
spec = importlib.util.spec_from_file_location("asl_recorded_renderer", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def test_result_timing_follows_last_sample_plus_recorded_latency(tmp_path):
    (tmp_path / "clip.ogv").write_bytes(b"source")
    evidence = tmp_path / "result.json"
    evidence.write_text(json.dumps({
        "case": {"file": "clip.ogv", "expected": "hello", "times_ms": [0, 750, 1500, 2250]},
        "result": {"status": "recognized", "label": "HELLO", "score": 0.9, "latency_ms": 5152.8},
    }))
    case = module.load_case(evidence, tmp_path)
    assert case.result_at_seconds == 7.4028
    assert case.duration_seconds == 10.4028


def test_invalid_sample_sequence_is_rejected(tmp_path):
    (tmp_path / "clip.ogv").write_bytes(b"source")
    evidence = tmp_path / "result.json"
    evidence.write_text(json.dumps({
        "case": {"file": "clip.ogv", "expected": "hello", "times_ms": [0, 750, 750, 2250]},
        "result": {"status": "unclear", "score": 0.2, "latency_ms": 100},
    }))
    try:
        module.load_case(evidence, tmp_path)
    except ValueError:
        return
    raise AssertionError("duplicate sample timestamps accepted")
