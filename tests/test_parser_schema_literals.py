"""Schema-bound recovery of unpaired literal labels, without label-name rules."""

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from lxml import etree

from src.processing.financial_parser import (
    FinancialParser,
    XMLRecoveryError,
    _dart_schema_vocabulary,
    _sanitize_xml_like_text,
)


DART_ROOT = ('<DOCUMENT xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
             'xsi:noNamespaceSchemaLocation="dart4.xsd">')


class ParserSchemaLiteralTests(unittest.TestCase):
    def parse(self, source):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'source.xml'
            path.write_text(source, encoding='utf-8')
            return FinancialParser()._parse_xml(str(path))

    def test_unpaired_labels_preserve_cell_text_entities_and_following_structure(self):
        source = (DART_ROOT + '<BODY><TABLE><TBODY><TR><TD><ALPHA> first '
                  'A&amp;B <BETA> second &lt;later&gt;</TD><TD>Adjacent.</TD>'
                  '</TR></TBODY></TABLE><P>Following.</P></BODY></DOCUMENT>')
        expected = source.replace('<ALPHA>', '&lt;ALPHA&gt;').replace('<BETA>', '&lt;BETA&gt;')
        self.assertEqual(_sanitize_xml_like_text(source), (expected, 2))
        root = self.parse(source)
        self.assertEqual([c.text for c in root.findall('.//TD')],
                         ['<ALPHA> first A&B <BETA> second <later>', 'Adjacent.'])
        self.assertEqual(root.find('.//BODY/P').text, 'Following.')
        self.assertEqual(_sanitize_xml_like_text(expected), (expected, 0))

    def test_rule_uses_schema_mixed_content_and_arbitrary_names(self):
        for parent in ('P', 'SPAN', 'A', 'TD', 'TH', 'TE'):
            for label in ('UNLISTED', 'label_2', 'name-with-dot.v3'):
                with self.subTest(parent=parent, label=label):
                    source = DART_ROOT + f'<BODY><{parent}><{label}> text</{parent}></BODY></DOCUMENT>'
                    self.assertEqual(self.parse(source).find(f'.//{parent}').text, f'<{label}> text')

    def test_paired_unknown_and_self_closing_elements_remain_markup(self):
        source = DART_ROOT + '<P><CUSTOM>Text</CUSTOM><EMPTY/></P></DOCUMENT>'
        self.assertEqual(_sanitize_xml_like_text(source), (source, 0))
        root = self.parse(source)
        self.assertEqual(root.find('.//CUSTOM').text, 'Text')
        self.assertIsNotNone(root.find('.//EMPTY'))

    def test_comments_cdata_instructions_and_attributes_are_not_tag_evidence(self):
        source = (DART_ROOT + '<P ID="&lt;/ALPHA&gt;">'
                  '<!-- </ALPHA> --><?hint </ALPHA>?>'
                  '<![CDATA[</ALPHA>]]><ALPHA> A&amp;B</P></DOCUMENT>')
        expected = source.replace('<ALPHA> A', '&lt;ALPHA&gt; A')
        self.assertEqual(_sanitize_xml_like_text(source), (expected, 1))
        self.assertEqual(''.join(self.parse(source).find('P').itertext()), '</ALPHA><ALPHA> A&B')

    def test_missing_wrong_or_spoofed_schema_does_not_enable_recovery(self):
        for opening in (
            '<DOCUMENT>', DART_ROOT.replace('dart4.xsd', 'dart3.xsd'),
            DART_ROOT.replace('dart4.xsd', 'https://example.invalid/dart4.xsd'),
            DART_ROOT.replace('http://www.w3.org/2001/XMLSchema-instance', 'urn:other'),
            DART_ROOT.replace('<DOCUMENT ', '<OTHER '),
        ):
            source = opening + '<P><ALPHA> text</P>' + ('</OTHER>' if '<OTHER ' in opening else '</DOCUMENT>')
            with self.subTest(opening=opening), self.assertRaises(XMLRecoveryError):
                self.parse(source)

    def test_structural_damage_and_nonliteral_candidates_still_fail_closed(self):
        for content in (
            '<P><SPAN>text</P>', '<TABLE><ALPHA>text</TABLE>',
            '<P><ALPHA ID="x">text</P>', '<P><x:ALPHA>text</P>',
            '<P><ALPHA>text</P><P></ALPHA></P>',
            '<P><ALPHA>text</P><TABLE><TR></TABLE>',
            '<P><ALPHA>text', '<P><ALPHA>text</P></DOCUMENT><P>extra</P>',
            '<CUSTOM><P><ALPHA>text</P></CUSTOM>',
            '<P xmlns="urn:extension"><ALPHA>text</P>',
            '<P><ALPHA>text</P><!-- unterminated',
        ):
            with self.subTest(content=content), self.assertRaises(XMLRecoveryError):
                self.parse(DART_ROOT + content + '</DOCUMENT>')

    def test_doctype_does_not_enable_schema_literal_recovery(self):
        source = '<!DOCTYPE DOCUMENT [<!ELEMENT ALPHA (#PCDATA)>]>' + DART_ROOT + '<P><ALPHA>text</P></DOCUMENT>'
        with self.assertRaises(XMLRecoveryError):
            self.parse(source)

    def test_bundled_schema_is_the_reviewed_official_distribution(self):
        path = Path(__file__).resolve().parents[1] / 'src/config/schemas/Dart4.xsd'
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                         'fafe75a2fde9854271c4568f6f510952292c0a829b411cc43b97f23a190ce6c2')

    def test_missing_or_corrupt_schema_keeps_the_xml_error_gate(self):
        real_parse = etree.parse
        source = DART_ROOT + '<P><ALPHA>text</P></DOCUMENT>'
        for failure in (OSError('missing schema'), etree.XMLSyntaxError('bad schema', 1, 1, 1)):
            def parse_with_unavailable_schema(path, *args, **kwargs):
                if isinstance(path, str) and path.endswith('Dart4.xsd'):
                    raise failure
                return real_parse(path, *args, **kwargs)

            _dart_schema_vocabulary.cache_clear()
            try:
                with patch('src.processing.financial_parser.etree.parse', side_effect=parse_with_unavailable_schema):
                    with self.assertLogs('src.processing.financial_parser', level='WARNING'):
                        with self.assertRaises(XMLRecoveryError):
                            self.parse(source)
                    valid = DART_ROOT + '<P>Still present.</P></DOCUMENT>'
                    self.assertEqual(self.parse(valid).find('P').text, 'Still present.')
            finally:
                _dart_schema_vocabulary.cache_clear()


if __name__ == '__main__':
    unittest.main()
