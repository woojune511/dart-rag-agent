"""Source-verified numeric-cell units; no retrieval, inference or budget policy.

This experiment reuses frozen pure XML/position helpers. Original XML is a
witness for saved payload positions, never a source for completing missing data.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path
import re
from typing import Any

HELPER_PATH = Path(__file__).resolve().parent.parent / "table_bundle_delivery_offline_20261022" / "projector.py"
HELPER_SHA256 = "72470814e769f6a03b8ee072d2fd8e2e204f4ed742c7411dac466a7971514ba0"
if hashlib.sha256(HELPER_PATH.read_bytes()).hexdigest() != HELPER_SHA256:
    raise RuntimeError("Frozen XML helper dependency hash mismatch")
_spec = importlib.util.spec_from_file_location("_frozen_table_bundle_helpers", HELPER_PATH)
_helper = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_helper)
BundleReject = _helper.BundleReject
_require, _norm, _int = _helper._require, _helper._norm, _helper._int

IGNORED_SCALARS = [
    "unit_hint", "period_text", "period_labels", "period_focus", "company",
    "consolidation_scope", "semantic_aliases", "normalized_value", "normalized_unit",
]
AXIS_NOTICE = (
    "Only located saved literals are supplied. Column axes are literal saved "
    "leading-prefix cells, including any inferred prefix data, not automatically "
    "semantic headers. Only declared_header_source_tr_indices identifies actual "
    "XML THEAD/TH rows. Period, entity, consolidation and unit semantics are not "
    "inferred from scalar hints, acquisition dates, file metadata or adjacency. "
    "A unit is not a certified complete financial fact."
)


def _error(exc: Exception) -> dict:
    if isinstance(exc, BundleReject):
        return {"reason": exc.reason, "detail": exc.detail}
    return {"reason": "invalid_payload_shape", "detail": type(exc).__name__ + ": " + str(exc)}


def _contexts(obj: dict, tree: Any, table: Any, expected_sha: str) -> tuple[list[dict], list[dict]]:
    """Bad context is local; none of its contents leak through scalar fields."""
    contexts = obj.get("source_contexts")
    if not isinstance(contexts, list):
        return [], [{"status": "REJECTED", "reason": "invalid_source_contexts"}]
    rendered, receipts = [], []
    ancestors = set(table.iterancestors())
    order = {node: i for i, node in enumerate(tree.getroot().iter())}
    allowed = {"ancestor_heading", "intermediate_heading", "caption", "preceding_block"}
    for index, context in enumerate(contexts):
        rec = {"index": index, "status": "REJECTED"}
        try:
            _require(isinstance(context, dict), "invalid_context")
            relation = context.get("relation")
            rec["relation"] = relation
            if relation not in allowed:
                rec.update(status="EXCLUDED", reason="not_rendered_or_used_as_unit_source")
                receipts.append(rec)
                continue
            _require(context.get("document_sha256") == expected_sha, "context_hash_mismatch")
            node = _helper._node(tree, context.get("source_locator"))
            _require(context.get("parent_locator") == tree.getpath(node.getparent()), "context_parent_mismatch")
            span = context.get("source_span")
            _require(isinstance(span, list) and len(span) == 2 and all(type(v) is int for v in span), "invalid_context_span")
            start, end = span
            text = "".join(node.itertext())
            _require(0 <= start <= end <= len(text), "outside_context_span")
            _require(isinstance(context.get("source_text"), str) and text[start:end] == context["source_text"], "context_text_span_mismatch")
            if relation == "ancestor_heading":
                physical = node.tag == "TITLE" and node.getparent() in ancestors
            elif relation == "intermediate_heading":
                physical = node.tag in {"TITLE", "P"} and node.getparent() in ancestors and order[node] < order[table]
            elif relation == "caption":
                physical = node.tag == "CAPTION" and node.getparent() is table
            else:
                physical = node is table.getprevious() and node.getparent() is table.getparent()
            _require(physical, "context_relation_mismatch")
            literal = {k: context[k] for k in ("relation", "source_locator", "source_span", "source_text")}
            rendered.append(literal)
            rec.update(status="VERIFIED", source_locator=literal["source_locator"], source_span=span)
        except (BundleReject, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            rec.update(_error(exc))
        receipts.append(rec)
    return rendered, receipts


def build_units(meta: dict, tree: Any, expected_sha: str) -> tuple[dict | None, dict]:
    """Build literal dependency-closed units in physical expanded-grid order.

    Caller verifies raw bytes SHA and provides a strict tree. No query, answer,
    case ID, model, search or budget input is accepted. Zero valid numeric units
    returns None with status NO_UNITS, distinct from a global REJECTED gate.
    """
    receipt = {
        "status": "REJECTED", "reason": None, "source_chunk_uid": meta.get("chunk_uid"),
        "document_sha256": expected_sha, "helper_sha256": HELPER_SHA256,
        "raw_byte_hash_preflight_owner": "caller", "global_validation_passed": False,
        "rows": [], "contexts": [], "unit_witnesses": [], "cell_mapping": [],
        "scalar_semantic_fields_ignored": IGNORED_SCALARS,
        "semantic_axis_assignments_certified": False,
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
        table = _helper._node(tree, locator)
        _require(table.tag == "TABLE", "locator_not_table")
        receipt["table_locator"] = locator
        grid, owners, raw_cells, declared, row_map = _helper._raw_grid(table, tree)
        by_locator = {c["cell_locator"]: c for c in raw_cells}
        receipt.update(raw_shape=[len(grid), len(grid[0])], raw_row_mapping=row_map)
        _require(_int(obj.get("row_count"), "invalid_row_count") == len(grid), "row_count_mismatch")
        _require(_int(obj.get("column_count"), "invalid_column_count") == len(grid[0]), "column_count_mismatch")
        headers = obj.get("header_rows")
        _require(isinstance(headers, list) and len(headers) <= len(grid), "invalid_header_rows")
        _require(all(isinstance(row, list) for row in headers), "invalid_header_rows")
        prefix = [[_norm(value) for value in row] for row in headers]
        # Deliberately global: this frozen prefix establishes the body-row offset.
        _require(prefix == grid[:len(prefix)], "header_prefix_mismatch")
        records = obj.get("rows")
        _require(isinstance(records, list), "invalid_row_records")
        declared_raw = [row_map["kept_source_tr_indices"][r] for r in declared]
        receipt.update(global_validation_passed=True, saved_header_prefix_count=len(prefix),
                       declared_header_source_tr_indices=declared_raw)
        literal_contexts, context_receipts = _contexts(obj, tree, table, expected_sha)
        receipt["contexts"] = context_receipts
        frame = {
            "document_sha256": expected_sha, "table_locator": locator,
            "coordinate_system": "unit at=[expanded row,column], with all-empty source rows excluded; cells=[raw source TR index,start column,rowspan,colspan,literal]",
            "declared_header_source_tr_indices": declared_raw,
            "literal_source_contexts": literal_contexts, "axis_semantics": AXIS_NOTICE,
        }

        # Resolve every row address before admitting anything. Duplicate records
        # reject all declarations for that row, including the first occurrence.
        addressed: dict[int, list[tuple[int, dict, dict]]] = {}
        for record_index, record in enumerate(records):
            rr = {"record_index": record_index, "status": "REJECTED", "cells": []}
            receipt["rows"].append(rr)
            try:
                _require(isinstance(record, dict), "invalid_row_record")
                row_id = record.get("row_id")
                rr["row_id"] = row_id
                match = re.fullmatch(r"([0-9]+):([0-9]+)", str(row_id))
                _require(match is not None and int(match[1]) == len(grid), "invalid_row_id")
                ri = len(prefix) + int(match[2])
                _require(0 <= ri < len(grid), "outside_row_id")
                rr["expanded_row"] = ri
                addressed.setdefault(ri, []).append((record_index, record, rr))
            except (BundleReject, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                rr.update(_error(exc))

        admitted = []
        for ri in sorted(addressed):
            declarations = addressed[ri]
            if len(declarations) != 1:
                for _, _, rr in declarations:
                    rr.update(reason="duplicate_row_address", detail={"expanded_row": ri, "declarations": len(declarations)})
                continue
            record_index, record, rr = declarations[0]
            try:
                cells = record.get("cells")
                _require(isinstance(cells, list), "invalid_record_cells")
                positions, explicit_owners = {}, set()
                # Bad addresses contaminate row-axis exclusion; bad values do not.
                for cell_index, cell in enumerate(cells):
                    _require(isinstance(cell, dict), "invalid_record_cell")
                    ci = _int(cell.get("column_index"), "invalid_column_index")
                    _require(0 <= ci < len(grid[ri]), "outside_column_index")
                    _require(ci not in positions, "duplicate_column_address", ci)
                    owner = owners[ri][ci]
                    _require(owner is not None, "cell_without_original_owner")
                    positions[ci] = (cell_index, cell, owner)
                    explicit_owners.add(owner)
                labels = record.get("row_headers")
                _require(isinstance(labels, list), "invalid_row_headers")
                labels = [_norm(label) for label in labels]
                _require(all(labels) and len(labels) == len(set(labels)), "invalid_or_duplicate_row_headers")
                candidates, seen = [], set()
                for ci, owner in enumerate(owners[ri]):
                    if owner and owner not in seen and owner not in explicit_owners and grid[ri][ci]:
                        candidates.append((owner, grid[ri][ci]))
                        seen.add(owner)
                row_axes = _helper._unique_ordered_match(labels, candidates)
                rr.update(status="VALIDATED_AXES", row_axis_locators=row_axes,
                          row_axes_empty=not row_axes, saved_row_headers=record["row_headers"])
            except (BundleReject, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                rr.update(_error(exc))
                continue

            for ci in sorted(positions):
                cell_index, cell, owner = positions[ci]
                cr = {"cell_record_index": cell_index, "column": ci, "status": "REJECTED", "value_locator": owner}
                rr["cells"].append(cr)
                try:
                    value = _norm(cell.get("value_text"))
                    _require(bool(value) and value == grid[ri][ci], "cell_value_or_column_mismatch")
                    expected_headers = list(dict.fromkeys(row[ci] for row in prefix if row[ci]))
                    observed = cell.get("column_headers")
                    _require(isinstance(observed, list), "invalid_column_headers")
                    _require([_norm(h) for h in observed] == expected_headers, "column_header_mismatch")
                    # Include header roles of row-axis cells as well: an acquired
                    # date's own column title must not disappear beside a value.
                    dependency_columns = {
                        c for r, c in by_locator[owner]["expanded_coordinates"] if r == ri
                    }
                    for axis in row_axes:
                        dependency_columns.update(c for r, c in by_locator[axis]["expanded_coordinates"] if r == ri)
                    column_axes, seen_headers, header_witnesses = [], set(), []
                    for hr in range(len(prefix)):
                        for hc in sorted(dependency_columns):
                            howner = owners[hr][hc]
                            if howner and prefix[hr][hc]:
                                header_witnesses.append({"kind": "saved_header_prefix", "row": hr, "column": hc, "cell_locator": howner})
                                if howner not in seen_headers:
                                    column_axes.append(howner)
                                    seen_headers.add(howner)
                    column_axes.sort(key=lambda loc: (
                        by_locator[loc]["source_tr_index"], by_locator[loc]["source_column_start"], loc,
                    ))
                    unit_id = hashlib.sha256(f"{expected_sha}\0{locator}\0{ri}\0{ci}\0{owner}".encode()).hexdigest()
                    unit = {"unit_id": unit_id, "at": [ri, ci], "value": owner,
                            "row_axes": row_axes, "column_axes": column_axes}
                    witnesses = {
                        "unit_id": unit_id, "at": [ri, ci],
                        "value_witness": {"kind": "saved_row_cell", "record_index": record_index,
                                          "row_id": record["row_id"], "cell_record_index": cell_index,
                                          "column": ci, "cell_locator": owner, "saved_cell": cell},
                        "row_axis_witnesses": [{"kind": "saved_row_axis", "record_index": record_index,
                                                "row_id": record["row_id"], "cell_locator": axis,
                                                "saved_row_headers": record["row_headers"]} for axis in row_axes],
                        "header_witnesses": header_witnesses,
                        "empty_row_axes": not row_axes, "empty_column_axes": not column_axes,
                        "semantic_axes_unresolved": ["absolute_period", "entity_scope", "unit_assignment"],
                    }
                    admitted.append((unit, witnesses))
                    cr.update(status="ADMITTED", unit_id=unit_id, empty_row_axes=not row_axes,
                              empty_column_axes=not column_axes)
                except (BundleReject, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
                    cr.update(_error(exc))
            rr["status"] = "HAS_UNITS" if any(c["status"] == "ADMITTED" for c in rr["cells"]) else "NO_UNITS"

        pool, pool_witnesses, units = {}, {}, []
        for unit, witness in admitted:
            units.append(unit)
            receipt["unit_witnesses"].append(witness)
            dependencies = [unit["value"], *unit["row_axes"], *unit["column_axes"]]
            for loc in dict.fromkeys(dependencies):
                c = by_locator[loc]
                pool[loc] = [c["source_tr_index"], c["source_column_start"], c["rowspan"], c["colspan"], c["value"]]
                pool_witnesses.setdefault(loc, []).append(unit["unit_id"])
        for loc, unit_ids in pool_witnesses.items():
            c = by_locator[loc]
            receipt["cell_mapping"].append({
                **{k: c[k] for k in ("cell_locator", "row_locator", "source_tr_index", "source_column_start", "rowspan", "colspan", "value", "expanded_coordinates")},
                "dependent_unit_ids": unit_ids,
            })
        receipt["counts"] = {
            "saved_row_records": len(records), "admitted_units": len(units), "emitted_physical_cells": len(pool),
            "rejected_row_records": sum(row["status"] == "REJECTED" for row in receipt["rows"]),
            "rejected_cells_in_addressable_rows": sum(c["status"] == "REJECTED" for row in receipt["rows"] for c in row["cells"]),
            "verified_contexts": len(literal_contexts),
            "rejected_contexts": sum(c["status"] == "REJECTED" for c in context_receipts),
        }
        if not units:
            receipt.update(status="NO_UNITS", reason="no_valid_numeric_units")
            return None, receipt
        receipt.update(status="ADMITTED", reason="independent_units_source_verified")
        return {"frame": frame, "cells": pool, "units": units}, receipt
    except (BundleReject, ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
        receipt.update(_error(exc))
        return None, receipt
