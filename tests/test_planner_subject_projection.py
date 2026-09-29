"""Authored planner projections and transport, not model inference/accuracy.

Names are anonymous. Authored source-link witnesses test transport, not a model's
ability to distinguish names, groups or free scope descriptions.
"""
from copy import deepcopy
from itertools import product
import json
import unittest

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram, SemanticTargetV1
from src.agent.financial_graph_planning import preserve_query_subject_surfaces
from src.agent.financial_request_units import build_request_units
from src.config.retrieval_policy import PLANNING_POLICY
from tests.semantic_program_test_support import FinancialAgent, _candidate, _StructuredQueueLLM
from tests.test_narrative_retry_context import prompt_json


def authored_owner(subjects, *, key="raw-output", kind="direct_value", scope=None, requirements=()):
    return {"obligation_id": key, "request_unit_ids": ["request_001"], "kind": kind,
        "label": "Quantity", "display_unit": "COUNT",
        "scope": {"period": "2042", **(scope or {})},
        "semantic_target": {"local_subjects": list(subjects), "metric_surfaces": ["quantity"]},
        "evidence_requirements": deepcopy(list(requirements))}


def cell(subject, cid="cell", **overrides):
    return {**_candidate(cid, 23, period=overrides.get("period", "2042")), "year": 2042, "company": "Issuer",
        "document_company": "Issuer", "row_headers": ["quantity", *([overrides["segment"]] if overrides.get("segment") else [])],
        "column_headers": ["Operating groups", subject], "physical_table_id": "table",
        "physical_row_id": f"row-{cid}", "physical_cell_id": cid, **overrides}


def direct(cid="cell", oid="ob_001"):
    return SemanticCalculationProgram.model_validate({"status": "ready", "direct_bindings": [
        {"obligation_id": oid, "candidate_id": cid}]})


def agent_for(llm):
    agent = FinancialAgent.__new__(FinancialAgent)
    agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
    return agent


def plan(query, owners):
    raw = RequirementPlannerOutput.model_validate({"obligations": owners})
    before = deepcopy(raw.model_dump())
    llm = _StructuredQueueLLM(raw)
    result = agent_for(llm)._build_llm_requirement_plan(query=query, topic="quantity",
        intent="qa", report_scope={"company": "Issuer", "year": 2042})
    assert before == raw.model_dump()
    assert len(llm.prompts) == 1
    assert not result["requirement_errors"]
    return result, llm


def validate(query, owners, candidates, program=None):
    from tests.source_interpretation_fixture_support import authored_source_program
    return validate_semantic_calculation_program(program=authored_source_program((program or direct()).model_dump(), owners, candidates, query),
        obligations=owners, candidate_catalog=candidates, query=query)


class PlannerSubjectProjectionTests(unittest.TestCase):
    def test_model_facing_contract_distinguishes_identity_from_request_constraints(self):
        description = SemanticTargetV1.model_json_schema()["properties"]["local_subjects"]["description"]
        for instruction in ("reading", "request", "group", "not an allowlist"):
            self.assertIn(instruction, description)
        prompt = PLANNING_POLICY["requirement_planner_prompt_template"]
        for instruction in ("요청 표현", "설명 표현", "집단", "evidence requirement", "request_unit_ids"):
            self.assertIn(instruction, prompt)

    def test_named_identity_and_full_request_conditions_survive_both_owner_levels(self):
        for kind, (subject, wrapper) in product(("direct_value", "derived_value"),
                (("Aster", "division"), ("Birch", "unit"), ("별빛", "부문"))):
            with self.subTest(kind=kind, subject=subject):
                query = f"Return 2042 quantity for the {subject} {wrapper}; use the Northern area and exclude transfers."
                target = {"local_subjects": [subject], "metric_surfaces": ["quantity"]}
                requirements = ([{"requirement_id": "raw-input", "label": "Quantity", "semantic_target": target}]
                    if kind == "derived_value" else [])
                raw = authored_owner([subject], kind=kind, scope={"segment": "Northern", "basis": "excluding transfers"},
                    requirements=requirements)
                result, llm = plan(query, [raw])
                owner = result["answer_obligations"][0]
                self.assertEqual(len(owner["evidence_requirements"]), len(requirements))
                for item in (owner, *owner["evidence_requirements"]):
                    self.assertEqual(item["semantic_target"]["local_subjects"], [subject])
                    self.assertEqual(item["scope"]["segment"], "Northern")
                    self.assertEqual(item["scope"]["basis"], "excluding transfers")
                    self.assertEqual(item["scope"]["company"], "Issuer")
                self.assertEqual(owner["request_unit_ids"], ["request_001"])
                self.assertEqual(build_request_units(query)[0].text, query)
                self.assertIn("질문:\n" + query + "\n", llm.prompts[0].to_messages()[0].content)
                self.assertIn(query, result["retrieval_queries"])

    def test_complete_names_and_identity_qualifiers_are_not_shortened(self):
        for subject, wrong in (("Aster Services", "Aster"), ("Aster East", "Aster West"),
                               ("Lumen Division", "Lumen"), ("별빛 연구소", "별빛")):
            with self.subTest(subject=subject):
                query = f"The complete unit name is {subject}; return its 2042 quantity."
                result, _ = plan(query, [authored_owner([subject])])
                owners = result["answer_obligations"]
                self.assertEqual(owners[0]["semantic_target"]["local_subjects"], [subject])
                self.assertEqual(validate(query, owners, [cell(subject)])["status"], "ready")
                invalid = validate(query, owners, [cell(wrong)])
                self.assertEqual(invalid["status"], "ready")
                self.assertEqual(invalid["valid_direct_bindings"][0]["source_interpretation_resolution"]["validation_scope"],
                                 "source_linkage_not_semantic_equivalence")

    def test_group_and_member_are_distinct_even_when_a_name_is_shared(self):
        for subject, foreign in (("Aster", "Aster and other participants"),
                                 ("Aster and other participants", "Aster"),
                                 ("별빛 등", "별빛")):
            query = f"Return the 2042 quantity for {subject}."
            result, _ = plan(query, [authored_owner([subject])])
            self.assertEqual(validate(query, result["answer_obligations"], [cell(subject)])["status"], "ready")
            invalid = validate(query, result["answer_obligations"], [cell(foreign, local_entity_surfaces=[subject])])
            self.assertEqual(invalid["status"], "ready")  # Deliberately wrong semantic selection with its own axes.

    def test_only_query_written_bilingual_forms_are_preserved(self):
        query = "별빛(Starbeam) 부문의 2042년 수량을 알려줘."
        result, _ = plan(query, [authored_owner(["별빛"])])
        owners = result["answer_obligations"]
        self.assertEqual(owners[0]["semantic_target"]["local_subjects"], ["별빛", "Starbeam"])
        for spelling in ("별빛", "Starbeam"):
            self.assertEqual(validate(query, owners, [cell(spelling)])["status"], "ready")
        self.assertEqual(validate(query, owners, [cell("Starbeam Services")])["status"], "ready")
        self.assertEqual(preserve_query_subject_surfaces("별빛 부문의 수량", ["별빛"]), ["별빛"])

    def test_derived_inputs_keep_their_own_named_subjects(self):
        query = "Add the 2042 quantities for Aster division and Birch unit."
        raw = authored_owner([], kind="derived_value", requirements=[{
            "requirement_id": subject, "label": "Quantity", "semantic_target": {"local_subjects": [subject]}}
            for subject in ("Aster", "Birch")])
        result, _ = plan(query, [raw])
        owners = result["answer_obligations"]
        requirements = owners[0]["evidence_requirements"]
        self.assertEqual([r["semantic_target"]["local_subjects"] for r in requirements], [["Aster"], ["Birch"]])
        program = SemanticCalculationProgram.model_validate({"status": "ready", "expressions": [{
            "obligation_id": "ob_001", "formula": "A+B", "source_display_candidate_id": None,
            "source_display_reason": "No reported combined display.", "display_unit": "COUNT",
            "variable_bindings": [{"variable": symbol, "source_id": symbol, "source_requirement_id": req["requirement_id"]}
                for symbol, req in zip(("A", "B"), requirements)]}]})
        catalog = [cell("Aster", "A"), cell("Birch", "B")]
        self.assertEqual(validate(query, owners, catalog, program)["status"], "ready")
        invalid = validate(query, owners, [catalog[0], cell("Aster", "B")], program)
        self.assertEqual(invalid["status"], "ready")  # Meaning is not certified by source linkage.

    def test_identity_match_does_not_override_wrong_period_region_or_basis(self):
        query = "Return Aster division's 2042 Northern-area quantity, excluding transfers."
        result, _ = plan(query, [authored_owner(["Aster"], scope={"segment": "Northern", "basis": "excluding transfers"})])
        source = cell("Aster", segment="Northern", basis="excluding transfers")
        self.assertEqual(validate(query, result["answer_obligations"], [source])["status"], "ready")
        for key, value in (("period", "2041"), ("segment", "Southern"), ("basis", "including transfers")):
            with self.subTest(key=key):
                changed = cell("Aster", **{"segment": "Northern", "basis": "excluding transfers", key: value})
                status = validate(query, result["answer_obligations"], [changed])["status"]
                self.assertEqual(status, "invalid" if key == "period" else "ready")

    def test_retry_preserves_named_targets_original_qualifiers_and_other_accepted_output(self):
        query = "Return the 2042 quantities for Birch unit and Aster division, excluding transfers."
        planner = RequirementPlannerOutput.model_validate({"obligations": [
            authored_owner([subject], key=subject, scope={"basis": "excluding transfers"}) for subject in ("Birch", "Aster")]})
        accepted, wrong, corrected = direct("stable"), direct("group", "ob_002"), direct("exact", "ob_002")
        llm = _StructuredQueueLLM(planner, accepted, wrong, corrected)
        agent = agent_for(llm)
        result = agent._build_llm_requirement_plan(query=query, topic="quantity", intent="qa", report_scope={"company": "Issuer", "year": 2042})
        catalog = [cell(subject, cid, basis="excluding transfers") for subject, cid in
            (("Birch", "stable"), ("Aster and others", "group"), ("Aster", "exact"))]
        owners = result["answer_obligations"]
        from tests.source_interpretation_fixture_support import authored_source_program
        accepted = SemanticCalculationProgram.model_validate(authored_source_program(accepted.model_dump(), owners, catalog, query))
        corrected = SemanticCalculationProgram.model_validate(authored_source_program(corrected.model_dump(), owners, catalog, query))
        wrong = deepcopy(corrected.model_dump())
        wrong["direct_bindings"][0]["candidate_id"] = "group"  # Borrowing another cell's axes is a physical failure.
        llm.responses = [accepted, SemanticCalculationProgram.model_validate(wrong), corrected]
        before = deepcopy((owners, catalog))
        compiled = agent._compile_semantic_calculation_program({"query": query, "answer_obligations": owners,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog})
        self.assertEqual(len(llm.prompts), 4)  # One planner, two islands, one existing retry.
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(json.dumps(compiled["semantic_program"]["direct_bindings"][0], sort_keys=True),
            json.dumps(accepted.model_dump()["direct_bindings"][0], sort_keys=True))
        for prompt in llm.prompts[-2:]:
            self.assertEqual(prompt_json(prompt, "Answer obligations:"), [owners[1]])
            self.assertIn("원본 질문:\n" + query + "\n", prompt.to_messages()[0].content)
        self.assertEqual((owners, catalog), before)
        changed = deepcopy(owners)
        changed[1]["semantic_target"]["local_subjects"] = ["Aster and others"]
        execution = execute_semantic_calculation_program(program=compiled["semantic_program"], obligations=changed,
            candidate_catalog=catalog, query=query, compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual(execution["validation"]["errors"][0]["code"], "execution_content_mismatch")

    def test_structural_validation_does_not_certify_planner_identity_interpretation(self):
        # Deliberately wrong authored plan: no semantic-success claim. Code does
        # not infer the complete requested name from its own suffix/name rules.
        query = "Return the 2042 quantity for the company named Aster Services."
        result, _ = plan(query, [authored_owner(["Aster"])])
        self.assertEqual(validate(query, result["answer_obligations"], [cell("Aster")])["status"], "ready")


if __name__ == "__main__":
    unittest.main()
