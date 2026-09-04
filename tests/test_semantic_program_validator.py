from __future__ import annotations

from tests.semantic_program_test_support import *


class SemanticCalculationProgramValidatorTests(unittest.TestCase):
    def test_selected_prose_value_requires_exact_source_assertion(self) -> None:
        obligation = _obligation(
            "ob_growth",
            "direct_value",
            "reported growth",
            display_unit="%",
        )
        candidate = {
            **_candidate(
                "cand-growth",
                11.5,
                raw_unit="%",
                normalized_unit="PERCENT",
            ),
            "candidate_kind": "sentence_value",
            "table_source_id": "",
            "source_text": "The source reports year-on-year growth of 11.5%.",
        }
        base_program = {
            "status": "ready",
            "direct_bindings": [
                {
                    "obligation_id": "ob_growth",
                    "candidate_id": "cand-growth",
                }
            ],
        }

        missing = validate_semantic_calculation_program(
            program=base_program,
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Return the reported growth.",
        )
        self.assertEqual(missing["status"], "invalid")
        self.assertIn(
            "missing_source_assertion",
            {item["code"] for item in missing["errors"]},
        )

        assertions = _source_assertions([candidate], "cand-growth")
        accepted = validate_semantic_calculation_program(
            program={**base_program, "source_assertions": assertions},
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Return the reported growth.",
        )
        self.assertEqual(accepted["status"], "ready")
        self.assertEqual(len(accepted["valid_source_assertions"]), 1)
        self.assertTrue(
            accepted["valid_source_assertions"][0]["assertion_fingerprint"]
        )

        mismatched_assertion = {
            **assertions[0],
            "evidence_text": assertions[0]["evidence_text"].replace(
                "11.5%", "11.6%"
            ),
        }
        rejected = validate_semantic_calculation_program(
            program={
                **base_program,
                "source_assertions": [mismatched_assertion],
            },
            obligations=[obligation],
            candidate_catalog=[candidate],
            query="Return the reported growth.",
        )
        self.assertEqual(rejected["status"], "invalid")
        self.assertIn(
            "source_assertion_text_mismatch",
            {item["code"] for item in rejected["errors"]},
        )

    def test_source_assertion_rejects_cross_bundle_hidden_and_uncovered_values(self) -> None:
        obligation = _obligation("ob_value", "direct_value", "reported value")
        first_text = "The first source reports 10 items."
        second_text = "The second source reports 20 items."
        first = {
            **_candidate("cand-first", 10),
            "candidate_kind": "sentence_value",
            "table_source_id": "",
            "source_candidate_id": "source-first",
            "source_text": first_text,
            "source_bundle_text": first_text,
        }
        second = {
            **_candidate("cand-second", 20),
            "candidate_kind": "sentence_value",
            "table_source_id": "",
            "source_candidate_id": "source-second",
            "source_text": second_text,
            "source_bundle_text": second_text,
        }
        catalog = [first, second]
        bundles = build_semantic_source_bundles(catalog)
        bundle_ids = source_bundle_id_by_candidate_id(bundles)
        base_program = {
            "status": "ready",
            "direct_bindings": [
                {"obligation_id": "ob_value", "candidate_id": "cand-first"}
            ],
        }

        cross_bundle = validate_semantic_calculation_program(
            program={
                **base_program,
                "source_assertions": [
                    {
                        "source_bundle_id": bundle_ids["cand-second"],
                        "candidate_ids": ["cand-first"],
                        "evidence_text": second_text,
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=catalog,
            query="Return the reported value.",
        )
        self.assertIn(
            "source_assertion_bundle_mismatch",
            {item["code"] for item in cross_bundle["errors"]},
        )

        uncovered = validate_semantic_calculation_program(
            program={
                **base_program,
                "source_assertions": [
                    {
                        "source_bundle_id": bundle_ids["cand-first"],
                        "candidate_ids": ["cand-first"],
                        "evidence_text": "The first source reports",
                    }
                ],
            },
            obligations=[obligation],
            candidate_catalog=catalog,
            query="Return the reported value.",
        )
        self.assertIn(
            "source_assertion_text_mismatch",
            {item["code"] for item in uncovered["errors"]},
        )

        hidden = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_value",
                        "candidate_id": "cand-second",
                    }
                ],
                "source_assertions": _source_assertions(
                    catalog, "cand-second"
                ),
            },
            obligations=[obligation],
            candidate_catalog=catalog,
            query="Return the reported value.",
            candidate_visibility=_semantic_candidate_visibility(
                catalog,
                visible_candidate_ids=["cand-first"],
                candidate_ids_by_owner={"ob_value": ["cand-first"]},
            ),
        )
        self.assertIn(
            "candidate_not_exposed_to_compiler",
            {item["code"] for item in hidden["errors"]},
        )

    def test_table_and_narrative_bindings_do_not_require_source_assertions(self) -> None:
        table_obligation = _obligation(
            "ob_table", "direct_value", "table value"
        )
        table_candidate = _candidate("cand-table", 10)
        table_validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "direct_bindings": [
                    {
                        "obligation_id": "ob_table",
                        "candidate_id": "cand-table",
                    }
                ],
            },
            obligations=[table_obligation],
            candidate_catalog=[table_candidate],
            query="Return the table value.",
        )
        self.assertEqual(table_validation["status"], "ready")

        narrative_obligation = _obligation(
            "ob_narrative", "narrative", "source summary"
        )
        narrative_candidate = {
            **_candidate("cand-narrative", 0),
            "kind": "narrative",
            "normalized_value": None,
            "candidate_kind": "chunk",
            "table_source_id": "",
            "source_text": "The source directly states the requested summary.",
        }
        narrative_validation = validate_semantic_calculation_program(
            program={
                "status": "ready",
                "narrative_bindings": [
                    {
                        "obligation_id": "ob_narrative",
                        "candidate_ids": ["cand-narrative"],
                        "text": "The source directly states the requested summary.",
                    }
                ],
            },
            obligations=[narrative_obligation],
            candidate_catalog=[narrative_candidate],
            query="Summarize the source.",
        )
        self.assertEqual(narrative_validation["status"], "ready")

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
            "table_source_id": "",
            "company": "sample",
            "year": 2024,
            "segment": "",
            "basis": "",
            "source_text": "The northmarket local sentence reports 380 items.",
        }
        prior = {
            **_candidate("cand-prior", 343, period="2023"),
            "candidate_kind": "sentence_value",
            "table_source_id": "",
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
                "source_assertions": _source_assertions(
                    [current, prior],
                    "cand-current",
                    "cand-prior",
                ),
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


if __name__ == "__main__":
    unittest.main()
