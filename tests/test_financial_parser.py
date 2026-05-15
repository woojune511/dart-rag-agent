import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from lxml import etree

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.processing.financial_parser import (
    FinancialParser,
    SectionParseTimeout,
    _classify_bracket_heading,
    _extract_standalone_table_context_hint,
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

    def test_table_chunking_propagates_header_metadata(self) -> None:
        parser = FinancialParser(chunk_size=120, chunk_overlap=20)
        rows = ["구분 | 2023년 | 2022년 | 단위: 백만원"]
        rows.extend(f"계정과목{i} | {100 + i} | {90 + i} | " for i in range(1, 10))
        table_text = "\n".join(rows)

        chunk_blocks = parser._chunk_blocks(
            [
                {
                    "text": table_text,
                    "type": "table",
                    "local_heading": "재무상태표",
                    "table_context": "요약 재무상태표",
                    "table_source_id": "section::table:1",
                    "table_header_context": "구분 | 2023년 | 2022년 | 단위: 백만원",
                    "period_labels": ["2023", "2022"],
                    "period_focus": "multi_period",
                    "unit_hint": "백만원",
                    "statement_type": "balance_sheet",
                    "consolidation_scope": "unknown",
                    "header_propagated": False,
                }
            ],
            "III. 재무에 관한 사항 > 2. 연결재무제표 > 2-1. 연결 재무상태표",
        )

        self.assertGreater(len(chunk_blocks), 1)
        self.assertTrue(all(block["table_source_id"] == "section::table:1" for block in chunk_blocks))
        self.assertTrue(
            all(block["table_header_context"] == "구분 | 2023년 | 2022년 | 단위: 백만원" for block in chunk_blocks)
        )
        self.assertTrue(all(block["period_labels"] == ["2023", "2022"] for block in chunk_blocks))
        self.assertTrue(all(block["unit_hint"] == "백만원" for block in chunk_blocks))
        self.assertTrue(any(block["header_propagated"] for block in chunk_blocks[1:]))

    def test_table_context_bundle_includes_value_records(self) -> None:
        parser = FinancialParser(chunk_size=2500, chunk_overlap=320)
        table_object = {
            "grid": [
                ["구분", "2023", "2022"],
                ["부채총계", "92,228,115", "93,674,903"],
                ["자본총계", "363,677,865", "354,749,604"],
            ],
            "row_labels": ["부채총계", "자본총계"],
            "row_count": 3,
            "column_count": 3,
            "has_spans": False,
        }

        bundle = parser._build_table_context_bundle(
            "구분 | 2023 | 2022\n부채총계 | 92,228,115 | 93,674,903\n자본총계 | 363,677,865 | 354,749,604",
            "III. 재무에 관한 사항 > 1. 요약재무정보",
            "section::table:2",
            local_heading="가. 요약연결재무정보",
            table_object=table_object,
        )

        self.assertTrue(bundle["table_value_records_json"])
        value_records = json.loads(bundle["table_value_records_json"])
        self.assertEqual(value_records[0]["semantic_label"], "부채총계")
        self.assertEqual(value_records[0]["period_text"], "2023")
        self.assertEqual(value_records[0]["value_text"], "92,228,115")

    def test_table_grid_reads_te_cells_from_tbody(self) -> None:
        parser = FinancialParser(chunk_size=2500, chunk_overlap=320)
        table = etree.fromstring(
            """
            <TABLE>
              <THEAD>
                <TR>
                  <TH>구분</TH>
                  <TH>2023</TH>
                  <TH>2022</TH>
                </TR>
              </THEAD>
              <TBODY>
                <TR>
                  <TE>부채총계</TE>
                  <TE>92,228,115</TE>
                  <TE>93,674,903</TE>
                </TR>
              </TBODY>
            </TABLE>
            """
        )

        table_object = parser._build_table_object(table)
        row_records = parser._build_table_row_records(table_object, "백만원")
        value_records = parser._build_table_value_records(
            row_records,
            table_id="section::table:te",
            unit_hint="백만원",
        )

        self.assertEqual(table_object["row_count"], 2)
        self.assertEqual(row_records[0]["row_label"], "부채총계")
        self.assertEqual(row_records[0]["cells"][0]["value_text"], "92,228,115")
        self.assertEqual(value_records[0]["semantic_label"], "부채총계")
        self.assertEqual(value_records[0]["value_text"], "92,228,115")

    def test_value_records_promote_aggregate_labels_for_wide_tables(self) -> None:
        parser = FinancialParser(chunk_size=2500, chunk_overlap=320)
        table_object = {
            "grid": [
                ["", "단기차입금", "장기 차입금", "장기 차입금"],
                ["", "단기차입금 합계", "장기차입금 합계", "장기차입금 합계"],
                ["단기차입금", "4,145,647", "", ""],
                ["합계, 장기차입금", "", "12,164,595", ""],
                ["차감: 유동성장기차입금", "", "(2,012,002)", ""],
                ["차감 계, 장기차입금", "", "10,121,033", ""],
            ],
            "row_labels": ["단기차입금", "합계, 장기차입금", "차감: 유동성장기차입금", "차감 계, 장기차입금"],
            "row_count": 6,
            "column_count": 4,
            "has_spans": False,
        }

        bundle = parser._build_table_context_bundle(
            parser._format_table_grid(table_object["grid"]),
            "III. 재무에 관한 사항 > 3. 연결재무제표 주석",
            "section::table:agg",
            local_heading="차입금 및 사채",
            table_object=table_object,
        )
        value_records = json.loads(bundle["table_value_records_json"])

        direct_total = next(record for record in value_records if record["value_text"] == "4,145,647")
        subtotal = next(record for record in value_records if record["value_text"] == "12,164,595")
        adjustment = next(record for record in value_records if record["value_text"] == "(2,012,002)")
        final_total = next(record for record in value_records if record["value_text"] == "10,121,033")

        self.assertEqual(direct_total["semantic_label"], "단기차입금 합계")
        self.assertEqual(direct_total["value_role"], "aggregate")
        self.assertEqual(direct_total["aggregation_stage"], "direct")
        self.assertEqual(direct_total["aggregate_role"], "direct_total")
        self.assertEqual(subtotal["semantic_label"], "장기차입금 합계")
        self.assertEqual(subtotal["value_role"], "aggregate")
        self.assertEqual(subtotal["aggregation_stage"], "subtotal")
        self.assertEqual(subtotal["aggregate_role"], "subtotal")
        self.assertEqual(adjustment["semantic_label"], "차감: 유동성장기차입금")
        self.assertEqual(adjustment["value_role"], "adjustment")
        self.assertEqual(adjustment["aggregation_stage"], "none")
        self.assertEqual(adjustment["aggregate_role"], "adjustment")
        self.assertEqual(final_total["semantic_label"], "장기차입금 합계")
        self.assertEqual(final_total["value_role"], "aggregate")
        self.assertEqual(final_total["aggregation_stage"], "final")
        self.assertEqual(final_total["aggregate_role"], "final_total")

    def test_standalone_period_table_is_promoted_to_context_hint(self) -> None:
        table_object = {
            "table_text": "당기 | (단위 : 백만원)",
            "row_count": 1,
            "column_count": 2,
        }

        hint = _extract_standalone_table_context_hint(table_object)

        self.assertEqual(hint, "당기 | (단위 : 백만원)")

    def test_standalone_unit_only_table_is_promoted_to_context_hint(self) -> None:
        table_object = {
            "table_text": "(단위 : 백만원)",
            "row_count": 1,
            "column_count": 1,
        }

        hint = _extract_standalone_table_context_hint(table_object)

        self.assertEqual(hint, "(단위 : 백만원)")


    def test_table_format_normalizes_merged_cells(self) -> None:
        parser = FinancialParser()
        table = etree.fromstring(
            """
            <TABLE>
              <TR>
                <TH ROWSPAN="2">구분</TH>
                <TH COLSPAN="2">2023</TH>
              </TR>
              <TR>
                <TH>1Q</TH>
                <TH>2Q</TH>
              </TR>
              <TR>
                <TD ROWSPAN="2">매출액</TD>
                <TD>10</TD>
                <TD>20</TD>
              </TR>
              <TR>
                <TD>11</TD>
                <TD>21</TD>
              </TR>
            </TABLE>
            """
        )

        table_object = parser._build_table_object(table)
        table_text = table_object["table_text"]
        bundle = parser._build_table_context_bundle(
            table_text,
            "III. 재무에 관한 사항 > 2. 연결재무제표 > 2-1. 연결 재무상태표",
            "section::table:merged",
            local_heading="연결 재무상태표",
            table_object=table_object,
        )

        self.assertIn("구분 | 2023 | 2023", table_text)
        self.assertIn("구분 | 1Q | 2Q", table_text)
        self.assertIn("매출액 | 10 | 20", table_text)
        self.assertIn("매출액 | 11 | 21", table_text)
        self.assertTrue(table_object["has_spans"])
        self.assertIn("매출액", bundle["table_row_labels_text"])
        self.assertTrue(bundle["table_has_spans"])
        row_records = json.loads(bundle["table_row_records_json"])
        sales_row = next(record for record in row_records if record["row_label"] == "매출액")
        self.assertEqual(sales_row["cells"][0]["column_headers"], ["2023", "1Q"])
        self.assertEqual(sales_row["cells"][0]["value_text"], "10")
        table_payload = json.loads(bundle["table_object_json"])
        self.assertEqual(table_payload["table_id"], "section::table:merged")
        self.assertEqual(table_payload["rows"][0]["row_label"], sales_row["row_label"])

    def test_extract_sections_falls_back_to_plain_mode_after_timeout(self) -> None:
        root = etree.fromstring(
            """
            <DOCUMENT>
              <SECTION-1>
                <TITLE ATOC="Y">III. 재무에 관한 사항</TITLE>
                <P><SPAN USERMARK=" B">(1) 재무정보 이용상의 유의점</SPAN>본문 설명</P>
              </SECTION-1>
            </DOCUMENT>
            """
        )
        parser = FinancialParser(section_warn_sec=0.0, section_parse_budget_sec=0.001)
        original_collect_blocks = parser._collect_blocks

        def fake_collect_blocks(section_elem, section_path, *, structured_override=None, deadline_monotonic=None, timeout_label=None):
            if structured_override is None:
                raise SectionParseTimeout(section_path, "paragraph:parsed", 0.25)
            return original_collect_blocks(
                section_elem,
                section_path,
                structured_override=structured_override,
                deadline_monotonic=deadline_monotonic,
                timeout_label=timeout_label,
            )

        with patch.object(parser, "_collect_blocks", side_effect=fake_collect_blocks):
            sections = parser._extract_sections(root)

        self.assertEqual(len(sections), 1)
        self.assertTrue(sections[0]["fallback_used"])
        self.assertEqual(sections[0]["parse_mode"], "plain_fallback")
        self.assertGreaterEqual(sections[0]["parse_sec"], 0.0)
        self.assertTrue(sections[0]["blocks"])


if __name__ == "__main__":
    unittest.main()
