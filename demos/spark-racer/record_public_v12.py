#!/usr/bin/env python3
"""One bounded real public v1.2 visual racer capture; no replayed/model-free actions."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time
import urllib.request

ROOT=Path(__file__).parent

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--output',type=Path,required=True)
    ap.add_argument('--ack-up-to-39-visual-calls',action='store_true')
    a=ap.parse_args()
    if not a.ack_up_to_39_visual_calls:ap.error('Explicit authorized call acknowledgement required')
    if not os.environ.get('TRIO_SPARK_API_KEY'):raise ValueError('Credential environment absent')
    from playwright.sync_api import sync_playwright
    a.output.mkdir(parents=True,exist_ok=False,mode=0o700)
    env=os.environ.copy();env.update(RACER_OUTPUT=str(a.output/'capture'),PORT='8879')
    def expired(*_):raise TimeoutError('90-second recording bound reached')
    signal.signal(signal.SIGALRM,expired);signal.alarm(90)
    started=time.monotonic();server=None
    try:
        with (a.output/'local-server.log').open('w') as log:
            server=subprocess.Popen(['python3',str(ROOT/'server_v12.py')],env=env,stdout=log,stderr=log)
            for _ in range(50):
                if server.poll() is not None:raise RuntimeError('Local server failed')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:8879/',timeout=.2):break
                except Exception:time.sleep(.1)
            else:raise RuntimeError('Local server readiness bound')
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=os.environ.get('RACER_BROWSER_EXECUTABLE','/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),headless=True,args=['--disable-gpu'])
                context=browser.new_context(viewport={'width':1280,'height':720},device_scale_factor=1,
                    record_video_dir=str(a.output/'browser-video'),record_video_size={'width':1280,'height':720})
                try:
                    page=context.new_page();page.goto('http://127.0.0.1:8879/',wait_until='load')
                    page.wait_for_timeout(1000);page.evaluate('window.startRacer()')
                    page.wait_for_timeout(12000);page.screenshot(path=str(a.output/'poster-12s.png'))
                    page.wait_for_function('window.racerDone === true',timeout=45000)
                    result=page.evaluate('window.racerResult')
                    (a.output/'browser-result.json').write_text(json.dumps(result,indent=2)+'\n')
                    page.screenshot(path=str(a.output/'final-frame.png'))
                    page.wait_for_timeout(700)
                    video=page.video
                finally:
                    context.close();browser.close()
                video_path=video.path()
            # Preserve a response requested before finish, without applying it after finish.
            while time.monotonic()-started<85:
                requests=list((a.output/'capture').glob('request-*.json'))
                responses=list((a.output/'capture').glob('response-*.json'))
                if len(responses)>=len(requests) or (a.output/'capture/errors.jsonl').exists():break
                time.sleep(.1)
            (a.output/'recording.json').write_text(json.dumps({'schema':'spark-v12-visual-racer-record-v1','production_api':True,
                'model':'trio-spark-v1.2','visual_backend':'unchanged','game_duration_s':35,'max_visual_calls':39,'min_api_start_interval_s':1.1,
                'recording_wall_seconds':time.monotonic()-started,'browser_video':str(Path(video_path).relative_to(a.output)),
                'scope':'One illustrative live visual run via v1.2 API. Not new visual capability or benchmark; no comparison/speed claim.',
                'source_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ['index-v12.html','server_v12.py','record_public_v12.py']}},indent=2)+'\n')
    finally:
        if server is not None and server.poll() is None:
            server.terminate()
            try:server.wait(timeout=3)
            except subprocess.TimeoutExpired:server.kill();server.wait()
        signal.alarm(0)

if __name__=='__main__':main()
