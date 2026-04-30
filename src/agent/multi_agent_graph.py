"""
Backward-compatible wrapper around the MAS skeleton modules.

This file exists so earlier local imports that referenced
`src.agent.multi_agent_graph` keep working while the implementation is split
into:

- `src.agent.mas_types`
- `src.agent.nodes.dummy_nodes`
- `src.agent.mas_graph`
"""

from __future__ import annotations

from src.agent.mas_graph import build_initial_state, build_mas_graph, run_mas_graph
from src.agent.mas_types import (
    AgentTask,
    Artifact,
    CriticReport,
    MultiAgentState,
    ReportScope,
    TaskStatus,
)


class MultiAgentDARTSkeleton:
    def __init__(self, **graph_kwargs) -> None:
        self._graph_kwargs = dict(graph_kwargs)
        self.graph = build_mas_graph(**graph_kwargs)

    def build_initial_state(self, query: str, **kwargs) -> MultiAgentState:
        return build_initial_state(query, **kwargs)

    def run(self, query: str, **kwargs) -> MultiAgentState:
        graph_kwargs = dict(self._graph_kwargs)
        graph_kwargs.update(kwargs)
        return run_mas_graph(query, **graph_kwargs)


__all__ = [
    "AgentTask",
    "Artifact",
    "CriticReport",
    "MultiAgentDARTSkeleton",
    "MultiAgentState",
    "ReportScope",
    "TaskStatus",
    "build_initial_state",
    "build_mas_graph",
    "run_mas_graph",
]
