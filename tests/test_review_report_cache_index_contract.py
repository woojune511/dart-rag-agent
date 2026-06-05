import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.review_report_cache_index_contract import run_review  # noqa: E402


class ReviewReportCacheIndexContractTests(unittest.TestCase):
    def test_run_review_uses_repo_defaults(self) -> None:
        result = run_review()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["difference_count"], 0)
        self.assertEqual(result["reviewer_handoff"]["status"], "ready")
        self.assertEqual(result["reviewer_handoff"]["mode"], "candidate_only")
        self.assertFalse(result["reviewer_handoff"]["serving_enabled"])
        self.assertFalse(result["reviewer_handoff"]["ledger_insertion_enabled"])
        self.assertEqual(result["reviewer_handoff"]["projection_ready_count"], 1)
        self.assertEqual(result["reviewer_handoff"]["fallback_count"], 1)
        self.assertIn("rehydration_diagnostics.json", result["report_cache_index_path"])
        self.assertIn("rehydration_contract_baseline.json", result["baseline"])

    def test_cli_runs_default_review_without_generated_smoke_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "review.json"

            review_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.review_report_cache_index_contract",
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(review_result.returncode, 0, review_result.stderr)
            self.assertIn('"status": "ok"', review_result.stdout)
            self.assertIn('"reviewer_handoff"', review_result.stdout)
            self.assertTrue(output.exists())
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["difference_count"], 0)
            self.assertEqual(payload["reviewer_handoff"]["status"], "ready")

    def test_cli_exits_nonzero_when_contract_differs(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            baseline = Path(temp_dir) / "baseline.json"
            baseline.write_text(json.dumps({"status": "unexpected"}, ensure_ascii=False), encoding="utf-8")

            review_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.review_report_cache_index_contract",
                    "--baseline",
                    str(baseline),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(review_result.returncode, 1)
            self.assertIn('"status": "mismatch"', review_result.stdout)
            self.assertIn('"status": "needs_review"', review_result.stdout)


if __name__ == "__main__":
    unittest.main()
