"""Bounded arithmetic transport; authored choices are not model accuracy evidence."""
from copy import deepcopy
import unittest

from pydantic import ValidationError

from src.agent.financial_formula_eval import safe_eval_formula
from src.agent.financial_formula_wire import (
    FormulaWireError, MAX_FORMULA_STEPS, MAX_EXPANDED_FORMULA_NODES, lower_formula_steps,
)
from src.ops.compiler_fixture_transport import project_offline_formula_steps
from tests import test_inline_formula_operands as inline_tests
from tests.formula_wire_test_support import formula_ast


def step(operation, *arguments):
    return {"operation": operation, "arguments": list(arguments)}


class FormulaStepTests(unittest.TestCase):
    def lower(self, steps):
        return lower_formula_steps(steps, source_variables=["x", "y"], resolve_request=lambda item: item)

    def test_parenthesis_repetition_and_old_tokens_are_not_production_formulas(self):
        _, _, model, raw = inline_tests.InlineFormulaOperandTests().wire()
        for formula in (["("] * 1433, [{"variable": "x"}, "*", "1"], "x * 1"):
            altered = deepcopy(raw)
            altered["outputs"]["double"]["result"]["formula"] = formula
            with self.subTest(kind=type(formula).__name__), self.assertRaises(ValidationError):
                model.model_validate(altered)
            with self.assertRaises(FormulaWireError):
                self.lower(formula)

    def test_step_dependencies_preserve_operand_order_and_last_step_is_result(self):
        steps = [step("subtract", {"variable": "x"}, {"variable": "y"}),
                 step("abs", {"variable": "y"}),
                 step("divide", {"step": 1}, {"step": 2}),
                 step("multiply", {"step": 3}, "100")]
        before = deepcopy(steps)
        result = self.lower(steps)
        self.assertEqual(formula_ast(result["formula"]), formula_ast("(x-y)/abs(y)*100"))
        self.assertEqual(safe_eval_formula(result["formula"], {"x": 9, "y": 10}), -10)
        self.assertEqual(steps, before)

    def test_forward_self_unknown_and_coerced_step_references_fail(self):
        for reference in (0, -1, 1, 2, 999, True, 1.0, "1"):
            with self.subTest(reference=reference), self.assertRaises(FormulaWireError):
                self.lower([step("identity", {"step": reference})])

    def test_unused_steps_cannot_hide_source_or_quantity_declarations(self):
        for argument in ({"variable": "x"}, {"value": 7, "request_unit_id": "q", "interpretation": "Seven."}):
            with self.subTest(argument=argument), self.assertRaisesRegex(FormulaWireError, "unused_formula_step"):
                self.lower([step("identity", argument), step("identity", {"variable": "y"})])

    def test_schema_enforces_operation_arity_without_changing_arithmetic(self):
        _, _, model, good = inline_tests.InlineFormulaOperandTests().wire()
        for operation, arguments in (("add", ["1"]), ("abs", ["1", "1"]),
                ("min", ["1"]), ("round", ["1", "1", "1"]), ("evaluate", ["1"])):
            raw = deepcopy(good)
            raw["outputs"]["double"]["result"]["formula"] = [step(operation, *arguments)]
            with self.subTest(operation=operation), self.assertRaises(ValidationError):
                model.model_validate(raw)
            with self.assertRaises(FormulaWireError):
                self.lower(raw["outputs"]["double"]["result"]["formula"])

    def test_all_arithmetic_shapes_round_trip_without_reassociation(self):
        formulas = ("x-y-y", "x-(y-y)", "x/(y/y)", "x/y/y", "-x**y", "(-x)**y",
                    "x**(y**1)", "(x**y)**1", "+x", "x", "min(x,y,1)",
                    "round(x)", "log(x,y)", "log(exp(x))", "max(x,y)+abs(y)")
        for formula in formulas:
            with self.subTest(formula=formula):
                lowered = self.lower(project_offline_formula_steps(formula))
                self.assertEqual(formula_ast(lowered["formula"]), formula_ast(formula))

    def test_shared_steps_do_not_duplicate_or_invent_request_proofs(self):
        quantity = {"value": 2.5, "request_unit_id": "q", "interpretation": "An authored factor."}
        result = self.lower([step("multiply", {"variable": "x"}, quantity),
                             step("add", {"step": 1}, {"step": 1})])
        self.assertEqual(len(result["request_inputs"]), 1)
        env = {"x": 4, result["request_inputs"][0]["variable"]: 2.5}
        self.assertEqual(safe_eval_formula(result["formula"], env), 20)

    def test_step_and_expansion_budgets_fail_without_truncation(self):
        steps = [step("identity", {"variable": "x"})]
        steps += [step("positive", {"step": i}) for i in range(1, MAX_FORMULA_STEPS)]
        self.lower(steps)
        with self.assertRaisesRegex(FormulaWireError, "formula_step_limit"):
            self.lower(steps + [step("identity", {"step": MAX_FORMULA_STEPS})])
        repeated = [step("identity", {"variable": "x"})]
        while 2 ** len(repeated) < MAX_EXPANDED_FORMULA_NODES:
            repeated.append(step("add", {"step": len(repeated)}, {"step": len(repeated)}))
        self.lower(repeated)
        before = deepcopy(repeated)
        with self.assertRaisesRegex(FormulaWireError, "formula_expansion_limit"):
            self.lower(repeated + [step("add", {"step": len(repeated)}, {"step": len(repeated)})])
        self.assertEqual(repeated, before)

    def test_offline_projection_does_not_fix_missing_proofs_or_unsupported_syntax(self):
        for formula in ("x*2", "x if y else 1", "x[0]", "x//y", "f(x)", "min(x)",
                        "'1'", "'binding_count'", "True"):
            with self.subTest(formula=formula), self.assertRaises(FormulaWireError):
                self.lower(project_offline_formula_steps(formula))

    def test_invalid_step_repairs_only_its_output_with_same_visible_sources(self):
        from tests.mixed_numeric_source_test_support import canonical, compile_case, execute
        from tests.test_named_request_inputs import named_witness
        case, good = named_witness(-2.5)
        clean, _, _ = compile_case(case, [good])
        repair = {**deepcopy(good), "expressions": [deepcopy(good["expressions"][-1])], "source_assertions": []}

        def self_reference(raw, attempt, model):
            if attempt == 0:
                raw["outputs"]["double"]["result"]["formula"][0]["arguments"][0] = {"step": 1}

        compiled, queue, _ = compile_case(case, [good, repair], mutate=self_reference)
        self.assertEqual((len(queue.wires), compiled["semantic_program_retry_count"]), (2, 1))
        self.assertEqual(canonical(clean["semantic_program"]), canonical(compiled["semantic_program"]))
        self.assertEqual(clean["semantic_compilation_envelope"].visibility,
                         compiled["semantic_compilation_envelope"].visibility)
        self.assertEqual(execute(case, compiled)["outputs_by_obligation"]["double"]["calculated_value"], -50)
        with self.assertRaises(FormulaWireError) as raised:
            self.lower([step("identity", {"step": 1})])
        self.assertEqual(raised.exception.location, "compiler_response.outputs.formula[0].arguments[0]")


if __name__ == "__main__":
    unittest.main()
