from __future__ import annotations

import json
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.agent.financial_calculation_execution import (
    derive_operation_family_from_formula,
    execute_semantic_calculation_program,
    semantic_candidate_applicability,
    validate_semantic_calculation_program,
)
from src.agent.financial_graph_models import (
    AnswerObligation,
    RequirementPlannerOutput,
    SemanticCalculationProgram,
)
from src.agent.financial_graph import (
    FINANCIAL_GRAPH_PHASE_WRITERS,
    FinancialAgent,
)
from src.agent.financial_run_result import (
    FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
    FinancialRunResultV1,
)
from src.agent.financial_graph_calculation import (
    _merge_targeted_program_retry,
    _retry_candidate_exclusions,
    _semantic_candidate_cohorts,
    _semantic_candidate_visibility,
    build_semantic_compilation_islands,
)
from src.agent.financial_graph_model_loaders import validate_answer_slots_payload
from src.agent.financial_runtime_normalization import _normalise_operand_value
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    semantic_candidate_id_fingerprint,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_stage_diagnostics,
)
from src.agent.financial_source_bundles import (
    build_semantic_source_bundles,
    source_bundle_id_by_candidate_id,
)
from src.config.retrieval_policy import (
    CALCULATION_PROMPT_POLICY,
    PLANNING_POLICY,
)


def _scope(**overrides):
    return {
        "company": "",
        "period": "",
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        **overrides,
    }


def _obligation(obligation_id, kind, label, **overrides):
    return {
        "obligation_id": obligation_id,
        "kind": kind,
        "label": label,
        "required": True,
        "display_unit": "",
        "display_format": "",
        "scope": _scope(),
        "retrieval_hints": [],
        "concept_hints": [],
        "evidence_requirements": [],
        "depends_on": [],
        "coupling_key": "",
        **overrides,
    }


def _requirement(requirement_id, label, *, period="", **scope_overrides):
    return {
        "requirement_id": requirement_id,
        "label": label,
        "required": True,
        "scope": _scope(period=period, **scope_overrides),
        "retrieval_hints": [],
        "concept_hints": [],
    }


def _binding(variable, source_id, source_requirement_id=""):
    return {
        "variable": variable,
        "source_id": source_id,
        "source_requirement_id": source_requirement_id,
    }


def _candidate(
    candidate_id,
    value,
    *,
    raw_unit="items",
    normalized_unit=None,
    normalized_value_override=None,
    period="",
    context="table-a",
    row_label="quantity",
):
    normalized_value, parsed_unit = _normalise_operand_value(str(value), raw_unit)
    return {
        "candidate_id": candidate_id,
        "kind": "numeric",
        "source_candidate_id": f"source-{candidate_id}",
        "evidence_id": f"evidence-{candidate_id}",
        "source_anchor": "[sample | 2024 | section]",
        "source_row_id": f"row-{candidate_id}",
        "table_source_id": context,
        "row_label": row_label,
        "statement_type": "",
        "company": "",
        "year": 2024,
        "consolidation_scope": "unknown",
        "segment": "",
        "basis": "",
        "context_fingerprint": context,
        "source_text": f"{row_label} {period} {value} {raw_unit}",
        "candidate_kind": "structured_value",
        "raw_value": str(value),
        "raw_unit": raw_unit,
        "normalized_value": normalized_value if normalized_value_override is None else normalized_value_override,
        "normalized_unit": parsed_unit if normalized_unit is None else normalized_unit,
        "period": period,
        "column_headers": [period] if period else [],
        "value_role": "",
        "aggregation_stage": "",
        "aggregate_label": "",
    }


def _source_assertions(catalog, *candidate_ids):
    requested = {str(item) for item in candidate_ids if str(item)}
    assertions = []
    for bundle in build_semantic_source_bundles(catalog):
        selected = [
            candidate_id
            for candidate_id in bundle.candidate_ids
            if candidate_id in requested
        ]
        if not selected:
            continue
        assertions.append(
            {
                "source_bundle_id": bundle.source_bundle_id,
                "candidate_ids": selected,
                "evidence_text": bundle.source_text,
            }
        )
    return assertions


def _contract_residual_fixture():
    fixture_path = (
        Path(__file__).parent
        / "fixtures"
        / "semantic_program_contract_residuals.json"
    )
    return json.loads(fixture_path.read_text(encoding="utf-8"))


def _catalog_from_document(page_content, metadata):
    source_candidates = build_semantic_source_candidates(
        {
            "retrieved_docs": [
                (
                    SimpleNamespace(
                        page_content=page_content,
                        metadata=dict(metadata),
                    ),
                    0.0,
                )
            ]
        },
        source_anchor_builder=lambda item: f"[{item.get('chunk_uid') or 'sample'}]",
    )
    return build_semantic_candidate_catalog(source_candidates)


def _source_display_program_fixture():
    scope = _scope(
        company="sample", period="2024", consolidation_scope="consolidated",
        segment="target unit", basis="reported",
    )
    obligation = _obligation(
        "ob_change", "derived_value", "quantity change", display_unit="%", scope=scope,
        evidence_requirements=[
            _requirement("ob_change:req_opening", "opening quantity", **{**scope, "period": "2023"}),
            _requirement("ob_change:req_closing", "closing quantity", **scope),
        ],
    )
    catalog = [
        {
            **_candidate("cand-opening", 40.0, period="2023"),
            **{**scope, "period": "2023"}, "year": 2023,
        },
        {**_candidate("cand-closing", 44.0, period="2024"), **scope},
        {
            **_candidate("cand-stated", 10.2, raw_unit="%", normalized_unit="PERCENT", period="2024"),
            **scope,
            "source_anchor": "[sample | 2024 | source note]",
            "source_text": "The target unit reports a quantity increase of 10.2%.",
        },
    ]
    return {
        "obligations": [obligation],
        "candidate_catalog": catalog,
        "program": {
            "status": "ready",
            "expressions": [{
                "obligation_id": "ob_change",
                "variable_bindings": [
                    _binding("OPEN", "cand-opening", "ob_change:req_opening"),
                    _binding("CLOSE", "cand-closing", "ob_change:req_closing"),
                ],
                "formula": "(CLOSE - OPEN) / OPEN * 100",
                "result_unit": "%",
                "source_display_candidate_id": "cand-stated",
                "source_display_reason": "The selected source candidate explicitly reports this derived result.",
            }],
        },
        "query": "Calculate the change using the displayed opening and closing quantities.",
    }

class _StructuredQueueLLM:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.models = []
        self.prompts = []

    def with_structured_output(self, model):
        self.models.append(model.__name__)
        return self

    def invoke(self, prompt):
        self.prompts.append(prompt)
        if not self.responses:
            raise AssertionError("unexpected structured invocation")
        return self.responses.pop(0)


class _StaticFinancialRunAgent:
    def __init__(self, payload):
        self.payload = dict(payload)

    def run(
        self,
        *_args,
        include_review_trace=False,
        include_debug_bundle=False,
        **_kwargs,
    ):
        answer_fields = {
            "query",
            "report_scope",
            "query_type",
            "intent",
            "planner_mode",
            "planner_feedback",
            "plan_loop_count",
            "target_metric_family",
            "target_metric_family_hint",
            "planned_metric_families",
            "format_preference",
            "routing_source",
            "routing_confidence",
            "routing_scores",
            "companies",
            "years",
            "answer",
            "citations",
            "resolved_calculation_trace",
            "structured_result",
        }
        return FinancialRunResultV1(
            schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
            agent_answer={
                key: value
                for key, value in self.payload.items()
                if key in answer_fields
            },
            review_trace={
                key: value
                for key, value in self.payload.items()
                if key not in answer_fields
            }
            if include_review_trace
            else None,
            debug_bundle={} if include_debug_bundle else None,
        )

__all__ = [name for name in globals() if not name.startswith("__")]
