"""State-free structured reconciliation candidate projections."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.financial_graph_helpers import (
    _operand_period_focus,
    _operand_target_years,
    _resolve_candidate_local_unit_hint,
    _score_operand_candidate,
    _score_structured_cell,
)
from src.agent.financial_operand_resolution import coerce_lookup_magnitude_value
from src.agent.financial_operation_policies import _label_implies_percent_metric
from src.agent.financial_runtime_normalization import _normalise_operand_value, _normalise_spaces
from src.agent.financial_structured_cells import _structured_cell_period_text
from src.config.retrieval_policy import (
    FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES,
    RECONCILIATION_POLICY,
)


def _candidate_statement_type(candidate: Dict[str, Any], metadata: Dict[str, Any]) -> str:
    explicit_statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    if explicit_statement_type:
        return explicit_statement_type
    surface = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                metadata.get("section_path"),
                metadata.get("section_title"),
                metadata.get("local_heading"),
                metadata.get("table_context"),
                candidate.get("source_anchor"),
                candidate.get("source_context"),
            )
            if str(value or "").strip()
        )
    )
    if not surface:
        return ""
    for policy in FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES:
        markers = [
            _normalise_spaces(str(marker))
            for marker in (policy.get("markers") or [])
            if _normalise_spaces(str(marker))
        ]
        if not any(marker in surface for marker in markers):
            continue
        statement_types = [
            _normalise_spaces(str(statement_type))
            for statement_type in (policy.get("statement_types") or [])
            if _normalise_spaces(str(statement_type))
        ]
        if statement_types:
            return statement_types[0]
    return ""


def _structured_candidate_unit_hint(
    *,
    raw_value: str,
    raw_unit: str,
    candidate: Dict[str, Any],
    operand: Dict[str, Any],
    selected_cell: Dict[str, Any],
) -> str:
    desired_unit_family = str(operand.get("unit_family") or "").strip().upper()
    policy = dict(RECONCILIATION_POLICY)
    percent_unit = str(policy.get("percent_unit") or "")
    if desired_unit_family == "PERCENT":
        if percent_unit and percent_unit in str(raw_unit or ""):
            return raw_unit
        label_surfaces = " ".join(
            part
            for part in (
                str(operand.get("label") or "").strip(),
                " ".join(str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()),
                " ".join(str(item).strip() for item in (selected_cell.get("column_headers") or []) if str(item).strip()),
                str((candidate.get("metadata") or {}).get("semantic_label") or "").strip(),
                str((candidate.get("metadata") or {}).get("row_label") or "").strip(),
            )
            if part
        )
        if _label_implies_percent_metric(label_surfaces):
            return percent_unit
    candidate_metadata = dict(candidate.get("metadata") or {})
    statement_type = str(candidate_metadata.get("statement_type") or "").strip().lower()
    current_unit = str(raw_unit or "").strip()
    ambiguous_units = {str(item) for item in (policy.get("ambiguous_krw_units") or ())}
    note_statement_type = str(policy.get("note_statement_type") or "")
    if current_unit in ambiguous_units:
        resolved_local_unit = _resolve_candidate_local_unit_hint(candidate, raw_value)
        if resolved_local_unit and (current_unit == "" or statement_type == note_statement_type):
            return resolved_local_unit
    return raw_unit


def _fallback_period_text_for_operand(operand: Dict[str, Any], query_years: List[int]) -> str:
    period_focus = str(operand.get("_effective_period_focus") or "").strip()
    role = str(operand.get("role") or "").strip()
    if query_years and (role == "current_period" or period_focus == "current"):
        return str(max(query_years))
    if query_years and (role == "prior_period" or period_focus == "prior"):
        ordered_years = sorted({int(year) for year in query_years}, reverse=True)
        if len(ordered_years) >= 2:
            return str(ordered_years[1])
        return str(ordered_years[0] - 1)
    return str(operand.get("period_hint") or "").strip()


def structured_cell_identity(cell: Dict[str, Any]) -> str:
    value_id = str(cell.get("value_id") or "").strip()
    if value_id:
        return value_id
    row_index = str(cell.get("row_index") or "").strip()
    column_index = str(cell.get("column_index") or "").strip()
    if row_index or column_index:
        return f"{row_index}:{column_index}"
    header_key = "|".join(str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip())
    return f"{header_key}|{str(cell.get('value_text') or '').strip()}"


def _resolved_period_text_for_operand(
    *,
    operand: Dict[str, Any],
    cell: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> str:
    effective_period_focus = _operand_period_focus(operand, period_focus)
    operand_with_period_focus = {**operand, "_effective_period_focus": effective_period_focus}
    period = _structured_cell_period_text(cell, query_years, effective_period_focus)
    period_presence_pattern = str(RECONCILIATION_POLICY.get("period_presence_pattern") or "")
    if period_presence_pattern and not re.search(period_presence_pattern, period):
        report_year: Optional[int] = None
        for raw_year in (cell.get("_report_year"), cell.get("report_year"), cell.get("year")):
            try:
                if raw_year not in (None, ""):
                    report_year = int(raw_year)
                    break
            except (TypeError, ValueError):
                continue
        target_years = _operand_target_years(operand, query_years)
        if report_year is not None and target_years and report_year in target_years:
            period = str(report_year)
        elif report_year is not None:
            period = str(report_year)
        else:
            period = _fallback_period_text_for_operand(operand_with_period_focus, query_years)
    return period


def pair_candidate_period_score(
    *,
    candidate: Dict[str, Any],
    cell: Dict[str, Any],
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    constraints: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
    report_scope: Optional[Dict[str, Any]] = None,
) -> tuple[float, str]:
    candidate_score = _score_operand_candidate(
        candidate,
        operand=operand,
        preferred_statement_types=preferred_statement_types,
        constraints=constraints,
        query_years=query_years,
        report_scope=report_scope,
    )
    cell_score = _score_structured_cell(
        cell,
        query_years=_operand_target_years(operand, query_years),
        period_focus=_operand_period_focus(operand, period_focus),
        operand=operand,
    )
    period = _resolved_period_text_for_operand(
        operand=operand,
        cell=cell,
        query_years=query_years,
        period_focus=period_focus,
    )
    return candidate_score + cell_score, period


def find_reconciliation_match_entry(
    reconciliation_result: Dict[str, Any],
    operand: Dict[str, Any],
) -> Dict[str, Any]:
    label = str(operand.get("label") or "").strip()
    role = str(operand.get("role") or "").strip()
    rows = [
        dict(item)
        for item in (reconciliation_result.get("matched_operands") or [])
        if str(item.get("label") or "").strip() == label
    ]
    if role:
        exact = next((row for row in rows if str(row.get("role") or "").strip() == role), None)
        if exact:
            return exact
    return rows[0] if rows else {}


def build_operand_row_from_candidate_cell(
    *,
    candidate: Dict[str, Any],
    selected_cell: Dict[str, Any],
    operand: Dict[str, Any],
    index: int,
    period_focus: str,
    query_years: List[int],
) -> Optional[Dict[str, Any]]:
    metadata = dict(candidate.get("metadata") or {})
    raw_value = str(selected_cell.get("value_text") or "").strip()
    raw_unit = str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or "").strip()
    raw_unit = _structured_candidate_unit_hint(
        raw_value=raw_value,
        raw_unit=raw_unit,
        candidate=candidate,
        operand=operand,
        selected_cell=selected_cell,
    )
    normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
    normalized_value = coerce_lookup_magnitude_value(
        normalized_value=normalized_value,
        normalized_unit=normalized_unit,
        raw_value=raw_value,
        concept=str(operand.get("concept") or ""),
        statement_type=_candidate_statement_type(candidate, metadata),
        row_label=str(metadata.get("row_label") or ""),
        semantic_label=str(metadata.get("semantic_label") or ""),
    )
    if normalized_value is None:
        return None
    period = _resolved_period_text_for_operand(
        operand=operand,
        cell=selected_cell,
        query_years=query_years,
        period_focus=period_focus,
    )
    row_label = str(operand.get("label") or metadata.get("semantic_label") or metadata.get("row_label") or "").strip()
    return {
        "operand_id": f"op_{index:03d}",
        "evidence_id": str(candidate.get("candidate_id") or ""),
        "source_anchor": candidate.get("source_anchor"),
        "label": f"{period} {row_label}".strip(),
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit,
        "period": period,
        "table_source_id": metadata.get("table_source_id"),
        "statement_type": _candidate_statement_type(candidate, metadata),
        "consolidation_scope": metadata.get("consolidation_scope"),
        "value_role": _normalise_spaces(str(selected_cell.get("value_role") or metadata.get("value_role") or "")),
        "aggregation_stage": _normalise_spaces(
            str(selected_cell.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
        ),
        "aggregate_label": _normalise_spaces(
            str(selected_cell.get("aggregate_label") or metadata.get("aggregate_label") or "")
        ),
        "matched_operand_label": str(operand.get("label") or "").strip(),
        "matched_operand_concept": str(operand.get("concept") or "").strip(),
        "matched_operand_role": str(operand.get("role") or "").strip(),
    }


def effective_structured_cell_unit_hint(
    *,
    candidate: Dict[str, Any],
    selected_cell: Dict[str, Any],
    operand: Dict[str, Any],
) -> str:
    metadata = dict(candidate.get("metadata") or {})
    raw_value = str(selected_cell.get("value_text") or "").strip()
    raw_unit = str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or "").strip()
    return _structured_candidate_unit_hint(
        raw_value=raw_value,
        raw_unit=raw_unit,
        candidate=candidate,
        operand=operand,
        selected_cell=selected_cell,
    )


def expand_structured_candidate_ids(
    candidate_ids: List[str],
    candidate_map: Dict[str, Dict[str, Any]],
) -> List[str]:
    expanded: List[str] = []
    seen: set[str] = set()
    for raw_candidate_id in candidate_ids:
        cleaned = str(raw_candidate_id).strip()
        if not cleaned:
            continue
        candidate_variants = [cleaned]
        if cleaned.startswith("recon::"):
            candidate_variants.append(cleaned.removeprefix("recon::"))
        else:
            candidate_variants.append(f"recon::{cleaned}")
        expanded_variants: List[str] = []
        for candidate_variant in list(dict.fromkeys(candidate_variants)):
            expanded_variants.append(candidate_variant)
            expanded_variants.append(f"{candidate_variant}::raw_row")
        for current_id in expanded_variants:
            if current_id in seen or current_id not in candidate_map:
                continue
            seen.add(current_id)
            expanded.append(current_id)
    return expanded


def structured_candidate_from_id(
    candidate_id: str,
    candidate_map: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    candidate = dict(candidate_map.get(str(candidate_id).strip()) or {})
    if not candidate:
        return None
    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    if candidate_kind == "evidence_row" and str(metadata.get("row_text") or "").strip():
        candidate["candidate_kind"] = "table_row"
    return candidate
