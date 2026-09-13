"""Characterize request/source seams, not a permanent synonym/entailment policy.

Anonymous controls expose literal-only input limits. Resolved section bindings
have separate positive/negative tests in test_source_section_bindings; the old
literal form remains strict. Authored name projection has separate transport
controls in test_planner_subject_projection; these fixed-target failures remain.
Passing this file does not establish semantic correctness or model accuracy.
"""

from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import validate_semantic_calculation_program
from src.agent.financial_candidate_matching import structured_subject_evidence
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_source_scope import source_section_applicability, source_section_requirement_errors
from tests.semantic_program_test_support import FinancialAgent, _StructuredQueueLLM, _candidate, _obligation
from tests.narrative_address_test_support import model_program


def numeric(subject="Orchid", candidate_id="cell"):
    return {**_candidate(candidate_id, 23, period="2024"),
        "row_headers": ["quantity"], "column_headers": ["Operating groups", subject],
        "physical_table_id": "table", "physical_row_id": "row", "physical_cell_id": candidate_id}


def owner(subject="Orchid division"):
    return _obligation("answer", "direct_value", "quantity", semantic_target={
        "local_subjects": [subject], "concept_keys": [], "metric_surfaces": ["quantity"]})


def narrative(text):
    return {**_candidate("body", 0), "kind": "narrative", "candidate_kind": "chunk",
        "raw_value": "", "raw_unit": "", "normalized_value": None,
        "normalized_unit": "UNKNOWN", "source_text": text, "source_bundle_text": text}


def validate_claim(subject, text, quotes, source):
    program = model_program({"narrative_bindings": [{
        "obligation_id": "answer", "claims": [{"subject": subject, "text": text,
            "evidence_bindings": [{"candidate_id": "body", "evidence_text": quote} for quote in quotes]}]}]}, [source])
    visibility = _semantic_candidate_visibility([source], visible_candidate_ids=["body"],
        candidate_ids_by_owner={"answer": ["body"]})
    return validate_semantic_calculation_program(program=program.model_dump(), candidate_catalog=[source],
        obligations=[_obligation("answer", "narrative", "Describe activities.")],
        query="Describe activities.", candidate_visibility=visibility, require_narrative_claims=True)


class RequestSourceBoundaryCharacterizationTests(unittest.TestCase):
    def test_verbatim_request_abbreviation_passes_query_check_but_not_source_path(self):
        for requested, located in (("group notes", "Notes to group statements"),
                                   ("operations overview", "Overview of operations")):
            with self.subTest(requested=requested):
                obligation = _obligation("answer", "narrative", "Describe.", source_sections=[requested])
                self.assertEqual(source_section_requirement_errors([obligation], f"Use {requested}."), [])
                result = source_section_applicability({"section_path": located}, obligation)
                self.assertEqual(result["state"], "conflict")

    def test_located_expansion_passes_membership_but_not_request_copy(self):
        for requested, located in (("group notes", "Notes to group statements"),
                                   ("operations overview", "Overview of operations")):
            with self.subTest(requested=requested):
                obligation = _obligation("answer", "narrative", "Describe.", source_sections=[located])
                self.assertEqual(source_section_applicability({"section_path": located}, obligation)["state"], "match")
                errors = source_section_requirement_errors([obligation], f"Use {requested}.")
                self.assertEqual([error["code"] for error in errors], ["invalid_requested_source_section"])

    def test_exact_named_path_is_a_positive_control_and_foreign_path_is_not(self):
        obligation = _obligation("answer", "narrative", "Describe.", source_sections=["Operations > Overview"])
        self.assertEqual(source_section_requirement_errors([obligation], "Use Operations > Overview."), [])
        for path, state in (("II. Operations > 1. Overview > Detail", "match"),
                            ("II. Other operations > 1. Overview", "conflict"),
                            ("II. Operations > 2. Overview annex", "conflict")):
            self.assertEqual(source_section_applicability({"section_path": path}, obligation)["state"], state)

    def test_changing_request_label_to_source_label_is_not_a_compiler_repair(self):
        catalog, obligations = [numeric()], [owner()]
        before = deepcopy((catalog, obligations))
        selected = SemanticCalculationProgram.model_validate({"status": "ready", "direct_bindings": [{
            "obligation_id": "answer", "candidate_id": "cell"}]})
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StructuredQueueLLM(selected, selected)
        compiled = agent._compile_semantic_calculation_program({
            "query": "Return the quantity for Orchid division.", "answer_obligations": obligations,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog,
            "semantic_candidate_catalog": catalog})
        self.assertEqual(len(agent.llm.prompts), 2)
        validation = compiled["semantic_program_validation"]
        self.assertEqual(validation["valid_direct_bindings"], [])
        self.assertEqual(validation["missing_obligation_ids"], ["answer"])
        # Rejected bindings are pruned from the final program; original errors
        # remain in per-attempt history, not necessarily in final validation.
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["program_validation_history"]
        self.assertTrue(all("candidate_subject_unresolved" in {error["code"] for error in attempt["errors"]}
                            for attempt in attempts))
        self.assertEqual(attempts[0]["visible_candidate_ids"], attempts[1]["visible_candidate_ids"])
        self.assertEqual((catalog, obligations), before)

    def test_composed_subject_is_unknown_even_when_its_head_is_an_exact_axis(self):
        for requested, located in (("Orchid division", "Orchid"), ("Maple unit", "Maple")):
            with self.subTest(requested=requested):
                source = numeric(located)
                self.assertEqual(structured_subject_evidence(source, [requested])["state"], "unknown")
                self.assertEqual(structured_subject_evidence(source, [located])["state"], "match")
                cohorts = _semantic_candidate_cohorts([source], [owner(requested)])
                self.assertEqual(cohorts["candidate_ids_by_owner"]["answer"], ["cell"])
                self.assertEqual(cohorts["candidate_match_by_id"]["cell"]["answer"]["state"], "unknown_only")

    def test_global_containment_would_also_admit_wrong_group_and_qualifier_controls(self):
        for label in ("Orchid and others", "Orchid (combined)", "Orchid Services"):
            with self.subTest(label=label):
                self.assertIn("Orchid", label)  # Why blanket substring acceptance is unsafe.
                self.assertEqual(structured_subject_evidence(numeric(label), ["Orchid"])["state"], "unknown")

    def test_query_supplied_alias_can_ground_a_whole_axis_without_invented_aliases(self):
        source = numeric("Maple")
        self.assertEqual(structured_subject_evidence(source, ["Maple unit", "Maple"])["state"], "match")
        self.assertEqual(structured_subject_evidence(source, ["Maple unit", "Birch"])["state"], "unknown")

    def test_metadata_or_parent_label_cannot_replace_cell_subject(self):
        source = numeric("Orchid and others")
        source.update(document_company="Orchid", local_entity_surfaces=["Orchid"])
        source["column_headers"] = ["Orchid", "Orchid and others"]
        self.assertEqual(structured_subject_evidence(source, ["Orchid"])["state"], "unknown")

    def test_multiple_exact_quotes_can_link_named_subject_and_implicit_followup(self):
        introduction = "Orchid operates a service platform."
        followup = "It supplies tools to business customers."
        source = narrative(introduction + "\n\n" + followup)
        valid = validate_claim("Orchid", "supplies business tools.", [introduction, followup], source)
        self.assertEqual(valid["status"], "ready")
        missing_subject = validate_claim("Orchid", "supplies business tools.", [followup], source)
        self.assertIn("ungrounded_narrative_subject", {error["code"] for error in missing_subject["errors"]})

    def test_quote_paraphrase_fails_but_public_claim_paraphrase_does_not(self):
        quote = "Orchid supplies tools to business customers."
        source = narrative(quote)
        self.assertEqual(validate_claim("Orchid", "provides business tools.", [quote], source)["status"], "ready")
        invalid = validate_claim("Orchid", "provides business tools.", [quote.replace("supplies", "provides")], source)
        self.assertIn("unknown_narrative_surface", {error["code"] for error in invalid["errors"]})

    def test_metadata_subject_is_not_accepted_as_a_quote(self):
        quote = "Birch supplies tools."
        source = narrative(quote)
        source["document_company"] = "Orchid"
        invalid = validate_claim("Orchid", "supplies tools.", [quote], source)
        self.assertIn("ungrounded_narrative_subject", {error["code"] for error in invalid["errors"]})

    def test_literal_quote_checks_do_not_prove_semantic_attribution(self):
        quote = "Orchid has no outlet. Birch operates a shop."
        source = narrative(quote)
        # Intentionally false authored control: structural acceptance is NOT a
        # semantic pass. Do not turn it into an accepted answer-quality fixture.
        result = validate_claim("Orchid", "operates a shop.", [quote], source)
        self.assertEqual(result["status"], "ready")


if __name__ == "__main__":
    unittest.main()
