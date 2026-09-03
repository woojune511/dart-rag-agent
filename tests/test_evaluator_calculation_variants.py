import json
import unittest
from pathlib import Path

from src.ops.evaluator import (
    EvalCalculationVariant,
    EvalExample,
    _compute_accepted_calculation_variant_match,
    _compute_example_numeric_equivalence,
    _compute_numeric_evaluation,
    _example_from_dict,
)
from src.ops.replay_full_eval_from_results import _score_row


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _variant(
    *,
    variant_id: str,
    answer_key: str,
    anchor: str,
    left_value: str,
    right_value: str,
    result_value: str,
    unit: str,
    strict_labels: bool,
) -> EvalCalculationVariant:
    return EvalCalculationVariant(
        id=variant_id,
        answer_key=answer_key,
        expected_operands=[
            {
                "label": "Closing measure",
                "strict_label": strict_labels,
                "period": "2024",
                "raw_value": left_value,
                "raw_unit": unit,
                "source_anchor_contains": anchor,
                "statement_type": "notes" if strict_labels else "narrative",
                "consolidation_scope": "consolidated",
            },
            {
                "label": "Opening measure",
                "strict_label": strict_labels,
                "period": "2024",
                "raw_value": right_value,
                "raw_unit": unit,
                "source_anchor_contains": anchor,
                "statement_type": "notes" if strict_labels else "narrative",
                "consolidation_scope": "consolidated",
            },
        ],
        expected_operation="difference",
        expected_calculation_result={
            "label": "Adjusted measure",
            "strict_label": strict_labels,
            "raw_value": result_value,
            "raw_unit": unit,
            "operation_family": "difference",
            "source_anchor_contains": anchor,
        },
    )


def _example() -> EvalExample:
    return EvalExample(
        id="generic_variant_case",
        question="Calculate the adjusted measure.",
        ground_truth="Closing 4억원 minus opening 3억원 is 1억원.",
        answer_key="Closing 4억원 minus opening 3억원 is 1억원.",
        company="Sample issuer",
        year=2024,
        section="Sample section",
        answer_type="numeric",
        category="numeric_fact",
        accepted_calculation_variants=[
            _variant(
                variant_id="table_precise",
                answer_key="Closing 380백만원 minus opening 343백만원 is 37백만원.",
                anchor="precise-note",
                left_value="380",
                right_value="343",
                result_value="37",
                unit="백만원",
                strict_labels=True,
            ),
            _variant(
                variant_id="discussion_rounded",
                answer_key="Closing 4억원 minus opening 3억원 is 1억원.",
                anchor="rounded-discussion",
                left_value="4",
                right_value="3",
                result_value="1",
                unit="억원",
                strict_labels=False,
            ),
        ],
    )


def _operand(
    *,
    candidate_id: str,
    label: str,
    raw_value: str,
    raw_unit: str,
    normalized_value: float,
    anchor: str,
    statement_type: str,
) -> dict:
    return {
        "operand_id": candidate_id,
        "candidate_id": candidate_id,
        "label": label,
        "period": "2024",
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "normalized_value": normalized_value,
        "normalized_unit": "KRW",
        "source_anchor": f"[Sample issuer | 2024 | {anchor}]",
        "source_row_id": f"row-{candidate_id}",
        "statement_type": statement_type,
        "consolidation_scope": "consolidated",
    }


def _trace(*, precise: bool = True, hybrid: bool = False, wrong_anchor: bool = False):
    if precise:
        left_anchor = "wrong-note" if wrong_anchor else "precise-note"
        right_anchor = "rounded-discussion" if hybrid else left_anchor
        left = _operand(
            candidate_id="cand-left",
            label="Closing measure",
            raw_value="380",
            raw_unit="백만원",
            normalized_value=380_000_000.0,
            anchor=left_anchor,
            statement_type="notes",
        )
        right = _operand(
            candidate_id="cand-right",
            label="Opening measure",
            raw_value="343",
            raw_unit="백만원",
            normalized_value=343_000_000.0,
            anchor=right_anchor,
            statement_type="narrative" if hybrid else "notes",
        )
        result_value = 37_000_000.0
        result_unit = "백만원"
        result_anchor = left_anchor
    else:
        left = _operand(
            candidate_id="cand-left",
            label="Closing measure",
            raw_value="4",
            raw_unit="억원",
            normalized_value=400_000_000.0,
            anchor="rounded-discussion",
            statement_type="narrative",
        )
        right = _operand(
            candidate_id="cand-right",
            label="Opening measure",
            raw_value="3",
            raw_unit="억원",
            normalized_value=300_000_000.0,
            anchor="rounded-discussion",
            statement_type="narrative",
        )
        result_value = 100_000_000.0
        result_unit = "억원"
        result_anchor = "rounded-discussion"

    plan = {
        "mode": "semantic_program",
        "operation_family": "lookup",
        "ordered_operand_ids": ["cand-left", "cand-right"],
    }
    result = {
        "status": "ok",
        "result_value": left["normalized_value"],
        "result_unit": left["raw_unit"],
        "operation_family": "lookup",
        "outputs": [
            {
                "obligation_id": "left",
                "kind": "direct_value",
                "label": "Closing measure",
                "status": "ok",
                "normalized_value": left["normalized_value"],
                "normalized_unit": "KRW",
                "result_unit": left["raw_unit"],
                "candidate_ids": ["cand-left"],
                "source_anchors": [left["source_anchor"]],
                "operation_family": "lookup",
            },
            {
                "obligation_id": "right",
                "kind": "direct_value",
                "label": "Opening measure",
                "status": "ok",
                "normalized_value": right["normalized_value"],
                "normalized_unit": "KRW",
                "result_unit": right["raw_unit"],
                "candidate_ids": ["cand-right"],
                "source_anchors": [right["source_anchor"]],
                "operation_family": "lookup",
            },
            {
                "obligation_id": "adjusted",
                "kind": "derived_value",
                "label": "Adjusted measure",
                "status": "ok",
                "normalized_value": result_value,
                "normalized_unit": "KRW",
                "result_unit": result_unit,
                "candidate_ids": ["cand-left", "cand-right"],
                "source_row_ids": ["row-cand-left", "row-cand-right"],
                "source_anchors": [f"[Sample issuer | 2024 | {result_anchor}]"],
                "operation_family": "difference",
            },
        ],
    }
    return [left, right], plan, result


class AcceptedCalculationVariantContractTests(unittest.TestCase):
    def test_loader_keeps_legacy_single_answer_contract(self) -> None:
        example = _example_from_dict(
            {
                "id": "legacy",
                "question": "What is the value?",
                "answer_key": "10억원",
                "company": "Sample issuer",
                "year": 2024,
                "section": "Sample section",
            }
        )

        self.assertEqual(example.accepted_calculation_variants, [])
        self.assertEqual(example.accepted_answer_keys, ["10억원"])

    def test_loader_preserves_typed_variants(self) -> None:
        variant = _example().accepted_calculation_variants[0]
        example = _example_from_dict(
            {
                "id": "typed",
                "question": "Calculate.",
                "answer_key": "legacy 1억원",
                "company": "Sample issuer",
                "year": 2024,
                "section": "Sample section",
                "accepted_calculation_variants": [
                    {
                        "id": variant.id,
                        "answer_key": variant.answer_key,
                        "expected_operands": variant.expected_operands,
                        "expected_operation": variant.expected_operation,
                        "expected_calculation_result": variant.expected_calculation_result,
                    }
                ],
            }
        )

        self.assertIsInstance(example.accepted_calculation_variants[0], EvalCalculationVariant)
        self.assertEqual(example.accepted_calculation_variants[0].id, "table_precise")
        self.assertEqual(len(example.accepted_answer_keys), 2)

    def test_loader_rejects_non_list_variant_contract(self) -> None:
        with self.assertRaisesRegex(ValueError, "must be a list"):
            _example_from_dict(
                {
                    "id": "malformed",
                    "question": "Calculate.",
                    "answer_key": "1억원",
                    "company": "Sample issuer",
                    "year": 2024,
                    "section": "Sample section",
                    "accepted_calculation_variants": {"id": "not-a-list"},
                }
            )

    def test_precise_semantic_program_output_matches_atomically(self) -> None:
        operands, plan, result = _trace(precise=True)

        score, variant_id, debug = _compute_accepted_calculation_variant_match(
            example=_example(),
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
        )

        self.assertEqual(score, 1.0)
        self.assertEqual(variant_id, "table_precise")
        self.assertEqual(debug["matched_variant_ids"], ["table_precise"])

    def test_rounded_semantic_program_output_matches_atomically(self) -> None:
        operands, plan, result = _trace(precise=False)

        score, variant_id, _ = _compute_accepted_calculation_variant_match(
            example=_example(),
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
        )

        self.assertEqual(score, 1.0)
        self.assertEqual(variant_id, "discussion_rounded")

    def test_hybrid_operands_cannot_cherry_pick_across_variants(self) -> None:
        operands, plan, result = _trace(precise=True, hybrid=True)

        score, variant_id, debug = _compute_accepted_calculation_variant_match(
            example=_example(),
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(variant_id, "")
        self.assertEqual(debug["matched_variant_ids"], [])

    def test_equal_values_with_wrong_source_context_fail_closed(self) -> None:
        operands, plan, result = _trace(precise=True, wrong_anchor=True)

        score, variant_id, _ = _compute_accepted_calculation_variant_match(
            example=_example(),
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(variant_id, "")

    def test_result_must_bind_every_selected_candidate(self) -> None:
        operands, plan, result = _trace(precise=True)
        result["outputs"][-1]["candidate_ids"] = ["cand-left"]

        score, variant_id, debug = _compute_accepted_calculation_variant_match(
            example=_example(),
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(variant_id, "")
        reasons = [
            reason
            for row in debug["variants"][0]["results"]
            for reason in row["reasons"]
        ]
        self.assertIn("result_not_bound_to_all_matched_operands", reasons)

    def test_distinct_operand_assignment_is_not_greedy(self) -> None:
        variant = EvalCalculationVariant(
            id="duplicate_value_rows",
            answer_key="Both inputs are 100백만원 and the difference is 0백만원.",
            expected_operands=[
                {
                    "label": "Either row",
                    "period": "2024",
                    "raw_value": "100",
                    "raw_unit": "백만원",
                    "source_anchor_contains": "same-note",
                },
                {
                    "label": "Specific row",
                    "strict_label": True,
                    "period": "2024",
                    "raw_value": "100",
                    "raw_unit": "백만원",
                    "source_anchor_contains": "same-note",
                },
            ],
            expected_operation="difference",
            expected_calculation_result={
                "label": "Difference",
                "strict_label": True,
                "raw_value": "0",
                "raw_unit": "백만원",
                "operation_family": "difference",
                "source_anchor_contains": "same-note",
            },
        )
        example = _example()
        example.accepted_calculation_variants = [variant]
        operands = [
            _operand(
                candidate_id="specific",
                label="Specific row",
                raw_value="100",
                raw_unit="백만원",
                normalized_value=100_000_000.0,
                anchor="same-note",
                statement_type="notes",
            ),
            _operand(
                candidate_id="other",
                label="Other row",
                raw_value="100",
                raw_unit="백만원",
                normalized_value=100_000_000.0,
                anchor="same-note",
                statement_type="notes",
            ),
        ]
        result = {
            "status": "ok",
            "outputs": [
                {
                    "label": "Difference",
                    "status": "ok",
                    "normalized_value": 0.0,
                    "normalized_unit": "KRW",
                    "result_unit": "백만원",
                    "candidate_ids": ["specific", "other"],
                    "source_anchors": ["[Sample issuer | 2024 | same-note]"],
                    "operation_family": "difference",
                }
            ],
        }

        score, variant_id, _ = _compute_accepted_calculation_variant_match(
            example=example,
            calculation_operands=operands,
            calculation_plan={"operation_family": "lookup"},
            calculation_result=result,
        )

        self.assertEqual(score, 1.0)
        self.assertEqual(variant_id, "duplicate_value_rows")

    def test_numeric_gate_requires_answer_and_trace_to_match_same_variant(self) -> None:
        operands, plan, result = _trace(precise=True, wrong_anchor=True)
        evaluation = _compute_numeric_evaluation(
            llm=None,
            example=_example(),
            answer="Closing 380백만원 minus opening 343백만원 is 37백만원.",
            runtime_evidence=[{"claim": "Closing 380백만원; opening 343백만원"}],
            contexts=[],
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
            retrieval_hit_at_k=1.0,
            deterministic_grounding_only=True,
        )

        self.assertEqual(evaluation["numeric_equivalence"], 0.0)
        self.assertEqual(evaluation["accepted_calculation_variant_match"], 0.0)
        self.assertEqual(evaluation["numeric_final_judgement"], "FAIL")

    def test_variant_answer_requires_every_numeric_claim(self) -> None:
        score, debug = _compute_example_numeric_equivalence(
            example=_example(),
            answer="The adjusted measure is 37백만원.",
        )

        self.assertEqual(score, 0.0)
        self.assertEqual(debug["matched_variant_ids"], [])

    def test_mixed_precision_answer_cannot_pair_with_precise_trace(self) -> None:
        operands, plan, result = _trace(precise=True)
        evaluation = _compute_numeric_evaluation(
            llm=None,
            example=_example(),
            answer="Closing 380백만원 minus opening 343백만원 is 1억원.",
            runtime_evidence=[{"claim": "Closing 380백만원; opening 343백만원"}],
            contexts=[],
            calculation_operands=operands,
            calculation_plan=plan,
            calculation_result=result,
            retrieval_hit_at_k=1.0,
            deterministic_grounding_only=True,
        )

        self.assertEqual(evaluation["numeric_equivalence"], 0.0)
        self.assertEqual(evaluation["accepted_calculation_variant_match"], 0.0)
        self.assertEqual(evaluation["numeric_final_judgement"], "FAIL")

    def test_no_call_replay_uses_the_same_atomic_variant_contract(self) -> None:
        operands, plan, result = _trace(precise=True)
        row = {
            "id": "generic_variant_case",
            "answer": "Closing 380백만원 minus opening 343백만원 is 37백만원.",
            "numeric_final_judgement": "PASS",
            "numeric_grounding": 1.0,
            "numeric_confidence": 1.0,
            "retrieval_hit_at_k": 1.0,
            "runtime_evidence": [{"claim": "Closing 380백만원; opening 343백만원"}],
            "calculation_operands": operands,
            "calculation_plan": plan,
            "calculation_result": result,
        }

        replayed = _score_row(row, {"generic_variant_case": _example()})

        self.assertEqual(replayed["numeric_final_judgement"], "PASS")
        self.assertEqual(replayed["accepted_calculation_variant_match"], 1.0)
        self.assertEqual(replayed["accepted_calculation_variant_id"], "table_precise")


class CuratedCalculationVariantDataTests(unittest.TestCase):
    def test_curated_lge_variants_are_identical_across_dataset_slices(self) -> None:
        paths = [
            PROJECT_ROOT / "benchmarks/datasets/single_doc_eval_full.curated.json",
            PROJECT_ROOT / "benchmarks/datasets/single_doc_eval_multi_metric_numeric.curated.json",
            PROJECT_ROOT / "benchmarks/datasets/single_doc_eval_multi_subtask.curated.json",
        ]
        records = []
        for path in paths:
            payload = json.loads(path.read_text(encoding="utf-8"))
            records.append(next(row for row in payload if row.get("id") == "LGE_T1_051"))

        variants = records[0]["accepted_calculation_variants"]
        self.assertEqual(
            [variant["id"] for variant in variants],
            ["connected_note_precise", "management_discussion_rounded"],
        )
        self.assertTrue(
            any("676,874" in evidence["quote"] for evidence in records[0]["evidence"])
        )
        for record in records[1:]:
            self.assertEqual(record["accepted_calculation_variants"], variants)
            self.assertEqual(record["evidence"], records[0]["evidence"])


if __name__ == "__main__":
    unittest.main()
