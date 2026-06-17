"""Experimental multi-agent runtime facade.

The implementation still lives behind compatibility modules under
``src.agent``. New experimental callers should import through this package so
the default single-agent runtime remains the obvious product surface.
"""

from src.experimental.mas.graph import build_initial_state, build_mas_graph, run_mas_graph
from src.experimental.mas.types import (
    AgentTask,
    Artifact,
    CriticReport,
    MultiAgentState,
    ReportScope,
    TaskStatus,
)

__all__ = [
    "AgentTask",
    "Artifact",
    "CriticReport",
    "MultiAgentState",
    "ReportScope",
    "TaskStatus",
    "build_initial_state",
    "build_mas_graph",
    "run_mas_graph",
]
