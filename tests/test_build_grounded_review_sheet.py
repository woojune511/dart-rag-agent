import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.build_grounded_review_sheet import (
    _risk_tags,
    _risk_score,
    prepare_review_records,
)


class BuildGroundedReviewSheetTests(unittest.TestCase):
    def test_risk_tags_capture_refusal_gap_and_mismatch(self) -> None:
        row = {
            "id": "row_001",
            "question": "2023 operating margin question",
            "year": 2023,
            "answer_type": "summary",
            "answer_key": "The figure cannot be found, but the platform performed well.",
            "expected_refusal": True,
            "expected_sections": [],
            "evidence": [],
            "eval_checkpoints": {"reject_expected": False},
            "source_reports": [
                {
                    "corp_name": "Example",
                    "year": 2023,
                    "rcept_no": "20240101000001",
                    "file_path": "C:/tmp/example.html",
                }
            ],
        }

        tags = _risk_tags(row)

        self.assertIn("generated_refusal_mismatch", tags)
        self.assertIn("refusal_without_evidence", tags)
        self.assertIn("refusal_without_sections", tags)
        self.assertIn("partial_answer_refusal", tags)
        self.assertEqual(_risk_score(tags), 12)

    def test_prepare_review_records_flags_year_mismatch_and_dedupes_reports(self) -> None:
        rows = [
            {
                "id": "row_002",
                "company": "Example Corp",
                "question": "2023 revenue ratio question",
                "year": 2023,
                "answer_type": "numeric",
                "answer_key": "Based on 2022 figures, the ratio is 91.2%.",
                "expected_refusal": False,
                "expected_sections": ["III. Statements"],
                "evidence": [{"quote": "For 2022, revenue was 100.", "section_path": "III. Statements"}],
                "expected_operands": [],
                "reasoning_steps": ["Find the reported figures and compute the ratio."],
                "source_report": {
                    "corp_name": "Example Corp",
                    "year": 2023,
                    "rcept_no": "20240101000002",
                    "file_path": "C:/tmp/example_2023.html",
                },
                "source_reports": [
                    {
                        "corp_name": "Example Corp",
                        "year": 2023,
                        "rcept_no": "20240101000002",
                        "file_path": "C:/tmp/example_2023.html",
                    }
                ],
            }
        ]

        records, summary = prepare_review_records(rows)
        record = records[0]

        self.assertEqual(summary["priority_counts"]["high"], 1)
        self.assertIn("possible_year_mismatch", record["review_risk_tags"])
        self.assertIn("evidence_year_mismatch", record["review_risk_tags"])
        self.assertIn("numeric_without_operands", record["review_risk_tags"])
        self.assertEqual(record["source_report_paths"], ["C:/tmp/example_2023.html"])
        self.assertEqual(
            record["source_report_urls"],
            ["https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20240101000002"],
        )


if __name__ == "__main__":
    unittest.main()
