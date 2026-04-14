"""
Benchmark runner for chunking / retrieval / ingest trade-off experiments.
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent.financial_graph import DEFAULT_CONTEXT_BATCH_SIZE, DEFAULT_CONTEXT_MAX_WORKERS, FinancialAgent
from ops.evaluator import RAGEvaluator
from processing.financial_parser import DEFAULT_CHUNK_OVERLAP, DEFAULT_CHUNK_SIZE, FinancialParser
from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

logger = logging.getLogger(__name__)


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


def _run_smoke_queries(agent: FinancialAgent, queries: List[str]) -> Dict[str, Any]:
    rows: List[Dict[str, Any]] = []
    for query in queries:
        started_at = time.perf_counter()
        result = agent.run(query)
        elapsed_sec = time.perf_counter() - started_at
        rows.append(
            {
                "query": query,
                "latency_sec": elapsed_sec,
                "query_type": result.get("query_type"),
                "retrieved_count": len(result.get("retrieved_docs", [])),
                "citation_count": len(result.get("citations", [])),
                "answer_preview": (result.get("answer", "") or "")[:240],
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


def _select_eval_examples(
    evaluator: RAGEvaluator,
    config: Dict[str, Any],
    report_metadata: Dict[str, Any],
) -> List[Any]:
    dataset_path = config.get("eval_dataset_path")
    if not dataset_path:
        return []

    examples = evaluator.load_dataset()
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
        return evaluator.build_single_company_eval_slice(filtered, max_questions=eval_limit)

    return filtered[:eval_limit] if eval_limit > 0 else filtered


def _build_plain_ingest_metrics(chunk_count: int, elapsed_sec: float) -> Dict[str, Any]:
    return {
        "mode": "plain",
        "chunks": chunk_count,
        "stored_parent_chunks": 0,
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


def _render_summary_markdown(results: List[Dict[str, Any]]) -> str:
    lines = [
        "# Benchmark Summary",
        "",
        "| Experiment | Chunk | Overlap | Mode | Parse (s) | Ingest (s) | Chunks | API Calls | Prompt Tokens | Output Tokens | Est. Cost (USD) | Faithfulness | Relevancy | Recall | Hit@k | Section | Citation |",
        "|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]

    for result in results:
        config = result["config"]
        ingest = result["ingest"]
        aggregate = result.get("eval", {}).get("aggregate", {})
        estimated_cost = result.get("estimated_ingest_cost_usd")
        lines.append(
            "| {id} | {chunk} | {overlap} | {mode} | {parse:.3f} | {ingest_sec:.3f} | {chunks} | {api_calls} | {prompt_tokens} | {output_tokens} | {cost} | {faith:.3f} | {rel:.3f} | {recall:.3f} | {hit:.3f} | {section:.3f} | {citation:.3f} |".format(
                id=result["id"],
                chunk=config.get("chunk_size"),
                overlap=config.get("chunk_overlap"),
                mode=config.get("ingest_mode"),
                parse=result["parse"]["elapsed_sec"],
                ingest_sec=ingest.get("elapsed_sec", 0.0),
                chunks=result["parse"]["chunk_count"],
                api_calls=ingest.get("api_calls", 0),
                prompt_tokens=ingest.get("prompt_tokens", 0),
                output_tokens=ingest.get("output_tokens", 0),
                cost="-" if estimated_cost is None else f"{estimated_cost:.6f}",
                faith=aggregate.get("faithfulness", 0.0),
                rel=aggregate.get("answer_relevancy", 0.0),
                recall=aggregate.get("context_recall", 0.0),
                hit=aggregate.get("retrieval_hit_at_k", 0.0),
                section=aggregate.get("section_match_rate", 0.0),
                citation=aggregate.get("citation_coverage", 0.0),
            )
        )

    lines.extend(
        [
            "",
            "## Reading Guide",
            "",
            "- `Ingest (s)` captures the document indexing path, which is currently the main latency bottleneck.",
            "- `Prompt Tokens` and `Output Tokens` are taken from contextual ingest responses when available.",
            "- `Est. Cost (USD)` is only filled when pricing is provided in the benchmark config.",
            "- The best default is usually the run that sits on the best speed/quality frontier, not the single highest metric.",
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
        "api_calls",
        "prompt_tokens",
        "output_tokens",
        "estimated_ingest_cost_usd",
        "smoke_avg_latency_sec",
        "smoke_avg_retrieved_count",
        "faithfulness",
        "answer_relevancy",
        "context_recall",
        "retrieval_hit_at_k",
        "section_match_rate",
        "citation_coverage",
        "avg_score",
        "avg_latency",
    ]
    with open(path, "w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        for result in results:
            config = result["config"]
            ingest = result["ingest"]
            smoke = result.get("smoke", {}).get("summary", {})
            aggregate = result.get("eval", {}).get("aggregate", {})
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
                    "api_calls": ingest.get("api_calls", 0),
                    "prompt_tokens": ingest.get("prompt_tokens", 0),
                    "output_tokens": ingest.get("output_tokens", 0),
                    "estimated_ingest_cost_usd": result.get("estimated_ingest_cost_usd"),
                    "smoke_avg_latency_sec": smoke.get("avg_latency_sec"),
                    "smoke_avg_retrieved_count": smoke.get("avg_retrieved_count"),
                    "faithfulness": aggregate.get("faithfulness"),
                    "answer_relevancy": aggregate.get("answer_relevancy"),
                    "context_recall": aggregate.get("context_recall"),
                    "retrieval_hit_at_k": aggregate.get("retrieval_hit_at_k"),
                    "section_match_rate": aggregate.get("section_match_rate"),
                    "citation_coverage": aggregate.get("citation_coverage"),
                    "avg_score": aggregate.get("avg_score"),
                    "avg_latency": aggregate.get("avg_latency"),
                }
            )


def run_experiment(config: Dict[str, Any], output_root: Path) -> Dict[str, Any]:
    experiment_id = config["id"]
    report_path = Path(config["report_path"])
    if not report_path.is_absolute():
        report_path = (PROJECT_ROOT / report_path).resolve()
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

    ingest_mode = config.get("ingest_mode", "contextual")
    if ingest_mode == "contextual":
        ingest_metrics = agent.benchmark_contextual_ingest(
            chunks,
            max_workers=int(config.get("max_workers", DEFAULT_CONTEXT_MAX_WORKERS)),
            batch_size=int(config.get("batch_size", DEFAULT_CONTEXT_BATCH_SIZE)),
        )
    elif ingest_mode == "plain":
        ingest_started = time.perf_counter()
        agent.ingest(chunks)
        ingest_metrics = _build_plain_ingest_metrics(len(chunks), time.perf_counter() - ingest_started)
    else:
        raise ValueError(f"Unsupported ingest_mode: {ingest_mode}")

    smoke = _run_smoke_queries(agent, list(config.get("smoke_queries", [])))

    eval_payload: Dict[str, Any] = {}
    eval_dataset_path = config.get("eval_dataset_path")
    if eval_dataset_path:
        evaluator = RAGEvaluator(
            agent,
            dataset_path=str((PROJECT_ROOT / eval_dataset_path).resolve()) if not Path(eval_dataset_path).is_absolute() else eval_dataset_path,
            experiment_name=config.get("mlflow_experiment_name", "dart_rag_benchmark"),
        )
        examples = _select_eval_examples(evaluator, config, metadata)
        if examples:
            eval_results = evaluator.run(
                examples=examples,
                run_name=experiment_id,
                params={
                    "chunk_size": config.get("chunk_size"),
                    "chunk_overlap": config.get("chunk_overlap"),
                    "ingest_mode": ingest_mode,
                    "k": config.get("k", 8),
                    "max_workers": config.get("max_workers"),
                    "batch_size": config.get("batch_size"),
                    "collection_name": collection_name,
                },
            )
            eval_payload = {
                "question_count": len(examples),
                "aggregate": eval_results["aggregate"],
                "per_question": _serialise_eval_results(eval_results["per_question"]),
            }

    estimated_cost = _estimate_cost_usd(ingest_metrics, config.get("pricing"))

    return {
        "id": experiment_id,
        "config": {
            "chunk_size": config.get("chunk_size"),
            "chunk_overlap": config.get("chunk_overlap"),
            "ingest_mode": ingest_mode,
            "k": config.get("k", 8),
            "max_workers": config.get("max_workers"),
            "batch_size": config.get("batch_size"),
            "collection_name": collection_name,
        },
        "report_path": str(report_path),
        "metadata": metadata,
        "parse": {
            "elapsed_sec": parse_elapsed,
            "chunk_count": len(chunks),
        },
        "ingest": ingest_metrics,
        "estimated_ingest_cost_usd": estimated_cost,
        "smoke": smoke,
        "eval": eval_payload,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run benchmark experiments for DART RAG settings.")
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

    config_path = Path(args.config)
    if not config_path.is_absolute():
        config_path = (PROJECT_ROOT / config_path).resolve()
    output_dir = Path(args.output_dir)
    if not output_dir.is_absolute():
        output_dir = (PROJECT_ROOT / output_dir).resolve()

    matrix = _load_json(config_path)
    defaults = matrix.get("defaults", {})
    experiments = matrix.get("experiments", [])
    if not experiments:
        raise ValueError("No experiments found in benchmark config.")

    results: List[Dict[str, Any]] = []
    for experiment in experiments:
        merged = _deep_merge(defaults, experiment)
        if "id" not in merged:
            raise ValueError("Each experiment must include an id.")
        logger.info("Running benchmark: %s", merged["id"])
        results.append(run_experiment(merged, output_dir))

    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "results.json", {"config_path": str(config_path), "results": results})
    _write_summary_csv(output_dir / "summary.csv", results)
    (output_dir / "summary.md").write_text(_render_summary_markdown(results), encoding="utf-8")

    logger.info("Wrote benchmark outputs to %s", output_dir)


if __name__ == "__main__":
    main()
