"""Authored period decisions through Planner/Compiler; not model accuracy."""
from copy import deepcopy
import unittest

from jsonschema import Draft202012Validator

from src.agent.financial_calculation_execution import semantic_candidate_applicability
from src.agent.financial_graph import compilation_phase_input, planning_phase_input, retrieval_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_request_units import build_request_units, project_request_units
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate
from tests.test_narrative_retry_context import prompt_json
from tests.test_planner_requirement_transport import agent_for, request


def owner(period='', *, kind='direct_value', children=None):
    return dict(kind=kind, label='quantity', scope=dict(period=period),
                evidence_requirements=list(children or []))


def cell(period, identifier='value', value=17):
    return dict(_candidate(identifier, value, period=period), company='Issuer',
                document_company='Issuer', year=2042, source_anchor='[Issuer | 2042 | quantities]')


class PlannerMeasurementPeriodTests(unittest.TestCase):
    def plan(self, query, rows, *, report_year=2042, responses=()):
        rows = deepcopy(rows)
        units = [u.request_unit_id for u in build_request_units(query)]
        for row in rows:
            row['request_unit_ids'] = units
        model = RequirementPlannerOutput.model_validate(dict(obligations=rows))
        original = deepcopy(model.model_dump())
        llm = _StructuredQueueLLM(model, *responses)
        agent = agent_for(llm)
        state = request(query, intent='numeric_fact')
        state['request']['report_scope'].pop('year')
        if report_year is not None:
            state['request']['report_scope']['year'] = report_year
        original_request = deepcopy(state['request'])
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(state['request'], original_request)
        self.assertEqual(model.model_dump(), original)
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
        self.assertEqual(llm.models, ['RequirementPlannerOutput'])
        self.assertEqual(len(llm.prompts), 1)
        self.assertEqual(prompt_json(llm.prompts[0], 'Request units:'),
                         project_request_units(build_request_units(query)))
        return agent, state, llm

    def finish(self, agent, state, llm, catalog, *, calls):
        before = deepcopy((state['request'], state['requirements'], catalog))
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=deepcopy(catalog))
        state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual((state['request'], state['requirements'], state['candidates']['semantic_candidate_catalog']), before)
        self.assertEqual(llm.responses, [])
        self.assertEqual(llm.models, ['RequirementPlannerOutput'] + ['CompilerResponseV2'] * calls)
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        return state['final_result']['agent_answer']

    def test_blank_numeric_period_does_not_become_report_year(self):
        for kind in ('direct_value', 'derived_value'):
            for period in ('', ' \t '):
                with self.subTest(kind=kind, period=period):
                    _, state, _ = self.plan('Return the quantity.', [owner(period, kind=kind)])
                    output, = state['requirements']['answer_obligations']
                    self.assertEqual(output['scope']['period'], '')
                    self.assertEqual(state['requirements']['years'], [2042])

    def test_blank_numeric_parent_and_child_do_not_invent_periods(self):
        _, state, _ = self.plan('Calculate the result.', [owner(kind='derived_value',
            children=[dict(label='input', scope=dict(period=''))])])
        output, = state['requirements']['answer_obligations']
        self.assertEqual(output['scope']['period'], '')
        self.assertEqual(output['evidence_requirements'][0]['scope']['period'], '')
        task, = state['requirements']['semantic_plan']['tasks']
        self.assertEqual(task['produces'][0]['period'], '')
        self.assertEqual(task['required_evidence'][0]['binding_policy']['period'], '')

    def test_report_year_changes_only_document_hints(self):
        for report_year in (None, 2037, 2042, 2048):
            with self.subTest(report_year=report_year):
                _, state, _ = self.plan('Return the quantity.', [owner()], report_year=report_year)
                self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['period'], '')
                self.assertEqual(state['requirements']['years'], [] if report_year is None else [report_year])

    def test_explicit_full_requested_period_survives_a_different_report_year(self):
        period = '2043년 1월 1일부터 2043년 12월 31일까지'
        query = f'선택한 2042년 보고서만 사용해서 {period}의 수량을 알려 줘.'
        _, state, _ = self.plan(query, [owner(period)])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['period'], period)
        self.assertEqual(state['requirements']['years'], [2042])
        self.assertEqual(state['requirements']['active_subtask']['query'], query)

    def test_explicit_same_report_period_is_a_model_choice_not_a_default(self):
        _, state, _ = self.plan('Return the quantity for the selected report year.', [owner('2042')])
        self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['period'], '2042')

    def test_relative_and_noncalendar_periods_are_not_rewritten(self):
        for period in ('전기', 'previous reporting period', '2041-07-01 to 2042-06-30', 'Q2 2041'):
            with self.subTest(period=period):
                _, state, _ = self.plan(f'Return the quantity for {period}.', [owner(period)])
                self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['period'], period)

    def test_multiple_requested_periods_restrict_their_own_outputs(self):
        _, state, _ = self.plan('Return the quantities for 2040 and 2041.', [owner('2040'), owner('2041')])
        outputs = state['requirements']['answer_obligations']
        self.assertEqual([o['scope']['period'] for o in outputs], ['2040', '2041'])
        for output, period in zip(outputs, ('2040', '2041')):
            self.assertEqual(semantic_candidate_applicability(cell(period), output)['state'], 'compatible')
            other = '2041' if period == '2040' else '2040'
            self.assertEqual(semantic_candidate_applicability(cell(other), output)['state'], 'explicit_conflict')

    def test_comparison_children_keep_distinct_periods_and_calculate(self):
        query = 'Subtract the 2040 quantity from the 2041 quantity.'
        rows = [owner(kind='derived_value', children=[dict(label='reference', scope=dict(period='2040')),
                                                      dict(label='target', scope=dict(period='2041'))])]
        program = SemanticCalculationProgram.model_validate(dict(expressions=[dict(
            obligation_id='ob_001', formula='target - reference', comparison_request_unit_id='request_001',
            source_display_candidate_id=None, source_display_reason='The request asks for a calculation.',
            variable_bindings=[dict(variable='reference', source_id='earlier', source_requirement_id='ob_001:req_001'),
                               dict(variable='target', source_id='later', source_requirement_id='ob_001:req_002')])]))
        agent, state, llm = self.plan(query, rows, responses=[program])
        output, = state['requirements']['answer_obligations']
        self.assertEqual(output['scope']['period'], '')
        self.assertEqual([r['scope']['period'] for r in output['evidence_requirements']], ['2040', '2041'])
        answer = self.finish(agent, state, llm, [cell('2040', 'earlier', 17), cell('2041', 'later', 23)], calls=1)
        self.assertEqual(answer['structured_result']['status'], 'ok')
        result, = answer['resolved_calculation_trace']['calculation_result']['outputs']
        self.assertEqual(result['normalized_value'], 6)

    def test_explicit_parent_inheritance_and_explicit_child_override_remain(self):
        _, state, _ = self.plan('Calculate the requested result for 2041.', [owner('2041', kind='derived_value',
            children=[dict(label='same period'), dict(label='prior', scope=dict(period='2040'))])])
        output, = state['requirements']['answer_obligations']
        self.assertEqual(output['scope']['period'], '2041')
        self.assertEqual([r['scope']['period'] for r in output['evidence_requirements']], ['2041', '2040'])

    def test_no_period_request_can_use_a_source_value_older_than_the_report(self):
        program = SemanticCalculationProgram(direct_bindings=[dict(obligation_id='ob_001', candidate_id='value')])
        agent, state, llm = self.plan('Return the quantity as reported.', [owner()], responses=[program])
        answer = self.finish(agent, state, llm, [cell('2041')], calls=1)
        self.assertEqual(answer['structured_result']['status'], 'ok')
        result, = answer['resolved_calculation_trace']['calculation_result']['outputs']
        self.assertEqual(result['normalized_value'], 17)
        compiled_owner, = prompt_json(llm.prompts[1], 'Answer obligations:')
        self.assertEqual(compiled_owner['scope']['period'], '')

    def test_explicit_foreign_period_remains_unanswered_without_compiler_call(self):
        agent, state, llm = self.plan('Return the actual 2043 quantity using only the selected 2042 report.',
                                      [owner('2043')])
        answer = self.finish(agent, state, llm, [cell('2042')], calls=0)
        self.assertEqual(answer['structured_result']['status'], 'incomplete')
        self.assertEqual(answer['resolved_calculation_trace']['calculation_result']['outputs'], [])
        self.assertIn('2043', answer['answer'])

    def test_phase_projections_keep_request_document_and_measurement_scopes_separate(self):
        _, state, _ = self.plan('Read the 2040 quantity from the selected 2042 report.', [owner('2040')])
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=[])
        before = deepcopy(state)
        for projection in (retrieval_phase_input(state), compilation_phase_input(state)):
            self.assertEqual(projection['query'], state['request']['query'])
            self.assertEqual(projection['report_scope'], state['request']['report_scope'])
            self.assertEqual(projection['answer_obligations'], state['requirements']['answer_obligations'])
        self.assertEqual(retrieval_phase_input(state)['years'], [2042])
        self.assertEqual(state, before)

    def test_negative_control_wrong_or_omitted_model_period_is_not_semantically_certified(self):
        # These deliberately wrong choices remain source-valid. They must never
        # be reported as semantic passes, even after removing the code default.
        for period in ('', '2042'):
            with self.subTest(period=period):
                program = SemanticCalculationProgram(direct_bindings=[dict(obligation_id='ob_001', candidate_id='value')])
                query = 'Return the actual 2043 quantity using only the selected 2042 report.'
                agent, state, llm = self.plan(query, [owner(period)], responses=[program])
                answer = self.finish(agent, state, llm, [cell('2042')], calls=1)
                self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['period'], period)
                self.assertEqual(answer['structured_result']['status'], 'ok')
                self.assertIn(query, llm.prompts[1].to_messages()[0].content)

    def test_generation_retains_open_period_strings_and_declares_source_separation(self):
        schema = RequirementPlannerOutput.model_json_schema()
        field = schema['$defs']['AnswerObligationScope']['properties']['period']
        self.assertEqual(field['type'], 'string')
        self.assertNotIn('enum', field)
        self.assertIn('measurement period', field.get('description', ''))
        self.assertIn('report_scope.year', field.get('description', ''))
        for period in ('', '2041', 'previous reporting period'):
            raw = dict(obligations=[dict(owner(period), request_unit_ids=['request_001'])])
            Draft202012Validator(schema).validate(raw)
        _, _, llm = self.plan('Return the quantity.', [owner()])
        self.assertIn('측정 기간의 기본값이 아닙니다', llm.prompts[0].to_messages()[0].content)


if __name__ == '__main__':
    unittest.main()
