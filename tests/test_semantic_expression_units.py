"""Formula/evidence own calculation units; the compiler chooses display intent."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_compiler_selection import (
    _case_state,
    _CompilerOnlyAgent,
    _materialize_catalog,
    _RecordingLLM,
    _ReviewedProgramQueue,
)
from tests.semantic_program_test_support import (
    _binding, _candidate, _obligation, _requirement,
    execute_semantic_calculation_program,
)


def _expression(**overrides):
    return {
        "obligation_id": "difference", "formula": "A - B",
        "variable_bindings": [_binding("A", "left", "left_input"), _binding("B", "right", "right_input")],
        "source_display_candidate_id": None,
        "source_display_reason": "The source reports the two inputs only.",
        **overrides,
    }


def _inputs(*, raw_unit="%", display_unit="", **expression_fields):
    return {
        "program": {"status": "ready", "expressions": [_expression(**expression_fields)]},
        "obligations": [_obligation(
            "difference", "derived_value", "difference", display_unit=display_unit,
            evidence_requirements=[_requirement("left_input", "left"), _requirement("right_input", "right")],
        )],
        "candidate_catalog": [_candidate("left", 1.83, raw_unit=raw_unit), _candidate("right", 1.73, raw_unit=raw_unit)],
        "query": "Calculate the difference between the two inputs.",
    }


class SemanticExpressionUnitTests(unittest.TestCase):
    def test_schema_requests_display_intent_not_calculation_unit(self):
        properties = SemanticCalculationProgram.model_json_schema()["$defs"]["SemanticProgramExpression"]["properties"]
        self.assertNotIn("result_unit", properties)
        self.assertIn("display_unit", properties)

    def test_legacy_unit_is_discarded_at_model_ingress_without_mutating_input(self):
        raw = {"expressions": [_expression(result_unit="PERCENT_POINT", display_unit="%p")]}
        before = deepcopy(raw)
        parsed = SemanticCalculationProgram.model_validate(raw)
        self.assertEqual(raw, before)
        self.assertNotIn("result_unit", parsed.model_dump()["expressions"][0])
        self.assertEqual(parsed.expressions[0].display_unit, "%p")
        with self.assertRaises(ValueError):
            SemanticCalculationProgram.model_validate({"expressions": [_expression(invented_field="value")]})

    def test_legacy_unit_cannot_veto_or_change_percentage_point_calculation(self):
        for legacy in ("PERCENT_POINT", "unsupported-unit", "USD", ""):
            with self.subTest(legacy=legacy):
                inputs = _inputs(display_unit="%p", result_unit=legacy)
                before = deepcopy(inputs)
                execution = execute_semantic_calculation_program(**inputs)
                self.assertEqual(inputs, before)
                self.assertEqual(execution["validation"]["errors"], [])
                self.assertEqual(execution["validation"]["inferred_units"]["difference"], "PERCENT")
                output = execution["outputs_by_obligation"]["difference"]
                self.assertAlmostEqual(output["calculated_value"], 0.1)
                self.assertEqual(output["rendered_value"], "0.10%p")
                self.assertEqual(output["result_unit"], "%p")  # Public display field stays intact.

    def test_missing_display_uses_inferred_canonical_unit(self):
        for unit, display in (("KRW", "원"), ("USD", "USD"), ("COUNT", ""), ("PERCENT", "%")):
            with self.subTest(unit=unit):
                execution = execute_semantic_calculation_program(**_inputs(raw_unit=unit, result_unit="ignored"))
                self.assertEqual(execution["validation"]["errors"], [])
                output = execution["outputs_by_obligation"]["difference"]
                self.assertEqual(output["normalized_unit"], unit)
                self.assertEqual(output["result_unit"], display)

    def test_expression_display_intent_overrides_requirement_scale(self):
        inputs = _inputs(raw_unit="백만달러", display_unit="USD")
        inputs["program"]["expressions"][0]["display_unit"] = "백만달러"
        execution = execute_semantic_calculation_program(**inputs)
        self.assertEqual(execution["validation"]["errors"], [])
        output = execution["outputs_by_obligation"]["difference"]
        self.assertAlmostEqual(output["calculated_value"], 100000)
        self.assertEqual(output["rendered_value"], "0.1백만달러")

    def test_percentage_formula_owns_times_100_and_default_display_is_consistent(self):
        execution = execute_semantic_calculation_program(**_inputs(raw_unit="COUNT", formula="A / B * 100"))
        self.assertEqual(execution["validation"]["errors"], [])
        self.assertEqual(execution["validation"]["inferred_units"]["difference"], "RATIO")
        output = execution["outputs_by_obligation"]["difference"]
        self.assertAlmostEqual(output["calculated_value"], 1.83 / 1.73 * 100)
        self.assertEqual(output["normalized_unit"], "PERCENT")
        self.assertEqual(output["result_unit"], "%")
        self.assertEqual(output["rendered_value"], "105.78%")

    def test_real_currency_and_display_conflicts_still_fail(self):
        inputs = _inputs(raw_unit="USD", display_unit="USD")
        inputs["candidate_catalog"][1] = _candidate("right", 1.73, raw_unit="KRW")
        execution = execute_semantic_calculation_program(**inputs)
        self.assertIn("formula_unit_mismatch", {error["code"] for error in execution["validation"]["errors"]})
        self.assertEqual(execution["outputs_by_obligation"], {})
        for display in ("USD", "unsupported-unit"):
            with self.subTest(display=display):
                inputs = _inputs(raw_unit="COUNT")
                inputs["program"]["expressions"][0]["display_unit"] = display
                execution = execute_semantic_calculation_program(**inputs)
                error = next(error for error in execution["validation"]["errors"] if error["code"] == "result_unit_mismatch")
                self.assertEqual(error["location"], "expression.display_unit")
                self.assertEqual(error["repair_action"], "repair_program")
                self.assertEqual(execution["outputs_by_obligation"], {})

    def test_reviewed_percentage_point_program_compiles_once_and_executes(self):
        from tests.request_unit_fixture_support import bind_fixture_request
        fixture = Path(__file__).parent / "fixtures" / "reviewed_runtime_replay_corpus_v2.json"
        case = bind_fixture_request(json.loads(fixture.read_text(encoding="utf-8"))["cases"][0])
        program = deepcopy(case["program"])
        program["expressions"][0].update(result_unit="PERCENT_POINT", display_unit="%p")
        queue = _ReviewedProgramQueue([SemanticCalculationProgram.model_validate(program)])
        llm = _RecordingLLM(queue)
        catalog, _ = _materialize_catalog(case["candidate_catalog"])
        state = _case_state(case, catalog)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.records), 1)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        execution = execute_semantic_calculation_program(
            program=compiled["semantic_program"], obligations=state["answer_obligations"],
            candidate_catalog=catalog, query=state["query"],
            compilation_envelope=compiled["semantic_compilation_envelope"], require_compilation_envelope=True,
        )
        self.assertEqual(execution["status"], "ok")
        output = execution["outputs_by_obligation"][program["expressions"][0]["obligation_id"]]
        self.assertAlmostEqual(output["calculated_value"], 0.1)
        self.assertEqual(output["rendered_value"], "0.10%p")


if __name__ == "__main__":
    unittest.main()
