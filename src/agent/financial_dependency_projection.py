"""Dependency-projection helpers for aggregate calculation repair."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, List

from src.agent.financial_graph_helpers import _clean_source_row_ids, _normalise_operand_value, _normalise_spaces
from src.agent.financial_graph_planning import _synthesize_lookup_answer_slot_from_prose
from src.agent.financial_numeric_surface import extract_numeric_surface_candidates, numeric_surface_slot_components
from src.config.retrieval_policy import CALCULATION_RENDER_POLICY


def _slot_from_single_answer_numeric(
    current_slot: Dict[str, Any],
    *,
    answer_text: str,
    result_row: Dict[str, Any],
) -> Dict[str, Any]:
    current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
    if current_raw and current_raw in answer_text:
        return {}
    candidates = [
        dict(candidate)
        for candidate in extract_numeric_surface_candidates(answer_text)
        if _normalise_spaces(str(candidate.get("text") or ""))
    ]
    if len(candidates) != 1:
        return {}
    candidate = candidates[0]
    components = numeric_surface_slot_components(candidate)
    if not components:
        return {}
    normalized_unit = _normalise_spaces(str(current_slot.get("normalized_unit") or ""))
    if not normalized_unit:
        normalized_unit = str(components.get("normalized_unit") or "UNKNOWN")
    return {
        **dict(current_slot),
        "status": "ok",
        "role": current_slot.get("role") or "primary_value",
        "label": _normalise_spaces(str(result_row.get("metric_label") or current_slot.get("label") or "")),
        "raw_value": components.get("raw_value"),
        "raw_unit": components.get("raw_unit") or _normalise_spaces(str(current_slot.get("raw_unit") or "")),
        "normalized_value": components.get("normalized_value"),
        "normalized_unit": normalized_unit,
        "rendered_value": components.get("rendered_value"),
    }


def build_dependency_lookup_slots_by_task(
    ordered_results: List[Dict[str, Any]],
    task_by_id: Dict[str, Dict[str, Any]],
    *,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Dict[str, Any]]:
    slots: Dict[str, Dict[str, Any]] = {}
    for result_row in ordered_results:
        result_task_id = _normalise_spaces(str(result_row.get("task_id") or ""))
        if not result_task_id:
            continue
        metric_family = _normalise_spaces(str(result_row.get("metric_family") or "")).lower()
        operation = _normalise_spaces(
            str(result_row.get("operation_family") or operation_family_for_result(result_row) or "")
        ).lower()
        if metric_family in {"concept_lookup", "generic_numeric"} and operation not in {"lookup", "single_value"}:
            operation = "lookup"
        if operation not in {"lookup", "single_value"}:
            continue
        result = dict(result_row.get("calculation_result") or {})
        result_slots = dict(result.get("answer_slots") or result_row.get("answer_slots") or {})
        slot = dict(result_slots.get("primary_value") or {})
        answer_text = _normalise_spaces(
            str(result_row.get("answer") or result.get("formatted_result") or result.get("rendered_value") or "")
        )
        answer_numeric_slot: Dict[str, Any] = {}
        if slot_has_material(slot) and answer_text:
            answer_numeric_slot = _slot_from_single_answer_numeric(
                slot,
                answer_text=answer_text,
                result_row=result_row,
            )
        if not slot_has_material(slot) or answer_numeric_slot:
            producer_task = {
                **(
                    dict(task_by_id.get(result_task_id) or {})
                    or {
                        "task_id": result_task_id,
                        "metric_family": result_row.get("metric_family") or "concept_lookup",
                        "operation_family": "lookup",
                    }
                )
            }
            row_metric_label = _normalise_spaces(str(result_row.get("metric_label") or ""))
            if row_metric_label and not _normalise_spaces(str(producer_task.get("metric_label") or "")):
                producer_task["metric_label"] = row_metric_label
            if not producer_task.get("required_operands"):
                producer_task["required_operands"] = [
                    {
                        "label": producer_task.get("metric_label") or row_metric_label,
                        "role": "primary_value",
                        "period": "",
                    }
                ]
            producer_required_operands = [
                dict(item)
                for item in (producer_task.get("required_operands") or [])
                if isinstance(item, dict) and bool(item.get("required", True))
            ]
            if len(producer_required_operands) == 1 and answer_numeric_slot:
                producer_operand = producer_required_operands[0]
                if not _normalise_spaces(str(answer_numeric_slot.get("concept") or "")):
                    answer_numeric_slot["concept"] = _normalise_spaces(str(producer_operand.get("concept") or ""))
                if not _normalise_spaces(str(answer_numeric_slot.get("period") or "")):
                    answer_numeric_slot["period"] = _normalise_spaces(str(producer_operand.get("period") or ""))
            synthetic_result = _synthesize_lookup_answer_slot_from_prose(
                active_subtask=producer_task,
                answer=answer_text,
                calculation_result=result,
                selected_claim_ids=[
                    str(claim_id).strip()
                    for claim_id in (result_row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
            )
            synthetic_slot_material = False
            if synthetic_result:
                result_slots = dict(synthetic_result.get("answer_slots") or {})
                synthetic_slot = dict(result_slots.get("primary_value") or {})
                if slot_has_material(synthetic_slot):
                    slot = synthetic_slot
                    synthetic_slot_material = True
            synthetic_raw = _normalise_spaces(str(slot.get("raw_value") or ""))
            synthetic_missing_concept = not _normalise_spaces(str(slot.get("concept") or ""))
            answer_numeric_has_concept = bool(_normalise_spaces(str(answer_numeric_slot.get("concept") or "")))
            if answer_numeric_slot and (
                not synthetic_slot_material
                or (synthetic_raw and synthetic_raw not in answer_text)
                or (synthetic_missing_concept and answer_numeric_has_concept)
            ):
                slot = answer_numeric_slot
        if slot_has_material(slot):
            slot = dict(slot)
            slot["source_task_id"] = result_task_id
            if not _clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]):
                slot["source_row_id"] = f"task_output:{result_task_id}"
                slot["source_row_ids"] = [f"task_output:{result_task_id}"]
            slots[result_task_id] = slot
    return slots


def collect_table_label_evidence_candidates(
    ordered_results: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for evidence_source in [
        *(row.get("runtime_evidence") or [] for row in ordered_results if isinstance(row, dict)),
        state.get("evidence_items") or [],
        state.get("runtime_evidence") or [],
    ]:
        for evidence_item in list(evidence_source or []):
            if not isinstance(evidence_item, dict):
                continue
            metadata = dict(evidence_item.get("metadata") or {})
            if not _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
                continue
            evidence_key = _normalise_spaces(
                str(
                    evidence_item.get("evidence_id")
                    or metadata.get("chunk_uid")
                    or evidence_item.get("source_anchor")
                    or len(candidates)
                )
            )
            if evidence_key in seen:
                continue
            seen.add(evidence_key)
            candidates.append(dict(evidence_item))
    return candidates


def _dependency_operand_from_slot(
    operand: Dict[str, Any],
    slot: Dict[str, Any],
    *,
    source_row_ids: List[str],
    evidence_id: Any,
    source_row_id: Any,
    extra_fields: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = {
        **dict(operand),
        "evidence_id": evidence_id,
        "source_row_id": source_row_id,
        "source_row_ids": source_row_ids,
        "normalized_value": slot.get("normalized_value"),
        "normalized_unit": _normalise_spaces(
            str(slot.get("normalized_unit") or operand.get("normalized_unit") or "UNKNOWN")
        ).upper()
        or "UNKNOWN",
        "matched_operand_label": _normalise_spaces(
            str(operand.get("matched_operand_label") or slot.get("label") or "")
        ),
        "matched_operand_concept": _normalise_spaces(
            str(operand.get("matched_operand_concept") or slot.get("concept") or "")
        ),
        "matched_operand_role": _normalise_spaces(
            str(operand.get("matched_operand_role") or operand.get("role") or slot.get("role") or "")
        ),
        "stated_change_raw_value": _normalise_spaces(str(slot.get("stated_change_raw_value") or "")),
        "stated_change_raw_unit": _normalise_spaces(str(slot.get("stated_change_raw_unit") or "")),
    }
    for key in ("source_anchor", "label", "raw_value", "raw_unit", "period"):
        row[key] = _normalise_spaces(str(slot.get(key) or operand.get(key) or ""))
    if extra_fields:
        row.update(extra_fields)
    return row


def dependency_operand_from_source_slot(
    operand: Dict[str, Any],
    slot: Dict[str, Any],
    *,
    source_task_id: str,
) -> Dict[str, Any]:
    source_row_ids = _clean_source_row_ids([
        f"task_output:{source_task_id}",
        slot.get("source_row_id"),
        slot.get("source_row_ids"),
    ])
    task_output_id = f"task_output:{source_task_id}"
    return _dependency_operand_from_slot(
        operand,
        slot,
        source_row_ids=source_row_ids or [task_output_id],
        evidence_id=task_output_id,
        source_row_id=source_row_ids[0] if source_row_ids else task_output_id,
        extra_fields={
            "source_task_id": source_task_id,
            "source_slot": _normalise_spaces(str(operand.get("source_slot") or "primary_value")) or "primary_value",
            "dependency_resolved": True,
        },
    )


def dependency_operand_from_answer_slot(
    operand: Dict[str, Any],
    slot: Dict[str, Any],
) -> Dict[str, Any]:
    source_row_ids = _clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")])
    return _dependency_operand_from_slot(
        operand,
        slot,
        source_row_ids=source_row_ids,
        evidence_id=source_row_ids[0] if source_row_ids else operand.get("evidence_id"),
        source_row_id=source_row_ids[0] if source_row_ids else operand.get("source_row_id"),
    )


def dependency_operand_from_table_label_evidence(
    operand: Dict[str, Any],
    table_label_evidence_candidates: List[Dict[str, Any]],
    *,
    lookup_value_from_table_label_metadata: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    for evidence_item in table_label_evidence_candidates:
        slot = lookup_value_from_table_label_metadata(operand, evidence_item)
        if not slot_has_material(slot):
            continue
        return dependency_operand_from_answer_slot(operand, slot)
    return {}


def dependency_slot_candidates_from_answer_slots(
    answer_slots: Dict[str, Any],
    active_subtask: Dict[str, Any],
    *,
    ratio_role_group: Callable[[str], str],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[tuple[str, Dict[str, Any]]]]:
    required_operands_by_role: Dict[str, Dict[str, Any]] = {}
    required_operands_by_group: Dict[str, Dict[str, Any]] = {}
    for required_operand in list(active_subtask.get("required_operands") or active_subtask.get("inputs") or []):
        if not isinstance(required_operand, dict) or not bool(required_operand.get("required", True)):
            continue
        required_role = _normalise_spaces(str(required_operand.get("role") or ""))
        if required_role:
            required_operands_by_role.setdefault(required_role, dict(required_operand))
        required_group = ratio_role_group(required_role)
        if required_group:
            required_operands_by_group.setdefault(required_group, dict(required_operand))

    slot_candidates: List[tuple[str, Dict[str, Any]]] = []
    for role, slot_key in (
        ("current_period", "current_value"),
        ("prior_period", "prior_value"),
        ("minuend", "minuend"),
        ("subtrahend", "subtrahend"),
    ):
        slot = dict(answer_slots.get(slot_key) or {})
        if slot:
            slot_candidates.append((role, slot))
    components_by_role = dict(answer_slots.get("components_by_role") or {})
    dependency_role_prefixes = (
        "current_period",
        "prior_period",
        "minuend",
        "subtrahend",
        "numerator",
        "denominator",
    )
    for role_key, entries in components_by_role.items():
        role = _normalise_spaces(str(role_key or ""))
        if not role:
            continue
        if role not in dependency_role_prefixes and not any(
            role.startswith(f"{prefix}_") for prefix in dependency_role_prefixes
        ):
            continue
        for slot in list(entries or []):
            if isinstance(slot, dict):
                slot_candidates.append((role, dict(slot)))
    components_by_group = dict(answer_slots.get("components_by_group") or {})
    for group_key, entries in components_by_group.items():
        group = _normalise_spaces(str(group_key or ""))
        if group not in {"numerator", "denominator"}:
            continue
        for slot in list(entries or []):
            if not isinstance(slot, dict):
                continue
            role = _normalise_spaces(str(slot.get("role") or group))
            if not role.startswith(group):
                role = group
            slot_candidates.append((role, dict(slot)))
    return required_operands_by_role, required_operands_by_group, slot_candidates


def derive_dependency_operands_from_source_task_slots(
    row: Dict[str, Any],
    *,
    active_subtask: Dict[str, Any],
    operation_family: str,
    task_id: str,
    lookup_slots_by_task: Dict[str, Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    ratio_role_group: Callable[[str], str],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
) -> List[Dict[str, Any]]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    required_operands_by_role, required_operands_by_group, slot_candidates = (
        dependency_slot_candidates_from_answer_slots(
            answer_slots,
            active_subtask,
            ratio_role_group=ratio_role_group,
        )
    )

    derived: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for role, slot in slot_candidates:
        if not slot_has_material(slot):
            continue
        required_operand = dict(
            required_operands_by_role.get(role)
            or required_operands_by_group.get(ratio_role_group(role))
            or {}
        )
        operand_seed = {
            "operand_id": _normalise_spaces(str(slot.get("operand_id") or role or f"operand_{len(derived) + 1}")),
            "matched_operand_role": role,
            "role": role,
            "label": _normalise_spaces(str(required_operand.get("label") or slot.get("label") or "")),
            "matched_operand_label": _normalise_spaces(
                str(required_operand.get("label") or slot.get("label") or "")
            ),
            "concept": _normalise_spaces(str(required_operand.get("concept") or slot.get("concept") or "")),
            "matched_operand_concept": _normalise_spaces(
                str(required_operand.get("concept") or slot.get("concept") or "")
            ),
            "source_row_id": slot.get("source_row_id"),
            "source_row_ids": slot.get("source_row_ids"),
            "source_task_id": slot.get("source_task_id"),
            "source_slot": slot.get("source_slot") or "primary_value",
        }
        source_task_id = source_task_id_for_operand(operand_seed)
        source_slot = dict(lookup_slots_by_task.get(source_task_id) or {})
        if not source_task_id or not slot_has_material(source_slot):
            excluded_source_task_ids: set[str] = set()
            if operation_family == "ratio":
                role_group = ratio_role_group(role)
                excluded_source_task_ids = {
                    source_task_id_for_operand(derived_operand)
                    for derived_operand in derived
                    if source_task_id_for_operand(derived_operand)
                    and ratio_role_group(
                        _normalise_spaces(
                            str(
                                derived_operand.get("matched_operand_role")
                                or derived_operand.get("role")
                                or ""
                            )
                        )
                    )
                    not in {"", role_group}
                }
            source_task_id, source_slot = lookup_source_for_arithmetic_slot(
                current_task_id=task_id,
                role=role,
                slot=operand_seed,
                excluded_task_ids=excluded_source_task_ids,
            )
        if (
            source_task_id
            and slot_has_material(source_slot)
            and operand_can_use_source_slot(operand_seed, source_slot)
        ):
            derived_operand = operand_from_source_slot(
                operand_seed,
                source_slot,
                source_task_id=source_task_id,
            )
        else:
            continue
        key = "|".join(
            (
                str(derived_operand.get("matched_operand_role") or ""),
                str(derived_operand.get("source_task_id") or ""),
                str(derived_operand.get("raw_value") or ""),
                str(derived_operand.get("raw_unit") or ""),
            )
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        derived.append(derived_operand)
    return derived


def build_fallback_dependency_operation_plan(
    derived_operands: List[Dict[str, Any]],
    *,
    operation_family: str,
    active_subtask: Dict[str, Any],
    calculation_result: Dict[str, Any],
) -> Dict[str, Any]:
    def _operand_for_role_prefix(prefix: str) -> Dict[str, Any]:
        return next(
            (
                operand
                for operand in derived_operands
                if _normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or "")).startswith(prefix)
            ),
            {},
        )

    if operation_family == "ratio":
        numerator = _operand_for_role_prefix("numerator")
        denominator = _operand_for_role_prefix("denominator")
        if not numerator or not denominator:
            return {}
        numerator_id = _normalise_spaces(str(numerator.get("operand_id") or ""))
        denominator_id = _normalise_spaces(str(denominator.get("operand_id") or ""))
        if not numerator_id or not denominator_id:
            return {}
        result_unit = _normalise_spaces(str(calculation_result.get("result_unit") or ""))
        if not result_unit:
            result_unit = "%"
        formula = "((A) / (B)) * 100" if result_unit in {"%", "%p"} else "((A) / (B))"
        numerator_label = _normalise_spaces(str(numerator.get("label") or numerator.get("matched_operand_label") or "A"))
        denominator_label = _normalise_spaces(
            str(denominator.get("label") or denominator.get("matched_operand_label") or "B")
        )
        metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("task_id") or ""))
        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "ratio",
            "ordered_operand_ids": [numerator_id, denominator_id],
            "variable_bindings": [
                {"variable": "A", "operand_id": numerator_id},
                {"variable": "B", "operand_id": denominator_id},
            ],
            "formula": formula,
            "pairwise_formula": "",
            "result_unit": result_unit,
            "operation_text": f"{numerator_label} / {denominator_label}",
            "explanation": f"{metric_label or 'ratio'} is recomputed from stronger dependency task outputs.",
            "missing_info": [],
        }
    if operation_family != "growth_rate":
        return {}
    current = _operand_for_role_prefix("current_period")
    prior = _operand_for_role_prefix("prior_period")
    if not current or not prior:
        return {}
    current_id = _normalise_spaces(str(current.get("operand_id") or ""))
    prior_id = _normalise_spaces(str(prior.get("operand_id") or ""))
    if not current_id or not prior_id:
        return {}
    metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("task_id") or ""))
    current_label = _normalise_spaces(str(current.get("label") or current.get("matched_operand_label") or "A"))
    prior_label = _normalise_spaces(str(prior.get("label") or prior.get("matched_operand_label") or "B"))
    return {
        "status": "ok",
        "mode": "single_value",
        "operation": "growth_rate",
        "ordered_operand_ids": [current_id, prior_id],
        "variable_bindings": [
            {"variable": "A", "operand_id": current_id},
            {"variable": "B", "operand_id": prior_id},
        ],
        "formula": "((A - B) / B) * 100",
        "pairwise_formula": "",
        "result_unit": "%",
        "operation_text": f"({current_label} - {prior_label}) / {prior_label} * 100",
        "explanation": (
            f"{metric_label or 'growth rate'} is computed as ((A - B) / B) * 100 "
            "from dependency task outputs."
        ),
        "missing_info": [],
    }


def dependency_plan_is_executable(plan: Dict[str, Any]) -> bool:
    plan_status = _normalise_spaces(str(plan.get("status") or "")).lower()
    plan_operation = _normalise_spaces(str(plan.get("operation") or "")).lower()
    plan_operand_ids = [
        _normalise_spaces(str(operand_id or ""))
        for operand_id in (plan.get("ordered_operand_ids") or [])
        if _normalise_spaces(str(operand_id or ""))
    ]
    return bool(
        plan
        and plan_status not in {"incomplete", "empty", "missing"}
        and plan_operation not in {"", "none"}
        and plan_operand_ids
    )


def rebuild_dependency_calculation_plan(
    calculation_plan: Dict[str, Any],
    *,
    state: Dict[str, Any],
    active_subtask: Dict[str, Any],
    updated_operands: List[Dict[str, Any]],
    operation_family: str,
    calculation_result: Dict[str, Any],
    build_deterministic_operation_plan: Callable[[Dict[str, Any], List[Dict[str, Any]]], Dict[str, Any]],
) -> Dict[str, Any]:
    if not dependency_plan_is_executable(calculation_plan):
        calculation_plan = {}
    if calculation_plan:
        return calculation_plan
    plan_state = {
        **dict(state),
        "active_subtask": active_subtask,
        "calculation_operands": updated_operands,
        "resolved_calculation_trace": {
            "calculation_operands": updated_operands,
            "calculation_plan": {},
            "calculation_result": {},
        },
    }
    calculation_plan = build_deterministic_operation_plan(plan_state, updated_operands) or {}
    if not dependency_plan_is_executable(calculation_plan):
        calculation_plan = build_fallback_dependency_operation_plan(
            updated_operands,
            operation_family=operation_family,
            active_subtask=active_subtask,
            calculation_result=calculation_result,
        )
    return calculation_plan


def build_dependency_recalculation_state(
    state: Dict[str, Any],
    *,
    active_subtask: Dict[str, Any],
    updated_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    calculation_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        **dict(state),
        "active_subtask": active_subtask,
        "calculation_operands": updated_operands,
        "calculation_plan": calculation_plan,
        "calculation_result": dict(calculation_result),
        "resolved_calculation_trace": {
            "calculation_operands": updated_operands,
            "calculation_plan": calculation_plan,
            "calculation_result": dict(calculation_result),
        },
        "tasks": [],
        "artifacts": [],
    }


def apply_absolute_ratio_magnitude_if_requested(
    calculation_result: Dict[str, Any],
    *,
    format_calculation_value: Callable[[float, str, str], str],
) -> Dict[str, Any]:
    updated = dict(calculation_result)
    try:
        recalculated_value = updated.get("result_value")
        if recalculated_value is None or float(recalculated_value) >= 0:
            return updated
        absolute_value = abs(float(recalculated_value))
        updated["result_value"] = absolute_value
        result_unit = str(updated.get("result_unit") or "%")
        absolute_rendered = format_calculation_value(absolute_value, result_unit, "PERCENT")
        if result_unit in {"%", "%p"} and "%" not in absolute_rendered:
            absolute_rendered = f"{absolute_rendered}{result_unit or '%'}"
        updated["rendered_value"] = absolute_rendered
        recalculated_slots = dict(updated.get("answer_slots") or {})
        recalculated_primary = dict(recalculated_slots.get("primary_value") or {})
        recalculated_primary["normalized_value"] = absolute_value
        recalculated_primary["normalized_unit"] = "PERCENT"
        recalculated_primary["raw_unit"] = recalculated_primary.get("raw_unit") or "%"
        recalculated_primary["rendered_value"] = absolute_rendered
        recalculated_slots["primary_value"] = recalculated_primary
        updated["answer_slots"] = recalculated_slots
    except (TypeError, ValueError):
        return updated
    return updated


def build_dependency_recalculated_row(
    row: Dict[str, Any],
    *,
    recalculated_trace: Dict[str, Any],
    updated_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    recalculated_result: Dict[str, Any],
    formatted_answer: str,
) -> Dict[str, Any]:
    return {
        **dict(row),
        "answer": formatted_answer or str(row.get("answer") or ""),
        "status": "ok",
        "calculation_operands": list(recalculated_trace.get("calculation_operands") or updated_operands),
        "calculation_plan": dict(recalculated_trace.get("calculation_plan") or calculation_plan),
        "calculation_result": recalculated_result,
        "source_row_ids": list(recalculated_result.get("source_row_ids") or row.get("source_row_ids") or []),
        "aligned_from_source_task_slots": True,
    }


def refresh_dependency_operands_from_lookup_slots(
    operands: List[Dict[str, Any]],
    *,
    task_id: str,
    lookup_slots_by_task: Dict[str, Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
    slot_differs_from_operand: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], bool]:
    updated_operands: List[Dict[str, Any]] = []
    changed = False
    for operand in operands:
        source_task_id = source_task_id_for_operand(operand)
        source_slot = dict(lookup_slots_by_task.get(source_task_id) or {})
        if not source_task_id or not slot_has_material(source_slot):
            source_task_id, source_slot = lookup_source_for_arithmetic_slot(
                current_task_id=task_id,
                role=_normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or "")),
                slot=operand,
            )
        if (
            source_task_id
            and slot_has_material(source_slot)
            and slot_differs_from_operand(source_slot, operand)
            and operand_can_use_source_slot(operand, source_slot)
        ):
            updated_operands.append(
                operand_from_source_slot(
                    operand,
                    source_slot,
                    source_task_id=source_task_id,
                )
            )
            changed = True
        else:
            updated_operands.append(operand)
    return updated_operands, changed


def dedupe_dependency_operands_by_id(operands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped_operands: List[Dict[str, Any]] = []
    operand_index_by_id: Dict[str, int] = {}
    for operand in operands:
        operand_id = _normalise_spaces(str(operand.get("operand_id") or ""))
        if not operand_id:
            deduped_operands.append(operand)
            continue
        existing_index = operand_index_by_id.get(operand_id)
        if existing_index is None:
            operand_index_by_id[operand_id] = len(deduped_operands)
            deduped_operands.append(operand)
        else:
            deduped_operands[existing_index] = operand
    return deduped_operands


def _numeric_values_differ(left: Any, right: Any) -> bool:
    try:
        if left is not None and right is not None:
            return abs(float(left) - float(right)) > 1e-6
    except (TypeError, ValueError):
        pass
    return left != right


def fill_missing_ratio_dependency_operands(
    updated_operands: List[Dict[str, Any]],
    *,
    ordered_results: List[Dict[str, Any]],
    active_subtask: Dict[str, Any],
    task_id: str,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
    operand_from_table_label_evidence: Callable[[Dict[str, Any]], Dict[str, Any]],
    operand_rows_share_source_value: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    ratio_role_group: Callable[[str], str],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
) -> tuple[List[Dict[str, Any]], bool]:
    present_groups = {
        ratio_role_group(_normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or "")))
        for operand in updated_operands
    }
    present_groups.discard("")
    required_operands = [
        dict(item)
        for item in (active_subtask.get("required_operands") or active_subtask.get("inputs") or [])
        if bool(item.get("required", True))
    ]
    if "denominator" not in present_groups:
        used_source_task_ids = {
            source_task_id_for_operand(operand)
            for operand in updated_operands
            if source_task_id_for_operand(operand)
        }
        existing_required_groups = {
            ratio_role_group(_normalise_spaces(str(operand.get("role") or "")))
            for operand in required_operands
        }
        if "denominator" not in existing_required_groups:
            for result_row in ordered_results:
                result_task_id = _normalise_spaces(str(result_row.get("task_id") or ""))
                if not result_task_id or result_task_id == task_id or result_task_id in used_source_task_ids:
                    continue
                result_operation = _normalise_spaces(
                    str(result_row.get("operation_family") or operation_family_for_result(result_row) or "")
                ).lower()
                result_metric_family = _normalise_spaces(str(result_row.get("metric_family") or "")).lower()
                if (
                    result_operation not in {"lookup", "single_value"}
                    and result_metric_family not in {"concept_lookup", "generic_numeric"}
                ):
                    continue
                result_label = _normalise_spaces(str(result_row.get("metric_label") or ""))
                if not result_label:
                    continue
                result_slot = dict(
                    (
                        dict(result_row.get("calculation_result") or {}).get("answer_slots")
                        or result_row.get("answer_slots")
                        or {}
                    ).get("primary_value")
                    or {}
                )
                required_operands.append(
                    {
                        "role": "denominator_1",
                        "label": result_label,
                        "concept": _normalise_spaces(str(result_slot.get("concept") or "")),
                        "required": True,
                    }
                )
                break

    changed = False
    for required_operand in required_operands:
        required_role = _normalise_spaces(str(required_operand.get("role") or ""))
        required_group = ratio_role_group(required_role)
        if required_group not in {"numerator", "denominator"} or required_group in present_groups:
            continue
        operand_seed = {
            "operand_id": _normalise_spaces(
                str(required_operand.get("operand_id") or f"{required_role}_{len(updated_operands) + 1}")
            ),
            "matched_operand_role": required_role,
            "role": required_role,
            "label": _normalise_spaces(str(required_operand.get("label") or "")),
            "matched_operand_label": _normalise_spaces(str(required_operand.get("label") or "")),
            "concept": _normalise_spaces(str(required_operand.get("concept") or "")),
            "matched_operand_concept": _normalise_spaces(str(required_operand.get("concept") or "")),
        }
        source_task_id, source_slot = lookup_source_for_arithmetic_slot(
            current_task_id=task_id,
            role=required_role,
            slot=required_operand,
        )
        if source_task_id and slot_has_material(source_slot):
            source_operand_seed = {
                **operand_seed,
                "label": _normalise_spaces(str(required_operand.get("label") or source_slot.get("label") or "")),
                "matched_operand_label": _normalise_spaces(
                    str(required_operand.get("label") or source_slot.get("label") or "")
                ),
                "concept": _normalise_spaces(str(required_operand.get("concept") or source_slot.get("concept") or "")),
                "matched_operand_concept": _normalise_spaces(
                    str(required_operand.get("concept") or source_slot.get("concept") or "")
                ),
            }
            if operand_can_use_source_slot(source_operand_seed, source_slot):
                source_operand = operand_from_source_slot(
                    source_operand_seed,
                    source_slot,
                    source_task_id=source_task_id,
                )
                if not any(
                    operand_rows_share_source_value(source_operand, existing_operand)
                    for existing_operand in updated_operands
                ):
                    updated_operands.append(source_operand)
                    present_groups.add(required_group)
                    changed = True
                    continue
        table_operand = operand_from_table_label_evidence(operand_seed)
        if table_operand and not any(
            operand_rows_share_source_value(table_operand, existing_operand)
            for existing_operand in updated_operands
        ):
            updated_operands.append(table_operand)
            present_groups.add(required_group)
            changed = True
            continue
    return updated_operands, changed


def realign_lookup_row_from_dependency_projection(
    row: Dict[str, Any],
    *,
    task: Dict[str, Any],
    projected_operands: List[Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    projection_operand_matches_lookup: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    slot_differs_from_operand: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    build_operand_value_slot: Callable[..., Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any], bool]:
    task_id = _normalise_spaces(str(row.get("task_id") or ""))
    required_operands = [
        dict(item)
        for item in (task.get("required_operands") or [])
        if bool(item.get("required", True))
    ]
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    current_slot = dict(answer_slots.get("primary_value") or {})
    if len(required_operands) != 1 and current_slot:
        fallback_operand = {
            "label": current_slot.get("label") or row.get("metric_label"),
            "concept": current_slot.get("concept"),
            "role": current_slot.get("role") or "primary_value",
            "required": True,
        }
        if _normalise_spaces(str(fallback_operand.get("label") or fallback_operand.get("concept") or "")):
            required_operands = [fallback_operand]
    if len(required_operands) != 1:
        return row, {}, False
    candidate = next(
        (
            dict(item)
            for item in projected_operands
            if projection_operand_matches_lookup(dict(item), required_operands[0])
        ),
        {},
    )
    if not candidate or not slot_has_material(current_slot):
        return row, {}, False
    candidate_raw = _normalise_spaces(str(candidate.get("raw_value") or ""))
    current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
    if not candidate_raw or not slot_differs_from_operand(candidate, current_slot):
        return row, {}, False

    source_ids = _clean_source_row_ids([candidate.get("source_row_id"), candidate.get("source_row_ids")])
    direct_source_ids = [source_id for source_id in source_ids if not source_id.startswith("task_output:")]
    current_source_ids = _clean_source_row_ids([current_slot.get("source_row_id"), current_slot.get("source_row_ids")])
    direct_current_source_ids = [
        source_id for source_id in current_source_ids if not source_id.startswith("task_output:")
    ]
    self_task_projection = f"task_output:{task_id}" in source_ids
    source_overlap_required = direct_current_source_ids and direct_source_ids
    source_ids_disjoint = source_overlap_required and not (set(direct_current_source_ids) & set(direct_source_ids))
    candidate_anchor = _normalise_spaces(str(candidate.get("source_anchor") or ""))
    current_anchor = _normalise_spaces(str(current_slot.get("source_anchor") or ""))
    source_anchor_conflict = bool(candidate_anchor and current_anchor and candidate_anchor != current_anchor)
    if not self_task_projection and (source_ids_disjoint or source_anchor_conflict):
        return row, {}, False
    if self_task_projection:
        candidate_unit = _normalise_spaces(str(candidate.get("raw_unit") or ""))
        current_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
        evidence_backed_unit_realignment = bool(
            direct_source_ids
            and (not direct_current_source_ids or bool(set(direct_source_ids) & set(direct_current_source_ids)))
            and candidate_unit
            and current_unit
            and candidate_unit != current_unit
        )
        normalized_differs = _numeric_values_differ(candidate.get("normalized_value"), current_slot.get("normalized_value"))
        if candidate_raw == current_raw and normalized_differs and not evidence_backed_unit_realignment:
            return row, {}, False
    component_slot = build_operand_value_slot(
        candidate,
        default_role=str(
            candidate.get("matched_operand_role")
            or required_operands[0].get("role")
            or current_slot.get("role")
            or "primary_value"
        ),
        preserve_source_display=True,
    )
    if direct_source_ids:
        component_slot["source_row_id"] = direct_source_ids[0]
        component_slot["source_row_ids"] = direct_source_ids
    primary_slot = {**component_slot, "role": "primary_value"}

    rendered_value = _normalise_spaces(str(primary_slot.get("rendered_value") or ""))
    if not rendered_value:
        rendered_value = _normalise_spaces(f"{primary_slot.get('raw_value') or ''}{primary_slot.get('raw_unit') or ''}")
    result_source_ids = list(primary_slot.get("source_row_ids") or source_ids)
    updated_slots = dict(answer_slots)
    updated_slots["primary_value"] = primary_slot
    updated_slots["source_row_ids"] = result_source_ids
    role_key = _normalise_spaces(str(component_slot.get("role") or ""))
    if role_key:
        components_by_role = dict(updated_slots.get("components_by_role") or {})
        components_by_role[role_key] = [component_slot]
        updated_slots["components_by_role"] = components_by_role
        group_key = "denominator" if role_key.startswith("denominator") else "numerator"
        components_by_group = dict(updated_slots.get("components_by_group") or {})
        components_by_group[group_key] = [component_slot]
        updated_slots["components_by_group"] = components_by_group

    updated_result = {
        **calculation_result,
        "status": "ok",
        "result_value": primary_slot.get("normalized_value"),
        "result_unit": primary_slot.get("raw_unit") or calculation_result.get("result_unit"),
        "rendered_value": rendered_value,
        "formatted_result": rendered_value,
        "series": [
            {
                "label": primary_slot.get("label"),
                "period": primary_slot.get("period"),
                "raw_value": primary_slot.get("raw_value"),
                "raw_unit": primary_slot.get("raw_unit"),
                "normalized_value": primary_slot.get("normalized_value"),
                "normalized_unit": primary_slot.get("normalized_unit"),
                "rendered_value": rendered_value,
            }
        ],
        "current_value": primary_slot.get("normalized_value"),
        "current_period": primary_slot.get("period") or calculation_result.get("current_period"),
        "source_row_ids": result_source_ids,
        "answer_slots": updated_slots,
    }
    return (
        {
            **dict(row),
            "answer": rendered_value,
            "calculation_result": updated_result,
            "answer_slots": updated_slots,
            "aligned_from_dependency_projection": True,
        },
        primary_slot,
        True,
    )


def replace_lookup_primary_slot(
    row: Dict[str, Any],
    updated_primary: Dict[str, Any],
    *,
    marker_key: str,
    component_source_ids: set[str] | None = None,
) -> Dict[str, Any]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    updated_slots = dict(answer_slots)
    updated_slots["primary_value"] = updated_primary
    raw_value = _normalise_spaces(str(updated_primary.get("raw_value") or ""))
    raw_unit = _normalise_spaces(str(updated_primary.get("raw_unit") or ""))
    normalized_value = updated_primary.get("normalized_value")
    normalized_unit = _normalise_spaces(str(updated_primary.get("normalized_unit") or ""))
    rendered_value = _normalise_spaces(str(updated_primary.get("rendered_value") or f"{raw_value}{raw_unit}"))
    if component_source_ids:
        for container_key in ("components_by_role", "components_by_group"):
            container = dict(updated_slots.get(container_key) or {})
            if not container:
                continue
            updated_slots[container_key] = {
                key: [
                    {
                        **dict(item),
                        "raw_unit": raw_unit,
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "rendered_value": rendered_value,
                        marker_key: True,
                    }
                    if isinstance(item, dict)
                    and _normalise_spaces(str(item.get("raw_value") or "")) == raw_value
                    and (
                        not component_source_ids
                        or set(_clean_source_row_ids([item.get("source_row_id"), item.get("source_row_ids")]))
                        & component_source_ids
                    )
                    else item
                    for item in list(entries or [])
                ]
                for key, entries in container.items()
            }
    label = _normalise_spaces(str(updated_primary.get("label") or row.get("metric_label") or ""))
    updated_result = {
        **calculation_result,
        "result_value": normalized_value,
        "result_unit": raw_unit or normalized_unit,
        "rendered_value": rendered_value,
        "formatted_result": _normalise_spaces(f"{label} {rendered_value}") if label and rendered_value else rendered_value,
        "answer_slots": updated_slots,
    }
    return {
        **dict(row),
        "answer": str(updated_result.get("formatted_result") or rendered_value),
        "calculation_result": updated_result,
        "answer_slots": updated_slots,
        marker_key: True,
    }


def lookup_primary_slot(row: Dict[str, Any]) -> Dict[str, Any]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    return dict(answer_slots.get("primary_value") or {})


def align_lookup_result_units_from_peer_source_slots(
    ordered_results: List[Dict[str, Any]],
    *,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> List[Dict[str, Any]]:
    render_policy = dict(CALCULATION_RENDER_POLICY)
    krw_units = {
        _normalise_spaces(str(item))
        for item in (render_policy.get("krw_display_units") or ())
        if _normalise_spaces(str(item))
    }

    def _source_keys(slot: Dict[str, Any]) -> set[str]:
        source_ids = set(_clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]))
        source_anchor = _normalise_spaces(str(slot.get("source_anchor") or ""))
        if source_anchor:
            source_ids.add(f"anchor::{source_anchor}")
        return source_ids

    peer_slots = [
        lookup_primary_slot(row)
        for row in ordered_results
        if isinstance(row, dict)
        and operation_family_for_result(row) in {"lookup", "single_value"}
        and slot_has_material(lookup_primary_slot(row))
    ]

    def _peer_unit_for(slot: Dict[str, Any]) -> str:
        raw_value = _normalise_spaces(str(slot.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
        if (
            not raw_value
            or not raw_unit
            or raw_unit not in krw_units
            or normalized_unit != "KRW"
            or not re.fullmatch(str(render_policy.get("operand_unit_bare_numeric_pattern") or r"$^"), raw_value)
        ):
            return ""
        keys = _source_keys(slot)
        if not keys:
            return ""
        concept = _normalise_spaces(str(slot.get("concept") or ""))
        candidates: List[str] = []
        for peer in peer_slots:
            if peer is slot:
                continue
            peer_unit = _normalise_spaces(str(peer.get("raw_unit") or ""))
            if not peer_unit or peer_unit == raw_unit or peer_unit not in krw_units:
                continue
            if _normalise_spaces(str(peer.get("normalized_unit") or "")).upper() != normalized_unit:
                continue
            peer_concept = _normalise_spaces(str(peer.get("concept") or ""))
            if concept and peer_concept and concept != peer_concept:
                continue
            if _source_keys(peer) & keys:
                candidates.append(peer_unit)
        if not candidates:
            return ""
        counts = {unit: candidates.count(unit) for unit in set(candidates)}
        best_count = max(counts.values())
        best_units = [unit for unit, count in counts.items() if count == best_count]
        if len(best_units) != 1:
            return ""
        peer_value, _peer_unit = _normalise_operand_value(raw_value, best_units[0])
        try:
            if abs(float(peer_value)) <= abs(float(slot.get("normalized_value"))):
                return ""
        except (TypeError, ValueError):
            return ""
        return best_units[0]

    aligned_results: List[Dict[str, Any]] = []
    changed_any = False
    for row in ordered_results:
        if not isinstance(row, dict) or operation_family_for_result(row) not in {"lookup", "single_value"}:
            aligned_results.append(row)
            continue
        primary_slot = lookup_primary_slot(row)
        peer_unit = _peer_unit_for(primary_slot)
        if not peer_unit:
            aligned_results.append(row)
            continue
        raw_value = _normalise_spaces(str(primary_slot.get("raw_value") or ""))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, peer_unit)
        if normalized_value is None:
            aligned_results.append(row)
            continue
        aligned_results.append(
            replace_lookup_primary_slot(
                row,
                {
                    **primary_slot,
                    "raw_unit": peer_unit,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "rendered_value": f"{raw_value}{peer_unit}",
                    "unit_aligned_from_peer_source_slot": True,
                },
                marker_key="unit_aligned_from_peer_source_slot",
            )
        )
        changed_any = True
    return aligned_results if changed_any else ordered_results
