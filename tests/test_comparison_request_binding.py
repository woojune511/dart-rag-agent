"""Request/operand wiring controls; authored replies are not model accuracy.

The paired questions below are fixed before the implementation. Each pair uses
identical sources, numbers, requirements and formula; only request and explicitly
authored endpoint assignments change. Wrong semantic assignments stay negatives.
"""

from copy import deepcopy
import json
import unittest

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_compiler_wire import lower_compiler_response
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.semantic_program_test_support import _obligation, _requirement, _StructuredQueueLLM
from tests.test_compiler_numeric_reading_intent import (
    AuthoredReadingLLM, calculation, comparison, compile_case, execute, selection,
)


FORMULA = "(target - reference) / abs(reference) * 100"
PAIRED_REQUESTS = (
    ("Calculate percentage change from previous to current.", "previous", "current"),
    ("Calculate percentage change from current to previous.", "current", "previous"),
    ("Use the previous period as reference and compare the current period.", "previous", "current"),
    ("Use the current period as reference and compare the previous period.", "current", "previous"),
)


def comparison_reply(catalog, query, reference="previous", *, unit="request_001", formula=FORMULA):
    def respond(refs):
        return {
            "comparison_request_unit_id": unit,
            "inputs": {name: [{**selection(refs, source, "quantity"),
                "variable": "reference" if name == reference else "target"}]
                for name, source in zip(("current", "previous"), catalog)},
            "formula": formula, "display_unit": "%", "source_display": None,
            "source_display_reason": "The request asks for a calculation, not a reported display.",
        }
    return respond


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


class ComparisonRequestBindingTests(unittest.TestCase):
    def test_paired_requests_use_named_endpoints_without_changing_sources_or_formula(self):
        for current, previous, year in ((84, 70, 2049), (-18, -30, 2062), (18, -30, 2062)):
            catalog, owner = comparison(current, previous, year)
            original = deepcopy((catalog, owner))
            fingerprint = semantic_candidate_catalog_fingerprint(catalog)
            for query, reference, target in PAIRED_REQUESTS:
                values = {"current": current, "previous": previous}
                expected = (values[target] - values[reference]) / abs(values[reference]) * 100
                for ordered in (catalog, catalog[::-1]):
                    with self.subTest(current=current, previous=previous, query=query, reversed=ordered != catalog):
                        llm = AuthoredReadingLLM(comparison_reply(catalog, query, reference))
                        compiled = compile_case(ordered, owner, query, llm)
                        result = execute(compiled, ordered, owner, query)
                        self.assertEqual(result["status"], "ok", compiled["semantic_program_validation"]["errors"])
                        output = result["outputs_by_obligation"]["answer"]
                        self.assertAlmostEqual(output["calculated_value"], expected)
                        self.assertEqual(output["formula"], FORMULA)
                        proof = output["comparison_resolution"]
                        self.assertEqual(proof["requested_text"], query)
                        self.assertEqual(proof["request_span"], [0, len(query)])
                        self.assertEqual(proof["reference"]["source_id"], reference + "-cell")
                        self.assertEqual(proof["target"]["source_id"], target + "-cell")
                        self.assertEqual(proof["validation_scope"], "request_binding_not_semantic_equivalence")
                        self.assertEqual(len(llm.prompts), 1)
            self.assertEqual((catalog, owner), original)
            self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_comparison_choice_is_required_nullable_only_on_calculations(self):
        catalog, owner = comparison()
        query = PAIRED_REQUESTS[0][0]
        llm = AuthoredReadingLLM(comparison_reply(catalog, query))
        compile_case(catalog, owner, query, llm)
        model = llm.models[0]
        schema = model.model_json_schema()["$defs"]["Calculation_answer"]
        self.assertIn("comparison_request_unit_id", schema["required"])
        self.assertLess(list(schema["properties"]).index("comparison_request_unit_id"), list(schema["properties"]).index("inputs"))
        raw = {"outputs": {"answer": {"status": "ready", "result": comparison_reply(catalog, query)(model.__compiler_references__)}}}
        del raw["outputs"]["answer"]["result"]["comparison_request_unit_id"]
        with self.assertRaises(ValueError):
            model.model_validate(raw)
        raw["outputs"]["answer"]["result"]["comparison_request_unit_id"] = None
        model.model_validate(raw)  # Null is a model decision, not code-detected intent.
        for kind in ("direct_value", "narrative"):
            other = _obligation("answer", kind, "quantity")
            no_answer = AuthoredReadingLLM(None, status="missing")
            compile_case(catalog, other, query, no_answer)
            self.assertNotIn('"comparison_request_unit_id"', json.dumps(no_answer.models[0].model_json_schema()))

    def test_ordinary_formula_retains_explicit_null_and_arbitrary_variables(self):
        catalog, owner = comparison()
        def reply(refs):
            return {**calculation(catalog, "A + B")(refs), "comparison_request_unit_id": None, "display_unit": ""}
        owner["display_unit"] = ""
        llm = AuthoredReadingLLM(reply)
        compiled = compile_case(catalog, owner, "Add the two quantities.", llm)
        output = execute(compiled, catalog, owner, "Add the two quantities.")["outputs_by_obligation"]["answer"]
        self.assertEqual(output["calculated_value"], 135)
        self.assertNotIn("comparison_resolution", output)
        self.assertEqual(compiled["semantic_program"]["expressions"][0]["formula"], "A + B")

    def test_request_reference_is_owned_and_copies_exact_text_and_python_span(self):
        catalog, owner = comparison()
        query = "참고🙂. Calculate current to previous; current to previous."
        owner["request_unit_ids"] = ["request_002"]
        for unit in ("request_001", "request_hidden", "request_002"):
            # Compile with a single owned unit; use direct validator below for a
            # multi-unit request whose other instruction has a different owner.
            program = {"status": "ready", "expressions": [{"obligation_id": "answer",
                "comparison_request_unit_id": unit,
                "variable_bindings": [
                    {"variable": "reference", "source_id": "current-cell", "source_requirement_id": "current"},
                    {"variable": "target", "source_id": "previous-cell", "source_requirement_id": "previous"}],
                "formula": FORMULA, "source_display_candidate_id": None, "source_display_reason": "Calculate."}]}
            with self.subTest(unit=unit):
                validated = validate_semantic_calculation_program(program=program, obligations=[owner], candidate_catalog=catalog, query=query)
                if unit == "request_002":
                    proof = validated["valid_expressions"][0]["comparison_resolution"]
                    self.assertEqual(proof["requested_text"], query[len("참고🙂. "):])
                    self.assertEqual(proof["request_span"], [len("참고🙂. "), len(query)])
                    continue
                errors = [error for error in validated["errors"] if error["code"] == "comparison_request_not_owned"]
                self.assertEqual(len(errors), 1, validated["errors"])
                self.assertEqual(errors[0]["location"], "expression.comparison_request")
                self.assertEqual(errors[0]["repair_action"], "repair_program")
                self.assertEqual(errors[0]["candidate_id"], "")

    def test_missing_or_unused_endpoint_requests_same_cohort_repair(self):
        catalog, owner = comparison()
        query = PAIRED_REQUESTS[0][0]
        for mode, code in (("rename", "comparison_binding_mismatch"), ("unused", "formula_binding_mismatch")):
            def reply(refs):
                result = comparison_reply(catalog, query)(refs)
                if mode == "rename":
                    result["inputs"]["previous"][0]["variable"] = "A"
                    result["formula"] = "(target-A)/abs(A)*100"
                else:
                    result["formula"] = "target"
                return result
            with self.subTest(mode=mode):
                llm = AuthoredReadingLLM(reply)
                compiled = compile_case(catalog, owner, query, llm)
                self.assertEqual(len(llm.prompts), 2)
                history = compiled["resolved_calculation_trace"]["calculation_plan"]["program_validation_history"]
                self.assertIn(code, {error["code"] for entry in history for error in entry["errors"]})
                self.assertEqual(execute(compiled, catalog, owner, query)["outputs"], [])
                attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
                self.assertEqual(attempts[0]["visible_candidate_ids"], attempts[1]["visible_candidate_ids"])

    def test_consistently_wrong_interpretation_and_wrong_formula_are_not_repaired(self):
        catalog, owner = comparison()
        query = PAIRED_REQUESTS[1][0]  # Current is reference, previous is target.
        for reference, formula in (("previous", FORMULA), ("current", "(reference-target)/abs(target)*100")):
            llm = AuthoredReadingLLM(comparison_reply(catalog, query, reference, formula=formula))
            compiled = compile_case(catalog, owner, query, llm)
            result = execute(compiled, catalog, owner, query)
            self.assertEqual(result["status"], "ok")  # Structurally valid semantic negatives.
            self.assertEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], -20)
            self.assertEqual(compiled["semantic_program"]["expressions"][0]["formula"], formula)
            self.assertEqual(len(llm.prompts), 1)

    def test_request_and_endpoint_tampering_are_blocked_by_execution_envelope(self):
        catalog, owner = comparison()
        query = PAIRED_REQUESTS[0][0]
        compiled = compile_case(catalog, owner, query, AuthoredReadingLLM(comparison_reply(catalog, query)))
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        for field in ("request", "endpoints", "query"):
            changed = deepcopy(compiled)
            expression = changed["semantic_program"]["expressions"][0]
            execution_query = query
            if field == "request":
                expression["comparison_request_unit_id"] = None
            elif field == "endpoints":
                for binding in expression["variable_bindings"]:
                    binding["variable"] = "reference" if binding["variable"] == "target" else "target"
            else:
                execution_query = PAIRED_REQUESTS[1][0]
            result = execute(changed, catalog, owner, execution_query)
            self.assertEqual(result["outputs"], [])
            self.assertIn(result["validation"]["errors"][0]["code"], {"validation_drift", "execution_content_mismatch"})

    def test_zero_reference_remains_undefined(self):
        catalog, owner = comparison(9, 0)
        query = PAIRED_REQUESTS[0][0]
        compiled = compile_case(catalog, owner, query, AuthoredReadingLLM(comparison_reply(catalog, query)))
        result = execute(compiled, catalog, owner, query)
        self.assertEqual(result["outputs"], [])
        self.assertIn("zero_division", {error["code"] for error in result["execution_errors"]})

    def test_retry_repairs_only_the_failed_island_and_keeps_accepted_request_bytes(self):
        catalog, _ = comparison()
        units = [PAIRED_REQUESTS[0][0], PAIRED_REQUESTS[1][0]]
        query = " ".join(units)
        owners = [_obligation(name, "derived_value", "change", display_unit="%",
            request_unit_ids=[f"request_{index:03d}"], evidence_requirements=[
                _requirement(name + "_current", "quantity", period="2051"),
                _requirement(name + "_previous", "quantity", period="2050")])
            for index, name in enumerate(("forward", "reverse"), 1)]

        class Queue:
            def __init__(self):
                self.models, self.prompts, self.raw = [], [], []

            def with_structured_output(self, model):
                self.models.append(model)
                return self

            def invoke(self, prompt):
                self.prompts.append(prompt)
                model = self.models[-1]
                owner_id, = model.model_fields["outputs"].annotation.model_fields
                index = 0 if owner_id == "forward" else 1
                unit_id = "request_001" if len(self.prompts) == 2 else f"request_{index + 1:03d}"
                endpoints = ["target", "reference"] if index == 0 else ["reference", "target"]
                result = {"comparison_request_unit_id": unit_id,
                    "inputs": {owner_id + "_" + period: [{"source_ref": model.__compiler_references__.ref(source["candidate_id"]), "variable": variable}]
                        for period, source, variable in zip(("current", "previous"), catalog, endpoints)},
                    "formula": FORMULA, "display_unit": "%", "source_display": None, "source_display_reason": "Calculated only."}
                raw = {"outputs": {owner_id: {"status": "ready", "result": result}}}
                self.raw.append(deepcopy(raw))
                return model.model_validate(raw)

        llm = Queue()
        agent = object.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
        state = {"query": query, "answer_obligations": owners, "include_debug_bundle": True,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog}
        before = deepcopy(state)
        compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready",
            (compiled["semantic_program_validation"]["errors"],
             compiled["resolved_calculation_trace"]["calculation_plan"]["program_validation_history"]))
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(state, before)
        initial = lower_compiler_response(llm.raw[0], model=llm.models[0], refs=llm.models[0].__compiler_references__,
            obligations=owners[:1], catalog=catalog, visibility=compiled["semantic_compilation_envelope"].visibility)
        self.assertEqual(canonical(compiled["semantic_program"]["expressions"][0]), canonical(initial["expressions"][0]))
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]
        self.assertEqual(diagnostics["attempts"][2]["target_obligation_ids"], ["reverse"])
        self.assertEqual(diagnostics["attempts"][1]["visible_candidate_ids"], diagnostics["attempts"][2]["visible_candidate_ids"])
        self.assertEqual(diagnostics["attempts"][1]["source_bundle_fingerprint"], diagnostics["attempts"][2]["source_bundle_fingerprint"])
        result = execute_semantic_calculation_program(program=compiled["semantic_program"], obligations=owners, candidate_catalog=catalog,
            query=query, compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["outputs_by_obligation"]["reverse"]["comparison_resolution"]["request_span"],
                         [len(units[0]) + 1, len(query)])

    def test_invalid_request_shape_fails_as_program_error_and_resolution_is_recomputed(self):
        catalog, owner = comparison()
        query = PAIRED_REQUESTS[0][0]
        compiled = compile_case(catalog, owner, query, AuthoredReadingLLM(comparison_reply(catalog, query)))
        original = compiled["semantic_program"]
        for request in (" ", {}, [], 3, {"request_unit_id": "request_001"}):
            with self.subTest(request=request):
                program = deepcopy(original)
                program["expressions"][0]["comparison_request_unit_id"] = request
                validated = validate_semantic_calculation_program(program=program, obligations=[owner], candidate_catalog=catalog, query=query)
                self.assertIn("invalid_comparison_request", {error["code"] for error in validated["errors"]})
        program = deepcopy(original)
        program["expressions"][0]["comparison_resolution"] = {"reference": "invented"}
        before = deepcopy(program)
        validated = validate_semantic_calculation_program(program=program, obligations=[owner], candidate_catalog=catalog, query=query)
        self.assertEqual(validated["status"], "ready")
        self.assertEqual(validated["valid_expressions"][0]["comparison_resolution"]["reference"]["source_id"], "previous-cell")
        self.assertEqual(program, before)

    def test_comparison_cannot_bypass_hidden_source_or_requirement_period(self):
        catalog, owner = comparison()
        query = PAIRED_REQUESTS[0][0]
        for foreign in ("hidden", "previous-cell"):
            def reply(refs):
                result = comparison_reply(catalog, query)(refs)
                result["inputs"]["current"][0]["source_ref"] = "c_hidden" if foreign == "hidden" else refs.ref(foreign)
                return result
            compiled = compile_case(catalog, owner, query, AuthoredReadingLLM(reply))
            self.assertEqual(execute(compiled, catalog, owner, query)["outputs"], [])

    def test_retry_endpoint_can_use_an_accepted_dependency_without_rewriting_it(self):
        catalog, _ = comparison()
        query = "Return the previous quantity and calculate its percentage change to the current quantity."
        owners = [_obligation("base", "direct_value", "quantity"),
            _obligation("answer", "derived_value", "change", display_unit="%", depends_on=["base"],
                        evidence_requirements=[_requirement("current", "quantity", period="2051")])]
        expression = {"obligation_id": "answer",
            "comparison_request_unit_id": "request_001",
            "variable_bindings": [{"variable": "reference", "source_id": "base"},
                {"variable": "target", "source_id": "current-cell", "source_requirement_id": "current"}],
            "formula": FORMULA, "display_unit": "%", "source_display_candidate_id": None, "source_display_reason": "Calculated only."}
        initial = {"status": "ready", "direct_bindings": [{"obligation_id": "base", "candidate_id": "previous-cell"}],
                   "expressions": [deepcopy(expression)]}
        initial["expressions"][0]["comparison_request_unit_id"] = "base"
        repaired = {"status": "ready", "expressions": [expression]}
        llm = _StructuredQueueLLM(*[SemanticCalculationProgram.model_validate(row) for row in (initial, repaired)])
        agent = object.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = llm, {}, None
        compiled = agent._compile_semantic_calculation_program({"query": query, "answer_obligations": owners,
            "semantic_candidate_catalog_prebuilt": True, "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog})
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 2)
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["attempts"]
        self.assertEqual(attempts[1]["read_only_dependency_ids"], ["base"])
        self.assertEqual(attempts[1]["target_obligation_ids"], ["answer"])
        result = execute_semantic_calculation_program(program=compiled["semantic_program"], obligations=owners, candidate_catalog=catalog,
            query=query, compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True)
        self.assertEqual(result["status"], "ok")
        output = result["outputs_by_obligation"]["answer"]
        self.assertEqual(output["comparison_resolution"]["reference"]["source_id"], "base")
        self.assertEqual(output["calculated_value"], -20)
        expected = SemanticCalculationProgram.model_validate(initial).model_dump()["direct_bindings"]
        self.assertEqual(canonical(compiled["semantic_program"]["direct_bindings"]), canonical(expected))


if __name__ == "__main__":
    unittest.main()
