"""
Run a real end-to-end MAS smoke with:
- Orchestrator_Plan
- Analyst
- Researcher
- Critic
- Orchestrator_Merge
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
from src.agent.nodes import (
    build_financial_analyst_node,
    build_financial_orchestrator_merge_node,
    build_financial_orchestrator_plan_node,
    build_financial_researcher_node,
)
from src.storage.vector_store import VectorStoreManager

DEFAULT_STORE_DIR = (
    Path("benchmarks/results/reference_note_phase1a/삼성전자-2024/stores/reference-note-plain-graph-2500-320")
)
DEFAULT_COLLECTION = "dart_reports_v2_reference-note-plain-graph-2500-320"
DEFAULT_SCOPE = {
    "company": "삼성전자",
    "report_type": "사업보고서",
    "rcept_no": "20250311001085",
    "year": "2024",
    "consolidation": "연결",
}
DEFAULT_QUERIES = [
    "삼성전자 2024 사업보고서에서 영업이익률은 얼마이고, 주요 재무 리스크는 무엇인가요?",
    "삼성전자 2024 사업보고서에서 연구개발비용 비중을 계산하고, 2024년 연구개발 성과 예시를 요약해줘.",
]


def _artifact_answer(artifact: Dict[str, Any]) -> str:
    content = artifact.get("content")
    if isinstance(content, dict):
        return str(content.get("answer") or "")
    return str(content or "")


def run_smoke(
    *,
    store_dir: Path,
    collection_name: str,
    queries: List[str],
    replan_budget: int = 0,
) -> Dict[str, Any]:
    vsm = VectorStoreManager(
        persist_directory=str(store_dir),
        collection_name=collection_name,
    )
    plan_node = build_financial_orchestrator_plan_node()
    merge_node = build_financial_orchestrator_merge_node()
    analyst_node = build_financial_analyst_node(vsm)
    researcher_node = build_financial_researcher_node(vsm)

    cases: List[Dict[str, Any]] = []
    for query in queries:
        final = run_mas_graph(
            query,
            report_scope=dict(DEFAULT_SCOPE),
            replan_budget=replan_budget,
            orchestrator_plan_node=plan_node,
            orchestrator_merge_node=merge_node,
            analyst_node=analyst_node,
            researcher_node=researcher_node,
        )
        artifacts = dict(final.get("artifacts") or {})
        tasks = dict(final.get("tasks") or {})
        critic_reports = list(final.get("critic_reports") or [])
        final_report_record = dict(final.get("final_report_record") or {})
        task_artifact_trace = dict(final.get("task_artifact_trace") or {})
        execution_trace = list(final.get("execution_trace") or [])
        cases.append(
            {
                "query": query,
                "task_count": len(tasks),
                "task_statuses": {task_id: str(task.get("status")) for task_id, task in tasks.items()},
                "critic_reports": critic_reports,
                "critic_feedback": final.get("critic_feedback"),
                "planner_feedback": final.get("planner_feedback"),
                "replan_budget": int(final.get("replan_budget", replan_budget) or 0),
                "replan_count": int(final.get("replan_count", 0) or 0),
                "replan_requested": final_report_record.get("status") == "replan_required",
                "replan_routed": "Orchestrator replanned" in " | ".join(execution_trace),
                "execution_trace": execution_trace,
                "final_report": final.get("final_report"),
                "final_report_record": final_report_record,
                "task_artifact_trace": task_artifact_trace,
                "task_artifact_integrity_status": task_artifact_trace.get("integrity_status"),
                "task_artifact_integrity_issue_count": task_artifact_trace.get("integrity_issue_count"),
                "artifact_answers": {
                    task_id: _artifact_answer(artifact)
                    for task_id, artifact in artifacts.items()
                },
            }
        )

    replan_routed_count = sum(1 for case in cases if case.get("replan_routed"))
    blocked_count = sum(
        1
        for case in cases
        if str((case.get("final_report_record") or {}).get("status") or "").strip() == "blocked"
    )
    integrity_error_count = sum(
        1
        for case in cases
        if str(case.get("task_artifact_integrity_status") or "").strip() == "error"
    )
    return {
        "store": {
            "persist_directory": str(store_dir),
            "collection_name": collection_name,
        },
        "report_scope": dict(DEFAULT_SCOPE),
        "replan_budget": int(replan_budget or 0),
        "case_count": len(cases),
        "summary": {
            "replan_routed_count": replan_routed_count,
            "blocked_count": blocked_count,
            "integrity_error_count": integrity_error_count,
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real end-to-end MAS smoke.")
    parser.add_argument("--store-dir", type=Path, default=DEFAULT_STORE_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--replan-budget", type=int, default=0)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = run_smoke(
        store_dir=args.store_dir,
        collection_name=args.collection_name,
        queries=args.queries or list(DEFAULT_QUERIES),
        replan_budget=args.replan_budget,
    )

    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
