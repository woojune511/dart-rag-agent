"""
Benchmark runner for chunking / retrieval / ingest trade-off experiments.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import csv
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent.financial_graph import DEFAULT_CONTEXT_BATCH_SIZE, DEFAULT_CONTEXT_MAX_WORKERS, FinancialAgent
from ops.evaluator import (
    EvalExample,
    RAGEvaluator,
    _compute_citation_coverage,
    _compute_retrieval_hit_at_k,
    _compute_section_match_rate,
)
from processing.financial_parser import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, FinancialParser
from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

logger = logging.getLogger(__name__)

RISK_CATEGORIES = {"risk", "risk_analysis"}
BUSINESS_CATEGORIES = {"business", "business_overview"}
MISSING_INFO_CATEGORIES = {"missing_information", "missing"}
MISSING_INFO_MARKERS = ("없", "찾지 못", "확인되지", "명시되지", "어렵")
RISK_FAILURE_MARKERS = ("찾지 못", "확인하기 어렵", "확인할 수 없", "명시되지")


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    merged = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def _slugify(value: str) -> str:
    lowered = "".join(ch.lower() if ch.isalnum() else "-" for ch in value)
    return "-".join(part for part in lowered.split("-") if part)


def _normalise_path(path_value: str | Path) -> Path:
    path = Path(path_value)
    if not path.is_absolute():
        path = (PROJECT_ROOT / path).resolve()
    return path


def _load_eval_dataset(dataset_path: Path) -> List[EvalExample]:
    data = _load_json(dataset_path)
    return [
        EvalExample(
            id=item["id"],
            question=item["question"],
            ground_truth=item["ground_truth"],
            company=item["company"],
            year=item["year"],
            section=item["section"],
            category=item.get("category"),
        )
        for item in data
    ]


def _build_single_company_eval_slice(examples: List[EvalExample], max_questions: int = 5) -> List[EvalExample]:
    buckets = {
        "numeric_fact": None,
        "risk_analysis": None,
        "business_overview": None,
        "r_and_d_investment": None,
        "missing_information": None,
    }

    for example in examples:
        question = example.question.lower()
        section = example.section.lower()
        category = (example.category or "").lower()

        if buckets["numeric_fact"] is None and (
            category == "numeric_fact"
            or any(term in question for term in ("매출", "영업이익", "부채", "수치", "금액"))
        ):
            buckets["numeric_fact"] = example
        elif buckets["risk_analysis"] is None and (
            category == "risk_analysis" or "리스크" in section or "위험" in question
        ):
            buckets["risk_analysis"] = example
        elif buckets["business_overview"] is None and (
            category == "business_overview" or "사업개요" in section or "사업" in question
        ):
            buckets["business_overview"] = example
        elif buckets["r_and_d_investment"] is None and (
            category == "r_and_d_investment"
            or "연구개발" in section
            or any(term in question for term in ("r&d", "연구개발", "투자"))
        ):
            buckets["r_and_d_investment"] = example
        elif buckets["missing_information"] is None and (
            category == "missing_information"
            or any(term in question for term in ("없", "확인되지", "공시 문서에서"))
        ):
            buckets["missing_information"] = example

    selected = [example for example in buckets.values() if example is not None]
    if len(selected) < max_questions:
        seen_ids = {example.id for example in selected}
        for example in examples:
            if example.id in seen_ids:
                continue
            selected.append(example)
            seen_ids.add(example.id)
            if len(selected) >= max_questions:
                break
    return selected[:max_questions]


def _estimate_cost_usd(ingest_metrics: Dict[str, Any], pricing: Dict[str, Any] | None) -> float | None:
    if not pricing:
        return None

    input_rate = float(pricing.get("input_per_million_tokens_usd", 0.0) or 0.0)
    output_rate = float(pricing.get("output_per_million_tokens_usd", 0.0) or 0.0)
    prompt_tokens = float(ingest_metrics.get("prompt_tokens", 0) or 0)
    output_tokens = float(ingest_metrics.get("output_tokens", 0) or 0)

    if input_rate == 0.0 and output_rate == 0.0:
        return None

    return (prompt_tokens / 1_000_000.0) * input_rate + (output_tokens / 1_000_000.0) * output_rate


def _serialise_eval_results(results: Iterable[Any]) -> List[Dict[str, Any]]:
    serialised: List[Dict[str, Any]] = []
    for result in results:
        serialised.append(
            {
                "id": result.id,
                "question": result.question,
                "faithfulness": result.faithfulness,
                "answer_relevancy": result.answer_relevancy,
                "context_recall": result.context_recall,
                "retrieval_hit_at_k": result.retrieval_hit_at_k,
                "section_match_rate": result.section_match_rate,
                "citation_coverage": result.citation_coverage,
                "retrieved_count": result.retrieved_count,
                "query_type": result.query_type,
                "latency_sec": result.latency_sec,
                "error": result.error,
            }
        )
    return serialised


def _run_smoke_queries(agent: FinancialAgent, queries: List[Any]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for item in _normalise_smoke_queries(queries):
        query = item["query"]
        started_at = time.perf_counter()
        error = None
        retrieved_docs = []
        citations = []
        answer = ""
        query_type = "unknown"
        try:
            result = agent.run(query)
            retrieved_docs = result.get("retrieved_docs", [])
            citations = result.get("citations", [])
            answer = result.get("answer", "") or ""
            query_type = result.get("query_type")
        except Exception as exc:
            error = str(exc)
            logger.error("Smoke query failed: %s", exc)
        elapsed_sec = time.perf_counter() - started_at
        rows.append(
            {
                "query": query,
                "category": item.get("category"),
                "expected_company": item.get("expected_company"),
                "expected_year": item.get("expected_year"),
                "latency_sec": elapsed_sec,
                "query_type": query_type,
                "retrieved_count": len(retrieved_docs),
                "citation_count": len(citations),
                "answer": answer,
                "answer_preview": answer[:240],
                "citations": citations,
                "retrieved_metadata": _extract_retrieved_metadata(retrieved_docs),
                "error": error,
            }
        )

    if not rows:
        return {"queries": [], "summary": {}}

    avg_latency = sum(row["latency_sec"] for row in rows) / len(rows)
    avg_retrieved = sum(row["retrieved_count"] for row in rows) / len(rows)
    avg_citations = sum(row["citation_count"] for row in rows) / len(rows)
    return {
        "queries": rows,
        "summary": {
            "count": len(rows),
            "avg_latency_sec": avg_latency,
            "avg_retrieved_count": avg_retrieved,
            "avg_citation_count": avg_citations,
        },
    }


def _run_screening_eval(agent: FinancialAgent, examples: List[EvalExample]) -> Dict[str, Any]:
    rows = []
    for example in examples:
        started_at = time.perf_counter()
        error = None
        answer = ""
        query_type = "unknown"
        retrieved_docs: List[Any] = []
        citations: List[str] = []
        try:
            result = agent.run(example.question)
            answer = result.get("answer", "")
            query_type = result.get("query_type", "unknown")
            retrieved_docs = result.get("retrieved_docs", [])
            citations = result.get("citations", [])
        except Exception as exc:
            error = str(exc)
            logger.error("[%s] screening run failed: %s", example.id, exc)

        rows.append(
            {
                "id": example.id,
                "question": example.question,
                "category": example.category,
                "company": example.company,
                "year": example.year,
                "section": example.section,
                "answer_preview": answer[:240],
                "retrieval_hit_at_k": _compute_retrieval_hit_at_k(example, retrieved_docs),
                "section_match_rate": _compute_section_match_rate(example, retrieved_docs),
                "citation_coverage": _compute_citation_coverage(example, citations),
                "retrieved_count": len(retrieved_docs),
                "query_type": query_type,
                "latency_sec": time.perf_counter() - started_at,
                "error": error,
            }
        )

    valid_rows = [row for row in rows if row["error"] is None]

    def _avg(key: str) -> float:
        return float(mean(row[key] for row in valid_rows)) if valid_rows else 0.0

    return {
        "question_count": len(rows),
        "aggregate": {
            "retrieval_hit_at_k": _avg("retrieval_hit_at_k"),
            "section_match_rate": _avg("section_match_rate"),
            "citation_coverage": _avg("citation_coverage"),
            "avg_latency": _avg("latency_sec"),
            "error_rate": (len(rows) - len(valid_rows)) / len(rows) if rows else 0.0,
        },
        "per_question": rows,
    }


def _contains_missing_language(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in MISSING_INFO_MARKERS)


def _looks_like_risk_failure(text: str) -> bool:
    lowered = (text or "").lower()
    return not lowered.strip() or any(marker in lowered for marker in RISK_FAILURE_MARKERS)


def _has_wrong_company_contamination(expected_company: Optional[str], metadata_rows: List[Dict[str, Any]]) -> bool:
    if not expected_company:
        return False
    expected = expected_company.lower()
    observed = {str(row.get("company", "")).lower() for row in metadata_rows if row.get("company")}
    return bool(observed) and any(company != expected for company in observed)


def _citations_match_expected(
    citations: List[str],
    expected_company: Optional[str],
    expected_year: Optional[int],
) -> bool:
    if not citations:
        return True
    citation_blob = " ".join(citations).lower()
    if expected_company and expected_company.lower() not in citation_blob:
        return False
    if expected_year and str(expected_year) not in citation_blob:
        return False
    return True


def _screen_failure_reasons(
    result: Dict[str, Any],
    baseline_aggregate: Dict[str, Any],
    screening_config: Dict[str, Any],
) -> List[str]:
    reasons: List[str] = []

    for row in result.get("smoke", {}).get("queries", []):
        category = (row.get("category") or "").lower()
        if row.get("error"):
            reasons.append(f"smoke query error: {row['query']}: {row['error']}")
        if category in RISK_CATEGORIES and _looks_like_risk_failure(row.get("answer", "")):
            reasons.append(f"risk smoke query failed: {row['query']}")
        if category in MISSING_INFO_CATEGORIES and not _contains_missing_language(row.get("answer", "")):
            reasons.append(f"missing-information smoke query hallucinated: {row['query']}")
        if _has_wrong_company_contamination(row.get("expected_company"), row.get("retrieved_metadata", [])):
            reasons.append(f"wrong-company contamination in smoke query: {row['query']}")
        if not _citations_match_expected(
            row.get("citations", []),
            row.get("expected_company"),
            row.get("expected_year"),
        ):
            reasons.append(f"citation mismatch in smoke query: {row['query']}")

    for row in result.get("screening_eval", {}).get("per_question", []):
        category = (row.get("category") or "").lower()
        if category in RISK_CATEGORIES | BUSINESS_CATEGORIES and float(row.get("retrieval_hit_at_k", 0.0)) == 0.0:
            reasons.append(f"retrieval_hit_at_k == 0 for {row['id']}")
        if row.get("error"):
            reasons.append(f"screening evaluation error for {row['id']}: {row['error']}")

    aggregate = result.get("screening_eval", {}).get("aggregate", {})
    retrieval_drop = float(baseline_aggregate.get("retrieval_hit_at_k", 0.0)) - float(
        aggregate.get("retrieval_hit_at_k", 0.0)
    )
    section_drop = float(baseline_aggregate.get("section_match_rate", 0.0)) - float(
        aggregate.get("section_match_rate", 0.0)
    )

    if retrieval_drop > float(screening_config.get("retrieval_hit_drop_threshold", 0.10)):
        reasons.append(f"retrieval_hit_at_k dropped by {retrieval_drop:.3f}")
    if section_drop > float(screening_config.get("section_match_drop_threshold", 0.15)):
        reasons.append(f"section_match_rate dropped by {section_drop:.3f}")

    return list(dict.fromkeys(reasons))


def _select_eval_examples(
    config: Dict[str, Any],
    report_metadata: Dict[str, Any],
) -> List[EvalExample]:
    dataset_path = config.get("eval_dataset_path")
    if not dataset_path:
        return []

    examples = _load_eval_dataset(_normalise_path(dataset_path))
    company = str(report_metadata.get("company", "")).lower()
    year = int(report_metadata.get("year", 0) or 0)

    filtered = [
        example
        for example in examples
        if (not company or example.company.lower() == company) and (not year or int(example.year) == year)
    ]

    eval_mode = config.get("eval_mode", "single_company_slice")
    eval_limit = int(config.get("eval_limit", 5) or 5)

    if eval_mode == "all_filtered":
        return filtered[:eval_limit] if eval_limit > 0 else filtered

    if eval_mode == "single_company_slice":
        return _build_single_company_eval_slice(filtered, max_questions=eval_limit)

    return filtered[:eval_limit] if eval_limit > 0 else filtered


def _build_plain_ingest_metrics(chunk_count: int, elapsed_sec: float) -> Dict[str, Any]:
    return {
        "mode": "plain",
        "chunks": chunk_count,
        "stored_parent_chunks": 0,
        "contextualized_chunks": 0,
        "api_calls": 0,
        "fallback_count": 0,
        "prompt_chars": 0,
        "response_chars": 0,
        "prompt_tokens": 0,
        "output_tokens": 0,
        "total_tokens": 0,
        "max_workers": 0,
        "batch_size": 0,
        "elapsed_sec": elapsed_sec,
    }


def _build_index_text(metadata: Dict[str, Any], content: str, context: Optional[str] = None) -> str:
    company = metadata.get("company", "?")
    year = metadata.get("year", "?")
    report_type = metadata.get("report_type", "?")
    section = metadata.get("section", "?")
    section_path = metadata.get("section_path", section)
    block_type = "table" if metadata.get("block_type") == "table" else "paragraph"
    lines = [
        f"{company} {year} {report_type}",
        f"섹션: {section_path}",
        f"분류: {section} / {block_type}",
    ]
    if context and context.strip():
        lines.insert(0, context.strip())
    return "\n".join(lines) + f"\n\n{content}"


def _fallback_context(metadata: Dict[str, Any]) -> str:
    company = metadata.get("company", "?")
    year = metadata.get("year", "?")
    section_path = metadata.get("section_path", metadata.get("section", "?"))
    block_type = "표" if metadata.get("block_type") == "table" else "문단"
    return f"{company} {year} 사업보고서 / {section_path} / {block_type}"


def _build_context_prompt(text: str, metadata: Dict[str, Any]) -> str:
    company = metadata.get("company", "?")
    year = metadata.get("year", "?")
    section_path = metadata.get("section_path", metadata.get("section", "?"))
    block_type = "표" if metadata.get("block_type") == "table" else "문단"
    preview = " ".join((text or "")[:400].split())
    return (
        f"다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션에서 발췌한 {block_type}입니다.\n"
        f"이 내용이 문서 전체 맥락에서 어떤 역할을 하는지 한 문장, 50자 이내로 설명하세요.\n\n"
        f"내용:\n{preview}"
    )


def _build_parent_context_prompt(text: str, metadata: Dict[str, Any]) -> str:
    company = metadata.get("company", "?")
    year = metadata.get("year", "?")
    section_path = metadata.get("section_path", metadata.get("section", "?"))
    preview = " ".join((text or "")[:800].split())
    return (
        f"다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션 전체입니다.\n"
        f"이 섹션이 문서 전체에서 다루는 핵심 내용을 한 문장, 60자 이내로 요약하세요.\n\n"
        f"섹션 내용:\n{preview}"
    )


def _should_contextualize_chunk(
    chunk: Any,
    short_text_threshold: int = 900,
    targeted_sections: Optional[List[str]] = None,
) -> bool:
    metadata = chunk.metadata or {}
    if metadata.get("block_type") == "table":
        return True
    if len((chunk.content or "").strip()) <= short_text_threshold:
        return True

    targets = targeted_sections or ["리스크", "연구개발", "매출현황", "사업개요", "경영진단"]
    section = str(metadata.get("section", "")).strip()
    section_path = str(metadata.get("section_path", section)).strip()
    return any(target and (target == section or target in section_path) for target in targets)


def _generate_context_map(
    agent: FinancialAgent,
    items: List[Dict[str, Any]],
    *,
    prompt_builder,
    fallback_builder,
    on_progress=None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
    log_label: str = "benchmark_context",
) -> tuple[Dict[Any, str], Dict[str, Any]]:
    total = len(items)
    if total == 0:
        return {}, {
            "api_calls": 0,
            "fallback_count": 0,
            "prompt_chars": 0,
            "response_chars": 0,
            "prompt_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
            "max_workers": 0,
            "batch_size": 0,
        }

    workers = agent._resolve_context_workers(max_workers, total)
    request_batch_size = agent._resolve_context_batch_size(batch_size, workers)
    contexts: Dict[Any, str] = {}
    prompt_chars = 0
    response_chars = 0
    prompt_tokens = 0
    output_tokens = 0
    total_tokens = 0
    fallback_count = 0
    completed_count = 0

    logger.info(
        "[%s] generating %s contexts with max_workers=%s batch_size=%s",
        log_label,
        total,
        workers,
        request_batch_size,
    )

    for start in range(0, total, request_batch_size):
        batch_items = items[start : start + request_batch_size]
        prompts = [prompt_builder(item) for item in batch_items]
        prompt_chars += sum(len(prompt) for prompt in prompts)
        try:
            responses = agent.llm.batch(
                prompts,
                config={"max_concurrency": workers},
                return_exceptions=True,
            )
        except Exception as exc:
            logger.warning("Context batch generation failed, falling back to per-item mode: %s", exc)
            responses = [exc] * len(batch_items)

        for item, response in zip(batch_items, responses):
            key = item["key"]
            if isinstance(response, Exception):
                contexts[key] = fallback_builder(item)
                fallback_count += 1
            else:
                content = getattr(response, "content", "") or ""
                contexts[key] = content.strip() or fallback_builder(item)
                usage = getattr(response, "usage_metadata", None) or {}
                response_metadata = getattr(response, "response_metadata", None) or {}
                token_usage = response_metadata.get("token_usage") or {}
                prompt_tokens += int(
                    usage.get("input_tokens")
                    or usage.get("prompt_token_count")
                    or token_usage.get("input_tokens")
                    or token_usage.get("prompt_token_count")
                    or 0
                )
                output_tokens += int(
                    usage.get("output_tokens")
                    or usage.get("candidates_token_count")
                    or token_usage.get("output_tokens")
                    or token_usage.get("candidates_token_count")
                    or 0
                )
                total_tokens += int(
                    usage.get("total_tokens")
                    or usage.get("total_token_count")
                    or token_usage.get("total_tokens")
                    or token_usage.get("total_token_count")
                    or 0
                )
            response_chars += len(contexts[key])
            completed_count += 1
            if on_progress:
                on_progress(completed_count, total)

    return contexts, {
        "api_calls": total,
        "fallback_count": fallback_count,
        "prompt_chars": prompt_chars,
        "response_chars": response_chars,
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "max_workers": workers,
        "batch_size": request_batch_size,
    }


def _store_parent_chunks(agent: FinancialAgent, chunks: List[Any]) -> Dict[str, str]:
    parents = FinancialParser.build_parents(chunks)
    agent.vsm.add_parents(parents)
    return parents


def _benchmark_parent_only_ingest(
    agent: FinancialAgent,
    chunks: List[Any],
    *,
    on_progress=None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    parents = _store_parent_chunks(agent, chunks)
    grouped: Dict[str, List[int]] = {}
    parent_metadata: Dict[str, Dict[str, Any]] = {}
    for idx, chunk in enumerate(chunks):
        parent_id = str((chunk.metadata or {}).get("parent_id") or f"chunk-{idx}")
        grouped.setdefault(parent_id, []).append(idx)
        parent_metadata.setdefault(parent_id, chunk.metadata)

    items = [
        {
            "key": parent_id,
            "text": parents.get(parent_id) or "\n\n".join(chunks[i].content for i in indexes),
            "metadata": parent_metadata[parent_id],
        }
        for parent_id, indexes in grouped.items()
    ]
    contexts, metrics = _generate_context_map(
        agent,
        items,
        prompt_builder=lambda item: _build_parent_context_prompt(item["text"], item["metadata"]),
        fallback_builder=lambda item: _fallback_context(item["metadata"]),
        on_progress=on_progress,
        max_workers=max_workers,
        batch_size=batch_size,
        log_label="benchmark_contextual_parent_only",
    )

    texts = []
    for idx, chunk in enumerate(chunks):
        parent_id = str((chunk.metadata or {}).get("parent_id") or f"chunk-{idx}")
        texts.append(_build_index_text(chunk.metadata, chunk.content, contexts.get(parent_id)))
    agent.vsm.add_documents(texts, [chunk.metadata for chunk in chunks])

    return {
        "mode": "contextual_parent_only",
        "chunks": len(chunks),
        "stored_parent_chunks": len(parents),
        "contextualized_chunks": len(items),
        **metrics,
        "elapsed_sec": time.perf_counter() - started_at,
    }


def _benchmark_selective_ingest(
    agent: FinancialAgent,
    chunks: List[Any],
    *,
    on_progress=None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
    short_text_threshold: int = 900,
    targeted_sections: Optional[List[str]] = None,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    parents = _store_parent_chunks(agent, chunks)
    selected_indexes = [
        idx
        for idx, chunk in enumerate(chunks)
        if _should_contextualize_chunk(
            chunk,
            short_text_threshold=short_text_threshold,
            targeted_sections=targeted_sections,
        )
    ]
    items = [
        {"key": idx, "text": chunks[idx].content, "metadata": chunks[idx].metadata}
        for idx in selected_indexes
    ]
    contexts, metrics = _generate_context_map(
        agent,
        items,
        prompt_builder=lambda item: _build_context_prompt(item["text"], item["metadata"]),
        fallback_builder=lambda item: _fallback_context(item["metadata"]),
        on_progress=on_progress,
        max_workers=max_workers,
        batch_size=batch_size,
        log_label="benchmark_contextual_selective",
    )

    texts = [
        _build_index_text(chunk.metadata, chunk.content, contexts.get(idx))
        for idx, chunk in enumerate(chunks)
    ]
    agent.vsm.add_documents(texts, [chunk.metadata for chunk in chunks])

    return {
        "mode": "contextual_selective",
        "chunks": len(chunks),
        "stored_parent_chunks": len(parents),
        "contextualized_chunks": len(items),
        **metrics,
        "elapsed_sec": time.perf_counter() - started_at,
    }


def _normalise_smoke_queries(raw_queries: List[Any]) -> List[Dict[str, Any]]:
    normalised = []
    for item in raw_queries:
        if isinstance(item, str):
            normalised.append({"query": item})
        elif isinstance(item, dict):
            normalised.append(dict(item))
    return normalised


def _extract_retrieved_metadata(retrieved_docs: List[Any]) -> List[Dict[str, Any]]:
    rows = []
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        rows.append(
            {
                "company": metadata.get("company"),
                "year": metadata.get("year"),
                "section": metadata.get("section"),
                "section_path": metadata.get("section_path"),
            }
        )
    return rows


def _render_summary_markdown(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        "| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Chunks | Contextualized | API Calls | Prompt Tokens | Output Tokens | Est. Cost (USD) | Screen Hit@k | Screen Section | Screen Citation | Full Faithfulness | Full Relevancy | Full Recall |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        config = result["config"]
        ingest = result["ingest"]
        screen = result.get("screening_eval", {}).get("aggregate", {})
        full = result.get("full_eval", {}).get("aggregate", {})
        estimated_cost = result.get("estimated_ingest_cost_usd")
        lines.append(
            "| {id} | {chunk} | {overlap} | {mode} | {passed} | {parse:.3f} | {ingest_sec:.3f} | {chunks} | {contextualized} | {api_calls} | {prompt_tokens} | {output_tokens} | {cost} | {hit:.3f} | {section:.3f} | {citation:.3f} | {faith} | {rel} | {recall} |".format(
                id=result["id"],
                chunk=config.get("chunk_size"),
                overlap=config.get("chunk_overlap"),
                mode=config.get("ingest_mode"),
                passed="yes" if result.get("screen_pass") else "no",
                parse=result["parse"]["elapsed_sec"],
                ingest_sec=ingest.get("elapsed_sec", 0.0),
                chunks=result["parse"]["chunk_count"],
                contextualized=ingest.get("contextualized_chunks", 0),
                api_calls=ingest.get("api_calls", 0),
                prompt_tokens=ingest.get("prompt_tokens", 0),
                output_tokens=ingest.get("output_tokens", 0),
                cost="-" if estimated_cost is None else f"{estimated_cost:.6f}",
                faith="-" if not full else f"{full.get('faithfulness', 0.0):.3f}",
                rel="-" if not full else f"{full.get('answer_relevancy', 0.0):.3f}",
                recall="-" if not full else f"{full.get('context_recall', 0.0):.3f}",
                hit=screen.get("retrieval_hit_at_k", 0.0),
                section=screen.get("section_match_rate", 0.0),
                citation=screen.get("citation_coverage", 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Reading Guide",
            "",
            "- `Screen Pass` means the run cleared the strict quality floor before full evaluation.",
            "- Screening metrics are the cheap retrieval-facing checks used to filter weak candidates early.",
            "- Full metrics are only populated for shortlisted candidates that proceed to stage 2.",
            "- The best default is the best point on the quality / speed / cost frontier, not the single highest metric.",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_summary_csv(path: Path, results: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "id",
        "chunk_size",
        "chunk_overlap",
        "ingest_mode",
        "k",
        "max_workers",
        "batch_size",
        "parse_elapsed_sec",
        "chunk_count",
        "ingest_elapsed_sec",
        "contextualized_chunks",
        "api_calls",
        "prompt_tokens",
        "output_tokens",
        "estimated_ingest_cost_usd",
        "smoke_avg_latency_sec",
        "screen_retrieval_hit_at_k",
        "screen_section_match_rate",
        "screen_citation_coverage",
        "screen_pass",
        "screen_failure_reasons",
        "full_faithfulness",
        "full_answer_relevancy",
        "full_context_recall",
        "full_retrieval_hit_at_k",
        "full_section_match_rate",
        "full_citation_coverage",
        "full_avg_score",
        "full_avg_latency",
    ]
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            config = result["config"]
            ingest = result["ingest"]
            smoke = result.get("smoke", {}).get("summary", {})
            screen = result.get("screening_eval", {}).get("aggregate", {})
            full = result.get("full_eval", {}).get("aggregate", {})
            writer.writerow(
                {
                    "id": result["id"],
                    "chunk_size": config.get("chunk_size"),
                    "chunk_overlap": config.get("chunk_overlap"),
                    "ingest_mode": config.get("ingest_mode"),
                    "k": config.get("k"),
                    "max_workers": config.get("max_workers"),
                    "batch_size": config.get("batch_size"),
                    "parse_elapsed_sec": result["parse"]["elapsed_sec"],
                    "chunk_count": result["parse"]["chunk_count"],
                    "ingest_elapsed_sec": ingest.get("elapsed_sec", 0.0),
                    "contextualized_chunks": ingest.get("contextualized_chunks", 0),
                    "api_calls": ingest.get("api_calls", 0),
                    "prompt_tokens": ingest.get("prompt_tokens", 0),
                    "output_tokens": ingest.get("output_tokens", 0),
                    "estimated_ingest_cost_usd": result.get("estimated_ingest_cost_usd"),
                    "smoke_avg_latency_sec": smoke.get("avg_latency_sec"),
                    "screen_retrieval_hit_at_k": screen.get("retrieval_hit_at_k"),
                    "screen_section_match_rate": screen.get("section_match_rate"),
                    "screen_citation_coverage": screen.get("citation_coverage"),
                    "screen_pass": result.get("screen_pass"),
                    "screen_failure_reasons": " | ".join(result.get("screen_failure_reasons", [])),
                    "full_faithfulness": full.get("faithfulness"),
                    "full_answer_relevancy": full.get("answer_relevancy"),
                    "full_context_recall": full.get("context_recall"),
                    "full_retrieval_hit_at_k": full.get("retrieval_hit_at_k"),
                    "full_section_match_rate": full.get("section_match_rate"),
                    "full_citation_coverage": full.get("citation_coverage"),
                    "full_avg_score": full.get("avg_score"),
                    "full_avg_latency": full.get("avg_latency"),
                }
            )


def _run_ingest(agent: FinancialAgent, chunks: List[Any], config: Dict[str, Any]) -> Dict[str, Any]:
    ingest_mode = str(config.get("ingest_mode", "contextual_all"))
    max_workers = int(config.get("max_workers", DEFAULT_CONTEXT_MAX_WORKERS))
    batch_size = int(config.get("batch_size", DEFAULT_CONTEXT_BATCH_SIZE))
    if ingest_mode == "plain":
        started_at = time.perf_counter()
        agent.ingest(chunks)
        return _build_plain_ingest_metrics(len(chunks), time.perf_counter() - started_at)
    if ingest_mode in {"contextual", "contextual_all"}:
        metrics = agent.benchmark_contextual_ingest(
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
        )
        metrics["mode"] = "contextual_all"
        metrics.setdefault("contextualized_chunks", len(chunks))
        return metrics
    if ingest_mode == "contextual_parent_only":
        return _benchmark_parent_only_ingest(
            agent,
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
        )
    if ingest_mode == "contextual_selective":
        return _benchmark_selective_ingest(
            agent,
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
            short_text_threshold=int(config.get("selective_short_text_threshold", 900)),
            targeted_sections=list(config.get("selective_sections", [])),
        )
    raise ValueError(f"Unsupported ingest_mode: {ingest_mode}")


def run_screening_experiment(config: Dict[str, Any], output_root: Path) -> Dict[str, Any]:
    experiment_id = config["id"]
    report_path = _normalise_path(config["report_path"])
    if not report_path.exists():
        raise FileNotFoundError(f"report_path not found: {report_path}")

    metadata = dict(config["metadata"])
    persist_dir = output_root / "stores" / _slugify(experiment_id)
    if config.get("reset_store", True) and persist_dir.exists():
        shutil.rmtree(persist_dir)

    collection_name = config.get("collection_name") or f"{DEFAULT_COLLECTION_NAME}_{_slugify(experiment_id)}"
    parser = FinancialParser(
        chunk_size=int(config.get("chunk_size", DEFAULT_CHUNK_SIZE)),
        chunk_overlap=int(config.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)),
    )
    parse_started = time.perf_counter()
    chunks = parser.process_document(str(report_path), metadata)
    parse_elapsed = time.perf_counter() - parse_started

    vsm = VectorStoreManager(
        persist_directory=str(persist_dir),
        collection_name=collection_name,
    )
    agent = FinancialAgent(vsm, k=int(config.get("k", 8)))
    ingest_metrics = _run_ingest(agent, chunks, config)
    smoke = _run_smoke_queries(agent, list(config.get("smoke_queries", [])))
    screening_examples = _select_eval_examples(config, metadata)
    screening_eval = _run_screening_eval(agent, screening_examples) if screening_examples else {}
    estimated_cost = _estimate_cost_usd(ingest_metrics, config.get("pricing"))

    return {
        "id": experiment_id,
        "config": {
            "chunk_size": config.get("chunk_size"),
            "chunk_overlap": config.get("chunk_overlap"),
            "ingest_mode": config.get("ingest_mode"),
            "k": config.get("k", 8),
            "max_workers": config.get("max_workers"),
            "batch_size": config.get("batch_size"),
            "collection_name": collection_name,
            "selective_short_text_threshold": config.get("selective_short_text_threshold"),
            "selective_sections": config.get("selective_sections", []),
        },
        "report_path": str(report_path),
        "metadata": metadata,
        "store": {
            "persist_directory": str(persist_dir),
            "collection_name": collection_name,
        },
        "parse": {
            "elapsed_sec": parse_elapsed,
            "chunk_count": len(chunks),
        },
        "ingest": ingest_metrics,
        "estimated_ingest_cost_usd": estimated_cost,
        "smoke": smoke,
        "screening_eval": screening_eval,
        "screen_pass": False,
        "screen_failure_reasons": [],
        "full_eval": {},
    }


def _select_full_eval_candidates(
    results: List[Dict[str, Any]],
    screening_config: Dict[str, Any],
) -> List[str]:
    selected: List[str] = []
    baseline_id = screening_config.get("baseline_experiment_id")
    if baseline_id:
        selected.append(baseline_id)

    for experiment_id in screening_config.get("always_include_full_eval_ids", []):
        if experiment_id not in selected:
            selected.append(experiment_id)

    passers = [result for result in results if result.get("screen_pass") and result["id"] not in selected]
    passers.sort(
        key=lambda result: (
            result.get("estimated_ingest_cost_usd")
            if result.get("estimated_ingest_cost_usd") is not None
            else float("inf"),
            result["ingest"].get("api_calls", 0),
            result["ingest"].get("elapsed_sec", 0.0),
        )
    )

    max_selected = int(screening_config.get("max_full_eval_candidates", 3) or 3)
    for result in passers:
        if len(selected) >= max_selected:
            break
        selected.append(result["id"])
    return selected


def _run_screening_experiments(
    merged_experiments: List[Dict[str, Any]],
    output_dir: Path,
    screening_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not merged_experiments:
        return []

    parallel_experiments = int(screening_config.get("parallel_experiments", 2) or 2)
    max_workers = max(1, min(parallel_experiments, len(merged_experiments)))

    if max_workers == 1:
        results_by_id: Dict[str, Dict[str, Any]] = {}
        for merged in merged_experiments:
            logger.info("Running screening benchmark: %s", merged["id"])
            results_by_id[merged["id"]] = run_screening_experiment(merged, output_dir)
        return [results_by_id[merged["id"]] for merged in merged_experiments]

    logger.info("Running screening benchmarks with parallel_experiments=%s", max_workers)
    results_by_id: Dict[str, Dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for merged in merged_experiments:
            logger.info("Queueing screening benchmark: %s", merged["id"])
            future = executor.submit(run_screening_experiment, merged, output_dir)
            futures[future] = merged["id"]

        for future in concurrent.futures.as_completed(futures):
            experiment_id = futures[future]
            try:
                results_by_id[experiment_id] = future.result()
                logger.info("Completed screening benchmark: %s", experiment_id)
            except Exception:
                logger.exception("Screening benchmark failed: %s", experiment_id)
                raise

    return [results_by_id[merged["id"]] for merged in merged_experiments]


def _run_full_evaluation(result: Dict[str, Any], merged_config: Dict[str, Any], full_eval_config: Dict[str, Any]) -> Dict[str, Any]:
    store_info = result["store"]
    vsm = VectorStoreManager(
        persist_directory=store_info["persist_directory"],
        collection_name=store_info["collection_name"],
    )
    agent = FinancialAgent(vsm, k=int(merged_config.get("k", 8)))
    evaluator = RAGEvaluator(
        agent,
        dataset_path=str(_normalise_path(merged_config["eval_dataset_path"])),
        experiment_name=merged_config.get("mlflow_experiment_name", "dart_rag_benchmark"),
    )

    full_config = dict(merged_config)
    full_config["eval_mode"] = full_eval_config.get("eval_mode", merged_config.get("eval_mode"))
    full_config["eval_limit"] = full_eval_config.get("eval_limit", merged_config.get("eval_limit"))
    examples = _select_eval_examples(full_config, result["metadata"])
    if not examples:
        return {}

    eval_results = evaluator.run(
        examples=examples,
        run_name=result["id"],
        params={
            "chunk_size": merged_config.get("chunk_size"),
            "chunk_overlap": merged_config.get("chunk_overlap"),
            "ingest_mode": merged_config.get("ingest_mode"),
            "k": merged_config.get("k", 8),
            "max_workers": merged_config.get("max_workers"),
            "batch_size": merged_config.get("batch_size"),
            "collection_name": store_info["collection_name"],
            "stage": "full_evaluation",
        },
    )
    return {
        "question_count": len(examples),
        "aggregate": eval_results["aggregate"],
        "per_question": _serialise_eval_results(eval_results["per_question"]),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run low-cost retrieval benchmark experiments.")
    parser.add_argument(
        "--config",
        default=str(PROJECT_ROOT / "benchmarks" / "experiment_matrix.sample.json"),
        help="Path to the benchmark matrix JSON file.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(PROJECT_ROOT / "benchmarks" / "results" / "latest"),
        help="Directory where JSON/CSV/Markdown summaries will be written.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config_path = _normalise_path(args.config)
    output_dir = _normalise_path(args.output_dir)
    matrix = _load_json(config_path)
    defaults = matrix.get("defaults", {})
    experiments = matrix.get("experiments", [])
    screening_config = matrix.get("screening", {})
    full_eval_config = matrix.get("full_evaluation", {})
    if not experiments:
        raise ValueError("No experiments found in benchmark config.")

    merged_experiments: List[Dict[str, Any]] = []
    merged_by_id: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        merged = _deep_merge(defaults, experiment)
        if "id" not in merged:
            raise ValueError("Each experiment must include an id.")
        merged_experiments.append(merged)
        merged_by_id[merged["id"]] = merged

    results = _run_screening_experiments(merged_experiments, output_dir, screening_config)

    baseline_id = screening_config.get("baseline_experiment_id")
    baseline_result = next((result for result in results if result["id"] == baseline_id), None)
    if baseline_id and baseline_result is None:
        raise ValueError(f"baseline_experiment_id not found: {baseline_id}")
    baseline_aggregate = baseline_result.get("screening_eval", {}).get("aggregate", {}) if baseline_result else {}

    for result in results:
        reasons = _screen_failure_reasons(result, baseline_aggregate, screening_config)
        result["screen_failure_reasons"] = reasons
        result["screen_pass"] = len(reasons) == 0

    selected_ids: List[str] = []
    if full_eval_config.get("enabled", True):
        selected_ids = _select_full_eval_candidates(results, screening_config)
        for experiment_id in selected_ids:
            logger.info("Running full evaluation: %s", experiment_id)
            result = next(result for result in results if result["id"] == experiment_id)
            result["full_eval"] = _run_full_evaluation(result, merged_by_id[experiment_id], full_eval_config)

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "results.json",
        {
            "config_path": str(config_path),
            "screening": screening_config,
            "full_evaluation": full_eval_config,
            "full_eval_candidates": selected_ids,
            "results": results,
        },
    )
    _write_summary_csv(output_dir / "summary.csv", results)
    (output_dir / "summary.md").write_text(_render_summary_markdown(results), encoding="utf-8")
    logger.info("Wrote benchmark outputs to %s", output_dir)


if __name__ == "__main__":
    main()
