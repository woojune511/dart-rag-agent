"""
Analyst node adapters for the DART MAS graph.

This module wraps the existing single-agent financial engine so it can be used
inside the task-ledger based MAS skeleton without rewriting the engine itself.
"""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Protocol, Sequence

from src.agent.mas_types import AgentTask, Artifact, EvidenceRecord, MultiAgentState, TaskStatus, build_artifact, build_evidence_record
from src.schema.runtime_enums import ArtifactKind


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


def _is_document_like(value: Any) -> bool:
    return hasattr(value, "page_content") and hasattr(value, "metadata")


def _resolve_runtime_calculation_trace(*args: Any, **kwargs: Any) -> Dict[str, Any]:
    from src.agent.financial_runtime_trace import _resolve_runtime_calculation_trace as impl

    return impl(*args, **kwargs)


def _extract_doc_links(retrieved_docs: Sequence[Any]) -> List[str]:
    links: List[str] = []
    for item in retrieved_docs or []:
        doc = item[0] if isinstance(item, tuple) and item else item
        if not _is_document_like(doc):
            continue
        metadata = doc.metadata or {}
        for key in ("chunk_uid", "section_path", "parent_id"):
            value = str(metadata.get(key) or "").strip()
            if value:
                links.append(value)
                break
    return links


def _extract_evidence_links(result: Dict[str, Any]) -> List[str]:
    resolved_trace = _resolve_runtime_calculation_trace(
        result,
        allow_legacy_top_level=False,
    )
    links: List[str] = []
    links.extend(str(item).strip() for item in result.get("citations", []) or [])

    for evidence_item in result.get("evidence_items", []) or []:
        anchor = str(evidence_item.get("source_anchor") or "").strip()
        if anchor:
            links.append(anchor)

    for operand in resolved_trace.get("calculation_operands", []) or []:
        anchor = str(operand.get("source_anchor") or "").strip()
        if anchor:
            links.append(anchor)

    links.extend(_extract_doc_links(result.get("retrieved_docs", []) or []))
    return _dedupe_preserve_order(links)


def _build_evidence_pool_entries(task_id: str, result: Dict[str, Any]) -> List[EvidenceRecord]:
    resolved_trace = _resolve_runtime_calculation_trace(
        result,
        allow_legacy_top_level=False,
    )
    pool: List[EvidenceRecord] = []

    for evidence_item in result.get("evidence_items", []) or []:
        pool.append(
            build_evidence_record(
                task_id=task_id,
                creator="Analyst",
                kind="evidence_item",
                source_anchor=str(evidence_item.get("source_anchor") or ""),
                claim=str(evidence_item.get("claim") or ""),
                support_level=str(evidence_item.get("support_level") or ""),
                metadata={"allowed_terms": list(evidence_item.get("allowed_terms", []) or [])},
            )
        )

    for operand in resolved_trace.get("calculation_operands", []) or []:
        pool.append(
            build_evidence_record(
                task_id=task_id,
                creator="Analyst",
                kind="calculation_operand",
                source_anchor=str(operand.get("source_anchor") or ""),
                metadata={
                    "label": operand.get("label", ""),
                    "raw_value": operand.get("raw_value", ""),
                    "raw_unit": operand.get("raw_unit", ""),
                    "normalized_value": operand.get("normalized_value"),
                    "normalized_unit": operand.get("normalized_unit", ""),
                    "period": operand.get("period", ""),
                },
            )
        )

    return pool


def _analyst_artifact_ids(task_id: str) -> Dict[str, str]:
    return {
        "operand": f"{task_id}::operand_set",
        "plan": f"{task_id}::calculation_plan",
        "result": task_id,
    }


def _build_analyst_artifacts(task_id: str, result: Dict[str, Any]) -> Dict[str, Artifact]:
    resolved_trace = _resolve_runtime_calculation_trace(
        result,
        allow_legacy_top_level=False,
    )
    structured_result = dict(
        result.get("structured_result")
        or resolved_trace.get("calculation_result")
        or {}
    )
    evidence_links = _extract_evidence_links(result)
    answer = str(result.get("answer") or "").strip()
    artifact_ids = _analyst_artifact_ids(task_id)
    calculation_operands = list(resolved_trace.get("calculation_operands", []) or [])
    calculation_plan = dict(resolved_trace.get("calculation_plan") or {})
    calculation_result = dict(structured_result or resolved_trace.get("calculation_result") or {})
    retrieval_debug_trace = dict(result.get("retrieval_debug_trace") or {})
    retrieval_debug_trace_history = [
        dict(item)
        for item in list(result.get("retrieval_debug_trace_history") or [])
        if isinstance(item, dict)
    ]
    if answer and not any(
        str(calculation_result.get(key) or "").strip()
        for key in ("rendered_value", "formatted_result")
    ) and not calculation_result.get("answer_slots"):
        calculation_result["formatted_result"] = answer
    return {
        artifact_ids["operand"]: build_artifact(
            task_id=task_id,
            creator="Analyst",
            artifact_id=artifact_ids["operand"],
            kind=ArtifactKind.OPERAND_SET.value,
            status="ok" if calculation_operands else "missing",
            summary=f"{len(calculation_operands)} operands",
            content={"calculation_operands": calculation_operands},
            payload={"calculation_operands": calculation_operands},
            evidence_links=evidence_links,
        ),
        artifact_ids["plan"]: build_artifact(
            task_id=task_id,
            creator="Analyst",
            artifact_id=artifact_ids["plan"],
            kind=ArtifactKind.CALCULATION_PLAN.value,
            status="ok" if calculation_plan else "missing",
            summary=str(calculation_plan.get("operation") or calculation_plan.get("mode") or ""),
            content={"calculation_plan": calculation_plan},
            payload={"calculation_plan": calculation_plan},
            evidence_links=evidence_links,
        ),
        artifact_ids["result"]: build_artifact(
            task_id=task_id,
            creator="Analyst",
            artifact_id=artifact_ids["result"],
            kind=ArtifactKind.CALCULATION_RESULT.value,
            status=str(calculation_result.get("status") or "ok"),
            summary=answer,
            content={
                "answer": answer,
                "query_type": result.get("query_type", ""),
                "intent": result.get("intent", ""),
                "legacy_target_metric_family_hint": result.get("target_metric_family", ""),
                "citations": list(result.get("citations", []) or []),
                "resolved_calculation_trace": resolved_trace,
                "structured_result": structured_result,
                "retrieval_debug_trace": retrieval_debug_trace,
                "retrieval_debug_trace_history": retrieval_debug_trace_history,
                "reflection_count": int(result.get("reflection_count", 0) or 0),
                "retry_reason": str(result.get("retry_reason", "") or ""),
            },
            payload={
                "answer": answer,
                "structured_result": structured_result,
                "resolved_calculation_trace": resolved_trace,
                "calculation_result": calculation_result,
                "retrieval_debug_trace": retrieval_debug_trace,
                "retrieval_debug_trace_history": retrieval_debug_trace_history,
            },
            evidence_links=evidence_links,
        ),
    }


def _is_successful_numeric_result(result: Dict[str, Any]) -> bool:
    answer = str(result.get("answer") or "").strip()
    resolved_trace = _resolve_runtime_calculation_trace(
        result,
        allow_legacy_top_level=False,
    )
    calc_result = dict(
        result.get("structured_result")
        or resolved_trace.get("calculation_result")
        or {}
    )
    calc_status = str(calc_result.get("status") or "").strip().lower()
    if calc_status and calc_status not in {"ok", "success"}:
        return False
    calculation_plan = resolved_trace.get("calculation_plan")
    calculation_operands = resolved_trace.get("calculation_operands")
    return bool(
        answer
        and isinstance(calculation_plan, dict)
        and calculation_plan
        and isinstance(calculation_operands, list)
        and calculation_operands
    )


def make_run_analyst(core_runner: AnalystCoreRunner) -> Callable[[MultiAgentState], Dict[str, Any]]:
    def run_analyst(state: MultiAgentState) -> Dict[str, Any]:
        task_updates: Dict[str, AgentTask] = {}
        artifact_updates: Dict[str, Artifact] = {}
        evidence_pool_entries: List[EvidenceRecord] = []
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

            analyst_artifacts = _build_analyst_artifacts(task_id, result)
            artifact_updates.update(analyst_artifacts)
            evidence_pool_entries.extend(_build_evidence_pool_entries(task_id, result))
            task_updates[task_id] = {
                **task,
                "status": TaskStatus.COMPLETED,
                "retry_count": task["retry_count"] + (1 if was_retry else 0),
                "artifact_ids": list(_analyst_artifact_ids(task_id).values()),
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
    routing_config: Dict[str, Any] | None = None,
) -> Callable[[MultiAgentState], Dict[str, Any]]:
    from src.agent.financial_graph import FinancialAgent

    financial_agent = FinancialAgent(
        vector_store_manager,
        k=k,
        graph_expansion_config=graph_expansion_config,
        routing_config=routing_config,
    )
    return make_run_analyst(financial_agent)
