"""
Orchestrator nodes for the DART MAS graph.

These nodes are responsible for:
1. planning worker tasks from the user's original question, and
2. synthesizing validated worker artifacts into the final report.
"""

from __future__ import annotations

import json
import os
import re
from typing import Any, Callable, Dict, List, Protocol, Sequence

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI

from src.agent.mas_types import (
    AgentTask,
    Artifact,
    MultiAgentState,
    ReportScope,
    TaskStatus,
    attach_task_artifact_trace,
    build_agent_task,
    build_artifact,
    build_final_report_record,
    project_worker_artifact_boundary,
)
from src.schema import ArtifactKind, TaskKind

load_dotenv()


class OrchestratorPlannerCore(Protocol):
    def run(self, query: str, *, report_scope: ReportScope | None = None) -> Dict[str, Any]:
        ...


class OrchestratorMergeCore(Protocol):
    def run(
        self,
        query: str,
        *,
        report_scope: ReportScope | None = None,
        artifacts: Dict[str, Artifact] | None = None,
        critic_feedback: str | None = None,
    ) -> Dict[str, Any]:
        ...


def _trace(message: str) -> List[str]:
    return [message]


def _context_keys_for_assignee(assignee: str) -> List[str]:
    key = str(assignee or "").strip().lower()
    if key == "analyst":
        return ["numeric_values"]
    if key == "researcher":
        return ["narrative_evidence"]
    return []


def _task_kind_for_assignee(assignee: str) -> str:
    key = str(assignee or "").strip().lower()
    if key == "analyst":
        return TaskKind.CALCULATION.value
    if key == "researcher":
        return TaskKind.RETRIEVAL.value
    return TaskKind.VERIFICATION.value


def _extract_json_payload(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    if not raw:
        raise ValueError("Empty planner response.")

    fence_match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, flags=re.DOTALL)
    if fence_match:
        raw = fence_match.group(1).strip()
    else:
        start = raw.find("{")
        end = raw.rfind("}")
        if start >= 0 and end >= start:
            raw = raw[start : end + 1]

    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise ValueError("Planner response was not a JSON object.")
    return payload


def _fallback_plan(query: str) -> Dict[str, Any]:
    text = str(query or "").strip()
    base = text or "(empty user query)"
    return {
        "tasks": [
            {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": (
                    f"{base}\n\n"
                    "Task: handle any numeric, table-backed, or calculation requirement. "
                    "Use only available evidence; if not applicable, return a limitation."
                ),
            },
            {
                "task_id": "task_2",
                "assignee": "Researcher",
                "instruction": (
                    f"{base}\n\n"
                    "Task: handle any narrative, contextual, or explanatory requirement. "
                    "Use only available evidence; if not applicable, return a limitation."
                ),
            },
        ]
    }


def _normalize_plan_tasks(payload: Dict[str, Any]) -> List[AgentTask]:
    raw_tasks = payload.get("tasks") or []
    if not isinstance(raw_tasks, Sequence):
        raise ValueError("Planner response missing task list.")

    normalized: List[AgentTask] = []
    for index, item in enumerate(raw_tasks, start=1):
        if not isinstance(item, dict):
            continue
        assignee = str(item.get("assignee") or "").strip()
        instruction = str(item.get("instruction") or "").strip()
        if assignee not in {"Analyst", "Researcher"} or not instruction:
            continue
        task_id = str(item.get("task_id") or f"task_{index}").strip() or f"task_{index}"
        normalized.append(
            build_agent_task(
                task_id=task_id,
                assignee=assignee,
                instruction=instruction,
                context_keys=list(item.get("context_keys") or _context_keys_for_assignee(assignee)),
                kind=_task_kind_for_assignee(assignee),
                label=str(item.get("label") or instruction).strip(),
            )
        )
    if not normalized:
        raise ValueError("Planner produced no valid tasks.")
    return normalized


def _artifact_payload(artifact: Artifact) -> Dict[str, Any]:
    return dict(project_worker_artifact_boundary(artifact).get("payload") or {})


def _artifact_answer(artifact: Artifact) -> str:
    return str(project_worker_artifact_boundary(artifact).get("answer") or "").strip()


def _artifact_refs(artifact: Artifact) -> List[str]:
    return list(project_worker_artifact_boundary(artifact).get("evidence_refs") or [])


def _blocking_integrity_issues(trace: Dict[str, Any]) -> List[Dict[str, Any]]:
    if str(trace.get("integrity_status") or "").strip().lower() != "error":
        return []
    return [
        dict(issue)
        for issue in (trace.get("integrity_issues") or [])
        if isinstance(issue, dict) and str(issue.get("severity") or "").strip().lower() == "error"
    ]


def _issue_list_field(issue: Dict[str, Any], key: str) -> List[str]:
    value = issue.get(key)
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _integrity_issue_detail(issue: Dict[str, Any]) -> str:
    issue_type = str(issue.get("type") or "").strip()
    parts = [issue_type] if issue_type else ["task_artifact_integrity_error"]
    for key in ("task_id", "artifact_kind", "payload_key"):
        text = str(issue.get(key) or "").strip()
        if text:
            parts.append(text)
    if issue_type == "critic_report_rejected":
        status = str(issue.get("runtime_acceptance_status") or "").strip()
        if status:
            parts.append(f"status={status}")
        reasons = _issue_list_field(issue, "reasons")
        if reasons:
            parts.append(f"reasons={','.join(reasons[:3])}")
        target_refs = _issue_list_field(issue, "target_refs")
        if target_refs:
            parts.append(f"targets={','.join(target_refs[:3])}")
    return ":".join(parts)


def _integrity_issue_summary(issues: List[Dict[str, Any]]) -> str:
    issue_details: List[str] = []
    seen: set[str] = set()
    for issue in issues:
        issue_detail = _integrity_issue_detail(issue)
        if not issue_detail or issue_detail in seen:
            continue
        seen.add(issue_detail)
        issue_details.append(issue_detail)
    return ", ".join(issue_details[:5]) or "task_artifact_integrity_error"


def _blocked_final_report(final_report: str, issues: List[Dict[str, Any]]) -> str:
    partial = str(final_report or "").strip()
    notice = (
        "Cannot close as fully answered because required task/artifact "
        f"contract checks failed: {_integrity_issue_summary(issues)}."
    )
    return f"{partial}\n\n{notice}" if partial else notice


def _planner_feedback_from_integrity_issues(issues: List[Dict[str, Any]]) -> str:
    return (
        "Replan required because task/artifact contract checks failed: "
        f"{_integrity_issue_summary(issues)}."
    )


def _task_ids_from_integrity_issues(issues: List[Dict[str, Any]]) -> List[str]:
    task_ids: List[str] = []
    seen: set[str] = set()
    for issue in issues:
        for key in ("task_id", "producer_task_id", "source_task_id", "target_task_id"):
            task_id = str(issue.get(key) or "").strip()
            if task_id and task_id not in seen:
                seen.add(task_id)
                task_ids.append(task_id)
        for key in ("source_task_ids", "target_task_ids", "target_refs"):
            for task_id in _issue_list_field(issue, key):
                if task_id and task_id not in seen:
                    seen.add(task_id)
                    task_ids.append(task_id)
    return task_ids


def _task_updates_for_replan_carry_forward(state: MultiAgentState) -> Dict[str, AgentTask]:
    issues = _blocking_integrity_issues(dict(state.get("task_artifact_trace") or {}))
    if not issues:
        return {}
    blocked_reason = _integrity_issue_summary(issues)
    updates: Dict[str, AgentTask] = {}
    for task_id in _task_ids_from_integrity_issues(issues):
        task = dict((state.get("tasks") or {}).get(task_id) or {})
        if not task:
            continue
        updates[task_id] = {
            **task,
            "status": TaskStatus.FAILED,
            "artifact_ids": [],
            "blocked_reason": blocked_reason,
        }
    return updates


def _query_with_planner_feedback(query: str, planner_feedback: str) -> str:
    feedback = str(planner_feedback or "").strip()
    if not feedback:
        return query
    return f"{query}\n\n[planner feedback]\n{feedback}"


def _replan_budget_remaining(state: MultiAgentState) -> bool:
    budget = int(state.get("replan_budget", 0) or 0)
    count = int(state.get("replan_count", 0) or 0)
    return count < budget


def _artifact_lines(artifacts: Dict[str, Artifact], creator: str) -> List[str]:
    lines: List[str] = []
    for task_id, artifact in (artifacts or {}).items():
        if artifact.get("creator") != creator:
            continue
        answer = _artifact_answer(artifact)
        if not answer:
            continue
        evidence_refs = ", ".join(_artifact_refs(artifact))
        suffix = f" | evidence={evidence_refs}" if evidence_refs else ""
        lines.append(f"{task_id}: {answer}{suffix}")
    return lines


def _accepted_worker_source_artifacts(state: MultiAgentState) -> Dict[str, Artifact]:
    tasks = dict(state.get("tasks") or {})
    artifacts = dict(state.get("artifacts") or {})
    completed_task_ids = {
        str(task.get("task_id") or task_id).strip()
        for task_id, task in tasks.items()
        if task.get("assignee") in {"Analyst", "Researcher"}
        and task.get("status") == TaskStatus.COMPLETED
    }
    referenced_artifact_ids = {
        str(artifact_id).strip()
        for task_id, task in tasks.items()
        if str(task.get("task_id") or task_id).strip() in completed_task_ids
        for artifact_id in (task.get("artifact_ids") or [])
        if str(artifact_id).strip()
    }
    return {
        key: artifact
        for key, artifact in artifacts.items()
        if artifact.get("creator") in {"Analyst", "Researcher"}
        and str(artifact.get("task_id") or "").strip() in completed_task_ids
        and str(artifact.get("artifact_id") or key).strip() in referenced_artifact_ids
    }


def _subtask_results(artifacts: Dict[str, Artifact]) -> List[Dict[str, str]]:
    results: List[Dict[str, str]] = []
    seen_task_ids: set[str] = set()
    for key, artifact in (artifacts or {}).items():
        answer = _artifact_answer(artifact)
        if not answer:
            continue
        task_id = str(artifact.get("task_id") or key).strip()
        if not task_id or task_id in seen_task_ids:
            continue
        artifact_id = str(artifact.get("artifact_id") or key).strip()
        seen_task_ids.add(task_id)
        results.append(
            {
                "task_id": task_id,
                "artifact_id": artifact_id,
                "source_artifact_id": artifact_id,
                "answer": answer,
            }
        )
    return results


class FinancialOrchestratorPlannerCore:
    def __init__(self) -> None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.prompt = ChatPromptTemplate.from_template(
            """당신은 DART 공시 분석 멀티 에이전트 시스템의 최고 책임자(Orchestrator)입니다.

사용자의 질문을 보고 하위 작업으로 분해하세요.

[하위 에이전트 역할]
1. Analyst
- 정량 수치 추출
- 비율/증감률/차이/합계 계산
- 표 기반 재무 질문 처리

2. Researcher
- 사업/리스크/연구개발/주석/경영진단 등 비정형 텍스트 맥락 요약
- Why / How / 주요 포인트 설명

[규칙]
- 질문에 계산이나 명시적 수치 답이 필요하면 Analyst task를 만드세요.
- 질문에 설명, 배경, 리스크, 사업 맥락이 필요하면 Researcher task를 만드세요.
- 복합 질문이면 두 task를 모두 만드세요.
- task는 최대 2개까지만 만드세요.
- 각 instruction은 하위 에이전트가 바로 실행할 수 있게 구체적으로 쓰세요.
- 출력은 반드시 JSON 객체 하나만 반환하세요.

[출력 형식]
{{
  "tasks": [
    {{
      "task_id": "task_1",
      "assignee": "Analyst" | "Researcher",
      "instruction": "구체적인 작업 지시",
      "context_keys": ["numeric_values"] | ["narrative_evidence"]
    }}
  ]
}}

[report scope]
company={company}
year={year}
report_type={report_type}
consolidation={consolidation}

[user question]
{question}
"""
        )

    def run(self, query: str, *, report_scope: ReportScope | None = None) -> Dict[str, Any]:
        scope = dict(report_scope or {})
        raw = (self.prompt | self.llm | StrOutputParser()).invoke(
            {
                "question": query,
                "company": str(scope.get("company") or ""),
                "year": str(scope.get("year") or ""),
                "report_type": str(scope.get("report_type") or ""),
                "consolidation": str(scope.get("consolidation") or ""),
            }
        )
        return _extract_json_payload(raw)


MERGE_ANSWER_COMPRESSION_GUIDANCE = """[additional compression policy]
- Start with the direct numeric conclusion when an Analyst result is present.
- Then compress Researcher context into 2-4 material points only.
- Preserve worker-provided values, signs, units, and periods exactly.
- Do not copy evidence refs, artifact ids, or internal task ids into the final answer.
- Avoid repeating the same claim across the numeric and narrative parts.

"""


class FinancialOrchestratorMergeCore:
    def __init__(self) -> None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.prompt = ChatPromptTemplate.from_template(
            MERGE_ANSWER_COMPRESSION_GUIDANCE
            + """당신은 금융 데이터 분석 보고서를 작성하는 Orchestrator입니다.

아래 Analyst / Researcher 산출물만 사용해서 사용자의 질문에 답하세요.

[규칙]
- 제공된 산출물 밖의 사실을 추가하지 마세요.
- 수치와 맥락을 자연스럽게 연결하세요.
- 2~5문장으로 간결하게 쓰세요.
- 한쪽 산출물만 있어도 그 범위 안에서 최대한 답하세요.
- 모르면 현재 확보된 산출물 기준으로만 한계를 말하세요.

[report scope]
company={company}
year={year}
report_type={report_type}

[user question]
{question}

[critic feedback]
{critic_feedback}

[Analyst artifacts]
{analyst_artifacts}

[Researcher artifacts]
{researcher_artifacts}

최종 답변:"""
        )

    def run(
        self,
        query: str,
        *,
        report_scope: ReportScope | None = None,
        artifacts: Dict[str, Artifact] | None = None,
        critic_feedback: str | None = None,
    ) -> Dict[str, Any]:
        scope = dict(report_scope or {})
        analyst_artifacts = "\n".join(_artifact_lines(artifacts or {}, "Analyst")) or "(none)"
        researcher_artifacts = "\n".join(_artifact_lines(artifacts or {}, "Researcher")) or "(none)"
        answer = (self.prompt | self.llm | StrOutputParser()).invoke(
            {
                "company": str(scope.get("company") or ""),
                "year": str(scope.get("year") or ""),
                "report_type": str(scope.get("report_type") or ""),
                "question": query,
                "critic_feedback": str(critic_feedback or ""),
                "analyst_artifacts": analyst_artifacts,
                "researcher_artifacts": researcher_artifacts,
            }
        )
        return {"final_report": str(answer or "").strip()}


def make_run_orchestrator_plan(
    core_runner: OrchestratorPlannerCore,
) -> Callable[[MultiAgentState], Dict[str, Any]]:
    def run_orchestrator_plan(state: MultiAgentState) -> Dict[str, Any]:
        query = str(state.get("original_query") or "").strip()
        planner_feedback = str(state.get("planner_feedback") or "").strip()
        planning_query = _query_with_planner_feedback(query, planner_feedback)
        scope = dict(state.get("report_scope") or {})
        try:
            payload = core_runner.run(planning_query, report_scope=scope)
        except Exception:
            payload = _fallback_plan(planning_query)

        tasks = _normalize_plan_tasks(payload)
        task_ledger = {
            **_task_updates_for_replan_carry_forward(state),
            **{task["task_id"]: task for task in tasks},
        }
        mode = "replanned" if planner_feedback else "planned"
        return attach_task_artifact_trace(state, {
            "tasks": task_ledger,
            "planner_feedback": None if planner_feedback else state.get("planner_feedback"),
            "execution_trace": _trace(f"Orchestrator {mode} {len(tasks)} tasks"),
        })

    return run_orchestrator_plan


def make_run_orchestrator_merge(
    core_runner: OrchestratorMergeCore,
) -> Callable[[MultiAgentState], Dict[str, Any]]:
    def run_orchestrator_merge(state: MultiAgentState) -> Dict[str, Any]:
        query = str(state.get("original_query") or "").strip()
        scope = dict(state.get("report_scope") or {})
        source_artifacts = _accepted_worker_source_artifacts(state)
        critic_feedback = state.get("critic_feedback")

        try:
            payload = core_runner.run(
                query,
                report_scope=scope,
                artifacts=source_artifacts,
                critic_feedback=str(critic_feedback or ""),
            )
            final_report = str(payload.get("final_report") or "").strip()
        except Exception:
            analyst_lines = _artifact_lines(source_artifacts, "Analyst")
            researcher_lines = _artifact_lines(source_artifacts, "Researcher")
            merged = analyst_lines + researcher_lines
            final_report = "\n".join(merged) if merged else "현재 확보된 산출물이 없습니다."

        source_artifact_ids = [
            str(artifact.get("artifact_id") or key).strip()
            for key, artifact in source_artifacts.items()
            if str(artifact.get("artifact_id") or key).strip()
        ]
        source_task_ids = [
            str(artifact.get("task_id") or key).strip()
            for key, artifact in source_artifacts.items()
            if str(artifact.get("task_id") or key).strip()
        ]
        evidence_refs = [
            str(value).strip()
            for artifact in source_artifacts.values()
            for value in _artifact_refs(artifact)
            if str(value).strip()
        ] or source_artifact_ids
        subtask_results = _subtask_results(source_artifacts)
        final_report_record = build_final_report_record(
            final_answer=final_report,
            source_task_ids=source_task_ids,
            source_artifact_ids=source_artifact_ids,
            evidence_refs=evidence_refs,
            subtask_results=subtask_results,
        )
        final_evidence_refs = list(final_report_record.get("evidence_refs") or [])
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
            evidence_links=final_evidence_refs,
        )
        updates = {
            "tasks": {"synthesis::final": synthesis_task},
            "artifacts": {"synthesis::final": synthesis_artifact},
            "final_report": final_report,
            "final_report_record": final_report_record,
            "execution_trace": _trace("Orchestrator synthesized final report"),
        }
        projected_updates = attach_task_artifact_trace(state, updates)
        blocking_issues = _blocking_integrity_issues(
            dict(projected_updates.get("task_artifact_trace") or {})
        )
        if not blocking_issues:
            return projected_updates

        planner_feedback = _planner_feedback_from_integrity_issues(blocking_issues)
        if _replan_budget_remaining(state):
            replan_record = build_final_report_record(
                final_answer="",
                source_task_ids=source_task_ids,
                source_artifact_ids=source_artifact_ids,
                evidence_refs=evidence_refs,
                subtask_results=subtask_results,
                status="replan_required",
            )
            return attach_task_artifact_trace(state, {
                "planner_feedback": planner_feedback,
                "replan_count": int(state.get("replan_count", 0) or 0) + 1,
                "final_report": None,
                "final_report_record": replan_record,
                "execution_trace": _trace("Orchestrator requested replan on integrity errors"),
            })

        blocked_report = _blocked_final_report(final_report, blocking_issues)
        blocked_record = build_final_report_record(
            final_answer=blocked_report,
            source_task_ids=source_task_ids,
            source_artifact_ids=source_artifact_ids,
            evidence_refs=evidence_refs,
            subtask_results=subtask_results,
            status="blocked",
        )
        blocked_evidence_refs = list(blocked_record.get("evidence_refs") or [])
        blocked_task = {
            **synthesis_task,
            "status": TaskStatus.FAILED,
            "blocked_reason": _integrity_issue_summary(blocking_issues),
        }
        blocked_artifact = build_artifact(
            task_id="synthesis::final",
            creator="Orchestrator",
            artifact_id="synthesis::final",
            kind=ArtifactKind.AGGREGATED_ANSWER.value,
            status="blocked",
            summary=blocked_report,
            content={"answer": blocked_report},
            payload={
                **blocked_record,
                "blocking_integrity_issues": blocking_issues,
            },
            evidence_links=blocked_evidence_refs,
        )
        return attach_task_artifact_trace(state, {
            "tasks": {"synthesis::final": blocked_task},
            "artifacts": {"synthesis::final": blocked_artifact},
            "final_report": blocked_report,
            "final_report_record": blocked_record,
            "planner_feedback": planner_feedback,
            "execution_trace": _trace("Orchestrator blocked final report on integrity errors"),
        })

    return run_orchestrator_merge


def build_financial_orchestrator_plan_node() -> Callable[[MultiAgentState], Dict[str, Any]]:
    return make_run_orchestrator_plan(FinancialOrchestratorPlannerCore())


def build_financial_orchestrator_merge_node() -> Callable[[MultiAgentState], Dict[str, Any]]:
    return make_run_orchestrator_merge(FinancialOrchestratorMergeCore())
