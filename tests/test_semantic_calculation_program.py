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
from src.agent.financial_graph_calculation import (
    _merge_targeted_program_retry,
    _retry_candidate_exclusions,
    _semantic_candidate_cohorts,
    _semantic_obligation_relevance_groups,
    _semantic_required_evidence_relevance_groups,
    build_semantic_compilation_islands,
)
from src.agent.financial_graph_model_loaders import validate_answer_slots_payload
from src.agent.financial_reconciliation_candidates import (
    build_semantic_candidate_catalog,
    build_semantic_source_candidates,
    select_semantic_prompt_candidates,
    semantic_candidate_id_fingerprint,
    semantic_candidate_catalog_fingerprint,
    semantic_candidate_stage_diagnostics,
)
from src.config.retrieval_policy import (
    CALCULATION_PROMPT_POLICY,
    CONSOLIDATION_SCOPE_POLICY,
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
    normalized_unit="COUNT",
    period="",
    context="table-a",
    row_label="quantity",
):
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
        "normalized_value": float(value),
        "normalized_unit": normalized_unit,
        "period": period,
        "column_headers": [period] if period else [],
        "value_role": "",
        "aggregation_stage": "",
        "aggregate_label": "",
    }


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
            }],
        },
        "query": "Calculate the change using the displayed opening and closing quantities.",
    }


class SemanticCalculationProgramTests(unittest.TestCase):
    def test_empty_obligation_program_fails_closed(self) -> None:
        execution = execute_semantic_calculation_program(
            program={"status": "incomplete"},
            obligations=[],
            candidate_catalog=[],
            query="Return the requested result.",
        )
        self.assertEqual(execution["status"], "incomplete")
        self.assertIn(
            "missing_answer_obligations",
            {item["code"] for item in execution["validation"]["errors"]},
        )

    def test_offline_comparison_fixture_matches_legacy_value_and_rejects_context_mix(self) -> None:
        fixture_path = Path(__file__).parent / "fixtures" / "semantic_program_offline_comparison.json"
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))
        cases = {item["case_id"]: item for item in fixture["cases"]}

        growth = cases["same_context_growth"]
        growth_result = execute_semantic_calculation_program(
            program=growth["program"],
            obligations=growth["obligations"],
            candidate_catalog=growth["candidate_catalog"],
            query=growth["query"],
        )
        self.assertEqual(growth_result["status"], growth["expected"]["status"])
        growth_output = growth_result["outputs_by_obligation"]["ob_growth"]
        self.assertAlmostEqual(
            growth_output["normalized_value"],
            growth["legacy_projection"]["result_value"],
        )
        self.assertEqual(
            growth_output["operation_family"],
            growth["expected"]["operation_family"],
        )

        mixed = cases["cross_context_composition"]
        mixed_validation = validate_semantic_calculation_program(
            program=mixed["program"],
            obligations=mixed["obligations"],
            candidate_catalog=mixed["candidate_catalog"],
            query=mixed["query"],
        )
        self.assertEqual(mixed_validation["status"], mixed["expected"]["status"])
        self.assertIn(
            mixed["expected"]["error_code"],
            {item["code"] for item in mixed_validation["errors"]},
        )

    def test_models_accept_open_obligations_and_restricted_program(self) -> None:
        planned = RequirementPlannerOutput.model_validate(
            {
                "topic": "opening and closing quantities",
                "obligations": [
                    {
                        "obligation_id": "growth",
                        "kind": "derived_value",
                        "label": "change rate",
                        "display_unit": "%",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": "consolidated",
                            "segment": "service",
                            "basis": "gross",
                        },
                        "evidence_requirements": [
                            {
                                "requirement_id": "current",
                                "label": "current quantity",
                                "scope": {"period": "2024"},
                            },
                            {
                                "requirement_id": "prior",
                                "label": "prior quantity",
                                "scope": {"period": "2023"},
                            },
                        ],
                    }
                ],
                "retrieval_queries": ["opening quantity", "closing quantity"],
            }
        )
        program = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_direct",
                        "candidate_id": "cand-direct",
                        "compatibility_candidate_ids": ["cand-scope-note"],
                    }
                ],
                "expressions": [
                    {
                        "obligation_id": "ob_001",
                        "variable_bindings": [
                            {
                                "variable": "CURR",
                                "source_id": "cand-current",
                                "source_requirement_id": "ob_001:req_001",
                                "scope_applicability_fields": ["segment"],
                            },
                            {
                                "variable": "PREV",
                                "source_id": "cand-prior",
                                "source_requirement_id": "ob_001:req_002",
                            },
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                    }
                ],
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_note",
                        "candidate_ids": ["cand-note"],
                        "scope_applicability_fields": [
                            "consolidation_scope",
                            "segment",
                        ],
                        "text": "The selected evidence directly states the relationship.",
                    }
                ],
            }
        )
        self.assertEqual(planned.obligations[0].kind, "derived_value")
        self.assertEqual(
            planned.obligations[0].evidence_requirements[1].scope.period,
            "2023",
        )
        self.assertEqual(
            program.direct_bindings[0].compatibility_candidate_ids,
            ["cand-scope-note"],
        )
        self.assertEqual(
            program.narrative_bindings[0].scope_applicability_fields,
            ["consolidation_scope", "segment"],
        )
        self.assertEqual(
            program.expressions[0].variable_bindings[0].scope_applicability_fields,
            ["segment"],
        )
        self.assertEqual(program.expressions[0].formula, "((CURR - PREV) / PREV) * 100")

    def test_derived_output_scope_is_distinct_from_declared_operand_scopes(self) -> None:
        obligation = _obligation(
            "ob_change",
            "derived_value",
            "2023 change",
            scope=_scope(period="2023"),
            evidence_requirements=[
                {
                    "requirement_id": "ob_change:req_current",
                    "label": "current value",
                    "scope": _scope(period="2023"),
                    "required": True,
                    "retrieval_hints": [],
                    "concept_hints": [],
                },
                {
                    "requirement_id": "ob_change:req_prior",
                    "label": "prior value",
                    "scope": _scope(period="2022"),
                    "required": True,
                    "retrieval_hints": [],
                    "concept_hints": [],
                },
            ],
        )
        current = {
            **_candidate(
                "cand-current",
                380,
                raw_unit="",
                normalized_unit="UNKNOWN",
                period="2023",
            ),
            "year": 2023,
        }
        prior = {
            **_candidate(
                "cand-prior",
                343,
                raw_unit="",
                normalized_unit="UNKNOWN",
                period="2022",
            ),
            "year": 2022,
        }
        program = {
            "status": "ready",
            "expressions": [
                {
                    "obligation_id": "ob_change",
                    "variable_bindings": [
                        {
                            "variable": "CURRENT",
                            "source_id": "cand-current",
                            "source_requirement_id": "ob_change:req_current",
                        },
                        {
                            "variable": "PRIOR",
                            "source_id": "cand-prior",
                            "source_requirement_id": "ob_change:req_prior",
                        },
                    ],
                    "formula": "CURRENT - PRIOR",
                    "result_unit": "",
                }
            ],
        }

        result = execute_semantic_calculation_program(
            program=program,
            obligations=[obligation],
            candidate_catalog=[current, prior],
            query="Return the 2023 change from the prior-year value.",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(
            result["outputs_by_obligation"]["ob_change"]["normalized_value"],
            37.0,
        )

    def test_candidate_binding_must_match_its_declared_evidence_requirement(self) -> None:
        obligation = _obligation(
            "ob_change",
            "derived_value",
            "2023 change",
            scope=_scope(period="2023"),
            evidence_requirements=[
                {
                    "requirement_id": "ob_change:req_current",
                    "label": "current value",
                    "scope": _scope(period="2023"),
                    "required": True,
                    "retrieval_hints": [],
                    "concept_hints": [],
                },
                {
                    "requirement_id": "ob_change:req_prior",
                    "label": "prior value",
                    "scope": _scope(period="2022"),
                    "required": True,
                    "retrieval_hints": [],
                    "concept_hints": [],
                },
            ],
        )
        current = {
            **_candidate(
                "cand-current",
                380,
                raw_unit="",
                normalized_unit="UNKNOWN",
                period="2023",
            ),
            "year": 2023,
        }
        prior = {
            **_candidate(
                "cand-prior",
                343,
                raw_unit="",
                normalized_unit="UNKNOWN",
                period="2022",
            ),
            "year": 2022,
        }
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_change",
                        "variable_bindings": [
                            {
                                "variable": "CURRENT",
                                "source_id": "cand-current",
                                "source_requirement_id": "ob_change:req_prior",
                            },
                            {
                                "variable": "PRIOR",
                                "source_id": "cand-prior",
                                "source_requirement_id": "ob_change:req_current",
                            },
                        ],
                        "formula": "CURRENT - PRIOR",
                        "result_unit": "",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[current, prior],
            query="Return the 2023 change from the prior-year value.",
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertIn(
            "candidate_requirement_scope_mismatch",
            {item["code"] for item in validation["errors"]},
        )

    def test_formula_input_scope_applicability_bridges_only_unknown_segment_and_basis(self) -> None:
        current_requirement = _requirement(
            "ob_change:req_current",
            "current reported quantity",
            period="2024",
            company="sample",
            segment="north market",
            basis="reported quantity",
        )
        prior_requirement = _requirement(
            "ob_change:req_prior",
            "prior reported quantity",
            period="2023",
            company="sample",
            segment="north market",
            basis="reported quantity",
        )
        obligation = _obligation(
            "ob_change",
            "derived_value",
            "reported quantity growth",
            display_unit="%",
            scope=_scope(company="sample", period="2024"),
            evidence_requirements=[current_requirement, prior_requirement],
        )
        current = {
            **_candidate("cand-current", 380, period="2024"),
            "candidate_kind": "sentence_value",
            "company": "sample",
            "year": 2024,
            "segment": "",
            "basis": "",
            "source_text": "The northmarket local sentence reports 380 items.",
        }
        prior = {
            **_candidate("cand-prior", 343, period="2023"),
            "candidate_kind": "sentence_value",
            "company": "sample",
            "year": 2023,
            "segment": "",
            "basis": "",
            "source_text": "The northmarket local sentence reports 343 items.",
        }

        def program(*, applicability=()):
            return {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_change",
                        "variable_bindings": [
                            {
                                **_binding(
                                    "CURRENT",
                                    "cand-current",
                                    "ob_change:req_current",
                                ),
                                "scope_applicability_fields": list(applicability),
                            },
                            {
                                **_binding(
                                    "PRIOR",
                                    "cand-prior",
                                    "ob_change:req_prior",
                                ),
                                "scope_applicability_fields": list(applicability),
                            },
                        ],
                        "formula": "((CURRENT - PRIOR) / PRIOR) * 100",
                        "result_unit": "%",
                    }
                ],
            }

        rejected = validate_semantic_calculation_program(
            program=program(),
            obligations=[obligation],
            candidate_catalog=[current, prior],
            query="Return the north market reported quantity growth.",
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "candidate_requirement_scope_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

        accepted = execute_semantic_calculation_program(
            program=program(applicability=["basis"]),
            obligations=[obligation],
            candidate_catalog=[current, prior],
            query="Return the north market reported quantity growth.",
        )
        self.assertEqual(accepted["status"], "ok")
        self.assertAlmostEqual(
            accepted["outputs_by_obligation"]["ob_change"]["normalized_value"],
            (380 - 343) / 343 * 100,
        )

        explicit_conflict = validate_semantic_calculation_program(
            program=program(applicability=["basis"]),
            obligations=[obligation],
            candidate_catalog=[{**current, "basis": "different basis"}, prior],
            query="Return the north market reported quantity growth.",
        )
        self.assertEqual(explicit_conflict["status"], "invalid")

        invalid_field = validate_semantic_calculation_program(
            program=program(applicability=["consolidation_scope"]),
            obligations=[obligation],
            candidate_catalog=[current, prior],
            query="Return the north market reported quantity growth.",
        )
        self.assertIn(
            "invalid_variable_scope_applicability_field",
            {item["code"] for item in invalid_field["errors"]},
        )

    def test_candidate_catalog_assigns_stable_ids_and_preserves_source_material(self) -> None:
        source_candidates = [
            {
                "candidate_id": "chunk-1::value:0",
                "source_anchor": "[sample | 2024 | section]",
                "text": "opening and closing quantity",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "quantity",
                    "table_source_id": "table-a",
                    "year": 2024,
                    "structured_cells": [
                        {"column_headers": ["opening"], "value_text": "343", "unit_hint": "items"},
                        {"column_headers": ["closing"], "value_text": "380", "unit_hint": "items"},
                    ],
                },
            }
        ]
        first = build_semantic_candidate_catalog(source_candidates)
        second = build_semantic_candidate_catalog(source_candidates)
        numeric = [item for item in first if item["kind"] == "numeric"]
        self.assertEqual(len(numeric), 2)
        self.assertEqual([item["candidate_id"] for item in first], [item["candidate_id"] for item in second])
        self.assertEqual(semantic_candidate_catalog_fingerprint(first), semantic_candidate_catalog_fingerprint(second))
        self.assertEqual([item["raw_value"] for item in numeric], ["343", "380"])
        self.assertTrue(all(item["context_fingerprint"].startswith("table-a") for item in numeric))

    def test_candidate_stage_diagnostics_distinguish_three_generic_loss_stages(self) -> None:
        state = {
            "retrieved_docs": [
                (
                    SimpleNamespace(
                        page_content="neighbor value only",
                        metadata={"chunk_uid": "source-local"},
                    ),
                    0.9,
                )
            ],
            "seed_retrieved_docs": [
                (
                    SimpleNamespace(
                        page_content="neighbor value only",
                        metadata={"chunk_uid": "source-local"},
                    ),
                    0.9,
                ),
                (
                    SimpleNamespace(
                        page_content="two projected values",
                        metadata={"chunk_uid": "source-prompt"},
                    ),
                    0.8,
                ),
            ],
            "retrieval_debug_trace": {
                "source_window": {
                    "retrieved_source_ids": ["source-local"],
                    "retrieved_unidentified_count": 0,
                    "seed_source_ids": ["source-local", "source-prompt"],
                    "seed_unidentified_count": 0,
                }
            },
        }
        source_candidates = [
            {
                "candidate_id": "source-local::row:0",
                "candidate_kind": "table_row",
            },
            {
                "candidate_id": "source-prompt::row:0",
                "candidate_kind": "table_row",
            },
        ]
        catalog = [
            {
                "candidate_id": "cand-neighbor",
                "evidence_id": "source-local",
                "kind": "numeric",
            },
            {
                "candidate_id": "cand-kept",
                "evidence_id": "source-prompt",
                "kind": "numeric",
            },
            {
                "candidate_id": "cand-dropped",
                "evidence_id": "source-prompt",
                "kind": "numeric",
            },
        ]
        diagnostics = semantic_candidate_stage_diagnostics(
            state=state,
            source_candidates=source_candidates,
            catalog=catalog,
            prompt_catalog=[catalog[1]],
        )
        by_source = {
            item["source_id"]: item for item in diagnostics["by_source"]
        }
        self.assertEqual(
            diagnostics["source_window_origin"],
            "retrieval_debug_trace",
        )

        # Stage 1: the expected source never entered either preserved window.
        self.assertNotIn("source-absent", diagnostics["source_window"]["seed_source_ids"])
        self.assertNotIn("source-absent", by_source)

        # Stage 2: the source was projected, but a reconstructed local-cell ID is absent.
        local = by_source["source-local"]
        self.assertTrue(local["in_retrieved_window"])
        self.assertEqual(local["source_candidate_count"], 1)
        self.assertEqual(local["catalog_candidate_count"], 1)
        self.assertEqual(
            local["catalog_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-neighbor"]),
        )
        self.assertNotEqual(
            local["catalog_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-neighbor", "cand-needed"]),
        )

        # Stage 3: the catalog contains the candidate but prompt admission removes it.
        prompt = by_source["source-prompt"]
        self.assertTrue(prompt["in_seed_window"])
        self.assertEqual(prompt["catalog_candidate_count"], 2)
        self.assertEqual(prompt["prompt_candidate_count"], 1)
        self.assertEqual(prompt["prompt_drop_count"], 1)
        self.assertEqual(
            prompt["catalog_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-kept", "cand-dropped"]),
        )
        self.assertEqual(
            prompt["prompt_candidate_id_fingerprint"],
            semantic_candidate_id_fingerprint(["cand-kept"]),
        )

    def test_candidate_catalog_bounds_by_obligation_relevance_and_source_coverage(self) -> None:
        source_candidates = [
            {
                "candidate_id": f"noise-{index}",
                "source_anchor": f"[sample | 2024 | noise-{index}]",
                "text": f"unrelated row {index}",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": f"unrelated {index}",
                    "year": 2024,
                    "structured_cells": [
                        {"value_text": str(index + 1), "unit_hint": "items"}
                    ],
                },
            }
            for index in range(120)
        ]
        source_candidates.extend(
            [
                {
                    "candidate_id": "late-target",
                    "source_anchor": "[sample | 2024 | target]",
                    "text": "target total 999 items",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "row_label": "target total",
                        "year": 2024,
                        "structured_cells": [
                            {"value_text": "999", "unit_hint": "items"}
                        ],
                    },
                },
                *[
                    {
                        "candidate_id": f"doc-{index}",
                        "source_anchor": f"[sample | 2024 | doc-{index}]",
                        "text": (
                            "critical context for the requested explanation"
                            if index == 39
                            else f"unrelated narrative {index}"
                        ),
                        "candidate_kind": "chunk",
                        "metadata": {"year": 2024},
                    }
                    for index in range(40)
                ],
            ]
        )

        catalog = build_semantic_candidate_catalog(
            source_candidates,
            relevance_texts=["target total", "critical context"],
            max_numeric_candidates=8,
            max_narrative_candidates=4,
        )
        self.assertIn("999", [item["raw_value"] for item in catalog if item["kind"] == "numeric"])
        self.assertTrue(
            any(
                "critical context" in item["source_text"]
                for item in catalog
                if item["kind"] == "narrative"
            )
        )
        self.assertFalse(
            any(
                item["kind"] == "narrative"
                and item["source_candidate_id"] == "late-target"
                for item in catalog
            )
        )

    def test_candidate_catalog_keeps_prose_values_and_prompt_stratifies_obligations(self) -> None:
        source_candidates = [
            {
                "candidate_id": f"first-{index}",
                "source_anchor": f"[sample | 2024 | first-{index}]",
                "text": f"first requested value {index + 1:,}억원",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "first requested value",
                    "year": 2024,
                    "structured_cells": [
                        {"value_text": str(index + 1), "unit_hint": "억원"}
                    ],
                },
            }
            for index in range(110)
        ]
        source_candidates.append(
            {
                "candidate_id": "late-prose",
                "source_anchor": "[sample | 2024 | narrative]",
                "text": (
                    "The disclosure explains the second requested adjustment and "
                    "states it as 6,769억원 in the source sentence."
                ),
                "candidate_kind": "chunk",
                "metadata": {"year": 2024, "consolidation_scope": "consolidated"},
            }
        )

        catalog = build_semantic_candidate_catalog(source_candidates)
        prose = next(
            item
            for item in catalog
            if item.get("candidate_kind") == "sentence_value"
            and item.get("raw_value") == "6,769"
        )
        self.assertGreater(
            sum(item["kind"] == "numeric" for item in catalog),
            96,
        )
        self.assertEqual(prose["raw_unit"], "억원")
        self.assertEqual(prose["normalized_value"], 676_900_000_000.0)
        self.assertIn("second requested adjustment", prose["source_text"])

        rows = FinancialAgent._semantic_program_prompt_rows(
            catalog,
            relevance_groups=[
                ["first requested value"],
                ["second requested adjustment"],
            ],
        )
        self.assertIn(prose["candidate_id"], {item["candidate_id"] for item in rows})

    def test_unstructured_table_row_ignores_data_preview_after_period_header(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "statement-row",
                    "source_anchor": "[sample | 2023 | primary statement]",
                    "text": "target metric | (300) | (200) | (100)",
                    "candidate_kind": "table_row",
                    "metadata": {
                        "year": 2023,
                        "row_label": "target metric",
                        "row_text": "target metric | (300) | (200) | (100)",
                        "unit_hint": "items",
                        "statement_type": "income_statement",
                        "consolidation_scope": "consolidated",
                        "table_source_id": "statement-table",
                        "table_header_context": (
                            "| 2023 | 2022 | 2021\n"
                            "baseline metric | 500 | 400 | 300"
                        ),
                        "period_labels": ["current", "2023", "2022", "2021"],
                    },
                }
            ]
        )

        numeric = [item for item in catalog if item["kind"] == "numeric"]
        self.assertEqual([item["period"] for item in numeric], ["2023", "2022", "2021"])
        self.assertEqual([item["value_year"] for item in numeric], [2023, 2022, 2021])

    def test_prompt_candidate_relevance_tolerates_spacing_only_label_variants(self) -> None:
        target = _candidate(
            "target",
            300,
            row_label="target metric",
        )
        noise = [
            _candidate(
                f"noise-{index}",
                index + 1,
                row_label=f"targetmetric component {index}",
            )
            for index in range(20)
        ]

        selected = select_semantic_prompt_candidates(
            [*noise, target],
            relevance_groups=[["targetmetric"]],
            max_numeric_candidates=4,
            max_narrative_candidates=0,
        )

        self.assertIn("target", {item["candidate_id"] for item in selected})

    def test_prompt_candidate_groups_are_owned_by_candidate_kind(self) -> None:
        numeric_target = _candidate(
            "numeric-target",
            300,
            row_label="reported amount",
        )
        narrative_target = {
            **_candidate("narrative-target", 0, row_label=""),
            "kind": "narrative",
            "normalized_value": None,
            "source_text": "stress scenario explains the reported change",
        }
        narrative_noise = [
            {
                **_candidate(f"narrative-noise-{index}", 0, row_label=""),
                "kind": "narrative",
                "normalized_value": None,
                "source_text": f"reported amount context {index}",
            }
            for index in range(8)
        ]

        selected = select_semantic_prompt_candidates(
            [numeric_target, *narrative_noise, narrative_target],
            relevance_groups=[["reported amount"], ["stress scenario"]],
            numeric_relevance_groups=[["reported amount"]],
            narrative_relevance_groups=[["stress scenario"]],
            max_numeric_candidates=1,
            max_narrative_candidates=1,
        )

        self.assertEqual(
            {item["candidate_id"] for item in selected},
            {"numeric-target", "narrative-target"},
        )

    def test_prompt_relevance_treats_period_only_hint_as_scope(self) -> None:
        groups = _semantic_obligation_relevance_groups(
            [
                _obligation(
                    "ob_note",
                    "narrative",
                    "change explanation",
                    scope=_scope(period="2024"),
                    retrieval_hints=["risk context", "2024"],
                )
            ],
            owner_kind="narrative",
        )

        self.assertEqual(groups, [["change explanation", "risk context"]])

    def test_prompt_relevance_removes_embedded_declared_scope_markers(self) -> None:
        consolidation_marker = str(
            CONSOLIDATION_SCOPE_POLICY["query_markers"]["consolidated"][0]
        )
        groups = _semantic_obligation_relevance_groups(
            [
                _obligation(
                    "ob_metric",
                    "direct_value",
                    f"2024 {consolidation_marker} target metric",
                    scope=_scope(
                        period="2024",
                        consolidation_scope="consolidated",
                    ),
                    retrieval_hints=[consolidation_marker, "target metric"],
                )
            ],
            owner_kind="numeric",
        )

        self.assertEqual(groups, [["target metric"]])

    def test_required_evidence_relevance_excludes_output_and_optional_inputs(self) -> None:
        required = _requirement("ob_value:req_required", "required quantity")
        optional = {
            **_requirement("ob_value:req_optional", "optional context"),
            "required": False,
        }
        obligations = [
            _obligation(
                "ob_value",
                "derived_value",
                "change rate",
                evidence_requirements=[required, optional],
            )
        ]

        groups = _semantic_required_evidence_relevance_groups(
            obligations,
            owner_kind="numeric",
        )

        self.assertEqual(groups, [["required quantity"]])

    def test_candidate_catalog_keeps_prose_value_when_paragraph_has_table_metadata(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "mixed-paragraph",
                    "source_anchor": "[sample | 2024 | discussion]",
                    "text": (
                        "Metric A | 2,163,234 | 백만원\n"
                        "The discussion states the requested adjustment as "
                        "6,769억원 and explains its effect."
                    ),
                    "candidate_kind": "chunk",
                    "metadata": {
                        "year": 2024,
                        "block_type": "paragraph",
                        "is_table": False,
                        "table_row_records_json": json.dumps(
                            [
                                {
                                    "row_label": "Metric A",
                                    "cells": [
                                        {
                                            "value_text": "2,163,234",
                                            "unit_hint": "백만원",
                                        }
                                    ],
                                }
                            ]
                        ),
                        "structured_cells": [
                            {"value_text": "2,163,234", "unit_hint": "백만원"}
                        ],
                    },
                }
            ]
        )

        prose = next(
            item
            for item in catalog
            if item.get("candidate_kind") == "sentence_value"
            and item.get("raw_value") == "6,769"
        )
        self.assertEqual(prose["raw_unit"], "억원")
        self.assertEqual(prose["normalized_value"], 676_900_000_000.0)
        self.assertIn("requested adjustment", prose["source_text"])

        table_catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "table-chunk",
                    "source_anchor": "[sample | 2024 | table]",
                    "text": "Metric A | 2,163,234백만원",
                    "candidate_kind": "chunk",
                    "metadata": {
                        "year": 2024,
                        "block_type": "table",
                        "is_table": True,
                        "structured_cells": [
                            {"value_text": "2,163,234", "unit_hint": "백만원"}
                        ],
                    },
                }
            ]
        )
        self.assertFalse(
            any(
                item.get("candidate_kind") == "sentence_value"
                for item in table_catalog
            )
        )

    def test_candidate_catalog_keeps_explicit_count_values_when_chunk_has_table_metadata(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "mixed-structure",
                    "source_anchor": "[sample | 2024 | operating discussion]",
                    "text": (
                        "The source states that the first quantity was 1,560만 대 and "
                        "the second quantity was 87.0만 대."
                    ),
                    "candidate_kind": "chunk",
                    "metadata": {
                        "year": 2024,
                        "structured_cells": [
                            {"value_text": "12.5", "unit_hint": "%"}
                        ],
                        "table_row_records_json": json.dumps(
                            [
                                {
                                    "row_label": "unrelated rate",
                                    "cells": [
                                        {"value_text": "12.5", "unit_hint": "%"}
                                    ],
                                }
                            ]
                        ),
                    },
                }
            ]
        )

        sentence_values = {
            (item.get("raw_value"), item.get("raw_unit")): item
            for item in catalog
            if item.get("candidate_kind") == "sentence_value"
        }
        self.assertEqual(
            sentence_values[("1,560", "만 대")]["normalized_value"],
            15_600_000.0,
        )
        self.assertEqual(
            sentence_values[("87.0", "만 대")]["normalized_value"],
            870_000.0,
        )
        self.assertTrue(
            all(item["normalized_unit"] == "COUNT" for item in sentence_values.values())
        )

    def test_prompt_admission_reserves_a_ranked_alternative_from_a_relevant_source(self) -> None:
        primary = {
            **_candidate("primary", 100, row_label="requested aggregate"),
            "source_candidate_id": "shared-source",
            "evidence_id": "shared-evidence",
        }
        alternative = {
            **_candidate("alternative", 90, row_label="similar amount"),
            "source_candidate_id": "shared-source",
            "evidence_id": "shared-evidence",
            "aggregate_label": "requested aggregate net amount",
        }
        noise = [
            _candidate(
                f"noise-{index}",
                index + 1,
                row_label=f"requested aggregate component {index}",
            )
            for index in range(8)
        ]

        selected = select_semantic_prompt_candidates(
            [primary, alternative, *noise],
            relevance_groups=[["requested aggregate"]],
            max_numeric_candidates=4,
            max_narrative_candidates=0,
        )
        selected_ids = {item["candidate_id"] for item in selected}
        selected_sources = {item["evidence_id"] for item in selected}

        self.assertEqual(len(selected), 4)
        self.assertIn("primary", selected_ids)
        self.assertIn("alternative", selected_ids)
        self.assertGreaterEqual(len(selected_sources), 3)

    def test_candidate_catalog_preserves_distinct_aggregate_labels(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "aggregate-total",
                    "source_anchor": "[sample | 2024 | section]",
                    "text": "source total row",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "year": 2024,
                        "row_label": "연구개발비용 총계",
                        "structured_cells": [
                            {"value_text": "1,010", "unit_hint": "백만원"}
                        ],
                    },
                },
                {
                    "candidate_id": "aggregate-net",
                    "source_anchor": "[sample | 2024 | section]",
                    "text": "source net row",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "year": 2024,
                        "row_label": "연구개발비용 계",
                        "structured_cells": [
                            {"value_text": "1,000", "unit_hint": "백만원"}
                        ],
                    },
                },
                {
                    "candidate_id": "non-aggregate",
                    "source_anchor": "[sample | 2024 | section]",
                    "text": "non-aggregate source row",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "year": 2024,
                        "row_label": "회계처리 비용",
                        "structured_cells": [
                            {"value_text": "900", "unit_hint": "백만원"}
                        ],
                    },
                }
            ]
        )
        aggregate_by_row = {
            item["row_label"]: item["aggregate_label"]
            for item in catalog
            if item["kind"] == "numeric"
        }
        self.assertEqual(aggregate_by_row["연구개발비용 총계"], "총계")
        self.assertEqual(aggregate_by_row["연구개발비용 계"], "계")
        self.assertEqual(aggregate_by_row["회계처리 비용"], "")

    def test_program_prompt_excerpt_centers_late_relevant_context(self) -> None:
        candidate = {
            **_candidate("late-context", 10),
            "source_text": (
                "unrelated prefix " * 80
                + "requested semantic context appears beside the source value "
                + "unrelated suffix " * 40
            ),
        }
        row = FinancialAgent._semantic_program_prompt_rows(
            [candidate],
            relevance_groups=[["requested semantic context"]],
        )[0]
        self.assertIn("requested semantic context", row["source_text"])
        self.assertLessEqual(len(row["source_text"]), 420)

    def test_period_scope_uses_report_year_only_for_non_temporal_cell_labels(self) -> None:
        obligation = _obligation(
            "value",
            "direct_value",
            "reported value",
            scope=_scope(period="2023"),
        )
        generic_period = _candidate("generic", 10, period="reported amount")
        generic_period["year"] = 2023
        generic_period["source_anchor"] = "[sample | 2023 | section]"
        ready = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "value", "candidate_id": "generic"}
                ],
            },
            obligations=[obligation],
            candidate_catalog=[generic_period],
            query="Return the 2023 value.",
        )
        self.assertEqual(ready["status"], "ready")

        conflicting_period = {**generic_period, "candidate_id": "conflict", "period": "2022"}
        rejected = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "value", "candidate_id": "conflict"}
                ],
            },
            obligations=[obligation],
            candidate_catalog=[conflicting_period],
            query="Return the 2023 value.",
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "candidate_scope_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

    def test_catalog_maps_fiscal_ordinals_to_value_year_and_source_scope(self) -> None:
        catalog = build_semantic_candidate_catalog(
            [
                {
                    "candidate_id": "chunk-scope::value:0",
                    "source_anchor": "[sample | 2023 | research]",
                    "text": "The following amounts are disclosed. 연결 누계기준입니다.",
                    "candidate_kind": "structured_value",
                    "metadata": {
                        "company": "sample",
                        "year": 2023,
                        "period_focus": "multi_period",
                        "row_label": "research total",
                        "table_source_id": "table-research",
                        "structured_cells": [
                            {
                                "column_headers": ["제55기"],
                                "value_text": "380",
                                "unit_hint": "개",
                            },
                            {
                                "column_headers": ["제54기"],
                                "value_text": "343",
                                "unit_hint": "개",
                            },
                        ],
                    },
                }
            ]
        )
        numeric = [item for item in catalog if item["kind"] == "numeric"]
        self.assertEqual([item["value_year"] for item in numeric], [2023, 2022])
        self.assertEqual([item["value_role"] for item in numeric], ["current", "prior"])
        self.assertTrue(
            all(item["consolidation_scope"] == "consolidated" for item in numeric)
        )
        self.assertTrue(
            all(
                item["consolidation_scope_source"] == "source_context"
                for item in numeric
            )
        )
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "current",
                        "candidate_id": numeric[0]["candidate_id"],
                    },
                    {
                        "obligation_id": "prior",
                        "candidate_id": numeric[1]["candidate_id"],
                    },
                ],
            },
            obligations=[
                _obligation(
                    "current",
                    "direct_value",
                    "current",
                    scope=_scope(
                        company="sample",
                        period="2023",
                        consolidation_scope="consolidated",
                    ),
                ),
                _obligation(
                    "prior",
                    "direct_value",
                    "prior",
                    scope=_scope(
                        company="sample",
                        period="2022",
                        consolidation_scope="consolidated",
                    ),
                ),
            ],
            candidate_catalog=numeric,
            query="Return the current and prior research totals.",
        )
        self.assertEqual(validation["status"], "ready")

    def test_growth_expression_executes_without_operation_type_planning(self) -> None:
        obligations = [
            _obligation(
                "ob_growth",
                "derived_value",
                "change rate",
                display_unit="%",
                evidence_requirements=[
                    _requirement("ob_growth:req_closing", "closing quantity", period="closing"),
                    _requirement("ob_growth:req_opening", "opening quantity", period="opening"),
                ],
            )
        ]
        catalog = [
            _candidate("cand-opening", 343, period="opening"),
            _candidate("cand-closing", 380, period="closing"),
        ]
        program = {
            "status": "ready",
            "direct_bindings": [],
            "expressions": [
                {
                    "obligation_id": "ob_growth",
                    "variable_bindings": [
                        _binding("CURR", "cand-closing", "ob_growth:req_closing"),
                        _binding("PREV", "cand-opening", "ob_growth:req_opening"),
                    ],
                    "formula": "((CURR - PREV) / PREV) * 100",
                    "result_unit": "%",
                    "display_unit": "%",
                    "constants": [],
                }
            ],
            "narrative_bindings": [],
            "missing_obligation_ids": [],
            "ambiguous_obligation_ids": [],
        }
        execution = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="What percent did the quantity increase from opening to closing?",
        )
        self.assertEqual(execution["status"], "ok")
        output = execution["outputs_by_obligation"]["ob_growth"]
        self.assertAlmostEqual(output["normalized_value"], (380 - 343) / 343 * 100)
        self.assertEqual(output["operation_family"], "growth_rate")
        self.assertEqual(output["candidate_ids"], ["cand-closing", "cand-opening"])

    def test_percentage_point_difference_accepts_percent_operands(self) -> None:
        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_change",
                        "variable_bindings": [
                            _binding("CURRENT", "cand-current", "ob_change:req_current"),
                            _binding("PRIOR", "cand-prior", "ob_change:req_prior"),
                        ],
                        "formula": "CURRENT - PRIOR",
                        "result_unit": "PERCENT",
                        "display_unit": "%p",
                    }
                ],
            },
            obligations=[
                _obligation(
                    "ob_change",
                    "derived_value",
                    "margin change",
                    display_unit="%p",
                    evidence_requirements=[
                        _requirement("ob_change:req_current", "current margin", period="2023"),
                        _requirement("ob_change:req_prior", "prior margin", period="2022"),
                    ],
                )
            ],
            candidate_catalog=[
                _candidate(
                    "cand-current",
                    1.83,
                    raw_unit="%",
                    normalized_unit="PERCENT",
                    period="2023",
                ),
                _candidate(
                    "cand-prior",
                    1.73,
                    raw_unit="%",
                    normalized_unit="PERCENT",
                    period="2022",
                ),
            ],
            query="Return the percentage-point difference between the two margins.",
        )

        self.assertEqual(execution["status"], "ok")
        output = execution["outputs_by_obligation"]["ob_change"]
        self.assertAlmostEqual(output["normalized_value"], 0.1)
        self.assertEqual(output["normalized_unit"], "PERCENT")
        self.assertEqual(output["rendered_value"], "0.10%p")
        self.assertEqual(output["operation_family"], "difference")

    def test_source_stated_display_is_preserved_beside_formula_value(self) -> None:
        obligations = [
            _obligation(
                "ob_growth",
                "derived_value",
                "change rate",
                display_unit="%",
                evidence_requirements=[
                    _requirement("ob_growth:req_closing", "closing quantity"),
                    _requirement("ob_growth:req_opening", "opening quantity"),
                ],
            )
        ]
        stated = _candidate(
            "cand-stated",
            10.8,
            raw_unit="%",
            normalized_unit="PERCENT",
            row_label="change rate",
        )
        catalog = [
            _candidate("cand-opening", 343),
            _candidate("cand-closing", 380),
            stated,
        ]
        program = {
            "status": "ready",
            "expressions": [
                {
                    "obligation_id": "ob_growth",
                    "variable_bindings": [
                        _binding("CURR", "cand-closing", "ob_growth:req_closing"),
                        _binding("PREV", "cand-opening", "ob_growth:req_opening"),
                    ],
                    "formula": "((CURR - PREV) / PREV) * 100",
                    "result_unit": "%",
                    "source_display_candidate_id": "cand-stated",
                    "constants": [],
                }
            ],
        }
        execution = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="opening 343, closing 380: calculate the change rate",
        )
        output = execution["outputs_by_obligation"]["ob_growth"]
        self.assertTrue(output["source_stated_result_used"])
        self.assertEqual(output["rendered_value"], "10.8%")
        self.assertAlmostEqual(output["formula_result_value"], (380 - 343) / 343 * 100)

    def test_source_display_discrepancy_retains_both_values_and_provenance(self) -> None:
        fixture = _source_display_program_fixture()
        # Synthetic precise inputs can round to 40.0 / 44.0 while the rate rounds to 10.2%.
        self.assertEqual(round(39.96, 1), 40.0)
        self.assertEqual(round(44.04, 1), 44.0)
        self.assertEqual(round((44.04 / 39.96 - 1) * 100, 1), 10.2)
        result = execute_semantic_calculation_program(**fixture)
        self.assertEqual(result["status"], "ok")
        output = result["outputs_by_obligation"]["ob_change"]
        self.assertEqual(output["normalized_value"], 10.0)
        self.assertEqual(output["formula_result_value"], 10.0)
        self.assertEqual(output["answer_slot"]["normalized_value"], 10.0)
        self.assertEqual(output["source_display_value"], "10.2%")
        self.assertEqual(output["source_display_candidate_id"], "cand-stated")
        self.assertEqual(output["source_display_normalized_value"], 10.2)
        self.assertFalse(output["source_display_matches_formula"])
        self.assertFalse(output["source_stated_result_used"])
        self.assertEqual(output["formula_rendered_value"], output["rendered_value"])
        self.assertIn(output["formula_rendered_value"], result["answer"])
        self.assertIn("source-stated 10.2%", result["answer"])
        self.assertIn("calculated", result["answer"])
        self.assertIn("cand-stated", result["selected_candidate_ids"])
        self.assertIn("row-cand-stated", output["source_row_ids"])
        self.assertIn("[sample | 2024 | source note]", output["source_anchors"])
        self.assertIn("cand-stated", {row["operand_id"] for row in result["calculation_operands"]})

    def test_differing_source_display_is_not_silently_declared_equivalent(self) -> None:
        fixture = _source_display_program_fixture()
        fixture["candidate_catalog"][-1].update(
            normalized_value=95.0, raw_value="95.0",
            source_text="The target unit reports a quantity increase of 95.0%.",
        )
        result = execute_semantic_calculation_program(**fixture)
        self.assertEqual(result["status"], "ok")
        output = result["outputs_by_obligation"]["ob_change"]
        self.assertEqual(output["normalized_value"], 10.0)
        self.assertEqual(output["source_display_value"], "95.0%")
        self.assertFalse(output["source_display_matches_formula"])
        self.assertFalse(output["source_stated_result_used"])
        self.assertIn("calculated", result["answer"])
        self.assertIn("source-stated 95.0%", result["answer"])

    def test_source_display_comparison_keeps_existing_close_and_absent_behavior(self) -> None:
        for stated_value in (10.0, None):
            with self.subTest(stated_value=stated_value):
                fixture = _source_display_program_fixture()
                if stated_value is None:
                    fixture["program"]["expressions"][0]["source_display_candidate_id"] = ""
                else:
                    fixture["candidate_catalog"][-1].update(
                        normalized_value=stated_value, raw_value=str(stated_value),
                    )
                result = execute_semantic_calculation_program(**fixture)
                self.assertEqual(result["status"], "ok")
                output = result["outputs_by_obligation"]["ob_change"]
                self.assertEqual(output["formula_result_value"], 10.0)
                self.assertTrue(output["formula_rendered_value"])
                self.assertEqual(output["source_stated_result_used"], stated_value is not None)
                self.assertNotIn("source-stated", result["answer"])
                if stated_value is None:
                    self.assertIsNone(output["source_display_matches_formula"])
                    self.assertEqual(output["source_display_value"], "")
                    self.assertNotIn("cand-stated", result["selected_candidate_ids"])
                else:
                    self.assertTrue(output["source_display_matches_formula"])
                    self.assertEqual(output["rendered_value"], "10.0%")

    def test_source_display_discrepancy_is_labelled_in_korean(self) -> None:
        fixture = _source_display_program_fixture()
        fixture["query"] = "표시된 기초 수량과 기말 수량으로 증가율을 계산해 줘."
        result = execute_semantic_calculation_program(**fixture)
        self.assertIn("원문 기재: 10.2%", result["answer"])
        self.assertIn("계산값", result["answer"])

    def test_preserved_source_display_cannot_bypass_scope_or_unit_checks(self) -> None:
        for field, value in (
            ("company", "other"), ("period", "2023"),
            ("consolidation_scope", "separate"), ("segment", "other unit"),
            ("basis", "adjusted"), ("normalized_unit", "COUNT"),
        ):
            with self.subTest(field=field):
                fixture = _source_display_program_fixture()
                fixture["candidate_catalog"][-1][field] = value
                if field == "period":
                    fixture["candidate_catalog"][-1]["column_headers"] = [value]
                result = execute_semantic_calculation_program(**fixture)
                self.assertNotEqual(result["status"], "ok")
                self.assertNotIn("ob_change", result["outputs_by_obligation"])
                self.assertNotIn("10.2%", result["answer"])

    def test_nonratio_source_display_requires_a_compatible_dimension(self) -> None:
        fixture = _source_display_program_fixture()
        fixture["obligations"][0].update(label="quantity difference", display_unit="개")
        fixture["program"]["expressions"][0].update(formula="CLOSE - OPEN", result_unit="개")
        fixture["candidate_catalog"][-1].update(
            normalized_value=4.0, raw_value="4.0", raw_unit="원", normalized_unit="KRW",
        )
        result = execute_semantic_calculation_program(**fixture)
        self.assertNotEqual(result["status"], "ok")
        self.assertIn(
            "source_display_unit_mismatch",
            {row["code"] for row in result["validation"]["errors"]},
        )

    def test_nonratio_source_display_preserves_compatible_dimensions(self) -> None:
        for dimension, unit in (("COUNT", "개"), ("KRW", "원"), ("PERCENT", "%")):
            with self.subTest(dimension=dimension):
                fixture = _source_display_program_fixture()
                fixture["obligations"][0].update(label="difference", display_unit=unit)
                fixture["program"]["expressions"][0].update(
                    formula="CLOSE - OPEN", result_unit=unit,
                )
                for candidate in fixture["candidate_catalog"]:
                    candidate.update(normalized_unit=dimension, raw_unit=unit)
                fixture["candidate_catalog"][-1].update(
                    normalized_value=4.2, raw_value="4.2",
                )
                result = execute_semantic_calculation_program(**fixture)
                self.assertEqual(result["status"], "ok")
                output = result["outputs_by_obligation"]["ob_change"]
                self.assertEqual(output["formula_result_value"], 4.0)
                self.assertEqual(output["normalized_unit"], dimension)
                self.assertEqual(output["source_display_value"], f"4.2{unit}")
                self.assertFalse(output["source_display_matches_formula"])
                self.assertFalse(output["source_stated_result_used"])
                self.assertIn(f"source-stated 4.2{unit}", result["answer"])

    def test_selected_source_display_without_renderable_raw_value_fails_closed(self) -> None:
        fixture = _source_display_program_fixture()
        fixture["candidate_catalog"][-1]["raw_value"] = ""
        result = execute_semantic_calculation_program(**fixture)
        self.assertNotEqual(result["status"], "ok")
        self.assertIn(
            "empty_source_display_rendering",
            {row["code"] for row in result["validation"]["errors"]},
        )
        self.assertNotIn("ob_change", result["outputs_by_obligation"])

    def test_source_percent_display_ignores_incompatible_table_unit_hint(self) -> None:
        obligation = _obligation(
            "ob_growth",
            "derived_value",
            "change rate",
            display_unit="%",
            evidence_requirements=[
                _requirement("ob_growth:req_closing", "closing quantity"),
                _requirement("ob_growth:req_opening", "opening quantity"),
            ],
        )
        stated = _candidate(
            "cand-stated",
            10.8,
            raw_unit="억원",
            normalized_unit="PERCENT",
            row_label="change rate",
        )
        stated["raw_value"] = "10.8%"
        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_growth",
                        "variable_bindings": [
                            _binding("CURR", "cand-closing", "ob_growth:req_closing"),
                            _binding("PREV", "cand-opening", "ob_growth:req_opening"),
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                        "source_display_candidate_id": "cand-stated",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[
                _candidate("cand-opening", 343),
                _candidate("cand-closing", 380),
                stated,
            ],
            query="opening 343, closing 380: calculate the change rate",
        )
        self.assertEqual(
            execution["outputs_by_obligation"]["ob_growth"]["rendered_value"],
            "10.8%",
        )

    def test_multi_output_program_keeps_coupled_values_in_one_context(self) -> None:
        obligations = [
            _obligation("ob_total", "direct_value", "total", display_unit="백만원", coupling_key="mix"),
            *[
                _obligation(f"ob_share_{index}", "direct_value", f"share {index}", display_unit="%", coupling_key="mix")
                for index in range(1, 5)
            ],
            _obligation("ob_note", "narrative", "context", coupling_key="mix"),
        ]
        catalog = [
            _candidate("cand-total", 4395, raw_unit="백만원", normalized_unit="KRW", context="table-mix", row_label="total"),
            *[
                _candidate(
                    f"cand-share-{index}",
                    value,
                    raw_unit="%",
                    normalized_unit="PERCENT",
                    context="table-mix",
                    row_label=f"share {index}",
                )
                for index, value in enumerate((40, 30, 20, 10), start=1)
            ],
            {
                **_candidate("cand-note", 0, context="table-mix"),
                "kind": "narrative",
                "raw_value": "",
                "normalized_value": None,
                "source_text": "The four shares use the same stated total and basis.",
            },
        ]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_total", "candidate_id": "cand-total"},
                *[
                    {"obligation_id": f"ob_share_{index}", "candidate_id": f"cand-share-{index}"}
                    for index in range(1, 5)
                ],
            ],
            "narrative_bindings": [
                {
                    "obligation_id": "ob_note",
                    "candidate_ids": ["cand-note"],
                    "text": "The four shares use the same stated total and basis.",
                }
            ],
        }
        execution = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the total, four shares, and explain their basis.",
        )
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(len(execution["outputs"]), 6)
        self.assertIn("total", execution["answer"])
        self.assertIn("same stated total", execution["answer"])

    def test_generic_rendering_residual_fixtures(self) -> None:
        fixture_path = (
            Path(__file__).parent
            / "fixtures"
            / "semantic_program_rendering_residuals.json"
        )
        fixture = json.loads(fixture_path.read_text(encoding="utf-8"))

        scoped = fixture["shared_scope_numeric_outputs"]
        scoped_result = execute_semantic_calculation_program(
            program=scoped["program"],
            obligations=scoped["obligations"],
            candidate_catalog=scoped["candidate_catalog"],
            query=scoped["query"],
        )
        self.assertEqual(scoped_result["status"], "ok")
        for expected_text in scoped["expected_answer_contains"]:
            self.assertIn(expected_text, scoped_result["answer"])
        self.assertNotIn(":", scoped_result["answer"])

        narrative = fixture["selected_narrative_boundary"]
        narrative_result = execute_semantic_calculation_program(
            program=narrative["program"],
            obligations=narrative["obligations"],
            candidate_catalog=narrative["candidate_catalog"],
            query=narrative["query"],
        )
        self.assertEqual(narrative_result["status"], "ok")
        self.assertIn(
            narrative["expected_selected_text"],
            narrative_result["answer"],
        )
        self.assertNotIn(
            narrative["unselected_text"],
            narrative_result["answer"],
        )

    def test_coupling_rejects_lookalike_values_from_different_contexts(self) -> None:
        obligations = [
            _obligation("ob_total", "direct_value", "total", coupling_key="mix"),
            _obligation("ob_share", "direct_value", "share", coupling_key="mix"),
        ]
        catalog = [
            _candidate("cand-total", 4395, context="table-a"),
            _candidate("cand-share", 40, raw_unit="%", normalized_unit="PERCENT", context="table-b"),
        ]
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "ob_total", "candidate_id": "cand-total"},
                    {"obligation_id": "ob_share", "candidate_id": "cand-share"},
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the coupled total and share.",
        )
        self.assertEqual(validation["status"], "invalid")
        self.assertEqual(validation["missing_obligation_ids"], ["ob_share", "ob_total"])
        self.assertTrue(all(item["code"] == "coupled_context_mismatch" for item in validation["errors"]))

    def test_expression_context_mix_requires_grounded_compatibility_evidence(self) -> None:
        obligations = [
            _obligation(
                "ob_result",
                "derived_value",
                "comparison",
                evidence_requirements=[
                    _requirement(
                        "ob_result:req_consolidated",
                        "consolidated value",
                        company="sample",
                        consolidation_scope="consolidated",
                    ),
                    _requirement(
                        "ob_result:req_separate",
                        "separate value",
                        company="sample",
                        consolidation_scope="separate",
                    ),
                ],
            )
        ]
        first = {
            **_candidate(
                "cand-consolidated",
                30,
                raw_unit="원",
                normalized_unit="KRW",
                context="table-consolidated",
            ),
            "company": "sample",
            "consolidation_scope": "consolidated",
        }
        second = {
            **_candidate(
                "cand-separate",
                20,
                raw_unit="원",
                normalized_unit="KRW",
                context="table-separate",
            ),
            "company": "sample",
            "consolidation_scope": "separate",
        }
        expression = {
            "obligation_id": "ob_result",
            "variable_bindings": [
                _binding("A", "cand-consolidated", "ob_result:req_consolidated"),
                _binding("B", "cand-separate", "ob_result:req_separate"),
            ],
            "formula": "A - B",
            "result_unit": "원",
        }
        rejected = validate_semantic_calculation_program(
            program={"status": "ready", "expressions": [expression]},
            obligations=obligations,
            candidate_catalog=[first, second],
            query="Compare the two explicitly compatible bases.",
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "expression_context_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

        compatibility = {
            **_candidate("cand-compatibility", 0, context="compatibility-note"),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "normalized_unit": "UNKNOWN",
            "source_text": "The disclosure explicitly presents the two bases as comparable.",
        }
        accepted = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        **expression,
                        "compatibility_candidate_ids": ["cand-compatibility"],
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=[first, second, compatibility],
            query="Compare the two explicitly compatible bases.",
        )
        self.assertEqual(accepted["status"], "ok")
        self.assertIn("cand-compatibility", accepted["selected_candidate_ids"])

    def test_declared_cross_period_inputs_are_distinct_from_same_period_context_mix(self) -> None:
        fixture = _contract_residual_fixture()["expression_compatibility"]

        for case in fixture["cases"]:
            with self.subTest(case_id=case["case_id"]):
                validation = validate_semantic_calculation_program(
                    program=case["program"],
                    obligations=case["obligations"],
                    candidate_catalog=case["candidate_catalog"],
                    query=case["query"],
                )
                expected = case["expected_current"]
                self.assertEqual(validation["status"], expected["status"])
                if expected["status"] == "ready":
                    self.assertEqual(validation["errors"], [])
                    self.assertEqual(len(validation["valid_expressions"]), 1)
                    continue
                matching_errors = [
                    item
                    for item in validation["errors"]
                    if item["code"] == expected["error_code"]
                ]
                self.assertEqual(len(matching_errors), 1)
                self.assertEqual(matching_errors[0]["detail"], expected["detail"])
                self.assertEqual(
                    {item["code"] for item in validation["errors"]},
                    {"expression_context_mismatch"},
                )

    def test_declared_cross_period_source_display_stays_with_output_period_context(self) -> None:
        fixture = _source_display_program_fixture()
        opening, closing, stated = fixture["candidate_catalog"]
        opening.update(
            context_fingerprint="report-2023",
            table_source_id="report-2023",
        )
        closing.update(
            context_fingerprint="report-2024",
            table_source_id="report-2024",
        )
        stated.update(
            context_fingerprint="report-2024",
            table_source_id="report-2024",
        )

        validation = validate_semantic_calculation_program(**fixture)

        self.assertEqual(validation["status"], "ready")
        self.assertEqual(validation["errors"], [])

        stated.update(
            context_fingerprint="unrelated-2024-context",
            table_source_id="unrelated-2024-context",
        )
        rejected = validate_semantic_calculation_program(**fixture)
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "expression_context_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

    def test_structured_table_records_preserve_local_sibling_provenance(self) -> None:
        row_records = [
            {
                "row_label": "target venture",
                "row_headers": ["target venture"],
                "cells": [
                    {
                        "column_headers": ["ownership share"],
                        "value_text": "25.81",
                        "unit_hint": "%",
                    },
                    {
                        "column_headers": ["carrying value"],
                        "value_text": "1,294,367",
                        "unit_hint": "items",
                    },
                    {
                        "column_headers": ["net result"],
                        "value_text": "-803,742",
                        "unit_hint": "items",
                    },
                ],
            },
            {
                "row_label": "unrelated region",
                "row_headers": ["unrelated region"],
                "cells": [
                    {
                        "column_headers": ["ownership share"],
                        "value_text": "53",
                        "unit_hint": "%",
                    },
                    {
                        "column_headers": ["carrying value"],
                        "value_text": "637,681",
                        "unit_hint": "items",
                    },
                ],
            },
        ]
        value_records = [
            {
                "row_index": row_index,
                "column_index": column_index,
                "semantic_label": row["row_label"],
                "period_text": cell["column_headers"][0],
                "value_text": cell["value_text"],
                "unit_hint": cell["unit_hint"],
            }
            for row_index, row in enumerate(row_records)
            for column_index, cell in enumerate(row["cells"])
        ]
        base_metadata = {
            "chunk_uid": "sample:table:1",
            "company": "sample",
            "year": 2024,
            "is_table": True,
            "block_type": "table",
            "table_source_id": "sample table::1",
        }
        expected_local_cells = {
            ("target venture", ("ownership share",), "25.81"),
            ("target venture", ("carrying value",), "1,294,367"),
            ("target venture", ("net result",), "-803,742"),
            ("unrelated region", ("ownership share",), "53"),
            ("unrelated region", ("carrying value",), "637,681"),
        }

        for metadata_key, records, candidate_kind in (
            ("table_row_records_json", row_records, "structured_row"),
            ("table_value_records_json", value_records, "structured_value"),
        ):
            with self.subTest(metadata_key=metadata_key):
                metadata = {**base_metadata, metadata_key: json.dumps(records)}
                first_catalog = _catalog_from_document(
                    "The table body is available through immutable structured records.",
                    metadata,
                )
                second_catalog = _catalog_from_document(
                    "The table body is available through immutable structured records.",
                    metadata,
                )
                numeric = [
                    item
                    for item in first_catalog
                    if item.get("kind") == "numeric"
                    and item.get("candidate_kind") == candidate_kind
                ]
                local_cells = {
                    (
                        item.get("row_label"),
                        tuple(item.get("column_headers") or []),
                        item.get("raw_value"),
                    )
                    for item in numeric
                }

                self.assertEqual(local_cells, expected_local_cells)
                self.assertNotIn(
                    ("target venture", ("ownership share",), "53"),
                    local_cells,
                )
                self.assertNotIn(
                    ("unrelated region", ("net result",), "-803,742"),
                    local_cells,
                )
                self.assertEqual(
                    {
                        item["candidate_id"]
                        for item in numeric
                    },
                    {
                        item["candidate_id"]
                        for item in second_catalog
                        if item.get("kind") == "numeric"
                        and item.get("candidate_kind") == candidate_kind
                    },
                )
                self.assertTrue(
                    all(
                        str(item.get("source_candidate_id") or "").startswith("table_")
                        and "::row_" in str(item.get("source_candidate_id") or "")
                        for item in numeric
                    )
                )

    def test_repeated_table_bundle_uses_one_candidate_per_physical_cell(self) -> None:
        table_source_id = "sample section::table:7"
        row_records = [
            {
                "row_id": "2:0",
                "row_label": "target entity",
                "row_headers": ["region", "target entity"],
                "cells": [
                    {
                        "cell_id": "2:0:2",
                        "column_index": 2,
                        "column_headers": ["current period", "ownership share"],
                        "value_text": "26",
                        "unit_hint": "%",
                    }
                ],
            },
            {
                "row_id": "2:1",
                "row_label": "other entity",
                "row_headers": ["region", "other entity"],
                "cells": [
                    {
                        "cell_id": "2:1:2",
                        "column_index": 2,
                        "column_headers": ["current period", "ownership share"],
                        "value_text": "53",
                        "unit_hint": "%",
                    }
                ],
            },
        ]
        value_records = [
            {
                "value_id": f"{table_source_id}:v:{row_index}:2",
                "row_index": row_index,
                "column_index": 2,
                "semantic_label": row["row_label"],
                "row_label": row["row_label"],
                "row_headers": row["row_headers"],
                "column_headers": ["current period", "ownership share"],
                "period_text": "current period",
                "value_text": row["cells"][0]["value_text"],
                "unit_hint": "%",
                "value_role": "detail",
                "aggregation_stage": "none",
            }
            for row_index, row in enumerate(row_records)
        ]

        def build(order):
            docs = []
            for chunk_uid in order:
                docs.append(
                    (
                        SimpleNamespace(
                            page_content=(
                                "PARENT TABLE BODY target entity 26% other entity 53% "
                                "unrelated material must not be copied into every row."
                            ),
                            metadata={
                                "chunk_uid": chunk_uid,
                                "company": "document company",
                                "year": 2024,
                                "is_table": True,
                                "block_type": "table",
                                "table_source_id": table_source_id,
                                "table_header_context": "entity | current period ownership share",
                                "table_row_records_json": json.dumps(row_records),
                                "table_value_records_json": json.dumps(value_records),
                            },
                        ),
                        0.0,
                    )
                )
            source_state = {"retrieved_docs": docs}
            sources = build_semantic_source_candidates(
                source_state,
                source_anchor_builder=lambda item: f"[{item.get('chunk_uid')}]",
            )
            return source_state, sources, build_semantic_candidate_catalog(sources)

        first_state, first_sources, first_catalog = build(["chunk-b", "chunk-a"])
        _second_state, second_sources, second_catalog = build(["chunk-a", "chunk-b"])
        first_numeric = [
            item
            for item in first_catalog
            if item.get("kind") == "numeric"
            and item.get("candidate_kind") == "structured_row"
        ]
        second_numeric = [
            item
            for item in second_catalog
            if item.get("kind") == "numeric"
            and item.get("candidate_kind") == "structured_row"
        ]

        self.assertEqual(
            len(
                [
                    item
                    for item in first_sources
                    if item.get("candidate_kind") == "structured_row"
                ]
            ),
            2,
        )
        self.assertEqual(len(first_numeric), 2)
        self.assertEqual(
            {item["candidate_id"] for item in first_numeric},
            {item["candidate_id"] for item in second_numeric},
        )
        self.assertEqual(
            semantic_candidate_catalog_fingerprint(first_catalog),
            semantic_candidate_catalog_fingerprint(second_catalog),
        )
        target = next(item for item in first_numeric if item["raw_value"] == "26")
        self.assertEqual(target["physical_table_id"], table_source_id)
        self.assertEqual(target["physical_row_id"], "2:0")
        self.assertEqual(target["physical_cell_id"], "2:0:2")
        self.assertEqual(
            target["physical_value_id"],
            f"{table_source_id}:v:0:2",
        )
        self.assertEqual(target["row_headers"], ["region", "target entity"])
        self.assertEqual(
            target["local_entity_surfaces"],
            ["target entity", "region"],
        )
        self.assertNotIn("other entity 53", target["source_text"])
        self.assertNotIn("unrelated material", target["source_text"])
        diagnostics = semantic_candidate_stage_diagnostics(
            state=first_state,
            source_candidates=first_sources,
            catalog=first_catalog,
            prompt_catalog=first_catalog,
        )
        self.assertEqual(
            diagnostics["physical_deduplication"],
            {
                "structured_table_attachment_count": 2,
                "attached_physical_cell_projection_count": 4,
                "unique_physical_cell_candidate_count": 2,
                "duplicate_physical_cell_projection_count": 2,
            },
        )

    def test_owner_cohort_prefers_local_match_and_excludes_conflicting_row(self) -> None:
        obligation = _obligation(
            "ob_share",
            "direct_value",
            "ownership share",
            scope=_scope(
                company="document company",
                segment="target entity",
            ),
        )
        target = {
            **_candidate("target", 26, raw_unit="%", normalized_unit="PERCENT"),
            "candidate_kind": "structured_row",
            "company": "document company",
            "document_company": "document company",
            "row_label": "ownership share",
            "row_headers": ["region", "target entity"],
            "local_entity_surfaces": ["ownership share", "region", "target entity"],
            "physical_table_id": "table-1",
            "physical_row_id": "row-target",
            "physical_cell_id": "cell-target",
        }
        conflicting = {
            **target,
            "candidate_id": "other",
            "row_headers": ["region", "other entity"],
            "local_entity_surfaces": ["ownership share", "region", "other entity"],
            "physical_row_id": "row-other",
            "physical_cell_id": "cell-other",
            "raw_value": "53",
            "normalized_value": 53.0,
        }
        unknown = {
            **_candidate("unknown", 25, raw_unit="%", normalized_unit="PERCENT"),
            "candidate_kind": "sentence_value",
            "company": "document company",
            "document_company": "document company",
            "row_label": "reported share",
            "row_headers": [],
            "local_entity_surfaces": [],
            "source_text": "A reported share of 25% appears in the note.",
        }

        self.assertEqual(
            semantic_candidate_applicability(target, obligation)["state"],
            "compatible",
        )
        self.assertEqual(
            semantic_candidate_applicability(conflicting, obligation)["state"],
            "explicit_conflict",
        )
        self.assertEqual(
            semantic_candidate_applicability(unknown, obligation)["state"],
            "unknown_only",
        )

        cohort_plan = _semantic_candidate_cohorts(
            [unknown, conflicting, target],
            [obligation],
        )
        output_cohort = next(
            item
            for item in cohort_plan["cohorts"]
            if item["cohort_id"] == "ob_share:output"
        )
        self.assertEqual(output_cohort["candidate_ids"], ["target", "unknown"])
        self.assertEqual(
            output_cohort["applicability_counts"],
            {"compatible": 1, "unknown_only": 1, "explicit_conflict": 1},
        )
        payload = FinancialAgent._semantic_program_prompt_payload(
            [unknown, conflicting, target],
            cohort_plan,
        )
        self.assertNotIn("other", payload["candidates_by_id"])
        target_row = payload["candidates_by_id"]["target"]
        self.assertEqual(target_row["document_company"], "document company")
        self.assertEqual(target_row["row_headers"], ["region", "target entity"])
        self.assertEqual(target_row["physical_row_id"], "row-target")
        self.assertEqual(
            target_row["applicability_by_owner"]["ob_share"]["state"],
            "compatible",
        )

    def test_source_defined_group_cohort_admits_structured_items_with_shared_cap(self) -> None:
        scope = _scope(
            company="document company",
            period="2024",
            segment="target entity",
        )
        label = "target entity source-defined result summary"
        requirement_id = "ob_summary:req_001"
        obligation = _obligation(
            "ob_summary",
            "narrative",
            label,
            scope=scope,
            evidence_mode="source_defined_group",
            retrieval_hints=[label],
            evidence_requirements=[
                {
                    **_requirement(
                        requirement_id,
                        label,
                        period="2024",
                        company="document company",
                        segment="target entity",
                    ),
                    "retrieval_hints": [label],
                }
            ],
        )

        def structured(candidate_id, value, row_label, entity="target entity"):
            return {
                **_candidate(
                    candidate_id,
                    value,
                    raw_unit="items",
                    period="2024",
                    row_label=row_label,
                ),
                "candidate_kind": "structured_row",
                "company": "document company",
                "document_company": "document company",
                "row_headers": [entity, row_label],
                "local_entity_surfaces": [entity, row_label],
                "source_text": f"{entity} {row_label} 2024 {value} items",
            }

        revenue = structured("target-revenue", 100, "revenue")
        result = structured("target-result", -20, "net result")
        conflicting = structured("other-result", 53, "net result", "other entity")
        narrative = {
            **_candidate("target-context", 0, period="2024"),
            "kind": "narrative",
            "candidate_kind": "narrative",
            "normalized_value": None,
            "raw_value": "",
            "company": "document company",
            "document_company": "document company",
            "row_headers": ["target entity"],
            "local_entity_surfaces": ["target entity"],
            "source_text": "The target entity disclosure presents its source-defined results.",
        }
        catalog = [conflicting, narrative, revenue, result]

        cohort_plan = _semantic_candidate_cohorts(catalog, [obligation])

        self.assertEqual(cohort_plan["status"], "ok")
        self.assertEqual(cohort_plan["reservation"]["numeric"], 12)
        self.assertEqual(cohort_plan["reservation"]["narrative"], 12)
        for cohort in cohort_plan["cohorts"]:
            self.assertEqual(cohort["candidate_kind"], "evidence")
            self.assertLessEqual(len(cohort["candidate_ids"]), 6)
            self.assertIn("target-revenue", cohort["candidate_ids"])
            self.assertIn("target-result", cohort["candidate_ids"])
            self.assertIn("target-context", cohort["candidate_ids"])
            self.assertNotIn("other-result", cohort["candidate_ids"])

        bounded_plan = _semantic_candidate_cohorts(
            [
                *catalog,
                *[
                    structured(
                        f"target-noise-{index}",
                        index,
                        f"unrelated source item {index}",
                    )
                    for index in range(1, 6)
                ],
            ],
            [obligation],
        )
        for cohort in bounded_plan["cohorts"]:
            self.assertEqual(len(cohort["candidate_ids"]), 6)
            self.assertNotIn("other-result", cohort["candidate_ids"])

        ordinary_narrative = _obligation(
            "ob_context",
            "narrative",
            "target entity context",
            scope=scope,
        )
        ordinary_plan = _semantic_candidate_cohorts(
            [narrative, revenue],
            [ordinary_narrative],
        )
        ordinary_cohort = ordinary_plan["cohorts"][0]
        self.assertEqual(ordinary_cohort["candidate_kind"], "narrative")
        self.assertEqual(ordinary_cohort["candidate_ids"], ["target-context"])

        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": ["target-revenue", "target-result"],
                        "evidence_bindings": [
                            {
                                "candidate_id": candidate_id,
                                "source_requirement_id": requirement_id,
                            }
                            for candidate_id in ("target-revenue", "target-result")
                        ],
                        "text": (
                            "The target entity reports revenue of 100 items "
                            "and net result of -20 items."
                        ),
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=catalog,
            query="Summarize the target entity's source-defined results.",
            selectable_candidate_ids_by_owner=cohort_plan[
                "candidate_ids_by_owner"
            ],
        )
        self.assertEqual(validation["status"], "ready")
        self.assertEqual(validation["errors"], [])

    def test_owner_cohort_scores_full_row_axis_before_other_target_cells(self) -> None:
        obligation = _obligation(
            "ob_share",
            "direct_value",
            "target entity ownership share",
            scope=_scope(
                company="document company",
                segment="target entity",
            ),
        )
        common = {
            "candidate_kind": "structured_row",
            "company": "document company",
            "document_company": "document company",
            "row_headers": ["all entities", "target entity", "region"],
            "local_entity_surfaces": ["all entities", "target entity", "region"],
            "physical_table_id": "table-1",
            "physical_row_id": "row-target",
        }
        distractors = [
            {
                **_candidate(f"other-{index}", index + 1),
                **common,
                "row_label": "target entity",
                "column_headers": [column_header],
                "physical_cell_id": f"cell-{index}",
            }
            for index, column_header in enumerate(
                ("cash", "current liabilities", "non-current liabilities", "assets")
            )
        ]
        target = {
            **_candidate("target-share", 26, raw_unit="%", normalized_unit="PERCENT"),
            **common,
            "row_label": "region",
            "column_headers": ["ownership share"],
            "physical_cell_id": "cell-share",
        }

        cohort_plan = _semantic_candidate_cohorts(
            [*distractors, target],
            [obligation],
        )
        output_cohort = next(
            item
            for item in cohort_plan["cohorts"]
            if item["cohort_id"] == "ob_share:output"
        )
        self.assertEqual(output_cohort["candidate_ids"][0], "target-share")
        self.assertIn("target-share", output_cohort["candidate_ids"])
        self.assertEqual(len(output_cohort["candidate_ids"]), 4)

    def test_owner_cohort_admits_relevant_unknown_before_scope_only_noise(self) -> None:
        obligation = _obligation(
            "ob_metric",
            "direct_value",
            "2024 target metric total",
            scope=_scope(
                company="document company",
                period="2024",
                consolidation_scope="consolidated",
            ),
            retrieval_hints=["target metric"],
        )
        target = {
            **_candidate(
                "target-unknown",
                42,
                period="2024",
                row_label="target metric total",
            ),
            "company": "document company",
            "document_company": "document company",
        }
        noise = [
            {
                **_candidate(
                    f"scope-only-{index}",
                    index + 1,
                    period="2024",
                    row_label=f"unrelated field {index}",
                ),
                "company": "document company",
                "document_company": "document company",
                "consolidation_scope": "consolidated",
            }
            for index in range(4)
        ]

        cohort_plan = _semantic_candidate_cohorts(
            [*noise, target],
            [obligation],
        )
        output_cohort = next(
            item
            for item in cohort_plan["cohorts"]
            if item["cohort_id"] == "ob_metric:output"
        )
        self.assertIn("target-unknown", output_cohort["candidate_ids"])
        self.assertEqual(output_cohort["candidate_ids"][-1], "target-unknown")
        self.assertEqual(len(output_cohort["candidate_ids"]), 4)
        self.assertEqual(
            output_cohort["applicability_counts"],
            {"compatible": 4, "unknown_only": 1, "explicit_conflict": 0},
        )

    def test_validator_rejects_cross_owner_candidate_visibility(self) -> None:
        target = _candidate("target-visible", 26, raw_unit="%", normalized_unit="PERCENT")
        other = _candidate("other-visible", 53, raw_unit="%", normalized_unit="PERCENT")
        obligations = [
            _obligation("ob_target", "direct_value", "target share", display_unit="%"),
            _obligation("ob_other", "direct_value", "other share", display_unit="%"),
        ]
        validation = validate_semantic_calculation_program(
            program={
                "status": "incomplete",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_target",
                        "candidate_id": "other-visible",
                    }
                ],
                "missing_obligation_ids": ["ob_other"],
            },
            obligations=obligations,
            candidate_catalog=[target, other],
            query="Return both shares.",
            selectable_candidate_ids_by_owner={
                "ob_target": ["target-visible"],
                "ob_other": ["other-visible"],
            },
        )
        self.assertIn(
            {
                "code": "candidate_not_exposed_to_compiler",
                "obligation_id": "ob_target",
                "detail": "other-visible",
            },
            validation["errors"],
        )

        derived = _obligation(
            "ob_derived",
            "derived_value",
            "difference",
            evidence_requirements=[
                _requirement("ob_derived:req_a", "first input"),
                _requirement("ob_derived:req_b", "second input"),
            ],
        )
        requirement_validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_derived",
                        "variable_bindings": [
                            _binding("A", "other-visible", "ob_derived:req_a"),
                            _binding("B", "target-visible", "ob_derived:req_b"),
                        ],
                        "formula": "A - B",
                    }
                ],
            },
            obligations=[derived],
            candidate_catalog=[target, other],
            query="Subtract the second input from the first input.",
            selectable_candidate_ids_by_owner={
                "ob_derived": ["target-visible", "other-visible"],
                "ob_derived:req_a": ["target-visible"],
                "ob_derived:req_b": ["other-visible"],
            },
        )
        self.assertGreaterEqual(
            sum(
                item["code"] == "candidate_not_exposed_to_compiler"
                for item in requirement_validation["errors"]
            ),
            2,
        )

    def test_candidate_cohort_reservation_overflow_fails_closed(self) -> None:
        obligations = [
            _obligation(
                f"ob_{index}",
                "derived_value",
                f"derived output {index}",
                evidence_requirements=[
                    _requirement(
                        f"ob_{index}:req_{requirement_index}",
                        f"input {requirement_index}",
                    )
                    for requirement_index in range(3)
                ],
            )
            for index in range(9)
        ]
        cohort_plan = _semantic_candidate_cohorts([], obligations)
        self.assertEqual(cohort_plan["status"], "capacity_exceeded")
        self.assertGreater(
            cohort_plan["reservation"]["numeric"],
            cohort_plan["reservation"]["numeric_limit"],
        )
        self.assertEqual(cohort_plan["cohorts"], [])

    def test_targeted_retry_merge_preserves_valid_output_bytes(self) -> None:
        preserved = {
            "obligation_id": "ob_valid",
            "candidate_id": "cand-valid",
            "compatibility_candidate_ids": [],
            "resolved_subject": "target",
            "subject_source": "candidate_row_identity",
            "subject_source_row_ids": ["row-valid"],
        }
        before = json.dumps(
            preserved,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        merged = _merge_targeted_program_retry(
            previous_validation={
                "valid_direct_bindings": [preserved],
                "valid_expressions": [],
                "valid_narrative_bindings": [],
            },
            retry_program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_retry",
                        "candidate_id": "cand-promoted",
                    }
                ],
            },
            target_obligation_ids=["ob_retry"],
        )
        after = json.dumps(
            merged["direct_bindings"][0],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(after, before)

    def test_canonical_operand_projection_resolves_local_unit_and_current_period(self) -> None:
        fixture = _contract_residual_fixture()["canonical_operand_projection"]
        expected = fixture["expected_after_repair"]
        catalog = build_semantic_candidate_catalog([fixture["source_candidate"]])
        numeric = {
            tuple(item.get("column_headers") or []): item
            for item in catalog
            if item.get("kind") == "numeric"
        }
        share = numeric[("ownership share",)]
        amount = numeric[("carrying amount",)]

        self.assertEqual(share["candidate_id"], expected["share_candidate_id"])
        self.assertEqual(amount["candidate_id"], expected["amount_candidate_id"])
        self.assertEqual(share["raw_value"], expected["share_raw_value"])
        self.assertEqual(share["raw_unit"], expected["share_raw_unit"])
        self.assertEqual(
            share["source_unit_hint"], expected["share_source_unit_hint"]
        )
        self.assertEqual(
            share["raw_unit_source"], expected["share_raw_unit_source"]
        )
        self.assertEqual(
            share["normalized_unit"], expected["share_normalized_unit"]
        )
        self.assertEqual(amount["raw_unit"], expected["amount_raw_unit"])
        self.assertEqual(
            amount["raw_unit_source"], expected["amount_raw_unit_source"]
        )
        self.assertEqual(
            amount["normalized_unit"], expected["amount_normalized_unit"]
        )
        self.assertEqual(
            [share["period"], amount["period"]],
            [expected["period"], expected["period"]],
        )
        self.assertEqual(
            [share["value_year"], amount["value_year"]],
            [expected["value_year"], expected["value_year"]],
        )
        self.assertEqual(
            [share["period_source"], amount["period_source"]],
            [expected["period_source"], expected["period_source"]],
        )
        self.assertEqual(
            [share["source_period_surface"], amount["source_period_surface"]],
            ["ownership share", "carrying amount"],
        )

        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_share",
                        "candidate_id": share["candidate_id"],
                    },
                    {
                        "obligation_id": "ob_amount",
                        "candidate_id": amount["candidate_id"],
                    },
                ],
                "expressions": [],
                "narrative_bindings": [],
                "missing_obligation_ids": [],
                "ambiguous_obligation_ids": [],
            },
            obligations=fixture["obligations"],
            candidate_catalog=catalog,
            query=fixture["query"],
        )

        self.assertEqual(execution["status"], "ok")
        outputs = {
            item["obligation_id"]: item for item in execution["outputs"]
        }
        operands = {
            item["candidate_id"]: item
            for item in execution["calculation_operands"]
        }
        self.assertEqual(outputs["ob_share"]["subject"], expected["subject"])
        self.assertEqual(outputs["ob_amount"]["subject"], expected["subject"])
        self.assertEqual(operands[share["candidate_id"]]["label"], "target venture ownership share")
        self.assertEqual(operands[amount["candidate_id"]]["label"], "target venture carrying amount")
        self.assertEqual(operands[share["candidate_id"]]["row_label"], "region")
        self.assertEqual(operands[share["candidate_id"]]["subject"], expected["subject"])
        self.assertEqual(
            operands[share["candidate_id"]]["subject_source"],
            "candidate_row_identity",
        )

    def test_pipe_table_rows_preserve_local_value_association_without_structured_metadata(self) -> None:
        catalog = _catalog_from_document(
            "\n".join(
                [
                    (
                        "entity | opening balance | opening balance | closing balance | "
                        "closing balance | latest result"
                    ),
                    (
                        "entity | ownership share | carrying value | ownership share | "
                        "carrying value | net result"
                    ),
                    "target venture | 25.92% | 700,691 | 25.81% | 1,294,367 | -803,742",
                    "unrelated region | 53% | 637,681 | 50% | 9,413 | 120",
                ]
            ),
            {
                "chunk_uid": "sample:legacy-table:1",
                "company": "sample",
                "year": 2024,
                "is_table": True,
                "block_type": "table",
                "unit_hint": "items",
                "table_source_id": "sample legacy table::1",
                "table_header_context": "\n".join(
                    [
                        (
                            "entity | opening balance | opening balance | "
                            "closing balance | closing balance | latest result"
                        ),
                        (
                            "entity | ownership share | carrying value | "
                            "ownership share | carrying value | net result"
                        ),
                    ]
                ),
            },
        )
        local_cells = {
            (
                item.get("row_label"),
                tuple(item.get("column_headers") or []),
                item.get("raw_value"),
            )
            for item in catalog
            if item.get("kind") == "numeric"
            and item.get("candidate_kind") == "table_row"
        }

        self.assertIn(
            (
                "target venture",
                ("opening balance", "ownership share"),
                "25.92",
            ),
            local_cells,
        )
        self.assertIn(
            (
                "target venture",
                ("closing balance", "ownership share"),
                "25.81",
            ),
            local_cells,
        )
        self.assertIn(
            (
                "target venture",
                ("closing balance", "carrying value"),
                "1,294,367",
            ),
            local_cells,
        )
        self.assertIn(
            ("target venture", ("latest result", "net result"), "-803,742"),
            local_cells,
        )
        self.assertNotIn(
            ("target venture", ("opening balance", "ownership share"), "53"),
            local_cells,
        )

    def test_flattened_table_summary_is_not_binding_authority(self) -> None:
        fixture = _contract_residual_fixture()["candidate_admission"]
        source_metadata = fixture["source_candidates"][0]["metadata"]
        catalog = build_semantic_candidate_catalog(
            fixture["source_candidates"],
            relevance_texts=fixture["relevance_texts"],
        )
        raw_values = {
            str(item.get("raw_value") or "")
            for item in catalog
            if item.get("kind") == "numeric"
        }
        expected = fixture["expected_current"]

        for raw_value in expected["present_raw_values"]:
            self.assertIn(raw_value, raw_values)
        for raw_value in expected["missing_raw_values"]:
            self.assertIn(raw_value, source_metadata["table_value_labels_text"])
            self.assertNotIn(raw_value, raw_values)

    def test_prompt_admission_keeps_each_relevant_sibling_cell(self) -> None:
        sibling_cells = []
        for candidate_id, raw_value, header in (
            ("share", 25.81, "ownership share"),
            ("carrying", 1_294_367, "carrying value"),
            ("result", -803_742, "net result"),
        ):
            candidate = {
                **_candidate(
                    candidate_id,
                    raw_value,
                    row_label="target venture",
                ),
                "source_candidate_id": "shared-row",
                "evidence_id": "shared-table",
                "source_row_id": "target-row",
                "column_headers": [header],
                "source_text": f"target venture {header} {raw_value}",
            }
            sibling_cells.append(candidate)
        noise = [
            _candidate(
                f"noise-{index}",
                index + 1,
                row_label=f"unrelated entity {index}",
            )
            for index in range(12)
        ]

        selected = select_semantic_prompt_candidates(
            [*noise, *sibling_cells],
            relevance_groups=[
                ["target venture", "ownership share"],
                ["target venture", "carrying value"],
                ["target venture", "net result"],
            ],
            max_numeric_candidates=3,
            max_narrative_candidates=0,
        )

        self.assertEqual(
            {item["candidate_id"] for item in selected},
            {"share", "carrying", "result"},
        )

    def test_prompt_admission_reserves_local_cohort_for_each_required_input(self) -> None:
        fixture = _contract_residual_fixture()["candidate_admission"][
            "required_input_prompt_coverage"
        ]
        rows = [
            {
                **_candidate(
                    "result-rate",
                    15,
                    raw_unit="%",
                    normalized_unit="PERCENT",
                    row_label="",
                ),
                "source_candidate_id": "result-source",
                "evidence_id": "result-source",
                "source_text": "change rate 15 percent",
                "candidate_kind": "sentence_value",
            }
        ]
        required_groups = []
        value = 100
        for group in fixture["required_input_groups"]:
            required_groups.append([group["surface"]])
            for candidate in group["candidates"]:
                is_percent = candidate["unit"] == "PERCENT"
                rows.append(
                    {
                        **_candidate(
                            candidate["candidate_id"],
                            value,
                            raw_unit="%" if is_percent else "items",
                            normalized_unit=candidate["unit"],
                            row_label="",
                        ),
                        "source_candidate_id": group["source_id"],
                        "evidence_id": group["source_id"],
                        "source_text": f"{group['surface']} reported value",
                        "candidate_kind": "sentence_value",
                    }
                )
                value += 1

        all_groups = [fixture["output_relevance_group"], *required_groups]
        selected = select_semantic_prompt_candidates(
            rows,
            relevance_groups=all_groups,
            numeric_relevance_groups=all_groups,
            required_numeric_relevance_groups=required_groups,
            max_numeric_candidates=fixture["max_numeric_candidates"],
            max_narrative_candidates=0,
        )

        selected_ids = {item["candidate_id"] for item in selected}
        self.assertEqual(len(selected), fixture["max_numeric_candidates"])
        self.assertTrue(
            set(fixture["expected_required_candidate_ids"]).issubset(selected_ids)
        )

    def test_sentence_value_context_does_not_split_at_decimal_points(self) -> None:
        fixture = _contract_residual_fixture()["candidate_admission"][
            "required_input_prompt_coverage"
        ]["decimal_pair_context"]
        catalog = _catalog_from_document(
            fixture["text"],
            {"chunk_uid": fixture["source_id"]},
        )
        target = next(
            item
            for item in catalog
            if item.get("kind") == "numeric"
            and item.get("raw_value") == fixture["target_value"]
        )

        self.assertEqual(target["source_text"], fixture["expected_context"])
        selected = select_semantic_prompt_candidates(
            catalog,
            relevance_groups=[[fixture["required_surface"]]],
            required_numeric_relevance_groups=[
                [fixture["required_surface"]]
            ],
            max_numeric_candidates=2,
            max_narrative_candidates=0,
            max_required_candidates_per_group=2,
        )

        self.assertIn(
            target["candidate_id"],
            {item["candidate_id"] for item in selected},
        )

    def test_direct_binding_rejects_table_wide_subject_match_for_wrong_local_row(self) -> None:
        fixture = _contract_residual_fixture()["direct_binding"]
        subject = fixture["subject_identity"]

        validation = validate_semantic_calculation_program(
            program=subject["program"],
            obligations=subject["obligations"],
            candidate_catalog=subject["candidate_catalog"],
            query=subject["query"],
        )
        expected = subject["expected_after_repair"]

        self.assertEqual(validation["status"], expected["status"])
        matching_errors = [
            item
            for item in validation["errors"]
            if item["code"] == expected["error_code"]
        ]
        self.assertEqual(len(matching_errors), 1)
        self.assertEqual(matching_errors[0]["detail"], expected["detail"])

    def test_direct_binding_accepts_subject_from_structured_same_row_header(self) -> None:
        fixture = _contract_residual_fixture()["direct_binding"]["subject_identity"]
        catalog = build_semantic_candidate_catalog(
            [fixture["same_row_source_candidate"]]
        )
        numeric_candidates = [item for item in catalog if item["kind"] == "numeric"]
        self.assertEqual(len(numeric_candidates), 1)
        candidate = numeric_candidates[0]
        expected = fixture["same_row_expected"]

        self.assertEqual(candidate.get("row_headers"), expected["row_headers"])
        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_share",
                        "candidate_id": candidate["candidate_id"],
                    }
                ],
            },
            obligations=fixture["obligations"],
            candidate_catalog=catalog,
            query=fixture["query"],
        )

        self.assertEqual(execution["status"], expected["status"])
        self.assertEqual(
            execution["outputs_by_obligation"]["ob_share"]["rendered_value"],
            expected["rendered_value"],
        )

    def test_direct_subject_compatibility_bridges_only_absent_row_identity(self) -> None:
        obligation = _obligation(
            "ob_value",
            "direct_value",
            "target venture value",
            scope=_scope(segment="target venture"),
        )
        numeric = {
            **_candidate("cand-value", 30, row_label=""),
            "candidate_kind": "structured_value",
            "evidence_id": "shared-evidence",
            "source_text": "30 items",
        }
        witness = {
            **_candidate("cand-subject", 0, row_label=""),
            "kind": "narrative",
            "candidate_kind": "evidence",
            "evidence_id": "shared-evidence",
            "raw_value": "",
            "normalized_value": None,
            "normalized_unit": "UNKNOWN",
            "source_text": "The table reports values for the target venture.",
        }
        program = {
            "status": "ready",
            "direct_bindings": [
                {
                    "obligation_id": "ob_value",
                    "candidate_id": "cand-value",
                    "compatibility_candidate_ids": ["cand-subject"],
                }
            ],
        }

        accepted = execute_semantic_calculation_program(
            program=program,
            obligations=[obligation],
            candidate_catalog=[numeric, witness],
            query="Return the target venture value.",
        )
        self.assertEqual(accepted["status"], "ok")

        contradictory = {
            **numeric,
            "row_label": "unrelated region",
            "row_headers": ["unrelated region"],
            "source_text": "The target venture appears elsewhere in this table.",
        }
        rejected = validate_semantic_calculation_program(
            program=program,
            obligations=[obligation],
            candidate_catalog=[contradictory, witness],
            query="Return the target venture value.",
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "candidate_subject_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

    def test_characterizes_direct_display_unit_fail_open_behavior(self) -> None:
        fixture = _contract_residual_fixture()["direct_binding"]
        conversion = fixture["display_unit_conversion"]
        conversion_execution = execute_semantic_calculation_program(
            program=conversion["program"],
            obligations=conversion["obligations"],
            candidate_catalog=conversion["candidate_catalog"],
            query=conversion["query"],
        )
        conversion_expected = conversion["expected_current"]
        self.assertEqual(conversion_execution["status"], conversion_expected["status"])
        conversion_output = conversion_execution["outputs_by_obligation"]["ob_value"]
        self.assertEqual(
            conversion_output["result_unit"],
            conversion_expected["requested_display_unit"],
        )
        self.assertEqual(
            conversion_output["rendered_value"],
            conversion_expected["rendered_value"],
        )

    def test_direct_binding_with_incompatible_unit_cannot_emit_an_empty_ok_output(self) -> None:
        obligation = _obligation(
            "ob_value",
            "direct_value",
            "reported amount",
            display_unit="원",
        )
        candidate = _candidate(
            "cand-unknown-unit",
            123,
            raw_unit="",
            normalized_unit="UNKNOWN",
        )

        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-unknown-unit",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Return the reported amount in won.",
        )

        self.assertEqual(execution["status"], "incomplete")
        self.assertNotIn("ob_value", execution["outputs_by_obligation"])
        self.assertIn("ob_value", execution["missing_obligation_ids"])
        self.assertTrue(
            {"direct_result_unit_mismatch", "empty_direct_rendering"}
            <= {item["code"] for item in execution["validation"]["errors"]}
        )

    def test_blank_display_contract_uses_only_source_visible_units(self) -> None:
        obligation = _obligation(
            "ob_value",
            "direct_value",
            "reported carrying amount",
        )
        unitless = _candidate(
            "cand-unitless",
            1294367,
            raw_unit="",
            normalized_unit="UNKNOWN",
            row_label="reported carrying amount",
        )
        explicit = _candidate(
            "cand-explicit",
            1294367,
            raw_unit="백만원",
            normalized_unit="KRW",
            row_label="reported carrying amount",
        )

        rejected = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-unitless",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[unitless],
            query="Return the reported carrying amount.",
        )
        self.assertEqual(rejected["status"], "incomplete")
        self.assertIn(
            "empty_direct_rendering",
            {item["code"] for item in rejected["validation"]["errors"]},
        )

        accepted = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-explicit",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[explicit],
            query="Return the reported carrying amount.",
        )
        self.assertEqual(accepted["status"], "ok")
        self.assertEqual(
            accepted["outputs_by_obligation"]["ob_value"]["rendered_value"],
            "1294367백만원",
        )

    def test_source_defined_group_remains_one_grounded_narrative_output(self) -> None:
        share = _obligation("ob_share", "direct_value", "target venture share")
        carrying = _obligation(
            "ob_carrying",
            "direct_value",
            "target venture carrying amount",
        )
        summary = _obligation(
            "ob_summary",
            "narrative",
            "target venture source-defined summary",
            evidence_requirements=[
                _requirement(
                    "ob_summary:req_summary",
                    "target venture source-defined summary",
                )
            ],
        )
        share_candidate = _candidate(
            "cand-share",
            25.81,
            raw_unit="%",
            normalized_unit="PERCENT",
            context="explicit-source",
            row_label="target venture share",
        )
        carrying_candidate = _candidate(
            "cand-carrying",
            1294367,
            raw_unit="백만원",
            normalized_unit="KRW",
            context="explicit-source",
            row_label="target venture carrying amount",
        )
        summary_text = (
            "The target venture summary reports continuing loss (803,742) "
            "and total comprehensive loss (791,627), both in 백만원."
        )
        summary_candidate = {
            **_candidate("cand-summary", 0),
            "kind": "narrative",
            "raw_value": "",
            "raw_unit": "",
            "normalized_value": None,
            "normalized_unit": "UNKNOWN",
            "source_text": summary_text,
        }
        execution = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "ob_share", "candidate_id": "cand-share"},
                    {
                        "obligation_id": "ob_carrying",
                        "candidate_id": "cand-carrying",
                    },
                ],
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": ["cand-summary"],
                        "evidence_bindings": [
                            {
                                "candidate_id": "cand-summary",
                                "source_requirement_id": "ob_summary:req_summary",
                            }
                        ],
                        "text": summary_text,
                    }
                ],
            },
            obligations=[share, carrying, summary],
            candidate_catalog=[
                share_candidate,
                carrying_candidate,
                summary_candidate,
            ],
            query="Return the target venture share, carrying amount, and source-defined summary.",
        )

        self.assertEqual(execution["status"], "ok")
        self.assertEqual(set(execution["outputs_by_obligation"]), {
            "ob_share",
            "ob_carrying",
            "ob_summary",
        })
        self.assertIn("(803,742)", execution["answer"])
        self.assertIn("(791,627)", execution["answer"])

    def test_source_defined_group_materializes_one_owned_requirement(self) -> None:
        obligation = AnswerObligation.model_validate(
            {
                "obligation_id": "summary",
                "kind": "narrative",
                "label": "target unit activity summary",
                "evidence_mode": "source_defined_group",
                "scope": {"period": "2024", "segment": "target unit"},
                "retrieval_hints": ["target unit activity summary"],
                "concept_hints": ["activity_overview"],
            }
        )
        self.assertEqual(len(obligation.evidence_requirements), 1)
        requirement = obligation.evidence_requirements[0]
        self.assertTrue(requirement.required)
        self.assertEqual(requirement.label, obligation.label)
        self.assertEqual(requirement.scope, obligation.scope)
        self.assertEqual(requirement.retrieval_hints, obligation.retrieval_hints)
        self.assertEqual(requirement.concept_hints, obligation.concept_hints)
        self.assertIsNot(requirement.scope, obligation.scope)
        self.assertIsNot(requirement.retrieval_hints, obligation.retrieval_hints)
        self.assertEqual(
            AnswerObligation.model_validate(obligation.model_dump()).model_dump(),
            obligation.model_dump(),
        )

    def test_source_defined_mode_is_explicit_in_schema_and_prompts(self) -> None:
        mode = AnswerObligation.model_json_schema()["properties"]["evidence_mode"]
        self.assertEqual(mode["enum"], ["declared_inputs", "source_defined_group"])
        self.assertEqual(mode["default"], "declared_inputs")
        planner = PLANNING_POLICY["requirement_planner_prompt_template"]
        compiler = CALCULATION_PROMPT_POLICY["semantic_program_prompt_template"]
        self.assertIn("evidence_mode를 source_defined_group", planner)
        self.assertIn("evidence_requirements는 비워", planner)
        self.assertIn("같은 질문·회사·보고서에 속한다는 이유만으로 묶지", planner)
        self.assertIn("evidence_mode가 source_defined_group", compiler)
        self.assertIn("구조화된 표의 숫자 셀", compiler)
        self.assertIn("원문에 기재된 항목 이름과 값을 보존", compiler)
        self.assertIn("호환성을 명시하는 narrative candidate ID", compiler)

    def test_source_defined_group_rejects_invented_required_members(self) -> None:
        for labels in (("received items",), ("received items", "processed items")):
            with self.subTest(labels=labels):
                with self.assertRaisesRegex(ValueError, "source-defined group"):
                    AnswerObligation.model_validate(
                        {
                            "kind": "narrative",
                            "label": "target unit activity summary",
                            "evidence_mode": "source_defined_group",
                            "evidence_requirements": [
                                {"label": label} for label in labels
                            ],
                        }
                    )

    def test_source_defined_group_cannot_replace_numeric_inputs(self) -> None:
        for kind in ("direct_value", "derived_value"):
            with self.subTest(kind=kind):
                with self.assertRaisesRegex(ValueError, "source-defined group"):
                    AnswerObligation.model_validate(
                        {
                            "kind": kind,
                            "label": "requested quantity",
                            "evidence_mode": "source_defined_group",
                        }
                    )

    def test_declared_narrative_members_are_not_silently_reinterpreted(self) -> None:
        obligation = AnswerObligation.model_validate(
            {
                "kind": "narrative",
                "label": "target unit activity summary",
                "evidence_requirements": [
                    {"label": "received items"},
                    {"label": "processed items"},
                ],
            }
        )
        self.assertEqual(
            [item.label for item in obligation.evidence_requirements],
            ["received items", "processed items"],
        )

    def test_source_defined_requirement_shape_fails_closed_without_model_parsing(self) -> None:
        obligation = _obligation(
            "ob_summary",
            "narrative",
            "target unit activity summary",
            evidence_mode="source_defined_group",
            evidence_requirements=[
                _requirement("ob_summary:req_001", "target unit activity summary")
            ],
        )
        candidate = {
            **_candidate("cand-summary", 0),
            "kind": "narrative",
            "normalized_value": None,
            "source_text": "The target unit reports active items 41 and total items 57.",
        }
        binding = {
            "obligation_id": "ob_summary",
            "candidate_ids": ["cand-summary"],
            "evidence_bindings": [
                {
                    "candidate_id": "cand-summary",
                    "source_requirement_id": "ob_summary:req_001",
                }
            ],
            "text": candidate["source_text"],
        }
        valid = validate_semantic_calculation_program(
            program={"narrative_bindings": [binding]},
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Summarize the target unit's reported activity.",
        )
        self.assertEqual(valid["status"], "ready")

        requirement = obligation["evidence_requirements"][0]
        for changes in (
            {"evidence_requirements": []},
            {"evidence_requirements": [None]},
            {"evidence_requirements": [{**requirement, "label": "received items"}]},
            {"evidence_requirements": [{**requirement, "required": False}]},
            {"evidence_requirements": [{**requirement, "retrieval_hints": ["processed items"]}]},
            {"evidence_requirements": [{**requirement, "concept_hints": ["processed_items"]}]},
            {"evidence_requirements": [{**requirement, "scope": _scope(period="2023")}]},
            {"kind": "derived_value"},
            {"evidence_mode": "inferred_members"},
        ):
            with self.subTest(changes=changes):
                invalid = execute_semantic_calculation_program(
                    program={"narrative_bindings": [binding]},
                    obligations=[{**obligation, **changes}],
                    candidate_catalog=[candidate],
                    query="Summarize the target unit's reported activity.",
                )
                self.assertNotEqual(invalid["status"], "ok")
                self.assertNotIn("ob_summary", invalid["outputs_by_obligation"])
                self.assertIn("ob_summary", invalid["missing_obligation_ids"])
                self.assertIn(
                    "invalid_evidence_mode" if "evidence_mode" in changes
                    else "invalid_source_defined_group",
                    {item["code"] for item in invalid["validation"]["errors"]},
                )

    def test_source_defined_group_keeps_binding_scope_and_numeric_guards(self) -> None:
        scope = _scope(
            company="sample", period="2024", consolidation_scope="consolidated",
            segment="target unit", basis="gross",
        )
        summary = AnswerObligation.model_validate(
            {
                "obligation_id": "ob_summary", "kind": "narrative",
                "label": "target unit activity summary", "scope": scope,
                "evidence_mode": "source_defined_group",
            }
        ).model_dump()
        summary["evidence_requirements"][0]["requirement_id"] = "ob_summary:req_001"
        narrative = {
            **_candidate("cand-summary", 0, context="activity-table"),
            **scope, "kind": "narrative", "normalized_value": None,
            "raw_value": "", "raw_unit": "", "normalized_unit": "UNKNOWN",
            "source_text": "The target unit reports active items 41 and total items 57.",
        }
        binding = {
            "obligation_id": "ob_summary", "candidate_ids": ["cand-summary"],
            "evidence_bindings": [
                {
                    "candidate_id": "cand-summary",
                    "source_requirement_id": "ob_summary:req_001",
                }
            ],
            "text": narrative["source_text"],
        }
        obligations = [
            _obligation("ob_capacity", "direct_value", "capacity"), summary,
        ]

        def execute(binding_changes=None, candidate_changes=None):
            return execute_semantic_calculation_program(
                program={
                    "direct_bindings": [
                        {"obligation_id": "ob_capacity", "candidate_id": "cand-capacity"}
                    ],
                    "narrative_bindings": [{**binding, **(binding_changes or {})}],
                },
                obligations=obligations,
                candidate_catalog=[
                    _candidate("cand-capacity", 84, context="capacity-table"),
                    {**narrative, **(candidate_changes or {})},
                ],
                query="Return capacity and summarize the target unit's reported activity.",
            )

        self.assertEqual(execute()["status"], "ok")
        for binding_changes, candidate_changes, expected_code in (
            ({"evidence_bindings": []}, {}, "missing_required_evidence_binding"),
            (
                {"evidence_bindings": [{
                    "candidate_id": "cand-summary",
                    "source_requirement_id": "ob_summary:req_invented",
                }]}, {}, "unknown_narrative_requirement",
            ),
            ({"candidate_ids": ["cand-unregistered"]}, {}, "unknown_narrative_candidate"),
            ({"text": "The target unit reports active items 42."}, {}, "ungrounded_narrative_number"),
            *(
                ({"scope_applicability_fields": ["segment", "basis", "consolidation_scope"]},
                 {field: value}, "candidate_scope_mismatch")
                for field, value in (
                    ("company", "other"), ("period", "2023"),
                    ("consolidation_scope", "separate"), ("segment", "other unit"),
                    ("basis", "net"),
                )
            ),
        ):
            with self.subTest(binding=binding_changes, candidate=candidate_changes):
                result = execute(binding_changes, candidate_changes)
                self.assertEqual(result["status"], "partial")
                self.assertEqual(set(result["outputs_by_obligation"]), {"ob_capacity"})
                self.assertEqual(result["missing_obligation_ids"], ["ob_summary"])
                self.assertIn(
                    expected_code,
                    {item["code"] for item in result["validation"]["errors"]},
                )

    def test_independent_direct_outputs_do_not_require_shared_table_context(self) -> None:
        obligations = [
            _obligation("ob_capacity", "direct_value", "target unit capacity"),
            _obligation("ob_share", "direct_value", "target unit allocation share"),
        ]
        catalog = [
            _candidate("cand-capacity", 84, context="capacity-table"),
            _candidate(
                "cand-share", 13.2, raw_unit="%", normalized_unit="PERCENT",
                context="allocation-table",
            ),
        ]
        program = {
            "direct_bindings": [
                {"obligation_id": "ob_capacity", "candidate_id": "cand-capacity"},
                {"obligation_id": "ob_share", "candidate_id": "cand-share"},
            ]
        }
        independent = validate_semantic_calculation_program(
            program=program, obligations=obligations, candidate_catalog=catalog,
            query="Return the target unit's reported capacity and allocation share.",
        )
        self.assertEqual(independent["status"], "ready")
        incorrectly_coupled = validate_semantic_calculation_program(
            program=program,
            obligations=[{**item, "coupling_key": "same-question"} for item in obligations],
            candidate_catalog=catalog,
            query="Return the target unit's reported capacity and allocation share.",
        )
        self.assertEqual(incorrectly_coupled["status"], "invalid")
        self.assertEqual(
            {item["code"] for item in incorrectly_coupled["errors"]},
            {"coupled_context_mismatch"},
        )
        for changes, expected_code in (
            ({"scope": _scope(period="2023")}, "candidate_scope_mismatch"),
            ({"display_unit": "%"}, "direct_result_unit_mismatch"),
        ):
            with self.subTest(changes=changes):
                result = execute_semantic_calculation_program(
                    program=program,
                    obligations=[{**obligations[0], **changes}, obligations[1]],
                    candidate_catalog=catalog,
                    query="Return capacity and allocation share.",
                )
                self.assertEqual(result["status"], "partial")
                self.assertEqual(set(result["outputs_by_obligation"]), {"ob_share"})
                self.assertIn(
                    expected_code,
                    {item["code"] for item in result["validation"]["errors"]},
                )

    def test_coupled_direct_outputs_keep_explicit_compatibility_boundary(self) -> None:
        obligations = [
            _obligation("ob_total", "direct_value", "total", coupling_key="composition"),
            _obligation("ob_share", "direct_value", "share", coupling_key="composition"),
        ]
        total = {
            **_candidate("cand-total", 84, context="total-table"),
            "source_anchor": "[sample | 2024 | total-table]",
        }
        share = {
            **_candidate(
                "cand-share", 13.2, raw_unit="%", normalized_unit="PERCENT",
                context="share-table",
            ),
            "source_anchor": "[sample | 2024 | share-table]",
        }
        witness = {
            **_candidate("cand-basis", 0, context="total-table"),
            "kind": "narrative", "normalized_value": None,
            "source_anchor": "[sample | 2024 | basis-note]",
            "source_text": "The allocation share uses the total in this table as its denominator.",
        }
        for share_context, witness_changes, witness_ids, expected_code in (
            ("total-table", {}, [], ""),
            ("share-table", {}, [], "coupled_context_mismatch"),
            ("share-table", {}, ["cand-basis"], ""),
            ("share-table", {}, ["cand-missing"], "invalid_compatibility_candidate"),
            ("share-table", {"source_text": ""}, ["cand-basis"], "invalid_compatibility_candidate"),
            (
                "share-table",
                {"context_fingerprint": "unrelated-note", "table_source_id": "unrelated-note"},
                ["cand-basis"], "direct_compatibility_context_mismatch",
            ),
        ):
            with self.subTest(context=share_context, witness=witness_changes, ids=witness_ids):
                result = validate_semantic_calculation_program(
                    program={
                        "direct_bindings": [
                            {
                                "obligation_id": "ob_total", "candidate_id": "cand-total",
                                "compatibility_candidate_ids": witness_ids,
                            },
                            {"obligation_id": "ob_share", "candidate_id": "cand-share"},
                        ]
                    },
                    obligations=obligations,
                    candidate_catalog=[
                        total,
                        {**share, "context_fingerprint": share_context, "table_source_id": share_context},
                        {**witness, **witness_changes},
                    ],
                    query="Return the total and allocation share on the same basis.",
                )
                if expected_code:
                    self.assertNotEqual(result["status"], "ready")
                    self.assertIn(expected_code, {item["code"] for item in result["errors"]})
                else:
                    self.assertEqual(result["status"], "ready")

    def test_direct_binding_scope_gap_requires_colocated_compatibility_evidence(self) -> None:
        obligation = _obligation(
            "ob_value",
            "direct_value",
            "consolidated value",
            scope=_scope(
                company="sample",
                period="2023",
                consolidation_scope="consolidated",
            ),
        )
        numeric = {
            **_candidate("cand-value", 30, period="2023", context="table-a"),
            "company": "sample",
            "year": 2023,
            "consolidation_scope": "unknown",
            "evidence_id": "shared-evidence",
        }
        witness = {
            **_candidate("cand-scope", 0, period="", context="note-a"),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "normalized_unit": "UNKNOWN",
            "company": "sample",
            "year": 2023,
            "consolidation_scope": "unknown",
            "evidence_id": "shared-evidence",
            "source_text": "The note explicitly states that the table is consolidated.",
        }
        rejected = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "ob_value", "candidate_id": "cand-value"}
                ],
            },
            obligations=[obligation],
            candidate_catalog=[numeric, witness],
            query="Return the 2023 consolidated value.",
        )
        self.assertEqual(rejected["status"], "invalid")

        accepted = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-value",
                        "compatibility_candidate_ids": ["cand-scope"],
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[numeric, witness],
            query="Return the 2023 consolidated value.",
        )
        self.assertEqual(accepted["status"], "ok")
        self.assertEqual(
            accepted["outputs_by_obligation"]["ob_value"]["candidate_ids"],
            ["cand-value", "cand-scope"],
        )

        explicit_conflict = {**numeric, "consolidation_scope": "separate"}
        still_rejected = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-value",
                        "compatibility_candidate_ids": ["cand-scope"],
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[explicit_conflict, witness],
            query="Return the 2023 consolidated value.",
        )
        self.assertEqual(still_rejected["status"], "invalid")

    def test_coupled_outputs_require_source_context(self) -> None:
        obligations = [
            _obligation("ob_total", "direct_value", "total", coupling_key="mix"),
            _obligation("ob_share", "direct_value", "share", coupling_key="mix"),
        ]
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "ob_total", "candidate_id": "cand-total"},
                    {"obligation_id": "ob_share", "candidate_id": "cand-share"},
                ],
            },
            obligations=obligations,
            candidate_catalog=[
                _candidate("cand-total", 100, context=""),
                _candidate("cand-share", 25, context="table-a"),
            ],
            query="Return the total and share from the same basis.",
        )
        self.assertEqual(validation["status"], "invalid")
        self.assertEqual(
            {item["code"] for item in validation["errors"]},
            {"coupled_context_missing"},
        )

    def test_unregistered_constant_and_unit_mismatch_fail_closed(self) -> None:
        obligations = [_obligation("ob_result", "derived_value", "result", display_unit="개")]
        catalog = [
            _candidate("cand-count", 10),
            _candidate("cand-money", 20, raw_unit="백만원", normalized_unit="KRW"),
        ]
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_result",
                        "variable_bindings": [
                            {"variable": "A", "source_id": "cand-count"},
                            {"variable": "B", "source_id": "cand-money"},
                        ],
                        "formula": "A + B + 7",
                        "result_unit": "개",
                        "constants": [],
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Add the two values.",
        )
        codes = {item["code"] for item in validation["errors"]}
        self.assertIn("undeclared_formula_constant", codes)
        self.assertEqual(validation["status"], "invalid")

    def test_negative_neutral_magnitude_is_not_an_implicit_constant(self) -> None:
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_result",
                        "variable_bindings": [
                            {"variable": "A", "source_id": "cand-count"}
                        ],
                        "formula": "A + -1",
                        "result_unit": "개",
                        "constants": [],
                    }
                ],
            },
            obligations=[
                _obligation(
                    "ob_result",
                    "derived_value",
                    "adjusted count",
                    display_unit="개",
                )
            ],
            candidate_catalog=[_candidate("cand-count", 10, raw_unit="개")],
            query="Return the adjusted count.",
        )
        self.assertIn(
            "undeclared_formula_constant",
            {item["code"] for item in validation["errors"]},
        )

    def test_cardinality_constant_and_generic_min_max_are_supported(self) -> None:
        obligations = [
            _obligation(
                "ob_average",
                "derived_value",
                "average",
                display_unit="개",
                evidence_requirements=[
                    _requirement("ob_average:req_a", "first value"),
                    _requirement("ob_average:req_b", "second value"),
                ],
            )
        ]
        catalog = [_candidate("cand-a", 10), _candidate("cand-b", 20)]
        program = {
            "status": "ready",
            "expressions": [
                {
                    "obligation_id": "ob_average",
                    "variable_bindings": [
                        _binding("A", "cand-a", "ob_average:req_a"),
                        _binding("B", "cand-b", "ob_average:req_b"),
                    ],
                    "formula": "(min(A, B) + max(A, B)) / 2",
                    "result_unit": "개",
                    "constants": [
                        {"value": 2, "origin": "deterministic_cardinality", "source_text": "two inputs"}
                    ],
                }
            ],
        }
        execution = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the average.",
        )
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(execution["outputs_by_obligation"]["ob_average"]["normalized_value"], 15.0)

    def test_missing_required_obligation_is_partial_even_when_other_output_is_valid(self) -> None:
        obligations = [
            _obligation("ob_value", "direct_value", "value"),
            _obligation("ob_missing", "narrative", "explanation"),
        ]
        catalog = [_candidate("cand-value", 10)]
        execution = execute_semantic_calculation_program(
            program={
                "status": "incomplete",
                "direct_bindings": [{"obligation_id": "ob_value", "candidate_id": "cand-value"}],
                "missing_obligation_ids": ["ob_missing"],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return the value and explanation.",
        )
        self.assertEqual(execution["status"], "partial")
        self.assertEqual(execution["missing_obligation_ids"], ["ob_missing"])
        self.assertIn("explanation", execution["answer"])

    def test_narrative_cannot_introduce_unseen_numbers(self) -> None:
        obligations = [_obligation("ob_note", "narrative", "context")]
        narrative = {
            **_candidate("cand-note", 0),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "source_text": "The source states ten units without a numeric display.",
        }
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_note",
                        "candidate_ids": ["cand-note"],
                        "text": "The amount increased by 42 units.",
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=[narrative],
            query="Explain the context.",
        )
        self.assertEqual(validation["status"], "invalid")
        self.assertIn("ungrounded_narrative_number", {item["code"] for item in validation["errors"]})
        self.assertEqual(
            next(
                item["detail"]
                for item in validation["errors"]
                if item["code"] == "ungrounded_narrative_number"
            ),
            "42",
        )

    def test_semantic_prompts_require_relation_grounded_narrative_evidence(self) -> None:
        planner_prompt = str(
            PLANNING_POLICY.get("requirement_planner_prompt_template") or ""
        )
        compiler_prompt = str(
            CALCULATION_PROMPT_POLICY.get("semantic_program_prompt_template") or ""
        )

        self.assertIn("narrative obligation", planner_prompt)
        self.assertIn("evidence_requirements", planner_prompt)
        self.assertIn("source schema", planner_prompt)
        self.assertIn("표준 항목을 추정", planner_prompt)
        self.assertIn("인과", compiler_prompt)
        self.assertIn("직접 연결", compiler_prompt)
        self.assertIn("일반적 맥락", compiler_prompt)
        self.assertIn("required evidence_requirements", compiler_prompt)
        self.assertIn("variable binding의 scope_applicability_fields", compiler_prompt)

    def test_narrative_candidates_may_ground_scope_collectively(self) -> None:
        obligation = _obligation(
            "ob_note",
            "narrative",
            "acquisition effect",
            scope=_scope(
                company="sample",
                period="2023",
                consolidation_scope="consolidated",
                segment="commerce",
            ),
        )
        scoped = {
            **_candidate("cand-scoped", 0),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "company": "sample",
            "year": 2023,
            "consolidation_scope": "consolidated",
            "segment": "commerce",
            "source_text": "The commerce result includes the acquisition effect.",
        }
        context = {
            **_candidate("cand-context", 0),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "company": "sample",
            "year": 2023,
            "consolidation_scope": "unknown",
            "segment": "",
            "source_text": "The acquisition expanded the service offering.",
        }
        program = {
            "status": "ready",
            "narrative_bindings": [
                {
                    "obligation_id": "ob_note",
                    "candidate_ids": ["cand-scoped", "cand-context"],
                    "text": "The acquisition expanded the commerce service offering.",
                }
            ],
        }
        accepted = validate_semantic_calculation_program(
            program=program,
            obligations=[obligation],
            candidate_catalog=[scoped, context],
            query="Explain the 2023 consolidated commerce acquisition effect.",
        )
        self.assertEqual(accepted["status"], "ready")

        conflicting = {**context, "segment": "another segment"}
        rejected = validate_semantic_calculation_program(
            program=program,
            obligations=[obligation],
            candidate_catalog=[scoped, conflicting],
            query="Explain the 2023 consolidated commerce acquisition effect.",
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "candidate_scope_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

    def test_narrative_scope_applicability_bridges_only_unknown_soft_scope_fields(self) -> None:
        expected_scope = _scope(
            company="sample",
            period="2024",
            consolidation_scope="consolidated",
            segment="commerce",
            basis="reported basis",
        )
        obligation = _obligation(
            "ob_note",
            "narrative",
            "reported relationship",
            scope=expected_scope,
            evidence_requirements=[
                {
                    **_requirement("ob_note:req_relation", "direct relationship"),
                    "scope": expected_scope,
                }
            ],
        )
        candidate = {
            **_candidate("cand-relation", 0, period="2024"),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "company": "sample",
            "year": 2024,
            "consolidation_scope": "unknown",
            "segment": "",
            "basis": "",
            "source_text": "The selected evidence directly states the requested relationship.",
        }
        base_binding = {
            "obligation_id": "ob_note",
            "candidate_ids": ["cand-relation"],
            "evidence_bindings": [
                {
                    "candidate_id": "cand-relation",
                    "source_requirement_id": "ob_note:req_relation",
                }
            ],
            "text": "The evidence directly states the requested relationship.",
        }

        rejected = validate_semantic_calculation_program(
            program={"status": "ready", "narrative_bindings": [base_binding]},
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Explain the 2024 consolidated commerce relationship.",
        )
        self.assertEqual(rejected["status"], "invalid")

        accepted = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        **base_binding,
                        "scope_applicability_fields": [
                            "consolidation_scope",
                            "segment",
                            "basis",
                        ],
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Explain the 2024 consolidated commerce relationship.",
        )
        self.assertEqual(accepted["status"], "ready")

        conflicting = {**candidate, "consolidation_scope": "separate"}
        conflict = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        **base_binding,
                        "scope_applicability_fields": ["consolidation_scope"],
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[conflicting],
            query="Explain the 2024 consolidated commerce relationship.",
        )
        self.assertEqual(conflict["status"], "invalid")

        invalid_field = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        **base_binding,
                        "scope_applicability_fields": ["company"],
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Explain the 2024 consolidated commerce relationship.",
        )
        self.assertIn(
            "invalid_scope_applicability_field",
            {item["code"] for item in invalid_field["errors"]},
        )

    def test_narrative_evidence_requirements_need_explicit_candidate_bindings(self) -> None:
        obligation = _obligation(
            "ob_note",
            "narrative",
            "reported change explanation",
            evidence_requirements=[
                _requirement(
                    "ob_note:req_relation",
                    "factor directly connected to the reported change",
                    period="2024",
                )
            ],
        )
        candidate = {
            **_candidate("cand-relation", 0, period="2024"),
            "kind": "narrative",
            "raw_value": "",
            "normalized_value": None,
            "source_text": "The source directly connects the scenario to the reported change.",
        }
        base_binding = {
            "obligation_id": "ob_note",
            "candidate_ids": ["cand-relation"],
            "text": "The scenario explains the reported change.",
        }

        missing = validate_semantic_calculation_program(
            program={"status": "ready", "narrative_bindings": [base_binding]},
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Explain why the reported result changed.",
        )
        self.assertEqual(missing["status"], "invalid")
        self.assertIn(
            "missing_required_evidence_binding",
            {item["code"] for item in missing["errors"]},
        )

        ready = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        **base_binding,
                        "evidence_bindings": [
                            {
                                "candidate_id": "cand-relation",
                                "source_requirement_id": "ob_note:req_relation",
                            }
                        ],
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Explain why the reported result changed.",
        )
        self.assertEqual(ready["status"], "ready")

    def test_cagr_and_time_series_outputs_share_the_restricted_program(self) -> None:
        obligations = [
            _obligation("start", "direct_value", "start", scope=_scope(period="2021")),
            _obligation("end", "direct_value", "end", scope=_scope(period="2024")),
            _obligation("cagr", "derived_value", "three-year CAGR", display_unit="%"),
            _obligation(
                "change_1",
                "derived_value",
                "first interval",
                display_unit="%",
                evidence_requirements=[
                    _requirement("change_1:req_start", "start", period="2021"),
                    _requirement("change_1:req_mid", "mid", period="2022"),
                ],
            ),
            _obligation(
                "change_2",
                "derived_value",
                "second interval",
                display_unit="%",
                evidence_requirements=[
                    _requirement("change_2:req_mid", "mid", period="2022"),
                    _requirement("change_2:req_next", "next", period="2023"),
                ],
            ),
        ]
        candidates = [
            _candidate("c_start", 100, period="2021"),
            _candidate("c_mid", 110, period="2022"),
            _candidate("c_next", 121, period="2023"),
            _candidate("c_end", 133.1, period="2024"),
        ]
        program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "start", "candidate_id": "c_start"},
                {"obligation_id": "end", "candidate_id": "c_end"},
            ],
            "expressions": [
                {
                    "obligation_id": "cagr",
                    "variable_bindings": [
                        {"variable": "START", "source_id": "start"},
                        {"variable": "END", "source_id": "end"},
                    ],
                    "formula": "((END / START) ** (1 / 3) - 1) * 100",
                    "result_unit": "%",
                    "constants": [{"value": 3, "origin": "query", "source_text": "3 years"}],
                },
                {
                    "obligation_id": "change_1",
                    "variable_bindings": [
                        _binding("PREV", "c_start", "change_1:req_start"),
                        _binding("CURR", "c_mid", "change_1:req_mid"),
                    ],
                    "formula": "((CURR - PREV) / PREV) * 100",
                    "result_unit": "%",
                },
                {
                    "obligation_id": "change_2",
                    "variable_bindings": [
                        _binding("PREV", "c_mid", "change_2:req_mid"),
                        _binding("CURR", "c_next", "change_2:req_next"),
                    ],
                    "formula": "((CURR - PREV) / PREV) * 100",
                    "result_unit": "%",
                },
            ],
        }
        result = execute_semantic_calculation_program(
            program=program,
            obligations=obligations,
            candidate_catalog=candidates,
            query="Return the CAGR over 3 years and the interval changes.",
        )
        self.assertEqual(result["status"], "ok")
        outputs = result["outputs_by_obligation"]
        self.assertAlmostEqual(outputs["cagr"]["normalized_value"], 10.0, places=8)
        self.assertAlmostEqual(outputs["change_1"]["normalized_value"], 10.0, places=8)
        self.assertAlmostEqual(outputs["change_2"]["normalized_value"], 10.0, places=8)

    def test_cycle_missing_candidate_and_zero_division_fail_closed(self) -> None:
        obligations = [
            _obligation("a", "derived_value", "a", display_unit="%"),
            _obligation("b", "derived_value", "b", display_unit="%"),
        ]
        cycle = {
            "status": "ready",
            "expressions": [
                {
                    "obligation_id": "a",
                    "variable_bindings": [{"variable": "B", "source_id": "b"}],
                    "formula": "B * 100",
                    "result_unit": "%",
                },
                {
                    "obligation_id": "b",
                    "variable_bindings": [{"variable": "A", "source_id": "a"}],
                    "formula": "A * 100",
                    "result_unit": "%",
                },
            ],
        }
        validation = validate_semantic_calculation_program(
            program=cycle,
            obligations=obligations,
            candidate_catalog=[],
            query="return both values",
        )
        self.assertEqual(validation["status"], "invalid")
        self.assertIn(
            "cyclic_or_unresolved_expression_dependency",
            {item["code"] for item in validation["errors"]},
        )

        missing = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [{"obligation_id": "value", "candidate_id": "not_registered"}],
            },
            obligations=[_obligation("value", "direct_value", "value")],
            candidate_catalog=[],
            query="return value",
        )
        self.assertEqual(missing["status"], "invalid")
        self.assertIn("unknown_or_nonnumeric_candidate", {item["code"] for item in missing["errors"]})

        hidden = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "value", "candidate_id": "hidden"}
                ],
            },
            obligations=[_obligation("value", "direct_value", "value")],
            candidate_catalog=[_candidate("visible", 10), _candidate("hidden", 20)],
            selectable_candidate_ids=["visible"],
            query="return value",
        )
        self.assertEqual(hidden["status"], "invalid")
        self.assertIn(
            "candidate_not_exposed_to_compiler",
            {item["code"] for item in hidden["errors"]},
        )

        zero_division = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ratio",
                        "variable_bindings": [
                            _binding("A", "c_a", "ratio:req_numerator"),
                            _binding("B", "c_zero", "ratio:req_denominator"),
                        ],
                        "formula": "(A / B) * 100",
                        "result_unit": "%",
                    }
                ],
            },
            obligations=[
                _obligation(
                    "ratio",
                    "derived_value",
                    "ratio",
                    display_unit="%",
                    evidence_requirements=[
                        _requirement("ratio:req_numerator", "numerator"),
                        _requirement("ratio:req_denominator", "denominator"),
                    ],
                )
            ],
            candidate_catalog=[_candidate("c_a", 10), _candidate("c_zero", 0)],
            query="return ratio",
        )
        self.assertEqual(zero_division["status"], "incomplete")
        self.assertIn("zero_division", {item["code"] for item in zero_division["execution_errors"]})

    def test_source_display_scope_and_llm_value_injection_are_rejected(self) -> None:
        obligations = [
            _obligation(
                "ratio",
                "derived_value",
                "ratio",
                display_unit="%",
                scope=_scope(period="2024"),
                evidence_requirements=[
                    _requirement("ratio:req_part", "part", period="2024"),
                    _requirement("ratio:req_total", "total", period="2024"),
                ],
            )
        ]
        candidates = [
            _candidate("part", 10, period="2024"),
            _candidate("total", 100, period="2024"),
            _candidate("stated", 10, raw_unit="%", normalized_unit="PERCENT", period="2023"),
        ]
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ratio",
                        "variable_bindings": [
                            _binding("PART", "part", "ratio:req_part"),
                            _binding("TOTAL", "total", "ratio:req_total"),
                        ],
                        "formula": "(PART / TOTAL) * 100",
                        "result_unit": "%",
                        "source_display_candidate_id": "stated",
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=candidates,
            query="return the 2024 ratio",
        )
        self.assertEqual(validation["status"], "invalid")
        self.assertIn("source_display_scope_mismatch", {item["code"] for item in validation["errors"]})

        with self.assertRaises(Exception):
            SemanticCalculationProgram.model_validate(
                {
                    "status": "ready",
                    "direct_bindings": [
                        {
                            "obligation_id": "ratio",
                            "candidate_id": "part",
                            "normalized_value": 999,
                        }
                    ],
                }
            )

    def test_program_output_kind_and_candidate_values_fail_closed(self) -> None:
        catalog = [
            _candidate("finite", 10),
            {**_candidate("not-finite", 10), "normalized_value": float("inf")},
        ]
        direct_for_derived = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "derived", "candidate_id": "finite"}
                ],
            },
            obligations=[_obligation("derived", "derived_value", "derived")],
            candidate_catalog=catalog,
            query="derive the value",
        )
        self.assertIn(
            "non_direct_obligation_has_direct_binding",
            {item["code"] for item in direct_for_derived["errors"]},
        )

        expression_for_direct = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "direct",
                        "variable_bindings": [
                            {"variable": "A", "source_id": "finite"}
                        ],
                        "formula": "A",
                    }
                ],
            },
            obligations=[_obligation("direct", "direct_value", "direct")],
            candidate_catalog=catalog,
            query="return the direct value",
        )
        self.assertIn(
            "non_derived_obligation_has_expression",
            {item["code"] for item in expression_for_direct["errors"]},
        )

        non_finite = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "direct", "candidate_id": "not-finite"}
                ],
            },
            obligations=[_obligation("direct", "direct_value", "direct")],
            candidate_catalog=catalog,
            query="return the direct value",
        )
        self.assertIn(
            "unknown_or_nonnumeric_candidate",
            {item["code"] for item in non_finite["errors"]},
        )

        non_finite_display = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ratio",
                        "variable_bindings": [
                            _binding("A", "finite", "ratio:req_a"),
                            _binding("B", "finite-two", "ratio:req_b"),
                        ],
                        "formula": "(A / B) * 100",
                        "result_unit": "%",
                        "source_display_candidate_id": "not-finite-display",
                    }
                ],
            },
            obligations=[
                _obligation(
                    "ratio",
                    "derived_value",
                    "ratio",
                    display_unit="%",
                    evidence_requirements=[
                        _requirement("ratio:req_a", "first value"),
                        _requirement("ratio:req_b", "second value"),
                    ],
                )
            ],
            candidate_catalog=[
                _candidate("finite", 10),
                _candidate("finite-two", 20),
                {
                    **_candidate(
                        "not-finite-display",
                        50,
                        raw_unit="%",
                        normalized_unit="PERCENT",
                    ),
                    "normalized_value": float("nan"),
                },
            ],
            query="return the ratio",
        )
        self.assertIn(
            "invalid_source_display_candidate",
            {item["code"] for item in non_finite_display["errors"]},
        )

    def test_generic_allowed_functions_execute_without_a_recipe(self) -> None:
        result = execute_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "value",
                        "variable_bindings": [
                            _binding("A", "c_a", "value:req_a"),
                            _binding("B", "c_b", "value:req_b"),
                        ],
                        "formula": "round(exp(log(abs(A / B))), 1)",
                        "result_unit": "",
                        "constants": [
                            {"value": 1, "origin": "deterministic_cardinality", "source_text": "one binding"}
                        ],
                    }
                ],
            },
            obligations=[
                _obligation(
                    "value",
                    "derived_value",
                    "value",
                    evidence_requirements=[
                        _requirement("value:req_a", "first value"),
                        _requirement("value:req_b", "second value"),
                    ],
                )
            ],
            candidate_catalog=[_candidate("c_a", -12.34), _candidate("c_b", 1)],
            query="return the transformed value",
        )
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["outputs_by_obligation"]["value"]["normalized_value"], 12.3)

    def test_operation_family_is_derived_from_formula_only(self) -> None:
        self.assertEqual(derive_operation_family_from_formula("A"), "lookup")
        self.assertEqual(derive_operation_family_from_formula("A + B + C"), "sum")
        self.assertEqual(derive_operation_family_from_formula("A - B"), "difference")
        self.assertEqual(derive_operation_family_from_formula("(A / B) * 100"), "ratio")
        self.assertEqual(derive_operation_family_from_formula("((A - B) / B) * 100"), "growth_rate")
        self.assertEqual(derive_operation_family_from_formula("max(A, B)"), "formula")

    def test_narrative_output_does_not_force_same_table_context_as_numeric_output(self) -> None:
        numeric = _candidate(
            "numeric",
            10,
            raw_unit="",
            normalized_unit="UNKNOWN",
            context="table-a",
        )
        narrative = {
            **_candidate("narrative", 0, context="paragraph-b"),
            "kind": "narrative",
            "normalized_value": None,
            "source_text": "The acquisition expanded the service offering.",
        }
        result = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "value",
                        "variable_bindings": [
                            _binding("A", "numeric", "value:req_numeric")
                        ],
                        "formula": "A",
                    }
                ],
                "narrative_bindings": [
                    {
                        "obligation_id": "context",
                        "candidate_ids": ["narrative"],
                        "text": "The acquisition expanded the service offering.",
                    }
                ],
            },
            obligations=[
                _obligation(
                    "value",
                    "derived_value",
                    "value",
                    coupling_key="combined-answer",
                    evidence_requirements=[
                        _requirement("value:req_numeric", "numeric value")
                    ],
                ),
                _obligation(
                    "context",
                    "narrative",
                    "context",
                    coupling_key="combined-answer",
                ),
            ],
            candidate_catalog=[numeric, narrative],
            query="Return the value and explain the acquisition.",
        )
        self.assertEqual(result["status"], "ready")

    def test_compatibility_candidate_authorizes_cross_context_coupled_formula(self) -> None:
        first = _candidate(
            "first",
            100,
            context="table-a",
        )
        second = _candidate(
            "second",
            20,
            context="table-b",
        )
        compatibility = {
            **_candidate("compatibility", 0, context="note-c"),
            "kind": "narrative",
            "normalized_value": None,
            "source_text": "The second amount is included in the first amount.",
        }
        result = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {"obligation_id": "first_value", "candidate_id": "first"},
                    {"obligation_id": "second_value", "candidate_id": "second"},
                ],
                "expressions": [
                    {
                        "obligation_id": "difference",
                        "variable_bindings": [
                            {"variable": "A", "source_id": "first_value"},
                            {"variable": "B", "source_id": "second_value"},
                        ],
                        "formula": "A - B",
                        "result_unit": "개",
                        "compatibility_candidate_ids": ["compatibility"],
                    }
                ],
            },
            obligations=[
                _obligation(
                    "first_value",
                    "direct_value",
                    "first",
                    coupling_key="shared-result",
                ),
                _obligation(
                    "second_value",
                    "direct_value",
                    "second",
                    coupling_key="shared-result",
                ),
                _obligation(
                    "difference",
                    "derived_value",
                    "difference",
                    coupling_key="shared-result",
                    depends_on=["first_value", "second_value"],
                ),
            ],
            candidate_catalog=[first, second, compatibility],
            query="Subtract the included second amount from the first amount.",
        )
        self.assertEqual(result["status"], "ready")


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


class SemanticCalculationProgramGraphTests(unittest.TestCase):
    def _agent(self, llm):
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        agent.llm_routes = {}
        agent.llm_usage_callback = None
        return agent

    def test_source_defined_summary_survives_planning_compilation_and_execution(self) -> None:
        planner_response = RequirementPlannerOutput.model_validate(
            {
                "topic": "target unit profile",
                "obligations": [
                    {
                        "kind": "direct_value", "label": "target unit capacity",
                        "scope": {"segment": "target unit"},
                    },
                    {
                        "kind": "direct_value", "label": "target unit allocation share",
                        "scope": {"segment": "target unit"},
                    },
                    {
                        "kind": "narrative", "label": "target unit activity summary",
                        "scope": {"segment": "target unit"},
                        "evidence_mode": "source_defined_group",
                        "retrieval_hints": ["target unit activity summary"],
                    },
                ],
            }
        )
        summary_text = "The target unit reports active items 41 and total items 57."
        compiler_responses = [
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {
                            "obligation_id": "ob_001",
                            "candidate_id": "cand-capacity",
                        }
                    ]
                }
            ),
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {
                            "obligation_id": "ob_002",
                            "candidate_id": "cand-share",
                        }
                    ]
                }
            ),
            SemanticCalculationProgram.model_validate(
                {
                    "narrative_bindings": [
                        {
                            "obligation_id": "ob_003",
                            "candidate_ids": ["cand-summary"],
                            "evidence_bindings": [
                                {
                                    "candidate_id": "cand-summary",
                                    "source_requirement_id": "ob_003:req_001",
                                }
                            ],
                            "text": summary_text,
                        }
                    ]
                }
            ),
        ]
        llm = _StructuredQueueLLM(planner_response, *compiler_responses)
        agent = self._agent(llm)
        initial_state = {
            "query": "Return the target unit's capacity, allocation share, and source-defined activity summary.",
            "query_type": "numeric_fact", "intent": "numeric_fact",
            "format_preference": "mixed", "topic": "target unit profile",
            "report_scope": {"company": "sample", "year": 2024},
            "companies": [], "years": [], "tasks": [], "artifacts": [],
            "plan_loop_count": 0,
        }
        planned = agent._plan_answer_obligation_program(initial_state)
        self.assertEqual(len(planned["calc_subtasks"]), 1)
        obligations = planned["answer_obligations"]
        self.assertEqual([item["coupling_key"] for item in obligations], ["", "", ""])
        summary = obligations[2]
        self.assertEqual(summary["evidence_mode"], "source_defined_group")
        self.assertEqual(len(summary["evidence_requirements"]), 1)
        requirement = summary["evidence_requirements"][0]
        self.assertEqual(requirement["requirement_id"], "ob_003:req_001")
        self.assertEqual(requirement["label"], summary["label"])
        self.assertEqual(requirement["scope"], summary["scope"])
        self.assertEqual(AnswerObligation.model_validate(summary).model_dump(), summary)
        task = planned["calc_subtasks"][0]
        self.assertEqual(
            [item["role"] for item in task["required_evidence"]],
            ["ob_001", "ob_002", "ob_003:req_001"],
        )
        self.assertEqual(task["required_evidence"][2]["label"], summary["label"])
        catalog = [
            {
                **_candidate(
                    "cand-capacity", 84, row_label="target unit",
                    context="capacity-table", period="2024",
                ),
                "company": "sample",
            },
            {
                **_candidate(
                    "cand-share", 13.2, raw_unit="%", normalized_unit="PERCENT",
                    row_label="target unit", context="allocation-table", period="2024",
                ),
                "company": "sample",
            },
            {
                **_candidate("cand-summary", 0, context="activity-table"),
                "company": "sample", "kind": "narrative",
                "normalized_value": None, "source_text": summary_text,
            },
        ]
        state = {
            **initial_state, **planned, "active_subtask": task,
            "evidence_items": [], "retrieved_docs": [], "seed_retrieved_docs": [],
            "planner_debug_trace": {}, "resolved_calculation_trace": {},
        }
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(
            llm.models,
            ["RequirementPlannerOutput", *["SemanticCalculationProgram"] * 3],
        )
        self.assertEqual(len(llm.prompts), 4)
        self.assertIn('"evidence_mode": "source_defined_group"', str(llm.prompts[3]))
        self.assertIn('"requirement_id": "ob_003:req_001"', str(llm.prompts[3]))
        compile_validation_bytes = json.dumps(
            compiled["semantic_program_validation"],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        executed = agent._execute_semantic_calculation_program({**state, **compiled})
        self.assertNotIn("semantic_program_validation", executed)
        self.assertEqual(
            json.dumps(
                compiled["semantic_program_validation"],
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8"),
            compile_validation_bytes,
        )
        self.assertEqual(executed["structured_result"]["status"], "ok")
        self.assertIn(summary_text, executed["answer"])
        trace = executed["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_result"]["semantic_status"], "ok")
        self.assertEqual(trace["calculation_result"]["derived_metrics"]["missing_obligation_ids"], [])
        self.assertEqual(len(trace["calculation_result"]["outputs"]), 3)
        self.assertEqual(
            trace["calculation_plan"]["answer_obligations"][2]["evidence_mode"],
            "source_defined_group",
        )

    def test_requirement_planner_emits_one_program_task_and_stable_obligations(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "companies": [],
                "years": [2024],
                "topic": "quantity movement and context",
                "obligations": [
                    {
                        "obligation_id": "closing",
                        "kind": "direct_value",
                        "label": "closing quantity",
                        "scope": {"period": "2024"},
                        "retrieval_hints": ["closing quantity"],
                    },
                    {
                        "obligation_id": "change",
                        "kind": "derived_value",
                        "label": "change rate",
                        "display_unit": "%",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": "consolidated",
                            "segment": "service",
                            "basis": "gross",
                        },
                        "depends_on": ["closing"],
                        "retrieval_hints": ["opening quantity", "closing quantity"],
                        "evidence_requirements": [
                            {
                                "requirement_id": "opening-input",
                                "label": "opening quantity",
                                "scope": {"period": "2023"},
                                "retrieval_hints": ["opening quantity"],
                            }
                        ],
                    },
                    {
                        "obligation_id": "context",
                        "kind": "narrative",
                        "label": "context",
                        "evidence_requirements": [
                            {
                                "requirement_id": "context-relation",
                                "label": "reported change explanation",
                                "retrieval_hints": ["reported change explanation"],
                            }
                        ],
                    },
                ],
                "retrieval_queries": ["quantity table", "quantity context"],
            }
        )
        llm = _StructuredQueueLLM(response)
        agent = self._agent(llm)
        result = agent._plan_answer_obligation_program(
            {
                "query": "Return the closing quantity, its change rate, and explain the context.",
                "query_type": "comparison",
                "intent": "comparison",
                "topic": "quantity movement",
                "report_scope": {"year": 2024},
                "companies": [],
                "years": [2024],
                "tasks": [],
                "artifacts": [],
                "plan_loop_count": 0,
            }
        )
        self.assertEqual(llm.models, ["RequirementPlannerOutput"])
        self.assertEqual(result["planned_metric_families"], ["semantic_program"])
        self.assertEqual(len(result["calc_subtasks"]), 1)
        task = result["calc_subtasks"][0]
        self.assertNotIn("operation_family", task)
        self.assertEqual(len(task["required_evidence"]), 3)
        self.assertEqual(
            [item["obligation_id"] for item in result["answer_obligations"]],
            ["ob_001", "ob_002", "ob_003"],
        )
        self.assertEqual(result["answer_obligations"][1]["depends_on"], ["ob_001"])
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0][
                "requirement_id"
            ],
            "ob_002:req_001",
        )
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0]["scope"][
                "period"
            ],
            "2023",
        )
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0]["scope"],
            {
                "company": "",
                "period": "2023",
                "consolidation_scope": "unknown",
                "segment": "service",
                "basis": "gross",
            },
        )
        self.assertEqual(
            result["answer_obligations"][1]["scope"]["consolidation_scope"],
            "unknown",
        )
        self.assertEqual(
            task["constraints"]["consolidation_scope"],
            "unknown",
        )
        self.assertEqual(
            [item["role"] for item in task["required_evidence"]],
            ["ob_001", "ob_002:req_001", "ob_003:req_001"],
        )
        self.assertTrue(result["semantic_plan"]["program_required"])

    def test_mixed_format_uses_requirement_program_even_when_router_intent_is_narrative(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                    },
                    {
                        "obligation_id": "context",
                        "kind": "narrative",
                        "label": "reported context",
                    },
                ]
            }
        )
        llm = _StructuredQueueLLM(response)
        agent = self._agent(llm)

        result = agent._plan_answer_obligation_program(
            {
                "query": "Return the value and explain its context.",
                "query_type": "risk",
                "intent": "risk",
                "format_preference": "mixed",
                "topic": "value and context",
                "report_scope": {},
                "companies": [],
                "years": [],
                "tasks": [],
                "artifacts": [],
                "plan_loop_count": 0,
            }
        )

        self.assertEqual(llm.models, ["RequirementPlannerOutput"])
        self.assertTrue(result["semantic_plan"]["program_required"])
        self.assertEqual(len(result["answer_obligations"]), 2)

    def test_requirement_planner_bounds_runaway_coupling_key(self) -> None:
        oversized = "shared-context-" * 1000
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                        "coupling_key": oversized,
                    }
                ]
            }
        )

        self.assertLessEqual(len(response.obligations[0].coupling_key), 128)
        self.assertNotEqual(response.obligations[0].coupling_key, oversized)

    def test_requirement_planner_uses_authoritative_company_and_removes_scope_placeholders(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                        "scope": {
                            "company": "alternate spelling",
                            "period": "2024",
                            "segment": "report_scope",
                            "basis": "report_scope",
                        },
                    }
                ]
            }
        )
        agent = self._agent(_StructuredQueueLLM(response))
        result = agent._build_llm_requirement_plan(
            query="Return the 2024 reported value.",
            topic="reported value",
            intent="numeric_fact",
            report_scope={"company": "Canonical Company", "year": 2024},
        )
        scope = result["answer_obligations"][0]["scope"]
        self.assertEqual(scope["company"], "Canonical Company")
        self.assertEqual(scope["period"], "2024")
        self.assertEqual(scope["segment"], "")
        self.assertEqual(scope["basis"], "")

    def test_requirement_planner_uses_source_report_company_for_candidate_identity(self) -> None:
        response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "value",
                        "kind": "direct_value",
                        "label": "reported value",
                        "scope": {"company": "display spelling", "period": "2024"},
                    }
                ]
            }
        )
        agent = self._agent(_StructuredQueueLLM(response))
        result = agent._build_llm_requirement_plan(
            query="Return the 2024 reported value.",
            topic="reported value",
            intent="numeric_fact",
            report_scope={
                "company": "Display Company",
                "year": 2024,
                "source_reports": [
                    {"corp_name": "Source Company", "year": 2024, "rcept_no": "receipt-1"}
                ],
            },
        )
        self.assertEqual(
            result["answer_obligations"][0]["scope"]["company"],
            "Source Company",
        )
        self.assertEqual(result["companies"][:2], ["Source Company", "Display Company"])

    def test_requirement_planner_rejects_hard_scope_without_query_provenance(self) -> None:
        fixture = _contract_residual_fixture()["scope_provenance"][
            "implicit_query"
        ]
        response = RequirementPlannerOutput.model_validate(
            {"obligations": fixture["planner_obligations"]}
        )
        agent = self._agent(_StructuredQueueLLM(response))

        result = agent._build_llm_requirement_plan(
            query=fixture["query"],
            topic="target venture results",
            intent="numeric_fact",
            report_scope=fixture["report_scope"],
        )

        self.assertEqual(
            [
                item["scope"]["consolidation_scope"]
                for item in result["answer_obligations"]
            ],
            fixture["expected_obligation_scopes"],
        )
        self.assertEqual(
            result["answer_obligations"][1]["evidence_requirements"][0][
                "scope"
            ]["consolidation_scope"],
            fixture["expected_requirement_scope"],
        )
        self.assertEqual(
            result["tasks"][0]["constraints"]["consolidation_scope"],
            fixture["expected_task_scope"],
        )
        self.assertIn(
            "report_scope의 문서 metadata",
            str(PLANNING_POLICY.get("requirement_planner_prompt_template") or ""),
        )

    def test_requirement_planner_uses_only_query_explicit_hard_scope(self) -> None:
        fixture = _contract_residual_fixture()["scope_provenance"]
        single = fixture["single_explicit_query"]
        single_response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": "share",
                        "kind": "direct_value",
                        "label": "target venture ownership share",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": single["planner_scope"],
                            "segment": "target venture",
                        },
                        "evidence_requirements": [
                            {
                                "requirement_id": "share-input",
                                "label": "target venture reported share",
                                "scope": {
                                    "period": "2024",
                                    "consolidation_scope": "unknown",
                                    "segment": "target venture",
                                },
                            }
                        ],
                    }
                ]
            }
        )
        single_result = self._agent(
            _StructuredQueueLLM(single_response)
        )._build_llm_requirement_plan(
            query=single["query"],
            topic="target venture ownership share",
            intent="numeric_fact",
            report_scope=single["report_scope"],
        )
        self.assertEqual(
            single_result["answer_obligations"][0]["scope"][
                "consolidation_scope"
            ],
            single["expected_scope"],
        )
        self.assertEqual(
            single_result["answer_obligations"][0][
                "evidence_requirements"
            ][0]["scope"]["consolidation_scope"],
            single["expected_scope"],
        )

        multiple = fixture["multiple_explicit_query"]
        multiple_response = RequirementPlannerOutput.model_validate(
            {
                "obligations": [
                    {
                        "obligation_id": f"share-{index}",
                        "kind": "direct_value",
                        "label": f"target venture ownership share {index}",
                        "scope": {
                            "period": "2024",
                            "consolidation_scope": scope,
                            "segment": "target venture",
                        },
                    }
                    for index, scope in enumerate(
                        multiple["planner_scopes"],
                        start=1,
                    )
                ]
            }
        )
        multiple_result = self._agent(
            _StructuredQueueLLM(multiple_response)
        )._build_llm_requirement_plan(
            query=multiple["query"],
            topic="target venture ownership share",
            intent="numeric_fact",
            report_scope={"year": 2024},
        )
        self.assertEqual(
            [
                item["scope"]["consolidation_scope"]
                for item in multiple_result["answer_obligations"]
            ],
            multiple["expected_scopes"],
        )
        self.assertEqual(
            multiple_result["tasks"][0]["constraints"][
                "consolidation_scope"
            ],
            multiple["expected_task_scope"],
        )

    def test_program_prompt_projection_is_bounded_by_candidate_kind(self) -> None:
        agent = self._agent(_StructuredQueueLLM())
        numeric = [
            {**_candidate(f"numeric-{index}", index + 1), "source_text": "n" * 1000}
            for index in range(110)
        ]
        narrative = [
            {
                **_candidate(f"narrative-{index}", 0),
                "kind": "narrative",
                "normalized_value": None,
                "source_text": "x" * 1000,
            }
            for index in range(40)
        ]
        rows = agent._semantic_program_prompt_rows([*numeric, *narrative])
        self.assertEqual(
            [sum(item["kind"] == kind for item in rows) for kind in ("numeric", "narrative")],
            [96, 32],
        )
        self.assertTrue(
            all(
                len(item["source_text"]) <= (420 if item["kind"] == "numeric" else 600)
                for item in rows
            )
        )

    def test_compiler_and_executor_use_candidate_ids_and_project_canonical_trace(self) -> None:
        source_candidates = [
            {
                "candidate_id": "chunk-1::value:0",
                "source_anchor": "[sample | 2024 | section]",
                "text": "opening and closing quantity",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "quantity",
                    "table_source_id": "table-a",
                    "year": 2024,
                    "structured_cells": [
                        {"column_headers": ["opening"], "value_text": "343", "unit_hint": "개"},
                        {"column_headers": ["closing"], "value_text": "380", "unit_hint": "개"},
                    ],
                },
            }
        ]
        catalog = build_semantic_candidate_catalog(source_candidates)
        numeric = [item for item in catalog if item["kind"] == "numeric"]
        opening_id, closing_id = [item["candidate_id"] for item in numeric]
        invalid_response = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_001",
                        "variable_bindings": [
                            _binding(
                                "CLOSING_VALUE",
                                closing_id,
                                "ob_001:req_closing",
                            ),
                            _binding(
                                "OPENING_VALUE",
                                opening_id,
                                "ob_001:req_opening",
                            ),
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                    }
                ],
            }
        )
        response = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_001",
                        "variable_bindings": [
                            _binding("CURR", closing_id, "ob_001:req_closing"),
                            _binding("PREV", opening_id, "ob_001:req_opening"),
                        ],
                        "formula": "((CURR - PREV) / PREV) * 100",
                        "result_unit": "%",
                    }
                ],
            }
        )
        llm = _StructuredQueueLLM(invalid_response, response)
        agent = self._agent(llm)
        obligations = [
            _obligation(
                "ob_001",
                "derived_value",
                "change rate",
                display_unit="%",
                evidence_requirements=[
                    _requirement("ob_001:req_closing", "closing quantity"),
                    _requirement("ob_001:req_opening", "opening quantity"),
                ],
            )
        ]
        state = {
            "query": "What percent did the quantity increase from opening to closing?",
            "query_type": "comparison",
            "intent": "comparison",
            "topic": "quantity",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {"program_required": True, "answer_obligations": obligations},
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "change rate",
                "query": "What percent did the quantity increase from opening to closing?",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(llm.models, ["SemanticCalculationProgram"])
        self.assertIn('"year": 2024', str(llm.prompts[0]))
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(llm.prompts), 2)
        retry_prompt = str(llm.prompts[1])
        self.assertIn("allowed_candidate_ids", retry_prompt)
        self.assertIn(opening_id, retry_prompt)
        self.assertIn(closing_id, retry_prompt)
        self.assertIn("declared_evidence_requirement_ids", retry_prompt)
        self.assertIn("ob_001:req_opening", retry_prompt)
        self.assertIn("ob_001:req_closing", retry_prompt)
        self.assertIn("repair_contract", retry_prompt)
        self.assertIn("evidence_requirement_ids_by_obligation", retry_prompt)
        self.assertIn("formula_variable_binding_invariant", retry_prompt)
        self.assertIn("exactly equal", retry_prompt)
        trace = compiled["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_plan"]["program_mode"], "semantic_program")
        self.assertEqual(
            trace["calculation_plan"]["prompt_candidate_strategy"],
            "compilation_islands_v1",
        )
        stage_diagnostics = trace["calculation_plan"]["candidate_stage_diagnostics"]
        self.assertEqual(
            stage_diagnostics["schema"],
            "semantic_candidate_stage_diagnostics_v3",
        )
        self.assertEqual(stage_diagnostics["catalog_candidate_count"], 2)
        self.assertEqual(stage_diagnostics["prompt_candidate_count"], 2)
        self.assertEqual(len(trace["calculation_operands"]), 2)
        merged = {**state, **compiled}
        executed = agent._execute_semantic_calculation_program(merged)
        executed_trace = executed["resolved_calculation_trace"]
        self.assertEqual(executed_trace["calculation_result"]["semantic_status"], "ok")
        self.assertAlmostEqual(executed_trace["calculation_result"]["result_value"], (380 - 343) / 343 * 100)
        self.assertEqual(
            executed_trace["calculation_plan"]["operation_family"],
            "growth_rate",
        )
        self.assertEqual(
            executed_trace["calculation_result"]["operation_family"],
            "growth_rate",
        )
        self.assertEqual(executed["structured_result"]["status"], "ok")
        self.assertEqual(len(executed["structured_result"]["subtask_results"]), 1)
        output_result = executed["structured_result"]["subtask_results"][0][
            "calculation_result"
        ]
        self.assertEqual(output_result["operation_family"], "growth_rate")
        self.assertEqual(output_result["answer_slots"]["operation_family"], "single_value")
        self.assertEqual(
            validate_answer_slots_payload(output_result["answer_slots"])[
                "operation_family"
            ],
            "single_value",
        )
        self.assertIn("change rate", executed["answer"])
        artifact_kinds = [item.get("kind") for item in executed["artifacts"]]
        self.assertIn("operand_set", artifact_kinds)
        self.assertIn("calculation_plan", artifact_kinds)
        self.assertIn("calculation_result", artifact_kinds)

    def test_retry_replaces_rejected_candidate_and_omits_valid_output(self) -> None:
        valid = {
            **_candidate(
                "cand-valid",
                10,
                raw_unit="%",
                normalized_unit="PERCENT",
            ),
            "candidate_kind": "structured_row",
            "row_headers": ["valid output"],
        }
        bad_candidates = [
            {
                **_candidate(
                    f"cand-bad-{index}",
                    20 + index,
                    raw_unit="%",
                    normalized_unit="PERCENT",
                ),
                "candidate_kind": "sentence_value",
                "row_label": "reported share",
                "row_headers": [],
                "local_entity_surfaces": [],
                "source_text": f"A generic note reports {20 + index}%.",
            }
            for index in range(1, 5)
        ]
        promoted = {
            **_candidate(
                "cand-promoted",
                26,
                raw_unit="%",
                normalized_unit="PERCENT",
            ),
            "candidate_kind": "structured_row",
            "row_label": "ownership share",
            "row_headers": ["target entity"],
            "local_entity_surfaces": ["ownership share", "target entity"],
        }
        catalog = [valid, *bad_candidates, promoted]
        obligations = [
            _obligation(
                "ob_valid",
                "direct_value",
                "valid output",
                display_unit="%",
            ),
            _obligation(
                "ob_retry",
                "direct_value",
                "target ownership share",
                display_unit="%",
                scope=_scope(segment="target entity"),
            ),
        ]
        first_program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_valid", "candidate_id": "cand-valid"},
                {"obligation_id": "ob_retry", "candidate_id": "cand-bad-1"},
            ],
        }
        retry_program = {
            "status": "ready",
            "direct_bindings": [
                {
                    "obligation_id": "ob_retry",
                    "candidate_id": "cand-promoted",
                }
            ],
        }
        first_model = SemanticCalculationProgram.model_validate(first_program)
        accepted_first_island = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_valid",
                        "candidate_id": "cand-valid",
                    }
                ],
            }
        )
        llm = _StructuredQueueLLM(
            accepted_first_island,
            SemanticCalculationProgram.model_validate(
                {
                    "status": "ready",
                    "direct_bindings": [
                        {
                            "obligation_id": "ob_retry",
                            "candidate_id": "cand-bad-1",
                        }
                    ],
                }
            ),
            SemanticCalculationProgram.model_validate(retry_program),
        )
        agent = self._agent(llm)
        state = {
            "query": "Return the valid output and the target entity ownership share.",
            "query_type": "multi_metric",
            "intent": "multi_metric",
            "topic": "ownership share",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "two outputs",
                "query": "Return both outputs.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        initial_cohorts = _semantic_candidate_cohorts(catalog, obligations)
        first_validation = validate_semantic_calculation_program(
            program=first_model.model_dump(),
            obligations=obligations,
            candidate_catalog=catalog,
            query=state["query"],
            selectable_candidate_ids_by_owner=initial_cohorts[
                "candidate_ids_by_owner"
            ],
        )
        preserved_before = json.dumps(
            accepted_first_island.model_dump()["direct_bindings"][0],
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(llm.prompts), 3)
        first_prompt = str(llm.prompts[1])
        retry_prompt = str(llm.prompts[2])
        self.assertNotIn("cand-bad-4", first_prompt)
        self.assertIn("cand-bad-4", retry_prompt)
        self.assertNotIn("cand-bad-1", retry_prompt)
        self.assertNotIn('"obligation_id": "ob_valid"', retry_prompt)
        final_valid = next(
            item
            for item in compiled["semantic_program"]["direct_bindings"]
            if item["obligation_id"] == "ob_valid"
        )
        preserved_after = json.dumps(
            final_valid,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        self.assertEqual(preserved_after, preserved_before)
        attempts = compiled["resolved_calculation_trace"]["calculation_plan"][
            "candidate_stage_diagnostics"
        ]["attempts"]
        attempts = [
            item for item in attempts if item["island_id"] == "island_002"
        ]
        self.assertEqual(len(attempts), 2)
        self.assertNotEqual(
            attempts[1]["visible_candidate_id_fingerprint"],
            attempts[0]["visible_candidate_id_fingerprint"],
        )

    def test_retry_excludes_only_the_candidate_role_that_failed(self) -> None:
        program = {
            "direct_bindings": [
                {
                    "obligation_id": "ob_direct",
                    "candidate_id": "cand-primary",
                    "compatibility_candidate_ids": ["cand-witness"],
                }
            ]
        }

        primary_exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "candidate_scope_mismatch",
                    "obligation_id": "ob_direct",
                    "detail": "period",
                }
            ],
            target_obligation_ids=["ob_direct"],
        )
        witness_exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "compatibility_scope_mismatch",
                    "obligation_id": "ob_direct",
                    "detail": "consolidation_scope",
                }
            ],
            target_obligation_ids=["ob_direct"],
        )

        self.assertEqual(primary_exclusions, {"ob_direct": ["cand-primary"]})
        self.assertEqual(witness_exclusions, {"ob_direct": ["cand-witness"]})

    def test_retry_keeps_same_cohort_for_context_field_mismatch(self) -> None:
        program = {
            "expressions": [
                {
                    "obligation_id": "ob_mix",
                    "variable_bindings": [
                        _binding("A", "cand-a", "ob_mix:req_a"),
                        _binding("B", "cand-b", "ob_mix:req_b"),
                    ],
                }
            ]
        }

        exclusions = _retry_candidate_exclusions(
            program=program,
            validation_errors=[
                {
                    "code": "expression_context_mismatch",
                    "obligation_id": "ob_mix",
                    "detail": "context_fingerprint",
                }
            ],
            target_obligation_ids=["ob_mix"],
        )

        self.assertEqual(exclusions, {})

    def test_structural_context_retry_reuses_identical_candidate_payload(self) -> None:
        obligations = [
            _obligation(
                "ob_mix",
                "derived_value",
                "same-period difference",
                display_unit="개",
                scope=_scope(period="2024"),
                evidence_requirements=[
                    _requirement("ob_mix:req_a", "first amount", period="2024"),
                    _requirement("ob_mix:req_b", "second amount", period="2024"),
                ],
            )
        ]
        catalog = [
            _candidate(
                "cand-a",
                30,
                raw_unit="개",
                period="2024",
                context="statement-context",
                row_label="first amount",
            ),
            _candidate(
                "cand-b",
                20,
                raw_unit="개",
                period="2024",
                context="note-context",
                row_label="second amount",
            ),
        ]
        first_program = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "expressions": [
                    {
                        "obligation_id": "ob_mix",
                        "variable_bindings": [
                            _binding("A", "cand-a", "ob_mix:req_a"),
                            _binding("B", "cand-b", "ob_mix:req_b"),
                        ],
                        "formula": "A - B",
                        "result_unit": "개",
                    }
                ],
            }
        )
        retry_program = SemanticCalculationProgram.model_validate(
            {
                "status": "ambiguous",
                "ambiguous_obligation_ids": ["ob_mix"],
                "rationale": "The disclosed contexts are not explicitly compatible.",
            }
        )
        llm = _StructuredQueueLLM(first_program, retry_program)
        agent = self._agent(llm)
        state = {
            "query": "Subtract the second amount from the first amount.",
            "query_type": "comparison",
            "intent": "comparison",
            "topic": "same-period difference",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "same-period difference",
                "query": "Subtract the second amount from the first amount.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        attempts = compiled["resolved_calculation_trace"]["calculation_plan"][
            "candidate_stage_diagnostics"
        ]["attempts"]
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(
            attempts[0]["visible_candidate_ids"],
            attempts[1]["visible_candidate_ids"],
        )
        self.assertEqual(
            attempts[0]["visible_candidate_id_fingerprint"],
            attempts[1]["visible_candidate_id_fingerprint"],
        )
        self.assertEqual(
            attempts[0]["serialized_candidate_bytes"],
            attempts[1]["serialized_candidate_bytes"],
        )

    def test_source_and_formula_displays_survive_graph_trace_ledger_and_numeric_evaluation(self) -> None:
        from src.agent.financial_task_artifacts import project_task_artifact_trace
        from src.ops.evaluator import EvalExample, RAGEvaluator

        fixture = _source_display_program_fixture()
        llm = _StructuredQueueLLM(SemanticCalculationProgram.model_validate(fixture["program"]))
        agent = self._agent(llm)
        state = {
            "query": fixture["query"], "query_type": "comparison", "intent": "comparison",
            "topic": "quantity", "format_preference": "table", "report_scope": {},
            "answer_obligations": fixture["obligations"],
            "semantic_plan": {"program_required": True, "answer_obligations": fixture["obligations"]},
            "active_subtask": {
                "task_id": "task_1", "metric_family": "semantic_program",
                "metric_label": "quantity change", "query": fixture["query"],
            },
            "tasks": [], "artifacts": [], "evidence_items": [],
            "retrieved_docs": [], "seed_retrieved_docs": [],
            "planner_debug_trace": {}, "resolved_calculation_trace": {},
        }
        with patch.object(
            agent, "_semantic_candidate_catalog_for_state", return_value=fixture["candidate_catalog"],
        ):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(llm.models, ["SemanticCalculationProgram"])
        self.assertEqual(len(llm.prompts), 1)
        executed = agent._execute_semantic_calculation_program({**state, **compiled})
        self.assertEqual(executed["structured_result"]["status"], "ok")
        self.assertIn("calculated 10% (source-stated 10.2%)", executed["answer"])
        trace = executed["resolved_calculation_trace"]
        calculation_result = trace["calculation_result"]
        output = calculation_result["outputs"][0]
        self.assertEqual(output["formula_rendered_value"], "10%")
        self.assertEqual(output["source_display_value"], "10.2%")
        self.assertFalse(output["source_display_matches_formula"])
        self.assertEqual(calculation_result["derived_metrics"]["semantic_outputs"], [output])
        self.assertEqual(
            executed["structured_result"]["resolved_calculation_trace"]["calculation_result"]["outputs"],
            [output],
        )
        self.assertEqual(
            validate_answer_slots_payload(calculation_result["answer_slots"])["primary_value"]["normalized_value"],
            10.0,
        )
        self.assertIn("cand-stated", executed["selected_claim_ids"])
        source_evidence = next(item for item in executed["evidence_items"] if item["evidence_id"] == "cand-stated")
        self.assertEqual(source_evidence["raw_value"], "10.2")
        citations = agent._format_citations({**state, **compiled, **executed})["citations"]
        self.assertTrue(any("source note" in citation for citation in citations))
        ledger = project_task_artifact_trace(executed["tasks"], executed["artifacts"])
        self.assertEqual(ledger["integrity_status"], "ok")

        runtime_result = {**state, **compiled, **executed, "citations": citations}
        evaluator = RAGEvaluator(
            SimpleNamespace(run=lambda *_args, **_kwargs: runtime_result), skip_llm_judges=True,
        )
        evaluation = evaluator.evaluate_one(EvalExample(
            id="generic-source-display", question=fixture["query"], ground_truth="10%",
            company="sample", year=2024, section="activity", answer_type="numeric",
            expected_calculation_result={"normalized_value": 10.0, "normalized_unit": "PERCENT", "tolerance": 0.0},
        ))
        self.assertIsNone(evaluation.error)
        self.assertEqual(evaluation.numeric_result_correctness, 1.0)
        self.assertEqual(evaluation.grounded_rendering_correctness, 1.0)
        self.assertEqual(evaluation.calculation_correctness, 1.0)
        self.assertIsNone(evaluation.raw_faithfulness)

    def test_program_compiler_retries_once_for_missing_obligation(self) -> None:
        source_candidates = [
            {
                "candidate_id": "chunk-1::value:0",
                "source_anchor": "[sample | 2024 | section]",
                "text": "quantity 10",
                "candidate_kind": "structured_value",
                "metadata": {
                    "row_label": "quantity",
                    "table_source_id": "table-a",
                    "structured_cells": [
                        {"column_headers": ["current"], "value_text": "10", "unit_hint": "개"},
                    ],
                },
            }
        ]
        candidate_id = next(
            item["candidate_id"]
            for item in build_semantic_candidate_catalog(source_candidates)
            if item["kind"] == "numeric"
        )
        first = SemanticCalculationProgram.model_validate(
            {"status": "incomplete", "missing_obligation_ids": ["ob_001"]}
        )
        second = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [{"obligation_id": "ob_001", "candidate_id": candidate_id}],
            }
        )
        llm = _StructuredQueueLLM(first, second)
        agent = self._agent(llm)
        obligations = [_obligation("ob_001", "direct_value", "quantity", display_unit="개")]
        state = {
            "query": "Return the quantity.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "quantity",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {"program_required": True, "answer_obligations": obligations},
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "quantity",
                "query": "Return the quantity.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        catalog = build_semantic_candidate_catalog(source_candidates)
        with patch.object(agent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertIn("missing_obligation_ids", str(llm.prompts[1]))
        history = compiled["resolved_calculation_trace"]["calculation_plan"][
            "program_validation_history"
        ]
        self.assertEqual([item["attempt"] for item in history], [1, 2])
        self.assertEqual([item["status"] for item in history], ["invalid", "ready"])
        self.assertEqual(
            compiled["resolved_calculation_trace"]["calculation_plan"][
                "program_retry_count"
            ],
            1,
        )

    def test_independent_island_cannot_rebind_an_accepted_obligation(self) -> None:
        catalog = [
            _candidate("cand-first", 10),
            _candidate("cand-missing", 20),
            _candidate("cand-replacement", 999),
        ]
        first = SemanticCalculationProgram.model_validate(
            {
                "status": "incomplete",
                "direct_bindings": [
                    {"obligation_id": "ob_001", "candidate_id": "cand-first"}
                ],
                "missing_obligation_ids": ["ob_002"],
            }
        )
        second = SemanticCalculationProgram.model_validate(
            {
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_001",
                        "candidate_id": "cand-replacement",
                    },
                    {
                        "obligation_id": "ob_002",
                        "candidate_id": "cand-missing",
                    },
                ],
            }
        )
        llm = _StructuredQueueLLM(first, second)
        agent = self._agent(llm)
        obligations = [
            _obligation("ob_001", "direct_value", "first"),
            _obligation("ob_002", "direct_value", "second"),
        ]
        state = {
            "query": "Return both values.",
            "query_type": "numeric_fact",
            "intent": "numeric_fact",
            "topic": "values",
            "report_scope": {},
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {
                "task_id": "task_1",
                "metric_family": "semantic_program",
                "metric_label": "values",
                "query": "Return both values.",
            },
            "tasks": [],
            "artifacts": [],
            "evidence_items": [],
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
            "planner_debug_trace": {},
            "resolved_calculation_trace": {},
        }
        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        bindings = {
            item["obligation_id"]: item["candidate_id"]
            for item in compiled["semantic_program"]["direct_bindings"]
        }
        self.assertEqual(
            bindings,
            {"ob_001": "cand-first", "ob_002": "cand-missing"},
        )
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertEqual(len(llm.prompts), 2)
        second_island_prompt = str(llm.prompts[1])
        self.assertIn("ob_002", second_island_prompt)
        self.assertNotIn(
            '"obligation_id": "ob_001"',
            second_island_prompt.split("Candidate catalog:", 1)[0],
        )

    def test_compilation_islands_follow_only_dependency_and_coupling_edges(self) -> None:
        obligations = [
            _obligation("ob_a", "direct_value", "a"),
            _obligation(
                "ob_b",
                "direct_value",
                "b",
                depends_on=["ob_a"],
            ),
            _obligation(
                "ob_c",
                "direct_value",
                "c",
                coupling_key="shared",
            ),
            _obligation(
                "ob_d",
                "direct_value",
                "d",
                coupling_key="shared",
            ),
            _obligation("ob_e", "direct_value", "e"),
        ]

        plan = build_semantic_compilation_islands(obligations)

        self.assertEqual(plan["status"], "ok")
        self.assertEqual(
            [item["obligation_ids"] for item in plan["islands"]],
            [["ob_a", "ob_b"], ["ob_c", "ob_d"], ["ob_e"]],
        )

    def test_invalid_dependency_islands_fail_before_any_compiler_call(self) -> None:
        obligations = [
            _obligation(
                "ob_a",
                "direct_value",
                "a",
                depends_on=["missing"],
            ),
            _obligation(
                "ob_b",
                "direct_value",
                "b",
                depends_on=["ob_b"],
            ),
            _obligation(
                "ob_c",
                "direct_value",
                "c",
                depends_on=["ob_d"],
            ),
            _obligation(
                "ob_d",
                "direct_value",
                "d",
                depends_on=["ob_c"],
            ),
        ]
        agent = self._agent(_StructuredQueueLLM())
        state = {
            "query": "Return the declared values.",
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {"task_id": "task_1"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
        }

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=[],
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        self.assertEqual(agent.llm.prompts, [])
        diagnostics = compiled["resolved_calculation_trace"][
            "calculation_plan"
        ]["candidate_stage_diagnostics"]
        self.assertEqual(diagnostics["compiler_call_count"], 0)
        self.assertEqual(
            {
                error["code"]
                for island in diagnostics["islands"]
                for error in island["preflight_errors"]
            },
            {"unknown_dependency", "self_dependency", "dependency_cycle"},
        )

    def test_island_and_global_reservation_limits_fail_before_calls(self) -> None:
        scenarios = {
            "island_limit": [
                _obligation(f"ob_{index}", "direct_value", f"value {index}")
                for index in range(9)
            ],
            "candidate_reservation": [
                _obligation(
                    f"ob_{index}",
                    "derived_value",
                    f"value {index}",
                    coupling_key="shared",
                    evidence_requirements=[
                        _requirement(
                            f"ob_{index}:req_{requirement}",
                            f"input {requirement}",
                        )
                        for requirement in range(3)
                    ],
                )
                for index in range(7)
            ],
        }
        for scenario, obligations in scenarios.items():
            with self.subTest(scenario=scenario):
                agent = self._agent(_StructuredQueueLLM())
                state = {
                    "query": "Return all declared values.",
                    "answer_obligations": obligations,
                    "semantic_plan": {
                        "program_required": True,
                        "answer_obligations": obligations,
                    },
                    "active_subtask": {"task_id": "task_1"},
                    "tasks": [],
                    "artifacts": [],
                    "resolved_calculation_trace": {},
                }
                with patch.object(
                    agent,
                    "_semantic_candidate_catalog_for_state",
                    return_value=[],
                ):
                    compiled = agent._compile_semantic_calculation_program(
                        state
                    )
                diagnostics = compiled["resolved_calculation_trace"][
                    "calculation_plan"
                ]["candidate_stage_diagnostics"]
                self.assertEqual(agent.llm.prompts, [])
                self.assertEqual(diagnostics["compiler_call_count"], 0)
                self.assertEqual(
                    compiled["semantic_program_validation"]["status"],
                    "invalid",
                )

    def test_independent_island_prompts_have_separate_candidate_authority(self) -> None:
        obligations = [
            _obligation(
                "ob_a",
                "direct_value",
                "alpha value",
                scope=_scope(segment="alpha"),
            ),
            _obligation(
                "ob_b",
                "direct_value",
                "beta value",
                scope=_scope(segment="beta"),
            ),
        ]
        catalog = [
            {**_candidate("cand-a", 10, row_label="alpha value"), "segment": "alpha"},
            {**_candidate("cand-b", 20, row_label="beta value"), "segment": "beta"},
        ]
        llm = _StructuredQueueLLM(
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {"obligation_id": "ob_a", "candidate_id": "cand-a"}
                    ]
                }
            ),
            SemanticCalculationProgram.model_validate(
                {
                    "direct_bindings": [
                        {"obligation_id": "ob_b", "candidate_id": "cand-b"}
                    ]
                }
            ),
        )
        agent = self._agent(llm)
        state = {
            "query": "Return alpha and beta values.",
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {"task_id": "task_1"},
            "tasks": [],
            "artifacts": [],
            "resolved_calculation_trace": {},
        }

        with patch.object(
            agent,
            "_semantic_candidate_catalog_for_state",
            return_value=catalog,
        ):
            compiled = agent._compile_semantic_calculation_program(state)

        self.assertEqual(len(llm.prompts), 2)
        self.assertIn("cand-a", str(llm.prompts[0]))
        self.assertNotIn("cand-b", str(llm.prompts[0]))
        self.assertIn("cand-b", str(llm.prompts[1]))
        self.assertNotIn("cand-a", str(llm.prompts[1]))
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")

    def test_graph_routes_program_path_without_operation_family_branching(self) -> None:
        agent = self._agent(_StructuredQueueLLM())
        state = {
            "semantic_plan": {"program_required": True},
            "active_subtask": {"operation_family": "ratio"},
            "intent": "comparison",
            "retrieved_docs": [],
            "seed_retrieved_docs": [],
        }
        self.assertEqual(agent._route_after_expand(state), "program_compiler")
        self.assertEqual(
            agent._route_after_expand({"semantic_plan": {"program_required": False}}),
            "evidence",
        )
        self.assertEqual(
            agent._route_after_retrieval_v2(
                {"requirements": {"semantic_plan": {"program_required": True}}}
            ),
            "build_candidates",
        )

    def test_graph_dag_contains_only_canonical_numeric_program_nodes(self) -> None:
        agent = self._agent(_StructuredQueueLLM())
        graph = agent._build_graph().get_graph()
        nodes = set(graph.nodes)
        self.assertTrue(
            {
                "route_request",
                "plan_requirements",
                "retrieve_evidence",
                "build_candidates",
                "compile_program",
                "execute_numeric",
                "build_narrative",
                "assemble_ledger",
                "assemble_final",
            }.issubset(nodes)
        )
        self.assertTrue(
            {
                "operand_extractor",
                "formula_planner",
                "calculator",
                "aggregate",
                "reflection",
                "reconcile",
            }.isdisjoint(nodes)
        )

    def test_graph_phase_keys_have_exactly_one_declared_writer(self) -> None:
        self.assertEqual(
            set(FINANCIAL_GRAPH_PHASE_WRITERS),
            {
                "request",
                "routing",
                "requirements",
                "retrieval",
                "candidates",
                "compilation",
                "numeric_result",
                "narrative_result",
                "ledger",
                "final_result",
            },
        )
        self.assertEqual(
            len(set(FINANCIAL_GRAPH_PHASE_WRITERS.values())),
            len(FINANCIAL_GRAPH_PHASE_WRITERS),
        )


if __name__ == "__main__":
    unittest.main()
