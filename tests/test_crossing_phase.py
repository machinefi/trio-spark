import importlib.util
from pathlib import Path

PATH=Path(__file__).parents[1]/'demos'/'crossing-phase'/'run.py'
spec=importlib.util.spec_from_file_location('crossing_phase',PATH); demo=importlib.util.module_from_spec(spec); spec.loader.exec_module(demo)

def test_protocol_is_bounded_and_stable():
    assert len(demo.WINDOWS) == 6
    assert all(len(window) == 4 and window == tuple(sorted(window)) for window in demo.WINDOWS)
    assert all(window[-1]-window[0] <= 30_000 for window in demo.WINDOWS)
    assert 2 <= len(demo.CHOICES) <= 8
    assert 'unclear' in demo.CHOICES
    assert 'Movement requires' in demo.STATE

def test_payload_uses_real_distinct_frames(tmp_path):
    frames=[]
    for i in range(4):
        p=tmp_path/f'{i}.jpg'; p.write_bytes(b'jpeg'+bytes([i])); frames.append(p)
    value=demo.payload(frames,demo.WINDOWS[0])
    assert value['model']=='trio-spark-v1.1'
    assert value['media']['type']=='video'
    assert [x['timestamp_ms'] for x in value['media']['frames']]==list(demo.WINDOWS[0])
    assert len({x['data_base64'] for x in value['media']['frames']})==4
