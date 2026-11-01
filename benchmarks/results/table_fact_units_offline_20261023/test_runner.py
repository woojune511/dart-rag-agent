"""Synthetic atomic-budget, ownership, coordinate-pool and preservation contracts."""
import copy
import unittest

import run


def source(uid):
    return {'source_id': 'doc:' + uid, 'chunk_id': uid, 'document_id': 'doc',
            'text': '원래의 근거와 단위', 'context': {'literal': '보존'}}


def projection(large=False):
    return {'frame': {'table_locator': '/TABLE', 'document_sha256': '1' * 64},
            'cells': {'row': [1, 0, 1, 1, '항목'], 'head': [0, 1, 1, 2, '기간'],
                      'a': [1, 1, 1, 1, '과대' * 200 if large else '10'],
                      'b': [1, 2, 1, 1, '10']},
            'units': [{'unit_id': 'one', 'at': [1, 1], 'value': 'a', 'row_axes': ['row'], 'column_axes': ['head']},
                      {'unit_id': 'two', 'at': [1, 2], 'value': 'b', 'row_axes': ['row'], 'column_axes': ['head']}]}


def item(key, value):
    return {'physical_key': key, 'projection': value, 'receipt': {'reason': 'synthetic'}}


class BudgetContracts(unittest.TestCase):
    def setUp(self):
        self.cap = run.CAP
        self.packet = {'query': '질문', 'report_scope': {'rcept_no': 'doc'},
                       'documents': [source('one'), source('two')]}

    def tearDown(self):
        run.CAP = self.cap

    def test_append_preserves_original_every_field_and_order(self):
        before = copy.deepcopy(self.packet)
        out, decisions = run.project_packet(self.packet, {
            'one': item('table1', projection()), 'two': item('table2', projection())})
        self.assertEqual(before, self.packet)
        for original, changed in zip(before['documents'], out['documents']):
            self.assertEqual(original, {k: v for k, v in changed.items() if k != run.FIELD})
        self.assertEqual(['attached', 'attached'], [d['status'] for d in decisions])

    def test_exact_utf8_byte_cap_and_not_character_count(self):
        p = projection(); p['units'] = p['units'][:1]
        items = {'one': item('t', p), 'two': item(None, None)}
        full, _ = run.project_packet(self.packet, items)
        run.CAP = len(run.encoded(full).encode('utf-8'))
        out, _ = run.project_packet(self.packet, items)
        self.assertEqual(full, out)
        run.CAP -= 1
        out, decisions = run.project_packet(self.packet, items)
        self.assertEqual(out, self.packet)
        self.assertEqual('rejected_byte_budget', decisions[0]['status'])

    def test_rejected_unit_discards_dependencies_and_next_smaller_fits(self):
        p = projection(True)
        small = copy.deepcopy(p); small['units'] = small['units'][1:]
        expected, _ = run.project_packet(self.packet, {'one': item('t', small), 'two': item(None, None)})
        run.CAP = len(run.encoded(expected).encode('utf-8'))
        out, decisions = run.project_packet(self.packet, {'one': item('t', p), 'two': item(None, None)})
        self.assertEqual(out, expected)
        self.assertEqual(['rejected_byte_budget', 'attached'], [u['status'] for u in decisions[0]['units']])
        self.assertNotIn('a', decisions[0]['cell_pool_locators'])
        wire = out['documents'][0][run.FIELD]
        self.assertEqual(3, len(wire['cells']))
        self.assertTrue(all(i < len(wire['cells']) for u in wire['units'] for i in [u[2], *u[3], *u[4]]))

    def test_dedupe_physical_origin_not_equal_value(self):
        out, decisions = run.project_packet(self.packet, {'one': item('t', projection()), 'two': item(None, None)})
        wire = out['documents'][0][run.FIELD]
        self.assertEqual(4, len(wire['cells']))
        self.assertNotEqual(wire['units'][0][2], wire['units'][1][2])
        self.assertEqual(wire['units'][0][3:], wire['units'][1][3:])
        self.assertEqual(['row', 'head', 'a', 'b'], decisions[0]['cell_pool_locators'])

    def test_first_owner_failure_not_repaired_by_later_owner(self):
        out, decisions = run.project_packet(self.packet, {
            'one': item('same', None), 'two': item('same', projection())})
        self.assertEqual(out, self.packet)
        self.assertEqual(['rejected_global_validation', 'duplicate_table_first_owner_only'], [d['status'] for d in decisions])

    def test_first_owner_budget_failure_not_repaired_by_later_owner(self):
        p = projection(); p['frame']['long_context'] = '너무큼' * 500
        small = projection()
        expected, _ = run.project_packet(self.packet, {'one': item('same', small), 'two': item(None, None)})
        run.CAP = len(run.encoded(expected).encode('utf-8'))
        out, decisions = run.project_packet(self.packet, {'one': item('same', p), 'two': item('same', small)})
        self.assertEqual(out, self.packet)
        self.assertEqual('duplicate_table_first_owner_only', decisions[1]['status'])

    def test_empty_unit_projection_does_not_emit_frame(self):
        p = projection(); p['units'] = []
        out, decisions = run.project_packet(self.packet, {'one': item('t', p), 'two': item(None, None)})
        self.assertEqual(out, self.packet)
        self.assertEqual('no_valid_numeric_units', decisions[0]['status'])

    def test_none_projection_with_no_units_receipt_is_not_global_failure(self):
        empty = item('t', None)
        empty['receipt'] = {'status': 'NO_UNITS', 'reason': 'no_valid_numeric_units'}
        out, decisions = run.project_packet(self.packet, {'one': empty, 'two': item(None, None)})
        self.assertEqual(out, self.packet)
        self.assertEqual('no_valid_numeric_units', decisions[0]['status'])

    def test_unused_later_source_never_refills(self):
        out, _ = run.project_packet(self.packet, {
            'one': item(None, None), 'two': item(None, None), 'third': item('t', projection())})
        self.assertEqual(out, self.packet)

    def test_multiple_tables_have_separate_pools_and_source_ids(self):
        out, _ = run.project_packet(self.packet, {'one': item('a', projection()), 'two': item('b', projection())})
        self.assertEqual(['doc:one', 'doc:two'], [d[run.FIELD]['source_id'] for d in out['documents']])
        self.assertTrue(all(len(d[run.FIELD]['cells']) == 4 for d in out['documents']))

    def test_repeated_serialization_is_deterministic(self):
        items = {'one': item('a', projection()), 'two': item('b', projection())}
        first = run.project_packet(self.packet, items)
        self.assertEqual(first, run.project_packet(self.packet, items))


if __name__ == '__main__':
    result = unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BudgetContracts))
    run.save('runner_synthetic_validation.json', {
        'passed': result.wasSuccessful(), 'tests': result.testsRun,
        'errors': len(result.errors), 'failures': len(result.failures),
        'run_sha256': run.file_sha(run.OUT / 'run.py'),
        'test_sha256': run.file_sha(run.OUT / 'test_runner.py')})
    raise SystemExit(0 if result.wasSuccessful() else 1)
