from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from src.ops.replay_reviewed_compiler_selection import (
    _sha256_file,
    _write_new_json,
    build_admission_manifest,
    rehearse_admission_manifest,
    rehearse_reviewed_compiler_selection,
    run_approved_manifest,
)


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "reviewed_runtime_replay_corpus_v1.json"
)


class ReviewedCompilerSelectionTests(unittest.TestCase):
    def test_rehearsal_runs_actual_compiler_contract_without_provider(self) -> None:
        first = rehearse_reviewed_compiler_selection(FIXTURE_PATH)
        second = rehearse_reviewed_compiler_selection(FIXTURE_PATH)

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
                corpus_path=FIXTURE_PATH,
                manifest_path=manifest_path,
                result_path=result_path,
                cost_cap_usd=0.12,
                runtime_build=runtime_build,
            )
            self.assertEqual(manifest["execution"]["initial_compiler_calls"], 6)
            self.assertEqual(
                manifest["execution"]["maximum_compiler_calls_with_internal_retry"],
                12,
            )
            self.assertEqual(manifest["provider"]["provider_client_retries"], 0)
            self.assertEqual(manifest["provider"]["max_output_tokens"], 2048)
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
                corpus_path=FIXTURE_PATH,
                manifest_path=manifest_path,
                result_path=result_path,
                cost_cap_usd=0.12,
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


if __name__ == "__main__":
    unittest.main()
