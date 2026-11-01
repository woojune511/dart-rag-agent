"""Synthetic invariants only; no real question scores inspected before freeze."""
import socket
import unittest
import run


class Contracts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m = run.MorphTokenizer()
        cls.m.fill(['가나다','학교에서','공부했다'])

    def test_ascii_and_numbers_unchanged(self):
        s = 'Acme-X 2024 1,234.56 ABC_99'
        self.assertEqual(self.m(s), run.prior.tokenize_ko(s))

    def test_shared_cache_query_document_and_repeated_terms(self):
        self.assertEqual(self.m('학교에서 학교에서'), self.m('학교에서')*2)
        self.assertEqual(self.m('학교에서'), self.m('학교에서'))

    def test_all_forms_retained_without_pos_filter(self):
        forms = [t.form for t in self.m.kiwi.tokenize('학교에서')]
        self.assertEqual(self.m('학교에서'), forms)

    def test_scope_before_topk(self):
        d = {'a':{'receipt':'A','order':0},'b':{'receipt':'B','order':1}}
        self.assertEqual(run.prior.fold_scores([1,100],['a','b'],d,'A',limit=1)[0]['uid'],'a')

    def test_rrf_ignores_score_scale(self):
        dense = [{'uid':'a','score':0.8}]
        lex = [{'uid':'b','score':100},{'uid':'a','score':1}]
        self.assertEqual(run.prior.merge(dense,lex,{},12),run.prior.merge(dense,[dict(x,score=x['score']*10) for x in lex],{},12))

    def test_whole_source_byte_cap_and_no_mutation(self):
        d = {'a':{'receipt':'R','text':'값'*30000,'metadata':{}},'b':{'receipt':'R','text':'원문 값','metadata':{}}}
        p,o = run.prior.packet({'question':'q','report_scope':{}},[{'uid':'a'},{'uid':'b'}],d,[],set())
        self.assertEqual(o,['a'])
        self.assertEqual(p['documents'][0]['text'],d['b']['text'])

    def test_network_blocked(self):
        with self.assertRaises(RuntimeError):
            socket.create_connection(('example.invalid',443))


if __name__ == '__main__':
    unittest.main()
