"""
Deterministic critic layer for the DART MAS skeleton.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Tuple

from src.agent.mas_types import AgentTask, Artifact, CriticReport, MultiAgentState, TaskStatus

MAX_CRITIC_RETRIES = 2
_PERCENT_RE = re.compile(r"\d+(?:\.\d+)?%")
_KRW_RE = re.compile(r"\d[\d,]*(?:조|억원|원|백만원)")


def _trace(message: str) -> List[str]:
    return [message]


def _artifact_answer(artifact: Artifact) -> str:
    content = artifact.get("content")
    if isinstance(content, dict):
        return str(content.get("answer") or "").strip()
    return str(content or "").strip()


def _artifact_calc_result(artifact: Artifact) -> Dict[str, Any]:
    content = artifact.get("content")
    if isinstance(content, dict):
        return dict(content.get("calculation_result") or {})
    return {}


def _apply_rejection(
    task: AgentTask,
    feedback: List[str],
) -> Tuple[AgentTask, bool]:
    retry_count = int(task.get("retry_count", 0) or 0)
    if retry_count >= MAX_CRITIC_RETRIES:
        return (
            {
                **task,
                "status": TaskStatus.FAILED,
            },
            False,
        )
    return (
        {
            **task,
            "status": TaskStatus.REJECTED_BY_CRITIC,
        },
        True,
    )


def _evaluate_analyst_artifact(task: AgentTask, artifact: Artifact | None) -> Tuple[bool, float, str]:
    passed = True
    score = 1.0
    feedback: List[str] = []

    if artifact is None:
        return False, 0.0, "Analyst artifact is missing."

    answer = _artifact_answer(artifact)
    if not answer:
        passed = False
        score -= 0.4
        feedback.append("결과 답변이 비어 있습니다.")

    evidence_links = [str(item).strip() for item in artifact.get("evidence_links", []) if str(item).strip()]
    if not evidence_links:
        passed = False
        score -= 0.4
        feedback.append("계산 근거 링크가 없습니다. (grounding 실패)")

    calc_result = _artifact_calc_result(artifact)
    calc_status = str(calc_result.get("status") or "").strip().lower()
    if calc_status and calc_status not in {"ok", "success"}:
        passed = False
        score -= 0.3
        feedback.append(f"계산 상태가 비정상입니다: {calc_status}")

    rendered_value = str(calc_result.get("rendered_value") or "").strip()
    if rendered_value and rendered_value not in answer:
        passed = False
        score -= 0.2
        feedback.append("답변에 계산 결과(rendered_value)가 포함되지 않았습니다.")

    result_unit = str(calc_result.get("result_unit") or "").strip()
    if result_unit == "%" and answer and not _PERCENT_RE.search(answer):
        passed = False
        score -= 0.1
        feedback.append("퍼센트 결과인데 답변 형식에 %가 없습니다.")
    if result_unit in {"KRW", "백만원", "억원", "원"} and answer and rendered_value:
        if not (_KRW_RE.search(answer) or "원" in answer):
            passed = False
            score -= 0.1
            feedback.append("금액 결과인데 답변 형식에 원 단위 표기가 없습니다.")

    return passed, max(score, 0.0), " | ".join(feedback) if feedback else "통과 (Deterministic 1층)"


def _evaluate_researcher_artifact(task: AgentTask, artifact: Artifact | None) -> Tuple[bool, float, str]:
    passed = True
    score = 1.0
    feedback: List[str] = []

    if artifact is None:
        return False, 0.0, "Researcher artifact is missing."

    answer = _artifact_answer(artifact)
    if len(answer) < 10:
        passed = False
        score -= 0.5
        feedback.append("리서치 결과가 너무 짧습니다.")

    evidence_links = [str(item).strip() for item in artifact.get("evidence_links", []) if str(item).strip()]
    if not evidence_links:
        passed = False
        score -= 0.4
        feedback.append("리서치 근거 링크가 없습니다. (grounding 실패)")

    return passed, max(score, 0.0), " | ".join(feedback) if feedback else "통과 (Deterministic 1층)"


def run_critic(state: MultiAgentState) -> Dict[str, Any]:
    tasks = dict(state.get("tasks", {}) or {})
    artifacts = dict(state.get("artifacts", {}) or {})
    force_retry = str(state.get("debug_force_retry_assignee") or "").strip().lower()
    retry_emitted = bool(state.get("debug_retry_emitted", False))

    critic_reports: List[CriticReport] = []
    task_updates: Dict[str, AgentTask] = {}
    should_retry = False
    feedback_lines: List[str] = []

    for task_id, task in tasks.items():
        artifact = artifacts.get(task_id)
        assignee = str(task.get("assignee") or "")

        if assignee == "Analyst":
            passed, score, feedback = _evaluate_analyst_artifact(task, artifact)
        elif assignee == "Researcher":
            passed, score, feedback = _evaluate_researcher_artifact(task, artifact)
        else:
            passed = artifact is not None
            score = 1.0 if passed else 0.0
            feedback = "통과 (Deterministic 1층)" if passed else "Unknown assignee artifact is missing."

        if force_retry and not retry_emitted and assignee.lower() == force_retry:
            passed = False
            score = 0.0
            feedback = f"Forced retry for {assignee} skeleton path."
            retry_emitted = True

        if not passed:
            updated_task, can_retry = _apply_rejection(task, [feedback])
            task_updates[task_id] = updated_task
            should_retry = should_retry or can_retry
            if updated_task["status"] == TaskStatus.FAILED:
                feedback = f"{feedback} | 최대 재시도 횟수를 초과하여 최종 실패 처리됨."
            feedback_lines.append(f"{task_id}: {feedback}")

        critic_reports.append(
            {
                "target_task_id": task_id,
                "passed": passed,
                "deterministic_score": score,
                "llm_feedback": feedback,
            }
        )

    critic_feedback = (
        "Critic passed all artifacts (Deterministic)"
        if not feedback_lines
        else "Critic rejected some artifacts (Deterministic): " + " ; ".join(feedback_lines)
    )
    trace_message = (
        "Critic passed all artifacts (Deterministic)"
        if not should_retry and not feedback_lines
        else "Critic rejected some artifacts (Deterministic)"
    )

    return {
        "critic_reports": critic_reports,
        "critic_feedback": critic_feedback,
        "tasks": task_updates,
        "debug_retry_emitted": retry_emitted,
        "execution_trace": _trace(trace_message),
    }
