"""Authored scope interpretations and deterministic transport; no model score."""
from copy import deepcopy
from contextlib import ExitStack
import socket
import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from src.agent.financial_graph import planning_phase_input, retrieval_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput
from src.agent.financial_request_units import build_request_units
from src.agent.financial_calculation_execution import source_candidate_applicability
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_planner_requirement_transport import agent_for
from tests.test_structured_measurement_period import cell, owner


def planned(query, scopes, *, children=None, report=None):
    refs = [unit.request_unit_id for unit in build_request_units(query)]
    rows = []
    for i, scope in enumerate(scopes):
        row = dict(obligation_id=f'raw-{i}', kind='direct_value', label='reported amount',
                   request_unit_ids=refs, scope=dict(consolidation_scope=scope))
        if children is not None:
            row.update(kind='derived_value', evidence_requirements=[
                dict(requirement_id=f'input-{i}-{j}', label='input amount',
                     scope=dict(consolidation_scope=value)) for j, value in enumerate(children[i])])
        rows.append(row)
    model = RequirementPlannerOutput.model_validate(dict(obligations=rows))
    before = deepcopy(model.model_dump())
    llm = _StructuredQueueLLM(model)
    agent = agent_for(llm)
    state = dict(request=dict(query=query, report_scope=report or {}),
                 routing=dict(intent='numeric_fact', query_type='numeric_fact', topic='reported amount',
                              format_preference='table'))
    state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
    assert model.model_dump() == before
    assert len(llm.prompts) == 1
    return agent, state


def scores(agent, state):
    docs = [(Document(page_content='reported amount 10', metadata={
        'consolidation_scope': scope, 'block_type': 'table'}), 1.0)
        for scope in ('consolidated', 'separate')]
    before = deepcopy((docs, state))
    agent._section_bias = lambda *_: 0.0
    # Isolate the scope preference; unrelated section and topic priors are not
    # evidence that a query actually requests either reporting basis.
    with ExitStack() as stack:
        for name, value in (('tokenize_terms', set()), ('_metric_terms_from_topic', set()),
                            ('_active_preferred_sections', []), ('_active_preferred_statement_types', [])):
            stack.enter_context(patch('src.agent.financial_retrieval_pipeline.' + name, return_value=value))
        ranked = agent._rerank_docs(docs, retrieval_phase_input(state))
    assert (docs, state) == before
    return {doc.metadata['consolidation_scope']: score for doc, score in ranked}


class PlannerConsolidationOwnershipTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')))
        self.enterContext(patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network forbidden')))

    def test_ordinary_words_do_not_create_scope(self):
        for query in ('값을 알려 줘. 별도의 날짜는 지정하지 마.',
                      '값과 설명을 연결해서 한 문장으로 답해 줘.',
                      '결과를 별도로 정리하고 근거에 연결해 줘.'):
            _, state = planned(query, ['unknown'])
            self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], 'unknown')

    def test_english_scope_interpretations_are_preserved(self):
        for scope, query in (('consolidated', 'Return the amount for the consolidated group.'),
                             ('separate', 'Return the amount for the standalone entity.')):
            _, state = planned(query, [scope])
            self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], scope)

    def test_unknown_is_not_repaired_from_a_single_query_marker(self):
        _, state = planned('연결 기준의 값을 알려 줘.', ['unknown'])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], 'unknown')

    def test_negated_scope_word_does_not_overwrite_interpretation(self):
        _, state = planned('별도 수치는 제외하고 그룹 전체의 값을 알려 줘.', ['consolidated'])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], 'consolidated')

    def test_wrong_well_formed_interpretation_remains_a_semantic_negative(self):
        _, state = planned('연결 기준의 값을 알려 줘.', ['separate'])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], 'separate')
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])

    def test_report_metadata_cannot_supply_request_scope(self):
        for scope in ('consolidated', 'separate'):
            _, state = planned('Return the amount.', ['unknown'], report={'consolidation': scope, 'consolidation_scope': scope})
            self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], 'unknown')

    def test_child_inherits_only_declared_parent_and_keeps_own_known_scope(self):
        _, state = planned('Return the requested calculation.', ['consolidated'], children=[['unknown', 'separate']])
        row, = state['requirements']['answer_obligations']
        self.assertEqual([child['scope']['consolidation_scope'] for child in row['evidence_requirements']],
                         ['consolidated', 'separate'])
        self.assertEqual(state['requirements']['active_subtask']['constraints']['consolidation_scope'], 'unknown')

    def test_task_scope_follows_source_inputs_not_a_calculation_output(self):
        _, state = planned('Return the requested calculation.', ['unknown'], children=[['separate', 'separate']])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['consolidation_scope'], 'unknown')
        self.assertEqual(state['requirements']['active_subtask']['constraints']['consolidation_scope'], 'separate')

    def test_ordinary_query_and_metadata_do_not_bias_ranking(self):
        for query in ('별도의 날짜 없이 값을 알려 줘.', '값과 근거를 연결해서 알려 줘.'):
            agent, state = planned(query, ['unknown'], report={'consolidation': 'consolidated'})
            values = scores(agent, state)
            self.assertEqual(values['consolidated'], values['separate'])

    def test_ranking_uses_declared_scope_without_query_keywords(self):
        for scope in ('consolidated', 'separate'):
            agent, state = planned('Return the amount on the requested basis.', [scope])
            values = scores(agent, state)
            other = 'separate' if scope == 'consolidated' else 'consolidated'
            self.assertAlmostEqual(values[scope] - values[other], 0.30)

    def test_mixed_or_unrestricted_owners_have_no_shared_ranking_preference(self):
        for declared in (['consolidated', 'separate'], ['consolidated', 'unknown']):
            agent, state = planned('연결 기준 값을 반환하고 별도 요청도 수행해 줘.', declared)
            values = scores(agent, state)
            self.assertEqual(values['consolidated'], values['separate'])

    def test_known_source_scope_conflicts_remain_conflicts(self):
        for scope in ('consolidated', 'separate'):
            obligation = owner('2042')
            obligation['scope']['consolidation_scope'] = scope
            candidate = cell('2042')
            candidate['consolidation_scope'] = 'separate' if scope == 'consolidated' else 'consolidated'
            self.assertEqual(source_candidate_applicability(candidate, obligation)['field_states']['consolidation_scope'], 'conflict')
