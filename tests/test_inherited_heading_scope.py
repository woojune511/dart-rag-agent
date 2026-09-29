"""Direct P text and tails honor paragraph style without changing SPAN policy."""
import unittest
from lxml import etree
from src.processing.financial_parser import FinancialParser

TABLE = '<TABLE><TR><TD>Witness</TD><TD>42</TD></TR></TABLE>'

class InheritedHeadingScopeTests(unittest.TestCase):
    def parse(self, paragraph):
        self.root = etree.fromstring(('<SECTION-2><P>가. Earlier</P><P>[Birch]</P>' + paragraph + TABLE + '</SECTION-2>').encode())
        blocks = FinancialParser()._collect_blocks(self.root, 'I. Example', structured_override=False)
        for block in blocks:
            for context in block.get('source_contexts', []):
                node, = self.root.xpath(context['source_locator'])
                a, z = context['source_span']
                self.assertEqual(''.join(node.itertext())[a:z], context['source_text'])
        return blocks

    def test_paragraph_bold_heading_then_normal_body(self):
        rows = self.parse('<P USERMARK=" B">나. Next topic\n<SPAN USERMARK=" !B">Body 53.</SPAN></P>')
        self.assertEqual(rows[-1]['local_heading'], '나. Next topic')
        body = next(b for b in rows if 'Body 53.' in b['text'])
        self.assertEqual(body['text'], '나. Next topic\nBody 53.')
        self.assertEqual(body['local_heading'], '나. Next topic')
        self.assertNotIn('Birch', str(body.get('source_contexts')))

    def test_paragraph_tail_resumes_parent_style(self):
        rows = self.parse('<P USERMARK="B"><SPAN USERMARK="!B">Old body 31.</SPAN>나. Next topic</P>')
        self.assertEqual(rows[-1]['local_heading'], '나. Next topic')
        self.assertIn('Birch', next(b for b in rows if 'Old body' in b['text'])['local_heading'])
        source = ''.join(self.root.findall('P')[-1].itertext())
        body = ''.join(b['text'] for b in rows if 'Old body' in b['text'] or b['text']=='나. Next topic')
        self.assertEqual(''.join(body.split()), ''.join(source.split()))

    def test_paragraph_bold_negation_and_font_name_do_not_enable_style(self):
        for marks in ['!B', 'B !B', 'F-BT']:
            with self.subTest(marks=marks):
                rows = self.parse(f'<P USERMARK="{marks}">나. Inline reference<SPAN> body continues.</SPAN></P>')
                self.assertEqual(rows[-1]['local_heading'], '가. Earlier > [Birch]')

    def test_last_explicit_paragraph_style_wins(self):
        rows = self.parse('<P USERMARK="I !B B">나. Next topic<SPAN>Body 53.</SPAN></P>')
        self.assertEqual(rows[-1]['local_heading'], '나. Next topic')

    def test_wrapped_prose_and_bold_sentence_do_not_reset_heading(self):
        for text in ['See the discussion in\n28. Reference details\nfor more information.', '2023. Results were stable.', '나. Results were stable.']:
            with self.subTest(text=text):
                rows = self.parse(f'<P USERMARK="B">{text}<SPAN USERMARK="!B">Body.</SPAN></P>')
                self.assertEqual(rows[-1]['local_heading'], '가. Earlier > [Birch]')

    def test_existing_plain_and_inline_span_boundaries_remain(self):
        for p in ['<P>나. Next topic</P>', '<P><SPAN USERMARK="B">나. Next topic</SPAN>Body.</P>']:
            with self.subTest(paragraph=p):
                self.assertEqual(self.parse(p)[-1]['local_heading'], '나. Next topic')

    def test_paragraph_style_does_not_shorten_an_existing_complete_heading(self):
        rows = self.parse('<P USERMARK="B">나. Next <SPAN USERMARK="!B">topic</SPAN></P>')
        self.assertEqual(rows[-1]['local_heading'], '나. Next topic')

    def test_unmarked_span_inherits_paragraph_heading_style(self):
        rows = self.parse('<P USERMARK="B">나. First topic<SPAN USERMARK="!B">First body.</SPAN>'
                          '<SPAN>다. Next topic</SPAN><SPAN USERMARK="!B">Next body.</SPAN></P>')
        self.assertEqual(rows[-1]['local_heading'], '다. Next topic')
        self.assertEqual(next(b for b in rows if 'First body.' in b['text'])['local_heading'], '나. First topic')

if __name__ == '__main__':
    unittest.main()
