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
    FinancialParser,
    _classify_bracket_heading,
    _is_structured_section,
    _looks_like_local_heading,
    _prepare_stack_for_heading,
    _sanitize_xml_like_text,
    _should_discard_bracket_heading,
    _should_promote_deferred_bracket_heading,
    _soft_heading_path,
    _split_compound_heading_text,
    _split_inline_heading_body,
)


class FinancialParserUtilityTests(unittest.TestCase):
    def test_sanitize_xml_like_text_escapes_textual_angle_brackets_only(self) -> None:
        raw = "<ROOT><P><소매판매액 중 온라인쇼핑 거래액 비중 ></P><SPAN USERMARK=\" B\">정상 태그</SPAN></ROOT>"
        sanitized, count = _sanitize_xml_like_text(raw)

        self.assertEqual(count, 1)
        self.assertIn("&lt;소매판매액 중 온라인쇼핑 거래액 비중 &gt;", sanitized)
        self.assertIn("<SPAN USERMARK=\" B\">정상 태그</SPAN>", sanitized)

    def test_structured_section_whitelist_is_narrow(self) -> None:
        self.assertTrue(_is_structured_section("III. 재무에 관한 사항 > 3. 연결재무제표 주석"))
        self.assertTrue(_is_structured_section("IV. 이사의 경영진단 및 분석의견"))
        self.assertTrue(_is_structured_section("II. 사업의 내용 > 7. 기타 참고사항"))
        self.assertFalse(_is_structured_section("I. 회사의 개요 > 2. 회사의 연혁"))
        self.assertFalse(_is_structured_section("VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항"))

    def test_soft_heading_path_keeps_at_most_two_levels(self) -> None:
        self.assertIsNone(_soft_heading_path([]))
        self.assertEqual(_soft_heading_path(["[클라우드]"]), "[클라우드]")
        self.assertEqual(
            _soft_heading_path(["3. 재무상태 및 영업실적", "나. 영업실적"]),
            "3. 재무상태 및 영업실적 > 나. 영업실적",
        )
        self.assertEqual(
            _soft_heading_path(["[클라우드]", "(1) 산업의 개요", "(가) 영업 개요"]),
            "[클라우드] > (가) 영업 개요",
        )

    def test_inline_heading_body_split_is_conservative(self) -> None:
        split = _split_inline_heading_body("(3) 연구개발실적2019년~2023년 말 현재 ...")
        self.assertIsNotNone(split)
        headings, body = split or ([], "")
        self.assertEqual(headings, ["(3) 연구개발실적"])
        self.assertTrue(body.startswith("2019년"))

        split = _split_inline_heading_body("(2) 경쟁환경- 카메라: 글로벌 시장에서 ...")
        self.assertIsNotNone(split)
        headings, body = split or ([], "")
        self.assertEqual(headings, ["(2) 경쟁환경"])
        self.assertTrue(body.startswith("- 카메라:"))

        self.assertIsNone(_split_inline_heading_body("(가) 산업의 개요네이버는 ..."))

    def test_circled_number_is_not_treated_as_independent_heading(self) -> None:
        self.assertFalse(_looks_like_local_heading("① 외환위험"))
        self.assertFalse(_looks_like_local_heading("(1)"))
        self.assertFalse(_looks_like_local_heading("(가)"))
        self.assertFalse(_looks_like_local_heading("3. 제품 에너지 소비효율 규정 (예: EU ErP Directive)"))

    def test_noisy_heading_suffix_is_trimmed_to_clean_prefix(self) -> None:
        self.assertEqual(
            _split_compound_heading_text("(가) 외환위험① 외환위험"),
            ["(가) 외환위험"],
        )
        self.assertEqual(
            _split_compound_heading_text("(3) 영업의 개황 - 카메라: 스노우는"),
            ["(3) 영업의 개황"],
        )
        self.assertEqual(
            _split_compound_heading_text("(1) 합병, 분할, 자산양수도, 영업양수도① 서치솔루션 합병"),
            ["(1) 합병, 분할, 자산양수도, 영업양수도"],
        )

    def test_attached_heading_markers_are_split_when_both_sides_are_valid(self) -> None:
        self.assertEqual(
            _split_compound_heading_text("4. 유동성 및 자금의 조달과 지출가. 유동성에 관한 사항"),
            ["4. 유동성 및 자금의 조달과 지출", "가. 유동성에 관한 사항"],
        )
        self.assertEqual(
            _split_compound_heading_text("5. 부외거래가. 지급보증"),
            ["5. 부외거래", "가. 지급보증"],
        )

    def test_date_bracket_heading_is_discarded_in_mda(self) -> None:
        self.assertTrue(
            _should_discard_bracket_heading("[2021년 12월]", "IV. 이사의 경영진단 및 분석의견")
        )
        self.assertFalse(
            _should_discard_bracket_heading("[클라우드]", "II. 사업의 내용 > 7. 기타 참고사항")
        )

    def test_bracket_heading_is_classified_by_role(self) -> None:
        self.assertEqual(
            _classify_bracket_heading(
                "[회사의 연혁]",
                "I. 회사의 개요 > 2. 회사의 연혁",
                "TABLE",
                has_body_segments=False,
            ),
            "table_label",
        )
        self.assertEqual(
            _classify_bracket_heading(
                "[클라우드]",
                "II. 사업의 내용 > 7. 기타 참고사항",
                None,
                has_body_segments=True,
            ),
            "defer_section_label",
        )
        self.assertEqual(
            _classify_bracket_heading(
                "[친환경인프라(건설부문)]",
                "II. 사업의 내용 > 7. 기타 참고사항",
                None,
                has_body_segments=True,
            ),
            "section_label",
        )
        self.assertEqual(
            _classify_bracket_heading(
                "[2021년 12월]",
                "IV. 이사의 경영진단 및 분석의견",
                None,
                has_body_segments=True,
            ),
            "discard",
        )

    def test_bracket_context_is_trimmed_for_high_value_children(self) -> None:
        self.assertEqual(
            _prepare_stack_for_heading(
                ["[클라우드]"],
                "가. 회사의 고객관리 정책",
                "II. 사업의 내용 > 7. 기타 참고사항",
            ),
            [],
        )
        self.assertEqual(
            _prepare_stack_for_heading(
                ["[클라우드]"],
                "(가) 산업의 특성",
                "II. 사업의 내용 > 7. 기타 참고사항",
            ),
            ["[클라우드]"],
        )

    def test_deferred_bracket_heading_promotes_only_for_supported_children(self) -> None:
        self.assertTrue(
            _should_promote_deferred_bracket_heading(
                "(가) 산업의 특성",
                "II. 사업의 내용 > 7. 기타 참고사항",
            )
        )
        self.assertFalse(
            _should_promote_deferred_bracket_heading(
                "라. 사업부문별 요약 재무 현황",
                "II. 사업의 내용 > 7. 기타 참고사항",
            )
        )

    def test_wide_table_is_split_into_column_windows(self) -> None:
        parser = FinancialParser(chunk_size=2500, chunk_overlap=320)
        wide_row = " | ".join(f"회사{i}" for i in range(1, 41))
        table_text = "\n".join(
            [
                "전체 종속기업 | 전체 종속기업 합계",
                "종속기업",
                wide_row,
            ]
        )

        windows = parser._split_wide_table_by_columns(table_text)

        self.assertIsNotNone(windows)
        self.assertGreater(len(windows or []), 1)
        for window in windows or []:
            self.assertIn("전체 종속기업 | 전체 종속기업 합계", window)
            self.assertIn("종속기업", window)

    def test_wide_table_chunking_can_apply_column_then_row_split(self) -> None:
        parser = FinancialParser(chunk_size=120, chunk_overlap=20)
        wide_row = " | ".join(f"회사{i}" for i in range(1, 41))
        table_text = "\n".join(
            [
                "전체 종속기업 | 전체 종속기업 합계",
                "종속기업",
                wide_row,
                wide_row,
            ]
        )

        chunks = parser._split_table_for_chunks(table_text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(any(chunk["table_view"] == "column_row_window" for chunk in chunks))

    def test_narrative_table_row_is_not_mistaken_for_header(self) -> None:
        parser = FinancialParser(chunk_size=2500, chunk_overlap=320)

        self.assertFalse(
            parser._looks_like_table_header_row(
                "1. 분할방법 | (1) 상법 제530조의2 내지 제530조의12의 규정이 정하는 바에 따라 아래와 같이 분할되는 회사가 영위하는 사업부문 중 분할대상 사업부문을 분할하여 분할신설회사를 설립하고, 존속회사가 분할대상 사업부문을 제외한 나머지 사업부문을 영위한다."
            )
        )

    def test_long_label_value_row_is_split_inside_table(self) -> None:
        parser = FinancialParser(chunk_size=180, chunk_overlap=20)
        table_text = (
            "1. 분할방법 | "
            "(1) 상법 제530조의2 내지 제530조의12의 규정이 정하는 바에 따라 분할되는 회사가 영위하는 사업부문 중 분할대상 사업부문을 분할한다. "
            "(2) 분할기일은 2020년 3월 31일로 하되, 이사회 결의로 변경할 수 있다. "
            "(3) 존속회사와 분할신설회사는 분할 전의 채무에 관하여 각 연대하여 변제할 책임이 있다. "
            "(4) 권리와 의무의 귀속은 분할계획서가 정하는 바에 따른다."
        )

        chunks = parser._split_table_for_chunks(table_text)

        self.assertGreater(len(chunks), 1)
        self.assertTrue(all(chunk["table_view"] == "row_window" for chunk in chunks))
        self.assertTrue(all(chunk["text"].startswith("1. 분할방법 | ") for chunk in chunks))
        self.assertTrue(any("(2) 분할기일은 2020년 3월 31일로 하되" in chunk["text"] for chunk in chunks))


if __name__ == "__main__":
    unittest.main()
