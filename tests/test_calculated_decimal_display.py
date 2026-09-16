"""Fixed decimal presentation from validated final rounding, not query parsing."""
from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation_rendering import render_value_with_unit
from tests.semantic_program_test_support import (
    _binding, _obligation, _requirement, _source_display_program_fixture, execute_compiled_fixture,
)
from tests.source_interpretation_fixture_support import execute_authored_fixture
from tests.test_compiler_display_intent import AuthoredDisplayLLM, fixture
from tests.test_semantic_expression_units import _inputs


class RoundedLLM(AuthoredDisplayLLM):
    def __init__(self, case, precision, mode, use_display):
        super().__init__(case, use_display=use_display)
        self.precision, self.mode = precision, mode

    def invoke(self, prompt):
        raw = super().invoke(prompt).model_dump()
        result = raw['outputs']['answer']['result']
        result['display_format'] = 'Show exactly two decimal places.'
        if self.mode != 'unrounded':
            args = [{'step': len(result['formula'])}]
            if self.mode != 'integer':
                args.append({'value': float(self.precision),
                    'request_unit_id': self.models[-1].__compiler_references__.ref('request_001'),
                    'interpretation': 'The requested final rounding precision.'})
            result['formula'].append({'operation': 'round', 'arguments': args})
            if self.mode == 'intermediate':
                result['formula'].append({'operation': 'add',
                    'arguments': [{'step': len(result['formula'])}, '1']})
        return self.models[-1].model_validate(raw)


def compile_case(*, precision=2, mode='final', use_display=False, initial='100', final='115.4'):
    case = fixture(initial=initial, final=final, reported='19.8000')
    question = f'Calculate the change and round the final result to {precision} decimal places.'
    if use_display:
        question = 'Report the source figure alongside the calculation: ' + question
    owner = _obligation('answer', 'derived_value', 'change', display_unit='%',
        evidence_requirements=[_requirement('initial', 'initial quantity'), _requirement('final', 'final quantity')])
    agent = object.__new__(FinancialAgent)
    agent.llm = RoundedLLM(case, precision, mode, use_display)
    agent.llm_routes, agent.llm_usage_callback = {}, None
    state = {'query': question, 'answer_obligations': [owner], 'include_debug_bundle': True,
        'semantic_candidate_catalog_prebuilt': True, 'semantic_source_candidates': case['catalog'],
        'semantic_candidate_catalog': case['catalog']}
    before = deepcopy(state)
    compiled = agent._compile_semantic_calculation_program(state)
    assert state == before
    return agent, state, compiled


class CalculatedDecimalDisplayTests(unittest.TestCase):
    def execute(self, **options):
        agent, state, compiled = compile_case(**options)
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertEqual(len(agent.llm.prompts), 1)
        self.assertEqual(compiled['semantic_program_retry_count'], 0)
        result = execute_compiled_fixture(agent, {**state, **compiled}, state['semantic_candidate_catalog'])
        self.assertEqual(result['task_artifact_trace']['integrity_status'], 'ok')
        aggregate = next(row['payload'] for row in result['artifacts'] if row['kind'] == 'aggregated_answer')
        self.assertEqual(aggregate['final_answer'], result['answer'])
        self.assertEqual(aggregate['structured_result'], result['structured_result'])
        return result, result['resolved_calculation_trace']['calculation_result']['outputs'][0]

    def test_final_request_precision_survives_wire_execution_answer_and_ledger(self):
        for precision, expected in ((0, '15%'), (1, '15.4%'), (2, '15.40%'), (3, '15.400%')):
            with self.subTest(precision=precision):
                result, output = self.execute(precision=precision)
                self.assertEqual(output['normalized_value'], round(15.4, precision))
                self.assertEqual(output['rendered_value'], expected)
                self.assertEqual(output['formula_rendered_value'], expected)
                self.assertEqual(output['answer_slot']['rendered_value'], expected)
                self.assertIn(expected, result['answer'])

    def test_signed_zero_and_small_final_values_keep_requested_places(self):
        for initial, final, precision, expected in (
            ('100', '84.6', 2, '-15.40%'), ('100', '100', 2, '0.00%'),
            ('100', '100.001', 4, '0.0010%'),
        ):
            with self.subTest(expected=expected):
                result, output = self.execute(initial=initial, final=final, precision=precision)
                self.assertEqual(output['rendered_value'], expected)
                self.assertIn(expected, result['answer'])

    def test_source_display_keeps_its_precision_separate_from_formula(self):
        result, output = self.execute(use_display=True)
        self.assertEqual(output['rendered_value'], '19.8000%')
        self.assertEqual(output['answer_slot']['rendered_value'], '19.8000%')
        self.assertEqual(output['formula_rendered_value'], '15.40%')
        self.assertEqual(output['calculated_value'], 15.4)
        self.assertTrue(output['source_stated_result_used'])
        self.assertIn('19.8000%', result['answer'])
        self.assertIn('15.40%', result['answer'])

    def test_unrounded_and_intermediate_rounds_do_not_inherit_display_precision(self):
        for mode, expected in (('unrounded', '15.4%'), ('intermediate', '16.4%'), ('integer', '15%')):
            with self.subTest(mode=mode):
                _, output = self.execute(mode=mode)
                self.assertEqual(output['rendered_value'], expected)

    def test_precision_converts_with_display_scale_without_changing_arithmetic(self):
        for precision, expected in ((-4, '0.10백만달러'), (0, '0.100000백만달러')):
            with self.subTest(precision=precision):
                inputs = _inputs(raw_unit='백만달러', display_unit='백만달러',
                    formula='round(A - B, precision)', request_inputs=[{
                        'variable': 'precision', 'value': float(precision), 'request_unit_id': 'request_001',
                        'source_text': 'Calculate the difference between the two inputs.',
                        'interpretation': 'Authored final rounding precision.',
                    }])
                before = deepcopy(inputs)
                execution = execute_authored_fixture(**inputs)
                self.assertEqual(execution['validation']['errors'], [])
                self.assertEqual(inputs, before)
                output = execution['outputs_by_obligation']['difference']
                self.assertEqual(output['calculated_value'], 100000)
                self.assertEqual(output['rendered_value'], expected)

    def test_unitless_and_currency_formatting_are_bounded_and_preserve_sign(self):
        for value, display, dimension, precision, expected in (
            (1200.5, '', 'COUNT', 2, '1,200.50'), (-12.0, 'USD', 'USD', 2, '-12.00USD'),
            (0.0, '', 'UNKNOWN', 3, '0.000'), (1200.0, '원', 'KRW', -2, '1,200원'),
            (15.4, '%', 'PERCENT', 20, '15.40000000000000000000%'),
            (0.0, '%', 'PERCENT', 324, '0.' + '0' * 324 + '%'),
        ):
            with self.subTest(expected=expected):
                self.assertEqual(render_value_with_unit(value, display, dimension, decimal_places=precision), expected)
        # Precision outside binary64's decimal range must not allocate unbounded output.
        self.assertEqual(render_value_with_unit(15.4, '%', 'PERCENT', decimal_places=10**20), '15.4%')

    def test_precision_changes_still_fail_protected_execution(self):
        _, state, compiled = compile_case()
        program = deepcopy(compiled['semantic_program'])
        program['expressions'][0]['request_inputs'][0]['value'] = 3.0
        execution = execute_semantic_calculation_program(program=program, query=state['query'],
            obligations=state['answer_obligations'], candidate_catalog=state['semantic_candidate_catalog'],
            compilation_envelope=compiled['semantic_compilation_envelope'], require_compilation_envelope=True)
        self.assertNotEqual(execution['status'], 'ok')
        self.assertEqual(execution['outputs'], [])

    def test_dependencies_keep_calculated_values_without_inheriting_display_precision(self):
        inputs = _source_display_program_fixture()
        first = inputs['program']['expressions'][0]
        first['formula'] = f"round({first['formula']}, precision)"
        first['request_inputs'] = [{'variable': 'precision', 'value': 2.0,
            'request_unit_id': 'request_001', 'source_text': inputs['query'],
            'interpretation': 'Authored final precision.'}]
        inputs['obligations'].append(_obligation('dependent', 'derived_value', 'twice the calculation',
            display_unit='%', depends_on=['ob_change']))
        inputs['program']['expressions'].append({'obligation_id': 'dependent', 'formula': 'X + X',
            'variable_bindings': [_binding('X', 'ob_change')], 'source_display_candidate_id': None,
            'source_display_reason': 'No source display for the subsequent calculation.'})
        before = deepcopy(inputs)
        execution = execute_authored_fixture(**inputs)
        self.assertEqual(execution['validation']['errors'], [])
        self.assertEqual(inputs, before)
        first, dependent = (execution['outputs_by_obligation'][key] for key in ('ob_change', 'dependent'))
        self.assertEqual(first['normalized_value'], 10)
        self.assertEqual(first['rendered_value'], '10.2%')
        self.assertEqual(first['formula_rendered_value'], '10.00%')
        self.assertEqual(dependent['normalized_value'], 20)
        self.assertEqual(dependent['rendered_value'], '20%')

    def test_non_integer_precision_still_fails_arithmetic_execution(self):
        _, state, compiled = compile_case(precision=2.5)
        execution = execute_semantic_calculation_program(program=compiled['semantic_program'], query=state['query'],
            obligations=state['answer_obligations'], candidate_catalog=state['semantic_candidate_catalog'],
            compilation_envelope=compiled['semantic_compilation_envelope'], require_compilation_envelope=True)
        self.assertEqual(execution['outputs'], [])
        self.assertIn('formula_execution_error', {error['code'] for error in execution['execution_errors']})


if __name__ == '__main__':
    unittest.main()
