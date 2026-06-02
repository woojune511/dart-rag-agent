"""Utilities for tracking embedding API usage without extra provider calls."""

from __future__ import annotations

import math
import threading
from typing import Any, Dict, Iterable, Mapping


_USAGE_KEYS = (
    "embedding_api_calls",
    "embedding_text_count",
    "embedding_input_chars",
    "embedding_estimated_input_tokens",
    "query_embedding_api_calls",
    "query_embedding_text_count",
    "query_embedding_input_chars",
    "query_embedding_estimated_input_tokens",
    "document_embedding_api_calls",
    "document_embedding_text_count",
    "document_embedding_input_chars",
    "document_embedding_estimated_input_tokens",
)


def estimate_embedding_input_tokens(text: str) -> int:
    """Return a cheap local token estimate for embedding inputs.

    Provider embedding APIs used through LangChain return vectors, not response
    usage metadata. This estimate avoids adding a separate count-tokens call.
    """
    cleaned = str(text or "")
    if not cleaned:
        return 0
    return max(1, int(math.ceil(len(cleaned) / 4.0)))


def zero_embedding_usage_counts() -> Dict[str, int]:
    return {key: 0 for key in _USAGE_KEYS}


def add_embedding_usage_counts(target: Dict[str, int], usage: Mapping[str, Any]) -> None:
    for key in _USAGE_KEYS:
        try:
            target[key] = int(target.get(key, 0) or 0) + int(usage.get(key, 0) or 0)
        except (TypeError, ValueError):
            target[key] = int(target.get(key, 0) or 0)


def subtract_embedding_usage_counts(after: Mapping[str, Any], before: Mapping[str, Any]) -> Dict[str, int]:
    delta = zero_embedding_usage_counts()
    for key in _USAGE_KEYS:
        delta[key] = max(int(after.get(key, 0) or 0) - int(before.get(key, 0) or 0), 0)
    return delta


def estimate_embedding_cost_usd(usage: Mapping[str, Any], pricing: Mapping[str, Any] | None) -> float | None:
    if not pricing:
        return None
    rate = float(pricing.get("embedding_input_per_million_tokens_usd", 0.0) or 0.0)
    if rate <= 0.0:
        return None
    tokens = int(usage.get("embedding_estimated_input_tokens", 0) or 0)
    return (tokens / 1_000_000.0) * rate


class TrackingEmbeddings:
    """Wrap a LangChain embeddings object and count embedding input volume."""

    def __init__(self, inner: Any) -> None:
        self._inner = inner
        self._lock = threading.Lock()
        self._local = threading.local()
        self._usage = zero_embedding_usage_counts()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._inner, name)

    def _record(self, *, kind: str, texts: Iterable[str]) -> None:
        text_list = [str(text or "") for text in texts]
        input_chars = sum(len(text) for text in text_list)
        estimated_tokens = sum(estimate_embedding_input_tokens(text) for text in text_list)
        prefix = "query" if kind == "query" else "document"
        local_usage = self._local_usage()
        local_usage["embedding_api_calls"] += 1
        local_usage["embedding_text_count"] += len(text_list)
        local_usage["embedding_input_chars"] += input_chars
        local_usage["embedding_estimated_input_tokens"] += estimated_tokens
        local_usage[f"{prefix}_embedding_api_calls"] += 1
        local_usage[f"{prefix}_embedding_text_count"] += len(text_list)
        local_usage[f"{prefix}_embedding_input_chars"] += input_chars
        local_usage[f"{prefix}_embedding_estimated_input_tokens"] += estimated_tokens
        with self._lock:
            self._usage["embedding_api_calls"] += 1
            self._usage["embedding_text_count"] += len(text_list)
            self._usage["embedding_input_chars"] += input_chars
            self._usage["embedding_estimated_input_tokens"] += estimated_tokens
            self._usage[f"{prefix}_embedding_api_calls"] += 1
            self._usage[f"{prefix}_embedding_text_count"] += len(text_list)
            self._usage[f"{prefix}_embedding_input_chars"] += input_chars
            self._usage[f"{prefix}_embedding_estimated_input_tokens"] += estimated_tokens

    def _local_usage(self) -> Dict[str, int]:
        usage = getattr(self._local, "usage", None)
        if usage is None:
            usage = zero_embedding_usage_counts()
            self._local.usage = usage
        return usage

    def snapshot_usage(self) -> Dict[str, int]:
        with self._lock:
            return dict(self._usage)

    def reset_usage(self) -> None:
        with self._lock:
            self._usage = zero_embedding_usage_counts()

    def reset_current_thread_usage(self) -> None:
        self._local.usage = zero_embedding_usage_counts()

    def snapshot_current_thread_usage(self) -> Dict[str, int]:
        return dict(self._local_usage())

    def embed_query(self, text: str, *args: Any, **kwargs: Any) -> list[float]:
        result = self._inner.embed_query(text, *args, **kwargs)
        self._record(kind="query", texts=[text])
        return result

    def embed_documents(self, texts: list[str], *args: Any, **kwargs: Any) -> list[list[float]]:
        result = self._inner.embed_documents(texts, *args, **kwargs)
        self._record(kind="document", texts=texts)
        return result
