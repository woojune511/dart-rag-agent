from __future__ import annotations

from typing import Any, Dict, Optional, Sequence


Chroma = None


def get_chroma_cls():
    """Return Chroma lazily so importing storage code does not load the backend."""
    global Chroma
    if Chroma is None:
        from langchain_community.vectorstores import Chroma as impl

        Chroma = impl
    return Chroma


def is_embedding_capacity_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    markers = (
        "resource_exhausted",
        "429",
        "rate limit",
        "quota",
        "error embedding content",
        "embed_query",
    )
    return any(marker in message for marker in markers)


def is_vector_store_read_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    markers = (
        "error loading hnsw index",
        "hnsw",
        "segment reader",
        "backfill request to compactor",
        "constructing hnsw segment reader",
    )
    return any(marker in message for marker in markers)


def is_transient_vector_add_error(exc: Exception) -> bool:
    message = str(exc or "").lower()
    markers = (
        "503",
        "unavailable",
        "service is currently unavailable",
        "servererror",
        "resource_exhausted",
        "429",
        "rate limit",
        "quota",
        "error embedding content",
    )
    return any(marker in message for marker in markers)


def probe_vector_index(
    vector_store: Any,
    bm25_docs: Sequence[str],
    *,
    query: Optional[str] = None,
    where_filter: Optional[dict] = None,
) -> Dict[str, Any]:
    """Probe vector search directly without allowing BM25 fallback."""
    probe = (query or "").strip()
    if not probe:
        for doc in bm25_docs:
            probe = str(doc or "").strip()
            if probe:
                break
    if not probe:
        probe = "vector store health check"
    probe = " ".join(probe.split())[:500]

    try:
        results = vector_store.similarity_search_with_score(
            probe,
            k=1,
            filter=where_filter,
        )
    except Exception as exc:
        return {
            "ok": False,
            "error": str(exc),
            "embedding_capacity_error": is_embedding_capacity_error(exc),
            "vector_store_read_error": is_vector_store_read_error(exc),
            "probe_query": probe,
        }

    return {
        "ok": bool(results),
        "result_count": len(results or []),
        "probe_query": probe,
    }
