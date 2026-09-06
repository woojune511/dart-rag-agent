"""Relative-period and cross-source calculation regressions; no providers/stores."""

from copy import deepcopy

from tests.semantic_program_test_support import *


def relative_period_source():
    return {
        "candidate_id": "annual-row",
        "candidate_kind": "structured_row",
        "source_anchor": "[sample | 2024 | annual table]",
        "text": "quantity | current and prior annual amounts",
        "metadata": {
            "company": "sample", "year": 2024, "table_source_id": "annual-table",
            "row_label": "quantity", "value_role": "detail", "period_focus": "multi_period",
            "structured_cells": [
                {"column_headers": ["연결", label, "금액"], "period_text": label,
                 "value_text": str(value), "unit_hint": "items", "value_role": "detail"}
                for label, value in (("당기", 120), ("전기", 100), ("전전기", 80))
            ],
        },
    }


class RelativePeriodContractTests(unittest.TestCase):
    def test_relative_projection_preserves_predecessor_ids_and_catalog_fingerprint(self):
        catalog = build_semantic_candidate_catalog([relative_period_source()])
        self.assertEqual([c["candidate_id"] for c in catalog], [
            "cand_fcae2ee3fb5a88312106", "cand_de904026a8e3278c7646", "cand_91df2487e727b75a75ba"])
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog),
                         "f99cd41fa6aa474158bccb39bd1914eea12ee01473e96efbf39090a91b98b77f")

    def test_cell_period_labels_override_generic_value_role_and_table_focus(self):
        source = relative_period_source()
        before = deepcopy(source)
        catalog = build_semantic_candidate_catalog([source])
        numeric = [c for c in catalog if c["kind"] == "numeric"]
        self.assertEqual([c["value_year"] for c in numeric], [2024, 2023, 2022])
        self.assertEqual([c["period"] for c in numeric], ["2024", "2023", "2022"])
        self.assertEqual([c["source_period_surface"] for c in numeric], ["당기", "전기", "전전기"])
        self.assertEqual([c["period_role"] for c in numeric], ["current", "prior", "prior"])
        self.assertTrue(all(c["period_source"] == "relative_period_label" for c in numeric))
        self.assertTrue(all(c["value_role"] == "detail" for c in numeric))
        self.assertEqual(source, before)

    def test_explicit_year_wins_over_relative_label(self):
        source = relative_period_source()
        source["metadata"]["structured_cells"][1]["period_text"] = "2021 전기"
        prior = next(c for c in build_semantic_candidate_catalog([source]) if c["raw_value"] == "100")
        self.assertEqual(prior["value_year"], 2021)
        self.assertEqual(prior["source_period_surface"], "2021 전기")

    def test_owner_cohorts_preserve_the_corresponding_period_member(self):
        catalog = build_semantic_candidate_catalog([relative_period_source()])
        owners = [_obligation(f"value-{year}", "direct_value", "quantity", scope=_scope(period=str(year)))
                  for year in (2024, 2023, 2022)]
        cohorts = _semantic_candidate_cohorts(catalog, owners)
        by_id = {c["candidate_id"]: c for c in catalog}
        for owner, expected in zip(owners, ("120", "100", "80")):
            cohort = next(c for c in cohorts["cohorts"] if c["owner_id"] == owner["obligation_id"])
            values = [by_id[cid]["raw_value"] for cid in cohort["candidate_ids"] if by_id[cid]["kind"] == "numeric"]
            self.assertEqual(values, [expected])

    def test_legacy_relative_candidate_is_not_the_report_year(self):
        prior = {**_candidate("prior", 100, period="전기"), "value_role": "detail", "value_year": None}
        for year, expected in ((2023, "compatible"), (2024, "explicit_conflict")):
            with self.subTest(year=year):
                owner = _obligation("value", "direct_value", "quantity", scope=_scope(period=str(year)))
                self.assertEqual(semantic_candidate_applicability(prior, owner)["state"], expected)

    def test_ambiguous_or_unanchored_relative_period_is_unknown(self):
        for overrides in ({"period": "당기 및 전기", "column_headers": []},
                          {"period": "전기", "column_headers": [], "year": None}):
            with self.subTest(overrides=overrides):
                candidate = {**_candidate("ambiguous", 100), **overrides}
                owner = _obligation("value", "direct_value", "quantity", scope=_scope(period="2024"))
                self.assertEqual(semantic_candidate_applicability(candidate, owner)["state"], "unknown_only")

    def test_ambiguous_cell_does_not_inherit_current_table_focus(self):
        source = relative_period_source()
        source["metadata"]["period_focus"] = "current"
        source["metadata"]["structured_cells"] = [
            {"period_text": "당기 및 전기", "value_text": "100", "unit_hint": "items"}
        ]
        candidate = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        self.assertIsNone(candidate["value_year"])

    def test_nonperiod_words_and_other_rows_do_not_supply_relative_period(self):
        source = relative_period_source()
        source["text"] = "전기 quantity in another row"
        source["metadata"]["structured_cells"] = [
            {"column_headers": ["전기차"], "value_text": "100", "unit_hint": "items"}
        ]
        candidate = next(c for c in build_semantic_candidate_catalog([source]) if c["kind"] == "numeric")
        self.assertIsNone(candidate["value_year"])


class ExpressionSourceContextContractTests(unittest.TestCase):
    def test_shared_prose_assertion_coverage_follows_declared_owner_order(self):
        catalog = _catalog_from_document(
            "The reported proportion is 20%.", {"company": "sample", "year": 2024, "is_table": False})
        candidate = next(c for c in catalog if c["kind"] == "numeric")
        # This source asserts a quantity, not its calendar year. Owner-order
        # coverage must not rely on the filing-year fallback being tested below.
        direct = _obligation("z_source", "direct_value", "quantity")
        derived = _obligation("a_copy", "derived_value", "copied quantity",
                              depends_on=["z_source"])
        program = {
            "status": "ready", "direct_bindings": [
                {"obligation_id": "z_source", "candidate_id": candidate["candidate_id"]}],
            "expressions": [{"obligation_id": "a_copy", "variable_bindings": [_binding("X", "z_source")],
                             "formula": "X", "source_display_candidate_id": None,
                             "source_display_reason": "No separate displayed result."}],
            "source_assertions": _source_assertions(catalog, candidate["candidate_id"]),
        }
        for owners in ([direct, derived], [derived, direct]):
            with self.subTest(order=[o["obligation_id"] for o in owners]):
                validation = validate_semantic_calculation_program(program=program,
                    obligations=owners, candidate_catalog=catalog, query="Copy the reported quantity.")
                self.assertEqual(validation["status"], "ready", validation["errors"])
                self.assertEqual(validation["valid_source_assertions"][0]["covered_obligation_ids"],
                                 [o["obligation_id"] for o in owners])

    def test_same_period_statement_and_note_inputs_are_compatible(self):
        case = _contract_residual_fixture()["expression_compatibility"]["cases"][1]
        validation = validate_semantic_calculation_program(
            program=case["program"], obligations=case["obligations"],
            candidate_catalog=case["candidate_catalog"], query=case["query"],
        )
        self.assertEqual(validation["status"], "ready", validation["errors"])

    def test_validated_dependency_values_can_come_from_different_sources(self):
        obligations = [
            _obligation("reported", "direct_value", "reported result", scope=_scope(period="2024")),
            _obligation("component", "direct_value", "disclosed component", scope=_scope(period="2024")),
            _obligation("net", "derived_value", "net result", depends_on=["reported", "component"],
                        scope=_scope(period="2024")),
        ]
        catalog = [_candidate("reported-cell", 120, period="2024", context="statement"),
                   _candidate("component-cell", 20, period="2024", context="note")]
        program = {"status": "ready", "direct_bindings": [
            {"obligation_id": "reported", "candidate_id": "reported-cell"},
            {"obligation_id": "component", "candidate_id": "component-cell"}],
            "expressions": [{"obligation_id": "net", "variable_bindings": [
                _binding("A", "reported"), _binding("B", "component")], "formula": "A - B",
                "source_display_candidate_id": None, "source_display_reason": "No stated result."}]}
        result = execute_semantic_calculation_program(program=program, obligations=obligations,
            candidate_catalog=catalog, query="Subtract the disclosed component from the reported result.")
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        self.assertEqual(result["outputs_by_obligation"]["net"]["normalized_value"], 100)

    def test_source_display_may_be_in_a_separate_scope_compatible_table(self):
        fixture = _source_display_program_fixture()
        for candidate, source in zip(fixture["candidate_catalog"], ("prior-table", "current-table", "summary-table")):
            candidate.update(context_fingerprint=source, table_source_id=source)
        result = execute_semantic_calculation_program(**fixture)
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        self.assertTrue(result["outputs_by_obligation"]["ob_change"]["source_stated_result_used"])

    def test_cross_source_permission_does_not_bypass_explicit_scope_conflicts(self):
        for field, conflicting in (("company", "other"), ("consolidation_scope", "separate"),
                                   ("segment", "other"), ("basis", "adjusted"), ("period", "2020")):
            with self.subTest(field=field):
                case = deepcopy(_contract_residual_fixture()["expression_compatibility"]["cases"][1])
                if field == "segment":
                    case["obligations"][0]["evidence_requirements"][1]["scope"][field] = "service"
                candidate = case["candidate_catalog"][1]
                candidate[field] = conflicting
                if field == "period":
                    candidate.update(column_headers=[conflicting], value_year=int(conflicting))
                validation = validate_semantic_calculation_program(program=case["program"],
                    obligations=case["obligations"], candidate_catalog=case["candidate_catalog"], query=case["query"])
                self.assertNotEqual(validation["status"], "ready")
                self.assertIn("candidate_requirement_scope_mismatch", {e["code"] for e in validation["errors"]})


if __name__ == "__main__":
    unittest.main()
