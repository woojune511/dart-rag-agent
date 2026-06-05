"""
Shared state and artifact types for the DART MAS skeleton.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Dict, List, NotRequired, Optional, TypedDict

from src.schema import ArtifactKind, TaskKind


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED_BY_CRITIC = "rejected_by_critic"


class AgentTask(TypedDict):
    task_id: str
    assignee: str
    instruction: str
    status: TaskStatus
    context_keys: List[str]
    retry_count: int
    kind: NotRequired[str]
    label: NotRequired[str]
    depends_on: NotRequired[List[str]]
    artifact_ids: NotRequired[List[str]]
    blocked_reason: NotRequired[str]


class Artifact(TypedDict):
    task_id: str
    creator: str
    content: Any
    evidence_links: List[str]
    artifact_id: NotRequired[str]
    kind: NotRequired[str]
    status: NotRequired[str]
    summary: NotRequired[str]
    payload: NotRequired[Dict[str, Any]]
    evidence_refs: NotRequired[List[str]]
    producer_task_id: NotRequired[str]
    metadata: NotRequired[Dict[str, Any]]


class EvidenceRecord(TypedDict, total=False):
    task_id: str
    creator: str
    kind: str
    source_anchor: str
    claim: str
    snippet: str
    support_level: str
    metadata: Dict[str, Any]


class CriticReport(TypedDict):
    target_task_id: str
    passed: bool
    deterministic_score: float
    llm_feedback: str
    verdict: NotRequired[str]
    target_artifact_id: NotRequired[str]
    target_artifact_ids: NotRequired[List[str]]
    acceptance_reason: NotRequired[str]
    blocking_issues: NotRequired[List[str]]


class CriticRuntimeAcceptance(TypedDict):
    accepted: bool
    runtime_acceptance_status: str
    reasons: List[str]
    target_refs: List[str]
    deterministic_score: float
    deterministic_score_used_for_acceptance: bool


class FinalReport(TypedDict, total=False):
    final_answer: str
    status: str
    source_task_ids: List[str]
    source_artifact_ids: List[str]
    evidence_refs: List[str]
    subtask_results: List[Dict[str, Any]]


class ReportScope(TypedDict):
    company: str
    report_type: str
    rcept_no: str
    year: str
    consolidation: str


def _coerce_task_status(value: Any) -> TaskStatus:
    if isinstance(value, TaskStatus):
        return value
    text = str(value or "").strip()
    try:
        return TaskStatus(text)
    except ValueError:
        return TaskStatus.PENDING


def build_agent_task(
    *,
    task_id: str,
    assignee: str,
    instruction: str,
    status: TaskStatus | str = TaskStatus.PENDING,
    context_keys: List[str] | None = None,
    retry_count: int = 0,
    kind: str = "",
    label: str = "",
    depends_on: List[str] | None = None,
    artifact_ids: List[str] | None = None,
    blocked_reason: str = "",
) -> AgentTask:
    normalized_task_id = str(task_id or "").strip()
    normalized_instruction = str(instruction or "").strip()
    task: AgentTask = {
        "task_id": normalized_task_id,
        "assignee": str(assignee or "").strip(),
        "instruction": normalized_instruction,
        "status": _coerce_task_status(status),
        "context_keys": [
            str(value).strip()
            for value in (context_keys or [])
            if str(value).strip()
        ],
        "retry_count": int(retry_count or 0),
    }
    kind_text = str(kind or "").strip()
    if kind_text:
        task["kind"] = kind_text
    label_text = str(label or normalized_instruction or normalized_task_id).strip()
    if label_text:
        task["label"] = label_text
    dependency_ids = [
        str(value).strip()
        for value in (depends_on or [])
        if str(value).strip()
    ]
    if dependency_ids:
        task["depends_on"] = dependency_ids
    produced_artifact_ids = [
        str(value).strip()
        for value in (artifact_ids or [])
        if str(value).strip()
    ]
    if produced_artifact_ids:
        task["artifact_ids"] = produced_artifact_ids
    blocked_text = str(blocked_reason or "").strip()
    if blocked_text:
        task["blocked_reason"] = blocked_text
    return task


def build_evidence_record(
    *,
    task_id: str,
    creator: str,
    kind: str,
    source_anchor: str = "",
    claim: str = "",
    snippet: str = "",
    support_level: str = "",
    metadata: Dict[str, Any] | None = None,
) -> EvidenceRecord:
    record: EvidenceRecord = {
        "task_id": str(task_id or "").strip(),
        "creator": str(creator or "").strip(),
        "kind": str(kind or "").strip(),
        "source_anchor": str(source_anchor or "").strip(),
        "metadata": dict(metadata or {}),
    }
    claim_text = str(claim or "").strip()
    if claim_text:
        record["claim"] = claim_text
    snippet_text = str(snippet or "").strip()
    if snippet_text:
        record["snippet"] = snippet_text
    support_text = str(support_level or "").strip()
    if support_text:
        record["support_level"] = support_text
    return record


def build_artifact(
    *,
    task_id: str,
    creator: str,
    content: Any,
    artifact_id: str = "",
    kind: str = "",
    status: str = "ok",
    summary: str = "",
    payload: Dict[str, Any] | None = None,
    evidence_links: List[str] | None = None,
    evidence_refs: List[str] | None = None,
    producer_task_id: str = "",
    metadata: Dict[str, Any] | None = None,
) -> Artifact:
    normalized_task_id = str(task_id or "").strip()
    normalized_artifact_id = str(artifact_id or normalized_task_id).strip()
    normalized_links = [
        str(value).strip()
        for value in (evidence_links or evidence_refs or [])
        if str(value).strip()
    ]
    normalized_refs = [
        str(value).strip()
        for value in (evidence_refs or normalized_links)
        if str(value).strip()
    ]
    if payload is None:
        payload = dict(content) if isinstance(content, dict) else {"answer": str(content or "")}
    artifact: Artifact = {
        "task_id": normalized_task_id,
        "creator": str(creator or "").strip(),
        "artifact_id": normalized_artifact_id,
        "status": str(status or "ok").strip() or "ok",
        "summary": str(summary or "").strip(),
        "content": content,
        "payload": dict(payload),
        "evidence_links": normalized_links,
        "evidence_refs": normalized_refs,
    }
    kind_text = str(kind or "").strip()
    if kind_text:
        artifact["kind"] = kind_text
    producer_text = str(producer_task_id or "").strip()
    if producer_text:
        artifact["producer_task_id"] = producer_text
    if metadata:
        artifact["metadata"] = dict(metadata)
    return artifact


def build_critic_report(
    *,
    target_task_id: str,
    passed: bool,
    deterministic_score: float,
    feedback: str,
    target_artifact_id: str = "",
    target_artifact_ids: List[str] | None = None,
) -> CriticReport:
    normalized_target_artifact_id = str(target_artifact_id or "").strip()
    normalized_target_artifact_ids = [
        str(value).strip()
        for value in (target_artifact_ids or ([normalized_target_artifact_id] if normalized_target_artifact_id else []))
        if str(value).strip()
    ]
    feedback_text = str(feedback or "").strip()
    passed_flag = bool(passed)
    return {
        "target_task_id": str(target_task_id or "").strip(),
        "passed": passed_flag,
        "verdict": "passed" if passed_flag else "rejected",
        "target_artifact_id": normalized_target_artifact_id,
        "target_artifact_ids": normalized_target_artifact_ids,
        "deterministic_score": float(deterministic_score or 0.0),
        "acceptance_reason": feedback_text if passed_flag else "",
        "blocking_issues": [] if passed_flag else ([feedback_text] if feedback_text else []),
        "llm_feedback": feedback_text,
    }


def _dedupe_strings(values: List[str]) -> List[str]:
    seen: set[str] = set()
    normalized: List[str] = []
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        normalized.append(text)
    return normalized


def _list_strings(value: Any) -> List[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


def critic_report_runtime_acceptance_state(report: Dict[str, Any]) -> CriticRuntimeAcceptance:
    passed = bool(report.get("passed"))
    verdict = str(report.get("verdict") or report.get("status") or "").strip().lower()
    target_refs = _dedupe_strings(
        [
            str(report.get("target_task_id") or "").strip(),
            str(report.get("target_artifact_id") or "").strip(),
            *_list_strings(report.get("target_task_ids")),
            *_list_strings(report.get("target_artifact_ids")),
            *_list_strings(report.get("checked_task_ids")),
            *_list_strings(report.get("checked_artifact_ids")),
            *_list_strings(report.get("source_task_ids")),
            *_list_strings(report.get("source_artifact_ids")),
        ]
    )
    acceptance_reason = str(
        report.get("acceptance_reason")
        or report.get("rationale")
        or report.get("feedback")
        or report.get("llm_feedback")
        or ""
    ).strip()
    blocking_issues = _dedupe_strings(
        [
            *_list_strings(report.get("blocking_issues")),
            *_list_strings(report.get("issues")),
            *_list_strings(report.get("findings")),
        ]
    )
    reasons: List[str] = []
    if not target_refs:
        reasons.append("missing_target_refs")
    if passed:
        if verdict != "passed":
            reasons.append("missing_passed_verdict")
        if not acceptance_reason:
            reasons.append("missing_acceptance_reason")
        if blocking_issues:
            reasons.append("passed_report_has_blocking_issues")
    else:
        reasons.append("critic_rejected")
        if verdict != "rejected":
            reasons.append("missing_rejected_verdict")
        if not blocking_issues:
            reasons.append("missing_blocking_issues")

    accepted = passed and not reasons
    return {
        "accepted": accepted,
        "runtime_acceptance_status": "accepted" if accepted else "blocked",
        "reasons": _dedupe_strings(reasons),
        "target_refs": target_refs,
        "deterministic_score": float(report.get("deterministic_score") or 0.0),
        "deterministic_score_used_for_acceptance": False,
    }


def build_final_report_record(
    *,
    final_answer: str,
    source_task_ids: List[str],
    source_artifact_ids: List[str],
    evidence_refs: List[str],
    subtask_results: List[Dict[str, Any]] | None = None,
    status: str = "ok",
) -> FinalReport:
    return {
        "final_answer": str(final_answer or "").strip(),
        "status": str(status or "ok").strip() or "ok",
        "source_task_ids": _dedupe_strings(source_task_ids),
        "source_artifact_ids": _dedupe_strings(source_artifact_ids),
        "evidence_refs": _dedupe_strings(evidence_refs),
        "subtask_results": [dict(item) for item in (subtask_results or []) if isinstance(item, dict)],
    }


def _merge_task_ledgers(
    left: Dict[str, AgentTask], right: Dict[str, AgentTask]
) -> Dict[str, AgentTask]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def _merge_artifacts(
    left: Dict[str, Artifact], right: Dict[str, Artifact]
) -> Dict[str, Artifact]:
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def _normalise_task_status(value: Any) -> str:
    raw = value.value if isinstance(value, Enum) else value
    text = str(raw or "").strip()
    if text == TaskStatus.REJECTED_BY_CRITIC.value:
        return TaskStatus.PENDING.value
    return text


def _normalise_mas_tasks(tasks: Dict[str, AgentTask]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for task_id, task in (tasks or {}).items():
        normalized_id = str(task.get("task_id") or task_id).strip()
        records.append(
            {
                "task_id": normalized_id,
                "kind": str(task.get("kind") or TaskKind.VERIFICATION.value).strip(),
                "label": str(task.get("label") or task.get("instruction") or normalized_id).strip(),
                "status": _normalise_task_status(task.get("status")),
                "metric_family": str(task.get("assignee") or "").strip().lower(),
                "artifact_ids": [
                    str(value).strip()
                    for value in (task.get("artifact_ids") or [])
                    if str(value).strip()
                ],
            }
        )
    return records


def _artifact_payload(artifact: Artifact) -> Dict[str, Any]:
    payload = artifact.get("payload")
    if isinstance(payload, dict):
        return dict(payload)
    content = artifact.get("content")
    return dict(content) if isinstance(content, dict) else {"answer": str(content or "")}


def _normalise_mas_artifacts(artifacts: Dict[str, Artifact]) -> List[Dict[str, Any]]:
    records: List[Dict[str, Any]] = []
    for key, artifact in (artifacts or {}).items():
        artifact_id = str(artifact.get("artifact_id") or key).strip()
        task_id = str(artifact.get("task_id") or artifact.get("producer_task_id") or key).strip()
        evidence_refs = artifact.get("evidence_refs")
        if not isinstance(evidence_refs, list):
            evidence_refs = artifact.get("evidence_links") or []
        records.append(
            {
                "artifact_id": artifact_id,
                "task_id": task_id,
                "kind": str(artifact.get("kind") or ArtifactKind.AGGREGATED_ANSWER.value).strip(),
                "status": str(artifact.get("status") or "ok").strip(),
                "summary": str(artifact.get("summary") or "").strip(),
                "payload": _artifact_payload(artifact),
                "evidence_refs": [
                    str(value).strip()
                    for value in evidence_refs
                    if str(value).strip()
                ],
            }
        )
    return records


def project_mas_task_artifact_trace(state: Dict[str, Any]) -> Dict[str, Any]:
    from src.agent.financial_graph_helpers import _project_task_artifact_trace

    return _project_task_artifact_trace(
        _normalise_mas_tasks(dict(state.get("tasks") or {})),
        _normalise_mas_artifacts(dict(state.get("artifacts") or {})),
    )


def attach_task_artifact_trace(
    state: Dict[str, Any],
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    merged_state = dict(state or {})
    merged_state["tasks"] = _merge_task_ledgers(
        dict((state or {}).get("tasks") or {}),
        dict(updates.get("tasks") or {}),
    )
    merged_state["artifacts"] = _merge_artifacts(
        dict((state or {}).get("artifacts") or {}),
        dict(updates.get("artifacts") or {}),
    )
    return {
        **updates,
        "task_artifact_trace": project_mas_task_artifact_trace(merged_state),
    }


class MultiAgentState(TypedDict):
    original_query: str
    report_scope: ReportScope

    # Task ledger
    tasks: Annotated[Dict[str, AgentTask], _merge_task_ledgers]

    # Artifact store
    evidence_pool: Annotated[List[EvidenceRecord], operator.add]
    artifacts: Annotated[Dict[str, Artifact], _merge_artifacts]
    critic_reports: Annotated[List[CriticReport], operator.add]

    # Final result
    critic_feedback: Optional[str]
    final_report: Optional[str]
    final_report_record: Optional[FinalReport]
    task_artifact_trace: Dict[str, Any]
    planner_feedback: Optional[str]
    replan_budget: int
    replan_count: int

    # Execution trace
    execution_trace: Annotated[List[str], operator.add]

    # Optional control fields for skeleton/testing
    debug_force_retry_assignee: Optional[str]
    debug_retry_emitted: bool
