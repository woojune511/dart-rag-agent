"""Authored execution/prompt controls, not sampled-model semantic accuracy."""

from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_source_interpretation import interpretation_axis_sources
from tests.semantic_program_test_support import _candidate, _obligation, _requirement, _scope
from tests.formula_wire_test_support import formula_ast, formula_steps


def cell(identifier, value, axes, year):
    return {**_candidate(identifier, value, period=str(year), row_label=axes[-1]),
        "year": year, "source_anchor": f"[synthetic | {year} | quantity]",
        "row_headers": list(axes), "column_headers": [str(year), "quantity"],
        "physical_table_id": "table", "physical_row_id": "row-" + identifier,
        "physical_cell_id": "cell-" + identifier}


def selection(refs, source, subject):
    return {"source_ref": refs.ref(source["candidate_id"]), "interpretation": {
        "request_unit_ids": ["request_001"], "subject": subject, "metric": "quantity"}}


def comparison(current=60, previous=75, year=2051):
    catalog = [cell("current-cell", current, ["Current period"], year),
               cell("previous-cell", previous, ["Previous period"], year - 1)]
    owner = _obligation("answer", "derived_value", "growth", display_unit="%", evidence_requirements=[
        _requirement("current", "current quantity", period=str(year)),
        _requirement("previous", "previous quantity", period=str(year - 1))])
    return catalog, owner


def calculation(catalog, formula, *, swap_source=False):
    def respond(refs):
        current, previous = catalog
        return {"inputs": {
            "current": [{**selection(refs, previous if swap_source else current, "quantity"), "variable": "A"}],
            "previous": [{**selection(refs, previous, "quantity"), "variable": "B"}]},
            # Legacy authored formula witness, not a new comparison interpretation.
            "comparison_request_unit_id": None, "formula": formula_steps(formula), "display_unit": "%", "source_display": None,
            "source_display_reason": "The request asks for a calculated comparison."}
    return respond


class AuthoredReadingLLM:
    """Fixed wire responses; deliberately does not infer meaning from prompts."""

    def __init__(self, respond, *, status="ready", rationale="", invalid_first=False):
        self.respond, self.status, self.rationale = respond, status, rationale
        self.invalid_first, self.models, self.prompts = invalid_first, [], []

    def with_structured_output(self, model):
        self.models.append(model)
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        model = self.models[-1]
        result = self.respond(model.__compiler_references__) if self.respond else None
        if self.invalid_first and len(self.prompts) == 1:
            result["unavailable_field"] = True
        return model.model_validate({"outputs": {"answer": {"status": self.status, "result": result}},
                                     "rationale": self.rationale})


def compile_case(catalog, owner, query, llm):
    agent = object.__new__(FinancialAgent)
    agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
    state = {"query": query, "answer_obligations": [owner], "include_debug_bundle": True,
        "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog,
        "semantic_candidate_catalog": catalog}
    return agent._compile_semantic_calculation_program(state)


def execute(compiled, catalog, owner, query):
    return execute_semantic_calculation_program(program=compiled["semantic_program"],
        obligations=[owner], candidate_catalog=catalog, query=query,
        compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)


class CompilerNumericReadingIntentTests(unittest.TestCase):
    def test_direction_guidance_and_exact_query_survive_same_cohort_retry(self):
        catalog, owner = comparison()
        query = "이 보고서의 현재 기간에서 이전 기간으로의 변화율을 계산하세요."
        llm = AuthoredReadingLLM(calculation(catalog, "(B - A) / A * 100"), invalid_first=True)
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 2)
        for prompt in llm.prompts:
            text = prompt.to_messages()[0].content
            self.assertIn(query, text)
            self.assertTrue("입력의 기간 라벨이나 나열 순서는 비교 방향을 정하지 않습니다" in text,
                            "Input labels/order must not dictate comparison direction.")
            self.assertTrue("기준점과 비교점을 먼저 해석" in text, "Request must determine baseline and target.")
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
        self.assertEqual(attempts[0]["visible_candidate_ids"], attempts[1]["visible_candidate_ids"])
        self.assertEqual(execute(compiled, catalog, owner, query)["outputs_by_obligation"]["answer"]["calculated_value"], 25)

    def test_reported_row_guidance_survives_retry_without_a_new_schema_field(self):
        parent = cell("parent", 31, ["Birch"], 2052)
        child = cell("child", 31, ["Birch", "Birch Research"], 2052)
        owner = _obligation("answer", "direct_value", "quantity", semantic_target={
            "local_subjects": ["Birch"], "concept_keys": [], "metric_surfaces": ["quantity"]})
        llm = AuthoredReadingLLM(lambda refs: {"selection": selection(refs, parent, "Birch")}, invalid_first=True)
        compiled = compile_case([parent, child], owner, "Return the reported Birch quantity.", llm)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 2)
        for prompt in llm.prompts:
            text = prompt.to_messages()[0].content
            self.assertTrue("보고된 행의 조회와 여러 행의 합산 요청을 구별" in text,
                            "A reported-row lookup must be distinguished from aggregation.")
            self.assertTrue("실제 대안 해석이나 필요한 근거의 공백" in text,
                            "Abstention must identify a real evidence/interpretation gap.")
        props = llm.models[-1].model_json_schema()["$defs"]["Direct_answer"]["properties"]
        self.assertEqual(set(props), {"selection", "compatibility_refs"})

    def test_authored_directions_ignore_calendar_and_candidate_order_without_changing_signs(self):
        for current, previous, year in ((60, 75, 2051), (144, 96, 2037), (-20, -50, 2064)):
            catalog, owner = comparison(current, previous, year)
            for formula, expected, request in (
                ("(A - B) / B * 100", (current - previous) / previous * 100, "previous to current"),
                ("(B - A) / A * 100", (previous - current) / current * 100, "current to previous")):
                for reordered in (catalog, list(reversed(catalog))):
                    with self.subTest(current=current, previous=previous, request=request, reversed=reordered != catalog):
                        before = deepcopy((reordered, owner))
                        query = f"Calculate percentage change from {request} in the {year} report."
                        llm = AuthoredReadingLLM(calculation(catalog, formula))
                        compiled = compile_case(reordered, owner, query, llm)
                        result = execute(compiled, reordered, owner, query)
                        self.assertEqual(result["status"], "ok")
                        self.assertAlmostEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], expected)
                        self.assertEqual(formula_ast(compiled["semantic_program"]["expressions"][0]["formula"]), formula_ast(formula))
                        self.assertEqual((reordered, owner), before)
                        self.assertEqual(len(llm.prompts), 1)

    def test_wrong_direction_remains_a_semantic_negative_not_silently_repaired(self):
        catalog, owner = comparison()
        query = "Calculate percentage change from current to previous."
        llm = AuthoredReadingLLM(calculation(catalog, "(A - B) / B * 100"))
        compiled = compile_case(catalog, owner, query, llm)
        result = execute(compiled, catalog, owner, query)
        self.assertEqual(result["status"], "ok")  # Linkage/arithmetic, not meaning.
        self.assertEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], -20)
        self.assertNotEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], 25)
        self.assertEqual(len(llm.prompts), 1)

    def test_parent_and_child_equal_values_keep_distinct_axes_and_shared_visibility(self):
        for name, suffix, year, value in (("Birch", "Research", 2052, 31), ("Lumen", "Labs", 2036, 57)):
            catalog = [cell("parent", value, [name], year), cell("child", value, [name, name + " " + suffix], year)]
            for chosen in catalog:
                subject = chosen["row_headers"][-1]
                owner = _obligation("answer", "direct_value", "quantity", scope=_scope(period=str(year)),
                    semantic_target={"local_subjects": [subject], "concept_keys": [], "metric_surfaces": ["quantity"]})
                for reordered in (catalog, list(reversed(catalog))):
                    with self.subTest(subject=subject, reversed=reordered != catalog):
                        query = f"Return the reported {subject} quantity for {year}."
                        llm = AuthoredReadingLLM(lambda refs: {"selection": selection(refs, chosen, subject)})
                        compiled = compile_case(reordered, owner, query, llm)
                        visibility = compiled["semantic_compilation_envelope"].visibility
                        self.assertEqual(set(visibility.visible_candidate_ids), {"parent", "child"})
                        result = execute(compiled, reordered, owner, query)
                        self.assertEqual(result["status"], "ok")
                        self.assertEqual(result["outputs_by_obligation"]["answer"]["candidate_ids"], [chosen["candidate_id"]])
                        proof = compiled["semantic_program"]["direct_bindings"][0]["source_interpretation"]
                        self.assertEqual(proof["axis_refs"], list(interpretation_axis_sources(chosen)))

    def test_explicit_abstention_is_not_overridden_for_available_row_or_genuine_scope_gap(self):
        parent = cell("parent", 31, ["Birch"], 2052)
        child = cell("child", 31, ["Birch", "Birch Research"], 2052)
        for catalog, query, status in (([parent, child], "Return the reported Birch quantity.", "ambiguous"),
                ([child], "Return the combined quantity for Birch and all its units.", "missing")):
            owner = _obligation("answer", "direct_value", "quantity")
            reason = "The authored response withholds this output; code must not invent its meaning."
            llm = AuthoredReadingLLM(None, status=status, rationale=reason)
            compiled = compile_case(catalog, owner, query, llm)
            self.assertEqual(len(llm.prompts), 1)
            self.assertEqual(compiled["semantic_program_retry_count"], 0)
            self.assertEqual(compiled["semantic_program_validation"]["errors"], [])
            self.assertEqual(compiled["semantic_program"]["rationale"], reason)
            self.assertEqual(execute(compiled, catalog, owner, query)["outputs"], [])

    def test_wrong_period_binding_is_still_rejected_not_reinterpreted_as_direction(self):
        catalog, owner = comparison()
        query = "Calculate percentage change from current to previous."
        llm = AuthoredReadingLLM(calculation(catalog, "(B - A) / A * 100", swap_source=True))
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(len(llm.prompts), 2)
        self.assertNotEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(execute(compiled, catalog, owner, query)["outputs"], [])


if __name__ == "__main__":
    unittest.main()
