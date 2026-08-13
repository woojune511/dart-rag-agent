"""Lookup-result recovery helpers for structured numeric subtasks."""

import re
from typing import Any, Callable, Dict, List, Optional

from src.agent.financial_answer_slots import answer_slot_has_material
from src.agent.financial_graph_model_loaders import _validate_answer_slots_payload
from src.agent.financial_operand_resolution import (
    DirectStructuredLookupEvidenceScoreInput,
    _evidence_item_for_operand_row,
    coerce_lookup_magnitude_value,
    coerce_operand_unit_from_evidence,
    operand_prefers_aggregate_value_role,
    score_direct_structured_lookup_evidence,
)
from src.agent.financial_row_surfaces import _operand_text_match
from src.agent.financial_runtime_normalization import _normalise_operand_value, _normalise_spaces
from src.agent.financial_scope_policies import operand_period_focus
from src.agent.financial_structured_cells import (
    _structured_cell_period_text,
    select_aggregate_structured_cell,
    select_structured_cell,
)
from src.agent.financial_surface_contracts import _operand_needles, _text_has_positive_surface
from src.config.retrieval_policy import NUMERIC_UNIT_NORMALIZATION_POLICY, PLANNING_POLICY


_MONEY_SURFACE_RE = re.compile(str(PLANNING_POLICY.get("money_surface_pattern") or r"$^"))
_LOOKUP_YEAR_RE = re.compile(str(PLANNING_POLICY.get("year_token_pattern") or r"$^"))
_LOOKUP_YEAR_LABEL_RE = re.compile(str(PLANNING_POLICY.get("year_label_token_pattern") or r"$^"))


def _money_match_to_slot_values(match: re.Match[str]) -> Dict[str, Any]:
    raw_number = _normalise_spaces(match.group("raw"))
    if raw_number.startswith("(") and not raw_number.endswith(")"):
        raw_number = raw_number[1:]
    raw_unit = _normalise_spaces(match.group("unit"))
    rendered_value = _normalise_spaces(f"{raw_number}{raw_unit}")
    compound_unit_prefix = str(PLANNING_POLICY.get("money_surface_compound_unit_prefix") or "")
    normalized_input = rendered_value if compound_unit_prefix and raw_unit.startswith(compound_unit_prefix) else raw_number
    normalized_value, normalized_unit = _normalise_operand_value(normalized_input, raw_unit)
    return {
        "raw_value": raw_number,
        "raw_unit": raw_unit,
        "rendered_value": rendered_value,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        }
def _slot_values_match_operand_unit(values: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    desired_unit = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
    actual_unit = _normalise_spaces(str(values.get("normalized_unit") or "")).upper()
    if desired_unit not in {"KRW", "USD", "COUNT", "PERCENT"}:
        return True
    if not actual_unit or actual_unit == "UNKNOWN":
        return True
    return actual_unit == desired_unit


def lookup_operand_matches_active_task(operand: Dict[str, Any], active_subtask: Dict[str, Any]) -> bool:
    active_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("query") or ""))
    operand_label = _normalise_spaces(
        str(operand.get("label") or operand.get("matched_operand_label") or operand.get("name") or "")
    )
    operand_period = _normalise_spaces(str(operand.get("period") or operand.get("period_hint") or ""))
    active_years = set(_LOOKUP_YEAR_RE.findall(active_label))
    operand_years = set(_LOOKUP_YEAR_RE.findall(f"{operand_label} {operand_period}"))
    if active_years and operand_years and not (active_years & operand_years):
        return False
    if active_years and not operand_years:
        return False
    if active_label and operand_label:
        if active_label == operand_label or active_label in operand_label or operand_label in active_label:
            return True
        active_tokens = {
            token
            for token in re.split(r"\s+", active_label)
            if token and not _LOOKUP_YEAR_LABEL_RE.fullmatch(token)
        }
        operand_tokens = {
            token
            for token in re.split(r"\s+", operand_label)
            if token and not _LOOKUP_YEAR_LABEL_RE.fullmatch(token)
        }
        return bool(active_tokens & operand_tokens)
    return True


def refine_lookup_slot_unit_from_evidence(slot: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    raw_value = _normalise_spaces(str(slot.get("raw_value") or ""))
    if not raw_value:
        return slot
    current_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
    current_normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
    direct_text = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in [
                evidence.get("raw_row_text"),
                evidence.get("quote_span"),
            ]
        )
    )
    claim_text = _normalise_spaces(str(evidence.get("claim") or ""))
    metadata_text = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in [
                (evidence.get("metadata") or {}).get("table_value_labels_text"),
            ]
        )
    )
    text_parts = [direct_text]
    if (
        not current_unit
        or current_normalized_unit in {"", "UNKNOWN"}
        or (
            claim_text
            and raw_value in direct_text
            and raw_value in claim_text
            and (not current_unit or current_unit not in claim_text)
        )
    ):
        text_parts.append(claim_text)
    if not current_unit or current_normalized_unit in {"", "UNKNOWN"}:
        text_parts.append(metadata_text)
    text = _normalise_spaces(" ".join(part for part in text_parts if part))

    def _update_with_unit(unit_text: str) -> Optional[Dict[str, Any]]:
        evidence_unit = _normalise_spaces(str(unit_text or "")).strip("()[]{}")
        if not evidence_unit or evidence_unit == current_unit:
            return None
        aliases = dict(NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_unit_aliases") or {})
        evidence_unit = str(aliases.get(evidence_unit, evidence_unit))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, evidence_unit)
        if normalized_value is not None and str(normalized_unit or "").strip().upper() != "UNKNOWN":
            updated = dict(slot)
            updated["raw_unit"] = evidence_unit
            updated["normalized_value"] = normalized_value
            updated["normalized_unit"] = normalized_unit
            updated["rendered_value"] = _normalise_spaces(f"{raw_value}{evidence_unit}")
            return updated
        return None

    if text and raw_value in text:
        inline_pattern = str(NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_value_unit_pattern") or "")
        if inline_pattern:
            raw_compact = re.sub(r"[,\s()]", "", raw_value)
            for match in re.finditer(inline_pattern, text):
                matched_compact = re.sub(r"[,\s()]", "", str(match.group("value") or ""))
                if matched_compact != raw_compact:
                    continue
                updated = _update_with_unit(str(match.group("unit") or ""))
                if updated:
                    return updated
        for match in re.finditer(rf"{re.escape(raw_value)}\s*\(\s*([^)]+?)\s*\)", text):
            updated = _update_with_unit(match.group(1))
            if updated:
                return updated
        for match in re.finditer(rf"{re.escape(raw_value)}\s*([^\s|,)]+)", text):
            updated = _update_with_unit(match.group(1))
            if updated:
                return updated
    if current_unit and current_normalized_unit not in {"", "UNKNOWN"}:
        return slot
    metadata = dict(evidence.get("metadata") or {})
    unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
    if unit_hint and not current_unit:
        updated = _update_with_unit(unit_hint)
        if updated:
            return updated
    if current_unit:
        return slot
    return slot


def _extract_lookup_slot_from_answer_text(
    *,
    answer: str,
    operand: Dict[str, Any],
    metric_label: str,
    selected_claim_ids: List[str],
) -> Optional[Dict[str, Any]]:
    """Build a lookup answer slot from ontology operand surfaces in prose."""
    text = _normalise_spaces(answer)
    if not text:
        return None
    surface_contract = dict(operand.get("surface_contract") or {})
    surfaces = [
        _normalise_spaces(str(surface))
        for surface in [
            *(surface_contract.get("positive") or []),
            *_operand_needles(operand),
        ]
        if _normalise_spaces(str(surface))
    ]
    surfaces = sorted(dict.fromkeys(surfaces), key=len, reverse=True)
    money_matches = list(_MONEY_SURFACE_RE.finditer(text))
    if not surfaces:
        if len(money_matches) != 1:
            return None
        best_match = money_matches[0]
        values = _money_match_to_slot_values(best_match)
        if values.get("normalized_value") is None and not values.get("rendered_value"):
            return None
        if not _slot_values_match_operand_unit(values, operand):
            return None
        source_claim_ids = [
            str(claim_id).strip()
            for claim_id in selected_claim_ids
            if str(claim_id).strip()
        ]
        return {
            "label": _normalise_spaces(str(operand.get("label") or metric_label)),
            "concept": _normalise_spaces(str(operand.get("concept") or "")),
            "role": _normalise_spaces(str(operand.get("role") or "primary_value")) or "primary_value",
            "period": _normalise_spaces(str(operand.get("period_hint") or operand.get("period") or "")),
            "status": "ok",
            **values,
            "source_row_id": source_claim_ids[0] if source_claim_ids else "",
            "source_row_ids": source_claim_ids[:1],
            "source_claim_ids": source_claim_ids,
        }
    haystack = text.lower()
    best_match: Optional[re.Match[str]] = None
    best_distance: Optional[int] = None
    for surface in surfaces:
        needle = surface.lower()
        search_from = 0
        while True:
            surface_index = haystack.find(needle, search_from)
            if surface_index < 0:
                break
            window = text[surface_index : surface_index + max(80, len(surface) + 80)]
            money_match = _MONEY_SURFACE_RE.search(window)
            if money_match:
                values = _money_match_to_slot_values(money_match)
                if not _slot_values_match_operand_unit(values, operand):
                    search_from = surface_index + max(1, len(needle))
                    continue
                distance = money_match.start()
                if best_distance is None or distance < best_distance:
                    best_distance = distance
                    best_match = money_match
            search_from = surface_index + max(1, len(needle))

    if best_match is None:
        return None
    values = _money_match_to_slot_values(best_match)
    if values.get("normalized_value") is None and not values.get("rendered_value"):
        return None
    source_claim_ids = [
        str(claim_id).strip()
        for claim_id in selected_claim_ids
        if str(claim_id).strip()
    ]
    return {
        "label": _normalise_spaces(str(operand.get("label") or metric_label)),
        "concept": _normalise_spaces(str(operand.get("concept") or "")),
        "role": _normalise_spaces(str(operand.get("role") or "primary_value")) or "primary_value",
        "period": _normalise_spaces(str(operand.get("period_hint") or operand.get("period") or "")),
        "status": "ok",
        **values,
        "source_row_id": source_claim_ids[0] if source_claim_ids else "",
        "source_row_ids": source_claim_ids[:1],
        "source_claim_ids": source_claim_ids,
        }
def synthesize_lookup_answer_slot_from_prose(
    *,
    active_subtask: Dict[str, Any],
    answer: str,
    calculation_result: Dict[str, Any],
    selected_claim_ids: List[str],
) -> Dict[str, Any]:
    operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
    metric_family = _normalise_spaces(str(active_subtask.get("metric_family") or "")).lower()
    if operation_family not in {"lookup", "single_value", "concept_lookup"} and not metric_family.startswith("concept_"):
        return calculation_result

    operands = [dict(item or {}) for item in list(active_subtask.get("required_operands") or []) if isinstance(item, dict)]
    if not operands:
        operands = [
            {
                "label": _normalise_spaces(str(active_subtask.get("metric_label") or "")),
                "concept": _normalise_spaces(str(active_subtask.get("metric_family") or "")),
                "role": "primary_value",
            }
        ]
    if len(operands) != 1:
        return calculation_result

    answer_slots = dict(calculation_result.get("answer_slots") or {})
    if answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
        return calculation_result

    slot = _extract_lookup_slot_from_answer_text(
        answer=answer,
        operand=operands[0],
        metric_label=str(active_subtask.get("metric_label") or ""),
        selected_claim_ids=selected_claim_ids,
    )
    if not slot:
        return calculation_result

    updated_slots = {
        **answer_slots,
        "operation_family": "lookup",
        "primary_value": slot,
    }
    rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
    return {
        **calculation_result,
        "status": "ok",
        "operation_family": "lookup",
        "rendered_value": rendered_value,
        "formatted_result": _normalise_spaces(answer) or rendered_value,
        "answer_slots": _validate_answer_slots_payload(updated_slots),
    }


def _doc_metadata_value(doc: Any, key: str) -> str:
    metadata = getattr(doc, "metadata", None)
    if isinstance(metadata, dict):
        return _normalise_spaces(str(metadata.get(key) or ""))
    return ""


def _doc_page_content(doc: Any) -> str:
    return _normalise_spaces(str(getattr(doc, "page_content", "") or ""))


def _source_anchor_from_doc(doc: Any) -> str:
    explicit = _doc_metadata_value(doc, "source_anchor")
    if explicit:
        return explicit
    metadata = getattr(doc, "metadata", None)
    if not isinstance(metadata, dict):
        return ""
    parts = [
        _normalise_spaces(str(metadata.get("company") or "")),
        _normalise_spaces(str(metadata.get("year") or "")),
        _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or "")),
    ]
    parts = [part for part in parts if part]
    return f"[{' | '.join(parts)}]" if parts else ""


def lookup_slot_supporting_doc_evidence(
    *,
    active_subtask: Dict[str, Any],
    slot: Dict[str, Any],
    docs: List[Any],
) -> Optional[Dict[str, Any]]:
    rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
    raw_value = _normalise_spaces(str(slot.get("raw_value") or ""))
    if not rendered_value and not raw_value:
        return None
    operands = [dict(item or {}) for item in list(active_subtask.get("required_operands") or []) if isinstance(item, dict)]
    operand = operands[0] if operands else {}
    surface_contract = dict(operand.get("surface_contract") or {})
    surfaces = [
        _normalise_spaces(str(surface))
        for surface in [
            *(surface_contract.get("positive") or []),
            *_operand_needles(operand),
            str(slot.get("label") or ""),
        ]
        if _normalise_spaces(str(surface))
    ]
    compact_raw = raw_value.replace(",", "")
    for doc in docs:
        text = _doc_page_content(doc)
        compact_text = text.replace(",", "")
        if rendered_value and rendered_value not in text:
            if not raw_value or raw_value not in text:
                if not compact_raw or compact_raw not in compact_text:
                    continue
        if surfaces and not any(surface in text for surface in surfaces):
            continue
        anchor = _source_anchor_from_doc(doc)
        metadata = dict(getattr(doc, "metadata", {}) or {})
        return {
            "evidence_id": f"slot_support:{str(active_subtask.get('task_id') or 'lookup')}:primary_value",
            "source_anchor": anchor,
            "claim": text[:700],
            "quote_span": rendered_value or raw_value,
            "metadata": metadata,
        }
    return None


def coerce_lookup_magnitude_record(
    record: Dict[str, Any],
    evidence_item: Optional[Dict[str, Any]] = None,
    *,
    concept: str = "",
    statement_type: str = "",
    row_label: str = "",
    semantic_label: str = "",
) -> Dict[str, Any]:
    """Apply ontology-declared lookup magnitude semantics to a slot/operand row."""
    updated = dict(record or {})
    normalized_unit = _normalise_spaces(str(updated.get("normalized_unit") or "")).upper()
    normalized_value = updated.get("normalized_value")
    try:
        numeric_value = float(normalized_value)
    except (TypeError, ValueError):
        return updated

    metadata = dict((evidence_item or {}).get("metadata") or {})
    resolved_concept = _normalise_spaces(
        str(
            concept
            or updated.get("concept")
            or updated.get("matched_operand_concept")
            or ""
        )
    )
    resolved_statement_type = _normalise_spaces(
        str(
            statement_type
            or updated.get("statement_type")
            or metadata.get("statement_type")
            or ""
        )
    )
    resolved_row_label = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in (
                row_label,
                updated.get("row_label"),
                updated.get("label"),
                updated.get("matched_operand_label"),
                metadata.get("row_label"),
            )
            if str(part or "").strip()
        )
    )
    resolved_semantic_label = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in (
                semantic_label,
                updated.get("semantic_label"),
                metadata.get("semantic_label"),
                metadata.get("table_value_labels_text"),
            )
            if str(part or "").strip()
        )
    )
    coerced_value = coerce_lookup_magnitude_value(
        normalized_value=numeric_value,
        normalized_unit=normalized_unit,
        raw_value=_normalise_spaces(str(updated.get("raw_value") or updated.get("rendered_value") or "")),
        concept=resolved_concept,
        statement_type=resolved_statement_type,
        row_label=resolved_row_label,
        semantic_label=resolved_semantic_label,
    )
    if coerced_value != numeric_value:
        raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
        rendered_value = _normalise_spaces(str(updated.get("rendered_value") or ""))
        magnitude_raw = raw_value.strip()
        if magnitude_raw.startswith("(") and magnitude_raw.endswith(")"):
            magnitude_raw = magnitude_raw[1:-1].strip()
        magnitude_raw = magnitude_raw.lstrip("△▲-").strip()
        if rendered_value and not updated.get("source_rendered_value"):
            updated["source_rendered_value"] = rendered_value
        if magnitude_raw and raw_unit:
            updated["rendered_value"] = _normalise_spaces(f"{magnitude_raw}{raw_unit}")
        updated["normalized_value"] = coerced_value
        updated["value_coercion"] = "lookup_magnitude_from_source_surface"
    return updated


def lookup_row_from_direct_structured_evidence(
    operand: Dict[str, Any],
    evidence_item: Dict[str, Any],
    *,
    index: int,
) -> Dict[str, Any]:
    metadata = dict(evidence_item.get("metadata") or {})
    cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if not cells:
        return {}
    selected_cell = select_structured_cell(
        [{**cell, "_report_year": metadata.get("year")} for cell in cells],
        operand=operand,
        query_years=[int(metadata["year"])] if str(metadata.get("year") or "").isdigit() else [],
        period_focus=operand_period_focus(operand, "current"),
    )
    metadata_value_role = _normalise_spaces(str(metadata.get("value_role") or "")).lower()
    metadata_aggregation_stage = _normalise_spaces(str(metadata.get("aggregation_stage") or "")).lower()
    if (
        metadata_value_role == "aggregate"
        or metadata_aggregation_stage in {"direct", "final", "subtotal"}
        or operand_prefers_aggregate_value_role(operand)
    ):
        aggregate_cells = [
            cell
            for cell in cells
            if _normalise_spaces(str(cell.get("value_role") or "")).lower() == "aggregate"
            or _normalise_spaces(str(cell.get("aggregation_stage") or "")).lower() in {"direct", "final", "subtotal"}
            or _normalise_spaces(str(cell.get("aggregate_label") or ""))
        ]
        aggregate_selected_cell = select_aggregate_structured_cell(
            [{**cell, "_report_year": metadata.get("year")} for cell in aggregate_cells],
            operand=operand,
            query_years=[int(metadata["year"])] if str(metadata.get("year") or "").isdigit() else [],
            period_focus=operand_period_focus(operand, "current"),
        )
        if aggregate_selected_cell:
            selected_cell = aggregate_selected_cell
    if not selected_cell:
        return {}
    raw_value = _normalise_spaces(str(selected_cell.get("value_text") or ""))
    raw_unit = _normalise_spaces(str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or ""))
    normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
    if normalized_value is None:
        return {}
    evidence_id = str(evidence_item.get("evidence_id") or "").strip()
    row = {
        "operand_id": f"direct_lookup_{index:03d}",
        "evidence_id": evidence_id,
        "source_row_id": evidence_id,
        "source_row_ids": [evidence_id] if evidence_id else [],
        "source_anchor": _normalise_spaces(str(evidence_item.get("source_anchor") or "")),
        "label": _normalise_spaces(str(operand.get("label") or metadata.get("row_label") or "")),
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "period": _normalise_spaces(str(metadata.get("year") or "")),
        "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
        "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
        "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
        "statement_type": metadata.get("statement_type"),
        "consolidation_scope": metadata.get("consolidation_scope"),
        "table_source_id": metadata.get("table_source_id"),
        "value_role": _normalise_spaces(str(selected_cell.get("value_role") or metadata.get("value_role") or "")),
        "aggregation_stage": _normalise_spaces(
            str(selected_cell.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
        ),
        "aggregate_label": _normalise_spaces(
            str(selected_cell.get("aggregate_label") or metadata.get("aggregate_label") or "")
        ),
    }
    return coerce_lookup_magnitude_record(
        row,
        evidence_item,
        concept=str(operand.get("concept") or ""),
        statement_type=str(metadata.get("statement_type") or ""),
        row_label=str(metadata.get("row_label") or operand.get("label") or ""),
        semantic_label=str(metadata.get("semantic_label") or metadata.get("row_label") or ""),
    )


def coerce_operand_value_from_direct_structured_evidence(
    row: Dict[str, Any],
    evidence_item: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    if not row or not evidence_item:
        return row
    metadata = dict(evidence_item.get("metadata") or {})
    cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
    if not cells:
        return row

    row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
    semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
    operand_spec = {
        "label": _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
        "concept": _normalise_spaces(str(row.get("matched_operand_concept") or row.get("concept") or "")),
        "role": _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")),
        "period": _normalise_spaces(str(row.get("period") or "")),
        "period_hint": _normalise_spaces(str(row.get("period") or "")),
        "aliases": [
            item
            for item in (
                row.get("matched_operand_label"),
                row.get("label"),
                row.get("concept"),
            )
            if _normalise_spaces(str(item or ""))
        ],
    }
    authoritative_surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                row_label,
                semantic_label,
                metadata.get("aggregate_label"),
            )
        )
    )
    if authoritative_surface and not (
        _operand_text_match(authoritative_surface, operand_spec)
        or _text_has_positive_surface(authoritative_surface, operand_spec)
    ):
        return row

    query_years: List[int] = []
    for raw_year in (operand_spec.get("period"), metadata.get("year")):
        try:
            if raw_year not in (None, ""):
                year = int(raw_year)
                if year not in query_years:
                    query_years.append(year)
        except (TypeError, ValueError):
            continue

    enriched_cells = [
        {
            **cell,
            "_report_year": metadata.get("year"),
            "_sibling_cells": [dict(item) for item in cells],
        }
        for cell in cells
    ]
    value_role = _normalise_spaces(str(row.get("value_role") or metadata.get("value_role") or "")).lower()
    aggregation_stage = _normalise_spaces(
        str(row.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
    ).lower()
    current_raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
    current_value = row.get("normalized_value")
    prefers_aggregate_cell = bool(
        value_role == "aggregate"
        or aggregation_stage in {"direct", "final", "subtotal"}
        or operand_prefers_aggregate_value_role(row)
    )
    period_specific_cell_selection_required = bool(
        operand_spec.get("period")
        and len(enriched_cells) > 1
        and any(
            re.search(
                r"(?:19|20)\d{2}|current|prior",
                _structured_cell_period_text(
                    cell,
                    query_years,
                    operand_period_focus(operand_spec, "unknown"),
                ),
                flags=re.IGNORECASE,
            )
            for cell in enriched_cells
        )
    )
    if (
        current_raw_value
        and current_value is not None
        and not prefers_aggregate_cell
        and not period_specific_cell_selection_required
    ):
        current_compact = re.sub(r"[\s,()]", "", current_raw_value)
        for cell in enriched_cells:
            cell_value = _normalise_spaces(str(cell.get("value_text") or ""))
            if current_compact and current_compact == re.sub(r"[\s,()]", "", cell_value):
                return row
    selected_cell: Optional[Dict[str, Any]] = None
    if prefers_aggregate_cell:
        selected_cell = select_aggregate_structured_cell(
            enriched_cells,
            operand=operand_spec,
            query_years=query_years,
            period_focus=operand_period_focus(operand_spec, "unknown"),
        )
    if not selected_cell:
        selected_cell = select_structured_cell(
            enriched_cells,
            operand=operand_spec,
            query_years=query_years,
            period_focus=operand_period_focus(operand_spec, "unknown"),
        )
    if not selected_cell:
        return row

    raw_value = _normalise_spaces(str(selected_cell.get("value_text") or ""))
    raw_unit = _normalise_spaces(str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or row.get("raw_unit") or ""))
    normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
    if normalized_value is None:
        return row
    try:
        if current_value is not None and abs(float(current_value) - float(normalized_value)) <= 1e-6:
            return row
    except (TypeError, ValueError):
        pass

    updated = dict(row)
    updated["raw_value"] = raw_value
    updated["raw_unit"] = raw_unit
    updated["normalized_value"] = normalized_value
    updated["normalized_unit"] = normalized_unit
    updated["rendered_value"] = _normalise_spaces(f"{raw_value}{raw_unit}") if raw_unit else raw_value
    updated["structured_evidence_cell_realigned"] = True
    return updated


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


def _lookup_recovery_scope_allows_refinement(
    *,
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
    current_evidence: Optional[Dict[str, Any]],
    preferred_evidence: Optional[Dict[str, Any]],
    desired_scope: str,
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
    return not (
        desired_scope != "unknown"
        and current_scope == desired_scope
        and preferred_scope != desired_scope
    )


def _lookup_recovery_has_structured_surface(preferred_metadata: Dict[str, Any]) -> bool:
    return any(
        _normalise_spaces(str(value or ""))
        for value in (
            preferred_metadata.get("table_value_labels_text"),
            preferred_metadata.get("row_label"),
            preferred_metadata.get("semantic_label"),
            preferred_metadata.get("structured_cells"),
        )
    )


def _lookup_recovery_float_pair(
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
) -> Optional[tuple[float, float]]:
    try:
        return float(current_slot.get("normalized_value")), float(preferred_slot.get("normalized_value"))
    except (TypeError, ValueError):
        return None


def _lookup_recovery_slot_relative_delta(current_float: float, preferred_float: float) -> float:
    return abs(preferred_float - current_float) / max(abs(current_float), abs(preferred_float), 1.0)


def _lookup_recovery_more_compact_same_raw_unit(
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
) -> bool:
    current_raw_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
    preferred_raw_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
    return (
        bool(preferred_raw_unit)
        and current_raw_unit == preferred_raw_unit
        and lookup_recovery_digit_count(preferred_slot.get("raw_value"))
        < lookup_recovery_digit_count(current_slot.get("raw_value"))
    )


def _lookup_recovery_table_label_refinement_allowed(
    *,
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
    preferred_metadata: Dict[str, Any],
    recovered_slot_matches_primary_label: Callable[[Dict[str, Any]], bool],
) -> Optional[bool]:
    if not bool(preferred_metadata.get("table_value_labels_text")) or not recovered_slot_matches_primary_label(
        preferred_slot
    ):
        return None
    current_raw_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
    preferred_raw_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
    if not preferred_raw_unit or (current_raw_unit and preferred_raw_unit != current_raw_unit):
        return None
    value_pair = _lookup_recovery_float_pair(current_slot, preferred_slot)
    if value_pair is not None:
        current_float, preferred_float = value_pair
        if (
            _lookup_recovery_slot_relative_delta(current_float, preferred_float) > 0.005
            and lookup_recovery_digit_count(preferred_slot.get("raw_value"))
            < lookup_recovery_digit_count(current_slot.get("raw_value"))
        ):
            return False
    return True


def _lookup_recovery_same_unit_refinement_allowed(
    *,
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
    preferred_evidence: Optional[Dict[str, Any]],
    preferred_metadata: Dict[str, Any],
    operand: Dict[str, Any],
    recovered_slot_matches_primary_label: Callable[[Dict[str, Any]], bool],
) -> bool:
    current_unit = _normalise_spaces(str(current_slot.get("normalized_unit") or "")).upper()
    preferred_unit = _normalise_spaces(str(preferred_slot.get("normalized_unit") or "")).upper()
    if not current_unit or not preferred_unit or current_unit == "UNKNOWN" or preferred_unit == "UNKNOWN":
        return False
    if current_unit != preferred_unit:
        return False
    value_pair = _lookup_recovery_float_pair(current_slot, preferred_slot)
    if value_pair is None:
        return False
    current_float, preferred_float = value_pair
    if current_float == 0:
        return False
    if (current_float < 0) != (preferred_float < 0):
        return False
    relative_delta = _lookup_recovery_slot_relative_delta(current_float, preferred_float)
    if relative_delta > 0.005:
        if _lookup_recovery_more_compact_same_raw_unit(current_slot, preferred_slot):
            return False
        evidence_score = (
            score_direct_structured_lookup_evidence(
                DirectStructuredLookupEvidenceScoreInput(
                    operand=operand,
                    evidence_item=preferred_evidence,
                )
            ).score
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


def lookup_recovery_value_refinement_allowed(
    current_slot: Dict[str, Any],
    preferred_slot: Dict[str, Any],
    preferred_evidence: Optional[Dict[str, Any]],
    *,
    desired_scope: str,
    current_evidence: Optional[Dict[str, Any]],
    operand: Dict[str, Any],
    recovered_slot_matches_primary_label: Callable[[Dict[str, Any]], bool],
    operand_rows_materially_conflict: Callable[[Dict[str, Any], Dict[str, Any]], bool],
) -> bool:
    if not _lookup_recovery_scope_allows_refinement(
        current_slot=current_slot,
        preferred_slot=preferred_slot,
        current_evidence=current_evidence,
        preferred_evidence=preferred_evidence,
        desired_scope=desired_scope,
    ):
        return False
    preferred_metadata = dict((preferred_evidence or {}).get("metadata") or {})
    if operand_rows_materially_conflict(current_slot, preferred_slot):
        selected_value_match = preferred_slot_value_matches_selected_evidence(
            preferred_slot,
            preferred_evidence,
        )
        if selected_value_match is False:
            return False
    if not _lookup_recovery_has_structured_surface(preferred_metadata):
        return False
    table_label_decision = _lookup_recovery_table_label_refinement_allowed(
        current_slot=current_slot,
        preferred_slot=preferred_slot,
        preferred_metadata=preferred_metadata,
        recovered_slot_matches_primary_label=recovered_slot_matches_primary_label,
    )
    if table_label_decision is not None:
        return table_label_decision
    return _lookup_recovery_same_unit_refinement_allowed(
        current_slot=current_slot,
        preferred_slot=preferred_slot,
        preferred_evidence=preferred_evidence,
        preferred_metadata=preferred_metadata,
        operand=operand,
        recovered_slot_matches_primary_label=recovered_slot_matches_primary_label,
    )


def normalize_lookup_slot_unit(
    slot: Dict[str, Any],
    *,
    evidence_by_id: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    updated = dict(slot)
    raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
    raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
    evidence_item = _evidence_item_for_operand_row(updated, evidence_by_id)
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

    current_evidence = _evidence_item_for_operand_row(current_slot, evidence_by_id)
    current_score = (
        score_direct_structured_lookup_evidence(
            DirectStructuredLookupEvidenceScoreInput(
                operand=operand,
                evidence_item=current_evidence,
            )
        ).score
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

    preferred_evidence = _evidence_item_for_operand_row(preferred_slot, evidence_by_id)
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
