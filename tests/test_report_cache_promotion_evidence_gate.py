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

from src.ops.report_cache_promotion_evidence_gate import render_text, run_gate  # noqa: E402


class ReportCachePromotionEvidenceGateTests(unittest.TestCase):
    def test_run_gate_covers_ready_incomplete_and_ambiguous_cases(self) -> None:
        result = run_gate()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["scenario_count"], 6)
        self.assertEqual(result["ready_count"], 2)
        self.assertEqual(result["fallback_count"], 4)
        self.assertEqual(result["trace_summary_count"], 1)
        self.assertTrue(result["disabled_flags_ok"])
        scenarios = {item["name"]: item for item in result["scenarios"]}
        self.assertTrue(scenarios["ready_entry_candidate_only"]["ready"])
        self.assertFalse(scenarios["ready_entry_candidate_only"]["serving_enabled"])
        self.assertFalse(scenarios["ready_entry_candidate_only"]["final_acceptance_enabled"])
        self.assertTrue(scenarios["incomplete_entry_fallback"]["fallback_required"])
        self.assertIn("missing_answer_slots", scenarios["incomplete_entry_fallback"]["reasons"])
        self.assertTrue(scenarios["ambiguous_match_fallback"]["fallback_required"])
        self.assertIn("ambiguous_rehydration_match", scenarios["ambiguous_match_fallback"]["reasons"])
        self.assertTrue(scenarios["trace_summary_ready_candidate_only"]["ready"])
        self.assertTrue(scenarios["trace_summary_ambiguous_candidate_fallback"]["fallback_required"])
        self.assertTrue(scenarios["trace_summary_incomplete_candidate_fallback"]["fallback_required"])

    def test_render_text_includes_gate_counts(self) -> None:
        text = render_text(run_gate())

        self.assertIn("# Report Cache Promotion Evidence Gate", text)
        self.assertIn("Status: ready", text)
        self.assertIn("Ready cases: 2", text)
        self.assertIn("Fallback cases: 4", text)
        self.assertIn("Trace summaries: 1", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "report_cache_promotion_evidence.json"

            gate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.report_cache_promotion_evidence_gate",
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
            self.assertEqual(payload["ready_count"], 2)
            self.assertEqual(payload["fallback_count"], 4)
            self.assertEqual(payload["trace_summary_count"], 1)


if __name__ == "__main__":
    unittest.main()
