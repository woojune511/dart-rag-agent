"""Authored planner-response transport, not planner inference or semantic accuracy."""

from copy import deepcopy
import json
import unittest
from unittest.mock import Mock

from src.agent.financial_graph import (
    FinancialAgent, planning_phase_input, retrieval_phase_input, compilation_phase_input,
)
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_narrative_claim_grounding import source, claim
from tests.test_narrative_retry_context import prompt_json


def agent_for(llm):
    agent = object.__new__(FinancialAgent)
    agent.llm, agent.llm_routes, agent.llm_usage_callback, agent.vsm = llm, {}, None, None
    return agent


def request(query, *, intent='business_overview', form='paragraph'):
    return {'request': {'query': query, 'report_scope': {'company': 'Issuer', 'year': 2042}},
            'routing': {'intent': intent, 'query_type': intent, 'format_preference': form,
                        'topic': 'deliberately short routing summary'}}


def owner(subject, label, *, key='raw-output', source_group=False):
    row = {'obligation_id': key, 'kind': 'narrative', 'label': label,
           'source_sections': ['Operating description'], 'required': True,
           'semantic_target': {'local_subjects': [subject], 'metric_surfaces': ['routes']},
           'retrieval_hints': ['route overview']}
    if source_group:
        row['evidence_mode'] = 'source_defined_group'
    else:
        row['evidence_requirements'] = [{'requirement_id': 'raw-input', 'label': label,
            'semantic_target': deepcopy(row['semantic_target']), 'retrieval_hints': ['route evidence']}]
    return row


def evidence(subject, cid):
    return source(cid, f'{subject} uses partners. The wider group is not described.',
                  company='Issuer', document_company='Issuer', year=2042,
                  source_document_id='anonymous-report',
                  source_anchor='[Issuer | 2042 | Operating description]',
                  physical_table_id='', physical_row_id='', physical_cell_id='')


def program(index, subject, cid, *, bad_quote=False):
    row = claim(subject, f'{subject} uses partners.', cid,
                'Unwritten quote.' if bad_quote else f'{subject} uses partners.',
                source_requirement_id=f'ob_{index:03d}:req_001')
    return SemanticCalculationProgram.model_validate({'narrative_bindings': [
        {'obligation_id': f'ob_{index:03d}', 'claims': [row]}]})


class PlannerRequirementTransportTests(unittest.TestCase):
    def plan(self, query, rows, *, rationale='', state=None):
        model = RequirementPlannerOutput.model_validate({'topic': 'routes', 'obligations': rows, 'rationale': rationale})
        before = deepcopy(model.model_dump())
        llm = _StructuredQueueLLM(model)
        state = deepcopy(state or request(query))
        initial = deepcopy(state)
        state['requirements'] = agent_for(llm)._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(model.model_dump(), before)
        self.assertEqual({k: v for k, v in state.items() if k != 'requirements'}, initial)
        self.assertEqual(llm.models, ['RequirementPlannerOutput'])
        self.assertEqual(len(llm.prompts), 1)
        return state, llm

    def test_original_query_not_routing_summary_reaches_planner_for_each_presentation(self):
        query = 'Operating description: distinguish Aspen Unit from Aspen Group as a whole.\n\tState what cannot be determined.'
        for intent, form in (('business_overview', 'paragraph'), ('qa', 'table'), ('comparison', 'mixed')):
            with self.subTest(intent=intent, form=form):
                state, llm = self.plan(query, [owner('Aspen Unit', query)], state=request(query, intent=intent, form=form))
                text = llm.prompts[0].to_messages()[0].content
                self.assertIn('질문:\n' + query + '\n', text)
                self.assertIn(query, state['requirements']['retrieval_queries'])
                self.assertEqual(state['requirements']['active_subtask']['query'], query)
                self.assertTrue(state['requirements']['semantic_plan']['program_required'])

    def test_qualifiers_survive_planning_retrieval_and_compilation_projections_without_truncation(self):
        for subject, group, limits in (
            ('Aspen Unit', 'Aspen Group as a whole', 'state what the source cannot establish'),
            ('오로라 사업부', '오로라 그룹 전체', '원문만으로 확정할 수 없는 범위를 밝혀라'),
        ):
            with self.subTest(subject=subject):
                qualifier = f'{subject}; distinguish {group}; {limits}'
                label = 'Describe the source relationship. ' * 35 + qualifier
                query = 'From Operating description: ' + label
                raw = owner(subject, label)
                state, _ = self.plan(query, [raw])
                planned = state['requirements']['answer_obligations'][0]
                self.assertEqual(planned['label'], label)
                self.assertEqual(planned['evidence_requirements'][0]['label'], label)
                self.assertEqual(planned['semantic_target']['local_subjects'], [subject])
                self.assertEqual(planned['scope']['company'], 'Issuer')
                self.assertEqual(planned['source_sections'], raw['source_sections'])
                self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
                state['candidates'] = {'semantic_candidate_catalog': [evidence(subject, 'note')], 'semantic_source_candidates': []}
                before = deepcopy(state)
                for projected in (retrieval_phase_input(state), compilation_phase_input(state)):
                    self.assertEqual(projected['query'], query)
                    self.assertEqual(projected['answer_obligations'], [planned])
                self.assertEqual(state, before)

    def test_source_defined_group_materializes_one_complete_requirement_without_inventing_members(self):
        label = 'Summarize source-defined members for Aspen Group as a whole, distinguish units and state uncertainty.'
        state, _ = self.plan('Operating description: ' + label, [owner('Aspen Group', label, source_group=True)])
        planned, = state['requirements']['answer_obligations']
        requirement, = planned['evidence_requirements']
        for key in ('label', 'scope', 'semantic_target', 'source_sections', 'retrieval_hints', 'concept_hints'):
            self.assertEqual(requirement[key], planned[key])
        self.assertTrue(requirement['required'])
        self.assertEqual(requirement['requirement_id'], 'ob_001:req_001')
        self.assertEqual(planned['evidence_mode'], 'source_defined_group')

    def test_islands_and_retry_preserve_targeted_requirements_and_the_original_question(self):
        labels = [f'Describe {subject}; distinguish the wider group and retain uncertainty.' for subject in ('Aspen', 'Birch')]
        query = 'Operating description: ' + ' '.join(labels)
        rows = [owner(subject, label, key=subject) for subject, label in zip(('Aspen', 'Birch'), labels)]
        planner = RequirementPlannerOutput.model_validate({'obligations': rows})
        accepted = program(1, 'Aspen', 'note-a')
        llm = _StructuredQueueLLM(planner, accepted, program(2, 'Birch', 'note-b', bad_quote=True), program(2, 'Birch', 'note-b'))
        agent = agent_for(llm)
        state = request(query)
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        state['candidates'] = {'semantic_source_candidates': [], 'semantic_candidate_catalog': [
            evidence('Aspen', 'note-a'), evidence('Birch', 'note-b')]}
        before = deepcopy(state)
        compiled = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        self.assertEqual(len(llm.prompts), 4)
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        for prompt, index in zip(llm.prompts[1:], (0, 1, 1)):
            self.assertIn('원본 질문:\n' + query + '\n', prompt.to_messages()[0].content)
            self.assertEqual(prompt_json(prompt, 'Answer obligations:'), [state['requirements']['answer_obligations'][index]])
            self.assertEqual(prompt_json(prompt, 'Compilation scope:')['active_obligation_ids'], [f'ob_{index + 1:03d}'])
        self.assertEqual(json.dumps(compiled['semantic_program']['narrative_bindings'][0], sort_keys=True),
                         json.dumps(accepted.model_dump()['narrative_bindings'][0], sort_keys=True))
        self.assertEqual(state, before)

    def test_rationale_is_diagnostic_not_a_replacement_for_required_output_fields(self):
        detail = 'Distinguish the whole group and state attribution uncertainty.'
        query = 'Operating description: describe Aspen routes. ' + detail
        state, _ = self.plan(query, [owner('Aspen', 'Describe routes.')], rationale=detail)
        self.assertIn(detail, state['requirements']['semantic_plan']['planner_notes'])
        self.assertNotIn(detail, json.dumps(state['requirements']['answer_obligations']))
        self.assertEqual(state['requirements']['active_subtask']['query'], query)

    def test_negative_control_ready_does_not_prove_unplanned_question_qualifiers_were_answered(self):
        # Deliberately incomplete authored planner/compiler outputs: this records
        # the open semantic limit, not an expected good answer or an acceptance oracle.
        query = 'Operating description: describe Aspen routes, distinguish the entire group, and disclose attribution uncertainty.'
        model = RequirementPlannerOutput.model_validate({'obligations': [owner('Aspen', 'Describe routes.')]})
        llm = _StructuredQueueLLM(model, program(1, 'Aspen', 'note'))
        agent = agent_for(llm)
        agent._classify_query = Mock(return_value={'query_type': 'business_overview', 'intent': 'business_overview'})
        agent._extract_entities = Mock(return_value={'companies': ['Issuer'], 'years': [2042], 'topic': 'routes'})
        agent._retrieve = Mock(return_value={'retrieved_docs': [], 'seed_retrieved_docs': []})
        agent._expand_via_structure_graph = Mock(return_value={'retrieved_docs': []})
        rows = [evidence('Aspen', 'note')]
        agent._semantic_source_candidates_for_state = Mock(return_value=rows)
        agent._semantic_candidate_catalog_for_state = Mock(return_value=rows)
        agent._format_citations = Mock(return_value={'citations': []})
        state = agent._build_graph().invoke(agent._initial_state(query, {'company': 'Issuer', 'year': 2042}))
        self.assertEqual(len(llm.prompts), 2)
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'ok')
        self.assertIn('Aspen uses partners.', answer['answer'])
        self.assertNotIn('uncertainty', answer['answer'])
        self.assertNotIn('group', answer['answer'])
        self.assertIn(query, llm.prompts[1].to_messages()[0].content)


if __name__ == '__main__':
    unittest.main()
