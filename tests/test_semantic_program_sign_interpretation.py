"""Provider-free execution contracts, not evidence of a model's formula choice."""

from __future__ import annotations

from copy import deepcopy
import json
import unittest

from tests.semantic_program_test_support import (
    FinancialAgent,
    SemanticCalculationProgram,
    _StructuredQueueLLM,
    _binding,
    _candidate,
    _obligation,
    _requirement,
    execute_semantic_calculation_program,
    semantic_candidate_catalog_fingerprint,
)


class SemanticProgramSignInterpretationTests(unittest.TestCase):
    def _run(
        self, current, prior, *, query, formula="", rationale, unit="%",
        status="ready",
    ):
        obligations = [_obligation(
            "change", "derived_value", "balance change", display_unit=unit,
            evidence_requirements=[
                _requirement("change:current", "current balance", period="2024"),
                _requirement("change:prior", "prior balance", period="2023"),
            ],
        )]
        source_text = f"balance | 2024: {current} USD | 2023: {prior} USD"
        # The shared helper uses the real normalizer; no copied normalized values.
        catalog = [
            {
                **_candidate(
                    candidate_id, raw, raw_unit="USD", period=period,
                    row_label="balance",
                ),
                "source_text": source_text,
                "physical_table_id": "balance-table",
                "physical_row_id": "balance-row",
                "physical_cell_id": candidate_id,
                "source_row_id": "balance-row",
            }
            for candidate_id, raw, period in (
                ("cand-current", current, "2024"),
                ("cand-prior", prior, "2023"),
            )
        ]
        program = SemanticCalculationProgram.model_validate({
            "status": status,
            "rationale": rationale,
            "expressions": [{
                "obligation_id": "change",
                "variable_bindings": [
                    _binding("CURRENT", "cand-current", "change:current"),
                    _binding("PRIOR", "cand-prior", "change:prior"),
                ],
                "formula": formula,
                "result_unit": unit,
                "display_unit": unit,
                "source_display_candidate_id": None,
                "source_display_reason": "The row reports inputs, not a derived result.",
            }] if formula else [],
            "missing_obligation_ids": ["change"] if status == "incomplete" else [],
            "ambiguous_obligation_ids": ["change"] if status == "ambiguous" else [],
        })
        retry_count = 0  # Valid answers and explicit evidence-insufficient decisions are terminal.
        llm = _StructuredQueueLLM(*[program] * (1 + retry_count))
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        agent.llm_routes = {}
        agent.llm_usage_callback = None
        state = {
            "query": query,
            "answer_obligations": obligations,
            "semantic_plan": {"answer_obligations": obligations},
            "semantic_candidate_catalog_prebuilt": True,
            "semantic_source_candidates": catalog,
            "semantic_candidate_catalog": catalog,
        }
        before = deepcopy(state)
        fingerprint = semantic_candidate_catalog_fingerprint(catalog)
        compiled = agent._compile_semantic_calculation_program(state)
        execution = execute_semantic_calculation_program(
            program=compiled["semantic_program"],
            obligations=obligations,
            candidate_catalog=catalog,
            query=query,
            compilation_envelope=compiled["semantic_compilation_envelope"],
            require_compilation_envelope=True,
        )
        self.assertEqual(state, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)
        self.assertEqual(compiled["semantic_program_retry_count"], retry_count)
        self.assertEqual(len(llm.prompts), 1 + retry_count)
        self.assertEqual(compiled["semantic_program"]["rationale"], rationale)
        if formula:
            self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        return compiled, execution, [prompt.to_string() for prompt in llm.prompts]

    def _assert_value(self, execution, expected):
        self.assertEqual(execution["status"], "ok")
        output = execution["outputs_by_obligation"]["change"]
        self.assertAlmostEqual(output["normalized_value"], expected)
        self.assertAlmostEqual(output["answer_slot"]["normalized_value"], expected)
        self.assertEqual(output["candidate_ids"], ["cand-current", "cand-prior"])
        return output

    def test_compiler_receives_sign_context_and_interpretation_guidance(self):
        query = "What is the percentage change in the magnitude of the balance?"
        rationale = "Compare magnitudes using the prior magnitude as denominator."
        _, execution, prompts = self._run(
            "(150)", "(100)", query=query, rationale=rationale,
            formula="(abs(CURRENT) - abs(PRIOR)) / abs(PRIOR) * 100",
        )
        self._assert_value(execution, 50)
        prompt = prompts[0]
        self.assertIn(query, prompt)
        payload = json.JSONDecoder().raw_decode(prompt.split(
            "Source bundles, candidate cohorts, and candidates_by_id:\n", 1
        )[1].lstrip())[0]
        from src.ops.compiler_fixture_transport import short_ref
        self.assertEqual(payload["candidates_by_id"][short_ref('cand-current', 'c')]["raw_value"], "(150)")
        self.assertEqual(prompt.count("balance | 2024: (150) USD | 2023: (100) USD"), 1)
        for guidance in (
            "원문 부호/배율을 유지",
            "필요한 의미 변환은 formula에 표현",
            "비교 대상과 분모를 rationale에 설명",
            "분모 0을 작은 상수로 보정하지",
        ):
            self.assertTrue(guidance in prompt, f"Compiler is missing sign guidance: {guidance}")
        self.assertNotIn(rationale, prompt)  # Stub output must not leak into input.

    def test_negative_magnitude_can_increase_or_decrease(self):
        for current, prior, expected in (
            ("(150)", "(100)", 50),
            ("(100)", "(150)", -100 / 3),
        ):
            with self.subTest(current=current, prior=prior):
                _, execution, _ = self._run(
                    current, prior,
                    query="Calculate the percentage change in balance magnitude.",
                    formula="(abs(CURRENT) - abs(PRIOR)) / abs(PRIOR) * 100",
                    rationale="Compare magnitudes; a smaller magnitude is a decrease.",
                )
                output = self._assert_value(execution, expected)
                self.assertTrue(all(row["normalized_value"] < 0 for row in output["input_rows"]))
                self.assertIn(current, execution["answer"])
                self.assertIn(prior, execution["answer"])

    def test_signed_change_is_not_rewritten_to_magnitude_change(self):
        _, execution, _ = self._run(
            "(150)", "(100)",
            query="Calculate the signed change as a percentage of the prior magnitude.",
            formula="(CURRENT - PRIOR) / abs(PRIOR) * 100",
            rationale="Keep the signed difference; only the denominator is a magnitude.",
        )
        self._assert_value(execution, -50)
        self.assertIn("-50", execution["answer"])

    def test_same_sign_pair_does_not_identify_a_unique_formula_convention(self):
        for formula in (
            "(CURRENT - PRIOR) / PRIOR * 100",
            "(abs(CURRENT) - abs(PRIOR)) / abs(PRIOR) * 100",
        ):
            with self.subTest(formula=formula):
                _, execution, _ = self._run(
                    "(150)", "(100)",
                    query="Return the specified relative change in the balance.",
                    formula=formula,
                    rationale="These conventions coincide for this same-sign negative pair.",
                )
                self._assert_value(execution, 50)

    def test_sign_transition_respects_an_explicit_question_convention(self):
        for query, formula, expected in (
            (
                "Express the signed difference relative to the signed prior balance.",
                "(CURRENT - PRIOR) / PRIOR * 100", -150,
            ),
            (
                "Express the signed difference relative to the prior balance magnitude.",
                "(CURRENT - PRIOR) / abs(PRIOR) * 100", 150,
            ),
            (
                "Express the change in magnitudes relative to the prior magnitude.",
                "(abs(CURRENT) - abs(PRIOR)) / abs(PRIOR) * 100", -50,
            ),
        ):
            with self.subTest(formula=formula):
                _, execution, _ = self._run(
                    "50", "(100)", query=query, formula=formula,
                    rationale=query,
                )
                self._assert_value(execution, expected)

    def test_zero_denominator_never_produces_an_answer_slot(self):
        for formula in (
            "(CURRENT - PRIOR) / PRIOR * 100",
            "(abs(CURRENT) - abs(PRIOR)) / abs(PRIOR) * 100",
        ):
            with self.subTest(formula=formula):
                _, execution, _ = self._run(
                    "(150)", "0", query="Calculate the relative change.",
                    formula=formula,
                    rationale="Deliberately invalid division exercises the execution boundary.",
                )
                self.assertEqual(execution["status"], "incomplete")
                self.assertEqual(execution["outputs"], [])
                self.assertEqual(execution["calculation_result"]["answer_slots"], {})
                self.assertEqual(execution["execution_errors"][0]["code"], "zero_division")

    def test_zero_prior_does_not_block_an_absolute_difference(self):
        _, execution, _ = self._run(
            "(150)", "0", query="How much did the signed balance change in USD?",
            formula="CURRENT - PRIOR", unit="USD",
            rationale="Subtract signed balances; no denominator is needed.",
        )
        self._assert_value(execution, -150)

    def test_unresolved_interpretation_does_not_invent_a_percentage(self):
        for current, prior, status, rationale in (
            ("50", "(100)", "ambiguous", "The comparison convention is not specified."),
            ("(150)", "0", "incomplete", "Relative change has a zero denominator."),
        ):
            with self.subTest(status=status):
                compiled, execution, _ = self._run(
                    current, prior, query="What is the growth rate?",
                    status=status, rationale=rationale,
                )
                self.assertEqual(compiled["semantic_program"]["expressions"], [])
                self.assertEqual(execution["status"], "incomplete")
                self.assertEqual(execution["outputs"], [])
                self.assertEqual(execution["calculation_result"]["answer_slots"], {})
                self.assertEqual(execution["execution_errors"], [])


if __name__ == "__main__":
    unittest.main()
