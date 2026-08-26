"""Lazy structured-output model loaders for graph runtime paths."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, Dict


@lru_cache(maxsize=None)
def _graph_model(name: str) -> Any:
    module = import_module("src.agent.financial_graph_models")
    return getattr(module, name)


def aggregate_synthesis_output_model() -> Any:
    return _graph_model("AggregateSynthesisOutput")


def calculation_plan_model() -> Any:
    return _graph_model("CalculationPlan")


def calculation_render_output_model() -> Any:
    return _graph_model("CalculationRenderOutput")


def calculation_verification_output_model() -> Any:
    return _graph_model("CalculationVerificationOutput")


def compression_output_model() -> Any:
    return _graph_model("CompressionOutput")


def concept_planner_output_model() -> Any:
    return _graph_model("ConceptPlannerOutput")


def evidence_extraction_model() -> Any:
    return _graph_model("EvidenceExtraction")


def numeric_extraction_model() -> Any:
    return _graph_model("NumericExtraction")


def operand_extraction_model() -> Any:
    return _graph_model("OperandExtraction")


def reconciliation_candidate_rerank_model() -> Any:
    return _graph_model("ReconciliationCandidateRerank")


def reflection_query_plan_model() -> Any:
    return _graph_model("ReflectionQueryPlan")


def validation_output_model() -> Any:
    return _graph_model("ValidationOutput")


def validate_answer_slots_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    validator = _graph_model("validate_answer_slots_payload")
    return validator(payload)
