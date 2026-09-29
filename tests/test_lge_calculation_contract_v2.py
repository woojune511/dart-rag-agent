"""Source-reviewed evaluation successor; no provider or local store required."""

from copy import deepcopy
import json
from pathlib import Path
import unittest

from src.agent.financial_runtime_normalization import _normalise_operand_value
from src.ops.evaluator import (
    _compute_accepted_calculation_variant_match,
    _compute_example_numeric_equivalence,
    _example_from_dict,
    _resolve_atomic_calculation_variant_evaluation,
)


ROOT = Path(__file__).resolve().parents[1]
SUCCESSOR = ROOT / "benchmarks/datasets/reviewed/lge_t1_051_calculation_v2.json"
PREDECESSOR = ROOT / "benchmarks/datasets/single_doc_eval_full.curated.json"
FIXTURE = ROOT / "tests/fixtures/lge_calculation_source_fields_v2.json"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


class LgeCalculationContractV2Tests(unittest.TestCase):
    def setUp(self):
        self.successor = _read(SUCCESSOR)[0]
        self.predecessor = next(row for row in _read(PREDECESSOR) if row["id"] == self.successor["id"])
        self.fixture = _read(FIXTURE)
        for operand in self.fixture["calculation_operands"]:
            value, unit = _normalise_operand_value(operand["raw_value"], operand["raw_unit"])
            self.assertEqual((value, unit), (operand["normalized_value"], operand["normalized_unit"]))
            operand.update(normalized_value=value, normalized_unit=unit)

    def match(self, record=None):
        return _compute_accepted_calculation_variant_match(
            example=_example_from_dict(record or self.successor),
            **{key: self.fixture[key] for key in (
                "calculation_operands", "calculation_plan", "calculation_result")})

    def test_successor_only_changes_declared_variant_contract_and_revision_metadata(self):
        revision = self.successor["evaluation_contract_revision"]
        # Exact original bytes are checked in the local review receipt. Git may
        # change checkout line endings, so portable tests compare parsed content.
        self.assertEqual(ROOT / revision["predecessor_dataset"], PREDECESSOR)
        excluded = {"accepted_calculation_variants", "evaluation_contract_revision"}
        self.assertEqual({k: v for k, v in self.successor.items() if k not in excluded},
                         {k: v for k, v in self.predecessor.items() if k not in excluded})
        self.assertEqual(self.successor["accepted_calculation_variants"][-1],
                         self.predecessor["accepted_calculation_variants"][-1])

    def test_same_frozen_trace_fails_old_contract_and_passes_explicit_successor(self):
        before = deepcopy(self.fixture)
        self.assertEqual(self.match(self.predecessor)[0], 0.0)
        score, variant, _ = self.match()
        self.assertEqual((score, variant), (1.0, "summary_note_precise_v2"))
        self.assertEqual(self.fixture, before)

    def test_answer_and_trace_must_match_the_same_precise_variant(self):
        example = _example_from_dict(self.successor)
        score, variant, trace_debug = self.match()
        for answer, expected in (
            (self.fixture["answer"], 1.0),
            (self.fixture["answer"].replace("676,874백만원", "6,769억원"), 0.0),
        ):
            with self.subTest(answer=answer):
                equivalence, debug = _compute_example_numeric_equivalence(example=example, answer=answer)
                resolved = _resolve_atomic_calculation_variant_evaluation(
                    example=example, equivalence=equivalence, equivalence_debug=debug,
                    trace_match=score, trace_variant_id=variant, trace_debug=trace_debug)
                self.assertEqual(resolved[0], expected)

    def test_period_source_row_document_and_basis_remain_required_on_both_operands(self):
        mutations = (
            ("period", "2022"), ("period", ""), ("period", "공시금액"),
            ("row_label", "다른 항목"), ("source_period_surface", "다른 머리글"),
            ("source_document_id", "rcept_no:another-filing"),
            ("consolidation_scope", "separate"), ("consolidation_scope", ""),
            ("source_anchor", "unrelated-source"), ("statement_type", "unknown"),
            ("normalized_value", 100.0),
        )
        original = deepcopy(self.fixture)
        for index in (0, 1):
            for key, value in mutations:
                with self.subTest(operand=index, key=key, value=value):
                    self.fixture = deepcopy(original)
                    self.fixture["calculation_operands"][index][key] = value
                    self.assertEqual(self.match()[0], 0.0)

    def test_precise_operands_cannot_be_relabelled_as_rounded_management_sources(self):
        self.fixture["calculation_operands"][1]["source_anchor"] = (
            "[LG에너지솔루션 | 2023 | IV. 이사의 경영진단 및 분석의견 > 2. 개요]")
        self.assertEqual(self.match()[0], 0.0)

    def test_derived_result_still_requires_operation_value_and_all_input_ids(self):
        original = deepcopy(self.fixture)
        for key, value in (("operation_family", "sum"), ("normalized_value", 100.0),
                           ("kind", "direct_value"), ("candidate_ids", []),
                           ("candidate_ids", [original["calculation_operands"][0]["candidate_id"]])):
            with self.subTest(key=key, value=value):
                self.fixture = deepcopy(original)
                self.fixture["calculation_result"]["outputs"][-1][key] = value
                self.assertEqual(self.match()[0], 0.0)


if __name__ == "__main__":
    unittest.main()
