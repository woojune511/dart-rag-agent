from tests.semantic_program_test_support import *


class SemanticDisplayExecutionTests(unittest.TestCase):
    def test_dependency_uses_calculated_value_not_primary_source_display(self):
        fixture = _source_display_program_fixture()
        fixture["obligations"].append(_obligation(
            "dependent", "derived_value", "twice the calculated rate", display_unit="%",
            depends_on=["ob_change"],
        ))
        fixture["program"]["expressions"].append({
            "obligation_id": "dependent", "formula": "X + X", "result_unit": "%",
            "variable_bindings": [_binding("X", "ob_change")],
            "source_display_candidate_id": None,
            "source_display_reason": "This subsequent calculation has no source display.",
        })
        execution = execute_semantic_calculation_program(**fixture)
        self.assertEqual(execution["validation"]["errors"], [])
        first = execution["outputs_by_obligation"]["ob_change"]
        self.assertEqual(first["normalized_value"], 10)
        self.assertEqual(first["display_value"], 10.2)
        self.assertEqual(first["answer_slot"]["normalized_value"], 10.2)
        self.assertEqual(first["display_provenance"]["source_display_candidate_id"], "cand-stated")
        self.assertEqual(first["calculated_provenance"]["input_candidate_ids"], ["cand-opening", "cand-closing"])
        self.assertEqual(execution["outputs_by_obligation"]["dependent"]["normalized_value"], 20)
        self.assertEqual(execution["calculation_result"]["result_value"], 10.2)
        self.assertEqual(execution["calculation_result"]["calculated_result_value"], 10)

    def test_raw_program_cannot_omit_source_display_decision(self):
        for field in ("source_display_candidate_id", "source_display_reason"):
            with self.subTest(field=field):
                fixture = _source_display_program_fixture()
                del fixture["program"]["expressions"][0][field]
                execution = execute_semantic_calculation_program(**fixture)
                self.assertEqual(execution["outputs"], [])
                self.assertIn("invalid_source_display_decision", {e["code"] for e in execution["validation"]["errors"]})
