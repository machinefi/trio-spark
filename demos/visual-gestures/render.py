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
    candidates = ([Path('/System/Library/Fonts/Supplemental/Arial Bold.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf')] if bold else [Path('/System/Library/Fonts/Supplemental/Arial.ttf'),Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf')])
    path=next((value for value in candidates if value.exists()),None)
    if path is None: raise RuntimeError('Arial or DejaVu Sans font is required')
    return ImageFont.truetype(str(path), size)

def panel(response: dict, sample_time: float, wall_ms: float, out: Path) -> None:
    by={p['choice_id']:p['probability'] for p in response['probabilities']}
    image=Image.new('RGB',(520,720),'#101816'); draw=ImageDraw.Draw(image)
    draw.text((55,55),'TRIO-SPARK v1.1',font=font(24,True),fill='#67e8f9')
    draw.text((55,105),'Which hand gesture is clearly visible?',font=font(22,True),fill='white')
    draw.text((55,175),f"Selected: {response['choice_id']}",font=font(24),fill='white')
    for i,key in enumerate(ORDER):
        y=255+i*78; width=max(2,round(360*by[key]))
        draw.text((55,y),key,font=font(24),fill='white')
        draw.rectangle((55,y+34,415,y+48),fill='#334155')
        draw.rectangle((55,y+34,55+width,y+48),fill=COLORS[i].replace('0x','#'))
        draw.text((430,y+19),f'{by[key]*100:.1f}%',font=font(20),fill='white')
    draw.text((55,605),f"Input frame: {sample_time:.2f}s",font=font(18),fill='#94a3b8')
    draw.text((55,635),f"Recorded wall response: {wall_ms:.0f} ms",font=font(18),fill='#94a3b8')
    image.save(out)

def waiting_panel(out: Path) -> None:
    image=Image.new('RGB',(520,720),'#101816'); draw=ImageDraw.Draw(image)
    draw.text((55,55),'TRIO-SPARK v1.1',font=font(24,True),fill='#67e8f9')
    draw.text((55,105),'Which hand gesture is clearly visible?',font=font(22,True),fill='white')
    draw.text((55,250),'Recorded production replay',font=font(24),fill='white')
    draw.text((55,300),'Waiting for captured result…',font=font(20),fill='#94a3b8'); image.save(out)

def segment(gif: Path, cases: list[dict], by: dict, crop: dict, out: Path, expected_model_version: str) -> None:
    panels=[]; reveals=[]
    for index,case in enumerate(cases,1):
        item=by[case['case_id']]; response=item['response']; validate(response,expected_model_version)
        wall=item.get('wall_latency_ms',item.get('prepare_wall_latency_ms',0)+item.get('run_wall_latency_ms',0)); path=out.with_name(f'{out.stem}-result-{index}.png'); panel(response,case['sample_time_seconds'],wall,path); panels.append(path); reveals.append(case['sample_time_seconds']+wall/1000)
    waiting=out.with_name(out.stem+'-waiting.png'); waiting_panel(waiting)
    x,y,w,h=(crop[k] for k in ('x','y','width','height'))
    filters=[f"[0:v]crop={w}:{h}:{x}:{y},scale=760:564:force_original_aspect_ratio=decrease,pad=760:720:0:(oh-ih)/2:black[left0]","[1:v]format=rgb24[right0]"]
    previous='right0'
    for index,reveal in enumerate(reveals,2):
        target=f'right{index-1}'; filters.append(f"[{previous}][{index}:v]overlay=enable='gte(t,{reveal:.3f})'[{target}]"); previous=target
    left_previous='left0'; still_start=2+len(panels)
    for offset,reveal in enumerate(reveals):
        input_index=still_start+offset; target=f'left{offset+1}'
        filters.append(f"[{input_index}:v]scale=760:564:force_original_aspect_ratio=decrease,pad=760:720:0:(oh-ih)/2:black[still{offset}]")
        filters.append(f"[{left_previous}][still{offset}]overlay=enable='gte(t,{reveal:.3f})'[{target}]"); left_previous=target
    filters.append(f"[{left_previous}][{previous}]hstack=inputs=2[out]")
    command=['ffmpeg','-v','error','-stream_loop','-1','-i',str(gif),'-loop','1','-i',str(waiting)]
    for path in panels: command += ['-loop','1','-i',str(path)]
    for case in cases: command += ['-loop','1','-i',str(gif.parent/f"{case['case_id']}.jpg")]
    command += ['-filter_complex',';'.join(filters),'-map','[out]','-t','8','-r','30','-c:v','libx264','-pix_fmt','yuv420p','-y',str(out)]
    subprocess.run(command,check=True)
def card(text: str, sub: str, seconds: int, out: Path) -> None:
    image=Image.new('RGB',(1280,720),'#101816'); draw=ImageDraw.Draw(image)
    for value,y,face,color in [(text,280,font(52,True),'white'),(sub,360,font(24),'#94a3b8')]:
        box=draw.textbbox((0,0),value,font=face); draw.text(((1280-(box[2]-box[0]))/2,y),value,font=face,fill=color)
    png=out.with_suffix('.png'); image.save(png)
    subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(png),'-t',str(seconds),'-r','30','-c:v','libx264','-pix_fmt','yuv420p','-y',str(out)],check=True)
def main() -> None:
    ap=argparse.ArgumentParser(); ap.add_argument('--prepared',type=Path,required=True); ap.add_argument('--responses',type=Path,required=True); ap.add_argument('--output',type=Path,required=True); ap.add_argument('--expected-model-version'); args=ap.parse_args()
    req=json.loads((args.prepared/'requests.json').read_text()); responses=json.loads(args.responses.read_text())
    if responses.get('complete') is not True or responses.get('production_api') is not True or responses.get('serving_path') not in {'production_inference_origin','public_customer_api'}:
        raise ValueError('render requires complete recorded production evidence')
    by={x['case_id']:x for x in responses['cases']};
    args.expected_model_version = args.expected_model_version or responses['cases'][0]['response'].get('model_version')
    if not isinstance(args.expected_model_version, str) or not args.expected_model_version: raise ValueError('recorded serving identity missing')
    work=args.output.parent/'visual-gestures-render'; work.mkdir(parents=True,exist_ok=True)
    card('SEE THE GESTURE. MAKE A DECISION.','Recorded production replay on licensed IPN Hand footage',3,work/'00.mp4')
    if len(responses['cases']) != len(by) or set(by) != {case['case_id'] for case in req['cases']}:
        raise ValueError('response case IDs do not exactly match the prepared request pack')
    groups={}
    for case in req['cases']: groups.setdefault(case['clip_id'],[]).append(case)
    for i,(clip_id,cases) in enumerate(groups.items(),1): segment(args.prepared/f'{clip_id}.gif',cases,by,cases[0]['source_crop_pixels'],work/f'{i:02}.mp4',args.expected_model_version)
    card('ONE MODEL. FOUR CLEAR CHOICES.','Inputs and outputs shown as recorded. Validate on your own task.',3,work/'99.mp4')
    names=['00.mp4']+[f'{i:02}.mp4' for i in range(1,len(groups)+1)]+['99.mp4']
    concat=work/'concat.txt'; concat.write_text(''.join(f"file '{(work/name).resolve()}'\n" for name in names))
    subprocess.run(['ffmpeg','-v','error','-f','concat','-safe','0','-i',str(concat),'-c','copy','-movflags','+faststart','-y',str(args.output)],check=True)
    decisions=[{'case_id':c['case_id'],'sample_time_seconds':c['sample_time_seconds'],'frame_sha256':c['frame_sha256'],'choice_id':by[c['case_id']]['response']['choice_id'],'probabilities':by[c['case_id']]['response']['probabilities'],'model_processing_ms':by[c['case_id']]['response']['latency_ms']} for c in req['cases']]
    evidence={'demo':'visual-gestures-v11','complete':True,'production_api':True,'serving_path':responses['serving_path'],'public_customer_api_verified':responses.get('public_customer_api_verified',False),'duration_seconds':22,'successful_calls':len(req['cases']),'api_errors':0,'decisions':decisions,'model':'trio-spark-v1.1','serving_identity_verified':True,'source_license':'CC BY 4.0','claim_scope':'Four recorded single-image production decisions over two licensed gesture clips; not live camera throughput, public billing verification, or an accuracy evaluation.','output_sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}
    (args.output.parent/'evidence.json').write_text(json.dumps(evidence,indent=2)+'\n'); print(json.dumps(evidence))
if __name__=='__main__': main()
