"""Answer slot construction helpers for calculation traces."""

from typing import Any, Dict, List, Optional

from src.agent.financial_graph_calculation_rendering import (
    adjusted_difference_source_display_unit,
    format_calculation_value_in_display_unit,
    render_grounded_operand_display,
    render_value_with_unit,
)
from src.agent.financial_graph_model_loaders import _validate_answer_slots_payload
from src.agent.financial_runtime_normalization import _clean_source_row_ids, _display_operand_label
from src.config.retrieval_policy import CALCULATION_RENDER_POLICY


def slot_status(
    *,
    normalized_value: Optional[float],
    rendered_value: str,
    raw_value: str,
) -> str:
    if normalized_value is not None:
        return "ok"
    if str(rendered_value or raw_value or "").strip():
        return "derived"
    return "missing"


def coerce_slot_numeric(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_missing_value_slot(
    *,
    role: str,
    label: str,
    concept: str = "",
    period: str = "",
    raw_unit: str = "",
    normalized_unit: str = "UNKNOWN",
    source_row_ids: Optional[List[str]] = None,
    source_anchor: str = "",
) -> Dict[str, Any]:
    row_ids = _clean_source_row_ids(source_row_ids or [])
    return {
        "status": "missing",
        "role": role,
        "label": _display_operand_label(label),
        "concept": concept,
        "period": str(period or ""),
        "raw_value": "",
        "raw_unit": str(raw_unit or ""),
        "normalized_value": None,
        "normalized_unit": str(normalized_unit or "UNKNOWN"),
        "rendered_value": "",
        "source_row_id": row_ids[0] if row_ids else "",
        "source_row_ids": row_ids,
        "source_anchor": str(source_anchor or ""),
    }


def build_operand_value_slot(
    row: Dict[str, Any],
    *,
    default_role: str = "operand",
    preserve_source_display: bool = False,
) -> Dict[str, Any]:
    raw_unit = str(row.get("raw_unit") or row.get("result_unit") or "")
    normalized_unit = str(row.get("normalized_unit") or "")
    normalized_value = row.get("normalized_value")
    rendered_value = render_grounded_operand_display(row) if preserve_source_display else ""
    if normalized_value is not None:
        try:
            if not rendered_value:
                rendered_value = render_value_with_unit(float(normalized_value), raw_unit, normalized_unit)
        except (TypeError, ValueError):
            rendered_value = str(row.get("raw_value") or "")
    source_row_ids = _clean_source_row_ids([
        row.get("evidence_id"),
        row.get("row_id"),
        row.get("source_row_id"),
        row.get("source_row_ids"),
    ])
    return {
        "status": slot_status(
            normalized_value=coerce_slot_numeric(normalized_value),
            rendered_value=rendered_value,
            raw_value=str(row.get("raw_value") or ""),
        ),
        "role": str(row.get("matched_operand_role") or default_role),
        "label": _display_operand_label(str(row.get("label") or row.get("matched_operand_label") or "")),
        "concept": str(row.get("matched_operand_concept") or ""),
        "period": str(row.get("period") or ""),
        "raw_value": str(row.get("raw_value") or ""),
        "raw_unit": raw_unit,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "rendered_value": rendered_value,
        "source_row_id": source_row_ids[0] if source_row_ids else "",
        "source_row_ids": source_row_ids,
        "source_anchor": str(row.get("source_anchor") or ""),
        "consolidation_scope": str(row.get("consolidation_scope") or ""),
        "statement_type": str(row.get("statement_type") or ""),
        "table_source_id": str(row.get("table_source_id") or ""),
        "value_role": str(row.get("value_role") or ""),
        "aggregation_stage": str(row.get("aggregation_stage") or ""),
        "aggregate_label": str(row.get("aggregate_label") or ""),
        "stated_change_raw_value": str(row.get("stated_change_raw_value") or ""),
        "stated_change_raw_unit": str(row.get("stated_change_raw_unit") or ""),
    }


def build_calculated_value_slot(
    *,
    label: str,
    normalized_value: Optional[float],
    normalized_unit: str,
    display_unit: str,
    period: str = "",
    source_row_ids: Optional[List[str]] = None,
    role: str = "primary_value",
    source_anchor: str = "",
) -> Dict[str, Any]:
    rendered_value = ""
    if normalized_value is not None:
        krw_normalized_unit = str(CALCULATION_RENDER_POLICY.get("krw_normalized_unit") or "").upper()
        krw_display_unit_scales = dict(CALCULATION_RENDER_POLICY.get("krw_display_unit_scales") or {})
        if str(normalized_unit or "").upper() == krw_normalized_unit and display_unit in krw_display_unit_scales:
            rendered_value = format_calculation_value_in_display_unit(float(normalized_value), display_unit)
        else:
            rendered_value = render_value_with_unit(float(normalized_value), display_unit, normalized_unit)
    row_ids = _clean_source_row_ids(source_row_ids or [])
    return {
        "status": slot_status(
            normalized_value=coerce_slot_numeric(normalized_value),
            rendered_value=rendered_value,
            raw_value="",
        ),
        "role": role,
        "label": _display_operand_label(label),
        "concept": "",
        "period": str(period or ""),
        "raw_value": "",
        "raw_unit": str(display_unit or ""),
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "rendered_value": rendered_value,
        "source_row_id": row_ids[0] if row_ids else "",
        "source_row_ids": row_ids,
        "source_anchor": str(source_anchor or ""),
    }


def _seed_for_roles(
    *,
    required_operands: List[Dict[str, Any]],
    ordered_operands: List[Dict[str, Any]],
    roles: tuple[str, ...],
) -> Dict[str, Any]:
    role_set = {str(role).strip().lower() for role in roles if str(role).strip()}
    for requirement in required_operands:
        req_role = str(requirement.get("role") or "").strip().lower()
        if req_role and req_role in role_set:
            return requirement
    for row in ordered_operands:
        row_role = str(row.get("matched_operand_role") or "").strip().lower()
        if row_role and row_role in role_set:
            return row
    return {}


def _build_operand_component_maps(
    *,
    family: str,
    active_subtask: Dict[str, Any],
    ordered_operands: List[Dict[str, Any]],
) -> tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]]]:
    components_by_role: Dict[str, List[Dict[str, Any]]] = {}
    components_by_group: Dict[str, List[Dict[str, Any]]] = {}
    preserve_difference_source_display = bool(
        family == "difference"
        and adjusted_difference_source_display_unit(
            active_subtask=active_subtask,
            ordered_operands=ordered_operands,
        )
    )
    for row in ordered_operands:
        row_normalized_unit = str(row.get("normalized_unit") or "").strip().upper()
        preserve_ratio_source_display = family == "ratio"
        preserve_growth_source_display = family == "growth_rate" and row_normalized_unit not in {"", "KRW"}
        slot = build_operand_value_slot(
            row,
            preserve_source_display=(
                family in {"lookup", "single_value"}
                or preserve_ratio_source_display
                or preserve_difference_source_display
                or preserve_growth_source_display
            ),
        )
        role = str(slot.get("role") or "operand")
        components_by_role.setdefault(role, []).append(slot)
        role_group = role.split("_", 1)[0] if "_" in role else role
        components_by_group.setdefault(role_group, []).append(slot)
    return components_by_role, components_by_group


def _build_lookup_primary_slot(
    *,
    ordered_operands: List[Dict[str, Any]],
    seed: Dict[str, Any],
    metric_label: str,
    result_unit: str,
    source_normalized_unit: str,
    current_period: str,
) -> Dict[str, Any]:
    if ordered_operands:
        primary_slot = build_operand_value_slot(
            ordered_operands[0],
            default_role="primary_value",
            preserve_source_display=True,
        )
        primary_slot["role"] = "primary_value"
        return primary_slot
    return build_missing_value_slot(
        role="primary_value",
        label=str(seed.get("label") or metric_label),
        concept=str(seed.get("concept") or seed.get("matched_operand_concept") or ""),
        period=str(seed.get("period") or seed.get("period_hint") or current_period or ""),
        raw_unit=str(seed.get("raw_unit") or result_unit or ""),
        normalized_unit=str(seed.get("normalized_unit") or source_normalized_unit or "UNKNOWN"),
        source_anchor=str(seed.get("source_anchor") or ""),
    )


def _build_period_value_slot(
    *,
    row: Optional[Dict[str, Any]],
    seed: Dict[str, Any],
    value: Optional[float],
    metric_label: str,
    normalized_unit: str,
    display_unit: str,
    period: str,
    source_row_ids: List[str],
    role: str,
) -> Dict[str, Any]:
    if row:
        preserve_display = str(row.get("normalized_unit") or "").strip().upper() != "KRW"
        slot = build_operand_value_slot(
            row,
            default_role=role,
            preserve_source_display=preserve_display,
        )
        slot["role"] = role
        return slot
    if value is not None:
        return build_calculated_value_slot(
            label=str(seed.get("label") or metric_label),
            normalized_value=value,
            normalized_unit=normalized_unit,
            display_unit="",
            period=period,
            source_row_ids=source_row_ids,
            role=role,
            source_anchor=str(seed.get("source_anchor") or ""),
        )
    return build_missing_value_slot(
        role=role,
        label=str(seed.get("label") or metric_label),
        concept=str(seed.get("concept") or seed.get("matched_operand_concept") or ""),
        period=str(seed.get("period") or seed.get("period_hint") or period or ""),
        raw_unit=str(seed.get("raw_unit") or display_unit or ""),
        normalized_unit=str(seed.get("normalized_unit") or normalized_unit or "UNKNOWN"),
        source_anchor=str(seed.get("source_anchor") or ""),
    )


def _period_comparison_requested(
    *,
    family: str,
    required_operands: List[Dict[str, Any]],
    ordered_operands: List[Dict[str, Any]],
) -> bool:
    operand_roles = {
        str(spec.get("role") or "").strip()
        for spec in required_operands
        if str(spec.get("role") or "").strip()
    }
    row_roles = {
        str(row.get("matched_operand_role") or "").strip()
        for row in ordered_operands
        if str(row.get("matched_operand_role") or "").strip()
    }
    return bool(family in {"difference", "growth_rate"} and {"current_period", "prior_period"} & (operand_roles | row_roles))


def _difference_direction(
    *,
    current_value: Optional[float],
    prior_value: Optional[float],
    delta_value: Optional[float],
) -> Optional[str]:
    if current_value is None or prior_value is None:
        return None
    if delta_value > 0:
        return "increase"
    if delta_value < 0:
        return "decrease"
    return "flat"


def _add_period_comparison_answer_slots(
    answer_slots: Dict[str, Any],
    *,
    family: str,
    required_operands: List[Dict[str, Any]],
    ordered_operands: List[Dict[str, Any]],
    metric_label: str,
    current_value: Optional[float],
    prior_value: Optional[float],
    delta_value: Optional[float],
    normalized_unit: str,
    source_normalized_unit: str,
    result_unit: str,
    current_period: str,
    prior_period: str,
    source_row_ids: List[str],
    current_row: Optional[Dict[str, Any]],
    prior_row: Optional[Dict[str, Any]],
) -> None:
    if family not in {"difference", "growth_rate"}:
        return
    current_seed = current_row or _seed_for_roles(
        required_operands=required_operands,
        ordered_operands=ordered_operands,
        roles=("current_period",),
    )
    answer_slots["current_value"] = _build_period_value_slot(
        row=current_row,
        seed=current_seed,
        value=current_value,
        metric_label=metric_label,
        normalized_unit=source_normalized_unit or normalized_unit,
        display_unit=result_unit,
        period=current_period,
        source_row_ids=source_row_ids[:1],
        role="current_value",
    )

    prior_seed = prior_row or _seed_for_roles(
        required_operands=required_operands,
        ordered_operands=ordered_operands,
        roles=("prior_period",),
    )
    answer_slots["prior_value"] = _build_period_value_slot(
        row=prior_row,
        seed=prior_seed,
        value=prior_value,
        metric_label=metric_label,
        normalized_unit=source_normalized_unit or normalized_unit,
        display_unit=result_unit,
        period=prior_period,
        source_row_ids=source_row_ids[1:2],
        role="prior_value",
    )

    if family != "difference":
        return
    answer_slots["delta_value"] = build_calculated_value_slot(
        label=metric_label,
        normalized_value=delta_value,
        normalized_unit=normalized_unit,
        display_unit=result_unit,
        period=current_period,
        source_row_ids=source_row_ids,
        role="delta_value",
    )
    answer_slots["direction"] = _difference_direction(
        current_value=current_value,
        prior_value=prior_value,
        delta_value=delta_value,
    )


def build_answer_slots(
    *,
    active_subtask: Dict[str, Any],
    operation_family: str,
    ordered_operands: List[Dict[str, Any]],
    result_value: Optional[float],
    result_unit: str,
    normalized_unit: str,
    source_normalized_unit: str,
    current_value: Optional[float],
    prior_value: Optional[float],
    delta_value: Optional[float],
    current_period: str,
    prior_period: str,
    source_row_ids: List[str],
    current_row: Optional[Dict[str, Any]] = None,
    prior_row: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    family = str(
        operation_family or active_subtask.get("operation_family") or "single_value"
    ).strip().lower()
    metric_label = str(
        active_subtask.get("metric_label")
        or active_subtask.get("query")
        or active_subtask.get("task_id")
        or ""
    )
    required_operands = [dict(item) for item in (active_subtask.get("required_operands") or [])]

    components_by_role, components_by_group = _build_operand_component_maps(
        family=family,
        active_subtask=active_subtask,
        ordered_operands=ordered_operands,
    )

    answer_slots: Dict[str, Any] = {
        "operation_family": family,
        "metric_label": metric_label,
        "components_by_role": components_by_role,
        "components_by_group": components_by_group,
        "source_row_ids": list(source_row_ids or []),
    }

    if family in {"lookup", "single_value"}:
        seed = _seed_for_roles(
            required_operands=required_operands,
            ordered_operands=ordered_operands,
            roles=("operand", "current_period", "primary_value"),
        )
        answer_slots["primary_value"] = _build_lookup_primary_slot(
            ordered_operands=ordered_operands,
            seed=seed,
            metric_label=metric_label,
            result_unit=result_unit,
            source_normalized_unit=source_normalized_unit,
            current_period=current_period,
        )
        return _validate_answer_slots_payload(answer_slots)

    period_difference = _period_comparison_requested(
        family=family,
        required_operands=required_operands,
        ordered_operands=ordered_operands,
    )

    primary_role = "delta_value" if family == "difference" and period_difference else "primary_value"
    answer_slots["primary_value"] = build_calculated_value_slot(
        label=metric_label,
        normalized_value=result_value,
        normalized_unit=normalized_unit,
        display_unit=result_unit,
        period=current_period,
        source_row_ids=source_row_ids,
        role=primary_role,
    )

    _add_period_comparison_answer_slots(
        answer_slots,
        family=family,
        required_operands=required_operands,
        ordered_operands=ordered_operands,
        metric_label=metric_label,
        current_value=current_value,
        prior_value=prior_value,
        delta_value=delta_value,
        normalized_unit=normalized_unit,
        source_normalized_unit=source_normalized_unit,
        result_unit=result_unit,
        current_period=current_period,
        prior_period=prior_period,
        source_row_ids=source_row_ids,
        current_row=current_row,
        prior_row=prior_row,
    )

    return _validate_answer_slots_payload(answer_slots)
