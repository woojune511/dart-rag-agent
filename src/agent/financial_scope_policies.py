"""Report-scope and consolidation policy helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import (
    CONSOLIDATION_SCOPE_POLICY,
    GENERIC_PERIOD_OPERAND_POLICY,
    PERIOD_FOCUS_POLICY,
    STRUCTURED_CELL_PERIOD_SCORING_POLICY,
)


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


def known_consolidation_scope_value(*values: Any) -> str:
    """Return the canonical known scope represented by the first matching value."""

    policy_values = {
        str(scope): tuple(str(marker).lower() for marker in (markers or ()) if str(marker))
        for scope, markers in dict(CONSOLIDATION_SCOPE_POLICY.get("metadata_values") or {}).items()
    }
    for value in values:
        scope = _normalise_spaces(str(value or "")).lower()
        if not scope:
            continue
        if scope in {"consolidated", "separate"}:
            return scope
        exact_scope = next(
            (
                candidate_scope
                for candidate_scope, markers in policy_values.items()
                if scope in markers
            ),
            "",
        )
        if exact_scope:
            return exact_scope
        marker_matches = [
            (len(marker), candidate_scope)
            for candidate_scope, markers in policy_values.items()
            for marker in markers
            if marker and marker in scope
        ]
        if marker_matches:
            return max(marker_matches)[1]
    return ""


def operand_target_years(operand: Dict[str, Any], query_years: List[int]) -> List[int]:
    hint = str(operand.get("period_hint") or "").strip()
    years: List[int] = []
    for token in re.findall(r"20\d{2}", f"{hint} {operand.get('label') or ''}"):
        year = int(token)
        if year not in years:
            years.append(year)
    if years:
        return years
    ordered_years: List[int] = []
    for raw_year in list(query_years or []):
        try:
            year = int(raw_year)
        except (TypeError, ValueError):
            continue
        if year not in ordered_years:
            ordered_years.append(year)
    if not ordered_years:
        return []

    period_focus = operand_period_focus(operand, "unknown")
    if period_focus == "current":
        return [max(ordered_years)]
    if period_focus == "prior":
        ranked_years = sorted(ordered_years, reverse=True)
        if len(ranked_years) >= 2:
            return [ranked_years[1]]
        return [ranked_years[0] - 1]
    return ordered_years


def operand_period_focus(operand: Dict[str, Any], default_period_focus: str) -> str:
    hint = str(operand.get("period_hint") or "").strip()
    role = str(operand.get("role") or "").strip()
    period_policy = dict(GENERIC_PERIOD_OPERAND_POLICY)
    current_hints = set(str(item) for item in (period_policy.get("current_period_hints") or ()) if str(item))
    prior_hints = set(str(item) for item in (period_policy.get("prior_period_hints") or ()) if str(item))
    if hint in current_hints or role == "current_period":
        return "current"
    if hint in prior_hints or role == "prior_period":
        return "prior"
    return default_period_focus


def query_period_focus(query: str, default_value: str = "unknown") -> str:
    text = _normalise_spaces(query)
    period_policy = dict(PERIOD_FOCUS_POLICY)
    if any(keyword in text for keyword in (period_policy.get("prior_markers") or ())):
        return "prior"
    if any(keyword in text for keyword in (period_policy.get("current_markers") or ())):
        return "current"
    explicit_years = list(dict.fromkeys(re.findall(str(period_policy.get("explicit_year_pattern") or r"$^"), text)))
    if len(explicit_years) == 1:
        return "current"
    return default_value or "unknown"


def task_period_focus_from_operands(
    operation_family: str,
    operand_specs: List[Dict[str, Any]],
    default_value: str,
) -> str:
    roles = {
        str(spec.get("role") or "").strip()
        for spec in operand_specs
        if str(spec.get("role") or "").strip()
    }
    if not roles:
        return default_value or "unknown"
    if operation_family in {"lookup", "single_value"}:
        if roles == {"current_period"}:
            return "current"
        if roles == {"prior_period"}:
            return "prior"
    if operation_family in {"difference", "growth_rate"}:
        if "current_period" in roles and "prior_period" in roles:
            return "multi_period"
        if roles == {"current_period"}:
            return "current"
        if roles == {"prior_period"}:
            return "prior"
    return default_value or "unknown"


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


def _operand_target_receipts(
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> List[str]:
    source_rows = _report_scope_source_reports(report_scope)
    if not source_rows:
        return []

    target_years = operand_target_years(operand, query_years)
    receipts: List[str] = []
    if target_years:
        for year in target_years:
            for row in source_rows:
                if row.get("year") == year:
                    receipt_no = str(row.get("rcept_no") or "").strip()
                    if receipt_no and receipt_no not in receipts:
                        receipts.append(receipt_no)
        if receipts:
            return receipts

    role = str(operand.get("role") or "").strip()
    year_ranked = [
        row for row in sorted(source_rows, key=lambda current: int(current.get("year") or -1), reverse=True)
        if row.get("year") is not None and str(row.get("rcept_no") or "").strip()
    ]
    if role == "current_period" and year_ranked:
        return [str(year_ranked[0].get("rcept_no") or "").strip()]
    if role == "prior_period" and len(year_ranked) >= 2:
        return [str(year_ranked[1].get("rcept_no") or "").strip()]
    return []


def _candidate_allows_comparative_report_scope_fallback(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> bool:
    source_rows = _report_scope_source_reports(report_scope)
    if len(source_rows) < 2:
        return False

    target_years = operand_target_years(operand, query_years)
    explicit_years = candidate_explicit_years(candidate)
    if not target_years or not explicit_years or not any(year in explicit_years for year in target_years):
        return False

    metadata = dict(candidate.get("metadata") or {})
    candidate_receipt = str(metadata.get("rcept_no") or "").strip()
    if not candidate_receipt:
        return False

    year_ranked = [
        row
        for row in sorted(source_rows, key=lambda current: int(current.get("year") or -1), reverse=True)
        if row.get("year") is not None and str(row.get("rcept_no") or "").strip()
    ]
    if not year_ranked:
        return False
    latest_receipt = str(year_ranked[0].get("rcept_no") or "").strip()
    if candidate_receipt != latest_receipt:
        return False

    role = str(operand.get("role") or "").strip()
    candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
    if role == "prior_period" and candidate_period_focus == "current":
        return False
    if role == "current_period" and candidate_period_focus == "prior":
        return False
    return True


def candidate_matches_target_report_scope(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> bool:
    source_rows = _report_scope_source_reports(report_scope)
    if not source_rows:
        return True

    metadata = dict(candidate.get("metadata") or {})
    candidate_receipt = str(metadata.get("rcept_no") or "").strip()
    candidate_year: Optional[int] = None
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            candidate_year = int(raw_year)
    except (TypeError, ValueError):
        candidate_year = None
    explicit_years = candidate_explicit_years(candidate)
    target_years = operand_target_years(operand, query_years)
    target_receipts = _operand_target_receipts(operand, query_years, report_scope)

    if target_receipts:
        if candidate_receipt:
            if candidate_receipt in target_receipts:
                return True
            if _candidate_allows_comparative_report_scope_fallback(
                candidate,
                operand=operand,
                query_years=query_years,
                report_scope=report_scope,
            ):
                return True
            return False
        if target_years and explicit_years and any(year in explicit_years for year in target_years):
            return True
        return False

    if target_years:
        if explicit_years:
            return any(year in explicit_years for year in target_years)
        if candidate_year is not None:
            return candidate_year in target_years
    return True


def candidate_report_scope_binding_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
    report_scope: Dict[str, Any],
) -> float:
    source_rows = _report_scope_source_reports(report_scope)
    if not source_rows:
        return 0.0

    metadata = dict(candidate.get("metadata") or {})
    candidate_receipt = str(metadata.get("rcept_no") or "").strip()
    explicit_years = candidate_explicit_years(candidate)
    candidate_year: Optional[int] = None
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            candidate_year = int(raw_year)
    except (TypeError, ValueError):
        candidate_year = None

    target_years = operand_target_years(operand, query_years)
    target_receipts = _operand_target_receipts(operand, query_years, report_scope)

    if target_receipts:
        if candidate_receipt:
            if candidate_receipt in target_receipts:
                return 3.0
            if _candidate_allows_comparative_report_scope_fallback(
                candidate,
                operand=operand,
                query_years=query_years,
                report_scope=report_scope,
            ):
                return 1.25
            return -3.0
        if explicit_years and target_years and any(year in explicit_years for year in target_years):
            return 1.0
        return -3.0

    if target_years:
        if explicit_years and any(year in explicit_years for year in target_years):
            return 1.0
        if candidate_year is not None and candidate_year in target_years:
            return 0.75
        if candidate_year is not None:
            return -0.75
    return 0.0


def candidate_matches_operand_target_year(
    candidate: Dict[str, Any],
    operand: Dict[str, Any],
    query_years: List[int],
) -> bool:
    target_years = operand_target_years(operand, query_years)
    if not target_years:
        return False

    explicit_years = candidate_explicit_years(candidate)
    if explicit_years and any(year in explicit_years for year in target_years):
        return True

    metadata = dict(candidate.get("metadata") or {})
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            candidate_year = int(raw_year)
            candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
            if candidate_period_focus == "prior":
                return (candidate_year - 1) in target_years
            if candidate_period_focus == "current":
                return candidate_year in target_years
            return candidate_year in target_years
    except (TypeError, ValueError):
        return False
    return False


def candidate_explicit_years(candidate: Dict[str, Any]) -> List[int]:
    metadata = dict(candidate.get("metadata") or {})
    years: set[int] = set()
    period_policy = dict(PERIOD_FOCUS_POLICY)
    scoring_policy = dict(STRUCTURED_CELL_PERIOD_SCORING_POLICY)
    year_pattern = str(period_policy.get("explicit_year_pattern") or r"20\d{2}")
    current_markers = tuple(str(item) for item in (scoring_policy.get("current_positive_markers") or ()) if str(item))
    prior_markers = tuple(str(item) for item in (scoring_policy.get("prior_positive_markers") or ()) if str(item))
    for raw in metadata.get("period_labels") or []:
        years.update(int(token) for token in re.findall(year_pattern, str(raw or "")))
    report_year: Optional[int] = None
    try:
        raw_year = metadata.get("year")
        if raw_year not in (None, ""):
            report_year = int(raw_year)
    except (TypeError, ValueError):
        report_year = None
    for cell in metadata.get("structured_cells") or []:
        cell_data = dict(cell or {})
        for raw in (
            str(cell_data.get("period_text") or ""),
            " ".join(str(item).strip() for item in (cell_data.get("column_headers") or []) if str(item).strip()),
        ):
            years.update(int(token) for token in re.findall(year_pattern, raw))
        if report_year is None:
            continue
        period_headers = _normalise_spaces(
            " ".join(str(item).strip() for item in (cell_data.get("column_headers") or []) if str(item).strip())
        )
        if not period_headers:
            continue
        if any(token in period_headers for token in current_markers):
            years.add(report_year)
        if any(token in period_headers for token in prior_markers):
            years.add(report_year - 1)
    return sorted(years)


def candidate_period_table_coherence_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
) -> float:
    metadata = dict(candidate.get("metadata") or {})
    years = candidate_explicit_years(candidate)
    if not years:
        return 0.0

    score = 0.0
    target_years = operand_target_years(operand, query_years)
    if target_years:
        if any(year in years for year in target_years):
            score += 1.0
        else:
            score -= 1.0

    role = str(operand.get("role") or "").strip()
    if role in {"current_period", "prior_period"} and len(years) >= 2:
        score += 0.75
        if str(metadata.get("table_source_id") or "").strip():
            score += 0.35

    desired_unit_family = str(operand.get("unit_family") or "").strip().upper()
    if desired_unit_family == "PERCENT" and len(years) >= 2:
        score += 0.5

    return score


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
