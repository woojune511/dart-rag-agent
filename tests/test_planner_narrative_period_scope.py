"""Filing identity stays separate from unspecified narrative measurement time."""
from copy import deepcopy
import unittest

from src.agent.financial_graph import planning_phase_input, retrieval_phase_input, compilation_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_planner_requirement_transport import agent_for


class PlannerNarrativePeriodScopeTests(unittest.TestCase):
    def plan(self, *, kind='narrative', period='', child_period=None,
             source_group=False, report_year=2047):
        query = 'From Methods: describe the requested source contents.'
        scope = dict(company='Birch', period=period)
        owner = dict(kind=kind, label='requested contents', request_unit_ids=['request_001'],
                     scope=scope, source_sections=['Methods'])
        if source_group:
            owner['evidence_mode'] = 'source_defined_group'
        elif child_period is not None:
            owner['evidence_requirements'] = [dict(label='support', scope=dict(period=child_period))]
        model = RequirementPlannerOutput.model_validate(dict(obligations=[owner]))
        original = deepcopy(model.model_dump())
        llm = _StructuredQueueLLM(model)
        report_scope = dict(company='Birch', rcept_no='anonymous-filing',
                            **({'year': report_year} if report_year is not None else {}))
        state = dict(request=dict(query=query, report_scope=report_scope),
                     routing=dict(intent='qa', query_type='qa', topic='source contents'))
        before = deepcopy(state)
        state['requirements'] = agent_for(llm)._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(state['request'], before['request'])
        self.assertEqual(state['routing'], before['routing'])
        self.assertEqual(model.model_dump(), original)
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
        self.assertEqual(llm.models, ['RequirementPlannerOutput'])
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['company'], 'Birch')
        self.assertEqual(state['requirements']['answer_obligations'][0]['source_sections'], ['Methods'])
        return state

    def test_unspecified_narrative_period_is_not_filled_from_filing_year(self):
        state = self.plan()
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['period'], '')
        self.assertEqual(state['requirements']['years'], [2047])

    def test_blank_narrative_child_does_not_reintroduce_filing_year(self):
        owner = self.plan(child_period='')['requirements']['answer_obligations'][0]
        self.assertEqual(owner['scope']['period'], '')
        self.assertEqual(owner['evidence_requirements'][0]['scope']['period'], '')

    def test_explicit_narrative_period_is_preserved(self):
        owner = self.plan(period='2045')['requirements']['answer_obligations'][0]
        self.assertEqual(owner['scope']['period'], '2045')

    def test_explicit_parent_period_still_governs_blank_child(self):
        owner = self.plan(period='2045', child_period='')['requirements']['answer_obligations'][0]
        self.assertEqual(owner['evidence_requirements'][0]['scope']['period'], '2045')

    def test_explicit_child_period_is_not_replaced_by_parent_or_filing(self):
        owner = self.plan(period='2045', child_period='2044')['requirements']['answer_obligations'][0]
        self.assertEqual(owner['evidence_requirements'][0]['scope']['period'], '2044')

    def test_source_defined_group_keeps_the_parent_scope(self):
        for period in ('', '2045'):
            with self.subTest(period=period):
                owner = self.plan(period=period, source_group=True)['requirements']['answer_obligations'][0]
                self.assertEqual(owner['scope']['period'], period)
                self.assertEqual(owner['evidence_requirements'][0]['scope'], owner['scope'])

    def test_numeric_unspecified_period_and_child_are_not_filled_from_filing_year(self):
        for kind, child in [('direct_value', None), ('derived_value', '')]:
            with self.subTest(kind=kind):
                owner = self.plan(kind=kind, child_period=child)['requirements']['answer_obligations'][0]
                self.assertEqual(owner['scope']['period'], '')
                if child is not None:
                    self.assertEqual(owner['evidence_requirements'][0]['scope']['period'], '')

    def test_no_filing_year_does_not_invent_a_period(self):
        for kind in ('narrative', 'direct_value'):
            with self.subTest(kind=kind):
                owner = self.plan(kind=kind, report_year=None)['requirements']['answer_obligations'][0]
                self.assertEqual(owner['scope']['period'], '')

    def test_retrieval_and_compiler_preserve_request_report_and_empty_scope(self):
        state = self.plan(child_period='')
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=[])
        before = deepcopy(state)
        for projection in (retrieval_phase_input(state), compilation_phase_input(state)):
            self.assertEqual(projection['query'], state['request']['query'])
            self.assertEqual(projection['report_scope'], state['request']['report_scope'])
            self.assertEqual(projection['answer_obligations'], state['requirements']['answer_obligations'])
        self.assertEqual(state, before)


if __name__ == '__main__':
    unittest.main()
