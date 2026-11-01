"""Chunk parser-collected section blocks into retrieval-ready block payloads."""

from __future__ import annotations

import re
import json
from typing import Any, Callable, Dict, List, Optional
from src.processing.source_context import heading_scope_key
from src.processing.table_records import cell_looks_numeric


WIDE_TABLE_COLUMN_THRESHOLD = 24
WIDE_TABLE_WINDOW_SIZE = 24
WIDE_TABLE_WINDOW_OVERLAP = 2
TABLE_NARRATIVE_BREAK_RE = re.compile(r"(?=(\(\d+\)|[①②③④⑤⑥⑦⑧⑨⑩]))")
NUMERIC_HEADING_RE = re.compile(r"^\d+\.\s")
KOREAN_ALPHA_HEADING_RE = re.compile(r"^[가-하]\.\s")


def _recursive_character_text_splitter(**kwargs):
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(**kwargs)


def looks_like_table_header_row(row_text: str, *, chunk_size: int) -> bool:
    cells = [cell.strip() for cell in row_text.split(" | ")]
    if len(cells) <= 1:
        return False
    if (
        len(cells) == 2
        and (NUMERIC_HEADING_RE.match(cells[0]) or KOREAN_ALPHA_HEADING_RE.match(cells[0]))
        and (cells[1].startswith("(") or len(cells[1]) > 120)
    ):
        return False
    if len(row_text) > min(400, chunk_size // 2):
        return False
    if any(len(cell) > 120 for cell in cells):
        return False
    return True


def split_table_text_fragment(
    text: str,
    max_len: int,
    *,
    normalize_text: Callable[[str], str],
) -> List[str]:
    if len(text) <= max_len:
        return [text]

    marker_positions = [match.start() for match in TABLE_NARRATIVE_BREAK_RE.finditer(text)]
    segments: List[str] = []
    if len(marker_positions) >= 2:
        # Numbered lists can follow a source-defining introductory sentence.
        # Segment from the beginning, not just from the first numbered item.
        positions = sorted({0, *marker_positions, len(text)})
        for start, end in zip(positions, positions[1:]):
            segment = normalize_text(text[start:end])
            if segment:
                segments.append(segment)

    if not segments:
        splitter = _recursive_character_text_splitter(
            chunk_size=max_len,
            chunk_overlap=0,
            separators=["\n\n", ". ", "다. ", "; ", " ", ""],
            length_function=len,
        )
        return [chunk for chunk in splitter.split_text(text) if chunk.strip()]

    result: List[str] = []
    current = ""
    for segment in segments:
        if len(segment) > max_len:
            if current:
                result.append(current)
                current = ""
            splitter = _recursive_character_text_splitter(
                chunk_size=max_len,
                chunk_overlap=0,
                separators=["\n\n", ". ", "다. ", "; ", " ", ""],
                length_function=len,
            )
            result.extend(chunk for chunk in splitter.split_text(segment) if chunk.strip())
            continue

        candidate = f"{current}{segment}" if current else segment
        if current and len(candidate) > max_len:
            result.append(current)
            current = segment
        else:
            current = candidate

    if current:
        result.append(current)
    return result or [text]


def split_long_table_row(
    row_text: str,
    max_len: int,
    *,
    normalize_text: Callable[[str], str],
) -> List[str]:
    if max_len <= 0 or len(row_text) <= max_len:
        return [row_text]

    cells = [cell.strip() for cell in row_text.split(" | ")]
    if len(cells) >= 2:
        label = cells[0]
        value = " | ".join(cells[1:])
        if label and len(label) <= 80 and len(value) > max_len // 2:
            value_max_len = max(120, max_len - len(label) - 3)
            value_parts = split_table_text_fragment(
                value,
                value_max_len,
                normalize_text=normalize_text,
            )
            return [f"{label} | {part}" for part in value_parts if part.strip()]

    return split_table_text_fragment(row_text, max_len, normalize_text=normalize_text)


def split_table_by_rows(
    table_text: str,
    *,
    chunk_size: int,
    normalize_text: Callable[[str], str],
) -> List[str]:
    rows = [row for row in table_text.split("\n") if row.strip()]
    if not rows:
        return []

    header = rows[0] if len(rows) > 1 and looks_like_table_header_row(rows[0], chunk_size=chunk_size) else None
    source_rows = rows[1:] if header else rows
    result: List[str] = []
    current = [header] if header else []
    current_len = len(header) if header else 0

    max_row_len = chunk_size - (len(header) + 1 if header else 0)

    for row in source_rows:
        for row_part in split_long_table_row(
            row,
            max_row_len,
            normalize_text=normalize_text,
        ):
            if not current:
                current = [row_part]
                current_len = len(row_part)
                continue

            if current_len + 1 + len(row_part) > chunk_size and (len(current) > 1 or not header):
                result.append("\n".join(current))
                current = [header, row_part] if header else [row_part]
                current_len = (len(header) + 1 + len(row_part)) if header else len(row_part)
            else:
                current.append(row_part)
                current_len += 1 + len(row_part)

    if current:
        result.append("\n".join(current))

    return result


def split_wide_table_by_columns(table_text: str) -> Optional[List[str]]:
    rows = [row for row in table_text.split("\n") if row.strip()]
    if len(rows) <= 1:
        return None

    row_cells = [row.split(" | ") for row in rows]
    max_cols = max(len(cells) for cells in row_cells)
    if max_cols < WIDE_TABLE_COLUMN_THRESHOLD:
        return None

    step = max(1, WIDE_TABLE_WINDOW_SIZE - WIDE_TABLE_WINDOW_OVERLAP)
    windows: List[str] = []

    for start in range(0, max_cols, step):
        end = min(max_cols, start + WIDE_TABLE_WINDOW_SIZE)
        window_rows: List[str] = []
        for cells in row_cells:
            if len(cells) <= 2:
                row_text = " | ".join(cells)
                if row_text:
                    window_rows.append(row_text)
                continue

            sliced = cells[start:end]
            if not sliced:
                continue
            row_text = " | ".join(sliced)
            if row_text:
                window_rows.append(row_text)

        if window_rows:
            candidate = "\n".join(window_rows)
            if candidate not in windows:
                windows.append(candidate)

    return windows or None


def split_table_for_chunks(
    table_text: str,
    *,
    chunk_size: int,
    normalize_text: Callable[[str], str],
    table_grid: Optional[List[List[str]]] = None,
    header_row_count: int = 0,
) -> List[Dict[str, str]]:
    if table_grid and max(map(len, table_grid)) >= WIDE_TABLE_COLUMN_THRESHOLD:
        return _split_wide_grid_for_chunks(
            table_grid, header_row_count=header_row_count, chunk_size=chunk_size,
        )
    wide_table_chunks = split_wide_table_by_columns(table_text)
    if wide_table_chunks:
        result: List[Dict[str, str]] = []
        for window in wide_table_chunks:
            if len(window) > chunk_size:
                row_windows = split_table_by_rows(
                    window,
                    chunk_size=chunk_size,
                    normalize_text=normalize_text,
                )
                if len(row_windows) > 1:
                    result.extend(
                        {"text": row_window, "table_view": "column_row_window"}
                        for row_window in row_windows
                    )
                else:
                    result.append({"text": row_windows[0], "table_view": "column_window"})
            else:
                result.append({"text": window, "table_view": "column_window"})
        return result

    if len(table_text) > chunk_size:
        return [
            {"text": sub, "table_view": "row_window"}
            for sub in split_table_by_rows(
                table_text,
                chunk_size=chunk_size,
                normalize_text=normalize_text,
            )
        ]

    return [{"text": table_text, "table_view": "full"}]


def _split_wide_grid_for_chunks(
    grid: List[List[str]], *, header_row_count: int, chunk_size: int,
) -> List[Dict[str, str]]:
    """Project original cell positions, then split only between whole rows.

    Leading row axes repeat in every column window. A header plus one intact
    row may exceed the soft chunk target; cutting a cell would corrupt its
    column identity. The downstream source-packet byte limit still applies.
    """
    width = max(map(len, grid))
    rows = [list(row) + [""] * (width - len(row)) for row in grid]
    header_count = min(max(header_row_count, 0), len(rows))
    numeric_rows = [row for row in rows[header_count:] if any(cell_looks_numeric(cell) for cell in row)]
    axis_count = 0 if numeric_rows else 1
    for row in numeric_rows:
        # Keep the first textual axis run through the next numeric value.
        # Leading numeric identifiers travel with that prefix. This projection
        # does not change or depend on semantic row-record label inference.
        first_text = next((i for i, cell in enumerate(row) if cell.strip() and not cell_looks_numeric(cell)), None)
        if first_text is None:
            continue
        for index in range(first_text, width):
            if cell_looks_numeric(row[index]):
                break
            if row[index].strip():
                axis_count = max(axis_count, index + 1)
    # Non-numeric descriptive rows do not turn every data column into an axis.
    # An uncertain long prefix is repeated, never dropped.
    axis_count = min(axis_count, width - 1)
    # Never let a long textual prefix consume the entire data window.
    window_size = max(1, WIDE_TABLE_WINDOW_SIZE - axis_count)
    step = max(1, window_size - WIDE_TABLE_WINDOW_OVERLAP)
    result: List[Dict[str, str]] = []
    for start in range(axis_count, width, step):
        end = min(width, start + window_size)
        columns = [*range(axis_count), *range(start, end)]
        projected = [" | ".join(row[i] for i in columns) for row in rows]
        headers = projected[:header_count]
        parts: List[str] = []
        current: List[str] = []
        for row in projected[header_count:]:
            candidate = "\n".join([*headers, *current, row])
            if current and len(candidate) > chunk_size:
                parts.append("\n".join([*headers, *current]))
                current = []
            current.append(row)
        if current or headers:
            parts.append("\n".join([*headers, *current]))
        view = "column_row_window" if len(parts) > 1 else "column_window"
        result.extend({"text": text, "table_view": view} for text in parts)
        if end == width:
            break
    return result


def table_bundle_from_block(
    block: Optional[Dict[str, Any]],
    *,
    header_propagated: Optional[bool] = None,
) -> Dict[str, Any]:
    if not block:
        return {}
    bundle = {
        "table_source_id": block.get("table_source_id"),
        "table_header_context": block.get("table_header_context"),
        "period_labels": list(block.get("period_labels") or []),
        "period_focus": block.get("period_focus"),
        "unit_hint": block.get("unit_hint"),
        "statement_type": block.get("statement_type"),
        "consolidation_scope": block.get("consolidation_scope"),
        "header_propagated": block.get("header_propagated", False),
        "table_summary_text": block.get("table_summary_text"),
        "table_row_labels_text": block.get("table_row_labels_text"),
        "table_row_records_json": block.get("table_row_records_json"),
        "table_value_records_json": block.get("table_value_records_json"),
        "table_value_labels_text": block.get("table_value_labels_text"),
        "table_object_json": block.get("table_object_json"),
        "table_row_count": block.get("table_row_count"),
        "table_column_count": block.get("table_column_count"),
        "table_has_spans": block.get("table_has_spans", False),
    }
    if header_propagated is not None:
        bundle["header_propagated"] = header_propagated
    return bundle


def heading_context_bundle(block: Dict[str, Any]) -> Dict[str, str]:
    contexts = block.get("source_contexts") or []
    return {"source_contexts_json": json.dumps(contexts, ensure_ascii=False)} if contexts else {}


def chunk_blocks(
    blocks: List[Dict[str, Any]],
    section_path: str,
    *,
    chunk_size: int,
    text_splitter: Any,
    summarize_for_context: Callable[[str], str],
    normalize_text: Callable[[str], str],
) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    pending_blocks: List[Dict[str, Any]] = []
    standalone_threshold = chunk_size // 2
    last_paragraph_context = section_path
    last_paragraph_heading = None
    last_paragraph_scope: tuple = ()

    def flush_pending() -> None:
        if not pending_blocks:
            return

        merged = "\n\n".join(block["text"] for block in pending_blocks)
        table_chars = sum(len(block["text"]) for block in pending_blocks if block["type"] == "table")
        has_table = any(block["type"] == "table" for block in pending_blocks)
        block_type = "table" if table_chars > len(merged) * 0.5 else "paragraph"
        local_heading = next((block.get("local_heading") for block in pending_blocks if block.get("local_heading")), None)
        table_context = None
        table_bundle: Dict[str, Any] = {}
        if has_table:
            first_table = next(block for block in pending_blocks if block["type"] == "table")
            table_context = first_table.get("table_context") or section_path
            table_bundle = table_bundle_from_block(first_table)

        if len(merged) > chunk_size:
            split_parts = [sub for sub in text_splitter.split_text(merged) if sub.strip()]
            propagate_headers = has_table and len(split_parts) > 1
            for idx, sub in enumerate(split_parts):
                if not sub.strip():
                    continue
                result.append(
                    {
                        "text": sub,
                        "block_type": block_type,
                        "table_context": table_context if idx == 0 else None,
                        "local_heading": local_heading,
                        "table_view": "text_split",
                        **heading_context_bundle(pending_blocks[0]),
                        **(
                            table_bundle_from_block(
                                first_table,
                                header_propagated=(propagate_headers and idx > 0),
                            )
                            if has_table
                            else {}
                        ),
                    }
                )
        else:
            result.append(
                {
                    "text": merged,
                    "block_type": block_type,
                    "table_context": table_context,
                    "local_heading": local_heading,
                    "table_view": "full" if has_table else None,
                    **heading_context_bundle(pending_blocks[0]),
                    **table_bundle,
                }
            )

        pending_blocks.clear()

    for block in blocks:
        text = block["text"]
        block_type = block["type"]
        explicit_table_context = block.get("table_context")
        if block.get("table_prefix_target"):
            # A physically linked forward caption cannot trail an earlier table.
            flush_pending()
        current_heading = next(
            (item.get("local_heading") for item in pending_blocks if item.get("local_heading")),
            None,
        )
        next_heading = block.get("local_heading")

        if pending_blocks and (
            ((current_heading or next_heading) and current_heading != next_heading)
            or heading_scope_key(pending_blocks[0]) != heading_scope_key(block)
        ):
            flush_pending()

        if block_type == "paragraph":
            last_paragraph_context = summarize_for_context(text)
            last_paragraph_heading = block.get("local_heading_scope", next_heading)
            last_paragraph_scope = heading_scope_key(block)

        if block_type == "table":
            table_heading = block.get("local_heading_scope", next_heading)
            table_scope = heading_scope_key(block)
            if table_heading != last_paragraph_heading or table_scope != last_paragraph_scope:
                # Adjacency context cannot cross a peer/child heading boundary.
                # An explicit caption retains its enclosing heading scope.
                last_paragraph_context = section_path
                last_paragraph_heading = table_heading
                last_paragraph_scope = table_scope
            block = {
                **block,
                "table_context": block.get("table_context") or last_paragraph_context or section_path,
            }
            if any(item.get("type") == "table" for item in pending_blocks):
                flush_pending()

        if block_type == "table" and len(text) >= standalone_threshold:
            flush_pending()
            table_chunks = split_table_for_chunks(
                text,
                chunk_size=chunk_size,
                normalize_text=normalize_text,
                table_grid=block.get("_table_grid"),
                header_row_count=block.get("_table_header_row_count", 0),
            )
            propagate_headers = len(table_chunks) > 1
            if len(text) > chunk_size:
                for idx, table_chunk in enumerate(table_chunks):
                    result.append(
                        {
                            "text": table_chunk["text"],
                            "block_type": "table",
                            "table_context": block["table_context"] if idx == 0 or explicit_table_context else None,
                            "local_heading": block.get("local_heading"),
                            "table_view": table_chunk["table_view"],
                            **heading_context_bundle(block),
                            **table_bundle_from_block(
                                block,
                                header_propagated=(propagate_headers and idx > 0),
                            ),
                        }
                    )
            else:
                result.append(
                    {
                        "text": text,
                        "block_type": "table",
                        "table_context": block["table_context"],
                        "local_heading": block.get("local_heading"),
                        "table_view": "full",
                        **heading_context_bundle(block),
                        **table_bundle_from_block(block),
                    }
                )
        else:
            projected = "\n\n".join(item["text"] for item in pending_blocks + [block])
            if len(projected) > chunk_size and pending_blocks:
                flush_pending()
            pending_blocks.append(block)

    flush_pending()
    return result
