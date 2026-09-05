"""Shared runtime normalization and display primitives."""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Any, List, Optional, Sequence

from src.config.retrieval_policy import (
    KOREAN_COUNT_SCALE_PREFIXES,
    KOREAN_COUNT_UNITS,
    KOREAN_WON_COMPACT_FORMAT_POLICY,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
)


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


@dataclass(frozen=True, slots=True)
class UnitSpecV1:
    """One source/display unit measured in the runtime's normalized units."""

    normalized_dimension: str
    scale: float
    display_unit: str


def resolve_unit_spec(unit: str) -> Optional[UnitSpecV1]:
    surface = _normalise_spaces(str(unit or ""))
    key = re.sub(r"\s+", "", surface).casefold()
    if not key:
        return None
    policy = NUMERIC_UNIT_NORMALIZATION_POLICY
    canonical = dict(policy.get("canonical_units") or {}).get(key.upper())
    if canonical:
        return UnitSpecV1(
            str(canonical["dimension"]), 1.0, str(canonical["display_unit"])
        )
    for dimension, policy_key in (
        ("KRW", "krw_scales"), ("USD", "usd_scales"), ("COUNT", "count_scales")
    ):
        for alias, scale in dict(policy.get(policy_key) or {}).items():
            if key == re.sub(r"\s+", "", str(alias)).casefold():
                return UnitSpecV1(dimension, float(scale), surface)
    if key in {str(item).casefold() for item in policy.get("percent_units", ())}:
        return UnitSpecV1("PERCENT", 1.0, surface)
    for base_unit in KOREAN_COUNT_UNITS:
        if key == base_unit:
            return UnitSpecV1("COUNT", 1.0, surface)
        for prefix, scale in KOREAN_COUNT_SCALE_PREFIXES:
            if key == f"{prefix}{base_unit}":
                return UnitSpecV1("COUNT", float(scale), surface)
    return None


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


def _split_numeric_sign(text: str) -> tuple[str, bool]:
    cleaned = _normalise_spaces(str(text or ""))
    negative = False
    if cleaned.startswith("(") and cleaned.endswith(")"):
        negative = True
        cleaned = cleaned[1:-1].strip()
    if cleaned.startswith(("-", "△", "▲")):
        negative = True
        cleaned = cleaned[1:].strip()
    elif cleaned.startswith("+"):
        cleaned = cleaned[1:].strip()
    return cleaned, negative


def _parse_number_text(text: str) -> Optional[float]:
    cleaned, negative = _split_numeric_sign(text)
    try:
        value = float(cleaned.replace(",", ""))
        if not math.isfinite(value):
            return None
        return -abs(value) if negative else value
    except ValueError:
        return None


def _number_precision(text: str) -> Optional[float]:
    cleaned, _negative = _split_numeric_sign(text)
    match = re.fullmatch(r"[\d,]+(?:\.([0-9]+))?", cleaned)
    if not match:
        return None
    return 0.5 * 10 ** -len(match.group(1) or "")


def _composite_numeric_parts(
    raw_value: str, raw_unit: str
) -> Optional[tuple[float, str, float]]:
    cleaned, negative = _split_numeric_sign(raw_value)
    policy = NUMERIC_UNIT_NORMALIZATION_POLICY
    match = re.fullmatch(str(policy.get("composite_value_pattern") or r"$^"), cleaned, re.IGNORECASE)
    if not match:
        return None
    currency = match.group("currency") or raw_unit or str(policy.get("composite_default_currency") or "")
    spec = resolve_unit_spec(currency)
    if spec is None or spec.normalized_dimension not in {"KRW", "USD"}:
        return None
    major = _parse_number_text(match.group("major"))
    minor_text = match.group("minor")
    minor = _parse_number_text(minor_text) if minor_text else 0.0
    if major is None or minor is None:
        return None
    major_scale = float(policy["composite_major_scale"])
    minor_scale = float(policy["composite_minor_scale"])
    value = major * major_scale + minor * minor_scale
    if not math.isfinite(value):
        return None
    precision = _number_precision(minor_text or match.group("major"))
    if precision is None:
        return None
    return (
        -value if negative else value,
        spec.normalized_dimension,
        precision * (minor_scale if minor_text else major_scale),
    )


def _extract_composite_krw(text: str) -> Optional[float]:
    parts = _composite_numeric_parts(text, "")
    return parts[0] if parts is not None and parts[1] == "KRW" else None


def _inline_numeric_unit_match(raw_value: str) -> Optional[re.Match[str]]:
    unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
    pattern = str(unit_policy.get("inline_value_unit_pattern") or "")
    if not pattern:
        return None
    cleaned, _negative = _split_numeric_sign(raw_value)
    return re.fullmatch(pattern, cleaned, re.IGNORECASE)


def resolve_source_numeric_unit(raw_value: str, source_unit_hint: str) -> tuple[str, str]:
    """Resolve the source display unit, preferring a unit inside the value cell."""

    inline_unit_match = _inline_numeric_unit_match(raw_value)
    if inline_unit_match:
        inline_unit = re.sub(r"\s+", "", inline_unit_match.group("unit"))
        inline_unit = str(
            dict(
                NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_unit_aliases") or {}
            ).get(inline_unit)
            or inline_unit
        )
        return inline_unit, "inline_value"

    hinted_unit = _normalise_spaces(source_unit_hint)
    if hinted_unit:
        return hinted_unit, "cell_or_table_hint"
    return "", "unknown"


def _normalise_operand_value(raw_value: str, raw_unit: str) -> tuple[Optional[float], str]:
    """Normalize display-level values into comparison-friendly numeric units."""
    resolved_unit, _unit_source = resolve_source_numeric_unit(raw_value, raw_unit)
    composite = _composite_numeric_parts(raw_value, resolved_unit)
    if composite is not None:
        return composite[0], composite[1]

    _cleaned, negative = _split_numeric_sign(raw_value)
    inline_unit_match = _inline_numeric_unit_match(raw_value)
    if inline_unit_match:
        raw_value = inline_unit_match.group("value")

    value = _parse_number_text(raw_value)
    if value is None:
        return None, "UNKNOWN"
    if negative:
        value = -abs(value)
    spec = resolve_unit_spec(resolved_unit)
    normalized_value = value * spec.scale if spec else value
    if not math.isfinite(normalized_value):
        return None, "UNKNOWN"
    return normalized_value, spec.normalized_dimension if spec else "UNKNOWN"


def source_display_precision(raw_value: str, raw_unit: str) -> Optional[float]:
    """Return the source's rounding half-width in normalized base units."""
    resolved_unit, _source = resolve_source_numeric_unit(raw_value, raw_unit)
    composite = _composite_numeric_parts(raw_value, resolved_unit)
    if composite is not None:
        return composite[2]
    match = _inline_numeric_unit_match(raw_value)
    precision = _number_precision(match.group("value") if match else raw_value)
    if precision is None:
        return None
    spec = resolve_unit_spec(resolved_unit)
    return precision * (spec.scale if spec else 1.0)


def format_korean_won_compact(value: float) -> str:
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


def display_operand_label(label: str) -> str:
    text = _normalise_spaces(label)
    text = re.sub(r"^[\uac00-\ud7a3A-Za-z0-9&.\- ]{2,40}\s+(?=\d{4}\ub144\s+)", "", text)
    text = re.sub(r"^\d{4}년\s*", "", text)
    text = re.sub(r"^\d{4}\s+", "", text)
    return text
