"""Budget-matched model comparison is diagnostic, never a relaxed release gate."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.ops.replay_reviewed_compiler_selection import (
    SemanticCalculationProgram,
    _ReviewedProgramQueue,
    _reviewed_response_queue,
    _sha256_file,
    _write_new_json,
    build_admission_manifest,
    rehearse_admission_manifest,
    run_approved_manifest,
)


FIXTURES = Path(__file__).parent / "fixtures"
RUNTIME = {"git_commit": "test", "file_count": 1, "sha256": "test"}
MODELS = ["gemini-2.5-flash", "gemini-2.5-pro"]


class CompilerModelComparisonTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        synthetic = json.loads((FIXTURES / "semantic_comparison_contrasts_v1.json").read_text(encoding="utf-8"))
        reviewed = json.loads((FIXTURES / "reviewed_runtime_replay_corpus_v2.json").read_text(encoding="utf-8"))
        self.corpus = {
            **synthetic,
            "cases": [synthetic["cases"][i] for i in (8, 3, 5)] + [reviewed["cases"][1]],
        }
        self.corpus_path = self.root / "corpus.json"
        self.manifest_path = self.root / "manifest.json"
        _write_new_json(self.corpus_path, self.corpus)

    def _prepare(self, **overrides):
        args = {
            "corpus_path": self.corpus_path,
            "manifest_path": self.manifest_path,
            "result_path": self.root / "result.json",
            "cost_cap_usd": 1.0,
            "runtime_build": RUNTIME,
            "comparison_model": MODELS[1],
        }
        manifest = build_admission_manifest(**{**args, **overrides})
        _write_new_json(self.manifest_path, manifest)
        return manifest

    def _run(self, factory):
        with patch("src.ops.replay_reviewed_compiler_selection._tracked_runtime_build", return_value=RUNTIME), patch(
            "socket.socket.connect", side_effect=AssertionError("no network"),
        ):
            return run_approved_manifest(
                self.manifest_path,
                approved_manifest_sha256=_sha256_file(self.manifest_path),
                provider_factory=factory,
            )

    def test_manifest_binds_both_models_total_cost_and_all_case_diagnostics(self):
        manifest = self._prepare()
        self.assertEqual(manifest["schema"], "reviewed_compiler_model_comparison_admission_v1")
        self.assertEqual(manifest["provider"]["models"], MODELS)
        self.assertNotIn("model", manifest["provider"])
        self.assertEqual(manifest["execution"]["initial_compiler_calls"], 8)
        self.assertEqual(manifest["execution"]["maximum_compiler_calls_with_internal_retry"], 16)
        self.assertFalse(manifest["execution"]["stop_after_first_failed_question"])
        self.assertTrue(manifest["execution"]["stop_after_provider_error"])
        self.assertTrue(manifest["acceptance"]["all_cases_match_declared_expectations"])
        prices = manifest["pricing"]["by_model"]
        self.assertEqual(prices[MODELS[1]]["input_per_million_tokens_usd"], 1.25)
        self.assertEqual(prices[MODELS[1]]["output_per_million_tokens_usd"], 10.0)
        self.assertAlmostEqual(manifest["pricing"]["retry_bounded_planning_estimate_usd"],
                               sum(p["retry_bounded_planning_estimate_usd"] for p in prices.values()))
        self.assertLess(manifest["pricing"]["retry_bounded_planning_estimate_usd"], 1.0)

    def test_old_single_model_budget_cannot_authorize_both_models(self):
        with self.assertRaisesRegex(ValueError, "cost cap"):
            self._prepare(cost_cap_usd=0.40)

    def test_rehearsal_is_byte_stable_and_model_inputs_match(self):
        self._prepare()
        with patch("src.ops.replay_reviewed_compiler_selection._tracked_runtime_build", return_value=RUNTIME), patch(
            "src.ops.replay_reviewed_compiler_selection._create_google_compiler",
            side_effect=AssertionError("no provider"),
        ), patch("socket.socket.connect", side_effect=AssertionError("no network")):
            first = rehearse_admission_manifest(self.manifest_path)
            second = rehearse_admission_manifest(self.manifest_path)
        self.assertEqual(first, second)
        self.assertEqual(first["status"], "passed")
        observation = first["observation"]
        self.assertEqual(observation["provider_network_calls"], 0)
        self.assertEqual(observation["summary"]["compiler_invocation_count"], 10)
        left, right = observation["model_results"]
        self.assertEqual(left["summary"]["prompt_fingerprint"], right["summary"]["prompt_fingerprint"])
        self.assertNotIn("elapsed_seconds", left["cases"][0])

    def test_semantic_failure_is_retained_but_does_not_hide_other_cases_or_model(self):
        self._prepare()
        seen = []
        queues = []

        def factory(spec, _callback):
            seen.append(dict(spec))
            if spec["model"] == MODELS[0]:
                # Valid signed formula, but this question explicitly leaves the convention open.
                responses = [SemanticCalculationProgram.model_validate(self.corpus["cases"][2]["program"])]
                responses += _reviewed_response_queue({**self.corpus, "cases": self.corpus["cases"][1:]})
            else:
                responses = _reviewed_response_queue(self.corpus)
            queue = _ReviewedProgramQueue(responses)
            queues.append(queue)
            return queue

        result = self._run(factory)
        self.assertEqual([s["model"] for s in seen], MODELS)
        self.assertEqual({k:v for k,v in seen[0].items() if k != "model"},
                         {k:v for k,v in seen[1].items() if k != "model"})
        self.assertEqual(result["status"], "failed")
        left, right = result["model_results"]
        self.assertEqual([left["summary"]["executed_case_count"], right["summary"]["executed_case_count"]], [4, 4])
        self.assertEqual([left["summary"]["passed_case_count"], right["summary"]["passed_case_count"]], [3, 4])
        self.assertEqual(left["cases"][0]["compiler_retry_count"], 0)
        self.assertTrue(all(q.remaining_response_count == 0 for q in queues))
        for a, b in zip(left["cases"], right["cases"], strict=True):
            self.assertEqual(a["prompt_records"][0]["prompt_sha256"], b["prompt_records"][0]["prompt_sha256"])
            self.assertGreaterEqual(a["elapsed_seconds"], 0)

    def test_provider_error_stops_remaining_cases_and_second_model(self):
        self._prepare()
        seen = []

        class BrokenQueue(_ReviewedProgramQueue):
            def invoke(self, _prompt):
                raise ConnectionError("synthetic transport failure")

        def factory(spec, _callback):
            seen.append(spec["model"])
            return BrokenQueue([])

        result = self._run(factory)
        self.assertEqual(seen, [MODELS[0]])
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["model_results"][0]["summary"]["executed_case_count"], 1)
        self.assertTrue(result["model_results"][0]["stopped_for_provider_error"])

    def test_default_single_model_gate_still_stops_at_first_semantic_failure(self):
        manifest = self._prepare(comparison_model=None)
        self.assertTrue(manifest["execution"]["stop_after_first_failed_question"])
        self.assertEqual(manifest["schema"], "reviewed_compiler_selection_admission_v2")
        wrong = SemanticCalculationProgram.model_validate(self.corpus["cases"][2]["program"])
        queue = _ReviewedProgramQueue([wrong])
        result = self._run(lambda *_args: queue)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["summary"]["executed_case_count"], 1)
        self.assertEqual(result["summary"]["compiler_invocation_count"], 1)

    def test_invalid_comparison_model_or_budget_fails_before_rehearsal(self):
        for overrides in ({"comparison_model": MODELS[0]}, {"comparison_model": "unknown"},
                          {"thinking_budget": 0}, {"thinking_budget": 24577, "max_output_tokens": 40000}):
            with self.subTest(overrides=overrides), patch(
                "src.ops.replay_reviewed_compiler_selection.rehearse_reviewed_compiler_selection",
            ) as rehearsal:
                with self.assertRaises(ValueError):
                    self._prepare(**overrides)
                rehearsal.assert_not_called()

    def test_wrong_approval_hash_cannot_create_either_provider(self):
        self._prepare()
        with patch("src.ops.replay_reviewed_compiler_selection._create_google_compiler") as factory:
            with self.assertRaisesRegex(ValueError, "approved manifest SHA-256"):
                run_approved_manifest(self.manifest_path, approved_manifest_sha256="0" * 64)
            factory.assert_not_called()

    def test_second_client_initialization_failure_preserves_completed_baseline(self):
        self._prepare()

        def factory(spec, _callback):
            if spec["model"] == MODELS[1]:
                raise ValueError("private configuration details")
            return _ReviewedProgramQueue(_reviewed_response_queue(self.corpus))

        result = self._run(factory)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["model_results"][0]["summary"]["passed_case_count"], 4)
        self.assertEqual(result["provider_initialization_error"], {"model": MODELS[1], "type": "ValueError"})
        self.assertNotIn("private configuration details", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
