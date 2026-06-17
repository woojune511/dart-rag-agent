import hashlib
import json
import os
from pathlib import Path
from typing import Any, Dict, Optional


CHROMA_METADATA_MAX_STRING_LEN = int(os.getenv("DART_CHROMA_METADATA_MAX_STRING_LEN", "8192") or 8192)
CHROMA_METADATA_DROP_KEYS = frozenset(
    {
        "table_object_json",
        "table_row_records_json",
        "table_value_records_json",
    }
)
TABLE_PAYLOAD_METADATA_KEYS = tuple(sorted(CHROMA_METADATA_DROP_KEYS))
TABLE_PAYLOAD_ID_KEY = "table_payload_id"


def metadata_for_chroma(metadata: Dict[str, Any]) -> Dict[str, Any]:
    """Return bounded metadata for Chroma's sqlite metadata table."""
    sanitized: Dict[str, Any] = {}
    for key, value in dict(metadata or {}).items():
        if key in CHROMA_METADATA_DROP_KEYS or value is None:
            continue
        if isinstance(value, (str, int, float, bool)):
            sanitized[key] = value[:CHROMA_METADATA_MAX_STRING_LEN] if isinstance(value, str) else value
            continue
        if isinstance(value, (list, tuple, set)):
            joined = " | ".join(str(item).strip() for item in value if str(item).strip())
            if joined:
                sanitized[key] = joined[:CHROMA_METADATA_MAX_STRING_LEN]
            continue
        if isinstance(value, dict):
            compact_json = json.dumps(value, ensure_ascii=False)
            if len(compact_json) <= CHROMA_METADATA_MAX_STRING_LEN:
                sanitized[key] = compact_json
    return sanitized


def table_payload_sidecar_stats(
    payloads: Dict[str, Dict[str, str]],
    nodes: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    payload_json_bytes = {
        payload_id: len(json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8"))
        for payload_id, payload in dict(payloads or {}).items()
    }
    referenced_ids: list[str] = []
    for node in dict(nodes or {}).values():
        metadata = dict((node or {}).get("metadata") or {})
        payload_id = str(metadata.get(TABLE_PAYLOAD_ID_KEY) or "").strip()
        if payload_id and payload_id in payload_json_bytes:
            referenced_ids.append(payload_id)

    inline_payload_bytes = sum(payload_json_bytes[payload_id] for payload_id in referenced_ids)
    unique_payload_bytes = sum(payload_json_bytes.values())
    return {
        "payload_count": len(payload_json_bytes),
        "referenced_node_count": len(referenced_ids),
        "metadata_keys": list(TABLE_PAYLOAD_METADATA_KEYS),
        "unique_payload_bytes": unique_payload_bytes,
        "inline_payload_bytes_estimate": inline_payload_bytes,
        "deduplicated_payload_bytes_saved_estimate": max(0, inline_payload_bytes - unique_payload_bytes),
    }


def load_table_payloads(path: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if path and path.exists():
        payload = json.loads(path.read_text(encoding="utf-8"))
        raw_payloads = payload.get("payloads", payload) if isinstance(payload, dict) else {}
        if isinstance(raw_payloads, dict):
            return {
                str(payload_id): {
                    key: str(value)
                    for key, value in dict(raw_payload or {}).items()
                    if key in TABLE_PAYLOAD_METADATA_KEYS and str(value or "").strip()
                }
                for payload_id, raw_payload in raw_payloads.items()
                if isinstance(raw_payload, dict)
            }
    return {}


def table_payload_id(payload: Dict[str, str]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "table_payload:" + hashlib.sha256(encoded).hexdigest()


def metadata_with_table_payload(
    metadata: Dict[str, Any],
    table_payloads: Dict[str, Dict[str, str]],
) -> Dict[str, Any]:
    hydrated = dict(metadata or {})
    payload_id = str(hydrated.get(TABLE_PAYLOAD_ID_KEY) or "").strip()
    payload = dict(table_payloads.get(payload_id, {}) or {}) if payload_id else {}
    for key, value in payload.items():
        hydrated.setdefault(key, value)
    return hydrated


def compact_node_for_storage(
    node: Dict[str, Any],
    payloads: Dict[str, Dict[str, str]],
    existing_payloads: Optional[Dict[str, Dict[str, str]]] = None,
) -> Dict[str, Any]:
    compact_node = dict(node or {})
    metadata = dict(compact_node.get("metadata") or {})
    table_payload = {
        key: str(metadata.pop(key))
        for key in TABLE_PAYLOAD_METADATA_KEYS
        if str(metadata.get(key) or "").strip()
    }

    payload_id = str(metadata.get(TABLE_PAYLOAD_ID_KEY) or "").strip()
    existing_payloads = dict(existing_payloads or {})
    if table_payload:
        payload_id = table_payload_id(table_payload)
        payloads[payload_id] = table_payload
        metadata[TABLE_PAYLOAD_ID_KEY] = payload_id
    elif payload_id and payload_id in existing_payloads:
        payloads[payload_id] = dict(existing_payloads[payload_id])
        metadata[TABLE_PAYLOAD_ID_KEY] = payload_id
    else:
        metadata.pop(TABLE_PAYLOAD_ID_KEY, None)

    compact_node["metadata"] = metadata
    return compact_node
