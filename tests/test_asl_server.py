import http.client, importlib.util, json, threading, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]; DIR=ROOT/'demos/asl-words'
spec=importlib.util.spec_from_file_location('recognizer',DIR/'recognizer.py'); recognizer=importlib.util.module_from_spec(spec);spec.loader.exec_module(recognizer)
import sys;sys.modules['recognizer']=recognizer
spec=importlib.util.spec_from_file_location('asl_server',DIR/'server.py'); server_module=importlib.util.module_from_spec(spec);spec.loader.exec_module(server_module)

class FixtureRecognizer:
    """Typed UI fixture. It is never presented as a model result."""
    def __init__(self): self.entered=threading.Event();self.release=threading.Event();self.block=False
    def recognize(self,frames):
        self.entered.set()
        if self.block:self.release.wait(2)
        return {'status':'recognized','label':'HELLO','word_id':'hello','score':.8,'score_scope':'conditional_within_bank','route':{},'leaf':{},'calls':2,'latency_ms':12}

def running(fixture):
    server=server_module.make_server(fixture,'127.0.0.1',0); thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();return server,thread

def request(server,method,path,body=None,headers=None):
    connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3); base={'Host':f'127.0.0.1:{server.server_port}'};base.update(headers or {});connection.request(method,path,body=body,headers=base);response=connection.getresponse();raw=response.read();connection.close();return response.status,response.headers,json.loads(raw) if response.headers.get_content_type()=='application/json' else raw

def test_config_static_security_and_no_secret_in_browser_bundle():
    server,thread=running(FixtureRecognizer())
    try:
        status,headers,value=request(server,'GET','/api/config');assert status==200 and len(value['vocabulary'])==10 and value['status']=='experimental_unvalidated';assert headers['Cache-Control']=='no-store'
        status,headers,raw=request(server,'GET','/app.js');assert status==200 and b'TRIO_SPARK_API_KEY' not in raw and "default-src 'self'" in headers['Content-Security-Policy']
    finally:server.shutdown();server.server_close();thread.join()

def test_post_requires_same_origin_csrf_and_singleflight():
    fixture=FixtureRecognizer();fixture.block=True;server,thread=running(fixture);body=json.dumps({'frames':[]});host=f'127.0.0.1:{server.server_port}';valid={'Origin':f'http://{host}','X-ASL-Prototype':'1','Content-Type':'application/json'}
    try:
        assert request(server,'POST','/api/recognize',body,{'Content-Type':'application/json'})[0]==403
        first={}
        worker=threading.Thread(target=lambda:first.update(result=request(server,'POST','/api/recognize',body,valid)));worker.start();assert fixture.entered.wait(1)
        assert request(server,'POST','/api/recognize',body,valid)[0]==429
        fixture.release.set();worker.join();assert first['result'][0]==200
    finally:fixture.release.set();server.shutdown();server.server_close();thread.join()

def test_private_https_origin_is_exact_and_binding_stays_loopback():
    fixture=FixtureRecognizer();server=server_module.make_server(fixture,'127.0.0.1',0,['https://demo.example.ts.net']);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start();body=json.dumps({'frames':[]});valid={'Host':'demo.example.ts.net','Origin':'https://demo.example.ts.net','X-ASL-Prototype':'1','Content-Type':'application/json'}
    try:
        connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=3);connection.request('POST','/api/recognize',body=body,headers=valid);response=connection.getresponse();assert response.status==200;response.read();connection.close()
        wrong={**valid,'Origin':'https://other.example.ts.net'};assert request(server,'POST','/api/recognize',body,wrong)[0]==403
        assert server.server_address[0]=='127.0.0.1'
    finally:server.shutdown();server.server_close();thread.join()
