"""Current source-address/shared-subject contract, with no provider calls."""

from copy import deepcopy
import json
import unittest

from pydantic import ValidationError
from src.agent.financial_calculation_execution import validate_semantic_calculation_program, execute_semantic_calculation_program
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_graph_calculation import _semantic_candidate_visibility, _semantic_candidate_cohorts
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.narrative_address_test_support import selection
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import source, claim
from tests.test_narrative_retry_context import prompt_json


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


class AddressedNarrativeCompilerTests(unittest.TestCase):
    query = "Describe the schedule and sample handling."

    def setUp(self):
        self.body = "Pine Workshop schedules inspections. It checks tools. It stores samples."
        self.catalog = [source("note", self.body), source("foreign", "Quartz has 93 stations.")]
        self.owners = [_obligation("activity", "narrative", self.query)]
        self.subject = {"subject_binding_id": "s1", "subject": "Pine Workshop", "evidence_selections": [
            selection(self.catalog, "note", "Pine Workshop schedules inspections.")]}
        self.program = {"narrative_bindings": [{"obligation_id": "activity", "subject_bindings": [self.subject],
            "claims": [{"subject_binding_id": "s1", "text": text, "fact_evidence_selections": [
                selection(self.catalog, "note", quote)]} for text, quote in (
                    ("Schedules inspections.", "Pine Workshop schedules inspections."),
                    ("Checks tools.", "It checks tools."), ("Stores samples.", "It stores samples."))]}]}

    def validate(self, program=None, *, catalog=None, visibility=None):
        catalog = self.catalog if catalog is None else catalog
        visibility = visibility or _semantic_candidate_visibility(catalog,
            visible_candidate_ids=[c["candidate_id"] for c in catalog],
            candidate_ids_by_owner={"activity": ["note"]})
        program = self.program if program is None else program
        validation = validate_semantic_calculation_program(program=program, candidate_catalog=catalog,
            obligations=self.owners, query=self.query, candidate_visibility=visibility, require_narrative_claims=True)
        return validation, CompilationEnvelopeV2.create(program=program, validation=validation,
            visibility=visibility, candidate_catalog=catalog, obligations=self.owners, query=self.query)

    def execute(self, program=None):
        program = self.program if program is None else program
        validation, envelope = self.validate(program)
        result = execute_semantic_calculation_program(program=program, candidate_catalog=self.catalog,
            obligations=self.owners, query=self.query, compilation_envelope=envelope, require_compilation_envelope=True)
        return validation, result

    def test_shared_subject_support_is_explicit_and_all_facts_survive(self):
        before = deepcopy((self.catalog, self.program))
        validation, result = self.execute()
        self.assertEqual(validation["status"], "ready", validation["errors"])
        self.assertEqual(result["status"], "ok")
        readings = result["outputs"][0]["claim_readings"]
        self.assertEqual(len(readings), 3)
        self.assertEqual(readings[-1]["evidence"][0]["evidence_text"], "It stores samples.")
        self.assertEqual(readings[-1]["subject_evidence"][0]["evidence_text"], "Pine Workshop schedules inspections. ")
        self.assertEqual((self.catalog, self.program), before)

    def test_list_quote_cannot_be_reformatted_by_model(self):
        self.body = "Pine Workshop visits sites.-Purpose: inspect tools.-Schedule: weekly."
        self.catalog = [source("note", self.body)]
        link = selection(self.catalog, "note", self.body)
        self.program["narrative_bindings"][0].update(subject_bindings=[{**self.subject, "evidence_selections": [link]}],
            claims=[{"subject_binding_id": "s1", "text": "Visits weekly to inspect tools.", "fact_evidence_selections": [link]}])
        validation, result = self.execute()
        self.assertEqual(validation["status"], "ready", validation["errors"])
        self.assertEqual(result["outputs"][0]["claim_readings"][0]["evidence"][0]["evidence_text"], self.body)
        bad = deepcopy(self.program)
        bad["narrative_bindings"][0]["claims"][0]["fact_evidence_selections"][0]["evidence_text"] = self.body.replace("-", "\n-")
        with self.assertRaises(ValidationError):
            SemanticCalculationProgram.model_validate(bad)

    def test_current_schema_and_executor_reject_old_quote_claims(self):
        old = {"narrative_bindings": [{"obligation_id": "activity", "claims": [
            claim("Pine Workshop", "Schedules inspections.", "note", self.body)]}]}
        with self.assertRaises(ValidationError):
            SemanticCalculationProgram.model_validate(old)
        validation, execution = self.execute(old)
        self.assertIn("missing_narrative_subject_bindings", {e["code"] for e in validation["errors"]})
        self.assertEqual(execution["outputs"], [])

    def test_schema_hides_parent_projection_and_requires_source_addresses(self):
        schema = SemanticCalculationProgram.model_json_schema()["$defs"]
        self.assertIn("subject_bindings", schema["SemanticProgramNarrativeBinding"]["required"])
        self.assertNotIn("text", schema["SemanticProgramNarrativeBinding"]["properties"])
        self.assertNotIn("evidence_text", schema["SemanticProgramNarrativeClaimEvidence"]["properties"])
        for key in ("surface_id", "first_piece_id", "last_piece_id"):
            self.assertIn(key, schema["SemanticProgramNarrativeClaimEvidence"]["required"])
        modeled = SemanticCalculationProgram.model_validate(self.program).model_dump()
        self.assertEqual(modeled["narrative_bindings"][0]["candidate_ids"], ["note"])
        self.assertEqual(self.validate(modeled)[0]["status"], "ready")

    def test_no_implicit_subject_inheritance_or_other_owner_registry(self):
        for key in ("", "s2", "other:s1"):
            bad = deepcopy(self.program)
            bad["narrative_bindings"][0]["claims"][-1]["subject_binding_id"] = key
            self.assertIn("unknown_narrative_subject_binding", {e["code"] for e in self.validate(bad)[0]["errors"]})

    def test_shared_subject_registry_does_not_bypass_owner_or_usage_checks(self):
        bad = deepcopy(self.program)
        subject = bad['narrative_bindings'][0]['subject_bindings'][0]
        subject.update(subject='Quartz', evidence_selections=[
            selection(self.catalog, 'foreign', 'Quartz has 93 stations.')])
        self.assertIn('candidate_not_exposed_to_compiler', {e['code'] for e in self.validate(bad)[0]['errors']})
        unused = deepcopy(self.program)
        unused['narrative_bindings'][0]['subject_bindings'].append({**self.subject, 'subject_binding_id': 'unused'})
        self.assertIn('unused_narrative_subject_binding', {e['code'] for e in self.validate(unused)[0]['errors']})
        duplicate = deepcopy(self.program)
        duplicate['narrative_bindings'][0]['subject_bindings'].append(deepcopy(self.subject))
        with self.assertRaises(ValidationError):
            SemanticCalculationProgram.model_validate(duplicate)

    def test_subject_only_numbers_and_other_fact_ranges_do_not_grant_authority(self):
        self.catalog[0].update(source_text=self.body + " Pine Workshop has 93 stations.",
            source_bundle_text=self.body + " Pine Workshop has 93 stations.")
        link = selection(self.catalog, "note", "Pine Workshop has 93 stations.")
        binding = self.program["narrative_bindings"][0]
        binding["subject_bindings"][0]["evidence_selections"] = [link]
        for row, quote in zip(binding["claims"], ("Pine Workshop schedules inspections.", "It checks tools.", "It stores samples.")):
            row["fact_evidence_selections"] = [selection(self.catalog, "note", quote)]
        binding["claims"][0]["text"] = "Schedules 93 inspections."
        errors = self.validate()[0]["errors"]
        self.assertIn("ungrounded_narrative_claim_number", {e["code"] for e in errors})
        binding["claims"][-1]["fact_evidence_selections"].append(link)
        self.assertIn("ungrounded_narrative_claim_number", {e["code"] for e in self.validate()[0]["errors"]})

    def test_hidden_foreign_stale_and_reversed_addresses_are_rejected(self):
        for link, code in ((selection(self.catalog, "foreign", "Quartz has 93 stations."), "candidate_not_exposed_to_compiler"),
            ({**selection(self.catalog, "note", self.body), "candidate_id": "invented"}, "unknown_narrative_candidate"),
            ({**selection(self.catalog, "note", self.body), "surface_id": "stale"}, "unknown_narrative_surface"),
            ({**selection(self.catalog, "note", self.body), "first_piece_id": "p3", "last_piece_id": "p1"}, "reversed_narrative_selection")):
            bad = deepcopy(self.program)
            bad["narrative_bindings"][0]["claims"][0]["fact_evidence_selections"] = [link]
            self.assertIn(code, {e["code"] for e in self.validate(bad)[0]["errors"]})

    def test_prompt_surface_ids_match_validator_with_attached_context(self):
        self.catalog[0]["source_contexts"] = [{"context_id": "heading", "relation": "ancestor_heading",
            "source_text": "Pine Workshop", "source_span": [7, 20]}]
        link = selection(self.catalog, "note", "Pine Workshop", context_id="heading")
        self.program["narrative_bindings"][0]["subject_bindings"][0]["evidence_selections"] = [link]
        self.assertEqual(self.validate()[0]["status"], "ready")
        payload = FinancialAgent._semantic_program_prompt_payload(self.catalog, _semantic_candidate_cohorts(self.catalog, self.owners))
        self.assertEqual(payload["schema"], "semantic_program_candidate_payload_v8")
        heading = next(fragment for row in payload["source_readings"]
            for fragment in row["enclosing_contexts"] if fragment["context_id"] == "heading")
        self.assertEqual(heading["surface_id"], link["surface_id"])
        self.assertEqual(heading["pieces"][0]["text"], "Pine Workshop")
        self.assertNotIn("source_text", heading)

    def test_retry_repairs_only_failed_owner_and_keeps_subjects_and_other_bytes(self):
        bad = deepcopy(self.program)
        bad["narrative_bindings"][0]["claims"][-1]["fact_evidence_selections"][0]["last_piece_id"] = "missing"
        accepted = SemanticCalculationProgram(direct_bindings=[{"obligation_id": "size", "candidate_id": "size-cell"}])
        llm = _StructuredQueueLLM(accepted, SemanticCalculationProgram.model_validate(bad),
            SemanticCalculationProgram.model_validate(self.program))
        state = _case_state({"question": self.query, "obligations": [_obligation("size", "direct_value", "Size"), *self.owners]},
            [_candidate("size-cell", 12), *self.catalog])
        before = deepcopy(state)
        result = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(result["semantic_program_validation"]["status"], "ready", result["semantic_program_validation"]["errors"])
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(canonical(result["semantic_program"]["direct_bindings"]), canonical(accepted.model_dump()["direct_bindings"]))
        marker = "Source bundles, candidate cohorts, and candidates_by_id:"
        self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))
        feedback = prompt_json(llm.prompts[2], "재시도 피드백(없으면 -):")
        drafts = feedback["unvalidated_compiler_response"]["outputs"]
        self.assertEqual(list(drafts), [self.owners[0]["obligation_id"]])
        self.assertEqual(next(iter(drafts.values()))["result"]["subjects"][0]["subject"], "Pine Workshop")
        self.assertNotIn("source_selection_check", canonical(drafts).decode())
        self.assertNotIn("subject_selection_invariant", feedback["repair_contract"])
        self.assertNotIn("size-cell", canonical(drafts).decode())
        self.assertEqual(state, before)

    def test_catalog_mutation_after_validation_is_blocked_before_execution(self):
        _, envelope = self.validate()
        changed = deepcopy(self.catalog)
        changed[0]["source_text"] += " changed"
        result = execute_semantic_calculation_program(program=self.program, candidate_catalog=changed,
            obligations=self.owners, query=self.query, compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(result["outputs"], [])
        self.assertIn("execution_content_mismatch", str(result))


if __name__ == "__main__":
    unittest.main()
