"""Preserve explicit row-axis unit annotations without converting their values."""

from __future__ import annotations

import re
from typing import Sequence

from src.config.retrieval_policy import (
    KOREAN_COUNT_SCALE_PREFIXES,
    KOREAN_COUNT_UNITS,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
    TABLE_COLUMN_UNIT_POLICY,
)


_POLICY = NUMERIC_UNIT_NORMALIZATION_POLICY
_KNOWN_UNITS = {
    *dict(_POLICY["krw_scales"]),
    *dict(_POLICY["usd_scales"]),
    *dict(_POLICY["count_scales"]),
    *_POLICY["percent_units"],
    *_POLICY["percent_display_units"],
    *KOREAN_COUNT_UNITS,
    *(prefix + unit for prefix, _ in KOREAN_COUNT_SCALE_PREFIXES
      for unit in KOREAN_COUNT_UNITS),
}
# An unscaled currency code can name an exposure converted into the table's
# reporting currency. Corporate abbreviations are also not unit declarations.
_IMPLICIT_UNITS = {unit.casefold() for unit in _KNOWN_UNITS} - {"usd", "사"}
_SCALES = tuple(sorted(
    (unit[:-1] for unit in _POLICY["krw_scales"] if unit != "원"),
    key=len, reverse=True,
))
_SCALE_PATTERN = "(?:" + "|".join(re.escape(unit) for unit in _SCALES) + ")"
_SCALED_CODE_RE = re.compile(rf"(?P<scale>{_SCALE_PATTERN})(?P<code>[A-Z]{{3}})")
_CODE_SCALE_RE = re.compile(rf"(?P<code>[A-Z]{{3}})[,，](?P<scale>{_SCALE_PATTERN})")
_ANNOTATION_RE = re.compile(r"\(([^()]*)\)|\[([^\[\]]*)\]")
_DECLARATION_RE = re.compile(TABLE_COLUMN_UNIT_POLICY["declaration_pattern"], re.I)
_EXPLICIT_UNIT_RE = re.compile(r"[A-Za-z가-힣%$€¥][A-Za-z0-9가-힣%$€¥/^·-]*")


def _unit_key(surface: str, *, explicit: bool) -> str | None:
    surface = str(surface or "")
    compact = re.sub(r"\s+", "", surface)
    scaled = _SCALED_CODE_RE.fullmatch(compact) or _CODE_SCALE_RE.fullmatch(compact)
    if scaled:
        return scaled.group("scale") + scaled.group("code")
    if compact.casefold() in _IMPLICIT_UNITS:
        return compact.casefold()
    if "/" in compact:
        numerator, denominator = compact.split("/", 1)
        if (numerator.casefold() in _IMPLICIT_UNITS
                and re.fullmatch(r"[A-Za-z가-힣%]+", denominator)):
            return compact.casefold()
    # Explicit declarations preserve unfamiliar physical/currency units as
    # opaque source strings; they do not claim a normalized dimension or scale.
    if explicit and _EXPLICIT_UNIT_RE.fullmatch(surface.strip()):
        return compact.casefold()
    return None


def _declared_units(headers: Sequence[str]) -> tuple[dict[str, str], bool]:
    units: dict[str, str] = {}
    unresolved = False
    for header in headers:
        text = str(header or "")
        annotations = [match.group(1) if match.group(1) is not None else match.group(2)
                       for match in _ANNOTATION_RE.finditer(text)]
        # A whole row-axis cell may itself say "단위: ...". Bare currency cells
        # and prose mentioning a currency are deliberately not declarations.
        if _DECLARATION_RE.fullmatch(text.strip()):
            annotations.append(text.strip())
        for annotation in annotations:
            declaration = _DECLARATION_RE.fullmatch(annotation.strip())
            surface = (declaration.group("units") if declaration else annotation).strip()
            key = _unit_key(surface, explicit=bool(declaration))
            if key is not None:
                units.setdefault(key, surface)
                continue
            parts = [part.strip() for part in re.split(r"[,，;]", surface)]
            parsed = [(_unit_key(part, explicit=bool(declaration)), part) for part in parts]
            if len(parts) > 1 and all(key is not None for key, _ in parsed):
                for key, part in parsed:
                    units.setdefault(str(key), part)
            elif declaration:
                unresolved = True
    return units, unresolved


def _repeats_table_declaration(header: str, table_unit_hint: str) -> bool:
    text = str(header or "").strip()
    annotation = _ANNOTATION_RE.fullmatch(text)
    if annotation:
        text = annotation.group(1) if annotation.group(1) is not None else annotation.group(2)
    declaration = _DECLARATION_RE.fullmatch(text.strip())
    table_key = _unit_key(table_unit_hint, explicit=True)
    return bool(declaration and table_key is not None
                and _unit_key(declaration.group("units"), explicit=True) == table_key)


def resolve_row_unit_hint(
    row_headers: Sequence[str], table_unit_hint: str, *,
    column_headers: Sequence[str] = (),
) -> str:
    """Use one unambiguous explicit row unit, otherwise retain the table hint.

    Conflicting or unparseable explicit declarations produce an empty hint.
    A missing row declaration alone permits the existing table-level fallback.
    Existing column declarations can veto a row override, not invent a unit.
    """
    units, unresolved = _declared_units(row_headers)
    if unresolved or len(units) > 1:
        return ""
    if units:
        # A merged table-wide unit declaration may be repeated in every header
        # stack. It is the fallback being overridden, not a contrary column axis.
        column_units, column_unresolved = _declared_units([
            header for header in column_headers
            if not _repeats_table_declaration(header, table_unit_hint)
        ])
        if column_unresolved or any(key not in units for key in column_units):
            return ""
        return next(iter(units.values()))
    return table_unit_hint or ""
