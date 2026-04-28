"""
Targeted debugger for calculation workflow failures.

Runs the same retrieve -> evidence -> operand -> plan path as the agent,
but prints intermediate artifacts for a small set of questions so we can
see exactly where operands are lost.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from agent.financial_graph import FinancialAgent
from storage.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


def _initial_state(query: str) -> Dict[str, Any]:
    return {
        "query": query,
        "query_type": "",
        "intent": "",
        "target_metric_family": "",
        "format_preference": "",
        "routing_source": "",
        "routing_confidence": 0.0,
        "routing_scores": {},
        "companies": [],
        "years": [],
        "topic": "",
        "section_filter": None,
        "seed_retrieved_docs": [],
        "retrieved_docs": [],
        "evidence_bullets": [],
        "evidence_items": [],
        "evidence_status": "missing",
        "selected_claim_ids": [],
        "draft_points": [],
        "compressed_answer": "",
        "kept_claim_ids": [],
        "dropped_claim_ids": [],
        "unsupported_sentences": [],
        "sentence_checks": [],
        "answer": "",
        "citations": [],
        "numeric_debug_trace": {},
        "calculation_operands": [],
        "calculation_plan": {},
        "calculation_result": {},
        "calculation_debug_trace": {},
        "planner_debug_trace": {},
    }


def _doc_summary(doc_tuple: Any) -> Dict[str, Any]:
    doc, score = doc_tuple
    metadata = dict(doc.metadata or {})
    return {
        "score": round(float(score), 4),
        "section_path": metadata.get("section_path"),
        "section": metadata.get("section"),
        "block_type": metadata.get("block_type"),
        "graph_relation": metadata.get("graph_relation"),
        "preview": str(doc.page_content or "")[:220],
    }


def _candidate_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "source_anchor": item.get("source_anchor"),
        "source_context": item.get("source_context"),
        "matched_metric": item.get("matched_metric"),
        "matched_value": item.get("matched_value"),
        "matched_unit": item.get("matched_unit"),
        "raw_row_text": str(item.get("raw_row_text") or "")[:280],
    }


def _evidence_summary(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "evidence_id": item.get("evidence_id"),
        "source_anchor": item.get("source_anchor"),
        "support_level": item.get("support_level"),
        "question_relevance": item.get("question_relevance"),
        "parent_category": item.get("parent_category"),
        "source_context": item.get("source_context"),
        "claim": str(item.get("claim") or "")[:280],
        "raw_row_text": str(item.get("raw_row_text") or "")[:280] if item.get("raw_row_text") else None,
    }


def debug_question(agent: FinancialAgent, query: str) -> Dict[str, Any]:
    state = _initial_state(query)

    state.update(agent._classify_query(state))
    state.update(agent._extract_entities(state))
    state.update(agent._retrieve(state))
    state.update(agent._expand_via_structure_graph(state))

    evidence_result = agent._extract_evidence(state)
    state.update(evidence_result)

    candidate_docs = state.get("seed_retrieved_docs") or state.get("retrieved_docs") or []
    ratio_row_candidates = agent._extract_ratio_row_candidates(candidate_docs, state["query"], state.get("topic") or state["query"])
    component_candidates = agent._extract_ratio_component_candidates(candidate_docs, state["query"], state.get("topic") or state["query"])

    operands_result = agent._extract_calculation_operands(state)
    state.update(operands_result)

    plan_result = agent._plan_formula_calculation(state)
    state.update(plan_result)

    calc_result = agent._execute_calculation(state)
    state.update(calc_result)

    return {
        "query": query,
        "routing": {
            "intent": state.get("intent"),
            "target_metric_family": state.get("target_metric_family"),
            "format_preference": state.get("format_preference"),
            "routing_source": state.get("routing_source"),
            "routing_confidence": state.get("routing_confidence"),
            "routing_scores": state.get("routing_scores"),
        },
        "extraction": {
            "companies": state.get("companies"),
            "years": state.get("years"),
            "topic": state.get("topic"),
            "section_filter": state.get("section_filter"),
        },
        "retrieved_docs": [_doc_summary(item) for item in (state.get("retrieved_docs") or [])],
        "seed_retrieved_docs": [_doc_summary(item) for item in (state.get("seed_retrieved_docs") or [])[:12]],
        "evidence_status": state.get("evidence_status"),
        "evidence_items": [_evidence_summary(item) for item in (state.get("evidence_items") or [])],
        "ratio_row_candidates": [_candidate_summary(item) for item in ratio_row_candidates],
        "component_candidates": [_candidate_summary(item) for item in component_candidates],
        "calculation_debug_trace": state.get("calculation_debug_trace"),
        "planner_debug_trace": state.get("planner_debug_trace"),
        "calculation_operands": state.get("calculation_operands"),
        "calculation_plan": state.get("calculation_plan"),
        "calculation_result": state.get("calculation_result"),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Debug targeted math workflow questions.")
    parser.add_argument("--store-dir", required=True, help="Path to an existing Chroma persist directory.")
    parser.add_argument("--collection-name", required=True, help="Chroma collection name.")
    parser.add_argument("--k", type=int, default=8, help="Retriever top-k.")
    parser.add_argument("--question", action="append", required=True, help="Question to debug. Repeat for multiple.")
    parser.add_argument("--output", help="Optional path to write JSON output.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    vsm = VectorStoreManager(
        persist_directory=args.store_dir,
        collection_name=args.collection_name,
    )
    agent = FinancialAgent(vsm, k=args.k)

    results = [
        debug_question(agent, question)
        for question in args.question
    ]

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(output_path))
    else:
        print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
