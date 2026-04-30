"""
Dummy node implementations for the DART MAS skeleton.

These nodes intentionally avoid real retrieval/calculation logic. They only
exercise task assignment, artifact writes, critic routing, and final merge.
"""

from __future__ import annotations

from typing import Any, Dict, List

from src.agent.mas_types import (
    AgentTask,
    Artifact,
    MultiAgentState,
    TaskStatus,
)


def _trace(message: str) -> List[str]:
    return [message]


def _artifact_answer(artifact: Dict[str, Any]) -> str:
    content = artifact.get("content")
    if isinstance(content, dict):
        return str(content.get("answer", "N/A") or "N/A")
    return str(content or "N/A")


def run_orchestrator_plan(state: MultiAgentState) -> Dict[str, Any]:
    query = state["original_query"].strip()
    tasks: Dict[str, AgentTask] = {
        "task_1": {
            "task_id": "task_1",
            "assignee": "Analyst",
            "instruction": query,
            "status": TaskStatus.PENDING,
            "context_keys": ["numeric_values"],
            "retry_count": 0,
        },
        "task_2": {
            "task_id": "task_2",
            "assignee": "Researcher",
            "instruction": f"{query}\n\n이 질문과 관련된 맥락/원인을 짧게 요약해줘.",
            "status": TaskStatus.PENDING,
            "context_keys": ["narrative_evidence"],
            "retry_count": 0,
        },
    }
    return {
        "tasks": tasks,
        "execution_trace": _trace("Orchestrator planned 2 tasks"),
    }


def run_analyst(state: MultiAgentState) -> Dict[str, Any]:
    task = state["tasks"].get("task_1")
    if not task:
        return {"execution_trace": _trace("Analyst found no assigned task")}

    was_retry = task["status"] == TaskStatus.REJECTED_BY_CRITIC
    updated_task: AgentTask = {
        **task,
        "status": TaskStatus.COMPLETED,
        "retry_count": task["retry_count"] + (1 if was_retry else 0),
    }
    artifact: Artifact = {
        "task_id": "task_1",
        "creator": "Analyst",
        "content": "1000억" if not was_retry else "1000억 (retried)",
        "evidence_links": ["dummy://analyst/task_1"],
    }
    trace = "Analyst completed task_1"
    if was_retry:
        trace += " after critic retry"
    return {
        "tasks": {"task_1": updated_task},
        "artifacts": {"task_1": artifact},
        "execution_trace": _trace(trace),
    }


def run_researcher(state: MultiAgentState) -> Dict[str, Any]:
    task = state["tasks"].get("task_2")
    if not task:
        return {"execution_trace": _trace("Researcher found no assigned task")}

    was_retry = task["status"] == TaskStatus.REJECTED_BY_CRITIC
    updated_task: AgentTask = {
        **task,
        "status": TaskStatus.COMPLETED,
        "retry_count": task["retry_count"] + (1 if was_retry else 0),
    }
    artifact: Artifact = {
        "task_id": "task_2",
        "creator": "Researcher",
        "content": (
            "AI 수요 증가와 제품 믹스 개선이 실적에 영향을 미쳤습니다."
            if not was_retry
            else "AI 수요 증가와 제품 믹스 개선이 실적에 영향을 미쳤습니다. (retried)"
        ),
        "evidence_links": ["dummy://researcher/task_2"],
    }
    trace = "Researcher completed task_2"
    if was_retry:
        trace += " after critic retry"
    return {
        "tasks": {"task_2": updated_task},
        "artifacts": {"task_2": artifact},
        "execution_trace": _trace(trace),
    }
def run_orchestrator_merge(state: MultiAgentState) -> Dict[str, Any]:
    task_1_artifact = state.get("artifacts", {}).get("task_1", {})
    task_2_artifact = state.get("artifacts", {}).get("task_2", {})
    task_1 = _artifact_answer(task_1_artifact)
    task_2 = _artifact_answer(task_2_artifact)
    final_report = f"매출은 {task_1}이고, 이유는 {task_2}입니다."
    return {
        "final_report": final_report,
        "execution_trace": _trace("Orchestrator merged final report"),
    }
