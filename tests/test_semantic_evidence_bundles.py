from __future__ import annotations

from tests.semantic_program_test_support import *

from src.agent.financial_graph_calculation import (
    _project_atomic_evidence_bundle_options,
    _semantic_candidate_visibility,
)
from src.agent.financial_runtime_contracts import (
    CompilationEnvelopeV1,
    EvidenceBundleConstraintV1,
    EvidenceBundleOptionV1,
)


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
            ["table-a"],
        )
        self.assertEqual(
            constraint.options[0].candidate_ids_by_owner(),
            {
                "ob_alpha": ["cand-alpha-a"],
                "ob_beta": ["cand-beta-a"],
            },
        )
        selection = cohort_plan["evidence_bundle_option_selections"][0]
        self.assertEqual(selection["selected_option_id"], constraint.options[0].option_id)
        self.assertEqual(
            [item["physical_table_id"] for item in selection["ranked_options"]],
            ["table-a", "table-b"],
        )
        self.assertEqual(selection["complete_option_count"], 2)
        self.assertEqual(selection["selected_physical_table_id"], "table-a")
        self.assertEqual(selection["selected_physical_row_id"], "row-target")
        self.assertEqual(
            [
                (item["position_sum"], item["worst_position"])
                for item in selection["ranked_option_diagnostics"]
            ],
            [(0, 0), (4, 2)],
        )
        self.assertEqual(
            cohort_plan["candidate_ids_by_owner"],
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
        self.assertEqual(
            prompt_payload["evidence_bundle_option_selections"],
            [
                {
                    key: selection[key]
                    for key in (
                        "constraint_id",
                        "source_constraint_id",
                        "selected_option_id",
                        "selection_strategy",
                    )
                }
            ],
        )
        self.assertNotIn("cand-alpha-b", prompt_payload["candidates_by_id"])
        self.assertNotIn("cand-beta-b", prompt_payload["candidates_by_id"])

    def test_atomic_option_selection_is_catalog_order_independent(self) -> None:
        obligations, catalog, _cohort_plan, _visibility = self._fixture()

        forward = _semantic_candidate_cohorts(catalog, obligations)
        reverse = _semantic_candidate_cohorts(list(reversed(catalog)), obligations)

        self.assertEqual(
            forward["evidence_bundle_option_selections"],
            reverse["evidence_bundle_option_selections"],
        )
        self.assertEqual(
            forward["candidate_ids_by_owner"],
            reverse["candidate_ids_by_owner"],
        )

    def test_excluding_selected_row_promotes_next_atomic_option(self) -> None:
        obligations, catalog, _cohort_plan, _visibility = self._fixture()

        promoted = _semantic_candidate_cohorts(
            catalog,
            obligations,
            excluded_candidate_ids_by_owner={"ob_alpha": ["cand-alpha-a"]},
        )

        constraint = promoted["evidence_bundle_constraints"][0]
        self.assertEqual(constraint["options"][0]["physical_table_id"], "table-b")
        self.assertEqual(
            promoted["candidate_ids_by_owner"],
            {
                "ob_alpha": ["cand-alpha-b"],
                "ob_beta": ["cand-beta-b"],
            },
        )

    def test_atomic_projection_preserves_numeric_compatibility_evidence(self) -> None:
        options = tuple(
            EvidenceBundleOptionV1.create(
                physical_table_id=table_id,
                physical_row_id="row-target",
                candidate_ids_by_owner={
                    "ob_alpha": [f"cand-alpha-{suffix}"],
                    "ob_beta": [f"cand-beta-{suffix}"],
                },
            )
            for table_id, suffix in (("table-a", "a"), ("table-b", "b"))
        )
        constraint = EvidenceBundleConstraintV1.create(
            owner_ids=["ob_alpha", "ob_beta"],
            options=options,
        )
        cohorts = [
            {
                "cohort_id": "ob_alpha:output",
                "owner_id": "ob_alpha",
                "parent_obligation_id": "ob_alpha",
                "owner_type": "obligation",
                "candidate_ids": ["cand-alpha-a", "cand-alpha-b"],
            },
            {
                "cohort_id": "ob_alpha:compatibility",
                "owner_id": "ob_alpha",
                "parent_obligation_id": "ob_alpha",
                "owner_type": "compatibility",
                "candidate_ids": ["cand-alpha-context"],
            },
            {
                "cohort_id": "ob_beta:output",
                "owner_id": "ob_beta",
                "parent_obligation_id": "ob_beta",
                "owner_type": "obligation",
                "candidate_ids": ["cand-beta-a", "cand-beta-b"],
            },
            {
                "cohort_id": "ob_beta:compatibility",
                "owner_id": "ob_beta",
                "parent_obligation_id": "ob_beta",
                "owner_type": "compatibility",
                "candidate_ids": ["cand-beta-context"],
            },
        ]

        projected = _project_atomic_evidence_bundle_options(
            cohorts=cohorts,
            visible_candidate_ids=[
                "cand-alpha-a",
                "cand-alpha-b",
                "cand-alpha-context",
                "cand-beta-a",
                "cand-beta-b",
                "cand-beta-context",
            ],
            constraints=[constraint],
        )

        self.assertEqual(
            projected["candidate_ids_by_owner"],
            {
                "ob_alpha": ["cand-alpha-a", "cand-alpha-context"],
                "ob_beta": ["cand-beta-a", "cand-beta-context"],
            },
        )
        self.assertNotIn("cand-alpha-b", projected["visible_candidate_ids"])
        self.assertNotIn("cand-beta-b", projected["visible_candidate_ids"])

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
        obligations, catalog, _cohort_plan, _visibility = self._fixture()
        options = tuple(
            EvidenceBundleOptionV1.create(
                physical_table_id=table_id,
                physical_row_id="row-target",
                candidate_ids_by_owner={
                    "ob_alpha": [f"cand-alpha-{suffix}"],
                    "ob_beta": [f"cand-beta-{suffix}"],
                },
            )
            for table_id, suffix in (("table-a", "a"), ("table-b", "b"))
        )
        raw_constraint = EvidenceBundleConstraintV1.create(
            owner_ids=["ob_alpha", "ob_beta"],
            options=options,
        )
        visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=[
                "cand-alpha-a",
                "cand-beta-a",
                "cand-alpha-b",
                "cand-beta-b",
            ],
            candidate_ids_by_owner={
                "ob_alpha": ["cand-alpha-a", "cand-alpha-b"],
                "ob_beta": ["cand-beta-a", "cand-beta-b"],
            },
            evidence_bundle_constraints=[raw_constraint.to_projection()],
        )
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
        self.assertEqual(
            cohort_plan["candidate_ids_by_owner"]["ob_summary:req_001"],
            ["cand-summary-explicit"],
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
        self.assertEqual(validation["status"], "partial")
        self.assertIn(
            {
                "code": "candidate_not_exposed_to_compiler",
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

    def test_source_defined_group_requires_every_visible_cell_from_one_row(self) -> None:
        direct_obligations, direct_catalog, _plan, _visibility = self._fixture()
        narrative = _bundle_obligation(
            "ob_summary",
            "summary metric",
            kind="narrative",
            evidence_mode="source_defined_group",
            consolidation_scope="unknown",
        )
        narrative["semantic_target"]["metric_surfaces"] = [
            "summary revenue",
            "summary loss",
        ]
        narrative["evidence_requirements"][0]["semantic_target"] = dict(
            narrative["semantic_target"]
        )
        summary_row = [
            _row_candidate(
                "cand-summary-revenue",
                7,
                metric="summary revenue",
                table_id="table-summary",
                row_id="row-summary",
            ),
            _row_candidate(
                "cand-summary-loss",
                8,
                metric="summary loss",
                table_id="table-summary",
                row_id="row-summary",
            ),
        ]
        alternative = _row_candidate(
            "cand-summary-alternative",
            9,
            metric="summary alternative",
            table_id="table-other-summary",
            row_id="row-other",
        )
        obligations = [*direct_obligations, narrative]
        catalog = [*direct_catalog, *summary_row, alternative]
        cohort_plan = _semantic_candidate_cohorts(catalog, obligations)

        output_cohort = next(
            cohort
            for cohort in cohort_plan["cohorts"]
            if cohort["cohort_id"] == "ob_summary:output"
        )
        self.assertEqual(
            output_cohort["candidate_ids"],
            ["cand-summary-loss", "cand-summary-revenue"],
        )
        self.assertEqual(
            output_cohort["source_defined_group_selection"],
            {
                "selection_mode": "complete_physical_row",
                "physical_table_id": "table-summary",
                "physical_row_id": "row-summary",
                "required_candidate_ids": [
                    "cand-summary-loss",
                    "cand-summary-revenue",
                ],
                "complete_option_count": 1,
                "policy_group_names": [],
            },
        )
        self.assertNotIn(
            "cand-summary-alternative",
            cohort_plan["visible_candidate_ids"],
        )

        visibility = _semantic_candidate_visibility(
            catalog,
            visible_candidate_ids=cohort_plan["visible_candidate_ids"],
            candidate_ids_by_owner=cohort_plan["candidate_ids_by_owner"],
            evidence_bundle_constraints=cohort_plan[
                "evidence_bundle_constraints"
            ],
        )
        direct_bindings = [
            {"obligation_id": "ob_alpha", "candidate_id": "cand-alpha-a"},
            {"obligation_id": "ob_beta", "candidate_id": "cand-beta-a"},
        ]
        partial = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": direct_bindings,
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": ["cand-summary-revenue"],
                        "evidence_bindings": [
                            {
                                "candidate_id": "cand-summary-revenue",
                                "source_requirement_id": "ob_summary:req_001",
                            }
                        ],
                        "text": "Target Entity summary revenue is 7 items",
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both metrics and every item in the source summary.",
            candidate_visibility=visibility,
        )
        self.assertEqual(partial["status"], "partial")
        self.assertIn(
            "incomplete_source_defined_group",
            {error["code"] for error in partial["errors"]},
        )

        omitted_value = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": direct_bindings,
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": [
                            "cand-summary-revenue",
                            "cand-summary-loss",
                        ],
                        "evidence_bindings": [
                            {
                                "candidate_id": candidate_id,
                                "source_requirement_id": "ob_summary:req_001",
                            }
                            for candidate_id in (
                                "cand-summary-revenue",
                                "cand-summary-loss",
                            )
                        ],
                        "text": "Target Entity summary revenue is 7 items",
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both metrics and every item in the source summary.",
            candidate_visibility=visibility,
        )
        self.assertIn(
            "source_defined_group_value_omitted",
            {error["code"] for error in omitted_value["errors"]},
        )

        accepted = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": direct_bindings,
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_summary",
                        "candidate_ids": [
                            "cand-summary-revenue",
                            "cand-summary-loss",
                        ],
                        "evidence_bindings": [
                            {
                                "candidate_id": candidate_id,
                                "source_requirement_id": "ob_summary:req_001",
                            }
                            for candidate_id in (
                                "cand-summary-revenue",
                                "cand-summary-loss",
                            )
                        ],
                        "text": (
                            "Target Entity summary revenue is 7 items and "
                            "summary loss is 8 items"
                        ),
                    }
                ],
            },
            obligations=obligations,
            candidate_catalog=catalog,
            query="Return both metrics and every item in the source summary.",
            candidate_visibility=visibility,
        )
        self.assertEqual(accepted["status"], "ready")

    def test_source_defined_policy_members_survive_atomic_bundle_projection(self) -> None:
        direct_obligations, direct_catalog, _plan, _visibility = self._fixture()
        narrative = _bundle_obligation(
            "ob_summary",
            "summary metric",
            kind="narrative",
            evidence_mode="source_defined_group",
            consolidation_scope="unknown",
        )
        narrative["semantic_target"]["metric_surfaces"] = [
            "summary revenue",
            "summary loss",
        ]
        narrative["evidence_requirements"][0]["semantic_target"] = dict(
            narrative["semantic_target"]
        )
        summary_row = [
            _row_candidate(
                "cand-summary-revenue",
                7,
                metric="summary revenue",
                table_id="table-summary",
                row_id="row-summary",
            ),
            _row_candidate(
                "cand-summary-loss",
                8,
                metric="summary loss",
                table_id="table-summary",
                row_id="row-summary",
            ),
            _row_candidate(
                "cand-summary-adjustment",
                9,
                metric="summary adjustment",
                table_id="table-summary",
                row_id="row-summary",
            ),
        ]
        policy = {
            "entity_metric_slot_groups": (
                {
                    "name": "complete_summary",
                    "query_terms": ("summary",),
                    "evidence_terms": (
                        "summary revenue",
                        "summary loss",
                        "summary adjustment",
                    ),
                },
            )
        }

        with patch(
            "src.agent.financial_candidate_matching.active_narrative_policies",
            return_value=[policy],
        ):
            cohort_plan = _semantic_candidate_cohorts(
                [*direct_catalog, *summary_row],
                [*direct_obligations, narrative],
            )

        output_cohort = next(
            cohort
            for cohort in cohort_plan["cohorts"]
            if cohort["cohort_id"] == "ob_summary:output"
        )
        self.assertEqual(
            output_cohort["candidate_ids"],
            [
                "cand-summary-loss",
                "cand-summary-revenue",
                "cand-summary-adjustment",
            ],
        )
        self.assertEqual(
            output_cohort["source_defined_group_selection"],
            {
                "selection_mode": "complete_physical_row",
                "physical_table_id": "table-summary",
                "physical_row_id": "row-summary",
                "required_candidate_ids": [
                    "cand-summary-loss",
                    "cand-summary-revenue",
                    "cand-summary-adjustment",
                ],
                "complete_option_count": 1,
                "policy_group_names": ["complete_summary"],
            },
        )
        constraint = cohort_plan["evidence_bundle_constraints"][0]
        self.assertEqual(
            constraint["options"][0]["candidate_ids_by_owner"]["ob_summary"],
            [
                "cand-summary-loss",
                "cand-summary-revenue",
                "cand-summary-adjustment",
            ],
        )

        alternative_row = [
            _row_candidate(
                "cand-alt-revenue",
                10,
                metric="summary revenue",
                table_id="table-alternative",
                row_id="row-alternative",
            ),
            _row_candidate(
                "cand-alt-loss",
                11,
                metric="summary loss",
                table_id="table-alternative",
                row_id="row-alternative",
            ),
            _row_candidate(
                "cand-alt-adjustment",
                12,
                metric="summary adjustment",
                table_id="table-alternative",
                row_id="row-alternative",
            ),
        ]
        with patch(
            "src.agent.financial_candidate_matching.active_narrative_policies",
            return_value=[policy],
        ):
            retried = _semantic_candidate_cohorts(
                [*direct_catalog, *summary_row, *alternative_row],
                [*direct_obligations, narrative],
                excluded_candidate_ids_by_owner={
                    "ob_summary": ["cand-summary-adjustment"]
                },
            )
        retried_cohort = next(
            cohort
            for cohort in retried["cohorts"]
            if cohort["cohort_id"] == "ob_summary:output"
        )
        self.assertEqual(
            retried_cohort["candidate_ids"],
            ["cand-alt-loss", "cand-alt-revenue", "cand-alt-adjustment"],
        )

        limits = CALCULATION_PROMPT_POLICY["semantic_program_prompt_limits"]
        with patch(
            "src.agent.financial_candidate_matching.active_narrative_policies",
            return_value=[policy],
        ), patch.dict(limits, {"narrative_candidates_per_owner": 2}):
            overflow = _semantic_candidate_cohorts(
                [*direct_catalog, *summary_row],
                [*direct_obligations, narrative],
            )
        self.assertEqual(overflow["status"], "capacity_exceeded")
        self.assertIn(
            "ob_summary",
            overflow["reservation"]["source_defined_group_overflow"],
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

    def test_bundle_retry_does_not_reintroduce_hidden_alternative(self) -> None:
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
        self.assertIn("evidence_bundle_option_selections", str(llm.prompts[0]))
        self.assertNotIn("cand-alpha-b", str(llm.prompts[0]))
        attempt_rows = compiled["resolved_calculation_trace"]["calculation_plan"][
            "candidate_stage_diagnostics"
        ]["attempts"]
        self.assertEqual(
            [row["visible_candidate_ids"] for row in attempt_rows],
            [
                ["cand-alpha-a", "cand-beta-a"],
                ["cand-alpha-a", "cand-beta-a"],
            ],
        )
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
                        "candidate_id": "cand-alpha-a",
                    },
                    {
                        "obligation_id": "ob_beta",
                        "candidate_id": "cand-beta-a",
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
            ["cand-alpha-a", "cand-beta-a"],
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
