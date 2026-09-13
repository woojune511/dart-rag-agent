"""Exact claim quotes, including context, are the numeric evidence surface."""
from copy import deepcopy
from tests.narrative_address_test_support import address_program, model_program
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from tests.semantic_program_test_support import _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import source, claim


class NarrativeNumberAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.query = "Describe regional coverage."
        self.owners = [_obligation("coverage", "narrative", self.query)]
        self.quote = "Birch serves 37 regions."
        self.catalog = [source("a", "Birch operates locally.", source_contexts=[{
            "context_id": "ctx-a", "relation": "source_continuation",
            "source_text": self.quote + " Birch also serves 91 ports.", "source_span": [40, 91]}]),
            source("b", "Cedar serves 23 regions.")]
        self.program = {"narrative_bindings": [{"obligation_id": "coverage", "claims": [
            claim("Birch", self.quote, "a", self.quote, context_id="ctx-a")]}]}

    def validate(self, program=None, catalog=None):
        program = self.program if program is None else program
        catalog = self.catalog if catalog is None else catalog
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["a", "b"],
            candidate_ids_by_owner={"coverage": ["a", "b"]})
        return validate_semantic_calculation_program(program=address_program(program, catalog), obligations=self.owners,
            candidate_catalog=catalog, candidate_visibility=visibility, query=self.query,
            require_narrative_claims=True), visibility

    def test_context_number_passes_both_validation_and_protected_execution(self):
        original = deepcopy((self.catalog, self.program))
        validation, visibility = self.validate()
        self.assertEqual(validation["status"], "ready", validation["errors"])
        envelope = CompilationEnvelopeV2.create(program=address_program(self.program, self.catalog), validation=validation,
            visibility=visibility, candidate_catalog=self.catalog, obligations=self.owners, query=self.query)
        result = execute_semantic_calculation_program(program=address_program(self.program, self.catalog), candidate_catalog=self.catalog,
            obligations=self.owners, query=self.query, compilation_envelope=envelope,
            require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok", result)
        evidence = result["outputs"][0]["claim_readings"][0]["evidence"][0]
        self.assertEqual(evidence["context_id"], "ctx-a")
        self.assertEqual(evidence["evidence_text"], self.quote + " ")
        self.assertEqual((self.catalog, self.program), original)

    def test_visible_shared_bundle_number_is_not_limited_to_selected_member_body(self):
        physical = {"physical_table_id": "table", "physical_row_id": "row"}
        catalog = [source("a", "Birch operates locally.", **physical),
            source("b", "Birch operates locally. " + self.quote, **physical)]
        program = {"narrative_bindings": [{"obligation_id": "coverage", "claims": [
            claim("Birch", self.quote, "a", self.quote)]}]}
        validation, _ = self.validate(program, catalog)
        self.assertEqual(validation["status"], "ready", validation["errors"])

    def test_unquoted_tail_and_other_claim_numbers_still_fail_locally(self):
        for amount in (91, 23):
            with self.subTest(amount=amount):
                program = deepcopy(self.program)
                claims = program["narrative_bindings"][0]["claims"]
                claims[0]["text"] = f"Birch serves {amount} regions."
                claims.append(claim("Cedar", "Cedar serves 23 regions.", "b", "Cedar serves 23 regions."))
                validation, _ = self.validate(program)
                errors = [e for e in validation["errors"] if e["code"] == "ungrounded_narrative_claim_number"]
                self.assertTrue(errors, validation)
                self.assertEqual(errors[0]["location"], "narrative_claims[0]")
                self.assertEqual(validation["valid_narrative_bindings"], [])

    def test_invalid_context_quote_or_model_written_reading_cannot_supply_numbers(self):
        for change, expected in (
            ({"context_id": "ctx-b"}, "unknown_narrative_surface"),
            ({"evidence_text": "Birch serves 37 regions!"}, "unknown_narrative_surface"),
            ({"candidate_id": "b"}, "unknown_narrative_surface"),
        ):
            with self.subTest(change=change):
                program = deepcopy(self.program)
                binding = program["narrative_bindings"][0]
                binding["claims"][0]["evidence_bindings"][0].update(change)
                binding["claim_readings"] = [{"evidence": [{"candidate_id": "a", "evidence_text": self.quote}]}]
                validation, _ = self.validate(program)
                self.assertIn(expected, {e["code"] for e in validation["errors"]})
                self.assertNotEqual(validation["status"], "ready")

    def test_description_only_reference_cannot_use_raw_scalar_even_in_exact_claim_quote(self):
        from tests.test_narrative_row_description import NarrativeRowDescriptionTests

        fixture = NarrativeRowDescriptionTests()
        fixture.setUp()
        candidate = fixture.catalog[0]
        program = {"narrative_bindings": [{"obligation_id": "routes", "claims": [claim(
            "Partners", "Partners account for 23.4%.", "cell", candidate["source_text"],
            source_requirement_id="routes-input", row_description_quote="Regional outlets")]}]}
        result = fixture.validate(program)
        self.assertIn("ungrounded_narrative_number", {e["code"] for e in result["errors"]})

    def test_valid_context_claim_needs_one_compiler_call_not_a_format_retry(self):
        from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state

        llm = _StructuredQueueLLM(model_program(self.program, self.catalog))
        state = _case_state({"question": self.query, "obligations": self.owners}, self.catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 1)


if __name__ == "__main__":
    unittest.main()
