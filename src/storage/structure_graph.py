from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Dict, List, Optional, Tuple

if TYPE_CHECKING:
    from langchain_core.documents import Document


MetadataHydrator = Callable[[Dict[str, Any]], Dict[str, Any]]
ChunkUidResolver = Callable[[Dict[str, Any]], str]


def _make_document(page_content: str, metadata: dict):
    from langchain_core.documents import Document

    return Document(page_content=page_content, metadata=metadata)


def empty_structure_graph() -> Dict[str, Any]:
    return {"nodes": {}, "parents": {}, "sections": {}}


def normalise_structure_graph_payload(payload: Any) -> Dict[str, Any]:
    if isinstance(payload, dict):
        return {
            "nodes": dict(payload.get("nodes", {}) or {}),
            "parents": dict(payload.get("parents", {}) or {}),
            "sections": dict(payload.get("sections", {}) or {}),
        }
    return empty_structure_graph()


def structure_graph_bm25_payload(
    graph: Dict[str, Any],
    hydrate_metadata: MetadataHydrator,
) -> Tuple[List[str], List[dict]]:
    nodes = dict((graph or {}).get("nodes", {}) or {})
    if not nodes:
        return [], []

    ordered_nodes = sorted(
        nodes.values(),
        key=lambda node: (
            str((node.get("metadata") or {}).get("rcept_no") or ""),
            int(node.get("chunk_id", 0) or 0),
            int(node.get("sub_chunk_idx", 0) or 0),
            str(node.get("chunk_uid") or ""),
        ),
    )
    docs: List[str] = []
    metadatas: List[dict] = []
    for node in ordered_nodes:
        text = str(node.get("text") or "").strip()
        metadata = hydrate_metadata(dict(node.get("metadata") or {}))
        if not text:
            continue
        docs.append(text)
        metadatas.append(metadata)
    return docs, metadatas


def hydrate_document_from_structure_graph(
    graph: Dict[str, Any],
    doc: Document,
    hydrate_metadata: MetadataHydrator,
    chunk_uid_from_metadata: ChunkUidResolver,
) -> Document:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    chunk_uid = chunk_uid_from_metadata(metadata)
    if not chunk_uid:
        return doc
    node = ((graph or {}).get("nodes", {}) or {}).get(chunk_uid)
    if not node:
        return doc
    hydrated_metadata = dict(metadata)
    hydrated_metadata.update(hydrate_metadata(dict((node.get("metadata") or {}))))
    text = str(node.get("text") or doc.page_content or "")
    return _make_document(page_content=text, metadata=hydrated_metadata)


def rebuild_structure_relationships(graph: Dict[str, Any]) -> Dict[str, Any]:
    nodes = dict((graph or {}).get("nodes", {}) or {})
    grouped: Dict[str, List[Dict[str, Any]]] = {}

    for node in nodes.values():
        parent_id = str(node.get("parent_id") or "")
        if not parent_id:
            continue
        grouped.setdefault(parent_id, []).append(node)

    parents: Dict[str, List[str]] = {}
    sections: Dict[str, Dict[str, Any]] = {}
    for parent_id, items in grouped.items():
        ordered = sorted(
            items,
            key=lambda item: (
                int(item.get("sub_chunk_idx", 0) or 0),
                int(item.get("chunk_id", 0) or 0),
            ),
        )
        chunk_uids = [str(item.get("chunk_uid")) for item in ordered if item.get("chunk_uid")]
        parents[parent_id] = chunk_uids
        lead_paragraph_uid = None
        previous_paragraph_uid = None
        for index, item in enumerate(ordered):
            chunk_uid = str(item.get("chunk_uid") or "")
            if not chunk_uid:
                continue
            prev_uid = chunk_uids[index - 1] if index > 0 else None
            next_uid = chunk_uids[index + 1] if index + 1 < len(chunk_uids) else None
            nodes[chunk_uid]["sibling_prev_uid"] = prev_uid
            nodes[chunk_uid]["sibling_next_uid"] = next_uid
            metadata = dict(item.get("metadata") or {})
            block_type = str(metadata.get("block_type") or metadata.get("is_table") and "table" or "")
            if block_type != "table":
                previous_paragraph_uid = chunk_uid
                if lead_paragraph_uid is None:
                    lead_paragraph_uid = chunk_uid
            elif previous_paragraph_uid:
                nodes[chunk_uid]["described_by_uid"] = previous_paragraph_uid
                described_node = nodes.get(previous_paragraph_uid)
                if described_node:
                    described_node.setdefault("describes_table_uids", [])
                    if chunk_uid not in described_node["describes_table_uids"]:
                        described_node["describes_table_uids"].append(chunk_uid)

        first_node = ordered[0] if ordered else {}
        first_metadata = dict(first_node.get("metadata", {}) or {})
        sections[parent_id] = {
            "parent_id": parent_id,
            "section_path": first_metadata.get("section_path"),
            "section": first_metadata.get("section"),
            "lead_paragraph_uid": lead_paragraph_uid,
            "chunk_uids": chunk_uids,
        }

    return {"nodes": nodes, "parents": parents, "sections": sections}


def update_structure_graph(
    graph: Dict[str, Any],
    chunks: List[str],
    metadatas: List[dict],
    chunk_uid_from_metadata: ChunkUidResolver,
) -> Dict[str, Any]:
    nodes = dict((graph or {}).get("nodes", {}) or {})

    for text, metadata in zip(chunks, metadatas):
        metadata = dict(metadata or {})
        chunk_uid = str(chunk_uid_from_metadata(metadata))
        if not chunk_uid:
            continue

        nodes[chunk_uid] = {
            "chunk_uid": chunk_uid,
            "text": text,
            "metadata": metadata,
            "parent_id": metadata.get("parent_id"),
            "chunk_id": metadata.get("chunk_id"),
            "sub_chunk_idx": metadata.get("sub_chunk_idx", 0),
            "table_context": metadata.get("table_context"),
            "reference_parent_ids": list(metadata.get("reference_parent_ids", []) or []),
        }

    graph = dict(graph or {})
    graph["nodes"] = nodes
    return rebuild_structure_relationships(graph)


def structure_graph_chunk_uids(
    graph: Dict[str, Any],
    *,
    rcept_no: Optional[str] = None,
    chunk_uid_from_metadata: ChunkUidResolver,
) -> set[str]:
    indexed: set[str] = set()
    for chunk_uid, node in dict((graph or {}).get("nodes", {}) or {}).items():
        metadata = dict((node or {}).get("metadata") or {})
        if rcept_no and str(metadata.get("rcept_no", "")) != str(rcept_no):
            continue
        resolved_uid = chunk_uid_from_metadata(metadata) or str(chunk_uid or "").strip()
        if resolved_uid:
            indexed.add(resolved_uid)
    return indexed


def get_structure_node(
    graph: Dict[str, Any],
    chunk_uid: str,
    hydrate_metadata: MetadataHydrator,
) -> Optional[Dict[str, Any]]:
    node = ((graph or {}).get("nodes", {}) or {}).get(chunk_uid)
    if not node:
        return None
    hydrated = dict(node)
    hydrated["metadata"] = hydrate_metadata(dict((node.get("metadata") or {})))
    return hydrated


def get_section_lead_doc(
    graph: Dict[str, Any],
    parent_id: str,
    hydrate_metadata: MetadataHydrator,
    *,
    exclude_chunk_uid: Optional[str] = None,
) -> Optional[Document]:
    if not parent_id:
        return None
    section = ((graph or {}).get("sections", {}) or {}).get(parent_id) or {}
    lead_uid = str(section.get("lead_paragraph_uid") or "")
    if not lead_uid or (exclude_chunk_uid and lead_uid == exclude_chunk_uid):
        return None
    node = get_structure_node(graph, lead_uid, hydrate_metadata)
    if not node:
        return None
    metadata = dict(node.get("metadata", {}) or {})
    metadata["graph_relation"] = "section_lead"
    metadata["graph_source_parent_id"] = parent_id
    return _make_document(page_content=str(node.get("text", "")), metadata=metadata)


def get_described_by_doc(
    graph: Dict[str, Any],
    chunk_uid: str,
    hydrate_metadata: MetadataHydrator,
) -> Optional[Document]:
    node = get_structure_node(graph, chunk_uid, hydrate_metadata)
    if not node:
        return None
    described_by_uid = str(node.get("described_by_uid") or "")
    if not described_by_uid:
        return None
    paragraph_node = get_structure_node(graph, described_by_uid, hydrate_metadata)
    if not paragraph_node:
        return None
    metadata = dict(paragraph_node.get("metadata", {}) or {})
    metadata["graph_relation"] = "described_by_paragraph"
    metadata["graph_source_chunk_uid"] = chunk_uid
    return _make_document(page_content=str(paragraph_node.get("text", "")), metadata=metadata)


def get_sibling_docs(
    graph: Dict[str, Any],
    parent_id: str,
    chunk_uid: str,
    hydrate_metadata: MetadataHydrator,
    *,
    window: int = 1,
) -> List[Document]:
    if not parent_id or not chunk_uid or window <= 0:
        return []

    parent_chunks = list(((graph or {}).get("parents", {}) or {}).get(parent_id, []) or [])
    if chunk_uid not in parent_chunks:
        return []

    index = parent_chunks.index(chunk_uid)
    start = max(0, index - window)
    end = min(len(parent_chunks), index + window + 1)
    siblings: List[Document] = []

    for sibling_index in range(start, end):
        sibling_uid = parent_chunks[sibling_index]
        if sibling_uid == chunk_uid:
            continue
        node = get_structure_node(graph, sibling_uid, hydrate_metadata)
        if not node:
            continue
        metadata = dict(node.get("metadata", {}) or {})
        direction = "sibling_prev" if sibling_index < index else "sibling_next"
        metadata["graph_relation"] = direction
        metadata["graph_source_chunk_uid"] = chunk_uid
        siblings.append(_make_document(page_content=str(node.get("text", "")), metadata=metadata))

    return siblings


def get_reference_docs(
    graph: Dict[str, Any],
    chunk_uid: str,
    hydrate_metadata: MetadataHydrator,
    *,
    limit: int = 4,
) -> List[Document]:
    node = get_structure_node(graph, chunk_uid, hydrate_metadata)
    if not node or limit <= 0:
        return []

    metadata = dict(node.get("metadata", {}) or {})
    source_parent_id = str(metadata.get("parent_id") or "")
    reference_parent_ids = [
        str(value).strip()
        for value in (metadata.get("reference_parent_ids") or node.get("reference_parent_ids") or [])
        if str(value).strip()
    ]
    if not reference_parent_ids:
        return []

    docs: List[Document] = []
    seen_parent_ids: set[str] = set()
    for reference_parent_id in reference_parent_ids:
        if reference_parent_id in seen_parent_ids or reference_parent_id == source_parent_id:
            continue
        seen_parent_ids.add(reference_parent_id)

        referenced_doc = get_section_lead_doc(
            graph,
            reference_parent_id,
            hydrate_metadata,
            exclude_chunk_uid=None,
        )
        if referenced_doc is None:
            section = ((graph or {}).get("sections", {}) or {}).get(reference_parent_id) or {}
            chunk_uids = list(section.get("chunk_uids", []) or [])
            if not chunk_uids:
                continue
            fallback_node = get_structure_node(graph, str(chunk_uids[0]), hydrate_metadata)
            if not fallback_node:
                continue
            fallback_metadata = dict(fallback_node.get("metadata", {}) or {})
            referenced_doc = _make_document(
                page_content=str(fallback_node.get("text", "")),
                metadata=fallback_metadata,
            )

        ref_metadata = dict(referenced_doc.metadata or {})
        ref_metadata["graph_relation"] = "reference_note"
        ref_metadata["graph_source_chunk_uid"] = chunk_uid
        ref_metadata["graph_reference_parent_id"] = reference_parent_id
        docs.append(_make_document(page_content=referenced_doc.page_content, metadata=ref_metadata))

        if len(docs) >= limit:
            break

    return docs
