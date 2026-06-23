"""Runtime calculation trace projection helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, MutableMapping, Optional

from src.agent.financial_answer_projection import _preferred_complete_aggregate_subtask_answer
from src.agent.financial_graph_state import RuntimeCalculationTrace
from src.agent.financial_graph_model_loaders import _validate_answer_slots_payload
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _format_korean_won_compact,
    _normalise_spaces,
)
from src.agent.financial_task_artifacts import (
    _find_task_record_in_list,
    _latest_artifact_value_for_task_records,
    _project_task_trace_from_runtime,
)
from src.config.report_scoped_cache import (
    classify_report_cache_candidate,
    classify_report_cache_consumer_candidate,
    report_cache_key_id,
)
from src.schema.runtime_enums import ArtifactKind


def _trace_has_material(trace: Mapping[str, Any]) -> bool:
    return bool(
        trace.get("calculation_operands")
        or trace.get("calculation_plan")
        or trace.get("calculation_result")
    )


def _attach_runtime_projection_metadata(
    trace: Dict[str, Any],
    *,
    source: str,
    source_task_id: str = "",
    legacy_fallback: bool = False,
) -> Dict[str, Any]:
    if not _trace_has_material(trace):
        return trace
    metadata = dict(trace.get("runtime_projection") or {})
    metadata.update(
        {
            "source": str(source or "").strip(),
            "legacy_fallback": bool(legacy_fallback),
        }
    )
    if source_task_id:
        metadata["source_task_id"] = str(source_task_id).strip()
    trace["runtime_projection"] = metadata
    return trace


def _build_runtime_calculation_trace(
    *,
    calculation_operands: Optional[List[Dict[str, Any]]] = None,
    calculation_plan: Optional[Dict[str, Any]] = None,
    calculation_result: Optional[Dict[str, Any]] = None,
    source: str,
    source_task_id: str = "",
    legacy_fallback: bool = False,
) -> RuntimeCalculationTrace:
    trace: RuntimeCalculationTrace = {
        "calculation_operands": [dict(item) for item in (calculation_operands or [])],
        "calculation_plan": dict(calculation_plan or {}),
        "calculation_result": dict(calculation_result or {}),
    }
    return _attach_runtime_projection_metadata(
        trace,
        source=source,
        source_task_id=source_task_id,
        legacy_fallback=legacy_fallback,
    )


def _first_mapping(*values: Any) -> Dict[str, Any]:
    for value in values:
        if isinstance(value, Mapping):
            return dict(value)
    return {}


def _source_section_from_table_id(value: Any) -> str:
    text = _normalise_spaces(str(value or ""))
    if not text:
        return ""
    marker_index = text.find("::table:")
    if marker_index <= 0:
        return ""
    return text[:marker_index].strip()


def _extract_source_evidence_ids_from_records(records: List[Any]) -> List[str]:
    values: List[Any] = []
    for record in records or []:
        if not isinstance(record, Mapping):
            continue
        values.extend(
            [
                record.get("evidence_id"),
                record.get("source_evidence_id"),
                record.get("source_evidence_ids"),
            ]
        )
    return _clean_source_row_ids(values)


def _extract_subtask_source_evidence_ids(
    row: Mapping[str, Any],
    calculation_result: Mapping[str, Any],
    answer_slots: Mapping[str, Any],
    source_row_ids: List[Any],
) -> List[str]:
    values: List[Any] = [
        row.get("evidence_id"),
        row.get("evidence_ids"),
        row.get("source_evidence_id"),
        row.get("source_evidence_ids"),
        calculation_result.get("evidence_id"),
        calculation_result.get("evidence_ids"),
        calculation_result.get("source_evidence_id"),
        calculation_result.get("source_evidence_ids"),
        answer_slots.get("evidence_id"),
        answer_slots.get("evidence_ids"),
        answer_slots.get("source_evidence_id"),
        answer_slots.get("source_evidence_ids"),
    ]
    if not _clean_source_row_ids(source_row_ids):
        values.extend(
            [
                _extract_source_evidence_ids_from_records(row.get("runtime_evidence") or []),
                _extract_source_evidence_ids_from_records(row.get("evidence_items") or []),
                _extract_source_evidence_ids_from_records(calculation_result.get("runtime_evidence") or []),
                _extract_source_evidence_ids_from_records(calculation_result.get("evidence_items") or []),
            ]
        )
    return _clean_source_row_ids(values)


def _collect_nested_result_evidence(
    rows: List[Mapping[str, Any]],
    *,
    max_depth: int = 6,
) -> List[Dict[str, Any]]:
    evidence: List[Dict[str, Any]] = []

    def _append(items: Any) -> None:
        evidence.extend(dict(item) for item in list(items or []) if isinstance(item, dict))

    def _collect(row: Mapping[str, Any], depth: int = 0) -> None:
        if depth > max_depth:
            return
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        for payload in (row, calculation_result):
            _append(payload.get("runtime_evidence"))
            _append(payload.get("evidence_items"))
        nested_rows = list(calculation_result.get("subtask_results") or [])
        nested_rows.extend(list(answer_slots.get("subtask_results") or []))
        for nested_row in nested_rows:
            if isinstance(nested_row, Mapping):
                _collect(nested_row, depth + 1)

    for row in list(rows or []):
        if isinstance(row, Mapping):
            _collect(row)
    return evidence


def _operand_row_has_material_numeric_payload(row: Mapping[str, Any]) -> bool:
    status = _normalise_spaces(str(row.get("status") or "")).lower()
    if status == "missing":
        return False
    raw_unit = _normalise_spaces(str(row.get("raw_unit") or row.get("unit") or ""))
    normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
    raw_value = _normalise_spaces(
        str(
            row.get("raw_value")
            or row.get("value")
            or row.get("rendered_value")
            or row.get("display_value")
            or ""
        )
    )
    raw_digit_count = len(re.findall(r"\d", raw_value))
    if normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4:
        return False
    if row.get("normalized_value") is not None:
        return True
    return bool(raw_value)


def _answer_mentions_any_surface(
    final_answer: str,
    surfaces: List[Any],
    *,
    default_on_empty_answer: bool = False,
) -> bool:
    final_text = _normalise_spaces(str(final_answer or ""))
    if not final_text:
        return default_on_empty_answer
    return any(
        surface_text and surface_text in final_text
        for surface_text in (_normalise_spaces(str(surface or "")) for surface in surfaces)
    )


def _subtask_numeric_result_visible_in_answer(
    final_answer: str,
    row: Mapping[str, Any],
    calculation_result: Mapping[str, Any],
    answer_slots: Mapping[str, Any],
) -> bool:
    primary_slot = dict(answer_slots.get("primary_value") or {})
    return _answer_mentions_any_surface(
        final_answer,
        [
            row.get("answer"),
            calculation_result.get("formatted_result"),
            calculation_result.get("rendered_value"),
            primary_slot.get("rendered_value"),
            primary_slot.get("raw_value"),
        ],
        default_on_empty_answer=True,
    )


def _answer_mentions_numeric_slot(final_answer: str, slot: Mapping[str, Any]) -> bool:
    if _answer_mentions_any_surface(
        final_answer,
        [
            slot.get("rendered_value"),
            slot.get("raw_value"),
            slot.get("display_value"),
        ],
    ):
        return True
    normalized_value = slot.get("normalized_value")
    if normalized_value is None:
        return False
    try:
        target_value = float(normalized_value)
    except (TypeError, ValueError):
        return False
    normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
    if normalized_unit == "KRW":
        compact_surface = _format_korean_won_compact(target_value)
        if _answer_mentions_any_surface(final_answer, [compact_surface]):
            return True
    try:
        from src.agent.financial_numeric_surface import extract_numeric_surface_candidates
    except Exception:
        return False
    for candidate in extract_numeric_surface_candidates(final_answer):
        candidate_value = candidate.get("value")
        if candidate_value is None:
            continue
        candidate_kind = _normalise_spaces(str(candidate.get("kind") or "")).lower()
        if normalized_unit == "KRW" and candidate_kind != "currency":
            continue
        if normalized_unit == "PERCENT" and candidate_kind != "percent":
            continue
        try:
            candidate_float = float(candidate_value)
        except (TypeError, ValueError):
            continue
        tolerance = max(abs(target_value), abs(candidate_float), 1.0) * 1e-6
        if abs(candidate_float - target_value) <= tolerance:
            return True
    return False


def _aggregate_operand_key(row: Mapping[str, Any], source_ids: List[str] | None = None) -> tuple[str, ...]:
    cleaned_source_ids = list(source_ids or _clean_source_row_ids([
        row.get("source_row_id"),
        row.get("source_row_ids"),
    ]))
    return (
        str(row.get("task_id") or ""),
        str(row.get("operand_id") or row.get("matched_operand_role") or ""),
        cleaned_source_ids[0] if cleaned_source_ids else "",
        "|".join(cleaned_source_ids),
        str(row.get("raw_value") or row.get("value") or ""),
        str(row.get("raw_unit") or ""),
        str(row.get("label") or row.get("label_kr") or ""),
    )


def _append_aggregate_operand(
    aggregate_operands: List[Dict[str, Any]],
    seen_operand_keys: set[tuple[str, ...]],
    operand_row: Mapping[str, Any],
    source_ids: List[Any] | None = None,
) -> None:
    row = dict(operand_row)
    cleaned_source_ids = (
        _clean_source_row_ids(source_ids)
        if source_ids is not None
        else _clean_source_row_ids([
            row.get("source_row_id"),
            row.get("source_row_ids"),
        ])
    )
    if source_ids is not None and cleaned_source_ids:
        row["source_row_id"] = cleaned_source_ids[0]
        row["source_row_ids"] = cleaned_source_ids
    if not _operand_row_has_material_numeric_payload(row):
        return
    operand_key = _aggregate_operand_key(row, cleaned_source_ids)
    if operand_key in seen_operand_keys:
        return
    seen_operand_keys.add(operand_key)
    aggregate_operands.append(row)


def _report_cache_candidate_for_trace(state: Dict[str, Any], trace: Dict[str, Any]) -> Dict[str, Any]:
    report_scope = dict(state.get("report_scope") or {})
    active_subtask = dict(state.get("active_subtask") or {})
    calculation_operands = [
        dict(item)
        for item in list(trace.get("calculation_operands") or [])
        if isinstance(item, Mapping)
    ]
    calculation_plan = dict(trace.get("calculation_plan") or {})
    calculation_result = dict(trace.get("calculation_result") or {})
    if not (calculation_operands or calculation_plan or calculation_result):
        return {}
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    primary_slot = _first_mapping(
        answer_slots.get("primary_value"),
        answer_slots.get("current_value"),
        answer_slots.get("delta_value"),
    )
    operand = calculation_operands[0] if calculation_operands else {}
    operand_metadata = dict(operand.get("metadata") or {})
    source_table_id = (
        operand.get("source_table_id")
        or operand.get("table_source_id")
        or operand_metadata.get("source_table_id")
        or operand_metadata.get("table_source_id")
    )

    candidate = {
        **report_scope,
        "value_kind": "calculation_result",
        "concept_id": (
            primary_slot.get("concept")
            or active_subtask.get("concept_id")
            or active_subtask.get("metric_family")
            or state.get("target_metric_family")
        ),
        "metric_label": (
            primary_slot.get("label")
            or active_subtask.get("metric_label")
            or calculation_result.get("metric_label")
        ),
        "period": (
            primary_slot.get("period")
            or primary_slot.get("period_label")
            or operand.get("period")
            or operand.get("period_label")
            or report_scope.get("year")
        ),
        "value_text": (
            calculation_result.get("rendered_value")
            or calculation_result.get("formatted_value")
            or calculation_result.get("formatted_result")
            or primary_slot.get("display")
            or primary_slot.get("value_text")
            or primary_slot.get("rendered_value")
        ),
        "normalized_value": (
            calculation_result.get("value")
            if calculation_result.get("value") is not None
            else primary_slot.get("normalized_value")
        ),
        "consolidation_scope": (
            operand.get("consolidation_scope")
            or operand_metadata.get("consolidation_scope")
            or active_subtask.get("consolidation_scope")
        ),
        "statement_type": operand.get("statement_type") or operand_metadata.get("statement_type"),
        "source_section": (
            operand.get("source_section")
            or operand.get("source_section_path")
            or operand.get("section_path")
            or operand_metadata.get("source_section")
            or operand_metadata.get("section_path")
            or _source_section_from_table_id(source_table_id)
        ),
        "source_table_id": source_table_id,
        "source_anchor": operand.get("source_anchor") or operand_metadata.get("source_anchor"),
        "source_row_id": (
            operand.get("source_row_id")
            or operand.get("source_row_ids")
            or operand.get("row_id")
            or primary_slot.get("source_row_id")
            or primary_slot.get("source_row_ids")
        ),
        "evidence_refs": calculation_result.get("evidence_refs") or primary_slot.get("evidence_refs"),
    }
    classification = classify_report_cache_candidate(candidate)
    projection = {
        "status": classification["status"],
        "reasons": list(classification.get("reasons") or []),
        "key": dict(classification.get("key") or {}),
        "key_id": report_cache_key_id(classification.get("key") or {}),
        "read_only": True,
    }
    projection["retrieval_bypass"] = classify_report_cache_consumer_candidate(projection)
    return projection


def _runtime_trace_state_update(
    state: Dict[str, Any],
    *,
    calculation_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    calculation_result: Dict[str, Any],
) -> Dict[str, Any]:
    resolved_trace = _build_runtime_calculation_trace(
        calculation_operands=calculation_operands,
        calculation_plan=calculation_plan,
        calculation_result=calculation_result,
        source="runtime_trace_state_update",
        legacy_fallback=False,
    )
    update: Dict[str, Any] = {
        "resolved_calculation_trace": resolved_trace,
        "structured_result": dict(calculation_result),
    }
    report_cache_candidate = _report_cache_candidate_for_trace(state, resolved_trace)
    if report_cache_candidate:
        resolved_trace["report_cache_candidate"] = report_cache_candidate
    return update


def _project_task_trace_from_state(
    state: Dict[str, Any],
    task_id: str,
) -> Dict[str, Any]:
    task_id = str(task_id or "").strip()
    active_task_id = str((state.get("active_subtask") or {}).get("task_id") or "").strip()
    tasks = [dict(item) for item in (state.get("tasks") or [])]
    artifacts = [dict(item) for item in (state.get("artifacts") or [])]

    calculation_operands = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.OPERAND_SET,
        payload_key="calculation_operands",
    )
    calculation_plan = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.CALCULATION_PLAN,
        payload_key="calculation_plan",
    )
    calculation_result = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.CALCULATION_RESULT,
        payload_key="calculation_result",
    )
    reconciliation_result = _latest_artifact_value_for_task_records(
        tasks,
        artifacts,
        task_id=task_id,
        kind=ArtifactKind.RECONCILIATION_RESULT,
        payload_key="reconciliation_result",
    )

    if task_id and task_id == active_task_id:
        active_trace = _normalise_resolved_calculation_trace(state)
        if not active_trace:
            active_trace = _resolve_runtime_calculation_trace(
                state,
                allow_legacy_top_level=False,
            )
        active_trace_result = dict(active_trace.get("calculation_result") or {})
        active_trace_plan = dict(active_trace.get("calculation_plan") or {})
        active_trace_operation = _trace_operation_family(
            calculation_plan=active_trace_plan,
            calculation_result=active_trace_result,
        )
        active_task_operation = _normalise_spaces(
            str((state.get("active_subtask") or {}).get("operation_family") or "")
        ).lower()
        if (
            active_trace_operation == "aggregate_subtasks"
            and active_task_operation != "aggregate_subtasks"
        ):
            if calculation_operands or calculation_plan or calculation_result:
                active_trace = {}
            else:
                # Aggregate projections summarize finished siblings and should
                # not become the active task's own result.
                active_trace = {}
        if active_trace.get("calculation_operands"):
            calculation_operands = [
                dict(item)
                for item in (
                    active_trace.get("calculation_operands")
                    or []
                )
            ]
        if active_trace.get("calculation_plan"):
            calculation_plan = dict(
                active_trace.get("calculation_plan")
            )
        if active_trace.get("calculation_result"):
            calculation_result = dict(
                active_trace.get("calculation_result")
            )
        if not reconciliation_result:
            reconciliation_result = dict(state.get("reconciliation_result") or {})

    task_record = _find_task_record_in_list(tasks, task_id)
    return {
        "task_id": task_id,
        "artifact_ids": [str(value).strip() for value in (task_record.get("artifact_ids") or []) if str(value).strip()],
        "calculation_operands": list(calculation_operands or []),
        "calculation_plan": dict(calculation_plan or {}),
        "calculation_result": dict(calculation_result or {}),
        "reconciliation_result": dict(reconciliation_result or {}),
    }


def _project_aggregate_subtask_row(
    row: Mapping[str, Any],
    *,
    final_answer: str,
    aggregate_operands: List[Dict[str, Any]],
    seen_operand_keys: set[tuple[str, ...]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    task_id = str(row.get("task_id") or "").strip()
    metric_family = str(row.get("metric_family") or "").strip()
    metric_label = str(row.get("metric_label") or "").strip()
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})

    has_result_surface = bool(calculation_result or answer_slots or str(row.get("answer") or "").strip())
    if not has_result_surface or _subtask_numeric_result_visible_in_answer(final_answer, row, calculation_result, answer_slots):
        for operand in list(row.get("calculation_operands") or []):
            operand_row = dict(operand)
            operand_row.setdefault("task_id", task_id)
            operand_row.setdefault("metric_family", metric_family)
            operand_row.setdefault("metric_label", metric_label)
            _append_aggregate_operand(aggregate_operands, seen_operand_keys, operand_row)

    plan = dict(row.get("calculation_plan") or {})
    subtask_plan = {}
    if plan:
        subtask_plan = {
            "task_id": task_id,
            "metric_family": metric_family,
            "metric_label": metric_label,
            "calculation_plan": plan,
        }

    operation_family = _trace_operation_family(
        calculation_plan=plan,
        calculation_result=calculation_result,
    ) or str(answer_slots.get("operation_family") or row.get("operation_family") or "").strip()
    primary_slot = dict(answer_slots.get("primary_value") or {})
    if operation_family in {"lookup", "single_value"} and _answer_mentions_numeric_slot(final_answer, primary_slot):
        operand_row = {
            **primary_slot,
            "operand_id": primary_slot.get("operand_id") or f"{task_id}:primary_value",
            "matched_operand_role": primary_slot.get("matched_operand_role") or primary_slot.get("role") or "primary_value",
            "task_id": task_id,
            "metric_family": metric_family,
            "metric_label": metric_label,
            "source_task_id": primary_slot.get("source_task_id") or task_id,
            "source_slot": primary_slot.get("source_slot") or "primary_value",
        }
        source_ids = _clean_source_row_ids([
            operand_row.get("source_row_id"),
            operand_row.get("source_row_ids"),
            row.get("source_row_id"),
            row.get("source_row_ids"),
            calculation_result.get("source_row_ids"),
        ])
        _append_aggregate_operand(aggregate_operands, seen_operand_keys, operand_row, source_ids)

    subtask_source_row_ids = _clean_source_row_ids([
        row.get("source_row_id"),
        row.get("source_row_ids"),
        calculation_result.get("source_row_ids"),
        answer_slots.get("source_row_ids"),
    ])
    subtask_source_evidence_ids = _extract_subtask_source_evidence_ids(
        row,
        calculation_result,
        answer_slots,
        subtask_source_row_ids,
    )
    subtask_result_view = {
        "task_id": task_id,
        "metric_family": metric_family,
        "metric_label": metric_label,
        "operation_family": operation_family,
        "answer": str(row.get("answer") or "").strip(),
        "status": str(row.get("status") or ""),
        "calculation_result": calculation_result,
        "source_row_ids": subtask_source_row_ids,
        "source_evidence_ids": subtask_source_evidence_ids,
    }
    return subtask_plan, subtask_result_view


def _aggregate_projection_source_ids(
    *,
    aggregate_operands: List[Dict[str, Any]],
    subtask_result_views: List[Dict[str, Any]],
) -> tuple[List[str], List[str]]:
    source_row_ids = list(
        dict.fromkeys(
            source_row_id
            for operand in aggregate_operands
            for source_row_id in _clean_source_row_ids([
                operand.get("source_row_id"),
                operand.get("source_row_ids"),
            ])
        )
    )
    subtask_source_row_ids = list(
        dict.fromkeys(
            source_row_id
            for item in subtask_result_views
            for source_row_id in _clean_source_row_ids(item.get("source_row_ids") or [])
        )
    )
    source_evidence_ids = list(
        dict.fromkeys(
            source_id
            for item in subtask_result_views
            for source_id in _clean_source_row_ids(item.get("source_evidence_ids") or [])
        )
    )
    aggregate_source_row_ids = list(dict.fromkeys([*source_row_ids, *subtask_source_row_ids, *source_evidence_ids]))
    return aggregate_source_row_ids, source_evidence_ids


def _aggregate_answer_slot_subtask_results(subtask_result_views: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [
        {
            "task_id": str(item.get("task_id") or ""),
            "metric_family": str(item.get("metric_family") or ""),
            "metric_label": str(item.get("metric_label") or ""),
            "operation_family": str(item.get("operation_family") or ""),
            "answer": str(item.get("answer") or ""),
            "answer_slots": dict((item.get("calculation_result") or {}).get("answer_slots") or {}),
            "rendered_value": str((item.get("calculation_result") or {}).get("rendered_value") or ""),
            "source_row_ids": list(item.get("source_row_ids") or []),
            "source_evidence_ids": list(item.get("source_evidence_ids") or []),
        }
        for item in subtask_result_views
    ]


def _build_aggregate_calculation_projection(
    subtask_results: List[Dict[str, Any]],
    final_answer: str,
) -> Dict[str, Any]:
    aggregate_operands: List[Dict[str, Any]] = []
    seen_operand_keys: set[tuple[str, ...]] = set()
    subtask_plans: List[Dict[str, Any]] = []
    subtask_result_views: List[Dict[str, Any]] = []

    for row in list(subtask_results or []):
        subtask_plan, subtask_result_view = _project_aggregate_subtask_row(
            row,
            final_answer=final_answer,
            aggregate_operands=aggregate_operands,
            seen_operand_keys=seen_operand_keys,
        )
        if subtask_plan:
            subtask_plans.append(subtask_plan)
        subtask_result_views.append(subtask_result_view)

    all_ok = all(str(item.get("status") or "") == "ok" for item in subtask_result_views) if subtask_result_views else False
    aggregate_source_row_ids, source_evidence_ids = _aggregate_projection_source_ids(
        aggregate_operands=aggregate_operands,
        subtask_result_views=subtask_result_views,
    )
    return {
        "calculation_operands": aggregate_operands,
        "calculation_plan": {
            "status": "ok" if subtask_plans else "empty",
            "mode": "aggregate_subtasks",
            "subtask_count": len(subtask_result_views),
            "subtasks": subtask_plans,
        },
        "calculation_result": {
            "status": "ok" if all_ok else "partial",
            "rendered_value": final_answer,
            "formatted_result": final_answer,
            "source_row_ids": aggregate_source_row_ids,
            "source_evidence_ids": source_evidence_ids,
            "subtask_results": subtask_result_views,
            "answer_slots": _validate_answer_slots_payload(
                {
                    "operation_family": "aggregate_subtasks",
                    "source_row_ids": aggregate_source_row_ids,
                    "subtask_results": _aggregate_answer_slot_subtask_results(subtask_result_views),
                }
            ),
            "derived_metrics": {
                "subtask_count": len(subtask_result_views),
                "subtask_ids": [
                    str(item.get("task_id") or "")
                    for item in subtask_result_views
                    if str(item.get("task_id") or "").strip()
                ],
                "aggregate_source_row_ids": aggregate_source_row_ids,
                "aggregate_source_evidence_ids": source_evidence_ids,
            },
        },
    }


def _trace_operands_cover_plan(
    trace: Mapping[str, Any],
    plan: Mapping[str, Any],
) -> bool:
    operands = [
        dict(item)
        for item in (trace.get("calculation_operands") or [])
        if isinstance(item, Mapping)
    ]
    if not operands:
        return False
    operand_ids = {
        str(row.get("operand_id") or "").strip()
        for row in operands
        if str(row.get("operand_id") or "").strip()
    }
    if not operand_ids:
        return False
    required_ids = [
        str(operand_id or "").strip()
        for operand_id in (plan.get("ordered_operand_ids") or [])
        if str(operand_id or "").strip()
    ]
    if not required_ids:
        required_ids = [
            str(binding.get("operand_id") or "").strip()
            for binding in (plan.get("variable_bindings") or [])
            if isinstance(binding, Mapping) and str(binding.get("operand_id") or "").strip()
        ]
    return bool(required_ids) and all(operand_id in operand_ids for operand_id in required_ids)


def _fill_projected_trace_from_canonical(
    projected: Mapping[str, Any],
    canonical: Mapping[str, Any],
) -> Dict[str, Any]:
    """Fill missing task-projected trace parts from canonical runtime trace."""
    merged = {
        "calculation_operands": list(projected.get("calculation_operands") or []),
        "calculation_plan": dict(projected.get("calculation_plan") or {}),
        "calculation_result": dict(projected.get("calculation_result") or {}),
    }
    canonical_plan = dict(canonical.get("calculation_plan") or {})
    projected_plan = dict(merged.get("calculation_plan") or {})
    active_plan = projected_plan or canonical_plan
    if (
        not merged["calculation_operands"]
        and active_plan
        and _trace_operands_cover_plan(canonical, active_plan)
    ):
        merged["calculation_operands"] = [
            dict(item)
            for item in (canonical.get("calculation_operands") or [])
            if isinstance(item, Mapping)
        ]
    if not merged["calculation_plan"] and canonical_plan:
        merged["calculation_plan"] = canonical_plan
    if not merged["calculation_result"] and canonical.get("calculation_result"):
        merged["calculation_result"] = dict(canonical.get("calculation_result") or {})
    return merged


def _build_fallback_calculation_trace(
    result: Dict[str, Any],
    *,
    allow_legacy_top_level: bool = False,
) -> Dict[str, Any]:
    operands = list(result.get("calculation_operands") or [])
    plan = dict(result.get("calculation_plan") or {})
    top_level_result = dict(result.get("calculation_result") or {})
    structured_result = dict(result.get("structured_result") or {})
    if not allow_legacy_top_level:
        if structured_result:
            return _build_runtime_calculation_trace(
                calculation_result=structured_result,
                source="structured_result",
                legacy_fallback=False,
            )
        return {}

    calculation_result = dict(top_level_result)
    source = "legacy_top_level"
    legacy_fallback = bool(operands or plan or top_level_result)

    if structured_result:
        calculation_result = structured_result
        if not operands and not plan and not top_level_result:
            source = "structured_result"
            legacy_fallback = False

    trace = _build_runtime_calculation_trace(
        calculation_operands=operands,
        calculation_plan=plan,
        calculation_result=calculation_result,
        source=source,
        legacy_fallback=legacy_fallback,
    )
    metadata = trace.get("runtime_projection")
    if (
        structured_result
        and isinstance(metadata, MutableMapping)
        and (operands or plan or top_level_result)
    ):
        metadata["calculation_result_source"] = "structured_result"
        if top_level_result:
            metadata["superseded_calculation_result_source"] = "legacy_top_level"
    return trace


def _normalise_resolved_calculation_trace(result: Dict[str, Any]) -> Dict[str, Any]:
    resolved = dict(result.get("resolved_calculation_trace") or {})
    structured_result = dict(result.get("structured_result") or {})

    operands = list(resolved.get("calculation_operands") or [])
    plan = dict(resolved.get("calculation_plan") or {})
    calc_result = dict(resolved.get("calculation_result") or {})
    report_cache_candidate = dict(resolved.get("report_cache_candidate") or {})
    source = "resolved_calculation_trace"
    if structured_result and not calc_result:
        calc_result = structured_result
        if not operands and not plan:
            source = "structured_result"

    if operands or plan or calc_result:
        trace = _build_runtime_calculation_trace(
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=calc_result,
            source=source,
            legacy_fallback=False,
        )
        if report_cache_candidate:
            trace["report_cache_candidate"] = report_cache_candidate
        return trace
    return {}


def _trace_operation_family(
    *,
    calculation_plan: Optional[Dict[str, Any]] = None,
    calculation_result: Optional[Dict[str, Any]] = None,
) -> str:
    plan = dict(calculation_plan or {})
    calc_result = dict(calculation_result or {})
    answer_slots = dict(calc_result.get("answer_slots") or {})
    operation_family = _normalise_spaces(
        str(
            answer_slots.get("operation_family")
            or calc_result.get("operation_family")
            or plan.get("operation_family")
            or ""
        )
    ).lower()
    if operation_family:
        return operation_family
    if str(plan.get("mode") or "").strip().lower() == "aggregate_subtasks":
        return "aggregate_subtasks"
    if calc_result.get("subtask_results"):
        return "aggregate_subtasks"
    return ""


def _structured_result_subtask_rows_and_answer(
    structured_result: Mapping[str, Any],
) -> tuple[List[Dict[str, Any]], str]:
    subtask_results = [
        dict(row)
        for row in list((structured_result or {}).get("subtask_results") or [])
        if isinstance(row, Mapping)
    ]
    structured_answer = _normalise_spaces(
        str(
            (structured_result or {}).get("formatted_result")
            or (structured_result or {}).get("rendered_value")
            or ""
        )
    )
    return subtask_results, structured_answer


def _structured_result_subtask_projection_if_public_aligned(
    result: Dict[str, Any],
    current_trace: Dict[str, Any],
) -> Dict[str, Any]:
    structured_result = dict(result.get("structured_result") or {})
    subtask_results, structured_answer = _structured_result_subtask_rows_and_answer(structured_result)
    if not subtask_results:
        return {}
    public_answer = _normalise_spaces(str(result.get("answer") or result.get("compressed_answer") or ""))
    if not public_answer or public_answer != structured_answer:
        return {}
    projection_answer = _preferred_complete_aggregate_subtask_answer(
        subtask_results,
        public_answer,
    ) or public_answer
    current_result = dict((current_trace or {}).get("calculation_result") or {})
    current_primary = dict((current_result.get("answer_slots") or {}).get("primary_value") or {})
    current_rendered = _normalise_spaces(
        str(
            current_result.get("formatted_result")
            or current_result.get("rendered_value")
            or current_primary.get("rendered_value")
            or ""
        )
    )
    projection = _build_aggregate_calculation_projection(subtask_results, projection_answer)
    projection_operands = [
        dict(item)
        for item in list(projection.get("calculation_operands") or [])
        if isinstance(item, Mapping)
    ]
    projection_result = dict(projection.get("calculation_result") or {})
    if not projection_result.get("subtask_results"):
        return {}
    projection_extends_public_answer = projection_answer != public_answer
    if current_rendered and current_rendered == public_answer and not projection_extends_public_answer:
        current_status = _normalise_spaces(str(current_result.get("status") or "")).lower()
        projection_status = _normalise_spaces(str(projection_result.get("status") or "")).lower()
        if not projection_operands:
            return {}
        if current_status == "ok" and projection_status != "ok":
            return {}
        current_operands = [
            dict(item)
            for item in list((current_trace or {}).get("calculation_operands") or [])
            if isinstance(item, Mapping)
        ]
        stale_current_operands = [
            operand
            for operand in current_operands
            if operand.get("normalized_value") is not None
            and not _answer_mentions_numeric_slot(public_answer, operand)
        ]
        if current_operands and not stale_current_operands:
            return {}
    return _attach_runtime_projection_metadata(
        projection,
        source="structured_result_subtasks",
    )


def _resolve_runtime_calculation_trace(
    result: Dict[str, Any],
    *,
    allow_legacy_top_level: bool = False,
) -> Dict[str, Any]:
    normalised = _normalise_resolved_calculation_trace(result)
    fallback_trace = _build_fallback_calculation_trace(
        result,
        allow_legacy_top_level=allow_legacy_top_level,
    )
    subtask_results = [dict(item) for item in (result.get("subtask_results") or [])]

    active_task_id = str((result.get("active_subtask") or {}).get("task_id") or "").strip()
    if not active_task_id and not subtask_results:
        calc_task_ids = [
            str(task.get("task_id") or "").strip()
            for task in (result.get("tasks") or [])
            if str(task.get("task_id") or "").strip()
            and str(task.get("kind") or "") == "calculation"
        ]
        if len(calc_task_ids) == 1:
            active_task_id = calc_task_ids[0]

    if normalised:
        plan = dict(normalised.get("calculation_plan") or {})
        calc_result = dict(normalised.get("calculation_result") or {})
        normalised_operation = _trace_operation_family(
            calculation_plan=plan,
            calculation_result=calc_result,
        )
        structured_projection = _structured_result_subtask_projection_if_public_aligned(result, normalised)
        if structured_projection:
            return structured_projection
        if normalised_operation and normalised_operation != "aggregate_subtasks":
            return normalised
        if normalised_operation == "aggregate_subtasks":
            if active_task_id:
                projected_active = _project_task_trace_from_runtime(result, active_task_id)
                if _trace_operation_family(
                    calculation_plan=dict(projected_active.get("calculation_plan") or {}),
                    calculation_result=dict(projected_active.get("calculation_result") or {}),
                ) != "aggregate_subtasks" and (
                    projected_active.get("calculation_operands")
                    or projected_active.get("calculation_plan")
                    or projected_active.get("calculation_result")
                ):
                    return _attach_runtime_projection_metadata(
                        projected_active,
                        source="task_artifact_ledger",
                        source_task_id=active_task_id,
                    )
                if _trace_operation_family(
                    calculation_plan=dict(fallback_trace.get("calculation_plan") or {}),
                    calculation_result=dict(fallback_trace.get("calculation_result") or {}),
                ) != "aggregate_subtasks" and (
                    fallback_trace.get("calculation_operands")
                    or fallback_trace.get("calculation_plan")
                    or fallback_trace.get("calculation_result")
                ):
                    return fallback_trace
            return normalised

    if active_task_id:
        projected = _project_task_trace_from_runtime(result, active_task_id)
        if normalised:
            projected = _fill_projected_trace_from_canonical(projected, normalised)
        if (
            projected["calculation_operands"]
            or projected["calculation_plan"]
            or projected["calculation_result"]
        ):
            return _attach_runtime_projection_metadata(
                projected,
                source="task_artifact_ledger",
                source_task_id=active_task_id,
            )

    if subtask_results:
        final_answer = str(result.get("answer") or result.get("compressed_answer") or "").strip()
        return _attach_runtime_projection_metadata(
            _build_aggregate_calculation_projection(subtask_results, final_answer),
            source="aggregate_subtasks",
        )

    if normalised:
        if (
            dict(normalised.get("runtime_projection") or {}).get("source")
            == "structured_result"
            and (fallback_trace.get("calculation_operands") or fallback_trace.get("calculation_plan"))
        ):
            return fallback_trace
        return normalised

    return fallback_trace


def _resolve_runtime_structured_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a structured result for the public run compatibility bridge.

    This helper intentionally preserves legacy top-level fallback for older
    caller-facing payloads. Live graph, benchmark export, MAS handoff, and debug
    readers should consume structured_result or the canonical trace directly.
    """
    structured_result = dict(result.get("structured_result") or {})
    if structured_result:
        return structured_result

    resolved_trace = _resolve_runtime_calculation_trace(
        result,
        allow_legacy_top_level=True,
    )
    resolved_result = dict(resolved_trace.get("calculation_result") or {})
    if resolved_result:
        return resolved_result

    return {}
