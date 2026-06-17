"""Probe MAS planner tasks directly against worker cores.

This diagnostic sits between the full MAS smoke and focused worker unit tests:
it uses the real planner task instructions, then runs Analyst and Researcher
cores directly so material-empty failures can be separated from Critic/final
merge behavior.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from langchain_core.documents import Document

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_helpers import (
    _resolve_runtime_calculation_trace,
    _resolve_runtime_structured_result,
)
from src.experimental.mas.graph import build_initial_state
from src.experimental.mas.nodes import (
    NarrativeResearcherCore,
    build_financial_orchestrator_plan_node,
)
from src.experimental.mas.diagnostics import (
    build_researcher_probe_query,
    build_researcher_probe_where_filter,
    select_researcher_probe_docs,
)
from src.ops.mas_e2e_smoke import DEFAULT_COLLECTION, DEFAULT_QUERIES, DEFAULT_SCOPE, DEFAULT_STORE_DIR
from src.storage.vector_store import VectorStoreManager


PlannerNode = Callable[[Dict[str, Any]], Dict[str, Any]]


def _doc_count(items: Sequence[Any]) -> int:
    count = 0
    for item in items or []:
        doc = item[0] if isinstance(item, tuple) and item else item
        if isinstance(doc, Document):
            count += 1
    return count


def _store_inventory(vector_store_manager: Any) -> Dict[str, Any]:
    chroma_count: int | None = None
    chroma_error = ""
    try:
        collection = getattr(getattr(vector_store_manager, "vector_store", None), "_collection", None)
        if collection is not None and hasattr(collection, "count"):
            chroma_count = int(collection.count())
    except Exception as exc:
        chroma_error = str(exc)
    structure_graph = getattr(vector_store_manager, "_structure_graph", {}) or {}
    return {
        "chroma_count": chroma_count,
        "chroma_count_error": chroma_error,
        "bm25_doc_count": len(list(getattr(vector_store_manager, "bm25_docs", []) or [])),
        "parent_count": len(dict(getattr(vector_store_manager, "_parents", {}) or {})),
        "structure_graph_node_count": len(list(dict(structure_graph).get("nodes") or [])),
    }


def _planned_tasks(
    query: str,
    *,
    report_scope: Dict[str, Any],
    planner_node: PlannerNode,
) -> List[Dict[str, Any]]:
    state = build_initial_state(query, report_scope=dict(report_scope or {}))
    updates = planner_node(state)
    tasks = dict(updates.get("tasks") or {})
    return [dict(task) for task in tasks.values() if isinstance(task, dict)]


def _task_projection(task: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "task_id": str(task.get("task_id") or "").strip(),
        "assignee": str(task.get("assignee") or "").strip(),
        "kind": str(task.get("kind") or "").strip(),
        "label": str(task.get("label") or task.get("instruction") or "").strip(),
        "instruction": str(task.get("instruction") or "").strip(),
    }


def _analyst_material_status(result: Dict[str, Any]) -> Dict[str, Any]:
    answer = str(result.get("answer") or "").strip()
    resolved_trace = _resolve_runtime_calculation_trace(
        result,
        allow_legacy_top_level=False,
    )
    structured_result = _resolve_runtime_structured_result(result)
    calc_result = dict(structured_result or resolved_trace.get("calculation_result") or {})
    calc_status = str(calc_result.get("status") or "").strip().lower()
    calculation_plan = dict(resolved_trace.get("calculation_plan") or {})
    calculation_operands = list(resolved_trace.get("calculation_operands") or [])
    retrieved_doc_count = _doc_count(
        list(result.get("seed_retrieved_docs") or []) + list(result.get("retrieved_docs") or [])
    )
    evidence_item_count = len(list(result.get("evidence_items") or []))

    success = bool(
        answer
        and calculation_plan
        and calculation_operands
        and (not calc_status or calc_status in {"ok", "success"})
    )
    if success:
        status = "ok"
    elif retrieved_doc_count <= 0:
        status = "no_retrieved_docs"
    elif not calculation_operands:
        status = "retrieved_without_operands"
    elif not calculation_plan:
        status = "missing_calculation_plan"
    elif calc_status and calc_status not in {"ok", "success"}:
        status = "calculation_status_not_ok"
    elif not answer:
        status = "missing_answer"
    else:
        status = "incomplete_numeric_result"

    return {
        "material_status": status,
        "material_success": success,
        "answer_nonempty": bool(answer),
        "answer_excerpt": answer[:300],
        "calculation_status": calc_status,
        "calculation_plan_present": bool(calculation_plan),
        "operand_count": len(calculation_operands),
        "retrieved_doc_count": retrieved_doc_count,
        "evidence_item_count": evidence_item_count,
    }


def _researcher_retrieval_probe(
    vector_store_manager: Any,
    *,
    instruction: str,
    report_scope: Dict[str, Any],
    k: int,
) -> Dict[str, Any]:
    where_filter = build_researcher_probe_where_filter(dict(report_scope or {}))
    enriched_query = build_researcher_probe_query(instruction, dict(report_scope or {}))
    try:
        raw_docs = vector_store_manager.search(
            enriched_query,
            k=max(int(k or 0) * 3, 12),
            where_filter=where_filter,
        )
        selected_docs = select_researcher_probe_docs(raw_docs, limit=int(k or 0))
        return {
            "status": "ok",
            "where_filter": where_filter,
            "enriched_query": enriched_query,
            "raw_retrieved_doc_count": _doc_count(raw_docs),
            "selected_doc_count": _doc_count(selected_docs),
        }
    except Exception as exc:
        return {
            "status": "error",
            "where_filter": where_filter,
            "enriched_query": enriched_query,
            "error": str(exc),
            "raw_retrieved_doc_count": 0,
            "selected_doc_count": 0,
        }


def _researcher_material_status(
    result: Dict[str, Any],
    *,
    retrieval_probe: Dict[str, Any],
) -> Dict[str, Any]:
    answer = str(result.get("answer") or "").strip()
    result_doc_count = _doc_count(result.get("retrieved_docs") or [])
    success = bool(answer and result_doc_count > 0)
    raw_count = int(retrieval_probe.get("raw_retrieved_doc_count", 0) or 0)
    selected_count = int(retrieval_probe.get("selected_doc_count", 0) or 0)

    if success:
        status = "ok"
    elif str(retrieval_probe.get("status") or "") == "error":
        status = "retrieval_error"
    elif raw_count <= 0:
        status = "no_raw_retrieval"
    elif selected_count <= 0:
        status = "no_selected_docs"
    elif result_doc_count <= 0:
        status = "no_result_docs"
    elif not answer:
        status = "missing_answer"
    else:
        status = "empty_narrative_result"

    return {
        "material_status": status,
        "material_success": success,
        "answer_nonempty": bool(answer),
        "answer_excerpt": answer[:300],
        "citation_count": len(list(result.get("citations") or [])),
        "summary_point_count": len(list(result.get("summary_points") or [])),
        "result_doc_count": result_doc_count,
        "retrieval_probe": dict(retrieval_probe),
    }


def _run_analyst_task(
    analyst_core: Any,
    *,
    task: Dict[str, Any],
    report_scope: Dict[str, Any],
) -> Dict[str, Any]:
    projected = _task_projection(task)
    try:
        result = analyst_core.run(projected["instruction"], report_scope=dict(report_scope or {}))
        material = _analyst_material_status(dict(result or {}))
    except Exception as exc:
        material = {
            "material_status": "error",
            "material_success": False,
            "error": str(exc),
        }
    return {**projected, **material}


def _run_researcher_task(
    researcher_core: Any,
    vector_store_manager: Any,
    *,
    task: Dict[str, Any],
    report_scope: Dict[str, Any],
    k: int,
) -> Dict[str, Any]:
    projected = _task_projection(task)
    retrieval_probe = _researcher_retrieval_probe(
        vector_store_manager,
        instruction=projected["instruction"],
        report_scope=dict(report_scope or {}),
        k=k,
    )
    try:
        result = researcher_core.run(projected["instruction"], report_scope=dict(report_scope or {}))
        material = _researcher_material_status(dict(result or {}), retrieval_probe=retrieval_probe)
    except Exception as exc:
        material = {
            "material_status": "error",
            "material_success": False,
            "error": str(exc),
            "retrieval_probe": retrieval_probe,
        }
    return {**projected, **material}


def run_probe(
    *,
    store_dir: Path,
    collection_name: str,
    queries: List[str],
    report_scope: Dict[str, Any] | None = None,
    analyst_k: int = 8,
    researcher_k: int = 6,
    vector_store_manager: Any | None = None,
    planner_node: PlannerNode | None = None,
    analyst_core: Any | None = None,
    researcher_core: Any | None = None,
) -> Dict[str, Any]:
    scope = dict(report_scope or DEFAULT_SCOPE)
    vsm = vector_store_manager or VectorStoreManager(
        persist_directory=str(store_dir),
        collection_name=collection_name,
    )
    planner = planner_node or build_financial_orchestrator_plan_node()
    analyst = analyst_core or FinancialAgent(vsm, k=analyst_k)
    researcher = researcher_core or NarrativeResearcherCore(vsm, k=researcher_k)
    store_inventory = _store_inventory(vsm)

    cases: List[Dict[str, Any]] = []
    task_assignee_counts: Counter[str] = Counter()
    analyst_status_counts: Counter[str] = Counter()
    researcher_status_counts: Counter[str] = Counter()

    for index, query in enumerate(list(queries or []), start=1):
        tasks = _planned_tasks(query, report_scope=scope, planner_node=planner)
        projected_tasks = [_task_projection(task) for task in tasks]
        analyst_tasks = [task for task in tasks if str(task.get("assignee") or "") == "Analyst"]
        researcher_tasks = [task for task in tasks if str(task.get("assignee") or "") == "Researcher"]

        for task in projected_tasks:
            task_assignee_counts[str(task.get("assignee") or "")] += 1

        analyst_results = [
            _run_analyst_task(analyst, task=task, report_scope=scope)
            for task in analyst_tasks
        ]
        researcher_results = [
            _run_researcher_task(
                researcher,
                vsm,
                task=task,
                report_scope=scope,
                k=researcher_k,
            )
            for task in researcher_tasks
        ]
        analyst_status_counts.update(str(item.get("material_status") or "") for item in analyst_results)
        researcher_status_counts.update(str(item.get("material_status") or "") for item in researcher_results)

        cases.append(
            {
                "index": index,
                "query": query,
                "planned_task_count": len(projected_tasks),
                "planned_tasks": projected_tasks,
                "analyst": {
                    "task_count": len(analyst_results),
                    "success_count": sum(1 for item in analyst_results if item.get("material_success")),
                    "material_status_counts": dict(sorted(Counter(str(item.get("material_status") or "") for item in analyst_results).items())),
                    "items": analyst_results,
                },
                "researcher": {
                    "task_count": len(researcher_results),
                    "success_count": sum(1 for item in researcher_results if item.get("material_success")),
                    "material_status_counts": dict(sorted(Counter(str(item.get("material_status") or "") for item in researcher_results).items())),
                    "items": researcher_results,
                },
            }
        )

    return {
        "store": {
            "persist_directory": str(store_dir),
            "collection_name": collection_name,
            "analyst_k": int(analyst_k or 0),
            "researcher_k": int(researcher_k or 0),
        },
        "store_inventory": store_inventory,
        "report_scope": scope,
        "case_count": len(cases),
        "summary": {
            "planned_task_assignee_counts": dict(sorted(task_assignee_counts.items())),
            "analyst_material_status_counts": dict(sorted((k, v) for k, v in analyst_status_counts.items() if k)),
            "researcher_material_status_counts": dict(sorted((k, v) for k, v in researcher_status_counts.items() if k)),
            "analyst_success_count": sum(case["analyst"]["success_count"] for case in cases),
            "researcher_success_count": sum(case["researcher"]["success_count"] for case in cases),
        },
        "cases": cases,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Probe MAS planner tasks directly against worker cores.")
    parser.add_argument("--store-dir", type=Path, default=DEFAULT_STORE_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--company")
    parser.add_argument("--report-type")
    parser.add_argument("--rcept-no")
    parser.add_argument("--year")
    parser.add_argument("--consolidation")
    parser.add_argument("--analyst-k", type=int, default=8)
    parser.add_argument("--researcher-k", type=int, default=6)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    scope = dict(DEFAULT_SCOPE)
    for key, value in {
        "company": args.company,
        "report_type": args.report_type,
        "rcept_no": args.rcept_no,
        "year": args.year,
        "consolidation": args.consolidation,
    }.items():
        if value is not None:
            scope[key] = str(value)

    payload = run_probe(
        store_dir=args.store_dir,
        collection_name=args.collection_name,
        queries=args.queries or list(DEFAULT_QUERIES),
        report_scope=scope,
        analyst_k=args.analyst_k,
        researcher_k=args.researcher_k,
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
