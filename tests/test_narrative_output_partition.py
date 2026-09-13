"""Check planner policy delivery and characterize output overlap.

All plans/claims are authored, not model inference or semantic acceptance. These
tests preserve distinct source facts and expose remaining assembly limitations.
No benchmark artifacts, provider clients, or semantic-dedup heuristic are used.
"""
from copy import deepcopy
from tests.narrative_address_test_support import model_program
from types import SimpleNamespace
import json
import unittest

from src.agent.financial_graph import planning_phase_input, compilation_phase_input
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_program_projection import render_narrative_claim
from src.agent.financial_request_units import build_request_units, project_request_units
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_narrative_claim_grounding import claim
from tests.test_narrative_retry_context import prompt_json
from tests.test_planner_requirement_transport import agent_for, request


def catalog_for_bodies(bodies, year=2051):
    agent = agent_for(_StructuredQueueLLM())
    documents = [(SimpleNamespace(page_content=body, metadata={
        'chunk_uid': f'source_{index}', 'source_document_id': f'anonymous_report_{year}',
        'company': 'Issuer', 'corp_name': 'Issuer', 'year': year,
        'section': 'Context', 'section_title': 'Context'}), 0.0) for index, body in enumerate(bodies)]
    sources = agent._semantic_source_candidates_for_state({'retrieved_docs': documents, 'seed_retrieved_docs': []})
    catalog = agent._semantic_candidate_catalog_for_state({}, source_candidates=sources)
    return {'semantic_source_candidates': sources, 'semantic_candidate_catalog': catalog}


def authored_pipeline(query, bodies, owners, response_specs, *, year=2051, coupling=''):
    """owner=(subject,label,refs); claim=(owner index,source index,subject,text,quote)."""
    candidates = catalog_for_bodies(bodies, year)
    ids = [next(row['candidate_id'] for row in candidates['semantic_candidate_catalog']
                if body in row['source_text']) for body in bodies]
    plan = RequirementPlannerOutput.model_validate({'obligations': [
        {'obligation_id': f'raw_{index}', 'kind': 'narrative', 'label': label,
         'request_unit_ids': refs, 'semantic_target': {'local_subjects': [subject]},
         'evidence_mode': 'source_defined_group', 'coupling_key': coupling}
        for index, (subject, label, refs) in enumerate(owners, 1)]})
    programs = []
    for specs in response_specs:
        bindings = {}
        for index, source_index, subject, text, quote in specs:
            oid = f'ob_{index:03d}'
            bindings.setdefault(oid, {'obligation_id': oid, 'claims': []})['claims'].append(
                claim(subject, text, ids[source_index], quote, source_requirement_id=f'{oid}:req_001'))
        programs.append(model_program({'narrative_bindings': list(bindings.values())}, candidates['semantic_candidate_catalog']))
    llm = _StructuredQueueLLM(plan, *programs)
    agent, state = agent_for(llm), request(query)
    state['request']['report_scope']['year'] = year
    before_candidates = deepcopy(candidates)
    state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
    state['candidates'] = candidates
    before = deepcopy(state)
    compiled = agent._compile_semantic_calculation_program(compilation_phase_input(state))
    assert state == before
    state['compilation'] = compiled
    state.update(agent._execute_numeric_phase(state))
    state.update(agent._assemble_final_phase(state))
    state.update(agent._assemble_ledger_phase(state))
    assert state['candidates'] == before_candidates
    return state, llm, programs


class NarrativeOutputPartitionTests(unittest.TestCase):
    def assert_ready(self, state):
        self.assertEqual(state['compilation']['semantic_program_validation']['status'], 'ready')
        answer = state['final_result']['agent_answer']
        self.assertEqual(answer['structured_result']['status'], 'ok')
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        aggregate, = [row for row in state['ledger']['artifacts'] if row['kind'] == 'aggregated_answer']
        self.assertEqual(aggregate['payload']['final_answer'], answer['answer'])
        self.assertEqual(aggregate['payload']['structured_result'], answer['structured_result'])
        return answer['answer']

    def test_planner_policy_attaches_qualifiers_without_merging_independent_same_subject_topics(self):
        intake = 'Aspen accepts requests only after consent.'
        schedule = 'Aspen schedules visits on weekdays.'
        query = 'Describe Aspen intake.\nInclude its consent condition.\nExplain Aspen visit scheduling.'
        state, llm, _ = authored_pipeline(query, [intake, schedule],
            [('Aspen', 'Intake', ['request_001', 'request_002']),
             ('Aspen', 'Scheduling', ['request_003'])],
            [[(1, 0, 'Aspen', intake, intake)], [(2, 1, 'Aspen', schedule, schedule)]])
        self.assertEqual(self.assert_ready(state), intake + ' ' + schedule)
        self.assertEqual(llm.models, ['RequirementPlannerOutput', 'SemanticCalculationProgram',
                                     'SemanticCalculationProgram'])
        prompt = llm.prompts[0].to_messages()[0].content
        # This checks delivery of the policy, not that a model follows it.
        self.assertIn('같은 설명을 한정하는 조건은 그 설명의 narrative obligation에 함께 담고', prompt)
        self.assertIn('관련 request_unit_ids를 모두 연결하세요', prompt)
        self.assertIn('독립적으로 요청된 설명 주제마다 obligation을 보존합니다', prompt)
        self.assertIn('같은 주어·문장·request unit을 공유한다는 이유로 독립적인 설명을 합치지 마세요', prompt)
        self.assertIn('출력 개수를 미리 정하지 마세요', prompt)
        units = build_request_units(query)
        self.assertEqual(prompt_json(llm.prompts[0], 'Request units:'), project_request_units(units))
        obligations = state['requirements']['answer_obligations']
        self.assertEqual([row['request_unit_ids'] for row in obligations],
                         [['request_001', 'request_002'], ['request_003']])
        for index, compiled_prompt in enumerate(llm.prompts[1:]):
            scope = prompt_json(compiled_prompt, 'Compilation scope:')
            self.assertEqual(scope['active_obligation_ids'], [f'ob_{index + 1:03d}'])
            self.assertEqual(scope['request_units_by_id'], project_request_units(units, [obligations[index]]))

    def test_shared_qualifier_reaches_each_independent_output_without_creating_an_extra_output(self):
        bodies = ['Aspen receives requests only after consent.', 'Birch schedules visits only after consent.']
        query = 'Describe Aspen intake.\nExplain Birch scheduling.\nInclude the consent condition for both.'
        refs = [['request_001', 'request_003'], ['request_002', 'request_003']]
        state, llm, _ = authored_pipeline(query, bodies,
            [('Aspen', 'Intake', refs[0]), ('Birch', 'Scheduling', refs[1])],
            [[(1, 0, 'Aspen', bodies[0], bodies[0])], [(2, 1, 'Birch', bodies[1], bodies[1])]])
        self.assertEqual(self.assert_ready(state), ' '.join(bodies))
        self.assertEqual(len(llm.prompts), 3)  # Authored plan: one planner and two independent islands.
        self.assertIn('공통 조건은 관련 출력 모두에 연결하세요', llm.prompts[0].to_messages()[0].content)
        obligations = state['requirements']['answer_obligations']
        self.assertEqual([row['request_unit_ids'] for row in obligations], refs)
        units = project_request_units(build_request_units(query))
        for index, compiled_prompt in enumerate(llm.prompts[1:]):
            scope = prompt_json(compiled_prompt, 'Compilation scope:')
            self.assertEqual(scope['active_obligation_ids'], [f'ob_{index + 1:03d}'])
            self.assertEqual(scope['request_units_by_id'], {ref: units[ref] for ref in refs[index]})

    def test_coarse_and_split_plans_share_sources_but_split_claims_may_overlap(self):
        for subject, year in (('Aspen', 2051), ('Morrow', 2063), ('나래', 2074)):
            with self.subTest(subject=subject, year=year):
                role, limit = f'{subject} receives requests.', f'{subject} does not repair devices.'
                full = role + ' ' + limit
                query = f'Describe {subject} role.\nInclude {subject} operating limits.'
                coarse, coarse_llm, _ = authored_pipeline(query, [full],
                    [(subject, 'Role with limits', ['request_001', 'request_002'])],
                    [[(1, 0, subject, full, full)]], year=year)
                split, split_llm, _ = authored_pipeline(query, [full],
                    [(subject, 'Role', ['request_001']), (subject, 'Limits', ['request_002'])],
                    [[(1, 0, subject, full, full)], [(2, 0, subject, limit, limit)]], year=year)
                self.assertEqual(self.assert_ready(coarse), full)
                self.assertEqual(self.assert_ready(split), full + ' ' + limit)
                self.assertEqual(coarse['candidates'], split['candidates'])
                self.assertEqual(len(coarse_llm.prompts), 2)
                self.assertEqual(len(split_llm.prompts), 3)
                self.assertEqual(len(split['requirements']['answer_obligations']), 2)
                # Active obligations stay local; sibling planning context grants no authority.
                first_scope = prompt_json(split_llm.prompts[1], 'Compilation scope:')
                self.assertEqual(first_scope['active_obligation_ids'], ['ob_001'])
                self.assertEqual(list(first_scope['request_units_by_id']), ['request_001'])
                self.assertEqual([row['label'] for row in prompt_json(split_llm.prompts[1], 'Answer obligations:')], ['Role'])
                self.assertIn(query, split_llm.prompts[1].to_messages()[0].content)

    def test_same_candidate_and_exact_quote_can_support_two_distinct_required_facts(self):
        role, limit = 'Aspen receives requests.', 'Aspen does not repair devices.'
        full = role + ' ' + limit
        state, _, _ = authored_pipeline('Describe Aspen role.\nState its limits.', [full],
            [('Aspen', 'Role', ['request_001']), ('Aspen', 'Limits', ['request_002'])],
            [[(1, 0, 'Aspen', role, full)], [(2, 0, 'Aspen', limit, full)]])
        self.assertEqual(self.assert_ready(state), full)
        rows = state['compilation']['semantic_program_validation']['valid_narrative_bindings']
        evidence = [row['claim_readings'][0]['evidence'][0] for row in rows]
        for key in ('candidate_id', 'source_bundle_id', 'evidence_text', 'source_span'):
            self.assertEqual(evidence[0][key], evidence[1][key])
        self.assertNotEqual(rows[0]['claims'][0]['text'], rows[1]['claims'][0]['text'])
        self.assertEqual(len(state['numeric_result']['execution']['selected_candidate_ids']), 1)
        self.assertEqual(len(state['numeric_result']['execution']['outputs_by_obligation']), 2)

    def test_shared_request_source_and_raw_text_do_not_make_different_subjects_redundant(self):
        full = 'Aspen may start after consent. Birch may start after consent.'
        state, llm, _ = authored_pipeline('Describe Aspen and Birch starting conditions.', [full],
            [('Aspen', 'Aspen condition', ['request_001']), ('Birch', 'Birch condition', ['request_001'])],
            [[(1, 0, 'Aspen', 'may start after consent.', full)],
             [(2, 0, 'Birch', 'may start after consent.', full)]])
        answer = self.assert_ready(state)
        self.assertEqual(answer, 'Aspen: may start after consent. Birch: may start after consent.')
        self.assertEqual(len(llm.prompts), 3)
        bindings = state['compilation']['semantic_program']['narrative_bindings']
        self.assertEqual(bindings[0]['claims'][0]['text'], bindings[1]['claims'][0]['text'])
        self.assertNotEqual(bindings[0]['text'], bindings[1]['text'])

    def test_exact_duplicate_claims_are_preserved_within_and_across_outputs(self):
        fact = 'Aspen receives requests.'
        for across in (False, True):
            with self.subTest(across_outputs=across):
                owners = [('Aspen', 'First view', ['request_001'])]
                first = (1, 0, 'Aspen', fact, fact)
                if across:
                    owners.append(('Aspen', 'Second view', ['request_001']))
                    responses = [[first], [(2, 0, 'Aspen', fact, fact)]]
                else:
                    responses = [[first, first]]
                state, _, _ = authored_pipeline('Describe Aspen.', [fact], owners, responses)
                self.assertEqual(self.assert_ready(state), fact + ' ' + fact)
                self.assertEqual(len(state['numeric_result']['execution']['selected_candidate_ids']), 1)
                # Known overlap: ready is not a semantic minimality guarantee.

    def test_paraphrased_contained_condition_is_not_an_exact_display_duplicate(self):
        full = 'Aspen receives requests. Aspen acts only after consent.'
        broad = 'Aspen receives requests and acts only after consent.'
        detail = 'Aspen does not act without consent.'
        state, _, _ = authored_pipeline('Describe Aspen role.\nState the starting condition.', [full],
            [('Aspen', 'Role', ['request_001']), ('Aspen', 'Start condition', ['request_002'])],
            [[(1, 0, 'Aspen', broad, full)], [(2, 0, 'Aspen', detail, full)]])
        self.assertEqual(self.assert_ready(state), broad + ' ' + detail)
        self.assertNotIn(detail, broad)
        self.assertNotEqual(broad, detail)

    def test_declared_coupling_reduces_calls_but_does_not_mechanically_resolve_overlap(self):
        full, limit = 'Aspen receives requests. Aspen waits for consent.', 'Aspen waits for consent.'
        state, llm, _ = authored_pipeline('Describe Aspen role.\nState its condition.', [full],
            [('Aspen', 'Role', ['request_001']), ('Aspen', 'Condition', ['request_002'])],
            [[(1, 0, 'Aspen', full, full), (2, 0, 'Aspen', limit, limit)]], coupling='declared-link')
        self.assertEqual(self.assert_ready(state), full + ' ' + limit)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(prompt_json(llm.prompts[1], 'Compilation scope:')['active_obligation_ids'], ['ob_001', 'ob_002'])

    def test_quote_retry_preserves_accepted_overlapping_reading_and_owner_scope(self):
        full, limit = 'Aspen receives requests. Aspen waits for consent.', 'Aspen waits for consent.'
        state, llm, programs = authored_pipeline('Describe Aspen role.\nState its condition.', [full],
            [('Aspen', 'Role', ['request_001']), ('Aspen', 'Condition', ['request_002'])],
            [[(1, 0, 'Aspen', full, full)], [(2, 0, 'Aspen', limit, 'Unwritten evidence.')],
             [(2, 0, 'Aspen', limit, limit)]])
        self.assertEqual(self.assert_ready(state), full + ' ' + limit)
        self.assertEqual(len(llm.prompts), 4)
        selected = state['compilation']['semantic_program']['narrative_bindings'][0]
        self.assertEqual(json.dumps(selected, sort_keys=True),
                         json.dumps(programs[0].model_dump()['narrative_bindings'][0], sort_keys=True))
        scope = prompt_json(llm.prompts[-1], 'Compilation scope:')
        self.assertEqual(scope['active_obligation_ids'], ['ob_002'])
        self.assertEqual(list(scope['request_units_by_id']), ['request_002'])
        marker = 'Source bundles, candidate cohorts, and candidates_by_id:'
        self.assertEqual(prompt_json(llm.prompts[-2], marker), prompt_json(llm.prompts[-1], marker))


if __name__ == '__main__':
    unittest.main()
