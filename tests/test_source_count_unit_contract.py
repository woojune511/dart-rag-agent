"""Source-linked unit choices; authored interpretations are not semantic accuracy."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_compiler_wire import CompilerReferencesV1, lower_compiler_response
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_graph_models import SourceInterpretationV1, compiler_response_model
from src.agent.financial_reconciliation_candidates import build_semantic_source_candidates, build_semantic_candidate_catalog
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.agent.financial_source_interpretation import (
    interpretation_axis_sources, source_unit_options, validate_source_interpretation,
)
from tests.semantic_program_test_support import _obligation, _requirement, _scope


QUERY = 'Return the 2050 item count.'


def catalog(label='item count', *, unit='', columns=None, values=('37', '11')):
    rows = [dict(row_id='row-A', row_label=label, row_headers=[label], cells=[
        dict(cell_id=f'row-A:{index}', column_index=index, column_headers=columns or ['2050'],
             value_text=value, unit_hint=unit) for index, value in enumerate(values, 1)])]
    metadata = dict(company='Issuer', rcept_no='filing-A', year=2050, chunk_uid='chunk-A',
        table_source_id='table-A', table_row_records_json=json.dumps(rows))
    documents = [(SimpleNamespace(page_content=label + ' | ' + ' | '.join(values), metadata=metadata), 0.0)]
    sources = build_semantic_source_candidates({'retrieved_docs': documents}, source_anchor_builder=lambda _: '[Issuer]')
    return [row for row in build_semantic_candidate_catalog(sources) if row['kind'] == 'numeric']


def owner(identifier='answer', kind='direct_value', **kwargs):
    return _obligation(identifier, kind, 'item count', display_unit='items',
        scope=_scope(company='Issuer', period='2050'),
        semantic_target={'metric_surfaces': ['item count']}, **kwargs)


def setup(sources, owners):
    cohorts = _semantic_candidate_cohorts(sources, owners)
    payload = FinancialAgent._semantic_program_prompt_payload(sources, cohorts)
    refs = CompilerReferencesV1.build(sources, owners, QUERY, payload)
    visibility = _semantic_candidate_visibility(sources,
        visible_candidate_ids=cohorts['visible_candidate_ids'], candidate_ids_by_owner=cohorts['candidate_ids_by_owner'],
        evidence_bundle_constraints=cohorts['evidence_bundle_constraints'])
    return cohorts, payload, refs, visibility, compiler_response_model(owners, refs, visibility)


def select(source, refs, *, unit=True):
    interpretation = dict(request_unit_ids=['request_001'], subject='reported items', metric='item count')
    if unit:
        interpretation['unit_ref'] = refs.ref(source_unit_options(source)[0]['unit_option_id'])
    return dict(source_ref=refs.ref(source['candidate_id']), interpretation=interpretation)


def direct(source, refs, *, unit=True, identifier='answer'):
    return {'outputs': {identifier: dict(status='ready', result=dict(selection=select(source, refs, unit=unit), compatibility_refs=[]))}}


def lower(raw, sources, owners, wire):
    return lower_compiler_response(raw, model=wire[4], refs=wire[2], catalog=sources,
        obligations=owners, visibility=wire[3])


def validate(program, sources, owners, wire):
    return validate_semantic_calculation_program(program=program, candidate_catalog=sources,
        obligations=owners, query=QUERY, candidate_visibility=wire[3])


def execute(program, sources, owners, wire, validation):
    inputs = dict(program=program, candidate_catalog=sources, obligations=owners, query=QUERY)
    envelope = CompilationEnvelopeV2.create(**inputs, visibility=wire[3], validation=validation)
    return execute_semantic_calculation_program(**inputs, compilation_envelope=envelope, require_compilation_envelope=True)


class SourceCountUnitContractTests(unittest.TestCase):
    def test_exact_policy_labels_offer_cell_owned_choices_without_mutation(self):
        for label, unit in (('건수', '건'), ('개수', '개'), ('인원수', '명'), ('count', 'COUNT'), ('item count', 'items')):
            with self.subTest(label=label):
                sources = catalog(label)
                before = deepcopy(sources)
                choices = [source_unit_options(row)[0] for row in sources]
                self.assertEqual([row['unit'] for row in choices], [unit, unit])
                self.assertNotEqual(choices[0]['unit_option_id'], choices[1]['unit_option_id'])
                self.assertEqual(sources, before)
                self.assertTrue(all(row['normalized_unit'] == 'UNKNOWN' and row['raw_unit'] == '' for row in sources))

    def test_substrings_unrelated_labels_and_year_headers_do_not_create_units(self):
        for label in ('discount', 'count expenses', 'code', 'completion year', 'number', 'quantity'):
            with self.subTest(label=label):
                self.assertTrue(all(not source_unit_options(row) for row in catalog(label)))

    def test_explicit_known_and_unsupported_units_are_not_overridden(self):
        for unit in ('items', 'USD', '%', 'unregistered-unit'):
            with self.subTest(unit=unit):
                self.assertTrue(all(not source_unit_options(row) for row in catalog(unit=unit)))
        self.assertTrue(all(not source_unit_options(row) for row in catalog('item count (USD)')))

    def test_conflicting_axes_offer_no_unit(self):
        for columns in (['2050', 'amount'], ['2050', 'percentage'], ['2050', '건수']):
            with self.subTest(columns=columns):
                self.assertTrue(all(not source_unit_options(row) for row in catalog(columns=columns)))

    def test_unlocated_cells_and_prose_cannot_borrow_axis_unit_choices(self):
        source = catalog()[0]
        for patch in ({'physical_cell_id': ''}, {'physical_table_id': ''}, {'candidate_kind': 'sentence_value'}):
            self.assertEqual(source_unit_options({**source, **patch}), [])

    def test_option_affects_exposure_without_declaring_unit_compatibility(self):
        sources = catalog()
        competing = {**deepcopy(sources[0]), 'candidate_id': 'unrelated-known', 'physical_table_id': 'other',
            'source_row_id': 'other-row', 'physical_cell_key': 'other-cell', 'source_candidate_id': 'other',
            'row_label': 'sequence', 'row_headers': ['sequence'], 'normalized_unit': 'COUNT', 'raw_unit': 'COUNT'}
        wire = setup([competing, *sources], [owner()])
        self.assertIn(sources[0]['candidate_id'], wire[0]['candidate_ids_by_owner']['answer'])
        match = wire[0]['candidate_match_by_id'][sources[0]['candidate_id']]['answer']
        self.assertEqual(match['unit_state'], 'unknown')
        self.assertEqual(match['state'], 'unknown_only')
        self.assertEqual(next(row['limit'] for row in wire[0]['cohorts'] if row['candidate_kind'] == 'numeric'), 2)

    def test_schema_and_prompt_offer_only_source_owned_options(self):
        sources = catalog()
        wire = setup(sources, [owner()])
        schema = json.dumps(wire[4].model_json_schema())
        for row in sources:
            option = source_unit_options(row)[0]
            self.assertIn(wire[2].ref(option['unit_option_id']), schema)
            self.assertEqual(wire[1]['candidates_by_id'][row['candidate_id']]['unit_options'], [option])
        known = catalog(unit='items')
        self.assertNotIn('unit_ref', json.dumps(setup(known, [owner()])[4].model_json_schema()))

    def test_null_unit_reading_remains_unknown_and_cannot_render_a_count(self):
        sources, owners = catalog(), [owner()]
        wire = setup(sources, owners)
        program = lower(direct(sources[0], wire[2], unit=False), sources, owners, wire)
        result = validate(program, sources, owners, wire)
        self.assertEqual(result['status'], 'invalid')
        self.assertIn('direct_result_unit_mismatch', [error['code'] for error in result['errors']])
        self.assertNotIn('unit_option_id', program['direct_bindings'][0]['source_interpretation'])

    def test_hidden_source_unit_options_are_absent_from_owner_schema(self):
        sources = [catalog()[0], catalog(columns=['2051'])[1]]
        wire = setup(sources, [owner()])
        self.assertNotIn(sources[1]['candidate_id'], wire[3].candidate_ids_by_owner()['answer'])
        hidden = wire[2].ref(source_unit_options(sources[1])[0]['unit_option_id'])
        self.assertNotIn(hidden, json.dumps(wire[4].model_json_schema()))

    def test_strict_generation_schema_requires_nullable_finite_unit_choice(self):
        from src.utils.openai_structured import strict_openai_schema
        sources = catalog()
        wire = setup(sources, [owner()])
        original = wire[4].model_json_schema()
        strict = strict_openai_schema(wire[4])
        definitions = [row for row in strict['$defs'].values() if 'unit_ref' in row.get('properties', {})]
        self.assertTrue(definitions)
        for definition in definitions:
            self.assertIn('unit_ref', definition['required'])
            self.assertEqual(set(definition['properties']['unit_ref']['enum']),
                {None, *(wire[2].ref(source_unit_options(row)[0]['unit_option_id']) for row in sources)})
        self.assertEqual(wire[4].model_json_schema(), original)

    def test_bad_unit_option_does_not_discard_valid_sibling_output(self):
        sources, owners = catalog(), [owner('good'), owner('bad')]
        wire = setup(sources, owners)
        good = direct(sources[0], wire[2], identifier='good')
        bad = direct(sources[1], wire[2], identifier='bad')
        bad['outputs']['bad']['result']['selection']['interpretation']['unit_ref'] = 'invented'
        raw = {'outputs': {**good['outputs'], **bad['outputs']}}
        errors = []
        program = lower_compiler_response(raw, model=wire[4], refs=wire[2], catalog=sources,
            obligations=owners, visibility=wire[3], errors=errors)
        self.assertEqual([row['obligation_id'] for row in program['direct_bindings']], ['good'])
        self.assertEqual(program['direct_bindings'], lower(good, sources, [owners[0]],
            setup(sources, [owners[0]]))['direct_bindings'])
        self.assertTrue(errors)
        self.assertTrue(all(row['obligation_id'] == 'bad' for row in errors))

    def test_selected_unit_renders_and_preserves_original_scalar_and_unit_trace(self):
        sources, owners = catalog(), [owner()]
        before = deepcopy(sources)
        wire = setup(sources, owners)
        program = lower(direct(sources[0], wire[2]), sources, owners, wire)
        result = validate(program, sources, owners, wire)
        self.assertEqual(result['status'], 'ready', result['errors'])
        output, = execute(program, sources, owners, wire, result)['outputs']
        self.assertEqual((output['value'], output['normalized_unit'], output['rendered_value']), (37, 'COUNT', '37items'))
        proof = output['answer_slot']['source_unit_resolution']
        self.assertEqual((proof['source_raw_unit'], proof['source_normalized_unit']), ('', 'UNKNOWN'))
        self.assertEqual(proof['axis_source']['physical_cell_id'], sources[0]['physical_cell_id'])
        self.assertEqual(sources, before)

    def test_foreign_or_fabricated_option_cannot_ground_selected_cell(self):
        sources, owners = catalog(), [owner()]
        wire = setup(sources, owners)
        for reference in (wire[2].ref(source_unit_options(sources[1])[0]['unit_option_id']), 'invented'):
            raw = direct(sources[0], wire[2])
            raw['outputs']['answer']['result']['selection']['interpretation']['unit_ref'] = reference
            with self.subTest(reference=reference), self.assertRaisesRegex(ValueError, 'unit_option_not_authorized_for_source'):
                lower(raw, sources, owners, wire)

    def test_internal_unit_reading_requires_its_axis_and_owned_request(self):
        sources, owners = catalog(), [owner()]
        wire = setup(sources, owners)
        proof = lower(direct(sources[0], wire[2]), sources, owners, wire)['direct_bindings'][0]['source_interpretation']
        for patch, error in (({'axis_refs': []}, 'source_interpretation_evidence_mismatch'),
                             ({'request_unit_ids': ['foreign']}, 'source_interpretation_request_mismatch')):
            with self.subTest(error=error), self.assertRaisesRegex(ValueError, error):
                validate_source_interpretation(sources[0], {**proof, **patch}, owner=owners[0], query=QUERY)
        other_axis = [key for key, axis in interpretation_axis_sources(sources[0]).items() if axis['field'] == 'column_headers']
        with self.assertRaisesRegex(ValueError, 'source_unit_axis_missing'):
            validate_source_interpretation(sources[0], {**proof, 'axis_refs': other_axis}, owner=owners[0], query=QUERY)

    def test_old_interpretation_projection_does_not_add_an_empty_unit_field(self):
        proof = SourceInterpretationV1(request_unit_ids=['request_001'], subject='items', metric='quantity')
        self.assertNotIn('unit_option_id', proof.model_dump())

    def test_v2_rejects_changed_source_axis_or_unit_selection(self):
        sources, owners = catalog(), [owner()]
        wire = setup(sources, owners)
        program = lower(direct(sources[0], wire[2]), sources, owners, wire)
        result = validate(program, sources, owners, wire)
        inputs = dict(program=program, candidate_catalog=sources, obligations=owners, query=QUERY)
        envelope = CompilationEnvelopeV2.create(**inputs, visibility=wire[3], validation=result)
        altered = deepcopy(program)
        altered['direct_bindings'][0]['source_interpretation'].pop('unit_option_id')
        changed = deepcopy(sources)
        changed[0]['row_headers'] = ['unrelated']
        for patch in ({'program': altered}, {'candidate_catalog': changed}):
            value = execute_semantic_calculation_program(**{**inputs, **patch},
                compilation_envelope=envelope, require_compilation_envelope=True)
            self.assertNotEqual(value['status'], 'ok')
            self.assertFalse(value['outputs'])

    def test_derived_inputs_use_validated_units_for_arithmetic_and_trace(self):
        sources = catalog()
        owners = [owner(kind='derived_value', evidence_requirements=[_requirement('inputs', 'item count', period='2050')])]
        wire = setup(sources, owners)
        selections = [{**select(row, wire[2]), 'variable': variable} for row, variable in zip(sources, ('A', 'B'))]
        raw = {'outputs': {'answer': {'status': 'ready', 'result': dict(inputs={'inputs': selections},
            formula=[{'operation': 'subtract', 'arguments': [{'variable': 'A'}, {'variable': 'B'}]}],
            display_unit='items', display_format='', source_display=None, source_display_reason='Use calculated difference.',
            comparison_request_unit_id=None, compatibility_refs=[])}}}
        program = lower(raw, sources, owners, wire)
        result = validate(program, sources, owners, wire)
        self.assertEqual(result['status'], 'ready', result['errors'])
        output, = execute(program, sources, owners, wire, result)['outputs']
        self.assertEqual((output['value'], output['normalized_unit'], output['rendered_value']), (26, 'COUNT', '26items'))
        self.assertTrue(all(row['raw_unit'] == '' and row['normalized_unit'] == 'COUNT' for row in output['input_rows']))
        self.assertTrue(all(row['source_unit_resolution']['source_normalized_unit'] == 'UNKNOWN' for row in output['input_rows']))

    def test_unit_reading_does_not_resolve_a_missing_year(self):
        sources, owners = catalog(columns=['Completion year']), [owner()]
        wire = setup(sources, owners)
        program = lower(direct(sources[0], wire[2]), sources, owners, wire)
        result = validate(program, sources, owners, wire)
        self.assertIn('candidate_scope_mismatch', [error['code'] for error in result['errors']])
        self.assertFalse(any(error['code'] in ('empty_direct_rendering', 'direct_result_unit_mismatch') for error in result['errors']))
        self.assertEqual(sources[0]['period'], '')


if __name__ == '__main__':
    unittest.main()
