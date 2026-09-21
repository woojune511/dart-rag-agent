"""Authored output-kind transport and source checks, not Planner accuracy tests."""
from copy import deepcopy
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator

from src.agent.financial_graph import compilation_phase_input, planning_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_request_units import build_request_units
from src.agent.financial_source_interpretation import validate_source_interpretation
from src.config.llm_profiles import app_llm_routing_config
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.narrative_address_test_support import model_program
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate
from tests.test_narrative_claim_grounding import claim, source
from tests.test_openai_compiler_transport import response_body
from tests.test_planner_requirement_transport import agent_for, request


STATUS_CASES = (
    ('Aster',
     'State whether installation of 24 units by Aster was complete as of the report date and retain any pending condition.',
     'Aster scheduled installation of 24 units. Aster had not completed installation at the report date; inspection was still required.'),
    ('아스터',
     '보고서 작성 시점에 아스터의 장비 24대 설치가 완료됐는지와 남은 조건을 설명해 줘.',
     '아스터는 장비 24대 설치를 계획했습니다. 아스터의 설치는 보고서 작성 시점에 완료되지 않았으며 검수 절차가 남아 있습니다.'),
)


def authored_owner(kind, label, query, *, subject='', key='requested'):
    row = dict(obligation_id=key, kind=kind, label=label, display_unit='',
        request_unit_ids=[u.request_unit_id for u in build_request_units(query)],
        display_format='brief answer', semantic_target=dict(local_subjects=[subject] if subject else []))
    if kind == 'narrative':
        row['evidence_requirements'] = [dict(label=label, semantic_target=deepcopy(row['semantic_target']))]
    return row


def status_source(subject, text):
    return source('status-note', text, company='Issuer', document_company='Issuer', year=2042,
        candidate_kind='chunk', table_source_id='', physical_table_id='', physical_row_id='',
        period='', row_label='', context_fingerprint='status-paragraph')


class PlannerOutputKindBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'))
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')))
        self.enterContext(patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network forbidden')))

    def run_authored(self, subject, query, text, *, mixed=False, claim_text=None):
        rows = [authored_owner('narrative', 'installation status and pending condition', query, subject=subject)]
        catalog = [status_source(subject, text)]
        narrative = model_program({'narrative_bindings': [dict(obligation_id='ob_001', claims=[
            claim(subject, claim_text or text, 'status-note', text, source_requirement_id='ob_001:req_001')])]}, catalog)
        responses = [narrative]
        if mixed:
            rows.append(authored_owner('direct_value', 'reported planned quantity', query, key='quantity'))
            catalog.append(dict(_candidate('quantity', '24.000', raw_unit='items', period='2042',
                row_label='planned installations'), company='Issuer', document_company='Issuer', year=2042))
            responses.append(SemanticCalculationProgram(direct_bindings=[dict(obligation_id='ob_002', candidate_id='quantity')]))
        plan = RequirementPlannerOutput(obligations=rows)
        before = deepcopy((plan.model_dump(), catalog))
        llm = _StructuredQueueLLM(plan, *responses)
        agent = agent_for(llm)
        state = request(query, intent='numeric_fact', form='table')
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=catalog)
        state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual((plan.model_dump(), catalog), before)
        self.assertEqual(llm.responses, [])
        self.assertEqual(llm.models, ['RequirementPlannerOutput'] + ['CompilerResponseV2'] * len(rows))
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        self.assertTrue(all(query in p.to_messages()[0].content for p in llm.prompts))
        return state

    def test_actual_sdk_carries_output_kind_meaning_and_unchanged_structural_choices(self):
        subject, query, _ = STATUS_CASES[0]
        rows = [authored_owner(kind, kind, query, subject=subject, key=kind)
                for kind in ('narrative', 'direct_value', 'derived_value')]
        for row in rows:
            for target in [row, *row.get('evidence_requirements', [])]:
                target['scope'] = dict(measurement_period=dict(kind='unspecified'))
        response = RequirementPlannerOutput(obligations=rows)
        agent = agent_for(None)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        route = dict(app_llm_routing_config('openai')['llm_routes']['default'], api_key='offline-placeholder')
        sent = []
        def send(request, **kwargs):
            sent.append(json.loads(request.content))
            body = response_body(response.model_dump())
            body['model'] = route['model']
            return httpx.Response(200, request=request, json=body)
        with patch.object(httpx.Client, 'send', side_effect=send):
            agent.llm = agent._create_chat_model(route, phase='requirement_planning')
            planned = agent._plan_answer_obligation_program(planning_phase_input(request(query)))
        self.assertEqual([o['kind'] for o in planned['answer_obligations']], ['narrative', 'direct_value', 'derived_value'])
        body, = sent
        prompt = body['input'][0]['content']
        self.assertIn(query, prompt)
        self.assertIn('요청된 단일 수치', prompt)
        self.assertIn('상태·발생 여부·조건·관계', prompt)
        self.assertIn('짧은 예/아니오', prompt)
        self.assertIn('별도로 요청한 수치 출력', prompt)
        schema = body['text']['format']['schema']
        self.assertTrue(body['text']['format']['strict'])
        Draft202012Validator(schema).validate(response.model_dump())
        local = RequirementPlannerOutput.model_json_schema()
        for branch, kind, meaning in (
            ('DirectValueAnswerObligation', 'direct_value', 'scalar numeric'),
            ('DerivedValueAnswerObligation', 'derived_value', 'calculated scalar'),
            ('NarrativeAnswerObligation', 'narrative', 'status')):
            field = schema['$defs'][branch]['properties']['kind']
            self.assertEqual(field['const'], kind)
            self.assertIn(meaning, field['description'])
            self.assertEqual(field['description'], local['$defs'][branch]['properties']['kind']['description'])

    def test_authored_status_with_numbers_and_pending_conditions_uses_narrative_path(self):
        for subject, query, text in STATUS_CASES:
            with self.subTest(subject=subject):
                state = self.run_authored(subject, query, text)
                owner, = state['requirements']['answer_obligations']
                self.assertEqual(owner['kind'], 'narrative')
                self.assertEqual((owner['display_unit'], owner['scope']['period']), ('', ''))
                answer = state['final_result']['agent_answer']
                self.assertEqual(answer['structured_result']['status'], 'ok')
                self.assertIn(text, answer['answer'])
                output, = answer['resolved_calculation_trace']['calculation_result']['outputs']
                self.assertTrue(output['claim_readings'])
                self.assertFalse(state['compilation']['semantic_program']['direct_bindings'])

    def test_mixed_status_and_explicit_scalar_stay_separate_despite_shared_unit(self):
        subject, query, text = STATUS_CASES[0]
        query = query.rstrip('.') + '; also return the separately reported planned installation count in its original notation.'
        state = self.run_authored(subject, query, text, mixed=True)
        owners = state['requirements']['answer_obligations']
        self.assertEqual([o['kind'] for o in owners], ['narrative', 'direct_value'])
        self.assertEqual(owners[0]['request_unit_ids'], owners[1]['request_unit_ids'])
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'ok')
        outputs = {o['obligation_id']: o for o in answer['resolved_calculation_trace']['calculation_result']['outputs']}
        self.assertTrue(outputs['ob_001']['claim_readings'])
        self.assertEqual(outputs['ob_002']['answer_slot']['raw_value'], '24.000')
        self.assertEqual(outputs['ob_002']['answer_slot']['raw_unit'], 'items')

    def test_misclassified_authored_plan_is_not_rewritten_from_question_keywords(self):
        subject, query, _ = STATUS_CASES[0]
        wrong = RequirementPlannerOutput(obligations=[authored_owner('direct_value', 'status', query, subject=subject)])
        before = deepcopy(wrong.model_dump())
        llm = _StructuredQueueLLM(wrong)
        result = agent_for(llm)._plan_answer_obligation_program(planning_phase_input(request(query)))
        owner, = result['answer_obligations']
        self.assertEqual(owner['kind'], 'direct_value')
        self.assertEqual(owner['label'], 'status')
        self.assertEqual(result['semantic_plan']['requirement_errors'], [])
        self.assertEqual(wrong.model_dump(), before)
        self.assertEqual(llm.models, ['RequirementPlannerOutput'])
        # Structural acceptance is not a correct semantic classification.

    def test_source_linkage_does_not_certify_a_counterfactual_status_claim(self):
        subject, query, text = STATUS_CASES[0]
        wrong_claim = 'Aster had completed installation at the report date.'
        state = self.run_authored(subject, query, text, claim_text=wrong_claim)
        self.assertEqual(state['compilation']['semantic_program_validation']['status'], 'ready')
        self.assertIn(wrong_claim, state['final_result']['agent_answer']['answer'])
        # Deliberate semantic negative: authored claims are not an entailment oracle.

    def test_numeric_source_quote_is_still_exact_and_never_trimmed(self):
        subject, query, _ = STATUS_CASES[0]
        text = 'Aster planned 24 units; installation remained subject to inspection.'
        candidate = dict(_candidate('planned-quantity', 24), candidate_kind='sentence_value',
            source_text=text, source_bundle_text=' ' + text)
        owner = dict(authored_owner('direct_value', 'status', query, subject=subject))
        interpretation = dict(request_unit_ids=owner['request_unit_ids'], subject=subject, metric='status',
            scope={}, source_evidence_text=' ' + text)
        before = deepcopy((candidate, interpretation, owner))
        with self.assertRaisesRegex(ValueError, '^source_interpretation_quote_mismatch$'):
            validate_source_interpretation(candidate, interpretation, owner=owner, query=query)
        self.assertEqual((candidate, interpretation, owner), before)


if __name__ == '__main__':
    unittest.main()
