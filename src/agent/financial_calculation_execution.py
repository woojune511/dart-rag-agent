"""Deterministic calculation execution payload helpers."""

from typing import Any, Dict, List

from src.agent.financial_answer_slots import build_answer_slots
from src.agent.financial_graph_helpers import (
    _append_artifact,
    _clean_source_row_ids,
    _normalise_operand_value,
    _normalise_spaces,
    _runtime_trace_state_update,
    _upsert_task,
)
from src.schema import ArtifactKind, TaskKind, TaskStatus


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


def build_success_calculation_state_payload(
    *,
    state: Dict[str, Any],
    calc_result: Dict[str, Any],
    selected_evidence_ids: List[str],
    runtime_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    query: str,
    metric_family: str,
) -> Dict[str, Any]:
    result_payload: Dict[str, Any] = {
        "answer": "",
        "compressed_answer": "",
        "selected_claim_ids": list(selected_evidence_ids),
        "draft_points": [],
        "kept_claim_ids": list(selected_evidence_ids),
        "dropped_claim_ids": [],
        "unsupported_sentences": [],
        "sentence_checks": [],
    }
    artifacts = list(state.get("artifacts") or [])
    tasks = list(state.get("tasks") or [])
    active_subtask = dict(state.get("active_subtask") or {})
    task_id = str(active_subtask.get("task_id") or "calc")
    artifact_id = f"result:{task_id}:{len(artifacts) + 1:03d}"
    artifacts = _append_artifact(
        artifacts,
        artifact_id=artifact_id,
        task_id=task_id,
        kind=ArtifactKind.CALCULATION_RESULT,
        status=str(calc_result.get("status") or "ok"),
        summary=str(calc_result.get("rendered_value") or calc_result.get("formatted_result") or ""),
        payload={"calculation_result": calc_result},
        evidence_refs=selected_evidence_ids,
    )
    tasks = _upsert_task(
        tasks,
        task_id=task_id,
        kind=TaskKind.CALCULATION,
        label=str(active_subtask.get("metric_label") or task_id),
        status=TaskStatus.COMPLETED if str(calc_result.get("status") or "") == "ok" else TaskStatus.FAILED,
        query=query,
        metric_family=metric_family,
        artifact_id=artifact_id,
    )
    result_payload["tasks"] = tasks
    result_payload["artifacts"] = artifacts
    result_payload.update(
        _runtime_trace_state_update(
            state,
            calculation_operands=list(runtime_operands),
            calculation_plan=dict(calculation_plan),
            calculation_result=dict(calc_result),
            include_compatibility_mirrors=False,
        )
    )
    return result_payload


def build_scalar_calculation_state(
    *,
    operation_family: str,
    ordered_operands: List[Dict[str, Any]],
    result_value: float,
    normalized_unit: str,
    result_unit: str,
    rendered_with_unit: str,
) -> Dict[str, Any]:
    current_value = None
    prior_value = None
    delta_value = None
    current_period = ""
    prior_period = ""
    current_row = None
    prior_row = None
    source_stated_result_used = False
    source_row_ids = _clean_source_row_ids(
        [
            [
                row.get("evidence_id"),
                row.get("source_row_id"),
                row.get("source_row_ids"),
            ]
            for row in ordered_operands
        ]
    )
    if operation_family in {"lookup", "single_value"} and ordered_operands:
        current_value = float(ordered_operands[0].get("normalized_value"))
        current_period = str(ordered_operands[0].get("period") or "")
    elif operation_family in {"difference", "growth_rate"}:
        current_row = next(
            (
                row
                for row in ordered_operands
                if str(row.get("matched_operand_role") or "").strip() == "current_period"
            ),
            None,
        )
        prior_row = next(
            (
                row
                for row in ordered_operands
                if str(row.get("matched_operand_role") or "").strip() == "prior_period"
            ),
            None,
        )
        if current_row is None and len(ordered_operands) >= 1:
            current_row = ordered_operands[0]
        if prior_row is None and len(ordered_operands) >= 2:
            prior_row = ordered_operands[1]
        if current_row and current_row.get("normalized_value") is not None:
            current_value = float(current_row.get("normalized_value"))
            current_period = str(current_row.get("period") or "")
        if prior_row and prior_row.get("normalized_value") is not None:
            prior_value = float(prior_row.get("normalized_value"))
            prior_period = str(prior_row.get("period") or "")
        if operation_family == "difference":
            delta_value = float(result_value)
        elif operation_family == "growth_rate" and current_row:
            stated_change_raw_value = _normalise_spaces(str(current_row.get("stated_change_raw_value") or ""))
            stated_change_raw_unit = _normalise_spaces(str(current_row.get("stated_change_raw_unit") or "%"))
            if stated_change_raw_value:
                stated_value, stated_unit = _normalise_operand_value(
                    stated_change_raw_value,
                    stated_change_raw_unit or "%",
                )
                if stated_value is not None and str(stated_unit or "").strip().upper() == "PERCENT":
                    result_value = stated_value
                    normalized_unit = "PERCENT"
                    result_unit = "%"
                    rendered_with_unit = f"{stated_change_raw_value}%"
                    source_stated_result_used = True
    return {
        "result_value": result_value,
        "normalized_unit": normalized_unit,
        "result_unit": result_unit,
        "rendered_with_unit": rendered_with_unit,
        "source_stated_result_used": source_stated_result_used,
        "current_value": current_value,
        "prior_value": prior_value,
        "delta_value": delta_value,
        "current_period": current_period,
        "prior_period": prior_period,
        "current_row": current_row,
        "prior_row": prior_row,
        "source_row_ids": source_row_ids,
    }


def build_scalar_calculation_result(
    *,
    result_value: float,
    result_unit: str,
    rendered_with_unit: str,
    result_series: List[Dict[str, Any]],
    scalar_state: Dict[str, Any],
    answer_slots: Dict[str, Any],
    operand_labels: List[str],
    formula: str,
    operation_family: str,
    operation: str,
    formula_result_value: float,
    explanation: str,
) -> Dict[str, Any]:
    return {
        "status": "ok",
        "result_value": result_value,
        "result_unit": result_unit,
        "rendered_value": rendered_with_unit,
        "formatted_result": "",
        "series": list(result_series),
        "current_value": scalar_state.get("current_value"),
        "prior_value": scalar_state.get("prior_value"),
        "delta_value": scalar_state.get("delta_value"),
        "current_period": scalar_state.get("current_period") or "",
        "prior_period": scalar_state.get("prior_period") or "",
        "source_row_ids": list(scalar_state.get("source_row_ids") or []),
        "answer_slots": dict(answer_slots),
        "derived_metrics": {
            "operand_labels": list(operand_labels),
            "formula": formula,
            "operation_family": operation_family or operation,
            "formula_result_value": formula_result_value,
            "source_stated_result_used": bool(scalar_state.get("source_stated_result_used")),
        },
        "explanation": explanation,
    }
