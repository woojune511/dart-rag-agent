"""Anonymous physical linkage controls, not model semantic acceptance."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest

from src.agent.financial_column_periods import project_column_period_evidence, source_period_options
from src.agent.financial_reconciliation_candidates import build_semantic_source_candidates, build_semantic_candidate_catalog
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_source_interpretation import source_unit_options, validate_source_interpretation
from src.utils.openai_structured import strict_openai_schema
from tests.test_source_count_unit_contract import QUERY, owner, setup, lower, validate, execute
from tests.test_compiler_numeric_reading_intent import AuthoredReadingLLM, compile_case, execute as execute_compiled
from tests.semantic_program_test_support import _requirement


def table(*, unit='', year_values=('2049', '2050'), label_source='column'):
    rows = []
    for row_id, label, values in (('axis', 'Category', (*year_values, 'Total', 'Pending')),
                                  ('data', 'item count', ('37', '37', '74', '9'))):
        rows.append(dict(row_id=row_id, row_headers=[label], row_label=label, cells=[
            dict(cell_id=f'{row_id}:{i}', column_index=i, column_headers=['Completion year'],
                value_text=value, unit_hint=unit if row_id == 'data' else '',
                label_source=label_source if row_id == 'axis' and i < 2 else 'row')
            for i, value in enumerate(values)]))
    text = 'Projects from 2049 through 2050 are included.'
    context = dict(context_id='ctx-period', source_locator='/DOC/P[1]', parent_locator='/DOC',
        source_text=text, source_span=[0, len(text)], relation='preceding_block', document_sha256='a' * 64)
    metadata = dict(company='Issuer', year=2050, rcept_no='filing-A', chunk_uid='chunk-A',
        table_source_id='table-A', table_row_records_json=json.dumps(rows),
        source_document_sha256='a' * 64, source_table_locator='/DOC/TABLE[1]', source_contexts=[context])
    sources = build_semantic_source_candidates({'retrieved_docs': [
        (SimpleNamespace(page_content='Category | item count', metadata=metadata), 0.0)]},
        source_anchor_builder=lambda _: '[Issuer]')
    return sources, build_semantic_candidate_catalog(sources)


def cells(catalog):
    return sorted([row for row in catalog if row.get('kind') == 'numeric' and row['row_label'] == 'item count'],
                  key=lambda row: row['physical_cell_id'])


def choose(source, refs, *, period=True, quote=''):
    interpretation = dict(request_unit_ids=['request_001'], subject='reported items', metric='item count')
    if options := source_unit_options(source):
        interpretation['unit_ref'] = refs.ref(options[0]['unit_option_id'])
    if period:
        interpretation['period_ref'] = refs.ref(source_period_options(source)[0]['period_option_id'])
    selection = dict(source_ref=refs.ref(source['candidate_id']), interpretation=interpretation, context_evidence=[])
    if quote:
        selection['context_evidence'] = [dict(context_ref=refs.ref('ctx-period'), evidence_text=quote,
            supports_interpretation=False, resolves=[dict(field='period', value='2050')])]
    return selection


def direct(source, refs, **kwargs):
    return {'outputs': {'answer': dict(status='ready', result=dict(selection=choose(source, refs, **kwargs), compatibility_refs=[]))}}


class SameColumnPeriodContractTests(unittest.TestCase):
    def test_exact_column_links_preserve_scalar_identity_and_unresolved_catalog_period(self):
        sources, catalog = table()
        before = deepcopy(sources)
        first, second, total, pending = cells(catalog)
        self.assertNotEqual(first['candidate_id'], second['candidate_id'])
        for candidate, year, source_cell in ((first, 2049, 'axis:0'), (second, 2050, 'axis:1')):
            option, = source_period_options(candidate)
            self.assertEqual((option['value_year'], option['evidence']['source']['physical_cell_id']), (year, source_cell))
            self.assertEqual((candidate['raw_value'], candidate['period'], candidate['value_year']), ('37', '', None))
        for candidate in (total, pending):
            self.assertTrue(candidate['source_column_period_evidence'])
            self.assertEqual(source_period_options(candidate), [])
        self.assertEqual(build_semantic_candidate_catalog(sources), catalog)
        self.assertEqual(sources, before)

    def test_ordinary_data_rows_or_non_calendar_numbers_do_not_become_period_axes(self):
        for kwargs in ({'label_source': 'row'}, {'year_values': ('2049.5', '2050.5')},
                       {'year_values': ('123', '456')}, {'year_values': ('2049-2050', '2050')}):
            with self.subTest(kwargs=kwargs):
                self.assertTrue(all(not row.get('source_column_period_evidence') for row in table(**kwargs)[1]))

    def test_missing_or_duplicate_coordinates_cannot_be_recovered_from_equal_values(self):
        sources, _ = table()
        header = next(row for row in sources if row['metadata'].get('row_label') == 'Category')
        for value in (None, True, -1, 1):
            changed = deepcopy(sources)
            row = next(row for row in changed if row['candidate_id'] == header['candidate_id'])
            row['metadata']['structured_cells'][0]['column_index'] = value
            catalog = build_semantic_candidate_catalog(changed)
            self.assertTrue(all(not cell.get('source_column_period_evidence') for cell in cells(catalog)))

    def test_different_documents_tables_and_header_paths_cannot_supply_axis(self):
        sources, _ = table()
        for key, value in (('source_document_sha256', 'b' * 64), ('physical_table_id', 'other-table'),
                           ('source_table_locator', '/DOC/TABLE[2]'), ('source_document_id', 'other-document')):
            changed = deepcopy(sources)
            header = next(row for row in changed if row['metadata'].get('row_label') == 'Category')
            header['metadata'][key] = value
            self.assertTrue(all(not row.get('source_column_period_evidence') for row in cells(build_semantic_candidate_catalog(changed))))
        changed = deepcopy(sources)
        header = next(row for row in changed if row['metadata'].get('row_label') == 'Category')
        header['metadata']['structured_cells'][1]['column_headers'] = ['Unrelated axis']
        self.assertFalse(cells(build_semantic_candidate_catalog(changed))[1].get('source_column_period_evidence'))

    def test_explicit_unit_in_possible_header_blocks_year_inference(self):
        sources, _ = table()
        header = next(row for row in sources if row['metadata'].get('row_label') == 'Category')
        header['metadata']['structured_cells'][0]['unit_hint'] = 'USD'
        self.assertTrue(all(not row.get('source_column_period_evidence') for row in cells(build_semantic_candidate_catalog(sources))))

    def test_reprojection_is_order_independent_and_drops_missing_source_links(self):
        sources, catalog = table()
        original = deepcopy(catalog)
        self.assertEqual(project_column_period_evidence(list(reversed(sources)), catalog), catalog)
        remaining = [row for row in sources if row['metadata'].get('row_label') != 'Category']
        self.assertTrue(all(not row.get('source_column_period_evidence')
            for row in project_column_period_evidence(remaining, catalog)))
        self.assertEqual(catalog, original)

    def test_source_linkage_does_not_certify_that_a_column_means_measurement_year(self):
        sources, _ = table()
        for row in sources:
            for cell in row['metadata'].get('structured_cells', []):
                cell['column_headers'] = ['Catalog identifier']
        catalog, owners = build_semantic_candidate_catalog(sources), [owner()]
        selected = cells(catalog)[1]
        wire = setup(catalog, owners)
        program = lower(direct(selected, wire[2]), catalog, owners, wire)
        result = validate(program, catalog, owners, wire)
        self.assertEqual(result['status'], 'ready')
        proof = result['valid_direct_bindings'][0]['source_interpretation_resolution']['period_resolution']
        self.assertEqual(proof['validation_scope'], 'source_linkage_not_semantic_equivalence')
        self.assertEqual(proof['evidence']['source']['column_headers'], ['Catalog identifier'])

    def test_valid_selection_reaches_slot_and_operand_without_rewriting_source(self):
        _, catalog = table()
        original, owners = deepcopy(catalog), [owner()]
        selected = cells(catalog)[1]
        wire = setup(catalog, owners)
        program = lower(direct(selected, wire[2]), catalog, owners, wire)
        validation = validate(program, catalog, owners, wire)
        self.assertEqual(validation['status'], 'ready', validation['errors'])
        result = execute(program, catalog, owners, wire, validation)
        output, = result['outputs']
        self.assertEqual(output['rendered_value'], '37items')
        operand, = result['calculation_operands']
        self.assertEqual((operand['period'], operand['value_year'], operand['period_source']), ('2050', 2050, 'source_column_period_binding'))
        proof = output['answer_slot']['source_period_resolution']
        self.assertEqual((proof['source_period'], proof['source_value_year']), ('', None))
        self.assertEqual(proof['evidence']['source']['physical_cell_id'], 'axis:1')
        self.assertEqual(catalog, original)

    def test_prior_equal_value_cell_keeps_its_own_year_and_fails_requested_period(self):
        _, catalog = table()
        owners = [owner()]
        wire = setup(catalog, owners)
        program = lower(direct(cells(catalog)[0], wire[2]), catalog, owners, wire)
        result = validate(program, catalog, owners, wire)
        self.assertEqual(result['status'], 'invalid')
        self.assertIn('candidate_scope_mismatch', [row['code'] for row in result['errors']])

    def test_foreign_column_or_invented_period_reference_is_output_local_error(self):
        _, catalog = table()
        owners = [owner()]
        first, second, *_ = cells(catalog)
        wire = setup(catalog, owners)
        for reference in (wire[2].ref(source_period_options(first)[0]['period_option_id']), 'invented'):
            raw = direct(second, wire[2])
            raw['outputs']['answer']['result']['selection']['interpretation']['period_ref'] = reference
            with self.assertRaisesRegex(ValueError, 'period_option_not_authorized_for_source'):
                lower(raw, catalog, owners, wire)

    def test_short_quote_does_not_replace_column_link_for_any_data_column(self):
        _, catalog = table()
        owners = [owner()]
        wire = setup(catalog, owners)
        for selected in cells(catalog):
            program = lower(direct(selected, wire[2], period=False, quote='2050'), catalog, owners, wire)
            result = validate(program, catalog, owners, wire)
            self.assertEqual(result['status'], 'invalid')
            self.assertIn('missing_source_column_period', [row['code'] for row in result['errors']])

    def test_column_selection_does_not_silence_conflicting_or_ambiguous_context(self):
        _, catalog = table()
        owners = [owner()]
        wire = setup(catalog, owners)
        for selected, quote, expected in ((cells(catalog)[0], '2050', 'context_conflicts_with_candidate'),
                (cells(catalog)[1], 'Projects from 2049 through 2050 are included.', 'context_period_mismatch')):
            program = lower(direct(selected, wire[2], quote=quote), catalog, owners, wire)
            result = validate(program, catalog, owners, wire)
            self.assertIn(expected, [row['code'] for row in result['errors']])

    def test_period_choice_needs_owned_request_and_full_own_column_axis(self):
        _, catalog = table()
        owners = [owner()]
        selected = cells(catalog)[1]
        wire = setup(catalog, owners)
        reading = lower(direct(selected, wire[2]), catalog, owners, wire)['direct_bindings'][0]['source_interpretation']
        for change, error in (({'request_unit_ids': ['foreign']}, 'source_interpretation_request_mismatch'),
                ({'axis_refs': reading['axis_refs'][:1]}, 'source_period_axis_missing')):
            with self.assertRaisesRegex(ValueError, error):
                validate_source_interpretation(selected, {**reading, **change}, owner=owners[0], query=QUERY)
        with self.assertRaisesRegex(ValueError, 'source_period_conflicts_with_candidate'):
            validate_source_interpretation({**selected, 'period': '2049', 'value_year': 2049}, reading, owner=owners[0], query=QUERY)
        with self.assertRaisesRegex(ValueError, 'source_period_conflicts_with_candidate'):
            validate_source_interpretation({**selected, 'period': '2049 / 2050'}, reading, owner=owners[0], query=QUERY)

    def test_null_period_choice_does_not_implicitly_resolve_year(self):
        _, catalog = table()
        owners = [owner()]
        wire = setup(catalog, owners)
        program = lower(direct(cells(catalog)[1], wire[2], period=False), catalog, owners, wire)
        self.assertNotIn('period_option_id', program['direct_bindings'][0]['source_interpretation'])
        self.assertIn('candidate_scope_mismatch', [row['code'] for row in validate(program, catalog, owners, wire)['errors']])

    def test_period_only_reading_supports_already_known_count_unit(self):
        _, catalog = table(unit='items')
        owners = [owner()]
        wire = setup(catalog, owners)
        program = lower(direct(cells(catalog)[1], wire[2]), catalog, owners, wire)
        self.assertEqual(validate(program, catalog, owners, wire)['status'], 'ready')
        self.assertNotIn('unit_ref', json.dumps(wire[4].model_json_schema()))

    def test_schema_choices_are_nullable_and_do_not_include_hidden_owner_cells(self):
        _, catalog = table()
        hidden = cells(catalog)[0]
        hidden.update(period='2049', value_year=2049)
        wire = setup(catalog, [owner()])
        schema = strict_openai_schema(wire[4])
        self.assertNotIn(wire[2].ref(source_period_options(hidden)[0]['period_option_id']), json.dumps(schema))
        definitions = [row for row in schema['$defs'].values() if 'period_ref' in row.get('properties', {})]
        self.assertTrue(definitions)
        for row in definitions:
            self.assertIn('period_ref', row['required'])
            self.assertIn(None, row['properties']['period_ref']['enum'])

    def test_v2_rejects_modified_column_proof_or_program(self):
        _, catalog = table()
        owners = [owner()]
        selected = cells(catalog)[1]
        wire = setup(catalog, owners)
        program = lower(direct(selected, wire[2]), catalog, owners, wire)
        validation = validate(program, catalog, owners, wire)
        inputs = dict(program=program, candidate_catalog=catalog, obligations=owners, query=QUERY)
        envelope = CompilationEnvelopeV2.create(**inputs, visibility=wire[3], validation=validation)
        changed = deepcopy(catalog)
        cells(changed)[1]['source_column_period_evidence'][0]['source']['column_index'] = 0
        altered = deepcopy(program)
        altered['direct_bindings'][0]['source_interpretation'].pop('period_option_id')
        for patch in ({'candidate_catalog': changed}, {'program': altered}):
            result = execute_semantic_calculation_program(**{**inputs, **patch}, compilation_envelope=envelope,
                require_compilation_envelope=True)
            self.assertFalse(result['outputs'])

    def test_derived_inputs_retain_separate_column_year_proofs(self):
        _, catalog = table()
        owners = [owner(kind='derived_value', evidence_requirements=[
            _requirement('current', 'item count', period='2050'), _requirement('prior', 'item count', period='2049')])]
        wire = setup(catalog, owners)
        first, second, *_ = cells(catalog)
        raw = {'outputs': {'answer': dict(status='ready', result=dict(
            inputs={'current': [{**choose(second, wire[2]), 'variable': 'A'}],
                    'prior': [{**choose(first, wire[2]), 'variable': 'B'}]},
            formula=[dict(operation='subtract', arguments=[dict(variable='A'), dict(variable='B')])],
            display_unit='items', display_format='', source_display=None,
            source_display_reason='Requested calculated difference.', comparison_request_unit_id=None, compatibility_refs=[]))}}
        program = lower(raw, catalog, owners, wire)
        validation = validate(program, catalog, owners, wire)
        self.assertEqual(validation['status'], 'ready', validation['errors'])
        output, = execute(program, catalog, owners, wire, validation)['outputs']
        self.assertEqual(output['calculated_value'], 0)
        self.assertEqual([row['value_year'] for row in output['input_rows']], [2050, 2049])

    def test_one_existing_repair_retains_exact_period_choice_and_executes(self):
        _, catalog = table()
        selected, answer = cells(catalog)[1], owner()
        llm = AuthoredReadingLLM(lambda refs: dict(selection=choose(selected, refs), compatibility_refs=[]), invalid_first=True)
        compiled = compile_case(catalog, answer, QUERY, llm)
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertEqual(len(llm.prompts), 2)
        for prompt in llm.prompts:
            self.assertIn('interpretation.period_ref', prompt.to_messages()[0].content)
        result = execute_compiled(compiled, catalog, answer, QUERY)
        self.assertEqual(result['outputs_by_obligation']['answer']['rendered_value'], '37items')


if __name__ == '__main__':
    unittest.main()
