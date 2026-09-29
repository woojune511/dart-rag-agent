"""Lossless wire tables retain exact evidence and the existing SDK/program contract."""
from copy import deepcopy
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx

from src.agent.financial_compiler_presentation import project_wire_reading_payload
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.compiler_presentation_test_support import expand_piece_rows
from tests.compiler_wire_test_support import wire_fixture
from tests.narrative_address_test_support import model_program
from tests.semantic_program_test_support import _candidate, _obligation
from tests.test_narrative_claim_grounding import claim, source
from tests.test_openai_compiler_transport import ROUTE, response_body


MARKER = 'Source bundles, candidate cohorts, and candidates_by_id:\n'


def encoded(value):
    return json.dumps(value, ensure_ascii=False, separators=(',', ':'))


def restore_payload(payload):
    result = expand_piece_rows(payload)
    if result.get('schema') == 'semantic_program_candidate_payload_v10':
        del result['piece_columns']
        result['schema'] = 'semantic_program_candidate_payload_v9'
    return result


def restore_request(value):
    if isinstance(value, dict):
        return {key: restore_request(item) for key, item in value.items()}
    if isinstance(value, list):
        return [restore_request(item) for item in value]
    if isinstance(value, str) and MARKER in value:
        prefix, tail = value.split(MARKER, 1)
        payload, end = json.JSONDecoder().raw_decode(tail)
        return prefix + MARKER + encoded(restore_payload(payload)) + tail[end:]
    return value


class CompilerPieceRowTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'))
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network forbidden')))

    def test_all_surface_positions_preserve_text_addresses_partitions_and_metadata(self):
        reading = {}
        for index, group in enumerate(('enclosing_contexts', 'preceding_contexts', 'bodies', 'following_contexts')):
            reading[group] = [dict(surface_id=f's{index}', source_id=f'own-{index}', pieces=[
                dict(piece_id='p1', partition=0, text='  나무\r\n(1,200)\t'),
                dict(piece_id='p2', partition=0, text='same wording; '),
                dict(piece_id='p3', partition=1, text='same wording; '),
            ])]
        reading['following_contexts'].append(dict(context_id='distinct-context', surface_ref='s2'))
        payload = dict(schema='semantic_program_candidate_payload_v9', source_readings=[reading],
            candidates_by_id={'c1': {'source_span': [0, 12], 'source_text': '  preserved\n'}},
            permission={'a': ['c1'], 'b': []})
        before = deepcopy(payload)
        result = project_wire_reading_payload(payload)
        self.assertEqual(encoded(restore_payload(result)), encoded(before))
        self.assertEqual(payload, before)
        self.assertLess(len(encoded(result).encode()), len(encoded(before).encode()))
        result['source_readings'][0]['bodies'][0]['pieces'][0][2] = 'changed copy'
        self.assertEqual(payload, before)

    def test_numeric_and_empty_readings_keep_the_exact_existing_wire(self):
        for body in ({'source_text': 'Amount | 12'}, {'surface_id': 's0', 'pieces': []}):
            with self.subTest(body=body):
                payload = dict(schema='semantic_program_candidate_payload_v9', source_readings=[dict(
                    enclosing_contexts=[], preceding_contexts=[], bodies=[body], following_contexts=[])],
                    candidates_by_id={'c1': {'metadata': {'pieces': 'source literal'}}})
                self.assertEqual(encoded(project_wire_reading_payload(payload)), encoded(payload))

    def test_unrecognized_piece_fields_fail_without_losing_data(self):
        piece = dict(piece_id='p1', partition=0, text='A source.', future_provenance={'scope': 'separate'})
        payload = dict(schema='semantic_program_candidate_payload_v9', source_readings=[dict(
            enclosing_contexts=[], preceding_contexts=[], bodies=[{'pieces': [piece]}], following_contexts=[])])
        before = deepcopy(payload)
        with self.assertRaisesRegex(ValueError, 'unsupported_reading_piece_fields'):
            project_wire_reading_payload(payload)
        self.assertEqual(payload, before)

    def compile_sdk(self, state, programs, *, previous_wire):
        owner = FinancialAgent.__new__(FinancialAgent)
        owner.llm_usage_callback = GeminiUsageCallbackHandler()
        llm = owner._create_chat_model(ROUTE, phase='program_compilation')
        sent, responses, schemas = [], [], []

        class ModelRecorder:
            def with_structured_output(self, model):
                self.model = model
                schemas.append(model.model_json_schema())
                return llm.with_structured_output(model)

        recorder = ModelRecorder()

        def send(client, request, **kwargs):
            self.assertEqual(str(request.url), 'https://api.openai.com/v1/responses')
            sent.append(json.loads(request.content))
            self.assertLessEqual(len(sent), len(programs))
            wire = recorder.model.model_validate(
                wire_fixture(programs[len(sent) - 1], recorder.model)).model_dump()
            responses.append(deepcopy(wire))
            return httpx.Response(200, request=request, json=response_body(wire))

        agent = _CompilerOnlyAgent(recorder, usage_callback=owner.llm_usage_callback)
        projection = (lambda payload: deepcopy(payload)) if previous_wire else project_wire_reading_payload
        before = deepcopy(state)
        with patch.object(httpx.Client, 'send', send), patch(
                'src.agent.financial_graph_calculation.project_wire_reading_payload', projection):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(state, before)
        self.assertEqual(len(sent), len(programs))
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        executed = execute_semantic_calculation_program(program=compiled['semantic_program'],
            candidate_catalog=state['semantic_candidate_catalog'], obligations=state['answer_obligations'],
            query=state['query'], compilation_envelope=compiled['semantic_compilation_envelope'],
            require_compilation_envelope=True)
        self.assertEqual(executed['status'], 'ok')
        return compiled, executed, sent, responses, schemas

    def compare_sdk(self, state, programs, *, expected_retry=0, numeric_only=False):
        old = self.compile_sdk(deepcopy(state), programs, previous_wire=True)
        new = self.compile_sdk(deepcopy(state), programs, previous_wire=False)
        for key in ('semantic_program', 'semantic_program_validation', 'semantic_compilation_envelope',
                    'semantic_program_retry_count', 'missing_info'):
            self.assertEqual(new[0][key], old[0][key], key)
        self.assertEqual(new[0]['semantic_program_retry_count'], expected_retry)
        self.assertEqual(new[1], old[1])
        self.assertEqual(new[3:], old[3:])
        self.assertEqual(restore_request(new[2]), old[2])
        if numeric_only:
            self.assertEqual(new[2], old[2])
        else:
            self.assertLess(len(encoded(new[2]).encode()), len(encoded(old[2]).encode()))
        return new

    def narrative_fixture(self):
        catalog = [source('note', 'Birch delivers through partners. Birch serves 17 regions.')]
        owners = [_obligation('routes', 'narrative', 'Describe routes.')]
        program = model_program({'narrative_bindings': [{'obligation_id': 'routes', 'claims': [
            claim('Birch', 'Delivers through partners.', 'note', 'Birch delivers through partners.'),
            claim('Birch', 'Serves 17 regions.', 'note', 'Birch serves 17 regions.'),
        ]}]}, catalog)
        return catalog, owners, program

    def test_sdk_narrative_request_round_trip_and_execution_are_identical(self):
        catalog, owners, program = self.narrative_fixture()
        state = _case_state({'question': 'Describe routes and reach.', 'obligations': owners}, catalog)
        self.compare_sdk(state, [program])

    def test_sdk_retry_keeps_failed_draft_schema_and_repaired_execution(self):
        catalog, owners, program = self.narrative_fixture()
        bad = program.model_copy(deep=True)
        bad.narrative_bindings[0].claims[1].text = 'Serves 93 regions.'
        state = _case_state({'question': 'Describe routes and reach.', 'obligations': owners}, catalog)
        self.compare_sdk(state, [bad, program], expected_retry=1)

    def test_sdk_numeric_request_is_byte_equivalent(self):
        state = _case_state({'question': 'Read the size.', 'obligations': [
            _obligation('size', 'direct_value', 'Read the size.')]}, [_candidate('cell', 12)])
        program = SemanticCalculationProgram(direct_bindings=[{'obligation_id': 'size', 'candidate_id': 'cell'}])
        self.compare_sdk(state, [program], numeric_only=True)

    def test_sdk_mixed_islands_keep_numeric_request_and_all_outputs(self):
        catalog, owners, program = self.narrative_fixture()
        state = _case_state({'question': 'Read the size and describe routes.', 'obligations': [
            _obligation('size', 'direct_value', 'Read the size.'), *owners]}, [_candidate('cell', 12), *catalog])
        numeric = SemanticCalculationProgram(direct_bindings=[{'obligation_id': 'size', 'candidate_id': 'cell'}])
        result = self.compare_sdk(state, [numeric, program])
        self.assertNotIn('piece_columns', encoded(result[2][0]))


if __name__ == '__main__':
    unittest.main()
