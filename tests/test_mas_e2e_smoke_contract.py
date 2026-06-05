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

from src.ops.check_mas_e2e_smoke_contract import check_contract, extract_contract


def _payload() -> dict:
    return {
        "embedding_compatibility": {"status": "ok"},
        "case_count": 2,
        "summary": {
            "replan_routed_count": 0,
            "blocked_count": 0,
            "integrity_error_count": 0,
        },
        "cases": [
            {
                "query": "question one",
                "task_count": 5,
                "task_statuses": {
                    "task_1": "TaskStatus.COMPLETED",
                    "task_2": "completed",
                    "synthesis::final": "TaskStatus.COMPLETED",
                },
                "replan_count": 0,
                "replan_routed": False,
                "final_report_record": {"status": "ok"},
                "task_artifact_integrity_status": "ok",
            },
            {
                "query": "question two",
                "task_count": 2,
                "task_statuses": {
                    "task_1": "TaskStatus.FAILED",
                    "synthesis::final": "TaskStatus.COMPLETED",
                },
                "replan_count": 1,
                "replan_routed": True,
                "final_report_record": {"status": "ok"},
                "task_artifact_integrity_status": "ok",
            },
        ],
    }


class MasE2ESmokeContractTests(unittest.TestCase):
    def test_extract_contract_keeps_stable_smoke_fields(self) -> None:
        contract = extract_contract(_payload())

        self.assertEqual(contract["embedding_compatibility_status"], "ok")
        self.assertEqual(contract["case_count"], 2)
        self.assertEqual(contract["blocked_count"], 0)
        self.assertEqual(contract["integrity_error_count"], 0)
        self.assertEqual(contract["cases"][0]["final_report_status"], "ok")
        self.assertEqual(contract["cases"][0]["task_status_counts"], {"completed": 3})
        self.assertEqual(contract["cases"][1]["task_status_counts"], {"completed": 1, "failed": 1})
        self.assertTrue(contract["cases"][1]["replan_routed"])

    def test_check_contract_reports_task_status_distribution_delta(self) -> None:
        baseline = _payload()
        current = _payload()
        current["cases"][1]["task_statuses"]["task_1"] = "TaskStatus.COMPLETED"

        result = check_contract(current_payload=current, baseline_payload=baseline)

        self.assertEqual(result["status"], "mismatch")
        paths = {item["path"] for item in result["differences"]}
        self.assertIn("cases[1].task_status_counts.completed", paths)
        self.assertIn("cases[1].task_status_counts.failed", paths)

    def test_cli_writes_compact_baseline_and_compares(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "current.json"
            baseline = root / "baseline.json"
            current.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8-sig")

            write_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "src.ops.check_mas_e2e_smoke_contract",
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
                    "src.ops.check_mas_e2e_smoke_contract",
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
