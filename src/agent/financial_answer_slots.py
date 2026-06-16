"""Answer slot construction helpers for calculation traces."""

from typing import Any, Dict, List, Optional

from src.agent.financial_graph_helpers import _clean_source_row_ids, _display_operand_label
from src.agent.financial_graph_calculation_rendering import (
    format_calculation_value_in_display_unit,
    render_grounded_operand_display,
    render_value_with_unit,
)
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
