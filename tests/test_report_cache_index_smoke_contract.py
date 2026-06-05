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

from src.ops.check_report_cache_index_smoke_contract import check_contract, extract_contract  # noqa: E402
from src.ops.report_cache_index_smoke import build_smoke_payload  # noqa: E402


FIXTURE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_diagnostics.json"
BASELINE_PATH = PROJECT_ROOT / "tests" / "fixtures" / "report_cache_index" / "rehydration_contract_baseline.json"


class ReportCacheIndexSmokeContractTests(unittest.TestCase):
    def test_extract_contract_keeps_stable_handoff_fields(self) -> None:
        contract = extract_contract(build_smoke_payload(report_cache_index_path=FIXTURE_PATH))

        self.assertEqual(contract["status"], "trace_only")
        self.assertFalse(contract["enabled"])
        self.assertFalse(contract["serving_enabled"])
        self.assertEqual(contract["match_count"], 2)
        self.assertEqual(contract["readable_match_count"], 2)
        self.assertEqual(contract["rehydration_ready_match_count"], 1)
        self.assertEqual(contract["rehydration_blocked_match_count"], 1)
        self.assertEqual(contract["rehydration_reason_counts"]["missing_answer_slots"], 1)
        self.assertEqual(contract["index_status"], "loaded")
        self.assertEqual(contract["index_readable_count"], 2)
        self.assertEqual(contract["index_rehydration_ready_count"], 1)
        self.assertEqual(contract["rehydrated_candidate_artifact_count"], 1)
        self.assertEqual(contract["rehydrated_candidate_artifact_blocked_count"], 1)
        self.assertEqual(len(contract["candidate_artifacts"]), 2)
        self.assertFalse(contract["candidate_artifacts"][0]["has_artifact"])
        self.assertTrue(contract["candidate_artifacts"][1]["has_artifact"])
        self.assertEqual(contract["candidate_artifacts"][1]["artifact_status"], "candidate")
        self.assertTrue(contract["candidate_artifacts"][1]["answer_present"])
        self.assertEqual(contract["candidate_artifacts"][1]["citation_count"], 1)
        self.assertEqual(contract["candidate_artifacts"][1]["evidence_item_count"], 1)
        self.assertEqual(contract["candidate_artifacts"][1]["calculation_operand_count"], 1)
        self.assertFalse(contract["candidate_artifacts"][1]["artifact_serving_enabled"])

    def test_check_contract_reports_candidate_count_delta(self) -> None:
        baseline = extract_contract(build_smoke_payload(report_cache_index_path=FIXTURE_PATH))
        current = dict(baseline)
        current["rehydrated_candidate_artifact_count"] = 0

        result = check_contract(current_payload=current, baseline_payload=baseline)

        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["difference_count"], 1)
        self.assertEqual(result["differences"][0]["path"], "rehydrated_candidate_artifact_count")

    def test_source_controlled_baseline_matches_fixture_smoke_contract(self) -> None:
        current = build_smoke_payload(report_cache_index_path=FIXTURE_PATH)
        baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

        result = check_contract(current_payload=current, baseline_payload=baseline)

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["difference_count"], 0)

    def test_cli_writes_compact_baseline_and_compares(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "current.json"
            baseline = root / "baseline.json"
            current.write_text(
                json.dumps(build_smoke_payload(report_cache_index_path=FIXTURE_PATH), ensure_ascii=False),
                encoding="utf-8-sig",
            )

            write_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.check_report_cache_index_smoke_contract",
                    "--current",
                    str(current),
                    "--baseline",
                    str(baseline),
                    "--write-baseline",
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(write_result.returncode, 0, write_result.stderr)
            self.assertTrue(baseline.exists())
            self.assertIn("baseline_written", write_result.stdout)

            compare_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.check_report_cache_index_smoke_contract",
                    "--current",
                    str(current),
                    "--baseline",
                    str(baseline),
                ],
                cwd=PROJECT_ROOT,
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(compare_result.returncode, 0, compare_result.stderr)
            self.assertIn('"status": "ok"', compare_result.stdout)


if __name__ == "__main__":
    unittest.main()
