from __future__ import annotations

from typing import TYPE_CHECKING, Any, Hashable, List, Optional, Tuple

if TYPE_CHECKING:
    from langchain_core.documents import Document


if TYPE_CHECKING:
    SearchResult = Tuple[Document, float]
else:
    SearchResult = Tuple[Any, float]


def doc_identity(doc: Document) -> str:
    metadata = getattr(doc, "metadata", {}) or {}
    return (
        metadata.get("chunk_uid")
        or metadata.get("id")
        or "|".join(
            str(metadata.get(key, ""))
            for key in ("rcept_no", "chunk_id", "sub_chunk_idx", "company", "year", "section_path")
        )
        or doc.page_content
    )


def freeze_filter(where_filter: Optional[dict]) -> Hashable:
    if where_filter is None:
        return ()
    if isinstance(where_filter, dict):
        return tuple(sorted((str(key), freeze_filter(value)) for key, value in where_filter.items()))
    if isinstance(where_filter, list):
        return tuple(freeze_filter(item) for item in where_filter)
    return where_filter


def search_cache_key(
    query: str,
    *,
    k: int,
    k_rrf: int,
    where_filter: Optional[dict],
) -> Tuple[str, int, int, Hashable]:
    normalized_query = " ".join(str(query or "").split())
    return (normalized_query, int(k), int(k_rrf), freeze_filter(where_filter))


def merge_rrf_results(
    vector_results: List[SearchResult],
    bm25_results: List[SearchResult],
    *,
    k: int,
    k_rrf: int,
) -> List[SearchResult]:
    rrf_scores: dict[str, float] = {}
    doc_map: dict[str, Document] = {}

    for rank, (doc, _) in enumerate(vector_results, 1):
        doc_id = doc_identity(doc)
        doc_map[doc_id] = doc
        rrf_scores[doc_id] = 1.0 / (int(k_rrf) + rank)

    for rank, (doc, _) in enumerate(bm25_results, 1):
        doc_id = doc_identity(doc)
        doc_map[doc_id] = doc
        rrf_scores[doc_id] = rrf_scores.get(doc_id, 0.0) + 1.0 / (int(k_rrf) + rank)

    sorted_rrf = sorted(rrf_scores.items(), key=lambda item: item[1], reverse=True)
    return [(doc_map[doc_id], rrf_score) for doc_id, rrf_score in sorted_rrf[: int(k)]]
