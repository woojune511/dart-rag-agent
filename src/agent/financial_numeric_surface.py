"""Shared numeric surface helpers for runtime evidence and evaluation."""

from __future__ import annotations

import re
from typing import Any, Callable, Dict, Iterable, List, Optional

from src.agent.financial_runtime_normalization import _normalise_spaces, _parse_number_text
from src.config.retrieval_policy import CALCULATION_RENDER_POLICY, NUMERIC_UNIT_NORMALIZATION_POLICY


def _numeric_unit_terms() -> tuple[Dict[str, float], List[str], List[str]]:
    render_policy = dict(CALCULATION_RENDER_POLICY)
    unit_scale = {
        str(unit): float(scale)
        for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
        if str(unit)
    }
    percent_units = [
        str(unit)
        for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())
        if str(unit)
    ]
    unit_terms = sorted([*unit_scale.keys(), *percent_units], key=len, reverse=True)
    return unit_scale, percent_units, unit_terms


def _mixed_currency_surface_candidates(
    text: str,
    *,
    unit_scale: Dict[str, float],
    magnitude_markers: List[str],
) -> tuple[List[Dict[str, Any]], List[tuple[int, int]]]:
    candidates: List[Dict[str, Any]] = []
    skip_spans: List[tuple[int, int]] = []
    major_marker = magnitude_markers[-1] if magnitude_markers else ""
    minor_marker = magnitude_markers[0] if magnitude_markers else ""
    major_unit = next((unit for unit in unit_scale if major_marker and major_marker in unit), "")
    minor_unit = next((unit for unit in unit_scale if minor_marker and minor_marker in unit), "")
    if not (major_marker and major_unit and minor_unit):
        return candidates, skip_spans
    mixed_pattern = re.compile(
        rf"(?P<major>\(?-?\d[\d,]*(?:\.\d+)?\)?)\s*{re.escape(major_marker)}\s+"
        rf"(?P<minor>\d[\d,]*(?:\.\d+)?)\s*{re.escape(minor_unit)}"
    )
    for match in mixed_pattern.finditer(str(text or "")):
        major = _parse_number_text(str(match.group("major") or "").strip("()"))
        minor = _parse_number_text(str(match.group("minor") or "").strip("()"))
        if major is None or minor is None:
            continue
        candidates.append(
            {
                "kind": "currency",
                "value": major * unit_scale[major_unit] + minor * unit_scale[minor_unit],
                "unit": f"{major_marker}+{minor_unit}",
                "display_step": unit_scale[minor_unit],
                "text": _normalise_spaces(match.group(0)),
                "span": match.span(),
            }
        )
        skip_spans.append(match.span())
    return candidates, skip_spans


def _numeric_surface_pattern(unit_terms: List[str]) -> re.Pattern[str]:
    unit_pattern = "|".join(re.escape(unit) for unit in unit_terms)
    if unit_pattern:
        return re.compile(
            rf"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)(?:\s*(?P<unit>{unit_pattern}))?"
        )
    return re.compile(r"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)")


def _numeric_surface_candidate_from_match(
    match: re.Match[str],
    *,
    unit_scale: Dict[str, float],
    percent_units: List[str],
    context_unit: str,
) -> Dict[str, Any]:
    raw_value = match.group("value")
    unit = match.groupdict().get("unit") or ""
    parsed = _parse_number_text(raw_value)
    if parsed is None:
        return {}
    candidate_text = _normalise_spaces(match.group(0))
    digit_count = len(re.sub(r"\D", "", raw_value))
    if not unit and digit_count == 4 and 1900 <= abs(parsed) <= 2100:
        return {}
    if unit in set(percent_units):
        return {
            "kind": "percent",
            "value": parsed,
            "unit": unit,
            "display_step": 0.01 if "." in raw_value else 1.0,
            "text": candidate_text,
            "span": match.span(),
        }
    if unit in unit_scale:
        return {
            "kind": "currency",
            "value": parsed * unit_scale[unit],
            "unit": unit,
            "display_step": unit_scale[unit],
            "text": candidate_text,
            "span": match.span(),
        }
    if context_unit and digit_count >= 4:
        return {
            "kind": "currency",
            "value": parsed * unit_scale[context_unit],
            "unit": context_unit,
            "display_step": unit_scale[context_unit],
            "text": candidate_text,
            "span": match.span(),
        }
    if digit_count >= 4:
        return {
            "kind": "generic",
            "value": parsed,
            "unit": unit,
            "display_step": 1.0,
            "text": candidate_text,
            "span": match.span(),
        }
    return {}


def extract_numeric_surface_candidates(text: str) -> List[Dict[str, Any]]:
    render_policy = dict(CALCULATION_RENDER_POLICY)
    unit_scale, percent_units, unit_terms = _numeric_unit_terms()
    magnitude_markers = [
        _normalise_spaces(str(marker))
        for marker in (render_policy.get("krw_value_magnitude_markers") or ())
        if _normalise_spaces(str(marker))
    ]
    candidates, skip_spans = _mixed_currency_surface_candidates(
        str(text or ""),
        unit_scale=unit_scale,
        magnitude_markers=magnitude_markers,
    )
    pattern = _numeric_surface_pattern(unit_terms)
    text_surface = str(text or "")
    context_unit = next((unit for unit in unit_terms if unit in unit_scale and unit in text_surface), "")
    for match in pattern.finditer(text_surface):
        if any(start <= match.start() < end for start, end in skip_spans):
            continue
        candidate = _numeric_surface_candidate_from_match(
            match,
            unit_scale=unit_scale,
            percent_units=percent_units,
            context_unit=context_unit,
        )
        if candidate:
            candidates.append(candidate)
    return candidates


def numeric_surface_candidates_equivalent(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    if str(left.get("kind") or "") != str(right.get("kind") or ""):
        return False
    try:
        left_value = float(left.get("value"))
        right_value = float(right.get("value"))
    except (TypeError, ValueError):
        return False
    kind = str(left.get("kind") or "")
    if kind == "currency":
        left_value = abs(left_value)
        right_value = abs(right_value)
        tolerance = max(
            abs(left_value) * 5e-4,
            float(left.get("display_step") or 1.0),
            float(right.get("display_step") or 1.0),
        )
    elif kind == "percent":
        tolerance = max(
            0.06,
            float(left.get("display_step") or 0.01) / 2.0,
            float(right.get("display_step") or 0.01) / 2.0,
        )
    else:
        tolerance = max(abs(left_value) * 1e-6, 0.5)
    return abs(left_value - right_value) <= tolerance


def numeric_surface_slot_components(candidate: Dict[str, Any]) -> Dict[str, Any]:
    value_text = _normalise_spaces(str(candidate.get("text") or ""))
    unit = _normalise_spaces(str(candidate.get("unit") or ""))
    raw_value = value_text
    if unit and raw_value.endswith(unit):
        raw_value = _normalise_spaces(raw_value[: -len(unit)])
    if not raw_value or candidate.get("value") is None:
        return {}
    kind = str(candidate.get("kind") or "")
    normalized_unit = "KRW" if kind == "currency" else "PERCENT" if kind == "percent" else "UNKNOWN"
    return {
        "raw_value": raw_value,
        "raw_unit": unit,
        "normalized_value": candidate.get("value"),
        "normalized_unit": normalized_unit,
        "rendered_value": value_text,
    }


def table_value_label_surfaces_with_unit_hint(table_value_labels: str, unit_hint: str) -> List[str]:
    cleaned_unit = _normalise_spaces(str(unit_hint or ""))
    if not cleaned_unit:
        return []
    percent_units = {str(unit) for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())}
    surfaces: List[str] = []
    for line in str(table_value_labels or "").splitlines():
        cleaned_line = _normalise_spaces(line)
        if not cleaned_line:
            continue
        for match in re.finditer(r"(?P<value>[\(\)\-+△]?\s*\d[\d,]*(?:\.\d+)?%?(?:\s*%p)?)", cleaned_line):
            value_text = _normalise_spaces(match.group("value"))
            if not value_text:
                continue
            if any(unit and unit in value_text for unit in percent_units):
                surfaces.append(value_text)
            else:
                surfaces.append(f"{value_text}{cleaned_unit}")
    return surfaces


def table_value_labels_text_with_unit_hint(table_value_labels: str, unit_hint: str) -> str:
    cleaned_unit = _normalise_spaces(str(unit_hint or ""))
    if not cleaned_unit:
        return ""
    table_lines: List[str] = []
    for line in str(table_value_labels or "").splitlines():
        def _append_unit(match: re.Match[str]) -> str:
            value_text = _normalise_spaces(str(match.group(0) or ""))
            if not value_text or "%" in value_text or cleaned_unit in value_text:
                return value_text
            return f"{value_text}{cleaned_unit}"

        table_lines.append(
            re.sub(r"[\(\)\-+△]?\s*\d[\d,]*(?:\.\d+)?%?(?:\s*%p)?", _append_unit, line)
        )
    return "\n".join(table_lines)


def evidence_text_for_numeric_support(
    evidence: Dict[str, Any],
    *,
    structured_table_formatter: Optional[Callable[[Dict[str, Any]], str]] = None,
    include_table_headers: bool = True,
) -> str:
    metadata = dict((evidence or {}).get("metadata") or {})
    table_value_labels = str(metadata.get("table_value_labels_text") or "").strip()
    table_value_labels_with_units = table_value_labels_text_with_unit_hint(
        table_value_labels,
        str(metadata.get("unit_hint") or "").strip(),
    )
    structured_table_text = structured_table_formatter(metadata) if structured_table_formatter else ""
    header_parts: Iterable[str] = (
        metadata.get("table_header_context"),
        metadata.get("table_summary_text"),
    ) if include_table_headers else ()
    return _normalise_spaces(
        " ".join(
            str(value or "").strip()
            for value in (
                evidence.get("claim"),
                evidence.get("quote_span"),
                evidence.get("raw_row_text"),
                evidence.get("source_context"),
                metadata.get("table_value_labels_text"),
                table_value_labels_with_units,
                *header_parts,
                structured_table_text,
            )
            if str(value or "").strip()
        )
    )


def evidence_numeric_display_candidates(
    evidence_items: List[Dict[str, Any]],
    evidence_surface: str = "",
) -> List[Dict[str, Any]]:
    candidates = extract_numeric_surface_candidates(evidence_surface)
    for item in evidence_items or []:
        if not isinstance(item, dict):
            continue
        metadata = dict(item.get("metadata") or {})
        for display_text in table_value_label_surfaces_with_unit_hint(
            str(metadata.get("table_value_labels_text") or ""),
            str(metadata.get("unit_hint") or ""),
        ):
            for candidate in extract_numeric_surface_candidates(display_text):
                candidate["text"] = display_text
                candidates.append(candidate)
    return candidates


def runtime_evidence_numeric_candidates(
    runtime_evidence: List[Dict[str, Any]],
    *,
    text_candidate_extractor: Callable[[str], List[Dict[str, Any]]],
    unitless_candidate_extractor: Optional[Callable[[str, str], List[Dict[str, Any]]]] = None,
    structured_table_formatter: Optional[Callable[[Dict[str, Any]], str]] = None,
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for row in list(runtime_evidence or []):
        if not isinstance(row, dict):
            continue
        evidence_text = evidence_text_for_numeric_support(
            row,
            structured_table_formatter=structured_table_formatter,
            include_table_headers=False,
        )
        if not evidence_text:
            continue
        row_candidates = list(text_candidate_extractor(evidence_text))
        if unitless_candidate_extractor:
            for kind in ("currency", "percent", "ratio"):
                row_candidates.extend(unitless_candidate_extractor(evidence_text, kind))
        candidates.extend(row_candidates)
    return candidates
