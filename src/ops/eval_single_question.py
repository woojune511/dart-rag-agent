"""
Evaluate a single question against an existing benchmark store.

Usage:
    python src/ops/eval_single_question.py \
        --source-result benchmarks/results/calc_render_fix_2026-04-27/삼성전자-2024/results.json \
        --question-id comparison_001 \
        --dataset benchmarks/eval_dataset.math_focus.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if __package__ in {None, ""} and str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


def _load_json(path: Path):
    with open(path, encoding="utf-8") as file:
        return json.load(file)


def _looks_like_windows_absolute_path(path_text: str) -> bool:
    return len(path_text) >= 3 and path_text[1] == ":" and path_text[2] in {"\\", "/"}


def _normalise_path(path_value: str | Path) -> Path:
    path_text = str(path_value)
    path = Path(path_text)
    if not path.is_absolute() and not _looks_like_windows_absolute_path(path_text):
        path = (PROJECT_ROOT / path).resolve()
    parts_lower = [part.lower() for part in path.parts]
    for index in range(len(parts_lower) - 1):
        if parts_lower[index] == "data" and parts_lower[index + 1] == "reports":
            return (PROJECT_ROOT / "data" / "reports" / Path(*path.parts[index + 2 :])).resolve()
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate a single question using an existing benchmark store.")
    parser.add_argument("--source-result", required=True, help="Path to existing results.json from a full benchmark run.")
    parser.add_argument("--question-id", required=True, help="Question id to evaluate (e.g. comparison_001).")
    parser.add_argument("--dataset", required=True, help="Path to eval dataset JSON.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    source_result_path = _normalise_path(args.source_result)
    payload = _load_json(source_result_path)
    results = list(payload.get("results", []) or [])
    if not results:
        raise ValueError(f"No results found in {source_result_path}")

    result = results[0]
    experiment_id = result.get("id", "")
    store = result.get("store", {})
    persist_dir = store.get("persist_directory", "")
    collection_name = store.get("collection_name", "")
    metadata = result.get("metadata", {})

    logger.info("Experiment: %s", experiment_id)
    logger.info("Store: %s", persist_dir)
    logger.info("Collection: %s", collection_name)

    # Build agent pointing to the existing store
    import os
    os.environ.setdefault("CHROMA_PERSIST_DIRECTORY", persist_dir)

    from src.agent.financial_graph import FinancialAgent
    from src.ops.evaluator import RAGEvaluator, load_eval_examples_from_path
    from src.storage.vector_store import VectorStoreManager

    vsm = VectorStoreManager(
        persist_directory=persist_dir,
        collection_name=collection_name,
    )
    agent = FinancialAgent(vector_store_manager=vsm)

    dataset_path = _normalise_path(args.dataset)
    all_examples = load_eval_examples_from_path(dataset_path)
    examples = [ex for ex in all_examples if ex.id == args.question_id]
    if not examples:
        raise ValueError(f"Question id '{args.question_id}' not found in {dataset_path}")

    evaluator = RAGEvaluator(agent=agent, dataset_path=str(dataset_path))
    result_out = evaluator.run(examples=examples, run_name=f"single_{args.question_id}")

    per_q = result_out.get("per_question", [])
    aggregate = result_out.get("aggregate", {})

    print("\n" + "=" * 60)
    print(f"Question: {args.question_id}")
    print("=" * 60)
    for q in per_q:
        # per_question은 EvalResult dataclass
        get = lambda attr: getattr(q, attr, None)
        print(f"  faithfulness         : {get('faithfulness')}")
        print(f"  raw_faithfulness     : {get('raw_faithfulness')}")
        print(f"  faith_override_reason: {get('faithfulness_override_reason')}")
        print(f"  numeric_equivalence  : {get('numeric_equivalence')}")
        print(f"  numeric_grounding    : {get('numeric_grounding')}")
        print(f"  numeric_retrieval_sup: {get('numeric_retrieval_support')}")
        print(f"  numeric_final_judgem : {get('numeric_final_judgement')}")
        print(f"  retrieval_hit_at_k   : {get('retrieval_hit_at_k')}")
        trace = get("retrieval_debug_trace") or {}
        print(f"  retrieval_trace_keys : {', '.join(sorted(trace.keys())) if trace else '-'}")
        print(f"  retrieval_selected   : {trace.get('selected_count') if trace else None}")
        print(f"  retrieval_candidates : {trace.get('candidate_count') if trace else None}")
        executed = trace.get("executed_queries") or []
        if executed:
            first_query = executed[0]
            print(f"  retrieval_first_query: {(first_query.get('executed_query') or '')[:200]}")
            print(f"  retrieval_filter     : {first_query.get('where_filter')}")
        print(f"  operand_selection    : {get('operand_selection_correctness')}")
        print(f"  numeric_result       : {get('numeric_result_correctness')}")
        print(f"  completeness         : {get('completeness')}")
        print(f"  answer               : {(get('answer') or '')[:200]}")
        if get('error'):
            print(f"  ERROR                : {get('error')}")

    print("\nAggregate:")
    for k, v in aggregate.items():
        if v is not None:
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
