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

from src.ops.promotion_trace_materiality_gate import render_text, run_gate  # noqa: E402


class PromotionTraceMaterialityGateTests(unittest.TestCase):
    def test_default_trace_summaries_are_materially_distinct(self) -> None:
        result = run_gate()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["summary_count"], 2)
        self.assertTrue(result["materiality_ok"])
        self.assertEqual(result["issue_ids"], [])
        self.assertEqual(
            result["source_types"],
            [
                "live_default_mas_trace_summary",
                "store_fixed_eval_only_trace_summary",
            ],
        )
        self.assertEqual(
            result["reflection_actions"],
            ["none", "retry_retrieval", "stop_insufficient"],
        )
        self.assertIn("ambiguous_rehydration_match", result["cache_fallback_reasons"])
        self.assertIn("missing_worker_material_artifact", result["cache_fallback_reasons"])
        self.assertGreaterEqual(result["reflection_material_signature_count"], 3)
        self.assertGreaterEqual(result["cache_material_signature_count"], 3)

    def test_single_trace_summary_is_not_enough_for_materiality(self) -> None:
        trace_summary = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "promotion_trace_summary"
            / "store_fixed_candidate_summary.json"
        )

        result = run_gate(trace_summary_paths=[trace_summary])

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["materiality_ok"])
        self.assertIn(
            "missing_source_type:live_default_mas_trace_summary",
            result["issue_ids"],
        )
        self.assertIn(
            "missing_reflection_action:stop_insufficient",
            result["issue_ids"],
        )

    def test_summary_without_fallback_reason_blocks_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            store_summary = Path(temp_dir) / "store.json"
            live_summary = Path(temp_dir) / "live.json"
            store_summary.write_text(
                json.dumps(
                    {
                        "summary_id": "store",
                        "source_type": "store_fixed_eval_only_trace_summary",
                        "reflection_promotion_cases": [
                            {
                                "case_id": "retry",
                                "eligible": True,
                                "reflection_triggered": True,
                                "expected_action": "retry_retrieval",
                                "initial_status": "missing",
                                "final_status": "accepted",
                                "task_artifact_trace": {"integrity_status": "ok"},
                                "calculation_trace_status": "ok",
                                "evidence_supported": True,
                            }
                        ],
                        "report_cache_promotion_cases": [
                            {
                                "name": "fallback",
                                "status": "normal_retrieval_fallback",
                                "fallback_required": True,
                                "reasons": [],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            live_summary.write_text(
                json.dumps(
                    {
                        "summary_id": "live",
                        "source_type": "live_default_mas_trace_summary",
                        "reflection_promotion_cases": [
                            {
                                "case_id": "clean",
                                "eligible": False,
                                "reflection_triggered": False,
                                "expected_action": "none",
                                "initial_status": "accepted",
                                "final_status": "accepted",
                                "task_artifact_trace": {"integrity_status": "ok"},
                                "calculation_trace_status": "ok",
                                "evidence_supported": True,
                            },
                            {
                                "case_id": "stop",
                                "eligible": True,
                                "reflection_triggered": True,
                                "expected_action": "stop_insufficient",
                                "initial_status": "missing",
                                "final_status": "blocked",
                                "task_artifact_trace": {"integrity_status": "blocked"},
                                "calculation_trace_status": "",
                                "evidence_supported": False,
                            },
                        ],
                        "report_cache_promotion_cases": [
                            {
                                "name": "ready",
                                "status": "ready",
                                "ready": True,
                                "fallback_required": False,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = run_gate(trace_summary_paths=[store_summary, live_summary])

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["materiality_ok"])
        self.assertIn("insufficient_distinct_cache_fallback_reasons", result["issue_ids"])

    def test_render_text_includes_materiality_fields(self) -> None:
        text = render_text(run_gate())

        self.assertIn("# Promotion Trace Materiality Gate", text)
        self.assertIn("Status: ready", text)
        self.assertIn("Materiality ok: true", text)
        self.assertIn("Reflection actions: none, retry_retrieval, stop_insufficient", text)

    def test_cli_writes_json_output(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "promotion_trace_materiality.json"

            gate_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.promotion_trace_materiality_gate",
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
            self.assertTrue(payload["materiality_ok"])
            self.assertEqual(payload["summary_count"], 2)


if __name__ == "__main__":
    unittest.main()
