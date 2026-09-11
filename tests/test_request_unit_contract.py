"""Request transport/ownership, not a semantic completeness oracle."""

from copy import deepcopy
from dataclasses import FrozenInstanceError
import unittest

from src.agent.financial_request_units import (
    build_request_units, project_request_units, request_unit_errors,
)
from src.agent.financial_graph_models import AnswerObligation


class RequestUnitContractTests(unittest.TestCase):
    def test_exact_partition_with_spacing_decimals_quotes_and_paragraphs(self):
        query = '  Compare 1.25 and (2.50).\r\n\r\n\t"Keep the sign!"  한계도 밝혀라。\n끝  '
        units = build_request_units(query)
        self.assertEqual(''.join(unit.text for unit in units), query)
        self.assertEqual([unit.request_unit_id for unit in units],
                         ['request_001', 'request_002', 'request_003', 'request_004'])
        self.assertEqual(units, build_request_units(query))
        for unit in units:
            self.assertEqual(query[unit.start:unit.end], unit.text)
        with self.assertRaises(FrozenInstanceError):
            units[0].text = 'replacement'

    def test_no_truncation_or_semantic_clause_classification(self):
        query = 'a; b, c ' * 400
        units = build_request_units(query)
        self.assertEqual(len(units), 1)
        self.assertEqual(units[0].text, query)
        self.assertEqual(build_request_units(' \n\t'), ())
        self.assertEqual(''.join(unit.text for unit in build_request_units('alpha\n  ')), 'alpha\n  ')

    def test_reference_projection_is_owned_ordered_and_lossless(self):
        units = build_request_units('First.\nSecond. Third.')
        rows = [{'obligation_id': 'b', 'request_unit_ids': ['request_003', 'request_001']},
                {'obligation_id': 'a', 'request_unit_ids': ['request_001']}]
        before = deepcopy(rows)
        projected = project_request_units(units, rows)
        self.assertEqual(list(projected), ['request_001', 'request_003'])
        self.assertEqual(projected['request_001'], {'text': 'First.\n', 'span': [0, 7]})
        projected['request_001']['text'] = 'mutated'
        self.assertEqual(units[0].text, 'First.\n')
        self.assertEqual(rows, before)

    def test_every_unit_has_an_owner_and_shared_units_are_allowed(self):
        units = build_request_units('First. Second.')
        rows = [{'obligation_id': 'a', 'request_unit_ids': ['request_001', 'request_002']},
                {'obligation_id': 'b', 'request_unit_ids': ['request_001']}]
        self.assertEqual(request_unit_errors(units, rows), [])
        rows[0]['request_unit_ids'] = ['request_001']
        error, = request_unit_errors(units, rows)
        self.assertEqual(error['code'], 'unassigned_request_unit')
        self.assertEqual(error['request_unit_id'], 'request_002')
        self.assertEqual(error['repair_action'], 'repair_requirements')

    def test_unknown_missing_and_malformed_references_are_not_inferred(self):
        units = build_request_units('One request')
        for refs, expected in ((None, 'missing_request_unit_refs'),
                               ([], 'missing_request_unit_refs'),
                               ('request_001', 'invalid_request_unit_refs'),
                               (['invented'], 'unknown_request_unit_id')):
            with self.subTest(refs=refs):
                row = {'obligation_id': 'owner'}
                if refs is not None:
                    row['request_unit_ids'] = refs
                before = deepcopy(row)
                errors = request_unit_errors(units, [row])
                self.assertEqual(errors[0]['code'], expected)
                self.assertEqual(errors[0]['owner_id'], 'owner')
                self.assertEqual(row, before)

    def test_planner_schema_requires_original_request_references(self):
        schema = AnswerObligation.model_json_schema()
        self.assertIn('request_unit_ids', schema['required'])

    def test_fixture_copy_changes_only_explicit_request_addresses(self):
        from tests.request_unit_fixture_support import bind_fixture_request
        case = {'question': 'Compare quantities. Retain uncertainty.',
                'obligations': [{'obligation_id': 'quantity', 'label': 'Compare'}],
                'candidate_catalog': [{'source_text': '(1.25)'}], 'program': {'formula': 'a-b'},
                'expected': {'value': 1}}
        before = deepcopy(case)
        copied = bind_fixture_request(case)
        self.assertEqual(copied['obligations'][0].pop('request_unit_ids'), ['request_001', 'request_002'])
        self.assertEqual(copied, before)
        self.assertEqual(case, before)


if __name__ == '__main__':
    unittest.main()
