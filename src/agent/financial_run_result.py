"""Versioned public result contract for ``FinancialAgent.run``."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from src.agent.financial_graph_state import AgentAnswer, DebugBundle, ReviewTrace


FINANCIAL_RUN_RESULT_SCHEMA_VERSION = "financial_run_result_v1"


@dataclass(frozen=True, slots=True)
class FinancialRunResultV1:
    schema_version: str
    agent_answer: AgentAnswer
    review_trace: Optional[ReviewTrace] = None
    debug_bundle: Optional[DebugBundle] = None

    def __post_init__(self) -> None:
        if self.schema_version != FINANCIAL_RUN_RESULT_SCHEMA_VERSION:
            raise ValueError(
                f"unsupported financial run result schema: {self.schema_version}"
            )
        object.__setattr__(self, "agent_answer", dict(self.agent_answer))
        if self.review_trace is not None:
            object.__setattr__(self, "review_trace", dict(self.review_trace))
        if self.debug_bundle is not None:
            object.__setattr__(self, "debug_bundle", dict(self.debug_bundle))

    def to_projection(self) -> Dict[str, Any]:
        projection: Dict[str, Any] = {
            "schema_version": self.schema_version,
            "agent_answer": dict(self.agent_answer),
        }
        if self.review_trace is not None:
            projection["review_trace"] = dict(self.review_trace)
        if self.debug_bundle is not None:
            projection["debug_bundle"] = dict(self.debug_bundle)
        return projection


__all__ = [
    "FINANCIAL_RUN_RESULT_SCHEMA_VERSION",
    "FinancialRunResultV1",
]
