"""Anonymous request/source coverage controls; authored meanings, no model score."""
from copy import deepcopy
import json
import unittest

from jsonschema import Draft202012Validator, ValidationError as SchemaError
from pydantic import ValidationError

from src.agent.financial_calculation_execution import source_candidate_applicability
from src.agent.financial_compiler_presentation import project_output_responsibility_context
from src.agent.financial_graph import compilation_phase_input
from src.agent.financial_graph_models import AnswerObligationScope, RequirementPlannerOutput
from src.agent.financial_measurement_periods import period_contract_error, source_date_shape
from src.utils.openai_structured import strict_openai_schema
import tests.test_structured_measurement_period as fixtures

cell, owner, period = fixtures.cell, fixtures.owner, fixtures.period


class MeasurementPeriodCoverageTests(unittest.TestCase):
    setUp = fixtures.StructuredMeasurementPeriodTests.setUp
    plan = fixtures.StructuredMeasurementPeriodTests.plan
    finish = fixtures.StructuredMeasurementPeriodTests.finish

    def period_state(self, candidate, spec):
        return source_candidate_applicability(candidate, owner('requested period', spec))['field_states']['period']

    def test_historical_years_do_not_silently_accept_finer_source_periods(self):
        for spec in (period('year', year=2042), period('relative_year', anchor_year=2043, year_offset=-1)):
            for label in ('2042-01-01 to 2042-03-31', '2042-03-31', '2042 Q1', '2042년 3월'):
                with self.subTest(spec=spec, label=label):
                    self.assertEqual(self.period_state(cell(label), spec), 'unknown')
            self.assertEqual(self.period_state(cell('2042'), spec), 'match')
        legacy = owner('2042')
        self.assertEqual(source_candidate_applicability(cell('2042 Q1'), legacy)['field_states']['period'], 'unknown')

    def test_whole_year_annual_sources_execute_for_absolute_and_relative_requests(self):
        for spec in (period('year', year=2042, coverage='whole_year'),
                     period('relative_year', anchor_year=2043, year_offset=-1, coverage='whole_year')):
            agent, state, llm = self.plan([owner('complete requested year', spec)])
            answer = self.finish(agent, state, llm, [cell('2042')])
            self.assertEqual(answer['structured_result']['status'], 'ok')
            self.assertIn('whole_year', str(llm.prompts[1]))
            self.assertEqual(answer['resolved_calculation_trace']['calculation_operands'][0]['value_year'], 2042)

    def test_whole_year_never_invents_fiscal_dates_from_source_geometry(self):
        spec = period('year', year=2042, coverage='whole_year')
        for label in ('2042-01-01 to 2042-03-31', '2042-12-31',
                      '2042-01-01 to 2042-12-31', '2041-07-01 to 2042-06-30'):
            with self.subTest(label=label):
                self.assertEqual(self.period_state(cell(label), spec), 'unknown')
        agent, state, llm = self.plan([owner('whole year', spec)])
        answer = self.finish(agent, state, llm, [cell('2042-01-01 to 2042-03-31', value=31)])
        self.assertNotEqual(answer['structured_result']['status'], 'ok')
        self.assertEqual(answer['resolved_calculation_trace']['calculation_result']['outputs'], [])

    def test_partial_period_markers_are_not_erased_by_year_projection(self):
        for label in ('2042 Q1', '2042Q4', 'Q2 2042', '2042 H1', '2042년 1분기', '2042년 상반기',
                      '2042년 3월', '2042년 12월말', '2042-03', 'March 2042', '2042 YTD', '2042 9 months'):
            with self.subTest(label=label):
                self.assertEqual(self.period_state(cell(label), period('year', year=2042, coverage='whole_year')), 'unknown')
                self.assertEqual(self.period_state(cell(label), period('year', year=2042, coverage='within_year')), 'match')

    def test_within_year_dates_and_intervals_execute_and_keep_source_axes(self):
        spec = period('year', year=2042, coverage='within_year')
        for label in ('2042-03-31', '2042-01-01 to 2042-03-31', '2042-01-01 to 2042-12-31', '2042 Q1'):
            agent, state, llm = self.plan([owner('any requested measurement inside the year', spec)])
            answer = self.finish(agent, state, llm, [cell(label)])
            self.assertEqual(answer['structured_result']['status'], 'ok')
            operand = answer['resolved_calculation_trace']['calculation_operands'][0]
            self.assertEqual(operand['source_period_surface'], label)
            self.assertEqual(state['candidates']['semantic_candidate_catalog'][0]['column_headers'], [label])

    def test_within_year_checks_both_endpoints_despite_projected_year(self):
        spec = period('relative_year', anchor_year=2043, year_offset=-1, coverage='within_year')
        for label in ('2041-12-01 to 2042-03-31', '2042-10-01 to 2043-03-31', '2041-12-31'):
            candidate = cell(label)
            candidate.update(period='2042', value_year=2042, period_source='source_context_binding')
            self.assertEqual(self.period_state(candidate, spec), 'conflict')

    def test_explicit_foreign_year_remains_a_conflict_when_coverage_is_unknown(self):
        for spec in (period('year', year=2041), period('year', year=2041, coverage='whole_year'),
                     period('year', year=2041, coverage='within_year')):
            for label in ('2042-03-31', '2042-01-01 to 2042-03-31', '2042 Q1'):
                self.assertEqual(self.period_state(cell(label), spec), 'conflict')

    def test_ambiguous_invalid_or_separate_axes_stay_unresolved(self):
        for headers in (['2042-01-01', '2042-03-31'], ['2042-02-30'], ['2042-01-01 to 03-31']):
            candidate = cell('2042')
            candidate.update(column_headers=headers, source_period_surface=' / '.join(headers))
            self.assertEqual(source_date_shape(candidate), ('unknown',))
            self.assertEqual(self.period_state(candidate, period('year', year=2042, coverage='within_year')), 'unknown')

    def test_partial_axis_is_seen_alongside_separate_year_axis(self):
        candidate = cell('2042')
        candidate['column_headers'].append('Q1')
        before = deepcopy(candidate)
        self.assertEqual(self.period_state(candidate, period('year', year=2042, coverage='whole_year')), 'unknown')
        self.assertEqual(candidate, before)

    def test_nonperiod_tokens_do_not_become_partial_period_rules(self):
        spec = period('year', year=2042, coverage='whole_year')
        for label in ('H1N1', 'Q10', 'H12', 'mayhem', 'quarterly_count'):
            candidate = cell('2042')
            candidate['column_headers'].append(label)
            self.assertEqual(self.period_state(candidate, spec), 'match')

    def test_context_year_and_unknown_waiver_cannot_erase_finer_period(self):
        candidate = cell('2042-01-01 to 2042-03-31')
        for source in ('source_context_binding', 'source_column_period_binding', 'explicit_period', 'fiscal_period'):
            projected = dict(candidate, period='2042', value_year=2042, period_source=source)
            self.assertEqual(self.period_state(projected, period('year', year=2042, coverage='whole_year')), 'unknown')
        agent, state, llm = self.plan([owner('whole year', period('year', year=2042, coverage='whole_year'))])
        with self.assertRaises(ValidationError):
            fixtures.SemanticCalculationProgram(direct_bindings=[dict(obligation_id='ob_001',
                candidate_id=candidate['candidate_id'], applicable_unknown_fields=['period'])])
        answer = self.finish(agent, state, llm, [candidate])
        self.assertNotEqual(answer['structured_result']['status'], 'ok')

    def test_historical_serialization_keeps_coverage_absent(self):
        for spec in (period('year', year=2042), period('relative_year', anchor_year=2043, year_offset=-1)):
            model = AnswerObligationScope(measurement_period=spec)
            self.assertEqual(model.model_dump()['measurement_period'], spec)
            _, state, _ = self.plan([owner('old year', spec)])
            self.assertEqual(state['requirements']['answer_obligations'][0]['scope']['measurement_period'], spec)

    def test_invalid_coverage_is_rejected_in_models_and_plain_mappings(self):
        for spec in [period('year', year=2042, coverage=value) for value in (None, '', 'annual', True, [])] + [
                period('date', date='2042-03-31', coverage='whole_year'),
                period('unspecified', coverage='within_year')]:
            with self.subTest(spec=spec):
                self.assertTrue(period_contract_error(spec))
                with self.assertRaises(ValidationError):
                    AnswerObligationScope(measurement_period=spec)

    def test_generation_requires_explicit_nonnull_coverage_for_both_year_kinds(self):
        from tests.planner_period_wire_test_support import declared_period
        schema = strict_openai_schema(RequirementPlannerOutput)
        validator = Draft202012Validator(schema)
        for kind, args, reference, offset in (
                ('year', dict(year=2042), 2042, 0),
                ('relative_year', dict(anchor_year=2043, year_offset=-1), 2043, -1)):
            shape = schema['$defs']['PlannerMeasurementPeriod']
            self.assertIn('coverage', shape['required'])
            choices = shape['properties']['coverage']['anyOf']
            self.assertEqual(set(next(c['enum'] for c in choices if 'enum' in c)), {'whole_year', 'within_year'})
            for coverage in ('whole_year', 'within_year'):
                raw = RequirementPlannerOutput(obligations=[owner('period', period(kind, **args, coverage=coverage))]).model_dump()
                raw['obligations'][0]['scope']['measurement_period'] = declared_period(
                    'year', reference_year=reference, year_offset=offset, coverage=coverage)
                validator.validate(raw)
                self.assertEqual(RequirementPlannerOutput.model_validate(raw).obligations[0].scope.measurement_period.coverage, coverage)
                for invalid in ('missing', None):
                    changed = deepcopy(raw)
                    target = changed['obligations'][0]['scope']['measurement_period']
                    if invalid == 'missing':
                        target.pop('coverage')
                    else:
                        target['coverage'] = invalid
                    if invalid == 'missing':
                        with self.assertRaises(SchemaError):
                            validator.validate(changed)
                    # The uniform schema permits inactive nulls. The typed
                    # cross-field guard rejects a null for active year coverage.
                    with self.assertRaises(ValidationError):
                        RequirementPlannerOutput.model_validate(changed)

    def test_coverage_inherits_only_with_owned_parent_period_and_reaches_compiler(self):
        spec = period('year', year=2042, coverage='whole_year')
        child = dict(label='quantity', scope=dict(period=''))
        own_spec = period('year', year=2042, coverage='within_year')
        independent = dict(label='independent quantity', scope=dict(measurement_period=own_spec))
        agent, state, llm = self.plan([owner('annual quantity', spec, kind='derived_value', children=[child, independent])])
        output = state['requirements']['answer_obligations'][0]
        self.assertEqual(output['evidence_requirements'][0]['scope']['measurement_period'], spec)
        context = project_output_responsibility_context(state['request']['query'], [output])
        self.assertEqual(context['outputs'][0]['scope']['measurement_period'], spec)
        self.assertIsNot(output['scope']['measurement_period'], output['evidence_requirements'][0]['scope']['measurement_period'])
        self.assertEqual(output['evidence_requirements'][1]['scope']['measurement_period'], own_spec)

    def test_unowned_coverage_interpretation_blocks_planner_requirements(self):
        spec = period('year', year=2042, coverage='whole_year')
        spec['request_unit_ids'] = ['request_002']
        _, state, _ = self.plan([owner('whole year', spec)], query='Return the quantity. Use the complete year.')
        errors = state['requirements']['semantic_plan']['requirement_errors']
        self.assertIn('unowned_measurement_period_request', [row['code'] for row in errors])

    def test_invalid_mapping_stops_before_compiler(self):
        agent, state, llm = self.plan([owner('whole year', period('year', year=2042, coverage='whole_year'))])
        state['requirements']['answer_obligations'][0]['scope']['measurement_period']['coverage'] = 'invented'
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=[cell('2042')])
        result = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        self.assertIn('invalid_measurement_period', str(result))
        self.assertEqual(len(llm.prompts), 1)

    def test_v2_binds_coverage_and_rejects_post_compile_tampering(self):
        agent, state, llm = self.plan([owner('whole year', period('year', year=2042, coverage='whole_year'))])
        self.finish(agent, state, llm, [cell('2042')])
        state['requirements']['answer_obligations'][0]['scope']['measurement_period']['coverage'] = 'within_year'
        self.assertIn('execution_content_mismatch', json.dumps(agent._execute_numeric_phase(state)))

    def test_explicit_unspecified_stays_unrestricted(self):
        agent, state, llm = self.plan([owner('', period('unspecified'))])
        answer = self.finish(agent, state, llm, [cell('2042-01-01 to 2042-03-31')])
        self.assertEqual(answer['structured_result']['status'], 'ok')

    def test_well_formed_but_wrong_coverage_remains_a_semantic_negative(self):
        agent, state, llm = self.plan([owner('authored wrong interpretation', period('year', year=2042, coverage='within_year'))],
                                      query='Return the amount for the whole year 2042.')
        answer = self.finish(agent, state, llm, [cell('2042-01-01 to 2042-03-31')])
        self.assertEqual(answer['structured_result']['status'], 'ok')


if __name__ == '__main__':
    unittest.main()
