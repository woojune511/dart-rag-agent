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

from src.ops.reflection_promotion_gate import (  # noqa: E402
    evaluate_cases,
    render_text,
    run_gate,
    run_gate_suite,
)


class ReflectionPromotionGateTests(unittest.TestCase):
    def test_run_gate_reports_documented_promotion_signals(self) -> None:
        result = run_gate_suite()
        signals = result["promotion_signals"]

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["fixture_count"], 2)
        self.assertEqual(result["trace_summary_count"], 1)
        self.assertEqual(result["case_count"], 10)
        self.assertTrue(result["required_actions_present"])
        self.assertTrue(result["source_coverage_ok"])
        self.assertEqual(result["source_coverage_issue_ids"], [])
        self.assertEqual(result["case_source_counts"]["base_fixture"], 4)
        self.assertEqual(
            result["case_source_counts"]["store_fixed_eval_only_candidate_surface"],
            4,
        )
        self.assertEqual(
            result["case_source_counts"]["store_fixed_eval_only_trace_summary"],
            2,
        )
        self.assertTrue(result["report_contract_ok"])
        self.assertEqual(result["report_contract_issue_case_ids"], [])
        self.assertTrue(result["clean_pass_no_trigger"])
        self.assertTrue(result["stop_insufficient_no_acceptance"])
        self.assertEqual(signals["reflection_trigger_rate"], 1.0)
        self.assertGreater(signals["recovery_rate"], 0.0)
        self.assertEqual(signals["false_recovery_rate"], 0.0)
        self.assertEqual(signals["integrity_preservation_rate"], 1.0)
        self.assertIn("latency_delta", signals)
        self.assertIn("reflection_promotion_gate_fixture_v1", result["source_gate_ids"])
        self.assertIn(
            "reflection_promotion_gate_store_fixed_candidate_v1",
            result["source_gate_ids"],
        )
        self.assertIn(
            "store_fixed_candidate_promotion_trace_summary_v1",
            result["source_gate_ids"],
        )

    def test_run_gate_legacy_single_fixture_path_still_works(self) -> None:
        result = run_gate()

        self.assertEqual(result["status"], "ready")
        self.assertEqual(result["fixture_count"], 1)
        self.assertEqual(result["case_count"], 4)
        self.assertEqual(len(result["cases_paths"]), 1)
        self.assertTrue(result["source_coverage_ok"])
        self.assertEqual(result["required_case_sources"], [])

    def test_suite_requires_store_fixed_candidate_surface(self) -> None:
        fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "reflection_promotion_gate"
        trace_summary = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "promotion_trace_summary"
            / "store_fixed_candidate_summary.json"
        )

        result = run_gate_suite(
            cases_paths=[fixture_dir / "cases.json"],
            trace_summary_paths=[trace_summary],
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["source_coverage_ok"])
        self.assertEqual(
            result["source_coverage_issue_ids"],
            ["missing_case_source:store_fixed_eval_only_candidate_surface"],
        )

    def test_suite_requires_store_fixed_trace_summary_surface(self) -> None:
        fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "reflection_promotion_gate"

        result = run_gate_suite(
            cases_paths=[
                fixture_dir / "cases.json",
                fixture_dir / "store_fixed_cases.json",
            ],
            trace_summary_paths=[],
        )

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["source_coverage_ok"])
        self.assertEqual(
            result["source_coverage_issue_ids"],
            ["missing_case_source:store_fixed_eval_only_trace_summary"],
        )

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

    def test_missing_report_target_refs_block_promotion_for_accepted_reflection(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][0]["reflection_report"].pop("target_artifact_ids")

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["report_contract_ok"])
        self.assertEqual(
            result["report_contract_issue_case_ids"],
            ["retry_retrieval_recovers_missing_evidence:missing_acceptance_target_refs"],
        )

    def test_budget_overrun_blocks_promotion(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][0]["reflection_report"]["budget_consumed"] = 2

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["report_contract_ok"])
        self.assertEqual(
            result["report_contract_issue_case_ids"],
            ["retry_retrieval_recovers_missing_evidence:budget_out_of_bounds"],
        )

    def test_reflection_cannot_claim_final_acceptance_authority(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][0]["reflection_report"]["final_acceptance_authority"] = "reflection"

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["report_contract_ok"])
        self.assertEqual(
            result["report_contract_issue_case_ids"],
            [
                "retry_retrieval_recovers_missing_evidence:"
                "reflection_marked_or_missing_acceptance_authority"
            ],
        )

    def test_retry_retrieval_requires_visible_retry_queries(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][0]["reflection_action"]["retry_queries"] = []

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["report_contract_ok"])
        self.assertEqual(
            result["report_contract_issue_case_ids"],
            [
                "retry_retrieval_recovers_missing_evidence:"
                "missing_retry_query_surface"
            ],
        )

    def test_reflection_action_must_match_report_action(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][0]["reflection_action"]["action_type"] = "stop_insufficient"

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["report_contract_ok"])
        self.assertEqual(
            result["report_contract_issue_case_ids"],
            [
                "retry_retrieval_recovers_missing_evidence:"
                "reflection_action_mismatch"
            ],
        )

    def test_synthesize_from_outputs_requires_visible_source_ids(self) -> None:
        fixture_path = (
            PROJECT_ROOT
            / "tests"
            / "fixtures"
            / "reflection_promotion_gate"
            / "cases.json"
        )
        payload = json.loads(fixture_path.read_text(encoding="utf-8"))
        payload["cases"][1]["reflection_action"]["synthesis_source_ids"] = []

        result = evaluate_cases(payload)

        self.assertEqual(result["status"], "needs_review")
        self.assertFalse(result["report_contract_ok"])
        self.assertEqual(
            result["report_contract_issue_case_ids"],
            [
                "synthesize_from_task_outputs_recovers_complete_material:"
                "missing_synthesis_source_surface"
            ],
        )

    def test_render_text_includes_signal_names(self) -> None:
        text = render_text(run_gate_suite())

        self.assertIn("# Reflection Promotion Gate", text)
        self.assertIn("Source coverage ok: true", text)
        self.assertIn("Report contract ok: true", text)
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
            self.assertEqual(payload["fixture_count"], 2)
            self.assertEqual(payload["trace_summary_count"], 1)
            self.assertEqual(payload["case_count"], 10)
            self.assertTrue(payload["source_coverage_ok"])
            self.assertEqual(payload["promotion_signals"]["false_recovery_rate"], 0.0)

    def test_cli_accepts_repeated_cases_paths(self) -> None:
        fixture_dir = PROJECT_ROOT / "tests" / "fixtures" / "reflection_promotion_gate"

        gate_result = subprocess.run(
            [
                sys.executable,
                "-m",
                "src.ops.reflection_promotion_gate",
                "--format",
                "json",
                "--cases",
                str(fixture_dir / "cases.json"),
                "--cases",
                str(fixture_dir / "store_fixed_cases.json"),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(gate_result.returncode, 0, gate_result.stderr)
        payload = json.loads(gate_result.stdout)
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["fixture_count"], 2)
        self.assertEqual(payload["trace_summary_count"], 1)
        self.assertEqual(payload["case_count"], 10)
        self.assertTrue(payload["source_coverage_ok"])


if __name__ == "__main__":
    unittest.main()
