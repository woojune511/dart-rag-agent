import unittest

from src.agent.financial_calculation_execution import (
    build_failed_calculation_result,
    build_scalar_calculation_result,
    build_scalar_calculation_state,
    build_success_calculation_state_payload,
)


class FinancialCalculationExecutionTests(unittest.TestCase):
    def test_build_failed_calculation_result_uses_missing_primary_slot_without_operands(self) -> None:
        result = build_failed_calculation_result(
            active_subtask={
                "operation_family": "lookup",
                "metric_label": "법인세비용차감전순이익",
                "required_operands": [
                    {
                        "role": "operand",
                        "label": "법인세비용차감전순이익",
                        "concept": "income_before_income_taxes",
                        "period_hint": "2023년",
                    }
                ],
            },
            operation_family="lookup",
            runtime_operands=[],
            result_unit="",
            source_normalized_unit="UNKNOWN",
            status="insufficient_operands",
            reason="no operation or operands",
        )

        self.assertEqual(result["status"], "insufficient_operands")
        self.assertEqual(result["result_value"], None)
        self.assertEqual(result["series"], [])
        self.assertEqual(result["explanation"], "no operation or operands")
        self.assertEqual(result["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(result["answer_slots"]["primary_value"]["status"], "missing")
        self.assertEqual(result["answer_slots"]["primary_value"]["concept"], "income_before_income_taxes")

    def test_build_failed_calculation_result_preserves_operand_components_when_available(self) -> None:
        result = build_failed_calculation_result(
            active_subtask={"operation_family": "ratio", "metric_label": "ratio"},
            operation_family="ratio",
            runtime_operands=[
                {
                    "operand_id": "op_1",
                    "label": "분자",
                    "matched_operand_role": "numerator",
                    "raw_value": "10",
                    "raw_unit": "%",
                    "normalized_value": 10.0,
                    "normalized_unit": "PERCENT",
                    "evidence_id": "ev_1",
                }
            ],
            result_unit="%",
            source_normalized_unit="PERCENT",
            status="unit_mismatch",
            reason="unit families differ",
        )

        self.assertEqual(result["status"], "unit_mismatch")
        self.assertEqual(result["answer_slots"]["components_by_role"]["numerator"][0]["source_row_id"], "ev_1")

    def test_build_success_calculation_state_payload_appends_result_artifact_and_trace(self) -> None:
        payload = build_success_calculation_state_payload(
            state={
                "active_subtask": {"task_id": "task_1", "metric_label": "Metric"},
                "tasks": [],
                "artifacts": [],
            },
            calc_result={
                "status": "ok",
                "result_value": 1.0,
                "rendered_value": "1",
                "formatted_result": "",
            },
            selected_evidence_ids=["ev_1"],
            runtime_operands=[{"operand_id": "op_1", "normalized_value": 1.0}],
            calculation_plan={"mode": "single_value", "formula": "A"},
            query="query",
            metric_family="metric",
        )

        self.assertEqual(payload["answer"], "")
        self.assertEqual(payload["selected_claim_ids"], ["ev_1"])
        self.assertEqual(payload["kept_claim_ids"], ["ev_1"])
        self.assertEqual(payload["artifacts"][0]["artifact_id"], "result:task_1:001")
        self.assertEqual(payload["artifacts"][0]["kind"], "calculation_result")
        self.assertEqual(payload["artifacts"][0]["payload"]["calculation_result"]["rendered_value"], "1")
        self.assertEqual(payload["tasks"][0]["task_id"], "task_1")
        self.assertEqual(payload["tasks"][0]["artifact_ids"], ["result:task_1:001"])
        trace = payload["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_operands"][0]["operand_id"], "op_1")
        self.assertEqual(trace["calculation_plan"]["formula"], "A")
        self.assertEqual(trace["calculation_result"]["result_value"], 1.0)

    def test_build_success_calculation_state_payload_upserts_existing_task(self) -> None:
        payload = build_success_calculation_state_payload(
            state={
                "active_subtask": {"task_id": "task_1", "metric_label": "Metric"},
                "tasks": [
                    {
                        "task_id": "task_1",
                        "kind": "calculation",
                        "label": "Metric",
                        "status": "in_progress",
                        "query": "old query",
                        "metric_family": "old metric",
                        "constraints": {},
                        "artifact_ids": ["artifact:operand_set"],
                        "notes": [],
                    }
                ],
                "artifacts": [{"artifact_id": "artifact:operand_set"}],
            },
            calc_result={"status": "ok", "rendered_value": "2", "formatted_result": ""},
            selected_evidence_ids=[],
            runtime_operands=[],
            calculation_plan={},
            query="new query",
            metric_family="new metric",
        )

        self.assertEqual(payload["artifacts"][1]["artifact_id"], "result:task_1:002")
        self.assertEqual(payload["tasks"][0]["query"], "new query")
        self.assertEqual(payload["tasks"][0]["metric_family"], "new metric")
        self.assertEqual(payload["tasks"][0]["artifact_ids"], ["artifact:operand_set", "result:task_1:002"])

    def test_build_scalar_calculation_state_sets_lookup_current_value(self) -> None:
        state = build_scalar_calculation_state(
            operation_family="lookup",
            ordered_operands=[
                {
                    "evidence_id": "ev_1",
                    "source_row_ids": ["row_1"],
                    "normalized_value": 10.0,
                    "period": "p1",
                }
            ],
            result_value=10.0,
            normalized_unit="COUNT",
            result_unit="",
            rendered_with_unit="10",
        )

        self.assertEqual(state["current_value"], 10.0)
        self.assertEqual(state["current_period"], "p1")
        self.assertEqual(state["source_row_ids"], ["ev_1", "row_1"])
        self.assertFalse(state["source_stated_result_used"])

    def test_build_scalar_calculation_state_sets_difference_period_components(self) -> None:
        state = build_scalar_calculation_state(
            operation_family="difference",
            ordered_operands=[
                {
                    "matched_operand_role": "current_period",
                    "normalized_value": 30.0,
                    "period": "current",
                    "evidence_id": "ev_current",
                },
                {
                    "matched_operand_role": "prior_period",
                    "normalized_value": 20.0,
                    "period": "prior",
                    "evidence_id": "ev_prior",
                },
            ],
            result_value=10.0,
            normalized_unit="COUNT",
            result_unit="",
            rendered_with_unit="10",
        )

        self.assertEqual(state["current_value"], 30.0)
        self.assertEqual(state["prior_value"], 20.0)
        self.assertEqual(state["delta_value"], 10.0)
        self.assertEqual(state["current_period"], "current")
        self.assertEqual(state["prior_period"], "prior")
        self.assertEqual(state["source_row_ids"], ["ev_current", "ev_prior"])

    def test_build_scalar_calculation_state_preserves_source_stated_growth_display(self) -> None:
        state = build_scalar_calculation_state(
            operation_family="growth_rate",
            ordered_operands=[
                {
                    "matched_operand_role": "current_period",
                    "normalized_value": 112.0,
                    "period": "current",
                    "stated_change_raw_value": "12.3",
                    "stated_change_raw_unit": "%",
                },
                {
                    "matched_operand_role": "prior_period",
                    "normalized_value": 100.0,
                    "period": "prior",
                },
            ],
            result_value=12.0,
            normalized_unit="PERCENT",
            result_unit="%",
            rendered_with_unit="12%",
        )

        self.assertEqual(state["result_value"], 12.3)
        self.assertEqual(state["normalized_unit"], "PERCENT")
        self.assertEqual(state["result_unit"], "%")
        self.assertEqual(state["rendered_with_unit"], "12.3%")
        self.assertTrue(state["source_stated_result_used"])
        self.assertEqual(state["current_value"], 112.0)
        self.assertEqual(state["prior_value"], 100.0)

    def test_build_scalar_calculation_result_projects_state_slots_and_metrics(self) -> None:
        result = build_scalar_calculation_result(
            result_value=12.3,
            result_unit="%",
            rendered_with_unit="12.3%",
            result_series=[{"label": "current", "normalized_value": 112.0}],
            scalar_state={
                "current_value": 112.0,
                "prior_value": 100.0,
                "delta_value": None,
                "current_period": "current",
                "prior_period": "prior",
                "source_row_ids": ["ev_1"],
                "source_stated_result_used": True,
            },
            answer_slots={"operation_family": "growth_rate"},
            operand_labels=["current", "prior"],
            formula="((A - B) / B) * 100",
            operation_family="growth_rate",
            operation="growth_rate",
            formula_result_value=12.0,
            explanation="calculated",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result_value"], 12.3)
        self.assertEqual(result["result_unit"], "%")
        self.assertEqual(result["rendered_value"], "12.3%")
        self.assertEqual(result["series"][0]["label"], "current")
        self.assertEqual(result["current_value"], 112.0)
        self.assertEqual(result["prior_value"], 100.0)
        self.assertEqual(result["current_period"], "current")
        self.assertEqual(result["source_row_ids"], ["ev_1"])
        self.assertEqual(result["answer_slots"]["operation_family"], "growth_rate")
        self.assertEqual(result["derived_metrics"]["operand_labels"], ["current", "prior"])
        self.assertEqual(result["derived_metrics"]["formula"], "((A - B) / B) * 100")
        self.assertEqual(result["derived_metrics"]["operation_family"], "growth_rate")
        self.assertEqual(result["derived_metrics"]["formula_result_value"], 12.0)
        self.assertTrue(result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(result["explanation"], "calculated")


if __name__ == "__main__":
    unittest.main()
