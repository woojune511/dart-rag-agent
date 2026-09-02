"""Provider-free contract tests for multi-output accepted answer variants."""

from __future__ import annotations

import json
import unittest
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from src.agent.financial_run_result import (
    FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
    FinancialRunResultV1,
)
from src.ops.evaluator import (
    EvalAnswerVariant,
    EvalAnswerVariantOutput,
    RAGEvaluator,
    _compute_accepted_answer_variant_match,
    _compute_completeness_judge,
    _example_from_dict,
)


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "multi_output_answer_variants.json"


def _contract_errors(contract):
    errors = []
    required_output_ids = [str(value) for value in contract.get("required_output_ids") or []]
    required_variant_fields = [
        str(value) for value in contract.get("required_variant_fields") or []
    ]
    required_output_fields = [
        str(value) for value in contract.get("required_output_fields") or []
    ]
    variants = contract.get("variants")
    if contract.get("field_name") != "accepted_answer_variants":
        errors.append("unexpected_field_name")
    if not required_output_ids or len(required_output_ids) != len(set(required_output_ids)):
        errors.append("invalid_required_output_ids")
    if not isinstance(variants, list) or not variants:
        return [*errors, "missing_variants"]

    variant_ids = [str(row.get("id") or "") for row in variants if isinstance(row, dict)]
    if len(variant_ids) != len(variants) or any(not value for value in variant_ids):
        errors.append("invalid_variant_id")
    if len(variant_ids) != len(set(variant_ids)):
        errors.append("duplicate_variant_id")

    for variant_index, variant in enumerate(variants):
        if not isinstance(variant, dict):
            errors.append(f"variant_{variant_index}_not_object")
            continue
        for field in required_variant_fields:
            if field not in variant or variant.get(field) in (None, "", []):
                errors.append(f"variant_{variant_index}_missing_{field}")
        outputs = variant.get("expected_outputs")
        if not isinstance(outputs, list) or not outputs:
            errors.append(f"variant_{variant_index}_missing_expected_outputs")
            continue
        output_ids = [
            str(row.get("output_id") or "") for row in outputs if isinstance(row, dict)
        ]
        if len(output_ids) != len(outputs) or len(output_ids) != len(set(output_ids)):
            errors.append(f"variant_{variant_index}_invalid_output_ids")
        if set(output_ids) != set(required_output_ids):
            errors.append(f"variant_{variant_index}_output_coverage_mismatch")
        for output_index, output in enumerate(outputs):
            if not isinstance(output, dict):
                errors.append(f"variant_{variant_index}_output_{output_index}_not_object")
                continue
            for field in required_output_fields:
                if field not in output or output.get(field) in (None, ""):
                    errors.append(
                        f"variant_{variant_index}_output_{output_index}_missing_{field}"
                    )
    return list(dict.fromkeys(errors))


def _normalized_value(raw_value, raw_unit):
    scale = {"%": 1.0, "백만원": 1_000_000.0}[raw_unit]
    return float(raw_value) * scale


def _materialize_case(contract, case):
    variants = {row["id"]: row for row in contract["variants"]}
    operands = []
    outputs = []
    for reference in case.get("output_refs") or []:
        variant_id, output_id = str(reference).split("/", 1)
        expected = next(
            row
            for row in variants[variant_id]["expected_outputs"]
            if row["output_id"] == output_id
        )
        actual = deepcopy(expected)
        source_token = actual.pop("source_anchor_contains")
        actual["source_anchor"] = f"[Sample issuer | 2024 | {source_token}]"
        actual.update(deepcopy((case.get("overrides") or {}).get(output_id) or {}))
        candidate_id = f"candidate-{len(outputs) + 1}"
        normalized_value = _normalized_value(actual["raw_value"], actual["raw_unit"])
        operand = {
            "operand_id": candidate_id,
            "candidate_id": candidate_id,
            "evidence_id": f"evidence-{candidate_id}",
            "label": actual["label"],
            "subject": actual["subject"],
            "subject_source": "candidate_row_identity",
            "subject_source_row_ids": [candidate_id],
            "raw_value": actual["raw_value"],
            "raw_unit": actual["raw_unit"],
            "normalized_value": normalized_value,
            "normalized_unit": actual["normalized_unit"],
            "period": actual["period"],
            "consolidation_scope": actual["consolidation_scope"],
            "source_anchor": actual["source_anchor"],
        }
        answer_slot = {
            "subject": actual["subject"],
            "period": actual["period"],
            "raw_value": actual["raw_value"],
            "raw_unit": actual["raw_unit"],
            "normalized_value": normalized_value,
            "normalized_unit": actual["normalized_unit"],
            "source_anchor": actual["source_anchor"],
            "consolidation_scope": actual["consolidation_scope"],
        }
        operands.append(operand)
        outputs.append(
            {
                "obligation_id": actual["output_id"],
                "kind": actual["kind"],
                "label": actual["label"],
                "subject": actual["subject"],
                "subject_source": "candidate_row_identity",
                "subject_source_row_ids": [candidate_id],
                "status": "ok",
                "normalized_value": normalized_value,
                "normalized_unit": actual["normalized_unit"],
                "candidate_ids": [candidate_id],
                "source_anchors": [actual["source_anchor"]],
                "answer_slot": answer_slot,
            }
        )
    return operands, {"status": "ok", "outputs": outputs}


class _FixedCompletenessJudge:
    def __init__(self):
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt)
        return SimpleNamespace(content='{"score": 0.5, "reason": "fixed fixture"}')


class _FixedAgent:
    def __init__(self, result):
        self.result = result

    def run(
        self,
        *_args,
        include_review_trace=False,
        include_debug_bundle=False,
        **_kwargs,
    ):
        return FinancialRunResultV1(
            schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
            agent_answer=deepcopy(self.result),
            review_trace={} if include_review_trace else None,
            debug_bundle={} if include_debug_bundle else None,
        )


class EvaluatorMultiOutputAnswerVariantTests(unittest.TestCase):
    def setUp(self):
        self.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
        self.contract = self.fixture["contract"]

    def test_proposed_schema_is_complete_source_qualified_and_atomic(self):
        self.assertEqual(_contract_errors(self.contract), [])
        required_ids = set(self.contract["required_output_ids"])
        display_labels = {
            "consolidated": "연결기준",
            "separate": "별도기준",
        }
        for variant in self.contract["variants"]:
            with self.subTest(variant=variant["id"]):
                self.assertEqual(
                    {row["output_id"] for row in variant["expected_outputs"]},
                    required_ids,
                )
                output_scopes = {
                    row["consolidation_scope"] for row in variant["expected_outputs"]
                }
                self.assertEqual(len(output_scopes), 1)
                self.assertIn(
                    display_labels[next(iter(output_scopes))],
                    variant["answer_key"],
                )
                for output in variant["expected_outputs"]:
                    self.assertTrue(output["subject"])
                    self.assertTrue(output["period"])
                    self.assertTrue(output["raw_unit"])
                    self.assertTrue(output["source_anchor_contains"])

    def _example(self):
        return _example_from_dict(
            {
                **deepcopy(self.fixture["example"]),
                self.contract["field_name"]: deepcopy(self.contract["variants"]),
            }
        )

    def _match(self, case, *, answer=None, example=None):
        operands, calculation_result = _materialize_case(self.contract, case)
        if answer is None:
            expected_ids = case.get("expected_variant_ids") or []
            answer = next(
                (
                    row["answer_key"]
                    for row in self.contract["variants"]
                    if row["id"] in expected_ids
                ),
                self.contract["variants"][0]["answer_key"],
            )
        return _compute_accepted_answer_variant_match(
            example=example or self._example(),
            answer=answer,
            calculation_operands=operands,
            calculation_result=calculation_result,
        )

    def _evaluate_with_trace(self, case, answer):
        example = self._example()
        before = deepcopy(example)
        operands, calculation_result = _materialize_case(self.contract, case)
        state = {
            "answer": answer,
            "format_preference": "mixed",
            "resolved_calculation_trace": {
                "calculation_operands": operands,
                "calculation_plan": {"mode": "semantic_program"},
                "calculation_result": calculation_result,
            },
        }
        judge = _FixedCompletenessJudge()
        with (
            patch(
                "src.ops.evaluator._chat_google_generative_ai",
                side_effect=AssertionError("provider construction forbidden"),
            ),
            patch(
                "src.ops.evaluator._create_embeddings",
                side_effect=AssertionError("embedding construction forbidden"),
            ),
            patch("src.ops.evaluator._compute_faithfulness", return_value=0.7),
            patch(
                "src.ops.evaluator._compute_trend_interpretation_correctness",
                return_value=(None, "not applicable"),
            ),
        ):
            evaluator = RAGEvaluator(_FixedAgent(state), skip_llm_judges=True)
            evaluator.skip_llm_judges = False
            evaluator._llm = judge
            result = evaluator.evaluate_one(example)
        return example, before, result, judge

    def test_fixed_outputs_match_only_one_complete_basis_qualified_variant(self):
        for case in self.fixture["fixed_output_cases"]:
            with self.subTest(case=case["id"]):
                operands, calculation_result = _materialize_case(self.contract, case)
                before = deepcopy((operands, calculation_result))
                score, variant_id, debug = _compute_accepted_answer_variant_match(
                    example=self._example(),
                    answer=next(
                        (
                            row["answer_key"]
                            for row in self.contract["variants"]
                            if row["id"] in (case.get("expected_variant_ids") or [])
                        ),
                        self.contract["variants"][0]["answer_key"],
                    ),
                    calculation_operands=operands,
                    calculation_result=calculation_result,
                )
                self.assertEqual(
                    debug["atomic_matched_variant_ids"],
                    case["expected_variant_ids"],
                )
                self.assertEqual(score, 1.0 if case["expected_variant_ids"] else 0.0)
                self.assertEqual(
                    variant_id,
                    case["expected_variant_ids"][0] if case["expected_variant_ids"] else "",
                )
                self.assertEqual((operands, calculation_result), before)

    def test_contract_rejects_missing_fields_duplicate_ids_and_incomplete_variants(self):
        mutations = []

        missing_source = deepcopy(self.contract)
        del missing_source["variants"][0]["expected_outputs"][0]["source_anchor_contains"]
        mutations.append(("missing_source", missing_source, "missing_source_anchor_contains"))

        duplicate_id = deepcopy(self.contract)
        duplicate_id["variants"][1]["id"] = duplicate_id["variants"][0]["id"]
        mutations.append(("duplicate_id", duplicate_id, "duplicate_variant_id"))

        missing_output = deepcopy(self.contract)
        missing_output["variants"][0]["expected_outputs"].pop()
        mutations.append(("missing_output", missing_output, "output_coverage_mismatch"))

        for name, contract, reason_fragment in mutations:
            with self.subTest(name=name):
                errors = _contract_errors(contract)
                self.assertTrue(any(reason_fragment in error for error in errors), errors)

    def test_loader_consumes_typed_variants_without_changing_scalar_answer_keys(self):
        example = self._example()
        self.assertEqual(len(example.accepted_answer_variants), 2)
        self.assertIsInstance(example.accepted_answer_variants[0], EvalAnswerVariant)
        self.assertIsInstance(
            example.accepted_answer_variants[0].expected_outputs[0],
            EvalAnswerVariantOutput,
        )
        self.assertEqual(example.accepted_calculation_variants, [])
        self.assertEqual(example.accepted_answer_keys, [example.canonical_answer_key])

    def test_loader_rejects_malformed_or_incomplete_answer_variant_contracts(self):
        invalid_payloads = []

        not_a_list = deepcopy(self.fixture["example"])
        not_a_list["accepted_answer_variants"] = {"id": "invalid"}
        invalid_payloads.append(not_a_list)

        for mutation in (
            "missing_source",
            "duplicate_variant",
            "missing_output",
            "duplicate_output",
            "unsupported_kind",
            "unexpected_field",
        ):
            payload = {
                **deepcopy(self.fixture["example"]),
                "accepted_answer_variants": deepcopy(self.contract["variants"]),
            }
            if mutation == "missing_source":
                del payload["accepted_answer_variants"][0]["expected_outputs"][0]["source_anchor_contains"]
            elif mutation == "duplicate_variant":
                payload["accepted_answer_variants"][1]["id"] = payload["accepted_answer_variants"][0]["id"]
            elif mutation == "missing_output":
                payload["accepted_answer_variants"][1]["expected_outputs"].pop()
            elif mutation == "duplicate_output":
                payload["accepted_answer_variants"][0]["expected_outputs"][1]["output_id"] = "share"
            elif mutation == "unsupported_kind":
                payload["accepted_answer_variants"][0]["expected_outputs"][0]["kind"] = "derived_value"
            else:
                payload["accepted_answer_variants"][0]["expected_outputs"][0]["typo_field"] = "ignored?"
            invalid_payloads.append(payload)

        for payload in invalid_payloads:
            with self.subTest(payload=payload.get("accepted_answer_variants")):
                with self.assertRaises(ValueError):
                    _example_from_dict(payload)

    def test_answer_and_trace_must_resolve_to_the_same_unique_variant(self):
        consolidated = self.fixture["fixed_output_cases"][0]
        consolidated_answer = self.contract["variants"][0]["answer_key"]
        separate_answer = self.contract["variants"][1]["answer_key"]
        matched, variant_id, debug = self._match(consolidated, answer=consolidated_answer)
        self.assertEqual((matched, variant_id), (1.0, "consolidated-answer"))
        self.assertEqual(debug["atomic_matched_variant_ids"], ["consolidated-answer"])

        mismatched, variant_id, debug = self._match(consolidated, answer=separate_answer)
        self.assertEqual((mismatched, variant_id), (0.0, ""))
        self.assertEqual(debug["trace_matched_variant_ids"], ["consolidated-answer"])
        self.assertEqual(debug["answer_matched_variant_ids"], ["separate-answer"])
        self.assertEqual(debug["atomic_matched_variant_ids"], [])

    def test_ambiguous_complete_trace_fails_closed(self):
        payload = {
            **deepcopy(self.fixture["example"]),
            "accepted_answer_variants": deepcopy(self.contract["variants"]),
        }
        payload["accepted_answer_variants"][1]["expected_outputs"] = deepcopy(
            payload["accepted_answer_variants"][0]["expected_outputs"]
        )
        example = _example_from_dict(payload)
        score, variant_id, debug = self._match(
            self.fixture["fixed_output_cases"][0],
            answer=self.contract["variants"][0]["answer_key"],
            example=example,
        )
        self.assertEqual((score, variant_id), (0.0, ""))
        self.assertEqual(
            debug["trace_matched_variant_ids"],
            ["consolidated-answer", "separate-answer"],
        )
        self.assertEqual(debug["reason"], "ambiguous_trace_variant_match")

    def test_hand_constructed_invalid_contract_fails_closed(self):
        example = self._example()
        example.accepted_answer_variants[0].expected_outputs[0].source_anchor_contains = []
        operands, calculation_result = _materialize_case(
            self.contract,
            self.fixture["fixed_output_cases"][0],
        )
        score, variant_id, debug = _compute_accepted_answer_variant_match(
            example=example,
            answer=self.contract["variants"][0]["answer_key"],
            calculation_operands=operands,
            calculation_result=calculation_result,
        )
        self.assertEqual((score, variant_id), (0.0, ""))
        self.assertEqual(debug["reason"], "invalid_answer_variant_contract")
        self.assertTrue(
            any("missing_source_anchor_contains" in row for row in debug["contract_errors"])
        )

        example.accepted_answer_variants = [{"id": "not-typed"}]
        score, variant_id, debug = _compute_accepted_answer_variant_match(
            example=example,
            answer=self.contract["variants"][0]["answer_key"],
            calculation_operands=operands,
            calculation_result=calculation_result,
        )
        self.assertEqual((score, variant_id), (0.0, ""))
        self.assertEqual(debug["contract_errors"], ["invalid_variant_type"])

    def test_unbound_or_extra_direct_outputs_fail_closed(self):
        case = self.fixture["fixed_output_cases"][0]
        operands, calculation_result = _materialize_case(self.contract, case)
        calculation_result["outputs"][0]["candidate_ids"] = ["not-bound"]
        score, _, debug = _compute_accepted_answer_variant_match(
            example=self._example(),
            answer=self.contract["variants"][0]["answer_key"],
            calculation_operands=operands,
            calculation_result=calculation_result,
        )
        self.assertEqual(score, 0.0)
        self.assertIn("unbound_output", debug["projection_errors"])

        operands, calculation_result = _materialize_case(self.contract, case)
        extra_operand = deepcopy(operands[0])
        extra_operand.update({"operand_id": "candidate-extra", "candidate_id": "candidate-extra"})
        extra_output = deepcopy(calculation_result["outputs"][0])
        extra_output.update({"obligation_id": "extra", "candidate_ids": ["candidate-extra"]})
        operands.append(extra_operand)
        calculation_result["outputs"].append(extra_output)
        score, _, debug = _compute_accepted_answer_variant_match(
            example=self._example(),
            answer=self.contract["variants"][0]["answer_key"],
            calculation_operands=operands,
            calculation_result=calculation_result,
        )
        self.assertEqual(score, 0.0)
        self.assertIn("actual_output_id_set_mismatch", debug["projection_errors"])

    def test_metric_label_cannot_substitute_for_validated_subject_identity(self):
        case = self.fixture["fixed_output_cases"][0]
        operands, calculation_result = _materialize_case(self.contract, case)
        operands[0]["label"] = operands[0]["subject"]
        operands[0].pop("subject")
        score, _, debug = _compute_accepted_answer_variant_match(
            example=self._example(),
            answer=self.contract["variants"][0]["answer_key"],
            calculation_operands=operands,
            calculation_result=calculation_result,
        )
        self.assertEqual(score, 0.0)
        self.assertIn("incomplete_bound_output", debug["projection_errors"])

        operands, calculation_result = _materialize_case(self.contract, case)
        operands[0]["subject_source_row_ids"] = ["not-an-operand-source"]
        score, _, debug = _compute_accepted_answer_variant_match(
            example=self._example(),
            answer=self.contract["variants"][0]["answer_key"],
            calculation_operands=operands,
            calculation_result=calculation_result,
        )
        self.assertEqual(score, 0.0)
        self.assertIn(
            "operand_subject_provenance_mismatch",
            debug["projection_errors"],
        )

    def test_completeness_reference_is_explicit_and_defaults_to_canonical(self):
        example = self._example()
        judge = _FixedCompletenessJudge()
        score, reason = _compute_completeness_judge(judge, example, "answer")
        self.assertEqual((score, reason), (0.5, "fixed fixture"))
        prompt_reference = judge.prompts[0].split("[정답 기준 요약]\n", 1)[1].split(
            "\n\n[필수 엔티티]", 1
        )[0]
        self.assertEqual(prompt_reference, example.canonical_answer_key)

        variant_reference = self.contract["variants"][0]["answer_key"]
        score, reason = _compute_completeness_judge(
            judge,
            example,
            variant_reference,
            reference_answer_key=variant_reference,
        )
        self.assertEqual((score, reason), (0.5, "fixed fixture"))
        selected_reference = judge.prompts[1].split("[정답 기준 요약]\n", 1)[1].split(
            "\n\n[필수 엔티티]", 1
        )[0]
        self.assertEqual(selected_reference, variant_reference)

    def test_evaluate_one_uses_only_the_atomic_variant_as_completeness_reference(self):
        answer = self.contract["variants"][0]["answer_key"]
        example, before, result, judge = self._evaluate_with_trace(
            self.fixture["fixed_output_cases"][0],
            answer,
        )
        self.assertEqual((result.raw_faithfulness, result.faithfulness), (0.7, 0.7))
        self.assertEqual((result.completeness, result.completeness_reason), (0.5, "fixed fixture"))
        self.assertEqual(len(judge.prompts), 1)
        self.assertIn(answer, judge.prompts[0])
        self.assertNotIn(example.canonical_answer_key, judge.prompts[0])
        self.assertEqual(example, before)

    def test_evaluate_one_uses_canonical_reference_when_answer_and_trace_differ(self):
        answer = self.contract["variants"][1]["answer_key"]
        example, before, result, judge = self._evaluate_with_trace(
            self.fixture["fixed_output_cases"][0],
            answer,
        )
        self.assertEqual((result.raw_faithfulness, result.faithfulness), (0.7, 0.7))
        self.assertEqual((result.completeness, result.completeness_reason), (0.5, "fixed fixture"))
        self.assertEqual(len(judge.prompts), 1)
        prompt_reference = judge.prompts[0].split("[정답 기준 요약]\n", 1)[1].split(
            "\n\n[필수 엔티티]", 1
        )[0]
        self.assertEqual(prompt_reference, example.canonical_answer_key)
        self.assertEqual(example, before)


if __name__ == "__main__":
    unittest.main()
