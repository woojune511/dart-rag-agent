"""Optional absence is allowed; selected evidence and failed replies stay accountable."""
from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_compiler_wire import CompilerReferencesV1, lower_compiler_response
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram, compiler_response_model
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from tests.narrative_address_test_support import model_program
from tests.semantic_program_test_support import (
    _candidate, _obligation, _requirement, _StructuredQueueLLM, execute_compiled_fixture,
)
from tests.test_narrative_claim_grounding import source, claim


QUERY = 'Describe the optional activities.'


def setup_wire(owners, catalog):
    cohorts = _semantic_candidate_cohorts(catalog, owners)
    payload = FinancialAgent._semantic_program_prompt_payload(catalog, cohorts)
    refs = CompilerReferencesV1.build(catalog, owners, QUERY, payload)
    visibility = _semantic_candidate_visibility(catalog,
        visible_candidate_ids=cohorts['visible_candidate_ids'],
        candidate_ids_by_owner=cohorts['candidate_ids_by_owner'],
        evidence_bundle_constraints=cohorts['evidence_bundle_constraints'])
    return cohorts, refs, visibility, compiler_response_model(owners, refs, visibility)


def compile_case(owners, catalog, *programs):
    agent = FinancialAgent.__new__(FinancialAgent)
    agent.llm = _StructuredQueueLLM(*(SemanticCalculationProgram.model_validate(row) for row in programs))
    state = dict(query=QUERY, answer_obligations=owners, semantic_source_candidates=catalog,
        semantic_candidate_catalog=catalog, semantic_candidate_catalog_prebuilt=True, include_debug_bundle=True)
    compiled = agent._compile_semantic_calculation_program(state)
    return compiled, agent, state


def numeric_program(owner='extra', candidate='value'):
    return dict(status='ready', direct_bindings=[dict(obligation_id=owner, candidate_id=candidate)])


class OptionalOutputContractTests(unittest.TestCase):
    def narrative_case(self):
        requirement = {**_requirement('extra:input', 'activity'), 'required': False}
        owners = [_obligation('extra', 'narrative', 'activity', required=False,
            evidence_requirements=[requirement])]
        catalog = [source('note', 'Willow routes messages.')]
        program = model_program(dict(narrative_bindings=[dict(obligation_id='extra', claims=[
            claim('Willow', 'Willow routes messages.', 'note', 'Willow routes messages.',
                  source_requirement_id='extra:input')])]), catalog).model_dump()
        return owners, catalog, program

    def test_optional_child_gets_its_own_bounded_authority(self):
        owners, catalog, _ = self.narrative_case()
        before = deepcopy(owners)
        cohorts, _, visibility, _ = setup_wire(owners, catalog)
        self.assertEqual(visibility.candidate_ids_by_owner()['extra:input'], ['note'])
        self.assertEqual(len(cohorts['cohorts']), 2)
        self.assertEqual(owners, before)

    def test_optional_child_still_intersects_parent_source_restrictions(self):
        owners, catalog, _ = self.narrative_case()
        owners[0]['source_sections'] = ['Methods']
        owners[0]['evidence_requirements'][0]['source_sections'] = ['Other']
        catalog[0]['source_anchor'] = '[Parent | 2024 | Methods]'
        _, _, visibility, model = setup_wire(owners, catalog)
        self.assertEqual(visibility.candidate_ids_by_owner().get('extra:input'), [])
        schema = model.model_json_schema()
        groups = [row for row in schema['$defs'].values() if 'extra:input' in row.get('properties', {})]
        self.assertEqual(len(groups), 1)
        self.assertEqual(groups[0]['properties']['extra:input'].get('maxItems'), 0)

    def test_optional_narrative_can_be_selected_and_rendered(self):
        owners, catalog, program = self.narrative_case()
        _, refs, visibility, model = setup_wire(owners, catalog)
        raw = project_offline_program_to_wire(program, model)
        errors = []
        lowered = lower_compiler_response(model.model_validate(raw), model=model, refs=refs,
            obligations=owners, catalog=catalog, visibility=visibility, errors=errors)
        self.assertEqual(errors, [])
        self.assertEqual(validate_semantic_calculation_program(program=lowered,
            obligations=owners, candidate_catalog=catalog, query=QUERY,
            candidate_visibility=visibility, require_narrative_claims=True)['status'], 'ready')
        compiled, agent, state = compile_case(owners, catalog, program)
        answer = execute_compiled_fixture(agent, {**state, **compiled}, catalog)
        self.assertEqual(len(agent.llm.prompts), 1)
        self.assertIn('Willow routes messages.', answer['answer'])
        self.assertEqual(answer['structured_result']['status'], 'ok')
        self.assertEqual(answer['task_artifact_trace']['integrity_status'], 'ok')

    def test_optional_transport_error_gets_one_targeted_repair(self):
        owners = [_obligation('extra', 'direct_value', 'optional quantity', required=False)]
        compiled, agent, _ = compile_case(owners, [_candidate('value', 7)],
            numeric_program(candidate='unknown'), numeric_program())
        self.assertEqual(len(agent.llm.prompts), 2)
        self.assertEqual(compiled['semantic_program_retry_count'], 1)
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertFalse(compiled['semantic_program'].get('failed_obligation_ids'))

    def test_optional_numeric_input_can_be_used_without_becoming_required(self):
        requirement = {**_requirement('extra:input', 'quantity'), 'required': False}
        owners = [_obligation('extra', 'derived_value', 'optional quantity', required=False,
            evidence_requirements=[requirement])]
        program = dict(expressions=[dict(obligation_id='extra', formula='x',
            source_display_candidate_id=None, source_display_reason='Use the selected quantity.', variable_bindings=[
            dict(variable='x', source_id='value', source_requirement_id='extra:input')])])
        compiled, agent, state = compile_case(owners, [_candidate('value', 7)], program)
        answer = execute_compiled_fixture(agent, {**state, **compiled}, [_candidate('value', 7)])
        self.assertEqual(answer['structured_result']['status'], 'ok')
        self.assertFalse(owners[0]['evidence_requirements'][0]['required'])
        self.assertEqual(len(agent.llm.prompts), 1)

    def test_unavailable_optional_sources_make_no_call_and_no_empty_success(self):
        owners = [_obligation('extra', 'narrative', 'optional activity', required=False)]
        compiled, agent, state = compile_case(owners, [])
        answer = execute_compiled_fixture(agent, {**state, **compiled}, [])
        self.assertEqual(agent.llm.prompts, [])
        self.assertEqual(answer['structured_result']['status'], 'incomplete')
        self.assertTrue(answer['answer'])

    def test_optional_schema_failure_repairs_once_and_keeps_safe_final_failure(self):
        class FailingModel:
            calls = 0
            def with_structured_output(self, model): return self
            def invoke(self, prompt):
                self.calls += 1
                raise ValueError('private-provider-sentinel')
        owners = [_obligation('extra', 'direct_value', 'optional quantity', required=False)]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = FailingModel()
        compiled = agent._compile_semantic_calculation_program(dict(query=QUERY,
            answer_obligations=owners, semantic_candidate_catalog=[_candidate('value', 7)],
            semantic_candidate_catalog_prebuilt=True, include_debug_bundle=True))
        self.assertEqual(agent.llm.calls, 2)
        self.assertEqual(compiled['semantic_program']['failed_obligation_ids'], ['extra'])
        self.assertEqual(compiled['semantic_program_validation']['status'], 'invalid')
        self.assertNotIn('private-provider-sentinel', str(compiled))

    def test_optional_invalid_subject_remains_rejected_after_repair_limit(self):
        owners, catalog, program = self.narrative_case()
        program['narrative_bindings'][0]['subject_bindings'][0]['subject'] = 'Unknown'
        for key in ('text', 'evidence_bindings'):
            program['narrative_bindings'][0].pop(key, None)
        compiled, agent, state = compile_case(owners, catalog, program, program)
        self.assertEqual(len(agent.llm.prompts), 2)
        self.assertEqual(compiled['semantic_program']['failed_obligation_ids'], ['extra'])
        self.assertEqual(compiled['semantic_program_validation']['valid_narrative_bindings'], [])
        self.assertIn('ungrounded_narrative_subject', {
            row['code'] for row in compiled['compiler_attempts'][0]['validation_errors']})

    def test_optional_target_repair_preserves_accepted_sibling_bytes(self):
        owners = [_obligation('main', 'direct_value', 'quantity'),
                  _obligation('extra', 'direct_value', 'optional quantity', required=False, depends_on=['main'])]
        first = dict(direct_bindings=[*numeric_program('main')['direct_bindings'],
                                    *numeric_program(candidate='unknown')['direct_bindings']])
        compiled, agent, _ = compile_case(owners, [_candidate('value', 7)], first, numeric_program())
        self.assertEqual(len(agent.llm.prompts), 2)
        import json
        initial = json.loads(compiled['compiler_attempts'][0]['validation_input_program_json'])
        accepted = next(row for row in initial['direct_bindings'] if row['obligation_id']=='main')
        final = next(row for row in compiled['semantic_program']['direct_bindings'] if row['obligation_id']=='main')
        self.assertEqual(accepted, final)
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')

    def test_unrepaired_optional_transport_error_survives_finalization(self):
        owners = [_obligation('extra', 'direct_value', 'optional quantity', required=False)]
        catalog = [_candidate('value', 7)]
        compiled, agent, state = compile_case(owners, catalog,
            numeric_program(candidate='unknown'), numeric_program(candidate='unknown'))
        self.assertEqual(len(agent.llm.prompts), 2)
        self.assertEqual(compiled['semantic_program']['failed_obligation_ids'], ['extra'])
        self.assertIn('compiler_output_failed', {e['code'] for e in compiled['semantic_program_validation']['errors']})
        answer = execute_compiled_fixture(agent, {**state, **compiled}, catalog)
        self.assertEqual(answer['structured_result']['status'], 'incomplete')
        self.assertTrue(answer['answer'])
        self.assertEqual(answer['task_artifact_trace']['integrity_status'], 'ok')

    def test_optional_semantic_error_is_material(self):
        owners = [_obligation('extra', 'direct_value', 'optional quantity', required=False)]
        invalid = validate_semantic_calculation_program(program=numeric_program(candidate='unknown'),
            obligations=owners, candidate_catalog=[_candidate('value', 7)], query=QUERY)
        self.assertEqual(invalid['status'], 'invalid')
        self.assertEqual(invalid['missing_obligation_ids'], ['extra'])

    def test_all_optional_abstention_does_not_retry_or_report_empty_success(self):
        owners = [_obligation('extra', 'direct_value', 'optional quantity', required=False)]
        for field in ('missing_obligation_ids', 'ambiguous_obligation_ids'):
            with self.subTest(field=field):
                compiled, agent, state = compile_case(owners, [_candidate('value', 7)],
                    dict(status='incomplete', **{field:['extra']}))
                self.assertEqual(len(agent.llm.prompts), 1)
                self.assertFalse(compiled['semantic_program'].get('failed_obligation_ids'))
                answer = execute_compiled_fixture(agent, {**state, **compiled}, [_candidate('value', 7)])
                self.assertEqual(answer['structured_result']['status'], 'incomplete')
                self.assertTrue(answer['answer'])

    def test_optional_abstention_does_not_invalidate_a_required_answer(self):
        owners = [_obligation('main', 'direct_value', 'quantity'),
                  _obligation('extra', 'direct_value', 'optional quantity', required=False)]
        compiled, agent, state = compile_case(owners, [_candidate('value', 7)],
            numeric_program('main'), dict(status='incomplete', missing_obligation_ids=['extra']))
        answer = execute_compiled_fixture(agent, {**state, **compiled}, [_candidate('value', 7)])
        self.assertEqual(len(agent.llm.prompts), 2)
        self.assertEqual(answer['structured_result']['status'], 'ok')
        self.assertEqual(compiled['semantic_program_validation']['errors'], [])

    def test_invalid_optional_sibling_preserves_valid_output_and_reports_partial(self):
        owners = [_obligation('main', 'direct_value', 'quantity'),
                  _obligation('extra', 'direct_value', 'optional quantity', required=False)]
        compiled, agent, state = compile_case(owners, [_candidate('value', 7)],
            numeric_program('main'), numeric_program(candidate='unknown'), numeric_program(candidate='unknown'))
        answer = execute_compiled_fixture(agent, {**state, **compiled}, [_candidate('value', 7)])
        self.assertEqual(len(agent.llm.prompts), 3)
        self.assertEqual(answer['structured_result']['status'], 'partial')
        self.assertEqual(compiled['semantic_program']['direct_bindings'][0]['obligation_id'], 'main')
        self.assertEqual(compiled['semantic_program']['failed_obligation_ids'], ['extra'])

    def test_failure_disposition_is_internal_and_envelope_bound(self):
        self.assertNotIn('failed_obligation_ids', SemanticCalculationProgram.model_json_schema()['properties'])
        self.assertNotIn('failed_obligation_ids', SemanticCalculationProgram().model_dump())
        owners = [_obligation('extra', 'direct_value', 'optional quantity', required=False)]
        catalog = [_candidate('value', 7)]
        compiled, agent, state = compile_case(owners, catalog,
            numeric_program(candidate='unknown'), numeric_program(candidate='unknown'))
        program = compiled['semantic_program']
        self.assertEqual(SemanticCalculationProgram.model_validate(program).model_dump()['failed_obligation_ids'], ['extra'])
        altered = {**program, 'failed_obligation_ids': []}
        self.assertFalse(compiled['semantic_compilation_envelope'].matches_program(altered))


if __name__=='__main__':
    unittest.main()
