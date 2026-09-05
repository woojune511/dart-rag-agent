from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from src.storage.atomic_json import atomic_write_json
from src.storage.metadata_payloads import load_table_payloads, table_payload_sidecar_stats
from src.storage.structure_graph import empty_structure_graph, normalise_structure_graph_payload


CompactNodeForStorage = Callable[[Dict[str, Any], Dict[str, Dict[str, str]]], Dict[str, Any]]


def load_structure_graph(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return empty_structure_graph()
    payload = json.loads(path.read_text(encoding="utf-8"))
    return normalise_structure_graph_payload(payload)


def persist_structure_graph(
    graph_path: Path,
    table_payloads_path: Path,
    structure_graph: Dict[str, Any],
    *,
    compact_node_for_storage: CompactNodeForStorage,
    existing_payloads: Optional[Dict[str, Dict[str, str]]] = None,
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]]]:
    # Retain old content IDs so readers of the previous graph stay valid until
    # the graph replacement commits. Readers load the graph before payloads.
    payloads = dict(
        load_table_payloads(table_payloads_path)
        if existing_payloads is None else existing_payloads
    )
    graph = dict(structure_graph or {})
    graph["nodes"] = {
        str(chunk_uid): compact_node_for_storage(dict(node or {}), payloads)
        for chunk_uid, node in dict(graph.get("nodes", {}) or {}).items()
    }
    stats = table_payload_sidecar_stats(payloads, dict(graph.get("nodes", {}) or {}))
    atomic_write_json(
        table_payloads_path,
        {"version": 1, "payloads": payloads, "stats": stats},
    )
    atomic_write_json(graph_path, graph)
    return graph, payloads
