import unittest
from copy import deepcopy
from unittest.mock import patch

from src.agent.financial_calculation_execution import (
    CalculationExecutionOutcome,
    build_failed_calculation_result,
    build_scalar_calculation_result,
    build_scalar_calculation_state,
    build_success_calculation_state_payload,
    build_time_series_calculation_result,
    execute_prepared_calculation_plan,
    guard_operation_plan,
    time_series_yoy_growth_rates,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import CalculationResult


class FinancialCalculationExecutionTests(unittest.TestCase):
    def test_guard_operation_plan_accepts_distinct_ratio_bindings(self) -> None:
        guarded_plan = guard_operation_plan(
            plan={
                "operation": "ratio",
                "ordered_operand_ids": ["op_num", "op_den"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "op_num"},
                    {"variable": "B", "operand_id": "op_den"},
                ],
            },
            operands=[
                {
                    "operand_id": "op_num",
                    "matched_operand_role": "numerator_1",
                    "matched_operand_label": "segment operating income",
                    "normalized_value": 100.0,
                    "evidence_id": "row_num",
                },
                {
                    "operand_id": "op_den",
                    "matched_operand_role": "denominator_1",
                    "matched_operand_label": "total operating income",
                    "normalized_value": 200.0,
                    "evidence_id": "row_den",
                },
            ],
            required_operands=[
                {"label": "segment operating income", "role": "numerator_1", "required": True},
                {"label": "total operating income", "role": "denominator_1", "required": True},
            ],
            operation_family="ratio",
        )

        self.assertIsNone(guarded_plan)

    def test_guard_operation_plan_uses_variable_bindings_when_ordered_ids_are_absent(self) -> None:
        guarded_plan = guard_operation_plan(
            plan={
                "operation": "difference",
                "ordered_operand_ids": [],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "current"},
                    {"variable": "B", "operand_id": "prior"},
                ],
            },
            operands=[
                {"operand_id": "current", "normalized_value": 30.0},
                {"operand_id": "prior", "normalized_value": 20.0},
            ],
            required_operands=[],
            operation_family="difference",
        )

        self.assertIsNone(guarded_plan)

    def test_guard_operation_plan_rejects_ratio_roles_sharing_source_value(self) -> None:
        guarded_plan = guard_operation_plan(
            plan={
                "operation": "ratio",
                "ordered_operand_ids": ["op_num", "op_den"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "op_num"},
                    {"variable": "B", "operand_id": "op_den"},
                ],
            },
            operands=[
                {
                    "operand_id": "op_num",
                    "matched_operand_role": "numerator_1",
                    "matched_operand_label": "segment operating income",
                    "raw_value": "100",
                    "raw_unit": "million",
                    "normalized_value": 100_000_000.0,
                    "evidence_id": "row_same",
                },
                {
                    "operand_id": "op_den",
                    "matched_operand_role": "denominator_1",
                    "matched_operand_label": "total operating income",
                    "raw_value": "100",
                    "raw_unit": "million",
                    "normalized_value": 100_000_000.0,
                    "evidence_id": "row_same",
                },
            ],
            required_operands=[
                {"label": "segment operating income", "role": "numerator_1", "required": True},
                {"label": "total operating income", "role": "denominator_1", "required": True},
            ],
            operation_family="ratio",
        )

        self.assertEqual(
            guarded_plan,
            {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": "operation plan does not satisfy required operand bindings",
                "missing_info": ["distinct_ratio_roles"],
            },
        )

    def test_calculation_result_schema_accepts_runtime_scale_mismatch_status(self) -> None:
        result = CalculationResult(status="scale_mismatch")

        self.assertEqual(result.status, "scale_mismatch")

    def test_execute_prepared_calculation_plan_runs_scalar_formula_without_graph_state(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="subtract",
            formula="A - B",
            pairwise_formula="",
            result_unit="KRW",
            operands_by_id={
                "current": {
                    "operand_id": "current",
                    "normalized_value": 30.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_current",
                },
                "prior": {
                    "operand_id": "prior",
                    "normalized_value": 20.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_prior",
                },
                "distractor": {
                    "operand_id": "distractor",
                    "normalized_value": 999.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_distractor",
                },
            },
            ordered_operand_ids=["current", "prior"],
            variable_bindings=[
                {"variable": "A", "operand_id": "current"},
                {"variable": "B", "operand_id": "prior"},
            ],
        )

        self.assertEqual(outcome.status, "ok")
        self.assertEqual(outcome.result_value, 10.0)
        self.assertEqual(outcome.normalized_unit, "KRW")
        self.assertEqual(outcome.source_normalized_unit, "KRW")
        self.assertEqual(outcome.selected_evidence_ids, ("ev_current", "ev_prior"))

    def test_execute_prepared_calculation_plan_rejects_divergent_operand_sets_without_mutation(
        self,
    ) -> None:
        operands_by_id = {
            "left": {
                "operand_id": "left",
                "normalized_value": 30.0,
                "normalized_unit": "KRW",
                "evidence_id": "ev_left",
            },
            "right": {
                "operand_id": "right",
                "normalized_value": 2.0,
                "normalized_unit": "COUNT",
                "evidence_id": "ev_right",
            },
        }
        ordered_operand_ids = ["left"]
        variable_bindings = [
            {"variable": "A", "operand_id": "left"},
            {"variable": "B", "operand_id": "right"},
        ]
        original_operands = deepcopy(operands_by_id)
        original_ordered_ids = list(ordered_operand_ids)
        original_bindings = deepcopy(variable_bindings)

        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="sum",
            formula="A + B",
            pairwise_formula="",
            result_unit="",
            operands_by_id=operands_by_id,
            ordered_operand_ids=ordered_operand_ids,
            variable_bindings=variable_bindings,
        )

        self.assertEqual(outcome.status, "parse_error")
        self.assertEqual(operands_by_id, original_operands)
        self.assertEqual(ordered_operand_ids, original_ordered_ids)
        self.assertEqual(variable_bindings, original_bindings)

    def test_graph_adapter_projects_executor_failures_only_to_canonical_trace(self) -> None:
        statuses = (
            "insufficient_operands",
            "unit_mismatch",
            "zero_division",
            "parse_error",
        )
        operand = {
            "operand_id": "value",
            "evidence_id": "ev_value",
            "label": "value",
            "raw_value": "10",
            "raw_unit": "",
            "normalized_value": 10.0,
            "normalized_unit": "COUNT",
            "matched_operand_role": "primary_value",
        }
        plan = {
            "status": "ok",
            "mode": "single_value",
            "operation": "lookup",
            "ordered_operand_ids": ["value"],
            "variable_bindings": [{"variable": "A", "operand_id": "value"}],
            "formula": "A",
            "pairwise_formula": "",
            "result_unit": "",
        }
        state = {
            "query": "Return the supported value.",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "value",
                "operation_family": "lookup",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [operand],
                "calculation_plan": plan,
                "calculation_result": {},
            },
            "evidence_items": [],
            "runtime_evidence": [],
            "tasks": [],
            "artifacts": [],
        }
        agent = FinancialAgent.__new__(FinancialAgent)

        for status in statuses:
            with self.subTest(status=status):
                original_state = deepcopy(state)
                execution_outcome = CalculationExecutionOutcome(
                    status=status,
                    reason=f"{status} from deterministic executor",
                    result_value=None,
                    normalized_unit="",
                    source_normalized_unit="COUNT",
                    ordered_operands=(deepcopy(operand),),
                    selected_evidence_ids=("ev_value",),
                )
                with patch(
                    "src.agent.financial_graph_calculation.execute_prepared_calculation_plan",
                    return_value=execution_outcome,
                ) as executor:
                    result = agent._execute_calculation(state)

                executor.assert_called_once()
                trace = result["resolved_calculation_trace"]
                self.assertEqual(trace["calculation_result"]["status"], status)
                self.assertEqual(
                    trace["calculation_result"]["explanation"],
                    execution_outcome.reason,
                )
                self.assertEqual(trace["calculation_plan"], plan)
                self.assertEqual(result["selected_claim_ids"], ["ev_value"])
                self.assertNotIn("calculation_operands", result)
                self.assertNotIn("calculation_plan", result)
                self.assertNotIn("calculation_result", result)
                self.assertEqual(state, original_state)

    def test_execute_prepared_calculation_plan_sorts_time_series_and_projects_growth_rates(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="time_series",
            operation="time_series_trend",
            formula="CURRENT - PRIOR",
            pairwise_formula="((CURR - PREV) / PREV) * 100",
            result_unit="KRW",
            operands_by_id={
                "current": {
                    "operand_id": "current",
                    "period": "2024",
                    "normalized_value": 115.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_current",
                },
                "prior": {
                    "operand_id": "prior",
                    "period": "2023",
                    "normalized_value": 100.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_prior",
                },
            },
            ordered_operand_ids=["current", "prior"],
            variable_bindings=[
                {"variable": "CURRENT", "operand_id": "current"},
                {"variable": "PRIOR", "operand_id": "prior"},
            ],
        )

        self.assertEqual(outcome.status, "ok")
        self.assertEqual(outcome.result_value, 15.0)
        self.assertEqual([row["period"] for row in outcome.ordered_operands], ["2023", "2024"])
        self.assertEqual(outcome.selected_evidence_ids, ("ev_prior", "ev_current"))
        self.assertEqual(outcome.yoy_growth_rates, (None, 15.0))

    def test_execute_prepared_calculation_plan_rejects_mixed_unit_families(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="ratio",
            formula="(A / B) * 100",
            pairwise_formula="",
            result_unit="%",
            operands_by_id={
                "numerator": {
                    "normalized_value": 10.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_numerator",
                },
                "denominator": {
                    "normalized_value": 20.0,
                    "normalized_unit": "COUNT",
                    "evidence_id": "ev_denominator",
                },
            },
            ordered_operand_ids=["numerator", "denominator"],
            variable_bindings=[
                {"variable": "A", "operand_id": "numerator"},
                {"variable": "B", "operand_id": "denominator"},
            ],
        )

        self.assertEqual(outcome.status, "unit_mismatch")
        self.assertIn("unit families differ", outcome.reason)
        self.assertIsNone(outcome.result_value)
        self.assertEqual(outcome.selected_evidence_ids, ("ev_numerator", "ev_denominator"))

    def test_execute_prepared_calculation_plan_classifies_zero_division(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="ratio",
            formula="A / B",
            pairwise_formula="",
            result_unit="%",
            operands_by_id={
                "numerator": {"normalized_value": 10.0, "normalized_unit": "KRW"},
                "denominator": {"normalized_value": 0.0, "normalized_unit": "KRW"},
            },
            ordered_operand_ids=["numerator", "denominator"],
            variable_bindings=[
                {"variable": "A", "operand_id": "numerator"},
                {"variable": "B", "operand_id": "denominator"},
            ],
        )

        self.assertEqual(outcome.status, "zero_division")
        self.assertIsNone(outcome.result_value)

    def test_execute_prepared_calculation_plan_requires_scalar_formula(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="lookup",
            formula="",
            pairwise_formula="",
            result_unit="KRW",
            operands_by_id={
                "value": {"normalized_value": 10.0, "normalized_unit": "KRW"},
            },
            ordered_operand_ids=["value"],
            variable_bindings=[{"variable": "A", "operand_id": "value"}],
        )

        self.assertEqual(outcome.status, "parse_error")
        self.assertEqual(outcome.reason, "missing scalar formula")

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

    def test_build_time_series_calculation_result_projects_series_slots_and_metrics(self) -> None:
        result = build_time_series_calculation_result(
            result_value=15.0,
            result_unit="%",
            rendered_value="15.0%",
            result_series=[
                {"label": "p1", "normalized_value": 100.0},
                {"label": "p2", "normalized_value": 115.0},
            ],
            operation_family="trend",
            operation="time_series_trend",
            metric_name="Metric",
            normalized_unit="PERCENT",
            yoy_growth_rates=[None, 15.0],
            formula="((B - A) / A) * 100",
            pairwise_formula="((CURR - PREV) / PREV) * 100",
            explanation="calculated trend",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result_value"], 15.0)
        self.assertEqual(result["result_unit"], "%")
        self.assertEqual(result["rendered_value"], "15.0%")
        self.assertEqual(result["series"][1]["label"], "p2")
        self.assertEqual(result["answer_slots"]["operation_family"], "trend")
        self.assertEqual(result["answer_slots"]["metric_label"], "Metric")
        self.assertEqual(result["answer_slots"]["primary_value"]["normalized_value"], 15.0)
        self.assertEqual(result["answer_slots"]["primary_value"]["normalized_unit"], "PERCENT")
        self.assertEqual(result["answer_slots"]["primary_value"]["rendered_value"], "15%")
        self.assertEqual(result["derived_metrics"]["metric_name"], "Metric")
        self.assertEqual(result["derived_metrics"]["yoy_growth_rates"], [None, 15.0])
        self.assertEqual(result["derived_metrics"]["formula"], "((B - A) / A) * 100")
        self.assertEqual(result["derived_metrics"]["pairwise_formula"], "((CURR - PREV) / PREV) * 100")
        self.assertEqual(result["explanation"], "calculated trend")

    def test_time_series_yoy_growth_rates_evaluates_pairwise_formula(self) -> None:
        rates = time_series_yoy_growth_rates(
            ordered_operands=[
                {"normalized_value": 100.0},
                {"normalized_value": 115.0},
                {"normalized_value": 138.0},
            ],
            pairwise_formula="((CURR - PREV) / PREV) * 100",
        )

        self.assertEqual(rates, [None, 15.0, 20.0])

    def test_time_series_yoy_growth_rates_keeps_none_for_zero_division(self) -> None:
        rates = time_series_yoy_growth_rates(
            ordered_operands=[
                {"normalized_value": 0.0},
                {"normalized_value": 10.0},
            ],
            pairwise_formula="((CURR - PREV) / PREV) * 100",
        )

        self.assertEqual(rates, [None, None])

    def test_time_series_yoy_growth_rates_without_formula_returns_initial_gap(self) -> None:
        rates = time_series_yoy_growth_rates(
            ordered_operands=[
                {"normalized_value": 100.0},
                {"normalized_value": 115.0},
            ],
            pairwise_formula="",
        )

        self.assertEqual(rates, [None])


if __name__ == "__main__":
    unittest.main()
