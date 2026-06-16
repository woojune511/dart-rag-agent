"""Deterministic calculation execution payload helpers."""

from typing import Any, Dict, List

from src.agent.financial_answer_slots import build_answer_slots
from src.agent.financial_graph_helpers import (
    _append_artifact,
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
