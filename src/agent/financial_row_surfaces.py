"""Row and table text-surface helpers for financial runtime paths."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_surface_contracts import _operand_needles
from src.config.retrieval_policy import HELPER_RUNTIME_POLICY


def _strip_financial_label_annotations(text: str) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    # Strip footnote-style parentheticals such as "(주25)" or "(*)", but keep
    # other semantic qualifiers intact.
    normalized = re.sub(r"\((?:주\s*\d+[^\)]*|\*)\)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _strip_leading_period_qualifiers(text: str) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    pattern = re.compile(
        r"^(?:(?:20\d{2}\s*년?)|(?:제\s*\d+\s*기)|(?:당기|전기|현재|이전|직전|이번|금년)(?:\s*연도)?)(?:\s+|$)"
    )
    stripped = normalized
    while True:
        updated = pattern.sub("", stripped, count=1).strip()
        if updated == stripped:
            break
        stripped = updated
    return stripped


def _surface_match_variants(text: str) -> List[str]:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return []
    variants = [
        normalized,
        _strip_financial_label_annotations(normalized),
        _strip_leading_period_qualifiers(normalized),
        _strip_leading_period_qualifiers(_strip_financial_label_annotations(normalized)),
    ]
    return list(dict.fromkeys(item for item in variants if item))


def _operand_text_match(text: str, operand: Dict[str, Any]) -> bool:
    haystack_variants = _surface_match_variants(text)
    if not haystack_variants:
        return False
    for haystack in haystack_variants:
        haystack_compact = re.sub(r"\s+", "", haystack)
        for needle in _operand_needles(operand):
            for normalized_needle in _surface_match_variants(needle):
                needle_compact = re.sub(r"\s+", "", normalized_needle)
                if (
                    haystack == normalized_needle
                    or normalized_needle in haystack
                    or (needle_compact and needle_compact in haystack_compact)
                ):
                    return True
    return False


_NUMERIC_VALUE_AFTER_OPERAND_PATTERN = re.compile(
    r"[\d,]+(?:\.\d+)?\s*조(?:\s*[\d,]+(?:\.\d+)?\s*억(?:원)?)?"
    r"|[\d,]+(?:\.\d+)?\s*(?:조|억|백만|천)\s*원?"
    r"|[\d,]+(?:\.\d+)?\s*원"
    r"|[\d,]+(?:\.\d+)?"
)


def _parenthetical_exact_value_after_numeric_surface(
    normalized: str,
    value_text: str,
    end: int,
) -> str:
    compact_value = re.sub(r"\s+", "", value_text or "")
    if not any(unit in compact_value for unit in ("조", "억")):
        return ""
    tail = normalized[end : end + 40]
    exact_match = re.match(
        r"\s*\(\s*(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>백\s*만\s*원|천\s*원|원)\s*\)",
        tail,
    )
    if not exact_match:
        return ""
    unit = re.sub(r"\s+", "", exact_match.group("unit"))
    return f"{exact_match.group('value')}{unit}"


def _parenthetical_unit_after_numeric_surface(
    normalized: str,
    value_text: str,
    end: int,
) -> str:
    if re.search(r"(?:조|억|백만|천)\s*원?|원", value_text or ""):
        return ""
    tail = normalized[end : end + 24]
    unit_match = re.match(
        r"\s*\(\s*(?P<unit>조\s*원|억\s*원|백\s*만\s*원|천\s*원|원)\s*\)",
        tail,
    )
    if not unit_match:
        return ""
    unit = re.sub(r"\s+", "", unit_match.group("unit"))
    return f"{_normalise_spaces(value_text)}{unit}"


def _numeric_operand_value_from_match(
    normalized: str,
    match: re.Match[str],
    absolute_end: int,
) -> str:
    exact_parenthetical = _parenthetical_exact_value_after_numeric_surface(
        normalized,
        match.group(0),
        absolute_end,
    )
    if exact_parenthetical:
        return exact_parenthetical
    parenthetical_unit = _parenthetical_unit_after_numeric_surface(
        normalized,
        match.group(0),
        absolute_end,
    )
    if parenthetical_unit:
        return parenthetical_unit
    return _normalise_spaces(match.group(0))


def _valid_numeric_operand_value_matches(surface: str) -> List[re.Match[str]]:
    return [
        match
        for match in _NUMERIC_VALUE_AFTER_OPERAND_PATTERN.finditer(surface)
        if re.search(r"\d", match.group(0))
    ]


def _recent_parenthetical_exact_value_before_operand(normalized: str, end: int) -> str:
    context = normalized[max(0, end - 140) : end]
    exact_matches = list(
        re.finditer(
            r"[\d,]+(?:\.\d+)?\s*(?:조|억)(?:\s*[\d,]+(?:\.\d+)?\s*억)?\s*원?"
            r"\s*\(\s*(?P<value>[\d,]+(?:\.\d+)?)\s*(?P<unit>백\s*만\s*원|천\s*원|원)\s*\)",
            context,
        )
    )
    if not exact_matches:
        return ""
    exact_match = exact_matches[-1]
    unit = re.sub(r"\s+", "", exact_match.group("unit"))
    return f"{exact_match.group('value')}{unit}"


def _numeric_operand_candidates_near_match(
    normalized: str,
    match: re.Match[str],
) -> List[tuple[int, str]]:
    candidates: List[tuple[int, str]] = []
    prefix = normalized[: match.start()]
    prefix_matches = _valid_numeric_operand_value_matches(prefix)
    if prefix_matches:
        nearest = prefix_matches[-1]
        if match.start() - nearest.end() <= 20:
            exact_parenthetical = _parenthetical_exact_value_after_numeric_surface(
                normalized,
                nearest.group(0),
                nearest.end(),
            )
            if exact_parenthetical:
                candidates.append((match.start() - nearest.end(), exact_parenthetical))
            else:
                recent_exact_parenthetical = _recent_parenthetical_exact_value_before_operand(
                    normalized,
                    match.start(),
                )
                if recent_exact_parenthetical:
                    candidates.append((match.start() - nearest.end(), recent_exact_parenthetical))
                else:
                    candidates.append(
                        (
                            match.start() - nearest.end(),
                            _numeric_operand_value_from_match(normalized, nearest, nearest.end()),
                        )
                    )
    suffix = normalized[match.end() :]
    suffix_matches = _valid_numeric_operand_value_matches(suffix)
    if suffix_matches:
        value_match = suffix_matches[0]
        absolute_end = match.end() + value_match.end()
        candidates.append(
            (
                value_match.start(),
                _numeric_operand_value_from_match(normalized, value_match, absolute_end),
            )
        )
    return candidates


def _extract_numeric_value_after_operand_text(text: str, operand: Dict[str, Any]) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    for needle in _operand_needles(operand):
        compact = re.sub(r"\s+", "", _normalise_spaces(needle))
        if not compact:
            continue
        spaced_pattern = r"\s*".join(re.escape(char) for char in compact)
        match = re.search(spaced_pattern, normalized)
        if not match:
            continue
        candidates = _numeric_operand_candidates_near_match(normalized, match)
        if candidates:
            return sorted(candidates, key=lambda item: item[0])[0][1]
    return ""


def _extract_table_row_label(row_text: str) -> str:
    normalized = _normalise_spaces(row_text)
    if not normalized:
        return ""
    if "|" in normalized:
        first_cell = _normalise_spaces(normalized.split("|", 1)[0])
        if first_cell:
            return first_cell
    return normalized


def _parse_unstructured_table_row_cells(row_text: str, metadata: Dict[str, Any]) -> List[Dict[str, Any]]:
    normalized_row = _normalise_spaces(str(row_text or ""))
    if "|" not in normalized_row:
        return []
    row_parts = [part.strip() for part in normalized_row.split("|")]
    row_parts = [part for part in row_parts if part]
    if len(row_parts) <= 1:
        return []

    header_text = _normalise_spaces(str(metadata.get("table_header_context") or ""))
    header_parts = [part.strip() for part in header_text.split("|") if part.strip()] if "|" in header_text else []
    period_labels = [str(item).strip() for item in (metadata.get("period_labels") or []) if str(item).strip()]

    value_parts = row_parts[1:]
    header_candidates = header_parts[-len(value_parts):] if len(header_parts) >= len(value_parts) else []
    if not header_candidates and len(period_labels) >= len(value_parts):
        header_candidates = period_labels[-len(value_parts):]
    if not header_candidates:
        header_candidates = [f"col_{index}" for index in range(1, len(value_parts) + 1)]

    cells: List[Dict[str, Any]] = []
    for header, value in zip(header_candidates, value_parts):
        raw_value = str(value).strip()
        if not raw_value or not re.search(r"[0-9]", raw_value):
            continue
        value_headers = [str(header).strip()] if str(header).strip() else []
        unit_hint = str(metadata.get("unit_hint") or "").strip()
        labeled_value_match = re.match(
            r"^(?P<label>.*?)(?P<value>[\(\)\-]?\d[\d,]*(?:\.\d+)?)\s*"
            r"(?P<unit>백만원|천원|억원|원|%|퍼센트)?$",
            raw_value,
        )
        if labeled_value_match:
            label = _normalise_spaces(labeled_value_match.group("label") or "")
            if label:
                value_headers.append(label)
            raw_value = _normalise_spaces(labeled_value_match.group("value") or raw_value)
            unit_hint = _normalise_spaces(labeled_value_match.group("unit") or unit_hint)
        cells.append(
            {
                "column_headers": value_headers,
                "row_label": row_parts[0],
                "value_text": raw_value,
                "unit_hint": unit_hint,
            }
        )
    return cells


def _format_structured_candidate_row_text(
    label: str,
    headers: List[str],
    cells: List[Dict[str, Any]],
) -> str:
    row_parts: List[str] = []
    for part in [label, *headers]:
        cleaned = _normalise_spaces(str(part or ""))
        if cleaned and cleaned not in row_parts:
            row_parts.append(cleaned)
    for cell in cells:
        cell_parts = [
            " / ".join(
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            ),
            _normalise_spaces(str(cell.get("value_text") or "")),
            _normalise_spaces(str(cell.get("unit_hint") or "")),
        ]
        cleaned_cell = _normalise_spaces(" ".join(part for part in cell_parts if part))
        if cleaned_cell:
            row_parts.append(cleaned_cell)
    return " | ".join(row_parts)


def _generic_column_headers() -> set[str]:
    return set(str(item) for item in (HELPER_RUNTIME_POLICY.get("generic_column_headers") or ()) if str(item))
