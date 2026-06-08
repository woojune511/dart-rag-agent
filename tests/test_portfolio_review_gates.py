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

from src.ops.portfolio_review_gates import render_text, run_review_gates  # noqa: E402


class PortfolioReviewGateTests(unittest.TestCase):
    def test_run_review_gates_aggregates_ready_subgates(self) -> None:
        result = run_review_gates()

        self.assertEqual(result["status"], "ready")
        self.assertTrue(result["checks"]["portfolio_demo_ready"])
        self.assertTrue(result["checks"]["cache_reviewer_ok"])
        self.assertTrue(result["checks"]["cache_handoff_ready"])
        self.assertTrue(result["checks"]["cache_promotion_evidence_ready"])
        self.assertTrue(result["checks"]["reflection_promotion_ready"])
        self.assertEqual(result["portfolio_demo"]["readiness"], "ready")
        self.assertEqual(result["cache_reviewer"]["status"], "ok")
        self.assertEqual(result["cache_reviewer"]["reviewer_handoff_status"], "ready")
        self.assertEqual(result["cache_reviewer"]["producer_policy_ready_count"], 1)
        self.assertEqual(result["cache_reviewer"]["producer_policy_fallback_count"], 1)
        self.assertFalse(result["cache_reviewer"]["serving_enabled"])
        self.assertFalse(result["cache_reviewer"]["ledger_insertion_enabled"])
        self.assertEqual(result["cache_promotion_evidence"]["status"], "ready")
        self.assertEqual(result["cache_promotion_evidence"]["ready_count"], 3)
        self.assertEqual(result["cache_promotion_evidence"]["fallback_count"], 5)
        self.assertEqual(result["cache_promotion_evidence"]["trace_summary_count"], 2)
        self.assertTrue(result["cache_promotion_evidence"]["disabled_flags_ok"])
        self.assertTrue(result["cache_promotion_evidence"]["producer_contract_ok"])
        self.assertTrue(result["cache_promotion_evidence"]["fallback_safety_ok"])
        self.assertEqual(result["reflection_promotion"]["status"], "ready")
        self.assertEqual(result["reflection_promotion"]["case_count"], 12)
        self.assertEqual(result["reflection_promotion"]["trace_summary_count"], 2)
        self.assertTrue(result["reflection_promotion"]["source_coverage_ok"])
        self.assertTrue(result["reflection_promotion"]["report_contract_ok"])
        self.assertEqual(
            result["reflection_promotion"]["promotion_signals"]["false_recovery_rate"],
            0.0,
        )
        self.assertEqual(
            result["reflection_promotion"]["promotion_signals"]["integrity_preservation_rate"],
            1.0,
        )

    def test_render_text_includes_subgate_sections(self) -> None:
        text = render_text(run_review_gates())

        self.assertIn("# Portfolio Review Gates", text)
        self.assertIn("Portfolio Demo:", text)
        self.assertIn("Cache Reviewer:", text)
        self.assertIn("Cache Promotion Evidence:", text)
        self.assertIn("Reflection Promotion:", text)
        self.assertIn("trace_summary_count:", text)
        self.assertIn("source_coverage_ok:", text)
        self.assertIn("report_contract_ok:", text)
        self.assertIn("producer_contract_ok:", text)
        self.assertIn("fallback_safety_ok:", text)
        self.assertIn("producer_policy_ready_count:", text)
        self.assertIn("false_recovery_rate:", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "portfolio_review_gates.json"

            gate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.portfolio_review_gates",
                    "--format",
                    "json",
                    "--output",
                    str(output),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )

            self.assertEqual(gate_result.returncode, 0, gate_result.stderr)
            self.assertIn('"status": "ready"', gate_result.stdout)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["cache_reviewer"]["status"], "ok")
            self.assertEqual(payload["reflection_promotion"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
