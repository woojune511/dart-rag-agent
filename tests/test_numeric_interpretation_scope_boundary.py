"""Free reading labels are not source facts or a numeric execution gate."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from src.agent import financial_calculation_execution as execution
from tests.semantic_program_test_support import _candidate
from tests.test_compiler_numeric_reading_intent import (
    AuthoredReadingLLM, calculation, comparison, compile_case, execute, selection,
)


def interpreted_calculation(catalog, formula, scopes):
    def respond(refs):
        result = calculation(catalog, formula)(refs)
        for requirement, scope in zip(("current", "previous"), scopes):
            result["inputs"][requirement][0]["interpretation"]["scope"] = deepcopy(scope)
        return result
    return respond


class NumericInterpretationScopeBoundaryTests(unittest.TestCase):
    def test_period_or_other_free_labels_do_not_create_expression_conflicts(self):
        for field in ("segment", "basis"):
            for current, previous, year, labels in (
                (63, 84, 2058, ("Current period", "Previous period")),
                (-24, -48, 2048, ("scope description A", "scope description B")),
            ):
                catalog, owner = comparison(current, previous, year)
                scopes = [{field: value} for value in labels]
                for sources in (catalog, list(reversed(catalog))):
                    with self.subTest(field=field, year=year, reordered=sources != catalog):
                        before = deepcopy((sources, owner))
                        query = "Calculate the change from the previous to the current period."
                        formula = "(A-B)/abs(B)*100"
                        llm = AuthoredReadingLLM(interpreted_calculation(catalog, formula, scopes))
                        compiled = compile_case(sources, owner, query, llm)
                        result = execute(compiled, sources, owner, query)
                        self.assertEqual(result["status"], "ok")
                        self.assertEqual(compiled["semantic_program_retry_count"], 0)
                        self.assertEqual(len(llm.prompts), 1)
                        output = result["outputs_by_obligation"]["answer"]
                        self.assertAlmostEqual(output["calculated_value"], (current - previous) / abs(previous) * 100)
                        self.assertEqual(output["formula"], formula)
                        self.assertEqual([r["source_interpretation_resolution"]["scope"] for r in output["input_rows"]],
                                         [{"segment": "", "basis": "", **scope} for scope in scopes])
                        self.assertEqual((sources, owner), before)

    def test_interpretation_is_retained_without_overwriting_source_or_context_scope(self):
        catalog, owner = comparison()
        for candidate in catalog:
            candidate.update(segment="observed row grouping", basis="observed basis")
        scopes = [{"segment": "model wording", "basis": "model description"}] * 2
        query = "Compare the quantities."
        llm = AuthoredReadingLLM(interpreted_calculation(catalog, "(A-B)/abs(B)*100", scopes))
        source_checker = execution._expression_context_conflicts
        with patch.object(execution, "_expression_context_conflicts", wraps=source_checker) as observed:
            compiled = compile_case(catalog, owner, query, llm)
            result = execute(compiled, catalog, owner, query)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(observed.call_args_list)
        for call in observed.call_args_list:
            for source in call.args[0]:
                self.assertEqual(source["segment"], "observed row grouping")
                self.assertEqual(source["basis"], "observed basis")
                self.assertEqual(source["source_interpretation_resolution"]["scope"], scopes[0])

    def test_attached_scope_resolution_is_not_overwritten_by_free_labels(self):
        catalog, owner = comparison()
        for source in catalog:
            text = "Observed region data for " + source["period"]
            source.update(source_document_sha256="doc", source_table_locator="/report[1]/table[1]",
                source_contexts=[{"context_id": "heading-" + source["candidate_id"], "document_sha256": "doc",
                    "relation": "ancestor_heading", "parent_locator": "/report[1]",
                    "source_locator": "/report[1]/title[1]", "source_text": text, "source_span": [0, len(text)]}])
        def respond(refs):
            result = interpreted_calculation(catalog, "(A-B)/abs(B)*100", [{"segment": "free wording"}] * 2)(refs)
            for role, source in zip(("current", "previous"), catalog):
                context = source["source_contexts"][0]
                result["inputs"][role][0]["context_evidence"] = [{"context_ref": refs.ref(context["context_id"]),
                    "evidence_text": context["source_text"], "supports_interpretation": True,
                    "resolves": [{"field": "segment", "value": "Observed region"}]}]
            return result
        llm = AuthoredReadingLLM(respond)
        query = "Compare the reported values."
        checker = execution._expression_context_conflicts
        with patch.object(execution, "_expression_context_conflicts", wraps=checker) as observed:
            compiled = compile_case(catalog, owner, query, llm)
            result = execute(compiled, catalog, owner, query)
        self.assertEqual(result["status"], "ok")
        self.assertTrue(observed.call_args_list)
        for call in observed.call_args_list:
            for source in call.args[0]:
                self.assertEqual(source["segment"], "Observed region")
                self.assertEqual(source["context_resolution"]["scope"]["segment"], "Observed region")
                self.assertEqual(source["source_interpretation_resolution"]["scope"]["segment"], "free wording")

    def test_legacy_catalog_free_scope_labels_are_not_an_equality_gate(self):
        catalog, owner = comparison()
        catalog[0].update(segment="region description", basis="presented scope")
        catalog[1].update(segment="another description", basis="comparison scope")
        llm = AuthoredReadingLLM(calculation(catalog, "(A-B)/abs(B)*100"))
        query = "Compare the reported values."
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(execute(compiled, catalog, owner, query)["status"], "ok")
        self.assertEqual(len(llm.prompts), 1)

    def test_actual_filing_and_consolidation_conflicts_remain_blocked(self):
        for field, left, right in (
            ("company", "issuer-one", "issuer-two"),
            ("document_company", "issuer-one", "issuer-two"),
            ("consolidation_scope", "consolidated", "separate"),
        ):
            with self.subTest(field=field):
                catalog, owner = comparison()
                catalog[0][field], catalog[1][field] = left, right
                scopes = [{"segment": "shared wording", "basis": "shared wording"}] * 2
                llm = AuthoredReadingLLM(interpreted_calculation(catalog, "(A-B)/abs(B)*100", scopes))
                query = "Compare the reported values."
                compiled = compile_case(catalog, owner, query, llm)
                self.assertFalse(execute(compiled, catalog, owner, query)["outputs"])
                errors = [e for attempt in compiled["compiler_attempts"] for e in attempt["validation_errors"]]
                self.assertIn("expression_context_mismatch", {e["code"] for e in errors})

    def test_filing_metadata_precedes_legacy_local_company_text(self):
        catalog, owner = comparison()
        for candidate, subject in zip(catalog, ("unit-one", "unit-two")):
            candidate.update(company=subject, document_company="shared-issuer")
        llm = AuthoredReadingLLM(calculation(catalog, "(A-B)/abs(B)*100"))
        query = "Compare the values in this filing."
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(execute(compiled, catalog, owner, query)["status"], "ok")

    def test_source_display_keeps_its_own_interpretation_without_scope_equality(self):
        catalog, owner = comparison(125, 100)
        display = {**_candidate("reported-display", 26, raw_unit="%", normalized_unit="PERCENT", period="2051"),
            "row_headers": ["Current period"], "column_headers": ["2051", "reported change"],
            "physical_table_id": "table", "physical_row_id": catalog[0]["physical_row_id"],
            "physical_cell_id": "display-cell"}
        def respond(refs):
            result = interpreted_calculation(catalog, "(A/B-1)*100", [{"basis": "operand"}] * 2)(refs)
            result["source_display"] = selection(refs, display, "reported change")
            result["source_display"]["interpretation"]["scope"] = {"basis": "reported display"}
            result["source_display_reason"] = "The request asks for reported and calculated values."
            return result
        sources = catalog + [display]
        llm = AuthoredReadingLLM(respond)
        query = "Return reported change alongside calculated change."
        compiled = compile_case(sources, owner, query, llm)
        result = execute(compiled, sources, owner, query)
        self.assertEqual(result["status"], "ok")
        output = result["outputs_by_obligation"]["answer"]
        self.assertEqual(output["answer_slot"]["normalized_value"], 26)
        self.assertEqual(output["display_value"], 26)
        self.assertEqual(output["calculated_value"], 25)
        self.assertEqual(output["source_display_candidate_id"], display["candidate_id"])
        self.assertEqual(len(llm.prompts), 1)

    def test_wrong_direction_is_not_repaired_when_free_scope_no_longer_blocks_it(self):
        catalog, owner = comparison()
        scopes = [{"basis": "Current period"}, {"basis": "Previous period"}]
        llm = AuthoredReadingLLM(interpreted_calculation(catalog, "(A-B)/abs(B)*100", scopes))
        query = "Calculate the change from the current to the previous period."
        compiled = compile_case(catalog, owner, query, llm)
        result = execute(compiled, catalog, owner, query)
        self.assertEqual(result["status"], "ok")  # Structural success is not meaning.
        self.assertEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], -20)
        self.assertNotEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], 25)

    def test_interpretation_scope_tampering_still_fails_before_execution(self):
        catalog, owner = comparison()
        llm = AuthoredReadingLLM(calculation(catalog, "(A-B)/abs(B)*100"))
        query = "Compare the values."
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(execute(compiled, catalog, owner, query)["status"], "ok")
        compiled["semantic_program"] = deepcopy(compiled["semantic_program"])
        compiled["semantic_program"]["expressions"][0]["variable_bindings"][0]["source_interpretation"]["scope"] = {"basis": "edited after validation"}
        self.assertEqual(execute(compiled, catalog, owner, query)["outputs"], [])


if __name__ == "__main__":
    unittest.main()
