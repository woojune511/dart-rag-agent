"""Summarize benchmark retrieval fan-out, usage, cost, and quality signals.

This is an offline audit tool. It reads existing benchmark ``results.json``
bundles and does not run retrieval, the agent, evaluators, or embedding calls.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


LLM_USAGE_KEYS = (
    "api_calls",
    "prompt_tokens",
    "output_tokens",
    "thoughts_tokens",
    "cached_tokens",
    "tool_use_prompt_tokens",
    "total_tokens",
)

EMBEDDING_USAGE_KEYS = (
    "embedding_api_calls",
    "embedding_text_count",
    "embedding_input_chars",
    "embedding_estimated_input_tokens",
    "query_embedding_api_calls",
    "query_embedding_text_count",
    "query_embedding_input_chars",
    "query_embedding_estimated_input_tokens",
)

QUALITY_KEYS = (
    "faithfulness",
    "completeness",
    "context_recall",
    "retrieval_hit_at_k",
    "numeric_equivalence",
    "numeric_grounding",
    "numeric_retrieval_support",
    "calculation_correctness",
)


def _as_float(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_int(value: Any) -> int:
    number = _as_float(value)
    return int(number) if number is not None else 0


def _sum_mapping_values(target: Dict[str, float], source: Mapping[str, Any], keys: Iterable[str]) -> None:
    for key in keys:
        number = _as_float(source.get(key))
        if number is not None:
            target[key] = target.get(key, 0.0) + number


def _safe_dict(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _query_signature(value: Any) -> str:
    text = " ".join(str(value or "").strip().lower().split())
    return text


def _duplicate_query_details(
    occurrences: Sequence[Mapping[str, Any]],
    *,
    limit: int = 5,
) -> List[Dict[str, Any]]:
    details_by_signature: Dict[str, Dict[str, Any]] = {}
    for occurrence in occurrences:
        signature = str(occurrence.get("signature") or "")
        if not signature:
            continue
        source = str(occurrence.get("source") or "unknown")
        trace_index = _as_int(occurrence.get("trace_index"))
        task_id = str(occurrence.get("active_task_id") or "")
        operation = str(occurrence.get("active_task_operation") or "")
        task_key = "/".join(part for part in (task_id, operation) if part) or "unknown"
        detail = details_by_signature.setdefault(
            signature,
            {
                "signature": signature,
                "count": 0,
                "duplicate_count": 0,
                "sources": defaultdict(int),
                "trace_indexes": set(),
                "trace_counts": defaultdict(int),
                "task_contexts": defaultdict(int),
            },
        )
        detail["count"] += 1
        detail["sources"][source] += 1
        detail["trace_indexes"].add(trace_index)
        detail["trace_counts"][trace_index] += 1
        detail["task_contexts"][task_key] += 1

    details: List[Dict[str, Any]] = []
    for detail in details_by_signature.values():
        count = int(detail.get("count") or 0)
        if count <= 1:
            continue
        sources = dict(sorted(dict(detail.get("sources") or {}).items()))
        trace_counts = dict(sorted(dict(detail.get("trace_counts") or {}).items()))
        trace_indexes = sorted(int(item) for item in set(detail.get("trace_indexes") or set()))
        task_contexts = dict(sorted(dict(detail.get("task_contexts") or {}).items()))
        within_trace_duplicate_count = sum(max(int(value) - 1, 0) for value in trace_counts.values())
        details.append(
            {
                "signature": detail.get("signature") or "",
                "count": count,
                "duplicate_count": count - 1,
                "sources": sources,
                "trace_indexes": trace_indexes,
                "trace_count": len(trace_indexes),
                "within_trace_duplicate_count": within_trace_duplicate_count,
                "cross_trace_repeat_count": max(len(trace_indexes) - 1, 0),
                "cross_source": len(sources) > 1,
                "task_contexts": task_contexts,
            }
        )
    details.sort(
        key=lambda item: (
            -int(item.get("duplicate_count") or 0),
            -int(item.get("count") or 0),
            str(item.get("signature") or ""),
        )
    )
    return details[: max(limit, 0)]


def _format_duplicate_query_details(details: Sequence[Mapping[str, Any]], *, limit: int = 3) -> str:
    parts: List[str] = []
    for detail in list(details)[: max(limit, 0)]:
        signature = str(detail.get("signature") or "")
        if len(signature) > 80:
            signature = f"{signature[:77]}..."
        sources = ", ".join(
            f"{source}:{count}"
            for source, count in _safe_dict(detail.get("sources")).items()
        )
        traces = ",".join(str(item) for item in _safe_list(detail.get("trace_indexes")))
        task_contexts = ", ".join(
            f"{task}:{count}"
            for task, count in _safe_dict(detail.get("task_contexts")).items()
        )
        qualifiers: List[str] = []
        if sources:
            qualifiers.append(sources)
        if traces:
            qualifiers.append(f"traces:{traces}")
        within_trace = _as_int(detail.get("within_trace_duplicate_count"))
        cross_trace = _as_int(detail.get("cross_trace_repeat_count"))
        if within_trace:
            qualifiers.append(f"same-trace-dup:{within_trace}")
        if cross_trace:
            qualifiers.append(f"cross-trace-repeat:{cross_trace}")
        if bool(detail.get("cross_source")):
            qualifiers.append("cross-source")
        if task_contexts and task_contexts != "unknown":
            qualifiers.append(f"tasks:{task_contexts}")
        if qualifiers:
            parts.append(f"{signature} ({detail.get('count')}x; {'; '.join(qualifiers)})")
        else:
            parts.append(f"{signature} ({detail.get('count')}x)")
    return "; ".join(parts)


def find_result_files(paths: Sequence[Path]) -> List[Path]:
    """Resolve files or directories into unique ``results.json`` files."""

    result_files: List[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        candidates: Iterable[Path]
        if resolved.is_file():
            candidates = [resolved]
        elif resolved.is_dir():
            direct = resolved / "results.json"
            if direct.exists():
                candidates = [direct]
            else:
                candidates = sorted(resolved.rglob("results.json"))
        else:
            continue
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate not in seen:
                result_files.append(candidate)
                seen.add(candidate)
    return result_files


def _iter_result_rows(payload: Mapping[str, Any], source_path: Path) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return serialized full-eval rows and aggregate records from known bundle shapes."""

    rows: List[Dict[str, Any]] = []
    aggregates: List[Dict[str, Any]] = []

    def add_result(result: Mapping[str, Any], *, company_id: str = "", company_label: str = "") -> None:
        experiment_id = str(result.get("id") or result.get("experiment_id") or "")
        full_eval = _safe_dict(result.get("full_eval"))
        aggregate = _safe_dict(full_eval.get("aggregate"))
        if aggregate:
            aggregates.append(
                {
                    "source_path": str(source_path),
                    "company_id": company_id,
                    "company_label": company_label,
                    "experiment_id": experiment_id,
                    **aggregate,
                }
            )
        for row in _safe_list(full_eval.get("per_question")):
            if not isinstance(row, Mapping):
                continue
            rows.append(
                {
                    "source_path": str(source_path),
                    "company_id": company_id,
                    "company_label": company_label,
                    "experiment_id": experiment_id,
                    **dict(row),
                }
            )

    if isinstance(payload.get("company_runs"), list):
        for bundle in payload.get("company_runs") or []:
            if not isinstance(bundle, Mapping):
                continue
            company_id = str(bundle.get("id") or bundle.get("company_run_id") or "")
            company_label = str(bundle.get("company_label") or bundle.get("label") or "")
            for result in _safe_list(bundle.get("results")):
                if isinstance(result, Mapping):
                    add_result(result, company_id=company_id, company_label=company_label)

    if isinstance(payload.get("results"), list):
        company_id = str(payload.get("company_id") or payload.get("company_run_id") or "")
        company_label = str(payload.get("company_label") or payload.get("label") or "")
        for result in payload.get("results") or []:
            if isinstance(result, Mapping):
                add_result(result, company_id=company_id, company_label=company_label)

    if isinstance(payload.get("full_eval"), Mapping):
        add_result(payload, company_id=str(payload.get("company_id") or ""), company_label=str(payload.get("company_label") or ""))

    return rows, aggregates


def load_result_rows(paths: Sequence[Path]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Path]]:
    result_files = find_result_files(paths)
    rows: List[Dict[str, Any]] = []
    aggregates: List[Dict[str, Any]] = []
    for result_file in result_files:
        payload = json.loads(result_file.read_text(encoding="utf-8"))
        file_rows, file_aggregates = _iter_result_rows(payload, result_file)
        rows.extend(file_rows)
        aggregates.extend(file_aggregates)
    return rows, aggregates, result_files


def _trace_entries(row: Mapping[str, Any]) -> List[Dict[str, Any]]:
    history = [dict(item) for item in _safe_list(row.get("retrieval_debug_trace_history")) if isinstance(item, Mapping)]
    if history:
        return history
    trace = row.get("retrieval_debug_trace")
    return [dict(trace)] if isinstance(trace, Mapping) and trace else []


def _summarize_trace(trace: Mapping[str, Any], *, trace_index: int) -> Dict[str, Any]:
    query_budget = _safe_dict(trace.get("query_budget"))
    search_summary = _safe_dict(trace.get("search_summary"))
    executed_query_signatures_by_source: Dict[str, List[str]] = defaultdict(list)
    executed_query_occurrences: List[Dict[str, Any]] = []
    source_trace = _safe_dict(query_budget.get("source"))
    active_task_id = str(source_trace.get("active_subtask_id") or "")
    active_task_operation = str(source_trace.get("active_subtask_operation") or "")
    if isinstance(trace.get("executed_queries"), list):
        for query in trace.get("executed_queries") or []:
            if not isinstance(query, Mapping):
                continue
            source = str(query.get("source") or "unknown")
            signature = _query_signature(query.get("executed_query") or query.get("base_query"))
            if signature:
                executed_query_signatures_by_source[source].append(signature)
                executed_query_occurrences.append(
                    {
                        "signature": signature,
                        "source": source,
                        "trace_index": trace_index,
                        "active_task_id": active_task_id,
                        "active_task_operation": active_task_operation,
                    }
                )
    if not search_summary and isinstance(trace.get("executed_queries"), list):
        by_source: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
        totals: Dict[str, float] = defaultdict(float)
        for query in trace.get("executed_queries") or []:
            if not isinstance(query, Mapping):
                continue
            source = str(query.get("source") or "unknown")
            telemetry = _safe_dict(query.get("search_telemetry"))
            usage = _safe_dict(telemetry.get("embedding_usage"))
            totals["executed_query_count"] += 1
            by_source[source]["executed_query_count"] += 1
            if telemetry.get("cache_hit"):
                totals["cache_hit_count"] += 1
                by_source[source]["cache_hit_count"] += 1
            if telemetry.get("vector_attempted"):
                totals["vector_attempted_count"] += 1
                by_source[source]["vector_attempted_count"] += 1
            for key in EMBEDDING_USAGE_KEYS:
                value = _as_float(usage.get(key))
                if value is not None:
                    totals[key] += value
                    by_source[source][key] += value
        search_summary = {**totals, "by_source": {key: dict(value) for key, value in by_source.items()}}

    selected = {
        "primary_selected_count": _as_int(_safe_dict(query_budget.get("primary")).get("selected_count")),
        "operand_focus_selected_count": _as_int(_safe_dict(query_budget.get("operand_focus")).get("selected_count")),
        "retry_selected_count": _as_int(_safe_dict(query_budget.get("retry")).get("selected_count")),
    }
    skipped_focus = bool(_safe_dict(query_budget.get("operand_focus")).get("skipped"))
    return {
        "search_summary": search_summary,
        "selected": selected,
        "operand_focus_skipped_count": 1 if skipped_focus else 0,
        "executed_query_signatures_by_source": {
            source: list(signatures) for source, signatures in executed_query_signatures_by_source.items()
        },
        "executed_query_occurrences": executed_query_occurrences,
    }


def audit_row(row: Mapping[str, Any]) -> Dict[str, Any]:
    traces = _trace_entries(row)
    selected = defaultdict(float)
    search_totals: Dict[str, float] = defaultdict(float)
    by_source: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    operand_focus_skipped_count = 0
    executed_query_signatures: List[str] = []
    executed_query_signatures_by_source: Dict[str, List[str]] = defaultdict(list)
    executed_query_occurrences: List[Dict[str, Any]] = []

    for trace_index, trace in enumerate(traces, start=1):
        summary = _summarize_trace(trace, trace_index=trace_index)
        for key, value in summary["selected"].items():
            selected[key] += value
        operand_focus_skipped_count += int(summary.get("operand_focus_skipped_count") or 0)
        search_summary = _safe_dict(summary.get("search_summary"))
        for key in ("executed_query_count", "cache_hit_count", "vector_attempted_count", *EMBEDDING_USAGE_KEYS):
            number = _as_float(search_summary.get(key))
            if number is not None:
                search_totals[key] += number
        for source, source_summary in _safe_dict(search_summary.get("by_source")).items():
            if not isinstance(source_summary, Mapping):
                continue
            for key in ("executed_query_count", "cache_hit_count", "vector_attempted_count", *EMBEDDING_USAGE_KEYS):
                number = _as_float(source_summary.get(key))
                if number is not None:
                    by_source[str(source)][key] += number
        for source, signatures in _safe_dict(summary.get("executed_query_signatures_by_source")).items():
            if not isinstance(signatures, list):
                continue
            clean_signatures = [str(item) for item in signatures if str(item)]
            executed_query_signatures.extend(clean_signatures)
            executed_query_signatures_by_source[str(source)].extend(clean_signatures)
        executed_query_occurrences.extend(
            dict(item)
            for item in _safe_list(summary.get("executed_query_occurrences"))
            if isinstance(item, Mapping)
        )

    unique_executed_query_count = len(set(executed_query_signatures))
    duplicate_executed_query_count = max(len(executed_query_signatures) - unique_executed_query_count, 0)
    for source, signatures in executed_query_signatures_by_source.items():
        unique_source_count = len(set(signatures))
        by_source[source]["unique_executed_query_count"] += unique_source_count
        by_source[source]["duplicate_executed_query_count"] += max(len(signatures) - unique_source_count, 0)
    duplicate_query_details = _duplicate_query_details(executed_query_occurrences)

    llm_usage: Dict[str, float] = defaultdict(float)
    _sum_mapping_values(llm_usage, _safe_dict(row.get("llm_usage")), LLM_USAGE_KEYS)
    embedding_usage: Dict[str, float] = defaultdict(float)
    _sum_mapping_values(embedding_usage, _safe_dict(row.get("embedding_usage")), EMBEDDING_USAGE_KEYS)

    audited = {
        "source_path": row.get("source_path") or "",
        "company_id": row.get("company_id") or "",
        "company_label": row.get("company_label") or "",
        "experiment_id": row.get("experiment_id") or "",
        "question_id": row.get("id") or row.get("question_id") or "",
        "latency_sec": _as_float(row.get("latency_sec")),
        "error": row.get("error") or "",
        "numeric_final_judgement": row.get("numeric_final_judgement"),
        "trace_count": len(traces),
        "operand_focus_skipped_count": operand_focus_skipped_count,
        "unique_executed_query_count": unique_executed_query_count,
        "duplicate_executed_query_count": duplicate_executed_query_count,
        "duplicate_query_details": duplicate_query_details,
        **{key: _as_float(row.get(key)) for key in QUALITY_KEYS},
        **dict(selected),
        **dict(search_totals),
        "by_source": {key: dict(value) for key, value in sorted(by_source.items())},
        "llm_usage": dict(llm_usage),
        "embedding_usage": dict(embedding_usage),
    }
    return audited


def _average(rows: Sequence[Mapping[str, Any]], key: str) -> Optional[float]:
    values = [_as_float(row.get(key)) for row in rows]
    clean = [value for value in values if value is not None]
    return float(mean(clean)) if clean else None


def build_audit(paths: Sequence[Path], *, top_n: int = 20) -> Dict[str, Any]:
    rows, aggregates, result_files = load_result_rows(paths)
    audited_rows = [audit_row(row) for row in rows]

    totals: Dict[str, float] = defaultdict(float)
    by_source: Dict[str, Dict[str, float]] = defaultdict(lambda: defaultdict(float))
    llm_usage: Dict[str, float] = defaultdict(float)
    embedding_usage: Dict[str, float] = defaultdict(float)

    for row in audited_rows:
        for key in (
            "trace_count",
            "primary_selected_count",
            "operand_focus_selected_count",
            "retry_selected_count",
            "operand_focus_skipped_count",
            "executed_query_count",
            "unique_executed_query_count",
            "duplicate_executed_query_count",
            "cache_hit_count",
            "vector_attempted_count",
            *EMBEDDING_USAGE_KEYS,
        ):
            totals[key] += _as_float(row.get(key)) or 0.0
        for source, source_summary in _safe_dict(row.get("by_source")).items():
            for key, value in source_summary.items():
                by_source[str(source)][key] += _as_float(value) or 0.0
        for key, value in _safe_dict(row.get("llm_usage")).items():
            llm_usage[key] += _as_float(value) or 0.0
        for key, value in _safe_dict(row.get("embedding_usage")).items():
            embedding_usage[key] += _as_float(value) or 0.0

    aggregate_runtime_cost = sum(
        _as_float(record.get("estimated_runtime_cost_usd")) or 0.0 for record in aggregates
    )
    aggregate_runtime_embedding_cost = sum(
        _as_float(record.get("estimated_runtime_embedding_cost_usd")) or 0.0 for record in aggregates
    )

    sorted_rows = sorted(
        audited_rows,
        key=lambda row: (
            -(_as_float(row.get("executed_query_count")) or 0.0),
            str(row.get("question_id") or ""),
        ),
    )
    return {
        "summary": {
            "result_file_count": len(result_files),
            "result_files": [str(path) for path in result_files],
            "question_count": len(audited_rows),
            "aggregate_record_count": len(aggregates),
            "estimated_runtime_cost_usd": aggregate_runtime_cost or None,
            "estimated_runtime_embedding_cost_usd": aggregate_runtime_embedding_cost or None,
            **{key: totals.get(key, 0.0) for key in sorted(totals)},
            "llm_usage": dict(sorted(llm_usage.items())),
            "embedding_usage": dict(sorted(embedding_usage.items())),
            "by_source": {key: dict(sorted(value.items())) for key, value in sorted(by_source.items())},
            **{f"avg_{key}": _average(audited_rows, key) for key in QUALITY_KEYS},
            "numeric_pass_count": sum(1 for row in audited_rows if row.get("numeric_final_judgement") == "PASS"),
            "error_count": sum(1 for row in audited_rows if row.get("error")),
        },
        "rows": audited_rows,
        "top_rows_by_executed_queries": sorted_rows[: max(top_n, 0)],
        "top_rows_by_duplicate_queries": sorted(
            audited_rows,
            key=lambda row: (
                -(_as_float(row.get("duplicate_executed_query_count")) or 0.0),
                -(_as_float(row.get("executed_query_count")) or 0.0),
                str(row.get("question_id") or ""),
            ),
        )[: max(top_n, 0)],
    }


def _format_number(value: Any, digits: int = 3) -> str:
    number = _as_float(value)
    if number is None:
        return ""
    if number.is_integer():
        return str(int(number))
    return f"{number:.{digits}f}"


def render_markdown(audit: Mapping[str, Any]) -> str:
    summary = _safe_dict(audit.get("summary"))
    rows = _safe_list(audit.get("top_rows_by_executed_queries"))
    duplicate_rows = _safe_list(audit.get("top_rows_by_duplicate_queries"))
    lines = [
        "# Benchmark Fan-out Cost Audit",
        "",
        "## Summary",
        "",
        f"- Result files: `{_format_number(summary.get('result_file_count'), 0)}`",
        f"- Questions: `{_format_number(summary.get('question_count'), 0)}`",
        f"- Retrieval traces: `{_format_number(summary.get('trace_count'), 0)}`",
        f"- Executed queries: `{_format_number(summary.get('executed_query_count'), 0)}`",
        f"- Unique executed queries: `{_format_number(summary.get('unique_executed_query_count'), 0)}`",
        f"- Duplicate executed queries: `{_format_number(summary.get('duplicate_executed_query_count'), 0)}`",
        f"- Query embedding API calls: `{_format_number(summary.get('query_embedding_api_calls'), 0)}`",
        f"- LLM API calls: `{_format_number(_safe_dict(summary.get('llm_usage')).get('api_calls'), 0)}`",
        f"- Estimated runtime cost USD: `{_format_number(summary.get('estimated_runtime_cost_usd'), 6)}`",
        f"- Estimated runtime embedding cost USD: `{_format_number(summary.get('estimated_runtime_embedding_cost_usd'), 6)}`",
        "",
        "## Retrieval By Source",
        "",
        "| Source | Executed queries | Unique queries | Duplicate queries | Cache hits | Vector attempts | Query embedding calls |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for source, values in _safe_dict(summary.get("by_source")).items():
        source_values = _safe_dict(values)
        lines.append(
            "| {source} | {executed} | {unique} | {duplicate} | {cache} | {vector} | {embed} |".format(
                source=source,
                executed=_format_number(source_values.get("executed_query_count"), 0),
                unique=_format_number(source_values.get("unique_executed_query_count"), 0),
                duplicate=_format_number(source_values.get("duplicate_executed_query_count"), 0),
                cache=_format_number(source_values.get("cache_hit_count"), 0),
                vector=_format_number(source_values.get("vector_attempted_count"), 0),
                embed=_format_number(source_values.get("query_embedding_api_calls"), 0),
            )
        )
    if not _safe_dict(summary.get("by_source")):
        lines.append("| n/a |  |  |  |  |  |  |")

    lines.extend(
        [
            "",
            "## Top Rows By Duplicate Executed Queries",
            "",
            "| Question | Company | Experiment | Executed | Unique | Duplicate | Top duplicate queries | Query embed | Faithfulness | Completeness | Error |",
            "| --- | --- | --- | ---: | ---: | ---: | --- | ---: | ---: | ---: | --- |",
        ]
    )
    for row in duplicate_rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| {qid} | {company} | {experiment} | {executed} | {unique} | {duplicate} | {details} | {embed} | {faith} | {complete} | {error} |".format(
                qid=row.get("question_id") or "",
                company=row.get("company_id") or row.get("company_label") or "",
                experiment=row.get("experiment_id") or "",
                executed=_format_number(row.get("executed_query_count"), 0),
                unique=_format_number(row.get("unique_executed_query_count"), 0),
                duplicate=_format_number(row.get("duplicate_executed_query_count"), 0),
                details=_format_duplicate_query_details(_safe_list(row.get("duplicate_query_details"))).replace(
                    "|",
                    "/",
                ),
                embed=_format_number(row.get("query_embedding_api_calls"), 0),
                faith=_format_number(row.get("faithfulness"), 3),
                complete=_format_number(row.get("completeness"), 3),
                error=str(row.get("error") or "").replace("|", "/"),
            )
        )
    if not duplicate_rows:
        lines.append("| n/a |  |  |  |  |  |  |  |  |  |  |")

    lines.extend(
        [
            "",
            "## Top Rows By Executed Queries",
            "",
            "| Question | Company | Experiment | Executed | Primary | Operand | Retry | Query embed | Faithfulness | Completeness | Numeric | Error |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- | --- |",
        ]
    )
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            "| {qid} | {company} | {experiment} | {executed} | {primary} | {operand} | {retry} | {embed} | {faith} | {complete} | {numeric} | {error} |".format(
                qid=row.get("question_id") or "",
                company=row.get("company_id") or row.get("company_label") or "",
                experiment=row.get("experiment_id") or "",
                executed=_format_number(row.get("executed_query_count"), 0),
                primary=_format_number(row.get("primary_selected_count"), 0),
                operand=_format_number(row.get("operand_focus_selected_count"), 0),
                retry=_format_number(row.get("retry_selected_count"), 0),
                embed=_format_number(row.get("query_embedding_api_calls"), 0),
                faith=_format_number(row.get("faithfulness"), 3),
                complete=_format_number(row.get("completeness"), 3),
                numeric=str(row.get("numeric_final_judgement") or ""),
                error=str(row.get("error") or "").replace("|", "/"),
            )
        )
    if not rows:
        lines.append("| n/a |  |  |  |  |  |  |  |  |  |  |  |")
    return "\n".join(lines) + "\n"


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="Result JSON files or directories to audit.")
    parser.add_argument("--output-json", type=Path, help="Optional path for machine-readable audit JSON.")
    parser.add_argument("--output-md", type=Path, help="Optional path for Markdown summary output.")
    parser.add_argument("--top", type=int, default=20, help="Number of highest-fanout rows to include in Markdown.")
    args = parser.parse_args(argv)

    audit = build_audit(args.paths, top_n=args.top)
    if not audit["summary"]["result_file_count"]:
        raise SystemExit("No results.json files found.")
    if not audit["summary"]["question_count"]:
        raise SystemExit("No full_eval.per_question rows found.")

    markdown = render_markdown(audit)
    if args.output_json:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(json.dumps(audit, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output_md:
        args.output_md.parent.mkdir(parents=True, exist_ok=True)
        args.output_md.write_text(markdown, encoding="utf-8")
    if not args.output_md:
        print(markdown, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
