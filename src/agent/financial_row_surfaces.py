"""Row and table text-surface helpers for financial runtime paths."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_surface_contracts import (
    _operand_needles,
    operand_segment_label,
    _text_has_positive_surface,
    candidate_matches_segment_binding,
)
from src.config.retrieval_policy import (
    HELPER_RUNTIME_POLICY,
    OPERAND_CANDIDATE_SCORING_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
)


def _strip_financial_label_annotations(text: str) -> str:
    normalized = _normalise_spaces(text or "")
    if not normalized:
        return ""
    # Strip footnote-style parentheticals such as "(주25)" or "(*)", but keep
    # other semantic qualifiers intact.
    normalized = re.sub(r"\((?:주\s*\d+[^\)]*|\*)\)", "", normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def is_delta_like_row_label(label: str) -> bool:
    text = _normalise_spaces(str(label or ""))
    if not text:
        return False
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    delta_markers = tuple(str(item) for item in (scoring_policy.get("delta_row_markers") or ()) if str(item))
    return any(token in text for token in delta_markers)


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


def column_candidate_label(column_headers: List[str]) -> str:
    cleaned = [_normalise_spaces(header) for header in column_headers if _normalise_spaces(header)]
    if not cleaned:
        return ""
    generic_headers = _generic_column_headers()
    filtered = [header for header in cleaned if header not in generic_headers]
    target = filtered[-1] if filtered else cleaned[-1]
    if re.fullmatch(r"20\d{2}(?:년)?", target):
        return ""
    return target


def aggregate_like_row_stage(label: str) -> str:
    compact = re.sub(r"\s+", "", _normalise_spaces(str(label or "")))
    if not compact:
        return "none"
    affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
    aggregate_stage_tokens = dict(affinity_policy.get("aggregate_stage_tokens") or {})
    for stage, tokens in aggregate_stage_tokens.items():
        if compact in {re.sub(r"\s+", "", _normalise_spaces(str(token))) for token in tokens}:
            return str(stage)
    return "none"


def aggregate_like_row_role(label: str) -> str:
    return "aggregate" if aggregate_like_row_stage(label) != "none" else "detail"


def candidate_value_role(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    explicit = _normalise_spaces(str(metadata.get("value_role") or ""))
    if explicit:
        return explicit
    aggregate_role = _normalise_spaces(str(metadata.get("aggregate_role") or ""))
    if aggregate_role == "adjustment":
        return "adjustment"
    if aggregate_role in {"direct_total", "subtotal", "final_total"}:
        return "aggregate"
    inferred_role = aggregate_like_row_role(
        str(metadata.get("row_label") or metadata.get("semantic_label") or "")
    )
    if inferred_role == "aggregate":
        return inferred_role
    return "detail"


def candidate_aggregation_stage(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    explicit = _normalise_spaces(str(metadata.get("aggregation_stage") or ""))
    if explicit:
        return explicit
    aggregate_role = _normalise_spaces(str(metadata.get("aggregate_role") or ""))
    if aggregate_role == "direct_total":
        return "direct"
    if aggregate_role == "subtotal":
        return "subtotal"
    if aggregate_role == "final_total":
        return "final"
    inferred_stage = aggregate_like_row_stage(
        str(metadata.get("row_label") or metadata.get("semantic_label") or "")
    )
    if inferred_stage != "none":
        return inferred_stage
    return "none"


def candidate_has_operand_context_surface(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    context_text = " ".join(
        str(part or "").strip()
        for part in (
            " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
            " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
            str(metadata.get("table_row_labels_text") or ""),
            str(metadata.get("table_summary_text") or ""),
            str(metadata.get("row_text") or ""),
            str(candidate.get("text") or ""),
        )
        if str(part or "").strip()
    )
    return _text_has_positive_surface(context_text, operand) or _operand_text_match(context_text, operand)


def table_row_has_matching_structured_sibling(metadata: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    for key in ("table_row_records_json", "table_value_records_json"):
        payload = str(metadata.get(key) or "").strip()
        if not payload:
            continue
        try:
            records = json.loads(payload)
        except json.JSONDecodeError:
            continue
        for record in records:
            surfaces = [
                str(record.get("row_label") or "").strip(),
                str(record.get("semantic_label") or "").strip(),
                " ".join(str(item).strip() for item in (record.get("row_headers") or []) if str(item).strip()),
                " ".join(str(item).strip() for item in (record.get("semantic_aliases") or []) if str(item).strip()),
            ]
            if any(_operand_text_match(surface, operand) for surface in surfaces if surface):
                return True
    return False


def candidate_has_segment_local_binding(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    segment_label = operand_segment_label(operand)
    if not segment_label:
        return True
    if candidate_matches_segment_binding(candidate, operand, strict=True):
        return True
    return candidate_supports_segment_metric_combo(candidate, operand)


def candidate_supports_segment_metric_combo(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    segment_label = operand_segment_label(operand)
    if not segment_label:
        return False
    if not candidate_matches_segment_binding(candidate, operand, strict=True):
        return False

    metadata = dict(candidate.get("metadata") or {})
    metric_surfaces = [
        str(metadata.get("table_row_labels_text") or "").strip(),
        str(metadata.get("table_context") or "").strip(),
        str(metadata.get("table_summary_text") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
    ]
    return any(_operand_text_match(surface, operand) for surface in metric_surfaces if surface)


def candidate_sibling_surface_hit_count(candidate: Dict[str, Any], sibling_surfaces: List[str]) -> int:
    if not sibling_surfaces:
        return 0
    metadata = dict(candidate.get("metadata") or {})
    haystack = _normalise_spaces(
        " ".join(
            part
            for part in (
                str(metadata.get("table_row_labels_text") or ""),
                str(metadata.get("table_value_labels_text") or ""),
                str(metadata.get("table_summary_text") or ""),
                str(metadata.get("row_context_text") or ""),
                str(metadata.get("row_text") or ""),
                str(candidate.get("text") or ""),
            )
            if part
        )
    )
    if not haystack:
        return 0
    compact_haystack = re.sub(r"\s+", "", haystack)
    hits = 0
    for surface in list(dict.fromkeys(sibling_surfaces)):
        normalized = _strip_leading_period_qualifiers(_normalise_spaces(str(surface or "")))
        if not normalized:
            continue
        compact_surface = re.sub(r"\s+", "", normalized)
        if normalized in haystack or (compact_surface and compact_surface in compact_haystack):
            hits += 1
    return hits
