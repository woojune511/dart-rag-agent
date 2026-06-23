from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from src.storage.metadata_payloads import table_payload_sidecar_stats
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
) -> Tuple[Dict[str, Any], Dict[str, Dict[str, str]]]:
    payloads: Dict[str, Dict[str, str]] = {}
    graph = dict(structure_graph or {})
    graph["nodes"] = {
        str(chunk_uid): compact_node_for_storage(dict(node or {}), payloads)
        for chunk_uid, node in dict(graph.get("nodes", {}) or {}).items()
    }
    graph_path.write_text(
        json.dumps(graph, ensure_ascii=False),
        encoding="utf-8",
    )

    stats = table_payload_sidecar_stats(payloads, dict(graph.get("nodes", {}) or {}))
    table_payloads_path.write_text(
        json.dumps({"version": 1, "payloads": payloads, "stats": stats}, ensure_ascii=False),
        encoding="utf-8",
    )
    return graph, payloads
