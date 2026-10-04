"""Two-stage ASL vocabulary prototype. Scores are conditional, not calibrated."""
from __future__ import annotations
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import time
import urllib.error
import urllib.request
import uuid

MODEL = 'trio-spark-v1.1'
ENDPOINT = 'https://platform.machinefi.com/api/spark/v1/decisions'
NONE = {'id':'no_sign','description':'No complete intentional sign is visible; hands are resting or only transitioning.'}
UNCLEAR = {'id':'unclear','description':'A sign is outside this vocabulary, obscured, incomplete, or cannot be distinguished confidently.'}

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None

class RecognitionError(RuntimeError):
    pass


def vocabulary():
    return json.loads(Path(__file__).with_name('vocabulary.json').read_text())


def validate_frames(frames):
    if not isinstance(frames,list) or len(frames)!=4:
        raise RecognitionError('Exactly four chronological frames are required.')
    total=0; stamps=[]
    for f in frames:
        if not isinstance(f,dict) or f.get('mime_type') not in ('image/jpeg','image/png'):
            raise RecognitionError('Only embedded JPEG and PNG frames are supported.')
        ts=f.get('timestamp_ms')
        if isinstance(ts,bool) or not isinstance(ts,int) or ts<0:
            raise RecognitionError('Frame timestamps must be nonnegative integer milliseconds.')
        data=f.get('data_base64')
        if not isinstance(data,str) or len(data)>2_800_000:
            raise RecognitionError('Frame size exceeds the local demo limit.')
        try: raw=base64.b64decode(data,validate=True)
        except (ValueError,TypeError): raise RecognitionError('Invalid base64 frame.') from None
        if not raw or len(raw)>2*1024*1024:
            raise RecognitionError('Decoded frame exceeds 2 MiB.')
        signature=raw.startswith(b'\xff\xd8\xff') if f['mime_type']=='image/jpeg' else raw.startswith(b'\x89PNG\r\n\x1a\n')
        if not signature: raise RecognitionError('Image signature does not match its media type.')
        total+=len(raw); stamps.append(ts)
    if total>8*1024*1024 or stamps!=sorted(set(stamps)) or stamps[-1]-stamps[0]>30_000:
        raise RecognitionError('Frames must be increasing and span at most 30 seconds.')
    return {'type':'video','frames':[{k:f[k] for k in ('mime_type','data_base64','timestamp_ms')} for f in frames]}


def decision(result, choices):
    if not isinstance(result,dict) or result.get('model')!=MODEL:
        raise RecognitionError('Unexpected model response.')
    ids={c['id'] for c in choices}; probs=result.get('probabilities')
    if not isinstance(probs,list) or len(probs)!=len(ids):
        raise RecognitionError('Incomplete probability distribution.')
    by={p.get('choice_id'):p.get('probability') for p in probs if isinstance(p,dict)}
    if set(by)!=ids or any(isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v) or v<0 or v>1 for v in by.values()) or not math.isclose(sum(by.values()),1,abs_tol=1e-4):
        raise RecognitionError('Invalid probability distribution.')
    choice=result.get('choice_id')
    if choice not in by: raise RecognitionError('Unknown choice.')
    return {'choice':choice,'score':by[choice],'probabilities':by}


class Recognizer:
    def __init__(self, api_key=None, caller=None, *, minimum_score=0.7):
        self.vocab=vocabulary()
        self.minimum_score=minimum_score
        self.api_key=api_key or os.environ.get('TRIO_SPARK_API_KEY','')
        self.caller=caller or self._public_call
        self.http=urllib.request.build_opener(NoRedirect())
        banks=self.vocab['banks']
        ids=[w['id'] for bank in banks for w in bank['words']]
        if len(banks)!=2 or any(len(b['words'])!=5 for b in banks) or len(set(ids))!=10:
            raise RecognitionError('Vocabulary must contain two fixed banks of five unique words.')

    def _public_call(self, payload):
        if not self.api_key:
            raise RecognitionError('Server API key is not configured.')
        request=urllib.request.Request(ENDPOINT,data=json.dumps(payload,separators=(',',':')).encode(),headers={
            'Authorization':'Bearer '+self.api_key, 'Content-Type':'application/json',
            'Idempotency-Key':str(uuid.uuid4()), 'User-Agent':'Trio-Spark-ASL-Prototype/1'},method='POST')
        try:
            with self.http.open(request,timeout=35) as response:
                raw=response.read(262145)
                if len(raw)>262144: raise RecognitionError('Response exceeded the limit.')
                return json.loads(raw)
        except urllib.error.HTTPError as e:
            raise RecognitionError(f'Model service returned HTTP {e.code}; this window was not retried.') from None
        except (urllib.error.URLError,TimeoutError,json.JSONDecodeError):
            raise RecognitionError('Model request failed; this window was not retried.') from None

    def recognize(self, frames):
        started=time.monotonic(); media=validate_frames(frames)
        image_hash=hashlib.sha256(json.dumps(media,sort_keys=True).encode()).hexdigest()
        banks=self.vocab['banks']
        route_choices=[{'id':b['id'],'description':'One complete American Sign Language sign for: '+', '.join(w['label'] for w in b['words'])+'.'} for b in banks]+[NONE,UNCLEAR]
        state='Four chronological frames of one person signing ASL. Use visible hand shape, location and movement. Do not infer a word from captions or the background. This is isolated-word recognition, not sentence translation.'
        def call(task,choices):
            payload={'model':MODEL,'task':task,'state':state,'choices':choices,'media':media}
            return decision(self.caller(payload),choices)
        route=call('Which vocabulary group contains the single complete ASL sign visible in this window? If none is clear, choose no_sign or unclear.',route_choices)
        out={'status':'unclear','label':None,'score':route['score'],'score_scope':'router_only','route':route,'leaf':None,'calls':1,'input_sha256':image_hash,'prototype':True}
        if route['choice']=='no_sign': out['status']='no_sign'
        elif route['choice'] in ('bank_a','bank_b') and route['score']>=self.minimum_score:
            bank=next(b for b in banks if b['id']==route['choice'])
            choices=[{'id':w['id'],'description':w['description']} for w in bank['words']]+[NONE,UNCLEAR]
            leaf=call('Identify the single complete ASL word visible in this same window. Choose unclear if it does not clearly match a supplied word.',choices)
            out.update(leaf=leaf,calls=2,score=leaf['score'],score_scope='conditional_within_bank')
            if leaf['choice']=='no_sign': out['status']='no_sign'
            elif leaf['choice']!='unclear' and leaf['score']>=self.minimum_score:
                word=next(w for w in bank['words'] if w['id']==leaf['choice'])
                out.update(status='recognized',label=word['label'],word_id=word['id'])
        out['latency_ms']=round((time.monotonic()-started)*1000,1)
        return out
