"""Lazy structured-output model loaders for graph runtime paths."""

from __future__ import annotations

from functools import lru_cache
from importlib import import_module
from typing import Any, Dict


@lru_cache(maxsize=None)
def _graph_model(name: str) -> Any:
    module = import_module("src.agent.financial_graph_models")
    return getattr(module, name)


def _aggregate_synthesis_output_model() -> Any:
    return _graph_model("AggregateSynthesisOutput")


def _calculation_plan_model() -> Any:
    return _graph_model("CalculationPlan")


def _calculation_render_output_model() -> Any:
    return _graph_model("CalculationRenderOutput")


def _calculation_verification_output_model() -> Any:
    return _graph_model("CalculationVerificationOutput")


def _compression_output_model() -> Any:
    return _graph_model("CompressionOutput")


def _concept_planner_output_model() -> Any:
    return _graph_model("ConceptPlannerOutput")


def _evidence_extraction_model() -> Any:
    return _graph_model("EvidenceExtraction")


def _numeric_extraction_model() -> Any:
    return _graph_model("NumericExtraction")


def _operand_extraction_model() -> Any:
    return _graph_model("OperandExtraction")


def _reconciliation_candidate_rerank_model() -> Any:
    return _graph_model("ReconciliationCandidateRerank")


def _reflection_query_plan_model() -> Any:
    return _graph_model("ReflectionQueryPlan")


def _validation_output_model() -> Any:
    return _graph_model("ValidationOutput")


def _validate_answer_slots_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    validate_answer_slots_payload = _graph_model("validate_answer_slots_payload")
    return validate_answer_slots_payload(payload)
