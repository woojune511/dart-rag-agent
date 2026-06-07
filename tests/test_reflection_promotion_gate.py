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

from src.ops.reflection_promotion_gate import evaluate_cases, render_text, run_gate  # noqa: E402


class ReflectionPromotionGateTests(unittest.TestCase):
    def test_run_gate_reports_documented_promotion_signals(self) -> None:
        result = run_gate()
        signals = result["promotion_signals"]

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["case_count"], 4)
        self.assertTrue(result["required_actions_present"])
        self.assertTrue(result["clean_pass_no_trigger"])
        self.assertTrue(result["stop_insufficient_no_acceptance"])
        self.assertEqual(signals["reflection_trigger_rate"], 1.0)
        self.assertGreater(signals["recovery_rate"], 0.0)
        self.assertEqual(signals["false_recovery_rate"], 0.0)
        self.assertEqual(signals["integrity_preservation_rate"], 1.0)
        self.assertIn("latency_delta", signals)

    def test_false_recovery_blocks_promotion(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][0]["evidence_supported"] = False

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertEqual(result["promotion_signals"]["false_recovery_rate"], 0.5)
        self.assertEqual(
            result["false_recovery_case_ids"],
            ["retry_retrieval_recovers_missing_evidence"],
        )

    def test_render_text_includes_signal_names(self) -> None:
        text = render_text(run_gate())

        self.assertIn("# Reflection Promotion Gate", text)
        self.assertIn("reflection_trigger_rate", text)
        self.assertIn("recovery_rate", text)
        self.assertIn("false_recovery_rate", text)
        self.assertIn("latency_delta", text)
        self.assertIn("integrity_preservation_rate", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "reflection_gate.json"

            gate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.reflection_promotion_gate",
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
            self.assertEqual(payload["promotion_signals"]["false_recovery_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
