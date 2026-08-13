"""Structured table-cell period helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.financial_row_surfaces import (
    _generic_column_headers,
    _operand_text_match,
    _parse_unstructured_table_row_cells,
)
from src.agent.financial_runtime_normalization import _normalise_operand_value, _normalise_spaces
from src.agent.financial_scope_policies import operand_target_years
from src.agent.financial_surface_contracts import _operand_needles
from src.config.retrieval_policy import (
    GENERIC_PERIOD_OPERAND_POLICY,
    PERIOD_FOCUS_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
    STRUCTURED_CELL_PERIOD_SCORING_POLICY,
)


def select_structured_cell(
    cells: List[Dict[str, Any]],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> Optional[Dict[str, Any]]:
    if not cells:
        return None

    enriched_cells: List[Dict[str, Any]] = []
    for cell in cells:
        enriched = dict(cell)
        enriched["_sibling_cells"] = [dict(item) for item in cells]
        enriched_cells.append(enriched)

    all_have_fiscal_ordinals = bool(enriched_cells) and all(
        _structured_cell_fiscal_ordinal(cell) is not None for cell in enriched_cells
    )
    if all_have_fiscal_ordinals and period_focus in {"current", "prior"}:
        ordered = sorted(
            enriched_cells,
            key=lambda current: _structured_cell_fiscal_ordinal(current) or -1,
            reverse=True,
        )
        if period_focus == "current":
            return ordered[0]
        if len(ordered) >= 2:
            return ordered[1]
        return ordered[0]

    ranked_cells = sorted(
        enriched_cells,
        key=lambda cell: score_structured_cell(
            cell,
            query_years=operand_target_years(operand, query_years),
            period_focus=period_focus,
            operand=operand,
        ),
        reverse=True,
    )
    return ranked_cells[0] if ranked_cells else None


def candidate_selected_cell_for_operand(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> Optional[Dict[str, Any]]:
    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if not cells and candidate_kind in {"table_row", "evidence_row"}:
        cells = _parse_unstructured_table_row_cells(str(metadata.get("row_text") or ""), metadata)
    if not cells:
        return None
    cells = [{**cell, "_report_year": metadata.get("year")} for cell in cells]
    return select_structured_cell(
        cells,
        operand=operand,
        query_years=query_years,
        period_focus=period_focus,
    )


def select_aggregate_structured_cell(
    cells: List[Dict[str, Any]],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    period_focus: str,
) -> Optional[Dict[str, Any]]:
    if not cells:
        return None

    aggregate_tokens = tuple(
        str(item)
        for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_tokens") or ())
        if str(item)
    )

    def _cell_aggregate_rank(cell: Dict[str, Any]) -> Optional[float]:
        raw_value = _normalise_spaces(str(cell.get("value_text") or ""))
        raw_unit = _normalise_spaces(str(cell.get("unit_hint") or ""))
        normalized_value, _normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        if normalized_value is None:
            return None

        headers = [
            _normalise_spaces(str(item))
            for item in (cell.get("column_headers") or [])
            if _normalise_spaces(str(item))
        ]
        header_text = _normalise_spaces(" ".join(headers))
        value_role = _normalise_spaces(str(cell.get("value_role") or "")).lower()
        aggregation_stage = _normalise_spaces(str(cell.get("aggregation_stage") or "")).lower()
        aggregate_role = _normalise_spaces(str(cell.get("aggregate_role") or "")).lower()
        aggregate_label = _normalise_spaces(str(cell.get("aggregate_label") or ""))
        aggregate_surface = _normalise_spaces(" ".join([header_text, aggregate_label, aggregate_role]))
        aggregate_like = (
            value_role == "aggregate"
            or aggregation_stage in {"final", "direct", "subtotal"}
            or aggregate_role in {"direct_total", "subtotal", "final_total"}
            or bool(aggregate_label)
            or any(token in aggregate_surface for token in aggregate_tokens)
        )
        if not aggregate_like:
            return None

        score = score_structured_cell(
            cell,
            query_years=operand_target_years(operand, query_years),
            period_focus=period_focus,
            operand=operand,
        )
        if value_role == "aggregate":
            score += 6.0
        if aggregation_stage == "final":
            score += 5.0
        elif aggregation_stage == "direct":
            score += 4.5
        elif aggregation_stage == "subtotal":
            score += 3.0
        if aggregate_role in {"final_total", "direct_total"}:
            score += 2.0
        elif aggregate_role == "subtotal":
            score += 1.0
        if aggregate_label:
            score += 1.5
        if _operand_text_match(aggregate_surface, operand):
            score += 4.0
        try:
            score += min(float(cell.get("column_index") or 0), 100.0) / 1000.0
        except (TypeError, ValueError):
            pass
        return score

    ranked_cells: List[tuple[float, Dict[str, Any]]] = []
    for cell in cells:
        enriched = dict(cell)
        enriched["_sibling_cells"] = [dict(item) for item in cells]
        rank = _cell_aggregate_rank(enriched)
        if rank is None:
            continue
        ranked_cells.append((rank, enriched))
    if not ranked_cells:
        return None
    ranked_cells.sort(key=lambda item: item[0], reverse=True)
    return ranked_cells[0][1]


def _structured_cell_operand_affinity(cell: Dict[str, Any], operand: Dict[str, Any]) -> float:
    headers = [
        _normalise_spaces(str(item))
        for item in (cell.get("column_headers") or [])
        if _normalise_spaces(str(item))
    ]
    if not headers:
        return 0.0

    generic_headers = _generic_column_headers()
    non_generic_headers = [header for header in headers if header not in generic_headers]
    last_header = non_generic_headers[-1] if non_generic_headers else headers[-1]
    needles = [_normalise_spaces(needle) for needle in _operand_needles(operand) if _normalise_spaces(needle)]
    if not needles:
        return 0.0

    score = 0.0
    if any(last_header == needle for needle in needles):
        score += 4.0
    elif _operand_text_match(last_header, operand):
        score += 2.0

    if any(header == needle for header in headers for needle in needles):
        score += 0.75
    elif any(_operand_text_match(header, operand) for header in headers):
        score += 0.35

    row_label = _normalise_spaces(str(cell.get("row_label") or ""))
    operand_label = _normalise_spaces(str(operand.get("label") or operand.get("name") or ""))
    affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
    metric_terms = tuple(str(item) for item in (affinity_policy.get("metric_terms") or ()) if str(item))
    if row_label and operand_label and any(term in row_label for term in metric_terms) and any(
        term in operand_label for term in metric_terms
    ):
        entity_surface = operand_label
        entity_surface = re.sub(str(affinity_policy.get("year_pattern") or r"$^"), " ", entity_surface)
        for term in (*metric_terms, *(affinity_policy.get("entity_surface_drop_terms") or ())):
            entity_surface = entity_surface.replace(term, " ")
        entity_tokens = [
            token
            for token in re.split(str(affinity_policy.get("entity_token_split_pattern") or r"\s+"), _normalise_spaces(entity_surface))
            if token
        ]
        header_blob = _normalise_spaces(" ".join(headers))
        header_compact = re.sub(r"\s+", "", header_blob)
        if any(token in header_blob or token in header_compact for token in entity_tokens):
            score += 3.0

    aggregate_tokens = tuple(str(item) for item in (affinity_policy.get("aggregate_tokens") or ()) if str(item))
    if any(token in last_header for token in aggregate_tokens) and _operand_text_match(last_header, operand):
        score += 4.0

    return score


def score_structured_cell(
    cell: Dict[str, Any],
    *,
    query_years: List[int],
    period_focus: str,
    operand: Optional[Dict[str, Any]] = None,
) -> float:
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    header_text = " ".join(headers)
    score = 0.0
    if query_years:
        for index, year in enumerate(query_years):
            if str(year) in header_text:
                score += 10.0 - index
    period_policy = dict(STRUCTURED_CELL_PERIOD_SCORING_POLICY)
    if period_focus == "current":
        if any(token in header_text for token in period_policy.get("current_positive_markers") or ()):
            score += 4.0
        if any(token in header_text for token in period_policy.get("current_negative_markers") or ()):
            score -= 1.0
    elif period_focus == "prior":
        if any(token in header_text for token in period_policy.get("prior_positive_markers") or ()):
            score += 4.0
        if any(token in header_text for token in period_policy.get("prior_negative_markers") or ()):
            score -= 1.0
    if operand:
        score += _structured_cell_operand_affinity(cell, operand)
        binding_policy = dict(operand.get("binding_policy") or {})
        preferred_value_roles = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_value_roles") or [])
            if str(item).strip()
        }
        preferred_aggregation_stages = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_aggregation_stages") or [])
            if str(item).strip()
        }
        value_role = _normalise_spaces(str(cell.get("value_role") or ""))
        aggregation_stage = _normalise_spaces(str(cell.get("aggregation_stage") or ""))
        aggregate_role = _normalise_spaces(str(cell.get("aggregate_role") or ""))
        aggregate_label = _normalise_spaces(str(cell.get("aggregate_label") or ""))
        aggregate_tokens = tuple(
            str(item)
            for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_tokens") or ())
            if str(item)
        )
        aggregate_surface = _normalise_spaces(" ".join([header_text, aggregate_label, aggregate_role]))
        aggregate_like = (
            value_role == "aggregate"
            or aggregation_stage in {"final", "direct", "subtotal"}
            or aggregate_role in {"direct_total", "subtotal", "final_total"}
            or any(token in aggregate_surface for token in aggregate_tokens)
        )
        if aggregate_like:
            if "aggregate" in preferred_value_roles:
                score += 3.0
            if preferred_aggregation_stages and aggregation_stage in preferred_aggregation_stages:
                score += 2.0
            if not _normalise_spaces(str(operand.get("segment_label") or "")):
                score += 1.25
        elif preferred_value_roles and "aggregate" in preferred_value_roles and value_role == "detail":
            score -= 1.0
    if not header_text:
        score -= 0.25
    return score


def _structured_cell_fiscal_ordinal(cell: Dict[str, Any]) -> Optional[int]:
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    header_text = " ".join(headers)
    match = re.search(r"제\s*(\d+)\s*기", header_text)
    if not match:
        return None
    try:
        return int(match.group(1))
    except (TypeError, ValueError):
        return None


def _structured_cell_fiscal_rank(cell: Dict[str, Any]) -> Optional[int]:
    ordinal = _structured_cell_fiscal_ordinal(cell)
    if ordinal is None:
        return None
    ordinal_candidates = [ordinal]
    for sibling in list(cell.get("_sibling_cells") or []):
        sibling_ordinal = _structured_cell_fiscal_ordinal(dict(sibling))
        if sibling_ordinal is not None and sibling_ordinal not in ordinal_candidates:
            ordinal_candidates.append(sibling_ordinal)
    ordered = sorted(ordinal_candidates, reverse=True)
    try:
        return ordered.index(ordinal)
    except ValueError:
        return None


def _structured_cell_period_text(cell: Dict[str, Any], query_years: List[int], period_focus: str) -> str:
    focus_policy = dict(PERIOD_FOCUS_POLICY)
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    current_markers = tuple(str(item) for item in (focus_policy.get("current_markers") or ()) if str(item))
    prior_markers = tuple(str(item) for item in (focus_policy.get("prior_markers") or ()) if str(item))
    current_hint = str(period_policy.get("current_period_hint") or "current")
    prior_hint = str(period_policy.get("prior_period_hint") or "prior")
    headers = [str(item).strip() for item in (cell.get("column_headers") or []) if str(item).strip()]
    report_year: Optional[int] = None
    for raw_year in (cell.get("_report_year"), cell.get("report_year"), cell.get("year")):
        try:
            if raw_year not in (None, ""):
                report_year = int(raw_year)
                break
        except (TypeError, ValueError):
            continue
    if query_years:
        for year in query_years:
            year_text = str(year)
            if any(year_text in header for header in headers):
                return year_text
    header_text = " ".join(headers)
    if period_focus == "current" and any(token in header_text for token in current_markers):
        if report_year is not None:
            return str(report_year)
        return current_hint
    if period_focus == "prior" and any(token in header_text for token in prior_markers):
        if report_year is not None:
            return str(report_year - 1)
        return prior_hint
    fiscal_rank = _structured_cell_fiscal_rank(cell)
    if fiscal_rank is not None and (report_year is not None or query_years):
        current_year = report_year if report_year is not None else max(query_years)
        return str(current_year - fiscal_rank)
    return header_text
