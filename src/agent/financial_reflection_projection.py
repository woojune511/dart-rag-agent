"""Reflection projection helpers for calculation retry handoff."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List, Mapping, Sequence

from src.agent.financial_retrieval_hints import (
    preferred_calc_sections,
    _section_hint_alias,
)
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_runtime_trace import _resolve_runtime_calculation_trace
from src.schema.runtime_enums import ArtifactKind

if TYPE_CHECKING:
    from src.agent.financial_graph_state import (
        FinancialAgentState,
        ReflectionAction,
        ReflectionPlanRecord,
        ReflectionReport,
        ReflectionRequest,
    )


ALLOWED_REFLECTION_RETRY_STRATEGIES = {
    "retry_retrieval",
    "synthesize_from_task_outputs",
    "stop_insufficient",
}

DEFAULT_REFLECTION_RETRY_BUDGET = 1


def build_retry_queries(state: FinancialAgentState, missing_info: List[str]) -> List[str]:
    companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
    if not companies:
        for doc, _score in (state.get("seed_retrieved_docs") or []):
            company = str((doc.metadata or {}).get("company") or "").strip()
            if company:
                companies.append(company)
                break
    years = [str(int(year)) for year in (state.get("years") or [])]
    query = state["query"]
    topic = state.get("topic") or query
    intent = state.get("intent") or state.get("query_type", "qa")
    preferred_sections = preferred_calc_sections(query, topic, intent)

    queries: List[str] = []
    for item in missing_info:
        parts: List[str] = []
        if companies:
            parts.extend(companies)
        if years:
            parts.extend(years)
        parts.append(item)
        if preferred_sections:
            parts.extend(preferred_sections[:2])
        queries.append(_normalise_spaces(" ".join(parts)))
    return list(dict.fromkeys(query_text for query_text in queries if query_text))


def finalize_retry_queries(
    state: FinancialAgentState,
    reflection_plan: Dict[str, Any],
    missing_info: List[str],
) -> List[str]:
    base_queries = [
        _normalise_spaces(str(item))
        for item in (reflection_plan.get("subqueries") or [])
        if _normalise_spaces(str(item))
    ]
    if not base_queries:
        base_queries = build_retry_queries(state, missing_info)

    retry_objective = str(reflection_plan.get("retry_objective") or "")
    if retry_objective in {
        "find_missing_values",
        "resolve_binding",
        "find_direct_row",
    }:
        for item in missing_info[:2]:
            normalized = _normalise_spaces(str(item))
            if normalized:
                base_queries.append(normalized)

    companies = [str(company).strip() for company in (state.get("companies") or []) if str(company).strip()]
    report_company_hint = ""
    for doc, _score in (state.get("seed_retrieved_docs") or []):
        company = str((doc.metadata or {}).get("company") or "").strip()
        if company:
            report_company_hint = company
            break
    if not report_company_hint:
        for doc, _score in (state.get("retrieved_docs") or []):
            company = str((doc.metadata or {}).get("company") or "").strip()
            if company:
                report_company_hint = company
                break

    global_preferred_sections = preferred_calc_sections(
        state["query"],
        state.get("topic") or state["query"],
        state.get("intent") or state.get("query_type", "qa"),
    )
    preferred_sections = [
        _section_hint_alias(section)
        for section in (
            global_preferred_sections
            + list(reflection_plan.get("preferred_sections") or [])
        )
        if _section_hint_alias(section)
    ]
    preferred_sections = list(dict.fromkeys(preferred_sections))

    if preferred_sections and retry_objective in {
        "find_direct_row",
        "resolve_binding",
    }:
        for item in missing_info[:2]:
            normalized = _normalise_spaces(str(item))
            if not normalized:
                continue
            for hint in preferred_sections[:2]:
                base_queries.append(_normalise_spaces(f"{normalized} {hint}"))

    finalized: List[str] = []
    for query_text in base_queries:
        normalized_query = _normalise_spaces(query_text)
        for raw_section in (reflection_plan.get("preferred_sections") or []):
            alias = _section_hint_alias(str(raw_section))
            raw_section_text = _normalise_spaces(str(raw_section))
            if raw_section_text and alias:
                normalized_query = normalized_query.replace(raw_section_text, alias)
        parts: List[str] = []
        lowered = normalized_query.lower()
        if report_company_hint and report_company_hint.lower() not in lowered:
            parts.append(report_company_hint)
        parts.append(normalized_query)
        finalized.append(_normalise_spaces(" ".join(parts)))

    return list(dict.fromkeys(item for item in finalized if item))


def normalise_reflection_plan_record(
    plan: Dict[str, Any],
    *,
    fallback_plan: Dict[str, Any],
    missing_info: List[str],
    preferred_sections: List[str],
) -> ReflectionPlanRecord:
    plan_data = dict(plan or {})
    plan_data["missing_info"] = [
        str(item).strip()
        for item in (plan_data.get("missing_info") or [])
        if str(item).strip()
    ]
    plan_data["subqueries"] = [
        _normalise_spaces(str(item))
        for item in (plan_data.get("subqueries") or [])
        if _normalise_spaces(str(item))
    ]
    plan_data["preferred_sections"] = [
        _normalise_spaces(str(item))
        for item in (plan_data.get("preferred_sections") or [])
        if _normalise_spaces(str(item))
    ]
    retry_strategy = _normalise_spaces(str(plan_data.get("retry_strategy") or "")).lower()
    if retry_strategy not in ALLOWED_REFLECTION_RETRY_STRATEGIES:
        retry_strategy = str(fallback_plan.get("retry_strategy") or "retry_retrieval")
    plan_data["retry_strategy"] = retry_strategy
    if not plan_data["missing_info"]:
        plan_data["missing_info"] = list(missing_info)
    if not plan_data["preferred_sections"]:
        plan_data["preferred_sections"] = list(preferred_sections[:3])
    if not plan_data["subqueries"]:
        plan_data = dict(fallback_plan)
        plan_data["explanation"] = "fallback to heuristic because reflection planner returned no subqueries"
    return plan_data


def _reflection_runtime_trace_summary(state: FinancialAgentState) -> Dict[str, Any]:
    runtime_trace = _resolve_runtime_calculation_trace(
        dict(state),
        allow_legacy_top_level=False,
    )
    operands = list(runtime_trace.get("calculation_operands") or [])
    plan = dict(runtime_trace.get("calculation_plan") or {})
    result = dict(runtime_trace.get("calculation_result") or {})
    return {
        "operand_count": len(operands),
        "plan_status": str(plan.get("status") or ""),
        "plan_operation": str(plan.get("operation") or plan.get("mode") or ""),
        "result_status": str(result.get("status") or ""),
        "result_explanation": str(result.get("explanation") or ""),
    }


def _reflection_evidence_summary(state: FinancialAgentState) -> Dict[str, Any]:
    return {
        "evidence_item_count": len(list(state.get("evidence_items") or [])),
        "retrieved_doc_count": len(list(state.get("retrieved_docs") or [])),
        "seed_retrieved_doc_count": len(list(state.get("seed_retrieved_docs") or [])),
        "evidence_status": str(state.get("evidence_status") or ""),
    }


def build_reflection_request(
    state: FinancialAgentState,
    *,
    missing_info: List[str],
    failure_status: str,
) -> ReflectionRequest:
    active_subtask = dict(state.get("active_subtask") or {})
    reflection_count = int(state.get("reflection_count") or 0)
    return {
        "query": str(state.get("query") or ""),
        "active_task_id": str(active_subtask.get("task_id") or ""),
        "failure_status": str(failure_status or ""),
        "missing_info": [
            str(item).strip()
            for item in missing_info
            if str(item).strip()
        ],
        "runtime_trace_summary": _reflection_runtime_trace_summary(state),
        "evidence_summary": _reflection_evidence_summary(state),
        "remaining_retry_budget": max(DEFAULT_REFLECTION_RETRY_BUDGET - reflection_count, 0),
    }


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
