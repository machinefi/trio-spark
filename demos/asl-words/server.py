#!/usr/bin/env python3
"""Loopback-only HTTP server for the ASL ten-word camera prototype."""
from __future__ import annotations
import argparse, importlib.util, json, mimetypes, threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

from recognizer import Recognizer, RecognitionError, vocabulary

MAX_BODY = 4 * 1024 * 1024
WEB = Path(__file__).with_name('web')

def public_vocabulary() -> dict:
    raw=vocabulary(); words=[{'id':word['id'],'display':word['label']} for bank in raw['banks'] for word in bank['words']]
    if len(words)!=10: raise RuntimeError('exactly ten words are required')
    return {'language':raw['language'],'version':raw['version'],'status':raw['status'],'vocabulary':words}

def loopback_host(value: str) -> bool:
    try: return urlsplit('//' + value).hostname in {'127.0.0.1','localhost','::1'}
    except ValueError: return False

def normalize_origins(values) -> tuple[str,...]:
    origins=[]
    for value in values:
        parsed=urlsplit(value)
        if parsed.scheme!='https' or not parsed.hostname or parsed.path not in ('','/') or parsed.query or parsed.fragment or parsed.username or parsed.password:
            raise ValueError('public origins must be exact HTTPS origins without paths or credentials')
        origins.append(f'https://{parsed.netloc}')
    return tuple(dict.fromkeys(origins))

def load_private(path: Path):
    spec=importlib.util.spec_from_file_location('asl_private_recognizer',path)
    if spec is None or spec.loader is None: raise RuntimeError('private recognizer module could not be loaded')
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    instance=module.create_recognizer()
    if not callable(getattr(instance,'recognize',None)): raise RuntimeError('private module must return a recognizer')
    return instance

def make_server(recognizer, host='127.0.0.1', port=8765, allowed_origins=()):
    gate=threading.Lock(); allowed_origins=normalize_origins(allowed_origins); allowed_hosts={urlsplit(value).netloc for value in allowed_origins}
    class Handler(BaseHTTPRequestHandler):
        server_version='ASLPrototype/1'; sys_version=''
        def log_message(self, fmt, *args): print(f'{self.client_address[0]} {fmt%args}')
        def secure(self) -> bool:
            request_host=self.headers.get('Host','')
            if self.client_address[0] not in {'127.0.0.1','::1'} or not (loopback_host(request_host) or request_host in allowed_hosts):
                self.reply(403,{'error':{'code':'forbidden','message':'Loopback access only.'}}); return False
            return True
        def headers_common(self, content_type, length):
            self.send_header('Content-Type',content_type); self.send_header('Content-Length',str(length)); self.send_header('Cache-Control','no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.send_header('X-Frame-Options','DENY'); self.send_header('Referrer-Policy','no-referrer'); self.send_header('Permissions-Policy','camera=(self)'); self.send_header('Content-Security-Policy',"default-src 'self'; img-src 'self' data:; media-src 'self' blob:; connect-src 'self'; script-src 'self'; style-src 'self'; frame-ancestors 'none'; base-uri 'none'")
        def reply(self,status,value):
            raw=json.dumps(value,separators=(',',':')).encode(); self.send_response(status); self.headers_common('application/json; charset=utf-8',len(raw)); self.end_headers(); self.wfile.write(raw)
        def do_GET(self):
            if not self.secure(): return
            if self.path=='/api/config': self.reply(200,public_vocabulary()); return
            path={'/':'index.html','/index.html':'index.html','/app.js':'app.js','/style.css':'style.css'}.get(self.path)
            if path is None: self.reply(404,{'error':{'code':'not_found','message':'Not found.'}}); return
            raw=(WEB/path).read_bytes(); self.send_response(200); self.headers_common(mimetypes.guess_type(path)[0] or 'application/octet-stream',len(raw)); self.end_headers(); self.wfile.write(raw)
        def do_POST(self):
            if not self.secure(): return
            host=self.headers.get('Host',''); origin=self.headers.get('Origin','')
            if origin not in {f'http://{host}',f'https://{host}',*allowed_origins} or self.headers.get('X-ASL-Prototype')!='1':
                self.reply(403,{'error':{'code':'forbidden','message':'Same-origin prototype request required.'}}); return
            if self.path!='/api/recognize': self.reply(404,{'error':{'code':'not_found','message':'Not found.'}}); return
            if self.headers.get_content_type()!='application/json': self.reply(415,{'error':{'code':'unsupported_media_type','message':'JSON is required.'}}); return
            try: length=int(self.headers.get('Content-Length','-1'))
            except ValueError: length=-1
            if length<2 or length>MAX_BODY: self.reply(413,{'error':{'code':'too_large','message':'Request body is outside the local limit.'}}); return
            if not gate.acquire(blocking=False): self.reply(429,{'error':{'code':'busy','message':'One recognition request is already running.'}}); return
            try:
                try:
                    value=json.loads(self.rfile.read(length))
                    if not isinstance(value,dict) or set(value)!={'frames'}: raise RecognitionError('Request requires only frames.')
                    result=recognizer.recognize(value['frames']); self.reply(200,result)
                except (json.JSONDecodeError,RecognitionError,KeyError,TypeError) as error:
                    self.reply(400,{'error':{'code':'invalid_request','message':str(error)[:240]}})
                except Exception:
                    self.reply(502,{'error':{'code':'recognizer_failed','message':'Recognition failed without a retry.'}})
            finally: gate.release()
    return ThreadingHTTPServer((host,port),Handler)

def serve(recognizer, host='127.0.0.1', port=8765, allowed_origins=()):
    server=make_server(recognizer,host,port,allowed_origins)
    print(f'ASL prototype listening on http://{host}:{server.server_port}',flush=True)
    try: server.serve_forever()
    finally: server.server_close()

def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--host',default='127.0.0.1',choices=('127.0.0.1','::1')); parser.add_argument('--port',type=int,default=8765); parser.add_argument('--recognizer-module',type=Path); parser.add_argument('--public-origin',action='append',default=[])
    args=parser.parse_args(); instance=load_private(args.recognizer_module) if args.recognizer_module else Recognizer(); serve(instance,args.host,args.port,args.public_origin)

if __name__=='__main__': main()
