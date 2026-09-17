"""Anonymous direct-witness contracts and authored SDK replies, not model accuracy."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_compiler_wire import CompilerReferencesV1, compiler_response_model
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.config.llm_profiles import app_llm_routing_config
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.semantic_program_test_support import _candidate, _obligation, _scope
from tests.source_interpretation_fixture_support import authored_source_program
from tests.test_compiler_numeric_reading_intent import AuthoredReadingLLM, compile_case, execute, selection
from tests.test_openai_compiler_transport import response_body


def direct_case(year=2042, value=73):
    query = f'Return the {year} reported quantity.'
    owner = _obligation('answer', 'direct_value', 'quantity', scope=_scope(company='Issuer', period=str(year)))
    selected = dict(_candidate('selected', value, period=str(year)), company='Issuer',
        document_company='Issuer', year=year, source_document_id='filing-a',
        physical_table_id='table-a', physical_row_id='row-a', physical_cell_id='cell-a',
        row_headers=['quantity'], source_anchor=f'[Issuer | {year} | Measurements]')
    witness = dict(selected, candidate_id='witness', kind='narrative', candidate_kind='table_context',
        source_text=f'The table reports the quantity for {year}.', raw_value='', raw_unit='',
        normalized_value=None, normalized_unit='UNKNOWN', physical_row_id='', physical_cell_id='')
    return query, owner, [selected, witness]


def separate_context(witness):
    return dict(witness, physical_table_id='', table_source_id='discussion',
        evidence_id='discussion', context_fingerprint='discussion',
        source_anchor=witness['source_anchor'].replace('Measurements', 'Discussion'))


def direct_program(owner, catalog, query, witnesses):
    return authored_source_program({'direct_bindings': [dict(obligation_id=owner['obligation_id'],
        candidate_id='selected', compatibility_candidate_ids=witnesses)]}, [owner], catalog, query)


def validate(query, owner, catalog, witnesses, **kwargs):
    program = direct_program(owner, catalog, query, witnesses)
    before = deepcopy((program, owner, catalog))
    result = validate_semantic_calculation_program(program=program, obligations=[owner],
        candidate_catalog=catalog, query=query, **kwargs)
    assert (program, owner, catalog) == before
    return result


class DirectCompatibilityGuidanceTests(unittest.TestCase):
    def test_complete_selection_needs_no_general_corroboration(self):
        for year, value in ((2042, 73), (2031, 128.5)):
            query, owner, catalog = direct_case(year, value)
            selected, witness = catalog
            for ordered in (catalog, list(reversed(catalog))):
                with self.subTest(year=year, reversed=ordered != catalog):
                    self.assertEqual(validate(query, owner, ordered, [])['status'], 'ready')
                    accepted = validate(query, owner, ordered, ['witness'])
                    self.assertEqual(accepted['status'], 'ready', accepted['errors'])
                    self.assertEqual(accepted['valid_direct_bindings'][0]['compatibility_candidate_ids'], ['witness'])
            # Same filing, year and topic do not link a separately located discussion.
            rejected = validate(query, owner, [selected, separate_context(witness)], ['witness'])
            self.assertEqual([e['code'] for e in rejected['errors']], ['direct_compatibility_context_mismatch'])
            self.assertEqual(rejected['valid_direct_bindings'], [])

    def test_located_period_witness_bridges_only_an_unknown_period_in_its_context(self):
        query, owner, catalog = direct_case()
        selected, witness = catalog
        selected.update(period='', column_headers=['quantity'], source_text='quantity 73 items')
        self.assertIn('candidate_scope_mismatch', {e['code'] for e in validate(query, owner, catalog, [])['errors']})
        self.assertEqual(validate(query, owner, catalog, ['witness'])['status'], 'ready')
        for changes, expected in (({'source_document_id': 'filing-b'}, 'direct_compatibility_context_mismatch'),
                ({'physical_table_id': 'table-b'}, 'direct_compatibility_context_mismatch'),
                ({'period': '2041', 'column_headers': ['2041']}, 'compatibility_scope_mismatch')):
            with self.subTest(changes=changes):
                rejected = validate(query, owner, [selected, {**witness, **changes}], ['witness'])
                self.assertIn(expected, {e['code'] for e in rejected['errors']})
                self.assertEqual(rejected['valid_direct_bindings'], [])
        selected.update(period='2041', column_headers=['2041'])
        self.assertIn('candidate_scope_mismatch', {e['code'] for e in validate(query, owner, catalog, ['witness'])['errors']})

    def test_witness_kind_company_and_owner_checks_remain_independent(self):
        query, owner, catalog = direct_case()
        selected, witness = catalog
        for changes, expected in (({'kind': 'numeric'}, 'invalid_compatibility_candidate'),
                ({'source_text': ''}, 'invalid_compatibility_candidate'),
                ({'company': 'Other', 'document_company': 'Other'}, 'compatibility_scope_mismatch')):
            with self.subTest(changes=changes):
                result = validate(query, owner, [selected, {**witness, **changes}], ['witness'])
                self.assertIn(expected, {e['code'] for e in result['errors']})
                self.assertEqual(result['valid_direct_bindings'], [])
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=['selected', 'witness'],
            candidate_ids_by_owner={'answer': ['selected'], 'sibling': ['witness']})
        result = validate(query, owner, catalog, ['witness'], candidate_visibility=visibility)
        self.assertIn('candidate_not_exposed_to_compiler', {e['code'] for e in result['errors']})
        self.assertEqual(result['valid_direct_bindings'], [])

    def test_existing_context_minimum_does_not_bypass_other_witness_checks(self):
        query, owner, catalog = direct_case()
        extra = dict(separate_context(catalog[1]), candidate_id='extra')
        catalog.append(extra)
        # Characterize the existing any-same-context rule, not a new all-same rule.
        accepted = validate(query, owner, catalog, ['witness', 'extra'])
        self.assertEqual(accepted['status'], 'ready', accepted['errors'])
        self.assertEqual(accepted['valid_direct_bindings'][0]['compatibility_candidate_ids'], ['witness', 'extra'])
        extra.update(period='2041', column_headers=['2041'])
        rejected = validate(query, owner, catalog, ['witness', 'extra'])
        self.assertIn('compatibility_scope_mismatch', {e['code'] for e in rejected['errors']})
        self.assertEqual(rejected['valid_direct_bindings'], [])

    def test_repeated_invalid_wire_is_not_silently_cleared(self):
        query, owner, catalog = direct_case()
        catalog[1] = separate_context(catalog[1])
        llm = AuthoredReadingLLM(lambda refs: {'selection': selection(refs, catalog[0], 'quantity'),
            'compatibility_refs': [refs.ref('witness')]})
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(execute(compiled, catalog, owner, query)['outputs'], [])
        attempts = compiled['compiler_attempts']
        self.assertEqual(len(attempts), 2)
        for attempt in attempts:
            program = json.loads(attempt['validation_input_program_json'])
            self.assertEqual(program['direct_bindings'][0]['candidate_id'], 'selected')
            self.assertEqual(program['direct_bindings'][0]['compatibility_candidate_ids'], ['witness'])
            self.assertIn('direct_compatibility_context_mismatch', {e['code'] for e in attempt['validation_errors']})

    def test_direct_guidance_reaches_sdk_and_feedback_keeps_selection_and_visibility(self):
        query, owner, catalog = direct_case()
        catalog[1] = separate_context(catalog[1])
        cohorts = _semantic_candidate_cohorts(catalog, [owner])
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=cohorts['visible_candidate_ids'],
            candidate_ids_by_owner=cohorts['candidate_ids_by_owner'])
        payload = FinancialAgent._semantic_program_prompt_payload(catalog, cohorts)
        refs = CompilerReferencesV1.build(catalog, [owner], query, payload)
        model = compiler_response_model([owner], refs, visibility)
        wires = [model.model_validate({'outputs': {'answer': {'status': 'ready', 'result': {
            'selection': selection(refs, catalog[0], 'quantity'), 'compatibility_refs': witnesses}}}}).model_dump()
            for witnesses in ([refs.ref('witness')], [])]
        sent = []
        def send(request, **kwargs):
            sent.append(json.loads(request.content))
            return httpx.Response(200, request=request, json=response_body(wires[len(sent) - 1]))
        agent = object.__new__(FinancialAgent)
        agent.llm_routes = {}
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        route = dict(app_llm_routing_config('openai')['llm_routes']['program_compilation'], api_key='offline-placeholder')
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network forbidden')), \
             patch.object(httpx.Client, 'send', side_effect=send):
            agent.llm = agent._create_chat_model(route, phase='program_compilation')
            compiled = agent._compile_semantic_calculation_program(dict(query=query, answer_obligations=[owner],
                include_debug_bundle=True, semantic_candidate_catalog_prebuilt=True,
                semantic_source_candidates=catalog, semantic_candidate_catalog=catalog))
        self.assertEqual(len(sent), 2)
        for body, wire in zip(sent, wires):
            self.assertTrue(body['text']['format']['strict'])
            schema = body['text']['format']['schema']
            Draft202012Validator(schema).validate(wire)
            fields = schema['$defs']['Direct_answer']['properties']
            self.assertEqual(set(fields), {'selection', 'compatibility_refs'})
            self.assertEqual(fields['compatibility_refs']['items'], {'type': 'string'})
            description = fields['compatibility_refs']['description']
            self.assertIn('Use []', description)
            self.assertIn('source context', description)
            self.assertIn('context_ref', description)
            self.assertIn('직접 조회의 compatibility_refs', json.dumps(body['input'], ensure_ascii=False))
        self.assertEqual(sent[0]['text']['format']['schema'], sent[1]['text']['format']['schema'])
        first, repair = [json.loads(a['validation_input_program_json'])['direct_bindings'][0]
                         for a in compiled['compiler_attempts']]
        self.assertEqual(first['compatibility_candidate_ids'], ['witness'])
        self.assertEqual(repair['compatibility_candidate_ids'], [])
        self.assertEqual({k:v for k,v in first.items() if k != 'compatibility_candidate_ids'},
                         {k:v for k,v in repair.items() if k != 'compatibility_candidate_ids'})
        attempts = compiled['resolved_calculation_trace']['calculation_plan']['candidate_stage_diagnostics']['attempts']
        self.assertEqual(attempts[0]['visible_candidate_ids'], attempts[1]['visible_candidate_ids'])
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertEqual(execute(compiled, catalog, owner, query)['outputs_by_obligation']['answer']['answer_slot']['normalized_value'], 73)


if __name__ == '__main__':
    unittest.main()
