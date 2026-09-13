"""Observed section selection, separate from exact request wording; no providers."""
from copy import deepcopy
from tests.narrative_address_test_support import model_program
import json
from types import SimpleNamespace
import unittest

from pydantic import ValidationError

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_compiler_presentation import project_output_responsibility_context
from src.agent.financial_graph_calculation import _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_graph_models import AnswerObligation, RequirementPlannerOutput, SemanticCalculationProgram, SourceSectionBindingV1
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.agent.financial_source_scope import (
    build_source_section_inventory, resolve_source_section_bindings,
    source_section_allowed_for_query, source_section_applicability, source_section_requirement_errors,
)
from tests.semantic_program_test_support import FinancialAgent, _StructuredQueueLLM, _candidate, _obligation
from tests.test_retrieval_scope_isolation import _Pipeline, _doc, _state


def metadata(path="II. Operations > 1. Overview", receipt="filing-A", **extra):
    return {"company": "Issuer", "year": 2042, "rcept_no": receipt, "section_path": path, **extra}


def inventory():
    return build_source_section_inventory([metadata(), metadata("III. Notes"), metadata(receipt="filing-B")])


def section_id(path="II. Operations > 1. Overview", receipt="filing-A", source=None):
    return next(row["section_id"] for row in (source or inventory())["sections"]
        if row["document_id"] == f"rcept_no:{receipt}" and row["path"] == path.split(" > "))


def request_binding(text="operating overview", ids=None, unit_id="request_001"):
    return {"request_unit_id": unit_id, "requested_text": text, "section_ids": ids if ids is not None else [section_id()]}


def requested(*bindings, **extra):
    return _obligation("answer", "narrative", "Describe activities.",
        source_section_bindings=list(bindings or [request_binding()]), **extra)


def resolve(owner=None, query="Use the operating overview.", source=None):
    return resolve_source_section_bindings([owner or requested()], query=query, inventory=source or inventory())[0]


def candidate(cid="inside", path="II. Operations > 1. Overview", receipt="filing-A"):
    return {**_candidate(cid, 0), "kind": "narrative", "candidate_kind": "chunk", "year": 2042,
        "normalized_value": None, "raw_value": "", "raw_unit": "", "normalized_unit": "UNKNOWN",
        "source_document_id": f"rcept_no:{receipt}", "section_path": path,
        "source_text": "Birch operates a workshop.", "source_bundle_text": "Birch operates a workshop."}


def program(cid="inside", owner_id="answer", *, quote="Birch operates a workshop."):
    return model_program({"status": "ready", "narrative_bindings": [{
        "obligation_id": owner_id, "claims": [{"subject": "Birch", "text": "operates a workshop.",
            "evidence_bindings": [{"candidate_id": cid, "evidence_text": quote}]}]}]}, [candidate(cid)])


class SourceSectionBindingTests(unittest.TestCase):
    def test_inventory_is_source_qualified_deterministic_and_input_owned(self):
        rows = [metadata(), metadata(), metadata(receipt="filing-B"),
            metadata(section_path="", local_heading="Invented title", source_text="III. Notes"),
            metadata(rcept_no="", section_path="Unknown filing")]
        before = deepcopy(rows)
        first = build_source_section_inventory(rows)
        self.assertEqual(first, build_source_section_inventory(list(reversed(rows))))
        self.assertEqual(first["visible_section_count"], 4)
        self.assertEqual(first["unlocated_metadata_count"], 2)
        self.assertNotEqual(section_id(receipt="filing-A", source=first), section_id(receipt="filing-B", source=first))
        first["sections"][0]["path"].append("mutated")
        self.assertEqual(rows, before)

    def test_inventory_limits_are_observable_and_omitted_ids_cannot_be_selected(self):
        rows = [metadata(), metadata("III. Notes")]
        limited = build_source_section_inventory(rows, max_sections=1)
        self.assertTrue(limited["truncated"])
        self.assertEqual(limited["omitted_section_count"], 2)
        self.assertEqual(limited["coverage"], "observed_paths_only")
        owner = resolve(source=limited)
        self.assertIn("unknown_source_section_id", {e["code"] for e in source_section_requirement_errors([owner], "Use the operating overview.")})
        tiny = build_source_section_inventory(rows, max_bytes=2)
        self.assertEqual(tiny["sections"], [])
        self.assertTrue(tiny["truncated"])

    def test_informal_request_retains_its_exact_span_and_resolves_observed_title(self):
        query = "Please use the operating overview."
        raw, source = requested(), inventory()
        before = deepcopy((raw, source))
        owner = resolve(raw, query, source)
        self.assertEqual(source_section_requirement_errors([owner], query), [])
        binding = owner["source_section_bindings"][0]
        self.assertEqual(query[slice(*binding["request_span"])], "operating overview")
        self.assertEqual(binding["resolved_sections"][0]["path"], ["II. Operations", "1. Overview"])
        self.assertEqual(source_section_applicability(candidate(), owner)["state"], "match")
        self.assertEqual((raw, source), before)

    def test_unicode_request_text_is_not_normalized_and_offsets_are_python_indices(self):
        query = "🗂 가상 조직의 활동 설명에서 요약해 줘."
        owner = resolve(requested(request_binding("활동 설명")), query)
        self.assertEqual(source_section_requirement_errors([owner], query), [])
        span = owner["source_section_bindings"][0]["request_span"]
        self.assertEqual(query[slice(*span)], "활동 설명")
        bad = resolve(requested(request_binding("활동  설명")), query)
        self.assertTrue(source_section_requirement_errors([bad], query))

    def test_foreign_request_unit_invented_text_and_ambiguous_quote_fail_closed(self):
        for binding, query in ((request_binding(unit_id="request_002"), "First request. Use operating overview."),
                               (request_binding("unwritten"), "Use operating overview."),
                               (request_binding(), "operating overview and operating overview")):
            with self.subTest(query=query):
                owner = resolve(requested(binding), query)
                self.assertEqual(source_section_applicability(candidate(), owner)["state"], "invalid")
                self.assertTrue(source_section_requirement_errors([owner], query))

    def test_unresolved_and_unknown_ids_are_errors_not_unrestricted_scopes(self):
        for ids, code in (([], "unresolved_source_section_request"), (["invented"], "unknown_source_section_id")):
            owner = resolve(requested(request_binding(ids=ids)))
            errors = source_section_requirement_errors([owner], "Use the operating overview.")
            self.assertEqual([row["code"] for row in errors], [code])
            self.assertFalse(source_section_allowed_for_query(candidate(), [owner]))

    def test_model_cannot_supply_its_own_resolution_or_source_location(self):
        for key, value in (("resolved_sections", []), ("request_span", [0, 3]), ("inventory_fingerprint", "made-up")):
            with self.subTest(key=key), self.assertRaises(ValidationError):
                SourceSectionBindingV1.model_validate({**request_binding(), key: value})

    def test_literal_named_path_cannot_be_reinterpreted_as_a_foreign_section(self):
        query = "Use Operations > Overview."
        good = resolve(requested(request_binding("Operations > Overview")), query)
        self.assertEqual(source_section_requirement_errors([good], query), [])
        bad = resolve(requested(request_binding("Operations > Overview", [section_id("III. Notes")])), query)
        self.assertEqual(source_section_requirement_errors([bad], query)[0]["code"], "explicit_source_section_conflict")

    def test_descendants_match_but_same_title_in_another_filing_or_branch_does_not(self):
        owner = resolve()
        for source, expected in ((candidate(path="II. Operations > 1. Overview > Detail"), "match"),
                                  (candidate(receipt="filing-B"), "conflict"),
                                  (candidate(path="I. Elsewhere > II. Operations > 1. Overview"), "conflict"),
                                  ({**candidate(), "source_document_id": ""}, "unknown")):
            self.assertEqual(source_section_applicability(source, owner)["state"], expected)

    def test_parent_and_required_input_intersect_instead_of_widening(self):
        parent = requested(request_binding(ids=[section_id("II. Operations")]), evidence_requirements=[{
            "requirement_id": "input", "label": "Detail", "source_section_bindings": [request_binding()]}])
        resolved = resolve(parent)
        requirement = resolved["evidence_requirements"][0]
        self.assertEqual(source_section_applicability(candidate(), requirement, resolved)["state"], "match")
        parent["evidence_requirements"][0]["source_section_bindings"] = [request_binding(ids=[section_id("III. Notes")])]
        resolved = resolve(parent)
        self.assertEqual(source_section_applicability(candidate(path="III. Notes"), resolved["evidence_requirements"][0], resolved)["state"], "conflict")

    def test_legacy_literal_constraint_remains_an_independent_intersection(self):
        owner = resolve(requested(source_sections=["Notes"]), "Use the operating overview, only Notes.")
        self.assertEqual(source_section_requirement_errors([owner], "Use the operating overview, only Notes."), [])
        self.assertEqual(source_section_applicability(candidate(), owner)["state"], "conflict")

    def test_validator_checks_section_authority_even_if_visibility_is_overwide(self):
        owner, catalog = resolve(), [candidate(), candidate("outside", receipt="filing-B")]
        cohorts = _semantic_candidate_cohorts(catalog, [owner])
        self.assertEqual(cohorts["visible_candidate_ids"], ["inside"])
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["inside", "outside"],
            candidate_ids_by_owner={"answer": ["inside", "outside"]})
        for cid, expected in (("inside", "ready"), ("outside", "invalid")):
            validation = validate_semantic_calculation_program(program=program(cid).model_dump(), obligations=[owner],
                candidate_catalog=catalog, candidate_visibility=visibility, query="Use the operating overview.", require_narrative_claims=True)
            self.assertEqual(validation["status"], expected)
            if cid == "outside":
                self.assertIn("candidate_source_section_mismatch", {error["code"] for error in validation["errors"]})

    def test_v2_binds_request_reference_and_selected_physical_source_location(self):
        owner, catalog, selected = resolve(), [candidate()], program().model_dump()
        query = "Use the operating overview."
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=["inside"], candidate_ids_by_owner={"answer": ["inside"]})
        valid = validate_semantic_calculation_program(program=selected, obligations=[owner], candidate_catalog=catalog,
            candidate_visibility=visibility, query=query, require_narrative_claims=True)
        self.assertEqual(valid["status"], "ready")
        envelope = CompilationEnvelopeV2.create(program=selected, validation=valid, visibility=visibility,
            candidate_catalog=catalog, obligations=[owner], query=query)
        for key, value in (("requested_text", "another request"), ("section_ids", ["hidden"]),
                           ("request_span", [0, 1]), ("resolved_sections", []), ("inventory_fingerprint", "changed")):
            changed = deepcopy(owner)
            changed["source_section_bindings"][0][key] = value
            result = execute_semantic_calculation_program(program=selected, obligations=[changed], candidate_catalog=catalog,
                query=query, compilation_envelope=envelope, require_compilation_envelope=True)
            self.assertEqual(result["validation"]["errors"][0]["code"], "execution_content_mismatch")

    def test_planner_receives_only_scoped_metadata_and_copies_model_inputs(self):
        raw = {**requested(), "scope": {"company": "Issuer", "period": "2042"}}
        response = RequirementPlannerOutput.model_validate({"obligations": [raw]})
        before = deepcopy(response.model_dump())
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = _StructuredQueueLLM(response), {}, None
        rows = [metadata(), metadata(receipt="filing-B"), metadata(receipt="filing-C", company="Foreign")]
        agent.vsm = SimpleNamespace(bm25_metadatas=rows)
        state = {"query": "Use the operating overview.", "report_scope": {"rcept_no": "filing-A", "company": "Issuer", "year": 2042}}
        planned = agent._plan_answer_obligation_program(state)
        self.assertEqual(response.model_dump(), before)
        self.assertEqual(len(agent.llm.prompts), 1)
        seen = planned["semantic_plan"]["source_section_inventory"]
        self.assertTrue(all(row["document_id"] == "rcept_no:filing-A" for row in seen["sections"]))
        prompt = agent.llm.prompts[0].to_messages()[0].content
        self.assertIn(section_id(), prompt)
        self.assertNotIn("filing-B", prompt)
        self.assertNotIn("Foreign", prompt)
        self.assertEqual(planned["semantic_plan"]["requirement_errors"], [])
        self.assertEqual(source_section_applicability(candidate(), planned["answer_obligations"][0])["state"], "match")

    def test_source_defined_group_copies_binding_without_shared_mutation(self):
        parsed = AnswerObligation.model_validate(requested(evidence_mode="source_defined_group"))
        raw = parsed.model_dump()
        self.assertEqual(raw["source_section_bindings"], raw["evidence_requirements"][0]["source_section_bindings"])
        self.assertIsNot(parsed.source_section_bindings[0], parsed.evidence_requirements[0].source_section_bindings[0])
        resolved = resolve(raw)
        self.assertEqual(resolved["source_section_bindings"], resolved["evidence_requirements"][0]["source_section_bindings"])

    def test_required_group_binding_is_validated_and_cannot_drop_its_restriction(self):
        owner = resolve(AnswerObligation.model_validate(requested(evidence_mode="source_defined_group")).model_dump())
        owner["evidence_requirements"][0]["requirement_id"] = "answer:input"
        selected = program().model_dump()
        binding = selected["narrative_bindings"][0]
        for link in [*binding["evidence_bindings"], *binding["claims"][0]["fact_evidence_selections"],
                     *binding["subject_bindings"][0]["evidence_selections"]]:
            link["source_requirement_id"] = "answer:input"
        def validate(obligation):
            return validate_semantic_calculation_program(program=selected, obligations=[obligation],
                candidate_catalog=[candidate()], query="Use the operating overview.", require_narrative_claims=True)
        self.assertEqual(validate(owner)["status"], "ready")
        changed = deepcopy(owner)
        changed["evidence_requirements"][0]["source_section_bindings"] = []
        self.assertIn("invalid_source_defined_group", {e["code"] for e in validate(changed)["errors"]})

    def test_same_cohort_retry_preserves_resolution_and_other_accepted_program_bytes(self):
        fixed, bound = _obligation("stable", "narrative", "Other activities."), resolve()
        accepted = program("outside", "stable")
        rejected = program(quote="An unwritten quotation.")
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StructuredQueueLLM(accepted, rejected, program())
        catalog = [candidate(), candidate("outside", receipt="filing-B")]
        before = deepcopy(bound)
        compiled = agent._compile_semantic_calculation_program({"query": "Use the operating overview.",
            "answer_obligations": [fixed, bound], "semantic_candidate_catalog_prebuilt": True,
            "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog})
        self.assertEqual(len(agent.llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        actual = compiled["semantic_program"]["narrative_bindings"][0]
        self.assertEqual(json.dumps(actual, sort_keys=True), json.dumps(accepted.model_dump()["narrative_bindings"][0], sort_keys=True))
        for prompt in agent.llm.prompts[-2:]:
            text = prompt.to_messages()[0].content
            self.assertIn(json.dumps(bound["source_section_bindings"], ensure_ascii=False, separators=(",", ":")), text)
        self.assertEqual(bound, before)

    def test_tampered_or_unresolved_runtime_projection_is_not_a_literal_fallback(self):
        original = resolve()
        for key, value in (("resolved_sections", []), ("section_ids", ["hidden"]),
                           ("request_span", [0, 2]), ("requested_text", "different")):
            changed = deepcopy(original)
            changed["source_section_bindings"][0][key] = value
            self.assertTrue(source_section_requirement_errors([changed], "Use the operating overview."))
        for raw in (None, "path", [None], [{}]):
            owner = {**original, "source_section_bindings": raw}
            self.assertEqual(source_section_applicability(candidate(), owner)["state"], "invalid")
            self.assertTrue(source_section_requirement_errors([owner], "Use the operating overview."))

    def test_unresolved_owner_makes_no_compiler_call_but_keeps_valid_island(self):
        invalid, valid = resolve(requested(request_binding(ids=[]))), resolve()
        invalid["obligation_id"] = "missing"
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = _StructuredQueueLLM(program())
        catalog = [candidate()]
        compiled = agent._compile_semantic_calculation_program({"query": "Use the operating overview.",
            "answer_obligations": [invalid, valid], "semantic_candidate_catalog_prebuilt": True,
            "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog})
        self.assertEqual(len(agent.llm.prompts), 1)
        self.assertEqual(compiled["semantic_program_validation"]["missing_obligation_ids"], ["missing"])
        self.assertEqual([b["obligation_id"] for b in compiled["semantic_program_validation"]["valid_narrative_bindings"]], ["answer"])
        prompt = agent.llm.prompts[0].to_messages()[0].content
        self.assertIn('"requested_text":"operating overview"', prompt)
        self.assertIn(section_id(), prompt)

    def test_retrieval_filters_seed_and_final_sources_with_the_same_resolution(self):
        pipeline = _Pipeline()
        pipeline.k = 1
        owner = resolve()
        state = _state(query="Use the operating overview.", companies=[], years=[], report_scope={}, answer_obligations=[owner])
        inside, outside = (_doc("inside", **metadata()), 0.2), (_doc("outside", **metadata(receipt="filing-B")), 1.0)
        selected = pipeline._select_evidence(state, pipeline._build_plan(state),
            {"docs": [outside, inside], "supplemental_docs": [outside, inside], "retry_queries": []})
        self.assertEqual(selected["docs"], [inside])
        self.assertEqual(selected["seed_docs"], [inside])
        # Responsibility is copied context, not mutable authorization.
        context = project_output_responsibility_context(state["query"], [owner])
        context["outputs"][0]["source_section_bindings"][0]["section_ids"].clear()
        self.assertEqual(owner["source_section_bindings"][0]["section_ids"], [section_id()])


if __name__ == "__main__":
    unittest.main()
