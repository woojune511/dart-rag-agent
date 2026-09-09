"""Source coverage of numbered long-table prose, using synthetic text only."""

import unittest

from src.processing.chunking import split_table_text_fragment


class ParserFragmentCoverageTests(unittest.TestCase):
    def test_numbered_fragments_preserve_leading_context(self):
        source = "Applies to the western branch. (1)first observation. (2)second observation."
        parts = split_table_text_fragment(source, 40, normalize_text=lambda text: text)
        self.assertEqual("".join(parts), source)
        self.assertTrue(all(len(part) <= 40 for part in parts))

    def test_starting_at_first_marker_does_not_add_empty_or_duplicate_parts(self):
        source = "(1)first observation. (2)second observation."
        parts = split_table_text_fragment(source, 30, normalize_text=lambda text: text)
        self.assertEqual("".join(parts), source)
        self.assertTrue(all(part for part in parts))

    def test_source_order_and_coverage_across_marker_styles(self):
        for markers in (("(1)", "(2)"), ("①", "②")):
            with self.subTest(markers=markers):
                source = f"Scope before lists. {markers[0]}Alpha section. {markers[1]}Beta section."
                parts = split_table_text_fragment(source, 30, normalize_text=lambda text: text)
                self.assertEqual("".join(parts), source)


if __name__ == "__main__":
    unittest.main()
