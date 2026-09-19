"""Exact selected prose surfaces, not whitespace repair or semantic entailment."""
from copy import deepcopy
import socket
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_compiler_wire import lower_compiler_response
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.agent.financial_source_bundles import build_semantic_source_bundles
from src.agent.financial_source_interpretation import validate_source_interpretation
from tests.test_compiler_source_choices import direct
from tests.test_numeric_compiler_grounding import QUERY, output, wire


def numeric(text):
    return [row for row in build_semantic_candidate_catalog([{
        'candidate_id': 'source', 'candidate_kind': 'chunk', 'source_anchor': '[anonymous]',
        'text': ' '.join(text.split()), 'source_text_exact': text,
        'metadata': {'is_table': False},
    }]) if row['kind'] == 'numeric']


def interpretation(quote):
    return dict(request_unit_ids=['request_001'], subject='Cedar', metric='reading',
        scope={}, source_evidence_text=quote)


def resolve(candidate, quote):
    return validate_source_interpretation(candidate, interpretation(quote),
        owner={**output(), 'request_unit_ids': ['request_001']}, query=QUERY)


class NumericQuoteSourceBoundaryTests(unittest.TestCase):
    def setUp(self):
        for method in ('connect', 'connect_ex'):
            blocker = patch.object(socket.socket, method, side_effect=AssertionError('network forbidden'))
            blocker.start()
            self.addCleanup(blocker.stop)

    def test_exact_bundle_whitespace_and_both_coordinate_spaces_are_preserved(self):
        for exact in ('Earlier 7%. Cedar reading is 23%.',
                      'Earlier 7%.\t  Cedar reading is 23%.',
                      'Earlier 7%.\u00a0Cedar\t reading is 23%.',
                      'Cedar\t reading is 23%   '):
            candidate = numeric(exact)[-1]
            quote = candidate['source_bundle_text']
            before = deepcopy(candidate)
            with self.subTest(exact=exact):
                proof = resolve(candidate, quote)
                evidence, = proof['evidence']
                bundle, = build_semantic_source_bundles([candidate])
                self.assertEqual(evidence['evidence_text'], quote)
                self.assertEqual(evidence['source_field'], 'source_bundle_text')
                self.assertEqual(evidence['source_bundle_id'], bundle.source_bundle_id)
                self.assertEqual(evidence['source_span'], [0, len(quote)])
                self.assertEqual(evidence['source_candidate_span'], candidate['source_bundle_context_span'])
                self.assertEqual(exact[slice(*evidence['source_candidate_span'])], quote)
                self.assertEqual(proof['validation_scope'], 'source_linkage_not_semantic_equivalence')
                self.assertEqual(candidate, before)

    def test_partial_exact_quote_uses_window_offset_without_expanding_to_other_values(self):
        exact = 'Earlier 7%. Cedar reading is 23%, alternate reading is 41%.'
        candidate = numeric(exact)[1]
        quote = 'Cedar reading is 23%'
        evidence, = resolve(candidate, quote)['evidence']
        self.assertEqual(evidence['source_span'], [1, 1 + len(quote)])
        self.assertEqual(exact[slice(*evidence['source_candidate_span'])], quote)
        self.assertEqual(evidence['source_bundle_context_span'], candidate['source_bundle_context_span'])
        self.assertEqual(evidence['source_candidate_id'], candidate['source_candidate_id'])

    def test_inexact_normalized_hidden_and_foreign_quotes_fail(self):
        candidate = numeric('Earlier 7%. Cedar\t reading is 23%.')[1]
        before = deepcopy(candidate)
        for quote in (' Cedar reading is 23%.', 'Cedar reading is 23%.', 'Earlier 7%.',
                      '\n Cedar\t reading is 23%.', ' ', 'Cedar\t reading is 24%.'):
            with self.subTest(quote=quote), self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
                resolve(candidate, quote)
        self.assertEqual(candidate, before)

    def test_incomplete_invalid_or_foreign_physical_projection_cannot_authorize_quote(self):
        candidate = numeric('Earlier 7%. Cedar reading is 23%.')[1]
        for change in ({'source_bundle_context_span': None}, {'source_bundle_value_span': None},
                       {'source_bundle_context_span': [0, 1]}, {'source_bundle_value_span': [0, 999]},
                       {'source_bundle_context_span': [True, 28]}, {'source_bundle_value_span': ['1', '3']},
                       {'source_bundle_value_span': [1, 2, 3]},
                       {'physical_table_id': 'other-table', 'physical_cell_id': 'other-cell'},
                       {'candidate_kind': 'structured_value'}):
            changed = {**deepcopy(candidate), **change}
            before = deepcopy(changed)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
                resolve(changed, candidate['source_bundle_text'])
            self.assertEqual(changed, before)

    def test_unlocated_historical_source_stays_exact_without_borrowing_bundle_bytes(self):
        candidate = numeric('Cedar reading is 23%.')[0]
        candidate.pop('source_bundle_context_span')
        candidate.pop('source_bundle_value_span')
        candidate['source_bundle_text'] = ' ' + candidate['source_text']
        proof = resolve(candidate, candidate['source_text'])
        self.assertEqual(proof['evidence'], [{'candidate_id': candidate['candidate_id'],
            'evidence_text': candidate['source_text'], 'source_span': [0, len(candidate['source_text'])]}])
        with self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
            resolve(candidate, candidate['source_bundle_text'])

    def test_long_context_cannot_quote_beyond_the_retained_bundle(self):
        exact = 'prefix ' * 90 + 'Cedar reading is 23% ' + 'tail ' * 140
        candidate, = numeric(exact)
        self.assertLessEqual(len(candidate['source_bundle_text']), 420)
        self.assertGreater(len(candidate['source_text']), len(candidate['source_bundle_text']))
        with self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
            resolve(candidate, candidate['source_text'])
        proof = resolve(candidate, candidate['source_bundle_text'])['evidence'][0]
        self.assertEqual(exact[slice(*proof['source_candidate_span'])], proof['evidence_text'])

    def test_partitioned_quote_uses_its_valid_occurrence_without_crossing_boundaries(self):
        exact = 'Cedar reading is 23%; Cedar reading is unchanged.'
        candidate, = numeric(exact)
        second = exact.index('Cedar', 1)
        candidate['source_context_provenance'] = {'source_text': exact, 'source_segments': [
            {'text_span': [0, 3]}, {'text_span': [3, second]}, {'text_span': [second, len(exact)]}]}
        quote = 'Cedar reading'
        evidence, = resolve(candidate, quote)['evidence']
        self.assertEqual(evidence['source_span'], [second, second + len(quote)])
        with self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
            resolve(candidate, '23%; Cedar')

    def test_repeated_value_windows_keep_selected_candidate_identity(self):
        exact = 'Cedar first reading is 23%. Cedar second reading is 23%.'
        candidates = numeric(exact)
        proofs = [resolve(row, row['source_bundle_text'])['evidence'][0] for row in candidates]
        self.assertNotEqual(proofs[0]['candidate_id'], proofs[1]['candidate_id'])
        self.assertNotEqual(proofs[0]['source_bundle_id'], proofs[1]['source_bundle_id'])
        for candidate, proof in zip(candidates, proofs):
            self.assertEqual(exact[slice(*proof['source_candidate_span'])], proof['evidence_text'])
            self.assertEqual(proof['candidate_id'], candidate['candidate_id'])
        with self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
            resolve(candidates[1], candidates[0]['source_bundle_text'])

    def test_lowering_validation_and_execution_preserve_exact_quote_and_scalar(self):
        candidate = numeric('Earlier 7%. Cedar\t reading is 23%.')[1]
        owners = [{**output(), 'request_unit_ids': ['request_001']}]
        refs, model, visibility, _ = wire([candidate], owners)
        raw = direct({'source_ref': refs.ref(candidate['candidate_id']),
            'interpretation': interpretation(candidate['source_bundle_text'])})
        before = deepcopy((candidate, owners, raw))
        program = lower_compiler_response(raw, model=model, refs=refs, obligations=owners,
            catalog=[candidate], visibility=visibility)
        self.assertEqual(program['source_assertions'][0]['evidence_text'], '23%')
        inputs = dict(program=program, candidate_catalog=[candidate], obligations=owners, query=QUERY)
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility)
        self.assertEqual(validation['status'], 'ready', validation['errors'])
        proof = validation['valid_direct_bindings'][0]['source_interpretation_resolution']
        envelope = CompilationEnvelopeV2.create(**inputs, visibility=visibility, validation=validation)
        result = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope)
        self.assertEqual(result['status'], 'ok', result['validation']['errors'])
        self.assertEqual(result['outputs_by_obligation']['answer']['normalized_value'], 23)
        self.assertEqual(proof['evidence'][0]['evidence_text'], candidate['source_bundle_text'])
        self.assertEqual((candidate, owners, raw), before)
        altered = deepcopy(validation)
        altered['valid_direct_bindings'][0]['source_interpretation_resolution']['evidence'][0]['source_candidate_span'][0] += 1
        self.assertFalse(envelope.matches_validation(altered))
        for field, value in (('source_bundle_text', candidate['source_bundle_text'].strip()),
                             ('source_bundle_context_span', [0, len(candidate['source_bundle_text'])])):
            changed = deepcopy(inputs)
            changed['candidate_catalog'][0][field] = value
            rejected = execute_semantic_calculation_program(**changed, compilation_envelope=envelope)
            self.assertEqual(rejected['outputs'], [])
            self.assertIn('execution_content_mismatch', [e['code'] for e in rejected['validation']['errors']])

    def test_valid_quote_does_not_resolve_missing_numeric_period(self):
        candidate = numeric('Earlier 7%. Cedar reading is 23%.')[1]
        owner = {**output(), 'request_unit_ids': ['request_001']}
        refs, model, visibility, _ = wire([candidate], [owner])
        program = lower_compiler_response(direct({'source_ref': refs.ref(candidate['candidate_id']),
            'interpretation': interpretation(candidate['source_bundle_text'])}),
            model=model, refs=refs, obligations=[owner], catalog=[candidate], visibility=visibility)
        owner['scope']['period'] = '2045'
        validation = validate_semantic_calculation_program(program=program, obligations=[owner],
            candidate_catalog=[candidate], query=QUERY)
        codes = [e['code'] for e in validation['errors']]
        self.assertNotIn('source_interpretation_quote_mismatch', codes)
        self.assertIn('candidate_scope_mismatch', codes)
        self.assertNotEqual(validation['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
