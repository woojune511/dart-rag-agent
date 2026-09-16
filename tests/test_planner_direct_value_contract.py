"""Direct lookup generation/preflight, with source validation kept independent."""
from copy import deepcopy
from types import SimpleNamespace
import unittest

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_graph import compilation_phase_input, planning_phase_input
from src.agent.financial_graph_calculation import build_semantic_compilation_islands
from src.agent.financial_graph_models import AnswerObligation, RequirementPlannerOutput, SemanticCalculationProgram
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate, _obligation, _requirement
from tests.test_planner_requirement_transport import agent_for, request


def direct_owner(**extra):
    return dict(kind='direct_value', label='quantity', request_unit_ids=['request_001'],
                display_unit='COUNT', **extra)


class PlannerDirectValueContractTests(unittest.TestCase):
    def test_generation_rejects_child_requirements_without_erasing_the_input(self):
        validator = Draft202012Validator(RequirementPlannerOutput.model_json_schema())
        for required in (True, False):
            with self.subTest(required=required):
                raw = dict(obligations=[direct_owner(evidence_requirements=[
                    dict(label='quantity', required=required)])])
                before = deepcopy(raw)
                self.assertFalse(validator.is_valid(raw))
                with self.assertRaises(ValidationError):
                    RequirementPlannerOutput.model_validate(raw)
                self.assertEqual(raw, before)

    def test_empty_direct_and_other_kinds_preserve_their_evidence_contracts(self):
        rows = [direct_owner(evidence_requirements=[]),
                dict(kind='derived_value', label='double', request_unit_ids=['request_001'],
                     evidence_requirements=[dict(label='input')]),
                dict(kind='narrative', label='activity', request_unit_ids=['request_001'],
                     evidence_requirements=[dict(label='fact')]),
                dict(kind='narrative', label='source group', request_unit_ids=['request_001'],
                     evidence_mode='source_defined_group')]
        model = RequirementPlannerOutput.model_validate(dict(obligations=rows))
        self.assertEqual([len(o.evidence_requirements) for o in model.obligations], [0, 1, 1, 1])
        self.assertEqual(RequirementPlannerOutput.model_validate(model.model_dump()), model)
        with self.assertRaises(ValidationError):
            RequirementPlannerOutput.model_validate(dict(obligations=[direct_owner(evidence_mode='source_defined_group')]))

    def compile_authored(self, *, legacy=False, coupled=False):
        rows = [direct_owner(obligation_id='first'), direct_owner(obligation_id='second')]
        if legacy:
            rows[0]['evidence_requirements'] = [dict(requirement_id='old-input', label='quantity')]
        if coupled:
            rows[1]['depends_on'] = ['first']
        # Explicit historical/internal transport, never bypass production parsing.
        plan = (SimpleNamespace(obligations=[AnswerObligation.model_validate(row) for row in rows],
                    output_relationships=[], retrieval_queries=[], companies=[], years=[], topic='',
                    section_filter=None, rationale='') if legacy else
                RequirementPlannerOutput.model_validate(dict(obligations=rows)))
        expected_ids = [] if coupled else (['ob_002'] if legacy else ['ob_001', 'ob_002'])
        programs = [SemanticCalculationProgram.model_validate(dict(direct_bindings=[
            dict(obligation_id=oid, candidate_id='quantity')])) for oid in expected_ids]
        llm = _StructuredQueueLLM(plan, *programs)
        agent = agent_for(llm)
        state = request('Return the requested quantities.')
        catalog = [{**_candidate('quantity', 42), 'company': 'Issuer', 'document_company': 'Issuer',
                    'year': 2042, 'period': '2042'}]
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        owners_before = deepcopy(state['requirements']['answer_obligations'])
        state['candidates'] = dict(semantic_source_candidates=[], semantic_candidate_catalog=deepcopy(catalog))
        state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual(state['requirements']['answer_obligations'], owners_before)
        self.assertEqual(state['candidates']['semantic_candidate_catalog'], catalog)
        self.assertEqual(llm.responses, [])
        self.assertEqual(llm.models, ['RequirementPlannerOutput'] + ['CompilerResponseV2'] * len(expected_ids))
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        return state

    def test_valid_direct_outputs_execute_once_with_unchanged_source_values(self):
        state = self.compile_authored()
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'ok')
        outputs = answer['resolved_calculation_trace']['calculation_result']['outputs']
        self.assertEqual([o['normalized_value'] for o in outputs], [42, 42])
        self.assertEqual([o['answer_slot']['raw_value'] for o in outputs], ['42', '42'])
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])

    def test_legacy_invalid_lookup_blocks_only_its_island_without_repair(self):
        state = self.compile_authored(legacy=True)
        islands = state['compilation']['planner_debug_trace']['compilation_islands']
        self.assertEqual([i['call_count'] for i in islands], [0, 1])
        self.assertEqual([i['retry_count'] for i in islands], [0, 0])
        issue, = islands[0]['preflight_errors']
        self.assertEqual(issue, state['requirements']['semantic_plan']['requirement_errors'][0])
        self.assertEqual(issue['code'], 'evidence_requirement_on_unsupported_obligation')
        self.assertEqual(issue['repair_action'], 'repair_requirements')
        self.assertEqual(issue['location'], 'obligation.evidence_requirements')
        self.assertEqual(issue['owner_id'], 'ob_001')
        self.assertEqual(len(state['requirements']['answer_obligations'][0]['evidence_requirements']), 1)
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'partial')
        outputs = answer['resolved_calculation_trace']['calculation_result']['outputs']
        self.assertEqual([o['obligation_id'] for o in outputs], ['ob_002'])
        self.assertEqual(outputs[0]['normalized_value'], 42)

    def test_invalid_lookup_blocks_its_dependent_component_before_compiler(self):
        state = self.compile_authored(legacy=True, coupled=True)
        island, = state['compilation']['planner_debug_trace']['compilation_islands']
        self.assertEqual(island['obligation_ids'], ['ob_001', 'ob_002'])
        self.assertEqual((island['call_count'], island['retry_count']), (0, 0))
        self.assertEqual(state['final_result']['agent_answer']['structured_result']['status'], 'incomplete')

    def test_preflight_and_final_validation_both_retain_invalid_historical_requirements(self):
        owners = [_obligation('answer', 'direct_value', 'quantity',
            evidence_requirements=[_requirement('answer:req_001', 'quantity')])]
        before = deepcopy(owners)
        errors = build_semantic_compilation_islands(owners)['islands'][0]['errors']
        self.assertEqual([e['code'] for e in errors], ['evidence_requirement_on_unsupported_obligation'])
        validation = validate_semantic_calculation_program(program=dict(direct_bindings=[
            dict(obligation_id='answer', candidate_id='value')]), obligations=owners,
            candidate_catalog=[_candidate('value', 42)], query='Return the quantity.')
        self.assertEqual(validation['status'], 'partial')
        self.assertIn('evidence_requirement_on_unsupported_obligation', [e['code'] for e in validation['errors']])
        self.assertEqual(owners, before)


if __name__ == '__main__':
    unittest.main()
