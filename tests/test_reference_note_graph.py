import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.processing.financial_parser import (
    _build_reference_index,
    _extract_reference_section_paths,
)


class ReferenceSectionExtractionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.raw_sections = [
            {
                "title": "4. 매출 및 수주상황",
                "path_titles": ["II. 사업의 내용", "4. 매출 및 수주상황"],
                "path": "II. 사업의 내용 > 4. 매출 및 수주상황",
            },
            {
                "title": "5. 위험관리 및 파생거래",
                "path_titles": ["II. 사업의 내용", "5. 위험관리 및 파생거래"],
                "path": "II. 사업의 내용 > 5. 위험관리 및 파생거래",
            },
            {
                "title": "3. 연결재무제표 주석",
                "path_titles": ["III. 재무에 관한 사항", "3. 연결재무제표 주석"],
                "path": "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            },
            {
                "title": "1. 연결대상 종속회사 현황(상세)",
                "path_titles": ["XII. 상세표", "1. 연결대상 종속회사 현황(상세)"],
                "path": "XII. 상세표 > 1. 연결대상 종속회사 현황(상세)",
            },
        ]
        self.reference_index = _build_reference_index(self.raw_sections)

    def test_extracts_pair_reference_path(self) -> None:
        text = "☞ 우발채무 등에 관한 사항은 'III. 재무에 관한 사항'의 '3. 연결재무제표 주석'을 참조하시기 바랍니다."
        self.assertEqual(
            _extract_reference_section_paths(text, self.reference_index),
            ["III. 재무에 관한 사항 > 3. 연결재무제표 주석"],
        )

    def test_extracts_multiple_pair_reference_paths(self) -> None:
        text = (
            "☞ 부문별 사업에 관한 자세한 사항은 "
            "'II. 사업의 내용'의 '5. 위험관리 및 파생거래'와 "
            "'III. 재무에 관한 사항'의 '3. 연결재무제표 주석'을 참고하시기 바랍니다."
        )
        self.assertEqual(
            _extract_reference_section_paths(text, self.reference_index),
            [
                "II. 사업의 내용 > 5. 위험관리 및 파생거래",
                "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            ],
        )

    def test_extracts_single_leaf_reference_path(self) -> None:
        text = "※ 세부 제품별 매출은 '4. 매출 및 수주상황' 항목을 참고하시기 바랍니다."
        self.assertEqual(
            _extract_reference_section_paths(text, self.reference_index),
            ["II. 사업의 내용 > 4. 매출 및 수주상황"],
        )

    def test_extracts_single_path_with_unicode_roman_numeral(self) -> None:
        text = "☞ 주요 종속기업에 대한 사항은 'Ⅻ. 상세표'의 '1. 연결대상 종속회사 현황(상세)' 항목을 참고하시기 바랍니다."
        self.assertEqual(
            _extract_reference_section_paths(text, self.reference_index),
            ["XII. 상세표 > 1. 연결대상 종속회사 현황(상세)"],
        )


if __name__ == "__main__":
    unittest.main()
