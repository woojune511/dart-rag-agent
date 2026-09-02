from __future__ import annotations

from tests.semantic_program_test_support import *


class SemanticCalculationProgramCohortTests(unittest.TestCase):
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

    def test_source_defined_group_reserves_relevant_prose_within_shared_cap(self) -> None:
        obligation = _obligation(
            "ob_summary",
            "narrative",
            "target unit operating strategy",
            scope=_scope(segment="target unit"),
            evidence_mode="source_defined_group",
        )
        compatible_numeric = [
            {
                **_candidate(
                    f"compatible-{index}",
                    index + 1,
                    row_label="target unit",
                ),
                "segment": "target unit",
            }
            for index in range(3)
        ]
        unknown_numeric = [
            {
                **_candidate(
                    f"unknown-{index}",
                    index + 10,
                    row_label="",
                ),
                "candidate_kind": "sentence_value",
                "source_text": f"Operating strategy metric {index + 10} items.",
            }
            for index in range(5)
        ]
        narrative = {
            **_candidate(
                "strategy-prose",
                0,
                row_label="",
            ),
            "kind": "narrative",
            "candidate_kind": "narrative",
            "normalized_value": None,
            "raw_value": "",
            "source_text": "The operating strategy emphasizes product reliability.",
        }
        compatible_narrative = {
            **narrative,
            "candidate_id": "compatible-prose",
            "source_candidate_id": "source-compatible-prose",
            "evidence_id": "evidence-compatible-prose",
            "segment": "target unit",
            "source_text": "A separate target unit overview is also relevant.",
        }

        cohort_plan = _semantic_candidate_cohorts(
            [
                *compatible_numeric,
                compatible_narrative,
                *unknown_numeric,
                narrative,
            ],
            [obligation],
        )
        output_cohort = next(
            item
            for item in cohort_plan["cohorts"]
            if item["cohort_id"] == "ob_summary:output"
        )

        self.assertEqual(len(output_cohort["candidate_ids"]), 6)
        self.assertIn("compatible-prose", output_cohort["candidate_ids"])
        self.assertIn("strategy-prose", output_cohort["candidate_ids"])
        self.assertTrue(
            {item["candidate_id"] for item in compatible_numeric}.issubset(
                output_cohort["candidate_ids"]
            )
        )

        fully_compatible_plan = _semantic_candidate_cohorts(
            [
                *compatible_numeric,
                *[
                    {
                        **_candidate(
                            f"compatible-extra-{index}",
                            index + 20,
                            row_label="target unit",
                        ),
                        "segment": "target unit",
                    }
                    for index in range(3)
                ],
                narrative,
            ],
            [obligation],
        )
        fully_compatible_output = next(
            item
            for item in fully_compatible_plan["cohorts"]
            if item["cohort_id"] == "ob_summary:output"
        )
        self.assertNotIn("strategy-prose", fully_compatible_output["candidate_ids"])

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


if __name__ == "__main__":
    unittest.main()
