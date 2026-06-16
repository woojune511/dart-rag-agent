"""Reflection projection helpers for calculation retry handoff."""

from __future__ import annotations

from typing import Any, Dict, List

from src.agent.financial_graph_helpers import _normalise_spaces
from src.agent.financial_graph_models import FinancialAgentState, ReflectionAction, ReflectionReport


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
