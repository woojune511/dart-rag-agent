"""Authored responses verify request transport; they do not measure LLM quality."""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph import planning_phase_input, compilation_phase_input
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts
from src.agent.financial_graph_models import RequirementPlannerOutput
from src.agent.financial_request_units import build_request_units, project_request_units
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_narrative_retry_context import prompt_json
from tests.test_planner_requirement_transport import agent_for, request, owner, evidence, program


class RequestUnitPipelineTests(unittest.TestCase):
    def compile(self, query, rows, *programs):
        model = RequirementPlannerOutput.model_validate({'obligations': rows})
        llm = _StructuredQueueLLM(model, *programs)
        agent, state = agent_for(llm), request(query)
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        state['candidates'] = {'semantic_candidate_catalog': [evidence('Aspen', 'a'), evidence('Birch', 'b')],
                               'semantic_source_candidates': []}
        before = deepcopy(state)
        compiled = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        self.assertEqual(state, before)
        return compiled, state, llm

    def test_short_label_cannot_erase_linked_request_and_retry_only_sees_active_units(self):
        query = 'Operating description: describe Aspen.\nState its attribution limits.\nDescribe Birch and distinguish its wider group.'
        rows = [owner('Aspen', 'Aspen routes', key='aspen', refs=['request_001', 'request_002']),
                owner('Birch', 'Birch routes', key='birch', refs=['request_003'])]
        accepted = program(1, 'Aspen', 'a')
        compiled, state, llm = self.compile(query, rows, accepted,
            program(2, 'Birch', 'b', bad_quote=True), program(2, 'Birch', 'b'))
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertEqual(len(llm.prompts), 4)  # One planner; two islands and one repair.
        units = build_request_units(query)
        self.assertEqual(prompt_json(llm.prompts[0], 'Request units:'), project_request_units(units))
        for prompt, index in zip(llm.prompts[1:], (0, 1, 1)):
            active = [state['requirements']['answer_obligations'][index]]
            scope = prompt_json(prompt, 'Compilation scope:')
            self.assertEqual(scope['request_units_by_id'], project_request_units(units, active))
            self.assertEqual(prompt_json(prompt, 'Answer obligations:'), active)
        payload_marker = 'Source bundles, candidate cohorts, and candidates_by_id:'
        self.assertEqual(prompt_json(llm.prompts[2], payload_marker), prompt_json(llm.prompts[3], payload_marker))
        self.assertEqual(json.dumps(compiled['semantic_program']['narrative_bindings'][0], sort_keys=True),
                         json.dumps(accepted.model_dump()['narrative_bindings'][0], sort_keys=True))

    def test_shared_request_is_not_a_coupling_edge_or_candidate_rank_signal(self):
        rows = [owner(subject, 'Describe routes', key=subject) for subject in ('Aspen', 'Birch')]
        compiled, state, llm = self.compile('Operating description: describe Aspen and Birch.', rows,
            program(1, 'Aspen', 'a'), program(2, 'Birch', 'b'))
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(len(compiled['planner_debug_trace']['compilation_islands']), 2)
        catalog = state['candidates']['semantic_candidate_catalog']
        obligations = state['requirements']['answer_obligations']
        before = deepcopy(catalog)
        without_refs = [{key: value for key, value in row.items() if key != 'request_unit_ids'} for row in obligations]
        self.assertEqual(_semantic_candidate_cohorts(catalog, obligations),
                         _semantic_candidate_cohorts(catalog, without_refs))
        self.assertEqual(catalog, before)

    def test_missing_or_unknown_ownership_blocks_all_compiler_calls_without_candidate_exclusion(self):
        query = 'Operating description: describe Aspen. Disclose uncertainty.'
        for refs, code in (([], 'missing_request_unit_refs'),
                           (['request_001', 'invented'], 'unknown_request_unit_id'),
                           (['request_001'], 'unassigned_request_unit')):
            with self.subTest(refs=refs):
                row = owner('Aspen', 'Routes')
                row['request_unit_ids'] = refs
                compiled, state, llm = self.compile(query, [row])
                self.assertEqual(len(llm.prompts), 1)
                plan = state['requirements']['semantic_plan']
                self.assertEqual(plan['status'], 'incomplete')
                self.assertIn(code, [error['code'] for error in plan['requirement_errors']])
                diag = compiled['resolved_calculation_trace']['calculation_plan']['candidate_stage_diagnostics']
                self.assertEqual(diag['request_unit_errors'], plan['requirement_errors'])
                self.assertEqual(diag['compiler_call_count'], 0)
                self.assertEqual(diag['compiler_retry_count'], 0)
                self.assertEqual(compiled['semantic_program_validation']['selected_candidate_ids'], [])

    def test_original_request_and_owner_references_are_bound_by_execution_authority(self):
        query = 'Operating description: describe Aspen.'
        compiled, state, _ = self.compile(query, [owner('Aspen', 'Routes')], program(1, 'Aspen', 'a'))
        for change in ('query', 'refs'):
            inputs = {'program': deepcopy(compiled['semantic_program']),
                'obligations': deepcopy(state['requirements']['answer_obligations']),
                'candidate_catalog': deepcopy(state['candidates']['semantic_candidate_catalog']),
                'query': query, 'compilation_envelope': compiled['semantic_compilation_envelope'],
                'require_compilation_envelope': True}
            if change == 'query':
                inputs['query'] += ' A new condition.'
            else:
                inputs['obligations'][0]['request_unit_ids'] = ['request_002']
            result = execute_semantic_calculation_program(**inputs)
            self.assertEqual(result['validation']['errors'][0]['code'], 'execution_content_mismatch')

    def test_old_or_stripped_compiler_input_has_no_production_fallback(self):
        row = owner('Aspen', 'Routes')
        del row['request_unit_ids']
        llm = _StructuredQueueLLM()
        compiled = agent_for(llm)._compile_semantic_calculation_program({
            'query': 'Operating description: describe Aspen.', 'answer_obligations': [row],
            'semantic_candidate_catalog_prebuilt': True,
            'semantic_candidate_catalog': [evidence('Aspen', 'a')], 'semantic_source_candidates': [],
        })
        self.assertEqual(llm.prompts, [])
        self.assertFalse(compiled['planner_debug_trace']['program_compiler_invoked'])
        self.assertNotEqual(compiled['semantic_program_validation']['status'], 'ready')

    def test_user_request_is_not_a_new_quote_surface(self):
        query = 'Operating description: Aspen has a wider group. Describe it.'
        bad = program(1, 'Aspen', 'a').model_dump()
        bad['narrative_bindings'][0]['claims'][0]['evidence_bindings'][0]['evidence_text'] = 'Aspen has a wider group.'
        from src.agent.financial_graph_models import SemanticCalculationProgram
        rejected = SemanticCalculationProgram.model_validate(bad)
        compiled, _, llm = self.compile(query,
            [owner('Aspen', 'Routes', refs=['request_001', 'request_002'])], rejected, rejected)
        self.assertEqual(len(llm.prompts), 3)
        self.assertNotEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertEqual(compiled['semantic_program_validation']['selected_candidate_ids'], [])


if __name__ == '__main__':
    unittest.main()
