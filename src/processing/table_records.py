"""Build structured row/value records from parser-normalized DART tables."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.schema import AggregationStage, CellRecord, RowRecord, ValueRecord, ValueRole


_YEAR_LABEL_RE = re.compile(r"\b(20\d{2})년\b")
_DATE_LABEL_RE = re.compile(r"\b(20\d{2})\.(\d{1,2})\.(\d{1,2})\b")
_AGGREGATE_LABEL_TERMS = ("합계", "소계", "총계", "잔액")
_ADJUSTMENT_ROW_RE = re.compile(r"^차감(?::|\s)")
_FINAL_AGGREGATE_ROW_RE = re.compile(r"^차감\s*계(?:\s*$|\s*[,，]\s*|\s+)")
_SUBTOTAL_ROW_RE = re.compile(r"^합계(?:\s*[,，]\s*|\s+)")
_GENERIC_VALUE_LABELS = {
    "구분",
    "항목",
    "내용",
    "세부항목",
    "비고",
    "차입금명칭",
    "범위",
    "하위범위",
    "상위범위",
    "소계",
    "합계",
}


def normalize_table_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


def dedupe_preserve_order(values: List[str]) -> List[str]:
    seen: set[str] = set()
    result: List[str] = []
    for value in values:
        normalized = normalize_table_text(value)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def extract_period_labels(text: str) -> List[str]:
    labels: List[str] = []
    normalized = normalize_table_text(text)
    if not normalized:
        return labels

    for keyword in ("당기", "전기", "전전기", "당기말", "전기말", "전전기말"):
        if keyword in normalized:
            labels.append(keyword)

    labels.extend(match.group(1) for match in _YEAR_LABEL_RE.finditer(normalized))
    labels.extend(match.group(1) for match in _DATE_LABEL_RE.finditer(normalized))
    return dedupe_preserve_order(labels)


def cell_looks_numeric(text: str) -> bool:
    value = normalize_table_text(text)
    if not value:
        return False
    if re.search(r"[A-Za-z가-힣]", value):
        return False
    return bool(re.match(r"^(?:-?\d[\d,]*(?:\.\d+)?|\(\d[\d,]*(?:\.\d+)?\))%?$", value))


def is_period_like_label(text: str) -> bool:
    normalized = normalize_table_text(text)
    if not normalized:
        return False
    if normalized in {"당기", "전기", "전전기", "당기말", "전기말", "전전기말"}:
        return True
    return bool(re.fullmatch(r"20\d{2}(?:년)?", normalized))


def is_generic_value_label(text: str) -> bool:
    normalized = normalize_table_text(text)
    if not normalized:
        return True
    if normalized in _GENERIC_VALUE_LABELS:
        return True
    return is_period_like_label(normalized)


def infer_table_row_axis(row: List[str]) -> Tuple[str, List[str], set[int]]:
    first_numeric_idx = next(
        (idx for idx, cell in enumerate(row) if cell_looks_numeric(cell)),
        None,
    )
    axis_scan = row[:first_numeric_idx] if first_numeric_idx is not None else row
    axis_labels: List[str] = []
    axis_indices: List[int] = []
    for col_idx, cell in enumerate(axis_scan):
        text = normalize_table_text(cell)
        if not text or cell_looks_numeric(text):
            continue
        axis_labels.append(text)
        axis_indices.append(col_idx)

    if not axis_labels:
        for col_idx, cell in enumerate(row):
            text = normalize_table_text(cell)
            if text and not cell_looks_numeric(text):
                axis_labels.append(text)
                axis_indices.append(col_idx)
                break

    if not axis_labels:
        return "", [], set()

    meaningful_axis = [label for label in axis_labels if not is_generic_value_label(label)]
    row_label = meaningful_axis[-1] if meaningful_axis else axis_labels[-1]
    return row_label, dedupe_preserve_order(axis_labels), set(axis_indices)


def infer_table_header_row_count(grid: List[List[str]]) -> int:
    if not grid:
        return 0
    header_count = 0
    for index, row in enumerate(grid[:3]):
        numeric_beyond_first = any(cell_looks_numeric(cell) for cell in row[1:])
        if not numeric_beyond_first:
            header_count = index + 1
            continue
        if index == 0:
            header_count = 1
        break
    if header_count == 1 and len(grid) > 1:
        first_head = normalize_table_text(grid[0][0] if grid[0] else "")
        second_head = normalize_table_text(grid[1][0] if grid[1] else "")
        second_row_non_numeric = not any(cell_looks_numeric(cell) for cell in grid[1][1:])
        if first_head and first_head == second_head and second_row_non_numeric:
            header_count = 2
    return min(max(header_count, 1), len(grid))


def merge_header_stack(parts: List[str]) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()
    for part in parts:
        normalized = normalize_table_text(part)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        merged.append(normalized)
    return merged


def semantic_label_from_axes(
    row_label: str,
    row_headers: List[str],
    column_headers: List[str],
) -> Tuple[str, str, List[str]]:
    normalized_row = normalize_table_text(row_label)
    row_parts = [
        normalize_table_text(item)
        for item in ([normalized_row] + list(row_headers or []))
        if normalize_table_text(item)
    ]
    col_parts = [
        normalize_table_text(item)
        for item in list(column_headers or [])
        if normalize_table_text(item)
    ]

    meaningful_row = [item for item in row_parts if not is_generic_value_label(item)]
    meaningful_col = [item for item in col_parts if not is_generic_value_label(item)]

    if normalized_row and not is_generic_value_label(normalized_row):
        label = normalized_row
        source = "row"
    elif meaningful_row and not meaningful_col:
        label = meaningful_row[0]
        source = "row"
    elif meaningful_col and (
        not meaningful_row
        or is_period_like_label(normalized_row)
        or normalized_row in {"범위", "하위범위", "상위범위"}
    ):
        label = meaningful_col[-1]
        source = "column"
    elif meaningful_row and meaningful_col:
        label = meaningful_row[0]
        source = "composite"
    else:
        label = meaningful_col[-1] if meaningful_col else ""
        source = "unknown"

    aliases = dedupe_preserve_order([label, *meaningful_row, *meaningful_col])
    return label, source, aliases


def _is_aggregate_like_label(text: str) -> bool:
    normalized = normalize_table_text(text)
    if not normalized:
        return False
    return any(term in normalized for term in _AGGREGATE_LABEL_TERMS)


def _aggregate_column_label(column_headers: List[str]) -> str:
    meaningful_headers = [
        normalize_table_text(item)
        for item in list(column_headers or [])
        if normalize_table_text(item)
    ]
    for header in reversed(meaningful_headers):
        if _is_aggregate_like_label(header):
            return header
    return ""


def _strip_leading_aggregate_prefix(text: str) -> str:
    normalized = normalize_table_text(text)
    if not normalized:
        return ""
    normalized = _FINAL_AGGREGATE_ROW_RE.sub("", normalized)
    normalized = _SUBTOTAL_ROW_RE.sub("", normalized)
    normalized = re.sub(r"^차감\s*계\s*$", "", normalized)
    return normalize_table_text(normalized.strip(" ,，"))


def _strip_trailing_aggregate_suffix(text: str) -> str:
    normalized = normalize_table_text(text)
    if not normalized:
        return ""
    normalized = re.sub(r"\s*(합계|소계|총계|잔액)\s*$", "", normalized)
    return normalize_table_text(normalized.strip(" ,，"))


def derive_value_record_semantics(
    *,
    row_label: str,
    row_headers: List[str],
    column_headers: List[str],
    semantic_label: str,
    label_source: str,
    aliases: List[str],
) -> Tuple[str, str, List[str], str, str, str, str]:
    aggregate_label = _aggregate_column_label(column_headers)
    normalized_row = normalize_table_text(row_label)
    if not aggregate_label:
        return (
            semantic_label,
            label_source,
            aliases,
            "",
            "none",
            ValueRole.DETAIL.value,
            AggregationStage.NONE.value,
        )

    aggregate_base = _strip_trailing_aggregate_suffix(aggregate_label)
    row_base = _strip_leading_aggregate_prefix(normalized_row)
    if row_base:
        row_base = _strip_trailing_aggregate_suffix(row_base)

    if _FINAL_AGGREGATE_ROW_RE.match(normalized_row):
        aggregate_role = "final_total"
        semantic_label = aggregate_label
        aliases = dedupe_preserve_order([aggregate_label, aggregate_base, normalized_row, row_base])
        return (
            semantic_label,
            "column",
            aliases,
            aggregate_label,
            aggregate_role,
            ValueRole.AGGREGATE.value,
            AggregationStage.FINAL.value,
        )

    if _ADJUSTMENT_ROW_RE.match(normalized_row):
        aggregate_role = "adjustment"
        aliases = dedupe_preserve_order([normalized_row, row_base, semantic_label])
        return (
            semantic_label,
            label_source,
            aliases,
            aggregate_label,
            aggregate_role,
            ValueRole.ADJUSTMENT.value,
            AggregationStage.NONE.value,
        )

    if _SUBTOTAL_ROW_RE.match(normalized_row):
        aggregate_role = "subtotal"
        semantic_label = aggregate_label
        aliases = dedupe_preserve_order([aggregate_label, aggregate_base, normalized_row, row_base])
        return (
            semantic_label,
            "column",
            aliases,
            aggregate_label,
            aggregate_role,
            ValueRole.AGGREGATE.value,
            AggregationStage.SUBTOTAL.value,
        )

    if (
        aggregate_base
        and row_base
        and re.sub(r"\s+", "", aggregate_base) == re.sub(r"\s+", "", row_base)
    ):
        aggregate_role = "direct_total"
        semantic_label = aggregate_label
        aliases = dedupe_preserve_order([aggregate_label, aggregate_base, normalized_row])
        return (
            semantic_label,
            "column",
            aliases,
            aggregate_label,
            aggregate_role,
            ValueRole.AGGREGATE.value,
            AggregationStage.DIRECT.value,
        )

    aliases = dedupe_preserve_order([semantic_label, *aliases])
    return (
        semantic_label,
        label_source,
        aliases,
        aggregate_label,
        "none",
        ValueRole.DETAIL.value,
        AggregationStage.NONE.value,
    )


def build_table_row_records(table_object: Dict[str, Any], unit_hint: str) -> List[Dict[str, Any]]:
    grid = list(table_object.get("grid") or [])
    if not grid:
        return []

    header_row_count = infer_table_header_row_count(grid)
    header_rows = grid[:header_row_count]
    body_rows = grid[header_row_count:]
    if not body_rows:
        return []

    max_cols = max(len(row) for row in grid)
    column_headers: List[List[str]] = [[] for _ in range(max_cols)]
    for col_idx in range(max_cols):
        header_stack: List[str] = []
        for row in header_rows:
            if col_idx < len(row):
                text = normalize_table_text(row[col_idx])
                if text:
                    header_stack.append(text)
        column_headers[col_idx] = merge_header_stack(header_stack)

    row_records: List[Dict[str, Any]] = []
    for row_idx, row in enumerate(body_rows):
        row_label, row_headers, row_axis_cols = infer_table_row_axis(row)
        if not row_label:
            continue
        cells: List[Dict[str, Any]] = []
        for col_idx in range(len(row)):
            if col_idx in row_axis_cols:
                continue
            value_text = normalize_table_text(row[col_idx])
            if not value_text:
                continue
            cells.append(
                CellRecord(
                    cell_id=f"{table_object.get('row_count', 0)}:{row_idx}:{col_idx}",
                    column_index=col_idx,
                    column_headers=list(column_headers[col_idx]),
                    value_text=value_text,
                    unit_hint=unit_hint or "",
                ).model_dump()
            )
        if not cells:
            continue
        row_records.append(
            RowRecord(
                row_id=f"{table_object.get('row_count', 0)}:{row_idx}",
                row_label=row_label,
                row_headers=row_headers,
                cells=[CellRecord(**cell) for cell in cells],
            ).model_dump()
        )
    return row_records


def build_table_value_records(
    row_records: List[Dict[str, Any]],
    *,
    table_id: str,
    unit_hint: str,
) -> List[Dict[str, Any]]:
    value_records: List[Dict[str, Any]] = []
    for row_idx, record in enumerate(row_records):
        row_label = normalize_table_text(str(record.get("row_label") or ""))
        row_headers = [
            normalize_table_text(str(item))
            for item in (record.get("row_headers") or [])
            if normalize_table_text(str(item))
        ]
        for cell in (record.get("cells") or []):
            value_text = normalize_table_text(str(cell.get("value_text") or ""))
            if not value_text or not re.search(r"\d", value_text):
                continue
            column_headers = [
                normalize_table_text(str(item))
                for item in (cell.get("column_headers") or [])
                if normalize_table_text(str(item))
            ]
            semantic_label, label_source, aliases = semantic_label_from_axes(
                row_label,
                row_headers,
                column_headers,
            )
            if not semantic_label:
                continue
            (
                semantic_label,
                label_source,
                aliases,
                aggregate_label,
                aggregate_role,
                value_role,
                aggregation_stage,
            ) = derive_value_record_semantics(
                row_label=row_label,
                row_headers=row_headers,
                column_headers=column_headers,
                semantic_label=semantic_label,
                label_source=label_source,
                aliases=aliases,
            )
            axis_text = " ".join([*row_headers, *column_headers])
            period_candidates = extract_period_labels(axis_text)
            if not period_candidates:
                bare_years = re.findall(r"\b(20\d{2})\b", axis_text)
                period_candidates = dedupe_preserve_order(bare_years)
            value_records.append(
                ValueRecord(
                    value_id=f"{table_id}:v:{row_idx}:{int(cell.get('column_index') or 0)}",
                    row_index=row_idx,
                    column_index=int(cell.get("column_index") or 0),
                    semantic_label=semantic_label,
                    semantic_aliases=aliases,
                    label_source=label_source,
                    value_role=value_role,
                    aggregation_stage=aggregation_stage,
                    aggregate_label=aggregate_label,
                    aggregate_role=aggregate_role,
                    row_label=row_label,
                    row_headers=row_headers,
                    column_headers=column_headers,
                    period_text=period_candidates[0] if period_candidates else "",
                    period_labels=period_candidates,
                    value_text=value_text,
                    unit_hint=normalize_table_text(str(cell.get("unit_hint") or unit_hint or "")),
                ).model_dump()
            )
    return value_records
