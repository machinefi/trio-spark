import ast
import math
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]/'demos/spark-racer'


def validator():
    tree=ast.parse((ROOT/'server_v12.py').read_text())
    fn=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='validate')
    ns={'math':math};exec(compile(ast.Module(body=[fn],type_ignores=[]),'validator','exec'),ns)
    return ns['validate']


def test_native_racer_identity_and_distribution_gate():
    check=validator()
    body={'model':'trio-spark-v1.2','model_version':'trio-spark-v1.1-visual-t4-native4-v1+canonical-choice-id-v2','choice_id':'left','probabilities':[{'choice_id':k,'probability':v} for k,v in [('left',.7),('center',.2),('right',.1)]]}
    assert check(body)==body
    for p in [float('nan'),float('inf'),-.1,True,'0.7']:
        bad=body|{'probabilities':[{'choice_id':'left','probability':p},*body['probabilities'][1:]]}
        with pytest.raises(ValueError):check(bad)
    with pytest.raises(ValueError):check(body|{'model_version':'old'})
    with pytest.raises(ValueError):check(body|{'model_version':'trio-spark-v1.2-2026-10-08'})
    with pytest.raises(ValueError):check(body|{'usage':{'output_tokens':1}})
    with pytest.raises(ValueError):check(body|{'probabilities':[body['probabilities'][0]]*3})


def test_only_version_timing_trace_changes_to_historical_game():
    original=(ROOT/'index.html').read_text();new=(ROOT/'index-v12.html').read_text()
    # Existing course, art, physics and target interpolation stay byte-identical.
    for start,end in [('function project','async function decide'),('function tick','$(\'start\').onclick')]:
        old=original[original.index(start):original.index(end)]
        actual=new[new.index(start):new.index(end)]
        old=old.replace('45-t','DURATION-t').replace('Math.min(45,t)/45','Math.min(DURATION,t)/DURATION').replace('if(t>=45)finish()','if(t>=DURATION)finish()')
        assert actual==old
    assert 'target=keys.indexOf(v.choice)' in new
    assert '1100-(performance.now()-lastDecisionStartMs)' in new
    server=(ROOT/'server_v12.py').read_text()
    assert "LIMIT=39" in server and 'DEADLINE=time.monotonic()+90' in server
    assert 'LAST_START+1.1-time.monotonic()' in server
    assert "URL='https://platform.machinefi.com/api/spark/v1/decisions'" in server
    assert 'NoRedirect' in server
    assert 'trio-spark-v1.1' in (ROOT/'server.py').read_text()


def test_recorder_ack_flag_parses_before_credentials_or_calls(tmp_path,monkeypatch):
    import importlib.util,sys
    spec=importlib.util.spec_from_file_location('racer_recorder',ROOT/'record_public_v12.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.delenv('TRIO_SPARK_API_KEY',raising=False)
    monkeypatch.setattr(sys,'argv',['record_public_v12.py','--ack-up-to-39-visual-calls','--output',str(tmp_path/'not-created')])
    with pytest.raises(ValueError,match='Credential environment absent'):module.main()
    assert not (tmp_path/'not-created').exists()
