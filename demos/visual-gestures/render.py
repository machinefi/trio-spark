#!/usr/bin/env python3
"""Render a 22-second demo from licensed clips and recorded production responses."""
from __future__ import annotations
import argparse, hashlib, json, math, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ORDER=['one','two','other','insufficient']; COLORS=['0x67e8f9','0xa78bfa','0xfbbf24','0x94a3b8']
def validate(response: dict, expected_model_version: str) -> None:
    if response.get('model') != 'trio-spark-v1.1' or response.get('model_version') != expected_model_version:
        raise ValueError('response does not match the locked Trio-Spark v1.1 visual identity')
    probs=response.get('probabilities'); by={p.get('choice_id'):p.get('probability') for p in probs or []}
    if len(probs or []) != len(ORDER) or set(by)!=set(ORDER) or any(not isinstance(by[k],(int,float)) or not math.isfinite(by[k]) or not 0<=by[k]<=1 for k in ORDER) or not math.isclose(sum(by.values()),1,abs_tol=1e-4): raise ValueError('invalid probability distribution')
    latency=response.get('latency_ms')
    if response.get('choice_id') not in by or not isinstance(latency,(int,float)) or not math.isfinite(latency) or latency < 0: raise ValueError('invalid decision fields')

def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    name = 'Arial Bold.ttf' if bold else 'Arial.ttf'
    return ImageFont.truetype(f'/System/Library/Fonts/Supplemental/{name}', size)

def panel(response: dict, official: str, out: Path) -> None:
    by={p['choice_id']:p['probability'] for p in response['probabilities']}
    image=Image.new('RGB',(520,720),'#101816'); draw=ImageDraw.Draw(image)
    draw.text((55,55),'TRIO-SPARK v1.1',font=font(24,True),fill='#67e8f9')
    draw.text((55,105),official,font=font(28,True),fill='white')
    draw.text((55,175),f"Selected: {response['choice_id']}",font=font(24),fill='white')
    for i,key in enumerate(ORDER):
        y=255+i*78; width=max(2,round(360*by[key]))
        draw.text((55,y),key,font=font(24),fill='white')
        draw.rectangle((55,y+34,415,y+48),fill='#334155')
        draw.rectangle((55,y+34,55+width,y+48),fill=COLORS[i].replace('0x','#'))
        draw.text((430,y+19),f'{by[key]*100:.1f}%',font=font(20),fill='white')
    draw.text((55,620),f"Model processing: {response['latency_ms']:.0f} ms",font=font(18),fill='#94a3b8')
    image.save(out)

def segment(frame: Path, response: dict, official: str, sample_time: float, out: Path, expected_model_version: str) -> None:
    validate(response, expected_model_version); panel_png=out.with_suffix('.png'); panel(response,official,panel_png)
    observed=out.with_name(out.stem+'-observed.png'); source=Image.open(frame).convert('RGB'); canvas=Image.new('RGB',(760,720),'black'); source.thumbnail((760,570)); canvas.paste(source,((760-source.width)//2,(720-source.height)//2)); ImageDraw.Draw(canvas).text((30,675),f'RECORDED PRODUCTION REPLAY · INPUT FRAME {sample_time:.2f}s',font=font(17,True),fill='#94a3b8'); canvas.save(observed)
    filters="[0:v][1:v]hstack=inputs=2[out]"
    subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(observed),'-loop','1','-i',str(panel_png),'-filter_complex',filters,'-map','[out]','-t','4','-r','30','-c:v','libx264','-pix_fmt','yuv420p','-y',str(out)],check=True)
def card(text: str, sub: str, seconds: int, out: Path) -> None:
    image=Image.new('RGB',(1280,720),'#101816'); draw=ImageDraw.Draw(image)
    for value,y,face,color in [(text,280,font(52,True),'white'),(sub,360,font(24),'#94a3b8')]:
        box=draw.textbbox((0,0),value,font=face); draw.text(((1280-(box[2]-box[0]))/2,y),value,font=face,fill=color)
    png=out.with_suffix('.png'); image.save(png)
    subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(png),'-t',str(seconds),'-r','30','-c:v','libx264','-pix_fmt','yuv420p','-y',str(out)],check=True)
def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--prepared',type=Path,required=True); ap.add_argument('--responses',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--expected-model-version', required=True); args=ap.parse_args()
    req=json.loads((args.prepared/'requests.json').read_text()); responses=json.loads(args.responses.read_text())
    if responses.get('complete') is not True or responses.get('production_api') is not True or responses.get('serving_path') not in {'production_inference_origin','public_customer_api'}:
        raise ValueError('render requires complete recorded production evidence')
    by={x['case_id']:x for x in responses['cases']}; work=args.output.parent/'visual-gestures-render'; work.mkdir(parents=True,exist_ok=True)
    card('SEE THE GESTURE. MAKE A DECISION.','Real production probabilities on licensed IPN Hand footage',3,work/'00.mp4')
    if len(responses['cases']) != len(by) or set(by) != {case['case_id'] for case in req['cases']}:
        raise ValueError('response case IDs do not exactly match the prepared request pack')
    for i,case in enumerate(req['cases'],1): segment(args.prepared/f"{case['case_id']}.jpg",by[case['case_id']]['response'],case['official_label'],case['sample_time_seconds'],work/f'{i:02}.mp4',args.expected_model_version)
    card('ONE MODEL. FOUR CLEAR CHOICES.','Inputs and outputs shown as recorded. Validate on your own task.',3,work/'99.mp4')
    names=['00.mp4']+[f'{i:02}.mp4' for i in range(1,len(req['cases'])+1)]+['99.mp4']
    concat=work/'concat.txt'; concat.write_text(''.join(f"file '{(work/name).resolve()}'\n" for name in names))
    subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart','-y',str(args.output)],check=True)
    decisions=[{'case_id':c['case_id'],'sample_time_seconds':c['sample_time_seconds'],'frame_sha256':c['frame_sha256'],'choice_id':by[c['case_id']]['response']['choice_id'],'probabilities':by[c['case_id']]['response']['probabilities'],'model_processing_ms':by[c['case_id']]['response']['latency_ms']} for c in req['cases']]
    evidence={'demo':'visual-gestures-v11','complete':True,'production_api':True,'serving_path':responses['serving_path'],'public_customer_api_verified':responses.get('public_customer_api_verified',False),'duration_seconds':22,'successful_calls':len(req['cases']),'api_errors':0,'decisions':decisions,'model':'trio-spark-v1.1','serving_identity_verified':True,'source_license':'CC BY 4.0','claim_scope':'Four recorded single-image production decisions over two licensed gesture clips; not live camera throughput, public billing verification, or an accuracy evaluation.','output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}
    (args.output.parent/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n'); print(json.dumps(evidence))
if __name__=='__main__': main()
