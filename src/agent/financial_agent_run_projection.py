"""State-free caller-facing projections for ``FinancialAgent.run()``."""

from __future__ import annotations

import re
from typing import Any, Dict, Optional

from src.agent.financial_graph_state import (
    AgentAnswer,
    DebugBundle,
    DebugTraceBundle,
    ReviewTrace,
    RuntimeCalculationTrace,
)
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_runtime_trace import (
    structured_result_subtask_rows_and_answer,
)
from src.config.retrieval_policy import CALCULATION_NARRATIVE_POLICY
from src.config.runtime_contract import CALCULATION_DEBUG_TRACE_FIELD


def _runtime_evidence_defaults(final: Dict[str, Any]) -> Dict[str, Any]:
    report_scope = dict(final.get("report_scope") or {})
    company = str(report_scope.get("company") or "").strip()
    if not company:
        companies = [str(value).strip() for value in (final.get("companies") or []) if str(value).strip()]
        company = companies[0] if companies else ""
    year = report_scope.get("year")
    if year in (None, ""):
        years = list(final.get("years") or [])
        year = years[0] if years else None
    return {"company": company, "year": year}


def _compact_runtime_evidence_metadata(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Keep caller-facing evidence metadata small while preserving routing signals."""
    compacted = dict(metadata or {})
    dropped_fields: list[str] = []
    always_drop = {"table_object_json", "table_value_records_json"}
    max_field_chars = 4_000
    max_structured_row_chars = 20_000
    for key in list(compacted):
        value = compacted.get(key)
        value_text = str(value or "")
        if key in always_drop:
            compacted.pop(key, None)
            dropped_fields.append(key)
            continue
        if key == "table_row_records_json":
            if len(value_text) > max_structured_row_chars:
                compacted.pop(key, None)
                dropped_fields.append(key)
            continue
        if len(value_text) > max_field_chars:
            compacted.pop(key, None)
            dropped_fields.append(key)
    if dropped_fields:
        compacted["metadata_compacted_fields"] = sorted(set(dropped_fields))
    return compacted


def enrich_runtime_evidence_metadata(
    final: Dict[str, Any],
    evidence_items: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    defaults = _runtime_evidence_defaults(final)
    enriched: list[Dict[str, Any]] = []
    for item in list(evidence_items or []):
        row = dict(item or {})
        metadata = dict(row.get("metadata") or {})
        if defaults.get("company") and not metadata.get("company"):
            metadata["company"] = defaults["company"]
        if defaults.get("year") not in (None, "") and not metadata.get("year"):
            metadata["year"] = defaults["year"]
        if not str(row.get("source_anchor") or "").strip():
            anchor = (
                metadata.get("source_anchor")
                or metadata.get("section_path")
                or metadata.get("section_title")
                or metadata.get("section")
            )
            if anchor:
                row["source_anchor"] = _normalise_spaces(str(anchor))
        row["metadata"] = _compact_runtime_evidence_metadata(metadata)
        enriched.append(row)
    return enriched


def structured_result_answer_for_missing_public_answer(
    public_answer: str,
    structured_result: Dict[str, Any],
) -> str:
    answer_text = _normalise_spaces(str(public_answer or ""))
    structured_answer = _normalise_spaces(
        str(
            structured_result.get("answer")
            or structured_result.get("final_answer")
            or ""
        )
    )
    if not structured_answer:
        _, structured_answer = structured_result_subtask_rows_and_answer(structured_result)
    if not structured_answer or structured_answer == answer_text or not re.search(r"\d", structured_answer):
        return ""
    missing_markers = tuple(
        str(item)
        for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ())
        if str(item)
    )
    if not missing_markers:
        return ""
    if any(marker in answer_text for marker in missing_markers) and not any(
        marker in structured_answer for marker in missing_markers
    ):
        return structured_answer
    return ""


def with_public_answer(state: Dict[str, Any], public_answer: str) -> Dict[str, Any]:
    return {
        **dict(state),
        "answer": public_answer,
        "compressed_answer": public_answer,
    }


def public_projection_state(
    final: Dict[str, Any],
    *,
    public_answer: str,
    runtime_calculation_trace: RuntimeCalculationTrace,
    runtime_evidence: Optional[list[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    projection_state = with_public_answer(final, public_answer)
    projection_state["resolved_calculation_trace"] = runtime_calculation_trace
    if runtime_evidence is not None:
        projection_state["runtime_evidence"] = runtime_evidence
        projection_state["evidence_items"] = [
            *list(final.get("evidence_items") or []),
            *list(runtime_evidence or []),
        ]
    return projection_state


def project_debug_traces(final: Dict[str, Any]) -> DebugTraceBundle:
    return {"calculation": dict(final.get(CALCULATION_DEBUG_TRACE_FIELD) or {})}


def project_query_retrieval_status(final: Dict[str, Any]) -> Dict[str, Any]:
    trace_history = [
        dict(item)
        for item in (final.get("retrieval_debug_trace_history") or [])
        if isinstance(item, dict)
    ]
    if not trace_history:
        current_trace = final.get("retrieval_debug_trace")
        if isinstance(current_trace, dict):
            trace_history.append(dict(current_trace))

    degraded_modes = {"bm25_only", "bm25_fallback"}
    modes: list[str] = []
    reasons: list[str] = []
    for trace in trace_history:
        for query in trace.get("executed_queries") or []:
            if not isinstance(query, dict):
                continue
            telemetry = query.get("search_telemetry")
            if not isinstance(telemetry, dict):
                continue
            mode = str(telemetry.get("retrieval_mode") or "").strip()
            cached_mode = str(
                telemetry.get("cached_retrieval_mode") or ""
            ).strip()
            for candidate_mode in (mode, cached_mode):
                if candidate_mode in degraded_modes and candidate_mode not in modes:
                    modes.append(candidate_mode)
            if not ({mode, cached_mode} & degraded_modes):
                continue
            reason = str(
                telemetry.get("vector_skipped_reason")
                or telemetry.get("cached_vector_skipped_reason")
                or ""
            ).strip()
            if reason and reason not in reasons:
                reasons.append(reason)

    return {
        "degraded": bool(modes),
        "modes": modes,
        "reasons": reasons,
    }


def project_agent_answer(
    final: Dict[str, Any],
    *,
    public_answer: str,
    citations: list[str],
    structured_result: Dict[str, Any],
    runtime_calculation_trace: RuntimeCalculationTrace,
) -> AgentAnswer:
    return {
        "query": final["query"],
        "report_scope": final.get("report_scope", {}),
        "query_type": final["query_type"],
        "intent": final.get("intent", final["query_type"]),
        "planner_mode": final.get("planner_mode", "initial"),
        "planner_feedback": final.get("planner_feedback", ""),
        "plan_loop_count": final.get("plan_loop_count", 0),
        "target_metric_family": final.get("target_metric_family", ""),
        "target_metric_family_hint": final.get(
            "target_metric_family_hint",
            final.get("target_metric_family", ""),
        ),
        "planned_metric_families": final.get("planned_metric_families", []),
        "format_preference": final.get("format_preference", ""),
        "routing_source": final.get("routing_source", ""),
        "routing_confidence": final.get("routing_confidence", 0.0),
        "routing_scores": final.get("routing_scores", {}),
        "routing_degraded_reason": final.get("routing_degraded_reason", ""),
        "retrieval_status": project_query_retrieval_status(final),
        "companies": final["companies"],
        "years": final["years"],
        "answer": public_answer,
        "citations": citations,
        "resolved_calculation_trace": runtime_calculation_trace,
        "structured_result": structured_result,
    }


def project_review_trace(
    final: Dict[str, Any],
    *,
    runtime_evidence: list[Dict[str, Any]],
    task_artifact_trace: Dict[str, Any],
) -> ReviewTrace:
    return {
        "seed_retrieved_docs": final.get("seed_retrieved_docs", []),
        "retrieved_docs": final["retrieved_docs"],
        "retrieval_debug_trace": final.get("retrieval_debug_trace", {}),
        "retrieval_debug_trace_history": final.get("retrieval_debug_trace_history", []),
        "evidence_items": runtime_evidence,
        "selected_claim_ids": final.get("selected_claim_ids", []),
        "draft_points": final.get("draft_points", []),
        "kept_claim_ids": final.get("kept_claim_ids", []),
        "dropped_claim_ids": final.get("dropped_claim_ids", []),
        "unsupported_sentences": final.get("unsupported_sentences", []),
        "sentence_checks": final.get("sentence_checks", []),
        "numeric_debug_trace": final.get("numeric_debug_trace", {}),
        "numeric_debug_trace_history": final.get("numeric_debug_trace_history", []),
        "planner_debug_trace": final.get("planner_debug_trace", {}),
        "missing_info": final.get("missing_info", []),
        "reflection_count": final.get("reflection_count", 0),
        "retry_reason": final.get("retry_reason", ""),
        "retry_strategy": final.get("retry_strategy", ""),
        "retry_queries": final.get("retry_queries", []),
        "reconciliation_retry_count": final.get("reconciliation_retry_count", 0),
        "reflection_plan": final.get("reflection_plan", {}),
        "reflection_request": final.get("reflection_request", {}),
        "reflection_action": final.get("reflection_action", {}),
        "reflection_report": final.get("reflection_report", {}),
        "semantic_plan": final.get("semantic_plan", {}),
        "answer_obligations": final.get("answer_obligations", []),
        "semantic_candidate_catalog": final.get("semantic_candidate_catalog", []),
        "semantic_program": final.get("semantic_program", {}),
        "semantic_program_validation": final.get("semantic_program_validation", {}),
        "semantic_program_retry_count": final.get("semantic_program_retry_count", 0),
        "calc_subtasks": final.get("calc_subtasks", []),
        "retrieval_queries": final.get("retrieval_queries", []),
        "active_subtask_index": final.get("active_subtask_index", 0),
        "active_subtask": final.get("active_subtask", {}),
        "subtask_results": final.get("subtask_results", []),
        "subtask_debug_trace": final.get("subtask_debug_trace", {}),
        "subtask_loop_complete": bool(final.get("subtask_loop_complete", False)),
        "reconciliation_result": final.get("reconciliation_result", {}),
        "tasks": final.get("tasks", []),
        "artifacts": final.get("artifacts", []),
        "task_artifact_trace": task_artifact_trace,
    }


def project_debug_bundle(
    *,
    debug_traces: DebugTraceBundle,
    llm_usage: Dict[str, Any],
    llm_usage_by_phase: Dict[str, Any],
    embedding_usage: Dict[str, Any],
) -> DebugBundle:
    return {
        "debug_traces": debug_traces,
        "llm_usage": llm_usage,
        "llm_usage_by_phase": llm_usage_by_phase,
        "embedding_usage": embedding_usage,
    }


def augment_citations_from_runtime_evidence(
    citations: list[str],
    runtime_evidence: list[Dict[str, Any]],
) -> list[str]:
    updated = [str(item).strip() for item in (citations or []) if str(item).strip()]
    seen = {_normalise_spaces(item).lower() for item in updated}
    for item in list(runtime_evidence or []):
        row = dict(item or {})
        metadata = dict(row.get("metadata") or {})
        anchor = _normalise_spaces(
            str(
                row.get("source_anchor")
                or metadata.get("source_anchor")
                or metadata.get("section_path")
                or metadata.get("section")
                or ""
            )
        )
        if not anchor:
            continue
        company = str(metadata.get("company") or "").strip()
        year = str(metadata.get("year") or "").strip()
        citation = anchor
        if (company or year) and not anchor.startswith("["):
            citation = "[{}]".format(" | ".join(part for part in (company, year, anchor) if part))
        key = _normalise_spaces(citation).lower()
        if key in seen:
            continue
        seen.add(key)
        updated.append(citation)
    return updated
