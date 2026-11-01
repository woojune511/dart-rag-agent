"""Offline, fail-closed projection of already saved table payloads.

The caller verifies original file bytes and supplies its strictly parsed tree.
Raw XML is a positional verifier, never a source for filling missing payload
values. No model, retrieval, configuration, or store code is imported here.
"""
from __future__ import annotations

import json
import re
from typing import Any

CELL_TAGS = {"TD", "TH", "TU", "TE"}
PATH_RE = re.compile(r"(?:/[A-Za-z_][A-Za-z0-9_.-]*(?:\[[1-9][0-9]*\])?)+\Z")
AXIS_NOTICE = (
    "Only literal stored row/column text and located source excerpts are supplied. "
    "Period, entity, consolidation and unit semantics are not inferred from "
    "scalar hints, acquisition dates, or file-level metadata. "
    "An adjacent excerpt is not a certified semantic assignment to this table."
)


class BundleReject(Exception):
    def __init__(self, reason: str, detail: Any = None):
        super().__init__(reason)
        self.reason, self.detail = reason, detail


def _require(condition: bool, reason: str, detail: Any = None) -> None:
    if not condition:
        raise BundleReject(reason, detail)


def _norm(value: str) -> str:
    _require(isinstance(value, str), "non_string_literal")
    return re.sub(r"[ \t]+", " ", value).strip()


def _int(value: Any, reason: str) -> int:
    _require(type(value) is int, reason)
    return value


def _node(tree: Any, locator: str) -> Any:
    _require(isinstance(locator, str) and bool(PATH_RE.fullmatch(locator)), "invalid_xpath", locator)
    matches = tree.xpath(locator)
    _require(len(matches) == 1, "non_unique_xpath", locator)
    node = matches[0]
    _require(hasattr(node, "tag") and tree.getpath(node) == locator, "noncanonical_xpath", locator)
    return node


def _span(cell: Any, name: str) -> int:
    found = [cell.get(k) for k in (name, name.lower()) if cell.get(k) is not None]
    if not found:
        return 1
    _require(all(re.fullmatch(r"[1-9][0-9]*", v.strip()) for v in found), "invalid_cell_span", name)
    values = [int(v.strip()) for v in found]
    _require(len(set(values)) == 1, "conflicting_cell_span_attributes", name)
    return values[0]


def _raw_grid(table: Any, tree: Any) -> tuple[list[list[str]], list[list[str | None]], list[dict], list[int], dict]:
    _require(not table.findall(".//TABLE"), "nested_table")
    rows = table.findall(".//TR")
    _require(bool(rows), "empty_table")
    occupancy: dict[tuple[int, int], str] = {}
    cells: dict[str, dict] = {}
    declared_raw: list[int] = []
    for ri, row in enumerate(rows):
        nearest = next((n for n in row.iterancestors() if n.tag == "TABLE"), None)
        _require(nearest is table, "foreign_table_row")
        row_cells = [c for c in row if c.tag in CELL_TAGS]
        for child in row:
            if isinstance(child.tag, str) and child.tag not in CELL_TAGS:
                _require(not "".join(child.itertext()).strip(), "unsupported_row_child", child.tag)
        if any(n.tag == "THEAD" for n in row.iterancestors() if n is not table) or (
            row_cells and all(c.tag == "TH" for c in row_cells)
        ):
            declared_raw.append(ri)
        ci = 0
        for cell in row_cells:
            while (ri, ci) in occupancy:
                ci += 1
            rs, cs = _span(cell, "ROWSPAN"), _span(cell, "COLSPAN")
            _require(ri + rs <= len(rows), "rowspan_beyond_table")
            _require(ci + cs <= 4096 and len(rows) * (ci + cs) <= 1_000_000, "grid_resource_bound")
            coordinates = [(r, c) for r in range(ri, ri + rs) for c in range(ci, ci + cs)]
            _require(not any(rc in occupancy for rc in coordinates), "overlapping_cell_spans")
            locator = tree.getpath(cell)
            raw_text = "".join(cell.itertext())
            cells[locator] = {
                "cell_locator": locator, "row_locator": tree.getpath(row),
                "source_tr_index": ri, "source_column_start": ci,
                "rowspan": rs, "colspan": cs, "raw_text": raw_text,
                "value": _norm(raw_text), "source_coordinates": coordinates,
            }
            for rc in coordinates:
                occupancy[rc] = locator
            ci += cs
    width = max((c + 1 for _, c in occupancy), default=0)
    _require(width > 0, "empty_table")
    grid, owners, kept = [], [], []
    for ri in range(len(rows)):
        row_owners = [occupancy.get((ri, c)) for c in range(width)]
        vals = [cells[owner]["value"] if owner else "" for owner in row_owners]
        # The saved grid explicitly discards all-empty rows. Record this mapping.
        if any(v.strip() for v in vals):
            kept.append(ri)
            grid.append(vals)
            owners.append(row_owners)
    _require(bool(grid), "empty_table")
    position_map = {source: i for i, source in enumerate(kept)}
    for record in cells.values():
        record["expanded_coordinates"] = [
            [position_map[r], c] for r, c in record["source_coordinates"] if r in position_map
        ]
    declared = [position_map[r] for r in declared_raw if r in position_map]
    mapping = {"kept_source_tr_indices": kept, "dropped_empty_source_tr_indices": [r for r in range(len(rows)) if r not in position_map]}
    return grid, owners, list(cells.values()), declared, mapping


def _text_partition(element: Any, tree: Any) -> list[dict]:
    """Reconstruct original cell ownership of decoded itertext offsets."""
    result: list[dict] = []
    offset = 0

    def append(text: str | None, cell: Any, boundary: bool = False) -> None:
        nonlocal offset
        identity = ({"cell_locator": tree.getpath(cell), "row_locator": tree.getpath(cell.getparent())}
                    if cell is not None else {})
        end = offset + len(text or "")
        if result and not boundary and {k: v for k, v in result[-1].items() if k != "text_span"} == identity:
            result[-1]["text_span"][1] = end
        elif text or boundary:
            result.append({**identity, "text_span": [offset, end]})
        offset = end

    def visit(node: Any, cell: Any = None) -> None:
        is_cell = node.tag in CELL_TAGS
        if is_cell:
            cell = node
        append(node.text, cell, is_cell)
        for child in node:
            if isinstance(child.tag, str):
                visit(child, cell)
            append(child.tail, cell)

    visit(element)
    return result


def _slice_segments(segments: list[dict], start: int, end: int) -> list[dict]:
    return [
        {**s, "text_span": [max(start, a) - start, min(end, b) - start]}
        for s in segments for a, b in [s["text_span"]]
        if (a < end and b > start) or (a == b and start <= a < end)
    ]


def _unique_ordered_match(labels: list[str], candidates: list[tuple[str, str]]) -> list[str]:
    """Map axis labels to distinct physical cells, rejecting repeated ambiguity."""
    paths: list[list[str]] = []

    def search(i: int, start: int, path: list[str]) -> None:
        if len(paths) > 1:
            return
        if i == len(labels):
            paths.append(path)
            return
        for j in range(start, len(candidates)):
            if candidates[j][1] == labels[i]:
                search(i + 1, j + 1, path + [candidates[j][0]])
                if len(paths) > 1:
                    return

    search(0, 0, [])
    _require(len(paths) == 1, "row_axis_not_unique_or_missing", {"labels": labels, "match_count_capped": len(paths)})
    return paths[0]


def build_bundle(meta: dict, tree: Any, expected_sha: str) -> tuple[dict | None, dict]:
    """Return a literal payload-complete table bundle and a detailed receipt.

    ``tree`` must come from raw bytes whose SHA256 equals ``expected_sha``.
    The caller owns that byte-level preflight; this function verifies all saved
    table/context hashes and locators against that supplied identity/tree.
    """
    receipt: dict = {
        "status": "REJECTED", "reason": None, "source_chunk_uid": meta.get("chunk_uid"),
        "document_sha256": expected_sha, "contexts": [], "cell_mapping": [],
        "scalar_semantic_fields_ignored": ["unit_hint", "period_text", "period_labels", "period_focus", "consolidation_scope", "company", "semantic_aliases", "normalized_value", "normalized_unit"],
        "raw_byte_hash_preflight_owner": "caller",
    }
    try:
        _require(isinstance(expected_sha, str) and bool(re.fullmatch(r"[0-9a-f]{64}", expected_sha)), "invalid_expected_hash")
        raw = meta.get("table_object_json")
        _require(isinstance(raw, str) and bool(raw), "missing_table_object")
        obj = json.loads(raw)
        _require(isinstance(obj, dict), "invalid_table_object")
        _require(obj.get("source_document_sha256") == expected_sha, "table_document_hash_mismatch")
        _require(bool(obj.get("table_id")) and obj["table_id"] == meta.get("table_source_id"), "table_identity_mismatch")
        locator = obj.get("source_table_locator")
        receipt["table_locator"] = locator
        table = _node(tree, locator)
        _require(table.tag == "TABLE", "locator_not_table")
        grid, owners, cell_records, declared, row_mapping = _raw_grid(table, tree)
        by_locator = {c["cell_locator"]: c for c in cell_records}
        receipt.update(raw_shape=[len(grid), len(grid[0])], raw_row_mapping=row_mapping)
        _require(_int(obj.get("row_count"), "invalid_row_count") == len(grid), "row_count_mismatch")
        _require(_int(obj.get("column_count"), "invalid_column_count") == len(grid[0]), "column_count_mismatch")
        header_rows = obj.get("header_rows")
        _require(isinstance(header_rows, list) and len(header_rows) <= len(grid), "invalid_header_rows")
        normalized_headers = [[_norm(v) for v in row] for row in header_rows]
        _require(normalized_headers == grid[:len(header_rows)], "header_prefix_mismatch")
        receipt["saved_header_prefix_count"] = len(header_rows)
        receipt["declared_header_row_indices"] = declared
        witnesses: dict[str, list[dict]] = {}

        def cover(owner: str | None, witness: dict) -> None:
            if owner and by_locator[owner]["value"]:
                witnesses.setdefault(owner, []).append(witness)

        for ri, row in enumerate(normalized_headers):
            for ci, value in enumerate(row):
                if value:
                    cover(owners[ri][ci], {"kind": "saved_header_prefix", "row": ri, "column": ci})

        row_records = obj.get("rows")
        _require(isinstance(row_records, list), "invalid_row_records")
        seen_rows: set[int] = set()
        for record_index, record in enumerate(row_records):
            _require(isinstance(record, dict), "invalid_row_record")
            row_id = record.get("row_id")
            match = re.fullmatch(r"([0-9]+):([0-9]+)", str(row_id))
            _require(match is not None and int(match[1]) == len(grid), "invalid_row_id", row_id)
            ri = len(header_rows) + int(match[2])
            _require(0 <= ri < len(grid) and ri not in seen_rows, "duplicate_or_outside_row_id", row_id)
            seen_rows.add(ri)
            cells = record.get("cells")
            _require(isinstance(cells, list), "invalid_record_cells")
            explicit_owners: set[str] = set()
            explicit_columns: set[int] = set()
            for ci_record, cell in enumerate(cells):
                _require(isinstance(cell, dict), "invalid_record_cell")
                ci = _int(cell.get("column_index"), "invalid_column_index")
                _require(0 <= ci < len(grid[ri]) and ci not in explicit_columns, "duplicate_or_outside_column_index")
                explicit_columns.add(ci)
                value = _norm(cell.get("value_text"))
                _require(bool(value) and value == grid[ri][ci], "cell_value_or_column_mismatch", {"row_id": row_id, "column": ci})
                expected_headers = list(dict.fromkeys(row[ci] for row in normalized_headers if row[ci]))
                observed_headers = cell.get("column_headers")
                _require(isinstance(observed_headers, list), "invalid_column_headers")
                _require([_norm(h) for h in observed_headers] == expected_headers, "column_header_mismatch", {"row_id": row_id, "column": ci})
                owner = owners[ri][ci]
                _require(owner is not None, "cell_without_original_owner")
                explicit_owners.add(owner)
                cover(owner, {"kind": "saved_row_cell", "record_index": record_index, "row_id": row_id, "column": ci, "cell_record_index": ci_record})
            labels = record.get("row_headers")
            _require(isinstance(labels, list), "invalid_row_headers")
            labels = [_norm(h) for h in labels]
            _require(all(labels) and len(labels) == len(set(labels)), "invalid_or_duplicate_row_headers")
            candidates: list[tuple[str, str]] = []
            seen_owners: set[str] = set()
            for ci, owner in enumerate(owners[ri]):
                if owner and owner not in seen_owners and owner not in explicit_owners and grid[ri][ci]:
                    candidates.append((owner, grid[ri][ci]))
                    seen_owners.add(owner)
            for owner in _unique_ordered_match(labels, candidates):
                cover(owner, {"kind": "saved_row_axis", "record_index": record_index, "row_id": row_id})

        contexts = obj.get("source_contexts")
        _require(isinstance(contexts, list), "invalid_source_contexts")
        rendered_contexts = []
        ancestors = set(table.iterancestors())
        order = {node: i for i, node in enumerate(tree.getroot().iter())}
        allowed = {"ancestor_heading", "intermediate_heading", "caption", "preceding_block", "table_text_row"}
        for idx, context in enumerate(contexts):
            _require(isinstance(context, dict), "invalid_context")
            relation = context.get("relation")
            if relation not in allowed:
                receipt["contexts"].append({"index": idx, "status": "EXCLUDED", "reason": "relation_excluded", "relation": relation})
                continue
            _require(context.get("document_sha256") == expected_sha, "context_hash_mismatch", idx)
            node = _node(tree, context.get("source_locator"))
            _require(context.get("parent_locator") == tree.getpath(node.getparent()), "context_parent_mismatch", idx)
            span = context.get("source_span")
            _require(isinstance(span, list) and len(span) == 2 and all(type(v) is int for v in span), "invalid_context_span", idx)
            start, end = span
            node_text = "".join(node.itertext())
            _require(0 <= start <= end <= len(node_text), "outside_context_span", idx)
            _require(isinstance(context.get("source_text"), str) and node_text[start:end] == context["source_text"], "context_text_span_mismatch", idx)
            if relation == "ancestor_heading":
                physical = node.tag == "TITLE" and node.getparent() in ancestors
            elif relation == "intermediate_heading":
                physical = node.tag in {"TITLE", "P"} and node.getparent() in ancestors and order[node] < order[table]
            elif relation == "caption":
                physical = node.tag == "CAPTION" and node.getparent() is table
            elif relation == "preceding_block":
                physical = node is table.getprevious() and node.getparent() is table.getparent()
            else:
                nearest = next((n for n in node.iterancestors() if n.tag == "TABLE"), None)
                physical = node.tag == "TR" and nearest is table
            _require(physical, "context_relation_mismatch", {"index": idx, "relation": relation})
            validation = {"index": idx, "relation": relation, "source_locator": context["source_locator"], "source_span": span, "status": "VERIFIED"}
            if relation == "table_text_row":
                segments = context.get("source_segments")
                _require(isinstance(segments, list), "missing_text_row_segments", idx)
                expected_segments = _slice_segments(_text_partition(node, tree), start, end)
                _require(segments == expected_segments, "context_cell_segments_mismatch", idx)
                complete_cells, clipped_cells = [], []
                for segment in segments:
                    owner = segment.get("cell_locator")
                    if not owner:
                        continue
                    _require(owner in by_locator, "foreign_context_cell", owner)
                    a, b = segment["text_span"]
                    raw_cell = by_locator[owner]["raw_text"]
                    if context["source_text"][a:b] == raw_cell:
                        cover(owner, {"kind": "saved_table_text_cell", "context_index": idx, "text_span": [a, b]})
                        complete_cells.append(owner)
                    else:
                        clipped_cells.append(owner)
                validation.update(complete_cell_witnesses=complete_cells, clipped_cell_fragments_not_used=clipped_cells)
            else:
                rendered_contexts.append({k: context[k] for k in ("relation", "source_locator", "source_span", "source_text")})
            receipt["contexts"].append(validation)

        for cell in cell_records:
            record = {k: v for k, v in cell.items() if k not in {"raw_text", "source_coordinates"}}
            record["payload_witnesses"] = witnesses.get(cell["cell_locator"], [])
            receipt["cell_mapping"].append(record)
        missing = [c["cell_locator"] for c in cell_records if c["value"] and c["cell_locator"] not in witnesses]
        receipt["nonempty_physical_cells"] = sum(bool(c["value"]) for c in cell_records)
        receipt["covered_nonempty_physical_cells"] = len(witnesses)
        _require(not missing, "payload_incomplete", {"missing_count": len(missing), "missing_cell_locators": missing})
        bundle = {
            "document_sha256": expected_sha,
            "table_locator": locator,
            "grid_coordinate_system": "zero-based expanded grid; empty source rows excluded with receipt mapping",
            "grid": grid,
            "declared_header_row_indices": declared,
            "literal_source_contexts": rendered_contexts,
            "axis_semantics": AXIS_NOTICE,
        }
        receipt.update(status="ADMITTED", reason="payload_complete_source_verified")
        return bundle, receipt
    except BundleReject as exc:
        receipt.update(reason=exc.reason, detail=exc.detail)
        return None, receipt
    except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        receipt.update(reason="invalid_payload_shape", detail=type(exc).__name__ + ": " + str(exc))
        return None, receipt
