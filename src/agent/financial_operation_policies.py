"""Generic answer-surface policy helpers."""

from __future__ import annotations

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import (
    HELPER_RUNTIME_POLICY,
    KOREAN_PERCENT_METRIC_HINT_TERMS,
)

def query_requests_narrative_context(query: str) -> bool:
    normalized = _normalise_spaces(str(query or "")).lower()
    if not normalized:
        return False
    narrative_hints = tuple(str(item) for item in (HELPER_RUNTIME_POLICY.get("narrative_context_hints") or ()) if str(item))
    return any(token in normalized for token in narrative_hints)

def label_implies_percent_metric(label: str) -> bool:
    normalized = _normalise_spaces(str(label or ""))
    if not normalized:
        return False
    return any(
        token in normalized
        for token in (*KOREAN_PERCENT_METRIC_HINT_TERMS, "%", "%p")
    )
