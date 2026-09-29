"""Only label tables may be consumed as context; table prose remains evidence."""
import unittest
from unittest.mock import patch

from lxml import etree

from src.processing.financial_parser import FinancialParser, _extract_standalone_table_context_hint


class TableContextHintPreservationTests(unittest.TestCase):
    def setUp(self):
        for name in ('socket.socket.connect', 'socket.create_connection'):
            self.enterContext(patch(name, side_effect=AssertionError('Provider-free test')))
        self.parser = FinancialParser(section_parse_budget_sec=0)

    def table(self, text):
        element = etree.Element('TABLE')
        etree.SubElement(etree.SubElement(element, 'TR'), 'TE').text = text
        return self.parser._build_table_object(element)

    def test_short_prose_with_period_is_not_a_context_label(self):
        text = '당기에는 방식을 변경하였습니다.'
        self.assertIsNone(_extract_standalone_table_context_hint(self.table(text)))

    def test_short_prose_with_statement_name_is_not_a_context_label(self):
        text = '현금흐름표에 표시한 방식은 다음 문단에서 설명합니다.'
        self.assertIsNone(_extract_standalone_table_context_hint(self.table(text)))

    def test_long_single_cell_prose_is_kept_through_chunking(self):
        text = '(1) 당기에는 다음 방식을 적용합니다. ' + '원문의 설명을 그대로 보존합니다. ' * 180 + '(2) 최종 기록입니다.'
        for mode in (False, True):
            for grouped in (False, True):
                with self.subTest(structured=mode, grouped=grouped):
                    section = etree.Element('SECTION-2')
                    etree.SubElement(section, 'P').text = '[Outer]'
                    owner = etree.SubElement(section, 'TABLE-GROUP') if grouped else section
                    table = etree.SubElement(owner, 'TABLE')
                    etree.SubElement(etree.SubElement(table, 'TR'), 'TE').text = text
                    blocks = self.parser._collect_blocks(section, 'Synthetic section', structured_override=mode)
                    self.assertEqual([b['text'] for b in blocks], [text.strip()])
                    self.assertTrue(all(b['local_heading'] == '[Outer]' for b in blocks))
                    chunks = self.parser._chunk_blocks(blocks, 'Synthetic section')
                    compact = lambda value: ''.join(value.split())
                    self.assertIn(compact(text), compact(''.join(c['text'] for c in chunks)))

    def test_small_numeric_table_with_period_in_row_label_is_preserved(self):
        obj = dict(table_text='당기 금액 | 42', row_count=1, column_count=2)
        self.assertIsNone(_extract_standalone_table_context_hint(obj))

    def test_real_period_unit_and_date_labels_remain_context(self):
        for text in ('당기 | (단위 : 백만원)', '(단위 : 백만원)', '(단위: 회, %)',
                     '(단위: USD 천, 천원)', '(단위 : 원화-백만원)',
                     '[2023.12.31 현재] | (원화단위 : 백만원, 외화단위 : 천USD)',
                     '(누적) | (단위 : 백만원,%)', '[요약] | (단위 : 백만원)',
                     '(기준일 : | 2023년 12월 31일 | )',
                     '(2023.1.1~2023.12.31) | (단위: 천원)'):
            with self.subTest(text=text):
                self.assertIsNotNone(_extract_standalone_table_context_hint(self.table(text)))

    def test_statement_title_dates_and_unit_remain_context(self):
        text = '연결 포괄손익계산서\n제 25 기 2023.01.01 부터 2023.12.31 까지\n제 24 기 2022.01.01 부터 2022.12.31 까지\n(단위 : 원)'
        obj = dict(table_text=text, row_count=4, column_count=1)
        self.assertEqual(_extract_standalone_table_context_hint(obj), ' '.join(text.splitlines()))

    def test_unit_label_propagates_without_consuming_following_prose(self):
        section = etree.fromstring('<SECTION-2><P>[Outer]</P><TABLE><TR><TD>당기</TD><TD>(단위 : 백만원)</TD></TR></TABLE><TABLE><TR><TE>당기에는 방법을 유지합니다.</TE></TR></TABLE></SECTION-2>')
        blocks = self.parser._collect_blocks(section, 'Synthetic section')
        self.assertEqual(len(blocks), 1)
        self.assertEqual(blocks[0]['text'], '당기에는 방법을 유지합니다.')
        self.assertEqual(blocks[0]['unit_hint'], '백만원')
        self.assertEqual(blocks[0]['local_heading'], '[Outer]')

    def test_mixed_caption_body_survives_and_only_explicit_unit_is_forwarded(self):
        for label in ('[Example] | (단위 : 백만원)', '[Example]\n(단위: 백만원)',
                      '(기준일: 2023. 12. 31) | (단위 : 백만원)',
                      '(단위: 백만원, 인원별 시간 합계)', '(외화: 천, 원화: 백만원)',
                      '설명이 이어집니다.(단위 : 백만원, 천 USD)'):
            for grouped in (False, True):
                with self.subTest(label=label, grouped=grouped):
                    section = etree.Element('SECTION-2')
                    owner = etree.SubElement(section, 'TABLE-GROUP') if grouped else section
                    table = etree.SubElement(owner, 'TABLE')
                    etree.SubElement(etree.SubElement(table, 'TR'), 'TE').text = label
                    owner.append(etree.fromstring('<TABLE><TR><TD>Item</TD><TD>42</TD></TR></TABLE>'))
                    blocks = self.parser._collect_blocks(section, 'Synthetic section')
                    self.assertEqual(len(blocks), 2)
                    self.assertEqual(blocks[0]['text'], label)
                    self.assertEqual(blocks[1]['unit_hint'], '백만원')
                    self.assertNotIn('[Example]', blocks[1].get('table_header_context', ''))

    def test_prose_unit_mentions_do_not_label_the_next_table(self):
        for text in ('당기에 50%를 반영합니다.', '단위원가는 방식에 따라 정합니다.',
                     '당기에는 42백만원이 포함되었습니다.'):
            with self.subTest(text=text):
                section = etree.Element('SECTION-2')
                table = etree.SubElement(section, 'TABLE')
                etree.SubElement(etree.SubElement(table, 'TR'), 'TE').text = text
                section.append(etree.fromstring('<TABLE><TR><TD>Item</TD><TD>42</TD></TR></TABLE>'))
                blocks = self.parser._collect_blocks(section, 'Synthetic section')
                self.assertEqual(len(blocks), 2)
                self.assertIsNone(blocks[1]['unit_hint'])

    def test_paragraph_ends_forwarded_unit_context(self):
        section = etree.fromstring('<SECTION-2><TABLE><TR><TE>[Example] (단위 : 백만원)</TE></TR></TABLE><P>A separate paragraph.</P><TABLE><TR><TD>Item</TD><TD>42</TD></TR></TABLE></SECTION-2>')
        blocks = self.parser._collect_blocks(section, 'Synthetic section')
        self.assertIsNone(blocks[-1]['unit_hint'])


if __name__ == '__main__':
    unittest.main()
