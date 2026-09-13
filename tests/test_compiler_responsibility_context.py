"""Real compiler prompt contracts with authored responses, not model quality tests."""
from copy import deepcopy
from tests.narrative_address_test_support import model_program
import hashlib
import json
import unittest
from unittest.mock import patch

from src.agent.financial_compiler_presentation import project_output_responsibility_context
from src.agent.financial_graph import compilation_phase_input
from src.agent.financial_graph_calculation import _merge_targeted_program_retry
from src.agent.financial_calculation_execution import semantic_candidate_applicability
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_request_units import build_request_units, project_request_units
from src.config.retrieval_policy import CALCULATION_PROMPT_POLICY
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate, _obligation
from tests.test_narrative_claim_grounding import claim, source
from tests.test_narrative_output_partition import authored_pipeline
from tests.test_narrative_retry_context import prompt_json
from tests.test_planner_requirement_transport import agent_for


MARKER = 'Output responsibility context:'
POLICY_KEY = 'semantic_program_output_responsibility_context_template'


def compile_authored(state, programs):
    copied = {key: deepcopy(state[key]) for key in ('request', 'routing', 'requirements', 'candidates')}
    queue = _StructuredQueueLLM(*programs)
    agent = agent_for(queue)
    before = deepcopy(copied)
    compiled = agent._compile_semantic_calculation_program(compilation_phase_input(copied))
    assert copied == before
    copied['compilation'] = compiled
    copied.update(agent._execute_numeric_phase(copied))
    copied.update(agent._assemble_final_phase(copied))
    copied.update(agent._assemble_ledger_phase(copied))
    return copied, queue


def simple_fixture(*, shared=False, bad_quote=False, overlap=False, coupling=''):
    bodies = ['Willow accepts requests only after consent.', 'Willow arranges visits on weekdays.']
    query = 'Explain Willow intake.\nInclude its consent condition.\nDescribe Willow visit scheduling.'
    refs = [['request_001', 'request_002'], ['request_003']]
    owners = [('Willow', 'Intake', refs[0]), ('Willow', 'Scheduling', refs[1])]
    if shared:
        bodies = ['Willow may start after consent. Rowan may start after consent.']
        query = 'Explain the starting conditions for Willow and Rowan.'
        owners = [('Willow', 'Willow condition', ['request_001']), ('Rowan', 'Rowan condition', ['request_001'])]
        responses = [[(1, 0, 'Willow', 'may start after consent.', bodies[0])],
                     [(2, 0, 'Rowan', 'may start after consent.', bodies[0])]]
    else:
        responses = [[(1, 0, 'Willow', bodies[0], bodies[0])],
                     [(2, 1, 'Willow', bodies[1], 'Unwritten quote.' if bad_quote else bodies[1])]]
        if overlap:
            responses[0].append((1, 1, 'Willow', bodies[1], bodies[1]))
        if bad_quote:
            responses.append([(2, 1, 'Willow', bodies[1], bodies[1])])
    if coupling:
        responses = [[*responses[0], *responses[1]], *responses[2:]]
    return authored_pipeline(query, bodies, owners, responses, coupling=coupling)


class CompilerResponsibilityContextTests(unittest.TestCase):
    def test_real_compiler_prompt_contains_planned_sibling_responsibilities(self):
        state, queue, _ = simple_fixture()
        prompt = queue.prompts[1].to_messages()[0].content
        self.assertIn('Output responsibility context:\n', prompt)
        context = prompt_json(queue.prompts[1], 'Output responsibility context:')
        self.assertEqual([row['obligation_id'] for row in context['outputs']],
                         [row['obligation_id'] for row in state['requirements']['answer_obligations']])

    def assert_unchanged(self, original, proposed):
        for key in ('semantic_program', 'semantic_program_validation', 'semantic_compilation_envelope'):
            self.assertEqual(original['compilation'][key], proposed['compilation'][key])
        for key in ('answer', 'citations'):
            self.assertEqual(original['final_result']['agent_answer'][key], proposed['final_result']['agent_answer'][key])
        results = [deepcopy(row['final_result']['agent_answer']['structured_result']) for row in (original, proposed)]
        # The policy-off counterfactual omits only the added presentation bytes.
        # Every other result/trace field must remain identical.
        for result in results:
            for attempt in result['resolved_calculation_trace']['calculation_plan']['candidate_stage_diagnostics']['attempts']:
                attempt.pop('output_responsibility_prompt_bytes')
        self.assertEqual(*results)
        self.assertEqual(original['candidates'], proposed['candidates'])
        self.assertEqual(proposed['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        aggregate, = [row for row in proposed['ledger']['artifacts'] if row['kind'] == 'aggregated_answer']
        self.assertEqual(aggregate['payload']['final_answer'], proposed['final_result']['agent_answer']['answer'])
        self.assertEqual(aggregate['payload']['structured_result'], proposed['final_result']['agent_answer']['structured_result'])

    def test_single_output_needs_no_additional_context(self):
        body = 'Willow accepts requests only after consent.'
        state, queue, programs = authored_pipeline('Explain Willow intake and its condition.', [body],
            [('Willow', 'Intake', ['request_001'])], [[(1, 0, 'Willow', body, body)]])
        self.assertNotIn(MARKER, queue.prompts[1].to_messages()[0].content)
        with patch.dict(CALCULATION_PROMPT_POLICY, {POLICY_KEY: ''}):
            baseline, baseline_queue = compile_authored(state, programs)
        self.assert_unchanged(baseline, state)
        self.assertEqual(queue.prompts[1], baseline_queue.prompts[0])
        self.assert_context_diagnostics(state, queue.prompts[1:])

    def test_projection_copies_only_planned_responsibility_and_exact_request(self):
        state, _, _ = simple_fixture()
        query, owners = state['request']['query'], deepcopy(state['requirements']['answer_obligations'])
        for row in owners:
            row.update({'candidate_ids': ['hidden-id'], 'accepted_answer': 'Not planning context.',
                        'status': 'ready', 'rationale': 'Diagnostic-only explanation.'})
            row['semantic_target']['unused_private'] = ['not-a-subject']
            row['scope']['extra_source'] = 'not-a-scope-field'
        before = deepcopy(owners)
        context = project_output_responsibility_context(query, owners)
        self.assertEqual(context['schema'], 'output_responsibility_context_v1')
        self.assertEqual(owners, before)
        self.assertEqual(context['request_units_by_id'], project_request_units(build_request_units(query)))
        self.assertEqual([row['obligation_id'] for row in context['outputs']], ['ob_001', 'ob_002'])
        expected = {'obligation_id', 'kind', 'label', 'request_unit_ids', 'local_subjects', 'scope', 'source_sections'}
        self.assertTrue(all(set(row) == expected for row in context['outputs']))
        serialized = json.dumps(context)
        for excluded in ('hidden-id', 'Not planning context.', 'Diagnostic-only', 'not-a-subject', 'extra_source'):
            self.assertNotIn(excluded, serialized)
        context['outputs'][0]['local_subjects'].append('changed copy')
        context['outputs'][0]['request_unit_ids'].clear()
        context['outputs'][0]['scope']['segment'] = 'changed copy'
        self.assertEqual(owners, before)

    def test_subject_scope_section_and_long_qualifiers_are_not_collapsed(self):
        for subject in ('Willow', '테스트부문', 'Unit (North)'):
            query = 'Compare the requested scopes.\n' + ('Keep the exact qualification; ' * 50) + 'do not generalize.'
            owners = [dict(obligation_id=f'view_{index}', kind='narrative', label='Activity',
                           request_unit_ids=['request_001', 'request_002'],
                           semantic_target={'local_subjects': [subject]},
                           scope={'period': str(2050 + index), 'basis': basis, 'segment': subject},
                           source_sections=[section])
                      for index, (basis, section) in enumerate((('observed', 'Section A'), ('planned', 'Section B')))]
            context = project_output_responsibility_context(query, owners)
            self.assertEqual(len(context['outputs']), 2)
            self.assertEqual(''.join(row['text'] for row in context['request_units_by_id'].values()), query)
            self.assertNotEqual(context['outputs'][0]['scope'], context['outputs'][1]['scope'])
            self.assertEqual([row['source_sections'] for row in context['outputs']], [['Section A'], ['Section B']])

    def test_independent_topics_gain_context_without_authority_or_call_changes(self):
        proposed, full_queue, programs = simple_fixture()
        with patch.dict(CALCULATION_PROMPT_POLICY, {POLICY_KEY: ''}):
            original, baseline_queue = compile_authored(proposed, programs)
        prompts = full_queue.prompts[1:]
        self.assert_unchanged(original, proposed)
        self.assertEqual(len(prompts), len(baseline_queue.prompts))
        for index, prompt in enumerate(prompts):
            scope = prompt_json(prompt, 'Compilation scope:')
            self.assertEqual(scope['active_obligation_ids'], [f'ob_{index + 1:03d}'])
            self.assertEqual([row['label'] for row in prompt_json(prompt, 'Answer obligations:')],
                             ['Intake' if index == 0 else 'Scheduling'])
            self.assertEqual([row['label'] for row in prompt_json(prompt, MARKER)['outputs']], ['Intake', 'Scheduling'])
            self.assertEqual(prompt_json(prompt, 'Source bundles, candidate cohorts, and candidates_by_id:'),
                             prompt_json(baseline_queue.prompts[index], 'Source bundles, candidate cohorts, and candidates_by_id:'))
            context_json = json.dumps(prompt_json(prompt, MARKER), ensure_ascii=False, separators=(',', ':'))
            block = CALCULATION_PROMPT_POLICY[POLICY_KEY].format(context=context_json)
            self.assertEqual(prompt.to_messages()[0].content.replace(block, '', 1),
                             baseline_queue.prompts[index].to_messages()[0].content)
            self.assertEqual(prompt.to_messages()[0].content.count(MARKER + '\n'), 1)
            self.assertNotIn(MARKER, baseline_queue.prompts[index].to_messages()[0].content)
        self.assert_context_diagnostics(proposed, prompts)

    def test_retry_reuses_plan_context_without_replaying_an_accepted_answer(self):
        for coupling in ('', 'authored-coupling'):
            with self.subTest(coupling=coupling):
                original, _, programs = simple_fixture(bad_quote=True, coupling=coupling)
                proposed, queue = compile_authored(original, programs)
                self.assert_unchanged(original, proposed)
                self.assertEqual(len(queue.prompts), 2 if coupling else 3)
                contexts = [prompt_json(prompt, MARKER) for prompt in queue.prompts]
                self.assertEqual(contexts, [contexts[0]] * len(queue.prompts))
                self.assertEqual(prompt_json(queue.prompts[-1], 'Compilation scope:')['active_obligation_ids'], ['ob_002'])
                self.assertNotIn(programs[0].narrative_bindings[0].claims[0].text, json.dumps(contexts[-1]))
                self.assertEqual(proposed['compilation']['semantic_program_retry_count'], 1)
                self.assert_context_diagnostics(proposed, queue.prompts)

    def test_shared_conditions_and_declared_coupling_keep_existing_meaning_and_islands(self):
        for shared, coupling in ((True, ''), (False, 'authored-coupling')):
            with self.subTest(shared=shared, coupling=coupling):
                original, baseline_queue, programs = simple_fixture(shared=shared, coupling=coupling)
                proposed, queue = compile_authored(original, programs)
                self.assert_unchanged(original, proposed)
                self.assertEqual(len(queue.prompts), len(baseline_queue.prompts) - 1)
                context = prompt_json(queue.prompts[0], MARKER)
                self.assertEqual(len(context['outputs']), 2)
                if shared:
                    self.assertEqual(context['outputs'][0]['request_unit_ids'], context['outputs'][1]['request_unit_ids'])
                    self.assertNotEqual(context['outputs'][0]['local_subjects'], context['outputs'][1]['local_subjects'])

    def test_context_cannot_grant_foreign_owner_candidate_or_quote_authority(self):
        original, _, programs = simple_fixture()
        for corruption in ('owner', 'candidate', 'quote'):
            with self.subTest(corruption=corruption):
                attempt_state = deepcopy(original)
                bad = programs[0].model_dump()
                binding = bad['narrative_bindings'][0]
                if corruption == 'owner':
                    binding['obligation_id'] = 'ob_002'  # Present in context, not an active output.
                elif corruption == 'candidate':
                    # Explicit negative fixture: registered in the catalog, but outside filing scope.
                    hidden = deepcopy(original['candidates']['semantic_candidate_catalog'][0])
                    hidden.update(candidate_id='hidden-foreign-filing', company='Elsewhere',
                                  document_company='Elsewhere', source_document_id='another-filing',
                                  source_anchor=hidden['source_anchor'].replace('Issuer', 'Elsewhere'))
                    attempt_state['candidates']['semantic_candidate_catalog'].append(hidden)
                    binding['claims'][0]['fact_evidence_selections'][0]['candidate_id'] = hidden['candidate_id']
                else:
                    binding['claims'][0]['fact_evidence_selections'][0]['surface_id'] = 'request-is-not-source'
                # Re-project only legacy mirrors; the intentionally bad claim stays unchanged.
                for projected in ('candidate_ids', 'evidence_bindings', 'text'):
                    binding.pop(projected, None)
                invalid = SemanticCalculationProgram.model_validate(bad)
                proposed, queue = compile_authored(attempt_state, [invalid, invalid, programs[1]])
                self.assertNotEqual(proposed['compilation']['semantic_program_validation']['status'], 'ready')
                self.assertEqual(len(queue.prompts), 3)
                self.assertEqual(proposed['compilation']['semantic_program_retry_count'], 1)
                self.assertIn('ob_001', proposed['compilation']['semantic_program_validation']['missing_obligation_ids'])
                history = proposed['compilation']['planner_debug_trace']['program_validation_history']
                self.assertTrue(any(row['errors'] for row in history))
                self.assertEqual([row['obligation_id'] for row in proposed['compilation']['semantic_program']['narrative_bindings']], ['ob_002'])
                if corruption == 'candidate':
                    payload = prompt_json(queue.prompts[0], 'Source bundles, candidate cohorts, and candidates_by_id:')
                    self.assertNotIn(hidden['candidate_id'], payload['candidates_by_id'])

    def test_existing_company_surface_match_is_not_an_exact_filing_identity_check(self):
        # Separate pre-existing limit discovered while constructing an explicit-conflict fixture.
        # This is not evidence of a foreign filing passing scoped retrieval, which is not run here.
        owner = {'kind': 'narrative', 'scope': {'company': 'Issuer'}}
        self.assertEqual(semantic_candidate_applicability({'company': 'OtherIssuer'}, owner)['state'], 'compatible')
        self.assertEqual(semantic_candidate_applicability({'company': 'Elsewhere'}, owner)['state'], 'explicit_conflict')

    def test_context_does_not_mechanically_remove_an_authored_semantic_overlap(self):
        original, _, programs = simple_fixture(overlap=True)
        proposed, _ = compile_authored(original, programs)
        self.assert_unchanged(original, proposed)
        answer = proposed['final_result']['agent_answer']['answer']
        self.assertEqual(answer.count('Willow arranges visits on weekdays.'), 2)
        # Honest negative control: source validation and more context do not prove better model selection.

    def assert_context_diagnostics(self, state, prompts):
        diagnostics = state['compilation']['resolved_calculation_trace']['calculation_plan']['candidate_stage_diagnostics']
        self.assertEqual(len(diagnostics['attempts']), len(prompts))
        for attempt, prompt in zip(diagnostics['attempts'], prompts):
            present = MARKER + '\n' in prompt.to_messages()[0].content
            serialized = json.dumps(prompt_json(prompt, MARKER), ensure_ascii=False, separators=(',', ':')) if present else ''
            raw = serialized.encode('utf-8')
            self.assertEqual(attempt['output_responsibility_context_fingerprint'], hashlib.sha256(raw).hexdigest() if raw else '')
            self.assertEqual(attempt['serialized_output_responsibility_context_bytes'], len(raw))
            block = CALCULATION_PROMPT_POLICY[POLICY_KEY].format(context=serialized) if present else ''
            self.assertEqual(attempt['output_responsibility_prompt_bytes'], len(block.encode('utf-8')))

    def test_numeric_only_calls_keep_the_previous_prompt_bytes(self):
        owners = [_obligation(key, 'direct_value', key) for key in ('first', 'second')]
        programs = [SemanticCalculationProgram.model_validate({'direct_bindings': [
            {'obligation_id': row['obligation_id'], 'candidate_id': 'number'}]}) for row in owners]
        state = {'query': 'Report both requested quantities.', 'answer_obligations': owners,
                 'semantic_candidate_catalog_prebuilt': True, 'semantic_candidate_catalog': [_candidate('number', 7)],
                 'semantic_source_candidates': []}
        queue = _StructuredQueueLLM(*programs)
        result = agent_for(queue)._compile_semantic_calculation_program(state)
        self.assertEqual(result['semantic_program_validation']['status'], 'ready')
        key = 'semantic_program_prompt_template'
        # Remove only the new placeholder to reconstruct the predecessor template.
        with patch.dict(CALCULATION_PROMPT_POLICY, {key: CALCULATION_PROMPT_POLICY[key].replace('{output_responsibility_context}', '')}):
            baseline_queue = _StructuredQueueLLM(*programs)
            baseline = agent_for(baseline_queue)._compile_semantic_calculation_program(state)
        self.assertEqual(queue.prompts, baseline_queue.prompts)
        self.assertEqual(result['semantic_compilation_envelope'], baseline['semantic_compilation_envelope'])
        self.assertTrue(all(MARKER not in p.to_messages()[0].content for p in queue.prompts))
        self.assert_context_diagnostics({'compilation': result}, queue.prompts)

    def test_mixed_island_shares_context_only_while_a_narrative_output_is_active(self):
        body = 'Willow accepts requests only after consent.'
        owners = [_obligation('activity', 'narrative', 'Activity', coupling_key='shared'),
                  _obligation('quantity', 'direct_value', 'Quantity', coupling_key='shared')]
        good = {'narrative_bindings': [{'obligation_id': 'activity', 'claims': [claim('Willow', body, 'note', body)]}],
                'direct_bindings': [{'obligation_id': 'quantity', 'candidate_id': 'number'}]}
        state = {'query': 'Describe activity and report the quantity.', 'answer_obligations': owners,
                 'semantic_candidate_catalog_prebuilt': True,
                 'semantic_candidate_catalog': [source('note', body), _candidate('number', 7)],
                 'semantic_source_candidates': []}
        before = deepcopy(state)
        for repair in ('narrative', 'numeric'):
            with self.subTest(repair=repair):
                bad, retry = deepcopy(good), deepcopy(good)
                if repair == 'narrative':
                    bad['narrative_bindings'][0]['claims'][0]['evidence_bindings'][0]['evidence_text'] = 'Not in source.'
                    retry.pop('direct_bindings')
                else:
                    bad['direct_bindings'][0]['candidate_id'] = 'invented'
                    retry.pop('narrative_bindings')
                queue = _StructuredQueueLLM(*[model_program(row, state['semantic_candidate_catalog']) for row in (bad, retry)])
                with patch('src.agent.financial_graph_calculation.project_output_responsibility_context',
                           wraps=project_output_responsibility_context) as projector, patch(
                               'src.agent.financial_graph_calculation._merge_targeted_program_retry',
                               wraps=_merge_targeted_program_retry) as merge:
                    result = agent_for(queue)._compile_semantic_calculation_program(state)
                self.assertEqual(projector.call_count, 1)
                self.assertEqual(state, before)
                self.assertEqual(result['semantic_program_validation']['status'], 'ready')
                self.assertEqual(len(queue.prompts), 2)
                context = prompt_json(queue.prompts[0], MARKER)
                self.assertEqual([row['kind'] for row in context['outputs']], ['narrative', 'direct_value'])
                active = 'activity' if repair == 'narrative' else 'quantity'
                self.assertEqual(prompt_json(queue.prompts[1], 'Compilation scope:')['active_obligation_ids'], [active])
                if repair == 'narrative':
                    self.assertEqual(prompt_json(queue.prompts[1], MARKER), context)
                else:
                    self.assertNotIn(MARKER, queue.prompts[1].to_messages()[0].content)
                accepted_key = 'direct_bindings' if repair == 'narrative' else 'narrative_bindings'
                # Quote-location readings belong to validation, not program JSON.
                expected = [{key: value for key, value in row.items() if key != 'claim_readings'}
                            for row in merge.call_args.kwargs['previous_validation']['valid_' + accepted_key]]
                self.assertEqual(json.dumps(result['semantic_program'][accepted_key], sort_keys=True), json.dumps(expected, sort_keys=True))
                self.assert_context_diagnostics({'compilation': result}, queue.prompts)

    def test_invalid_plan_blocks_before_context_projection_and_compiler_dispatch(self):
        state, _, _ = simple_fixture()
        state['requirements']['answer_obligations'][0]['request_unit_ids'] = ['unknown']
        queue = _StructuredQueueLLM()
        with patch('src.agent.financial_graph_calculation.project_output_responsibility_context') as projector:
            result = agent_for(queue)._compile_semantic_calculation_program(compilation_phase_input(state))
        projector.assert_not_called()
        self.assertEqual(queue.prompts, [])
        self.assertNotEqual(result['semantic_program_validation']['status'], 'ready')


if __name__ == '__main__':
    unittest.main()
