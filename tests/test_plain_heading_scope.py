"""Numbered peer boundaries, inline labels and captions in plain sections."""
import unittest
from lxml import etree
from src.processing.financial_parser import FinancialParser

TABLE = '<TABLE><TR><TD>Value</TD><TD>12.5</TD></TR></TABLE>'


class PlainHeadingScopeTests(unittest.TestCase):
    def parse(self, text, structured=False):
        self.root = etree.fromstring(('<SECTION-2>' + text + '</SECTION-2>').encode())
        self.parser = FinancialParser()
        return self.parser._collect_blocks(self.root, 'I. Example > 1. Overview', structured_override=structured)

    def test_numbered_peer_closes_nested_bracket_and_splits_chunk(self):
        rows = self.parse('<P>사. Earlier topic</P><P>[Birch]</P><P>Birch body.</P>'
                          '<P>아. Next topic</P><P>Issuer body.</P>' + TABLE)
        issuer = next(r for r in rows if 'Issuer body' in r['text'])
        self.assertEqual(issuer['local_heading'], '아. Next topic')
        self.assertNotIn('Birch', rows[-1]['local_heading'])
        chunks = self.parser._chunk_blocks(rows, 'I. Example > 1. Overview')
        self.assertFalse(any('Birch body' in c['text'] and 'Issuer body' in c['text'] for c in chunks))

    def test_bracket_child_is_preserved_until_observed_parent_peer(self):
        rows = self.parse('<P>가. Parent topic</P><P>[Birch]</P><P>(1) Child topic</P>'
                          '<P>Child body.</P><P>(2) Other child</P><P>Other body.</P>'
                          '<P>나. Next topic</P><P>Next body.</P>')
        for row in rows:
            if row['text'] in ('Child body.', 'Other body.'):
                self.assertIn('[Birch]', row['local_heading'])
        self.assertEqual(rows[-1]['local_heading'], '나. Next topic')

    def test_bracket_root_keeps_numbered_children_without_observed_outer_parent(self):
        rows = self.parse('<P>[Birch]</P><P>가. Child topic</P><P>Body.</P>')
        self.assertEqual(rows[-1]['local_heading'], '[Birch] > 가. Child topic')

    def test_inline_labels_and_bold_peer_keep_all_text_and_exact_locations(self):
        rows = self.parse('<P>가. Parent topic</P><P>[Birch]Birch body 31.</P>'
                          '<P><SPAN USERMARK="B">[Maple]</SPAN>Maple body 42.</P>'
                          '<P><SPAN USERMARK="B">나. Next topic</SPAN>Issuer body 53.</P>')
        self.assertIn('[Maple]', next(r for r in rows if '42' in r['text'])['local_heading'])
        self.assertEqual(rows[-1]['local_heading'], '나. Next topic')
        self.assertEqual(''.join(''.join(r['text'].split()) for r in rows),
                         ''.join(''.join(self.root.itertext()).split()))
        for row in rows:
            for c in row.get('source_contexts', []):
                node, = self.root.xpath(c['source_locator'])
                start, end = c['source_span']
                self.assertEqual(''.join(node.itertext())[start:end], c['source_text'])

    def test_caption_does_not_replace_owner(self):
        rows = self.parse('<P>가. Parent topic</P><P>[Birch]</P><P>Before.</P>'
                          '<P>[Caption]</P>' + TABLE + '<P>After.</P>')
        table = next(r for r in rows if r['type'] == 'table')
        self.assertEqual(table['local_heading'], '[Caption]')
        self.assertIn('[Birch]', table['local_heading_scope'])
        self.assertIn('[Birch]', rows[-1]['local_heading'])
        self.assertNotIn('Caption', rows[-1]['local_heading'])

    def test_unmarked_prose_and_bracket_in_body_do_not_reset_scope(self):
        rows = self.parse('<P>[Birch]</P><P>Refer to [Maple] for details.</P><P>2023. Results were stable.</P>')
        self.assertTrue(all(r['local_heading'] == '[Birch]' for r in rows))

    def test_peer_return_also_works_in_structured_mode(self):
        rows = self.parse('<P>가. Earlier</P><P>[Birch]</P><P>Body.</P>'
                          '<P>나. Next</P><P>Issuer.</P>', structured=True)
        self.assertEqual(rows[-1]['local_heading'], '나. Next')

    def test_other_numbering_families_close_only_observed_parent(self):
        for first, second, child in [('1. Earlier', '2. Next', '가. Child'),
                                      ('(1) Earlier', '(2) Next', '(가) Child')]:
            with self.subTest(first=first):
                rows = self.parse(f'<P>{first}</P><P>[Birch]</P><P>{child}</P><P>Child body.</P>'
                                  f'<P>{second}</P><P>Next body.</P>')
                self.assertIn('[Birch]', next(r for r in rows if r['text'] == 'Child body.')['local_heading'])
                self.assertEqual(rows[-1]['local_heading'], second)

    def test_multiple_bold_headings_in_one_paragraph_keep_separate_scopes(self):
        rows = self.parse('<P><SPAN USERMARK="B">가. Earlier</SPAN>First 10.'
                          '<SPAN USERMARK="B">나. Next</SPAN>Second 20.</P>')
        self.assertEqual(len(rows), 2)
        self.assertEqual([r['local_heading'] for r in rows], ['가. Earlier', '나. Next'])
        self.assertEqual(''.join(''.join(r['text'].split()) for r in rows),
                         ''.join(''.join(self.root.itertext()).split()))

    def test_v2_store_requires_explicit_successor_after_heading_fix(self):
        from dataclasses import replace
        from tempfile import TemporaryDirectory
        from src.storage.store_manifest import canonical_store_manifest, write_store_manifest, assess_store_readiness
        expected = canonical_store_manifest(collection_name='scope-test')
        old = replace(expected, ingest=replace(expected.ingest, parser_schema_version='financial_parser_v2_source_context'))
        with TemporaryDirectory() as directory:
            path = write_store_manifest(directory, old)
            before = path.read_bytes()
            self.assertEqual(assess_store_readiness(directory, expected=expected).status, 'mismatch')
            self.assertEqual(path.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
