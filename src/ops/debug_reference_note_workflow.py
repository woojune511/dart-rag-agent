from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from agent.financial_graph import FinancialAgent
from processing.financial_parser import FinancialParser
from storage.vector_store import VectorStoreManager

logger = logging.getLogger(__name__)


def _build_source_metadata(args: argparse.Namespace) -> Dict[str, Any]:
    return {
        "company": args.company,
        "stock_code": args.stock_code,
        "year": int(args.year),
        "report_type": args.report_type,
        "rcept_no": args.rcept_no,
    }


def _parser_reference_summary(chunks: List[Any]) -> Dict[str, Any]:
    reference_chunks = [
        chunk
        for chunk in chunks
        if list((chunk.metadata or {}).get("reference_section_paths") or [])
    ]
    relation_counter = Counter()
    sample_mappings: List[Dict[str, Any]] = []

    for chunk in reference_chunks[:12]:
        metadata = dict(chunk.metadata or {})
        refs = list(metadata.get("reference_section_paths") or [])
        relation_counter[metadata.get("section") or ""] += 1
        sample_mappings.append(
            {
                "chunk_uid": metadata.get("chunk_uid"),
                "section_path": metadata.get("section_path"),
                "block_type": metadata.get("block_type"),
                "references": refs,
                "preview": str(chunk.content or "")[:220],
            }
        )

    return {
        "total_chunks": len(chunks),
        "reference_chunk_count": len(reference_chunks),
        "reference_section_distribution": dict(relation_counter),
        "sample_mappings": sample_mappings,
    }


def _store_reference_summary(vsm: VectorStoreManager) -> Dict[str, Any]:
    nodes = dict((vsm._structure_graph or {}).get("nodes", {}) or {})
    reference_nodes = []
    sample_resolved_edges: List[Dict[str, Any]] = []

    for chunk_uid, node in nodes.items():
        metadata = dict((node or {}).get("metadata", {}) or {})
        reference_parent_ids = [
            str(value).strip()
            for value in (metadata.get("reference_parent_ids") or node.get("reference_parent_ids") or [])
            if str(value).strip()
        ]
        if not reference_parent_ids:
            continue
        reference_nodes.append((chunk_uid, node, reference_parent_ids))

    for chunk_uid, node, reference_parent_ids in reference_nodes[:8]:
        docs = vsm.get_reference_docs(chunk_uid=chunk_uid, limit=4)
        sample_resolved_edges.append(
            {
                "chunk_uid": chunk_uid,
                "section_path": dict((node or {}).get("metadata", {}) or {}).get("section_path"),
                "reference_parent_ids": reference_parent_ids,
                "resolved_reference_doc_count": len(docs),
                "resolved_reference_sections": [
                    dict(doc.metadata or {}).get("section_path") for doc in docs
                ],
            }
        )

    return {
        "structure_node_count": len(nodes),
        "reference_node_count": len(reference_nodes),
        "sample_resolved_edges": sample_resolved_edges,
    }


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


def _doc_summary(item: Any) -> Dict[str, Any]:
    doc, score = item
    metadata = dict(doc.metadata or {})
    return {
        "score": round(float(score), 4),
        "graph_relation": metadata.get("graph_relation"),
        "section_path": metadata.get("section_path"),
        "block_type": metadata.get("block_type"),
        "chunk_uid": metadata.get("chunk_uid"),
        "graph_reference_parent_id": metadata.get("graph_reference_parent_id"),
        "preview": str(doc.page_content or "")[:220],
    }


def _graph_smoke(agent: FinancialAgent, query: str) -> Dict[str, Any]:
    state = _initial_state(query)
    state.update(agent._classify_query(state))
    state.update(agent._extract_entities(state))
    state.update(agent._retrieve(state))

    before_expand = list(state.get("retrieved_docs") or [])
    state.update(agent._expand_via_structure_graph(state))
    after_expand = list(state.get("retrieved_docs") or [])

    relation_counter = Counter(
        str((doc.metadata or {}).get("graph_relation") or "seed")
        for doc, _ in after_expand
    )
    reference_docs = [
        _doc_summary(item)
        for item in after_expand
        if str((item[0].metadata or {}).get("graph_relation") or "") == "reference_note"
    ]

    answer_payload = agent.run(query)

    return {
        "query": query,
        "routing": {
            "intent": state.get("intent"),
            "format_preference": state.get("format_preference"),
            "routing_source": state.get("routing_source"),
            "routing_confidence": state.get("routing_confidence"),
        },
        "entity_extraction": {
            "companies": state.get("companies"),
            "years": state.get("years"),
            "topic": state.get("topic"),
            "section_filter": state.get("section_filter"),
        },
        "before_expand_count": len(before_expand),
        "after_expand_count": len(after_expand),
        "graph_relation_counts": dict(relation_counter),
        "top_seed_docs": [_doc_summary(item) for item in before_expand[:8]],
        "top_expanded_docs": [_doc_summary(item) for item in after_expand[:12]],
        "reference_docs": reference_docs,
        "answer": answer_payload.get("answer"),
        "citations": answer_payload.get("citations"),
    }


def _graph_config(k: int, include_reference_notes: bool) -> Dict[str, Any]:
    return {
        "enabled": True,
        "include_parent_context": True,
        "include_section_lead": True,
        "include_reference_notes": include_reference_notes,
        "include_described_by_paragraph": True,
        "include_table_context": True,
        "include_sibling_prev": True,
        "include_sibling_next": False,
        "table_sibling_prev_paragraph_only": True,
        "sibling_window": 1,
        "max_docs": max(k * 3, 12),
    }


def _run_post_expand(agent: FinancialAgent, state: Dict[str, Any]) -> Dict[str, Any]:
    route_after_expand = agent._route_after_expand(state)
    if route_after_expand == "numeric_extractor":
        state.update(agent._extract_numeric_fact(state))
        state.update(agent._format_citations(state))
        return state

    state.update(agent._extract_evidence(state))
    route_after_evidence = agent._route_after_evidence(state)
    if route_after_evidence == "operand_extractor":
        state.update(agent._extract_calculation_operands(state))
        state.update(agent._plan_formula_calculation(state))
        state.update(agent._execute_calculation(state))
        state.update(agent._render_calculation_answer(state))
        state.update(agent._format_citations(state))
        return state

    state.update(agent._compress_answer(state))
    state.update(agent._validate_answer(state))
    state.update(agent._format_citations(state))
    return state


def _summarize_branch(
    state: Dict[str, Any],
    before_expand: List[Any],
) -> Dict[str, Any]:
    after_expand = list(state.get("retrieved_docs") or [])
    relation_counter = Counter(
        str((doc.metadata or {}).get("graph_relation") or "seed")
        for doc, _ in after_expand
    )
    reference_docs = [
        _doc_summary(item)
        for item in after_expand
        if str((item[0].metadata or {}).get("graph_relation") or "") == "reference_note"
    ]
    return {
        "before_expand_count": len(before_expand),
        "after_expand_count": len(after_expand),
        "graph_relation_counts": dict(relation_counter),
        "top_seed_docs": [_doc_summary(item) for item in before_expand[:8]],
        "top_expanded_docs": [_doc_summary(item) for item in after_expand[:12]],
        "reference_docs": reference_docs,
        "answer": state.get("answer"),
        "citations": state.get("citations"),
        "evidence_status": state.get("evidence_status"),
    }


def _graph_smoke_seed_fixed_compare(
    vsm: VectorStoreManager,
    query: str,
    k: int,
) -> Dict[str, Any]:
    seed_agent = FinancialAgent(
        vsm,
        k=k,
        graph_expansion_config=_graph_config(k, include_reference_notes=False),
    )
    seed_state = _initial_state(query)
    seed_state.update(seed_agent._classify_query(seed_state))
    seed_state.update(seed_agent._extract_entities(seed_state))
    seed_state.update(seed_agent._retrieve(seed_state))
    before_expand = list(seed_state.get("retrieved_docs") or [])

    branches: Dict[str, Any] = {}
    for label, include_reference_notes in (("off", False), ("on", True)):
        branch_agent = FinancialAgent(
            vsm,
            k=k,
            graph_expansion_config=_graph_config(k, include_reference_notes=include_reference_notes),
        )
        branch_state = copy.deepcopy(seed_state)
        branch_state.update(branch_agent._expand_via_structure_graph(branch_state))
        branch_state = _run_post_expand(branch_agent, branch_state)
        branches[label] = _summarize_branch(branch_state, before_expand)

    return {
        "query": query,
        "routing": {
            "intent": seed_state.get("intent"),
            "format_preference": seed_state.get("format_preference"),
            "routing_source": seed_state.get("routing_source"),
            "routing_confidence": seed_state.get("routing_confidence"),
        },
        "entity_extraction": {
            "companies": seed_state.get("companies"),
            "years": seed_state.get("years"),
            "topic": seed_state.get("topic"),
            "section_filter": seed_state.get("section_filter"),
        },
        "shared_seed": {
            "count": len(before_expand),
            "top_seed_docs": [_doc_summary(item) for item in before_expand[:8]],
        },
        "branches": branches,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Inspect REFERENCE_NOTE Phase 1a at parser level and, optionally, through graph expansion."
    )
    parser.add_argument("--report-path", required=True, help="Path to the DART report HTML/XML file.")
    parser.add_argument("--company", required=True, help="Company name for parser metadata.")
    parser.add_argument("--stock-code", default="", help="Stock code for parser metadata.")
    parser.add_argument("--year", type=int, required=True, help="Report year.")
    parser.add_argument("--report-type", default="사업보고서", help="Report type metadata.")
    parser.add_argument("--rcept-no", required=True, help="DART receipt number for metadata.")
    parser.add_argument("--chunk-size", type=int, default=2500, help="Parser chunk size.")
    parser.add_argument("--chunk-overlap", type=int, default=320, help="Parser chunk overlap.")
    parser.add_argument("--store-dir", help="Optional Chroma persist directory for graph smoke.")
    parser.add_argument("--collection-name", help="Optional Chroma collection name for graph smoke.")
    parser.add_argument("--k", type=int, default=8, help="Retriever top-k for graph smoke.")
    parser.add_argument(
        "--disable-reference-notes",
        action="store_true",
        help="Disable reference_note graph expansion for A/B comparison.",
    )
    parser.add_argument(
        "--seed-fixed-compare-reference-notes",
        action="store_true",
        help="Run classify/extract/retrieve once per question, then compare expand+downstream with reference_note off vs on.",
    )
    parser.add_argument("--question", action="append", default=[], help="Question(s) for graph smoke. Repeatable.")
    parser.add_argument("--output", help="Optional path to write JSON output.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

    report_path = Path(args.report_path)
    if not report_path.exists():
        raise FileNotFoundError(f"report_path not found: {report_path}")

    financial_parser = FinancialParser(chunk_size=args.chunk_size, chunk_overlap=args.chunk_overlap)
    source_metadata = _build_source_metadata(args)
    chunks = financial_parser.process_document(str(report_path), source_metadata)

    result: Dict[str, Any] = {
        "report_path": str(report_path),
        "parser": _parser_reference_summary(chunks),
    }

    if args.store_dir or args.collection_name or args.question:
        if not (args.store_dir and args.collection_name):
            raise ValueError("--store-dir and --collection-name are required for any store-level inspection.")
        vsm = VectorStoreManager(
            persist_directory=args.store_dir,
            collection_name=args.collection_name,
        )
        result["store"] = _store_reference_summary(vsm)

        if args.question:
            if not os.environ.get("GOOGLE_API_KEY"):
                raise ValueError("GOOGLE_API_KEY is required for graph smoke because the agent reuses LLM-based routing/extraction.")
            agent = FinancialAgent(
                vsm,
                k=args.k,
                graph_expansion_config={
                    "enabled": True,
                    "include_parent_context": True,
                    "include_section_lead": True,
                    "include_reference_notes": not args.disable_reference_notes,
                    "include_described_by_paragraph": True,
                    "include_table_context": True,
                    "include_sibling_prev": True,
                    "include_sibling_next": False,
                    "table_sibling_prev_paragraph_only": True,
                    "sibling_window": 1,
                    "max_docs": max(args.k * 3, 12),
                },
            )
            result["graph_smoke_config"] = {
                "include_reference_notes": not args.disable_reference_notes,
                "k": args.k,
            }
            if args.seed_fixed_compare_reference_notes:
                result["graph_smoke_compare"] = [
                    _graph_smoke_seed_fixed_compare(vsm, question, args.k) for question in args.question
                ]
            else:
                result["graph_smoke"] = [_graph_smoke(agent, question) for question in args.question]

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(str(output_path))
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
