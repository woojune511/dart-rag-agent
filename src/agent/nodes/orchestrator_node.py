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

from src.agent.mas_types import AgentTask, Artifact, MultiAgentState, ReportScope, TaskStatus

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
    lowered = text.lower()
    numeric_signals = [
        "얼마",
        "비중",
        "차이",
        "증가",
        "감소",
        "계산",
        "매출",
        "영업이익",
        "%",
        "ratio",
        "compare",
    ]
    narrative_signals = [
        "무엇",
        "왜",
        "원인",
        "리스크",
        "설명",
        "요약",
        "현황",
        "사업",
        "맥락",
        "성과",
    ]

    tasks: List[Dict[str, Any]] = []
    if any(signal in text or signal in lowered for signal in numeric_signals):
        tasks.append(
            {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": text,
            }
        )
    if any(signal in text or signal in lowered for signal in narrative_signals):
        tasks.append(
            {
                "task_id": "task_2",
                "assignee": "Researcher",
                "instruction": f"{text}\n\n이 질문과 관련된 맥락/원인을 짧게 요약해줘.",
            }
        )

    if not tasks:
        tasks = [
            {
                "task_id": "task_1",
                "assignee": "Analyst",
                "instruction": text,
            }
        ]
    if len(tasks) == 1 and tasks[0]["assignee"] == "Analyst":
        tasks.append(
            {
                "task_id": "task_2",
                "assignee": "Researcher",
                "instruction": f"{text}\n\n이 질문과 관련된 맥락/원인을 짧게 요약해줘.",
            }
        )

    return {"tasks": tasks[:2]}


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
            {
                "task_id": task_id,
                "assignee": assignee,
                "instruction": instruction,
                "status": TaskStatus.PENDING,
                "context_keys": list(item.get("context_keys") or _context_keys_for_assignee(assignee)),
                "retry_count": 0,
            }
        )
    if not normalized:
        raise ValueError("Planner produced no valid tasks.")
    return normalized


def _artifact_answer(artifact: Artifact) -> str:
    content = artifact.get("content")
    if isinstance(content, dict):
        return str(content.get("answer") or "").strip()
    return str(content or "").strip()


def _artifact_lines(artifacts: Dict[str, Artifact], creator: str) -> List[str]:
    lines: List[str] = []
    for task_id, artifact in (artifacts or {}).items():
        if artifact.get("creator") != creator:
            continue
        answer = _artifact_answer(artifact)
        if not answer:
            continue
        evidence_links = ", ".join(str(item) for item in artifact.get("evidence_links", []) if str(item).strip())
        suffix = f" | evidence={evidence_links}" if evidence_links else ""
        lines.append(f"{task_id}: {answer}{suffix}")
    return lines


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


class FinancialOrchestratorMergeCore:
    def __init__(self) -> None:
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.prompt = ChatPromptTemplate.from_template(
            """당신은 금융 데이터 분석 보고서를 작성하는 Orchestrator입니다.

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
        scope = dict(state.get("report_scope") or {})
        try:
            payload = core_runner.run(query, report_scope=scope)
        except Exception:
            payload = _fallback_plan(query)

        tasks = _normalize_plan_tasks(payload)
        task_ledger = {task["task_id"]: task for task in tasks}
        return {
            "tasks": task_ledger,
            "execution_trace": _trace(f"Orchestrator planned {len(task_ledger)} tasks"),
        }

    return run_orchestrator_plan


def make_run_orchestrator_merge(
    core_runner: OrchestratorMergeCore,
) -> Callable[[MultiAgentState], Dict[str, Any]]:
    def run_orchestrator_merge(state: MultiAgentState) -> Dict[str, Any]:
        query = str(state.get("original_query") or "").strip()
        scope = dict(state.get("report_scope") or {})
        artifacts = dict(state.get("artifacts") or {})
        critic_feedback = state.get("critic_feedback")

        try:
            payload = core_runner.run(
                query,
                report_scope=scope,
                artifacts=artifacts,
                critic_feedback=str(critic_feedback or ""),
            )
            final_report = str(payload.get("final_report") or "").strip()
        except Exception:
            analyst_lines = _artifact_lines(artifacts, "Analyst")
            researcher_lines = _artifact_lines(artifacts, "Researcher")
            merged = analyst_lines + researcher_lines
            final_report = "\n".join(merged) if merged else "현재 확보된 산출물이 없습니다."

        return {
            "final_report": final_report,
            "execution_trace": _trace("Orchestrator synthesized final report"),
        }

    return run_orchestrator_merge


def build_financial_orchestrator_plan_node() -> Callable[[MultiAgentState], Dict[str, Any]]:
    return make_run_orchestrator_plan(FinancialOrchestratorPlannerCore())


def build_financial_orchestrator_merge_node() -> Callable[[MultiAgentState], Dict[str, Any]]:
    return make_run_orchestrator_merge(FinancialOrchestratorMergeCore())
