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
    attach_task_artifact_trace,
    build_agent_task,
    build_artifact,
    build_final_report_record,
)
from src.schema import ArtifactKind, TaskKind


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
            "kind": TaskKind.CALCULATION.value,
            "label": "Analyst worker task",
        },
        "task_2": {
            "task_id": "task_2",
            "assignee": "Researcher",
            "instruction": f"{query}\n\n이 질문과 관련된 맥락/원인을 짧게 요약해줘.",
            "status": TaskStatus.PENDING,
            "context_keys": ["narrative_evidence"],
            "retry_count": 0,
            "kind": TaskKind.RETRIEVAL.value,
            "label": "Researcher worker task",
        },
    }
    return attach_task_artifact_trace(state, {
        "tasks": tasks,
        "execution_trace": _trace("Orchestrator planned 2 tasks"),
    })


def run_analyst(state: MultiAgentState) -> Dict[str, Any]:
    task = state["tasks"].get("task_1")
    if not task:
        return {"execution_trace": _trace("Analyst found no assigned task")}

    was_retry = task["status"] == TaskStatus.REJECTED_BY_CRITIC
    updated_task: AgentTask = {
        **task,
        "status": TaskStatus.COMPLETED,
        "retry_count": task["retry_count"] + (1 if was_retry else 0),
        "artifact_ids": ["task_1::operand_set", "task_1::calculation_plan", "task_1"],
    }
    answer = "1000억" if not was_retry else "1000억 (retried)"
    evidence_refs = ["dummy://analyst/task_1"]
    artifacts: Dict[str, Artifact] = {
        "task_1::operand_set": build_artifact(
            task_id="task_1",
            creator="Analyst",
            artifact_id="task_1::operand_set",
            kind=ArtifactKind.OPERAND_SET.value,
            status="ok",
            summary="1 operands",
            content={"calculation_operands": [{"label": "dummy value", "value": "1000", "row_id": evidence_refs[0]}]},
            payload={"calculation_operands": [{"label": "dummy value", "value": "1000", "row_id": evidence_refs[0]}]},
            evidence_links=evidence_refs,
        ),
        "task_1::calculation_plan": build_artifact(
            task_id="task_1",
            creator="Analyst",
            artifact_id="task_1::calculation_plan",
            kind=ArtifactKind.CALCULATION_PLAN.value,
            status="ok",
            summary="lookup",
            content={"calculation_plan": {"mode": "lookup"}},
            payload={"calculation_plan": {"mode": "lookup"}},
            evidence_links=evidence_refs,
        ),
        "task_1": build_artifact(
            task_id="task_1",
            creator="Analyst",
            artifact_id="task_1",
            kind=ArtifactKind.CALCULATION_RESULT.value,
            status="ok",
            summary=answer,
            content=answer,
            payload={"answer": answer, "calculation_result": {"status": "ok", "rendered_value": answer}},
            evidence_links=evidence_refs,
        ),
    }
    trace = "Analyst completed task_1"
    if was_retry:
        trace += " after critic retry"
    return {
        "tasks": {"task_1": updated_task},
        "artifacts": artifacts,
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
        "artifact_ids": ["task_2"],
    }
    answer = (
        "AI 수요 증가와 제품 믹스 개선이 실적에 영향을 미쳤습니다."
        if not was_retry
        else "AI 수요 증가와 제품 믹스 개선이 실적에 영향을 미쳤습니다. (retried)"
    )
    artifact = build_artifact(
        task_id="task_2",
        creator="Researcher",
        artifact_id="task_2",
        kind=ArtifactKind.RETRIEVAL_BUNDLE.value,
        status="ok",
        summary=answer,
        content=answer,
        payload={
            "answer": answer,
            "retrieved_docs": [
                {
                    "chunk_id": "dummy://researcher/task_2",
                    "source_anchor": "dummy://researcher/task_2",
                    "text": answer,
                }
            ],
        },
        evidence_links=["dummy://researcher/task_2"],
    )
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
    source_artifact_ids = [
        str(artifact.get("artifact_id") or key)
        for key, artifact in (state.get("artifacts") or {}).items()
        if artifact.get("creator") in {"Analyst", "Researcher"}
    ]
    source_task_ids = ["task_1", "task_2"]
    final_report_record = build_final_report_record(
        final_answer=final_report,
        source_task_ids=source_task_ids,
        source_artifact_ids=source_artifact_ids,
        evidence_refs=source_artifact_ids,
        subtask_results=[
            {
                "task_id": "task_1",
                "artifact_id": "task_1",
                "source_artifact_id": "task_1",
                "answer": task_1,
            },
            {
                "task_id": "task_2",
                "artifact_id": "task_2",
                "source_artifact_id": "task_2",
                "answer": task_2,
            },
        ],
    )
    synthesis_task = build_agent_task(
        task_id="synthesis::final",
        assignee="Orchestrator",
        instruction="Synthesize final report from accepted artifacts.",
        status=TaskStatus.COMPLETED,
        context_keys=["artifact_store"],
        kind=TaskKind.SYNTHESIS.value,
        label="Final report synthesis",
        artifact_ids=["synthesis::final"],
    )
    synthesis_artifact = build_artifact(
        task_id="synthesis::final",
        creator="Orchestrator",
        artifact_id="synthesis::final",
        kind=ArtifactKind.AGGREGATED_ANSWER.value,
        status="ok",
        summary=final_report,
        content={"answer": final_report},
        payload={**final_report_record},
        evidence_links=source_artifact_ids,
    )
    return attach_task_artifact_trace(state, {
        "tasks": {"synthesis::final": synthesis_task},
        "artifacts": {"synthesis::final": synthesis_artifact},
        "final_report": final_report,
        "final_report_record": final_report_record,
        "execution_trace": _trace("Orchestrator merged final report"),
    })
