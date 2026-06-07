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
from collections import Counter
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
from src.agent.mas_types import project_final_report_carry_forward
from src.storage.vector_store import VectorStoreManager, get_embedding_runtime_spec

DEFAULT_STORE_DIR = (
    Path(
        "benchmarks/results/policy_gate_regression_2026-06-03_1138_actual/"
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


def _find_report_cache_candidates(obj: Any, *, path: str = "") -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        candidate = obj.get("report_cache_candidate")
        if isinstance(candidate, dict):
            item = {
                "path": path,
                "status": str(candidate.get("status") or "").strip(),
                "reasons": [str(reason) for reason in list(candidate.get("reasons") or [])],
                "key_id": str(candidate.get("key_id") or "").strip(),
            }
            key = candidate.get("key")
            if isinstance(key, dict):
                item["key"] = key
            retrieval_bypass = candidate.get("retrieval_bypass")
            if isinstance(retrieval_bypass, dict):
                item["retrieval_bypass"] = {
                    "status": str(retrieval_bypass.get("status") or "").strip(),
                    "eligible": bool(retrieval_bypass.get("eligible")),
                    "enabled": bool(retrieval_bypass.get("enabled")),
                    "mode": str(retrieval_bypass.get("mode") or "").strip(),
                    "reasons": [str(reason) for reason in list(retrieval_bypass.get("reasons") or [])],
                }
            candidates.append(item)
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else str(key)
            candidates.extend(_find_report_cache_candidates(value, path=child_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            candidates.extend(_find_report_cache_candidates(value, path=f"{path}[{index}]"))
    return candidates


def _summarize_report_cache_candidates(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, tuple[str, ...]]] = set()
    for artifact_id, artifact in sorted(dict(artifacts or {}).items()):
        for candidate in _find_report_cache_candidates(artifact, path=f"artifacts.{artifact_id}"):
            candidate["artifact_id"] = str(artifact_id)
            dedupe_key = (
                str(artifact_id),
                str(candidate.get("key_id") or ""),
                str(candidate.get("status") or ""),
                tuple(str(reason) for reason in list(candidate.get("reasons") or [])),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(candidate)

    status_counts = Counter(str(item.get("status") or "").strip() for item in items)
    status_counts.pop("", None)
    reason_counts: Counter[str] = Counter()
    for item in items:
        reason_counts.update(str(reason) for reason in list(item.get("reasons") or []))
    reason_counts.pop("", None)
    return {
        "count": len(items),
        "status_counts": dict(sorted(status_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "items": items,
    }


def _find_report_cache_index_diagnostics(obj: Any, *, path: str = "") -> List[Dict[str, Any]]:
    diagnostics_items: List[Dict[str, Any]] = []
    if isinstance(obj, dict):
        diagnostics = obj.get("report_cache_index_diagnostics")
        if isinstance(diagnostics, dict):
            index = diagnostics.get("index")
            item = {
                "path": path,
                "status": str(diagnostics.get("status") or "").strip(),
                "enabled": bool(diagnostics.get("enabled")),
                "serving_enabled": bool(diagnostics.get("serving_enabled")),
                "lookup_attempted": bool(diagnostics.get("lookup_attempted")),
                "key_id": str(diagnostics.get("key_id") or "").strip(),
                "match_count": int(diagnostics.get("match_count") or 0),
                "readable_match_count": int(diagnostics.get("readable_match_count") or 0),
                "rehydration_ready_match_count": int(diagnostics.get("rehydration_ready_match_count") or 0),
                "rehydration_blocked_match_count": int(diagnostics.get("rehydration_blocked_match_count") or 0),
                "rehydration_reason_counts": dict(diagnostics.get("rehydration_reason_counts") or {}),
                "normal_retrieval_executed": bool(diagnostics.get("normal_retrieval_executed")),
                "executed_query_count": int(diagnostics.get("executed_query_count") or 0),
            }
            if isinstance(index, dict):
                item["index"] = {
                    "status": str(index.get("status") or "").strip(),
                    "path": str(index.get("path") or "").strip(),
                    "readable_count": int(index.get("readable_count") or 0),
                    "rehydration_ready_count": int(index.get("rehydration_ready_count") or 0),
                    "blocked_count": int(index.get("blocked_count") or 0),
                    "malformed_count": int(index.get("malformed_count") or 0),
                }
            diagnostics_items.append(item)
        for key, value in obj.items():
            child_path = f"{path}.{key}" if path else str(key)
            diagnostics_items.extend(_find_report_cache_index_diagnostics(value, path=child_path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            diagnostics_items.extend(_find_report_cache_index_diagnostics(value, path=f"{path}[{index}]"))
    return diagnostics_items


def _summarize_report_cache_index_diagnostics(artifacts: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    seen: set[tuple[str, str, str, int, int, str]] = set()
    for artifact_id, artifact in sorted(dict(artifacts or {}).items()):
        for diagnostics in _find_report_cache_index_diagnostics(artifact, path=f"artifacts.{artifact_id}"):
            diagnostics["artifact_id"] = str(artifact_id)
            index = dict(diagnostics.get("index") or {})
            dedupe_key = (
                str(artifact_id),
                str(diagnostics.get("key_id") or ""),
                str(diagnostics.get("status") or ""),
                int(diagnostics.get("match_count") or 0),
                int(diagnostics.get("readable_match_count") or 0),
                int(diagnostics.get("rehydration_ready_match_count") or 0),
                str(index.get("path") or ""),
            )
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(diagnostics)

    status_counts = Counter(str(item.get("status") or "").strip() for item in items)
    status_counts.pop("", None)
    rehydration_reason_counts: Counter[str] = Counter()
    for item in items:
        rehydration_reason_counts.update(dict(item.get("rehydration_reason_counts") or {}))
    rehydration_reason_counts.pop("", None)
    return {
        "count": len(items),
        "status_counts": dict(sorted(status_counts.items())),
        "lookup_attempted_count": sum(1 for item in items if bool(item.get("lookup_attempted"))),
        "match_count": sum(int(item.get("match_count") or 0) for item in items),
        "readable_match_count": sum(int(item.get("readable_match_count") or 0) for item in items),
        "rehydration_ready_match_count": sum(
            int(item.get("rehydration_ready_match_count") or 0) for item in items
        ),
        "rehydration_blocked_match_count": sum(
            int(item.get("rehydration_blocked_match_count") or 0) for item in items
        ),
        "rehydration_reason_counts": dict(sorted(rehydration_reason_counts.items())),
        "normal_retrieval_executed_count": sum(
            1 for item in items if bool(item.get("normal_retrieval_executed"))
        ),
        "items": items,
    }


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


def _load_json_count(path: Path, key: str = "") -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return 0
    if key and isinstance(payload, dict):
        value = payload.get(key)
    else:
        value = payload
    if isinstance(value, dict):
        return len(value)
    if isinstance(value, list):
        return len(value)
    return 0


def _load_chroma_collection_inventory(store_dir: Path, collection_name: str) -> Dict[str, Any]:
    sqlite_path = store_dir / "chroma.sqlite3"
    if not sqlite_path.exists():
        return {
            "chroma_sqlite_present": False,
            "chroma_collection_present": False,
            "chroma_embedding_count": None,
        }
    conn: sqlite3.Connection | None = None
    try:
        conn = sqlite3.connect(sqlite_path)
        row = conn.execute(
            "SELECT id FROM collections WHERE name = ? LIMIT 1",
            (collection_name,),
        ).fetchone()
        if not row:
            return {
                "chroma_sqlite_present": True,
                "chroma_collection_present": False,
                "chroma_embedding_count": 0,
            }
        collection_id = str(row[0])
        count_row = conn.execute(
            """
            SELECT COUNT(*)
            FROM embeddings
            JOIN segments ON embeddings.segment_id = segments.id
            WHERE segments.collection = ?
            """,
            (collection_id,),
        ).fetchone()
        return {
            "chroma_sqlite_present": True,
            "chroma_collection_present": True,
            "chroma_embedding_count": int(count_row[0] if count_row else 0),
        }
    except sqlite3.Error as exc:
        return {
            "chroma_sqlite_present": True,
            "chroma_collection_present": False,
            "chroma_embedding_count": None,
            "chroma_inventory_error": str(exc),
        }
    finally:
        if conn is not None:
            conn.close()


def _load_store_inventory(store_dir: Path, collection_name: str) -> Dict[str, Any]:
    chroma = _load_chroma_collection_inventory(store_dir, collection_name)
    parent_count = _load_json_count(store_dir / "parents.json")
    structure_graph_node_count = _load_json_count(store_dir / "document_structure_graph.json", "nodes")
    table_payload_count = _load_json_count(store_dir / "table_payloads.json")
    known_artifact_present = any(
        [
            bool(chroma.get("chroma_sqlite_present")),
            (store_dir / "benchmark_cache_meta.json").exists(),
            (store_dir / "vector_store_meta.json").exists(),
            (store_dir / "parents.json").exists(),
            (store_dir / "document_structure_graph.json").exists(),
            (store_dir / "table_payloads.json").exists(),
        ]
    )
    empty_material = (
        bool(chroma.get("chroma_collection_present"))
        and int(chroma.get("chroma_embedding_count") or 0) == 0
        and parent_count == 0
        and structure_graph_node_count == 0
        and table_payload_count == 0
    )
    return {
        **chroma,
        "parent_count": parent_count,
        "structure_graph_node_count": structure_graph_node_count,
        "table_payload_count": table_payload_count,
        "known_artifact_present": known_artifact_present,
        "empty_material": empty_material,
    }


def _assert_store_has_material(store_dir: Path, collection_name: str) -> Dict[str, Any]:
    inventory = _load_store_inventory(store_dir, collection_name)
    if inventory.get("empty_material"):
        raise ValueError(
            "Store appears empty for MAS smoke "
            f"(collection={collection_name}, store_dir={store_dir}, "
            f"chroma_embedding_count={inventory.get('chroma_embedding_count')}, "
            f"parent_count={inventory.get('parent_count')}, "
            f"structure_graph_node_count={inventory.get('structure_graph_node_count')}, "
            f"table_payload_count={inventory.get('table_payload_count')}). "
            "Pass a populated --store-dir/--collection-name or rebuild the smoke store."
        )
    return inventory


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


def _resolve_smoke_embedding_runtime_spec(
    store_dir: Path,
    *,
    embedding_provider: str = "",
    embedding_model: str = "",
) -> Dict[str, Any]:
    provider = str(embedding_provider or "").strip()
    model = str(embedding_model or "").strip()
    if provider or model:
        return get_embedding_runtime_spec(
            provider=provider or None,
            model_name=model or None,
        )
    store_spec = _load_store_embedding_spec(store_dir)
    store_provider = str(store_spec.get("provider") or "").strip()
    store_model = str(store_spec.get("model_name") or "").strip()
    if store_provider or store_model:
        return get_embedding_runtime_spec(
            provider=store_provider or None,
            model_name=store_model or None,
        )
    return get_embedding_runtime_spec()


def _wrap_node(name: str, node: Callable[[Dict[str, Any]], Dict[str, Any]], log: Callable[[str], None]):
    def wrapped(state: Dict[str, Any]) -> Dict[str, Any]:
        started = time.monotonic()
        log(f"node_start name={name}")
        result = node(state)
        elapsed = time.monotonic() - started
        log(f"node_done name={name} elapsed={elapsed:.1f}s")
        return result

    return wrapped


def _summarize_critic_acceptance_issues(task_artifact_trace: Dict[str, Any]) -> Dict[str, Any]:
    items: List[Dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    for issue in task_artifact_trace.get("integrity_issues") or []:
        if not isinstance(issue, dict) or str(issue.get("type") or "").strip() != "critic_report_rejected":
            continue
        status = str(issue.get("runtime_acceptance_status") or "unknown").strip() or "unknown"
        reasons = [
            str(reason).strip()
            for reason in (issue.get("reasons") or [])
            if str(reason).strip()
        ]
        target_refs = [
            str(ref).strip()
            for ref in (issue.get("target_refs") or [])
            if str(ref).strip()
        ]
        target_task_ids = [
            str(ref).strip()
            for ref in (issue.get("target_task_ids") or [])
            if str(ref).strip()
        ]
        target_artifact_ids = [
            str(ref).strip()
            for ref in (issue.get("target_artifact_ids") or [])
            if str(ref).strip()
        ]
        status_counts[status] += 1
        reason_counts.update(reasons)
        items.append(
            {
                "task_id": str(issue.get("task_id") or "").strip(),
                "artifact_id": str(issue.get("artifact_id") or "").strip(),
                "runtime_acceptance_status": status,
                "reasons": reasons,
                "target_refs": target_refs,
                "target_task_ids": target_task_ids,
                "target_artifact_ids": target_artifact_ids,
            }
        )
    return {
        "count": len(items),
        "status_counts": dict(sorted(status_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "items": items,
    }


def _summarize_final_acceptance_outcome(
    *,
    final_report_record: Dict[str, Any],
    task_artifact_trace: Dict[str, Any],
    execution_trace: List[str],
    replan_count: int,
    replan_budget: int,
    critic_acceptance_issues: Dict[str, Any],
) -> Dict[str, Any]:
    final_status = str(final_report_record.get("status") or "").strip() or "unknown"
    integrity_status = str(task_artifact_trace.get("integrity_status") or "").strip() or "unknown"
    trace_text = " | ".join(str(item or "") for item in execution_trace)
    replan_routed = "Orchestrator replanned" in trace_text
    replan_requested = final_status == "replan_required"
    blocked = final_status == "blocked"
    if replan_requested:
        outcome = "replan_pending"
    elif blocked and replan_count > 0:
        outcome = "blocked_after_replan"
    elif blocked:
        outcome = "blocked_without_replan"
    elif replan_routed and final_status == "ok":
        outcome = "replan_succeeded"
    elif final_status == "ok":
        outcome = "accepted_without_replan"
    else:
        outcome = "unknown"
    return {
        "outcome": outcome,
        "final_report_status": final_status,
        "task_artifact_integrity_status": integrity_status,
        "replan_budget": int(replan_budget or 0),
        "replan_count": int(replan_count or 0),
        "replan_requested": replan_requested,
        "replan_routed": replan_routed,
        "blocked": blocked,
        "critic_acceptance_issue_count": int(critic_acceptance_issues.get("count", 0) or 0),
    }


def _trace_failure_reasons(execution_trace: List[str], task_id: str) -> List[str]:
    marker = f"failed {task_id}:"
    reasons: List[str] = []
    for item in execution_trace:
        text = str(item or "").strip()
        if marker not in text:
            continue
        reason = text.split(marker, 1)[1].strip()
        if reason and reason not in reasons:
            reasons.append(reason)
    return reasons


def _summarize_worker_failure_diagnostics(
    *,
    tasks: Dict[str, Any],
    task_artifact_trace: Dict[str, Any],
    execution_trace: List[str],
) -> Dict[str, Any]:
    trace_tasks = {
        str(item.get("task_id") or "").strip(): dict(item)
        for item in list(task_artifact_trace.get("tasks") or [])
        if isinstance(item, dict) and str(item.get("task_id") or "").strip()
    }
    items: List[Dict[str, Any]] = []
    assignee_counts: Counter[str] = Counter()
    reason_counts: Counter[str] = Counter()
    missing_artifact_count = 0

    for task_id, task in dict(tasks or {}).items():
        task_record = dict(task or {})
        assignee = str(task_record.get("assignee") or "").strip()
        if assignee not in {"Analyst", "Researcher"}:
            continue
        status = str(task_record.get("status") or "").strip()
        if status not in {"TaskStatus.FAILED", "failed"}:
            continue

        normalized_task_id = str(task_record.get("task_id") or task_id).strip()
        trace_record = trace_tasks.get(normalized_task_id, {})
        artifact_ids = [
            str(value).strip()
            for value in (
                task_record.get("artifact_ids")
                or trace_record.get("artifact_ids")
                or []
            )
            if str(value).strip()
        ]
        reasons = _trace_failure_reasons(execution_trace, normalized_task_id)
        blocked_reason = str(task_record.get("blocked_reason") or "").strip()
        if blocked_reason and blocked_reason not in reasons:
            reasons.append(blocked_reason)
        if not reasons:
            reasons.append("worker_failed")
        if not artifact_ids:
            missing_artifact_count += 1
            if "missing_worker_artifact" not in reasons:
                reasons.append("missing_worker_artifact")

        assignee_counts[assignee] += 1
        reason_counts.update(reasons)
        items.append(
            {
                "task_id": normalized_task_id,
                "assignee": assignee,
                "kind": str(task_record.get("kind") or trace_record.get("kind") or "").strip(),
                "status": status,
                "label": str(task_record.get("label") or trace_record.get("label") or "").strip(),
                "artifact_ids": artifact_ids,
                "latest_artifact_id": str(trace_record.get("latest_artifact_id") or "").strip(),
                "latest_artifact_status": str(trace_record.get("latest_artifact_status") or "").strip(),
                "reasons": reasons,
            }
        )

    return {
        "count": len(items),
        "missing_artifact_count": missing_artifact_count,
        "assignee_counts": dict(sorted(assignee_counts.items())),
        "reason_counts": dict(sorted(reason_counts.items())),
        "items": items,
    }


def run_smoke(
    *,
    store_dir: Path,
    collection_name: str,
    queries: List[str],
    replan_budget: int = 0,
    progress: bool = False,
    report_scope: Dict[str, str] | None = None,
    report_cache_index_path: Path | None = None,
    embedding_provider: str = "",
    embedding_model: str = "",
) -> Dict[str, Any]:
    log = _progress_logger(progress)
    log("check_store_embedding_signature")
    embedding_runtime_spec = _resolve_smoke_embedding_runtime_spec(
        store_dir,
        embedding_provider=embedding_provider,
        embedding_model=embedding_model,
    )
    embedding_compatibility = _assert_store_embedding_compatible(
        store_dir,
        collection_name,
        runtime_spec=embedding_runtime_spec,
    )
    log(f"store_embedding_signature status={embedding_compatibility['status']}")
    log("check_store_material")
    store_inventory = _assert_store_has_material(store_dir, collection_name)
    log(
        "store_material "
        f"empty={store_inventory['empty_material']} "
        f"chroma_embeddings={store_inventory['chroma_embedding_count']} "
        f"parents={store_inventory['parent_count']} "
        f"graph_nodes={store_inventory['structure_graph_node_count']}"
    )
    log("init_vector_store")
    vsm = VectorStoreManager(
        persist_directory=str(store_dir),
        collection_name=collection_name,
        embedding_provider=str(embedding_runtime_spec.get("provider") or ""),
        embedding_model_name=str(embedding_runtime_spec.get("model_name") or ""),
    )
    log("build_nodes")
    plan_node = _wrap_node("Orchestrator_Plan", build_financial_orchestrator_plan_node(), log)
    merge_node = _wrap_node("Orchestrator_Merge", build_financial_orchestrator_merge_node(), log)
    analyst_routing_config: Dict[str, Any] = {}
    if report_cache_index_path:
        analyst_routing_config["report_cache_index_path"] = str(report_cache_index_path)
    analyst_node = _wrap_node(
        "Analyst",
        build_financial_analyst_node(vsm, routing_config=analyst_routing_config or None),
        log,
    )
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
        report_cache_candidates = _summarize_report_cache_candidates(artifacts)
        report_cache_index_diagnostics = _summarize_report_cache_index_diagnostics(artifacts)
        critic_acceptance_issues = _summarize_critic_acceptance_issues(task_artifact_trace)
        worker_failure_diagnostics = _summarize_worker_failure_diagnostics(
            tasks=tasks,
            task_artifact_trace=task_artifact_trace,
            execution_trace=execution_trace,
        )
        final_carry_forward = project_final_report_carry_forward(final_report_record)
        replan_count = int(final.get("replan_count", 0) or 0)
        case_replan_budget = int(final.get("replan_budget", replan_budget) or 0)
        final_acceptance_outcome = _summarize_final_acceptance_outcome(
            final_report_record=final_report_record,
            task_artifact_trace=task_artifact_trace,
            execution_trace=execution_trace,
            replan_count=replan_count,
            replan_budget=case_replan_budget,
            critic_acceptance_issues=critic_acceptance_issues,
        )
        cases.append(
            {
                "query": query,
                "task_count": len(tasks),
                "task_statuses": {task_id: str(task.get("status")) for task_id, task in tasks.items()},
                "critic_reports": critic_reports,
                "critic_feedback": final.get("critic_feedback"),
                "planner_feedback": final.get("planner_feedback"),
                "replan_budget": case_replan_budget,
                "replan_count": replan_count,
                "replan_requested": final_report_record.get("status") == "replan_required",
                "replan_routed": "Orchestrator replanned" in " | ".join(execution_trace),
                "execution_trace": execution_trace,
                "final_report": final.get("final_report"),
                "final_report_record": final_report_record,
                "final_carry_forward": final_carry_forward,
                "final_acceptance_outcome": final_acceptance_outcome,
                "task_artifact_trace": task_artifact_trace,
                "task_artifact_integrity_status": task_artifact_trace.get("integrity_status"),
                "task_artifact_integrity_issue_count": task_artifact_trace.get("integrity_issue_count"),
                "critic_acceptance_issues": critic_acceptance_issues,
                "worker_failure_diagnostics": worker_failure_diagnostics,
                "artifact_answers": {
                    task_id: _artifact_answer(artifact)
                    for task_id, artifact in artifacts.items()
                },
                "report_cache_candidates": report_cache_candidates,
                "report_cache_index_diagnostics": report_cache_index_diagnostics,
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
    report_cache_status_counts: Counter[str] = Counter()
    report_cache_reason_counts: Counter[str] = Counter()
    report_cache_candidate_count = 0
    report_cache_index_status_counts: Counter[str] = Counter()
    report_cache_index_diagnostic_count = 0
    report_cache_index_lookup_attempted_count = 0
    report_cache_index_match_count = 0
    report_cache_index_readable_match_count = 0
    report_cache_index_rehydration_ready_match_count = 0
    report_cache_index_rehydration_blocked_match_count = 0
    report_cache_index_rehydration_reason_counts: Counter[str] = Counter()
    report_cache_index_normal_retrieval_count = 0
    critic_acceptance_issue_count = 0
    critic_acceptance_status_counts: Counter[str] = Counter()
    critic_acceptance_reason_counts: Counter[str] = Counter()
    worker_failure_count = 0
    worker_failure_missing_artifact_count = 0
    worker_failure_assignee_counts: Counter[str] = Counter()
    worker_failure_reason_counts: Counter[str] = Counter()
    final_acceptance_outcome_counts: Counter[str] = Counter()
    final_source_task_count = 0
    final_source_artifact_count = 0
    final_evidence_ref_count = 0
    final_subtask_result_count = 0
    for case in cases:
        carry_forward = dict(case.get("final_carry_forward") or {})
        final_source_task_count += int(carry_forward.get("source_task_count", 0) or 0)
        final_source_artifact_count += int(carry_forward.get("source_artifact_count", 0) or 0)
        final_evidence_ref_count += int(carry_forward.get("evidence_ref_count", 0) or 0)
        final_subtask_result_count += int(carry_forward.get("subtask_result_count", 0) or 0)
        critic_summary = dict(case.get("critic_acceptance_issues") or {})
        critic_acceptance_issue_count += int(critic_summary.get("count", 0) or 0)
        critic_acceptance_status_counts.update(dict(critic_summary.get("status_counts") or {}))
        critic_acceptance_reason_counts.update(dict(critic_summary.get("reason_counts") or {}))
        worker_summary = dict(case.get("worker_failure_diagnostics") or {})
        worker_failure_count += int(worker_summary.get("count", 0) or 0)
        worker_failure_missing_artifact_count += int(worker_summary.get("missing_artifact_count", 0) or 0)
        worker_failure_assignee_counts.update(dict(worker_summary.get("assignee_counts") or {}))
        worker_failure_reason_counts.update(dict(worker_summary.get("reason_counts") or {}))
        outcome = str(dict(case.get("final_acceptance_outcome") or {}).get("outcome") or "").strip()
        if outcome:
            final_acceptance_outcome_counts[outcome] += 1
        summary = dict(case.get("report_cache_candidates") or {})
        report_cache_candidate_count += int(summary.get("count", 0) or 0)
        report_cache_status_counts.update(dict(summary.get("status_counts") or {}))
        report_cache_reason_counts.update(dict(summary.get("reason_counts") or {}))
        index_summary = dict(case.get("report_cache_index_diagnostics") or {})
        report_cache_index_diagnostic_count += int(index_summary.get("count", 0) or 0)
        report_cache_index_status_counts.update(dict(index_summary.get("status_counts") or {}))
        report_cache_index_lookup_attempted_count += int(index_summary.get("lookup_attempted_count", 0) or 0)
        report_cache_index_match_count += int(index_summary.get("match_count", 0) or 0)
        report_cache_index_readable_match_count += int(index_summary.get("readable_match_count", 0) or 0)
        report_cache_index_rehydration_ready_match_count += int(
            index_summary.get("rehydration_ready_match_count", 0) or 0
        )
        report_cache_index_rehydration_blocked_match_count += int(
            index_summary.get("rehydration_blocked_match_count", 0) or 0
        )
        report_cache_index_rehydration_reason_counts.update(
            dict(index_summary.get("rehydration_reason_counts") or {})
        )
        report_cache_index_normal_retrieval_count += int(
            index_summary.get("normal_retrieval_executed_count", 0) or 0
        )
    payload = {
        "store": {
            "persist_directory": str(store_dir),
            "collection_name": collection_name,
        },
        "embedding_compatibility": embedding_compatibility,
        "store_inventory": store_inventory,
        "report_scope": scope,
        "replan_budget": int(replan_budget or 0),
        "report_cache_index_path": str(report_cache_index_path or ""),
        "case_count": len(cases),
        "summary": {
            "replan_routed_count": replan_routed_count,
            "blocked_count": blocked_count,
            "integrity_error_count": integrity_error_count,
            "final_source_task_count": final_source_task_count,
            "final_source_artifact_count": final_source_artifact_count,
            "final_evidence_ref_count": final_evidence_ref_count,
            "final_subtask_result_count": final_subtask_result_count,
            "critic_acceptance_issue_count": critic_acceptance_issue_count,
            "critic_acceptance_status_counts": dict(sorted(critic_acceptance_status_counts.items())),
            "critic_acceptance_reason_counts": dict(sorted(critic_acceptance_reason_counts.items())),
            "worker_failure_count": worker_failure_count,
            "worker_failure_missing_artifact_count": worker_failure_missing_artifact_count,
            "worker_failure_assignee_counts": dict(sorted(worker_failure_assignee_counts.items())),
            "worker_failure_reason_counts": dict(sorted(worker_failure_reason_counts.items())),
            "final_acceptance_outcome_counts": dict(sorted(final_acceptance_outcome_counts.items())),
            "report_cache_candidate_count": report_cache_candidate_count,
            "report_cache_candidate_status_counts": dict(sorted(report_cache_status_counts.items())),
            "report_cache_candidate_reason_counts": dict(sorted(report_cache_reason_counts.items())),
            "report_cache_index_diagnostic_count": report_cache_index_diagnostic_count,
            "report_cache_index_status_counts": dict(sorted(report_cache_index_status_counts.items())),
            "report_cache_index_lookup_attempted_count": report_cache_index_lookup_attempted_count,
            "report_cache_index_match_count": report_cache_index_match_count,
            "report_cache_index_readable_match_count": report_cache_index_readable_match_count,
            "report_cache_index_rehydration_ready_match_count": report_cache_index_rehydration_ready_match_count,
            "report_cache_index_rehydration_blocked_match_count": report_cache_index_rehydration_blocked_match_count,
            "report_cache_index_rehydration_reason_counts": dict(
                sorted(report_cache_index_rehydration_reason_counts.items())
            ),
            "report_cache_index_normal_retrieval_count": report_cache_index_normal_retrieval_count,
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
    parser.add_argument("--embedding-provider", default="")
    parser.add_argument("--embedding-model", default="")
    parser.add_argument("--progress", action="store_true", help="Print node/query progress to stderr.")
    parser.add_argument(
        "--report-cache-index-path",
        type=Path,
        help="Optional local report-cache index path for retrieval trace diagnostics only; hits are never served.",
    )
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    payload = run_smoke(
        store_dir=args.store_dir,
        collection_name=args.collection_name,
        queries=args.queries or list(DEFAULT_QUERIES),
        replan_budget=args.replan_budget,
        progress=args.progress,
        report_cache_index_path=args.report_cache_index_path,
        embedding_provider=args.embedding_provider,
        embedding_model=args.embedding_model,
        report_scope=_report_scope(
            company=args.company,
            report_type=args.report_type,
            rcept_no=args.rcept_no,
            year=args.year,
            consolidation=args.consolidation,
        ),
    )

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
