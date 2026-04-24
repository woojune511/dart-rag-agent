from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from itertools import product
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple

from langchain_huggingface import HuggingFaceEmbeddings

from src.storage.vector_store import DEFAULT_EMBEDDING_MODEL


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CANONICAL_PATH = ROOT / "benchmarks" / "golden" / "query_routing_canonical_v1.json"
DEFAULT_EVAL_PATH = ROOT / "benchmarks" / "golden" / "query_routing_eval_v1.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"


@dataclass
class ExampleScore:
    query_id: str
    query: str
    true_intent: str
    true_format_preference: str
    top_intent: str
    top_score: float
    second_intent: str
    second_score: float
    margin: float
    scores: Dict[str, float]


def _cosine_similarity(left: Sequence[float], right: Sequence[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = sum(float(a) * float(a) for a in left) ** 0.5
    right_norm = sum(float(b) * float(b) for b in right) ** 0.5
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_canonical_examples(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    examples: List[Dict[str, Any]] = []
    for entry in payload:
        intent = str(entry.get("id") or "").strip()
        queries = [str(query).strip() for query in entry.get("queries", []) if str(query).strip()]
        for query in queries:
            examples.append({"intent": intent, "query": query})
    if not examples:
        raise ValueError(f"No canonical routing queries found in {path}")
    return examples


def _load_eval_examples(path: Path) -> List[Dict[str, Any]]:
    payload = _load_json(path)
    examples: List[Dict[str, Any]] = []
    for entry in payload:
        query = str(entry.get("query") or "").strip()
        intent = str(entry.get("intent") or "").strip()
        format_preference = str(entry.get("format_preference") or "").strip()
        query_id = str(entry.get("query_id") or "").strip() or f"query_{len(examples)+1:03d}"
        if not query or not intent or not format_preference:
            continue
        examples.append(
            {
                "query_id": query_id,
                "query": query,
                "intent": intent,
                "format_preference": format_preference,
            }
        )
    if not examples:
        raise ValueError(f"No eval routing examples found in {path}")
    return examples


def _score_examples(
    embeddings: HuggingFaceEmbeddings,
    canonical_examples: List[Dict[str, Any]],
    eval_examples: List[Dict[str, Any]],
) -> List[ExampleScore]:
    canonical_queries = [entry["query"] for entry in canonical_examples]
    eval_queries = [entry["query"] for entry in eval_examples]

    canonical_vectors = embeddings.embed_documents(canonical_queries)
    eval_vectors = embeddings.embed_documents(eval_queries)

    enriched_canonical = []
    for entry, embedding in zip(canonical_examples, canonical_vectors):
        enriched_canonical.append(
            {
                "intent": entry["intent"],
                "query": entry["query"],
                "embedding": embedding,
            }
        )

    scored: List[ExampleScore] = []
    for entry, query_vector in zip(eval_examples, eval_vectors):
        best_score_by_intent: Dict[str, float] = {}
        for canonical in enriched_canonical:
            intent = canonical["intent"]
            score = _cosine_similarity(query_vector, canonical["embedding"])
            if score > best_score_by_intent.get(intent, float("-inf")):
                best_score_by_intent[intent] = score

        ranked = sorted(best_score_by_intent.items(), key=lambda item: item[1], reverse=True)
        top_intent, top_score = ranked[0]
        second_intent, second_score = ranked[1] if len(ranked) > 1 else ("", 0.0)
        scored.append(
            ExampleScore(
                query_id=entry["query_id"],
                query=entry["query"],
                true_intent=entry["intent"],
                true_format_preference=entry["format_preference"],
                top_intent=top_intent,
                top_score=float(top_score),
                second_intent=second_intent,
                second_score=float(second_score),
                margin=float(top_score - second_score),
                scores={intent: round(score, 6) for intent, score in ranked},
            )
        )

    return scored


def _evaluate_thresholds(
    scored_examples: List[ExampleScore],
    score_threshold: float,
    margin_threshold: float,
) -> Dict[str, Any]:
    fast_path = [
        example
        for example in scored_examples
        if example.top_score >= score_threshold and example.margin >= margin_threshold
    ]
    total = len(scored_examples)
    fast_total = len(fast_path)
    correct_fast = sum(1 for example in fast_path if example.top_intent == example.true_intent)

    per_intent: Dict[str, Dict[str, Any]] = {}
    for example in fast_path:
        bucket = per_intent.setdefault(
            example.true_intent,
            {
                "fast_total": 0,
                "correct": 0,
                "mismatches": [],
            },
        )
        bucket["fast_total"] += 1
        if example.top_intent == example.true_intent:
            bucket["correct"] += 1
        else:
            bucket["mismatches"].append(
                {
                    "query_id": example.query_id,
                    "query": example.query,
                    "predicted_intent": example.top_intent,
                    "score": round(example.top_score, 4),
                    "margin": round(example.margin, 4),
                }
            )

    return {
        "score_threshold": round(score_threshold, 4),
        "margin_threshold": round(margin_threshold, 4),
        "total_examples": total,
        "fast_path_total": fast_total,
        "fallback_total": total - fast_total,
        "fast_path_coverage": round(fast_total / total, 4) if total else 0.0,
        "fast_path_correct": correct_fast,
        "fast_path_accuracy": round(correct_fast / fast_total, 4) if fast_total else 0.0,
        "per_intent": per_intent,
    }


def _pick_recommended(results: List[Dict[str, Any]], min_precision: float) -> Dict[str, Any]:
    qualified = [result for result in results if result["fast_path_accuracy"] >= min_precision]
    pool = qualified if qualified else results
    return max(
        pool,
        key=lambda result: (
            result["fast_path_accuracy"],
            result["fast_path_coverage"],
            -result["margin_threshold"],
            -result["score_threshold"],
        ),
    )


def _render_markdown(
    scored_examples: List[ExampleScore],
    current_result: Dict[str, Any],
    recommended_result: Dict[str, Any],
    ambiguous_examples: List[ExampleScore],
) -> str:
    lines = [
        "# Query Router Calibration",
        "",
        "## Summary",
        "",
        f"- Current threshold: `score >= {current_result['score_threshold']:.2f}`, `margin >= {current_result['margin_threshold']:.2f}`",
        f"- Current fast-path coverage: `{current_result['fast_path_coverage']:.3f}`",
        f"- Current fast-path accuracy: `{current_result['fast_path_accuracy']:.3f}`",
        f"- Recommended threshold: `score >= {recommended_result['score_threshold']:.2f}`, `margin >= {recommended_result['margin_threshold']:.2f}`",
        f"- Recommended fast-path coverage: `{recommended_result['fast_path_coverage']:.3f}`",
        f"- Recommended fast-path accuracy: `{recommended_result['fast_path_accuracy']:.3f}`",
        "",
        "## Ambiguous Queries",
        "",
        "| Query ID | True Intent | Top-1 | Score | Top-2 | Margin | Query |",
        "| --- | --- | --- | ---: | --- | ---: | --- |",
    ]
    for example in ambiguous_examples:
        lines.append(
            f"| {example.query_id} | {example.true_intent} | {example.top_intent} | {example.top_score:.3f} | "
            f"{example.second_intent or '-'} | {example.margin:.3f} | {example.query} |"
        )

    lines.extend(
        [
            "",
            "## Current Threshold Misroutes",
            "",
            "| Query ID | True Intent | Predicted | Score | Margin | Query |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    current_misroutes = [
        example
        for example in scored_examples
        if example.top_score >= current_result["score_threshold"]
        and example.margin >= current_result["margin_threshold"]
        and example.top_intent != example.true_intent
    ]
    if current_misroutes:
        for example in current_misroutes:
            lines.append(
                f"| {example.query_id} | {example.true_intent} | {example.top_intent} | {example.top_score:.3f} | "
                f"{example.margin:.3f} | {example.query} |"
            )
    else:
        lines.append("| - | - | - | - | - | No fast-path misroutes at current threshold |")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate semantic router thresholds using a held-out routing dataset.")
    parser.add_argument("--canonical-path", type=Path, default=DEFAULT_CANONICAL_PATH)
    parser.add_argument("--eval-path", type=Path, default=DEFAULT_EVAL_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-name", type=str, default="query_router_calibration_2026-04-24")
    parser.add_argument("--embedding-model", type=str, default=DEFAULT_EMBEDDING_MODEL)
    parser.add_argument("--min-precision", type=float, default=0.95)
    args = parser.parse_args()

    canonical_examples = _load_canonical_examples(args.canonical_path)
    eval_examples = _load_eval_examples(args.eval_path)
    embeddings = HuggingFaceEmbeddings(model_name=args.embedding_model)

    scored_examples = _score_examples(embeddings, canonical_examples, eval_examples)

    score_thresholds = [round(value, 2) for value in [0.76, 0.78, 0.80, 0.82, 0.84, 0.86, 0.88, 0.90]]
    margin_thresholds = [round(value, 2) for value in [0.00, 0.02, 0.04, 0.06, 0.08, 0.10]]
    results = [
        _evaluate_thresholds(scored_examples, score_threshold, margin_threshold)
        for score_threshold, margin_threshold in product(score_thresholds, margin_thresholds)
    ]

    current_result = _evaluate_thresholds(scored_examples, 0.86, 0.04)
    recommended_result = _pick_recommended(results, args.min_precision)

    ambiguous_examples = sorted(
        scored_examples,
        key=lambda example: (example.margin, -example.top_score, example.query_id),
    )[:10]

    output_dir = args.output_dir / args.output_name
    output_dir.mkdir(parents=True, exist_ok=True)

    (output_dir / "scores.json").write_text(
        json.dumps(
            [
                {
                    "query_id": example.query_id,
                    "query": example.query,
                    "true_intent": example.true_intent,
                    "true_format_preference": example.true_format_preference,
                    "top_intent": example.top_intent,
                    "top_score": round(example.top_score, 6),
                    "second_intent": example.second_intent,
                    "second_score": round(example.second_score, 6),
                    "margin": round(example.margin, 6),
                    "scores": example.scores,
                }
                for example in scored_examples
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "grid_search.json").write_text(
        json.dumps(
            {
                "current": current_result,
                "recommended": recommended_result,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (output_dir / "summary.md").write_text(
        _render_markdown(scored_examples, current_result, recommended_result, ambiguous_examples),
        encoding="utf-8",
    )

    print(f"[router-calibration] wrote results to {output_dir}")
    print(
        "[router-calibration] current="
        f"score>={current_result['score_threshold']:.2f}, margin>={current_result['margin_threshold']:.2f}, "
        f"coverage={current_result['fast_path_coverage']:.3f}, accuracy={current_result['fast_path_accuracy']:.3f}"
    )
    print(
        "[router-calibration] recommended="
        f"score>={recommended_result['score_threshold']:.2f}, margin>={recommended_result['margin_threshold']:.2f}, "
        f"coverage={recommended_result['fast_path_coverage']:.3f}, accuracy={recommended_result['fast_path_accuracy']:.3f}"
    )


if __name__ == "__main__":
    main()
