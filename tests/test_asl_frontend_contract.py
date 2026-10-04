from pathlib import Path
import re

SOURCE=(Path(__file__).resolve().parents[1]/'demos/asl-words/web/app.js').read_text()

def test_window_cadence_and_session_bound_are_locked():
    assert re.search(r'CAPTURE_MS=500,WINDOW=4,REQUEST_MS=3000,MAX_WINDOWS=60',SOURCE)
    assert 'state.windows>=MAX_WINDOWS' in SOURCE
    assert "title:'Session ended'" in SOURCE

def test_errors_and_camera_play_failure_release_the_session():
    assert "if(failed)stopCamera({title:'Session stopped after an error'" in SOURCE
    assert 'if(stream)stream.getTracks().forEach(track=>track.stop())' in SOURCE
    assert "els.stop.addEventListener('click',()=>stopCamera())" in SOURCE
    assert "window.addEventListener('pagehide',()=>stopCamera())" in SOURCE
