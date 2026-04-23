"""
Benchmark runner for chunking / retrieval / ingest trade-off experiments.
"""

from __future__ import annotations

import argparse
from collections import Counter
import concurrent.futures
import csv
import hashlib
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
    load_eval_examples_from_path,
)
from processing.financial_parser import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, FinancialParser
from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

logger = logging.getLogger(__name__)

RISK_CATEGORIES = {"risk", "risk_analysis"}
BUSINESS_CATEGORIES = {"business", "business_overview"}
NUMERIC_CATEGORIES = {"numeric", "numeric_fact"}
MISSING_INFO_CATEGORIES = {"missing_information", "missing"}
DEFAULT_NUMERIC_SECTION_ALIASES = ["매출현황", "재무제표", "요약재무", "연결재무제표", "연결재무제표 주석"]
DEFAULT_PARENT_HYBRID_SECTIONS = ["매출현황", "재무제표", "연구개발", "리스크", "사업개요"]
DEFAULT_SELECTIVE_V2_SECTIONS = ["사업개요", "위험관리 및 파생거래", "매출 및 수주상황", "연구개발"]
MISSING_INFO_MARKERS = (
    "없",
    "찾지 못",
    "근거를 찾지 못",
    "답할 수 있는 근거를 찾지 못",
    "확인되지",
    "확인할 수 없",
    "명시되지",
    "어렵",
)
ABSTENTION_MARKERS = (
    "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다",
    "질문에 직접 답할 수 있는 근거를 찾지 못했습니다",
    "공시 문서에 정보가 없거나",
    "현재 검색 결과만으로는 확인하기 어렵습니다",
)
RISK_FAILURE_MARKERS = ("찾지 못", "확인하기 어렵", "확인할 수 없", "명시되지")
BENCHMARK_CACHE_SCHEMA_VERSION = 1


def _load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            chunk = file.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


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


def _is_path_like_key(key: str) -> bool:
    lowered = key.lower()
    return lowered.endswith("_path") or "directory" in lowered


def _sanitize_settings(value: Any, key: str = "") -> Any:
    if isinstance(value, dict):
        sanitised: Dict[str, Any] = {}
        for child_key, child_value in value.items():
            if _is_path_like_key(child_key):
                continue
            sanitised[child_key] = _sanitize_settings(child_value, child_key)
        return sanitised
    if isinstance(value, list):
        return [_sanitize_settings(item, key) for item in value]
    return value


def _build_recorded_settings(
    config: Dict[str, Any],
    screening_config: Dict[str, Any],
    full_eval_config: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "experiment": _sanitize_settings(config),
        "screening": _sanitize_settings(screening_config),
        "full_evaluation": _sanitize_settings(full_eval_config),
    }


def _build_cache_signature(config: Dict[str, Any]) -> Dict[str, Any]:
    parser_path = PROJECT_ROOT / "src" / "processing" / "financial_parser.py"
    runner_path = PROJECT_ROOT / "src" / "ops" / "benchmark_runner.py"
    metadata = config.get("metadata", {})
    return {
        "schema_version": BENCHMARK_CACHE_SCHEMA_VERSION,
        "company": metadata.get("company"),
        "year": metadata.get("year"),
        "report_type": metadata.get("report_type"),
        "rcept_no": metadata.get("rcept_no"),
        "chunk_size": config.get("chunk_size"),
        "chunk_overlap": config.get("chunk_overlap"),
        "ingest_mode": config.get("ingest_mode"),
        "k": config.get("k", 8),
        "parser_signature": _hash_file(parser_path),
        "runner_signature": _hash_file(runner_path),
        "parent_hybrid_short_text_threshold": config.get("parent_hybrid_short_text_threshold"),
        "parent_hybrid_sections": list(config.get("parent_hybrid_sections", [])),
        "selective_short_text_threshold": config.get("selective_short_text_threshold"),
        "selective_sections": list(config.get("selective_sections", [])),
        "selective_v2_short_text_threshold": config.get("selective_v2_short_text_threshold"),
        "selective_v2_short_table_threshold": config.get("selective_v2_short_table_threshold"),
        "selective_v2_sections": list(config.get("selective_v2_sections", [])),
        "use_zero_cost_prefix": bool(config.get("use_zero_cost_prefix", False)),
    }


def _cache_meta_path(persist_dir: Path) -> Path:
    return persist_dir / "benchmark_cache_meta.json"


def _context_cache_path(output_root: Path, experiment_id: str) -> Path:
    return output_root / "context_cache" / f"{_slugify(experiment_id)}.json"


def _load_cache_meta(persist_dir: Path) -> Dict[str, Any]:
    path = _cache_meta_path(persist_dir)
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception:
        logger.warning("Failed to load benchmark cache metadata: %s", path)
        return {}


def _write_cache_meta(persist_dir: Path, payload: Dict[str, Any]) -> None:
    _write_json(_cache_meta_path(persist_dir), payload)


def _load_context_cache(output_root: Path, experiment_id: str) -> Dict[str, Any]:
    path = _context_cache_path(output_root, experiment_id)
    if not path.exists():
        return {}
    try:
        return _load_json(path)
    except Exception:
        logger.warning("Failed to load benchmark context cache: %s", path)
        return {}


def _write_context_cache(output_root: Path, experiment_id: str, payload: Dict[str, Any]) -> None:
    _write_json(_context_cache_path(output_root, experiment_id), payload)


def _cache_meta_matches(cache_meta: Dict[str, Any], signature: Dict[str, Any]) -> bool:
    return bool(cache_meta) and cache_meta.get("signature") == signature


def _build_cache_hit_ingest_metrics(source_metrics: Dict[str, Any]) -> Dict[str, Any]:
    metrics = dict(source_metrics or {})
    metrics["cache_hit"] = True
    metrics["elapsed_sec"] = 0.0
    metrics["api_calls"] = 0
    metrics["prompt_tokens"] = 0
    metrics["output_tokens"] = 0
    metrics["total_tokens"] = 0
    metrics["fallback_count"] = 0
    metrics["cached_source_api_calls"] = int((source_metrics or {}).get("api_calls", 0) or 0)
    metrics["cached_source_prompt_tokens"] = int((source_metrics or {}).get("prompt_tokens", 0) or 0)
    metrics["cached_source_output_tokens"] = int((source_metrics or {}).get("output_tokens", 0) or 0)
    return metrics


def _build_context_cache_restore_metrics(source_metrics: Dict[str, Any], elapsed_sec: float) -> Dict[str, Any]:
    metrics = dict(source_metrics or {})
    metrics["cache_hit"] = True
    metrics["api_calls"] = 0
    metrics["prompt_tokens"] = 0
    metrics["output_tokens"] = 0
    metrics["total_tokens"] = 0
    metrics["fallback_count"] = 0
    metrics["elapsed_sec"] = elapsed_sec
    metrics["cached_source_api_calls"] = int((source_metrics or {}).get("api_calls", 0) or 0)
    metrics["cached_source_prompt_tokens"] = int((source_metrics or {}).get("prompt_tokens", 0) or 0)
    metrics["cached_source_output_tokens"] = int((source_metrics or {}).get("output_tokens", 0) or 0)
    return metrics


def _restore_store_from_context_cache(vsm: VectorStoreManager, context_cache: Dict[str, Any]) -> Dict[str, Any]:
    artifacts = dict(context_cache.get("artifacts", {}) or {})
    parents = dict(artifacts.get("parents", {}) or {})
    texts = list(artifacts.get("texts", []) or [])
    metadatas = list(artifacts.get("metadatas", []) or [])
    if parents:
        vsm.add_parents(parents)
    if texts:
        vsm.add_documents(texts, metadatas)
    return {
        "stored_parent_chunks": len(parents),
        "restored_documents": len(texts),
    }


def _resolve_boolean_config(config: Dict[str, Any], key: str, default: bool) -> bool:
    value = config.get(key)
    if value is None:
        return default
    return bool(value)


def _build_graph_expansion_config(config: Dict[str, Any]) -> Dict[str, Any]:
    graph_config = dict(config.get("graph_expansion", {}) or {})
    enabled = bool(graph_config.get("enabled", False))
    sibling_window = int(graph_config.get("sibling_window", 1) or 1)
    max_docs = int(graph_config.get("max_docs", max(int(config.get("k", 8)) * 3, 12)) or max(int(config.get("k", 8)) * 3, 12))
    return {
        "enabled": enabled,
        "include_parent_context": bool(graph_config.get("include_parent_context", True)),
        "include_table_context": bool(graph_config.get("include_table_context", True)),
        "sibling_window": max(0, sibling_window),
        "max_docs": max(int(config.get("k", 8)), max_docs),
    }


def _load_eval_dataset(dataset_path: Path) -> List[EvalExample]:
    return load_eval_examples_from_path(dataset_path)


def _normalise_section_alias_config(raw_aliases: Dict[str, Any] | None) -> Dict[str, List[str]]:
    normalised: Dict[str, List[str]] = {}
    for category, aliases in (raw_aliases or {}).items():
        values: List[str] = []
        if isinstance(aliases, list):
            values = [str(alias).strip() for alias in aliases if str(alias).strip()]
        elif aliases:
            values = [str(aliases).strip()]
        normalised[str(category).strip().lower()] = values
    return normalised


def _expected_sections_for_example(example: EvalExample, screening_config: Dict[str, Any]) -> List[str]:
    sections = [section for section in example.canonical_expected_sections if section]
    alias_config = _normalise_section_alias_config(screening_config.get("section_aliases"))
    sections.extend(alias_config.get((example.category or "").lower(), []))
    if (example.category or "").lower() == "numeric_fact" and not alias_config.get("numeric_fact"):
        sections.extend(DEFAULT_NUMERIC_SECTION_ALIASES)
    deduped: List[str] = []
    seen = set()
    for section in sections:
        if section not in seen:
            seen.add(section)
            deduped.append(section)
    return deduped


def _metadata_matches_expected(
    metadata: Dict[str, Any],
    *,
    company: str,
    year: int,
    expected_sections: List[str],
) -> bool:
    actual_company = str(metadata.get("company", "")).lower()
    actual_year = int(metadata.get("year", 0) or 0)
    if actual_company != company or actual_year != year:
        return False
    section = str(metadata.get("section", ""))
    section_path = str(metadata.get("section_path", ""))
    return any(expected == section or expected in section_path for expected in expected_sections)


def _compute_screen_retrieval_hit_at_k(
    example: EvalExample,
    retrieved_docs: List[Any],
    screening_config: Dict[str, Any],
) -> float:
    expected_company = example.company.lower()
    expected_year = int(example.year)
    expected_sections = _expected_sections_for_example(example, screening_config)
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        if _metadata_matches_expected(
            metadata,
            company=expected_company,
            year=expected_year,
            expected_sections=expected_sections,
        ):
            return 1.0
    return 0.0


def _compute_screen_section_match_rate(
    example: EvalExample,
    retrieved_docs: List[Any],
    screening_config: Dict[str, Any],
) -> float:
    if not retrieved_docs:
        return 0.0
    expected_sections = _expected_sections_for_example(example, screening_config)
    matched = 0
    for item in retrieved_docs:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        section = str(metadata.get("section", ""))
        section_path = str(metadata.get("section_path", ""))
        if any(expected == section or expected in section_path for expected in expected_sections):
            matched += 1
    return matched / len(retrieved_docs)


def _compute_screen_citation_coverage(
    example: EvalExample,
    citations: List[str],
    screening_config: Dict[str, Any],
) -> float:
    if not citations:
        return 0.0

    expected_sections = _expected_sections_for_example(example, screening_config)
    citation_blob = " ".join(citations).lower()
    checks = [
        example.company.lower() in citation_blob,
        str(example.year) in citation_blob,
        any(section.lower() in citation_blob for section in expected_sections),
    ]
    return sum(1.0 for matched in checks if matched) / len(checks)


def _compute_contamination_rate(
    expected_company: str,
    expected_year: int,
    metadata_rows: List[Dict[str, Any]],
) -> float:
    if not metadata_rows:
        return 0.0

    mismatched = 0
    considered = 0
    lowered_company = expected_company.lower()
    for row in metadata_rows:
        company = str(row.get("company", "")).lower()
        year = int(row.get("year", 0) or 0)
        if not company and not year:
            continue
        considered += 1
        if company != lowered_company or year != expected_year:
            mismatched += 1
    if considered == 0:
        return 0.0
    return mismatched / considered


def _summarise_metadata_rows(metadata_rows: List[Dict[str, Any]], limit: int = 3) -> List[str]:
    summary: List[str] = []
    for row in metadata_rows[:limit]:
        company = row.get("company") or "?"
        year = row.get("year") or "?"
        section = row.get("section_path") or row.get("section") or "?"
        summary.append(f"{company}/{year}/{section}")
    return summary


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
                "answer": result.answer,
                "ground_truth": result.ground_truth,
                "answer_key": result.answer_key,
                "expected_sections": result.expected_sections,
                "evidence": result.evidence,
                "raw_faithfulness": result.raw_faithfulness,
                "faithfulness": result.faithfulness,
                "faithfulness_override_reason": result.faithfulness_override_reason,
                "answer_relevancy": result.answer_relevancy,
                "context_recall": result.context_recall,
                "retrieval_hit_at_k": result.retrieval_hit_at_k,
                "ndcg_at_3": result.ndcg_at_3,
                "ndcg_at_5": result.ndcg_at_5,
                "context_precision_at_3": result.context_precision_at_3,
                "context_precision_at_5": result.context_precision_at_5,
                "section_match_rate": result.section_match_rate,
                "citation_coverage": result.citation_coverage,
                "entity_coverage": result.entity_coverage,
                "completeness": result.completeness,
                "completeness_reason": result.completeness_reason,
                "refusal_accuracy": result.refusal_accuracy,
                "numeric_equivalence": result.numeric_equivalence,
                "numeric_grounding": result.numeric_grounding,
                "numeric_retrieval_support": result.numeric_retrieval_support,
                "numeric_final_judgement": result.numeric_final_judgement,
                "numeric_confidence": result.numeric_confidence,
                "numeric_debug": result.numeric_debug,
                "absolute_error_rate": result.absolute_error_rate,
                "calculation_correctness": result.calculation_correctness,
                "missing_info_compliance": result.missing_info_compliance,
                "retrieved_count": result.retrieved_count,
                "query_type": result.query_type,
                "intent": result.intent,
                "format_preference": result.format_preference,
                "routing_source": result.routing_source,
                "routing_confidence": result.routing_confidence,
                "routing_scores": result.routing_scores,
                "latency_sec": result.latency_sec,
                "citations": result.citations,
                "retrieved_metadata": result.retrieved_metadata,
                "retrieved_previews": result.retrieved_previews,
                "runtime_evidence": result.runtime_evidence,
                "selected_claim_ids": result.selected_claim_ids,
                "draft_points": result.draft_points,
                "kept_claim_ids": result.kept_claim_ids,
                "dropped_claim_ids": result.dropped_claim_ids,
                "unsupported_sentences": result.unsupported_sentences,
                "sentence_checks": result.sentence_checks,
                "missing_info_policy": result.missing_info_policy,
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
                "retrieved_previews": _extract_retrieved_previews(retrieved_docs),
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


def _run_screening_eval(
    agent: FinancialAgent,
    examples: List[EvalExample],
    screening_config: Dict[str, Any],
) -> Dict[str, Any]:
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

        retrieved_metadata = _extract_retrieved_metadata(retrieved_docs)
        contamination_rate = _compute_contamination_rate(example.company, int(example.year), retrieved_metadata)
        retrieval_hit_at_k = _compute_screen_retrieval_hit_at_k(example, retrieved_docs, screening_config)
        section_match_rate = _compute_screen_section_match_rate(example, retrieved_docs, screening_config)
        citation_coverage = _compute_screen_citation_coverage(example, citations, screening_config)
        failure_flags: List[str] = []
        if retrieval_hit_at_k == 0.0:
            failure_flags.append("hit_at_k_zero")
        if section_match_rate == 0.0:
            failure_flags.append("section_match_zero")
        if contamination_rate > 0.0:
            failure_flags.append("contamination")
        if error:
            failure_flags.append("error")

        rows.append(
            {
                "id": example.id,
                "question": example.question,
                "category": example.category,
                "company": example.company,
                "year": example.year,
                "section": example.section,
                "expected_sections": example.canonical_expected_sections,
                "answer_key": example.canonical_answer_key,
                "answer_preview": answer[:240],
                "retrieval_hit_at_k": retrieval_hit_at_k,
                "section_match_rate": section_match_rate,
                "citation_coverage": citation_coverage,
                "contamination_rate": contamination_rate,
                "retrieved_count": len(retrieved_docs),
                "retrieved_metadata": retrieved_metadata,
                "retrieved_previews": _extract_retrieved_previews(retrieved_docs),
                "top_retrieved": _summarise_metadata_rows(retrieved_metadata),
                "failure_flags": failure_flags,
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
            "contamination_rate": _avg("contamination_rate"),
            "avg_latency": _avg("latency_sec"),
            "error_rate": (len(rows) - len(valid_rows)) / len(rows) if rows else 0.0,
            "failure_examples": [
                {
                    "id": row["id"],
                    "category": row.get("category"),
                    "failure_flags": row.get("failure_flags", []),
                    "top_retrieved": row.get("top_retrieved", []),
                }
                for row in rows
                if row.get("failure_flags")
            ],
        },
        "per_question": rows,
    }


def _contains_missing_language(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in MISSING_INFO_MARKERS)


def _looks_like_full_abstention_answer(text: str) -> bool:
    lowered = (text or "").lower()
    return any(marker in lowered for marker in ABSTENTION_MARKERS)


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
        if category not in MISSING_INFO_CATEGORIES and _looks_like_full_abstention_answer(row.get("answer", "")):
            reasons.append(f"answerable smoke query abstained: {row['query']}")
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
        if category in RISK_CATEGORIES | BUSINESS_CATEGORIES | NUMERIC_CATEGORIES and float(
            row.get("retrieval_hit_at_k", 0.0)
        ) == 0.0:
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

    if eval_mode == "question_ids":
        allowed = set(config.get("question_ids") or [])
        return [e for e in filtered if e.id in allowed]

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


def _zero_cost_alias_terms(metadata: Dict[str, Any]) -> List[str]:
    section = str(metadata.get("section", "")).strip()
    section_path = str(metadata.get("section_path", section)).strip()
    block_type = "table" if metadata.get("block_type") == "table" else "paragraph"
    lowered = f"{section} {section_path}".lower()

    terms: List[str] = [section, section_path]
    if "위험관리" in section_path or "리스크" in section_path or "risk" in lowered:
        terms.extend(["리스크", "재무 리스크", "위험관리", "시장위험", "신용위험", "유동성위험"])
    if any(token in section_path for token in ["매출", "수주", "손익", "재무제표", "연결재무제표"]):
        terms.extend(["매출", "연결 기준", "재무", "손익", "영업이익", "매출액"])
    if any(token in section_path for token in ["사업의 개요", "회사의 개요", "주요 제품 및 서비스"]):
        terms.extend(["주요 사업", "사업 개요", "제품", "서비스", "사업 부문"])
    if "연구개발" in section_path:
        terms.extend(["연구개발", "R&D", "투자", "기술 개발"])
    if metadata.get("table_context"):
        terms.append("표 설명 문맥")
    terms.append("표" if block_type == "table" else "문단")

    unique_terms: List[str] = []
    seen: set[str] = set()
    for term in terms:
        cleaned = str(term or "").strip()
        if not cleaned:
            continue
        lowered_term = cleaned.lower()
        if lowered_term in seen:
            continue
        seen.add(lowered_term)
        unique_terms.append(cleaned)
    return unique_terms


def _build_zero_cost_prefixed_text(metadata: Dict[str, Any], content: str) -> str:
    prefix_lines = [
        f"[회사: {metadata.get('company', '?')}] [연도: {metadata.get('year', '?')}] [보고서: {metadata.get('report_type', '?')}]",
        f"[섹션: {metadata.get('section_path', metadata.get('section', '?'))}]",
        f"[분류: {metadata.get('section', '?')} / {'table' if metadata.get('block_type') == 'table' else 'paragraph'}]",
        f"[키워드: {', '.join(_zero_cost_alias_terms(metadata))}]",
    ]
    return "\n".join(prefix_lines) + f"\n\n{content}"


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


def _contains_any_target(section: str, section_path: str, targets: List[str]) -> bool:
    return any(target and (target == section or target in section_path) for target in targets)


def _selective_reason_v1(
    chunk: Any,
    *,
    short_text_threshold: int = 900,
    targeted_sections: Optional[List[str]] = None,
) -> Optional[str]:
    metadata = chunk.metadata or {}
    content = (chunk.content or "").strip()
    section = str(metadata.get("section", "")).strip()
    section_path = str(metadata.get("section_path", section)).strip()
    targets = targeted_sections or ["리스크", "연구개발", "매출현황", "사업개요", "경영진단"]

    if metadata.get("block_type") == "table":
        return "table"
    if len(content) <= short_text_threshold:
        return "short_text"
    if _contains_any_target(section, section_path, targets):
        return "targeted_section"
    return None


def _selective_reason_v2(
    chunk: Any,
    *,
    short_text_threshold: int = 700,
    targeted_sections: Optional[List[str]] = None,
    short_table_threshold: int = 1600,
) -> Optional[str]:
    metadata = chunk.metadata or {}
    content = (chunk.content or "").strip()
    content_len = len(content)
    section = str(metadata.get("section", "")).strip()
    section_path = str(metadata.get("section_path", section)).strip()
    block_type = str(metadata.get("block_type", "")).strip()
    targets = targeted_sections or DEFAULT_SELECTIVE_V2_SECTIONS

    if block_type == "table":
        if content_len <= short_table_threshold:
            return "short_table"
        if metadata.get("table_context"):
            return "context_dependent_table"

    if _contains_any_target(section, section_path, ["사업개요"]) and block_type == "paragraph" and content_len <= 1800:
        return "business_overview_paragraph"
    if _contains_any_target(section, section_path, ["위험관리 및 파생거래", "리스크"]) and content_len <= 2200:
        return "risk_section_chunk"
    if _contains_any_target(section, section_path, ["연구개발"]) and block_type == "paragraph" and content_len <= 1800:
        return "rnd_summary_paragraph"
    if _contains_any_target(section, section_path, ["매출 및 수주상황", "매출현황"]) and block_type == "table":
        return "sales_table"
    if block_type == "paragraph" and content_len <= short_text_threshold and _contains_any_target(section, section_path, targets):
        return "short_targeted_paragraph"
    return None


def _selective_reason_parent_hybrid(
    chunk: Any,
    *,
    short_text_threshold: int = 700,
    targeted_sections: Optional[List[str]] = None,
) -> Optional[str]:
    metadata = chunk.metadata or {}
    content = (chunk.content or "").strip()
    section = str(metadata.get("section", "")).strip()
    section_path = str(metadata.get("section_path", section)).strip()
    block_type = str(metadata.get("block_type", "")).strip()
    targets = targeted_sections or DEFAULT_PARENT_HYBRID_SECTIONS

    if block_type == "table":
        return "table"
    if len(content) <= short_text_threshold:
        return "short_text"
    if _contains_any_target(section, section_path, targets):
        return "targeted_section"
    return None


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


def _count_reason_counts(selected_reasons: Dict[int, str]) -> Dict[str, int]:
    counter = Counter(selected_reasons.values())
    return {reason: count for reason, count in sorted(counter.items())}


def _select_chunk_reasons(
    chunks: List[Any],
    selector,
    **selector_kwargs,
) -> Dict[int, str]:
    selected: Dict[int, str] = {}
    for idx, chunk in enumerate(chunks):
        reason = selector(chunk, **selector_kwargs)
        if reason:
            selected[idx] = reason
    return selected


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
    return_artifacts: bool = False,
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
    metadatas = [chunk.metadata for chunk in chunks]
    agent.vsm.add_documents(texts, metadatas)

    result = {
        "mode": "contextual_parent_only",
        "chunks": len(chunks),
        "stored_parent_chunks": len(parents),
        "contextualized_chunks": len(items),
        "selector_reason_counts": {},
        "parent_context_calls": len(items),
        "child_context_calls": 0,
        **metrics,
        "elapsed_sec": time.perf_counter() - started_at,
    }
    if return_artifacts:
        result["artifacts"] = {
            "texts": texts,
            "metadatas": metadatas,
            "parents": parents,
        }
    return result


def _benchmark_parent_hybrid_ingest(
    agent: FinancialAgent,
    chunks: List[Any],
    *,
    on_progress=None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
    short_text_threshold: int = 700,
    targeted_sections: Optional[List[str]] = None,
    return_artifacts: bool = False,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    parents = _store_parent_chunks(agent, chunks)
    grouped: Dict[str, List[int]] = {}
    parent_metadata: Dict[str, Dict[str, Any]] = {}
    for idx, chunk in enumerate(chunks):
        parent_id = str((chunk.metadata or {}).get("parent_id") or f"chunk-{idx}")
        grouped.setdefault(parent_id, []).append(idx)
        parent_metadata.setdefault(parent_id, chunk.metadata)

    parent_items = [
        {
            "key": parent_id,
            "text": parents.get(parent_id) or "\n\n".join(chunks[i].content for i in indexes),
            "metadata": parent_metadata[parent_id],
        }
        for parent_id, indexes in grouped.items()
    ]
    child_reasons = _select_chunk_reasons(
        chunks,
        _selective_reason_parent_hybrid,
        short_text_threshold=short_text_threshold,
        targeted_sections=targeted_sections,
    )
    child_items = [
        {"key": idx, "text": chunks[idx].content, "metadata": chunks[idx].metadata}
        for idx in sorted(child_reasons)
    ]

    total_progress = len(parent_items) + len(child_items)

    parent_contexts, parent_metrics = _generate_context_map(
        agent,
        parent_items,
        prompt_builder=lambda item: _build_parent_context_prompt(item["text"], item["metadata"]),
        fallback_builder=lambda item: _fallback_context(item["metadata"]),
        on_progress=None,
        max_workers=max_workers,
        batch_size=batch_size,
        log_label="benchmark_contextual_parent_hybrid_parent",
    )
    completed = len(parent_items)
    if on_progress:
        on_progress(completed, total_progress)

    child_contexts, child_metrics = _generate_context_map(
        agent,
        child_items,
        prompt_builder=lambda item: _build_context_prompt(item["text"], item["metadata"]),
        fallback_builder=lambda item: _fallback_context(item["metadata"]),
        on_progress=(lambda current, total: on_progress(completed + current, total_progress)) if on_progress else None,
        max_workers=max_workers,
        batch_size=batch_size,
        log_label="benchmark_contextual_parent_hybrid_child",
    )

    texts = []
    for idx, chunk in enumerate(chunks):
        parent_id = str((chunk.metadata or {}).get("parent_id") or f"chunk-{idx}")
        context_parts = [parent_contexts.get(parent_id, "")]
        if idx in child_contexts:
            context_parts.append(child_contexts[idx])
        context = "\n".join(part.strip() for part in context_parts if part and part.strip())
        texts.append(_build_index_text(chunk.metadata, chunk.content, context or None))
    metadatas = [chunk.metadata for chunk in chunks]
    agent.vsm.add_documents(texts, metadatas)

    result = {
        "mode": "contextual_parent_hybrid",
        "chunks": len(chunks),
        "stored_parent_chunks": len(parents),
        "contextualized_chunks": len(parent_items) + len(child_items),
        "selector_reason_counts": _count_reason_counts(child_reasons),
        "parent_context_calls": len(parent_items),
        "child_context_calls": len(child_items),
        "api_calls": parent_metrics.get("api_calls", 0) + child_metrics.get("api_calls", 0),
        "fallback_count": parent_metrics.get("fallback_count", 0) + child_metrics.get("fallback_count", 0),
        "prompt_chars": parent_metrics.get("prompt_chars", 0) + child_metrics.get("prompt_chars", 0),
        "response_chars": parent_metrics.get("response_chars", 0) + child_metrics.get("response_chars", 0),
        "prompt_tokens": parent_metrics.get("prompt_tokens", 0) + child_metrics.get("prompt_tokens", 0),
        "output_tokens": parent_metrics.get("output_tokens", 0) + child_metrics.get("output_tokens", 0),
        "total_tokens": parent_metrics.get("total_tokens", 0) + child_metrics.get("total_tokens", 0),
        "max_workers": max(parent_metrics.get("max_workers", 0), child_metrics.get("max_workers", 0)),
        "batch_size": max(parent_metrics.get("batch_size", 0), child_metrics.get("batch_size", 0)),
        "elapsed_sec": time.perf_counter() - started_at,
    }
    if return_artifacts:
        result["artifacts"] = {
            "texts": texts,
            "metadatas": metadatas,
            "parents": parents,
        }
    return result


def _benchmark_selective_ingest(
    agent: FinancialAgent,
    chunks: List[Any],
    *,
    on_progress=None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
    short_text_threshold: int = 900,
    targeted_sections: Optional[List[str]] = None,
    return_artifacts: bool = False,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    parents = _store_parent_chunks(agent, chunks)
    selected_reasons = _select_chunk_reasons(
        chunks,
        _selective_reason_v1,
        short_text_threshold=short_text_threshold,
        targeted_sections=targeted_sections,
    )
    items = [
        {"key": idx, "text": chunks[idx].content, "metadata": chunks[idx].metadata}
        for idx in sorted(selected_reasons)
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
    metadatas = [chunk.metadata for chunk in chunks]
    agent.vsm.add_documents(texts, metadatas)

    result = {
        "mode": "contextual_selective",
        "chunks": len(chunks),
        "stored_parent_chunks": len(parents),
        "contextualized_chunks": len(items),
        "selector_reason_counts": _count_reason_counts(selected_reasons),
        "parent_context_calls": 0,
        "child_context_calls": len(items),
        **metrics,
        "elapsed_sec": time.perf_counter() - started_at,
    }
    if return_artifacts:
        result["artifacts"] = {
            "texts": texts,
            "metadatas": metadatas,
            "parents": parents,
        }
    return result


def _benchmark_selective_v2_ingest(
    agent: FinancialAgent,
    chunks: List[Any],
    *,
    on_progress=None,
    max_workers: Optional[int] = None,
    batch_size: Optional[int] = None,
    short_text_threshold: int = 700,
    targeted_sections: Optional[List[str]] = None,
    short_table_threshold: int = 1600,
    use_zero_cost_prefix: bool = False,
    return_artifacts: bool = False,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    parents = _store_parent_chunks(agent, chunks)
    selected_reasons = _select_chunk_reasons(
        chunks,
        _selective_reason_v2,
        short_text_threshold=short_text_threshold,
        targeted_sections=targeted_sections,
        short_table_threshold=short_table_threshold,
    )
    items = [
        {"key": idx, "text": chunks[idx].content, "metadata": chunks[idx].metadata}
        for idx in sorted(selected_reasons)
    ]
    contexts, metrics = _generate_context_map(
        agent,
        items,
        prompt_builder=lambda item: _build_context_prompt(item["text"], item["metadata"]),
        fallback_builder=lambda item: _fallback_context(item["metadata"]),
        on_progress=on_progress,
        max_workers=max_workers,
        batch_size=batch_size,
        log_label="benchmark_contextual_selective_v2",
    )

    texts = []
    for idx, chunk in enumerate(chunks):
        context = contexts.get(idx)
        if use_zero_cost_prefix:
            base = _build_zero_cost_prefixed_text(chunk.metadata, chunk.content)
            texts.append((context.strip() + "\n\n" + base) if context and context.strip() else base)
        else:
            texts.append(_build_index_text(chunk.metadata, chunk.content, context))
    metadatas = [chunk.metadata for chunk in chunks]
    agent.vsm.add_documents(texts, metadatas)

    result = {
        "mode": "contextual_selective_v2",
        "chunks": len(chunks),
        "stored_parent_chunks": len(parents),
        "contextualized_chunks": len(items),
        "selector_reason_counts": _count_reason_counts(selected_reasons),
        "parent_context_calls": 0,
        "child_context_calls": len(items),
        "use_zero_cost_prefix": use_zero_cost_prefix,
        **metrics,
        "elapsed_sec": time.perf_counter() - started_at,
    }
    if return_artifacts:
        result["artifacts"] = {
            "texts": texts,
            "metadatas": metadatas,
            "parents": parents,
        }
    return result


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
                "block_type": metadata.get("block_type"),
                "graph_relation": metadata.get("graph_relation"),
            }
        )
    return rows


def _compact_text_preview(text: str, limit: int = 220) -> str:
    flattened = " ".join((text or "").split())
    if len(flattened) <= limit:
        return flattened
    return flattened[: max(limit - 3, 0)].rstrip() + "..."


def _extract_retrieved_previews(retrieved_docs: List[Any], limit: int = 8, chars: int = 220) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for item in retrieved_docs[:limit]:
        doc = item[0] if isinstance(item, (tuple, list)) else item
        metadata = getattr(doc, "metadata", {}) or {}
        text = getattr(doc, "content", None) or getattr(doc, "page_content", "")
        rows.append(
            {
                "company": metadata.get("company"),
                "year": metadata.get("year"),
                "section": metadata.get("section"),
                "section_path": metadata.get("section_path"),
                "block_type": metadata.get("block_type"),
                "graph_relation": metadata.get("graph_relation"),
                "preview": _compact_text_preview(text, limit=chars),
            }
        )
    return rows


def _flatten_review_rows(results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for result in results:
        screening_lookup = {
            row.get("id"): row
            for row in result.get("screening_eval", {}).get("per_question", [])
        }
        for question_result in result.get("full_eval", {}).get("per_question", []):
            evidence_rows = question_result.get("evidence") or []
            evidence_quotes = [
                f"{row.get('section_path', '?')}: {row.get('quote', '')}"
                for row in evidence_rows
                if row.get("quote")
            ]
            runtime_evidence_rows = question_result.get("runtime_evidence") or []
            runtime_evidence = []
            for row in runtime_evidence_rows:
                metadata = row.get("metadata") or {}
                section = metadata.get("section_path") or metadata.get("section") or "?"
                runtime_evidence.append(
                    " | ".join(
                        part
                        for part in [
                            row.get("evidence_id") or "?",
                            row.get("support_level") or "?",
                            row.get("question_relevance") or "?",
                            row.get("source_anchor") or "?",
                            f"section={section}",
                            f"claim={row.get('claim', '')}",
                            f"quote={row.get('quote_span', '')}",
                        ]
                        if part
                    )
                )
            draft_points_rows = question_result.get("draft_points") or []
            unsupported_rows = question_result.get("unsupported_sentences") or []
            sentence_check_rows = question_result.get("sentence_checks") or []
            sentence_checks = []
            for row in sentence_check_rows:
                sentence_checks.append(
                    " | ".join(
                        part
                        for part in [
                            row.get("verdict") or "?",
                            row.get("sentence") or "",
                            f"reason={row.get('reason', '')}" if row.get("reason") else "",
                            (
                                "claims=" + ", ".join(row.get("supporting_claim_ids") or [])
                                if row.get("supporting_claim_ids")
                                else ""
                            ),
                        ]
                        if part
                    )
                )
            top_retrieved = []
            for metadata in (question_result.get("retrieved_metadata") or [])[:3]:
                company = metadata.get("company") or "?"
                year = metadata.get("year") or "?"
                section = metadata.get("section_path") or metadata.get("section") or "?"
                top_retrieved.append(f"{company}/{year}/{section}")
            screening_row = screening_lookup.get(question_result.get("id"), {})
            retrieved_preview_rows = question_result.get("retrieved_previews") or screening_row.get("retrieved_previews") or []
            retrieved_previews = []
            for preview in retrieved_preview_rows:
                section = preview.get("section_path") or preview.get("section") or "?"
                block_type = preview.get("block_type") or "?"
                relation = preview.get("graph_relation") or "seed"
                body = preview.get("preview") or ""
                retrieved_previews.append(f"{section} [{block_type} / {relation}] {body}".strip())
            rows.append(
                {
                    "experiment_id": result["id"],
                    "question_id": question_result.get("id"),
                    "category": screening_row.get("category"),
                    "question": question_result.get("question"),
                    "answer_key": question_result.get("answer_key"),
                    "expected_sections": " | ".join(question_result.get("expected_sections", [])),
                    "evidence_quotes": "\n\n".join(evidence_quotes),
                    "runtime_evidence": "\n\n".join(runtime_evidence),
                    "selected_claim_ids": " | ".join(question_result.get("selected_claim_ids", [])),
                    "draft_points": "\n\n".join(str(row) for row in draft_points_rows),
                    "kept_claim_ids": " | ".join(question_result.get("kept_claim_ids", [])),
                    "dropped_claim_ids": " | ".join(question_result.get("dropped_claim_ids", [])),
                    "unsupported_sentences": "\n\n".join(str(row) for row in unsupported_rows),
                    "sentence_checks": "\n\n".join(sentence_checks),
                    "actual_answer": question_result.get("answer"),
                    "top_retrieved": " | ".join(top_retrieved),
                    "retrieved_previews": "\n\n".join(retrieved_previews),
                    "citations": " | ".join(question_result.get("citations", [])),
                    "query_type": question_result.get("query_type"),
                    "intent": question_result.get("intent"),
                    "format_preference": question_result.get("format_preference"),
                    "routing_source": question_result.get("routing_source"),
                    "routing_confidence": question_result.get("routing_confidence"),
                    "routing_scores": json.dumps(question_result.get("routing_scores", {}), ensure_ascii=False),
                    "raw_faithfulness": question_result.get("raw_faithfulness"),
                    "faithfulness": question_result.get("faithfulness"),
                    "faithfulness_override_reason": question_result.get("faithfulness_override_reason"),
                    "answer_relevancy": question_result.get("answer_relevancy"),
                    "context_recall": question_result.get("context_recall"),
                    "retrieval_hit_at_k": question_result.get("retrieval_hit_at_k"),
                    "ndcg_at_3": question_result.get("ndcg_at_3"),
                    "ndcg_at_5": question_result.get("ndcg_at_5"),
                    "context_precision_at_3": question_result.get("context_precision_at_3"),
                    "context_precision_at_5": question_result.get("context_precision_at_5"),
                    "section_match_rate": question_result.get("section_match_rate"),
                    "citation_coverage": question_result.get("citation_coverage"),
                    "entity_coverage": question_result.get("entity_coverage"),
                    "completeness": question_result.get("completeness"),
                    "completeness_reason": question_result.get("completeness_reason"),
                    "refusal_accuracy": question_result.get("refusal_accuracy"),
                    "numeric_equivalence": question_result.get("numeric_equivalence"),
                    "numeric_grounding": question_result.get("numeric_grounding"),
                    "numeric_retrieval_support": question_result.get("numeric_retrieval_support"),
                    "numeric_final_judgement": question_result.get("numeric_final_judgement"),
                    "numeric_confidence": question_result.get("numeric_confidence"),
                    "absolute_error_rate": question_result.get("absolute_error_rate"),
                    "calculation_correctness": question_result.get("calculation_correctness"),
                    "missing_info_compliance": question_result.get("missing_info_compliance"),
                    "missing_info_policy": question_result.get("missing_info_policy"),
                    "error": question_result.get("error"),
                }
            )
    return rows


def _write_review_csv(path: Path, results: List[Dict[str, Any]]) -> None:
    rows = _flatten_review_rows(results)
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "experiment_id",
        "question_id",
        "category",
        "question",
        "answer_key",
        "expected_sections",
        "evidence_quotes",
        "runtime_evidence",
        "selected_claim_ids",
        "draft_points",
        "kept_claim_ids",
        "dropped_claim_ids",
        "unsupported_sentences",
        "sentence_checks",
        "actual_answer",
        "top_retrieved",
        "retrieved_previews",
        "citations",
        "query_type",
        "intent",
        "format_preference",
        "routing_source",
        "routing_confidence",
        "routing_scores",
        "raw_faithfulness",
        "faithfulness",
        "faithfulness_override_reason",
        "answer_relevancy",
        "context_recall",
        "retrieval_hit_at_k",
        "ndcg_at_3",
        "ndcg_at_5",
        "context_precision_at_3",
        "context_precision_at_5",
        "section_match_rate",
        "citation_coverage",
        "entity_coverage",
        "completeness",
        "completeness_reason",
        "refusal_accuracy",
        "numeric_equivalence",
        "numeric_grounding",
        "numeric_retrieval_support",
        "numeric_final_judgement",
        "numeric_confidence",
        "absolute_error_rate",
        "calculation_correctness",
        "missing_info_compliance",
        "missing_info_policy",
        "error",
    ]
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def _render_review_markdown(results: List[Dict[str, Any]]) -> str:
    rows = _flatten_review_rows(results)
    lines = [
        "# Benchmark Review",
        "",
        "질문별로 정답 요약, 근거 quote, 실제 응답, 상위 retrieval을 한 번에 검수하기 위한 보기다.",
        "",
    ]
    if not rows:
        lines.append("full evaluation 결과가 없어 review 대상 질문이 없습니다.")
        return "\n".join(lines) + "\n"

    current_experiment = None
    for row in rows:
        if row["experiment_id"] != current_experiment:
            current_experiment = row["experiment_id"]
            lines.extend([f"## {current_experiment}", ""])
        lines.extend(
            [
                f"### {row['question_id']}: {row['question']}",
                "",
                f"- Answer Key: {row['answer_key']}",
                f"- Expected Sections: {row['expected_sections'] or '-'}",
                f"- Top Retrieved: {row['top_retrieved'] or '-'}",
                f"- Routing: query_type={row['query_type'] or '-'}, intent={row['intent'] or '-'}, format={row['format_preference'] or '-'}, source={row['routing_source'] or '-'}, confidence={row['routing_confidence'] if row['routing_confidence'] is not None else '-'}",
                f"- Citations: {row['citations'] or '-'}",
                f"- Metrics: raw_faithfulness={row['raw_faithfulness']}, faithfulness={row['faithfulness']}, relevancy={row['answer_relevancy']}, recall={row['context_recall']}, hit@k={row['retrieval_hit_at_k']}, ndcg@5={row['ndcg_at_5']}, p@5={row['context_precision_at_5']}, section={row['section_match_rate']}, citation={row['citation_coverage']}, entity={row['entity_coverage']}, completeness={row['completeness']}, refusal={row['refusal_accuracy']}",
            ]
        )
        if row.get("routing_scores"):
            lines.append(f"- Routing Scores: {row['routing_scores']}")
        if row.get("faithfulness_override_reason"):
            lines.append(f"- Faithfulness Override: {row['faithfulness_override_reason']}")
        if row.get("completeness_reason"):
            lines.append(f"- Completeness Reason: {row['completeness_reason']}")
        if row.get("numeric_final_judgement"):
            lines.append(
                f"- Numeric Eval: judgement={row['numeric_final_judgement']}, "
                f"equivalence={row['numeric_equivalence']}, grounding={row['numeric_grounding']}, "
                f"retrieval_support={row['numeric_retrieval_support']}, confidence={row['numeric_confidence']}, "
                f"abs_error={row['absolute_error_rate']}, calc={row['calculation_correctness']}"
            )
        if row.get("missing_info_policy"):
            lines.append(f"- Missing Info Policy: {row['missing_info_policy']}")
        if row.get("missing_info_compliance") is not None:
            lines.append(f"- Missing Info Compliance: {row['missing_info_compliance']}")
        lines.extend(
            [
                "",
                "Evidence",
                "",
                row["evidence_quotes"] or "-",
                "",
                "Retrieved Chunks",
                "",
                row["retrieved_previews"] or "-",
                "",
                "Runtime Evidence",
                "",
                row["runtime_evidence"] or "-",
                "",
                "Selected Claims",
                "",
                row["selected_claim_ids"] or "-",
                "",
                "Draft Points",
                "",
                row["draft_points"] or "-",
                "",
                "Kept Claims",
                "",
                row["kept_claim_ids"] or "-",
                "",
                "Dropped Claims",
                "",
                row["dropped_claim_ids"] or "-",
                "",
                "Unsupported Sentences",
                "",
                row["unsupported_sentences"] or "-",
                "",
                "Sentence Checks",
                "",
                row["sentence_checks"] or "-",
                "",
                "Actual Answer",
                "",
                row["actual_answer"] or "-",
                "",
            ]
        )
    return "\n".join(lines) + "\n"


def _render_summary_markdown(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        "| Experiment | Chunk | Overlap | Mode | Screen Pass | Parse (s) | Ingest (s) | Est. Cost (USD) | API Δ | Time Δ | Cost Δ | Parent Calls | Child Calls | API Calls | Contam | Hit@k | NDCG@5 | P@5 | Entity | Section | Citation | Full Faithfulness | Full Relevancy | Full Recall | Full Completeness | Refusal | Numeric Pass |",
        "|---|---:|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        config = result["config"]
        ingest = result["ingest"]
        screen = result.get("screening_eval", {}).get("aggregate", {})
        full = result.get("full_eval", {}).get("aggregate", {})
        estimated_cost = result.get("estimated_ingest_cost_usd")
        comparison = result.get("comparison_to_baseline", {})
        api_delta = comparison.get("api_call_reduction_ratio")
        ingest_delta = comparison.get("ingest_time_reduction_ratio")
        cost_delta = comparison.get("estimated_cost_reduction_ratio")
        lines.append(
              "| {id} | {chunk} | {overlap} | {mode} | {passed} | {parse:.3f} | {ingest_sec:.3f} | {cost} | {api_delta} | {ingest_delta} | {cost_delta} | {parent_calls} | {child_calls} | {api_calls} | {contam:.3f} | {hit:.3f} | {ndcg} | {p5} | {entity} | {section:.3f} | {citation:.3f} | {faith} | {rel} | {recall} | {complete} | {refusal} | {numeric_pass} |".format(
                  id=result["id"],
                chunk=config.get("chunk_size"),
                overlap=config.get("chunk_overlap"),
                mode=config.get("ingest_mode"),
                passed="yes" if result.get("screen_pass") else "no",
                parse=result["parse"]["elapsed_sec"],
                ingest_sec=ingest.get("elapsed_sec", 0.0),
                cost="-" if estimated_cost is None else f"{float(estimated_cost):.4f}",
                api_delta="-" if api_delta is None else f"{api_delta:.1%}",
                ingest_delta="-" if ingest_delta is None else f"{ingest_delta:.1%}",
                cost_delta="-" if cost_delta is None else f"{cost_delta:.1%}",
                parent_calls=ingest.get("parent_context_calls", 0),
                child_calls=ingest.get("child_context_calls", 0),
                  api_calls=ingest.get("api_calls", 0),
                  faith="-" if not full else f"{full.get('faithfulness', 0.0):.3f}",
                  rel="-" if not full else f"{full.get('answer_relevancy', 0.0):.3f}",
                  recall="-" if not full else f"{full.get('context_recall', 0.0):.3f}",
                  complete="-" if not full or full.get("completeness") is None else f"{full.get('completeness', 0.0):.3f}",
                  refusal="-" if not full or full.get("refusal_accuracy") is None else f"{full.get('refusal_accuracy', 0.0):.3f}",
                  numeric_pass="-" if not full or full.get("numeric_pass_rate") is None else f"{full.get('numeric_pass_rate', 0.0):.3f}",
                  contam=screen.get("contamination_rate", 0.0),
                  hit=screen.get("retrieval_hit_at_k", 0.0),
                  ndcg="-" if screen.get("ndcg_at_5") is None else f"{screen.get('ndcg_at_5', 0.0):.3f}",
                  p5="-" if screen.get("context_precision_at_5") is None else f"{screen.get('context_precision_at_5', 0.0):.3f}",
                  entity="-" if screen.get("entity_coverage") is None else f"{screen.get('entity_coverage', 0.0):.3f}",
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
            "- `API Δ` and `Time Δ` are reduction ratios versus the baseline experiment.",
            "- `Contam` is the average screening contamination rate across retrieved top-k docs.",
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
        "selector_reason_counts",
        "parent_context_calls",
        "child_context_calls",
        "api_calls",
        "prompt_tokens",
        "output_tokens",
        "estimated_ingest_cost_usd",
        "baseline_api_call_reduction_ratio",
        "baseline_ingest_time_reduction_ratio",
        "baseline_estimated_cost_reduction_ratio",
        "smoke_avg_latency_sec",
          "screen_retrieval_hit_at_k",
          "screen_ndcg_at_3",
          "screen_ndcg_at_5",
          "screen_context_precision_at_3",
          "screen_context_precision_at_5",
          "screen_section_match_rate",
          "screen_citation_coverage",
          "screen_entity_coverage",
          "screen_completeness",
          "screen_refusal_accuracy",
          "screen_contamination_rate",
          "screen_pass",
        "screen_failure_reasons",
        "screen_failure_examples",
          "full_faithfulness",
          "full_answer_relevancy",
          "full_context_recall",
          "full_completeness",
          "full_refusal_accuracy",
          "full_retrieval_hit_at_k",
          "full_section_match_rate",
          "full_citation_coverage",
          "full_numeric_pass_rate",
          "full_absolute_error_rate",
          "full_calculation_correctness",
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
            comparison = result.get("comparison_to_baseline", {})
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
                    "selector_reason_counts": json.dumps(ingest.get("selector_reason_counts", {}), ensure_ascii=False),
                    "parent_context_calls": ingest.get("parent_context_calls", 0),
                    "child_context_calls": ingest.get("child_context_calls", 0),
                    "api_calls": ingest.get("api_calls", 0),
                    "prompt_tokens": ingest.get("prompt_tokens", 0),
                    "output_tokens": ingest.get("output_tokens", 0),
                    "estimated_ingest_cost_usd": result.get("estimated_ingest_cost_usd"),
                    "baseline_api_call_reduction_ratio": comparison.get("api_call_reduction_ratio"),
                    "baseline_ingest_time_reduction_ratio": comparison.get("ingest_time_reduction_ratio"),
                    "baseline_estimated_cost_reduction_ratio": comparison.get("estimated_cost_reduction_ratio"),
                    "smoke_avg_latency_sec": smoke.get("avg_latency_sec"),
                      "screen_retrieval_hit_at_k": screen.get("retrieval_hit_at_k"),
                      "screen_ndcg_at_3": screen.get("ndcg_at_3"),
                      "screen_ndcg_at_5": screen.get("ndcg_at_5"),
                      "screen_context_precision_at_3": screen.get("context_precision_at_3"),
                      "screen_context_precision_at_5": screen.get("context_precision_at_5"),
                      "screen_section_match_rate": screen.get("section_match_rate"),
                      "screen_citation_coverage": screen.get("citation_coverage"),
                      "screen_entity_coverage": screen.get("entity_coverage"),
                      "screen_completeness": screen.get("completeness"),
                      "screen_refusal_accuracy": screen.get("refusal_accuracy"),
                      "screen_contamination_rate": screen.get("contamination_rate"),
                    "screen_pass": result.get("screen_pass"),
                    "screen_failure_reasons": " | ".join(result.get("screen_failure_reasons", [])),
                    "screen_failure_examples": json.dumps(screen.get("failure_examples", []), ensure_ascii=False),
                      "full_faithfulness": full.get("faithfulness"),
                      "full_answer_relevancy": full.get("answer_relevancy"),
                      "full_context_recall": full.get("context_recall"),
                      "full_completeness": full.get("completeness"),
                      "full_refusal_accuracy": full.get("refusal_accuracy"),
                      "full_retrieval_hit_at_k": full.get("retrieval_hit_at_k"),
                      "full_section_match_rate": full.get("section_match_rate"),
                      "full_citation_coverage": full.get("citation_coverage"),
                      "full_numeric_pass_rate": full.get("numeric_pass_rate"),
                      "full_absolute_error_rate": full.get("absolute_error_rate"),
                      "full_calculation_correctness": full.get("calculation_correctness"),
                      "full_avg_score": full.get("avg_score"),
                      "full_avg_latency": full.get("avg_latency"),
                  }
            )


def _company_run_label(company_run: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    metadata = _deep_merge(defaults.get("metadata", {}), company_run.get("defaults", {}).get("metadata", {}))
    company = str(metadata.get("company") or company_run.get("id") or "company").strip()
    year = metadata.get("year")
    return f"{company} {year}".strip() if year else company


def _company_output_subdir(company_run: Dict[str, Any], defaults: Dict[str, Any]) -> str:
    if company_run.get("output_subdir"):
        return str(company_run["output_subdir"])
    metadata = _deep_merge(defaults.get("metadata", {}), company_run.get("defaults", {}).get("metadata", {}))
    company = str(metadata.get("company") or company_run.get("id") or "company")
    year = str(metadata.get("year") or "").strip()
    parts = [_slugify(company)]
    if year:
        parts.append(year)
    return "-".join(part for part in parts if part)


def _filter_experiments_by_candidate_ids(
    experiments: List[Dict[str, Any]],
    candidate_ids: List[str],
) -> List[Dict[str, Any]]:
    if not candidate_ids:
        return experiments
    requested = [candidate_id for candidate_id in candidate_ids if candidate_id]
    requested_set = set(requested)
    filtered = [experiment for experiment in experiments if str(experiment.get("id")) in requested_set]
    missing = [candidate_id for candidate_id in requested if candidate_id not in {str(exp.get("id")) for exp in filtered}]
    if missing:
        raise ValueError(f"Unknown candidate_ids requested: {missing}")
    return filtered


def _load_completed_company_bundle(
    *,
    output_root: Path,
    company_run: Dict[str, Any],
    defaults: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    company_id = str(company_run.get("id") or _company_output_subdir(company_run, defaults))
    company_label = _company_run_label(company_run, defaults)
    company_output_dir = output_root / _company_output_subdir(company_run, defaults)
    result_path = company_output_dir / "results.json"
    if not result_path.exists():
        return None

    data = _load_json(result_path)
    return {
        "company_id": company_id,
        "company_label": company_label,
        "output_dir": str(company_output_dir),
        "full_eval_candidates": data.get("full_eval_candidates", []),
        "results": data.get("results", []),
        "recorded_matrix": data.get("recorded_matrix", {}),
    }


def _mean_or_none(values: List[float | None]) -> float | None:
    filtered = [float(value) for value in values if value is not None]
    return float(mean(filtered)) if filtered else None


def _critical_category_miss_count(result: Dict[str, Any]) -> int:
    misses = 0
    for row in result.get("screening_eval", {}).get("per_question", []):
        category = (row.get("category") or "").lower()
        if category in RISK_CATEGORIES | BUSINESS_CATEGORIES | NUMERIC_CATEGORIES and float(
            row.get("retrieval_hit_at_k", 0.0)
        ) == 0.0:
            misses += 1
    return misses


def _build_cross_company_rows(company_bundles: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for bundle in company_bundles:
        company_id = bundle["company_id"]
        company_label = bundle["company_label"]
        for result in bundle["results"]:
            config = result["config"]
            ingest = result.get("ingest", {})
            screen = result.get("screening_eval", {}).get("aggregate", {})
            full = result.get("full_eval", {}).get("aggregate", {})
            comparison = result.get("comparison_to_baseline", {})
            rows.append(
                {
                    "company_id": company_id,
                    "company": company_label,
                    "experiment_id": result["id"],
                    "screen_pass": bool(result.get("screen_pass")),
                    "critical_category_miss_count": _critical_category_miss_count(result),
                    "retrieval_hit_at_k": screen.get("retrieval_hit_at_k"),
                    "section_match_rate": screen.get("section_match_rate"),
                    "citation_coverage": screen.get("citation_coverage"),
                    "contamination_rate": screen.get("contamination_rate"),
                    "api_calls": ingest.get("api_calls", 0),
                    "estimated_ingest_cost_usd": result.get("estimated_ingest_cost_usd"),
                    "ingest_elapsed_sec": ingest.get("elapsed_sec", 0.0),
                    "api_call_reduction_ratio": comparison.get("api_call_reduction_ratio"),
                    "ingest_time_reduction_ratio": comparison.get("ingest_time_reduction_ratio"),
                    "estimated_cost_reduction_ratio": comparison.get("estimated_cost_reduction_ratio"),
                    "full_faithfulness": full.get("faithfulness"),
                    "full_context_recall": full.get("context_recall"),
                    "full_answer_relevancy": full.get("answer_relevancy"),
                    "full_retrieval_hit_at_k": full.get("retrieval_hit_at_k"),
                    "full_section_match_rate": full.get("section_match_rate"),
                    "full_citation_coverage": full.get("citation_coverage"),
                    "full_avg_score": full.get("avg_score"),
                    "screen_failure_reasons": result.get("screen_failure_reasons", []),
                    "screen_failure_examples": screen.get("failure_examples", []),
                    "ingest_mode": config.get("ingest_mode"),
                    "chunk_size": config.get("chunk_size"),
                    "chunk_overlap": config.get("chunk_overlap"),
                }
            )
    return rows


def _build_winner_ranking(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        experiment_id = row["experiment_id"]
        aggregate = grouped.setdefault(
            experiment_id,
            {
                "experiment_id": experiment_id,
                "company_count": 0,
                "pass_count": 0,
                "critical_category_miss_count": 0,
                "api_call_reduction_ratios": [],
                "ingest_time_reduction_ratios": [],
                "estimated_cost_reduction_ratios": [],
                "full_faithfulness_values": [],
                "full_context_recall_values": [],
                "screen_failures": [],
            },
        )
        aggregate["company_count"] += 1
        if row.get("screen_pass"):
            aggregate["pass_count"] += 1
        aggregate["critical_category_miss_count"] += int(row.get("critical_category_miss_count", 0) or 0)
        aggregate["api_call_reduction_ratios"].append(row.get("api_call_reduction_ratio"))
        aggregate["ingest_time_reduction_ratios"].append(row.get("ingest_time_reduction_ratio"))
        aggregate["estimated_cost_reduction_ratios"].append(row.get("estimated_cost_reduction_ratio"))
        aggregate["full_faithfulness_values"].append(row.get("full_faithfulness"))
        aggregate["full_context_recall_values"].append(row.get("full_context_recall"))
        if row.get("screen_failure_reasons"):
            aggregate["screen_failures"].append(
                {
                    "company": row["company"],
                    "reasons": row["screen_failure_reasons"],
                }
            )

    ranking: List[Dict[str, Any]] = []
    for aggregate in grouped.values():
        ranking.append(
            {
                "experiment_id": aggregate["experiment_id"],
                "company_count": aggregate["company_count"],
                "pass_count": aggregate["pass_count"],
                "critical_category_miss_count": aggregate["critical_category_miss_count"],
                "avg_api_call_reduction_ratio": _mean_or_none(aggregate["api_call_reduction_ratios"]),
                "avg_ingest_time_reduction_ratio": _mean_or_none(aggregate["ingest_time_reduction_ratios"]),
                "avg_estimated_cost_reduction_ratio": _mean_or_none(aggregate["estimated_cost_reduction_ratios"]),
                "avg_full_faithfulness": _mean_or_none(aggregate["full_faithfulness_values"]),
                "avg_full_context_recall": _mean_or_none(aggregate["full_context_recall_values"]),
                "screen_failures": aggregate["screen_failures"],
            }
        )

    ranking.sort(
        key=lambda row: (
            -int(row["pass_count"]),
            int(row["critical_category_miss_count"]),
            -float(row["avg_api_call_reduction_ratio"] if row["avg_api_call_reduction_ratio"] is not None else -1.0),
            -float(
                row["avg_ingest_time_reduction_ratio"] if row["avg_ingest_time_reduction_ratio"] is not None else -1.0
            ),
            -float(row["avg_full_faithfulness"] if row["avg_full_faithfulness"] is not None else -1.0),
            -float(row["avg_full_context_recall"] if row["avg_full_context_recall"] is not None else -1.0),
            row["experiment_id"],
        )
    )
    return ranking


def _write_cross_company_summary_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "company_id",
        "company",
        "experiment_id",
        "screen_pass",
        "critical_category_miss_count",
        "retrieval_hit_at_k",
        "section_match_rate",
        "citation_coverage",
        "contamination_rate",
        "api_calls",
        "estimated_ingest_cost_usd",
        "ingest_elapsed_sec",
        "api_call_reduction_ratio",
        "ingest_time_reduction_ratio",
        "estimated_cost_reduction_ratio",
        "full_faithfulness",
        "full_context_recall",
        "full_answer_relevancy",
        "full_retrieval_hit_at_k",
        "full_section_match_rate",
        "full_citation_coverage",
        "full_avg_score",
        "screen_failure_reasons",
        "screen_failure_examples",
    ]
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{key: row.get(key) for key in fieldnames},
                    "screen_failure_reasons": " | ".join(row.get("screen_failure_reasons", [])),
                    "screen_failure_examples": json.dumps(row.get("screen_failure_examples", []), ensure_ascii=False),
                }
            )


def _render_cross_company_summary_markdown(rows: List[Dict[str, Any]], ranking: List[Dict[str, Any]]) -> str:
    lines = [
        "# Cross-Company Summary",
        "",
        "## Per-Company Results",
        "",
        "| Company | Experiment | Screen Pass | Critical Misses | Hit@k | Section | Citation | Contam | API Calls | Est. Cost (USD) | Ingest (s) | API Δ | Time Δ | Cost Δ | Full Faithfulness | Full Recall |",
        "|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for row in rows:
        lines.append(
            "| {company} | {experiment_id} | {passed} | {critical} | {hit} | {section} | {citation} | {contam} | {api_calls} | {cost} | {ingest} | {api_delta} | {time_delta} | {cost_delta} | {faith} | {recall} |".format(
                company=row["company"],
                experiment_id=row["experiment_id"],
                passed="yes" if row.get("screen_pass") else "no",
                critical=int(row.get("critical_category_miss_count", 0) or 0),
                hit="-" if row.get("retrieval_hit_at_k") is None else f"{float(row['retrieval_hit_at_k']):.3f}",
                section="-" if row.get("section_match_rate") is None else f"{float(row['section_match_rate']):.3f}",
                citation="-" if row.get("citation_coverage") is None else f"{float(row['citation_coverage']):.3f}",
                contam="-" if row.get("contamination_rate") is None else f"{float(row['contamination_rate']):.3f}",
                api_calls=int(row.get("api_calls", 0) or 0),
                cost="-"
                if row.get("estimated_ingest_cost_usd") is None
                else f"{float(row['estimated_ingest_cost_usd']):.4f}",
                ingest=f"{float(row.get('ingest_elapsed_sec', 0.0) or 0.0):.3f}",
                api_delta="-" if row.get("api_call_reduction_ratio") is None else f"{float(row['api_call_reduction_ratio']):.1%}",
                time_delta="-" if row.get("ingest_time_reduction_ratio") is None else f"{float(row['ingest_time_reduction_ratio']):.1%}",
                cost_delta="-"
                if row.get("estimated_cost_reduction_ratio") is None
                else f"{float(row['estimated_cost_reduction_ratio']):.1%}",
                faith="-" if row.get("full_faithfulness") is None else f"{float(row['full_faithfulness']):.3f}",
                recall="-" if row.get("full_context_recall") is None else f"{float(row['full_context_recall']):.3f}",
            )
        )

    lines.extend(
        [
            "",
            "## Winner Ranking",
            "",
            "| Rank | Experiment | Pass Count | Company Count | Critical Misses | Avg API Δ | Avg Time Δ | Avg Cost Δ | Avg Faithfulness | Avg Recall |",
            "|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|",
        ]
    )

    for index, row in enumerate(ranking, start=1):
        lines.append(
            "| {rank} | {experiment_id} | {pass_count} | {company_count} | {critical} | {api_delta} | {time_delta} | {cost_delta} | {faith} | {recall} |".format(
                rank=index,
                experiment_id=row["experiment_id"],
                pass_count=int(row["pass_count"]),
                company_count=int(row["company_count"]),
                critical=int(row["critical_category_miss_count"]),
                api_delta="-"
                if row.get("avg_api_call_reduction_ratio") is None
                else f"{float(row['avg_api_call_reduction_ratio']):.1%}",
                time_delta="-"
                if row.get("avg_ingest_time_reduction_ratio") is None
                else f"{float(row['avg_ingest_time_reduction_ratio']):.1%}",
                cost_delta="-"
                if row.get("avg_estimated_cost_reduction_ratio") is None
                else f"{float(row['avg_estimated_cost_reduction_ratio']):.1%}",
                faith="-"
                if row.get("avg_full_faithfulness") is None
                else f"{float(row['avg_full_faithfulness']):.3f}",
                recall="-"
                if row.get("avg_full_context_recall") is None
                else f"{float(row['avg_full_context_recall']):.3f}",
            )
        )
        if row.get("screen_failures"):
            lines.append("")
            lines.append(f"Failure Notes for `{row['experiment_id']}`")
            for failure in row["screen_failures"]:
                lines.append(f"- {failure['company']}: {' | '.join(failure['reasons'])}")

    lines.extend(
        [
            "",
            "## Selection Policy",
            "",
            "The default candidate is ranked by:",
            "1. cross-company screening pass count",
            "2. critical category misses",
            "3. average API call reduction ratio",
            "4. average ingest time reduction ratio",
            "5. full evaluation faithfulness",
            "6. full evaluation context recall",
        ]
    )
    return "\n".join(lines) + "\n"


def _write_benchmark_outputs(
    *,
    output_dir: Path,
    config_path: Path,
    recorded_matrix: Dict[str, Any],
    screening_config: Dict[str, Any],
    full_eval_config: Dict[str, Any],
    selected_ids: List[str],
    results: List[Dict[str, Any]],
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(
        output_dir / "results.json",
        {
            "config_path": str(config_path),
            "recorded_matrix": recorded_matrix,
            "screening": screening_config,
            "full_evaluation": full_eval_config,
            "full_eval_candidates": selected_ids,
            "results": results,
        },
    )
    _write_summary_csv(output_dir / "summary.csv", results)
    (output_dir / "summary.md").write_text(_render_summary_markdown(results), encoding="utf-8")
    _write_review_csv(output_dir / "review.csv", results)
    (output_dir / "review.md").write_text(_render_review_markdown(results), encoding="utf-8")


def _write_multi_company_outputs(
    *,
    output_dir: Path,
    config_path: Path,
    defaults: Dict[str, Any],
    experiments: List[Dict[str, Any]],
    company_runs: List[Dict[str, Any]],
    screening_config: Dict[str, Any],
    full_eval_config: Dict[str, Any],
    company_bundles: List[Dict[str, Any]],
) -> None:
    cross_company_rows = _build_cross_company_rows(company_bundles)
    winner_ranking = _build_winner_ranking(cross_company_rows)
    completed_company_ids = [bundle["company_id"] for bundle in company_bundles]
    all_company_ids = [str(company_run.get("id") or _company_output_subdir(company_run, defaults)) for company_run in company_runs]
    pending_company_ids = [company_id for company_id in all_company_ids if company_id not in completed_company_ids]
    run_status = "completed" if not pending_company_ids else "partial"

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_cross_company_summary_csv(output_dir / "cross_company_summary.csv", cross_company_rows)
    (output_dir / "cross_company_summary.md").write_text(
        _render_cross_company_summary_markdown(cross_company_rows, winner_ranking),
        encoding="utf-8",
    )
    _write_json(
        output_dir / "results.json",
        {
            "config_path": str(config_path),
            "mode": "multi_company",
            "run_status": run_status,
            "completed_companies": completed_company_ids,
            "pending_companies": pending_company_ids,
            "recorded_matrix": {
                "defaults": _sanitize_settings(defaults),
                "screening": _sanitize_settings(screening_config),
                "full_evaluation": _sanitize_settings(full_eval_config),
                "experiments": [_sanitize_settings(experiment) for experiment in experiments],
                "company_runs": [_sanitize_settings(company_run) for company_run in company_runs],
            },
            "company_runs": company_bundles,
            "cross_company_summary": cross_company_rows,
            "winner_ranking": winner_ranking,
        },
    )


def _run_ingest(
    agent: FinancialAgent,
    chunks: List[Any],
    config: Dict[str, Any],
    *,
    return_artifacts: bool = False,
) -> Dict[str, Any]:
    ingest_mode = str(config.get("ingest_mode", "contextual_all"))
    max_workers = int(config.get("max_workers", DEFAULT_CONTEXT_MAX_WORKERS))
    batch_size = int(config.get("batch_size", DEFAULT_CONTEXT_BATCH_SIZE))
    if ingest_mode == "plain":
        started_at = time.perf_counter()
        if bool(config.get("use_zero_cost_prefix", False)):
            texts = [_build_zero_cost_prefixed_text(chunk.metadata, chunk.content) for chunk in chunks]
            metadatas = [chunk.metadata for chunk in chunks]
            agent.vsm.add_documents(texts, metadatas)
        else:
            agent.ingest(chunks)
        metrics = _build_plain_ingest_metrics(len(chunks), time.perf_counter() - started_at)
        metrics["use_zero_cost_prefix"] = bool(config.get("use_zero_cost_prefix", False))
        if return_artifacts:
            texts = (
                [_build_zero_cost_prefixed_text(chunk.metadata, chunk.content) for chunk in chunks]
                if bool(config.get("use_zero_cost_prefix", False))
                else [chunk.content for chunk in chunks]
            )
            metrics["artifacts"] = {
                "texts": texts,
                "metadatas": [chunk.metadata for chunk in chunks],
                "parents": {},
            }
        return metrics
    if ingest_mode in {"contextual", "contextual_all"}:
        metrics = agent.benchmark_contextual_ingest(
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
            return_artifacts=return_artifacts,
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
            return_artifacts=return_artifacts,
        )
    if ingest_mode == "contextual_parent_hybrid":
        return _benchmark_parent_hybrid_ingest(
            agent,
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
            short_text_threshold=int(config.get("parent_hybrid_short_text_threshold", 700)),
            targeted_sections=list(config.get("parent_hybrid_sections", [])),
            return_artifacts=return_artifacts,
        )
    if ingest_mode == "contextual_selective":
        return _benchmark_selective_ingest(
            agent,
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
            short_text_threshold=int(config.get("selective_short_text_threshold", 900)),
            targeted_sections=list(config.get("selective_sections", [])),
            return_artifacts=return_artifacts,
        )
    if ingest_mode == "contextual_selective_v2":
        return _benchmark_selective_v2_ingest(
            agent,
            chunks,
            max_workers=max_workers,
            batch_size=batch_size,
            short_text_threshold=int(config.get("selective_v2_short_text_threshold", 700)),
            targeted_sections=list(config.get("selective_v2_sections", [])),
            short_table_threshold=int(config.get("selective_v2_short_table_threshold", 1600)),
            use_zero_cost_prefix=bool(config.get("use_zero_cost_prefix", False)),
            return_artifacts=return_artifacts,
        )
    raise ValueError(f"Unsupported ingest_mode: {ingest_mode}")


def run_screening_experiment(
    config: Dict[str, Any],
    output_root: Path,
    screening_config: Dict[str, Any],
    full_eval_config: Dict[str, Any],
) -> Dict[str, Any]:
    experiment_id = config["id"]
    report_path = _normalise_path(config["report_path"])

    metadata = dict(config["metadata"])
    persist_dir = output_root / "stores" / _slugify(experiment_id)
    context_cache_path = _context_cache_path(output_root, experiment_id)
    force_reindex = _resolve_boolean_config(config, "force_reindex", False)
    reuse_store = _resolve_boolean_config(config, "reuse_store", True)
    reuse_context_cache = _resolve_boolean_config(config, "reuse_context_cache", True)

    collection_name = config.get("collection_name") or f"{DEFAULT_COLLECTION_NAME}_{_slugify(experiment_id)}"
    cache_signature = _build_cache_signature(config)
    cache_meta = _load_cache_meta(persist_dir) if persist_dir.exists() else {}
    context_cache = _load_context_cache(output_root, experiment_id)

    store_matches = _cache_meta_matches(cache_meta, cache_signature)
    context_matches = _cache_meta_matches(context_cache, cache_signature)

    if force_reindex:
        if persist_dir.exists():
            shutil.rmtree(persist_dir)
        if context_cache_path.exists():
            context_cache_path.unlink()
    elif persist_dir.exists() and (not reuse_store or not store_matches):
        shutil.rmtree(persist_dir)
        cache_meta = {}

    vsm = VectorStoreManager(
        persist_directory=str(persist_dir),
        collection_name=collection_name,
    )
    agent = FinancialAgent(
        vsm,
        k=int(config.get("k", 8)),
        graph_expansion_config=_build_graph_expansion_config(config),
    )

    store_cache_hit = (
        reuse_store
        and not force_reindex
        and store_matches
        and vsm.is_indexed(str(metadata.get("rcept_no", "")))
    )

    context_cache_hit = False
    cache_level = "none"

    if store_cache_hit:
        parse_info = cache_meta.get("parse", {})
        parse_elapsed = float(parse_info.get("elapsed_sec", 0.0) or 0.0)
        chunk_count = int(parse_info.get("chunk_count", 0) or 0)
        ingest_metrics = _build_cache_hit_ingest_metrics(cache_meta.get("ingest", {}))
        cache_level = "store"
    elif reuse_context_cache and not force_reindex and context_matches:
        restore_started = time.perf_counter()
        restore_info = _restore_store_from_context_cache(vsm, context_cache)
        restore_elapsed = time.perf_counter() - restore_started
        parse_info = context_cache.get("parse", {})
        parse_elapsed = float(parse_info.get("elapsed_sec", 0.0) or 0.0)
        chunk_count = int(parse_info.get("chunk_count", 0) or 0)
        ingest_metrics = _build_context_cache_restore_metrics(context_cache.get("ingest", {}), restore_elapsed)
        ingest_metrics["stored_parent_chunks"] = restore_info.get(
            "stored_parent_chunks",
            int(ingest_metrics.get("stored_parent_chunks", 0) or 0),
        )
        context_cache_hit = True
        cache_level = "context"
        _write_cache_meta(
            persist_dir,
            {
                "signature": cache_signature,
                "parse": {
                    "elapsed_sec": parse_elapsed,
                    "chunk_count": chunk_count,
                },
                "ingest": {
                    **(context_cache.get("ingest", {}) or {}),
                    "elapsed_sec": float((context_cache.get("ingest", {}) or {}).get("elapsed_sec", 0.0) or 0.0),
                },
                "metadata": _sanitize_settings(metadata),
                "collection_name": collection_name,
            },
        )
    else:
        if not report_path.exists():
            raise FileNotFoundError(f"report_path not found: {report_path}")
        parser = FinancialParser(
            chunk_size=int(config.get("chunk_size", DEFAULT_CHUNK_SIZE)),
            chunk_overlap=int(config.get("chunk_overlap", DEFAULT_CHUNK_OVERLAP)),
        )
        parse_started = time.perf_counter()
        chunks = parser.process_document(str(report_path), metadata)
        parse_elapsed = time.perf_counter() - parse_started
        chunk_count = len(chunks)
        ingest_metrics = _run_ingest(agent, chunks, config, return_artifacts=True)
        artifacts = dict(ingest_metrics.pop("artifacts", {}) or {})
        _write_cache_meta(
            persist_dir,
            {
                "signature": cache_signature,
                "parse": {
                    "elapsed_sec": parse_elapsed,
                    "chunk_count": chunk_count,
                },
                "ingest": {
                    **ingest_metrics,
                    "elapsed_sec": float(ingest_metrics.get("elapsed_sec", 0.0) or 0.0),
                },
                "metadata": _sanitize_settings(metadata),
                "collection_name": collection_name,
            },
        )
        _write_context_cache(
            output_root,
            experiment_id,
            {
                "signature": cache_signature,
                "parse": {
                    "elapsed_sec": parse_elapsed,
                    "chunk_count": chunk_count,
                },
                "ingest": {
                    **ingest_metrics,
                    "elapsed_sec": float(ingest_metrics.get("elapsed_sec", 0.0) or 0.0),
                },
                "metadata": _sanitize_settings(metadata),
                "collection_name": collection_name,
                "artifacts": artifacts,
            },
        )

    smoke = _run_smoke_queries(agent, list(config.get("smoke_queries", [])))
    screening_examples = _select_eval_examples(config, metadata)
    screening_eval = _run_screening_eval(agent, screening_examples, screening_config) if screening_examples else {}
    estimated_cost = _estimate_cost_usd(ingest_metrics, config.get("pricing"))

    return {
        "id": experiment_id,
        "config": {
            "chunk_size": config.get("chunk_size"),
            "chunk_overlap": config.get("chunk_overlap"),
            "ingest_mode": config.get("ingest_mode"),
            "graph_expansion": _sanitize_settings(config.get("graph_expansion", {})),
            "k": config.get("k", 8),
            "max_workers": config.get("max_workers"),
            "batch_size": config.get("batch_size"),
            "collection_name": collection_name,
            "parent_hybrid_short_text_threshold": config.get("parent_hybrid_short_text_threshold"),
            "parent_hybrid_sections": config.get("parent_hybrid_sections", []),
            "selective_short_text_threshold": config.get("selective_short_text_threshold"),
            "selective_sections": config.get("selective_sections", []),
            "selective_v2_short_text_threshold": config.get("selective_v2_short_text_threshold"),
            "selective_v2_short_table_threshold": config.get("selective_v2_short_table_threshold"),
            "selective_v2_sections": config.get("selective_v2_sections", []),
            "section_aliases": screening_config.get("section_aliases", {}),
        },
        "report_path": str(report_path),
        "metadata": metadata,
        "recorded_settings": _build_recorded_settings(config, screening_config, full_eval_config),
        "store": {
            "persist_directory": str(persist_dir),
            "collection_name": collection_name,
        },
        "parse": {
            "elapsed_sec": parse_elapsed,
            "chunk_count": chunk_count,
        },
        "ingest": ingest_metrics,
        "cache": {
            "cache_hit": store_cache_hit or context_cache_hit,
            "cache_level": cache_level,
            "force_reindex": force_reindex,
            "reuse_store": reuse_store,
            "reuse_context_cache": reuse_context_cache,
            "signature": cache_signature,
        },
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


def _attach_baseline_comparison(
    results: List[Dict[str, Any]],
    baseline_result: Optional[Dict[str, Any]],
) -> None:
    if not baseline_result:
        for result in results:
            result["comparison_to_baseline"] = {}
        return

    baseline_api_calls = int(baseline_result.get("ingest", {}).get("api_calls", 0) or 0)
    baseline_elapsed = float(baseline_result.get("ingest", {}).get("elapsed_sec", 0.0) or 0.0)
    baseline_cost = baseline_result.get("estimated_ingest_cost_usd")
    baseline_cost_value = float(baseline_cost) if baseline_cost is not None else None
    for result in results:
        api_calls = int(result.get("ingest", {}).get("api_calls", 0) or 0)
        ingest_elapsed = float(result.get("ingest", {}).get("elapsed_sec", 0.0) or 0.0)
        estimated_cost = result.get("estimated_ingest_cost_usd")
        estimated_cost_value = float(estimated_cost) if estimated_cost is not None else None
        result["comparison_to_baseline"] = {
            "api_call_reduction_ratio": (1.0 - (api_calls / baseline_api_calls)) if baseline_api_calls > 0 else None,
            "ingest_time_reduction_ratio": (1.0 - (ingest_elapsed / baseline_elapsed)) if baseline_elapsed > 0 else None,
            "estimated_cost_reduction_ratio": (
                1.0 - (estimated_cost_value / baseline_cost_value)
                if baseline_cost_value is not None and baseline_cost_value > 0 and estimated_cost_value is not None
                else None
            ),
        }


def _run_screening_experiments(
    merged_experiments: List[Dict[str, Any]],
    output_dir: Path,
    screening_config: Dict[str, Any],
    full_eval_config: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not merged_experiments:
        return []

    parallel_experiments = int(screening_config.get("parallel_experiments", 2) or 2)
    max_workers = max(1, min(parallel_experiments, len(merged_experiments)))

    if max_workers == 1:
        results_by_id: Dict[str, Dict[str, Any]] = {}
        for merged in merged_experiments:
            logger.info("Running screening benchmark: %s", merged["id"])
            results_by_id[merged["id"]] = run_screening_experiment(merged, output_dir, screening_config, full_eval_config)
        return [results_by_id[merged["id"]] for merged in merged_experiments]

    logger.info("Running screening benchmarks with parallel_experiments=%s", max_workers)
    results_by_id: Dict[str, Dict[str, Any]] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for merged in merged_experiments:
            logger.info("Queueing screening benchmark: %s", merged["id"])
            future = executor.submit(run_screening_experiment, merged, output_dir, screening_config, full_eval_config)
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
    agent = FinancialAgent(
        vsm,
        k=int(merged_config.get("k", 8)),
        graph_expansion_config=_build_graph_expansion_config(merged_config),
    )
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


def _run_company_bundle(
    *,
    config_path: Path,
    output_root: Path,
    global_defaults: Dict[str, Any],
    shared_experiments: List[Dict[str, Any]],
    screening_config: Dict[str, Any],
    full_eval_config: Dict[str, Any],
    company_run: Dict[str, Any],
) -> Dict[str, Any]:
    company_defaults = _deep_merge(global_defaults, company_run.get("defaults", {}))
    experiments = company_run.get("experiments", shared_experiments)
    if not experiments:
        raise ValueError("Each company run must resolve to at least one experiment.")

    company_id = str(company_run.get("id") or _company_output_subdir(company_run, global_defaults))
    company_label = _company_run_label(company_run, global_defaults)
    company_output_dir = output_root / _company_output_subdir(company_run, global_defaults)

    candidate_ids = list(company_run.get("candidate_ids") or global_defaults.get("candidate_ids") or [])
    experiments = _filter_experiments_by_candidate_ids(list(experiments), candidate_ids)
    if not experiments:
        raise ValueError(f"No experiments left after candidate_ids filter for company_run={company_id}")

    merged_experiments: List[Dict[str, Any]] = []
    merged_by_id: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        merged = _deep_merge(company_defaults, experiment)
        if "id" not in merged:
            raise ValueError(f"Each experiment must include an id. company_run={company_id}")
        merged_experiments.append(merged)
        merged_by_id[merged["id"]] = merged

    results = _run_screening_experiments(merged_experiments, company_output_dir, screening_config, full_eval_config)

    baseline_id = screening_config.get("baseline_experiment_id")
    baseline_result = next((result for result in results if result["id"] == baseline_id), None)
    if baseline_id and baseline_result is None:
        raise ValueError(f"baseline_experiment_id not found for {company_id}: {baseline_id}")
    baseline_aggregate = baseline_result.get("screening_eval", {}).get("aggregate", {}) if baseline_result else {}

    for result in results:
        reasons = _screen_failure_reasons(result, baseline_aggregate, screening_config)
        result["screen_failure_reasons"] = reasons
        result["screen_pass"] = len(reasons) == 0
    _attach_baseline_comparison(results, baseline_result)

    selected_ids: List[str] = []
    if full_eval_config.get("enabled", True):
        selected_ids = _select_full_eval_candidates(results, screening_config)
        for experiment_id in selected_ids:
            logger.info("Running full evaluation for %s: %s", company_id, experiment_id)
            result = next(result for result in results if result["id"] == experiment_id)
            result["full_eval"] = _run_full_evaluation(result, merged_by_id[experiment_id], full_eval_config)

    recorded_matrix = {
        "mode": "company_run",
        "company_run": {
            "id": company_id,
            "label": company_label,
            "defaults": _sanitize_settings(company_run.get("defaults", {})),
            "experiments": [_sanitize_settings(experiment) for experiment in experiments],
        },
        "defaults": _sanitize_settings(global_defaults),
        "screening": _sanitize_settings(screening_config),
        "full_evaluation": _sanitize_settings(full_eval_config),
    }

    _write_benchmark_outputs(
        output_dir=company_output_dir,
        config_path=config_path,
        recorded_matrix=recorded_matrix,
        screening_config=screening_config,
        full_eval_config=full_eval_config,
        selected_ids=selected_ids,
        results=results,
    )

    return {
        "company_id": company_id,
        "company_label": company_label,
        "output_dir": str(company_output_dir),
        "full_eval_candidates": selected_ids,
        "results": results,
        "recorded_matrix": recorded_matrix,
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
    parser.add_argument(
        "--company-run-id",
        action="append",
        default=[],
        help="Optional company_run id to execute. Repeat to run multiple companies as separate jobs.",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    config_path = _normalise_path(args.config)
    output_dir = _normalise_path(args.output_dir)
    matrix = _load_json(config_path)
    defaults = matrix.get("defaults", {})
    experiments = _filter_experiments_by_candidate_ids(
        matrix.get("experiments", []),
        list(matrix.get("candidate_ids") or defaults.get("candidate_ids") or []),
    )
    company_runs = matrix.get("company_runs", [])
    screening_config = matrix.get("screening", {})
    full_eval_config = matrix.get("full_evaluation", {})
    if not experiments:
        raise ValueError("No experiments found in benchmark config.")

    if company_runs:
        requested_company_ids = set(args.company_run_id or [])
        selected_company_runs = [
            company_run
            for company_run in company_runs
            if not requested_company_ids or str(company_run.get("id")) in requested_company_ids
        ]
        if requested_company_ids and len(selected_company_runs) != len(requested_company_ids):
            found_ids = {str(company_run.get("id")) for company_run in selected_company_runs}
            missing_ids = sorted(requested_company_ids - found_ids)
            raise ValueError(f"Unknown company_run ids requested: {missing_ids}")

        company_bundles: List[Dict[str, Any]] = []
        for company_run in selected_company_runs:
            logger.info("Running company benchmark: %s", company_run.get("id") or company_run.get("defaults", {}))
            company_bundles.append(
                _run_company_bundle(
                    config_path=config_path,
                    output_root=output_dir,
                    global_defaults=defaults,
                    shared_experiments=experiments,
                    screening_config=screening_config,
                    full_eval_config=full_eval_config,
                    company_run=company_run,
                )
            )

        completed_bundles: List[Dict[str, Any]] = []
        for company_run in company_runs:
            bundle = _load_completed_company_bundle(
                output_root=output_dir,
                company_run=company_run,
                defaults=defaults,
            )
            if bundle is not None:
                completed_bundles.append(bundle)

        _write_multi_company_outputs(
            output_dir=output_dir,
            config_path=config_path,
            defaults=defaults,
            experiments=experiments,
            company_runs=company_runs,
            screening_config=screening_config,
            full_eval_config=full_eval_config,
            company_bundles=completed_bundles,
        )
        logger.info("Wrote multi-company benchmark outputs to %s", output_dir)
        return

    merged_experiments: List[Dict[str, Any]] = []
    merged_by_id: Dict[str, Dict[str, Any]] = {}
    for experiment in experiments:
        merged = _deep_merge(defaults, experiment)
        if "id" not in merged:
            raise ValueError("Each experiment must include an id.")
        merged_experiments.append(merged)
        merged_by_id[merged["id"]] = merged

    results = _run_screening_experiments(merged_experiments, output_dir, screening_config, full_eval_config)

    baseline_id = screening_config.get("baseline_experiment_id")
    baseline_result = next((result for result in results if result["id"] == baseline_id), None)
    if baseline_id and baseline_result is None:
        raise ValueError(f"baseline_experiment_id not found: {baseline_id}")
    baseline_aggregate = baseline_result.get("screening_eval", {}).get("aggregate", {}) if baseline_result else {}

    for result in results:
        reasons = _screen_failure_reasons(result, baseline_aggregate, screening_config)
        result["screen_failure_reasons"] = reasons
        result["screen_pass"] = len(reasons) == 0
    _attach_baseline_comparison(results, baseline_result)

    selected_ids: List[str] = []
    if full_eval_config.get("enabled", True):
        selected_ids = _select_full_eval_candidates(results, screening_config)
        for experiment_id in selected_ids:
            logger.info("Running full evaluation: %s", experiment_id)
            result = next(result for result in results if result["id"] == experiment_id)
            result["full_eval"] = _run_full_evaluation(result, merged_by_id[experiment_id], full_eval_config)

    _write_benchmark_outputs(
        output_dir=output_dir,
        config_path=config_path,
        recorded_matrix={
            "mode": "single_company",
            "defaults": _sanitize_settings(defaults),
            "screening": _sanitize_settings(screening_config),
            "full_evaluation": _sanitize_settings(full_eval_config),
            "experiments": [_sanitize_settings(experiment) for experiment in experiments],
        },
        screening_config=screening_config,
        full_eval_config=full_eval_config,
        selected_ids=selected_ids,
        results=results,
    )
    logger.info("Wrote benchmark outputs to %s", output_dir)


if __name__ == "__main__":
    main()
