#!/usr/bin/env python3
"""Download two reviewed CC BY clips and prepare exact v1.1 image requests."""
from __future__ import annotations
import argparse, base64, hashlib, json, subprocess, urllib.request, uuid
from pathlib import Path

CHOICES = [
    {"id": "one", "description": "One: only the index finger is extended."},
    {"id": "two", "description": "Two: the index and middle fingers are extended."},
    {"id": "other", "description": "A different clear hand gesture is visible."},
    {"id": "insufficient", "description": "The hand or fingers are not clear enough to decide."},
]

def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument("--output",type=Path,required=True); args=ap.parse_args()
    root=Path(__file__).resolve().parent; manifest=json.loads((root/'source_manifest.json').read_text()); args.output.mkdir(parents=True,exist_ok=True); crop=manifest['input_crop_pixels']
    cases=[]
    for item in manifest['clips']:
        gif=args.output/f"{item['case_id']}.gif"; urllib.request.urlretrieve(item['url'],gif)
        digest=hashlib.sha256(gif.read_bytes()).hexdigest()
        if digest != item['sha256']: raise RuntimeError(f"source hash mismatch: {item['case_id']}")
        for sample_time in item['sample_times_seconds']:
            case_id=f"{item['case_id']}_t{round(sample_time*1000):04d}"
            frame=args.output/f"{case_id}.jpg"
            vf=f"crop={crop['width']}:{crop['height']}:{crop['x']}:{crop['y']},scale=512:512:force_original_aspect_ratio=decrease"
            subprocess.run(['ffmpeg','-v','error','-ss',str(sample_time),'-i',str(gif),'-frames:v','1','-vf',vf,'-q:v','3','-y',str(frame)],check=True)
            request={
                'model':'trio-spark-v1.1',
                'task':'Which hand gesture is clearly visible in this image?',
                'state':'Inspect only the supplied image. Choose insufficient when the fingers are not clear.',
                'choices':CHOICES,
                'media':{'type':'image','frames':[{'mime_type':'image/jpeg','data_base64':base64.b64encode(frame.read_bytes()).decode()}]},
            }
            cases.append({'case_id':case_id,'clip_id':item['case_id'],'sample_time_seconds':sample_time,'source_crop_pixels':crop,'official_label':item['official_label'],'idempotency_key':str(uuid.uuid4()),'request':request,'source_sha256':digest,'frame_sha256':hashlib.sha256(frame.read_bytes()).hexdigest()})
    (args.output/'requests.json').write_text(json.dumps({'cases':cases},indent=2)+'\n')
    (args.output/'SOURCE-COMPLETE').write_text('verified\n')
    print(json.dumps({'status':'PASS','cases':len(cases),'output':str(args.output)}))
if __name__=='__main__': main()
