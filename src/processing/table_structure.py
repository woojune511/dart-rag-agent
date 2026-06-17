"""Reconstruct DART XML table structure into normalized grid payloads."""

from __future__ import annotations

from typing import Any, Dict, List

from src.processing.table_records import cell_looks_numeric, is_generic_value_label, normalize_table_text


TABLE_CELL_TAGS = ("TD", "TH", "TU", "TE")


def cell_span_int(cell: Any, attr_name: str) -> int:
    raw = cell.get(attr_name) or cell.get(attr_name.lower()) or cell.get(attr_name.upper())
    try:
        value = int(str(raw or "1").strip())
    except (TypeError, ValueError):
        value = 1
    return max(1, value)


def normalize_table_grid(table_elem: Any) -> List[List[str]]:
    grid: List[List[str]] = []
    carry: Dict[int, Dict[str, Any]] = {}

    def advance_carry_into_row(row: List[str], col_idx: int) -> int:
        while col_idx in carry:
            slot = carry[col_idx]
            row.append(slot["text"])
            slot["remaining_rows"] -= 1
            if slot["remaining_rows"] <= 0:
                del carry[col_idx]
            col_idx += 1
        return col_idx

    for tr in table_elem.findall(".//TR"):
        row: List[str] = []
        col_idx = 0
        col_idx = advance_carry_into_row(row, col_idx)

        for cell in tr:
            if cell.tag not in TABLE_CELL_TAGS:
                continue
            col_idx = advance_carry_into_row(row, col_idx)
            text = normalize_table_text("".join(cell.itertext()))
            rowspan = cell_span_int(cell, "ROWSPAN")
            colspan = cell_span_int(cell, "COLSPAN")
            if not text and rowspan == 1 and colspan == 1:
                col_idx += 1
                row.append("")
                continue

            for _ in range(colspan):
                row.append(text)
                if rowspan > 1:
                    carry[col_idx] = {"text": text, "remaining_rows": rowspan - 1}
                col_idx += 1

        col_idx = advance_carry_into_row(row, col_idx)
        if any(cell.strip() for cell in row):
            grid.append(row)

    if not grid:
        return []

    max_cols = max(len(row) for row in grid)
    return [row + [""] * (max_cols - len(row)) for row in grid]


def format_table_grid(grid: List[List[str]]) -> str:
    rows: List[str] = []
    for row in grid:
        trimmed = list(row)
        while trimmed and not trimmed[-1].strip():
            trimmed.pop()
        if trimmed and any(cell.strip() for cell in trimmed):
            rows.append(" | ".join(trimmed))
    return "\n".join(rows)


def table_has_spans(table_elem: Any) -> bool:
    cells = []
    for tag in TABLE_CELL_TAGS:
        cells.extend(table_elem.findall(f".//{tag}"))
    for cell in cells:
        for attr_name in ("ROWSPAN", "COLSPAN", "rowspan", "colspan"):
            raw = cell.get(attr_name)
            if raw and str(raw).strip() not in {"", "1"}:
                return True
    return False


def extract_table_row_labels_from_grid(grid: List[List[str]], max_labels: int = 20) -> List[str]:
    def row_axis_label(row: List[str]) -> str:
        first_numeric_idx = next((idx for idx, cell in enumerate(row) if cell_looks_numeric(cell)), None)
        axis_scan = row[:first_numeric_idx] if first_numeric_idx is not None else row
        axis_labels = [
            normalize_table_text(cell)
            for cell in axis_scan
            if normalize_table_text(cell) and not cell_looks_numeric(cell)
        ]
        if axis_labels:
            meaningful_axis = [label for label in axis_labels if not is_generic_value_label(label)]
            return meaningful_axis[-1] if meaningful_axis else axis_labels[-1]
        return next((normalize_table_text(cell) for cell in row if normalize_table_text(cell)), "")

    labels: List[str] = []
    seen: set[str] = set()
    for row in grid:
        label = row_axis_label(row)
        if label and label not in seen:
            seen.add(label)
            labels.append(label)
        if len(labels) >= max_labels:
            break
    return labels


def build_table_object(table_elem: Any) -> Dict[str, Any]:
    grid = normalize_table_grid(table_elem)
    table_text = format_table_grid(grid)
    row_labels = extract_table_row_labels_from_grid(grid)
    return {
        "grid": grid,
        "table_text": table_text,
        "row_count": len(grid),
        "column_count": max((len(row) for row in grid), default=0),
        "row_labels": row_labels,
        "has_spans": table_has_spans(table_elem),
    }


def grid_row_to_text(row: List[str]) -> str:
    trimmed = list(row)
    while trimmed and not trimmed[-1].strip():
        trimmed.pop()
    return " | ".join(trimmed)
