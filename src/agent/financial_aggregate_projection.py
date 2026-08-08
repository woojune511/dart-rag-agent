"""Pure projection helpers for aggregate-subtask closure."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal, Mapping, Sequence

from src.agent import financial_graph_calculation_rendering as calculation_rendering
from src.agent.financial_runtime_normalization import _clean_source_row_ids, _normalise_spaces


AggregateStaleRepairTargetResolution = Literal[
    "unique_overlap",
    "single_identity_candidate",
    "ambiguous_target",
    "no_target",
]


@dataclass(frozen=True)
class AggregateStaleRepairProvenanceInput:
    ordered_results: Sequence[Mapping[str, Any]]
    aggregate_projection: Mapping[str, Any]
    selected_claim_ids: Sequence[Any]
    repaired_calculation_result: Mapping[str, Any]
    repaired_selected_evidence_ids: Sequence[str]
    evidence_items: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateStaleRepairProvenanceResult:
    selected_claim_ids: tuple[str, ...]
    target_resolution: AggregateStaleRepairTargetResolution


@dataclass(frozen=True)
class RuntimeRatioAbsoluteMagnitudeProjectionInput:
    """Prepared mutable copies for query-approved ratio magnitude projection."""

    calculation_result: Dict[str, Any]
    answer_slots: Dict[str, Any]
    primary_value: Dict[str, Any]


@dataclass(frozen=True)
class RuntimeRatioAbsoluteMagnitudeProjectionResult:
    """The same prepared calculation-result object after attempted projection."""

    calculation_result: Dict[str, Any]


def aggregate_result_operation_family(row: Mapping[str, Any]) -> str:
    """Return the normalized operation family projected by an aggregate row."""

    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    operation_family = _normalise_spaces(
        str(
            row.get("operation_family")
            or answer_slots.get("operation_family")
            or (row.get("calculation_plan") or {}).get("operation")
            or ""
        )
    ).lower()
    if not operation_family:
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if metric_family.startswith("concept_"):
            operation_family = metric_family.removeprefix("concept_")
        elif metric_family.endswith("_ratio"):
            operation_family = "ratio"
        elif metric_family.endswith("_growth_rate"):
            operation_family = "growth_rate"
        elif metric_family.endswith("_difference"):
            operation_family = "difference"
        elif metric_family.endswith("_sum"):
            operation_family = "sum"
    operation_aliases = {
        "divide": "ratio",
        "division": "ratio",
        "subtract": "difference",
        "subtraction": "difference",
        "add": "sum",
        "addition": "sum",
    }
    return operation_aliases.get(operation_family, operation_family)


def project_runtime_ratio_absolute_magnitude(
    projection_input: RuntimeRatioAbsoluteMagnitudeProjectionInput,
) -> RuntimeRatioAbsoluteMagnitudeProjectionResult:
    """Project a negative runtime ratio onto graph-prepared result and slot copies."""

    runtime_result = projection_input.calculation_result
    runtime_slots = projection_input.answer_slots
    runtime_primary = projection_input.primary_value
    try:
        runtime_value = runtime_result.get("result_value")
        if runtime_value is not None and float(runtime_value) < 0:
            absolute_value = abs(float(runtime_value))
            runtime_result["result_value"] = absolute_value
            runtime_primary["normalized_value"] = absolute_value
            runtime_primary["normalized_unit"] = runtime_primary.get("normalized_unit") or "PERCENT"
            runtime_primary["raw_unit"] = (
                runtime_primary.get("raw_unit") or runtime_result.get("result_unit") or "%"
            )
            runtime_rendered = calculation_rendering.format_calculation_value(
                absolute_value,
                str(runtime_result.get("result_unit") or "%"),
                str(runtime_primary.get("normalized_unit") or "PERCENT"),
            )
            runtime_result["rendered_value"] = runtime_rendered
            runtime_primary["rendered_value"] = runtime_rendered
            runtime_slots["primary_value"] = runtime_primary
            runtime_result["answer_slots"] = runtime_slots
    except (TypeError, ValueError):
        pass
    return RuntimeRatioAbsoluteMagnitudeProjectionResult(
        calculation_result=runtime_result,
    )


def _aggregate_stale_repair_provenance_refs(payload: Mapping[str, Any]) -> set[str]:
    calculation_result = dict(payload.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or payload.get("answer_slots") or {})
    calculation_operands = [
        dict(row)
        for row in list(payload.get("calculation_operands") or [])
        if isinstance(row, dict)
    ]
    return set(
        _clean_source_row_ids(
            [
                payload.get("selected_claim_ids"),
                payload.get("source_row_id"),
                payload.get("source_row_ids"),
                payload.get("source_evidence_ids"),
                calculation_result.get("source_row_id"),
                calculation_result.get("source_row_ids"),
                calculation_result.get("source_evidence_ids"),
                answer_slots.get("source_row_id"),
                answer_slots.get("source_row_ids"),
                answer_slots.get("source_evidence_ids"),
                *[
                    value
                    for operand in calculation_operands
                    for value in (
                        operand.get("evidence_id"),
                        operand.get("source_row_id"),
                        operand.get("source_row_ids"),
                        operand.get("source_claim_ids"),
                    )
                ],
            ]
        )
    )


def select_aggregate_stale_repair_provenance(
    selection_input: AggregateStaleRepairProvenanceInput,
) -> AggregateStaleRepairProvenanceResult:
    """Replace only a uniquely identified stale target's selected provenance."""

    repaired_slots = dict(
        selection_input.repaired_calculation_result.get("answer_slots") or {}
    )
    target_operation = _normalise_spaces(
        str(repaired_slots.get("operation_family") or "")
    ).lower()
    target_metric = _normalise_spaces(
        str(repaired_slots.get("metric_label") or "")
    ).casefold()
    matching_rows: List[Mapping[str, Any]] = []
    if target_operation and target_metric:
        for row in selection_input.ordered_results:
            row_result = dict(row.get("calculation_result") or {})
            row_slots = dict(row_result.get("answer_slots") or row.get("answer_slots") or {})
            row_metric = _normalise_spaces(
                str(row.get("metric_label") or row_slots.get("metric_label") or "")
            ).casefold()
            if (
                aggregate_result_operation_family(row) != target_operation
                or row_metric != target_metric
            ):
                continue
            matching_rows.append(row)
    projection_refs = _aggregate_stale_repair_provenance_refs(
        selection_input.aggregate_projection
    )
    overlapping_rows = [
        row
        for row in matching_rows
        if projection_refs.intersection(_aggregate_stale_repair_provenance_refs(row))
    ]
    target_rows: List[Mapping[str, Any]] = []
    target_resolution: AggregateStaleRepairTargetResolution = "no_target"
    if len(overlapping_rows) == 1:
        target_rows = overlapping_rows
        target_resolution = "unique_overlap"
    elif not overlapping_rows and len(matching_rows) == 1:
        target_rows = matching_rows
        target_resolution = "single_identity_candidate"
    elif matching_rows:
        target_resolution = "ambiguous_target"

    superseded_claim_ids: set[str] = set()
    for row in target_rows:
        superseded_claim_ids.update(
            str(claim_id).strip()
            for claim_id in (row.get("selected_claim_ids") or [])
            if str(claim_id).strip()
        )

    evidence_ids = {
        str(item.get("evidence_id") or "").strip()
        for item in selection_input.evidence_items
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    }
    repaired_claim_ids = [
        claim_id
        for claim_id in selection_input.repaired_selected_evidence_ids
        if claim_id in evidence_ids
    ]
    selected_claim_ids = tuple(
        dict.fromkeys(
            [
                *[
                    str(claim_id).strip()
                    for claim_id in selection_input.selected_claim_ids
                    if str(claim_id).strip()
                    and str(claim_id).strip() not in superseded_claim_ids
                ],
                *repaired_claim_ids,
            ]
        )
    )
    return AggregateStaleRepairProvenanceResult(
        selected_claim_ids=selected_claim_ids,
        target_resolution=target_resolution,
    )


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
