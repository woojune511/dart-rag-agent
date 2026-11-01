"""Explicit forward period captions stay with their own physical value table."""
import json
import unittest
from unittest.mock import patch

from lxml import etree

from src.processing.financial_parser import FinancialParser


def data_table(value, rows=1):
    body = ''.join(f'<TR><TD>Item{i}</TD><TD>{value+i}</TD></TR>' for i in range(rows))
    return '<TABLE><THEAD><TR><TH>Item</TH><TH>Amount</TH></TR></THEAD><TBODY>'+body+'</TBODY></TABLE>'


UNIT = '<TABLE><TR><TD>(단위: 천원)</TD></TR></TABLE>'


class ForwardTableCaptionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('Offline only')))
        self.parser = FinancialParser(section_parse_budget_sec=0)

    def parse(self, body, *, size=2500, structured=True):
        parser = self.parser if size==2500 else FinancialParser(chunk_size=size, chunk_overlap=20)
        root = etree.fromstring('<SECTION-2>'+body+'</SECTION-2>')
        blocks = parser._collect_blocks(root, 'Synthetic section', structured_override=structured)
        return blocks, parser._chunk_blocks(blocks, 'Synthetic section')

    def test_period_introduction_moves_forward_not_onto_previous_value_table(self):
        for structured in (False, True):
            with self.subTest(structured=structured):
                intro = '다음은 항목별 내역입니다.① 당기말'
                blocks, chunks = self.parse('<P>① 당기말</P>'+UNIT+data_table(100)+
                    '<P>② 전기말</P>'+UNIT+data_table(90)+'<P>'+intro+'</P>'+UNIT+data_table(7), structured=structured)
                tables = [b for b in blocks if b['type']=='table']
                by_table = {b.get('table_source_id'):b for b in chunks if b.get('table_source_id')}
                for table, caption in zip(tables, ('① 당기말','② 전기말',intro)):
                    chunk = by_table[table['table_source_id']]
                    self.assertEqual(chunk['table_context'], caption)
                    self.assertEqual(chunk['text'], caption+'\n\n'+table['text'])
                self.assertNotIn(intro,by_table[tables[1]['table_source_id']]['text'])
                self.assertNotIn('② 전기말',by_table[tables[0]['table_source_id']]['text'])

    def test_two_row_period_unit_caption_preserves_body_and_binds_value_context(self):
        caption = '<TABLE><TR><TD COLSPAN="2">Categories by location</TD></TR><TR><TD>당기</TD><TD>(단위: 천원)</TD></TR></TABLE>'
        for grouped in (False,True):
            body = data_table(99)+caption+data_table(42)
            if grouped: body='<TABLE-GROUP>'+body+'</TABLE-GROUP>'
            with self.subTest(grouped=grouped):
                blocks,chunks = self.parse(body)
                source,target = blocks[-2:]
                selected=next(c for c in chunks if c.get('table_source_id')==target['table_source_id'])
                self.assertEqual(selected['table_context'], source['text'])
                self.assertIn('당기',selected['table_context'])
                self.assertEqual(selected['text'],target['text'])
                self.assertTrue(any(c['text']==source['text'] for c in chunks))
                self.assertEqual(target['table_header_context'],'Item | Amount')
                table=json.loads(target['table_object_json'])
                self.assertEqual(table['rows'][0]['cells'][0]['value_text'],'42')
                self.assertTrue(any(c['relation']=='caption' and 'Categories by location' in c['source_text'] for c in table['source_contexts']))

    def test_plain_period_text_is_located_through_unit_and_page_break(self):
        blocks,chunks=self.parse('<P>② 전기말</P>'+UNIT+'<PGBRK/>'+data_table(90))
        table=json.loads(blocks[-1]['table_object_json'])
        caption=next(c for c in table['source_contexts'] if c['relation']=='caption')
        self.assertEqual(caption['source_locator'],'/SECTION-2/P')
        self.assertEqual(caption['source_text'],'② 전기말')
        self.assertEqual(chunks[-1]['table_context'],'② 전기말')

    def test_next_period_stays_visible_in_every_large_table_fragment(self):
        blocks,chunks=self.parse(data_table(1)+'<P>② 전기말</P>'+UNIT+data_table(100,30),size=180)
        target=blocks[-1]['table_source_id']
        parts=[c for c in chunks if c.get('table_source_id')==target]
        self.assertGreater(len(parts),1)
        self.assertTrue(all(c['table_context']=='② 전기말' for c in parts))
        self.assertTrue(all(c['text'].startswith('Item | Amount') for c in parts))
        self.assertNotIn('② 전기말', next(c['text'] for c in chunks if c.get('table_source_id')==blocks[0]['table_source_id']))

    def test_prose_containing_period_word_is_not_promoted(self):
        for text in ('당기에는 방식을 변경하였습니다.','설명 끝의 전기말','다음 표를 보세요.'):
            blocks,_=self.parse(data_table(1)+'<P>'+text+'</P>'+data_table(2))
            self.assertFalse(any(b.get('table_prefix_target') for b in blocks))

    def test_mixed_table_prose_is_not_promoted_from_a_period_mention(self):
        blocks,_=self.parse('<TABLE><TR><TD>당기에 42천원을 사용하였습니다. (단위: 천원)</TD></TR></TABLE>'+data_table(2))
        self.assertFalse(any(b.get('table_prefix_target') for b in blocks))

    def test_intervening_content_period_or_container_blocks_binding(self):
        barriers=('<P>Unrelated paragraph.</P>',
                  '<TABLE><TR><TD>당기</TD><TD>(단위: 천원)</TD></TR></TABLE>',
                  '<TABLE><TR><TD>연결 재무상태표 (단위: 천원)</TD></TR></TABLE>',
                  '<P>[Different heading]</P>')
        for barrier in barriers:
            with self.subTest(barrier=barrier):
                blocks,_=self.parse('<P>② 전기말</P>'+barrier+data_table(2))
                self.assertFalse(blocks[0].get('table_prefix_target'))
        blocks,_=self.parse('<P>② 전기말</P><TABLE-GROUP>'+data_table(2)+'</TABLE-GROUP>')
        self.assertFalse(blocks[0].get('table_prefix_target'))

    def test_no_target_or_long_intro_remains_unbound(self):
        for body in ('<P>② 전기말</P>', '<P>'+('설명입니다. '*80)+'① 당기말</P>'+data_table(2)):
            blocks,_=self.parse(body)
            self.assertFalse(any(b.get('table_prefix_target') for b in blocks))

    def test_literal_text_between_elements_prevents_forward_binding(self):
        for body in ('<P>② 전기말</P>Intervening text.'+data_table(2),
                     '<P>② 전기말</P>'+UNIT+'Intervening text.'+data_table(2)):
            blocks,_=self.parse(body)
            self.assertFalse(any(b.get('table_prefix_target') for b in blocks))

    def test_caption_cannot_evict_existing_source_context_at_the_budget(self):
        rows=''.join('<TR><TD>'+('Explanation '+chr(65+i)+' ')*90+'</TD></TR>' for i in range(7))
        body='<P>② 전기말</P>'+UNIT+'<TABLE>'+rows+'<TR><TD>Item</TD><TD>42</TD></TR></TABLE>'
        with patch('src.processing.financial_parser._is_forward_table_caption',return_value=False):
            baseline,_=self.parse(body)
        actual,_=self.parse(body)
        self.assertFalse(any(b.get('table_prefix_target') for b in actual))
        self.assertEqual(json.loads(actual[-1]['table_object_json'])['source_contexts'],
                         json.loads(baseline[-1]['table_object_json'])['source_contexts'])


if __name__=='__main__':
    unittest.main()
