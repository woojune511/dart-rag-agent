import json
import shutil
import sys
import unittest
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.ops.build_dataset_review_pack import build_review_pack


class BuildDatasetReviewPackTests(unittest.TestCase):
    def test_build_review_pack_writes_compact_csv_and_markdown(self) -> None:
        curated_rows = [
            {
                "id": "row_001",
                "company": "Example Corp",
                "year": 2023,
                "question": "2023 operating margin을 계산해 줘.",
                "answer_key": "영업이익률은 12.3%입니다.",
                "answer_type": "numeric",
                "expected_refusal": False,
                "expected_sections": ["III. 재무에 관한 사항 > 연결손익계산서"],
                "evidence": [
                    {
                        "section_path": "III. 재무에 관한 사항 > 연결손익계산서",
                        "quote": "영업이익 123, 매출액 1,000",
                        "why_it_supports_answer": "비율 계산 근거입니다.",
                    }
                ],
                "verification_status": "verified",
                "source_reports": [
                    {
                        "corp_name": "Example Corp",
                        "year": 2023,
                        "report_type": "사업보고서",
                        "rcept_no": "20240101000001",
                        "file_path": "C:/tmp/example_2023.html",
                    }
                ],
            }
        ]
        review_rows = [
            {
                "id": "row_001",
                "review_decision": "answer_verified",
            }
        ]
        rewrite_log = [{"id": "row_001"}]

        tmp_path = PROJECT_ROOT / f"tmp_review_pack_test_{uuid.uuid4().hex}"
        tmp_path.mkdir(parents=True, exist_ok=False)
        try:
            dataset_path = tmp_path / "curated.json"
            review_seed_path = tmp_path / "review_seed.json"
            rewrite_log_path = tmp_path / "rewrite_log.json"
            compact_csv_path = tmp_path / "inspect.csv"
            inspect_guide_path = tmp_path / "inspect.md"
            review_markdown_path = tmp_path / "review.md"

            dataset_path.write_text(json.dumps(curated_rows, ensure_ascii=False), encoding="utf-8")
            review_seed_path.write_text(json.dumps(review_rows, ensure_ascii=False), encoding="utf-8")
            rewrite_log_path.write_text(json.dumps(rewrite_log, ensure_ascii=False), encoding="utf-8")

            summary = build_review_pack(
                dataset_path=dataset_path,
                review_seed_path=review_seed_path,
                rewrite_log_path=rewrite_log_path,
                compact_csv_path=compact_csv_path,
                inspect_guide_path=inspect_guide_path,
                review_markdown_path=review_markdown_path,
            )

            self.assertEqual(summary["row_count"], 1)
            csv_text = compact_csv_path.read_text(encoding="utf-8-sig")
            markdown_text = review_markdown_path.read_text(encoding="utf-8")
            guide_text = inspect_guide_path.read_text(encoding="utf-8")

            self.assertIn("source_report_paths", csv_text)
            self.assertIn("영업이익률은 12.3%입니다.", csv_text)
            self.assertIn("[2023 사업보고서 (20240101000001)](<C:/tmp/example_2023.html>)", markdown_text)
            self.assertIn("[DART](https://dart.fss.or.kr/dsaf001/main.do?rcpNo=20240101000001)", markdown_text)
            self.assertIn("문서 대조용 review packet", guide_text)
        finally:
            shutil.rmtree(tmp_path, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
