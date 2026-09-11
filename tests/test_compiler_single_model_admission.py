"""An explicitly chosen model uses its own prices without changing the gate."""

from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from tests.request_unit_fixture_support import request_bound_fixture

from src.ops.replay_reviewed_compiler_selection import (
    _ReviewedProgramQueue,
    _reviewed_response_queue,
    _sha256_file,
    _write_new_json,
    build_admission_manifest,
    main,
    run_approved_manifest,
)


CORPUS = Path(__file__).parent / "fixtures" / "reviewed_runtime_replay_corpus_v3.json"
RUNTIME = {"git_commit": "test", "file_count": 1, "sha256": "test"}
PRO = "gemini-2.5-pro"


class CompilerSingleModelAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.fixture_path = request_bound_fixture(self, CORPUS)
        temp = TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.args = {
            "corpus_path": self.fixture_path,
            "manifest_path": self.root / "manifest.json",
            "result_path": self.root / "result.json",
            "cost_cap_usd": 1.0,
            "runtime_build": RUNTIME,
        }

    def test_pro_prices_only_one_model_and_retains_single_model_stop_policy(self):
        baseline = build_admission_manifest(**self.args)
        pro = build_admission_manifest(**self.args, model=PRO)
        self.assertEqual(baseline["provider"]["model"], "gemini-2.5-flash")
        self.assertEqual(pro["provider"]["model"], PRO)
        self.assertNotIn("models", pro["provider"])
        self.assertEqual(pro["schema"], baseline["schema"])
        self.assertEqual(pro["inputs"], baseline["inputs"])
        self.assertEqual(pro["execution"], baseline["execution"])
        self.assertTrue(pro["execution"]["stop_after_first_failed_question"])
        self.assertEqual(pro["execution"]["initial_compiler_calls"], 6)
        self.assertEqual(pro["execution"]["maximum_compiler_calls_with_internal_retry"], 12)
        self.assertEqual(pro["pricing"]["input_per_million_tokens_usd"], 1.25)
        self.assertEqual(pro["pricing"]["output_per_million_tokens_usd"], 10.0)
        self.assertEqual(pro["pricing"]["cached_input_per_million_tokens_usd"], 0.125)
        self.assertGreater(pro["pricing"]["likely_estimate_usd"], baseline["pricing"]["likely_estimate_usd"])
        with self.assertRaisesRegex(ValueError, "cost cap"):
            build_admission_manifest(**{**self.args, "cost_cap_usd": 0.20}, model=PRO)

    def test_cli_model_reaches_only_one_provider_factory_with_unchanged_controls(self):
        seen = []
        corpus = json.loads(self.fixture_path.read_text(encoding="utf-8"))

        def factory(spec, _callback):
            seen.append(dict(spec))
            return _ReviewedProgramQueue(_reviewed_response_queue(corpus))

        with patch("src.ops.replay_reviewed_compiler_selection._tracked_runtime_build", return_value=RUNTIME), patch(
            "socket.socket.connect", side_effect=AssertionError("no network"),
        ), redirect_stdout(StringIO()):
            status = main([
                "prepare", "--model", PRO, "--corpus", str(self.fixture_path),
                "--manifest", str(self.args["manifest_path"]),
                "--result", str(self.args["result_path"]), "--cost-cap-usd", "1.0",
            ])
            self.assertEqual(status, 0)
            result = run_approved_manifest(
                self.args["manifest_path"],
                approved_manifest_sha256=_sha256_file(self.args["manifest_path"]),
                provider_factory=factory,
            )
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["model"], PRO)
        self.assertEqual(seen[0]["max_output_tokens"], 4096)
        self.assertEqual(seen[0]["thinking_budget"], 1024)
        self.assertEqual(seen[0]["provider_client_retries"], 0)
        self.assertEqual(result["summary"]["passed_case_count"], 5)

    def test_invalid_model_or_mixed_modes_stop_before_rehearsal(self):
        for overrides in (
            {"model": "unknown"}, {"model": PRO, "thinking_budget": 0},
            {"model": PRO, "comparison_model": PRO},
        ):
            with self.subTest(overrides=overrides), patch(
                "src.ops.replay_reviewed_compiler_selection.rehearse_reviewed_compiler_selection",
            ) as rehearsal:
                with self.assertRaises(ValueError):
                    build_admission_manifest(**self.args, **overrides)
                rehearsal.assert_not_called()

    def test_invalid_pro_budget_in_manifest_cannot_reach_provider(self):
        manifest = build_admission_manifest(**self.args, model=PRO)
        manifest["provider"]["thinking_budget"] = 0
        _write_new_json(self.args["manifest_path"], manifest)
        with patch("src.ops.replay_reviewed_compiler_selection._create_google_compiler") as factory:
            with self.assertRaisesRegex(ValueError, "budget"):
                run_approved_manifest(
                    self.args["manifest_path"],
                    approved_manifest_sha256=_sha256_file(self.args["manifest_path"]),
                )
            factory.assert_not_called()


if __name__ == "__main__":
    unittest.main()
