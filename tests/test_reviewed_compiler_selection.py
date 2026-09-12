from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests.request_unit_fixture_support import request_bound_fixture

from src.ops.replay_reviewed_compiler_selection import (
    _canonical_bytes,
    _sha256_bytes,
    _sha256_file,
    _write_new_json,
    build_admission_manifest,
    main,
    rehearse_admission_manifest,
    rehearse_reviewed_compiler_selection,
    run_approved_manifest,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "reviewed_runtime_replay_corpus_v3.json"
)


class ReviewedCompilerSelectionTests(unittest.TestCase):
    def setUp(self):
        self.fixture_path = request_bound_fixture(self, FIXTURE_PATH)

    def test_rehearsal_runs_actual_compiler_contract_without_provider(self) -> None:
        first = rehearse_reviewed_compiler_selection(self.fixture_path)
        second = rehearse_reviewed_compiler_selection(self.fixture_path)

        self.assertEqual(first, second)
        self.assertEqual(first["status"], "passed")
        self.assertEqual(first["provider_network_calls"], 0)
        self.assertEqual(first["retrieval_calls"], 0)
        self.assertEqual(first["planner_calls"], 0)
        self.assertEqual(first["evaluator_calls"], 0)
        self.assertEqual(first["embedding_calls"], 0)
        self.assertEqual(first["store_writes"], 0)
        self.assertEqual(first["summary"]["configured_case_count"], 5)
        self.assertEqual(first["summary"]["passed_case_count"], 5)
        self.assertEqual(first["summary"]["compiler_island_count"], 6)
        self.assertEqual(first["summary"]["compiler_invocation_count"], 6)
        self.assertEqual(first["summary"]["compiler_retry_count"], 0)
        self.assertEqual(first["unused_reviewed_response_count"], 0)
        self.assertGreater(first["summary"]["prompt_bytes"], 0)
        for case in first["cases"]:
            attempts = case["compiler_attempts"]
            self.assertEqual(len(attempts), len(case["prompt_records"]))
            self.assertTrue(all(row["response_status"] == "parsed" for row in attempts))
            self.assertTrue(all(row["model_program_json"] for row in attempts))

    def test_manifest_rehearsal_binds_runtime_corpus_and_prompt(self) -> None:
        runtime_build = {
            "algorithm": "test",
            "git_commit": "test-commit",
            "file_count": 1,
            "sha256": "test-runtime",
            "tracked_worktree_clean": True,
        }
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            result_path = root / "provider-result.json"
            manifest = build_admission_manifest(
                corpus_path=self.fixture_path,
                manifest_path=manifest_path,
                result_path=result_path,
                cost_cap_usd=0.20,
                runtime_build=runtime_build,
            )
            self.assertEqual(manifest["execution"]["initial_compiler_calls"], 6)
            self.assertEqual(
                manifest["execution"]["maximum_compiler_calls_with_internal_retry"],
                12,
            )
            self.assertEqual(manifest["provider"]["provider_client_retries"], 0)
            self.assertEqual(manifest["provider"]["max_output_tokens"], 4096)
            self.assertEqual(manifest["provider"]["thinking_budget"], 1024)
            self.assertEqual(manifest["schema"], "reviewed_compiler_selection_admission_v2")
            self.assertGreater(manifest["pricing"]["retry_bounded_planning_estimate_usd"], 0.12)
            self.assertFalse(manifest["provider"]["credential_value_recorded"])
            self.assertEqual(manifest["inputs"]["runtime_build"], runtime_build)
            self.assertTrue(
                all(
                    "program" not in item
                    for item in manifest["transmission_scope"]["included"]
                )
            )
            self.assertIn(
                "reviewed expected programs and answers",
                manifest["transmission_scope"]["excluded"],
            )
            _write_new_json(manifest_path, manifest)
            with patch(
                "src.ops.replay_reviewed_compiler_selection._tracked_runtime_build",
                return_value=runtime_build,
            ):
                first = rehearse_admission_manifest(manifest_path)
                second = rehearse_admission_manifest(manifest_path)
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "passed")
            self.assertEqual(first["observation"]["provider_network_calls"], 0)

    def test_wrong_approval_hash_stops_before_provider_factory(self) -> None:
        runtime_build = {
            "algorithm": "test",
            "git_commit": "test-commit",
            "file_count": 1,
            "sha256": "test-runtime",
            "tracked_worktree_clean": True,
        }
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            root = Path(temp_dir)
            manifest_path = root / "manifest.json"
            result_path = root / "provider-result.json"
            manifest = build_admission_manifest(
                corpus_path=self.fixture_path,
                manifest_path=manifest_path,
                result_path=result_path,
                cost_cap_usd=0.20,
                runtime_build=runtime_build,
            )
            _write_new_json(manifest_path, manifest)
            calls = []

            def provider_factory(*_args):
                calls.append(True)
                raise AssertionError("provider factory must not run")

            with self.assertRaisesRegex(ValueError, "approved manifest SHA-256"):
                run_approved_manifest(
                    manifest_path,
                    approved_manifest_sha256="0" * 64,
                    provider_factory=provider_factory,
                )
            self.assertEqual(calls, [])
            self.assertNotEqual(_sha256_file(manifest_path), "0" * 64)

    def test_rehearsal_response_unavailable_and_prompt_hash_excludes_responses(self) -> None:
        result = rehearse_reviewed_compiler_selection(self.fixture_path)
        records = [record for case in result["cases"] for record in case["prompt_records"]]
        for record in records:
            self.assertFalse(record["response"]["raw_response_available"])
            self.assertIsNone(record["response"]["final_text"])
            self.assertIsNone(record["response"]["finish_reason"])
            self.assertIsNone(record["response"]["usage"])
        prompts_only = [{
            "prompt_bytes": record["prompt_bytes"],
            "prompt_sha256": record["prompt_sha256"],
        } for record in records]
        self.assertEqual(result["summary"]["prompt_fingerprint"],
                         _sha256_bytes(_canonical_bytes(prompts_only)))

    def test_configurable_budgets_change_estimate_and_cannot_reuse_old_cap(self) -> None:
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            args = {
                "corpus_path": self.fixture_path,
                "manifest_path": Path(temp_dir) / "manifest.json",
                "result_path": Path(temp_dir) / "result.json",
                "runtime_build": {"algorithm": "test"},
            }
            with self.assertRaisesRegex(ValueError, "cost cap"):
                build_admission_manifest(**args, cost_cap_usd=0.12)
            smaller = build_admission_manifest(
                **args, cost_cap_usd=0.12, max_output_tokens=2048, thinking_budget=512,
            )
            larger = build_admission_manifest(**args, cost_cap_usd=0.20)
            # The total output cap includes thinking; do not add it a second time.
            self.assertAlmostEqual(
                larger["pricing"]["retry_bounded_planning_estimate_usd"]
                - smaller["pricing"]["retry_bounded_planning_estimate_usd"],
                12 * 2048 / 1_000_000 * 2.5,
            )
            self.assertGreater(larger["pricing"]["likely_estimate_usd"],
                               smaller["pricing"]["likely_estimate_usd"])
            self.assertEqual(smaller["provider"]["max_output_tokens"], 2048)
            self.assertEqual(smaller["provider"]["thinking_budget"], 512)

    def test_missing_budget_stops_before_provider_factory(self) -> None:
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            _write_new_json(manifest_path, {
                "schema": "reviewed_compiler_selection_admission_v2",
                "provider": {"max_output_tokens": 4096},
            })
            with patch("src.ops.replay_reviewed_compiler_selection._create_google_compiler") as factory:
                with self.assertRaisesRegex(ValueError, "thinking_budget"):
                    run_approved_manifest(
                        manifest_path, approved_manifest_sha256=_sha256_file(manifest_path),
                    )
                factory.assert_not_called()

    def test_invalid_budget_fails_before_rehearsal(self) -> None:
        for output, thinking in ((0, 0), (4096, -1), (4096, 4096), (True, 0), (4096, 1.5)):
            with self.subTest(output=output, thinking=thinking):
                with patch("src.ops.replay_reviewed_compiler_selection.rehearse_reviewed_compiler_selection") as rehearsal:
                    with self.assertRaisesRegex(ValueError, "token|budget"):
                        build_admission_manifest(
                            corpus_path=self.fixture_path, manifest_path=Path("unused.json"),
                            result_path=Path("unused-result.json"), cost_cap_usd=0.20,
                            max_output_tokens=output, thinking_budget=thinking,
                        )
                    rehearsal.assert_not_called()

    def test_prepare_cli_binds_explicit_zero_thinking_budget(self) -> None:
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            with patch("src.ops.replay_reviewed_compiler_selection._tracked_runtime_build",
                       return_value={"algorithm": "test"}), redirect_stdout(StringIO()):
                status = main([
                    "prepare", "--corpus", str(self.fixture_path),
                    "--manifest", str(manifest_path),
                    "--result", str(Path(temp_dir) / "result.json"),
                    "--cost-cap-usd", "0.12", "--max-output-tokens", "2048",
                    "--thinking-budget", "0",
                ])
            self.assertEqual(status, 0)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["provider"]["max_output_tokens"], 2048)
            self.assertEqual(manifest["provider"]["thinking_budget"], 0)


if __name__ == "__main__":
    unittest.main()
