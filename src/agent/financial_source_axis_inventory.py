"""Bounded observed axes for the existing planner, never selection authority."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping, Sequence

from src.agent.financial_reconciliation_candidates import _table_record_bundle
from src.agent.financial_source_scope import _document_identity, candidate_section_path


def _bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _headers(value: Any) -> list[str]:
    # Copy whole parser axes, including their hierarchy/qualifiers. Never
    # tokenize a name, infer an entity, or read labels from contextual prose.
    return [item for item in value if isinstance(item, str) and item.strip()] if isinstance(value, (list, tuple)) else []


def build_source_axis_inventory(
    metadata_rows: Sequence[Mapping[str, Any]], *, query: str, max_axes: int = 64, max_bytes: int = 16384,
) -> dict[str, Any]:
    """Expose query-literal axes from already-hydrated, report-scoped metadata.

    Literal occurrence only budgets planner context; it is NOT a subject match.
    Show each whole axis path and one deterministic observed record reference.
    No scalar/body extraction, source-only aliases, store access or calls.
    """
    records: dict[tuple, dict[str, Any]] = {}
    bundles: dict[tuple, tuple] = {}
    seen: set[tuple] = set()
    unlocated = 0
    for metadata in metadata_rows:
        payload_key = tuple(value if isinstance(value, str) else _bytes(value)
            for key in ("table_object_json", "table_row_records_json", "table_value_records_json")
            for value in [metadata.get(key) or ""])
        if payload_key not in bundles:
            bundles[payload_key] = _table_record_bundle(metadata)
        table, rows, values = bundles[payload_key]
        if not rows and not values:
            continue
        document_id = _document_identity(metadata)
        table_id = str(metadata.get("table_source_id") or metadata.get("source_table_id")
            or metadata.get("table_id") or table.get("table_id") or "")
        if not document_id or table_id.strip().casefold() in {"", "unknown", "?"}:
            unlocated += 1
            continue
        section = candidate_section_path(metadata)
        attachment = (document_id, table_id, section, payload_key)
        if attachment in seen:
            continue
        seen.add(attachment)

        def add(axis: str, headers: list[str], reference: dict[str, Any]) -> None:
            if not headers or not reference:
                return
            key = (document_id, section, axis, tuple(headers))
            reference = {"table_source_id": table_id, **reference}
            # Identical named axes repeated across tables add no new planning
            # information. Keep one observed example, not merged cell authority.
            row = {"document_id": document_id, "section_path": list(section),
                "axis": axis, "headers": headers, "example_reference": reference}
            old = records.get(key)
            if old is None or _bytes(reference) < _bytes(old["example_reference"]):
                records[key] = row

        for row in rows:
            row_id = row.get("row_id")
            if not isinstance(row_id, str) or not row_id:
                continue
            add("row", _headers(row.get("row_headers")) or _headers([row.get("row_label")]), {"row_id": row_id})
            for cell in row.get("cells") or []:
                if isinstance(cell, Mapping) and isinstance(cell.get("cell_id"), str) and cell["cell_id"]:
                    add("column", _headers(cell.get("column_headers")), {"row_id": row_id, "cell_id": cell["cell_id"]})
        # Values can preserve axes absent from the row projection; dedupe by
        # complete axis, not value or attachment count. No semantic_aliases.
        for value in values:
            value_id = value.get("value_id")
            if not isinstance(value_id, str) or not value_id:
                continue
            reference = {"value_id": value_id}
            add("row", _headers(value.get("row_headers")) or _headers([value.get("row_label")]), reference)
            add("column", _headers(value.get("column_headers")), reference)

    matching = []
    for row in records.values():
        spans = [{"header_index": index, "query_span": [start, start + len(header)]}
            for index, header in enumerate(row["headers"]) if (start := query.find(header)) >= 0]
        if spans:
            matching.append({**row, "query_matches": spans})
    # Original request order, then observed location; no semantic score or
    # preference for shorter names, numeric cells, metric or company.
    matching.sort(key=lambda row: (min(match["query_span"][0] for match in row["query_matches"]),
        row["document_id"], row["section_path"], row["axis"], row["headers"]))
    visible = []
    for row in matching:
        if len(visible) >= max_axes or len(_bytes([*visible, row])) > max_bytes:
            break
        visible.append(row)
    encoded = _bytes(visible)
    return {"schema": "source_axis_inventory_v1", "authority": "planning_hint_only", "axes": visible,
        "fingerprint": hashlib.sha256(encoded).hexdigest(), "serialized_axes_bytes": len(encoded),
        "observed_axis_count": len(records), "matching_axis_count": len(matching),
        "visible_axis_count": len(visible), "omitted_matching_axis_count": len(matching) - len(visible),
        "unlocated_metadata_count": unlocated, "truncated": len(matching) != len(visible),
        "coverage": "observed_query_literal_axes_only"}
