"""Wide table views retain original cells and their row/column axes."""
import json
import unittest
from unittest.mock import patch
from xml.sax.saxutils import escape

from lxml import etree

from src.processing.financial_parser import FinancialParser


def table_xml(headers, body):
    def rows(values, tag):
        return ''.join('<TR>' + ''.join(f'<{tag}>{escape(cell)}</{tag}>' for cell in row) + '</TR>' for row in values)
    return '<TABLE><THEAD>' + rows(headers, 'TH') + '</THEAD><TBODY>' + rows(body, 'TD') + '</TBODY></TABLE>'


class WideTableAxesTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch('socket.socket.connect', side_effect=AssertionError('Offline only')))

    def parse(self, headers, body, size=350):
        parser = FinancialParser(chunk_size=size, chunk_overlap=20)
        root = etree.fromstring(('<SECTION-2>' + table_xml(headers, body) + '</SECTION-2>').encode())
        blocks = parser._collect_blocks(root, 'Synthetic', structured_override=True)
        return blocks[0], parser._chunk_blocks(blocks, 'Synthetic')

    def test_blank_header_keeps_every_numeric_value_under_its_original_column(self):
        for first in ('', 'Item'):
            block, chunks = self.parse([[first, *[f'C{i:02}' for i in range(1, 41)]]], [['Alpha', *map(str, range(1, 41))]])
            self.assertGreater(len(chunks), 1)
            seen = set()
            for chunk in chunks:
                header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
                self.assertEqual(row[0], 'Alpha')
                self.assertEqual(header[0], first)
                self.assertEqual(len(header), len(row))
                for h, value in zip(header[1:], row[1:]):
                    self.assertEqual(h, f'C{int(value):02}')
                    seen.add(value)
            self.assertEqual(seen, set(map(str, range(1, 41))))
            self.assertTrue(all(c['table_object_json'] == block['table_object_json'] for c in chunks))

    def test_two_row_axes_and_unit_column_repeat_in_every_window(self):
        headers = [['Group', 'Item', 'Unit', *[f'C{i:02}' for i in range(1, 41)]]]
        body = [['Outer', 'Alpha', 'thousand USD', *map(str, range(1, 41))]]
        _, chunks = self.parse(headers, body, size=450)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertEqual(header[:3], headers[0][:3])
            self.assertEqual(row[:3], body[0][:3])
            for h, value in zip(header[3:], row[3:]):
                self.assertEqual(h, f'C{int(value):02}')

    def test_every_row_fragment_repeats_all_explicit_header_rows(self):
        headers = [['Item', *['Current'] * 40], ['Item', *[f'C{i:02}' for i in range(1, 41)]]]
        body = [[f'R{r}', *[str(r * 100 + c) for c in range(1, 41)]] for r in range(1, 8)]
        _, chunks = self.parse(headers, body, size=400)
        self.assertGreater(len(chunks), 2)
        observed = set()
        for chunk in chunks:
            rows = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertTrue(all(value == 'Current' for value in rows[0][1:]))
            for row in rows[2:]:
                r = int(row[0][1:])
                for h, value in zip(rows[1][1:], row[1:]):
                    self.assertEqual(int(value), r * 100 + int(h[1:]))
                    observed.add(value)
        self.assertEqual(observed, {str(r * 100 + c) for r in range(1, 8) for c in range(1, 41)})

    def test_blank_cells_keep_positions_including_trailing_blank(self):
        body = ['Alpha', *map(str, range(1, 41))]
        body[5] = body[22] = body[40] = ''
        headers = [['', *[f'C{i:02}' for i in range(1, 41)]]]
        _, chunks = self.parse(headers, [body])
        found = {}
        for chunk in chunks:
            header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertEqual(len(header), len(row))
            self.assertEqual(row[0], 'Alpha')
            found.update(zip(header[1:], row[1:]))
        self.assertEqual(found, dict(zip(headers[0][1:], body[1:])))

    def test_cell_containing_literal_separator_is_not_a_new_source_column(self):
        headers = [['Item', *[f'C{i:02}' for i in range(1, 41)]]]
        body = ['Alpha', *map(str, range(1, 41))]
        body[23] = 'literal | separator'
        _, chunks = self.parse(headers, [body], size=450)
        self.assertTrue(any('literal | separator' in c['text'] for c in chunks))
        for chunk in chunks:
            header, row = chunk['text'].splitlines()
            # The original source cell remains intact; the next source column
            # still carries value 24 in the same window, not the split tail.
            if 'C24' in header:
                self.assertIn('literal | separator | 24', row)

    def test_long_wide_row_is_never_split_across_column_positions(self):
        headers = [['Item', *[f'C{i:02}' for i in range(1, 41)]]]
        body = ['Alpha', *map(str, range(1, 41))]
        body[7] = 'LongCell' * 100
        _, chunks = self.parse(headers, [body], size=350)
        long_chunk = next(c for c in chunks if body[7] in c['text'])
        self.assertGreater(len(long_chunk['text']), 350)
        header, row = [line.split(' | ') for line in long_chunk['text'].splitlines()]
        self.assertEqual(row[0], 'Alpha')
        self.assertEqual(row[header.index('C07')], body[7])

    def test_numeric_only_rows_keep_all_values_without_invented_axis(self):
        headers = [[f'C{i:02}' for i in range(40)]]
        body = [list(map(str, range(40)))]
        _, chunks = self.parse(headers, body, size=300)
        seen = set()
        for chunk in chunks:
            header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
            for h, value in zip(header, row):
                self.assertEqual(h, f'C{int(value):02}')
                seen.add(value)
        self.assertEqual(seen, set(map(str, range(40))))

    def test_merged_multirow_headers_and_rowspan_axis_keep_source_coordinates(self):
        header = '<THEAD><TR><TH ROWSPAN="2">Item</TH><TH COLSPAN="40">Current</TH></TR><TR>' + ''.join(f'<TH>C{i:02}</TH>' for i in range(1, 41)) + '</TR></THEAD>'
        body = '<TBODY><TR><TD ROWSPAN="2">Alpha (USD)</TD>' + ''.join(f'<TD>{i}</TD>' for i in range(1, 41)) + '</TR><TR>' + ''.join(f'<TD>{100+i}</TD>' for i in range(1, 41)) + '</TR></TBODY>'
        parser = FinancialParser(chunk_size=400, chunk_overlap=20)
        root = etree.fromstring(('<SECTION-2><TABLE>' + header + body + '</TABLE></SECTION-2>').encode())
        block = parser._collect_blocks(root, 'Synthetic', structured_override=True)[0]
        chunks = parser._chunk_blocks([block], 'Synthetic')
        expected = set(map(str, [*range(1, 41), *range(101, 141)]))
        observed = set()
        for chunk in chunks:
            rows = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertTrue(all(value == 'Current' for value in rows[0][1:]))
            for row in rows[2:]:
                self.assertEqual(row[0], 'Alpha (USD)')
                for h, value in zip(rows[1][1:], row[1:]):
                    self.assertEqual(int(value) % 100, int(h[1:]))
                    observed.add(value)
            self.assertEqual(chunk['table_object_json'], block['table_object_json'])
        self.assertEqual(observed, expected)

    def test_explicit_zero_header_wide_table_does_not_turn_first_value_row_into_header(self):
        block, chunks = self.parse([], [['Alpha', *map(str, range(1, 41))]], size=150)
        self.assertEqual(json.loads(block['table_object_json'])['header_rows'], [])
        found = set()
        for chunk in chunks:
            self.assertEqual(len(chunk['text'].splitlines()), 1)
            row = chunk['text'].split(' | ')
            self.assertEqual(row[0], 'Alpha')
            found.update(row[1:])
        self.assertEqual(found, set(map(str, range(1, 41))))

    def test_numeric_identifier_does_not_hide_the_following_row_label(self):
        headers = [['ID', 'Item', *[f'C{i:02}' for i in range(1, 41)]]]
        _, chunks = self.parse(headers, [['1', 'Alpha', *map(str, range(1, 41))]], size=350)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertEqual(row[:2], ['1', 'Alpha'])
            for h, value in zip(header[2:], row[2:]):
                self.assertEqual(h, f'C{int(value):02}')

    def test_different_axis_depths_preserve_each_rows_label(self):
        headers = [['Group', 'Item', *[f'C{i:02}' for i in range(1, 41)]]]
        body = [['Total', '1', *map(str, range(1, 41))], ['Outer', 'Alpha', *map(str, range(1, 41))]]
        _, chunks = self.parse(headers, body, size=350)
        for chunk in chunks:
            rows = [line.split(' | ') for line in chunk['text'].splitlines()]
            for row in rows[1:]:
                self.assertIn(row[:2], [b[:2] for b in body])
                for h, value in zip(rows[0][2:], row[2:]):
                    self.assertEqual(h, f'C{int(value):02}')

    def test_blank_cells_before_first_value_do_not_expand_axes_or_drop_cells(self):
        headers = [['Item', *[f'C{i:02}' for i in range(1, 41)]]]
        body = ['Alpha', *([''] * 30), *map(str, range(31, 41))]
        _, chunks = self.parse(headers, [body], size=300)
        observed = {}
        for chunk in chunks:
            header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertEqual(row[0], 'Alpha')
            self.assertLessEqual(len(row), 24)
            observed.update(zip(header[1:], row[1:]))
        self.assertEqual(observed, dict(zip(headers[0][1:], body[1:])))

    def test_uncertain_axis_at_last_column_keeps_the_entire_row(self):
        headers = [[f'C{i:02}' for i in range(41)]]
        body = [*map(str, range(40)), 'Label at end']
        _, chunks = self.parse(headers, [body], size=200)
        self.assertEqual(len(chunks), 1)
        header, row = [line.split(' | ') for line in chunks[0]['text'].splitlines()]
        self.assertEqual(header, headers[0])
        self.assertEqual(row, body)

    def test_numeric_identifier_before_multiple_axes_and_unit_keeps_entire_prefix(self):
        headers = [['ID', 'Group', 'Item', 'Unit', *[f'C{i:02}' for i in range(1, 41)]]]
        body = ['1', 'Outer', 'Alpha', 'USD', *map(str, range(1, 41))]
        _, chunks = self.parse(headers, [body], size=350)
        self.assertGreater(len(chunks), 1)
        for chunk in chunks:
            header, row = [line.split(' | ') for line in chunk['text'].splitlines()]
            self.assertEqual(row[:4], body[:4])
            for h, value in zip(header[4:], row[4:]):
                self.assertEqual(h, f'C{int(value):02}')

    def test_small_wide_table_stays_whole_when_no_split_is_needed(self):
        headers = [['', *[f'C{i:02}' for i in range(1, 41)]]]
        body = [['Alpha', *map(str, range(1, 41))]]
        block, chunks = self.parse(headers, body, size=2500)
        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0]['text'], block['text'])
        self.assertEqual(chunks[0]['table_view'], 'full')


if __name__ == '__main__':
    unittest.main()
