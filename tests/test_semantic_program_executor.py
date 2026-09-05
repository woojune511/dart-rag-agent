from __future__ import annotations

from tests.semantic_program_test_support import *


class SemanticCalculationProgramExecutorTests(unittest.TestCase):
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
                    "source_display_candidate_id": None,
                    "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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
        self.assertIn("Inputs:", execution["answer"])
        self.assertIn("closing quantity 380items", execution["answer"])
        self.assertIn("opening quantity 343items", execution["answer"])

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
                        "source_display_candidate_id": None,
                        "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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
                    "source_display_reason": "The selected source candidate explicitly reports this derived result.",
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
        self.assertEqual(output["answer_slot"]["normalized_value"], 10.2)
        self.assertEqual(output["source_display_value"], "10.2%")
        self.assertEqual(output["source_display_candidate_id"], "cand-stated")
        self.assertEqual(output["source_display_normalized_value"], 10.2)
        self.assertFalse(output["source_display_matches_formula"])
        self.assertTrue(output["source_stated_result_used"])
        self.assertNotEqual(output["formula_rendered_value"], output["rendered_value"])
        self.assertIn(output["formula_rendered_value"], result["answer"])
        self.assertIn("10.2% (recalculated 10%)", result["answer"])
        self.assertIn("calculated", result["answer"])
        self.assertIn("cand-stated", result["selected_candidate_ids"])
        self.assertIn("row-cand-stated", output["source_row_ids"])
        self.assertIn("[sample | 2024 | source note]", output["source_anchors"])
        self.assertIn("cand-stated", {row["operand_id"] for row in result["calculation_operands"]})

    def test_source_display_comparison_keeps_existing_close_and_absent_behavior(self) -> None:
        for stated_value in (10.0, None):
            with self.subTest(stated_value=stated_value):
                fixture = _source_display_program_fixture()
                if stated_value is None:
                    fixture["program"]["expressions"][0]["source_display_candidate_id"] = None
                    fixture["program"]["expressions"][0]["source_display_reason"] = "No source-stated result is selected for this calculation-only case."
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
        self.assertIn("10.2% (재계산값", result["answer"])
        self.assertIn("계산값", result["answer"])
        self.assertIn("입력값은", result["answer"])
        self.assertIn("40.0items", result["answer"])
        self.assertIn("44.0items", result["answer"])

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
                self.assertTrue(output["source_stated_result_used"])
                self.assertIn(f"4.2{unit} (recalculated", result["answer"])

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
                        "source_display_candidate_id": None,
                        "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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
                    "source_display_candidate_id": None,
                    "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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
                        "source_display_candidate_id": None,
                        "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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
                        "source_display_candidate_id": None,
                        "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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
                        "source_display_candidate_id": None,
                        "source_display_reason": "The fixture provides operands without a matching source-stated result.",
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


if __name__ == "__main__":
    unittest.main()
