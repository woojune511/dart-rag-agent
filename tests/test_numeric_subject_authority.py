"""Source-proof gates and former identity contrasts (semantic review, not code truth)."""

from copy import deepcopy
import hashlib
import json
import unittest

from src.agent.financial_candidate_matching import project_candidate_fact
from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _retry_candidate_exclusions
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_source_interpretation import interpretation_axis_sources
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.semantic_program_test_support import (
    FinancialAgent, _StructuredQueueLLM, _candidate, _obligation, _requirement, _binding,
)


def numeric(candidate_id="group", subject="Alpha Cells and others", axis="column", value=37):
    row = _candidate(candidate_id, value, raw_unit="백만원", period="2024", row_label="cash flow")
    row.update(physical_table_id="table-1", physical_row_id="row-1", physical_cell_id=candidate_id,
        row_headers=["cash flow"], local_entity_surfaces=["cash flow"], column_headers=["2024", subject],
        source_text=f"cash flow | 2024 | {subject} | {value} 백만원")
    if axis == "row":
        row.update(row_label=subject, row_headers=["region", subject], local_entity_surfaces=[subject], column_headers=["2024"])
    return row


def owner(subject="Alpha Cells", kind="direct_value"):
    return _obligation("answer", kind, "cash flow", display_unit="백만원",
        semantic_target={"local_subjects": [subject], "metric_surfaces": ["cash flow"], "concept_keys": []})


def direct(candidate_id):
    return {"status": "ready", "direct_bindings": [{"obligation_id": "answer", "candidate_id": candidate_id}]}


def authored_interpretation(candidate, subject):
    """Explicit fixture authorship, not a runtime fallback or a model accuracy oracle."""
    return {"request_unit_ids": ["request_001"], "subject": subject, "metric": "cash flow",
            "axis_refs": list(interpretation_axis_sources(candidate)), "context_evidence": []}


class NumericSubjectAuthorityTests(unittest.TestCase):
    def validate(self, candidate, obligation=None, program=None, *, interpreted=False):
        if interpreted:
            program = deepcopy(program or direct(candidate["candidate_id"]))
            program["direct_bindings"][0]["source_interpretation"] = authored_interpretation(
                candidate, (obligation or owner())["semantic_target"]["local_subjects"][0])
        return validate_semantic_calculation_program(program=program or direct(candidate["candidate_id"]),
            obligations=[obligation or owner()], candidate_catalog=[candidate], query="Return the named subject's amount.")

    def test_column_subject_is_exposed_and_wrong_column_is_not_equivalent(self):
        exact, group = numeric("exact", "Alpha Cells"), numeric()
        self.assertIn("Alpha Cells", project_candidate_fact(exact).subject_surfaces)
        plan = _semantic_candidate_cohorts([group, exact], [owner()])
        self.assertEqual(plan["candidate_match_by_id"]["exact"]["answer"]["subject_state"], "match")
        self.assertNotEqual(plan["candidate_match_by_id"]["group"]["answer"]["subject_state"], "match")
        self.assertEqual(self.validate(exact, interpreted=True)["status"], "ready")
        reverse = _semantic_candidate_cohorts([exact, group], [owner()])
        self.assertEqual(plan["candidate_ids_by_owner"], reverse["candidate_ids_by_owner"])
        self.assertEqual(plan["candidate_match_by_id"], reverse["candidate_match_by_id"])

    def test_named_group_is_allowed_but_cannot_substitute_for_member(self):
        for axis in ("row", "column"):
            for surface in ("Alpha Cells and others", "Alpha Cells 등", "Alpha Cells (combined)"):
                candidate = numeric(subject=surface, axis=axis)
                with self.subTest(axis=axis, surface=surface):
                    result = self.validate(candidate)
                    self.assertNotEqual(result["status"], "ready")
                    self.assertTrue(any(error["code"] == "missing_source_interpretation" for error in result["errors"]))
                    self.assertEqual(self.validate(candidate, owner(surface), interpreted=True)["status"], "ready")
                    # Former member/group equivalence assertions are semantic controls.
                    # A source-linked but wrong interpretation is not code-proven correct.
                    self.assertEqual(self.validate(candidate, interpreted=True)["status"], "ready")

    def test_partial_name_is_unknown_not_an_excluded_candidate(self):
        candidate = numeric()
        before, fingerprint = deepcopy(candidate), semantic_candidate_catalog_fingerprint([candidate])
        plan = _semantic_candidate_cohorts([candidate], [owner()])
        self.assertEqual(plan["candidate_match_by_id"]["group"]["answer"]["state"], "unknown_only")
        rejected = self.validate(candidate)
        issue = next(error for error in rejected["errors"] if error["code"] == "missing_source_interpretation")
        self.assertEqual((issue["candidate_id"], issue["owner_id"], issue["location"], issue["repair_action"]),
            ("group", "answer", "direct_binding.context_bindings", "repair_program"))
        self.assertEqual(_retry_candidate_exclusions(program=direct("group"),
            validation_errors=rejected["errors"], target_obligation_ids=["answer"]), {})
        self.assertEqual(candidate, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint([candidate]), fingerprint)

    def test_question_aliases_footnotes_case_and_spaces_preserve_whole_identity(self):
        candidate = numeric(subject=" ALPHA   Cells (*1,5) ")
        self.assertEqual(self.validate(candidate, interpreted=True)["status"], "ready")
        candidate = numeric(subject="대상법인")
        obligation = owner()
        obligation["semantic_target"]["local_subjects"].append("대상법인")
        self.assertEqual(self.validate(candidate, obligation, interpreted=True)["status"], "ready")
        self.assertNotEqual(self.validate(numeric(subject="Alpha / Cells"))["status"], "ready")

    def test_more_specific_axis_cannot_borrow_parent_or_metadata_identity(self):
        candidate = numeric()
        candidate["column_headers"] = ["Alpha Cells", "Alpha Cells and others"]
        candidate["local_entity_surfaces"] = ["Alpha Cells"]
        candidate["segment"] = "Alpha Cells"
        self.assertNotEqual(self.validate(candidate)["status"], "ready")
        candidate["column_headers"] = ["Beta Cells"]
        self.assertNotEqual(self.validate(candidate)["status"], "ready")

    def test_unrequested_subject_and_narrative_keep_existing_contract(self):
        candidate = numeric()
        obligation = owner()
        obligation["semantic_target"]["local_subjects"] = []
        self.assertEqual(self.validate(candidate, obligation)["status"], "ready")
        narrative = {**candidate, "kind": "narrative", "candidate_kind": "chunk",
            "physical_table_id": "", "normalized_value": None,
            "source_text": "Alpha Cells and other participants describe their activities."}
        program = {"narrative_bindings": [{"obligation_id": "answer", "candidate_ids": ["group"],
            "text": narrative["source_text"]}]}
        self.assertEqual(self.validate(narrative, owner(kind="narrative"), program)["status"], "ready")

    def test_prose_local_target_does_not_disable_existing_segment_validation(self):
        candidate = {**numeric(), "candidate_kind": "sentence_value", "physical_table_id": "",
            "source_text": "Beta Cells reports 37.", "local_entity_surfaces": ["Beta Cells"], "segment": "Beta Cells"}
        obligation = owner()
        obligation["scope"]["segment"] = "Alpha Cells"
        result = self.validate(candidate, obligation)
        self.assertIn("missing_source_interpretation", [error["code"] for error in result["errors"]])

    def test_whole_local_identity_does_not_override_an_independent_segment(self):
        candidate, obligation = numeric(subject="Alpha Cells"), owner()
        candidate["segment"] = "other area"
        obligation["scope"]["segment"] = "requested area"
        result = self.validate(candidate, obligation)
        self.assertNotEqual(result["status"], "ready")
        plan = _semantic_candidate_cohorts([candidate], [obligation])
        self.assertNotEqual(plan["candidate_match_by_id"]["group"]["answer"]["state"], "explicit_conflict")

    def test_derived_input_requires_its_own_subject_even_with_soft_scope_override(self):
        obligation = owner(kind="derived_value")
        obligation["evidence_requirements"] = [_requirement("answer:input", "cash flow")]
        # Empty child targets inherit the explicit parent subject.
        binding = _binding("A", "group", "answer:input")
        binding["scope_applicability_fields"] = ["segment", "basis"]
        program = {"status": "ready", "expressions": [{"obligation_id": "answer", "formula": "A",
            "variable_bindings": [binding], "source_display_candidate_id": None, "source_display_reason": "No separate display."}]}
        result = self.validate(numeric(), obligation, program)
        self.assertTrue(any(error["code"] == "missing_source_interpretation" and error["owner_id"] == "answer:input"
            for error in result["errors"]))
        execution = execute_semantic_calculation_program(program=program, obligations=[obligation], candidate_catalog=[numeric()], query="Return the amount.")
        self.assertEqual(execution["outputs"], [])

    def test_source_display_cannot_bypass_subject_check(self):
        exact, group = numeric("exact", "Alpha Cells"), numeric()
        obligation = owner(kind="derived_value")
        obligation["evidence_requirements"] = [_requirement("answer:input", "cash flow")]
        program = {"status": "ready", "expressions": [{"obligation_id": "answer", "formula": "A",
            "variable_bindings": [{**_binding("A", "exact", "answer:input"),
                "source_interpretation": authored_interpretation(exact, "Alpha Cells")}],
            "source_display_candidate_id": "group", "source_display_reason": "Selected display."}]}
        result = validate_semantic_calculation_program(program=program, obligations=[obligation], candidate_catalog=[exact, group], query="Return the amount.")
        self.assertTrue(any(error["code"] == "missing_source_interpretation" and error["location"] == "source_display.context_bindings"
            for error in result["errors"]))

    def test_unknown_subject_retries_same_cohort_and_preserves_accepted_island(self):
        stable_owner = owner("Beta Cells")
        stable_owner["obligation_id"] = "stable"
        catalog, obligations = [numeric("stable-value", "Beta Cells"), numeric()], [stable_owner, owner()]
        accepted = SemanticCalculationProgram.model_validate({"status": "ready",
            "direct_bindings": [{"obligation_id": "stable", "candidate_id": "stable-value",
                "source_interpretation": authored_interpretation(catalog[0], "Beta Cells")}],
            "rationale": "Preserve this accepted result."})
        wrong = SemanticCalculationProgram.model_validate(direct("group"))
        abstain = SemanticCalculationProgram.model_validate({"status": "ambiguous", "ambiguous_obligation_ids": ["answer"],
            "rationale": "This expanded label does not establish the requested single subject."})
        llm = _StructuredQueueLLM(accepted, wrong, abstain)
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = llm
        compiled = agent._compile_semantic_calculation_program({
            "query": "Return both subjects' amounts.", "answer_obligations": obligations,
            "semantic_candidate_catalog_prebuilt": True,
            "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog,
        })
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]
        retried = [attempt for attempt in diagnostics["attempts"] if attempt["island_id"] == "island_002"]
        self.assertEqual(len(retried), 2)
        self.assertEqual(retried[0]["visible_candidate_ids"], retried[1]["visible_candidate_ids"])
        self.assertEqual(diagnostics["islands"][0]["accepted_program_fingerprint"],
            hashlib.sha256(json.dumps(accepted.model_dump(), ensure_ascii=False, sort_keys=True,
                separators=(",", ":")).encode("utf-8")).hexdigest())
        self.assertEqual(compiled["semantic_program"]["direct_bindings"], accepted.model_dump()["direct_bindings"])
        self.assertEqual(compiled["semantic_program_validation"]["ambiguous_obligation_ids"], ["answer"])
        self.assertEqual(compiled["semantic_program_validation"]["errors"], [])
        execution = execute_semantic_calculation_program(program=compiled["semantic_program"], obligations=obligations,
            candidate_catalog=catalog, query="Return both subjects' amounts.",
            compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual([item["obligation_id"] for item in execution["outputs"]], ["stable"])

    def test_repeated_unresolved_choice_is_blocked_after_one_retry(self):
        wrong = SemanticCalculationProgram.model_validate(direct("group"))
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StructuredQueueLLM(wrong, wrong)
        catalog, obligations = [numeric()], [owner()]
        query = "Return the named subject's amount."
        compiled = agent._compile_semantic_calculation_program({"query": query, "answer_obligations": obligations,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog,
            "semantic_candidate_catalog": catalog})
        self.assertEqual(len(agent.llm.prompts), 2)
        execution = execute_semantic_calculation_program(program=compiled["semantic_program"], obligations=obligations,
            candidate_catalog=catalog, query=query, compilation_envelope=compiled["semantic_compilation_envelope"],
            require_compilation_envelope=True)
        self.assertEqual(execution["outputs"], [])
        self.assertIn("missing_source_interpretation", str(agent.llm.prompts[-1]))
        self.assertEqual(compiled["semantic_program_validation"]["missing_obligation_ids"], ["answer"])


if __name__ == "__main__":
    unittest.main()
