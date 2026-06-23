"""Shared runtime normalization and display primitives."""

from __future__ import annotations

import re
from typing import Any, List, Optional, Sequence

from src.config.retrieval_policy import (
    KOREAN_COUNT_SCALE_PREFIXES,
    KOREAN_COUNT_UNITS,
    KOREAN_WON_COMPACT_FORMAT_POLICY,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
)


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _clean_source_row_ids(values: Sequence[Any]) -> List[str]:
    blocked = {"none", "null", "nan"}
    cleaned: List[str] = []

    def _append(value: Any) -> None:
        if isinstance(value, (list, tuple, set)):
            for item in value:
                _append(item)
            return
        text = str(value).strip()
        if not text or text.lower() in blocked:
            return
        cleaned.append(text)

    for value in values or []:
        _append(value)
    return list(dict.fromkeys(cleaned))


def _parse_number_text(text: str) -> Optional[float]:
    cleaned = _normalise_spaces(str(text or "")).replace(",", "").strip()
    if not cleaned:
        return None
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith("△"):
        negative = True
        cleaned = cleaned[1:].strip()
    if cleaned.startswith("▲"):
        negative = True
        cleaned = cleaned[1:].strip()
    try:
        value = float(cleaned)
        return -value if negative else value
    except ValueError:
        return None


def _extract_composite_krw(text: str) -> Optional[float]:
    cleaned = _normalise_spaces(text)
    composite = re.search(r"(?P<jo>[\d,]+(?:\.\d+)?)\s*조\s*(?P<eok>[\d,]+(?:\.\d+)?)\s*억", cleaned)
    if composite:
        jo = _parse_number_text(composite.group("jo"))
        eok = _parse_number_text(composite.group("eok"))
        if jo is None or eok is None:
            return None
        return jo * 1_0000_0000_0000 + eok * 100_000_000
    only_jo = re.search(r"(?P<jo>[\d,]+(?:\.\d+)?)\s*조\s*원?", cleaned)
    if only_jo:
        jo = _parse_number_text(only_jo.group("jo"))
        if jo is not None:
            return jo * 1_0000_0000_0000
    return None


def _normalise_operand_value(raw_value: str, raw_unit: str) -> tuple[Optional[float], str]:
    """Normalize display-level values into comparison-friendly numeric units."""
    unit = _normalise_spaces(raw_unit).lower()
    composite_krw = _extract_composite_krw(raw_value)
    if composite_krw is not None:
        return composite_krw, "KRW"

    unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
    inline_unit_match = re.fullmatch(
        str(unit_policy.get("inline_value_unit_pattern") or ""),
        _normalise_spaces(raw_value),
    )
    if inline_unit_match:
        raw_value = inline_unit_match.group("value")
        inline_unit = re.sub(r"\s+", "", inline_unit_match.group("unit"))
        inline_unit = str(dict(unit_policy.get("inline_unit_aliases") or {}).get(inline_unit) or inline_unit)
        unit = inline_unit.lower()

    value = _parse_number_text(raw_value)
    percent_units = tuple(str(item) for item in (unit_policy.get("percent_units") or ()) if str(item))
    if value is None and unit in percent_units:
        stripped_value = str(raw_value or "")
        for percent_unit in percent_units:
            stripped_value = stripped_value.replace(percent_unit, "")
        value = _parse_number_text(stripped_value)
    if value is None:
        return None, "UNKNOWN"

    krw_scale = dict(unit_policy.get("krw_scales") or {})
    usd_scale = dict(unit_policy.get("usd_scales") or {})
    compact_unit = re.sub(r"\s+", "", unit)
    count_scale = {base_unit: 1.0 for base_unit in KOREAN_COUNT_UNITS}
    for prefix, scale in KOREAN_COUNT_SCALE_PREFIXES:
        for base_unit in KOREAN_COUNT_UNITS:
            count_scale[f"{prefix}{base_unit}"] = scale

    if unit in krw_scale:
        return value * krw_scale[unit], "KRW"
    if unit in usd_scale:
        return value * usd_scale[unit], "USD"
    if compact_unit in count_scale:
        return value * count_scale[compact_unit], "COUNT"
    if unit in percent_units:
        return value, "PERCENT"
    return value, "UNKNOWN"


def _format_korean_won_compact(value: float) -> str:
    format_policy = dict(KOREAN_WON_COMPACT_FORMAT_POLICY)
    threshold = int(format_policy.get("hundred_million_threshold") or 100_000_000)
    hundred_million_scale = int(format_policy.get("hundred_million_scale") or threshold)
    if abs(value) >= threshold:
        amount = int(round(abs(value) / hundred_million_scale)) * hundred_million_scale
    else:
        amount = int(round(abs(value)))
    negative = value < 0
    trillion_scale = int(format_policy.get("trillion_scale") or 1_0000_0000_0000)
    ten_thousand_scale = int(format_policy.get("ten_thousand_scale") or 10_000)
    jo = amount // trillion_scale
    amount %= trillion_scale
    eok = amount // hundred_million_scale
    amount %= hundred_million_scale
    man = amount // ten_thousand_scale

    parts: List[str] = []
    if jo:
        parts.append(f"{jo}{format_policy.get('trillion_suffix') or ''}")
    if eok:
        parts.append(f"{eok:,}{format_policy.get('hundred_million_suffix') or ''}")
    elif jo:
        parts.append(str(format_policy.get("zero_hundred_million_label") or "0"))
    elif man:
        parts.append(f"{man:,}{format_policy.get('ten_thousand_suffix') or ''}")
    else:
        parts.append(f"{int(round(abs(value))):,}{format_policy.get('base_suffix') or ''}")

    rendered = " ".join(parts)
    return f"-{rendered}" if negative else rendered


def _display_operand_label(label: str) -> str:
    text = _normalise_spaces(label)
    text = re.sub(r"^[\uac00-\ud7a3A-Za-z0-9&.\- ]{2,40}\s+(?=\d{4}\ub144\s+)", "", text)
    text = re.sub(r"^\d{4}년\s*", "", text)
    text = re.sub(r"^\d{4}\s+", "", text)
    return text
