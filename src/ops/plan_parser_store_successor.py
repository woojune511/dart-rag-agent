"""Read-only parser/store transition inventory; never opens Chroma or a provider.

This is a plan, not a migration/adoption command. Exact index-text equality only
identifies possible vector reuse; vector coverage/health must still be checked
by a separately approved successor builder.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import ExitStack
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import sys
from unittest.mock import patch

from src.config.runtime_contract import CANONICAL_INGEST_PROFILE_ID, CANONICAL_PARSER_SCHEMA_VERSION
from src.processing.financial_parser import FinancialParser
from src.storage.graph_persistence import load_structure_graph
from src.storage.metadata_payloads import load_table_payloads, metadata_with_table_payload
from src.storage.store_manifest import read_store_manifest


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _file_sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _without_units(value):
    if isinstance(value, dict):
        return {key: _without_units(item) for key, item in value.items() if key != "unit_hint"}
    if isinstance(value, list):
        return [_without_units(item) for item in value]
    return value


def _table_inventory(metadatas):
    tables = defaultdict(dict)
    parsed = {}
    for metadata in metadatas:
        raw = metadata.get("table_object_json")
        if not raw:
            continue
        if raw not in parsed:
            parsed[raw] = json.loads(raw)
        table = parsed[raw]
        key = (str(metadata.get("rcept_no") or ""), str(table.get("table_id") or ""))
        if not all(key):
            raise ValueError("Table lacks filing-qualified identity")
        tables[key][_sha(_json(table))] = table
    return tables


def compare_tables(before_metadatas, after_metadatas) -> dict:
    """Compare exact filing/table keys, keeping conflicting payloads ambiguous."""
    before, after = _table_inventory(before_metadatas), _table_inventory(after_metadatas)
    rows = []
    for key in sorted(before.keys() | after.keys()):
        old, new = before.get(key, {}), after.get(key, {})
        row = {"receipt": key[0], "table_id": key[1],
               "old_variants": len(old), "new_variants": len(new)}
        if not old or not new or len(old) != 1 or len(new) != 1:
            row["status"] = "new_table" if not old else "missing_table" if not new else "ambiguous_payload"
        else:
            previous, current = next(iter(old.values())), next(iter(new.values()))
            fields = sorted(field for field in previous if previous[field] != current.get(field))
            row.update({"status": "changed" if fields else "additive_only",
                        "changed_fields": fields,
                        "unit": [previous.get("unit_hint"), current.get("unit_hint")],
                        "header_changed": previous.get("header_rows") != current.get("header_rows"),
                        "records_equal_except_unit": all(
                            _without_units(previous.get(field)) == _without_units(current.get(field))
                            for field in ("rows", "values")),
                        "source_table_locator": current.get("source_table_locator"),
                        "source_document_sha256": current.get("source_document_sha256"),
                        "context_count": len(current.get("source_contexts") or [])})
            if row["unit"][0] != row["unit"][1]:
                row["preceding_contexts"] = [context for context in current.get("source_contexts", [])
                                             if context.get("relation") == "preceding_block"]
        rows.append(row)
    return {"old_tables": len(before), "new_tables": len(after),
            "status_counts": dict(sorted(Counter(row["status"] for row in rows).items())), "tables": rows}


def compare_index_texts(old_nodes: dict, new_chunks: list, new_texts: list[str]) -> dict:
    """Exact full embedding inputs only, not raw-value/fuzzy/chunk-ID matches."""
    if len(new_chunks) != len(new_texts):
        raise ValueError("Index text/chunk count mismatch")
    sources = defaultdict(list)
    for uid, node in sorted(old_nodes.items()):
        receipt = str(node.get("metadata", {}).get("rcept_no") or "")
        sources[receipt, str(node.get("text") or "")].append(uid)
    rows, seen = [], set()
    for chunk, text in sorted(zip(new_chunks, new_texts), key=lambda pair: pair[0].metadata["chunk_uid"]):
        uid = chunk.metadata["chunk_uid"]
        if uid in seen:
            raise ValueError(f"Duplicate new chunk identity: {uid}")
        seen.add(uid)
        matches = sources.get((str(chunk.metadata.get("rcept_no") or ""), text), []) if text else []
        rows.append({"chunk_uid": uid, "index_text_sha256": _sha(text),
                     "index_text_bytes": len(text.encode("utf-8")),
                     "exact_text_source_uids": list(matches),
                     "same_uid_text_equal": uid in matches})
    reusable = sum(bool(row["exact_text_source_uids"]) for row in rows)
    return {"old_chunks": len(old_nodes), "new_chunks": len(rows),
            "exact_text_reuse_candidates": reusable,
            "new_or_changed_texts": len(rows) - reusable,
            "new_or_changed_text_bytes": sum(row["index_text_bytes"] for row in rows if not row["exact_text_source_uids"]),
            "same_uid_same_text": sum(row["same_uid_text_equal"] for row in rows),
            "old_uids_absent_from_new": sorted(set(old_nodes) - seen),
            "vector_reuse_verified": False, "chunks": rows}


class _ObservedParser(FinancialParser):
    def _extract_sections(self, root):
        sections = super()._extract_sections(root)
        self.section_modes = [{"path": row["path"], "mode": row["parse_mode"],
                               "fallback_used": row["fallback_used"]} for row in sections]
        return sections


def plan_store_successor(source_store: Path, reports: list[dict], *, section_parse_budget_sec: float = 0) -> dict:
    """Parse all declared original filings in memory and compare with the store."""
    # Reuse the current zero-model-call benchmark index projection, not a new
    # prefix policy. Import lazily; neither a FinancialAgent nor a store is made.
    from src.ops.benchmark_runner import _build_structural_selective_prefixed_text, _selective_reason_v2

    source_store = source_store.resolve()
    manifest = read_store_manifest(source_store)
    if manifest is None:
        raise ValueError("A predecessor manifest is required; this tool cannot adopt stores")
    if manifest.ingest.profile_id != CANONICAL_INGEST_PROFILE_ID:
        raise ValueError("Only the existing canonical structural-selective prefix is supported")
    source_files = [Path(report["source_file"]).resolve() for report in reports]
    store_files = sorted(path for path in source_store.rglob("*") if path.is_file())
    hashes = {str(path): _file_sha(path) for path in sorted(set(store_files + source_files))}
    graph_path = source_store / "document_structure_graph.json"
    if not graph_path.is_file():
        raise ValueError("Predecessor graph is missing")
    graph = load_structure_graph(graph_path)
    payloads = load_table_payloads(source_store / "table_payloads.json")
    old_nodes = graph["nodes"]
    expected_receipts = {str(node.get("metadata", {}).get("rcept_no") or "") for node in old_nodes.values()}
    receipts = [str(report["metadata"].get("rcept_no") or "") for report in reports]
    if not receipts or "" in expected_receipts or "" in receipts or len(set(receipts)) != len(receipts) or set(receipts) != expected_receipts:
        raise ValueError("Source reports must cover every predecessor filing exactly once")
    old_metadata = []
    for node in old_nodes.values():
        metadata = node.get("metadata", {})
        payload_id = metadata.get("table_payload_id")
        if payload_id and payload_id not in payloads:
            raise ValueError(f"Missing predecessor payload: {payload_id}")
        old_metadata.append(metadata_with_table_payload(metadata, payloads))

    chunks, parsed_reports = [], []
    for report in sorted(reports, key=lambda row: str(row["metadata"]["rcept_no"])):
        parser = _ObservedParser(chunk_size=manifest.ingest.chunk_size,
                                 chunk_overlap=manifest.ingest.chunk_overlap,
                                 section_parse_budget_sec=section_parse_budget_sec)
        parsed = parser.process_document(str(report["source_file"]), dict(report["metadata"]))
        if not parsed:
            raise ValueError(f"Source produced no chunks: {report['source_file']}")
        chunks.extend(parsed)
        parsed_reports.append({"receipt": str(report["metadata"]["rcept_no"]), "chunks": len(parsed),
                               "section_modes": parser.section_modes})
        print(f"Parsed {report['metadata']['rcept_no']}: {len(parsed)} chunks", file=sys.stderr, flush=True)
    texts = [_build_structural_selective_prefixed_text(chunk.metadata, chunk.content,
                                                     selected_reason=_selective_reason_v2(chunk)) for chunk in chunks]
    parents = FinancialParser.build_parents(chunks)
    table_comparison = compare_tables(old_metadata, [chunk.metadata for chunk in chunks])
    text_comparison = compare_index_texts(old_nodes, chunks, texts)
    successor = replace(manifest, ingest=replace(manifest.ingest, parser_schema_version=CANONICAL_PARSER_SCHEMA_VERSION))
    projection = [{"metadata": chunk.metadata, "text": text} for chunk, text in
                  sorted(zip(chunks, texts), key=lambda pair: pair[0].metadata["chunk_uid"])]
    if set(store_files) != {path for path in source_store.rglob("*") if path.is_file()} or any(
        _file_sha(Path(path)) != sha for path, sha in hashes.items()
    ):
        raise RuntimeError("An input changed during the read-only inventory")
    return {"schema_version": "parser_store_successor_plan_v1", "source_store": str(source_store),
            "predecessor_manifest": manifest.to_projection(), "proposed_manifest": successor.to_projection(),
            "section_parse_budget_sec": section_parse_budget_sec, "parsed_reports": parsed_reports,
            "table_comparison": table_comparison, "index_text_comparison": text_comparison,
            "new_parent_count": len(parents), "new_parent_fingerprint": _sha(_json(parents)),
            "new_source_projection_fingerprint": _sha(_json(projection)), "input_hashes": hashes,
            "inputs_unchanged": True, "store_writes": 0, "provider_calls": 0,
            "manifest_relabel_allowed": False, "ready_to_publish": False,
            "claim": "Read-only source reparse plan, not vector health, migration approval, or model-quality evidence."}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", type=Path, required=True, help="JSON with stores[{source_store,reports[{source_file,metadata}]}]")
    parser.add_argument("--output", type=Path, required=True, help="New diagnostic JSON, outside all predecessor stores")
    parser.add_argument("--section-parse-budget-sec", type=float, default=0,
                        help="0 disables wall-clock fallback for this diagnostic; not a production-equivalence claim")
    args = parser.parse_args(argv)
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    output = args.output.resolve()
    if output.exists() or any(output.is_relative_to(Path(store["source_store"]).resolve()) for store in spec["stores"]):
        raise ValueError("Output must be new and outside predecessor stores")
    if args.section_parse_budget_sec < 0:
        raise ValueError("Section parse budget must be nonnegative")
    with ExitStack() as stack:
        for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(name, side_effect=AssertionError("Network prohibited in parser dry-run")))
        result = {"schema_version": "parser_store_successor_inventory_v1", "spec_sha256": _file_sha(args.spec),
                  "stores": [plan_store_successor(Path(store["source_store"]), store["reports"],
                              section_parse_budget_sec=args.section_parse_budget_sec)
                             for store in spec["stores"]]}
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(_json({"output": str(output), "sha256": _file_sha(output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
