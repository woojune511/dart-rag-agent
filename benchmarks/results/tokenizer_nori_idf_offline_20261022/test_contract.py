"""Frozen linguistic and execution gates, before any new retrieval scores."""
import math
import socket
import unittest
from collections import Counter
import run

TEXTS=['판매대수의','금융상품판매대리','상품을 매대에 놓았다.','현금흐름표에서','현금흐름',
       '가곡역','비급여','급여','미확정','확정','포함하지 않는다','포함한다','Acme-X 2024 1,234.56 ABC_99',
       '학교에서 책을 읽었다.','학교에서 책을 읽었다.','안 된다','된다']

class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rows=run.java_tokens(TEXTS,'fixtures',trace=True)
        cls.tokens=dict(zip(TEXTS,rows))
        run.save('fixture_tokens.json',[{'text':s,'legacy':run.prior.tokenize_ko(s),'nori':t} for s,t in zip(TEXTS,rows)])

    def test_false_boundary_and_real_word(self):
        self.assertNotIn('매대',self.tokens['판매대수의'])
        self.assertNotIn('매대',self.tokens['금융상품판매대리'])
        self.assertIn('매대',self.tokens['상품을 매대에 놓았다.'])

    def test_compound_components(self):
        self.assertTrue({'현금','흐름'} <= set(self.tokens['현금흐름표에서']) & set(self.tokens['현금흐름']))
        self.assertTrue({'가곡역','가곡','역'} <= set(self.tokens['가곡역']))

    def test_prefixes_preserve_polarity(self):
        self.assertIn('비',self.tokens['비급여'])
        self.assertIn('미',self.tokens['미확정'])
        self.assertNotEqual(self.tokens['비급여'],self.tokens['급여'])
        self.assertNotEqual(self.tokens['미확정'],self.tokens['확정'])

    def test_negation_and_content_verbs(self):
        self.assertIn('않',self.tokens['포함하지 않는다'])
        self.assertIn('안',self.tokens['안 된다'])
        self.assertNotEqual(self.tokens['포함하지 않는다'],self.tokens['포함한다'])

    def test_same_query_document_and_ascii(self):
        s='Acme-X 2024 1,234.56 ABC_99'
        self.assertEqual(self.tokens[s],run.prior.tokenize_ko(s))
        rows=run.prior.load(run.OUT/'fixture_tokens.json')
        self.assertEqual(rows[13]['nori'],rows[14]['nori'])
        self.assertNotIn('에서',self.tokens['학교에서 책을 읽었다.'])

    def test_idf_is_the_only_score_change(self):
        idx=run.prior.BM25Okapi([['common','a'],['common','b'],['common','c'],['rare']])
        pos=run.positive_idf(idx)
        self.assertIs(idx.doc_freqs,pos.doc_freqs)
        self.assertIs(idx.doc_len,pos.doc_len)
        self.assertEqual((idx.k1,idx.b,idx.avgdl),(pos.k1,pos.b,pos.avgdl))
        self.assertGreater(pos.idf['rare'],pos.idf['common'])
        self.assertAlmostEqual(pos.idf['common'],math.log1p(1.5/3.5))
        self.assertEqual(idx.idf['a'],run.prior.BM25Okapi([['common','a'],['common','b'],['common','c'],['rare']]).idf['a'])

    def test_scope_rrf_packet_and_network(self):
        d={'a':{'receipt':'A','order':0},'b':{'receipt':'B','order':1}}
        self.assertEqual(run.prior.fold_scores([1,100],['a','b'],d,'A',limit=1)[0]['uid'],'a')
        dense=[{'uid':'a','score':.8}];lex=[{'uid':'b','score':100},{'uid':'a','score':1}]
        self.assertEqual(run.prior.merge(dense,lex,{},12),run.prior.merge(dense,[dict(x,score=x['score']*10) for x in lex],{},12))
        d={'a':{'receipt':'R','text':'값'*30000,'metadata':{}},'b':{'receipt':'R','text':'원문 값','metadata':{}}}
        p,o=run.prior.packet({'question':'q','report_scope':{}},[{'uid':'a'},{'uid':'b'}],d,[],set())
        self.assertEqual(o,['a']);self.assertEqual(p['documents'][0]['text'],d['b']['text'])
        with self.assertRaises(RuntimeError):socket.create_connection(('example.invalid',443))

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(Contracts)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    run.save('contract_result.json',{'passed':result.wasSuccessful(),'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)})
    raise SystemExit(0 if result.wasSuccessful() else 1)
