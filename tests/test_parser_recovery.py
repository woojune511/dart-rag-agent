"""Reject unverified XML recovery before partial source text reaches ingest."""

from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from lxml import etree

from src.ingestion.ingest_service import IngestService
from src.processing.financial_parser import FinancialParser, XMLRecoveryError
from src.storage.store_manifest import canonical_store_manifest


EARLIER_SECTION = (
    '<SECTION-1><TITLE ATOC="Y">I. Earlier section</TITLE>'
    '<P>Retained observation.</P></SECTION-1>'
)
LATER_SECTION = (
    '<SECTION-1><TITLE ATOC="Y">II. Later section</TITLE>'
    '<P>Missing observation.</P></SECTION-1>'
)
TRAILING_SECTION = f'<DOCUMENT>{EARLIER_SECTION}</DOCUMENT>\n{LATER_SECTION}'


class ParserRecoveryTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.source = self.root / 'source.xml'
        self.parser = FinancialParser(section_parse_budget_sec=0)

    def write_source(self, text):
        self.source.write_text(text, encoding='utf-8')
        return str(self.source)

    def test_trailing_section_is_rejected_before_section_extraction(self):
        path = self.write_source(TRAILING_SECTION)
        original = self.source.read_bytes()
        with patch.object(self.parser, '_extract_sections') as extract:
            with self.assertRaisesRegex(XMLRecoveryError, 'XML recovery.*ERR_DOCUMENT_END') as raised:
                self.parser.process_document(path, {'rcept_no': 'anonymous'})
        extract.assert_not_called()
        self.assertEqual(self.source.read_bytes(), original)
        self.assertEqual(raised.exception.file_path, path)
        self.assertIn('line 2, column 1', str(raised.exception))

    def test_all_public_parse_paths_surface_loss_instead_of_empty_or_partial_results(self):
        path = self.write_source(TRAILING_SECTION)
        for method in (self.parser.parse_sections, self.parser.extract_structure_outline):
            with self.subTest(method=method.__name__):
                with self.assertRaisesRegex(ValueError, 'XML recovery'):
                    method(path)

    def test_mismatched_tags_are_rejected_even_when_visible_words_survive(self):
        path = self.write_source('<DOCUMENT><P>First.</WRONG><P>Second.</P></DOCUMENT>')
        with self.assertRaisesRegex(ValueError, 'ERR_TAG_NAME_MISMATCH'):
            self.parser._parse_xml(path)

    def test_nonfatal_parser_error_is_also_rejected(self):
        path = self.write_source('<DOCUMENT><unknown:P>Text.</unknown:P></DOCUMENT>')
        with self.assertRaisesRegex(ValueError, 'NS_ERR_UNDEFINED_NAMESPACE'):
            self.parser._parse_xml(path)

    def test_empty_xml_cannot_be_reported_as_successful_empty_ingest(self):
        path = self.write_source('')
        with self.assertRaisesRegex(ValueError, 'XML recovery'):
            self.parser.process_document(path, {'rcept_no': 'anonymous'})

    def test_recovery_diagnostics_do_not_leak_into_a_subsequent_valid_parse(self):
        path = self.write_source(TRAILING_SECTION)
        with self.assertRaises(ValueError):
            self.parser._parse_xml(path)
        self.write_source(f'<DOCUMENT>{EARLIER_SECTION}{LATER_SECTION}</DOCUMENT>')
        chunks = self.parser.process_document(path, {'rcept_no': 'anonymous'})
        self.assertTrue(any('Retained observation.' in chunk.content for chunk in chunks))
        self.assertTrue(any('Missing observation.' in chunk.content for chunk in chunks))

    def test_warning_only_xml_remains_accepted(self):
        path = self.write_source('<?xml version="1.1"?><DOCUMENT><P>Preserved.</P></DOCUMENT>')
        self.assertEqual(self.parser._parse_xml(path).find('P').text, 'Preserved.')

    def test_ingest_stops_before_context_generation_or_store_mutation(self):
        path = self.write_source(TRAILING_SECTION)
        report = SimpleNamespace(
            file_path=path, corp_name='Example', stock_code='000000',
            year=2042, report_type='annual', rcept_no='anonymous',
        )
        context_generator = Mock()
        context_generator.contextual_ingest.return_value = {'added_chunks': 1}
        store = SimpleNamespace(
            persist_directory=str(self.root / 'store'), bm25_docs=[],
            vector_store=SimpleNamespace(_collection=SimpleNamespace(count=lambda: 0)),
            is_indexed=lambda _receipt: False,
        )
        service = IngestService(
            Mock(fetch_company_reports=Mock(return_value=[report])),
            self.parser, context_generator, store, canonical_store_manifest(collection_name='runtime'),
        )
        with self.assertRaisesRegex(ValueError, 'XML recovery'):
            service.ingest_company('Example', [2042], max_workers=1)
        self.assertEqual(context_generator.mock_calls, [])
        self.assertFalse((self.root / 'store').exists())

    def test_diagnostic_summary_is_bounded_and_preserves_the_final_error(self):
        path = self.write_source(
            '<DOCUMENT>' + '<P>Original text.</WRONG>' * 10
            + '</DOCUMENT>' + LATER_SECTION
        )
        with self.assertRaises(XMLRecoveryError) as raised:
            self.parser._parse_xml(path)
        error = raised.exception
        self.assertGreater(error.error_count, 5)
        self.assertEqual(len(error.diagnostics), 5)
        # libxml versions differ on which error ends recovery of this malformed
        # input. Preserve the parser's actual final diagnostic, not one platform's
        # particular error name. Source bytes contain no literal-label repairs.
        reference = etree.XMLParser(recover=True, encoding='utf-8', huge_tree=True)
        try:
            etree.parse(BytesIO(self.source.read_bytes()), reference)
        except etree.XMLSyntaxError:
            pass
        reported = [entry for entry in reference.error_log if entry.level >= etree.ErrorLevels.ERROR]
        self.assertEqual(error.error_count, len(reported))
        final = reported[-1]
        self.assertEqual(
            error.diagnostics[-1],
            f'{final.level_name}/{final.type_name} at line {final.line}, column {final.column}',
        )
        self.assertNotIn('Original text.', str(error))


if __name__ == '__main__':
    unittest.main()
