from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

from src.routing import QueryRouter, default_canonical_queries_path
from src.storage.vector_store import DEFAULT_EMBEDDING_MODEL, create_embeddings


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CASES_PATH = ROOT / "benchmarks" / "golden" / "routing_confusion_cases_v1.json"
DEFAULT_OUTPUT_DIR = ROOT / "benchmarks" / "results"

load_dotenv()


def _load_json(path: Path) -> Any:
    return json.loads(path.resolve().read_text(encoding="utf-8"))


def _display_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(ROOT))
    except ValueError:
        return str(resolved)


def _render_markdown(summary: Dict[str, Any], rows: List[Dict[str, Any]]) -> str:
    lines = [
        "# Routing Confusion Check",
        "",
        "## Summary",
        "",
        f"- Canonical file: `{summary['canonical_path']}`",
        f"- Cases: `{summary['total_cases']}`",
        f"- Final intent accuracy: `{summary['intent_accuracy']:.3f}`",
        f"- Final format accuracy: `{summary['format_accuracy']:.3f}`",
        f"- Routing source accuracy: `{summary['routing_source_accuracy']:.3f}`",
        f"- Semantic top-1 accuracy: `{summary['semantic_top1_accuracy']:.3f}`",
        f"- Fast-path count: `{summary['fast_path_count']}`",
        f"- Fallback count: `{summary['fallback_count']}`",
        "",
        "## Case Results",
        "",
        "| Case | Expected Intent | Final Intent | Expected Source | Final Source | Semantic Top-1 | Pass | Query |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            f"| {row['case_id']} | {row['expected_intent']} | {row['final_intent']} | "
            f"{row.get('expected_routing_source') or '-'} | {row['final_routing_source']} | "
            f"{row['semantic_top1']} | {'yes' if row['case_pass'] else 'no'} | {row['query']} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run routing confusion-pair regression checks.")
    parser.add_argument(
        "--canonical",
        type=Path,
        default=default_canonical_queries_path(),
        help="Canonical routing query JSON path.",
    )
    parser.add_argument(
        "--cases",
        type=Path,
        default=DEFAULT_CASES_PATH,
        help="Routing confusion cases JSON path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / "routing_confusion_check",
        help="Directory to write summary artifacts.",
    )
    args = parser.parse_args()

    cases: List[Dict[str, Any]] = _load_json(args.cases)
    embeddings = create_embeddings(model_name=DEFAULT_EMBEDDING_MODEL)
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
    router = QueryRouter(embeddings=embeddings, llm=llm, canonical_queries_path=args.canonical)

    rows: List[Dict[str, Any]] = []
    intent_correct = 0
    format_correct = 0
    source_total = 0
    source_correct = 0
    semantic_correct = 0
    fast_path_count = 0
    fallback_count = 0

    for case in cases:
        query = str(case["query"])
        semantic = router.semantic_route(query)
        routed = router.route(query)

        final_intent = str(routed.intent)
        final_format = str(routed.format_preference)
        final_source = str(routed.routing_source)
        semantic_top1 = str(semantic.get("intent") or "")

        is_intent_correct = final_intent == case["expected_intent"]
        is_format_correct = final_format == case["expected_format_preference"]
        if case.get("expected_routing_source"):
            source_total += 1
            if final_source == case["expected_routing_source"]:
                source_correct += 1
            is_source_correct = final_source == case["expected_routing_source"]
        else:
            is_source_correct = True
        is_semantic_correct = semantic_top1 == case["expected_intent"]
        case_pass = is_intent_correct and is_format_correct and is_source_correct

        intent_correct += int(is_intent_correct)
        format_correct += int(is_format_correct)
        semantic_correct += int(is_semantic_correct)
        fast_path_count += int(final_source == "semantic_fast_path")
        fallback_count += int(final_source == "llm_fallback")

        rows.append(
            {
                "case_id": case["case_id"],
                "query": query,
                "confusion_pair": case.get("confusion_pair"),
                "note": case.get("note"),
                "expected_intent": case["expected_intent"],
                "expected_format_preference": case["expected_format_preference"],
                "expected_routing_source": case.get("expected_routing_source"),
                "semantic_top1": semantic_top1,
                "semantic_top2": semantic.get("second_intent") or "",
                "semantic_confidence": round(float(semantic.get("confidence") or 0.0), 4),
                "semantic_margin": round(float(semantic.get("margin") or 0.0), 4),
                "semantic_required_margin": round(float(semantic.get("required_margin") or 0.0), 4),
                "semantic_fast_path": bool(semantic.get("fast_path")),
                "final_intent": final_intent,
                "final_format_preference": final_format,
                "final_routing_source": final_source,
                "final_routing_confidence": round(float(routed.routing_confidence or 0.0), 4),
                "final_routing_scores": routed.routing_scores,
                "intent_pass": is_intent_correct,
                "format_pass": is_format_correct,
                "routing_source_pass": is_source_correct,
                "semantic_top1_pass": is_semantic_correct,
                "case_pass": case_pass,
            }
        )

    total_cases = len(rows)
    summary = {
        "canonical_path": _display_path(args.canonical),
        "cases_path": _display_path(args.cases),
        "total_cases": total_cases,
        "intent_accuracy": intent_correct / total_cases if total_cases else 0.0,
        "format_accuracy": format_correct / total_cases if total_cases else 0.0,
        "routing_source_accuracy": source_correct / source_total if source_total else 0.0,
        "semantic_top1_accuracy": semantic_correct / total_cases if total_cases else 0.0,
        "fast_path_count": fast_path_count,
        "fallback_count": fallback_count,
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "results.json").write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    (args.output_dir / "summary.md").write_text(_render_markdown(summary, rows), encoding="utf-8")


if __name__ == "__main__":
    main()
