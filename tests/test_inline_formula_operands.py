"""Inline operand contracts; authored successes are not model-accuracy evidence."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from pydantic import ValidationError

from src.agent.financial_compiler_wire import lower_compiler_response
from src.agent.financial_formula_eval import safe_eval_formula
from src.agent.financial_formula_wire import FormulaWireError, lower_formula_steps
from src.ops.compiler_fixture_transport import project_offline_program_to_wire
from tests.formula_wire_test_support import formula_ast, formula_steps, request_operand
from tests.mixed_numeric_source_test_support import canonical, capture_initial, compile_case, execute
from tests.test_named_request_inputs import named_witness
from tests.test_request_formula_constants import validate


class InlineFormulaOperandTests(unittest.TestCase):
    def setUp(self):
        for method in ("connect", "connect_ex"):
            blocker = patch.object(socket.socket, method, side_effect=AssertionError("provider forbidden"))
            blocker.start()
            self.addCleanup(blocker.stop)

    def wire(self, value=2):
        case, program = named_witness(value)
        model, _ = capture_initial(case)
        return case, program, model, project_offline_program_to_wire(program, model)

    def lower(self, case, model, raw, errors=None):
        return lower_compiler_response(raw, model=model, refs=model.__compiler_references__,
            obligations=case["obligations"], catalog=case["candidate_catalog"],
            visibility=model.__compiler_visibility__, errors=errors)

    def test_non_neutral_literal_cannot_be_separated_from_its_request_proof(self):
        _, _, model, good = self.wire()
        schema = Draft202012Validator(model.model_json_schema())
        for value in (2, "2", True, {"value": 2}, {"value": 2, "request_unit_id": "request_002"}):
            raw = deepcopy(good)
            raw["outputs"]["double"]["result"]["formula"][-1]["arguments"][-1] = value
            with self.subTest(value=value):
                self.assertFalse(schema.is_valid(raw))
                with self.assertRaises(ValidationError):
                    model.model_validate(raw)

    def test_old_correct_arithmetic_with_empty_declarations_is_not_repaired(self):
        _, _, model, good = self.wire()
        for formula in ("calculated_rate * 2", "calculated_rate / 2"):
            raw = deepcopy(good)
            raw["outputs"]["double"]["result"].update(formula=formula, request_inputs=[])
            before = deepcopy(raw)
            with self.subTest(formula=formula), self.assertRaises(ValidationError):
                model.model_validate(raw)
            self.assertEqual(raw, before)

    def test_neutral_symbols_and_inline_proofs_have_no_parallel_lists(self):
        _, _, model, raw = self.wire()
        props = model.model_json_schema()["$defs"]["Calculation_double"]["properties"]
        self.assertEqual(props["formula"]["type"], "array")
        self.assertNotIn("request_inputs", props)
        self.assertNotIn("binding_count_variable", props)
        self.assertNotIn("constants", props)
        self.assertEqual(set(request_operand(raw["outputs"]["double"]["result"])),
                         {"value", "request_unit_id", "interpretation"})
        for bad in (False, "3", "x * 7", {"variable": "x", "value": 7}):
            with self.subTest(token=bad), self.assertRaises(FormulaWireError):
                lower_formula_steps([{"operation": "identity", "arguments": [bad]}],
                    source_variables=["x"], resolve_request=lambda item: item)

    def test_operator_order_parentheses_functions_and_precedence_are_unchanged(self):
        formulas = ("(x-y)/abs(y)*100", "-(x+y)/y", "min(x,y)+max(x,y)",
                    "round(x/y,1)", "log(exp(x))", "x**(1+1)")
        for formula in formulas:
            steps = formula_steps(formula)
            before = deepcopy(steps)
            lowered = lower_formula_steps(steps, source_variables=["x", "y"], resolve_request=lambda item: item)
            with self.subTest(formula=formula):
                self.assertEqual(formula_ast(lowered["formula"]), formula_ast(formula))
                self.assertEqual(lowered["request_inputs"], [])
                self.assertEqual(steps, before)
                for x, y in ((3, 4), (-2, -5), (1, -2)):
                    self.assertAlmostEqual(safe_eval_formula(lowered["formula"], dict(x=x, y=y)),
                                           safe_eval_formula(formula, dict(x=x, y=y)))

    def test_multiple_equal_quantities_get_distinct_position_bound_internal_names(self):
        case, _, model, raw = self.wire()
        result = raw["outputs"]["double"]["result"]
        result["formula"].append({"operation": "divide",
            "arguments": [{"step": len(result["formula"])}, deepcopy(request_operand(result))]})
        first = self.lower(case, model, raw)
        self.assertEqual(validate(case, first)["status"], "ready")
        scalars = first["expressions"][-1]["request_inputs"]
        self.assertEqual([row["value"] for row in scalars], [2, 2])
        self.assertNotEqual(scalars[0]["variable"], scalars[1]["variable"])
        self.assertEqual(canonical(first), canonical(self.lower(case, model, deepcopy(raw))))

    def test_generated_names_do_not_capture_source_or_unbound_variables(self):
        scalar = {"value": 3, "request_unit_id": "q", "interpretation": "Authored quantity."}
        for name in ("_request_operand_0_1", "_request_operand_0_1_", "_binding_count"):
            steps = [{"operation": "multiply", "arguments": [{"variable": name}, scalar]},
                     {"operation": "divide", "arguments": [{"step": 1}, "binding_count"]}]
            lowered = lower_formula_steps(steps, source_variables=[name], resolve_request=lambda item: item)
            self.assertNotEqual(lowered["request_inputs"][0]["variable"], name)
            self.assertNotEqual(lowered["binding_count_variable"], name)
            self.assertIn(name, lowered["formula"])

    def test_foreign_request_is_target_local_and_preserves_sibling_program(self):
        case, _, model, raw = self.wire()
        correct = self.lower(case, model, raw)
        request_operand(raw["outputs"]["double"]["result"])["request_unit_id"] = "request_001"
        errors = []
        bad = self.lower(case, model, raw, errors)
        self.assertEqual([e["code"] for e in errors], ["constant_request_not_owned"])
        self.assertEqual(errors[0]["location"], "compiler_response.outputs.formula[0].arguments[1]")
        self.assertEqual(canonical(correct["expressions"][0]), canonical(bad["expressions"][0]))
        self.assertEqual(bad["missing_obligation_ids"], ["double"])

    def test_unknown_variable_is_not_rebound_or_fixed(self):
        case, _, model, good = self.wire()
        for steps in ([{"operation": "identity", "arguments": [{"variable": "hidden"}]}],
                      [{"operation": "add", "arguments": [{"variable": "calculated_rate"}, {"variable": "missing"}]}]):
            raw = deepcopy(good)
            raw["outputs"]["double"]["result"]["formula"] = steps
            lowered = self.lower(case, model, raw)
            self.assertTrue(any(e["obligation_id"] == "double" for e in validate(case, lowered)["errors"]))
            self.assertEqual(raw["outputs"]["double"]["result"]["formula"], steps)

    def test_invalid_quantity_or_identifier_never_reaches_arithmetic(self):
        for value in (True, float("inf"), float("nan"), "2", 10**400):
            token = {"value": value, "request_unit_id": "q", "interpretation": "Quantity."}
            with self.subTest(value=repr(value)), self.assertRaises(FormulaWireError):
                lower_formula_steps([{"operation": "identity", "arguments": [token]}],
                    source_variables=[], resolve_request=lambda item: item)
        for name in ("x + 7", "obj.attr", "for", "", "a[0]"):
            with self.subTest(name=name), self.assertRaises(FormulaWireError):
                lower_formula_steps([{"operation": "identity", "arguments": [{"variable": name}]}],
                    source_variables=[], resolve_request=lambda item: item)

    def test_named_source_cannot_be_replaced_by_an_inline_request_number(self):
        case, _, model, raw = self.wire()
        raw["outputs"]["double"]["result"]["inputs"]["own"] = []
        raw["outputs"]["double"]["result"]["formula"] = [{"operation": "identity",
            "arguments": [request_operand(raw["outputs"]["double"]["result"])]}]
        lowered = self.lower(case, model, raw)
        self.assertIn("invalid_variable_binding", {e["code"] for e in validate(case, lowered)["errors"]})

    def test_whole_request_linkage_does_not_certify_a_quantity_interpretation(self):
        case, _, model, raw = self.wire()
        request_operand(raw["outputs"]["double"]["result"])["value"] = 7
        lowered = self.lower(case, model, raw)
        validated = validate(case, lowered)
        self.assertEqual(validated["status"], "ready")  # Structurally linked, semantically wrong by authored criterion.
        proof = validated["valid_expressions"][-1]["constant_resolutions"][0]
        self.assertEqual(proof["value"], 7)
        self.assertEqual(proof["validation_scope"], "request_binding_not_semantic_equivalence")
        self.assertNotEqual(20 * proof["value"], 40)

    def test_same_cohort_retry_keeps_accepted_bytes_and_does_not_sample_a_provider(self):
        case, good = named_witness(-2.5)
        correct, _, _ = compile_case(case, [good])
        repair = {**deepcopy(good), "expressions": [deepcopy(good["expressions"][-1])], "source_assertions": []}
        def invalid_address(raw, attempt, model):
            if attempt == 0:
                request_operand(raw["outputs"]["double"]["result"])["request_unit_id"] = "request_999"
        compiled, queue, prompts = compile_case(case, [good, repair], mutate=invalid_address)
        self.assertEqual((len(queue.wires), compiled["semantic_program_retry_count"]), (2, 1))
        feedback = json.loads(prompts[-1]["retry_feedback"])
        self.assertEqual(feedback["read_only_dependency_outputs"]["growth"]["normalized_value"], 20)
        self.assertEqual(canonical(correct["semantic_program"]), canonical(compiled["semantic_program"]))
        self.assertEqual(correct["semantic_compilation_envelope"].visibility,
                         compiled["semantic_compilation_envelope"].visibility)
        self.assertEqual(execute(case, compiled)["outputs_by_obligation"]["double"]["calculated_value"], -50)


if __name__ == "__main__":
    unittest.main()
