"""Retrieval query budget, dedupe, and fan-out telemetry helpers."""

import json
import re
from typing import Any, Dict, List

from src.agent.financial_graph_helpers import _normalise_spaces


def _query_budget_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except (TypeError, ValueError):
        return 0
    return max(parsed, 0)


def _retrieval_query_signature(query: Any) -> str:
    normalized = _normalise_spaces(str(query or "")).lower()
    if not normalized:
        return ""
    return re.sub(r"\s+", " ", normalized)


def _dedupe_queries_for_retrieval(queries: List[str]) -> List[str]:
    seen: set[str] = set()
    deduped: List[str] = []
    for query in queries:
        normalized = _normalise_spaces(str(query or ""))
        if not normalized:
            continue
        signature = _retrieval_query_signature(normalized)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(normalized)
    return deduped


def _drop_queries_already_selected(
    queries: List[str],
    selected_queries: List[str],
) -> tuple[List[str], Dict[str, Any]]:
    selected_signatures = {
        signature
        for signature in (_retrieval_query_signature(query) for query in selected_queries)
        if signature
    }
    kept: List[str] = []
    dropped: List[str] = []
    for query in queries:
        signature = _retrieval_query_signature(query)
        if signature and signature in selected_signatures:
            dropped.append(query)
            continue
        kept.append(query)
    return kept, {
        "duplicate_selected_query_dropped_count": len(dropped),
        "duplicate_selected_query_dropped_queries": dropped,
    }


def _drop_duplicate_executed_query(
    seen_signatures_by_source: Dict[str, set[str]],
    trace: Dict[str, Any],
    *,
    source: str,
    executed_query: str,
    base_query: str,
) -> bool:
    source_key = _normalise_spaces(str(source or "unknown")) or "unknown"
    signature = _retrieval_query_signature(executed_query)
    if not signature:
        return False
    seen = seen_signatures_by_source.setdefault(source_key, set())
    if signature not in seen:
        seen.add(signature)
        return False

    by_source = trace.setdefault("by_source", {})
    source_trace = by_source.setdefault(
        source_key,
        {
            "dropped_count": 0,
            "dropped_queries": [],
        },
    )
    source_trace["dropped_count"] = int(source_trace.get("dropped_count") or 0) + 1
    source_trace.setdefault("dropped_queries", []).append(
        {
            "base_query": base_query,
            "executed_query": executed_query,
        }
    )
    trace["dropped_count"] = int(trace.get("dropped_count") or 0) + 1
    return True


def _limit_query_context_terms(
    items: List[str],
    budget: int,
    *,
    strategy: str = "head",
) -> tuple[List[str], Dict[str, Any]]:
    cleaned = [_normalise_spaces(str(item or "")) for item in items]
    cleaned = [item for item in cleaned if item]
    deduped = list(dict.fromkeys(cleaned))
    if budget <= 0 or len(deduped) <= budget:
        selected = deduped
    elif strategy == "head_tail":
        head_count = (budget + 1) // 2
        tail_count = budget - head_count
        selected = list(deduped[:head_count])
        for item in deduped[len(deduped) - tail_count :] if tail_count else []:
            if item not in selected:
                selected.append(item)
    else:
        selected = deduped[:budget]
    dropped_terms = [item for item in deduped if item not in selected]
    return selected, {
        "input_count": len(cleaned),
        "deduped_count": len(deduped),
        "selected_count": len(selected),
        "budget": budget,
        "selection_strategy": strategy,
        "dropped_count": max(len(deduped) - len(selected), 0),
        "dropped_terms": dropped_terms,
    }


def _period_balanced_queries_for_retrieval(queries: List[str]) -> List[str]:
    grouped: Dict[tuple[str, ...], List[str]] = {}
    group_order: List[tuple[str, ...]] = []
    for query in queries:
        years = tuple(dict.fromkeys(re.findall(r"20\d{2}", query)))
        key = years or ("",)
        if key not in grouped:
            grouped[key] = []
            group_order.append(key)
        grouped[key].append(query)
    if len(group_order) <= 1:
        return queries

    balanced: List[str] = []
    index = 0
    while len(balanced) < len(queries):
        progressed = False
        for key in group_order:
            bucket = grouped[key]
            if index < len(bucket):
                balanced.append(bucket[index])
                progressed = True
        if not progressed:
            break
        index += 1
    return balanced


def _apply_query_budget(
    queries: List[str],
    budget: int,
    *,
    dedupe: bool = True,
) -> tuple[List[str], Dict[str, Any]]:
    normalized = [_normalise_spaces(str(item or "")) for item in queries]
    normalized = [item for item in normalized if item]
    candidates = _dedupe_queries_for_retrieval(normalized) if dedupe else normalized
    if budget <= 0 or len(candidates) <= budget:
        selected = candidates
    else:
        candidates = _period_balanced_queries_for_retrieval(candidates)
        selected = candidates[:budget]
    return selected, {
        "input_count": len(normalized),
        "deduped_count": len(candidates),
        "selected_count": len(selected),
        "budget": budget,
        "dropped_count": max(len(candidates) - len(selected), 0),
        "dropped_queries": candidates[len(selected) :],
        "dedupe_enabled": dedupe,
    }


def _summarize_executed_query_telemetry(executed_queries: List[Dict[str, Any]]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {
        "executed_query_count": len(executed_queries),
        "cache_hit_count": 0,
        "vector_attempted_count": 0,
        "embedding_api_calls": 0,
        "embedding_text_count": 0,
        "query_embedding_api_calls": 0,
        "query_embedding_text_count": 0,
        "by_source": {},
    }
    for query_trace in executed_queries:
        source = _normalise_spaces(str(query_trace.get("source") or "unknown")) or "unknown"
        by_source = summary["by_source"].setdefault(
            source,
            {
                "executed_query_count": 0,
                "cache_hit_count": 0,
                "vector_attempted_count": 0,
                "embedding_api_calls": 0,
                "query_embedding_api_calls": 0,
            },
        )
        by_source["executed_query_count"] += 1

        telemetry = dict(query_trace.get("search_telemetry") or {})
        if not telemetry:
            continue
        if bool(telemetry.get("cache_hit")):
            summary["cache_hit_count"] += 1
            by_source["cache_hit_count"] += 1
        if bool(telemetry.get("vector_attempted")):
            summary["vector_attempted_count"] += 1
            by_source["vector_attempted_count"] += 1
        embedding_usage = dict(telemetry.get("embedding_usage") or {})
        embedding_api_calls = int(embedding_usage.get("embedding_api_calls") or 0)
        embedding_text_count = int(embedding_usage.get("embedding_text_count") or 0)
        query_embedding_api_calls = int(embedding_usage.get("query_embedding_api_calls") or 0)
        query_embedding_text_count = int(embedding_usage.get("query_embedding_text_count") or 0)
        summary["embedding_api_calls"] += embedding_api_calls
        summary["embedding_text_count"] += embedding_text_count
        summary["query_embedding_api_calls"] += query_embedding_api_calls
        summary["query_embedding_text_count"] += query_embedding_text_count
        by_source["embedding_api_calls"] += embedding_api_calls
        by_source["query_embedding_api_calls"] += query_embedding_api_calls
    return summary


def _filter_signature(value: Any) -> str:
    if value in (None, ""):
        return ""
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        return str(value)


def _query_result_cache_key(
    *,
    source: str,
    executed_query: Any,
    where_filter: Any,
) -> str:
    source_key = _normalise_spaces(str(source or "unknown")) or "unknown"
    query_signature = _retrieval_query_signature(executed_query)
    if not query_signature:
        return ""
    return "\0".join((source_key, query_signature, _filter_signature(where_filter)))


def _lookup_query_result_cache(
    cache: Dict[str, Dict[str, Any]],
    *,
    source: str,
    executed_query: Any,
    where_filter: Any,
    k: int,
) -> Dict[str, Any]:
    key = _query_result_cache_key(
        source=source,
        executed_query=executed_query,
        where_filter=where_filter,
    )
    if not key:
        return {}
    entry = dict(cache.get(key) or {})
    if not entry:
        return {}
    cached_k = int(entry.get("k") or 0)
    if cached_k < int(k or 0):
        return {}
    return {
        **entry,
        "cache_key": key,
        "docs": list(entry.get("docs") or [])[: int(k or 0)],
    }


def _store_query_result_cache(
    cache: Dict[str, Dict[str, Any]],
    *,
    source: str,
    executed_query: Any,
    where_filter: Any,
    k: int,
    docs: List[Any],
) -> Dict[str, Any]:
    key = _query_result_cache_key(
        source=source,
        executed_query=executed_query,
        where_filter=where_filter,
    )
    if not key:
        return {}
    entry = {
        "source": _normalise_spaces(str(source or "unknown")) or "unknown",
        "executed_query": str(executed_query or ""),
        "where_filter": where_filter,
        "where_filter_signature": _filter_signature(where_filter),
        "k": int(k or 0),
        "docs": list(docs or []),
        "doc_count": len(list(docs or [])),
    }
    cache[key] = entry
    return {"cache_key": key, **entry}


def _trace_task_context(trace: Dict[str, Any]) -> Dict[str, str]:
    source = dict((trace.get("query_budget") or {}).get("source") or {})
    return {
        "task_id": str(source.get("active_subtask_id") or ""),
        "operation": str(source.get("active_subtask_operation") or ""),
    }


def _cross_trace_reuse_candidate_diagnostics(
    executed_queries: List[Dict[str, Any]],
    previous_traces: List[Dict[str, Any]],
    *,
    current_trace_index: int,
    max_candidates: int = 20,
) -> Dict[str, Any]:
    previous_by_key: Dict[tuple[str, str, str], List[Dict[str, Any]]] = {}
    for trace_offset, trace in enumerate(previous_traces, start=1):
        if not isinstance(trace, dict):
            continue
        task_context = _trace_task_context(trace)
        for query_trace in trace.get("executed_queries") or []:
            if not isinstance(query_trace, dict):
                continue
            source = _normalise_spaces(str(query_trace.get("source") or "unknown")) or "unknown"
            signature = _retrieval_query_signature(query_trace.get("executed_query"))
            if not signature:
                continue
            filter_signature = _filter_signature(query_trace.get("where_filter"))
            key = (source, signature, filter_signature)
            previous_by_key.setdefault(key, []).append(
                {
                    "trace_index": trace_offset,
                    "task_id": task_context.get("task_id", ""),
                    "operation": task_context.get("operation", ""),
                    "source": source,
                    "base_query": query_trace.get("base_query"),
                    "executed_query": query_trace.get("executed_query"),
                    "cache_hit": bool((query_trace.get("search_telemetry") or {}).get("cache_hit")),
                }
            )

    candidates: List[Dict[str, Any]] = []
    by_source: Dict[str, Dict[str, int]] = {}
    for query_trace in executed_queries:
        source = _normalise_spaces(str(query_trace.get("source") or "unknown")) or "unknown"
        signature = _retrieval_query_signature(query_trace.get("executed_query"))
        if not signature:
            continue
        filter_signature = _filter_signature(query_trace.get("where_filter"))
        prior_matches = previous_by_key.get((source, signature, filter_signature), [])
        if not prior_matches:
            continue
        source_summary = by_source.setdefault(source, {"candidate_count": 0, "prior_match_count": 0})
        source_summary["candidate_count"] += 1
        source_summary["prior_match_count"] += len(prior_matches)
        if len(candidates) >= max(max_candidates, 0):
            continue
        candidates.append(
            {
                "source": source,
                "signature": signature,
                "base_query": query_trace.get("base_query"),
                "executed_query": query_trace.get("executed_query"),
                "where_filter_signature": filter_signature,
                "current_trace_index": current_trace_index,
                "current_cache_hit": bool((query_trace.get("search_telemetry") or {}).get("cache_hit")),
                "prior_match_count": len(prior_matches),
                "prior_matches": prior_matches[:5],
            }
        )

    candidate_count = sum(int(item.get("candidate_count") or 0) for item in by_source.values())
    prior_match_count = sum(int(item.get("prior_match_count") or 0) for item in by_source.values())
    return {
        "enabled": True,
        "mode": "trace_only",
        "scope": "cross_trace_same_source_same_filter_exact_signature",
        "candidate_count": candidate_count,
        "prior_match_count": prior_match_count,
        "previous_trace_count": len(previous_traces),
        "current_trace_index": current_trace_index,
        "by_source": by_source,
        "candidates": candidates,
        "truncated": candidate_count > len(candidates),
    }
