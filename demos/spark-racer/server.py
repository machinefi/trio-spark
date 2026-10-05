#!/usr/bin/env python3
"""Local screenshot-driven racer. Credentials stay on the server; no fallback driver."""
import base64, hashlib, json, os, threading, time, urllib.request, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).parent
OUT=Path(os.environ.get('RACER_OUTPUT','./racer-evidence')).resolve(); OUT.mkdir(parents=True,exist_ok=True)
URL=os.environ.get('TRIO_SPARK_API_URL','https://platform.machinefi.com/api/spark/v1/decisions')
KEY=os.environ.get('TRIO_SPARK_API_KEY','')
PORT=int(os.environ.get('PORT','8878'))
LOCK=threading.Lock(); COUNT=0; LIMIT=int(os.environ.get('RACER_MAX_CALLS','100'))
TASK='Choose a clear lane for the yellow player car at the bottom of this three-lane road. Avoid red vehicles ahead. Prefer a lane with no red vehicle in the lower half of the road. If multiple lanes are clear, prefer a lane with gold coins. Lane names are absolute from the viewer: LEFT, CENTER, RIGHT.'
CHOICES=[{'id':k,'description':v} for k,v in [('left','Drive in the leftmost road lane.'),('center','Drive in the middle road lane.'),('right','Drive in the rightmost road lane.')]]
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def send(self,code,data,ctype='application/json'):
  body=data if isinstance(data,bytes) else json.dumps(data).encode()
  self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path.split('?')[0] in ('/','/index.html'):return self.send(200,(ROOT/'index.html').read_bytes(),'text/html')
  return self.send(404,{'error':'Not found'})
 def do_POST(self):
  global COUNT
  if self.headers.get('Host') not in (f'127.0.0.1:{PORT}',f'localhost:{PORT}') or self.headers.get('Origin') not in (None,f'http://127.0.0.1:{PORT}',f'http://localhost:{PORT}'):
   return self.send(403,{'error':'Local origin required'})
  n=int(self.headers.get('Content-Length','0'))
  if n<=0 or n>1500000:return self.send(413,{'error':'Invalid size'})
  try: value=json.loads(self.rfile.read(n))
  except Exception:return self.send(400,{'error':'Invalid JSON'})
  if self.path=='/finish':
   (OUT/'game-result.json').write_text(json.dumps(value,indent=2));return self.send(200,{'saved':True})
  if self.path!='/decide':return self.send(404,{'error':'Not found'})
  if not LOCK.acquire(blocking=False):return self.send(429,{'error':'One decision at a time'})
  try:
   if not KEY:raise ValueError('Set TRIO_SPARK_API_KEY')
   if COUNT>=LIMIT:raise ValueError('Decision budget exhausted')
   data=value['image'];raw=base64.b64decode(data,validate=True)
   if not raw.startswith(b'\xff\xd8'):raise ValueError('JPEG required')
   COUNT+=1;seq=COUNT
   (OUT/f'frame-{seq:03}.jpg').write_bytes(raw)
   payload={'model':'trio-spark-v1.1','task':TASK,'state':'Select the target lane from the screenshot. The car moves toward the top of the road. Red cars are obstacles. There is no hidden road-state input.','choices':CHOICES,'media':{'type':'image','frames':[{'mime_type':'image/jpeg','data_base64':data}]}}
   started=time.perf_counter();rid=str(uuid.uuid4())
   request=urllib.request.Request(URL,json.dumps(payload).encode(),headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json','Idempotency-Key':rid,'User-Agent':'Trio-Spark-Racer/1.1'})
   with urllib.request.urlopen(request,timeout=20) as response:result=json.load(response)
   wall=round((time.perf_counter()-started)*1000,1)
   if result.get('choice_id') not in ('left','center','right'):raise ValueError('Invalid model choice')
   record={'sequence':seq,'frame_sha256':hashlib.sha256(raw).hexdigest(),'captured_game_s':value.get('game_s'),'request_id':rid,'wall_ms':wall,'response':result}
   with (OUT/'decisions.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
   self.send(200,{'sequence':seq,'choice':result['choice_id'],'probabilities':result['probabilities'],'wall_ms':wall})
  except Exception as error:
   with (OUT/'errors.jsonl').open('a') as f:f.write(json.dumps({'type':type(error).__name__,'time':time.time()})+'\n')
   self.send(502,{'error':'Inference failed. Run stopped; no scripted fallback.'})
  finally:LOCK.release()
if __name__=='__main__':
 print(f'Racer http://127.0.0.1:{PORT}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
