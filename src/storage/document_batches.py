from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, List, Optional


PreparedChunk = tuple[str, dict, str]


@dataclass(frozen=True)
class PreparedDocuments:
    chunks: List[PreparedChunk]
    duplicate_input_count: int


def prepare_documents_for_add(
    chunks: Iterable[str],
    metadatas: Iterable[dict],
    *,
    chunk_uid_from_metadata: Callable[[Dict[str, Any]], str],
) -> PreparedDocuments:
    prepared: List[PreparedChunk] = []
    seen_input_chunk_uids: set[str] = set()
    duplicate_input_count = 0

    for text, metadata in zip(chunks, metadatas):
        normalized_metadata = dict(metadata or {})
        chunk_uid = chunk_uid_from_metadata(normalized_metadata)
        if chunk_uid and chunk_uid in seen_input_chunk_uids:
            duplicate_input_count += 1
            continue
        if chunk_uid:
            seen_input_chunk_uids.add(chunk_uid)
        prepared.append((text, normalized_metadata, chunk_uid))

    return PreparedDocuments(chunks=prepared, duplicate_input_count=duplicate_input_count)


def single_rcept_no_for_resume(prepared: Iterable[PreparedChunk]) -> Optional[str]:
    rcept_nos = {
        str(metadata.get("rcept_no")).strip()
        for _, metadata, _ in prepared
        if str(metadata.get("rcept_no", "")).strip()
    }
    return next(iter(rcept_nos)) if len(rcept_nos) == 1 else None


def pending_documents(
    prepared: Iterable[PreparedChunk],
    *,
    existing_chunk_uids: set[str],
) -> List[PreparedChunk]:
    return [
        (text, metadata, chunk_uid)
        for text, metadata, chunk_uid in prepared
        if not chunk_uid or chunk_uid not in existing_chunk_uids
    ]


def batch_count(item_count: int, batch_size: int) -> int:
    effective_batch_size = max(int(batch_size or 0), 1)
    return (int(item_count) + effective_batch_size - 1) // effective_batch_size


def iter_batches(items: List[PreparedChunk], batch_size: int) -> Iterable[List[PreparedChunk]]:
    effective_batch_size = max(int(batch_size or 0), 1)
    for start in range(0, len(items), effective_batch_size):
        yield items[start : start + effective_batch_size]


def batch_texts(batch: Iterable[PreparedChunk]) -> List[str]:
    return [text for text, _, _ in batch]


def batch_metadatas(batch: Iterable[PreparedChunk]) -> List[dict]:
    return [metadata for _, metadata, _ in batch]
