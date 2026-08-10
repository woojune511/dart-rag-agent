"""Pure projection helpers for aggregate-subtask closure."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence

from src.agent import financial_graph_calculation_rendering as calculation_rendering
from src.agent.financial_answer_slots import answer_slot_has_material
from src.agent.financial_answer_projection import (
    material_gap_feedback_for_subtask_result,
    subtask_row_has_material,
)
from src.agent.financial_dependency_projection import (
    dependency_lookup_slot_match_score,
    dependency_projection_slot_differs_from_operand,
    structured_unit_realigned_operand_matches_source_slot,
)
from src.agent.financial_numeric_surface import (
    extract_numeric_surface_candidates,
    numeric_surface_candidates_equivalent,
    numeric_surface_slot_components,
)
from src.agent.financial_row_surfaces import _operand_text_match, _strip_leading_period_qualifiers
from src.agent.financial_runtime_normalization import _clean_source_row_ids, _normalise_spaces
from src.agent.financial_runtime_trace import operand_row_has_material_numeric_payload
from src.agent.financial_scope_policies import known_consolidation_scope_value
from src.agent.financial_text_surface import _tokenize_terms, split_narrative_sentences as _split_narrative_sentences


AggregateStaleRepairTargetResolution = Literal[
    "unique_overlap",
    "single_identity_candidate",
    "ambiguous_target",
    "no_target",
]


def aggregate_synthesis_prompt_rows(
    ordered_results: Sequence[Any],
    aggregate_projection: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Project subtask rows into the compact contract needed by final synthesis."""
    calculation_result = dict(aggregate_projection.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    projected_rows = list(calculation_result.get("subtask_results") or answer_slots.get("subtask_results") or [])
    if not projected_rows:
        projected_rows = list(ordered_results or [])

    operands_by_task_id: Dict[str, List[Dict[str, Any]]] = {}
    for operand in list(aggregate_projection.get("calculation_operands") or []):
        operand_row = dict(operand or {})
        if not operand_row_has_material_numeric_payload(operand_row):
            continue
        task_id = str(operand_row.get("task_id") or "").strip()
        compact_operand = {
            key: operand_row.get(key)
            for key in (
                "operand_id",
                "matched_operand_role",
                "label",
                "label_kr",
                "raw_value",
                "value",
                "raw_unit",
                "normalized_value",
                "normalized_unit",
                "period",
                "source_row_id",
                "source_row_ids",
                "source_evidence_ids",
            )
            if operand_row.get(key) not in (None, "", [], {})
        }
        if compact_operand:
            operands_by_task_id.setdefault(task_id, []).append(compact_operand)

    compact_rows: List[Dict[str, Any]] = []
    for row in projected_rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        compact_row: Dict[str, Any] = {
            key: row.get(key)
            for key in (
                "task_id",
                "metric_family",
                "metric_label",
                "operation_family",
                "answer",
                "rendered_value",
                "status",
                "source_row_ids",
                "source_evidence_ids",
            )
            if row.get(key) not in (None, "", [], {})
        }
        row_answer_slots = dict(row.get("answer_slots") or {})
        if row_answer_slots:
            compact_row["answer_slots"] = row_answer_slots
        row_result = dict(row.get("calculation_result") or {})
        if row_result:
            compact_result = {
                key: row_result.get(key)
                for key in (
                    "status",
                    "rendered_value",
                    "formatted_result",
                    "answer_slots",
                    "source_row_ids",
                    "source_evidence_ids",
                )
                if row_result.get(key) not in (None, "", [], {})
            }
            if compact_result:
                compact_row["calculation_result"] = compact_result
        row_operands = operands_by_task_id.get(task_id) or []
        if row_operands:
            compact_row["calculation_operands"] = row_operands
        if compact_row:
            compact_rows.append(compact_row)
    return compact_rows


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


@dataclass(frozen=True)
class AggregateProjectionFinalAnswerSyncInput:
    """Prepared aggregate projection and final-answer synchronization flags."""

    aggregate_projection: Dict[str, Any]
    final_answer: str
    sync_rendered_for_aggregate: bool = True
    status_ok: bool = False


@dataclass(frozen=True)
class AggregateProjectionFinalAnswerSyncResult:
    """The same aggregate projection after attempted final-answer synchronization."""

    aggregate_projection: Dict[str, Any]


@dataclass(frozen=True)
class AggregateAnswerCandidatePackagingInput:
    """Prepared fields for one normalized aggregate-answer candidate payload."""

    answer: Any
    selected_claim_ids: Optional[Iterable[Any]] = None
    sync_projection: bool = True
    sync_rendered_for_aggregate: bool = True
    status_ok: bool = False


@dataclass(frozen=True)
class AggregateRefreshedAnswerCandidatePackagingInput:
    """Prepared refresh payload and fallback for candidate packaging."""

    refreshed_answer: Optional[Mapping[str, Any]]
    fallback_answer: Any
    sync_projection: bool = True
    sync_rendered_for_aggregate: bool = True
    status_ok: bool = False


@dataclass(frozen=True)
class AggregateAnswerCandidatePackagingResult:
    """Fresh normalized candidate payload for aggregate answer application."""

    candidate: Dict[str, Any]


@dataclass(frozen=True)
class AggregateAnswerCandidateApplicationInput:
    """Graph-prepared candidate inputs for state-free aggregate application."""

    aggregate_projection: Dict[str, Any]
    selected_claim_ids: Sequence[Any]
    candidate: Optional[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateAnswerCandidateApplicationResult:
    """Applied projection, normalized answer, and newly merged claim ids."""

    aggregate_projection: Dict[str, Any]
    final_answer: str
    selected_claim_ids: List[str]


@dataclass(frozen=True)
class AggregateProjectionProvenanceFilterInput:
    """Prepared aggregate projection and the evidence ids retained by the graph."""

    aggregate_projection: Dict[str, Any]
    kept_evidence_ids: Sequence[Any]


@dataclass(frozen=True)
class AggregateProjectionProvenanceFilterResult:
    """The original or shallow-filtered aggregate projection."""

    aggregate_projection: Dict[str, Any]


@dataclass(frozen=True)
class AggregateNestedSubtaskSynchronizationInput:
    """Graph-prepared ordered rows for recursive nested-result synchronization."""

    ordered_results: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateNestedSubtaskSynchronizationResult:
    """New ordered rows whose nested task results use current row authorities."""

    ordered_results: List[Dict[str, Any]]


@dataclass(frozen=True)
class AggregateProjectionRowSurfaceSyncInput:
    """One graph-prepared aggregate row and its selected answer surface."""

    projection_row: Mapping[str, Any]
    answer: str
    rendered_value: str


@dataclass(frozen=True)
class AggregateProjectionRowSurfaceSyncResult:
    """Fresh row with the prepared answer surface synchronized into its result."""

    projection_row: Dict[str, Any]


@dataclass(frozen=True)
class AggregateArithmeticComponentSyncInput:
    """One prepared projection row and the available lookup primary slots."""

    projection_row: Dict[str, Any]
    lookup_slots: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateArithmeticComponentSyncResult:
    """The original or synchronized aggregate arithmetic projection row."""

    projection_row: Dict[str, Any]


def filter_aggregate_projection_provenance(
    filter_input: AggregateProjectionProvenanceFilterInput,
) -> AggregateProjectionProvenanceFilterResult:
    """Remove pruned generated evidence refs from a prepared aggregate projection."""

    kept = {
        str(value).strip()
        for value in (filter_input.kept_evidence_ids or [])
        if str(value).strip()
    }
    if not kept:
        return AggregateProjectionProvenanceFilterResult(
            aggregate_projection=filter_input.aggregate_projection,
        )

    def _filter_ids(values: Any) -> List[str]:
        current = _clean_source_row_ids([values])
        return [
            value
            for value in current
            if not (value.startswith("ev_") or value.startswith("recon::")) or value in kept
        ]

    updated = dict(filter_input.aggregate_projection)
    calculation_result = dict(updated.get("calculation_result") or {})
    calculation_result["source_evidence_ids"] = _filter_ids(calculation_result.get("source_evidence_ids"))
    calculation_result["source_row_ids"] = _filter_ids(calculation_result.get("source_row_ids"))
    derived_metrics = dict(calculation_result.get("derived_metrics") or {})
    for key in ("aggregate_source_evidence_ids", "aggregate_source_row_ids"):
        if key in derived_metrics:
            derived_metrics[key] = _filter_ids(derived_metrics.get(key))
    calculation_result["derived_metrics"] = derived_metrics
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    if answer_slots:
        answer_slots["source_row_ids"] = _filter_ids(answer_slots.get("source_row_ids"))
        subtask_results: List[Dict[str, Any]] = []
        for subtask in list(answer_slots.get("subtask_results") or []):
            if not isinstance(subtask, dict):
                continue
            row = dict(subtask)
            row["source_evidence_ids"] = _filter_ids(row.get("source_evidence_ids"))
            row["source_row_ids"] = _filter_ids(row.get("source_row_ids"))
            subtask_results.append(row)
        if subtask_results:
            answer_slots["subtask_results"] = subtask_results
        calculation_result["answer_slots"] = answer_slots
    updated["calculation_result"] = calculation_result
    return AggregateProjectionProvenanceFilterResult(
        aggregate_projection=updated,
    )


def synchronize_nested_aggregate_subtask_rows(
    sync_input: AggregateNestedSubtaskSynchronizationInput,
) -> AggregateNestedSubtaskSynchronizationResult:
    """Recursively synchronize nested task rows from current ordered results."""

    ordered_results = sync_input.ordered_results
    by_task_id = {
        _normalise_spaces(str(row.get("task_id") or "")): dict(row)
        for row in ordered_results
        if _normalise_spaces(str(row.get("task_id") or ""))
    }

    def _sync_rows(rows: List[Any], stack: set[str], depth: int) -> List[Dict[str, Any]]:
        synced: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            task_id = _normalise_spaces(str(item.get("task_id") or ""))
            source = dict(item)
            if task_id and task_id not in stack and by_task_id.get(task_id):
                source = dict(by_task_id[task_id])
            synced.append(_sync_row(source, stack, depth + 1))
        return synced

    def _sync_row(row: Dict[str, Any], stack: set[str], depth: int = 0) -> Dict[str, Any]:
        if depth > 8:
            return dict(row)
        synced = dict(row)
        task_id = _normalise_spaces(str(synced.get("task_id") or ""))
        child_stack = set(stack)
        if task_id:
            child_stack.add(task_id)

        calculation_result = dict(synced.get("calculation_result") or {})
        if calculation_result:
            nested_rows = list(calculation_result.get("subtask_results") or [])
            if nested_rows:
                calculation_result["subtask_results"] = _sync_rows(nested_rows, child_stack, depth)
            answer_slots = dict(calculation_result.get("answer_slots") or {})
            nested_slot_rows = list(answer_slots.get("subtask_results") or [])
            if nested_slot_rows:
                answer_slots["subtask_results"] = _sync_rows(nested_slot_rows, child_stack, depth)
                calculation_result["answer_slots"] = answer_slots
            synced["calculation_result"] = calculation_result

        row_answer_slots = dict(synced.get("answer_slots") or {})
        row_nested_slot_rows = list(row_answer_slots.get("subtask_results") or [])
        if row_nested_slot_rows:
            row_answer_slots["subtask_results"] = _sync_rows(row_nested_slot_rows, child_stack, depth)
            synced["answer_slots"] = row_answer_slots
        return synced

    return AggregateNestedSubtaskSynchronizationResult(
        ordered_results=[_sync_row(dict(row), set()) for row in ordered_results],
    )


def sync_aggregate_projection_final_answer(
    sync_input: AggregateProjectionFinalAnswerSyncInput,
) -> AggregateProjectionFinalAnswerSyncResult:
    """Synchronize one prepared answer onto the same aggregate projection."""

    aggregate_projection = sync_input.aggregate_projection
    final_answer = sync_input.final_answer
    if not final_answer:
        return AggregateProjectionFinalAnswerSyncResult(
            aggregate_projection=aggregate_projection,
        )
    calculation_result = aggregate_projection.setdefault("calculation_result", {})
    calculation_result["formatted_result"] = final_answer
    if (
        sync_input.sync_rendered_for_aggregate
        and str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks"
    ):
        calculation_result["rendered_value"] = final_answer
    if sync_input.status_ok:
        calculation_result["status"] = "ok"
    return AggregateProjectionFinalAnswerSyncResult(
        aggregate_projection=aggregate_projection,
    )


def package_aggregate_answer_candidate(
    packaging_input: AggregateAnswerCandidatePackagingInput,
) -> AggregateAnswerCandidatePackagingResult:
    """Build one normalized aggregate-answer candidate payload."""

    return AggregateAnswerCandidatePackagingResult(
        candidate={
            "answer": _normalise_spaces(str(packaging_input.answer or "")),
            "selected_claim_ids": [
                str(claim_id).strip()
                for claim_id in (packaging_input.selected_claim_ids or [])
                if str(claim_id).strip()
            ],
            "sync_projection": bool(packaging_input.sync_projection),
            "sync_rendered_for_aggregate": bool(packaging_input.sync_rendered_for_aggregate),
            "status_ok": bool(packaging_input.status_ok),
        }
    )


def package_refreshed_aggregate_answer_candidate(
    packaging_input: AggregateRefreshedAnswerCandidatePackagingInput,
) -> AggregateAnswerCandidatePackagingResult:
    """Package a prepared refreshed answer with the existing fallback order."""

    payload = dict(packaging_input.refreshed_answer or {})
    return package_aggregate_answer_candidate(
        AggregateAnswerCandidatePackagingInput(
            answer=str(payload.get("answer") or packaging_input.fallback_answer or ""),
            selected_claim_ids=payload.get("selected_claim_ids") or [],
            sync_projection=packaging_input.sync_projection,
            sync_rendered_for_aggregate=packaging_input.sync_rendered_for_aggregate,
            status_ok=packaging_input.status_ok,
        )
    )


def apply_aggregate_answer_candidate(
    application_input: AggregateAnswerCandidateApplicationInput,
) -> AggregateAnswerCandidateApplicationResult:
    """Apply one graph-prepared candidate without selecting or refreshing it."""

    candidate = application_input.candidate
    aggregate_projection = application_input.aggregate_projection
    final_answer = _normalise_spaces(str((candidate or {}).get("answer") or ""))
    if bool((candidate or {}).get("sync_projection", True)):
        sync_rendered_for_aggregate = bool(
            (candidate or {}).get("sync_rendered_for_aggregate", True)
        )
        status_ok = bool((candidate or {}).get("status_ok", False))
        aggregate_projection = sync_aggregate_projection_final_answer(
            AggregateProjectionFinalAnswerSyncInput(
                aggregate_projection=aggregate_projection,
                final_answer=final_answer,
                sync_rendered_for_aggregate=sync_rendered_for_aggregate,
                status_ok=status_ok,
            )
        ).aggregate_projection
    merged_claim_ids = list(
        dict.fromkeys(
            [
                *[
                    str(claim_id).strip()
                    for claim_id in (application_input.selected_claim_ids or [])
                    if str(claim_id).strip()
                ],
                *[
                    str(claim_id).strip()
                    for claim_id in ((candidate or {}).get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
            ]
        )
    )
    return AggregateAnswerCandidateApplicationResult(
        aggregate_projection=aggregate_projection,
        final_answer=final_answer,
        selected_claim_ids=merged_claim_ids,
    )


def subtask_numeric_answers_conflict(
    candidate_row: Mapping[str, Any],
    current_row: Mapping[str, Any],
) -> bool:
    candidate_answer = _normalise_spaces(
        str(
            candidate_row.get("answer")
            or (candidate_row.get("calculation_result") or {}).get("formatted_result")
            or (candidate_row.get("calculation_result") or {}).get("rendered_value")
            or ""
        )
    )
    current_answer = _normalise_spaces(
        str(
            current_row.get("answer")
            or (current_row.get("calculation_result") or {}).get("formatted_result")
            or (current_row.get("calculation_result") or {}).get("rendered_value")
            or ""
        )
    )
    candidate_numbers = extract_numeric_surface_candidates(candidate_answer)
    current_numbers = extract_numeric_surface_candidates(current_answer)
    if not candidate_numbers or not current_numbers:
        return False
    return not all(
        any(
            numeric_surface_candidates_equivalent(candidate_number, current_number)
            for current_number in current_numbers
        )
        for candidate_number in candidate_numbers
    )


def subtask_row_has_direct_source_refs(row: Mapping[str, Any]) -> bool:
    calculation_result = dict(row.get("calculation_result") or {})
    source_ids = _clean_source_row_ids([
        row.get("source_row_ids"),
        calculation_result.get("source_row_ids"),
        row.get("selected_claim_ids"),
        calculation_result.get("source_evidence_ids"),
    ])
    return any(source_id and not source_id.startswith("task_output:") for source_id in source_ids)


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


def aggregate_row_primary_answer_slot(row: Dict[str, Any]) -> Dict[str, Any]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    return dict(answer_slots.get("primary_value") or {})


def aggregate_source_slot_by_task_id(ordered_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    source_slot_by_task_id: Dict[str, Dict[str, Any]] = {}
    for row in ordered_results:
        if not isinstance(row, dict):
            continue
        task_id = _normalise_spaces(str(row.get("task_id") or ""))
        if not task_id:
            continue
        slot = aggregate_row_primary_answer_slot(dict(row))
        if not slot:
            continue
        scope = known_consolidation_scope_value(
            slot.get("consolidation_scope"),
            row.get("consolidation_scope"),
        )
        if scope and not slot.get("consolidation_scope"):
            slot["consolidation_scope"] = scope
        metric_label = _normalise_spaces(str(row.get("metric_label") or ""))
        if metric_label and not slot.get("metric_label"):
            slot["metric_label"] = metric_label
        source_slot_by_task_id[task_id] = slot
    return source_slot_by_task_id


def aggregate_source_task_ids_for_operand(
    operand: Dict[str, Any],
    source_slots: Dict[str, Dict[str, Any]],
) -> List[str]:
    source_task_ids = [
        _normalise_spaces(str(operand.get("source_task_id") or "")),
        *[
            source_id.removeprefix("task_output:")
            for source_id in _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")])
            if source_id.startswith("task_output:")
        ],
    ]
    source_task_ids = [task_id for task_id in source_task_ids if task_id]
    if source_task_ids or not source_slots:
        return list(dict.fromkeys(source_task_ids))
    role = _normalise_spaces(str(operand.get("role") or operand.get("matched_operand_role") or ""))
    inferred_task_ids = []
    for task_id, source_slot in source_slots.items():
        slot = dict(source_slot or {})
        if not answer_slot_has_material(slot):
            continue
        if dependency_lookup_slot_match_score(slot, operand, role) >= 12:
            inferred_task_ids.append(task_id)
    return inferred_task_ids


def _aggregate_result_candidate_operands(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    candidate_operands = [dict(item) for item in list(row.get("calculation_operands") or []) if isinstance(item, dict)]
    candidate_operands.extend(
        dict(item) for item in list(calculation_result.get("calculation_operands") or []) if isinstance(item, dict)
    )
    for container_key in ("components_by_group", "components_by_role"):
        for entries in dict(answer_slots.get(container_key) or {}).values():
            candidate_operands.extend(dict(item) for item in list(entries or []) if isinstance(item, dict))
    return candidate_operands


def aggregate_result_dependency_coherence_ranks(
    row: Dict[str, Any],
    source_slot_by_task_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[int, int]:
    operation_family = aggregate_result_operation_family(row)
    if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
        return 1, 1
    source_slots = dict(source_slot_by_task_id or {})
    saw_source_slot = False
    saw_source_scope = False
    candidate_operands = _aggregate_result_candidate_operands(row)
    structured_realigned_operands = [
        dict(operand)
        for operand in candidate_operands
        if isinstance(operand, dict) and operand.get("unit_realigned_from_structured_provenance")
    ]
    for operand in candidate_operands:
        source_task_ids = aggregate_source_task_ids_for_operand(operand, source_slots)
        source_task_id = source_task_ids[0] if source_task_ids else ""
        if source_task_id and source_slots:
            source_slot = dict(source_slots.get(source_task_id) or {})
            if answer_slot_has_material(source_slot):
                saw_source_slot = True
                source_anchor = _normalise_spaces(str(source_slot.get("source_anchor") or ""))
                operand_anchor = _normalise_spaces(str(operand.get("source_anchor") or ""))
                source_mismatch = bool(source_anchor and operand_anchor and source_anchor != operand_anchor)
                projection_mismatch = dependency_projection_slot_differs_from_operand(source_slot, operand)
                if (
                    (source_mismatch or projection_mismatch)
                    and not structured_unit_realigned_operand_matches_source_slot(
                        source_slot,
                        operand,
                        structured_realigned_operands=structured_realigned_operands,
                    )
                ):
                    return 0, 2 if saw_source_scope else 1
        if operation_family == "ratio" and source_slots and source_task_ids:
            source_scope = next(
                (
                    known_consolidation_scope_value(source_slots.get(task_id, {}).get("consolidation_scope"))
                    for task_id in source_task_ids
                    if source_slots.get(task_id)
                ),
                "",
            )
            if source_scope:
                saw_source_scope = True
                operand_scope = known_consolidation_scope_value(operand.get("consolidation_scope"))
                if operand_scope and operand_scope != source_scope:
                    return 2 if saw_source_slot else 1, 0
    return 2 if saw_source_slot else 1, 2 if saw_source_scope else 1


def aggregate_dependency_slot_coherence_rank_for_operands(
    *,
    operation_family: str,
    operands: List[Any],
    ordered_results: List[Dict[str, Any]],
    calculation_result: Optional[Dict[str, Any]] = None,
) -> int:
    return aggregate_result_dependency_coherence_ranks(
        {
            "operation_family": operation_family,
            "calculation_operands": [
                dict(item)
                for item in list(operands or [])
                if isinstance(item, dict)
            ],
            "calculation_result": dict(calculation_result or {}),
        },
        aggregate_source_slot_by_task_id(ordered_results),
    )[0]


def select_aggregate_projection_row_for_task(
    task_id: str,
    ordered_results: List[Dict[str, Any]],
    aggregate_projection: Dict[str, Any],
) -> Dict[str, Any]:
    target_task_id = _normalise_spaces(str(task_id or ""))
    if not target_task_id:
        return {}
    calculation_result = dict(aggregate_projection.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    candidate_groups = [
        calculation_result.get("subtask_results"),
        answer_slots.get("subtask_results"),
        ordered_results,
    ]
    for rows in candidate_groups:
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            if _normalise_spaces(str(row.get("task_id") or "")) == target_task_id:
                return dict(row)
    return {}


def select_aggregate_projection_answer_sentence(
    final_answer: str,
    row: Dict[str, Any],
) -> str:
    final_answer = _normalise_spaces(final_answer)
    if not final_answer:
        return ""
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    primary_slot = dict(answer_slots.get("primary_value") or {})
    raw_labels = [
        row.get("metric_label"),
        row.get("label"),
        primary_slot.get("label"),
    ]
    row_labels: List[str] = []
    for label in raw_labels:
        normalized = _normalise_spaces(str(label or "")).lower()
        if not normalized:
            continue
        row_labels.append(normalized)
        stripped = _normalise_spaces(_strip_leading_period_qualifiers(normalized)).lower()
        if stripped and stripped != normalized:
            row_labels.append(stripped)
    row_labels = list(dict.fromkeys(row_labels))
    operation_family = aggregate_result_operation_family(row)
    sentences = _split_narrative_sentences(final_answer) or [final_answer]

    def _label_match_score(sentence: str) -> int:
        normalized = _normalise_spaces(sentence).lower()
        if not normalized:
            return 0
        sentence_tokens = _tokenize_terms(normalized)
        score = 0
        for label in row_labels:
            if not label:
                continue
            if label in normalized:
                score = max(score, 3)
                continue
            label_tokens = _tokenize_terms(label)
            if not label_tokens:
                continue
            overlap = len(label_tokens & sentence_tokens)
            required_overlap = len(label_tokens)
            if len(label_tokens) >= 3:
                required_overlap = max(2, len(label_tokens) - 1)
            if overlap >= required_overlap and _operand_text_match(normalized, {"label": label, "aliases": []}):
                score = max(score, 1)
        return score

    def _score(sentence: str) -> tuple[int, int, int, int, int]:
        normalized = _normalise_spaces(sentence)
        numeric_candidates = extract_numeric_surface_candidates(normalized)
        if not normalized or not numeric_candidates:
            return (0, 0, 0, 0, 0)
        label_score = _label_match_score(normalized)
        percent_score = int(operation_family in {"ratio", "growth_rate"} and "%" in normalized)
        arithmetic_score = len(numeric_candidates) if operation_family in {"difference", "sum"} else 0
        conflict_score = int(subtask_numeric_answers_conflict({"answer": normalized}, row))
        return (label_score, percent_score, arithmetic_score, conflict_score, len(normalized))

    best_sentence = max(sentences, key=_score, default="")
    return _normalise_spaces(best_sentence) if _score(best_sentence)[:3] != (0, 0, 0) else ""


def aggregate_projection_rendered_value(
    answer_sentence: str,
    operation_family: str,
) -> str:
    sentence = _normalise_spaces(answer_sentence)
    if not sentence:
        return ""
    if operation_family in {"ratio", "growth_rate"}:
        match = re.search(r"[\(\)\-+]?\d[\d,]*(?:\.\d+)?\s*%p?", sentence)
        return _normalise_spaces(match.group(0)) if match else ""
    candidates = extract_numeric_surface_candidates(sentence)
    if not candidates:
        return ""
    return _normalise_spaces(str(candidates[-1].get("text") or ""))


def aggregate_result_signature(row: Mapping[str, Any]) -> str:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    metric_label = _normalise_spaces(
        str(
            row.get("metric_label")
            or answer_slots.get("metric_label")
            or row.get("task_id")
            or ""
        )
    )
    if not metric_label:
        return ""
    operation_family = aggregate_result_operation_family(row)
    if operation_family:
        return f"{operation_family}:{metric_label}"
    return metric_label


def growth_operand_sign_consistency_rank(row: Mapping[str, Any]) -> int:
    if aggregate_result_operation_family(row) != "growth_rate":
        return 1
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    current_slot = dict(answer_slots.get("current_value") or {})
    prior_slot = dict(answer_slots.get("prior_value") or {})

    def _sign(slot: Dict[str, Any]) -> int:
        value = slot.get("normalized_value")
        if value is None:
            return 0
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return 0
        if numeric_value > 0:
            return 1
        if numeric_value < 0:
            return -1
        return 0

    current_sign = _sign(current_slot)
    prior_sign = _sign(prior_slot)
    if current_sign and prior_sign:
        return 2 if current_sign == prior_sign else 0
    return 1


def _aggregate_result_rank(
    row: Dict[str, Any],
    source_slot_by_task_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[int, int, int, int, int, int, int]:
    calculation_result = dict(row.get("calculation_result") or {})
    status = _normalise_spaces(
        str(
            row.get("status")
            or calculation_result.get("status")
            or ""
        )
    ).lower()
    status_rank = {
        "ok": 4,
        "partial": 3,
        "ready": 3,
        "insufficient_operands": 1,
        "retry_retrieval": 1,
        "missing": 0,
    }.get(status, 0)
    material_rank = 0 if material_gap_feedback_for_subtask_result(row) else 1
    answer_rank = 1 if _normalise_spaces(str(row.get("answer") or "")) else 0
    growth_sign_rank = growth_operand_sign_consistency_rank(row)
    dependency_slot_rank, scope_coherence_rank = aggregate_result_dependency_coherence_ranks(
        row,
        source_slot_by_task_id,
    )
    operand_rank = len(list(calculation_result.get("source_row_ids") or []))
    return status_rank, material_rank, answer_rank, growth_sign_rank, dependency_slot_rank, scope_coherence_rank, operand_rank


def nested_aggregate_result_rank(row: Dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    calculation_result = dict(row.get("calculation_result") or {})
    status = _normalise_spaces(
        str(row.get("status") or calculation_result.get("status") or "")
    ).lower()
    status_rank = {
        "ok": 4,
        "partial": 3,
        "ready": 3,
        "insufficient_operands": 1,
        "retry_retrieval": 1,
        "missing": 0,
    }.get(status, 0)
    material_rank = 1 if subtask_row_has_material(row) else 0
    gap_free_rank = 0 if material_gap_feedback_for_subtask_result(row) else 1
    operation_family = aggregate_result_operation_family(row)
    non_aggregate_rank = 0 if operation_family == "aggregate_subtasks" else 1
    growth_sign_rank = growth_operand_sign_consistency_rank(row)
    source_count = len(_clean_source_row_ids([
        row.get("source_row_ids"),
        calculation_result.get("source_row_ids"),
        row.get("selected_claim_ids"),
        calculation_result.get("source_evidence_ids"),
    ]))
    answer_text = _normalise_spaces(
        str(
            row.get("answer")
            or calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or ""
        )
    )
    digit_count = len(re.findall(r"\d", answer_text))
    return (
        status_rank,
        material_rank,
        gap_free_rank,
        non_aggregate_rank,
        growth_sign_rank,
        source_count,
        digit_count,
        len(answer_text),
    )


def dedupe_aggregate_subtask_results(
    ordered_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    source_slot_by_task_id = aggregate_source_slot_by_task_id(ordered_results)
    winners: Dict[str, tuple[int, tuple[int, int, int, int, int, int, int], Dict[str, Any]]] = {}
    passthrough: List[tuple[int, Dict[str, Any]]] = []
    for index, row in enumerate(ordered_results):
        signature = aggregate_result_signature(row)
        if not signature:
            passthrough.append((index, row))
            continue
        rank = _aggregate_result_rank(row, source_slot_by_task_id)
        incumbent = winners.get(signature)
        if incumbent is None or rank > incumbent[1] or (rank == incumbent[1] and index > incumbent[0]):
            winners[signature] = (index, rank, row)
    deduped = sorted(
        [item for item in winners.values()] + [(index, (0, 0, 0, 0, 0, 0, 0), row) for index, row in passthrough],
        key=lambda item: item[0],
    )
    return [dict(item[2]) for item in deduped]


def _replacement_lookup_slot_for_component(
    component: Dict[str, Any],
    lookup_slots: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    label = _normalise_spaces(str(component.get("label") or ""))
    concept = _normalise_spaces(str(component.get("concept") or ""))
    if not (label or concept):
        return {}
    for slot in lookup_slots:
        slot_label = _normalise_spaces(str(slot.get("label") or ""))
        slot_concept = _normalise_spaces(str(slot.get("concept") or ""))
        if concept and slot_concept and concept == slot_concept:
            return slot
        if label and slot_label and (
            _operand_text_match(label, {"label": slot_label, "aliases": []})
            or _operand_text_match(slot_label, {"label": label, "aliases": []})
        ):
            return slot
    return {}


def _sync_component_slot_from_lookup_slot(
    component: Dict[str, Any],
    lookup_slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    replacement = _replacement_lookup_slot_for_component(component, lookup_slots)
    if not replacement:
        return component
    value_keys = (
        "raw_value",
        "raw_unit",
        "normalized_value",
        "normalized_unit",
        "rendered_value",
    )
    return {
        **component,
        **{key: replacement.get(key) for key in value_keys if replacement.get(key) is not None},
        "source_row_id": replacement.get("source_row_id") or component.get("source_row_id"),
        "source_row_ids": replacement.get("source_row_ids") or component.get("source_row_ids"),
        "source_anchor": replacement.get("source_anchor") or component.get("source_anchor"),
    }


def synchronize_aggregate_arithmetic_components(
    sync_input: AggregateArithmeticComponentSyncInput,
) -> AggregateArithmeticComponentSyncResult:
    """Synchronize prepared lookup slots into one aggregate arithmetic row."""

    row = sync_input.projection_row
    lookup_slots = sync_input.lookup_slots
    if not lookup_slots or aggregate_result_operation_family(row) not in {
        "ratio",
        "growth_rate",
        "difference",
        "sum",
    }:
        return AggregateArithmeticComponentSyncResult(projection_row=row)
    updated = dict(row)
    calculation_result = dict(updated.get("calculation_result") or {})
    if not calculation_result:
        return AggregateArithmeticComponentSyncResult(projection_row=updated)
    answer_slots = dict(calculation_result.get("answer_slots") or {})

    for container_key in ("components_by_role", "components_by_group"):
        container = dict(answer_slots.get(container_key) or {})
        if not container:
            continue
        synced_container: Dict[str, Any] = {}
        for key, values in container.items():
            synced_container[key] = [
                _sync_component_slot_from_lookup_slot(dict(item), lookup_slots)
                if isinstance(item, dict)
                else item
                for item in list(values or [])
            ]
        answer_slots[container_key] = synced_container

    series = [dict(item) for item in list(calculation_result.get("series") or []) if isinstance(item, dict)]
    if series:
        calculation_result["series"] = [
            _sync_component_slot_from_lookup_slot(item, lookup_slots)
            for item in series
        ]

    primary_value = dict(answer_slots.get("primary_value") or {})
    operation_family = aggregate_result_operation_family(row)
    if primary_value and operation_family in {"difference", "sum"}:
        answer_slots["delta_value"] = dict(primary_value)
    if answer_slots:
        calculation_result["answer_slots"] = answer_slots
    updated["calculation_result"] = calculation_result
    return AggregateArithmeticComponentSyncResult(projection_row=updated)


def _numeric_slot_from_synced_answer_sentence(
    answer_sentence: str,
    operation_family: str,
) -> Dict[str, Any]:
    sentence = _normalise_spaces(answer_sentence)
    if not sentence:
        return {}
    candidates = extract_numeric_surface_candidates(sentence)
    if not candidates:
        return {}
    candidate = candidates[0]
    if operation_family not in {"ratio", "growth_rate"}:
        candidate = candidates[-1]
    return numeric_surface_slot_components(candidate)


def synchronize_aggregate_projection_row_surface(
    sync_input: AggregateProjectionRowSurfaceSyncInput,
) -> AggregateProjectionRowSurfaceSyncResult:
    """Synchronize one graph-selected answer surface into a prepared result row."""

    row = sync_input.projection_row
    answer = sync_input.answer
    rendered_value = sync_input.rendered_value
    updated = {
        **dict(row),
        "answer": answer,
        "projection_surface_synced_from_final_answer": True,
    }
    if rendered_value:
        updated["rendered_value"] = rendered_value

    calculation_result = dict(row.get("calculation_result") or {})
    if not calculation_result:
        return AggregateProjectionRowSurfaceSyncResult(projection_row=updated)
    slot_components = _numeric_slot_from_synced_answer_sentence(
        answer,
        aggregate_result_operation_family(row),
    )
    calculation_result["formatted_result"] = answer
    if rendered_value:
        calculation_result["rendered_value"] = rendered_value
    if slot_components:
        calculation_result["result_value"] = slot_components.get("normalized_value")
        raw_unit = _normalise_spaces(str(slot_components.get("raw_unit") or ""))
        if raw_unit:
            calculation_result["result_unit"] = raw_unit
        operation_family = aggregate_result_operation_family(row)
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        primary_value = dict(answer_slots.get("primary_value") or {})
        if primary_value or operation_family in {"difference", "sum", "lookup"}:
            primary_value = {
                **primary_value,
                "status": primary_value.get("status") or "ok",
                "role": primary_value.get("role") or "primary_value",
                "label": primary_value.get("label") or row.get("metric_label") or "",
                "raw_value": slot_components.get("raw_value"),
                "raw_unit": slot_components.get("raw_unit"),
                "normalized_value": slot_components.get("normalized_value"),
                "normalized_unit": slot_components.get("normalized_unit"),
                "rendered_value": slot_components.get("rendered_value") or rendered_value,
            }
            primary_value["rendered_value"] = rendered_value
            answer_slots["primary_value"] = primary_value
            if operation_family == "lookup":
                calculation_result["current_value"] = slot_components.get("normalized_value")
                calculation_result["current_period"] = calculation_result.get("current_period") or primary_value.get("period") or ""
                series = [
                    dict(item)
                    for item in list(calculation_result.get("series") or [])
                    if isinstance(item, dict)
                ]
                if series:
                    series[0] = {**series[0], **slot_components, "rendered_value": rendered_value}
                else:
                    series = [dict(primary_value)]
                calculation_result["series"] = series

                for container_key in ("components_by_role", "components_by_group"):
                    container = dict(answer_slots.get(container_key) or {})
                    target_keys = ["primary_value"] if container_key == "components_by_role" else ["primary", "primary_value"]
                    for target_key in target_keys:
                        if target_key not in container:
                            continue
                        values = [
                            dict(item)
                            for item in list(container.get(target_key) or [])
                            if isinstance(item, dict)
                        ]
                        if values:
                            values[0] = {**values[0], **slot_components, "rendered_value": rendered_value}
                        else:
                            values = [dict(primary_value)]
                        container[target_key] = values
                    if container:
                        answer_slots[container_key] = container
                derived_metrics = dict(calculation_result.get("derived_metrics") or {})
                if derived_metrics:
                    derived_metrics["formula_result_value"] = slot_components.get("normalized_value")
                    calculation_result["derived_metrics"] = derived_metrics
            calculation_result["answer_slots"] = answer_slots
    updated["calculation_result"] = calculation_result
    return AggregateProjectionRowSurfaceSyncResult(projection_row=updated)


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
