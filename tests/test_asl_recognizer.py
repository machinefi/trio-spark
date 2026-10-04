import base64
import copy
import importlib.util
from pathlib import Path
import unittest

P=Path(__file__).resolve().parents[1]/'demos/asl-words/recognizer.py'
spec=importlib.util.spec_from_file_location('recognizer',P); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)

def frames():
    # Signature-only unit fixture: never submitted to a model.
    data=base64.b64encode(b'\xff\xd8\xffunit-fixture').decode()
    return [{'mime_type':'image/jpeg','data_base64':data,'timestamp_ms':t} for t in (0,400,800,1200)]

def response(payload, chosen):
    choices=payload['choices']
    return {'model':m.MODEL,'choice_id':chosen,'probabilities':[{'choice_id':c['id'],'probability':1 if c['id']==chosen else 0} for c in choices]}

class Tests(unittest.TestCase):
    def test_both_banks_reachable_with_identical_media_and_bounded_choices(self):
        for bank,word in [('bank_a','hello'),('bank_b','water')]:
            seen=[]
            def call(p):
                seen.append(copy.deepcopy(p));return response(p,bank if len(seen)==1 else word)
            out=m.Recognizer(caller=call).recognize(frames())
            self.assertEqual(out['word_id'],word);self.assertEqual(out['calls'],2)
            self.assertEqual(seen[0]['media'],seen[1]['media'])
            self.assertEqual([len(p['choices']) for p in seen],[4,7])
            self.assertEqual(out['score_scope'],'conditional_within_bank')
            self.assertNotIn('probabilities',out)
    def test_no_sign_and_unclear_do_not_force_word_or_extra_call(self):
        for selected in ('no_sign','unclear'):
            calls=[]
            def call(p): calls.append(p);return response(p,selected)
            out=m.Recognizer(caller=call).recognize(frames())
            self.assertEqual(out['status'],selected);self.assertIsNone(out['label']);self.assertEqual(len(calls),1)
    def test_leaf_unclear_remains_unclear_no_fallback_retry(self):
        n=[]
        def call(p): n.append(p);return response(p,'bank_b' if len(n)==1 else 'unclear')
        out=m.Recognizer(caller=call).recognize(frames())
        self.assertEqual(out['status'],'unclear');self.assertEqual(len(n),2)
    def test_bad_media_never_reaches_model(self):
        bad=frames();bad[2]['timestamp_ms']=0
        calls=[]
        with self.assertRaises(m.RecognitionError):m.Recognizer(caller=lambda p:calls.append(p)).recognize(bad)
        self.assertFalse(calls)
    def test_invalid_distribution_rejected(self):
        def call(p):
            r=response(p,'bank_a');r['probabilities'][0]['probability']=float('nan');return r
        with self.assertRaises(m.RecognitionError):m.Recognizer(caller=call).recognize(frames())

if __name__=='__main__':unittest.main()
