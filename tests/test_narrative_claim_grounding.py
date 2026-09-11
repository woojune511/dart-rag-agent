"""Claim-local source authority, not a natural-language entailment oracle."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM


def source(candidate_id, text, **extra):
    return {**_candidate(candidate_id, 0), "kind": "narrative", "raw_value": "",
        "raw_unit": "", "normalized_value": None, "normalized_unit": "UNKNOWN",
        "source_text": text, "source_bundle_text": text, "document_company": "Parent",
        **extra}


def claim(subject, text, candidate_id, quote, **evidence):
    return {"subject": subject, "text": text, "evidence_bindings": [{
        "candidate_id": candidate_id, "evidence_text": quote, **evidence}]}


class NarrativeClaimGroundingTests(unittest.TestCase):
    def setUp(self):
        self.catalog = [source("a", "Birch sells through partners. Birch serves 17 regions."),
            source("b", "Cedar uses direct delivery. Cedar serves 23 regions."),
            source("hidden", "Parent uses every route.")]
        self.owners = [_obligation("routes", "narrative", "Describe routes.")]
        self.program = {"narrative_bindings": [{"obligation_id": "routes", "claims": [
            claim("Birch", "Birch sells through partners.", "a", "Birch sells through partners."),
            claim("Cedar", "Cedar uses direct delivery.", "b", "Cedar uses direct delivery."),
        ]}]}
        self.visibility = _semantic_candidate_visibility(self.catalog,
            visible_candidate_ids=["a", "b"], candidate_ids_by_owner={"routes": ["a", "b"]})

    def validate(self, program=None, catalog=None):
        return validate_semantic_calculation_program(program=program or self.program,
            candidate_catalog=catalog or self.catalog, obligations=self.owners,
            query="Describe routes.", candidate_visibility=self.visibility,
            require_narrative_claims=True)

    def codes(self, program=None, catalog=None):
        return {item["code"] for item in self.validate(program, catalog)["errors"]}

    def test_schema_and_projection_have_one_text_and_evidence_writer(self):
        schema = SemanticCalculationProgram.model_json_schema()
        properties = schema["$defs"]["SemanticProgramNarrativeBinding"]["properties"]
        self.assertIn("claims", properties)
        self.assertIn("claims", schema["$defs"]["SemanticProgramNarrativeBinding"]["required"])
        self.assertEqual(properties["claims"]["minItems"], 1)
        self.assertNotIn("text", properties)
        self.assertNotIn("evidence_bindings", properties)
        original = deepcopy(self.program)
        modeled = SemanticCalculationProgram.model_validate(self.program).model_dump()
        row = modeled["narrative_bindings"][0]
        self.assertEqual(row["candidate_ids"], ["a", "b"])
        self.assertEqual(row["text"], "Birch sells through partners. Cedar uses direct delivery.")
        self.assertEqual(self.validate()["status"], "ready")
        self.assertEqual(self.validate(modeled)["status"], "ready")
        self.assertEqual(self.program, original)

    def test_issuer_metadata_cannot_ground_claim_subject(self):
        for entity in ("Parent", "Unmentioned entity"):
            with self.subTest(entity=entity):
                program = deepcopy(self.program)
                row = program["narrative_bindings"][0]["claims"][0]
                row.update(subject=entity, text=f"{entity} sells through partners.")
                self.assertIn("ungrounded_narrative_subject", self.codes(program))

    def test_renderer_retains_subject_but_cannot_certify_text_attribution(self):
        program = deepcopy(self.program)
        program["narrative_bindings"][0]["claims"][0]["text"] = "Parent sells through partners."
        validation = self.validate(program)
        self.assertEqual(validation["status"], "ready")
        self.assertIn("Birch: Parent sells through partners.", validation["valid_narrative_bindings"][0]["text"])
        # Negative control, not a faithful answer: labeling cannot judge the
        # grammatical subject or entailment. The old repetition check also let
        # "Birch reports that Parent sells through partners" through. Semantic
        # attribution remains the compiler's responsibility, not a new classifier.

    def test_exact_quote_and_claim_local_numbers_cannot_borrow_other_evidence(self):
        for quote, text, code in (
            ("Birch sells through partners!", "Birch sells through partners.", "invalid_narrative_claim_quote"),
            ("Birch sells through partners.", "Birch serves 17 regions.", "ungrounded_narrative_claim_number"),
            ("Birch sells through partners.", "Birch serves 23 regions.", "ungrounded_narrative_claim_number"),
        ):
            program = deepcopy(self.program)
            row = program["narrative_bindings"][0]["claims"][0]
            row["text"] = text
            row["evidence_bindings"][0]["evidence_text"] = quote
            self.assertIn(code, self.codes(program))

    def test_hidden_invented_and_cross_source_quotes_fail(self):
        for candidate_id, quote, expected in (
            ("hidden", "Parent uses every route.", "candidate_not_exposed_to_compiler"),
            ("invented", "Birch sells through partners.", "unknown_narrative_candidate"),
            ("a", "Cedar uses direct delivery.", "invalid_narrative_claim_quote"),
        ):
            program = deepcopy(self.program)
            program["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0].update(
                candidate_id=candidate_id, evidence_text=quote)
            self.assertIn(expected, self.codes(program))

    def test_only_attached_visible_context_can_supply_a_quote(self):
        catalog = deepcopy(self.catalog)
        catalog[0]["source_contexts"] = [{"context_id": "ctx-a", "relation": "source_continuation",
            "source_text": "Birch delivers internationally.", "source_span": [80, 111]}]
        program = deepcopy(self.program)
        program["narrative_bindings"][0]["claims"][0] = claim(
            "Birch", "Birch delivers internationally.", "a", "Birch delivers internationally.", context_id="ctx-a")
        self.assertEqual(self.validate(program, catalog)["status"], "ready")
        program["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["candidate_id"] = "b"
        self.assertIn("invalid_narrative_claim_context", self.codes(program, catalog))

    def test_unreferenced_body_tail_or_metadata_cannot_supply_quote(self):
        catalog = deepcopy(self.catalog)
        catalog[0].update(source_text="Birch sells through partners. Birch serves 17 regions.",
            source_bundle_text="Birch sells through partners.", local_heading="Parent uses every route.")
        for quote in ("Birch serves 17 regions.", "Parent uses every route."):
            program = deepcopy(self.program)
            program["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = quote
            self.assertIn("invalid_narrative_claim_quote", self.codes(program, catalog))

    def test_quote_uses_visible_shared_row_bundle_not_only_selected_member(self):
        from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin

        physical = {"physical_table_id": "table-one", "physical_row_id": "row-one"}
        catalog = [source("a", "Birch supplies partners.", **physical),
            source("b", "Birch supplies partners. Birch also uses direct delivery.", **physical),
            source("hidden", "Birch supplies partners. Birch also uses direct delivery. Birch owns all channels.", **physical)]
        program = {"narrative_bindings": [{"obligation_id": "routes", "claims": [
            claim("Birch", "Birch also uses direct delivery.", "a", "Birch also uses direct delivery.")]}]}
        payload = FinancialAgentCalculationMixin._semantic_program_prompt_payload(catalog,
            {"visible_candidate_ids": ["a", "b"]})
        self.assertEqual(len(payload["source_bundles_by_id"]), 1)
        visible_text = next(iter(payload["source_bundles_by_id"].values()))["source_text"]
        self.assertIn("Birch also uses direct delivery.", visible_text)
        self.assertNotIn("Birch owns all channels.", visible_text)
        self.assertEqual(self.validate(program, catalog)["status"], "ready")
        program["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = "Birch owns all channels."
        self.assertIn("invalid_narrative_claim_quote", self.codes(program, catalog))

    def test_conflicting_flat_projection_cannot_add_unattributed_text(self):
        for field, value in (("text", "Parent owns every route."), ("evidence_bindings", [])):
            program = deepcopy(self.program)
            program["narrative_bindings"][0][field] = value
            self.assertIn("narrative_claim_projection_mismatch", self.codes(program))

    def test_legacy_flat_text_is_not_current_compilation_authority(self):
        program = {"narrative_bindings": [{"obligation_id": "routes", "text": "Parent sells through partners.",
            "evidence_bindings": [{"candidate_id": "a"}]}]}
        self.assertIn("missing_narrative_claims", self.codes(program))
        # Read-only historical inspection remains possible; protected execution cannot use it.
        old = validate_semantic_calculation_program(program=program, candidate_catalog=self.catalog,
            obligations=self.owners, query="Describe routes.", candidate_visibility=self.visibility)
        envelope = CompilationEnvelopeV2.create(program=program, validation=old, visibility=self.visibility,
            candidate_catalog=self.catalog, obligations=self.owners, query="Describe routes.")
        result = execute_semantic_calculation_program(program=program, candidate_catalog=self.catalog,
            obligations=self.owners, query="Describe routes.", compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertNotEqual(result["status"], "ok")

    def test_claim_trace_survives_executor_and_input_is_immutable(self):
        original = deepcopy(self.program)
        validation = self.validate()
        envelope = CompilationEnvelopeV2.create(program=self.program, validation=validation, visibility=self.visibility,
            candidate_catalog=self.catalog, obligations=self.owners, query="Describe routes.")
        result = execute_semantic_calculation_program(program=self.program, candidate_catalog=self.catalog,
            obligations=self.owners, query="Describe routes.", compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok")
        output = result["outputs"][0]
        self.assertEqual([row["subject"] for row in output["claim_readings"]], ["Birch", "Cedar"])
        self.assertEqual(output["claim_readings"][0]["evidence"][0]["source_span"], [0, len("Birch sells through partners.")])
        self.assertEqual(self.program, original)

    def test_claim_format_retry_keeps_cohort_and_other_island_bytes(self):
        accepted = SemanticCalculationProgram.model_validate({"direct_bindings": [{
            "obligation_id": "quantity", "candidate_id": "quantity-cell"}]})
        bad = deepcopy(self.program)
        bad["narrative_bindings"][0]["claims"][0]["evidence_bindings"][0]["evidence_text"] = "Wrong quote"
        llm = _StructuredQueueLLM(accepted, SemanticCalculationProgram.model_validate(bad),
            SemanticCalculationProgram.model_validate(self.program))
        owners = [_obligation("quantity", "direct_value", "quantity"), *self.owners]
        catalog = [_candidate("quantity-cell", 10), *self.catalog[:2]]
        state = _case_state({"question": "Describe routes and quantity.", "obligations": owners}, catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"], sort_keys=True),
            json.dumps(accepted.model_dump()["direct_bindings"], sort_keys=True))
        def payload(prompt):
            text = prompt.to_messages()[0].content.split("Source bundles, candidate cohorts, and candidates_by_id:\n", 1)[1]
            return json.JSONDecoder().raw_decode(text.lstrip())[0]
        self.assertEqual(payload(llm.prompts[1]), payload(llm.prompts[2]))

    def test_exact_source_checks_are_not_semantic_entailment(self):
        program = deepcopy(self.program)
        program["narrative_bindings"][0]["claims"][0]["text"] = "Birch never sells through partners."
        self.assertEqual(self.validate(program)["status"], "ready")
        # Deliberate negative control: source and subject attachment alone cannot detect negation.

    def test_claim_requirement_cannot_borrow_another_owners_visible_source(self):
        owners = deepcopy(self.owners)
        owners[0]["evidence_requirements"] = [{"requirement_id": key, "label": key, "required": True}
            for key in ("routes:a", "routes:b")]
        visibility = _semantic_candidate_visibility(self.catalog, visible_candidate_ids=["a", "b"],
            candidate_ids_by_owner={"routes": ["a", "b"], "routes:a": ["a"], "routes:b": ["b"]})
        program = deepcopy(self.program)
        links = [row["evidence_bindings"][0] for row in program["narrative_bindings"][0]["claims"]]
        for link in links:
            link["source_requirement_id"] = "routes:" + link["candidate_id"]
        def validate():
            return validate_semantic_calculation_program(program=program, candidate_catalog=self.catalog,
                obligations=owners, query="Describe routes.", candidate_visibility=visibility,
                require_narrative_claims=True)
        self.assertEqual(validate()["status"], "ready")
        links[0]["source_requirement_id"] = "routes:b"
        self.assertIn("candidate_not_exposed_to_compiler", {row["code"] for row in validate()["errors"]})

    def test_malformed_claims_fail_closed_without_mutation(self):
        for claims in ([], "not-a-list", [None], [{"text": 3, "evidence_bindings": []}],
                       [{"subject": "Birch", "text": "Birch sells.", "evidence_bindings": []}]):
            program = {"narrative_bindings": [{"obligation_id": "routes", "claims": claims}]}
            before = deepcopy(program)
            self.assertNotEqual(self.validate(program)["status"], "ready")
            self.assertEqual(program, before)

    def test_v2_rejects_claim_changes_after_validation(self):
        envelope = CompilationEnvelopeV2.create(program=self.program, validation=self.validate(), visibility=self.visibility,
            candidate_catalog=self.catalog, obligations=self.owners, query="Describe routes.")
        changed = deepcopy(self.program)
        changed["narrative_bindings"][0]["claims"][0]["subject"] = "Parent"
        result = execute_semantic_calculation_program(program=changed, candidate_catalog=self.catalog,
            obligations=self.owners, query="Describe routes.", compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(result["validation"]["errors"][0]["code"], "validation_drift")

    def test_versioned_claim_fixture_does_not_rewrite_sources_answers_or_predecessor(self):
        folder = Path(__file__).parent / "fixtures"
        old_bytes = (folder / "reviewed_runtime_replay_corpus_v2.json").read_bytes()
        old = json.loads(old_bytes)
        new = json.loads((folder / "reviewed_runtime_replay_corpus_v3.json").read_text(encoding="utf-8"))
        self.assertEqual(hashlib.sha256(old_bytes).hexdigest(), new["predecessor"]["sha256"])
        self.assertEqual(new["corpus_revision"], 3)
        for before, after in zip(old["cases"], new["cases"]):
            for key in before.keys() - {"program"}:
                self.assertEqual(before[key], after[key])
            for key in before["program"].keys() - {"narrative_bindings"}:
                self.assertEqual(before["program"][key], after["program"][key])
            for a, b in zip(before["program"].get("narrative_bindings", []), after["program"].get("narrative_bindings", [])):
                self.assertEqual(a["text"], b["text"])
                self.assertEqual(a["candidate_ids"], b["candidate_ids"])
                self.assertTrue(b["claims"])


if __name__ == "__main__":
    unittest.main()
