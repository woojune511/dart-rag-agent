"""Answer slot construction helpers for calculation traces."""

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Mapping, Optional

from src.agent.financial_graph_calculation_rendering import (
    format_calculation_value_in_display_unit,
    format_ratio_percent_result,
    render_grounded_operand_display,
    render_value_with_unit,
)
from src.agent.financial_numeric_surface import (
    extract_numeric_surface_candidates,
    numeric_surface_candidates_equivalent,
)
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    display_operand_label,
    _normalise_spaces,
)
from src.config.retrieval_policy import (
    CALCULATION_RENDER_POLICY,
    CALCULATION_SLOT_POLICY,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
)


def answer_slot_has_material(slot: Dict[str, Any]) -> bool:
    if not isinstance(slot, dict) or not slot:
        return False
    status = str(slot.get("status") or "").strip().lower()
    if status == "missing":
        return False
    if slot.get("normalized_value") is not None:
        return True
    return bool(str(slot.get("rendered_value") or slot.get("raw_value") or "").strip())


def answer_slot_period_hint(slot: Dict[str, Any]) -> str:
    period = _normalise_spaces(str(slot.get("period") or ""))
    if period:
        return period
    label = _normalise_spaces(str(slot.get("label") or ""))
    period_pattern = str(CALCULATION_SLOT_POLICY.get("period_pattern") or "")
    if period_pattern:
        match = re.search(period_pattern, label)
        if match:
            return _normalise_spaces(match.group(0))
    return ""


def period_match_key(value: str) -> str:
    return re.sub(r"\D", "", _normalise_spaces(str(value or "")))


def ratio_component_consolidation_scope(
    calculation_result: Dict[str, Any],
    operands: Optional[List[Dict[str, Any]]] = None,
) -> str:
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    scopes: List[str] = []
    for entries in dict(answer_slots.get("components_by_group") or {}).values():
        for entry in entries or []:
            scope = _normalise_spaces(str((entry or {}).get("consolidation_scope") or ""))
            if scope in {"consolidated", "separate"} and scope not in scopes:
                scopes.append(scope)
    for operand in operands or []:
        scope = _normalise_spaces(str((operand or {}).get("consolidation_scope") or ""))
        if scope in {"consolidated", "separate"} and scope not in scopes:
            scopes.append(scope)
    return scopes[0] if len(scopes) == 1 else ""


def ratio_components_collapse_to_same_slot(calculation_result: Dict[str, Any]) -> bool:
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    components_by_group = dict(answer_slots.get("components_by_group") or {})
    numerator_slots = [dict(item) for item in list(components_by_group.get("numerator") or []) if isinstance(item, dict)]
    denominator_slots = [
        dict(item) for item in list(components_by_group.get("denominator") or []) if isinstance(item, dict)
    ]

    def _slot_identity(slot: Dict[str, Any]) -> tuple[str, str, str, str, str]:
        source_ids = "|".join(_clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]))
        normalized_value = slot.get("normalized_value")
        try:
            normalized_text = f"{float(normalized_value):.6f}" if normalized_value is not None else ""
        except (TypeError, ValueError):
            normalized_text = _normalise_spaces(str(normalized_value or ""))
        return (
            _normalise_spaces(str(slot.get("label") or "")),
            _normalise_spaces(str(slot.get("raw_value") or "")),
            _normalise_spaces(str(slot.get("raw_unit") or "")),
            normalized_text,
            source_ids,
        )

    if numerator_slots and denominator_slots:
        numerator_identities = {_slot_identity(slot) for slot in numerator_slots if answer_slot_has_material(slot)}
        denominator_identities = {_slot_identity(slot) for slot in denominator_slots if answer_slot_has_material(slot)}
        if numerator_identities and numerator_identities == denominator_identities:
            return True
        numerator_value_identities = {identity[1:] for identity in numerator_identities if identity[-1]}
        denominator_value_identities = {identity[1:] for identity in denominator_identities if identity[-1]}
        if numerator_value_identities and numerator_value_identities & denominator_value_identities:
            return True
    return False


def ratio_components_are_complete(calculation_result: Dict[str, Any]) -> bool:
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    components_by_group = dict(answer_slots.get("components_by_group") or {})
    numerator_slots = [dict(item) for item in list(components_by_group.get("numerator") or []) if isinstance(item, dict)]
    denominator_slots = [
        dict(item) for item in list(components_by_group.get("denominator") or []) if isinstance(item, dict)
    ]

    def _slot_has_value(slot: Dict[str, Any]) -> bool:
        return bool(
            _normalise_spaces(
                str(slot.get("rendered_value") or slot.get("raw_value") or slot.get("normalized_value") or "")
            )
        )

    if ratio_components_collapse_to_same_slot(calculation_result):
        return False

    return any(_slot_has_value(slot) for slot in numerator_slots) and any(
        _slot_has_value(slot) for slot in denominator_slots
    )


def source_task_display_compatible_with_slot(
    slot: Mapping[str, Any],
    source_display: str,
) -> bool:
    display = _normalise_spaces(str(source_display or ""))
    if not display:
        return False
    slot_display = _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))
    if slot_display and display == slot_display:
        return True
    source_row_id = _normalise_spaces(str(slot.get("source_row_id") or ""))
    if source_row_id.startswith("task_output:"):
        return True
    raw_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
    if not raw_unit:
        return True
    if raw_unit in display:
        return True
    normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
    krw_normalized_unit = str(CALCULATION_RENDER_POLICY.get("krw_normalized_unit") or "").upper()
    if normalized_unit == krw_normalized_unit:
        krw_display_units = tuple(
            str(item)
            for item in (CALCULATION_RENDER_POLICY.get("krw_display_units") or ())
            if str(item)
        )
        if any(unit in display for unit in krw_display_units):
            return False
    return True


@dataclass(frozen=True)
class RatioResultDisplaySyncInput:
    """Prepared ratio calculation result whose display may need synchronization."""

    calculation_result: Dict[str, Any]


@dataclass(frozen=True)
class RatioResultDisplaySyncResult:
    """The original or copied calculation result after display synchronization."""

    calculation_result: Dict[str, Any]


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


def synchronize_ratio_result_display(
    sync_input: RatioResultDisplaySyncInput,
) -> RatioResultDisplaySyncResult:
    """Synchronize a ratio result and its primary answer-slot display."""

    calculation_result = sync_input.calculation_result
    if _normalise_spaces(str(calculation_result.get("status") or "")).lower() != "ok":
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    if _normalise_spaces(str(calculation_result.get("operation_family") or "")).lower() not in {"", "ratio"}:
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    derived_metrics = dict(calculation_result.get("derived_metrics") or {})
    if derived_metrics.get("source_stated_result_used"):
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    result_value = calculation_result.get("result_value")
    formula_result_value = coerce_slot_numeric(
        derived_metrics.get("formula_result_value")
    )
    result_numeric_value = coerce_slot_numeric(result_value)
    if formula_result_value is not None and result_numeric_value is not None:
        tolerance = max(abs(float(formula_result_value)), abs(float(result_numeric_value)), 1.0) * 1e-6
        if abs(float(formula_result_value) - float(result_numeric_value)) > tolerance:
            calculation_result = dict(calculation_result)
            calculation_result["result_value"] = float(formula_result_value)
            derived_metrics["result_value_synced_from_formula_trace"] = True
            calculation_result["derived_metrics"] = derived_metrics
            result_value = formula_result_value
    try:
        result_float = float(result_value)
    except (TypeError, ValueError):
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    result_unit = _normalise_spaces(str(calculation_result.get("result_unit") or ""))
    percent_units = {
        _normalise_spaces(str(unit))
        for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())
        if _normalise_spaces(str(unit))
    }
    if result_unit not in percent_units:
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    target_rendered = format_ratio_percent_result(result_float)
    target_candidates = extract_numeric_surface_candidates(target_rendered)
    target_candidate = next(
        (candidate for candidate in target_candidates if str(candidate.get("kind") or "") == "percent"),
        {},
    )
    if not target_candidate:
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    current_surface = _normalise_spaces(
        str(
            (dict(calculation_result.get("answer_slots") or {}).get("primary_value") or {}).get("rendered_value")
            or calculation_result.get("rendered_value")
            or calculation_result.get("formatted_result")
            or ""
        )
    )
    current_candidates = [
        candidate
        for candidate in extract_numeric_surface_candidates(current_surface)
        if str(candidate.get("kind") or "") == "percent"
    ]
    if current_candidates and any(
        numeric_surface_candidates_equivalent(candidate, target_candidate)
        for candidate in current_candidates
    ):
        return RatioResultDisplaySyncResult(calculation_result=calculation_result)
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    primary_value = dict(answer_slots.get("primary_value") or {})
    primary_value.update(
        {
            "status": primary_value.get("status") or "ok",
            "raw_value": target_rendered,
            "raw_unit": "%",
            "normalized_value": result_float,
            "normalized_unit": "PERCENT",
            "rendered_value": target_rendered,
        }
    )
    answer_slots["primary_value"] = primary_value
    calculation_result.update(
        {
            "rendered_value": target_rendered,
            "answer_slots": answer_slots,
            "ratio_display_synced_from_result_value": True,
        }
    )
    return RatioResultDisplaySyncResult(calculation_result=calculation_result)


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
        "label": display_operand_label(str(row.get("label") or row.get("matched_operand_label") or "")),
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
        "label": display_operand_label(label),
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
