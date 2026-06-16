"""Deterministic calculation execution payload helpers."""

from typing import Any, Dict, List

from src.agent.financial_answer_slots import build_answer_slots


def build_failed_calculation_result(
    *,
    active_subtask: Dict[str, Any],
    operation_family: str,
    runtime_operands: List[Dict[str, Any]],
    result_unit: str,
    source_normalized_unit: str,
    status: str,
    reason: str,
) -> Dict[str, Any]:
    failure_slots = build_answer_slots(
        active_subtask=active_subtask,
        operation_family=operation_family or "single_value",
        ordered_operands=list(runtime_operands),
        result_value=None,
        result_unit=result_unit,
        normalized_unit="UNKNOWN",
        source_normalized_unit=source_normalized_unit or "UNKNOWN",
        current_value=None,
        prior_value=None,
        delta_value=None,
        current_period="",
        prior_period="",
        source_row_ids=[],
        current_row=None,
        prior_row=None,
    )
    return {
        "status": status,
        "result_value": None,
        "result_unit": result_unit,
        "rendered_value": "",
        "formatted_result": "",
        "series": [],
        "answer_slots": failure_slots,
        "derived_metrics": {},
        "explanation": reason,
    }
