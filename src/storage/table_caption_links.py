"""Persisted physical attachments; no query interpretation or neighbor guessing."""

from copy import deepcopy
import hashlib
import json
from pathlib import Path


CAPTION_LINK_VERSION = 1
CAPTION_LINK_FILENAME = "table_caption_links.json"


def node_fingerprint(node, hydrate_metadata):
    """Bind source bytes, scope and table provenance across payload compaction."""
    bound = {key: node.get(key) for key in (
        "chunk_uid", "text", "parent_id", "sibling_prev_uid", "sibling_next_uid",
    )}
    metadata = hydrate_metadata(dict(node.get("metadata") or {}))
    metadata.pop("table_payload_id", None)
    bound["metadata"] = metadata
    encoded = json.dumps(bound, ensure_ascii=False, sort_keys=True,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def load_caption_links(path: Path):
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if (not isinstance(payload, dict) or type(payload.get("version")) is not int
            or payload["version"] != CAPTION_LINK_VERSION
            or not isinstance(payload.get("links"), dict)):
        raise ValueError("Invalid caption link file")
    links = payload["links"]
    required = {"table_uid", "caption_uid", "receipt", "parent_id", "document_sha256",
                "table_locator", "caption_locator", "table_fingerprint", "caption_fingerprint"}
    for uid, link in links.items():
        if (not isinstance(link, dict) or set(link) != required
                or any(not isinstance(v, str) or not v for v in link.values())
                or uid != link["table_uid"] or uid == link["caption_uid"]):
            raise ValueError("Invalid caption link entry")
    return links


def get_caption_doc(graph, links, table_doc, hydrate_metadata):
    """Validate saved witnesses on every lookup, including after store mutation."""
    uid = str(table_doc.metadata.get("chunk_uid") or "")
    link = links.get(uid)
    if link is None:
        return None
    nodes = graph.get("nodes", {})
    table, caption = nodes.get(uid), nodes.get(link["caption_uid"])
    if table is None or caption is None:
        raise ValueError("Caption link references missing source")
    for role, node in (("table", table), ("caption", caption)):
        metadata = hydrate_metadata(dict(node.get("metadata") or {}))
        try:
            source = json.loads(metadata.get("table_object_json") or "{}")
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid caption source provenance") from exc
        if (node_fingerprint(node, hydrate_metadata) != link[role + "_fingerprint"]
                or node.get("parent_id") != link["parent_id"]
                or metadata.get("rcept_no") != link["receipt"]
                or metadata.get("chunk_uid") != node.get("chunk_uid")
                or source.get("source_document_sha256") != link["document_sha256"]
                or source.get("source_table_locator") != link[role + "_locator"]):
            raise ValueError("Stale or mismatched caption source binding")
    if (table.get("sibling_prev_uid") != caption["chunk_uid"]
            or caption.get("sibling_next_uid") != uid):
        raise ValueError("Caption sources are no longer adjacent")
    stored_metadata = hydrate_metadata(dict(table["metadata"]))
    # Search hydration may carry extra debug metadata, but may not replace any
    # stored metadata or body used to bind this physical source.
    if (table_doc.page_content != table["text"]
            or any(table_doc.metadata.get(k) != v for k, v in stored_metadata.items())):
        raise ValueError("Selected table differs from bound source")
    from langchain_core.documents import Document

    return Document(page_content=caption["text"],
                    metadata=deepcopy(hydrate_metadata(dict(caption["metadata"]))))
