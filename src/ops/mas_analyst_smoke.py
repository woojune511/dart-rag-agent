"""
Smoke-test the MAS Analyst wrapper against the direct single-agent engine.

This is a migration acceptance check:
1. instantiate a real VectorStoreManager,
2. run direct FinancialAgent queries,
3. run the same questions through the MAS graph with an injected Analyst node,
4. compare core numeric outputs and artifact wiring.
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

from src.agent.financial_graph import FinancialAgent
from src.agent.mas_graph import run_mas_graph
from src.agent.nodes.analyst_node import build_financial_analyst_node
from src.storage.vector_store import VectorStoreManager

DEFAULT_STORE_DIR = (
    Path("benchmarks/results/reference_note_phase1a/삼성전자-2024/stores/reference-note-plain-graph-2500-320")
)
DEFAULT_COLLECTION = "dart_reports_v2_reference-note-plain-graph-2500-320"
DEFAULT_DATASET = Path("benchmarks/eval_dataset.math_focus.json")
DEFAULT_QUESTION_IDS = ["comparison_001", "comparison_004", "trend_002"]


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


def _artifact_answer(final_state: Dict[str, Any]) -> str:
    artifact = ((final_state.get("artifacts") or {}).get("task_1") or {})
    content = artifact.get("content") or {}
    return str(content.get("answer") or "")


def _artifact_calc_status(final_state: Dict[str, Any]) -> str:
    artifact = ((final_state.get("artifacts") or {}).get("task_1") or {})
    content = artifact.get("content") or {}
    calculation_result = content.get("calculation_result") or {}
    return str(calculation_result.get("status") or "")


def _artifact_operand_count(final_state: Dict[str, Any]) -> int:
    artifact = ((final_state.get("artifacts") or {}).get("task_1") or {})
    content = artifact.get("content") or {}
    operands = content.get("calculation_operands") or []
    return len(operands)


def _calc_payload(result: Dict[str, Any]) -> Dict[str, Any]:
    return dict(result.get("calculation_result") or {})


def _artifact_calc_payload(final_state: Dict[str, Any]) -> Dict[str, Any]:
    artifact = ((final_state.get("artifacts") or {}).get("task_1") or {})
    content = artifact.get("content") or {}
    return dict(content.get("calculation_result") or {})


def _numeric_result_match(left: Dict[str, Any], right: Dict[str, Any], tolerance: float = 1e-9) -> bool:
    left_unit = str(left.get("normalized_unit") or left.get("result_unit") or "")
    right_unit = str(right.get("normalized_unit") or right.get("result_unit") or "")
    if left_unit != right_unit:
        return False

    left_value = left.get("normalized_value", left.get("value"))
    right_value = right.get("normalized_value", right.get("value"))

    if isinstance(left_value, (int, float)) and isinstance(right_value, (int, float)):
        return abs(float(left_value) - float(right_value)) <= tolerance
    return left_value == right_value


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
    direct_agent = FinancialAgent(vsm, k=k)
    analyst_node = build_financial_analyst_node(vsm, k=k)
    questions = _load_questions(dataset_path, question_ids)

    cases: List[Dict[str, Any]] = []
    answer_match_count = 0
    calc_status_match_count = 0
    operand_count_match_count = 0
    numeric_result_match_count = 0

    for question in questions:
        text = str(question["question"])
        scope = _report_scope(question)
        direct = direct_agent.run(text, report_scope=scope)
        mas_final = run_mas_graph(
            text,
            report_scope=scope,
            analyst_node=analyst_node,
        )

        direct_answer = str(direct.get("answer") or "")
        mas_answer = _artifact_answer(mas_final)
        direct_calc_payload = _calc_payload(direct)
        mas_calc_payload = _artifact_calc_payload(mas_final)
        direct_calc_status = str(direct_calc_payload.get("status") or "")
        mas_calc_status = _artifact_calc_status(mas_final)
        direct_operand_count = len(direct.get("calculation_operands") or [])
        mas_operand_count = _artifact_operand_count(mas_final)
        mas_artifact = ((mas_final.get("artifacts") or {}).get("task_1") or {})
        evidence_links = list(mas_artifact.get("evidence_links") or [])

        answer_match = direct_answer == mas_answer
        calc_status_match = direct_calc_status == mas_calc_status
        operand_count_match = direct_operand_count == mas_operand_count
        numeric_result_match = _numeric_result_match(direct_calc_payload, mas_calc_payload)

        answer_match_count += int(answer_match)
        calc_status_match_count += int(calc_status_match)
        operand_count_match_count += int(operand_count_match)
        numeric_result_match_count += int(numeric_result_match)

        cases.append(
            {
                "id": question["id"],
                "question": text,
                "direct_answer": direct_answer,
                "mas_answer": mas_answer,
                "answer_match": answer_match,
                "direct_calc_status": direct_calc_status,
                "mas_calc_status": mas_calc_status,
                "calc_status_match": calc_status_match,
                "direct_calculation_result": direct_calc_payload,
                "mas_calculation_result": mas_calc_payload,
                "numeric_result_match": numeric_result_match,
                "direct_operand_count": direct_operand_count,
                "mas_operand_count": mas_operand_count,
                "operand_count_match": operand_count_match,
                "mas_evidence_link_count": len(evidence_links),
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
            "calc_status_match_rate": calc_status_match_count / total,
            "numeric_result_match_rate": numeric_result_match_count / total,
            "operand_count_match_rate": operand_count_match_count / total,
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Compare direct FinancialAgent vs MAS Analyst wrapper on a real store.")
    parser.add_argument("--store-dir", type=Path, default=DEFAULT_STORE_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--question-id", action="append", dest="question_ids")
    parser.add_argument("--k", type=int, default=8)
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
