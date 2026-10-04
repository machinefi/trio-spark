#!/usr/bin/env python3
"""Record the frozen gesture requests through the public customer API."""
from __future__ import annotations
import argparse, json, math, os, time, urllib.error, urllib.request
from pathlib import Path

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError(f'unexpected HTTP redirect {code}')

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--prepared',type=Path,required=True); ap.add_argument('--api-url',default='https://platform.machinefi.com/api/spark/v1/decisions'); ap.add_argument('--output',type=Path,required=True); args=ap.parse_args()
    if args.output.exists(): raise FileExistsError('refusing to replace recorded evidence')
    key=os.environ.get('TRIO_SPARK_API_KEY','')
    if not key: raise RuntimeError('TRIO_SPARK_API_KEY is required')
    pack=json.loads((args.prepared/'requests.json').read_text()); cases=[]; errors=[]; opener=urllib.request.build_opener(NoRedirect)
    for case in pack['cases']:
        started=time.perf_counter(); result={}; status=0
        try:
            request=urllib.request.Request(args.api_url,data=json.dumps(case['request'],separators=(',',':')).encode(),method='POST',headers={'Authorization':'Bearer '+key,'Content-Type':'application/json','Idempotency-Key':case['idempotency_key'],'User-Agent':'Trio-Spark-Demo/1.1'})
            with opener.open(request,timeout=45) as response: status=response.status; result=json.load(response)
            probabilities=result.get('probabilities',[]); values=[p.get('probability') for p in probabilities]
            if result.get('model')!='trio-spark-v1.1' or result.get('choice_id') not in {x['id'] for x in case['request']['choices']} or len(probabilities)!=4 or not all(isinstance(x,(int,float)) and math.isfinite(x) for x in values) or abs(sum(values)-1)>1e-4: raise ValueError('invalid public API response')
            cases.append({'case_id':case['case_id'],'sample_time_seconds':case['sample_time_seconds'],'frame_sha256':case['frame_sha256'],'wall_latency_ms':round((time.perf_counter()-started)*1000,1),'response':result})
        except Exception as error:
            errors.append({'case_id':case['case_id'],'http_status':status,'error_type':type(error).__name__,'message':str(error)[:200]})
    evidence={'complete':len(cases)==len(pack['cases']) and not errors,'production_api':True,'serving_path':'public_customer_api','public_customer_api_verified':True,'successful_calls':len(cases),'api_errors':len(errors),'errors':errors,'cases':cases}
    args.output.write_text(json.dumps(evidence,indent=2)+'\n')
    if not evidence['complete']: raise RuntimeError('public capture incomplete; evidence retained without retry')

if __name__=='__main__': main()
