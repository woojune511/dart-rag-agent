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
        self.assertEqual(result["scenario_count"], 8)
        self.assertEqual(result["ready_count"], 3)
        self.assertEqual(result["fallback_count"], 5)
        self.assertEqual(result["trace_summary_count"], 2)
        self.assertTrue(result["disabled_flags_ok"])
        self.assertTrue(result["producer_contract_ok"])
        self.assertEqual(result["producer_contract_issue_ids"], [])
        self.assertTrue(result["fallback_safety_ok"])
        self.assertEqual(result["fallback_safety_issue_ids"], [])
        scenarios = {item["name"]: item for item in result["scenarios"]}
        self.assertTrue(scenarios["ready_entry_candidate_only"]["ready"])
        self.assertFalse(scenarios["ready_entry_candidate_only"]["serving_enabled"])
        self.assertFalse(scenarios["ready_entry_candidate_only"]["final_acceptance_enabled"])
        self.assertEqual(
            scenarios["ready_entry_candidate_only"]["producer_policy_name"],
            "calculation_task_contract",
        )
        self.assertEqual(
            scenarios["ready_entry_candidate_only"]["producer_policy_artifact_kinds"],
            ["operand_set", "calculation_plan", "calculation_result"],
        )
        self.assertEqual(scenarios["ready_entry_candidate_only"]["producer_policy_artifact_count"], 3)
        self.assertTrue(scenarios["ready_entry_candidate_only"]["calculation_contract_valid"])
        self.assertTrue(scenarios["incomplete_entry_fallback"]["fallback_required"])
        self.assertIn("missing_answer_slots", scenarios["incomplete_entry_fallback"]["reasons"])
        self.assertTrue(scenarios["ambiguous_match_fallback"]["fallback_required"])
        self.assertIn("ambiguous_rehydration_match", scenarios["ambiguous_match_fallback"]["reasons"])
        self.assertTrue(scenarios["trace_summary_ready_candidate_only"]["ready"])
        self.assertTrue(scenarios["trace_summary_ambiguous_candidate_fallback"]["fallback_required"])
        self.assertTrue(scenarios["trace_summary_incomplete_candidate_fallback"]["fallback_required"])
        self.assertTrue(scenarios["live_default_mas_ready_candidate_only"]["ready"])
        self.assertTrue(
            scenarios["live_default_mas_incomplete_candidate_fallback"]["fallback_required"]
        )

    def test_render_text_includes_gate_counts(self) -> None:
        text = render_text(run_gate())

        self.assertIn("# Report Cache Promotion Evidence Gate", text)
        self.assertIn("Status: ready", text)
        self.assertIn("Ready cases: 3", text)
        self.assertIn("Fallback cases: 5", text)
        self.assertIn("Trace summaries: 2", text)
        self.assertIn("Fallback safety ok: true", text)

    def test_ready_trace_summary_without_calculation_contract_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_summary = Path(temp_dir) / "trace_summary.json"
            trace_summary.write_text(
                json.dumps(
                    {
                        "report_cache_promotion_cases": [
                            {
                                "name": "trace_ready_missing_policy",
                                "status": "ready",
                                "ready": True,
                                "fallback_required": False,
                                "producer_policy_status": "ready",
                                "producer_policy_ready": True,
                                "serving_enabled": False,
                                "ledger_insertion_enabled": False,
                                "retrieval_bypass_enabled": False,
                                "final_acceptance_enabled": False,
                                "acceptance_authority": (
                                    "task_artifact_integrity_and_critic_orchestrator"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_gate(trace_summary_paths=[trace_summary])

        self.assertEqual(result["status"], "needs_evidence")
        self.assertFalse(result["producer_contract_ok"])
        self.assertIn(
            "trace_ready_missing_policy:producer_policy_name",
            result["producer_contract_issue_ids"],
        )
        self.assertIn(
            "trace_ready_missing_policy:producer_policy_artifact_kinds",
            result["producer_contract_issue_ids"],
        )

    def test_fallback_trace_summary_without_reason_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            trace_summary = Path(temp_dir) / "trace_summary.json"
            trace_summary.write_text(
                json.dumps(
                    {
                        "report_cache_promotion_cases": [
                            {
                                "name": "trace_fallback_missing_reason",
                                "status": "normal_retrieval_fallback",
                                "ready": False,
                                "fallback_required": True,
                                "reasons": [],
                                "serving_enabled": False,
                                "ledger_insertion_enabled": False,
                                "retrieval_bypass_enabled": False,
                                "final_acceptance_enabled": False,
                                "acceptance_authority": (
                                    "task_artifact_integrity_and_critic_orchestrator"
                                ),
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            result = run_gate(trace_summary_paths=[trace_summary])

        self.assertEqual(result["status"], "needs_evidence")
        self.assertFalse(result["fallback_safety_ok"])
        self.assertEqual(
            result["fallback_safety_issue_ids"],
            ["trace_fallback_missing_reason:fallback_reasons"],
        )

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
            self.assertEqual(payload["ready_count"], 3)
            self.assertEqual(payload["fallback_count"], 5)
            self.assertEqual(payload["trace_summary_count"], 2)
            self.assertTrue(payload["producer_contract_ok"])
            self.assertTrue(payload["fallback_safety_ok"])


if __name__ == "__main__":
    unittest.main()
