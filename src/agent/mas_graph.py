"""
LangGraph builder for the DART MAS skeleton.
"""

from __future__ import annotations

from typing import Any, Callable, Dict

from langgraph.graph import END, StateGraph

from src.agent.mas_types import MultiAgentState, ReportScope, TaskStatus
from src.agent.nodes.critic_node import run_critic
from src.agent.nodes.dummy_nodes import (
    run_orchestrator_merge as run_dummy_orchestrator_merge,
    run_orchestrator_plan as run_dummy_orchestrator_plan,
    run_researcher as run_dummy_researcher,
    run_analyst as run_dummy_analyst,
)


def check_critic_approval(state: MultiAgentState) -> str:
    tasks = state.get("tasks", {})
    for task in tasks.values():
        if task["status"] == TaskStatus.REJECTED_BY_CRITIC:
            assignee = task["assignee"].lower()
            if assignee == "analyst":
                return "retry_analyst"
            if assignee == "researcher":
                return "retry_researcher"
    return "pass"


def build_initial_state(
    query: str,
    *,
    report_scope: ReportScope | None = None,
    debug_force_retry_assignee: str | None = None,
) -> MultiAgentState:
    return {
        "original_query": query,
        "report_scope": report_scope
        or {
            "company": "",
            "report_type": "",
            "rcept_no": "",
            "year": "",
            "consolidation": "",
        },
        "tasks": {},
        "evidence_pool": [],
        "artifacts": {},
        "critic_reports": [],
        "critic_feedback": None,
        "final_report": None,
        "execution_trace": [],
        "debug_force_retry_assignee": debug_force_retry_assignee,
        "debug_retry_emitted": False,
    }


def build_mas_graph(
    *,
    orchestrator_plan_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
    orchestrator_merge_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
    analyst_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
    researcher_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
):
    workflow = StateGraph(MultiAgentState)

    workflow.add_node("Orchestrator_Plan", orchestrator_plan_node or run_dummy_orchestrator_plan)
    workflow.add_node("Analyst", analyst_node or run_dummy_analyst)
    workflow.add_node("Researcher", researcher_node or run_dummy_researcher)
    workflow.add_node("Critic", run_critic)
    workflow.add_node("Orchestrator_Merge", orchestrator_merge_node or run_dummy_orchestrator_merge)

    workflow.set_entry_point("Orchestrator_Plan")
    workflow.add_edge("Orchestrator_Plan", "Analyst")
    workflow.add_edge("Orchestrator_Plan", "Researcher")
    workflow.add_edge("Analyst", "Critic")
    workflow.add_edge("Researcher", "Critic")
    workflow.add_conditional_edges(
        "Critic",
        check_critic_approval,
        {
            "pass": "Orchestrator_Merge",
            "retry_analyst": "Analyst",
            "retry_researcher": "Researcher",
        },
    )
    workflow.add_edge("Orchestrator_Merge", END)
    return workflow.compile()


def run_mas_graph(
    query: str,
    *,
    report_scope: ReportScope | None = None,
    debug_force_retry_assignee: str | None = None,
    orchestrator_plan_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
    orchestrator_merge_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
    analyst_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
    researcher_node: Callable[[MultiAgentState], Dict[str, Any]] | None = None,
) -> MultiAgentState:
    graph = build_mas_graph(
        orchestrator_plan_node=orchestrator_plan_node,
        orchestrator_merge_node=orchestrator_merge_node,
        analyst_node=analyst_node,
        researcher_node=researcher_node,
    )
    initial_state = build_initial_state(
        query,
        report_scope=report_scope,
        debug_force_retry_assignee=debug_force_retry_assignee,
    )
    return graph.invoke(initial_state)
