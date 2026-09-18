"""Lossless candidate-local presentation; authored replies are not model evidence."""
from copy import deepcopy
import json
import unittest
from unittest.mock import patch

from src.agent.financial_compiler_presentation import project_wire_axis_provenance
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from src.ops.replay_reviewed_compiler_selection import _case_state
from tests import test_compiler_piece_rows as piece_rows
from tests import test_shared_basis_compiler as shared_basis
from tests.semantic_program_test_support import _candidate, _obligation, _requirement
from tests.source_interpretation_fixture_support import authored_source_program


INSTRUCTION = CALCULATION_PROMPT_POLICY['semantic_program_axis_source_instructions']
PROVENANCE = ('candidate_id', 'source_document_id', 'source_document_sha256', 'source_anchor',
    'physical_table_id', 'physical_row_id', 'physical_cell_id', 'physical_value_id',
    'source_row_id', 'table_source_id')


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def restore_payload(payload):
    """Test-only inverse; production never decodes model-supplied provenance."""
    result = deepcopy(payload)
    if result['schema'] == 'semantic_program_candidate_payload_v11':
        result['schema'] = ('semantic_program_candidate_payload_v10' if 'piece_columns' in result
                            else 'semantic_program_candidate_payload_v9')
        for row in result['candidates_by_id'].values():
            common = row.pop('axis_source_common', {})
            assert not set(common) - set(PROVENANCE)
            for axis in row.get('interpretation_axis_sources', {}).values():
                assert not set(axis) & set(common)
                axis.update(deepcopy(common))
    return result


def restore_request(value):
    if isinstance(value, dict):
        return {key: restore_request(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_request(item) for item in value]
    if isinstance(value, str) and piece_rows.MARKER in value:
        prefix, tail = value.split(piece_rows.MARKER, 1)
        payload, end = json.JSONDecoder().raw_decode(tail)
        if payload['schema'] == 'semantic_program_candidate_payload_v11':
            assert prefix.endswith(INSTRUCTION) and prefix.count(INSTRUCTION) == 1
            prefix = prefix[:-len(INSTRUCTION)]
        else:
            assert INSTRUCTION not in prefix
        return prefix + piece_rows.MARKER + canonical(restore_payload(payload)) + tail[end:]
    return value


def payload_fixture():
    common = {key: 'exact-' + key for key in PROVENANCE}
    common.update(candidate_id='c1', source_anchor='  source\r\n"A\\B"\t')
    return {'schema': 'semantic_program_candidate_payload_v9',
        'candidates_by_id': {'c1': {'raw_value': '(12.00)', 'raw_unit': ' items ',
            'interpretation_axis_sources': {
                'a1': {'field': 'row_headers', 'path': ['  Cedar\t', 'quantity'], **common},
                'a2': {'field': 'column_headers', 'path': ['2048', 'items'], **common}},
            'future': {'source_text': 'preserve  this\n'}}},
        'cohorts': [{'owner_id': 'o1', 'candidate_ids': ['c1']}, {'owner_id': 'o2', 'candidate_ids': []}],
        'source_readings': [{'source_text': 'same wording', 'address': 'first'},
                            {'source_text': 'same wording', 'address': 'second'}],
        'source_contexts_by_id': {'x1': {'attached_candidate_ids': ['c1']}}}


class CompilerAxisProvenanceTests(unittest.TestCase):
    setUp = piece_rows.CompilerPieceRowTests.setUp
    compile_sdk = piece_rows.CompilerPieceRowTests.compile_sdk
    narrative_fixture = piece_rows.CompilerPieceRowTests.narrative_fixture

    def test_exact_round_trip_preserves_order_addresses_source_strings_and_authority(self):
        payload = payload_fixture()
        before = deepcopy(payload)
        result = project_wire_axis_provenance(payload)
        self.assertEqual(canonical(restore_payload(result)), canonical(before))
        self.assertEqual(payload, before)
        self.assertEqual(list(result['candidates_by_id']), list(before['candidates_by_id']))
        self.assertEqual(list(result['candidates_by_id']['c1']['interpretation_axis_sources']), ['a1', 'a2'])
        self.assertEqual(set(result['candidates_by_id']['c1']['axis_source_common']), set(PROVENANCE))
        self.assertLess(len(canonical(result).encode()), len(canonical(before).encode()))
        result['candidates_by_id']['c1']['future']['source_text'] = 'edited copy'
        self.assertEqual(payload, before)

    def test_missing_unequal_and_unknown_fields_remain_axis_local(self):
        for key in PROVENANCE:
            for variant in ('missing', 'different', 'typed'):
                with self.subTest(key=key, variant=variant):
                    payload = payload_fixture()
                    axes = payload['candidates_by_id']['c1']['interpretation_axis_sources']
                    if variant == 'missing':
                        del axes['a2'][key]
                    elif variant == 'typed':
                        axes['a1'][key], axes['a2'][key] = True, 1
                    else:
                        axes['a2'][key] += ' distinct'
                    for axis in axes.values():
                        axis['future_provenance'] = {'same': [1, True, ' full\tpath ']}
                    projected = project_wire_axis_provenance(payload)
                    row = projected['candidates_by_id']['c1']
                    self.assertNotIn(key, row['axis_source_common'])
                    self.assertNotIn('future_provenance', row['axis_source_common'])
                    self.assertEqual(canonical(restore_payload(projected)), canonical(payload))
        for left, right in ((1, 1.0), (0.0, -0.0), ('1', 1), (None, '')):
            payload = payload_fixture()
            axes = payload['candidates_by_id']['c1']['interpretation_axis_sources']
            axes['a1']['candidate_id'], axes['a2']['candidate_id'] = left, right
            result = project_wire_axis_provenance(payload)
            self.assertNotIn('candidate_id', result['candidates_by_id']['c1']['axis_source_common'])
            self.assertEqual(canonical(restore_payload(result)), canonical(payload))

    def test_empty_single_axis_and_no_shared_fields_keep_exact_wire(self):
        for axes in ({}, {'a1': {'candidate_id': 'c1'}},
                     {'a1': {'candidate_id': 'c1'}, 'a2': {'candidate_id': 'c2'}},
                     {'a1': {'field': 'same', 'path': ['same']}, 'a2': {'field': 'same', 'path': ['same']}}):
            payload = payload_fixture()
            payload['candidates_by_id']['c1']['interpretation_axis_sources'] = axes
            self.assertEqual(piece_rows.encoded(project_wire_axis_provenance(payload)), piece_rows.encoded(payload))

    def test_equal_literals_in_distinct_candidates_never_merge_authority(self):
        payload = payload_fixture()
        second = deepcopy(payload['candidates_by_id']['c1'])
        for axis in second['interpretation_axis_sources'].values():
            axis.update(candidate_id='c2', physical_cell_id='another-cell', source_document_id='another-document')
        payload['candidates_by_id']['c2'] = second
        payload['cohorts'][1]['candidate_ids'] = ['c2']
        result = project_wire_axis_provenance(payload)
        self.assertEqual(result['cohorts'], payload['cohorts'])
        self.assertEqual(result['source_readings'], payload['source_readings'])
        self.assertEqual(result['source_contexts_by_id'], payload['source_contexts_by_id'])
        self.assertNotEqual(result['candidates_by_id']['c1']['axis_source_common'],
                            result['candidates_by_id']['c2']['axis_source_common'])
        self.assertEqual(canonical(restore_payload(result)), canonical(payload))

    def test_reserved_fields_and_repeated_projection_fail_without_mutating_input(self):
        for payload in (project_wire_axis_provenance(payload_fixture()), payload_fixture()):
            payload['candidates_by_id']['c1']['axis_source_common'] = {'candidate_id': 'existing'}
            before = deepcopy(payload)
            with self.assertRaisesRegex(ValueError, 'already_projected|reserved_axis_source_common'):
                project_wire_axis_provenance(payload)
            self.assertEqual(payload, before)

    def compare_sdk(self, state, programs, *, expected_retry=0, unchanged=False):
        with patch('src.agent.financial_graph_calculation.project_wire_axis_provenance', deepcopy):
            old = self.compile_sdk(state, programs, previous_wire=False)
        new = self.compile_sdk(state, programs, previous_wire=False)
        for key in ('semantic_program', 'semantic_program_validation', 'semantic_compilation_envelope',
                    'semantic_program_retry_count', 'missing_info'):
            self.assertEqual(new[0][key], old[0][key], key)
        self.assertEqual(new[0]['semantic_program_retry_count'], expected_retry)
        self.assertEqual(new[1], old[1])
        self.assertEqual(new[3:], old[3:])  # Original replies and strict SDK schemas.
        self.assertEqual(restore_request(new[2]), restore_request(old[2]))
        if unchanged:
            self.assertEqual(new[2], old[2])
        else:
            self.assertIn('axis_source_common', canonical(new[2]))
            self.assertLess(len(canonical(new[2]).encode()), len(canonical(old[2]).encode()))
        return new

    def test_sdk_direct_lookup_retains_exact_value_unit_and_execution_proofs(self):
        catalog = [_candidate('cell', 12, period='2048')]
        owners = [_obligation('size', 'direct_value', 'Read the size.')]
        state = _case_state({'question': 'Read the size.', 'obligations': owners}, catalog)
        program = SemanticCalculationProgram(direct_bindings=[{'obligation_id': 'size', 'candidate_id': 'cell'}])
        self.compare_sdk(state, [program])

    def test_sdk_calculation_retains_formula_bindings_and_arithmetic(self):
        catalog = [_candidate('first', 12, period='2047'), _candidate('last', 21, period='2048')]
        owners = [_obligation('change', 'derived_value', 'Calculate the difference.', evidence_requirements=[
            _requirement('initial', 'initial quantity'), _requirement('final', 'final quantity')])]
        state = _case_state({'question': 'Calculate the difference.', 'obligations': owners}, catalog)
        program = SemanticCalculationProgram(expressions=[{'obligation_id': 'change', 'formula': 'B-A',
            'variable_bindings': [{'variable': 'A', 'source_id': 'first', 'source_requirement_id': 'initial'},
                                  {'variable': 'B', 'source_id': 'last', 'source_requirement_id': 'final'}],
            'source_display_candidate_id': None, 'source_display_reason': 'Calculated difference only.'}])
        self.compare_sdk(state, [program])

    def test_sdk_pure_narrative_and_single_axis_requests_are_byte_identical(self):
        catalog, owners, program = self.narrative_fixture()
        state = _case_state({'question': 'Describe routes and reach.', 'obligations': owners}, catalog)
        self.compare_sdk(state, [program], unchanged=True)
        state = _case_state({'question': 'Read size.', 'obligations': [
            _obligation('size', 'direct_value', 'Read size.')]}, [_candidate('cell', 12)])
        self.compare_sdk(state, [SemanticCalculationProgram(direct_bindings=[
            {'obligation_id': 'size', 'candidate_id': 'cell'}])], unchanged=True)

    def test_sdk_mixed_retry_preserves_accepted_numeric_output_and_narrative_draft(self):
        catalog, owners, good = self.narrative_fixture()
        owners[0]['depends_on'] = ['size']
        catalog.insert(0, _candidate('cell', 12, period='2048'))
        owners.insert(0, _obligation('size', 'direct_value', 'Read size.'))
        bad = good.model_copy(deep=True)
        bad.narrative_bindings[0].claims[1].text = 'Serves 93 regions.'
        initial = bad.model_copy(update={'direct_bindings': SemanticCalculationProgram(direct_bindings=[
            {'obligation_id': 'size', 'candidate_id': 'cell'}]).direct_bindings})
        state = _case_state({'question': 'Read size and describe routes and reach.', 'obligations': owners}, catalog)
        result = self.compare_sdk(state, [initial, good], expected_retry=1)
        self.assertEqual(result[0]['semantic_program']['direct_bindings'][0]['candidate_id'], 'cell')

    def test_sdk_shared_basis_retains_local_axis_proofs_and_declarations(self):
        case = shared_basis.fixture()
        case.make_mixed()
        case.catalog[0]['column_headers'] = ['2048', 'items']
        case.program['direct_bindings'][0].pop('source_interpretation')
        program = authored_source_program(case.program, case.owners, case.catalog, case.query)
        program['direct_bindings'][0]['source_interpretation']['scope']['basis'] = case.basis
        state = _case_state({'question': case.query, 'obligations': case.owners}, case.catalog)
        result = self.compare_sdk(state, [SemanticCalculationProgram.model_validate(program)])
        self.assertEqual(result[0]['semantic_program']['relationship_declarations'], case.program['relationship_declarations'])


if __name__ == '__main__':
    unittest.main()
