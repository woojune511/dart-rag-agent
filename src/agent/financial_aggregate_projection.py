"""Pure projection helpers for aggregate-subtask closure."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List

from src.agent.financial_runtime_normalization import _clean_source_row_ids, _normalise_spaces


def aggregate_selected_claim_ids(
    ordered_results: List[Dict[str, Any]],
    composition_selected_claim_ids: List[str],
) -> List[str]:
    """Return ordered, de-duplicated evidence ids used by aggregate synthesis."""
    return list(
        dict.fromkeys(
            [
                *[
                    claim_id
                    for row in ordered_results
                    for claim_id in (row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
                *composition_selected_claim_ids,
            ]
        )
    )


def aggregate_extend_selected_claim_ids(
    selected_claim_ids: List[str],
    additional_claim_ids: Iterable[str],
) -> List[str]:
    """Append selected claim ids while preserving first-seen order."""
    return list(dict.fromkeys([*selected_claim_ids, *additional_claim_ids]))


def aggregate_ordered_result_source_refs(ordered_results: List[Dict[str, Any]]) -> List[str]:
    """Collect source refs from aggregate subtask rows for ledger integrity."""
    return _clean_source_row_ids(
        [
            value
            for row in ordered_results
            for value in [
                row.get("source_row_id"),
                row.get("source_row_ids"),
                (row.get("calculation_result") or {}).get("source_row_id")
                if isinstance(row.get("calculation_result"), dict)
                else None,
                (row.get("calculation_result") or {}).get("source_row_ids")
                if isinstance(row.get("calculation_result"), dict)
                else None,
                (row.get("answer_slots") or {}).get("source_row_id")
                if isinstance(row.get("answer_slots"), dict)
                else None,
                (row.get("answer_slots") or {}).get("source_row_ids")
                if isinstance(row.get("answer_slots"), dict)
                else None,
            ]
        ]
    )


def aggregate_source_task_ids(ordered_results: List[Dict[str, Any]]) -> List[str]:
    """Return non-empty task ids represented by aggregate subtask rows."""
    return [
        str(row.get("task_id") or "").strip()
        for row in ordered_results
        if str(row.get("task_id") or "").strip()
    ]


def aggregate_period_context_evidence_items(
    aggregate_evidence_items: List[Dict[str, Any]],
    runtime_context_items: Iterable[Any],
) -> List[Dict[str, Any]]:
    """Append context evidence rows while preserving existing evidence ids."""
    period_context_evidence_items = list(aggregate_evidence_items)
    seen_period_context_ids = {
        _normalise_spaces(str(item.get("evidence_id") or ""))
        for item in period_context_evidence_items
        if isinstance(item, dict) and _normalise_spaces(str(item.get("evidence_id") or ""))
    }
    for item in runtime_context_items:
        if not isinstance(item, dict):
            continue
        evidence_id = _normalise_spaces(str(item.get("evidence_id") or ""))
        if evidence_id and evidence_id in seen_period_context_ids:
            continue
        if evidence_id:
            seen_period_context_ids.add(evidence_id)
        period_context_evidence_items.append(dict(item))
    return period_context_evidence_items


def aggregate_projection_for_integrity(
    preliminary_projection: Dict[str, Any],
    calculation_projection_override: Any,
) -> Dict[str, Any]:
    """Choose the projection that should back ledger integrity checks."""
    if isinstance(calculation_projection_override, dict) and calculation_projection_override:
        return calculation_projection_override
    return preliminary_projection


def aggregate_projection_apply_override(
    aggregate_projection: Dict[str, Any],
    calculation_projection_override: Any,
) -> Dict[str, Any]:
    """Apply supported calculation projection override fields in place."""
    if not isinstance(calculation_projection_override, dict):
        return aggregate_projection
    for key in ("calculation_operands", "calculation_plan", "calculation_result"):
        if calculation_projection_override.get(key):
            aggregate_projection[key] = calculation_projection_override[key]
    return aggregate_projection


def aggregate_integrity_extra_refs(
    projection_for_integrity: Dict[str, Any],
    ordered_result_source_refs: List[str],
    selected_claim_ids_for_integrity: List[str],
) -> List[Any]:
    """Build extra provenance refs for aggregate ledger artifact enrichment."""
    projection_result_for_integrity = dict(projection_for_integrity.get("calculation_result") or {})
    projection_slots_for_integrity = dict(projection_result_for_integrity.get("answer_slots") or {})
    return [
        projection_result_for_integrity.get("source_row_id"),
        projection_result_for_integrity.get("source_row_ids"),
        projection_slots_for_integrity.get("source_row_id"),
        projection_slots_for_integrity.get("source_row_ids"),
        ordered_result_source_refs,
        selected_claim_ids_for_integrity,
    ]


def aggregate_completion_base_payload(
    *,
    state: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
    aggregate_projection: Dict[str, Any],
    final_answer: str,
    selected_claim_ids: List[str],
    aggregate_evidence_items: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    planner_feedback: str,
    should_replan: bool,
    replan_blocked_reason: str,
    aggregate_synthesis_debug: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the non-trace fields returned after aggregate subtask closure."""
    return {
        "subtask_results": ordered_results,
        "subtask_loop_complete": True,
        "answer": final_answer,
        "compressed_answer": final_answer,
        "planner_mode": "replan" if should_replan else "initial",
        "planner_feedback": planner_feedback,
        "replan_blocked_reason": replan_blocked_reason,
        "draft_points": [final_answer] if final_answer else [],
        "selected_claim_ids": selected_claim_ids,
        "kept_claim_ids": selected_claim_ids,
        "dropped_claim_ids": [],
        "unsupported_sentences": [],
        "sentence_checks": [],
        "tasks": tasks,
        "artifacts": artifacts,
        "evidence_items": aggregate_evidence_items or aggregate_projection.get("evidence_items", []),
        "subtask_debug_trace": {
            **dict(state.get("subtask_debug_trace") or {}),
            "aggregate_synthesis_prompt": aggregate_synthesis_debug,
        },
    }


def aggregate_artifact_payload(
    *,
    ordered_results: List[Dict[str, Any]],
    final_answer: str,
    planner_feedback: str,
    aggregate_projection: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the payload stored on the aggregate synthesis artifact."""
    return {
        "subtask_results": ordered_results,
        "final_answer": final_answer,
        "planner_feedback": planner_feedback,
        **aggregate_projection,
    }


def aggregate_task_status_value(*, planner_feedback: str, completed_value: Any, partial_value: Any) -> Any:
    """Choose aggregate task status without coupling projection code to enums."""
    return partial_value if planner_feedback else completed_value
