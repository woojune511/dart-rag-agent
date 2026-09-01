"""Generic report-scope and consolidation helpers used during retrieval."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import CONSOLIDATION_SCOPE_POLICY


def is_scope_only_period_surface(surface: str, scope: Dict[str, Any]) -> bool:
    """Return whether a hint contributes only an already-declared period."""

    period_years = set(
        re.findall(r"(?:19|20)\d{2}", str(scope.get("period") or ""))
    )
    normalized = _normalise_spaces(str(surface or ""))
    surface_years = set(re.findall(r"(?:19|20)\d{2}", normalized))
    if not period_years or surface_years != period_years:
        return False
    residue = re.sub(r"(?:19|20)\d{2}", "", normalized)
    letters = "".join(character for character in residue if character.isalpha())
    return not letters or letters.lower() in {"fy", "year"} or len(letters) <= 2


def explicit_query_consolidation_scopes(query: str) -> List[str]:
    """Return only policy scopes whose markers are explicit in the query."""

    text = _normalise_spaces(query).lower()
    scopes: List[str] = []
    for scope, markers in dict(
        CONSOLIDATION_SCOPE_POLICY.get("query_markers") or {}
    ).items():
        if any(
            marker
            and marker in text
            for marker in (
                _normalise_spaces(str(item or "")).lower()
                for item in markers or ()
            )
        ):
            scopes.append(str(scope))
    return scopes


def desired_consolidation_scope(query: str, report_scope: Dict[str, Any]) -> str:
    """Resolve the requested reporting scope without inferring a calculation type."""

    text = _normalise_spaces(query)
    query_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("query_markers") or {})
    for scope, markers in query_markers.items():
        if any(str(marker) and str(marker) in text for marker in markers or ()):
            return str(scope)

    scope_value = _normalise_spaces(
        str((report_scope or {}).get("consolidation") or "")
    ).lower()
    metadata_values = dict(CONSOLIDATION_SCOPE_POLICY.get("metadata_values") or {})
    for scope, values in metadata_values.items():
        if scope_value in {str(value).lower() for value in values or ()}:
            return str(scope)

    default_markers = tuple(
        str(item)
        for item in CONSOLIDATION_SCOPE_POLICY.get("default_consolidated_markers") or ()
    )
    if any(marker in text for marker in default_markers):
        return "consolidated"
    return "unknown"


def _report_scope_source_reports(report_scope: Dict[str, Any]) -> List[Dict[str, Any]]:
    scope = dict(report_scope or {})
    rows: List[Dict[str, Any]] = []
    for key in ("source_reports", "report_inventory"):
        for item in list(scope.get(key) or []):
            current = dict(item or {})
            metadata = dict(current.get("metadata") or {})
            receipt_no = str(
                current.get("rcept_no")
                or current.get("receipt_no")
                or metadata.get("rcept_no")
                or ""
            ).strip()
            year_raw = current.get("year")
            if year_raw in (None, ""):
                year_raw = metadata.get("year")
            try:
                year = int(year_raw) if year_raw not in (None, "") else None
            except (TypeError, ValueError):
                year = None
            if not receipt_no and year is None:
                continue
            rows.append({"rcept_no": receipt_no, "year": year})
    return rows


def report_scope_source_receipts(report_scope: Dict[str, Any]) -> List[str]:
    receipts: List[str] = []
    for row in _report_scope_source_reports(report_scope):
        receipt_no = str(row.get("rcept_no") or "").strip()
        if receipt_no and receipt_no not in receipts:
            receipts.append(receipt_no)
    return receipts


def metadata_period_match_strength(
    period_labels: List[str],
    query_years: List[int],
) -> float:
    if not query_years or not period_labels:
        return 0.0
    normalized_labels = {
        str(label).strip() for label in period_labels if str(label).strip()
    }
    wanted = {str(year) for year in query_years}
    overlap = len(normalized_labels & wanted)
    if overlap <= 0:
        return 0.0
    if overlap >= len(wanted):
        return 1.0
    return overlap / max(len(wanted), 1)


def should_apply_strict_company_scope(
    companies: List[str],
    report_scope: Dict[str, Any],
) -> bool:
    if not companies:
        return False
    scope = dict(report_scope or {})
    if str(scope.get("rcept_no") or "").strip():
        return False
    if report_scope_source_receipts(scope):
        return False
    return True
