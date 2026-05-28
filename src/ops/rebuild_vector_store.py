"""
Rebuild a persisted Chroma vector store from document_structure_graph.json.

This is intended for benchmark bundles where the auxiliary structure graph is
still readable but the persisted Chroma/HNSW index can no longer be reopened.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from storage.vector_store import (  # noqa: E402
    DEFAULT_COLLECTION_NAME,
    DEFAULT_EMBEDDING_MODEL,
    DEFAULT_EMBEDDING_PROVIDER,
    VectorStoreManager,
)

logger = logging.getLogger(__name__)


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Required file not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def _node_sort_key(node: Dict[str, Any]) -> Tuple[str, int, int, str]:
    metadata = dict(node.get("metadata") or {})
    return (
        str(metadata.get("rcept_no") or ""),
        int(node.get("chunk_id", metadata.get("chunk_id", 0)) or 0),
        int(node.get("sub_chunk_idx", metadata.get("sub_chunk_idx", 0)) or 0),
        str(node.get("chunk_uid") or metadata.get("chunk_uid") or ""),
    )


def load_structure_graph_documents(source_store: Path) -> Tuple[List[str], List[dict], Dict[str, str]]:
    graph = _load_json(source_store / "document_structure_graph.json")
    nodes = dict(graph.get("nodes", {}) or {})
    chunks: List[str] = []
    metadatas: List[dict] = []
    seen_chunk_uids: set[str] = set()

    for node in sorted(nodes.values(), key=_node_sort_key):
        if not isinstance(node, dict):
            continue
        text = str(node.get("text") or "").strip()
        metadata = dict(node.get("metadata") or {})
        chunk_uid = str(node.get("chunk_uid") or metadata.get("chunk_uid") or "").strip()
        if not text:
            continue
        if chunk_uid:
            metadata.setdefault("chunk_uid", chunk_uid)
            if chunk_uid in seen_chunk_uids:
                continue
            seen_chunk_uids.add(chunk_uid)
        chunks.append(text)
        metadatas.append(metadata)

    parents_path = source_store / "parents.json"
    parents: Dict[str, str] = {}
    if parents_path.exists():
        parents_payload = _load_json(parents_path)
        parents = {str(key): str(value) for key, value in parents_payload.items()}

    if not chunks:
        raise ValueError(f"No rebuildable documents found in {source_store / 'document_structure_graph.json'}")
    return chunks, metadatas, parents


def prepare_output_store(source_store: Path, output_store: Path, *, force: bool, in_place: bool, resume: bool) -> None:
    source_resolved = source_store.resolve()
    output_resolved = output_store.resolve()
    if source_resolved == output_resolved and not in_place:
        raise ValueError("source-store and output-store are the same; pass --in-place --force to rebuild in place.")
    if output_store.exists():
        if resume and not force and not in_place:
            return
        if not force:
            raise FileExistsError(f"Output store already exists; pass --force to replace it: {output_store}")
        shutil.rmtree(output_store)
    output_store.mkdir(parents=True, exist_ok=True)


def backup_in_place_source_graph(source_store: Path) -> Path:
    backup_store = source_store.with_name(f"{source_store.name}.rebuild-source-backup")
    if backup_store.exists():
        shutil.rmtree(backup_store)
    backup_store.mkdir(parents=True, exist_ok=True)
    for filename in ("document_structure_graph.json", "parents.json"):
        source_file = source_store / filename
        if source_file.exists():
            shutil.copy2(source_file, backup_store / filename)
    return backup_store


def validate_vector_store_external(
    *,
    store: Path,
    collection_name: str,
    embedding_provider: str,
    embedding_model_name: str,
    timeout_sec: int = 180,
) -> Dict[str, Any]:
    code = """
import json
import os
import sys
sys.path.insert(0, os.environ["DART_SRC_ROOT"])
from storage.vector_store import VectorStoreManager
vsm = VectorStoreManager(
    persist_directory=os.environ["DART_HEALTH_STORE"],
    collection_name=os.environ["DART_HEALTH_COLLECTION"],
    embedding_provider=os.environ["DART_HEALTH_EMBEDDING_PROVIDER"],
    embedding_model_name=os.environ["DART_HEALTH_EMBEDDING_MODEL"],
    allow_query_embedding_fallback=False,
)
print(json.dumps(vsm.validate_vector_index(), ensure_ascii=False))
"""
    env = dict(os.environ)
    env.update(
        {
            "DART_SRC_ROOT": str(SRC_ROOT),
            "DART_HEALTH_STORE": str(store),
            "DART_HEALTH_COLLECTION": collection_name,
            "DART_HEALTH_EMBEDDING_PROVIDER": embedding_provider,
            "DART_HEALTH_EMBEDDING_MODEL": embedding_model_name,
        }
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(PROJECT_ROOT),
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout_sec,
    )
    if completed.returncode != 0:
        return {
            "ok": False,
            "external_process": True,
            "error": (completed.stderr or completed.stdout or "").strip(),
        }
    stdout_lines = [line.strip() for line in (completed.stdout or "").splitlines() if line.strip()]
    if not stdout_lines:
        return {"ok": False, "external_process": True, "error": "External health check produced no output."}
    try:
        health = json.loads(stdout_lines[-1])
    except json.JSONDecodeError as exc:
        return {
            "ok": False,
            "external_process": True,
            "error": f"Failed to parse external health output: {exc}: {stdout_lines[-1]}",
        }
    if isinstance(health, dict):
        health["external_process"] = True
        return health
    return {"ok": False, "external_process": True, "error": f"Unexpected external health payload: {health!r}"}


def rebuild_vector_store(
    *,
    source_store: Path,
    output_store: Path,
    collection_name: str,
    embedding_provider: str,
    embedding_model_name: str,
    batch_size: int,
    force: bool,
    in_place: bool = False,
    resume: bool = False,
    external_health_check: bool = True,
) -> Dict[str, Any]:
    chunks, metadatas, parents = load_structure_graph_documents(source_store)
    backup_store: Path | None = None
    if in_place:
        backup_store = backup_in_place_source_graph(source_store)

    try:
        prepare_output_store(source_store, output_store, force=force, in_place=in_place, resume=resume)

        manager = VectorStoreManager(
            persist_directory=str(output_store),
            collection_name=collection_name,
            embedding_provider=embedding_provider,
            embedding_model_name=embedding_model_name,
            allow_query_embedding_fallback=False,
        )
        add_result = manager.add_documents(chunks, metadatas, resume=resume, batch_size=batch_size)
        if parents:
            manager.add_parents(parents)
        manager.persist()
        if external_health_check:
            health = validate_vector_store_external(
                store=output_store,
                collection_name=collection_name,
                embedding_provider=embedding_provider,
                embedding_model_name=embedding_model_name,
            )
        else:
            reopened = VectorStoreManager(
                persist_directory=str(output_store),
                collection_name=collection_name,
                embedding_provider=embedding_provider,
                embedding_model_name=embedding_model_name,
                allow_query_embedding_fallback=False,
            )
            health = reopened.validate_vector_index()

        if not health.get("ok"):
            raise RuntimeError(f"Rebuilt vector store failed health check: {health.get('error')}")

        if backup_store and backup_store.exists():
            shutil.rmtree(backup_store)
    except Exception:
        if backup_store:
            logger.error("In-place rebuild failed; source graph backup retained at %s", backup_store)
        raise

    return {
        "source_store": str(source_store),
        "output_store": str(output_store),
        "collection_name": collection_name,
        "embedding_provider": embedding_provider,
        "embedding_model_name": embedding_model_name,
        "documents": len(chunks),
        "parents": len(parents),
        "resume": bool(resume),
        "add_result": add_result,
        "health": health,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rebuild a Chroma vector store from a persisted document_structure_graph.json."
    )
    parser.add_argument("--source-store", required=True, help="Existing store directory containing document_structure_graph.json.")
    parser.add_argument("--output-store", help="Destination store directory. Required unless --in-place is set.")
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME, help="Chroma collection name for the rebuilt store.")
    parser.add_argument("--embedding-provider", default=DEFAULT_EMBEDDING_PROVIDER, help="Embedding provider for reindexing.")
    parser.add_argument("--embedding-model-name", default=DEFAULT_EMBEDDING_MODEL, help="Embedding model name for reindexing.")
    parser.add_argument("--batch-size", type=int, default=64, help="Vector add batch size.")
    parser.add_argument("--force", action="store_true", help="Replace the output store directory if it already exists.")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume into an existing output store by skipping already indexed chunk_uids.",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Rebuild the source store directory in place. Requires --force and reads graph files before deletion.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    source_store = Path(args.source_store).resolve()
    if args.in_place:
        if not args.force:
            raise ValueError("--in-place requires --force")
        if args.resume:
            raise ValueError("--resume cannot be combined with --in-place")
        output_store = source_store
    elif args.output_store:
        output_store = Path(args.output_store).resolve()
    else:
        raise ValueError("--output-store is required unless --in-place is set")

    summary = rebuild_vector_store(
        source_store=source_store,
        output_store=output_store,
        collection_name=args.collection_name,
        embedding_provider=args.embedding_provider,
        embedding_model_name=args.embedding_model_name,
        batch_size=args.batch_size,
        force=bool(args.force),
        in_place=bool(args.in_place),
        resume=bool(args.resume),
    )
    logger.info(
        "Rebuilt vector store: documents=%s parents=%s health_ok=%s output=%s",
        summary["documents"],
        summary["parents"],
        summary["health"].get("ok"),
        summary["output_store"],
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
