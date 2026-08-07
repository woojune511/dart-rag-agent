"""Reflection projection helpers for calculation retry handoff."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.schema.runtime_enums import ArtifactKind

if TYPE_CHECKING:
    from src.agent.financial_graph_state import FinancialAgentState, ReflectionAction, ReflectionReport


def reflection_synthesis_source_ids_from_task_outputs(
    *,
    active_subtask: Mapping[str, Any],
    subtask_results: Sequence[Mapping[str, Any]],
    artifacts: Sequence[Mapping[str, Any]],
) -> List[str]:
    active_subtask = dict(active_subtask or {})
    preferred_task_ids: List[str] = []
    for binding in active_subtask.get("inputs") or []:
        if not isinstance(binding, dict):
            continue
        source_preference = [
            _normalise_spaces(str(item or "")).lower()
            for item in (binding.get("source_preference") or [])
            if _normalise_spaces(str(item or ""))
        ]
        preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
        if "task_output" in source_preference and preferred_task_id:
            preferred_task_ids.append(preferred_task_id)
    if not preferred_task_ids:
        preferred_task_ids = [
            _normalise_spaces(str(item or ""))
            for item in (active_subtask.get("depends_on") or [])
            if _normalise_spaces(str(item or ""))
        ]

    preferred_task_ids = list(dict.fromkeys(preferred_task_ids))
    if not preferred_task_ids:
        return []

    artifacts_by_id = {
        str(artifact.get("artifact_id") or "").strip(): dict(artifact)
        for artifact in (artifacts or [])
        if isinstance(artifact, dict) and str(artifact.get("artifact_id") or "").strip()
    }
    result_by_task_id = {
        str(row.get("task_id") or "").strip(): dict(row)
        for row in (subtask_results or [])
        if isinstance(row, dict) and str(row.get("task_id") or "").strip()
    }

    source_ids: List[str] = []
    for task_id in preferred_task_ids:
        result_row = result_by_task_id.get(task_id)
        if not result_row:
            continue
        artifact_ids = [
            str(item).strip()
            for item in (result_row.get("artifact_ids") or [])
            if str(item).strip()
        ]
        result_artifact_ids = [
            artifact_id
            for artifact_id in artifact_ids
            if str(artifacts_by_id.get(artifact_id, {}).get("kind") or "").strip()
            == ArtifactKind.CALCULATION_RESULT.value
        ]
        source_ids.extend(result_artifact_ids or artifact_ids)
        if not artifact_ids and result_row.get("calculation_result"):
            source_ids.append(f"task_output:{task_id}")

    return list(dict.fromkeys(item for item in source_ids if item))
def reflection_action_from_plan(
    reflection_plan: Dict[str, Any],
    *,
    retry_queries: List[str],
    retry_strategy: str,
) -> ReflectionAction:
    return {
        "action_type": retry_strategy,
        "retry_queries": list(retry_queries),
        "retrieval_scope_hints": [
            str(item).strip()
            for item in (reflection_plan.get("preferred_sections") or [])
            if str(item).strip()
        ],
        "synthesis_source_ids": [
            str(item).strip()
            for item in (reflection_plan.get("synthesis_source_ids") or [])
            if str(item).strip()
        ],
        "stop_reason": str(reflection_plan.get("explanation") or ""),
    }


def reflection_report_from_action(
    state: FinancialAgentState,
    *,
    reflection_action: ReflectionAction,
    reflection_request: Dict[str, Any],
) -> ReflectionReport:
    action_type = _normalise_spaces(str(reflection_action.get("action_type") or "")).lower()
    stop_reason = str(reflection_action.get("stop_reason") or "").strip()
    active_subtask = dict(state.get("active_subtask") or {})
    task_id = str(active_subtask.get("task_id") or "").strip()
    artifact_id = str(
        active_subtask.get("artifact_id")
        or active_subtask.get("result_artifact_id")
        or active_subtask.get("source_artifact_id")
        or ""
    ).strip()
    blocking_issues: List[Dict[str, Any]] = []
    if action_type == "stop_insufficient":
        blocking_issues.append(
            {
                "type": "stop_insufficient",
                "reason": stop_reason
                or str(reflection_request.get("failure_status") or "insufficient evidence"),
            }
        )
    return {
        "outcome": "stop_requested" if action_type == "stop_insufficient" else "retry_prepared",
        "action_taken": action_type,
        "budget_consumed": 0 if action_type == "stop_insufficient" else 1,
        "target_task_ids": [task_id] if task_id else [],
        "target_artifact_ids": [artifact_id] if artifact_id else [],
        "blocking_issues": blocking_issues,
    }


def task_artifact_integrity_feedback(trace: Dict[str, Any]) -> str:
    status = _normalise_spaces(str(trace.get("integrity_status") or "")).lower()
    if status != "error":
        return ""
    issue_surfaces: List[str] = []
    for issue in trace.get("integrity_issues") or []:
        if not isinstance(issue, dict):
            continue
        if str(issue.get("severity") or "").strip().lower() != "error":
            continue
        issue_type = str(issue.get("type") or "").strip()
        if not issue_type:
            continue
        detail_parts = [
            str(issue.get("task_id") or "").strip(),
            str(issue.get("artifact_kind") or issue.get("artifact_id") or "").strip(),
            str(issue.get("payload_key") or "").strip(),
        ]
        detail = ":".join(part for part in detail_parts if part)
        issue_surfaces.append(f"{issue_type}:{detail}" if detail else issue_type)
    issue_surface = ", ".join(sorted(set(issue_surfaces))) if issue_surfaces else "unknown_integrity_error"
    return (
        "Task/artifact ledger integrity error prevents final answer closure. "
        f"Repair the required artifact contract before closing: {issue_surface}."
    )
