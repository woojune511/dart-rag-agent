"""Authored period witnesses through model transport; no model-quality claim."""

from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program,
    validate_semantic_calculation_program,
)
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from tests.test_compiler_numeric_reading_intent import (
    AuthoredReadingLLM, compile_case, execute,
)
from tests.test_numeric_compiler_grounding import (
    QUERY, lower, output, selection, source, wire,
)
from tests.semantic_program_test_support import _obligation, _requirement, _scope
from tests.formula_wire_test_support import formula_steps


def period_cell(label="당기", *, identifier="cell", year=2037):
    candidate = source(identifier, period="")
    candidate.update(year=year, value_year=None, column_headers=["quantity"],
        source_anchor=f"[sample | {year} | quantity]",
        source_document_id="rcept_no:20380315000001")
    candidate["source_contexts"][0].update(source_text=label, source_span=[0, len(label)])
    return candidate


def choose(refs, candidate, period):
    selected = selection(refs, candidate)
    context = candidate["source_contexts"][0]
    selected["context_evidence"] = [{"context_ref": refs.ref(context["context_id"]),
        "evidence_text": context["source_text"], "supports_interpretation": False,
        "resolves": [{"field": "period", "value": period}]}]
    return selected


def validate(candidate, period):
    catalog, owners = [candidate], [output(scope=_scope(period=period))]
    setup = wire(catalog, owners)
    program = lower(choose(setup[0], candidate, period), catalog, owners, setup)
    inputs = dict(program=program, obligations=owners, candidate_catalog=catalog, query=QUERY)
    validation = validate_semantic_calculation_program(**inputs, candidate_visibility=setup[2])
    return inputs, validation, setup[2]


class CompilerRelativePeriodContractTests(unittest.TestCase):
    def test_located_relative_quote_uses_business_year_not_receipt_year(self):
        for anchor in (2037, 2024):
            for label, offset in (("당기", 0), ("전기", -1), ("전전기", -2)):
                with self.subTest(anchor=anchor, label=label):
                    candidate = period_cell(label, year=anchor)
                    before = deepcopy(candidate)
                    inputs, validation, visibility = validate(candidate, str(anchor + offset))
                    self.assertEqual(validation["status"], "ready", validation["errors"])
                    envelope = CompilationEnvelopeV2.create(
                        visibility=visibility, validation=validation, **inputs)
                    result = execute_semantic_calculation_program(**inputs,
                        compilation_envelope=envelope, require_compilation_envelope=True)
                    self.assertEqual(result["status"], "ok", result["validation"]["errors"])
                    operand = result["calculation_operands"][0]
                    self.assertEqual(operand["value_year"], anchor + offset)
                    self.assertEqual(operand["period_source"], "source_context_binding")
                    self.assertEqual(operand["raw_value"], candidate["raw_value"])
                    self.assertEqual(operand["context_resolution"]["evidence"][0]["evidence_text"], label)
                    self.assertEqual(candidate, before)

    def test_missing_business_year_cannot_be_replaced_by_authored_calendar_value(self):
        for year in (None, "", "unknown"):
            with self.subTest(year=year):
                candidate = period_cell(year=year)
                before = deepcopy(candidate)
                inputs, validation, _ = validate(candidate, "2037")
                errors = [e for e in validation["errors"] if e["code"] == "context_period_mismatch"]
                self.assertTrue(errors, validation["errors"])
                self.assertTrue(all(e["repair_action"] == "repair_program" for e in errors))
                self.assertFalse(validation["valid_direct_bindings"])
                self.assertFalse(execute_semantic_calculation_program(**inputs)["outputs_by_obligation"])
                self.assertEqual(candidate, before)

    def test_absent_or_ambiguous_quote_cannot_be_replaced_by_authored_calendar_value(self):
        for quote in ("Quantity", "당기 및 전기", "2036 / 2037"):
            with self.subTest(quote=quote):
                candidate = period_cell(quote)
                before = deepcopy(candidate)
                _, validation, _ = validate(candidate, "2037")
                self.assertIn("context_period_mismatch", [e["code"] for e in validation["errors"]])
                self.assertFalse(validation["valid_direct_bindings"])
                self.assertEqual(candidate, before)

    def test_explicit_calendar_quote_resolves_without_business_year(self):
        for year in (None, 2037):
            candidate = period_cell("2031 전기", year=year)
            _, validation, _ = validate(candidate, "2031")
            self.assertEqual(validation["status"], "ready", validation["errors"])
            proof = validation["valid_direct_bindings"][0]["context_resolution"]
            self.assertEqual(proof["scope"]["value_year"], 2031)
            self.assertEqual(proof["evidence"][0]["evidence_text"], "2031 전기")

    def test_unselected_context_and_business_year_do_not_implicitly_fill_period(self):
        candidate = period_cell()
        catalog, owners = [candidate], [output(scope=_scope(period="2037"))]
        setup = wire(catalog, owners)
        program = lower(selection(setup[0], candidate), catalog, owners, setup)
        validation = validate_semantic_calculation_program(program=program, obligations=owners,
            candidate_catalog=catalog, query=QUERY, candidate_visibility=setup[2])
        self.assertFalse(validation["valid_direct_bindings"])
        self.assertIn("candidate_scope_mismatch", [e["code"] for e in validation["errors"]])

    def test_initial_and_retry_prompts_explain_located_relative_resolution(self):
        catalog = [period_cell(identifier="now"), period_cell("전기", identifier="prior")]
        owner = _obligation("answer", "derived_value", "difference", evidence_requirements=[
            _requirement("current", "current quantity", period="2037"),
            _requirement("previous", "previous quantity", period="2036")])
        query = "Subtract the 2036 quantity from the 2037 quantity."

        def respond(refs):
            return {"inputs": {key: [{**choose(refs, candidate, period), "variable": variable}]
                for key, candidate, period, variable in zip(
                    ("current", "previous"), catalog, ("2037", "2036"), ("A", "B"))},
                "formula": formula_steps("A-B"), "comparison_request_unit_id": None,
                "display_unit": "items", "source_display": None,
                "source_display_reason": "The request asks for the calculated difference."}

        before = deepcopy((catalog, owner))
        llm = AuthoredReadingLLM(respond, invalid_first=True)
        compiled = compile_case(catalog, owner, query, llm)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(len(llm.prompts), 2)
        for prompt in llm.prompts:
            text = prompt.to_messages()[0].content
            self.assertTrue("year는 보고서의 사업연도" in text, "Explain the report-year anchor.")
            self.assertFalse("year는 공시 연도" in text, "Do not call the anchor a filing year.")
            self.assertTrue("selection.context_evidence" in text, "Require an attached exact quote.")
            self.assertTrue("상대기간" in text, "Explain source-relative periods.")
            self.assertTrue("사업연도가 없거나 기간이 모호하면" in text, "Retain uncertain periods.")
        result = execute(compiled, catalog, owner, query)
        self.assertEqual(result["status"], "ok", result["validation"]["errors"])
        self.assertEqual(result["outputs_by_obligation"]["answer"]["calculated_value"], 0)
        self.assertEqual((catalog, owner), before)


if __name__ == "__main__":
    unittest.main()
