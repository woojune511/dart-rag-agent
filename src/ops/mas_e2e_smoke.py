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
import sqlite3
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, List

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
from src.storage.vector_store import VectorStoreManager, get_embedding_runtime_spec

DEFAULT_STORE_DIR = (
    Path(
        "benchmarks/results/concept_gate_refresh_after_answer_composition_2026-06-04/"
        "삼성전자-2023/stores/structural-selective-v2-prefix-2500-320"
    )
)
DEFAULT_COLLECTION = "dart_reports_v2_structural-selective-v2-prefix-2500-320"
DEFAULT_SCOPE = {
    "company": "삼성전자",
    "report_type": "사업보고서",
    "rcept_no": "20240312000736",
    "year": "2023",
    "consolidation": "연결",
}
DEFAULT_SMOKE_CASES = [
    {
        "query": "삼성전자 2023 사업보고서에서 영업이익률은 얼마이고, 주요 재무 리스크는 무엇인가요?",
        "value_assertion": {
            "name": "samsung_2023_operating_margin",
            "must_include": ["2.54%", "6,566,976", "258,935,494"],
            "must_not_include": ["-4.45%"],
        },
    },
    {
        "query": "삼성전자 2023 사업보고서에서 연구개발비용 비중을 계산하고, 2023년 연구개발 성과 예시를 요약해줘.",
        "value_assertion": {
            "name": "samsung_2023_rnd_ratio",
            "must_include": ["10.95%", "28,352,769", "258,935,494"],
            "must_not_include": [],
        },
    },
]
DEFAULT_QUERIES = [str(case["query"]) for case in DEFAULT_SMOKE_CASES]


def _matches_default_scope(scope: Dict[str, Any]) -> bool:
    actual = dict(scope or {})
    for key, expected in DEFAULT_SCOPE.items():
        if str(actual.get(key) or "").strip() != str(expected or "").strip():
            return False
    return True


def build_smoke_value_contract(
    *,
    report_scope: Dict[str, Any] | None = None,
    queries: List[str] | None = None,
) -> Dict[str, Any]:
    scope = dict(report_scope or DEFAULT_SCOPE)
    if not _matches_default_scope(scope):
        return {}

    query_list = [str(query or "") for query in list(queries or DEFAULT_QUERIES)]
    assertions: List[Dict[str, Any]] = []
    cases_by_query = {str(case["query"]): dict(case) for case in DEFAULT_SMOKE_CASES}
    for index, query in enumerate(query_list, start=1):
        case = cases_by_query.get(query)
        if not case:
            continue
        assertion = dict(case.get("value_assertion") or {})
        if not assertion:
            continue
        assertion["case_index"] = index
        assertions.append(assertion)
    if not assertions:
        return {}
    return {
        "source": "mas_e2e_smoke_default_profile",
        "scope_match": dict(DEFAULT_SCOPE),
        "assertions": assertions,
    }


def _artifact_answer(artifact: Dict[str, Any]) -> str:
    content = artifact.get("content")
    if isinstance(content, dict):
        return str(content.get("answer") or "")
    return str(content or "")


def _report_scope(
    *,
    company: str | None = None,
    report_type: str | None = None,
    rcept_no: str | None = None,
    year: str | None = None,
    consolidation: str | None = None,
) -> Dict[str, str]:
    scope = dict(DEFAULT_SCOPE)
    overrides = {
        "company": company,
        "report_type": report_type,
        "rcept_no": rcept_no,
        "year": year,
        "consolidation": consolidation,
    }
    for key, value in overrides.items():
        text = str(value or "").strip()
        if text:
            scope[key] = text
    return scope


def _progress_logger(enabled: bool) -> Callable[[str], None]:
    def log(message: str) -> None:
        if not enabled:
            return
        print(f"[mas_e2e_smoke] {message}", file=sys.stderr, flush=True)

    return log


def _normalise_embedding_spec(spec: Dict[str, Any] | None) -> Dict[str, Any]:
    payload = dict(spec or {})
    dimension = payload.get("dimension")
    try:
        dimension = int(dimension) if dimension is not None else None
    except (TypeError, ValueError):
        dimension = None
    return {
        "provider": str(payload.get("provider") or "").strip().lower(),
        "model_name": str(payload.get("model_name") or payload.get("model") or "").strip(),
        "dimension": dimension,
    }


def _load_store_embedding_spec(store_dir: Path) -> Dict[str, Any]:
    meta_paths = [
        store_dir / "benchmark_cache_meta.json",
        store_dir / "vector_store_meta.json",
    ]
    for meta_path in meta_paths:
        if not meta_path.exists():
            continue
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        candidates = [
            dict(meta.get("store_signature") or {}).get("embedding"),
            dict(dict(meta.get("signature") or {}).get("store_signature") or {}).get("embedding"),
            meta.get("embedding"),
        ]
        for candidate in candidates:
            if isinstance(candidate, dict):
                normalised = _normalise_embedding_spec(candidate)
                if any(value not in ("", None) for value in normalised.values()):
                    return normalised
    return {}


def _load_chroma_collection_dimension(store_dir: Path, collection_name: str) -> int | None:
    sqlite_path = store_dir / "chroma.sqlite3"
    if not sqlite_path.exists():
        return None
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(sqlite_path)
        row = conn.execute(
            "SELECT dimension FROM collections WHERE name = ? LIMIT 1",
            (collection_name,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        if conn is not None:
            conn.close()
    if not row:
        return None
    try:
        return int(row[0]) if row[0] is not None else None
    except (TypeError, ValueError):
        return None


def _assert_store_embedding_compatible(
    store_dir: Path,
    collection_name: str,
    runtime_spec: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    store_spec = _load_store_embedding_spec(store_dir)
    chroma_dimension = _load_chroma_collection_dimension(store_dir, collection_name)
    if chroma_dimension is not None:
        store_spec = {
            "provider": str(store_spec.get("provider") or ""),
            "model_name": str(store_spec.get("model_name") or ""),
            "dimension": store_spec.get("dimension") or chroma_dimension,
        }
    runtime = _normalise_embedding_spec(runtime_spec or get_embedding_runtime_spec())
    result = {
        "status": "unknown" if not store_spec else "ok",
        "store_embedding": store_spec,
        "runtime_embedding": runtime,
    }
    if not store_spec:
        return result

    mismatches = [
        key
        for key in ("provider", "model_name", "dimension")
        if store_spec.get(key) not in ("", None)
        and runtime.get(key) not in ("", None)
        and store_spec.get(key) != runtime.get(key)
    ]
    if not mismatches:
        return result

    result["status"] = "mismatch"
    result["mismatches"] = mismatches
    raise ValueError(
        "Store embedding signature mismatch "
        f"({', '.join(mismatches)}): "
        f"store={store_spec}, runtime={runtime}. "
        "Pass a compatible --store-dir/--collection-name or rebuild the store."
    )


def _wrap_node(name: str, node: Callable[[Dict[str, Any]], Dict[str, Any]], log: Callable[[str], None]):
    def wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        log(f"node_start name={name}")
        result = node(state)
        elapsed = time.monotonic() - started
        log(f"node_done name={name} elapsed={elapsed:.1f}s")
        return result

    return wrapped


def run_smoke(
    *,
    store_dir: Path,
    collection_name: str,
    queries: List[str],
    replan_budget: int = 0,
    progress: bool = False,
    report_scope: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    log = _progress_logger(progress)
    log("check_store_embedding_signature")
    embedding_compatibility = _assert_store_embedding_compatible(store_dir, collection_name)
    log(f"store_embedding_signature status={embedding_compatibility['status']}")
    log("init_vector_store")
    vsm = VectorStoreManager(
        persist_directory=str(store_dir),
        collection_name=collection_name,
    )
    log("build_nodes")
    plan_node = _wrap_node("Orchestrator_Plan", build_financial_orchestrator_plan_node(), log)
    merge_node = _wrap_node("Orchestrator_Merge", build_financial_orchestrator_merge_node(), log)
    analyst_node = _wrap_node("Analyst", build_financial_analyst_node(vsm), log)
    researcher_node = _wrap_node("Researcher", build_financial_researcher_node(vsm), log)

    cases: List[Dict[str, Any]] = []
    scope = dict(report_scope or DEFAULT_SCOPE)
    for index, query in enumerate(queries, start=1):
        started = time.monotonic()
        log(f"query_start index={index}/{len(queries)}")
        final = run_mas_graph(
            query,
            report_scope=dict(scope),
            replan_budget=replan_budget,
            orchestrator_plan_node=plan_node,
            orchestrator_merge_node=merge_node,
            analyst_node=analyst_node,
            researcher_node=researcher_node,
        )
        elapsed = time.monotonic() - started
        log(f"query_done index={index}/{len(queries)} elapsed={elapsed:.1f}s")
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
    payload = {
        "store": {
            "persist_directory": str(store_dir),
            "collection_name": collection_name,
        },
        "embedding_compatibility": embedding_compatibility,
        "report_scope": scope,
        "replan_budget": int(replan_budget or 0),
        "case_count": len(cases),
        "summary": {
            "replan_routed_count": replan_routed_count,
            "blocked_count": blocked_count,
            "integrity_error_count": integrity_error_count,
        },
        "cases": cases,
    }
    value_contract = build_smoke_value_contract(report_scope=scope, queries=queries)
    if value_contract:
        payload["value_contract"] = value_contract
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="Run a real end-to-end MAS smoke.")
    parser.add_argument("--store-dir", type=Path, default=DEFAULT_STORE_DIR)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION)
    parser.add_argument("--query", action="append", dest="queries")
    parser.add_argument("--replan-budget", type=int, default=0)
    parser.add_argument("--company")
    parser.add_argument("--report-type")
    parser.add_argument("--rcept-no")
    parser.add_argument("--year")
    parser.add_argument("--consolidation")
    parser.add_argument("--progress", action="store_true", help="Print node/query progress to stderr.")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = run_smoke(
        store_dir=args.store_dir,
        collection_name=args.collection_name,
        queries=args.queries or list(DEFAULT_QUERIES),
        replan_budget=args.replan_budget,
        progress=args.progress,
        report_scope=_report_scope(
            company=args.company,
            report_type=args.report_type,
            rcept_no=args.rcept_no,
            year=args.year,
            consolidation=args.consolidation,
        ),
    )

    if args.output:
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
