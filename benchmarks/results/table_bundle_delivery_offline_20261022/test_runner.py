"""Synthetic budget/order tests for the isolated packet experiment only."""
import copy
import unittest

import run


def source(uid):
    return {'source_id': 'doc:' + uid, 'chunk_id': uid, 'document_id': 'doc',
            'text': '원래의 근거와 단위', 'context': {'literal': '보존'}}


def item(key, payload):
    return {'physical_key': key, 'bundle': payload, 'receipt': {'reason': 'synthetic'}}


class BudgetContracts(unittest.TestCase):
    def setUp(self):
        self.cap = run.CAP
        self.packet = {'query': '질문', 'report_scope': {'rcept_no': 'doc'},
                       'documents': [source('one'), source('two')]}

    def tearDown(self):
        run.CAP = self.cap

    def test_append_preserves_original_values_and_order(self):
        before = copy.deepcopy(self.packet)
        out, decisions = run.project_packet(self.packet, [], {
            'one': item('table1', {'grid': [['행', '값'], ['A', '3']]}),
            'two': item('table2', {'grid': [['행', '값'], ['B', '4']]})})
        self.assertEqual(before, self.packet)
        self.assertEqual([d['chunk_id'] for d in out['documents']], ['one', 'two'])
        for original, changed in zip(before['documents'], out['documents']):
            self.assertEqual(original, {k: v for k, v in changed.items() if k != 'table_evidence'})
        self.assertEqual([d['status'] for d in decisions], ['attached', 'attached'])

    def test_exact_utf8_budget_accepts_not_character_count(self):
        bundle = {'grid': [['한글' * 9]]}
        proposed = copy.deepcopy(self.packet)
        proposed['documents'][0]['table_evidence'] = bundle
        run.CAP = len(run.encoded(proposed).encode('utf-8'))
        items = {'one': item('table1', bundle), 'two': item(None, None)}
        out, decisions = run.project_packet(self.packet, [], items)
        self.assertEqual(decisions[0]['status'], 'attached')
        self.assertEqual(len(run.encoded(out).encode('utf-8')), run.CAP)
        run.CAP -= 1
        out, decisions = run.project_packet(self.packet, [], items)
        self.assertEqual(out, self.packet)
        self.assertEqual(decisions[0]['status'], 'rejected_byte_budget')

    def test_oversize_table_does_not_remove_source_and_small_next_can_fit(self):
        run.CAP = len(run.encoded(self.packet).encode('utf-8')) + 120
        out, decisions = run.project_packet(self.packet, [], {
            'one': item('table1', {'grid': [['과대' * 200]]}),
            'two': item('table2', {'grid': [['값']]})})
        self.assertEqual(decisions[0]['status'], 'rejected_byte_budget')
        self.assertEqual(decisions[1]['status'], 'attached')
        self.assertEqual(len(out['documents']), 2)
        self.assertEqual(out['documents'][0], self.packet['documents'][0])

    def test_rejected_first_owner_not_repaired_from_later_duplicate(self):
        out, decisions = run.project_packet(self.packet, [], {
            'one': item('same_physical_table', None),
            'two': item('same_physical_table', {'grid': [['later owner value']]})})
        self.assertEqual(out, self.packet)
        self.assertEqual([d['status'] for d in decisions],
                         ['rejected_structural_validation', 'duplicate_table_first_owner_only'])

    def test_no_refill_from_hits_not_in_original_packet(self):
        out, _ = run.project_packet(self.packet, [source('third')], {
            'one': item(None, None), 'two': item(None, None)})
        self.assertEqual(out, self.packet)
        self.assertNotIn('third', str(out))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BudgetContracts))
    run.save('runner_synthetic_validation.json', {
        'passed': result.wasSuccessful(), 'tests': result.testsRun,
        'errors': len(result.errors), 'failures': len(result.failures)})
    raise SystemExit(0 if result.wasSuccessful() else 1)
