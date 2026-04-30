"""
Shared state and artifact types for the DART MAS skeleton.
"""

from __future__ import annotations

import operator
from enum import Enum
from typing import Annotated, Any, Dict, List, Optional, TypedDict


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


class Artifact(TypedDict):
    task_id: str
    creator: str
    content: Any
    evidence_links: List[str]


class CriticReport(TypedDict):
    target_task_id: str
    passed: bool
    deterministic_score: float
    llm_feedback: str


class ReportScope(TypedDict):
    company: str
    report_type: str
    rcept_no: str
    year: str
    consolidation: str


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


class MultiAgentState(TypedDict):
    original_query: str
    report_scope: ReportScope

    # Task ledger
    tasks: Annotated[Dict[str, AgentTask], _merge_task_ledgers]

    # Artifact store
    evidence_pool: Annotated[List[Dict[str, Any]], operator.add]
    artifacts: Annotated[Dict[str, Artifact], _merge_artifacts]
    critic_reports: Annotated[List[CriticReport], operator.add]

    # Final result
    critic_feedback: Optional[str]
    final_report: Optional[str]

    # Execution trace
    execution_trace: Annotated[List[str], operator.add]

    # Optional control fields for skeleton/testing
    debug_force_retry_assignee: Optional[str]
    debug_retry_emitted: bool
