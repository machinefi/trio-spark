import hashlib
import importlib.util
import json
import sys
from pathlib import Path

PATH = Path(__file__).parents[1] / "demos" / "asl-recorded" / "render.py"
spec = importlib.util.spec_from_file_location("asl_recorded_renderer", PATH)
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


def write_case(tmp_path, *, status="recognized", label="HELLO", latency=5152.8, times=None):
    source = tmp_path / "clip.ogv"
    source.write_bytes(b"source")
    evidence = tmp_path / "result.json"
    evidence.write_text(json.dumps({
        "case": {"file": "clip.ogv", "expected": "hello", "times_ms": times or [0, 750, 1500, 2250]},
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "result": {"status": status, "label": label, "score": 0.9, "latency_ms": latency},
    }))
    return evidence, source


def test_result_timing_follows_last_sample_plus_recorded_latency(tmp_path):
    evidence, _ = write_case(tmp_path)
    case = module.load_case(evidence, tmp_path)
    assert case.result_at_seconds == 7.4028
    assert case.duration_seconds == 10.4028


def test_nonrecognized_null_label_uses_status(tmp_path):
    evidence, _ = write_case(tmp_path, status="unclear", label=None)
    case = module.load_case(evidence, tmp_path)
    assert case.actual == "UNCLEAR"


def test_invalid_sample_sequence_and_nonfinite_latency_are_rejected(tmp_path):
    evidence, _ = write_case(tmp_path, times=[0, 750, 750, 2250])
    try:
        module.load_case(evidence, tmp_path)
    except ValueError:
        pass
    else:
        raise AssertionError("duplicate sample timestamps accepted")
    evidence, _ = write_case(tmp_path, latency=float("nan"))
    try:
        module.load_case(evidence, tmp_path)
    except ValueError:
        return
    raise AssertionError("non-finite latency accepted")


def test_source_hash_mismatch_is_rejected(tmp_path):
    evidence, source = write_case(tmp_path)
    source.write_bytes(b"different")
    try:
        module.load_case(evidence, tmp_path)
    except ValueError as error:
        assert "source SHA-256 mismatch" in str(error)
        return
    raise AssertionError("wrong source accepted")
