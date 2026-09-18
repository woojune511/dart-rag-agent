"""Authored anonymous section references; no provider or semantic accuracy claim."""

from copy import deepcopy
import json
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import httpx
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph import compilation_phase_input, planning_phase_input
from src.agent.financial_graph_models import AnswerObligation, RequirementPlannerOutput, SourceSectionReferenceV2
from src.agent.financial_request_units import build_request_units
from src.agent.financial_source_scope import (
    resolve_source_section_bindings, source_section_requirement_errors,
    source_section_applicability, source_section_allowed_for_query,
)
from src.config.llm_profiles import app_llm_routing_config
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from src.utils.openai_structured import strict_openai_schema
from tests.semantic_program_test_support import _StructuredQueueLLM
from tests.test_narrative_retry_context import prompt_json
from tests.test_openai_compiler_transport import response_body
from tests.test_planner_requirement_transport import agent_for, request
from tests.test_source_section_bindings import (
    candidate, inventory, metadata, program, requested, request_binding, section_id,
)


# Freeze these anonymous requests before changing the production contract.
RESTRICTIONS = (
    "Use 'II. Operations > 2. Channels' only; retain the limits. ",
    'Use “IV. Methods > 3. Sequence” excluding drafts. ',
    "🧭 '1. 안내 > 2. 경로'에서만 설명해 줘. ",
    "Read 'A. Process > 1. Inputs' only.\r\n",
    "Use '2.40 Channels' with  two spaces. ",
    "Use 'Path' and compare 'Path' within the same section. ",
)
PIPELINE_RESTRICTION = "Use 'II. Operations > 1. Overview' only; preserve its limits. "
PIPELINE_QUERY = PIPELINE_RESTRICTION + 'Keep the uncertainty.'


def reference(first='request_001', last='request_003', ids=None):
    return dict(first_request_unit_id=first, last_request_unit_id=last,
                section_ids=[section_id()] if ids is None else ids)


def range_owner(query=PIPELINE_QUERY, binding=None, **extra):
    return requested(binding or reference(), request_unit_ids=[u.request_unit_id for u in build_request_units(query)], **extra)


class SectionRequestCharacterizationTests(unittest.TestCase):
    def test_numbered_quoted_restrictions_are_lossless_but_can_span_units(self):
        for restriction in RESTRICTIONS:
            with self.subTest(restriction=restriction):
                query = restriction + 'Keep the uncertainty.'
                units = build_request_units(query)
                self.assertEqual(''.join(unit.text for unit in units), query)
                self.assertEqual(''.join(unit.text for unit in units[:-1]), restriction)
                for unit in units:
                    self.assertEqual(query[unit.start:unit.end], unit.text)
        self.assertEqual(len(build_request_units(RESTRICTIONS[0])), 3)
        self.assertEqual(len(build_request_units(RESTRICTIONS[4])), 1)

    def test_added_opening_quote_remains_invalid_without_repair(self):
        for restriction in RESTRICTIONS[:4]:
            with self.subTest(restriction=restriction):
                units = build_request_units(restriction)
                selected = units[-1]
                binding = request_binding("'" + selected.text.rstrip(), unit_id=selected.request_unit_id)
                owner = requested(binding, request_unit_ids=[u.request_unit_id for u in units])
                before = deepcopy(owner)
                resolved = resolve_source_section_bindings([owner], query=restriction, inventory=inventory())
                self.assertEqual([e['code'] for e in source_section_requirement_errors(resolved, restriction)],
                                 ['invalid_source_section_request'])
                self.assertEqual(owner, before)
                self.assertEqual(resolved[0]['source_section_bindings'][0]['requested_text'], binding['requested_text'])


class SectionRequestRangeTests(unittest.TestCase):
    def resolve(self, owner=None, query=PIPELINE_QUERY):
        return resolve_source_section_bindings([owner or range_owner(query)], query=query, inventory=inventory())[0]

    def test_ranges_copy_complete_numbered_quoted_and_repeated_text_without_rewriting(self):
        for restriction in RESTRICTIONS:
            with self.subTest(restriction=restriction):
                query = restriction + 'Keep the uncertainty.'
                end = build_request_units(restriction)[-1].request_unit_id
                raw = range_owner(query, reference(last=end))
                before = deepcopy(raw)
                resolved = self.resolve(raw, query)
                binding, = resolved['source_section_bindings']
                self.assertEqual(binding['requested_text'], restriction)
                self.assertEqual(binding['request_span'], [0, len(restriction)])
                self.assertEqual(source_section_requirement_errors([resolved], query), [])
                self.assertEqual(raw, before)

    def test_noninitial_single_unit_copies_only_its_original_span(self):
        query = 'Describe it. Use the operating overview. Keep the uncertainty.'
        resolved = self.resolve(range_owner(query, reference('request_002', 'request_002')), query)
        binding, = resolved['source_section_bindings']
        self.assertEqual(binding['requested_text'], 'Use the operating overview. ')
        self.assertEqual(binding['request_span'], [13, 41])
        self.assertEqual(source_section_requirement_errors([resolved], query), [])

    def test_bad_endpoints_and_unowned_intermediate_units_stay_invalid(self):
        variants = [reference('missing'), reference(last='missing'), reference('request_003', 'request_001'),
                    reference(None), reference(last=3), {'first_request_unit_id': 'request_001', 'section_ids': [section_id()]}]
        owners = [range_owner(binding=ref) for ref in variants]
        unowned = range_owner()
        unowned['request_unit_ids'].remove('request_002')
        owners.append(unowned)
        for owner in owners:
            with self.subTest(binding=owner['source_section_bindings'], owned=owner['request_unit_ids']):
                before = deepcopy(owner)
                resolved = self.resolve(owner)
                self.assertEqual([e['code'] for e in source_section_requirement_errors([resolved], PIPELINE_QUERY)],
                                 ['invalid_source_section_request'])
                self.assertFalse(source_section_allowed_for_query(candidate(), [resolved]))
                self.assertEqual(owner, before)

    def test_unknown_or_unresolved_sections_never_become_unrestricted(self):
        for ids, code in (([], 'unresolved_source_section_request'), (['missing'], 'unknown_source_section_id')):
            resolved = self.resolve(range_owner(binding=reference(ids=ids)))
            self.assertEqual([e['code'] for e in source_section_requirement_errors([resolved], PIPELINE_QUERY)], [code])
            self.assertFalse(source_section_allowed_for_query(candidate(), [resolved]))
            self.assertEqual(resolved['source_section_bindings'][0]['requested_text'], PIPELINE_RESTRICTION)

    def test_explicit_whole_path_and_filing_authority_remain_strict(self):
        query = 'II. Operations > 1. Overview'
        good = self.resolve(range_owner(query), query)
        bad = self.resolve(range_owner(query, reference(ids=[section_id('III. Notes')])), query)
        self.assertEqual(source_section_requirement_errors([good], query), [])
        self.assertEqual(source_section_requirement_errors([bad], query)[0]['code'], 'explicit_source_section_conflict')
        self.assertEqual(source_section_applicability(candidate(receipt='filing-B'), good)['state'], 'conflict')
        self.assertEqual(source_section_applicability(candidate(path='II. Operations > 1. Overview > Detail'), good)['state'], 'match')

    def test_valid_request_link_does_not_certify_the_models_section_interpretation(self):
        # Whole instructions retain their meaning for the Compiler/reviewer.
        # A known ID in an authored, semantically wrong choice is not repaired.
        resolved = self.resolve(range_owner(binding=reference(ids=[section_id('III. Notes')])))
        self.assertEqual(source_section_requirement_errors([resolved], PIPELINE_QUERY), [])
        self.assertEqual(source_section_applicability(candidate(), resolved)['state'], 'conflict')
        self.assertEqual(source_section_applicability(candidate(path='III. Notes'), resolved)['state'], 'match')

    def test_parent_and_input_range_restrictions_intersect(self):
        owner = range_owner(binding=reference(ids=[section_id('II. Operations')]),
            evidence_requirements=[dict(label='detail', source_section_bindings=[reference()])])
        good = self.resolve(owner)
        self.assertEqual(source_section_applicability(candidate(), good['evidence_requirements'][0], good)['state'], 'match')
        owner['evidence_requirements'][0]['source_section_bindings'][0]['section_ids'] = [section_id('III. Notes')]
        bad = self.resolve(owner)
        self.assertEqual(source_section_applicability(candidate(path='III. Notes'), bad['evidence_requirements'][0], bad)['state'], 'conflict')

    def test_copied_text_span_and_endpoint_tampering_is_rejected_without_repair(self):
        original = self.resolve()
        for key, value in (('requested_text', "'" + PIPELINE_RESTRICTION), ('request_span', [0, 4]),
                           ('last_request_unit_id', 'request_002'), ('request_unit_id', 'request_001')):
            changed = deepcopy(original)
            changed['source_section_bindings'][0][key] = value
            self.assertTrue(source_section_requirement_errors([changed], PIPELINE_QUERY))
        changed = deepcopy(original)
        del changed['source_section_bindings'][0]['requested_text']
        self.assertTrue(source_section_requirement_errors([changed], PIPELINE_QUERY))

    def test_generation_has_only_range_fields_at_output_and_input_owners(self):
        schema = strict_openai_schema(RequirementPlannerOutput)
        self.assertNotIn('SourceSectionBindingV1', schema['$defs'])
        props = schema['$defs']['SourceSectionReferenceV2']['properties']
        self.assertEqual(set(props), {'first_request_unit_id', 'last_request_unit_id', 'section_ids'})
        self.assertEqual(set(schema['$defs']['SourceSectionReferenceV2']['required']), set(props))
        self.assertFalse(schema['$defs']['SourceSectionReferenceV2']['additionalProperties'])
        local_validator = Draft202012Validator(RequirementPlannerOutput.model_json_schema())
        for kind in ('direct_value', 'derived_value', 'narrative'):
            raw = {**range_owner(), 'kind': kind}
            if kind != 'direct_value':
                raw['evidence_requirements'] = [dict(label='detail', source_section_bindings=[reference()])]
            parsed = RequirementPlannerOutput(obligations=[raw])
            Draft202012Validator(schema).validate(parsed.model_dump())
            for location in ('output', 'input') if kind != 'direct_value' else ('output',):
                changed = deepcopy(raw)
                target = changed if location == 'output' else changed['evidence_requirements'][0]
                target['source_section_bindings'] = [request_binding()]
                self.assertFalse(local_validator.is_valid(dict(obligations=[changed])))
                with self.assertRaises(ValidationError):
                    RequirementPlannerOutput(obligations=[changed])

    def test_model_cannot_supply_code_owned_text_span_or_resolutions(self):
        for key, value in (('requested_text', PIPELINE_RESTRICTION), ('request_span', [0, 1]),
                           ('resolved_sections', []), ('inventory_fingerprint', 'invented'),
                           ('request_unit_id', 'request_001')):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                SourceSectionReferenceV2.model_validate({**reference(), key: value})

    def test_source_group_roundtrip_and_copy_keep_range_ownership(self):
        parsed = RequirementPlannerOutput(obligations=[range_owner(evidence_mode='source_defined_group')])
        self.assertEqual(RequirementPlannerOutput.model_validate(parsed.model_dump()), parsed)
        owner = parsed.obligations[0]
        self.assertEqual(owner.source_section_bindings, owner.evidence_requirements[0].source_section_bindings)
        self.assertIsNot(owner.source_section_bindings[0], owner.evidence_requirements[0].source_section_bindings[0])
        resolved = self.resolve(owner.model_dump())
        self.assertEqual(source_section_requirement_errors([resolved], PIPELINE_QUERY), [])
        self.assertEqual(resolved['source_section_bindings'], resolved['evidence_requirements'][0]['source_section_bindings'])
        # Explicit historical/internal parsing still retains V1; generation does not.
        self.assertEqual(AnswerObligation.model_validate(requested()).source_section_bindings[0].requested_text, 'operating overview')

    def test_planning_compilation_final_answer_and_ledger_keep_the_same_range(self):
        value = RequirementPlannerOutput(obligations=[range_owner()])
        llm = _StructuredQueueLLM(value, program(owner_id='ob_001'))
        agent, state = agent_for(llm), request(PIPELINE_QUERY)
        state['request']['report_scope'] = {'rcept_no': 'filing-A'}
        agent.vsm = SimpleNamespace(bm25_metadatas=[metadata()])
        state['requirements'] = agent._plan_answer_obligation_program(planning_phase_input(state))
        self.assertEqual(state['requirements']['semantic_plan']['requirement_errors'], [])
        owner, = state['requirements']['answer_obligations']
        before = deepcopy(owner)
        state['candidates'] = dict(semantic_candidate_catalog=[candidate()], semantic_source_candidates=[])
        state['compilation'] = agent._compile_semantic_calculation_program(compilation_phase_input(state))
        state.update(agent._execute_numeric_phase(state))
        state.update(agent._assemble_final_phase(state))
        state.update(agent._assemble_ledger_phase(state))
        self.assertEqual(llm.models, ['RequirementPlannerOutput', 'CompilerResponseV2'])
        self.assertEqual(prompt_json(llm.prompts[1], 'Answer obligations:')[0]['source_section_bindings'], owner['source_section_bindings'])
        self.assertEqual(state['final_result']['agent_answer']['structured_result']['status'], 'ok')
        self.assertEqual(state['ledger']['task_artifact_trace']['integrity_status'], 'ok')
        self.assertEqual(owner, before)
        for key, value in (('first_request_unit_id', 'request_002'), ('last_request_unit_id', 'request_004'),
                           ('requested_text', 'rewritten'), ('section_ids', [section_id('III. Notes')])):
            changed = deepcopy(owner)
            changed['source_section_bindings'][0][key] = value
            compiled = state['compilation']
            result = execute_semantic_calculation_program(program=compiled['semantic_program'], obligations=[changed],
                candidate_catalog=[candidate()], query=PIPELINE_QUERY,
                compilation_envelope=compiled['semantic_compilation_envelope'], require_compilation_envelope=True)
            self.assertEqual(result['validation']['errors'][0]['code'], 'execution_content_mismatch')

    def test_invalid_range_blocks_only_its_island_with_no_compiler_retry(self):
        valid, invalid = self.resolve(), self.resolve(range_owner(binding=reference(last='missing')))
        invalid['obligation_id'] = 'invalid'
        llm = _StructuredQueueLLM(program())
        compiled = agent_for(llm)._compile_semantic_calculation_program(dict(query=PIPELINE_QUERY,
            answer_obligations=[invalid, valid], semantic_candidate_catalog_prebuilt=True,
            semantic_source_candidates=[], semantic_candidate_catalog=[candidate()]))
        self.assertEqual(llm.models, ['CompilerResponseV2'])
        self.assertEqual(compiled['semantic_program_validation']['missing_obligation_ids'], ['invalid'])
        self.assertEqual([i['retry_count'] for i in compiled['planner_debug_trace']['compilation_islands']], [0, 0])

    def test_compiler_retry_preserves_full_original_restriction(self):
        owner = self.resolve()
        before = deepcopy(owner)
        llm = _StructuredQueueLLM(program(quote='Invented evidence.'), program())
        compiled = agent_for(llm)._compile_semantic_calculation_program(dict(query=PIPELINE_QUERY,
            answer_obligations=[owner], semantic_candidate_catalog_prebuilt=True,
            semantic_source_candidates=[], semantic_candidate_catalog=[candidate()]))
        self.assertEqual(llm.models, ['CompilerResponseV2', 'CompilerResponseV2'])
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        for prompt in llm.prompts:
            self.assertEqual(prompt_json(prompt, 'Answer obligations:')[0]['source_section_bindings'], owner['source_section_bindings'])
        self.assertEqual(owner, before)

    def test_real_sdk_sends_only_range_schema_and_preserves_returned_ids(self):
        value = RequirementPlannerOutput(obligations=[range_owner()])
        agent = agent_for(None)
        agent.vsm = SimpleNamespace(bm25_metadatas=[metadata()])
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        route = dict(app_llm_routing_config('openai')['llm_routes']['default'], api_key='offline-placeholder')
        calls = []

        def send(http_request, **kwargs):
            calls.append(json.loads(http_request.content))
            body = response_body(value.model_dump())
            body['model'] = route['model']
            return httpx.Response(200, request=http_request, json=body)

        with patch.object(socket.socket, 'connect', side_effect=AssertionError('Network forbidden')), \
             patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('Network forbidden')), \
             patch.object(httpx.Client, 'send', side_effect=send):
            agent.llm = agent._create_chat_model(route, phase='requirement_planning')
            planned = agent._plan_answer_obligation_program(planning_phase_input(request(PIPELINE_QUERY)))
        self.assertEqual(planned['semantic_plan']['requirement_errors'], [])
        self.assertEqual(len(calls), 1)
        schema = calls[0]['text']['format']['schema']
        Draft202012Validator(schema).validate(value.model_dump())
        self.assertNotIn('SourceSectionBindingV1', schema['$defs'])
        original, = value.obligations[0].source_section_bindings
        actual, = planned['answer_obligations'][0]['source_section_bindings']
        self.assertEqual({key: actual[key] for key in original.model_dump()}, original.model_dump())
        self.assertEqual(actual['requested_text'], PIPELINE_RESTRICTION)


if __name__ == '__main__':
    unittest.main()
