"""Experimental MAS diagnostic helper facade.

These helpers support ops probes around MAS worker behavior. They intentionally
stay out of the top-level MAS namespace so the product-facing runtime surface
does not grow around diagnostic-only utilities.
"""

from __future__ import annotations

from typing import Any, Dict, Optional, Sequence

from langchain_core.documents import Document

from src.agent.nodes.researcher_node import (
    _build_enriched_query,
    _build_where_filter,
    _select_narrative_docs,
)


def build_researcher_probe_query(query: str, report_scope: Dict[str, Any] | None) -> str:
    return _build_enriched_query(query, report_scope)


def build_researcher_probe_where_filter(
    report_scope: Dict[str, Any] | None,
) -> Optional[Dict[str, Any]]:
    return _build_where_filter(report_scope)


def select_researcher_probe_docs(
    docs: Sequence[Any],
    *,
    limit: int,
) -> list[tuple[Document, float]]:
    return _select_narrative_docs(docs, limit=limit)


__all__ = [
    "build_researcher_probe_query",
    "build_researcher_probe_where_filter",
    "select_researcher_probe_docs",
]
