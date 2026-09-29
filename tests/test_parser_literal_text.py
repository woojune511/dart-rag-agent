"""Anonymous XML text-preservation regressions, including malformed input."""
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from src.processing.financial_parser import FinancialParser, _sanitize_xml_like_text


class ParserLiteralTextTests(unittest.TestCase):
    def parse(self, source):
        with TemporaryDirectory() as directory:
            path = Path(directory) / "source.xml"
            path.write_text(source, encoding="utf-8")
            return FinancialParser()._parse_xml(str(path))

    def test_bare_ampersands_preserve_adjacent_names_and_spaced_text(self):
        for surface in ("X&YUnit label.", "Alpha & Beta.", "A&B부문 내용.", "A&unknown; B"):
            with self.subTest(surface=surface):
                root = self.parse(f"<DOCUMENT><P>{surface}</P></DOCUMENT>")
                self.assertEqual("".join(root.find("P").itertext()), surface)

    def test_malformed_neighbor_does_not_damage_valid_entity(self):
        root = self.parse("<DOCUMENT><P>X&YUnit.</P><P>A&amp;B.</P></DOCUMENT>")
        self.assertEqual([node.text for node in root.findall("P")], ["X&YUnit.", "A&B."])

    def test_predefined_and_numeric_entities_are_decoded_once(self):
        root = self.parse("<DOCUMENT><P>&amp; &lt; &gt; &apos; &quot; &#38; &#x26; &amp;amp;</P></DOCUMENT>")
        self.assertEqual(root.find("P").text, "& < > ' \" & & &amp;")

    def test_cdata_comments_and_processing_instructions_are_not_escaped(self):
        source = "<DOCUMENT><!--A&B <literal>--><?probe A&B?><P><![CDATA[A&B <literal>]]></P></DOCUMENT>"
        sanitized, _ = _sanitize_xml_like_text(source)
        self.assertEqual(sanitized, source)
        self.assertEqual(self.parse(source).find("P").text, "A&B <literal>")

    def test_attributes_and_inline_markup_keep_text_and_structure(self):
        root = self.parse('<DOCUMENT><P LABEL="A&B > C">A&B <SPAN>C&amp;D</SPAN> E&F</P></DOCUMENT>')
        paragraph = root.find("P")
        self.assertEqual(paragraph.get("LABEL"), "A&B > C")
        self.assertEqual("".join(paragraph.itertext()), "A&B C&D E&F")
        self.assertEqual(paragraph.find("SPAN").text, "C&D")

    def test_xml_like_display_and_ampersand_repairs_are_idempotent(self):
        source = "<DOCUMENT><P><1 & 2> A&B</P></DOCUMENT>"
        once, _ = _sanitize_xml_like_text(source)
        twice, _ = _sanitize_xml_like_text(once)
        self.assertEqual(once, twice)
        self.assertEqual(self.parse(source).find("P").text, "<1 & 2> A&B")


if __name__ == "__main__":
    unittest.main()
