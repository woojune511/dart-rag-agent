from __future__ import annotations

from tests.semantic_program_test_support import *

from src.agent.financial_graph_calculation import (
    _semantic_candidate_visibility,
)
from src.agent.financial_runtime_contracts import CompilationEnvelopeV1


def _bundle_obligation(
    obligation_id: str,
    metric: str,
    *,
    kind: str = "direct_value",
    evidence_mode: str = "declared_inputs",
    consolidation_scope: str = "consolidated",
) -> dict:
    label = f"Target Entity {metric}"
    scope = _scope(
        company="sample",
        period="2024",
        consolidation_scope=consolidation_scope,
    )
    semantic_target = {
        "local_subjects": ["Target Entity"],
        "concept_keys": [],
        "metric_surfaces": [metric],
    }
    return _obligation(
        obligation_id,
        kind,
        label,
        display_unit="",
        scope=scope,
        semantic_target=semantic_target,
        evidence_mode=evidence_mode,
        evidence_requirements=(
            [
                {
                    **_requirement(
                        f"{obligation_id}:req_001",
                        label,
                        period="2024",
                        company="sample",
                        consolidation_scope=consolidation_scope,
                    ),
                    "semantic_target": semantic_target,
                }
            ]
            if kind == "narrative"
            else []
        ),
    )


def _row_candidate(
    candidate_id: str,
    value: float,
    *,
    metric: str,
    table_id: str,
    row_id: str = "row-target",
    consolidation_scope: str = "consolidated",
) -> dict:
    candidate = _candidate(
        candidate_id,
        value,
        period="2024",
        context=table_id,
        row_label="Target Entity",
    )
    return {
        **candidate,
        "source_row_id": f"{table_id}::{row_id}",
        "physical_table_id": table_id,
        "physical_row_id": row_id,
        "physical_cell_id": f"{row_id}:{metric}",
        "row_headers": ["Target Entity"],
        "local_entity_surfaces": ["Target Entity"],
        "column_headers": [metric],
        "company": "sample",
        "document_company": "sample",
        "consolidation_scope": consolidation_scope,
        "source_text": f"Target Entity {metric} {value} items",
    }


class SemanticEvidenceBundleTests(unittest.TestCase):
    def _fixture(self):
        obligations = [
            _bundle_obligation("ob_alpha", "alpha metric"),
            _bundle_obligation("ob_beta", "beta metric"),
        ]
        catalog = [
            _row_candidate(
                "cand-alpha-a", 10, metric="alpha metric", table_id="table-a"
            ),
            _row_candidate(
                "cand-beta-a", 20, metric="beta metric", table_id="table-a"
            ),
            _row_candidate(
                "cand-alpha-b", 11, metric="alpha metric", table_id="table-b"
            ),
            _row_candidate(
                "cand-beta-b", 21, metric="beta metric", table_id="table-b"
            ),
        ]
        cohort_plan = _semantic_candidate_cohorts(catalog, obligations)
        visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=cohort_plan["visible_candidate_ids"],
            candidate_ids_by_owner=cohort_plan["candidate_ids_by_owner"],
            evidence_bundle_constraints=cohort_plan[
                "evidence_bundle_constraints"
            ],
        )
        return obligations, catalog, cohort_plan, visibility

    @staticmethod
    def _compile(obligations, catalog, *responses):
        llm = _StructuredQueueLLM(
            *(
                SemanticCalculationProgram.model_validate(response)
                for response in responses
            )
        )
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        agent.llm_routes = {}
        agent.llm_usage_callback = None
        state = {
            "query": "Return both Target Entity metrics.",
            "answer_obligations": obligations,
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "active_subtask": {"task_id": "task_1"},
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
        return llm, compiled

    def test_complete_physical_rows_become_atomic_bundle_options(self) -> None:
        obligations, catalog, cohort_plan, visibility = self._fixture()

        self.assertEqual(len(cohort_plan["evidence_bundle_constraints"]), 1)
        constraint = visibility.evidence_bundle_constraints[0]
        self.assertEqual(constraint.owner_ids, ("ob_alpha", "ob_beta"))
        self.assertEqual(
            [option.physical_table_id for option in constraint.options],
            ["table-a", "table-b"],
        )
        self.assertEqual(
            constraint.options[0].candidate_ids_by_owner(),
            {
                "ob_alpha": ["cand-alpha-a"],
                "ob_beta": ["cand-beta-a"],
            },
        )
        island_plan = build_semantic_compilation_islands(
            obligations,
            evidence_bundle_constraints=cohort_plan[
                "evidence_bundle_constraints"
            ],
        )
        self.assertEqual(island_plan["schema"], "semantic_compilation_islands_v2")
        self.assertEqual(
            [item["obligation_ids"] for item in island_plan["islands"]],
            [["ob_alpha", "ob_beta"]],
        )

        prompt_payload = FinancialAgent._semantic_program_prompt_payload(
            catalog, cohort_plan
        )
        self.assertEqual(
            prompt_payload["evidence_bundle_constraints"],
            cohort_plan["evidence_bundle_constraints"],
        )

    def test_independent_same_subject_output_does_not_hide_a_complete_pair(self) -> None:
        obligations, catalog, _cohort_plan, _visibility = self._fixture()
        obligations.append(_bundle_obligation("ob_gamma", "gamma metric"))
        catalog.append(
            _row_candidate(
                "cand-gamma-c",
                30,
                metric="gamma metric",
                table_id="table-c",
            )
        )

        cohort_plan = _semantic_candidate_cohorts(catalog, obligations)

        self.assertEqual(len(cohort_plan["evidence_bundle_constraints"]), 1)
        self.assertEqual(
            cohort_plan["evidence_bundle_constraints"][0]["owner_ids"],
            ["ob_alpha", "ob_beta"],
        )

    def test_validator_and_executor_reject_cross_row_selection(self) -> None:
        obligations, catalog, _cohort_plan, visibility = self._fixture()
        mixed_program = {
            "status": "ready",
            "direct_bindings": [
                {
                    "obligation_id": "ob_alpha",
                    "candidate_id": "cand-alpha-b",
                },
                {
                    "obligation_id": "ob_beta",
                    "candidate_id": "cand-beta-a",
                },
            ],
        }
        validation = validate_semantic_calculation_program(
            program=mixed_program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both Target Entity metrics.",
            candidate_visibility=visibility,
        )

        self.assertEqual(validation["status"], "invalid")
        self.assertEqual(
            validation["missing_obligation_ids"], ["ob_alpha", "ob_beta"]
        )
        self.assertEqual(
            [
                item
                for item in validation["errors"]
                if item["code"] == "evidence_bundle_mismatch"
            ],
            [
                {
                    "code": "evidence_bundle_mismatch",
                    "obligation_id": "ob_alpha",
                    "detail": "cand-alpha-b",
                }
            ],
        )
        envelope = CompilationEnvelopeV1.create(
            visibility=visibility,
            program=mixed_program,
            validation=validation,
        )
        executed = execute_semantic_calculation_program(
            program=mixed_program,
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both Target Entity metrics.",
            compilation_envelope=envelope,
        )
        self.assertEqual(executed["status"], "incomplete")
        self.assertEqual(executed["outputs"], [])
        self.assertNotIn(
            "validation_drift",
            {item["code"] for item in executed["validation"]["errors"]},
        )

    def test_source_defined_narrative_uses_compatible_cross_table_context(self) -> None:
        direct_obligations, direct_catalog, _plan, _visibility = self._fixture()
        narrative = _bundle_obligation(
            "ob_summary",
            "summary metric",
            kind="narrative",
            evidence_mode="source_defined_group",
            consolidation_scope="unknown",
        )
        explicit_summary = _row_candidate(
            "cand-summary-explicit",
            7,
            metric="summary metric",
            table_id="table-summary",
        )
        unknown_summary = _row_candidate(
            "cand-summary-unknown",
            8,
            metric="summary metric",
            table_id="table-unknown",
            consolidation_scope="unknown",
        )
        obligations = [*direct_obligations, narrative]
        catalog = [*direct_catalog, explicit_summary, unknown_summary]
        cohort_plan = _semantic_candidate_cohorts(catalog, obligations)
        constraint = cohort_plan["evidence_bundle_constraints"][0]

        self.assertEqual(
            constraint["owner_ids"], ["ob_alpha", "ob_beta", "ob_summary"]
        )
        self.assertTrue(
            all(
                option["candidate_ids_by_owner"]["ob_summary"]
                == ["cand-summary-explicit"]
                for option in constraint["options"]
            )
        )

        visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=cohort_plan["visible_candidate_ids"],
            candidate_ids_by_owner=cohort_plan["candidate_ids_by_owner"],
            evidence_bundle_constraints=cohort_plan[
                "evidence_bundle_constraints"
            ],
        )
        validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-a",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    },
                ],
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": ["cand-summary-unknown"],
                        "evidence_bindings": [
                            {
                                "candidate_id": "cand-summary-unknown",
                                "source_requirement_id": "ob_summary:req_001",
                            }
                        ],
                        "text": "Target Entity summary metric 8 items",
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both metrics and the source-defined summary.",
            candidate_visibility=visibility,
        )
        self.assertEqual(validation["status"], "invalid")
        self.assertIn(
            {
                "code": "evidence_bundle_mismatch",
                "obligation_id": "ob_summary",
                "detail": "cand-summary-unknown",
            },
            validation["errors"],
        )

        accepted = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-a",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    },
                ],
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": ["cand-summary-explicit"],
                        "evidence_bindings": [
                            {
                                "candidate_id": "cand-summary-explicit",
                                "source_requirement_id": "ob_summary:req_001",
                            }
                        ],
                        "text": "Target Entity summary metric 7 items",
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both metrics and the source-defined summary.",
            candidate_visibility=visibility,
        )
        self.assertEqual(accepted["status"], "ready")
        self.assertEqual(
            accepted["evidence_bundle_validation"][0]["status"], "ready"
        )

    def test_visibility_copies_bundle_projection_inputs(self) -> None:
        _obligations, catalog, cohort_plan, _visibility = self._fixture()
        bundle_rows = cohort_plan["evidence_bundle_constraints"]
        visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=cohort_plan["visible_candidate_ids"],
            candidate_ids_by_owner=cohort_plan["candidate_ids_by_owner"],
            evidence_bundle_constraints=bundle_rows,
        )
        bundle_rows[0]["options"][0]["candidate_ids_by_owner"]["ob_alpha"].append(
            "cand-late"
        )

        self.assertEqual(
            visibility.evidence_bundle_constraints[0]
            .options[0]
            .candidate_ids_by_owner()["ob_alpha"],
            ["cand-alpha-a"],
        )

    def test_bundle_retry_replaces_only_the_incompatible_candidate(self) -> None:
        obligations, catalog, _cohort_plan, _visibility = self._fixture()
        llm, compiled = self._compile(
            obligations,
            catalog,
            {
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-b",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    },
                ]
            },
            {
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-a",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    },
                ]
            },
        )

        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertIn("evidence_bundle_constraints", str(llm.prompts[0]))
        self.assertIn("cand-alpha-a", str(llm.prompts[1]))
        self.assertEqual(
            [
                binding["candidate_id"]
                for binding in compiled["semantic_program"]["direct_bindings"]
            ],
            ["cand-alpha-a", "cand-beta-a"],
        )
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"][
            "candidate_stage_diagnostics"
        ]
        self.assertEqual(diagnostics["island_count"], 1)
        self.assertEqual(
            diagnostics["islands"][0]["obligation_ids"],
            ["ob_alpha", "ob_beta"],
        )

    def test_missing_bundle_owner_retries_the_whole_bundle(self) -> None:
        obligations, catalog, _cohort_plan, _visibility = self._fixture()
        _llm, compiled = self._compile(
            obligations,
            catalog,
            {
                "direct_bindings": [
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    }
                ]
            },
            {
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-b",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-b",
                    },
                ]
            },
        )

        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(
            [
                binding["candidate_id"]
                for binding in compiled["semantic_program"]["direct_bindings"]
            ],
            ["cand-alpha-b", "cand-beta-b"],
        )

    def test_retry_preserves_an_unaffected_bundle_in_the_same_island(self) -> None:
        obligations, catalog, _cohort_plan, _visibility = self._fixture()
        gamma = _bundle_obligation("ob_gamma", "gamma metric")
        gamma["depends_on"] = ["ob_beta"]
        obligations.extend(
            [gamma, _bundle_obligation("ob_delta", "delta metric")]
        )
        catalog.extend(
            [
                _row_candidate(
                    "cand-gamma-c",
                    30,
                    metric="gamma metric",
                    table_id="table-c",
                ),
                _row_candidate(
                    "cand-delta-c",
                    40,
                    metric="delta metric",
                    table_id="table-c",
                ),
            ]
        )
        _llm, compiled = self._compile(
            obligations,
            catalog,
            {
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-b",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    },
                    {
                        "obligation_id": "ob_gamma",
                        "candidate_id": "cand-gamma-c",
                    },
                    {
                        "obligation_id": "ob_delta",
                        "candidate_id": "cand-delta-c",
                    },
                ]
            },
            {
                "direct_bindings": [
                    {
                        "obligation_id": "ob_alpha",
                        "candidate_id": "cand-alpha-a",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
                    },
                ]
            },
        )

        envelope = compiled["semantic_compilation_envelope"]
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(envelope.visibility.evidence_bundle_constraints), 2)
        self.assertEqual(
            [
                binding["candidate_id"]
                for binding in compiled["semantic_program"]["direct_bindings"]
            ],
            ["cand-alpha-a", "cand-beta-a", "cand-gamma-c", "cand-delta-c"],
        )


if __name__ == "__main__":
    unittest.main()
