"""Kind-specific generation and authored execution; no model-quality claims."""
from copy import deepcopy
import unittest

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.agent.financial_graph import planning_phase_input, compilation_phase_input
from src.agent.financial_graph_calculation import build_semantic_compilation_islands
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from tests.narrative_address_test_support import model_program
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate
from tests.test_narrative_claim_grounding import claim, source
from tests.test_narrative_retry_context import prompt_json
from tests.test_planner_requirement_transport import agent_for, request


def owner(kind, unit='', form='', **extra):
    return dict(kind=kind, label='requested output', request_unit_ids=['request_001'],
                display_unit=unit, display_format=form, **extra)


class PlannerNarrativeUnitContractTests(unittest.TestCase):
    def test_generation_schema_and_parser_reject_every_nonempty_narrative_unit(self):
        validator = Draft202012Validator(RequirementPlannerOutput.model_json_schema())
        for unit in ('text', '서술', 'paragraph', 'bespoke-format', 'KRW', '%', 'UNKNOWN'):
            with self.subTest(unit=unit):
                raw = {'obligations': [owner('narrative', unit)]}
                before = deepcopy(raw)
                self.assertFalse(validator.is_valid(raw))
                with self.assertRaises(ValidationError):
                    RequirementPlannerOutput.model_validate(raw)
                self.assertEqual(raw, before)

    def test_numeric_units_remain_declared_and_unsupported_values_still_block(self):
        validator = Draft202012Validator(RequirementPlannerOutput.model_json_schema())
        for kind in ('direct_value', 'derived_value'):
            for unit in ('', 'COUNT', 'KRW', '%', 'UNKNOWN', 'unsupported-unit', 'text', '서술'):
                with self.subTest(kind=kind, unit=unit):
                    raw = {'obligations': [owner(kind, unit, obligation_id='quantity')]}
                    self.assertTrue(validator.is_valid(raw))
                    parsed = RequirementPlannerOutput.model_validate(raw)
                    rows = [row.model_dump() for row in parsed.obligations]
                    self.assertEqual(rows[0]['display_unit'], unit)
                    errors = build_semantic_compilation_islands(rows)['islands'][0]['errors']
                    self.assertEqual(bool(errors), unit in ('unsupported-unit', 'text', '서술'))
                    if errors:
                        self.assertEqual(errors[0]['code'], 'invalid_obligation_unit')
                        self.assertEqual(errors[0]['detail'], unit)

    def test_blank_unit_preserves_narrative_format_and_null_compatibility(self):
        for value in ('', None, 'null', 'None', '  '):
            with self.subTest(value=value):
                parsed = RequirementPlannerOutput.model_validate({'obligations': [
                    owner('narrative', value, '표현 형식', evidence_mode='source_defined_group')]})
                row, = parsed.obligations
                self.assertEqual(row.display_unit, '')
                self.assertEqual(row.display_format, '표현 형식')
                self.assertEqual(len(row.evidence_requirements), 1)
                self.assertEqual(RequirementPlannerOutput.model_validate(parsed.model_dump()), parsed)

    def run_authored(self, *, mode='declared_inputs', form='paragraph', bad_numeric=False,
                     unsupported_fact=False):
        body = 'Willow accepts requests only after consent.'
        candidates = [source('note', body, company='Issuer', document_company='Issuer', year=2042),
                      {**_candidate('quantity', 10), 'company': 'Issuer', 'document_company': 'Issuer',
                       'year': 2042, 'period': '2042'}]
        raw = []
        if bad_numeric:
            raw.append(owner('direct_value', 'unsupported-unit'))
        narrative_index = len(raw) + 1
        narrative_id = f'ob_{narrative_index:03d}'
        narrative = owner('narrative', form=form, evidence_mode=mode,
                          semantic_target={'local_subjects': ['Willow']})
        if mode == 'declared_inputs':
            narrative['evidence_requirements'] = [{'label': 'acceptance condition'}]
        raw.append(narrative)
        if bad_numeric:
            raw.append(owner('direct_value', 'COUNT'))
        plan = RequirementPlannerOutput.model_validate({'obligations': raw})
        statement = 'Willow accepted 37 requests.' if unsupported_fact else body
        program = model_program({'narrative_bindings': [{'obligation_id': narrative_id,
            'claims': [claim('Willow', statement, 'note', body,
                source_requirement_id=f'{narrative_id}:req_001')]}]}, candidates)
        responses = [program, program] if unsupported_fact else [program]
        if bad_numeric:
            responses.append(SemanticCalculationProgram.model_validate({'direct_bindings': [
                {'obligation_id': f'ob_{len(raw):03d}', 'candidate_id': 'quantity'}]}))
        llm = _StructuredQueueLLM(plan, *responses)
        agent = agent_for(llm)
        state = request('Explain the acceptance condition and return any requested quantities.')
        original_plan, original_catalog = deepcopy(plan.model_dump()), deepcopy(candidates)
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        state['candidates'] = {'semantic_source_candidates': [], 'semantic_candidate_catalog': candidates}
        state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual(plan.model_dump(), original_plan)
        self.assertEqual(candidates, original_catalog)
        self.assertEqual(llm.responses, [])
        self.assertEqual(state['compilation']['planner_debug_trace']['program_invocation_errors'], [])
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        compiled_owner, = prompt_json(llm.prompts[1], 'Answer obligations:')
        self.assertEqual(compiled_owner['display_unit'], '')
        self.assertEqual(compiled_owner['display_format'], form)
        return state, llm

    def test_narrative_modes_reach_source_grounded_execution_with_free_display_formats(self):
        for mode in ('declared_inputs', 'source_defined_group'):
            for form in ('text', '서술', 'bespoke-format'):
                with self.subTest(mode=mode, form=form):
                    state, llm = self.run_authored(mode=mode, form=form)
                    self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
                    answer = state['final_result']['agent_answer']
                    self.assertEqual(answer['structured_result']['status'], 'ok')
                    self.assertEqual(answer['answer'], 'Willow accepts requests only after consent.')
                    self.assertEqual(llm.models, ['RequirementPlannerOutput', 'CompilerResponseV2'])

    def test_bad_numeric_island_stays_blocked_beside_valid_narrative_and_numeric_outputs(self):
        state, llm = self.run_authored(bad_numeric=True)
        errors = state['requirements']['semantic_plan']['requirement_errors']
        self.assertEqual([(row['code'], row['obligation_id']) for row in errors],
                         [('invalid_obligation_unit', 'ob_001')])
        islands = state['compilation']['planner_debug_trace']['compilation_islands']
        self.assertEqual([row['call_count'] for row in islands], [0, 1, 1])
        self.assertEqual([row['retry_count'] for row in islands], [0, 0, 0])
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'partial')
        outputs = answer['resolved_calculation_trace']['calculation_result']['outputs']
        self.assertCountEqual([row['obligation_id'] for row in outputs], ['ob_002', 'ob_003'])
        self.assertIn('Willow accepts requests only after consent.', answer['answer'])
        self.assertEqual(llm.models, ['RequirementPlannerOutput', 'CompilerResponseV2', 'CompilerResponseV2'])

    def test_narrative_unit_contract_does_not_authorize_unsupported_numeric_claims(self):
        state, llm = self.run_authored(unsupported_fact=True)
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'incomplete')
        self.assertNotIn('37', answer['answer'])
        self.assertEqual(state['compilation']['semantic_program_validation']['valid_narrative_bindings'], [])
        self.assertEqual(llm.models, ['RequirementPlannerOutput', 'CompilerResponseV2', 'CompilerResponseV2'])


if __name__ == '__main__':
    unittest.main()
