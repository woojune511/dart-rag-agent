"""Authored display-intent transport and rejection; not Planner inference tests."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator

from src.agent.financial_graph import compilation_phase_input, planning_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_request_units import build_request_units
from src.config.llm_profiles import app_llm_routing_config
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate
from tests.test_narrative_retry_context import prompt_json
from tests.test_openai_compiler_transport import response_body
from tests.test_planner_requirement_transport import agent_for, request


def authored_plan(query, unit, form, kind='direct_value'):
    return RequirementPlannerOutput(obligations=[dict(
        obligation_id='ob_001', kind=kind, label='quantity',
        request_unit_ids=[u.request_unit_id for u in build_request_units(query)],
        display_unit=unit, display_format=form)])


class PlannerNumericPresentationTests(unittest.TestCase):
    def run_direct(self, query, unit, form, source_unit):
        planned = authored_plan(query, unit, form)
        llm = _StructuredQueueLLM(planned, SemanticCalculationProgram(direct_bindings=[
            dict(obligation_id='ob_001', candidate_id='quantity')]))
        agent = agent_for(llm)
        state = request(query, intent='numeric_fact')
        candidate = dict(_candidate('quantity', '1,234.500', raw_unit=source_unit,
                                   period='2042'), company='Issuer', document_company='Issuer', year=2042)
        before = deepcopy((planned.model_dump(), candidate))
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=[candidate])
        state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        compiled_owner, = prompt_json(llm.prompts[1], 'Answer obligations:')
        self.assertEqual((compiled_owner['display_unit'], compiled_owner['display_format']), (unit, form))
        self.assertEqual(compiled_owner['request_unit_ids'], planned.obligations[0].request_unit_ids)
        self.assertEqual(compiled_owner['scope']['company'], 'Issuer')
        self.assertEqual(compiled_owner['scope']['period'], '')
        self.assertIn(query, llm.prompts[1].to_messages()[0].content)
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual(llm.models, ['RequirementPlannerOutput', 'CompilerResponseV2'])
        self.assertEqual(llm.responses, [])
        self.assertEqual((planned.model_dump(), candidate), before)
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'ok')
        output, = answer['resolved_calculation_trace']['calculation_result']['outputs']
        self.assertEqual(output['answer_slot']['raw_value'], '1,234.500')
        self.assertEqual(output['answer_slot']['raw_unit'], source_unit)
        self.assertIn('1,234.500' + source_unit, answer['answer'])

    def test_source_preservation_formats_reach_compiler_without_guessing_unit(self):
        for instruction in ('원문 표기와 단위를 그대로 유지해 줘.',
                            'Preserve the source notation and unit.',
                            'Use the reported scale without rounding.'):
            for unit in ('백만원', '만 대', '%'):
                with self.subTest(instruction=instruction, source_unit=unit):
                    self.run_direct('Return the quantity. ' + instruction, '', instruction, unit)

    def test_explicit_unit_and_independent_format_both_survive_planning(self):
        for unit in ('백만원', '만 대', '%p'):
            with self.subTest(unit=unit):
                instruction = 'Keep all reported decimal places.'
                self.run_direct(f'Return the quantity in {unit}. ' + instruction, unit, instruction, unit)

    def test_misplaced_presentation_and_unsupported_concrete_units_are_not_cleared(self):
        for kind in ('direct_value', 'derived_value'):
            for unit in ('원문 단위', 'as reported', 'no rounding', 'EUR', 'unregistered-unit'):
                with self.subTest(kind=kind, unit=unit):
                    query = f'Return the requested quantity in {unit}.'
                    plan = authored_plan(query, unit, 'Preserve the requested display.', kind)
                    before = deepcopy(plan.model_dump())
                    llm = _StructuredQueueLLM(plan)
                    agent = agent_for(llm)
                    state = request(query, intent='numeric_fact')
                    state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
                    state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=[])
                    state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
                    owner, = state['requirements']['answer_obligations']
                    self.assertEqual((owner['display_unit'], owner['display_format']),
                                     (unit, plan.obligations[0].display_format))
                    error, = state['requirements']['semantic_plan']['requirement_errors']
                    self.assertEqual((error['code'], error['detail'], error['repair_action']),
                                     ('invalid_obligation_unit', unit, 'repair_requirements'))
                    self.assertEqual(llm.models, ['RequirementPlannerOutput'])
                    self.assertEqual(plan.model_dump(), before)

    def test_real_sdk_keeps_open_numeric_units_and_both_field_descriptions(self):
        query = 'Return the requested quantity with its original notation.'
        value = authored_plan(query, '', 'Preserve source notation and unit.')
        value.obligations.append(authored_plan(query, 'unsupported-unit', 'Two decimal places.',
                                              'derived_value').obligations[0])
        agent = agent_for(None)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        route = dict(app_llm_routing_config('openai')['llm_routes']['default'], api_key='offline-placeholder')
        sent = []
        def send(request, **kwargs):
            sent.append(json.loads(request.content))
            body = response_body(value.model_dump())
            body['model'] = route['model']
            return httpx.Response(200, request=request, json=body)
        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network forbidden')), \
             patch.object(httpx.Client, 'send', side_effect=send):
            agent.llm = agent._create_chat_model(route, phase='requirement_planning')
            planned = agent._plan_answer_obligation_program(planning_phase_input(request(query, intent='numeric_fact')))
        self.assertEqual([o['display_unit'] for o in planned['answer_obligations']], ['', 'unsupported-unit'])
        self.assertEqual([o['display_format'] for o in planned['answer_obligations']],
                         [o.display_format for o in value.obligations])
        error, = planned['semantic_plan']['requirement_errors']
        self.assertEqual((error['code'], error['obligation_id']), ('invalid_obligation_unit', 'ob_002'))
        body, = sent
        self.assertIn(query, json.dumps(body['input']))
        self.assertTrue(body['text']['format']['strict'])
        schema = body['text']['format']['schema']
        Draft202012Validator(schema).validate(value.model_dump())
        local = RequirementPlannerOutput.model_json_schema()
        for branch in ('DirectValueAnswerObligation', 'DerivedValueAnswerObligation'):
            props = schema['$defs'][branch]['properties']
            self.assertEqual(props['display_unit']['type'], 'string')
            self.assertNotIn('enum', props['display_unit'])
            for field in ('display_unit', 'display_format'):
                self.assertEqual(props[field]['description'], local['$defs'][branch]['properties'][field]['description'])


if __name__ == '__main__':
    unittest.main()
