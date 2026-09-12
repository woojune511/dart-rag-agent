"""Project metadata eligibility into a shared native dense/lexical filter."""
from __future__ import annotations

from copy import deepcopy
import hashlib
import json
from typing import Any, Callable, Mapping, Sequence

from src.storage.bm25_index import metadata_matches_filter


def restrict_search_filter(
    metadata_rows: Sequence[Mapping[str, Any]], *, where_filter: dict | None,
    allowed: Callable[[Mapping[str, Any]], bool],
) -> tuple[dict, dict[str, Any]]:
    """Use observed source IDs, qualified by their stored document identity.

    No rank or text inference enters eligibility. Missing IDs are observable,
    not synthesized metadata fields that a native index cannot filter on.
    """
    groups: dict[tuple[str, str, str], set[str]] = {}
    report_count = matched_count = unaddressable_count = 0
    for metadata in metadata_rows:
        if not metadata_matches_filter(metadata, where_filter):
            continue
        report_count += 1
        if not allowed(metadata):
            continue
        matched_count += 1
        key = next((key for key in ("chunk_uid", "id")
                    if isinstance(metadata.get(key), str) and metadata[key].strip()), "")
        if not key:
            unaddressable_count += 1
            continue
        document_key = next((key for key in ("rcept_no", "document_id", "source_document_id")
                             if isinstance(metadata.get(key), str) and metadata[key].strip()), "")
        groups.setdefault((key, document_key, metadata.get(document_key, "")), set()).add(metadata[key])
    alternatives = []
    for (key, document_key, document_id), ids in sorted(groups.items()):
        identity = {key: {"$in": sorted(ids)}}
        alternatives.append({"$and": [{document_key: document_id}, identity]} if document_key else identity)
    # Empty membership is an explicit zero-source filter. The storage owner
    # short-circuits it before constructing any provider/backend request.
    restriction = (alternatives[0] if len(alternatives) == 1 else
                   {"$or": alternatives} if alternatives else {"chunk_uid": {"$in": []}})
    result = {"$and": [deepcopy(where_filter), restriction]} if where_filter else restriction
    fingerprint = hashlib.sha256(json.dumps(result, ensure_ascii=False, sort_keys=True,
                                            separators=(",", ":")).encode("utf-8")).hexdigest()
    return result, {
        "applied": True, "stage": "before_dense_bm25_top_k",
        "report_source_count": report_count, "matching_source_count": matched_count,
        "eligible_source_count": sum(len(ids) for ids in groups.values()),
        "unaddressable_source_count": unaddressable_count,
        "filter_fingerprint": fingerprint,
    }


def filter_selects_nothing(where_filter: dict | None) -> bool:
    """Recognize explicit empty membership, including nested conjunction/union."""
    if not where_filter:
        return False
    if "$and" in where_filter:
        return any(filter_selects_nothing(clause) for clause in where_filter["$and"])
    if "$or" in where_filter:
        return all(filter_selects_nothing(clause) for clause in where_filter["$or"])
    return any(isinstance(value, dict) and value.get("$in") == [] for value in where_filter.values())
