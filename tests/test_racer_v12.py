import ast
import importlib.util
import math
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1] / 'demos/spark-racer'


def validator():
    tree = ast.parse((ROOT / 'server_v12.py').read_text())
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == 'validate')
    namespace = {'math': math}
    exec(compile(ast.Module(body=[fn], type_ignores=[]), 'validator', 'exec'), namespace)
    return namespace['validate']


class TestRacerV12(unittest.TestCase):
    def test_native_racer_identity_and_distribution_gate(self):
        check = validator()
        body = {'model': 'trio-spark-v1.2',
                'model_version': 'trio-spark-v1.1-visual-t4-native4-v1+canonical-choice-id-v2',
                'choice_id': 'left', 'probabilities': [
                    {'choice_id': k, 'probability': v}
                    for k, v in [('left', .7), ('center', .2), ('right', .1)]]}
        self.assertEqual(check(body), body)
        for probability in [float('nan'), float('inf'), -.1, True, '0.7']:
            bad = body | {'probabilities': [
                {'choice_id': 'left', 'probability': probability}, *body['probabilities'][1:]]}
            with self.subTest(probability=probability), self.assertRaises(ValueError):
                check(bad)
        for version in ['old', 'trio-spark-v1.2-2026-10-08']:
            with self.subTest(version=version), self.assertRaises(ValueError):
                check(body | {'model_version': version})
        with self.assertRaises(ValueError):
            check(body | {'usage': {'output_tokens': 1}})
        with self.assertRaises(ValueError):
            check(body | {'probabilities': [body['probabilities'][0]] * 3})

    def test_only_version_timing_trace_changes_to_historical_game(self):
        original = (ROOT / 'index.html').read_text()
        new = (ROOT / 'index-v12.html').read_text()
        for start, end in [('function project', 'async function decide'),
                           ('function tick', "$('start').onclick")]:
            old = original[original.index(start):original.index(end)]
            actual = new[new.index(start):new.index(end)]
            old = old.replace('45-t', 'DURATION-t').replace(
                'Math.min(45,t)/45', 'Math.min(DURATION,t)/DURATION').replace(
                'if(t>=45)finish()', 'if(t>=DURATION)finish()')
            self.assertEqual(actual, old)
        self.assertIn('target=keys.indexOf(v.choice)', new)
        self.assertIn('1100-(performance.now()-lastDecisionStartMs)', new)
        server = (ROOT / 'server_v12.py').read_text()
        self.assertIn('LIMIT=39', server)
        self.assertIn('DEADLINE=time.monotonic()+90', server)
        self.assertIn('LAST_START+1.1-time.monotonic()', server)
        self.assertIn("URL='https://platform.machinefi.com/api/spark/v1/decisions'", server)
        self.assertIn('NoRedirect', server)
        self.assertIn('trio-spark-v1.1', (ROOT / 'server.py').read_text())

    def test_recorder_ack_flag_parses_before_credentials_or_calls(self):
        spec = importlib.util.spec_from_file_location('racer_recorder', ROOT / 'record_public_v12.py')
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as scratch:
            output = Path(scratch) / 'not-created'
            argv = ['record_public_v12.py', '--ack-up-to-39-visual-calls', '--output', str(output)]
            with patch.dict(os.environ, {}, clear=True), patch.object(sys, 'argv', argv):
                with self.assertRaisesRegex(ValueError, 'Credential environment absent'):
                    module.main()
            self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
