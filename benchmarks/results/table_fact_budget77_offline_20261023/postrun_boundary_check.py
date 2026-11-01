"""Two-cap saved-output audit adapted from the prior independent checker.

Same task context and prior review code; not a fresh blind review.
Never calls a projector, retriever or model.

Only the existing XML sanitizer is reused. Occupancy, row-axis matching,
stored-witness checks and full-packet budget verification are implemented here.
"""
from __future__ import annotations

import copy
import hashlib
import json
import re
import socket
import sys
import time
from collections import Counter, defaultdict
from io import BytesIO
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
FACT = OUT.parent / "table_fact_units_offline_20261023"
START = time.monotonic()
FIELD = "table_fact_units"
CAPS = {"64KiB": 65536, "160KiB": 163840}
PRIOR_CHECKER_SHA256 = "b929a75df87a26789e6c3bcc54fb724b263f47789a16518f4cdb4f0eb8e9fcb8"
CELL_TAGS = {"TD", "TH", "TU", "TE"}
PATH_PATTERN = re.compile(r"(?:/[A-Za-z_][A-Za-z0-9_.-]*(?:\[[1-9][0-9]*\])?)+\Z")
WIRE_SCHEMA = {
    "cells": "[source_TR_index,source_start_column,rowspan,colspan,literal]; zero-based original physical origins",
    "units": "[expanded_row,column,value_cell_index,row_axis_cell_indices,column_prefix_cell_indices]; zero-based pool indices local to this table; expanded rows exclude all-empty source rows",
    "meaning": "Located literal cell dependencies only; period, entity, scope and unit assignment remain unverified semantics",
}
ISSUES = []


def denied(*args, **kwargs):
    raise RuntimeError("This audit does not permit network access")


socket.create_connection = socket.socket.connect = socket.socket.connect_ex = socket.getaddrinfo = denied


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False, separators=(",", ":")).encode("utf-8")


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def file_hash(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def check(condition, kind, detail):
    if not condition:
        ISSUES.append({"kind": kind, "detail": detail})
    return bool(condition)


def demand(condition, kind):
    if not condition:
        raise ValueError(kind)


def progress(phase, **values):
    print(json.dumps({"phase": phase, "elapsed_seconds": round(time.monotonic() - START, 2), **values}, ensure_ascii=False), flush=True)


def literal(value):
    demand(isinstance(value, str), "literal is not string")
    return re.sub(r"[ \t]+", " ", value).strip()


def unique_node(tree, xpath):
    demand(isinstance(xpath, str) and PATH_PATTERN.fullmatch(xpath) is not None, "invalid canonical XPath")
    nodes = tree.xpath(xpath)
    demand(len(nodes) == 1 and hasattr(nodes[0], "tag"), "nonunique XPath")
    demand(tree.getpath(nodes[0]) == xpath, "XPath is not canonical")
    return nodes[0]


def nearest_table(node):
    parent = node.getparent()
    while parent is not None:
        if parent.tag == "TABLE":
            return parent
        parent = parent.getparent()
    return None


def span_value(cell, name):
    values = [cell.attrib[k].strip() for k in (name, name.lower()) if k in cell.attrib]
    if not values:
        return 1
    demand(all(re.fullmatch(r"[1-9][0-9]*", v) for v in values), "invalid span")
    values = [int(v) for v in values]
    demand(len(set(values)) == 1, "conflicting spans")
    return values[0]


def independent_geometry(tree, table):
    """Build physical occupancy from raw XML without importing project helpers."""
    demand(table.tag == "TABLE", "locator is not TABLE")
    demand(not any(n.tag == "TABLE" for n in table.iterdescendants()), "nested table")
    rows = list(table.iter("TR"))
    demand(rows, "no rows")
    occupied = {}
    cells = {}
    declared = []
    for raw_row, row in enumerate(rows):
        demand(nearest_table(row) is table, "foreign row")
        source_cells = [n for n in row if n.tag in CELL_TAGS]
        for child in row:
            if isinstance(child.tag, str) and child.tag not in CELL_TAGS:
                demand(not "".join(child.itertext()).strip(), "unsupported nonempty row child")
        parent = row.getparent()
        in_thead = False
        while parent is not None and parent is not table:
            in_thead |= parent.tag == "THEAD"
            parent = parent.getparent()
        if in_thead or (source_cells and all(c.tag == "TH" for c in source_cells)):
            declared.append(raw_row)
        column = 0
        for cell in source_cells:
            while (raw_row, column) in occupied:
                column += 1
            rs, cs = span_value(cell, "ROWSPAN"), span_value(cell, "COLSPAN")
            demand(raw_row + rs <= len(rows), "span exceeds table rows")
            demand(column + cs <= 4096 and len(rows) * (column + cs) <= 1_000_000, "grid resource limit")
            locator = tree.getpath(cell)
            coords = [(r, c) for r in range(raw_row, raw_row + rs) for c in range(column, column + cs)]
            demand(all(x not in occupied for x in coords), "overlapping physical spans")
            value = literal("".join(cell.itertext()))
            cells[locator] = {"cell_locator": locator, "row_locator": tree.getpath(row),
                              "source_tr_index": raw_row, "source_column_start": column,
                              "rowspan": rs, "colspan": cs, "value": value,
                              "raw_coordinates": coords}
            occupied.update({coord: locator for coord in coords})
            column += cs
    width = max((c for _, c in occupied), default=-1) + 1
    demand(width > 0, "empty table width")
    all_rows = [[cells[occupied[(r, c)]]["value"] if (r, c) in occupied else "" for c in range(width)] for r in range(len(rows))]
    kept = [r for r, vals in enumerate(all_rows) if any(v.strip() for v in vals)]
    demand(kept, "all rows empty")
    compressed = {r: i for i, r in enumerate(kept)}
    grid = [all_rows[r] for r in kept]
    owners = [[occupied.get((r, c)) for c in range(width)] for r in kept]
    for cell in cells.values():
        cell["expanded_coordinates"] = [[compressed[r], c] for r, c in cell["raw_coordinates"] if r in compressed]
    return {"cells": cells, "grid": grid, "owners": owners, "width": width,
            "kept": kept, "dropped": [r for r in range(len(rows)) if r not in compressed],
            "declared_raw": [r for r in declared if r in compressed]}


def ordered_axis_match(labels, candidates):
    """Independent capped dynamic programming, not projector's DFS helper."""
    states = [[[]]] + [[] for _ in labels]
    for locator, value in candidates:
        for n in range(len(labels), 0, -1):
            if labels[n - 1] == value:
                extra = [path + [locator] for path in states[n - 1]]
                states[n] = (states[n] + extra)[:2]
    demand(len(states[-1]) == 1, "row axis is missing or ambiguous")
    return states[-1][0]


def validate_context(context, tree, table, source_sha, node_order):
    demand(isinstance(context, dict), "context is not dict")
    relation = context.get("relation")
    allowed = {"ancestor_heading", "intermediate_heading", "caption", "preceding_block"}
    if relation not in allowed:
        return None, "EXCLUDED"
    demand(context.get("document_sha256") == source_sha, "context hash mismatch")
    node = unique_node(tree, context.get("source_locator"))
    demand(node.getparent() is not None and context.get("parent_locator") == tree.getpath(node.getparent()), "context parent mismatch")
    span = context.get("source_span")
    demand(isinstance(span, list) and len(span) == 2 and all(type(v) is int for v in span), "invalid context span")
    text = "".join(node.itertext())
    start, end = span
    demand(0 <= start <= end <= len(text), "context span outside node")
    demand(isinstance(context.get("source_text"), str) and text[start:end] == context["source_text"], "context text mismatch")
    ancestors = set(table.iterancestors())
    if relation == "ancestor_heading":
        physical = node.tag == "TITLE" and node.getparent() in ancestors
    elif relation == "intermediate_heading":
        physical = node.tag in {"TITLE", "P"} and node.getparent() in ancestors and node_order[node] < node_order[table]
    elif relation == "caption":
        physical = node.tag == "CAPTION" and node.getparent() is table
    else:
        physical = node is table.getprevious() and node.getparent() is table.getparent()
    demand(physical, "context physical relation mismatch")
    return {k: context[k] for k in ("relation", "source_locator", "source_span", "source_text")}, "VERIFIED"


def row_contract(obj, geom, record_index):
    records = obj["rows"]
    record = records[record_index]
    demand(isinstance(record, dict), "invalid saved row")
    prefix = [[literal(v) for v in row] for row in obj["header_rows"]]
    total = len(geom["grid"])

    def address(rec):
        if not isinstance(rec, dict):
            return None
        match = re.fullmatch(r"([0-9]+):([0-9]+)", str(rec.get("row_id")))
        if match is None or int(match[1]) != total:
            return None
        result = len(prefix) + int(match[2])
        return result if 0 <= result < total else None

    row = address(record)
    demand(row is not None, "invalid stored row address")
    demand(sum(address(rec) == row for rec in records) == 1, "duplicate saved row address")
    positions = {}
    explicit = set()
    demand(isinstance(record.get("cells"), list), "invalid row cells")
    for cell_index, cell in enumerate(record["cells"]):
        demand(isinstance(cell, dict), "invalid saved cell")
        col = cell.get("column_index")
        demand(type(col) is int and 0 <= col < geom["width"] and col not in positions, "invalid or duplicate saved column")
        owner = geom["owners"][row][col]
        demand(owner is not None, "saved value has no physical owner")
        positions[col] = (cell_index, cell, owner)
        explicit.add(owner)
    labels = record.get("row_headers")
    demand(isinstance(labels, list), "invalid row labels")
    labels = [literal(v) for v in labels]
    demand(all(labels) and len(labels) == len(set(labels)), "empty or duplicate row labels")
    candidate_list, seen = [], set()
    for col, owner in enumerate(geom["owners"][row]):
        if owner is not None and owner not in seen and owner not in explicit and geom["grid"][row][col]:
            candidate_list.append((owner, geom["grid"][row][col]))
            seen.add(owner)
    axes = ordered_axis_match(labels, candidate_list)
    return record, row, positions, axes, prefix


def main():
    demand((OUT / "results.json").is_file(), "Wait for root results-complete signal before running")
    freeze = load(OUT / "freeze.json")
    for name, sha in freeze["files"].items():
        check(file_hash(OUT / name) == sha, "frozen_file_changed", name)
    for name, sha in freeze["dependencies"].items():
        check(file_hash(ROOT / name) == sha, "frozen_dependency_changed", name)
    check(file_hash(FACT / "postrun_boundary_check.py") == PRIOR_CHECKER_SHA256, "prior_checker_changed", None)
    progress("loading_saved_outputs")
    panel = load(OUT.parent / "full77_sol_top12_20261020/panel.json")
    ranks = {x["case_id"]: x for x in load(OUT.parent / "tokenizer_nori_idf_offline_20261022/results.json")}
    requests = {x["case_id"]: x for x in load(OUT.parent / "full77_sol_top12_20261020/requests.json")}
    results = load(OUT / "results.json")
    by_case = {x["case_id"]: x for x in results}
    old_results = {x["case_id"]: x for x in load(FACT / "results.json")}
    projections = load(FACT / "projections.json")
    contract = load(OUT / "evaluation_contract.json")
    case_ids = [c["case_id"] for c in panel]
    check(len(case_ids) == len(set(case_ids)) == 77, "case_count", len(case_ids))
    check(case_ids == [c["case_id"] for c in results], "case_order", None)
    check(set(case_ids) == {c["case_id"] for c in contract["cases"]}, "evaluation_population", None)
    groups = dict(Counter(c["group"] for c in contract["cases"]))
    del contract
    metadata = {}
    needed = set()
    attached = defaultdict(lambda: {"unit_ids": set(), "cell_locators": set(), "case_ids": set()})
    arm_attached = {label: defaultdict(lambda: {"unit_ids": set(), "cell_locators": set()}) for label in CAPS}
    table_status = {label: Counter() for label in CAPS}
    unit_status = {label: Counter() for label in CAPS}
    case_checks = []
    change_rows = []
    total_unit_proposals = 0
    replay64_count = 0
    for number, case in enumerate(panel, 1):
        cid, base = case["case_id"], case["packet"]
        result, rank = by_case[cid], ranks[cid]
        a = load(FACT / "packets" / f"{cid}_A12.json")
        check(a == base, "original_A12_identity", cid)
        check(json.loads(requests[cid]["body"]["input"][1]["content"]) == a, "original_request_identity", cid)
        selection = [h["metadata"]["chunk_uid"] for h in case["hits"]]
        check(selection == result["selected12"] == [x["uid"] for x in rank["rrf"]["A12"][:12]] and len(selection) == 12, "selected12_order", cid)
        check(result["candidate_order_score_sha256"] == digest({"dense": rank["dense"], "lexical": rank["lexical"]["A12"], "rrf": rank["rrf"]["A12"]}), "candidate_order_scores", cid)
        ids = [d["chunk_id"] for d in a["documents"]]
        check(ids == result["delivered_ids"] == rank["packets"]["A12"]["uids"], "actual_original_document_ids_order", cid)
        check(a["query"] == case["question"] == rank["query"] and a["report_scope"] == case["report_scope"] == rank["report_scope"], "query_scope_parity", cid)
        check(len(encoded(a)) == result["baseline_bytes"] == rank["packets"]["A12"]["bytes"], "baseline_bytes", cid)
        check(digest(a) == result["baseline_packet_sha256"], "baseline_packet_hash", cid)
        for doc in a["documents"]:
            uid = doc["chunk_id"]
            needed.add(uid)
            hit = next(h for h in case["hits"] if h["metadata"]["chunk_uid"] == uid)
            check(doc["text"] == hit["text"] and all(hit["metadata"].get(k) == v for k, v in doc["context"].items()), "saved_hit_packet_parity", [cid, uid])
            if uid in metadata:
                check(metadata[uid] == hit["metadata"], "same_UID_metadata_consistency", uid)
            else:
                metadata[uid] = hit["metadata"]
        inventories = {}
        role_inventories = {}
        for label, cap in CAPS.items():
            before = len(ISSUES)
            arm = result["arms"][label]
            t = load(OUT / "packets" / f"{cid}_{label}.json")
            check(arm["cap_bytes"] == cap, "declared_cap", [cid, label])
            check(ids == [d["chunk_id"] for d in t["documents"]], "actual_documents_ids_order", [cid, label])
            stripped = copy.deepcopy(t)
            for doc in stripped["documents"]:
                doc.pop(FIELD, None)
            check(stripped == a, "all_original_fields_preserved", [cid, label])
            check(len(encoded(t)) == arm["packet_bytes"] <= cap, "experimental_bytes_cap", [cid, label])
            check(digest(t) == arm["packet_sha256"], "experimental_packet_hash", [cid, label])
            if label == "64KiB":
                replay_ok = (t == load(FACT / "packets" / f"{cid}_FCT12.json") and arm["decisions"] == old_results[cid]["decisions"] and arm["packet_sha256"] == old_results[cid]["experimental_packet_sha256"])
                check(replay_ok, "exact_64KiB_previous_packet_and_decisions", cid)
                replay64_count += replay_ok
            current = copy.deepcopy(a)
            seen_tables = set()
            expected_decisions = []
            inventory = {}
            roles = {role: set() for role in ("value_cells", "row_axes", "column_axes", "literal_contexts")}
            for position, doc in enumerate(current["documents"], 1):
                uid = doc["chunk_id"]
                item = projections[uid]
                obj = json.loads(metadata[uid].get("table_object_json") or "{}")
                key = obj.get("source_document_sha256", "") + "|" + obj.get("source_table_locator", "") if obj else None
                check(key == item["physical_key"], "physical_key_from_saved_payload", uid)
                projection = item["projection"]
                decision = {"uid": uid, "position": position, "physical_key": key}
                if key is None:
                    decision.update(status="no_table_payload", reason=item["receipt"].get("reason"))
                elif key in seen_tables:
                    decision.update(status="duplicate_table_first_owner_only")
                else:
                    seen_tables.add(key)
                    if projection is None:
                        status = "no_valid_numeric_units" if item["receipt"].get("status") == "NO_UNITS" else "rejected_global_validation"
                        decision.update(status=status, reason=item["receipt"].get("reason"))
                    elif not projection["units"]:
                        decision.update(status="no_valid_numeric_units", reason=item["receipt"].get("reason"))
                    else:
                        units = projection["units"]
                        check([u["at"] for u in units] == sorted(u["at"] for u in units), "physical_unit_order", uid)
                        check(len({u["unit_id"] for u in units}) == len(units), "unique_unit_IDs", uid)
                        wire = {**copy.deepcopy(projection["frame"]), "source_id": doc["source_id"], "schema": WIRE_SCHEMA, "cells": [], "units": []}
                        locators, records = [], []
                        for unit in units:
                            total_unit_proposals += 1
                            proposed = copy.deepcopy(wire)
                            next_locs = list(locators)
                            for loc in [*unit["row_axes"], *unit["column_axes"], unit["value"]]:
                                if loc not in next_locs:
                                    next_locs.append(loc)
                                    proposed["cells"].append(projection["cells"][loc])
                            indices = {loc: i for i, loc in enumerate(next_locs)}
                            proposed["units"].append([*unit["at"], indices[unit["value"]], [indices[x] for x in unit["row_axes"]], [indices[x] for x in unit["column_axes"]]])
                            old_bytes = len(encoded(current))
                            had_wire = FIELD in doc
                            old_wire = doc.get(FIELD)
                            doc[FIELD] = proposed
                            actual_size = len(encoded(current))
                            record = {"unit_id": unit["unit_id"], "at": unit["at"], "proposed_packet_bytes": actual_size, "incremental_bytes": actual_size - old_bytes}
                            if actual_size <= cap:
                                wire, locators = proposed, next_locs
                                record.update(status="attached", wire_unit_index=len(wire["units"]) - 1)
                                attached[uid]["unit_ids"].add(unit["unit_id"])
                                attached[uid]["cell_locators"].update(next_locs)
                                attached[uid]["case_ids"].add(cid + "|" + label)
                                arm_attached[label][uid]["unit_ids"].add(unit["unit_id"])
                                arm_attached[label][uid]["cell_locators"].update(next_locs)
                                ikey = uid + "|" + unit["unit_id"]
                                inventory[ikey] = {"unit": unit, "frame": projection["frame"], "cells": {loc: projection["cells"][loc] for loc in [unit["value"], *unit["row_axes"], *unit["column_axes"]]}}
                                roles["value_cells"].add(uid + "|" + unit["value"])
                                roles["row_axes"].update(uid + "|" + loc for loc in unit["row_axes"])
                                roles["column_axes"].update(uid + "|" + loc for loc in unit["column_axes"])
                            else:
                                if had_wire:
                                    doc[FIELD] = old_wire
                                else:
                                    del doc[FIELD]
                                record.update(status="rejected_byte_budget")
                            unit_status[label][record["status"]] += 1
                            records.append(record)
                        decision["units"] = records
                        if wire["units"]:
                            demand(doc[FIELD] == wire, "audit bookkeeping error")
                            referenced = {i for u in wire["units"] for i in [u[2], *u[3], *u[4]]}
                            check(referenced == set(range(len(wire["cells"]))), "same_table_pool_no_orphans", [cid, label, uid])
                            roles["literal_contexts"].update(uid + "|" + digest(ctx) for ctx in wire["literal_source_contexts"])
                            decision.update(status="attached", unit_count=len(wire["units"]), unique_physical_cells=len(wire["cells"]), cell_pool_locators=locators,
                                            packet_bytes_after=len(encoded(current)), projection_sha256=digest(wire))
                        else:
                            check(FIELD not in doc, "no_standalone_frame", [cid, label, uid])
                            decision.update(status="rejected_byte_budget", unit_count=0)
                table_status[label][decision["status"]] += 1
                expected_decisions.append(decision)
            check(expected_decisions == arm["decisions"], "all_budget_ownership_decisions_exact", [cid, label])
            check(current == t, "atomic_full_packet_reconstruction", [cid, label])
            check(arm["attached_tables"] == sum(x["status"] == "attached" for x in expected_decisions), "table_count", [cid, label])
            check(arm["attached_units"] == sum(x.get("unit_count", 0) for x in expected_decisions), "unit_count", [cid, label])
            check(arm["budget_rejected_units"] == sum(u["status"] == "rejected_byte_budget" for d in expected_decisions for u in d.get("units", [])), "rejected_unit_count", [cid, label])
            case_checks.append({"case_id": cid, "arm": label, "original_delivered_documents": len(ids), "baseline_bytes": len(encoded(a)), "experimental_bytes": len(encoded(t)),
                                "attached_tables": arm["attached_tables"], "attached_units": arm["attached_units"], "issues": len(ISSUES) - before})
            inventories[label], role_inventories[label] = inventory, roles
        small, large = inventories["64KiB"], inventories["160KiB"]
        common = small.keys() & large.keys()
        changed = sorted(k for k in common if small[k] != large[k])
        lost = sorted(small.keys() - large.keys())
        added = sorted(large.keys() - small.keys())
        expected_changes = {"retained": len(common), "added": added, "lost": lost, "changed_payloads": len(changed)}
        check(result["unit_changes"] == expected_changes, "between_cap_unit_change_counts", cid)
        check(not changed, "retained_units_changed_payload_or_axes", [cid, changed])
        roles = {}
        for role in role_inventories["64KiB"]:
            sa, la = role_inventories["64KiB"][role], role_inventories["160KiB"][role]
            roles[role] = {"retained": len(sa & la), "added": sorted(la - sa), "lost": sorted(sa - la)}
        change_rows.append({"case_id": cid, "unit_changes": expected_changes, "retained_changed_unit_keys": changed, "physical_dependency_role_changes": roles})
        if number % 10 == 0 or number == len(panel):
            progress("mechanical_cases_both_caps", completed=number, total=len(panel), issues=len(ISSUES))
    check(needed == set(projections), "projection_UID_coverage", [len(needed), len(projections)])
    del ranks, requests, by_case, old_results

    sys.path.insert(0, str(ROOT))
    from lxml import etree
    from src.processing.financial_parser import _sanitize_xml_like_text
    sources = load(FACT / "source_checks.json")
    before_manifest = load(OUT / "before.json")["files"]
    preparation = load(OUT.parent / "full77_v12_final_20261018/preparation.json")
    prep_paths = {r["metadata"]["rcept_no"]: Path(r["path"]) for r in preparation["reports"]}
    trees, raw_hashes, orders, source_audit = {}, {}, {}, []
    for receipt, source in sources.items():
        path = ROOT / source["path"]
        data = path.read_bytes()
        raw_hash = hashlib.sha256(data).hexdigest()
        check(Path(source["path"]) == prep_paths[receipt], "original_source_path", receipt)
        check(raw_hash == source["sha256"] == before_manifest[source["path"].replace("\\", "/")]["sha256"], "raw_source_hash", receipt)
        clean, changes = _sanitize_xml_like_text(data.decode("utf-8"))
        parser = etree.XMLParser(no_network=True, resolve_entities=False, recover=False, huge_tree=True)
        tree = etree.parse(BytesIO(clean.encode("utf-8")), parser)
        check(not len(parser.error_log), "strict_parse_diagnostics", receipt)
        trees[receipt], raw_hashes[receipt] = tree, raw_hash
        orders[receipt] = {node: i for i, node in enumerate(tree.getroot().iter())}
        source_audit.append({"receipt": receipt, "path": source["path"], "raw_sha256": raw_hash, "sanitizer_changes_in_memory": changes, "strict_parse_errors": len(parser.error_log)})
    progress("source_trees_loaded", reports=len(trees))
    geom_cache = {}
    unit_checks = 0
    cell_checks = 0
    contexts_checked = 0
    context_validation_counts = Counter()
    fragments = Counter()
    physical_cells = set()
    physical_units = set()
    physical_tables = set()
    binding_rows = []
    for ordinal, (uid, delivered) in enumerate(sorted(attached.items()), 1):
        begin = len(ISSUES)
        meta = metadata[uid]
        item = projections[uid]
        projection, receipt = item["projection"], item["receipt"]
        obj = json.loads(meta["table_object_json"])
        rcept = meta["rcept_no"]
        tree, raw_hash = trees[rcept], raw_hashes[rcept]
        frame = projection["frame"]
        key = item["physical_key"]
        physical_tables.add(key)
        try:
            demand(obj["source_document_sha256"] == raw_hash == frame["document_sha256"] == receipt["document_sha256"], "source identity mismatch")
            demand(obj["table_id"] == meta["table_source_id"] and obj["table_id"], "table identity mismatch")
            demand(frame["table_locator"] == obj["source_table_locator"] == receipt["table_locator"], "table locator mismatch")
            table = unique_node(tree, frame["table_locator"])
            if key not in geom_cache:
                geom_cache[key] = independent_geometry(tree, table)
            geom = geom_cache[key]
            demand(obj["row_count"] == len(geom["grid"]) and obj["column_count"] == geom["width"], "saved shape mismatch")
            prefix = [[literal(v) for v in row] for row in obj["header_rows"]]
            demand(prefix == geom["grid"][:len(prefix)], "global saved prefix mismatch")
            demand(frame["declared_header_source_tr_indices"] == geom["declared_raw"], "declared header role mismatch")
            demand(receipt["raw_row_mapping"] == {"kept_source_tr_indices": geom["kept"], "dropped_empty_source_tr_indices": geom["dropped"]}, "raw row map mismatch")
            demand(receipt["raw_shape"] == [len(geom["grid"]), geom["width"]], "receipt raw shape mismatch")
            demand(set(frame) == {"document_sha256", "table_locator", "coordinate_system", "declared_header_source_tr_indices", "literal_source_contexts", "axis_semantics"}, "unexpected frame field")
            demand("not a certified complete financial fact" in frame["axis_semantics"], "missing semantic limitation")
            valid_contexts = []
            ctxs = obj.get("source_contexts")
            if isinstance(ctxs, list):
                for context in ctxs:
                    try:
                        accepted, status = validate_context(context, tree, table, raw_hash, orders[rcept])
                    except (ValueError, TypeError, KeyError, IndexError, AttributeError):
                        accepted, status = None, "REJECTED"
                    context_validation_counts[status] += 1
                    if accepted is not None:
                        valid_contexts.append(accepted)
                        contexts_checked += 1
            else:
                context_validation_counts["REJECTED_CONTAINER"] += 1
            demand(valid_contexts == frame["literal_source_contexts"], "included context hash/span/physical relation mismatch")
            unit_map = {u["unit_id"]: u for u in projection["units"]}
            witnesses = {w["unit_id"]: w for w in receipt["unit_witnesses"]}
            demand(len(unit_map) == len(projection["units"]) and len(witnesses) == len(receipt["unit_witnesses"]), "duplicate unit witness identity")
            cell_receipts = {c["cell_locator"]: c for c in receipt["cell_mapping"]}
            demand(len(cell_receipts) == len(receipt["cell_mapping"]), "duplicate cell receipt identity")
            verified_roles = set()
            row_cache = {}
            for unit_id in sorted(delivered["unit_ids"]):
                unit = unit_map[unit_id]
                witness = witnesses[unit_id]
                vw = witness["value_witness"]
                record_index = vw["record_index"]
                if record_index not in row_cache:
                    row_cache[record_index] = row_contract(obj, geom, record_index)
                record, row, positions, row_axes, prefix = row_cache[record_index]
                col = vw["column"]
                index, cell, owner = positions[col]
                demand(vw["kind"] == "saved_row_cell" and vw["cell_record_index"] == index and vw["saved_cell"] == cell and vw["row_id"] == record["row_id"], "saved value witness record mismatch")
                demand(unit["at"] == witness["at"] == [row, col], "unit coordinate mismatch")
                demand(unit["value"] == vw["cell_locator"] == owner, "unit value physical owner mismatch")
                value = literal(cell["value_text"])
                demand(value and value == geom["grid"][row][col], "stored value versus raw cell mismatch")
                expected_headers = list(dict.fromkeys(hr[col] for hr in prefix if hr[col]))
                demand([literal(v) for v in cell["column_headers"]] == expected_headers, "saved cell header stack mismatch")
                demand(unit["row_axes"] == row_axes, "row axis ownership mismatch")
                expected_rw = [{"kind": "saved_row_axis", "record_index": record_index, "row_id": record["row_id"], "cell_locator": loc, "saved_row_headers": record["row_headers"]} for loc in row_axes]
                demand(witness["row_axis_witnesses"] == expected_rw, "stored row-axis witness mismatch")
                columns = {c for loc in [owner, *row_axes] for rr, c in geom["cells"][loc]["expanded_coordinates"] if rr == row}
                column_axes, header_witnesses = [], []
                for pr in range(len(prefix)):
                    for pc in sorted(columns):
                        loc = geom["owners"][pr][pc]
                        if loc is not None and prefix[pr][pc]:
                            header_witnesses.append({"kind": "saved_header_prefix", "row": pr, "column": pc, "cell_locator": loc})
                            if loc not in column_axes:
                                column_axes.append(loc)
                demand(unit["column_axes"] == column_axes and witness["header_witnesses"] == header_witnesses, "complete column-prefix dependency mismatch")
                expected_id = hashlib.sha256(f"{raw_hash}\0{frame['table_locator']}\0{row}\0{col}\0{owner}".encode()).hexdigest()
                demand(unit_id == expected_id, "physical unit ID mismatch")
                demand(witness["empty_row_axes"] == (not row_axes) and witness["empty_column_axes"] == (not column_axes), "axis absence receipt mismatch")
                if not row_axes:
                    fragments["delivered_unique_UID_units_without_row_axes"] += 1
                if not column_axes:
                    fragments["delivered_unique_UID_units_without_column_axes"] += 1
                dependencies = set([owner, *row_axes, *column_axes])
                for loc in dependencies:
                    demand(unit_id in cell_receipts[loc]["dependent_unit_ids"], "cell receipt misses dependent unit")
                verified_roles.update(dependencies)
                physical_units.add((key, row, col, owner))
                unit_checks += 1
            demand(verified_roles == delivered["cell_locators"], "pool contains unreferenced or unvalidated raw-only cell")
            for loc in sorted(delivered["cell_locators"]):
                raw = geom["cells"][loc]
                expected_cell = [raw["source_tr_index"], raw["source_column_start"], raw["rowspan"], raw["colspan"], raw["value"]]
                demand(projection["cells"][loc] == expected_cell, "wire physical cell literal/span mismatch")
                cr = cell_receipts[loc]
                for field in ("cell_locator", "row_locator", "source_tr_index", "source_column_start", "rowspan", "colspan", "value", "expanded_coordinates"):
                    demand(cr[field] == raw[field], "physical cell receipt mismatch: " + field)
                node = unique_node(tree, loc)
                demand(nearest_table(node) is table and node.tag in CELL_TAGS, "pool cell in foreign table")
                physical_cells.add((key, loc))
                cell_checks += 1
        except (ValueError, TypeError, KeyError, IndexError, AttributeError) as exc:
            ISSUES.append({"kind": "source_binding_failure", "detail": {"uid": uid, "error": str(exc)}})
        binding_rows.append({"uid": uid, "physical_key": key, "cases": sorted(delivered["case_ids"]),
                             "delivered_unique_units": len(delivered["unit_ids"]), "delivered_unique_pool_cells": len(delivered["cell_locators"]),
                             "new_issues": len(ISSUES) - begin})
        if ordinal % 50 == 0 or ordinal == len(attached):
            progress("source_binding_UIDs", completed=ordinal, total=len(attached), units_checked=unit_checks, cells_checked=cell_checks, issues=len(ISSUES))


    for name, sha in freeze["files"].items():
        check(file_hash(OUT / name) == sha, "frozen_file_changed_during_audit", name)
    for name in ("projections.json", "results.json", "source_checks.json", "run.py", "projector.py"):
        rel = str((FACT / name).relative_to(ROOT)).replace("\\", "/")
        check(file_hash(FACT / name) == freeze["dependencies"][rel], "saved_fact_input_changed_during_audit", name)
    per_arm = {}
    for label in CAPS:
        cells = {(projections[uid]["physical_key"], loc) for uid, a in arm_attached[label].items() for loc in a["cell_locators"]}
        units = {(uid, unit) for uid, a in arm_attached[label].items() for unit in a["unit_ids"]}
        per_arm[label] = {"cap_bytes": CAPS[label], "case_checks": sum(c["arm"] == label for c in case_checks),
                          "table_decision_case_occurrences": dict(table_status[label]), "unit_decision_case_occurrences": dict(unit_status[label]),
                          "attached_unique_UIDs": len(arm_attached[label]), "attached_unique_physical_tables": len({projections[uid]["physical_key"] for uid in arm_attached[label]}),
                          "delivered_unique_UID_units": len(units), "delivered_unique_physical_pool_cells": len(cells),
                          "maximum_packet_bytes": max(c["experimental_bytes"] for c in case_checks if c["arm"] == label)}
    old_unit_set = {(uid, unit) for uid, a in arm_attached["64KiB"].items() for unit in a["unit_ids"]}
    new_unit_set = {(uid, unit) for uid, a in arm_attached["160KiB"].items() for unit in a["unit_ids"]}
    old_cell_set = {(projections[uid]["physical_key"], loc) for uid, a in arm_attached["64KiB"].items() for loc in a["cell_locators"]}
    new_cell_set = {(projections[uid]["physical_key"], loc) for uid, a in arm_attached["160KiB"].items() for loc in a["cell_locators"]}
    changes = {"unit_event_counts": {key: sum((row["unit_changes"][key] if key == "retained" else len(row["unit_changes"][key])) for row in change_rows) for key in ("retained", "added", "lost")},
               "cases_with_lost_units": [row["case_id"] for row in change_rows if row["unit_changes"]["lost"]],
               "cases_with_any_lost_dependency_role": [row["case_id"] for row in change_rows if any(v["lost"] for v in row["physical_dependency_role_changes"].values())],
               "retained_units_with_changed_payload_or_axes": sum(len(row["retained_changed_unit_keys"]) for row in change_rows),
               "dependency_role_event_counts": {role: {key: sum((row["physical_dependency_role_changes"][role][key] if key == "retained" else len(row["physical_dependency_role_changes"][role][key])) for row in change_rows) for key in ("retained", "added", "lost")} for role in ("value_cells", "row_axes", "column_axes", "literal_contexts")},
               "new_160_only_unique_UID_units_validated": len(new_unit_set - old_unit_set), "new_160_only_unique_physical_pool_cells_validated": len(new_cell_set - old_cell_set),
               "interpretation": "Greedy atomic skip-and-continue is not monotonic under a larger cap. Lost saved additions are reported separately from unchanged original A12; retained-unit axis closure is checked independently. Mandatory-fact or answer regression is not inferred from these counts."}
    result = {
        "schema_version": "fact_budget77_independent_postrun_boundary_review_v1",
        "status": "PASS_OBSERVED_MECHANICAL_AND_PHYSICAL_BINDING_CHECKS" if not ISSUES else "ISSUES_FOUND",
        "review_date": "2026-10-23",
        "independence": {"review": "Adapted prior independent checker in the same shared task context; not a fresh blind or semantic review", "prior_checker_sha256": PRIOR_CHECKER_SHA256,
                         "implementation_helper_reused": False, "projector_or_assembler_functions_called": False,
                         "only_shared_source_preprocessing": "src.processing.financial_parser._sanitize_xml_like_text in memory; strict no-network XML parse",
                         "independent_algorithms": ["raw occupancy/span expansion", "dynamic-programming ordered row-axis match", "stored cell/header/axis witnesses", "context hash/span/physical adjacency", "actual full-packet serialization for every budget proposal"],
                         "numeric_evaluator_peer_judgments_read": False},
        "execution": {"new_projector_runs": 0, "new_scored_runs": 0, "new_model_API_calls": 0, "new_search_calls": 0, "new_answers": 0,
                      "store_or_SQLite_opened": False, "runtime_or_env_modified": False, "elapsed_seconds": round(time.monotonic() - START, 2)},
        "scope": {"cases": len(panel), "case_arm_checks": len(case_checks), "groups": groups,
                  "actual_original_document_occurrences_per_arm": sum(c["original_delivered_documents"] for c in case_checks if c["arm"] == "64KiB"),
                  "exact_64KiB_previous_packet_and_decision_replays": replay64_count, "unique_saved_UIDs": len(needed), "budget_proposals_checked_both_caps": total_unit_proposals,
                  "union_attached_unique_UIDs": len(attached), "union_attached_unique_physical_tables": len(physical_tables),
                  "union_delivered_unique_UID_unit_checks": unit_checks, "union_delivered_unique_physical_units": len(physical_units),
                  "union_delivered_unique_UID_pool_cell_checks": cell_checks, "union_delivered_unique_physical_pool_cells": len(physical_cells),
                  "verified_literal_context_occurrences_across_unique_UIDs": contexts_checked, "independently_recomputed_saved_context_statuses_across_unique_UIDs": dict(context_validation_counts),
                  "source_documents_hashed_and_strictly_parsed": len(source_audit), "fragment_counts_not_semantic_failure_scores": dict(fragments)},
        "per_arm": per_arm, "between_cap_delivery_changes": changes,
        "confirmed_checks": ["all77 original A12 equals saved panel/request and both arms preserve every original field", "all77 original candidates/scores/RRF order/top12/actual documents unchanged", "64KiB packet and full decisions exactly equal saved FCT12", "both caps exact full-packet byte bounds and fixed first-owner/atomic pool behavior", "all actually delivered union units and pool cells independently checked against stored witnesses and original physical grid", "all included union contexts verified by SHA, XPath, exact span, parent and physical relation", "between-cap unit/value/row-axis/header/context additions and losses inventoried; retained units keep identical dependencies"],
        "issues": ISSUES,
        "limitations": ["Passed source binding is not certified financial period/entity/scope/unit interpretation or complete required-fact recovery.", "No answers were generated; answer accuracy, faithfulness, refusal success and attention effects remain unmeasured.", "Source validation covers the union of actually delivered units, including all newly delivered160KiB units, not every budget-rejected candidate or raw source cell.", "The independent checker is adapted from the prior review by the same reviewer with shared task context. Only XML sanitation is shared with the implementation; occupancy and witness logic is separate.", "Larger-cap loss of an earlier addition is a delivery regression candidate, not automatically a source-contract failure or a mandatory-answer error; it must be judged by unchanged criteria separately.", "An explicit table extension shares the original source ID; its new cells are not claimed to appear in the old chunk text.", "The checker ends a UID source walk at its first binding exception; any issue would qualify total coverage.", "Owner preservation receipts cover runtime/env/stores; this checker does not reopen stores or repeat all protected-file hashing."],
        "source_documents": source_audit, "case_arm_invariants": case_checks, "between_cap_case_changes": change_rows,
        "attachment_binding_checks_union": binding_rows,
        "checker_sha256": file_hash(Path(__file__)),
        "reviewed_artifact_hashes": {"freeze.json": file_hash(OUT / "freeze.json"), "results.json": file_hash(OUT / "results.json"), "saved_projections.json": file_hash(FACT / "projections.json"), "saved_source_checks.json": file_hash(FACT / "source_checks.json")},
    }
    (OUT / "postrun_boundary_review.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    progress("completed", status=result["status"], issues=len(ISSUES), scope=result["scope"], between_cap_delivery_changes=changes)
    if ISSUES:
        print(json.dumps(ISSUES[:30], ensure_ascii=False, indent=2), flush=True)
    return 0 if not ISSUES else 1


if __name__ == "__main__":
    raise SystemExit(main())
