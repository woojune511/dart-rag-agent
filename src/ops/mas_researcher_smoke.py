"""
Smoke-test the MAS Researcher wrapper against the direct narrative core.

This is the Researcher-side migration acceptance check:
1. instantiate a real VectorStoreManager,
2. run direct NarrativeResearcherCore queries,
3. run the same questions through the MAS graph with an injected Researcher node,
4. compare narrative outputs and grounding wiring.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.mas_graph import run_mas_graph
from src.agent.nodes.researcher_node import (
    NarrativeResearcherCore,
    build_financial_researcher_node,
)
from src.storage.vector_store import VectorStoreManager

DEFAULT_STORE_DIR = (
    Path("benchmarks/results/reference_note_phase1a/삼성전자-2024/stores/reference-note-plain-graph-2500-320")
)
DEFAULT_COLLECTION = "dart_reports_v2_reference-note-plain-graph-2500-320"
DEFAULT_DATASET = Path("benchmarks/eval_dataset.canonical.json")
DEFAULT_QUESTION_IDS = [
    "business_overview_001",
    "risk_analysis_001",
    "r_and_d_investment_002",
]


def _load_questions(dataset_path: Path, question_ids: List[str]) -> List[Dict[str, Any]]:
    payload = json.loads(dataset_path.read_text(encoding="utf-8"))
    question_map = {item["id"]: item for item in payload}
    missing = [qid for qid in question_ids if qid not in question_map]
    if missing:
        raise KeyError(f"Unknown question ids: {missing}")
    return [question_map[qid] for qid in question_ids]


def _report_scope(question: Dict[str, Any]) -> Dict[str, str]:
    return {
        "company": str(question.get("company") or ""),
        "report_type": "사업보고서",
        "rcept_no": "20250311001085",
        "year": str(question.get("year") or ""),
        "consolidation": "연결",
    }


def _research_instruction(question: str) -> str:
    return f"{question}\n\n이 질문과 관련된 맥락/원인을 짧게 요약해줘."


def _artifact_content(final_state: Dict[str, Any]) -> Dict[str, Any]:
    artifact = ((final_state.get("artifacts") or {}).get("task_2") or {})
    content = artifact.get("content") or {}
    if isinstance(content, dict):
        return dict(content)
    return {"answer": str(content or "")}


def _artifact_answer(final_state: Dict[str, Any]) -> str:
    return str(_artifact_content(final_state).get("answer") or "")


def _artifact_citations(final_state: Dict[str, Any]) -> List[str]:
    return list(_artifact_content(final_state).get("citations") or [])


def _artifact_evidence_links(final_state: Dict[str, Any]) -> List[str]:
    artifact = ((final_state.get("artifacts") or {}).get("task_2") or {})
    return list(artifact.get("evidence_links") or [])


def _critic_report_for_task(final_state: Dict[str, Any], task_id: str) -> Dict[str, Any]:
    for report in final_state.get("critic_reports") or []:
        if str(report.get("target_task_id") or "") == task_id:
            return dict(report)
    return {}


def run_smoke(
    *,
    store_dir: Path,
    collection_name: str,
    dataset_path: Path,
    question_ids: List[str],
    k: int,
) -> Dict[str, Any]:
    vsm = VectorStoreManager(
        persist_directory=str(store_dir),
        collection_name=collection_name,
    )
    direct_core = NarrativeResearcherCore(vsm, k=k)
    researcher_node = build_financial_researcher_node(vsm, k=k)
    questions = _load_questions(dataset_path, question_ids)

    cases: List[Dict[str, Any]] = []
    answer_match_count = 0
    citation_match_count = 0
    evidence_link_nonempty_count = 0
    critic_pass_count = 0

    for question in questions:
        original_question = str(question["question"] or "")
        instruction = _research_instruction(original_question)
        scope = _report_scope(question)

        direct = direct_core.run(instruction, report_scope=scope)
        mas_final = run_mas_graph(
            original_question,
            report_scope=scope,
            researcher_node=researcher_node,
        )

        direct_answer = str(direct.get("answer") or "")
        mas_answer = _artifact_answer(mas_final)
        direct_citations = list(direct.get("citations") or [])
        mas_citations = _artifact_citations(mas_final)
        evidence_links = _artifact_evidence_links(mas_final)
        critic_report = _critic_report_for_task(mas_final, "task_2")
        critic_passed = bool(critic_report.get("passed", False))

        answer_match = direct_answer == mas_answer
        citation_match = direct_citations == mas_citations
        evidence_link_nonempty = bool(evidence_links)

        answer_match_count += int(answer_match)
        citation_match_count += int(citation_match)
        evidence_link_nonempty_count += int(evidence_link_nonempty)
        critic_pass_count += int(critic_passed)

        cases.append(
            {
                "id": question["id"],
                "question": original_question,
                "instruction": instruction,
                "direct_answer": direct_answer,
                "mas_answer": mas_answer,
                "answer_match": answer_match,
                "direct_citations": direct_citations,
                "mas_citations": mas_citations,
                "citation_match": citation_match,
                "mas_evidence_link_count": len(evidence_links),
                "evidence_link_nonempty": evidence_link_nonempty,
                "critic_report": critic_report,
                "critic_passed": critic_passed,
                "mas_execution_trace": list(mas_final.get("execution_trace") or []),
            }
        )

    total = max(len(cases), 1)
    return {
        "store": {
            "persist_directory": str(store_dir),
            "collection_name": collection_name,
            "k": k,
        },
        "question_ids": question_ids,
        "summary": {
            "case_count": len(cases),
            "answer_match_rate": answer_match_count / total,
            "citation_match_rate": citation_match_count / total,
            "evidence_link_nonempty_rate": evidence_link_nonempty_count / total,
            "critic_pass_rate": critic_pass_count / total,
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare direct NarrativeResearcherCore vs MAS Researcher wrapper.")
    parser.add_argument("--store-dir", type=Path, default=DEFAULT_STORE_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--question-id", action="append", dest="question_ids")
    parser.add_argument("--k", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = run_smoke(
        store_dir=args.store_dir,
        collection_name=args.collection_name,
        dataset_path=args.dataset,
        question_ids=args.question_ids or list(DEFAULT_QUESTION_IDS),
        k=args.k,
    )

    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
