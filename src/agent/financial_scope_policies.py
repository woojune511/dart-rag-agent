"""Report-scope and consolidation policy helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import CONSOLIDATION_SCOPE_POLICY


def _desired_consolidation_scope(query: str, report_scope: Dict[str, Any]) -> str:
    text = _normalise_spaces(query)
    query_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("query_markers") or {})
    for scope, markers in query_markers.items():
        if any(str(marker) and str(marker) in text for marker in markers or ()):
            return str(scope)
    scope_value = _normalise_spaces(str((report_scope or {}).get("consolidation") or "")).lower()
    metadata_values = dict(CONSOLIDATION_SCOPE_POLICY.get("metadata_values") or {})
    for scope, values in metadata_values.items():
        if scope_value in {str(value).lower() for value in values or ()}:
            return str(scope)
    default_markers = tuple(str(item) for item in (CONSOLIDATION_SCOPE_POLICY.get("default_consolidated_markers") or ()))
    if any(marker in text for marker in default_markers):
        return "consolidated"
    return "unknown"


def _report_scope_source_reports(report_scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    scope = dict(report_scope or {})
    rows: List[Dict[str, Any]] = []
    for key in ("source_reports", "report_inventory"):
        for item in list(scope.get(key) or []):
            current = dict(item or {})
            receipt_no = str(
                current.get("rcept_no")
                or current.get("receipt_no")
                or str((current.get("metadata") or {}).get("rcept_no") or "")
            ).strip()
            year_raw = current.get("year")
            if year_raw in (None, ""):
                year_raw = (current.get("metadata") or {}).get("year")
            try:
                year = int(year_raw) if year_raw not in (None, "") else None
            except (TypeError, ValueError):
                year = None
            if not receipt_no and year is None:
                continue
            rows.append(
                {
                    "rcept_no": receipt_no,
                    "year": year,
                    "report_type": str(
                        current.get("report_type")
                        or current.get("report_nm")
                        or (current.get("metadata") or {}).get("report_type")
                        or ""
                    ).strip(),
                }
            )
    return rows


def _report_scope_source_receipts(report_scope: Dict[str, Any]) -> List[str]:
    receipts: List[str] = []
    for row in _report_scope_source_reports(report_scope):
        receipt_no = str(row.get("rcept_no") or "").strip()
        if receipt_no and receipt_no not in receipts:
            receipts.append(receipt_no)
    return receipts


def _metadata_period_match_strength(period_labels: List[str], query_years: List[int]) -> float:
    if not query_years or not period_labels:
        return 0.0
    normalized_labels = {str(label).strip() for label in period_labels if str(label).strip()}
    wanted = {str(year) for year in query_years}
    overlap = len(normalized_labels & wanted)
    if overlap <= 0:
        return 0.0
    if overlap >= len(wanted):
        return 1.0
    return overlap / max(len(wanted), 1)


def _extract_period_sort_key(period: str) -> int:
    text = _normalise_spaces(period)
    year_match = re.search(r"(19|20)\d{2}", text)
    if year_match:
        return int(year_match.group(0))
    if "당기" in text:
        return 9999
    if "전기" in text:
        return 9998
    return -1


def _extract_year_tokens(query: str, report_scope: Dict[str, Any]) -> List[int]:
    years: List[int] = []
    for token in re.findall(r"(20\d{2})년", str(query or "")):
        year = int(token)
        if year not in years:
            years.append(year)
    scope_year_raw = report_scope.get("year")
    try:
        if scope_year_raw not in (None, ""):
            scope_year = int(scope_year_raw)
            if scope_year not in years:
                years.insert(0, scope_year)
    except (TypeError, ValueError):
        pass
    for row in _report_scope_source_reports(report_scope):
        year_raw = row.get("year")
        if year_raw in (None, ""):
            year_raw = dict(row.get("metadata") or {}).get("year")
        try:
            year = int(year_raw)
        except (TypeError, ValueError):
            continue
        if year not in years:
            years.append(year)
    return years


def _should_apply_strict_company_scope(companies: List[str], report_scope: Dict[str, Any]) -> bool:
    if not companies:
        return False
    scope = dict(report_scope or {})
    scope_rcept_no = str(scope.get("rcept_no") or "").strip()
    if scope_rcept_no:
        return False
    if _report_scope_source_receipts(scope):
        return False
    return True
