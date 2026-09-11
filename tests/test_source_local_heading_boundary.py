"""Source-local headings survive layout changes but never masquerade as body."""
from copy import deepcopy
import unittest
from unittest.mock import patch

from lxml import etree

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin, _semantic_candidate_visibility
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog, semantic_candidate_catalog_fingerprint
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.processing.financial_parser import FinancialParser
from tests.semantic_program_test_support import _obligation


def paragraph(text, layout):
    if layout == "span":
        return f'<P><SPAN USERMARK="B">{text}</SPAN></P>'
    if layout == "bold":
        return f'<P USERMARK="B">{text}</P>'
    return f'<P>{text}</P>'


def catalog_for(text, **metadata):
    return build_semantic_candidate_catalog([{
        "candidate_id": "source-A", "candidate_kind": "chunk",
        "source_anchor": "[Parent group | 2042 | Chapter > Routes]",
        "text": " ".join(text.split()), "source_text_exact": text,
        "metadata": {"company": "Parent group", "year": 2042, "is_table": False, **metadata},
    }])


class SourceLocalHeadingBoundaryTests(unittest.TestCase):
    def test_peer_heading_replaces_prior_scope_in_all_paragraph_layouts(self):
        for layout in ("plain", "bold", "span"):
            for names in (("Amber", "Birch"), ("Quartz", "Maple")):
                with self.subTest(layout=layout, names=names):
                    xml = '<SECTION-2>' + ''.join(
                        paragraph(f'[{name}]', layout) + paragraph('가. Routes', layout)
                        + f'<P>{name} uses partner locations.</P>' for name in names
                    ) + '</SECTION-2>'
                    blocks = FinancialParser()._collect_blocks(etree.fromstring(xml.encode()),
                        'II. Example > 4. Routes', structured_override=True)
                    self.assertEqual([block['local_heading'] for block in blocks],
                        [f'[{name}] > 가. Routes' for name in names])

    def test_bracket_scope_does_not_leak_across_explicit_section_boundary(self):
        xml = ('<DOCUMENT><SECTION-1><TITLE ATOC="Y">II. Example</TITLE>'
               '<SECTION-2><TITLE ATOC="Y">1. Routes</TITLE><P>[Amber]</P><P>First source.</P></SECTION-2>'
               '<SECTION-2><TITLE ATOC="Y">2. Routes</TITLE><P>Second source.</P></SECTION-2>'
               '</SECTION-1></DOCUMENT>')
        sections = FinancialParser()._extract_sections(etree.fromstring(xml.encode()))
        self.assertEqual(sections[0]['blocks'][0]['local_heading'], '[Amber]')
        self.assertIsNone(sections[1]['blocks'][0]['local_heading'])

    def test_table_caption_is_local_but_prior_scope_is_preserved_after_table(self):
        table = '<TABLE><THEAD><TR><TH>Route</TH></TR></THEAD><TBODY><TR><TD>Partner locations</TD></TR></TBODY></TABLE>'
        xml = '<SECTION-2><P>[Amber]</P><P>Amber source.</P><P>[Table caption]</P>' + table + '<P>Amber continuation.</P></SECTION-2>'
        blocks = FinancialParser()._collect_blocks(etree.fromstring(xml.encode()),
            'II. Example > 4. Routes', structured_override=True)
        self.assertEqual([block['local_heading'] for block in blocks], ['[Amber]', '[Table caption]', '[Amber]'])

    def test_nested_prefix_is_not_body_and_exact_offsets_survive(self):
        prefix = ('[company: not a recognized prefix]\n')
        # Unknown labels remain source text, unlike the declared structural prefix.
        body = 'Birch ships through partners.\r\n[Note: source-owned [nested] brackets stay.]'
        metadata = '[local_heading: [Amber] > 가. Routes]\r\n[table_context: old [context] hint]\r\n[회사: Parent group] [연도: 2042]\r\n\r\n'
        for leading in (metadata, metadata.replace('\r\n', '\n')):
            row = next(row for row in catalog_for(leading + body) if row['kind'] == 'narrative')
            self.assertEqual(row['source_text'], body)
            self.assertEqual(row['source_bundle_context_span'], [len(leading), len(leading + body)])
        row = next(row for row in catalog_for(prefix + body) if row['kind'] == 'narrative')
        self.assertEqual(row['source_text'], prefix + body)

    def test_table_context_cannot_inherit_a_previous_peer_paragraph(self):
        blocks = [
            {'text': 'Amber routes use partner locations.', 'type': 'paragraph', 'local_heading': '[Amber]'},
            {'text': 'Birch | Direct delivery', 'type': 'table', 'local_heading': '[Birch]'},
        ]
        before = deepcopy(blocks)
        chunks = FinancialParser()._chunk_blocks(blocks, 'II. Example > 4. Routes')
        table = next(row for row in chunks if 'Birch' in row['text'])
        self.assertNotIn('Amber', table['table_context'])
        self.assertEqual(blocks, before)

    def test_table_caption_does_not_hide_same_scope_paragraph_context(self):
        table = '<TABLE><THEAD><TR><TH>Route</TH></TR></THEAD><TBODY><TR><TD>Partner locations</TD></TR></TBODY></TABLE>'
        xml = '<SECTION-2><P>[Amber]</P><P>Amber source context.</P><P>[Table caption]</P>' + table + '</SECTION-2>'
        parser = FinancialParser()
        blocks = parser._collect_blocks(etree.fromstring(xml.encode()), 'II. Example > 4. Routes', structured_override=True)
        chunks = parser._chunk_blocks(blocks, 'II. Example > 4. Routes')
        table_chunk = next(row for row in chunks if 'Partner locations' in row['text'])
        self.assertIn('Amber source context.', table_chunk['table_context'])

    def test_body_projection_does_not_rekey_candidates_or_change_numeric_records(self):
        text = '[local_heading: [Birch]]\nBirch reports 17%.'
        with patch('src.agent.financial_reconciliation_candidates._narrative_source_projection', return_value={}):
            original = catalog_for(text, local_heading='[Birch]')
        current = catalog_for(text, local_heading='[Birch]')
        self.assertEqual([row['candidate_id'] for row in original], [row['candidate_id'] for row in current])
        self.assertEqual(semantic_candidate_catalog_fingerprint(original), semantic_candidate_catalog_fingerprint(current))
        numeric = [row for row in current if row['kind'] == 'numeric']
        self.assertTrue(numeric)
        self.assertEqual(numeric, [row for row in original if row['kind'] == 'numeric'])

    def test_unbalanced_or_mixed_metadata_looking_source_is_not_deleted(self):
        for text in ('[local_heading: [Amber]\nOriginal body.',
                     '[local_heading: Amber] This is original prose.',
                     '[Note: [local_heading: not metadata]]\nOriginal body.'):
            self.assertEqual(next(row for row in catalog_for(text) if row['kind'] == 'narrative')['source_text'], text)

    def test_local_heading_is_separate_prompt_context_not_document_subject(self):
        body = 'Birch ships through partners.'
        catalog = catalog_for('[local_heading: [Birch] > 가. Routes]\n' + body,
            local_heading='[Birch] > 가. Routes')
        row = next(row for row in catalog if row['kind'] == 'narrative')
        before = deepcopy(catalog)
        fingerprint = semantic_candidate_catalog_fingerprint(catalog)
        payload = FinancialAgentCalculationMixin._semantic_program_prompt_payload(catalog,
            {'visible_candidate_ids': [row['candidate_id']]})
        visible = payload['candidates_by_id'][row['candidate_id']]
        self.assertEqual(visible['local_heading'], '[Birch] > 가. Routes')
        self.assertEqual(payload['document_provenance']['candidates_by_id'][row['candidate_id']]['document_company'], 'Parent group')
        self.assertEqual(visible['local_entity_surfaces'], [])  # No guessed entity classifier.
        bundle = payload['source_bundles_by_id'][visible['source_bundle_id']]
        from tests.compiler_presentation_test_support import bundle_text
        self.assertEqual(bundle_text(payload, bundle['source_bundle_id']), body)
        self.assertEqual(catalog, before)
        self.assertEqual(semantic_candidate_catalog_fingerprint(catalog), fingerprint)

    def test_heading_change_is_bound_by_execution_content_not_a_new_authority(self):
        catalog = catalog_for('Birch ships through partners.', local_heading='[Birch]')
        row = next(row for row in catalog if row['kind'] == 'narrative')
        owners = [_obligation('routes', 'narrative', 'Routes')]
        program = {'narrative_bindings': [{'obligation_id': 'routes', 'text': 'Birch ships through partners.',
            'evidence_bindings': [{'candidate_id': row['candidate_id']}]}]}
        visibility = _semantic_candidate_visibility(catalog, visible_candidate_ids=[row['candidate_id']],
            candidate_ids_by_owner={'routes': [row['candidate_id']]})
        inputs = dict(candidate_catalog=catalog, obligations=owners, query='Describe routes.')
        validation = validate_semantic_calculation_program(program=program, candidate_visibility=visibility, **inputs)
        self.assertEqual(validation['status'], 'ready')
        envelope = CompilationEnvelopeV2.create(program=program, validation=validation, visibility=visibility, **inputs)
        catalog[0]['local_heading'] = '[Other source]'
        with patch('src.agent.financial_calculation_execution.validate_semantic_calculation_program') as validator:
            execution = execute_semantic_calculation_program(program=program, compilation_envelope=envelope,
                require_compilation_envelope=True, **inputs)
        validator.assert_not_called()
        self.assertEqual(execution['validation']['errors'][0]['code'], 'execution_content_mismatch')


if __name__ == '__main__':
    unittest.main()
