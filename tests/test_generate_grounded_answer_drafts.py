import sys
import shutil
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.generate_grounded_answer_drafts import (
    _checkpoint_output_path,
    _checkpoint_summary_path,
    _extract_business_period,
    _merge_rows,
    _missing_core_fields,
    _select_best_report,
    _summary_payload,
)
from src.ingestion.dart_fetcher import ReportMetadata


class GenerateGroundedAnswerDraftsTests(unittest.TestCase):
    def test_checkpoint_paths_are_derived_from_output(self) -> None:
        output_path = Path("benchmarks/datasets/single_doc_eval_full.grounded_draft.json")

        self.assertEqual(
            _checkpoint_output_path(output_path).name,
            "single_doc_eval_full.grounded_draft.checkpoint.json",
        )
        self.assertEqual(
            _checkpoint_summary_path(output_path).name,
            "single_doc_eval_full.grounded_draft.checkpoint.summary.json",
        )

    def test_summary_payload_tracks_partial_progress(self) -> None:
        dataset_path = Path("benchmarks/datasets/single_doc_eval_full.json")
        output_path = Path("benchmarks/datasets/single_doc_eval_full.grounded_draft.json")

        payload = _summary_payload(
            dataset_path=dataset_path,
            output_path=output_path,
            row_count=80,
            completed_rows=17,
            failures=[{"id": "row_001", "error": "timeout"}],
            start_time=0.0,
            status="running",
            last_completed_row_id="row_017",
        )

        self.assertEqual(payload["row_count"], 80)
        self.assertEqual(payload["completed_rows"], 17)
        self.assertEqual(payload["failure_count"], 1)
        self.assertEqual(payload["status"], "running")
        self.assertEqual(payload["last_completed_row_id"], "row_017")

    def test_missing_core_fields_detects_empty_sections_and_evidence(self) -> None:
        row = {
            "id": "row_001",
            "answer_key": "filled",
            "expected_sections": [],
            "evidence": [],
        }

        self.assertEqual(
            _missing_core_fields(row),
            ["expected_sections", "evidence"],
        )

    def test_merge_rows_replaces_matching_ids_and_preserves_order(self) -> None:
        base_rows = [
            {"id": "a", "answer_key": "old-a"},
            {"id": "b", "answer_key": "old-b"},
        ]
        updated_rows = [
            {"id": "b", "answer_key": "new-b"},
            {"id": "c", "answer_key": "new-c"},
        ]

        merged = _merge_rows(base_rows, updated_rows)

        self.assertEqual(
            [(row["id"], row["answer_key"]) for row in merged],
            [("a", "old-a"), ("b", "new-b"), ("c", "new-c")],
        )

    def test_extract_business_period_reads_cover_period(self) -> None:
        temp_dir = PROJECT_ROOT / "archive" / f"tmp_generate_grounded_{uuid.uuid4().hex}"
        temp_dir.mkdir(parents=True, exist_ok=False)
        try:
            report_path = temp_dir / "report.html"
            report_path.write_text(
                '<TU AUNIT="PERIODFROM" AUNITVALUE="20230101">2023년 01월 01일</TU>\n'
                '<TU AUNIT="PERIODTO" AUNITVALUE="20231231">2023년 12월 31일</TU>\n',
                encoding="utf-8",
            )

            self.assertEqual(_extract_business_period(report_path), ("20230101", "20231231"))
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    def test_select_best_report_prefers_matching_business_year_file(self) -> None:
        temp_root = PROJECT_ROOT / "archive" / f"tmp_generate_grounded_{uuid.uuid4().hex}"
        temp_root.mkdir(parents=True, exist_ok=False)
        try:
            wrong_report_path = temp_root / "2023_사업보고서_20240314001531.html"
            correct_report_path = temp_root / "2023_사업보고서_20240313001451.html"

            wrong_report_path.write_text(
                '<TU AUNIT="PERIODFROM" AUNITVALUE="20220101">2022년 01월 01일</TU>\n'
                '<TU AUNIT="PERIODTO" AUNITVALUE="20221231">2022년 12월 31일</TU>\n',
                encoding="utf-8",
            )
            correct_report_path.write_text(
                '<TU AUNIT="PERIODFROM" AUNITVALUE="20230101">2023년 01월 01일</TU>\n'
                '<TU AUNIT="PERIODTO" AUNITVALUE="20231231">2023년 12월 31일</TU>\n',
                encoding="utf-8",
            )

            reports = [
                ReportMetadata(
                    rcept_no="20240314001531",
                    corp_name="현대자동차",
                    corp_code="",
                    stock_code="",
                    report_nm="사업보고서 (2022.12) [정정]",
                    report_type="사업보고서",
                    rcept_dt="20240314",
                    year=2023,
                    file_path=str(wrong_report_path),
                ),
                ReportMetadata(
                    rcept_no="20240313001451",
                    corp_name="현대자동차",
                    corp_code="",
                    stock_code="",
                    report_nm="사업보고서 (2023.12)",
                    report_type="사업보고서",
                    rcept_dt="20240313",
                    year=2023,
                    file_path=str(correct_report_path),
                ),
            ]

            selected = _select_best_report(reports, 2023)

            self.assertEqual(selected.rcept_no, "20240313001451")
        finally:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
