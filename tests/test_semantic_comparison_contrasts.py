"""Offline contrast oracles and harness tests, not claims about model accuracy."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_compiler_selection import (
    _ReviewedProgramQueue,
    _reviewed_response_queue,
    _write_new_json,
    build_admission_manifest,
    evaluate_reviewed_compiler_selection,
    rehearse_reviewed_compiler_selection,
)


FIXTURE = Path(__file__).parent / "fixtures" / "semantic_comparison_contrasts_v1.json"


class _PromptQueue(_ReviewedProgramQueue):
    def __init__(self, responses):
        super().__init__(responses)
        self.prompts = []

    def invoke(self, prompt):
        self.prompts.append(prompt.to_string())
        return super().invoke(prompt)


class SemanticComparisonContrastTests(unittest.TestCase):
    def setUp(self):
        self.original_bytes = FIXTURE.read_bytes()
        self.corpus = json.loads(self.original_bytes)

    def tearDown(self):
        self.assertEqual(FIXTURE.read_bytes(), self.original_bytes)

    def _evaluate_case(self, index, program):
        corpus = {**self.corpus, "cases": [deepcopy(self.corpus["cases"][index])]}
        # A well-formed explicit abstention is terminal even if the oracle disagrees.
        model = SemanticCalculationProgram.model_validate(program)
        queue = _PromptQueue([model])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            _write_new_json(path, corpus)
            result = evaluate_reviewed_compiler_selection(path, queue, run_mode="rehearsal")
        self.assertEqual(queue.remaining_response_count, 0)
        return result["cases"][0], queue.prompts

    def test_rehearsal_is_deterministic_and_includes_explicit_abstentions(self):
        with patch("socket.socket.connect", side_effect=AssertionError("no network")), patch(
            "src.ops.replay_reviewed_compiler_selection._create_google_compiler",
            side_effect=AssertionError("no provider"),
        ):
            first = rehearse_reviewed_compiler_selection(FIXTURE)
            second = rehearse_reviewed_compiler_selection(FIXTURE)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["provider_network_calls"], 0)
        self.assertEqual(first["summary"]["passed_case_count"], 9)
        self.assertEqual(first["summary"]["compiler_island_count"], 9)
        self.assertEqual(first["summary"]["compiler_invocation_count"], 9)
        self.assertEqual(first["summary"]["compiler_retry_count"], 0)
        self.assertEqual(first["unused_reviewed_response_count"], 0)
        for index in (6, 8):
            self.assertEqual(first["cases"][index]["execution"]["outputs"], [])
            self.assertEqual(first["cases"][index]["execution"]["errors"], [])

    def test_contrast_pairs_keep_inputs_identical_and_change_only_intent(self):
        cases = self.corpus["cases"]
        for indices in ((0, 1), (3, 4, 5, 8)):
            base = cases[indices[0]]
            for index in indices[1:]:
                self.assertEqual(base["candidate_catalog"], cases[index]["candidate_catalog"])
                self.assertEqual(base["obligations"], cases[index]["obligations"])
                self.assertNotEqual(base["question"], cases[index]["question"])
        self.assertEqual(
            [cases[index]["expected"]["outputs"][0]["normalized_value"] for index in (3, 4, 5)],
            [-75, 125, -125],
        )
        self.assertEqual(cases[6]["candidate_catalog"], cases[7]["candidate_catalog"])

    def test_prompts_exclude_oracles_and_keep_shared_source_once(self):
        queue = _PromptQueue(_reviewed_response_queue(self.corpus))
        result = evaluate_reviewed_compiler_selection(FIXTURE, queue, run_mode="rehearsal")
        self.assertEqual(result["status"], "passed")
        for prompt in queue.prompts:
            self.assertNotIn("ORACLE_ONLY_", prompt)
            self.assertNotIn('"expected_normalized_value"', prompt)
            self.assertNotIn('"expected"', prompt)
            self.assertEqual(prompt.count("Synthetic balance table"), 1)
            self.assertIn("계산 해석 순서", prompt)
            self.assertIn("크기의 상대 변화", prompt)
            self.assertIn("부호 있는 차이를 이전 크기로", prompt)

    def test_valid_math_with_wrong_meaning_fails_only_the_numeric_oracle(self):
        program = deepcopy(self.corpus["cases"][0]["program"])
        # The captured failure's mechanism, with synthetic operands and no filing IDs.
        program["expressions"][0]["formula"] = "(CURRENT - PRIOR) / abs(PRIOR) * 100"
        result, prompts = self._evaluate_case(0, program)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["validation"]["status"], "ready")
        self.assertEqual(result["execution"]["status"], "ok")
        self.assertEqual(result["execution"]["outputs"][0]["normalized_value"], -50)
        self.assertEqual([key for key, ok in result["checks"].items() if not ok],
                         ["expected_outputs_match"])
        self.assertEqual(result["compiler_retry_count"], 0)
        self.assertEqual(len(prompts), 1)  # An offline oracle never triggers a runtime retry.

    def test_equivalent_formulas_are_not_rejected_by_string_comparison(self):
        program = deepcopy(self.corpus["cases"][0]["program"])
        program["expressions"][0]["formula"] = "(abs(CURRENT) / abs(PRIOR) - 1) * 100"
        result, _ = self._evaluate_case(0, program)
        self.assertEqual(result["status"], "passed")

    def test_abstention_does_not_pass_an_answerable_case(self):
        result, _ = self._evaluate_case(0, self.corpus["cases"][6]["program"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["expected_outputs_match"])
        self.assertFalse(result["checks"]["resolution_matches_expectation"])

    def test_incomplete_is_not_a_substitute_for_expected_ambiguity(self):
        result, _ = self._evaluate_case(8, self.corpus["cases"][6]["program"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["resolution_matches_expectation"])

    def test_zero_division_error_is_not_a_valid_abstention(self):
        result, _ = self._evaluate_case(6, self.corpus["cases"][0]["program"])
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["checks"]["execution_errors_zero"])
        self.assertEqual(result["execution"]["errors"][0]["code"], "zero_division")

    def test_admission_counts_islands_separately_from_rehearsal_retries(self):
        with TemporaryDirectory(dir=Path.cwd()) as directory:
            manifest = build_admission_manifest(
                corpus_path=FIXTURE,
                manifest_path=Path(directory) / "manifest.json",
                result_path=Path(directory) / "result.json",
                cost_cap_usd=1.0,
                runtime_build={"algorithm": "test"},
            )
        self.assertEqual(manifest["execution"]["initial_compiler_calls"], 9)
        self.assertEqual(manifest["execution"]["maximum_compiler_calls_with_internal_retry"], 18)
        self.assertEqual(manifest["inputs"]["rehearsal"]["compiler_invocation_count"], 9)
        self.assertTrue(manifest["acceptance"]["all_cases_match_declared_expectations"])
        self.assertEqual(manifest["transmission_scope"]["included"][0], "9 question texts")
        self.assertIn("validated read-only dependency outputs",
                      " ".join(manifest["transmission_scope"]["included"]))

    def test_abstaining_island_does_not_duplicate_an_independent_answer(self):
        case = deepcopy(self.corpus["cases"][6])
        answered = deepcopy(self.corpus["cases"][7])
        obligation = answered["obligations"][0]
        obligation["obligation_id"] = "difference"
        for requirement in obligation["evidence_requirements"]:
            requirement["requirement_id"] = requirement["requirement_id"].replace("change:", "difference:")
        expression = answered["program"]["expressions"][0]
        expression["obligation_id"] = "difference"
        for binding in expression["variable_bindings"]:
            binding["source_requirement_id"] = binding["source_requirement_id"].replace("change:", "difference:")
        case["obligations"].append(obligation)
        case["question"] += " " + answered["question"]
        case["program"]["expressions"] = [expression]
        case["expected"].update({
            "validation_status": "partial", "execution_status": "partial",
            "selected_candidate_ids": ["cand-current", "cand-prior"],
            "outputs": [{**answered["expected"]["outputs"][0], "obligation_id": "difference"}],
        })
        with TemporaryDirectory() as directory:
            path = Path(directory) / "case.json"
            _write_new_json(path, {**self.corpus, "cases": [case]})
            result = rehearse_reviewed_compiler_selection(path)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["summary"]["compiler_island_count"], 2)
        self.assertEqual(result["summary"]["compiler_invocation_count"], 2)
        self.assertEqual(result["unused_reviewed_response_count"], 0)


if __name__ == "__main__":
    unittest.main()
