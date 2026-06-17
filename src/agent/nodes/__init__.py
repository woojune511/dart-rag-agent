"""Compatibility exports for MAS node factories.

New experimental MAS callers should import from ``src.experimental.mas.nodes``.
The concrete node implementations still live in this package until the
implementation move has explicit compatibility coverage.
"""

from src.agent.nodes.analyst_node import build_financial_analyst_node, make_run_analyst
from src.agent.nodes.orchestrator_node import (
    build_financial_orchestrator_merge_node,
    build_financial_orchestrator_plan_node,
    make_run_orchestrator_merge,
    make_run_orchestrator_plan,
)
from src.agent.nodes.researcher_node import build_financial_researcher_node, make_run_researcher

__all__ = [
    "build_financial_analyst_node",
    "make_run_analyst",
    "build_financial_orchestrator_merge_node",
    "build_financial_orchestrator_plan_node",
    "make_run_orchestrator_merge",
    "make_run_orchestrator_plan",
    "build_financial_researcher_node",
    "make_run_researcher",
]
