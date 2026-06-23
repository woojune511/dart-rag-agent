"""Structured table-cell period helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.config.retrieval_policy import GENERIC_PERIOD_OPERAND_POLICY, PERIOD_FOCUS_POLICY


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
