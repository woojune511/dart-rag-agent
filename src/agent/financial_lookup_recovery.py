"""Lookup-result recovery helpers for structured numeric subtasks."""

import re
from typing import Any, Callable, Dict, List, Optional

from src.agent.financial_graph_helpers import (
    _normalise_operand_value,
    _normalise_spaces,
    _operand_text_match,
)


def lookup_recovery_digit_count(value: Any) -> int:
    return len(re.findall(r"\d", str(value or "")))


def compact_lookup_cell_value(value: Any) -> str:
    return re.sub(r"[,\s()]", "", str(value or ""))


def preferred_slot_value_matches_selected_evidence(
    preferred_slot: Dict[str, Any],
    preferred_evidence: Optional[Dict[str, Any]],
) -> Optional[bool]:
    raw_value = compact_lookup_cell_value(preferred_slot.get("raw_value") or preferred_slot.get("rendered_value"))
    if not raw_value or not preferred_evidence:
        return None
    metadata = dict(preferred_evidence.get("metadata") or {})
    selected_headers = {
        _normalise_spaces(str(header)).lower()
        for header in (metadata.get("column_headers_chain") or [])
        if _normalise_spaces(str(header))
    }
    matching_cells: List[Dict[str, Any]] = []
    for cell in list(metadata.get("structured_cells") or []):
        cell_data = dict(cell or {})
        if compact_lookup_cell_value(cell_data.get("value_text")) == raw_value:
            matching_cells.append(cell_data)
    if matching_cells:
        if not selected_headers:
            return True
        for cell_data in matching_cells:
            cell_headers = {
                _normalise_spaces(str(header)).lower()
                for header in (cell_data.get("column_headers") or [])
                if _normalise_spaces(str(header))
            }
            if not cell_headers or selected_headers.intersection(cell_headers):
                return True
        return False
    local_surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                preferred_evidence.get("claim"),
                preferred_evidence.get("quote_span"),
                preferred_evidence.get("raw_row_text"),
                preferred_evidence.get("source_context"),
                metadata.get("row_text"),
            )
        )
    )
    if local_surface:
        return raw_value in compact_lookup_cell_value(local_surface)
    return None


def recovered_slot_has_primary_label_match(
    slot: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    metric_label: str,
    slot_metric_keys: Callable[[Dict[str, Any]], set[str]],
) -> bool:
    matched_line_label = _normalise_spaces(str(slot.get("_matched_line_label") or ""))
    if not matched_line_label:
        return False
    primary_keys = slot_metric_keys({"label": str(operand.get("label") or ""), "concept": ""})
    primary_keys.update(
        key
        for key in (
            _normalise_spaces(str(operand.get("label") or "")),
            _normalise_spaces(str(metric_label or "")),
            *[
                _normalise_spaces(str(alias or ""))
                for alias in (operand.get("aliases") or [])
            ],
        )
        if key
    )
    primary_surfaces = [
        _normalise_spaces(str(value or ""))
        for value in (
            operand.get("label"),
            metric_label,
        )
        if _normalise_spaces(str(value or ""))
    ]
    if any(
        matched_line_label in surface
        or re.sub(r"\s+", "", matched_line_label) in re.sub(r"\s+", "", surface)
        for surface in primary_surfaces
    ):
        return True
    return matched_line_label in primary_keys


def lookup_recovery_value_refinement_allowed(
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
    preferred_evidence: Optional[Dict[str, Any]],
    *,
    desired_scope: str,
    current_evidence: Optional[Dict[str, Any]],
    operand: Dict[str, Any],
    recovered_slot_matches_primary_label: Callable[[Dict[str, Any]], bool],
    direct_structured_lookup_evidence_score: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], float],
    operand_rows_materially_conflict: Callable[[Dict[str, Any], Dict[str, Any]], bool],
) -> bool:
    current_scope = _normalise_spaces(
        str(
            current_slot.get("consolidation_scope")
            or dict((current_evidence or {}).get("metadata") or {}).get("consolidation_scope")
            or "unknown"
        )
    )
    preferred_scope = _normalise_spaces(
        str(
            preferred_slot.get("consolidation_scope")
            or dict((preferred_evidence or {}).get("metadata") or {}).get("consolidation_scope")
            or "unknown"
        )
    )
    if desired_scope != "unknown" and current_scope == desired_scope and preferred_scope != desired_scope:
        return False
    preferred_metadata = dict((preferred_evidence or {}).get("metadata") or {})
    if operand_rows_materially_conflict(current_slot, preferred_slot):
        selected_value_match = preferred_slot_value_matches_selected_evidence(
            preferred_slot,
            preferred_evidence,
        )
        if selected_value_match is False:
            return False
    has_structured_surface = any(
        _normalise_spaces(str(value or ""))
        for value in (
            preferred_metadata.get("table_value_labels_text"),
            preferred_metadata.get("row_label"),
            preferred_metadata.get("semantic_label"),
            preferred_metadata.get("structured_cells"),
        )
    )
    if not has_structured_surface:
        return False
    if bool(preferred_metadata.get("table_value_labels_text")) and recovered_slot_matches_primary_label(
        preferred_slot
    ):
        current_raw_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
        preferred_raw_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
        if preferred_raw_unit and (not current_raw_unit or preferred_raw_unit == current_raw_unit):
            try:
                current_float = float(current_slot.get("normalized_value"))
                preferred_float = float(preferred_slot.get("normalized_value"))
            except (TypeError, ValueError):
                current_float = None
                preferred_float = None
            if current_float is not None and preferred_float is not None:
                relative_delta = abs(preferred_float - current_float) / max(
                    abs(current_float),
                    abs(preferred_float),
                    1.0,
                )
                if (
                    relative_delta > 0.005
                    and lookup_recovery_digit_count(preferred_slot.get("raw_value"))
                    < lookup_recovery_digit_count(current_slot.get("raw_value"))
                ):
                    return False
            return True
    current_unit = _normalise_spaces(str(current_slot.get("normalized_unit") or "")).upper()
    preferred_unit = _normalise_spaces(str(preferred_slot.get("normalized_unit") or "")).upper()
    if not current_unit or not preferred_unit or current_unit == "UNKNOWN" or preferred_unit == "UNKNOWN":
        return False
    if current_unit != preferred_unit:
        return False
    current_value = current_slot.get("normalized_value")
    preferred_value = preferred_slot.get("normalized_value")
    try:
        current_float = float(current_value)
        preferred_float = float(preferred_value)
    except (TypeError, ValueError):
        return False
    if current_float == 0:
        return False
    if (current_float < 0) != (preferred_float < 0):
        return False
    relative_delta = abs(preferred_float - current_float) / max(abs(current_float), abs(preferred_float), 1.0)
    if relative_delta > 0.005:
        current_raw_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
        preferred_raw_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
        if (
            preferred_raw_unit
            and current_raw_unit == preferred_raw_unit
            and lookup_recovery_digit_count(preferred_slot.get("raw_value"))
            < lookup_recovery_digit_count(current_slot.get("raw_value"))
        ):
            return False
        evidence_score = (
            direct_structured_lookup_evidence_score(operand, preferred_evidence)
            if preferred_evidence
            else 0.0
        )
        direct_label = _normalise_spaces(
            str(
                preferred_metadata.get("row_label")
                or preferred_metadata.get("semantic_label")
                or ""
            )
        )
        if evidence_score >= 6.0 and direct_label:
            return True
        return bool(preferred_metadata.get("table_value_labels_text")) and recovered_slot_matches_primary_label(
            preferred_slot
        )
    return lookup_recovery_digit_count(preferred_slot.get("raw_value")) > lookup_recovery_digit_count(
        current_slot.get("raw_value")
    )


def normalize_lookup_slot_unit(
    slot: Dict[str, Any],
    *,
    evidence_by_id: Dict[str, Dict[str, Any]],
    evidence_item_for_operand_row: Callable[[Dict[str, Any], Dict[str, Dict[str, Any]]], Optional[Dict[str, Any]]],
    coerce_operand_unit_from_evidence: Callable[..., str],
) -> Dict[str, Any]:
    updated = dict(slot)
    raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
    raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
    evidence_item = evidence_item_for_operand_row(updated, evidence_by_id)
    metadata = dict((evidence_item or {}).get("metadata") or {})
    unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
    source_surface = _normalise_spaces(
        " ".join(
            str((evidence_item or {}).get(key) or "")
            for key in ("claim", "quote_span", "raw_row_text")
        )
    )
    if raw_value and unit_hint and raw_unit != unit_hint:
        source_has_value = raw_value in source_surface or raw_value.replace(",", "") in source_surface.replace(",", "")
        source_has_raw_unit = bool(raw_unit and raw_unit in source_surface)
        if source_has_value and not source_has_raw_unit:
            coerced_unit = unit_hint
        else:
            coerced_unit = coerce_operand_unit_from_evidence(
                raw_value=raw_value,
                raw_unit=raw_unit,
                evidence_item=evidence_item,
            )
    else:
        coerced_unit = coerce_operand_unit_from_evidence(
            raw_value=raw_value,
            raw_unit=raw_unit,
            evidence_item=evidence_item,
        )
    if coerced_unit and coerced_unit != raw_unit:
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, coerced_unit)
        updated["raw_unit"] = coerced_unit
        if normalized_value is not None:
            updated["normalized_value"] = normalized_value
            updated["normalized_unit"] = normalized_unit
        if raw_value:
            updated["rendered_value"] = f"{raw_value}{coerced_unit}"
    return updated


def lookup_result_from_slot(
    slot: Dict[str, Any],
    source_note: str,
    *,
    normalize_slot: Callable[[Dict[str, Any]], Dict[str, Any]],
) -> Dict[str, Any]:
    slot = normalize_slot(slot)
    rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
    label = _normalise_spaces(str(slot.get("label") or ""))
    clean_slot = {
        key: value
        for key, value in slot.items()
        if not str(key).startswith("_")
    }
    return {
        "status": "ok",
        "result_value": clean_slot.get("normalized_value"),
        "result_unit": clean_slot.get("raw_unit") or clean_slot.get("normalized_unit"),
        "rendered_value": rendered_value,
        "formatted_result": _normalise_spaces(f"{label} {rendered_value}") if label and rendered_value else rendered_value,
        "source_row_ids": list(clean_slot.get("source_row_ids") or []),
        "answer_slots": {
            "metric_label": label,
            "operation_family": "lookup",
            "primary_value": clean_slot,
            "source_row_ids": list(clean_slot.get("source_row_ids") or []),
        },
        "explanation": source_note,
    }


def align_or_replace_successful_lookup_row(
    row: Dict[str, Any],
    *,
    current_slot: Dict[str, Any],
    operand: Dict[str, Any],
    evidence_by_id: Dict[str, Dict[str, Any]],
    evidence_pool: List[Dict[str, Any]],
    state: Dict[str, Any],
    normalize_slot: Callable[[Dict[str, Any]], Dict[str, Any]],
    lookup_result_builder: Callable[[Dict[str, Any], str], Dict[str, Any]],
    evidence_item_for_operand_row: Callable[[Dict[str, Any], Dict[str, Dict[str, Any]]], Optional[Dict[str, Any]]],
    direct_structured_lookup_evidence_score: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], float],
    best_direct_lookup_slot: Callable[..., tuple[Dict[str, Any], float]],
    preferred_slot_has_evidence_surface_match: Callable[[Dict[str, Any], Optional[Dict[str, Any]]], bool],
    value_refinement_allowed: Callable[[Dict[str, Any], Dict[str, Any], Optional[Dict[str, Any]]], bool],
) -> Dict[str, Any]:
    normalized_current_slot = normalize_slot(current_slot)
    unit_aligned_row: Optional[Dict[str, Any]] = None
    if (
        _normalise_spaces(str(normalized_current_slot.get("raw_unit") or ""))
        != _normalise_spaces(str(current_slot.get("raw_unit") or ""))
        or normalized_current_slot.get("normalized_value") != current_slot.get("normalized_value")
    ):
        current_slot = normalized_current_slot
        normalized_result = lookup_result_builder(
            current_slot,
            "lookup result unit aligned from structured evidence metadata.",
        )
        unit_aligned_row = {
            **dict(row),
            "answer": str(normalized_result.get("formatted_result") or ""),
            "calculation_result": normalized_result,
            "answer_slots": normalized_result["answer_slots"],
            "unit_aligned_from_evidence_metadata": True,
        }

    current_evidence = evidence_item_for_operand_row(current_slot, evidence_by_id)
    current_score = (
        direct_structured_lookup_evidence_score(operand, current_evidence)
        if current_evidence
        else 0.0
    )
    preferred_slot, preferred_score = best_direct_lookup_slot(
        operand,
        evidence_pool,
        state=state,
    )
    if not preferred_slot or preferred_score <= current_score:
        return unit_aligned_row or row

    preferred_evidence = evidence_item_for_operand_row(preferred_slot, evidence_by_id)
    if not preferred_slot_has_evidence_surface_match(preferred_slot, preferred_evidence):
        return unit_aligned_row or row

    preferred_slot = normalize_slot(preferred_slot)
    preferred_raw = _normalise_spaces(str(preferred_slot.get("raw_value") or ""))
    current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
    preferred_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
    current_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
    preferred_normalized = preferred_slot.get("normalized_value")
    current_normalized = current_slot.get("normalized_value")
    try:
        if preferred_normalized is not None and current_normalized is not None:
            normalized_differs = abs(float(preferred_normalized) - float(current_normalized)) > 1e-6
        else:
            normalized_differs = preferred_normalized != current_normalized
    except (TypeError, ValueError):
        normalized_differs = preferred_normalized != current_normalized

    if normalized_differs and not value_refinement_allowed(current_slot, preferred_slot, preferred_evidence):
        return unit_aligned_row or row
    if preferred_raw == current_raw and preferred_unit == current_unit and not normalized_differs:
        return unit_aligned_row or row

    preferred_result = lookup_result_builder(
        preferred_slot,
        "lookup result replaced with stronger direct structured evidence.",
    )
    return {
        **dict(row),
        "answer": str(preferred_result.get("formatted_result") or ""),
        "calculation_result": preferred_result,
        "answer_slots": preferred_result["answer_slots"],
        "recovered_from_sibling_table_evidence": True,
    }
