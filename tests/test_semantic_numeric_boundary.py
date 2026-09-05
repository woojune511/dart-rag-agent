"""Real source normalization across validation and numeric execution."""

from tests.semantic_program_test_support import *
from tests.test_numeric_unit_contract import _catalog_value
from src.agent.financial_calculation_execution import _source_display_matches


class SemanticNumericBoundaryTests(unittest.TestCase):
    def test_real_catalog_direct_units_and_signs(self):
        for raw, unit, declared, value, display in (
            ("9", "만 대", "COUNT", 90000, "9만 대"),
            ("1", "백만달러", "USD", 1000000, "1백만달러"),
            ("(1조원)", "원", "KRW", -1e12, "(1조원)"),
            ("-1조달러", "USD", "USD", -1e12, "-1조달러"),
        ):
            with self.subTest(raw=raw, unit=unit):
                candidate = _catalog_value(raw, unit)
                execution = execute_semantic_calculation_program(
                    program={"status": "ready", "direct_bindings": [{
                        "obligation_id": "value", "candidate_id": candidate["candidate_id"],
                    }]},
                    obligations=[_obligation("value", "direct_value", "quantity", display_unit=declared)],
                    candidate_catalog=[candidate], query="Report the quantity.",
                )
                self.assertEqual(execution["validation"]["errors"], [])
                output = execution["outputs_by_obligation"]["value"]
                self.assertEqual(output["normalized_value"], value)
                self.assertEqual(output["rendered_value"], display)

    def test_formula_scale_round_trip_uses_real_catalog(self):
        for unit, raw_a, raw_b, expected in (
            ("만 대", "87", "78", "9만 대"),
            ("백만달러", "2", "1", "1백만달러"),
        ):
            with self.subTest(unit=unit):
                left, right = _catalog_value(raw_a, unit), _catalog_value(raw_b, unit)
                obligation = _obligation("difference", "derived_value", "difference", display_unit=unit,
                    evidence_requirements=[_requirement("left", "left quantity"), _requirement("right", "right quantity")])
                execution = execute_semantic_calculation_program(
                    program={"status": "ready", "expressions": [{
                        "obligation_id": "difference", "formula": "A - B", "result_unit": unit,
                        "variable_bindings": [_binding("A", left["candidate_id"], "left"), _binding("B", right["candidate_id"], "right")],
                        "source_display_candidate_id": None,
                        "source_display_reason": "The fixture provides operands without a matching source-stated result.",
                    }]}, obligations=[obligation], candidate_catalog=[left, right], query="Calculate the difference.",
                )
                self.assertEqual(execution["validation"]["errors"], [])
                self.assertEqual(execution["outputs_by_obligation"]["difference"]["rendered_value"], expected)

    def test_source_precision_is_scaled_during_comparison(self):
        candidate = _catalog_value("1.2", "백만원")
        self.assertTrue(_source_display_matches(candidate, 1249999))
        self.assertFalse(_source_display_matches(candidate, 1260000))

    def test_unsupported_planner_unit_blocks_only_affected_island(self):
        obligations = [
            _obligation("bad", "direct_value", "quantity", display_unit="unsupported-unit"),
            _obligation("good", "direct_value", "quantity", display_unit="COUNT"),
        ]
        plan = build_semantic_compilation_islands(obligations)
        self.assertEqual(plan["islands"][0]["obligation_ids"], ["bad"])
        error = plan["islands"][0]["errors"][0]
        self.assertEqual(error["code"], "invalid_obligation_unit")
        self.assertEqual(error["repair_action"], "repair_requirements")
        self.assertEqual(plan["islands"][1]["errors"], [])

    def test_compiler_unit_error_does_not_evict_candidate(self):
        program = {"status": "ready", "expressions": [{
            "obligation_id": "derived", "formula": "A + A", "result_unit": "unsupported-unit",
            "display_unit": "COUNT", "variable_bindings": [_binding("A", "candidate")],
            "source_display_candidate_id": None,
            "source_display_reason": "The fixture provides operands without a matching source-stated result.",
        }]}
        validation = validate_semantic_calculation_program(
            program=program, obligations=[_obligation("derived", "derived_value", "quantity")],
            candidate_catalog=[_candidate("candidate", 1)], query="Calculate the quantity.",
        )
        self.assertTrue(validation["errors"])
        self.assertTrue(all(error["repair_action"] == "repair_program" for error in validation["errors"]))
        self.assertEqual(_retry_candidate_exclusions(program=program, validation_errors=validation["errors"], target_obligation_ids=["derived"]), {})

    def test_explicit_candidate_conflict_has_exact_replacement_target(self):
        program = {"status": "ready", "direct_bindings": [{"obligation_id": "value", "candidate_id": "candidate"}]}
        validation = validate_semantic_calculation_program(
            program=program, obligations=[_obligation("value", "direct_value", "quantity", scope=_scope(segment="target entity"))],
            candidate_catalog=[_candidate("candidate", 1, row_label="other entity")], query="Report target entity quantity.",
        )
        error = next(e for e in validation["errors"] if e["code"] == "candidate_subject_mismatch")
        self.assertEqual((error["owner_id"], error["candidate_id"], error["location"]), ("value", "candidate", "direct_binding"))
        self.assertEqual(_retry_candidate_exclusions(program=program, validation_errors=validation["errors"], target_obligation_ids=["value"]), {"value": ["candidate"]})

    def test_finite_operands_cannot_publish_overflow(self):
        candidate = _catalog_value("1" + "0" * 308, "COUNT")
        execution = execute_semantic_calculation_program(
            program={"status": "ready", "expressions": [{
                "obligation_id": "derived", "formula": "A + A", "result_unit": "COUNT",
                "variable_bindings": [_binding("A", candidate["candidate_id"], "input")],
                "source_display_candidate_id": None,
                "source_display_reason": "The fixture provides operands without a matching source-stated result.",
            }]}, obligations=[_obligation("derived", "derived_value", "quantity", evidence_requirements=[_requirement("input", "quantity")])],
            candidate_catalog=[candidate], query="Double the quantity.",
        )
        self.assertEqual(execution["outputs_by_obligation"], {})
        self.assertIn("non_finite_formula_result", {e["code"] for e in execution["execution_errors"]})
