"""Lazy structured-output model loaders for graph runtime paths."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, Dict


@lru_cache(maxsize=None)
def _graph_model(name: str) -> Any:
    module = import_module("src.agent.financial_graph_models")
    return getattr(module, name)


def requirement_planner_output_model() -> Any:
    return _graph_model("RequirementPlannerOutput")


def semantic_calculation_program_model() -> Any:
    return _graph_model("SemanticCalculationProgram")


def compiler_response_model(obligations, references, visibility, **kwargs):
    return _graph_model("compiler_response_model")(obligations, references, visibility, **kwargs)


def validate_answer_slots_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    validator = _graph_model("validate_answer_slots_payload")
    return validator(payload)
