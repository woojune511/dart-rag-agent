"""Explicit query source scope is authority, not a relevance hint."""
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_graph_models import AnswerObligation, RequirementPlannerOutput, SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog, build_semantic_source_candidates, semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _requirement, _scope, _StructuredQueueLLM, _with_narrative_claims
from tests.test_retrieval_scope_isolation import _Pipeline, _doc, _state


def candidate(cid, path, *, kind="narrative"):
    row = {**_candidate(cid, 17, period="2037"), "company": "Example", "year": 2037,
        "source_document_id": "report-A", "source_anchor": f"[Example | 2037 | {path} | parent]",
        "source_text": "Services include shared operations. Cedar operations is mentioned here."}
    if kind == "narrative":
        row.update(kind="narrative", candidate_kind="chunk", normalized_value=None, raw_value="", raw_unit="")
    return row


def binding(owner_id, cid):
    return {"obligation_id": owner_id, "text": "Services include shared operations.",
        "evidence_bindings": [{"candidate_id": cid}]}


def claimed_model(program, catalog):
    return SemanticCalculationProgram.model_validate(_with_narrative_claims(program,
        subject="Services", quotes={key: "Services include shared operations." for key in ("right", "wrong")}, catalog=catalog))


class RequestedSourceSectionTests(unittest.TestCase):
    def setUp(self):
        self.query = 'Summarize services from "Cedar operations".'
        self.owner = _obligation("services", "narrative", "Services", source_sections=["Cedar operations"],
            scope=_scope(company="Example", period="2037"))
        self.catalog = [candidate("wrong", "III. Notes > 1. Services"),
            candidate("right", "II. Cedar operations > 1. Services"), candidate("unknown", "?")]

    def validate(self, program, owners=None, catalog=None, *, visibility=None, query=None):
        return validate_semantic_calculation_program(program=program, obligations=owners or [self.owner],
            candidate_catalog=catalog or self.catalog, query=query or self.query, candidate_visibility=visibility)

    def test_wrong_and_unlocated_sections_cannot_spend_owner_budget(self):
        before = deepcopy(self.catalog)
        fingerprint = semantic_candidate_catalog_fingerprint(self.catalog)
        for rows in (self.catalog, list(reversed(self.catalog))):
            plan = _semantic_candidate_cohorts(rows, [self.owner])
            self.assertEqual(plan["candidate_ids_by_owner"]["services"], ["right"])
        self.assertEqual(self.catalog, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(self.catalog), fingerprint)

    def test_actual_parser_metadata_survives_legacy_catalog_anchor_projection(self):
        from tests.test_table_reading_evidence import TableReadingEvidenceTests
        from src.agent.financial_source_scope import source_section_applicability
        docs, _, _ = TableReadingEvidenceTests().project([("Alpha", "partner locations", "35%")])
        agent = FinancialAgent.__new__(FinancialAgent)
        sources = build_semantic_source_candidates({"retrieved_docs": [(doc, 0) for doc in docs]},
            source_anchor_builder=agent._build_source_anchor)
        catalog = build_semantic_candidate_catalog(sources)
        rows = [row for row in catalog if row.get("physical_row_id")]
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(source_section_applicability(row, {"source_sections": ["사업의 내용 > Overview"]})["state"], "match")
            self.assertEqual(source_section_applicability(row, {"source_sections": ["Notes"]})["state"], "conflict")

    def test_numeric_bundle_expansion_does_not_restore_foreign_members(self):
        rows = [candidate("inside", "Cedar operations", kind="numeric"), candidate("outside", "Notes", kind="numeric")]
        for row in rows:
            row.update(physical_table_id="table-A", physical_row_id="row-A", physical_cell_id=row["candidate_id"])
        owner = {**self.owner, "kind": "direct_value"}
        before = deepcopy(rows)
        for ordered in (rows, list(reversed(rows))):
            plan = _semantic_candidate_cohorts(ordered, [owner])
            self.assertEqual(plan["candidate_ids_by_owner"]["services"], ["inside"])
        self.assertEqual(rows, before)

    def test_body_context_and_graph_relation_do_not_establish_section_membership(self):
        self.catalog[0]["source_contexts"] = [{"relation": "ancestor_heading", "source_text": "Cedar operations"}]
        self.catalog[0]["source_anchor"] = "[Example | 2037 | III. Notes | Cedar operations]"
        self.catalog[2]["table_context"] = "Cedar operations"
        plan = _semantic_candidate_cohorts(self.catalog, [self.owner])
        self.assertEqual(plan["candidate_ids_by_owner"]["services"], ["right"])

    def test_titles_match_whole_hierarchy_components_not_substrings(self):
        from src.agent.financial_source_scope import source_section_applicability
        for path, requested, allowed in (
            ("II. Cedar operations > 3. Services", "Cedar operations", True),
            ("II. Cedar operations > 3. Services", "Cedar operations > Services", True),
            ("II. Cedar operations annex", "Cedar operations", False),
            ("III. Notes > 3. Services", "Cedar operations > Services", False),
            ("II. Cedar operations > 3. Services", "2. Services", False),
            ("II. Cedar operations > 3. Services", "3. Services", True),
        ):
            with self.subTest(path=path, requested=requested):
                result = source_section_applicability(candidate("x", path), {"source_sections": [requested]})
                self.assertEqual(result["state"] == "match", allowed)

    def test_requirement_can_narrow_but_not_widen_parent_sections(self):
        self.owner["evidence_requirements"] = [{**_requirement("input", "Services"), "source_sections": ["Notes"]}]
        plan = _semantic_candidate_cohorts(self.catalog, [self.owner])
        self.assertEqual(plan["candidate_ids_by_owner"]["input"], [])
        self.owner["evidence_requirements"][0]["source_sections"] = ["Services"]
        plan = _semantic_candidate_cohorts(self.catalog, [self.owner])
        self.assertEqual(plan["candidate_ids_by_owner"]["input"], ["right"])

    def test_hints_and_unspecified_scope_keep_existing_behavior(self):
        self.owner.pop("source_sections")
        self.owner["retrieval_hints"] = ["Cedar operations"]
        self.assertEqual(set(_semantic_candidate_cohorts(self.catalog, [self.owner])["visible_candidate_ids"]),
            {"wrong", "right", "unknown"})

    def test_validator_rejects_outside_section_even_with_overwide_visibility(self):
        visibility = _semantic_candidate_visibility(self.catalog, visible_candidate_ids=["wrong", "unknown", "right"],
            candidate_ids_by_owner={"services": ["wrong", "unknown", "right"]})
        for cid in ("wrong", "unknown"):
            with self.subTest(cid=cid):
                result = self.validate({"narrative_bindings": [binding("services", cid)]}, visibility=visibility)
                self.assertNotEqual(result["status"], "ready")
                self.assertTrue(any(error["code"].startswith("candidate_source_section_") for error in result["errors"]))
        self.assertEqual(self.validate({"narrative_bindings": [binding("services", "right")]}, visibility=visibility)["status"], "ready")

    def test_numeric_direct_operand_display_and_compatibility_follow_section_authority(self):
        catalog = [candidate("outside", "III. Notes", kind="numeric"), candidate("inside", "II. Cedar operations", kind="numeric"),
            candidate("witness", "III. Notes")]
        owner = {**self.owner, "kind": "direct_value"}
        programs = [
            {"direct_bindings": [{"obligation_id": "services", "candidate_id": "outside"}]},
            {"direct_bindings": [{"obligation_id": "services", "candidate_id": "inside", "compatibility_candidate_ids": ["witness"]}]},
        ]
        for program in programs:
            result = self.validate(program, [owner], catalog)
            self.assertIn("candidate_source_section_mismatch", {row["code"] for row in result["errors"]})
        owner["kind"] = "derived_value"
        owner["evidence_requirements"] = [_requirement("input", "Services")]
        expression = {"obligation_id": "services", "formula": "x", "variable_bindings": [
            {"variable": "x", "source_id": "inside", "source_requirement_id": "input"}],
            "source_display_candidate_id": None, "source_display_reason": "No source display", "display_unit": "COUNT"}
        self.assertEqual(self.validate({"expressions": [expression]}, [owner], catalog)["status"], "ready")
        for field in ("operand", "display", "compatibility"):
            changed = deepcopy(expression)
            if field == "operand":
                changed["variable_bindings"][0]["source_id"] = "outside"
            elif field == "display":
                changed["source_display_candidate_id"] = "outside"
            else:
                changed["compatibility_candidate_ids"] = ["witness"]
            result = self.validate({"expressions": [changed]}, [owner], catalog)
            self.assertIn("candidate_source_section_mismatch", {row["code"] for row in result["errors"]}, field)

    def test_dependency_cannot_launder_outside_section_sources(self):
        catalog = [candidate("cell", "III. Notes", kind="numeric")]
        owners = [_obligation("first", "direct_value", "Quantity"),
            _obligation("last", "derived_value", "Quantity", depends_on=["first"], source_sections=["Cedar operations"])]
        program = {"direct_bindings": [{"obligation_id": "first", "candidate_id": "cell"}], "expressions": [{
            "obligation_id": "last", "formula": "x", "variable_bindings": [{"variable": "x", "source_id": "first"}],
            "source_display_candidate_id": None, "source_display_reason": "No source display"}]}
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["cell"],
            candidate_ids_by_owner={"first": ["cell"], "last": []})
        result = self.validate(program, owners, catalog, visibility=visibility)
        self.assertIn("candidate_source_section_mismatch", {row["code"] for row in result["errors"]})
        self.assertEqual(len(result["valid_direct_bindings"]), 1)
        self.assertEqual(result["valid_expressions"], [])
        catalog[0]["source_anchor"] = "[Example | 2037 | Cedar operations]"
        self.assertEqual(self.validate(program, owners, catalog, visibility=visibility)["status"], "ready")

    def test_malformed_or_invented_section_constraints_block_raw_execution(self):
        for sections in (None, "Cedar operations", [""], ["Cedar operations >"], ["Unmentioned"]):
            with self.subTest(sections=sections):
                owner = {**self.owner, "source_sections": sections}
                result = self.validate({"narrative_bindings": [binding("services", "right")]}, [owner])
                self.assertIn("invalid_requested_source_section", {row["code"] for row in result["errors"]})
                self.assertEqual(result["valid_narrative_bindings"], [])

    def test_source_defined_group_copies_restriction_and_cannot_widen_input(self):
        owner = AnswerObligation.model_validate({**self.owner, "evidence_mode": "source_defined_group"}).model_dump()
        requirement = owner["evidence_requirements"][0]
        self.assertEqual(requirement["source_sections"], owner["source_sections"])
        self.assertIsNot(requirement["source_sections"], owner["source_sections"])
        requirement.update(requirement_id="input", source_sections=["Notes"])
        plan = _semantic_candidate_cohorts(self.catalog, [owner])
        self.assertEqual(plan["candidate_ids_by_owner"]["input"], [])
        result = self.validate({"narrative_bindings": [binding("services", "right")]}, [owner])
        self.assertIn("invalid_source_defined_group", {row["code"] for row in result["errors"]})

    def test_requirement_scope_is_independently_checked_with_overwide_visibility(self):
        self.owner["evidence_requirements"] = [{**_requirement("input", "Services"), "source_sections": ["Overview"]}]
        self.query += ' Use "Overview" for supporting evidence.'
        program = {"narrative_bindings": [{**binding("services", "right"), "evidence_bindings": [
            {"candidate_id": "right", "source_requirement_id": "input"}]}]}
        result = self.validate(program)
        self.assertTrue(any(row["owner_id"] == "input" and row["code"] == "candidate_source_section_mismatch"
            for row in result["errors"]))

    def test_source_scope_and_source_path_mutation_fail_v2_before_execution(self):
        program = {"narrative_bindings": [binding("services", "right")]}
        visibility = _semantic_candidate_visibility(self.catalog, visible_candidate_ids=["right"], candidate_ids_by_owner={"services": ["right"]})
        validation = self.validate(program, visibility=visibility)
        self.assertEqual(validation["status"], "ready")
        envelope = CompilationEnvelopeV2.create(visibility=visibility, program=program, validation=validation,
            candidate_catalog=self.catalog, obligations=[self.owner], query=self.query)
        for mutate_catalog in (True, False):
            catalog, owners = deepcopy(self.catalog), [deepcopy(self.owner)]
            if mutate_catalog:
                catalog[1]["source_anchor"] = "[Example | 2037 | III. Notes]"
            else:
                owners[0]["source_sections"] = []
            result = execute_semantic_calculation_program(program=program, obligations=owners,
                candidate_catalog=catalog, query=self.query, compilation_envelope=envelope, require_compilation_envelope=True)
            self.assertEqual(result["validation"]["errors"][0]["code"], "execution_content_mismatch")

    def test_compiler_keeps_independent_owner_spaces_and_accepted_retry_bytes(self):
        other = _obligation("notes", "narrative", "Services", source_sections=["Notes"],
                            request_unit_ids=["request_002"])
        self.query += ' Also summarize "Notes".'
        accepted = claimed_model({"narrative_bindings": [binding("services", "right")]}, self.catalog)
        bad = claimed_model({"narrative_bindings": [binding("notes", "right")]}, self.catalog)
        good = claimed_model({"narrative_bindings": [binding("notes", "wrong")]}, self.catalog)
        llm = _StructuredQueueLLM(accepted, bad, good)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(_case_state(
            {"question": self.query, "obligations": [self.owner, other]}, self.catalog))
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(json.dumps(compiled["semantic_program"]["narrative_bindings"][0], sort_keys=True),
            json.dumps(accepted.model_dump()["narrative_bindings"][0], sort_keys=True))
        for prompt, expected in zip(llm.prompts, (["right"], ["wrong"], ["wrong"])):
            content = prompt.to_messages()[0].content.split("Source bundles, candidate cohorts, and candidates_by_id:\n", 1)[1]
            payload = json.JSONDecoder().raw_decode(content.lstrip())[0]
            from tests.compiler_wire_test_support import short_ref
            self.assertEqual(sorted(payload["candidates_by_id"]), sorted(short_ref(value, "c") for value in expected))

    def test_planner_preserves_source_sections_and_blocks_invented_constraints_only(self):
        planned_response = RequirementPlannerOutput.model_validate({"topic": "services", "obligations": [
            {"request_unit_ids": ["request_001"], "obligation_id": "invented", "kind": "narrative", "label": "Services", "source_sections": ["Unmentioned section"]},
            {**self.owner, "evidence_requirements": [_requirement("evidence", "Services")]},
        ]})
        llm = _StructuredQueueLLM(planned_response, claimed_model({
            "narrative_bindings": [{**binding("ob_002", "right"), "evidence_bindings": [
                {"candidate_id": "right", "source_requirement_id": "ob_002:req_001"}]}]}, self.catalog))
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
        state = {"query": self.query, "report_scope": {}, "topic": "services", "companies": [], "years": []}
        planned = agent._plan_answer_obligation_program(state)
        self.assertEqual(planned["answer_obligations"][1]["source_sections"], ["Cedar operations"])
        self.assertTrue(any(error["code"] == "invalid_requested_source_section" for error in planned["semantic_plan"]["requirement_errors"]))
        compiled = agent._compile_semantic_calculation_program({**_case_state(
            {"question": self.query, "obligations": planned["answer_obligations"]}, self.catalog), "semantic_plan": planned["semantic_plan"]})
        self.assertEqual(len(llm.prompts), 2)  # planner plus the valid island only
        self.assertEqual(compiled["semantic_program_validation"]["missing_obligation_ids"], ["ob_001"])

    def test_retrieval_filters_before_quota_and_keeps_unrestricted_owner_union(self):
        pipeline = _Pipeline()
        pipeline.k = 1
        state = _state(companies=[], years=[], report_scope={}, query=self.query, answer_obligations=[self.owner])
        wrong = (_doc("wrong", section_path="III. Notes"), 1.0)
        right = (_doc("right", section_path="II. Cedar operations > Services"), 0.1)
        def select():
            return pipeline._select_evidence(state, pipeline._build_plan(state),
                {"docs": [wrong, right], "supplemental_docs": [wrong, right], "retry_queries": []})
        result = select()
        self.assertEqual(result["docs"], [right])
        self.assertEqual(result["seed_docs"], [right])
        state["answer_obligations"].append(_obligation("unrestricted", "narrative", "Other facts"))
        self.assertEqual(select()["docs"], [wrong])
        state["answer_obligations"] = [{**self.owner, "source_sections": ["Absent"]}]
        self.assertEqual(select()["seed_docs"], [])

    def test_local_supplement_filters_before_bounded_ranking(self):
        pipeline = _Pipeline()
        metadata = [{"chunk_uid": f"wrong-{index}", "section_path": "Notes"} for index in range(8)]
        metadata.append({"chunk_uid": "right", "section_path": "Cedar operations"})
        pipeline.vsm = SimpleNamespace(bm25_docs=["Services measurement 42"] * len(metadata), bm25_metadatas=metadata)
        state = _state(companies=[], years=[], report_scope={}, query=self.query, answer_obligations=[self.owner])
        with patch("src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query", return_value=["Services"]), \
             patch("src.agent.financial_retrieval_pipeline._active_preferred_sections", return_value=[]), \
             patch("src.agent.financial_retrieval_pipeline._active_preferred_statement_types", return_value=[]):
            selected = pipeline._supplement_section_seed_docs(state)
        self.assertEqual([doc.metadata["chunk_uid"] for doc, _ in selected], ["right"])


if __name__ == "__main__":
    unittest.main()
