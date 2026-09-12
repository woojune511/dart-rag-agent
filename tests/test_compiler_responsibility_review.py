"""Provider-free design probes, not an enabled runtime change or LLM improvement."""
from copy import deepcopy
import json
import unittest

from src.agent.financial_graph import compilation_phase_input
from src.agent.financial_calculation_execution import semantic_candidate_applicability
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_request_units import build_request_units, project_request_units
from tests.compiler_responsibility_review_support import (
    MARKER, ResponsibilityReviewQueue, context_suffix, proposed_responsibility_context,
)
from tests.test_narrative_output_partition import authored_pipeline
from tests.test_narrative_retry_context import prompt_json
from tests.test_planner_requirement_transport import agent_for


def compile_proposal(state, programs):
    copied = {key: deepcopy(state[key]) for key in ('request', 'routing', 'requirements', 'candidates')}
    context = proposed_responsibility_context(copied['request']['query'], copied['requirements']['answer_obligations'])
    queue = ResponsibilityReviewQueue(context, *programs)
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


class CompilerResponsibilityReviewTests(unittest.TestCase):
    def assert_unchanged(self, original, proposed):
        for key in ('semantic_program', 'semantic_program_validation', 'semantic_compilation_envelope'):
            self.assertEqual(original['compilation'][key], proposed['compilation'][key])
        for key in ('answer', 'citations', 'structured_result'):
            self.assertEqual(original['final_result']['agent_answer'][key], proposed['final_result']['agent_answer'][key])
        self.assertEqual(original['candidates'], proposed['candidates'])
        self.assertEqual(proposed['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        aggregate, = [row for row in proposed['ledger']['artifacts'] if row['kind'] == 'aggregated_answer']
        self.assertEqual(aggregate['payload']['final_answer'], proposed['final_result']['agent_answer']['answer'])

    def test_single_output_needs_no_additional_context(self):
        state, _, _ = simple_fixture()
        only = deepcopy(state['requirements']['answer_obligations'][0])
        only['request_unit_ids'] = ['request_001', 'request_002', 'request_003']
        self.assertEqual(context_suffix(proposed_responsibility_context(state['request']['query'], [only])), '')

    def test_projection_copies_only_planned_responsibility_and_exact_request(self):
        state, _, _ = simple_fixture()
        query, owners = state['request']['query'], deepcopy(state['requirements']['answer_obligations'])
        for row in owners:
            row.update({'candidate_ids': ['hidden-id'], 'accepted_answer': 'Not planning context.',
                        'status': 'ready', 'rationale': 'Diagnostic-only explanation.'})
            row['semantic_target']['unused_private'] = ['not-a-subject']
            row['scope']['extra_source'] = 'not-a-scope-field'
        before = deepcopy(owners)
        context = proposed_responsibility_context(query, owners)
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
            context = proposed_responsibility_context(query, owners)
            self.assertEqual(len(context['outputs']), 2)
            self.assertEqual(''.join(row['text'] for row in context['request_units_by_id'].values()), query)
            self.assertNotEqual(context['outputs'][0]['scope'], context['outputs'][1]['scope'])
            self.assertEqual([row['source_sections'] for row in context['outputs']], [['Section A'], ['Section B']])

    def test_independent_topics_gain_context_without_authority_or_call_changes(self):
        original, baseline_queue, programs = simple_fixture()
        proposed, queue = compile_proposal(original, programs)
        self.assert_unchanged(original, proposed)
        self.assertEqual(len(queue.prompts), len(baseline_queue.prompts) - 1)
        for index, prompt in enumerate(queue.prompts):
            scope = prompt_json(prompt, 'Compilation scope:')
            self.assertEqual(scope['active_obligation_ids'], [f'ob_{index + 1:03d}'])
            self.assertEqual([row['label'] for row in prompt_json(prompt, 'Answer obligations:')],
                             ['Intake' if index == 0 else 'Scheduling'])
            self.assertEqual([row['label'] for row in prompt_json(prompt, MARKER)['outputs']], ['Intake', 'Scheduling'])
            self.assertEqual(prompt_json(prompt, 'Source bundles, candidate cohorts, and candidates_by_id:'),
                             prompt_json(baseline_queue.prompts[index + 1], 'Source bundles, candidate cohorts, and candidates_by_id:'))
            self.assertEqual(queue.original_prompts[index], baseline_queue.prompts[index + 1])
            self.assertNotIn(MARKER, baseline_queue.prompts[index + 1].to_messages()[0].content)

    def test_retry_reuses_plan_context_without_replaying_an_accepted_answer(self):
        for coupling in ('', 'authored-coupling'):
            with self.subTest(coupling=coupling):
                original, _, programs = simple_fixture(bad_quote=True, coupling=coupling)
                proposed, queue = compile_proposal(original, programs)
                self.assert_unchanged(original, proposed)
                self.assertEqual(len(queue.prompts), 2 if coupling else 3)
                contexts = [prompt_json(prompt, MARKER) for prompt in queue.prompts]
                self.assertEqual(contexts, [contexts[0]] * len(queue.prompts))
                self.assertEqual(prompt_json(queue.prompts[-1], 'Compilation scope:')['active_obligation_ids'], ['ob_002'])
                self.assertNotIn(programs[0].narrative_bindings[0].claims[0].text, json.dumps(contexts[-1]))
                self.assertEqual(proposed['compilation']['semantic_program_retry_count'], 1)

    def test_shared_conditions_and_declared_coupling_keep_existing_meaning_and_islands(self):
        for shared, coupling in ((True, ''), (False, 'authored-coupling')):
            with self.subTest(shared=shared, coupling=coupling):
                original, baseline_queue, programs = simple_fixture(shared=shared, coupling=coupling)
                proposed, queue = compile_proposal(original, programs)
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
                    binding['claims'][0]['evidence_bindings'][0]['candidate_id'] = hidden['candidate_id']
                else:
                    binding['claims'][0]['evidence_bindings'][0]['evidence_text'] = original['request']['query'].splitlines()[0]
                # Re-project only legacy mirrors; the intentionally bad claim stays unchanged.
                for projected in ('candidate_ids', 'evidence_bindings', 'text'):
                    binding.pop(projected, None)
                invalid = SemanticCalculationProgram.model_validate(bad)
                proposed, queue = compile_proposal(attempt_state, [invalid, invalid, programs[1]])
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
        proposed, _ = compile_proposal(original, programs)
        self.assert_unchanged(original, proposed)
        answer = proposed['final_result']['agent_answer']['answer']
        self.assertEqual(answer.count('Willow arranges visits on weekdays.'), 2)
        # Honest negative control: source validation and more context do not prove better model selection.


if __name__ == '__main__':
    unittest.main()
