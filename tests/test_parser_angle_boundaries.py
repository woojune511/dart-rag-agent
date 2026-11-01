"""Literal less-than text cannot consume the following XML tag boundary."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.processing.financial_parser import (
    FinancialParser,
    XMLRecoveryError,
    _sanitize_xml_like_text,
)


class ParserAngleBoundaryTests(unittest.TestCase):
    def parse(self, source):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'source.xml'
            path.write_text(source, encoding='utf-8')
            return FinancialParser()._parse_xml(str(path))

    def test_standalone_angle_preserves_closing_tag_and_following_text(self):
        root = self.parse('<DOCUMENT><P><SPAN><</SPAN><SPAN>Label></SPAN></P></DOCUMENT>')
        spans = root.findall('.//SPAN')
        self.assertEqual([span.text for span in spans], ['<', 'Label>'])
        self.assertEqual(''.join(root.find('P').itertext()), '<Label>')

    def test_literal_comparison_and_unclosed_display_keep_the_original_surface(self):
        for literal in ('5< duration', '<50 units', '<표시 제목〉 ', '< A&B', '<<<'):
            with self.subTest(literal=literal):
                root = self.parse(f'<DOCUMENT><P>{literal}</P><P>Following.</P></DOCUMENT>')
                self.assertEqual([p.text for p in root.findall('P')], [literal, 'Following.'])

    def test_literal_before_an_opening_tag_preserves_inline_and_later_structure(self):
        source = ('<DOCUMENT><SECTION-1><TITLE ATOC="Y">I. Earlier</TITLE>'
                  '<P>Value (<50 units).\n<SPAN>Inline.</SPAN></P></SECTION-1>'
                  '<SECTION-1><TITLE ATOC="Y">II. Later</TITLE><P>Still present.</P>'
                  '</SECTION-1></DOCUMENT>')
        root = self.parse(source)
        sections = root.findall('SECTION-1')
        self.assertEqual(len(sections), 2)
        self.assertEqual(''.join(sections[0].find('P').itertext()), 'Value (<50 units).\nInline.')
        self.assertEqual(sections[1].find('P').text, 'Still present.')

    def test_only_literal_angle_changes_and_line_count_is_preserved(self):
        source = '<DOCUMENT>\n<P>Value <50\n<SPAN>Inline.</SPAN></P>\n</DOCUMENT>'
        expected = source.replace('Value <50', 'Value &lt;50')
        sanitized, changes = _sanitize_xml_like_text(source)
        self.assertEqual(sanitized, expected)
        self.assertEqual(changes, 1)
        self.assertEqual(_sanitize_xml_like_text(sanitized), (sanitized, 0))
        self.assertEqual(sanitized.count('\n'), source.count('\n'))

    def test_complete_markup_and_literal_regions_are_unchanged(self):
        source = ('<DOCUMENT><!--< literal--><?test <literal?>'
                  '<P LABEL="a > b"><![CDATA[<literal]]><CUSTOM>Content</CUSTOM></P>'
                  '</DOCUMENT>')
        self.assertEqual(_sanitize_xml_like_text(source), (source, 0))
        self.assertEqual(self.parse(source).find('.//CUSTOM').text, 'Content')

    def test_entities_after_the_repaired_boundary_are_decoded_without_loss(self):
        root = self.parse(
            '<DOCUMENT><P><</P><P>A&amp;B &lt;X&gt; &#49; &amp;amp;</P></DOCUMENT>'
        )
        self.assertEqual([p.text for p in root.findall('P')], ['<', 'A&B <X> 1 &amp;'])

    def test_ambiguous_unclosed_tags_and_broken_attributes_remain_blocked(self):
        for source in (
            '<DOCUMENT><P><LABEL>Some content.</P></DOCUMENT>',
            '<DOCUMENT><P>Text <SPAN <B>More.</B></P></DOCUMENT>',
            '<DOCUMENT><P>Text <SPAN A="broken<SPAN>More.</SPAN></P></DOCUMENT>',
            '<DOCUMENT><P>Text <',
        ):
            with self.subTest(source=source):
                with self.assertRaises(XMLRecoveryError):
                    self.parse(source)


if __name__ == '__main__':
    unittest.main()
