"""
Analyst node adapters for the DART MAS graph.

This module wraps the existing single-agent financial engine so it can be used
inside the task-ledger based MAS skeleton without rewriting the engine itself.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Protocol, Sequence

from langchain_core.documents import Document

from src.agent.financial_graph import FinancialAgent
from src.agent.mas_types import AgentTask, Artifact, MultiAgentState, TaskStatus


class AnalystCoreRunner(Protocol):
    def run(self, query: str, *, report_scope: Dict[str, Any] | None = None) -> Dict[str, Any]:
        ...


def _trace(message: str) -> List[str]:
    return [message]


def _iter_analyst_tasks(state: MultiAgentState) -> Iterable[tuple[str, AgentTask]]:
    tasks = state.get("tasks", {}) or {}
    for task_id, task in tasks.items():
        if task["assignee"] != "Analyst":
            continue
        if task["status"] not in {TaskStatus.PENDING, TaskStatus.REJECTED_BY_CRITIC}:
            continue
        yield task_id, task


def _dedupe_preserve_order(values: Sequence[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        item = str(value or "").strip()
        if not item or item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered


def _extract_doc_links(retrieved_docs: Sequence[Any]) -> List[str]:
    links: List[str] = []
    for item in retrieved_docs or []:
        doc = item[0] if isinstance(item, tuple) and item else item
        if not isinstance(doc, Document):
            continue
        metadata = doc.metadata or {}
        for key in ("chunk_uid", "section_path", "parent_id"):
            value = str(metadata.get(key) or "").strip()
            if value:
                links.append(value)
                break
    return links


def _extract_evidence_links(result: Dict[str, Any]) -> List[str]:
    links: List[str] = []
    links.extend(str(item).strip() for item in result.get("citations", []) or [])

    for evidence_item in result.get("evidence_items", []) or []:
        anchor = str(evidence_item.get("source_anchor") or "").strip()
        if anchor:
            links.append(anchor)

    for operand in result.get("calculation_operands", []) or []:
        anchor = str(operand.get("source_anchor") or "").strip()
        if anchor:
            links.append(anchor)

    links.extend(_extract_doc_links(result.get("retrieved_docs", []) or []))
    return _dedupe_preserve_order(links)


def _build_evidence_pool_entries(task_id: str, result: Dict[str, Any]) -> List[Dict[str, Any]]:
    pool: List[Dict[str, Any]] = []

    for evidence_item in result.get("evidence_items", []) or []:
        pool.append(
            {
                "task_id": task_id,
                "creator": "Analyst",
                "kind": "evidence_item",
                "source_anchor": evidence_item.get("source_anchor", ""),
                "claim": evidence_item.get("claim", ""),
                "support_level": evidence_item.get("support_level", ""),
                "allowed_terms": list(evidence_item.get("allowed_terms", []) or []),
            }
        )

    for operand in result.get("calculation_operands", []) or []:
        pool.append(
            {
                "task_id": task_id,
                "creator": "Analyst",
                "kind": "calculation_operand",
                "source_anchor": operand.get("source_anchor", ""),
                "label": operand.get("label", ""),
                "raw_value": operand.get("raw_value", ""),
                "raw_unit": operand.get("raw_unit", ""),
                "normalized_value": operand.get("normalized_value"),
                "normalized_unit": operand.get("normalized_unit", ""),
                "period": operand.get("period", ""),
            }
        )

    return pool


def _build_analyst_artifact(task_id: str, result: Dict[str, Any]) -> Artifact:
    return {
        "task_id": task_id,
        "creator": "Analyst",
        "content": {
            "answer": result.get("answer", ""),
            "query_type": result.get("query_type", ""),
            "intent": result.get("intent", ""),
            "target_metric_family": result.get("target_metric_family", ""),
            "citations": list(result.get("citations", []) or []),
            "calculation_plan": dict(result.get("calculation_plan", {}) or {}),
            "calculation_result": dict(result.get("calculation_result", {}) or {}),
            "calculation_operands": list(result.get("calculation_operands", []) or []),
            "reflection_count": int(result.get("reflection_count", 0) or 0),
            "retry_reason": str(result.get("retry_reason", "") or ""),
        },
        "evidence_links": _extract_evidence_links(result),
    }


def _is_successful_numeric_result(result: Dict[str, Any]) -> bool:
    answer = str(result.get("answer") or "").strip()
    calc_result = dict(result.get("calculation_result", {}) or {})
    calc_status = str(calc_result.get("status") or "").strip().lower()
    if calc_status and calc_status not in {"ok", "success"}:
        return False
    return bool(answer)


def make_run_analyst(core_runner: AnalystCoreRunner) -> Callable[[MultiAgentState], Dict[str, Any]]:
    def run_analyst(state: MultiAgentState) -> Dict[str, Any]:
        task_updates: Dict[str, AgentTask] = {}
        artifact_updates: Dict[str, Artifact] = {}
        evidence_pool_entries: List[Dict[str, Any]] = []
        trace: List[str] = []

        for task_id, task in _iter_analyst_tasks(state):
            was_retry = task["status"] == TaskStatus.REJECTED_BY_CRITIC
            try:
                result = core_runner.run(
                    task["instruction"],
                    report_scope=dict(state.get("report_scope") or {}),
                )
            except Exception as exc:
                task_updates[task_id] = {
                    **task,
                    "status": TaskStatus.FAILED,
                }
                trace.append(f"Analyst failed {task_id}: {exc}")
                continue

            if not _is_successful_numeric_result(result):
                task_updates[task_id] = {
                    **task,
                    "status": TaskStatus.FAILED,
                }
                trace.append(f"Analyst failed {task_id}: incomplete numeric result")
                continue

            artifact_updates[task_id] = _build_analyst_artifact(task_id, result)
            evidence_pool_entries.extend(_build_evidence_pool_entries(task_id, result))
            task_updates[task_id] = {
                **task,
                "status": TaskStatus.COMPLETED,
                "retry_count": task["retry_count"] + (1 if was_retry else 0),
            }

            trace_message = f"Analyst completed {task_id} successfully"
            if was_retry:
                trace_message += " after critic retry"
            trace.append(trace_message)

        return {
            "tasks": task_updates,
            "artifacts": artifact_updates,
            "evidence_pool": evidence_pool_entries,
            "execution_trace": trace,
        }

    return run_analyst


def build_financial_analyst_node(
    vector_store_manager: Any,
    *,
    k: int = 8,
    graph_expansion_config: Dict[str, Any] | None = None,
) -> Callable[[MultiAgentState], Dict[str, Any]]:
    financial_agent = FinancialAgent(
        vector_store_manager,
        k=k,
        graph_expansion_config=graph_expansion_config,
    )
    return make_run_analyst(financial_agent)
