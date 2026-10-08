#!/usr/bin/env python3
"""Local screenshot-driven racer. Credentials stay on the server; no fallback driver."""
import base64, hashlib, json, math, os, threading, time, urllib.request, urllib.error, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT=Path(__file__).parent
OUT=Path(os.environ['RACER_OUTPUT']).resolve(); OUT.mkdir(parents=True,exist_ok=False)
URL='https://platform.machinefi.com/api/spark/v1/decisions'
KEY=os.environ.get('TRIO_SPARK_API_KEY','')
PORT=int(os.environ.get('PORT','8879'))
LOCK=threading.Lock(); COUNT=0; LIMIT=39; LAST_START=0.; DEADLINE=time.monotonic()+90
TASK='Choose a clear lane for the yellow player car at the bottom of this three-lane road. Avoid red vehicles ahead. Prefer a lane with no red vehicle in the lower half of the road. If multiple lanes are clear, prefer a lane with gold coins. Lane names are absolute from the viewer: LEFT, CENTER, RIGHT.'
CHOICES=[{'id':k,'description':v} for k,v in [('left','Drive in the leftmost road lane.'),('center','Drive in the middle road lane.'),('right','Drive in the rightmost road lane.')]]
class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):return None

def validate(result):
 if result.get('model')!='trio-spark-v1.2' or result.get('model_version')!='trio-spark-v1.1-visual-t4-native4-v1+canonical-choice-id-v2':raise ValueError('Model/version identity mismatch')
 probabilities=result.get('probabilities')
 if not isinstance(probabilities,list) or len(probabilities)!=3:raise ValueError('Three probabilities required')
 ps={p.get('choice_id'):p.get('probability') for p in probabilities}
 if set(ps)!={'left','center','right'} or result.get('choice_id') not in ps:raise ValueError('Invalid choice keys')
 if any(type(p) not in (int,float) or not math.isfinite(p) or not 0<=p<=1 for p in ps.values()) or not math.isclose(sum(ps.values()),1,rel_tol=0,abs_tol=1e-4):raise ValueError('Invalid probabilities')
 u=result.get('usage',{})
 if 'output_tokens' in u and (type(u['output_tokens']) is not int or u['output_tokens']!=0):raise ValueError('Unexpected generated tokens')
 return result

class Handler(BaseHTTPRequestHandler):
 def log_message(self,*args): pass
 def send(self,code,data,ctype='application/json'):
  body=data if isinstance(data,bytes) else json.dumps(data).encode()
  self.send_response(code);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(body)));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(body)
 def do_GET(self):
  if self.path.split('?')[0] in ('/','/index.html'):return self.send(200,(ROOT/'index-v12.html').read_bytes(),'text/html')
  return self.send(404,{'error':'Not found'})
 def do_POST(self):
  global COUNT, LAST_START
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
   if COUNT>=LIMIT or time.monotonic()>=DEADLINE:raise ValueError('Decision budget/deadline exhausted')
   time.sleep(max(0,LAST_START+1.1-time.monotonic()))
   if time.monotonic()>=DEADLINE:raise ValueError('Deadline exhausted')
   data=value['image'];raw=base64.b64decode(data,validate=True)
   if not raw.startswith(b'\xff\xd8'):raise ValueError('JPEG required')
   COUNT+=1;seq=COUNT
   (OUT/f'frame-{seq:03}.jpg').write_bytes(raw)
   payload={'model':'trio-spark-v1.2','task':TASK,'state':'Select the target lane from the screenshot. The car moves toward the top of the road. Red cars are obstacles. There is no hidden road-state input.','choices':CHOICES,'media':{'type':'image','frames':[{'mime_type':'image/jpeg','data_base64':data}]}}
   started=time.perf_counter();rid=str(uuid.uuid4()); LAST_START=time.monotonic()
   (OUT/f'request-{seq:03}.json').write_text(json.dumps({'sequence':seq,'api_start_monotonic':LAST_START,'captured_game_s':value.get('game_s'),'payload':payload},indent=2))
   request=urllib.request.Request(URL,json.dumps(payload).encode(),headers={'Authorization':'Bearer '+KEY,'Content-Type':'application/json','Idempotency-Key':rid,'User-Agent':'trio-spark-production-canary/1'})
   with urllib.request.build_opener(NoRedirect()).open(request,timeout=min(20,max(.1,DEADLINE-time.monotonic()))) as response:
    raw_response=response.read(256*1024+1)
    if len(raw_response)>256*1024:raise ValueError('Oversized response')
    result=json.loads(raw_response)
   (OUT/f'response-{seq:03}.json').write_text(json.dumps({'http_status':200,'response':result},indent=2))
   validate(result)
   wall=round((time.perf_counter()-started)*1000,1)
   record={'sequence':seq,'frame_sha256':hashlib.sha256(raw).hexdigest(),'captured_game_s':value.get('game_s'),'request_id':rid,'wall_ms':wall,'api_start_monotonic':LAST_START,'response':result}
   with (OUT/'decisions.jsonl').open('a') as f:f.write(json.dumps(record)+'\n')
   self.send(200,{'sequence':seq,'choice':result['choice_id'],'probabilities':result['probabilities'],'wall_ms':wall})
  except Exception as error:
   diagnostic={'type':type(error).__name__,'time':time.time(),'validation_error':str(error) if isinstance(error,ValueError) else None}
   if isinstance(error,urllib.error.HTTPError):
    diagnostic['http_status']=error.code
    diagnostic['error_body']=error.read(256*1024).decode('utf-8',errors='replace').replace(KEY,'[REDACTED]')
   with (OUT/'errors.jsonl').open('a') as f:f.write(json.dumps(diagnostic)+'\n')
   self.send(502,{'error':'Inference failed. Run stopped; no scripted fallback.'})
  finally:LOCK.release()
if __name__=='__main__':
 print(f'Racer http://127.0.0.1:{PORT}',flush=True)
 ThreadingHTTPServer(('127.0.0.1',PORT),Handler).serve_forever()
