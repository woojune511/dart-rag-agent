"""Compiler admission controls, not changes to runtime/evaluator acceptance."""

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from tests.request_unit_fixture_support import bind_fixture_requests

from src.ops.replay_reviewed_compiler_selection import (
    _ReviewedProgramQueue, _reviewed_response_queue, _write_new_json,
    build_admission_manifest, evaluate_reviewed_compiler_selection, rehearse_reviewed_compiler_selection,
)


FIXTURE = Path(__file__).parent / "fixtures/reviewed_runtime_replay_corpus_v3.json"


class CompilerReviewExpectationTests(unittest.TestCase):
    def narrative_corpus(self):
        corpus = bind_fixture_requests(json.loads(FIXTURE.read_text(encoding="utf-8")))
        case = deepcopy(corpus["cases"][1])
        case["obligations"] = [case["obligations"][1]]
        case["obligations"][0]["coupling_key"] = ""
        case["program"]["expressions"] = []
        case["expected"] = {
            "selection_policy": "runtime_validated_narrative",
            "outputs": [{"obligation_id": "credit_loss_reason", "kind": "narrative", "status": "ok"}],
        }
        # An equivalent source is legal: the harness must not force the witness ID.
        source = next(c for c in case["candidate_catalog"] if c["kind"] == "narrative")
        alternative = deepcopy(source)
        alternative["candidate_id"] += "_alternative"
        case["candidate_catalog"].append(alternative)
        corpus["cases"] = [case]
        return corpus

    def evaluate(self, corpus, response_corpus=None):
        with TemporaryDirectory() as folder:
            path = Path(folder) / "corpus.json"
            _write_new_json(path, corpus)
            if response_corpus is None:
                return rehearse_reviewed_compiler_selection(path)
            return evaluate_reviewed_compiler_selection(
                path, _ReviewedProgramQueue(_reviewed_response_queue(response_corpus)), run_mode="rehearsal",
            )

    def test_alternative_narrative_source_passes_contract_with_review_still_pending(self):
        corpus = self.narrative_corpus()
        response = deepcopy(corpus)
        binding = response["cases"][0]["program"]["narrative_bindings"][0]
        binding["candidate_ids"][0] += "_alternative"
        binding["evidence_bindings"][0]["candidate_id"] += "_alternative"
        binding["claims"][0]["evidence_bindings"][0]["candidate_id"] += "_alternative"
        result = self.evaluate(corpus, response)
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["cases"][0]["acceptance_scope"], "runtime_contract_only")
        self.assertEqual(result["summary"]["semantic_review_pending_case_count"], 1)

    def test_exact_set_default_still_rejects_alternative(self):
        corpus = self.narrative_corpus()
        expected = corpus["cases"][0]["expected"]
        expected.pop("selection_policy")
        expected["selected_candidate_ids"] = ["not_the_witness"]
        result = self.evaluate(corpus)
        self.assertEqual(result["status"], "failed")
        self.assertFalse(result["cases"][0]["checks"]["selected_candidate_ids_expected"])

    def test_manifest_keeps_semantic_review_pending_after_narrative_contract_pass(self):
        with TemporaryDirectory(dir=Path.cwd()) as folder:
            path = Path(folder)
            _write_new_json(path / "corpus.json", self.narrative_corpus())
            manifest = build_admission_manifest(
                corpus_path=path / "corpus.json", manifest_path=path / "manifest.json",
                result_path=path / "result.json", cost_cap_usd=0.20, runtime_build={"algorithm": "test"},
            )
        self.assertEqual(len(manifest["acceptance"]["semantic_review_pending_question_ids"]), 1)
        self.assertEqual(manifest["acceptance"]["selected_candidate_set_matches_review"], "per_case_selection_policy")
        self.assertIn("semantic source review pending", manifest["claim_boundary"])

    def test_narrative_policy_does_not_allow_hidden_id(self):
        corpus = self.narrative_corpus()
        binding = corpus["cases"][0]["program"]["narrative_bindings"][0]
        binding["candidate_ids"] = ["hidden_candidate"]
        binding["evidence_bindings"][0]["candidate_id"] = "hidden_candidate"
        binding["claims"][0]["evidence_bindings"][0]["candidate_id"] = "hidden_candidate"
        result = self.evaluate(corpus)
        self.assertEqual(result["status"], "failed")
        self.assertNotEqual(result["cases"][0]["validation"]["status"], "ready")
        self.assertEqual(result["cases"][0]["execution"]["outputs"], [])

    def test_narrative_policy_cannot_relax_numeric_case(self):
        corpus = self.narrative_corpus()
        corpus["cases"][0]["obligations"][0]["kind"] = "direct_value"
        with self.assertRaisesRegex(ValueError, "narrative-only"):
            self.evaluate(corpus, {"cases": []})

    def test_conflicting_or_unknown_selection_policy_is_rejected(self):
        for policy, extra in (("not_a_policy", {}), ("runtime_validated_narrative", {"selected_candidate_ids": []})):
            corpus = self.narrative_corpus()
            corpus["cases"][0]["expected"].update(selection_policy=policy, **extra)
            with self.subTest(policy=policy), self.assertRaises(ValueError):
                self.evaluate(corpus, {"cases": []})

    def test_declared_missing_or_ambiguous_resolution_does_not_admit_a_resolved_output(self):
        corpus = self.narrative_corpus()
        case = corpus["cases"][0]
        owner = case["obligations"][0]["obligation_id"]
        case["expected"] = {
            "validation_status": "invalid", "execution_status": "incomplete", "outputs": [],
            "selected_candidate_ids": [],
            "resolution_options": [{"missing_obligation_ids": [owner]},
                {"missing_obligation_ids": [owner], "ambiguous_obligation_ids": [owner]}],
        }
        # A resolved answer is not one of the declared abstention alternatives.
        self.assertEqual(self.evaluate(corpus)["status"], "failed")
        case["program"].update(status="incomplete", narrative_bindings=[], missing_obligation_ids=[owner])
        missing = self.evaluate(corpus)
        self.assertEqual(missing["status"], "passed")
        case["program"].update(missing_obligation_ids=[], ambiguous_obligation_ids=[owner])
        ambiguous = self.evaluate(corpus)
        self.assertEqual(ambiguous["status"], "passed")
        case["expected"]["resolution_options"] = [{"missing_obligation_ids": [owner]}]
        self.assertFalse(self.evaluate(corpus)["cases"][0]["checks"]["resolution_matches_expectation"])


if __name__ == "__main__":
    unittest.main()
