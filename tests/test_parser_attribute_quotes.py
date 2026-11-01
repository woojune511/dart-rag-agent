"""Anonymous malformed-attribute regressions at the XML ingestion boundary."""

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.processing.financial_parser import FinancialParser, _sanitize_xml_like_text


class ParserAttributeQuoteTests(unittest.TestCase):
    def parse(self, source):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.xml"
            path.write_text(source, encoding="utf-8")
            return FinancialParser()._parse_xml(str(path))

    def test_doubled_attribute_delimiters_preserve_cell_and_literal_quotes(self):
        source = '<DOCUMENT><TABLE><TR><TH LABEL=""Quoted name"" WIDTH="12">Cell value</TH><TD>42</TD></TR></TABLE></DOCUMENT>'
        root = self.parse(source)
        header = root.find(".//TH")
        self.assertIsNotNone(header)
        self.assertEqual(header.text, "Cell value")
        self.assertEqual(header.get("LABEL"), '"Quoted name"')
        self.assertEqual(header.get("WIDTH"), "12")
        self.assertEqual(root.find(".//TD").text, "42")

    def test_later_sections_survive_repeated_malformed_header_attributes(self):
        table = '<TABLE><THEAD><TR><TH LABEL=""Quoted name"">Column</TH></TR></THEAD><TBODY><TR><TD>42</TD></TR></TBODY></TABLE>'
        source = ('<DOCUMENT><BODY><SECTION-1><TITLE ATOC="Y">I. Earlier section</TITLE>'
                  + table * 4
                  + '</SECTION-1><SECTION-1><TITLE ATOC="Y">IV. Later section</TITLE>'
                  '<P>The later observation remains available.</P></SECTION-1></BODY></DOCUMENT>')
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.xml"
            path.write_text(source, encoding="utf-8")
            chunks = FinancialParser(section_parse_budget_sec=0).process_document(
                str(path), {"rcept_no": "anonymous", "company": "Example", "year": 2025}
            )
        later = [c for c in chunks if c.metadata["section_path"] == "IV. Later section"]
        self.assertTrue(later)
        self.assertIn("The later observation remains available.", "\n".join(c.content for c in later))

    def test_valid_attributes_and_lexical_literal_regions_stay_unchanged(self):
        source = ('<DOCUMENT><!--LABEL=""literal""--><P A="" B="" C="&quot;name&quot;">'
                  '<![CDATA[LABEL=""literal""]]></P></DOCUMENT>')
        sanitized, changes = _sanitize_xml_like_text(source)
        self.assertEqual(sanitized, source)
        self.assertEqual(changes, 0)
        paragraph = self.parse(source).find("P")
        self.assertEqual(paragraph.attrib, {"A": "", "B": "", "C": '"name"'})
        self.assertEqual(paragraph.text, 'LABEL=""literal""')

    def test_repair_is_idempotent_and_preserves_line_positions(self):
        source = '<DOCUMENT>\n<P LABEL=""A&B"">Text</P>\n</DOCUMENT>'
        once, _ = _sanitize_xml_like_text(source)
        twice, changes = _sanitize_xml_like_text(once)
        self.assertEqual(once, twice)
        self.assertEqual(changes, 0)
        self.assertEqual(once.count("\n"), source.count("\n"))
        paragraph = self.parse(source).find("P")
        self.assertIsNotNone(paragraph)
        self.assertEqual(paragraph.get("LABEL"), '"A&B"')
        self.assertEqual(paragraph.sourceline, 2)

    def test_candidate_must_be_complete_markup_before_repair_is_accepted(self):
        source = '<DOCUMENT><P><display words LABEL=""name""> remains text</P></DOCUMENT>'
        root = self.parse(source)
        paragraph = root.find("P")
        self.assertEqual("".join(paragraph.itertext()), '<display words LABEL=""name""> remains text')
        self.assertEqual(len(paragraph), 0)


if __name__ == "__main__":
    unittest.main()
