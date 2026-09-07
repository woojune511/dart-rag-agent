"""Explicit, provider-free source reparse + exact-input vector reuse.

prepare writes a source working copy and hash-bound embedding requests; build
consumes separately supplied vectors. Neither operation creates an embedding
client. Real-store use needs separate authorization; there is no in-place mode.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack, closing
from dataclasses import replace
import json
import math
from pathlib import Path
import shutil
import struct
from unittest.mock import patch

from src.config.runtime_contract import CANONICAL_INGEST_PROFILE_ID, CANONICAL_PARSER_SCHEMA_VERSION
from src.ops.plan_parser_store_successor import (
    _file_sha, _json, _sha, compare_index_texts, parse_source_projection,
)
from src.storage.atomic_json import atomic_write_json
from src.storage.graph_persistence import load_structure_graph, persist_structure_graph
from src.storage.metadata_payloads import compact_node_for_storage, load_table_payloads, metadata_for_chroma
from src.storage.parent_store import load_parents, save_parents
from src.storage.store_manifest import StoreManifestV1, read_store_manifest, write_store_manifest
from src.storage.structure_graph import empty_structure_graph, update_structure_graph


def _client(path):
    import chromadb
    from chromadb.config import Settings

    return chromadb.PersistentClient(path=str(path), settings=Settings(anonymized_telemetry=False))


def _read_vectors(collection):
    rows = []
    for offset in range(0, collection.count(), 512):
        data = collection.get(limit=512, offset=offset, include=["documents", "metadatas", "embeddings"])
        for index, vector_id in enumerate(data["ids"]):
            vectors = data.get("embeddings")
            rows.append({"vector_id": vector_id, "text": data["documents"][index],
                         "metadata": data["metadatas"][index] or {},
                         "embedding": list(vectors[index]) if vectors is not None else None})
    return sorted(rows, key=lambda row: row["vector_id"])


def _vector(value, dimension):
    if value is None or len(value) != dimension:
        raise ValueError("Missing embedding or dimension mismatch")
    try:
        # Chroma stores float32. Compare its actual representation on readback,
        # without normalizing/recomputing the provider's vector.
        vector = [struct.unpack("<f", struct.pack("<f", float(item)))[0] for item in value]
    except (OverflowError, TypeError, struct.error) as exc:
        raise ValueError("Invalid embedding component") from exc
    if not all(math.isfinite(item) for item in vector) or not any(vector):
        raise ValueError("Embedding must be finite and nonzero")
    return vector


def _assert_inputs_unchanged(source_store, hashes):
    source_store = Path(source_store).resolve()
    expected_files = {Path(path).resolve() for path in hashes if Path(path).resolve().is_relative_to(source_store)}
    actual_files = {path.resolve() for path in source_store.rglob("*") if path.is_file()}
    if not expected_files or expected_files != actual_files or any(
        not Path(path).is_file() or _file_sha(Path(path)) != sha for path, sha in hashes.items()
    ):
        raise ValueError("Source input hashes/files changed; make a new inventory")


def _outside_inputs(path, source_store, hashes):
    path, source_store = Path(path).resolve(), Path(source_store).resolve()
    if path.is_relative_to(source_store) or source_store.is_relative_to(path) or any(
        Path(item).resolve().is_relative_to(path) for item in hashes
    ):
        raise ValueError("Output must be disjoint from original inputs")
    return path


def _projection_fingerprint(documents):
    return _sha(_json([{"metadata": row["metadata"], "text": row["text"]}
                      for row in sorted(documents, key=lambda row: row["metadata"]["chunk_uid"])]))


def assemble_reuse_documents(chunks, texts, comparison, vector_rows, dimension):
    by_uid = defaultdict(list)
    for row in sorted(vector_rows, key=lambda row: row["vector_id"]):
        by_uid[str(row["metadata"].get("chunk_uid") or "")].append(row)
    authority = {row["chunk_uid"]: row for row in comparison["chunks"]}
    documents, requests = [], {}
    for chunk, text in zip(chunks, texts, strict=True):
        uid = chunk.metadata["chunk_uid"]
        candidates = authority[uid]["exact_text_source_uids"]
        source = next((row for old_uid in candidates for row in by_uid[old_uid]
                       if row["text"] == text and str(row["metadata"].get("rcept_no")) == str(chunk.metadata["rcept_no"])), None)
        if candidates and source is None:
            raise ValueError(f"Reusable source vector missing or text/provenance changed: {uid}")
        vector = _vector(source["embedding"], dimension) if source else None
        if source is None:
            requests[_sha(text)] = text
        documents.append({"text": text, "metadata": dict(chunk.metadata), "embedding": vector,
                          "reused_from": {"chunk_uid": source["metadata"]["chunk_uid"],
                                          "vector_id": source["vector_id"], "text_sha256": _sha(text)} if source else None})
    return sorted(documents, key=lambda row: row["metadata"]["chunk_uid"]), [
        {"text_sha256": sha, "text": requests[sha]} for sha in sorted(requests)]


def prepare_successor(plan, reports, workspace: Path):
    """Create an inspectable preparation, not a query-ready successor store."""
    if plan.get("schema_version") != "parser_store_successor_plan_v1":
        raise ValueError("Unsupported inventory plan")
    source = Path(plan["source_store"]).resolve()
    hashes = plan["input_hashes"]
    workspace = _outside_inputs(workspace, source, hashes)
    if workspace.exists():
        raise FileExistsError("Preparation workspace must be new")
    _assert_inputs_unchanged(source, hashes)
    old = read_store_manifest(source)
    manifest = StoreManifestV1.from_projection(plan["proposed_manifest"])
    if old is None or old.to_projection() != plan["predecessor_manifest"] or old.ingest.profile_id != CANONICAL_INGEST_PROFILE_ID:
        raise ValueError("Predecessor embedding/profile identity mismatch")
    if manifest != replace(old, ingest=replace(old.ingest, parser_schema_version=CANONICAL_PARSER_SCHEMA_VERSION)):
        raise ValueError("Successor must preserve embedding identity and use the current parser")
    chunks, texts, parents, modes = parse_source_projection(
        reports, manifest, section_parse_budget_sec=plan["section_parse_budget_sec"])
    rows = [{"metadata": chunk.metadata, "text": text} for chunk, text in zip(chunks, texts, strict=True)]
    if (_projection_fingerprint(rows) != plan["new_source_projection_fingerprint"]
            or _sha(_json(parents)) != plan["new_parent_fingerprint"] or modes != plan["parsed_reports"]):
        raise ValueError("Fresh parser projection drifted; make a new inventory")
    comparison = compare_index_texts(load_structure_graph(source / "document_structure_graph.json")["nodes"], chunks, texts)
    if comparison != plan["index_text_comparison"]:
        raise ValueError("Index-text inventory drifted")

    workspace.mkdir(parents=True)
    source_copy = workspace / "source_copy"
    try:
        shutil.copytree(source, source_copy)
        for path, sha in hashes.items():
            original = Path(path)
            if original.is_relative_to(source) and _file_sha(source_copy / original.relative_to(source)) != sha:
                raise ValueError("Source working copy is incomplete")
        with closing(_client(source_copy)) as client:
            collection = client.get_collection(old.collection_name, embedding_function=None)
            hnsw = collection.configuration.get("hnsw")
            if not hnsw or hnsw.get("space") not in {"l2", "cosine", "ip"}:
                raise ValueError("Unsupported source index configuration")
            documents, requests = assemble_reuse_documents(chunks, texts, comparison, _read_vectors(collection), manifest.embedding.dimension)
        request = {"schema_version": "parser_successor_embedding_request_v1",
                   "embedding": manifest.embedding.to_projection(), "texts": requests}
        request["fingerprint"] = _sha(_json(request))
        prepared = {"schema_version": "prepared_parser_store_successor_v1", "source_store": str(source),
                    "input_hashes": hashes, "plan_fingerprint": _sha(_json(plan)),
                    "source_projection_fingerprint": plan["new_source_projection_fingerprint"],
                    "parent_fingerprint": plan["new_parent_fingerprint"],
                    "manifest": manifest.to_projection(), "hnsw_space": hnsw["space"],
                    "parents": parents, "documents": documents, "embedding_request": request}
        _assert_inputs_unchanged(source, hashes)
        atomic_write_json(workspace / "embedding_request.json", request)
        atomic_write_json(workspace / "prepared.json", prepared)
        return prepared
    finally:
        _assert_inputs_unchanged(source, hashes)


def _resolved_documents(prepared, supplied):
    if prepared.get("schema_version") != "prepared_parser_store_successor_v1":
        raise ValueError("Unsupported prepared source")
    manifest = StoreManifestV1.from_projection(prepared["manifest"])
    predecessor = read_store_manifest(prepared["source_store"])
    if predecessor is None or manifest != replace(predecessor, ingest=replace(
        predecessor.ingest, parser_schema_version=CANONICAL_PARSER_SCHEMA_VERSION
    )):
        raise ValueError("Prepared embedding/parser identity mismatch")
    documents = prepared["documents"]
    ids = [row["metadata"]["chunk_uid"] for row in documents]
    if not ids or len(set(ids)) != len(ids) or _projection_fingerprint(documents) != prepared["source_projection_fingerprint"]:
        raise ValueError("Prepared source projection mismatch")
    if _sha(_json(prepared["parents"])) != prepared["parent_fingerprint"]:
        raise ValueError("Prepared parent projection mismatch")
    request = prepared["embedding_request"]
    if request["fingerprint"] != _sha(_json({key: value for key, value in request.items() if key != "fingerprint"})):
        raise ValueError("Embedding request fingerprint mismatch")
    required = {_sha(row["text"]): row["text"] for row in documents if row["embedding"] is None}
    if request["embedding"] != manifest.embedding.to_projection() or request["texts"] != [
        {"text_sha256": sha, "text": required[sha]} for sha in sorted(required)
    ]:
        raise ValueError("Embedding request does not cover the exact missing inputs")
    supplied = supplied or {"schema_version": "parser_successor_embeddings_v1", "request_fingerprint": request["fingerprint"],
                            "embedding": request["embedding"], "vectors_by_text_sha256": {}}
    if (supplied.get("schema_version") != "parser_successor_embeddings_v1"
            or supplied.get("embedding") != request["embedding"]
            or supplied.get("request_fingerprint") != request["fingerprint"]):
        raise ValueError("Supplied embedding identity/request mismatch")
    vectors = supplied.get("vectors_by_text_sha256") or {}
    if set(vectors) != set(required):
        raise ValueError("Missing or extra supplied vectors; automatic embedding is prohibited")
    result = []
    for row in documents:
        value = row["embedding"] if row["embedding"] is not None else vectors[_sha(row["text"])]
        result.append({**row, "embedding": _vector(value, manifest.embedding.dimension)})
    return manifest, result


def _expected_snapshot(prepared, documents):
    graph = update_structure_graph(empty_structure_graph(), [row["text"] for row in documents],
                                   [row["metadata"] for row in documents], lambda metadata: metadata["chunk_uid"])
    payloads = {}
    graph["nodes"] = {uid: compact_node_for_storage(node, payloads) for uid, node in graph["nodes"].items()}
    records = {row["metadata"]["chunk_uid"]: {"text": row["text"], "embedding": row["embedding"],
               "metadata": metadata_for_chroma(graph["nodes"][row["metadata"]["chunk_uid"]]["metadata"])} for row in documents}
    return graph, payloads, records


def _check_vector_rows(rows, expected, dimension, *, partial=False):
    actual = {row["vector_id"]: row for row in rows}
    if len(actual) != len(rows) or not set(actual).issubset(expected) or (not partial and set(actual) != set(expected)):
        raise ValueError("Vector coverage mismatch")
    for uid, row in actual.items():
        wanted = expected[uid]
        if row["text"] != wanted["text"] or row["metadata"] != wanted["metadata"] or _vector(row["embedding"], dimension) != wanted["embedding"]:
            raise ValueError(f"Stored vector/text/metadata mismatch: {uid}")
    return set(actual)


def _verify_output(path, manifest, graph, payloads, parents, records, hnsw_space):
    if load_structure_graph(path / "document_structure_graph.json") != graph:
        raise ValueError("Committed graph mismatch")
    if load_table_payloads(path / "table_payloads.json") != payloads or load_parents(path / "parents.json") != parents:
        raise ValueError("Committed payload/parent mismatch")
    with closing(_client(path)) as client:
        collection = client.get_collection(manifest.collection_name, embedding_function=None)
        if collection.configuration["hnsw"]["space"] != hnsw_space:
            raise ValueError("Index distance configuration mismatch")
        _check_vector_rows(_read_vectors(collection), records, manifest.embedding.dimension)
        ids = sorted(records)
        probes = sorted({ids[0], ids[len(ids) // 2], ids[-1]})
        for uid in probes:
            result = collection.query(query_embeddings=[records[uid]["embedding"]], n_results=1, include=["distances"])
            if not result["ids"][0] or not math.isfinite(result["distances"][0][0]):
                raise ValueError("Dense index probe failed")
    return {"vectors": len(records), "graph_nodes": len(graph["nodes"]), "payloads": len(payloads),
            "parents": len(parents), "dense_probes": len(probes), "ok": True}


def build_successor(prepared, supplied, output_store: Path, *, resume=False, batch_size=64):
    """Build only from prepared/supplied vectors; explicit resume makes no calls."""
    path = _outside_inputs(output_store, prepared["source_store"], prepared["input_hashes"])
    _assert_inputs_unchanged(prepared["source_store"], prepared["input_hashes"])
    manifest, documents = _resolved_documents(prepared, supplied)
    graph, payloads, records = _expected_snapshot(prepared, documents)
    seal = _sha(_json({"prepared": prepared, "vectors": [row["embedding"] for row in documents]}))
    state = {"schema_version": "parser_successor_build_state_v1", "input_fingerprint": seal}
    if batch_size < 1:
        raise ValueError("Batch size must be positive")
    if path.exists():
        if not resume:
            raise FileExistsError("Output exists; only an explicit, input-identical resume is allowed")
        if json.loads((path / "build_state.json").read_text(encoding="utf-8")) != state:
            raise ValueError("Resume input fingerprint mismatch")
    else:
        path.mkdir(parents=True)
        atomic_write_json(path / "build_state.json", state)
    try:
        actual_manifest = read_store_manifest(path)
        if actual_manifest is not None:
            if actual_manifest != manifest:
                raise ValueError("Published successor manifest mismatch")
            health = _verify_output(path, manifest, graph, payloads, prepared["parents"], records, prepared["hnsw_space"])
            return {"ready": True, "input_fingerprint": seal, "health": health, "provider_calls": 0}
        with closing(_client(path)) as client:
            collection = client.get_or_create_collection(manifest.collection_name, embedding_function=None,
                          configuration={"hnsw": {"space": prepared["hnsw_space"]}})
            existing = _check_vector_rows(_read_vectors(collection), records, manifest.embedding.dimension, partial=True)
            pending = sorted(set(records) - existing)
            for start in range(0, len(pending), batch_size):
                ids = pending[start:start + batch_size]
                collection.add(ids=ids, documents=[records[uid]["text"] for uid in ids],
                               metadatas=[records[uid]["metadata"] for uid in ids],
                               embeddings=[records[uid]["embedding"] for uid in ids])
        save_parents(path / "parents.json", prepared["parents"])
        persist_structure_graph(path / "document_structure_graph.json", path / "table_payloads.json", graph,
                                compact_node_for_storage=lambda node, _: node, existing_payloads=payloads)
        health = _verify_output(path, manifest, graph, payloads, prepared["parents"], records, prepared["hnsw_space"])
        _assert_inputs_unchanged(prepared["source_store"], prepared["input_hashes"])
        result = {"ready": True, "input_fingerprint": seal, "health": health, "provider_calls": 0}
        atomic_write_json(path / "build_receipt.json", {**result, "ready": False, "status": "validated_before_manifest"})
        write_store_manifest(path, manifest)  # Publication is the final write.
        return result
    finally:
        _assert_inputs_unchanged(prepared["source_store"], prepared["input_hashes"])


def _load_bound_json(path, sha):
    path = Path(path)
    if _file_sha(path) != sha:
        raise ValueError(f"Artifact SHA-256 mismatch: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    prepare = modes.add_parser("prepare", help="Explicitly create a source copy and prepared inputs; no provider calls")
    prepare.add_argument("--inventory", required=True)
    prepare.add_argument("--inventory-sha256", required=True)
    prepare.add_argument("--spec", required=True)
    prepare.add_argument("--store-index", type=int, required=True)
    prepare.add_argument("--workspace", type=Path, required=True)
    build = modes.add_parser("build", help="Publish a new store from supplied vectors only")
    build.add_argument("--prepared", required=True)
    build.add_argument("--prepared-sha256", required=True)
    build.add_argument("--embeddings")
    build.add_argument("--embeddings-sha256")
    build.add_argument("--output-store", type=Path, required=True)
    build.add_argument("--resume", action="store_true")
    args = parser.parse_args(argv)
    with ExitStack() as stack:
        for name in ("socket.create_connection", "socket.socket.connect", "socket.socket.connect_ex"):
            stack.enter_context(patch(name, side_effect=AssertionError("Provider/network prohibited in successor builder")))
        if args.mode == "prepare":
            inventory = _load_bound_json(args.inventory, args.inventory_sha256)
            spec = _load_bound_json(args.spec, inventory["spec_sha256"])
            if args.store_index < 0 or Path(spec["stores"][args.store_index]["source_store"]).resolve() != Path(inventory["stores"][args.store_index]["source_store"]).resolve():
                raise ValueError("Source spec/store index mismatch")
            prepared = prepare_successor(inventory["stores"][args.store_index], spec["stores"][args.store_index]["reports"], args.workspace)
            print(_json({"prepared_sha256": _file_sha(args.workspace / "prepared.json"),
                         "embedding_request_fingerprint": prepared["embedding_request"]["fingerprint"],
                         "new_embedding_texts": len(prepared["embedding_request"]["texts"]), "provider_calls": 0}))
        else:
            prepared = _load_bound_json(args.prepared, args.prepared_sha256)
            if bool(args.embeddings) != bool(args.embeddings_sha256):
                raise ValueError("Supplied embeddings require a SHA-256")
            supplied = _load_bound_json(args.embeddings, args.embeddings_sha256) if args.embeddings else None
            print(_json(build_successor(prepared, supplied, args.output_store, resume=args.resume)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
