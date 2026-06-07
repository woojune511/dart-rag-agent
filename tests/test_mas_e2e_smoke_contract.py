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

from src.ops import mas_e2e_smoke
from src.ops.check_mas_e2e_smoke_contract import (
    check_contract,
    evaluate_value_contract,
    extract_contract,
    resolve_value_contract,
)


def _payload() -> dict:
    return {
        "embedding_compatibility": {"status": "ok"},
        "case_count": 2,
        "summary": {
            "replan_routed_count": 0,
            "blocked_count": 0,
            "integrity_error_count": 0,
            "final_acceptance_outcome_counts": {
                "accepted_without_replan": 1,
                "replan_succeeded": 1,
            },
            "final_source_task_count": 1,
            "final_source_artifact_count": 1,
            "final_evidence_ref_count": 2,
            "final_subtask_result_count": 1,
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
                "final_acceptance_outcome": {"outcome": "accepted_without_replan"},
                "final_carry_forward": {
                    "source_task_count": 1,
                    "source_artifact_count": 1,
                    "evidence_ref_count": 2,
                    "subtask_result_count": 1,
                },
                "final_report": "final has value 2.54%",
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
                "final_acceptance_outcome": {"outcome": "replan_succeeded"},
                "final_carry_forward": {
                    "source_task_count": 0,
                    "source_artifact_count": 0,
                    "evidence_ref_count": 0,
                    "subtask_result_count": 0,
                },
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
        self.assertEqual(
            contract["final_acceptance_outcome_counts"],
            {"accepted_without_replan": 1, "replan_succeeded": 1},
        )
        self.assertEqual(contract["final_source_task_count"], 1)
        self.assertEqual(contract["final_source_artifact_count"], 1)
        self.assertEqual(contract["final_evidence_ref_count"], 2)
        self.assertEqual(contract["final_subtask_result_count"], 1)
        self.assertEqual(contract["cases"][0]["final_report_status"], "ok")
        self.assertEqual(
            contract["cases"][0]["final_acceptance_outcome"],
            "accepted_without_replan",
        )
        self.assertEqual(contract["cases"][0]["task_status_counts"], {"completed": 3})
        self.assertEqual(contract["cases"][0]["final_source_task_count"], 1)
        self.assertEqual(contract["cases"][0]["final_source_artifact_count"], 1)
        self.assertEqual(contract["cases"][0]["final_evidence_ref_count"], 2)
        self.assertEqual(contract["cases"][0]["final_subtask_result_count"], 1)
        self.assertEqual(contract["cases"][1]["task_status_counts"], {"completed": 1, "failed": 1})
        self.assertEqual(
            contract["cases"][1]["final_acceptance_outcome"],
            "replan_succeeded",
        )
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

    def test_value_contract_reports_missing_and_forbidden_numeric_values(self) -> None:
        payload = _payload()
        payload["report_scope"] = {"company": "ACME", "year": "2023"}
        payload["cases"][0]["final_report"] = "final has value -4.45%"
        payload["cases"][0]["final_report_record"] = {
            "status": "ok",
            "subtask_results": [{"answer": "subtask has 258,935,494"}],
        }
        value_contract = {
            "scope_match": {"company": "ACME", "year": "2023"},
            "assertions": [
                {
                    "name": "operating_margin",
                    "case_index": 1,
                    "must_include": ["2.54%", "258,935,494"],
                    "must_not_include": ["-4.45%"],
                }
            ],
        }

        failures = evaluate_value_contract(payload, value_contract)

        self.assertEqual(len(failures), 2)
        reasons = {failure["reason"] for failure in failures}
        self.assertEqual(reasons, {"missing_value", "forbidden_value_present"})

    def test_check_contract_includes_value_assertion_failures(self) -> None:
        baseline = _payload()
        current = _payload()
        current["report_scope"] = {"company": "ACME", "year": "2023"}
        current["cases"][0]["final_report"] = "final has value -4.45%"
        value_contract = {
            "scope_match": {"company": "ACME", "year": "2023"},
            "assertions": [
                {
                    "name": "operating_margin",
                    "case_index": 1,
                    "must_include": ["2.54%"],
                    "must_not_include": ["-4.45%"],
                }
            ],
        }

        result = check_contract(
            current_payload=current,
            baseline_payload=baseline,
            value_contract_payload=value_contract,
        )

        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["value_assertion_failure_count"], 2)
        self.assertTrue(any(item["path"].startswith("value_assertions") for item in result["differences"]))

    def test_check_contract_generates_default_profile_value_assertions(self) -> None:
        baseline = _payload()
        current = _payload()
        for payload in (baseline, current):
            payload["report_scope"] = dict(mas_e2e_smoke.DEFAULT_SCOPE)
            payload["cases"][0]["query"] = mas_e2e_smoke.DEFAULT_QUERIES[0]
            payload["cases"][1]["query"] = mas_e2e_smoke.DEFAULT_QUERIES[1]
            payload["cases"][1]["final_report"] = "final has value 10.95% with 28,352,769 and 258,935,494"
        current["cases"][0]["final_report"] = "final has value -4.45%"

        resolved = resolve_value_contract(current)
        result = check_contract(current_payload=current, baseline_payload=baseline)

        self.assertEqual(resolved["source"], "mas_e2e_smoke_default_profile")
        self.assertEqual(result["status"], "mismatch")
        self.assertEqual(result["value_assertion_failure_count"], 4)

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
