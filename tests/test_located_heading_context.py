"""Located intermediate headings, not inferred entities or benchmark answers."""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from langchain_core.documents import Document

from src.agent.financial_calculation_execution import (
    execute_semantic_calculation_program, validate_semantic_calculation_program,
)
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin, _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_reconciliation_candidates import (
    build_semantic_source_candidates, build_semantic_candidate_catalog, semantic_candidate_catalog_fingerprint,
)
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.agent.financial_candidate_matching import project_candidate_fact
from src.processing.financial_parser import FinancialParser
from src.storage.metadata_payloads import compact_node_for_storage, metadata_for_chroma, metadata_with_table_payload, load_table_payloads
from tests.semantic_program_test_support import _obligation


TABLE = ('<TABLE><THEAD><TR><TH>Route</TH><TH>Description</TH></TR></THEAD>'
         '<TBODY><TR><TD>Delivery</TD><TD>We use partners.</TD></TR></TBODY></TABLE>')


def xml(body):
    return '<DOCUMENT><SECTION-1><TITLE ATOC="Y">II. Example</TITLE>' + body + '</SECTION-1></DOCUMENT>'


def catalog(chunks):
    docs = [(Document(page_content=c.content, metadata=deepcopy(c.metadata)), 0.0) for c in chunks]
    return from_docs(docs)


def from_docs(docs):
    sources = build_semantic_source_candidates({'retrieved_docs': docs},
        source_anchor_builder=lambda m: f"[{m['company']} | {m['year']} | {m['section_path']}]")
    return build_semantic_candidate_catalog(sources)


class LocatedHeadingContextTests(unittest.TestCase):
    def parse(self, text, **kwargs):
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'source.xml'
            path.write_text(text, encoding='utf-8')
            parser = FinancialParser(**kwargs)
            chunks = parser.process_document(str(path), {'company': 'Issuer', 'year': 2042, 'rcept_no': 'source'})
            return chunks, parser._parse_xml(str(path)), hashlib.sha256(path.read_bytes()).hexdigest()

    def assert_located(self, rows, root, digest):
        contexts = [c for r in rows for c in r.get('source_contexts') or []]
        self.assertTrue(contexts)
        for context in contexts:
            if context.get('document_sha256') != digest:
                continue
            node, = root.xpath(context['source_locator'])
            start, end = context['source_span']
            self.assertEqual(''.join(node.itertext())[start:end], context['source_text'])
            self.assertLessEqual(len(context['source_text']), 1200)
            self.assertTrue(context['context_id'].startswith('ctx_'))

    def test_paragraph_heading_layouts_reach_exact_quoteable_context(self):
        for name in ('Aspen', '오로라', 'Mizu & Co.'):
            for template in ('<P>[{}]</P>', '<P USERMARK="B">[{}]</P>', '<P><SPAN USERMARK="B">[{}]</SPAN></P>'):
                with self.subTest(name=name, template=template):
                    chunks, root, digest = self.parse(xml(template.format(name) + '<P>We use partners.</P>'))
                    rows = catalog(chunks)
                    self.assert_located(rows, root, digest)
                    self.assertTrue(all(any(c['source_text'] == f'[{name}]' and c['relation'] == 'intermediate_heading'
                        for c in row.get('source_contexts', [])) for row in rows))
                    self.assertTrue(all(name not in row['source_text'] for row in rows))
                    for row in rows:
                        fact = project_candidate_fact(row)
                        self.assertIn(f'[{name}]', fact.text_metric_surfaces)
                        self.assertEqual(fact.identity_surfaces, ())

    def test_inline_heading_preserves_only_exact_heading_span(self):
        text = xml('<P><SPAN USERMARK="B">[North\t  Unit]</SPAN><SPAN> We use partners.</SPAN>'
                   '<SPAN USERMARK="B">[South]</SPAN><SPAN> We deliver directly.</SPAN></P>')
        parser = FinancialParser()
        from lxml import etree
        root = etree.fromstring(text.encode())
        blocks = parser._collect_blocks(root[0], 'II. Example', structured_override=True)
        from src.processing.source_context import bind_document_contexts
        bind_document_contexts([{'blocks': blocks}], 'source-sha')
        self.assertEqual(len(blocks), 2)
        headings = [[c for c in b.get('source_contexts', []) if c['relation'] == 'intermediate_heading'] for b in blocks]
        self.assertEqual([[c['source_text'] for c in group] for group in headings], [['[North\t  Unit]'], ['[South]']])
        for group in headings:
            for context in group:
                node, = root.xpath(context['source_locator'])
                start, end = context['source_span']
                self.assertEqual(''.join(node.itertext())[start:end], context['source_text'])
                self.assertNotIn('We ', context['source_text'])

    def test_peer_and_explicit_section_contexts_do_not_leak(self):
        text = xml('<SECTION-2><TITLE ATOC="Y">1. First</TITLE><P>[Aspen]</P><P>We use partners.</P>'
                   + TABLE + '<P>[Birch]</P><P>We deliver directly.</P>' + TABLE + '</SECTION-2>'
                   '<SECTION-2><TITLE ATOC="Y">2. Next</TITLE><P>We operate locally.</P></SECTION-2>')
        chunks, root, digest = self.parse(text)
        rows = catalog(chunks)
        self.assert_located(rows, root, digest)
        for row in rows:
            contexts = ' '.join(c['source_text'] for c in row.get('source_contexts', []))
            hint = row.get('local_heading', '')
            if hint == '[Aspen]':
                self.assertIn('[Aspen]', contexts)
                self.assertNotIn('[Birch]', contexts)
            elif hint == '[Birch]':
                self.assertIn('[Birch]', contexts)
                self.assertNotIn('[Aspen]', contexts)
            else:
                self.assertNotIn('[Aspen]', contexts)
                self.assertNotIn('[Birch]', contexts)

    def test_caption_does_not_become_scope_of_following_paragraph(self):
        chunks, _, _ = self.parse(xml('<P>[Aspen]</P><P>We use partners.</P><P>[Routes caption]</P>'
                                     + TABLE + '<P>We also operate locally.</P>'))
        for row in catalog(chunks):
            contexts = row.get('source_contexts', [])
            self.assertTrue(any(c['source_text'] == '[Aspen]' for c in contexts))
            if 'also operate' in row['source_text']:
                self.assertFalse(any('Routes caption' in c['source_text'] for c in contexts))

    def test_inner_scope_changes_flush_even_when_compact_heading_hint_is_identical(self):
        from lxml import etree
        text = xml('<P>[Aspen]</P><P><SPAN USERMARK="B">가. East</SPAN></P>'
                   '<P><SPAN USERMARK="B">(1) Routes</SPAN></P><P>We use partners.</P>'
                   '<P><SPAN USERMARK="B">나. West</SPAN></P>'
                   '<P><SPAN USERMARK="B">(1) Routes</SPAN></P><P>We deliver directly.</P>')
        parser = FinancialParser()
        blocks = parser._collect_blocks(etree.fromstring(text.encode())[0], 'II. Example', structured_override=True)
        from src.processing.source_context import bind_document_contexts
        bind_document_contexts([{'blocks': blocks}], 'source-sha')
        self.assertEqual(blocks[0]['local_heading'], blocks[1]['local_heading'])
        parts = parser._chunk_blocks(blocks, 'II. Example')
        self.assertEqual(len(parts), 2)
        for part, own, foreign in zip(parts, ('East', 'West'), ('West', 'East')):
            contexts = json.loads(part['source_contexts_json'])
            self.assertTrue(any(own in c['source_text'] for c in contexts))
            self.assertFalse(any(foreign in c['source_text'] for c in contexts))

    def test_heading_context_does_not_change_catalog_ids_or_physical_cells(self):
        table = '<TABLE><THEAD><TR><TH>Size</TH><TH>2042</TH></TR></THEAD><TBODY><TR><TD>Count</TD><TD>17</TD></TR></TBODY></TABLE>'
        chunks, _, _ = self.parse(xml('<P>[Aspen]</P><P>We report 9%.</P>' + table))
        current = catalog(chunks)
        stripped = deepcopy(chunks)
        for chunk in stripped:
            chunk.metadata.pop('source_contexts_json', None)
            if chunk.metadata.get('table_object_json'):
                table_object = json.loads(chunk.metadata['table_object_json'])
                table_object['source_contexts'] = [c for c in table_object.get('source_contexts', [])
                    if c['relation'] != 'intermediate_heading']
                chunk.metadata['table_object_json'] = json.dumps(table_object, ensure_ascii=False)
        previous = catalog(stripped)
        self.assertEqual(semantic_candidate_catalog_fingerprint(current), semantic_candidate_catalog_fingerprint(previous))
        self.assertEqual([c['candidate_id'] for c in current], [c['candidate_id'] for c in previous])
        for left, right in zip(current, previous):
            for key in ('raw_value', 'raw_unit', 'normalized_value', 'physical_table_id', 'physical_row_id', 'physical_cell_id'):
                self.assertEqual(left.get(key), right.get(key))

    def test_same_compact_hint_cannot_transfer_prior_paragraph_to_new_inner_scope(self):
        from lxml import etree
        from src.processing.source_context import bind_document_contexts
        text = xml('<P>[Aspen]</P><P><SPAN USERMARK="B">가. East</SPAN></P>'
                   '<P><SPAN USERMARK="B">(1) Routes</SPAN></P><P>Old-only explanation.</P>'
                   '<P><SPAN USERMARK="B">나. West</SPAN></P>'
                   '<P><SPAN USERMARK="B">(1) Routes</SPAN></P>' + TABLE)
        parser = FinancialParser()
        blocks = parser._collect_blocks(etree.fromstring(text.encode())[0], 'II. Example', structured_override=True)
        bind_document_contexts([{'blocks': blocks}], 'source-sha')
        self.assertEqual(blocks[0]['local_heading'], blocks[1]['local_heading'])
        parts = parser._chunk_blocks(blocks, 'II. Example')
        table = next(part for part in parts if 'Delivery' in part['text'])
        self.assertNotIn('Old-only', table['table_context'])

    def test_formal_and_soft_title_supply_the_same_exact_subject_surface(self):
        forms = (xml('<SECTION-2><TITLE ATOC="Y">[Aspen]</TITLE><P>We use partners.</P>' + TABLE + '</SECTION-2>'),
                 xml('<P USERMARK="B">[Aspen]</P><P>We use partners.</P>' + TABLE))
        for text in forms:
            chunks, root, digest = self.parse(text)
            rows = catalog(chunks)
            self.assert_located(rows, root, digest)
            self.assertTrue(all(any(c['source_text'] == '[Aspen]' for c in r.get('source_contexts', [])) for r in rows))

    def test_discarded_date_heading_remains_an_adjacent_source_note(self):
        chunks, _, _ = self.parse(xml('<P>[Aspen]</P><P>We use partners.</P><P>[2042년]</P>' + TABLE))
        table = next(json.loads(c.metadata['table_object_json']) for c in chunks if c.metadata.get('table_object_json'))
        dates = [c for c in table['source_contexts'] if c['source_text'] == '[2042년]']
        self.assertEqual([c['relation'] for c in dates], ['preceding_block'])
        self.assertTrue(any(c['source_text'] == '[Aspen]' for c in table['source_contexts']))

    def test_context_budget_keeps_exact_xml_spans(self):
        text = ('<DOCUMENT><SECTION-1><TITLE ATOC="Y">' + 'Outer ' * 300 + '</TITLE>'
                '<SECTION-2><TITLE ATOC="Y">' + 'Middle ' * 300 + '</TITLE>'
                '<SECTION-3><TITLE ATOC="Y">' + 'Inner ' * 300 + '</TITLE>'
                '<P>[Aspen]</P><P>' + 'We use partners. ' * 130 + '</P>' + TABLE +
                '</SECTION-3></SECTION-2></SECTION-1></DOCUMENT>')
        chunks, root, digest = self.parse(text)
        self.assert_located(catalog(chunks), root, digest)
        for chunk in chunks:
            self.assertLessEqual(sum(len(c['source_text']) for c in json.loads(chunk.metadata['source_contexts_json'])), 4800)
            if chunk.metadata.get('table_object_json'):
                self.assertLessEqual(sum(len(c['source_text']) for c in json.loads(chunk.metadata['table_object_json'])['source_contexts']), 4800)

    def test_context_roundtrips_existing_sidecar_without_chroma_truncation(self):
        chunks, _, _ = self.parse(xml('<P>[Aspen]</P><P>We use partners.</P>'))
        metadata = chunks[0].metadata
        self.assertIn('source_contexts_json', metadata)
        payloads = {}
        compact = compact_node_for_storage({'metadata': metadata}, payloads)
        self.assertNotIn('source_contexts_json', compact['metadata'])
        self.assertNotIn('source_contexts_json', metadata_for_chroma(metadata))
        with TemporaryDirectory() as directory:
            path = Path(directory) / 'payloads.json'
            path.write_text(json.dumps({'payloads': payloads}), encoding='utf-8')
            hydrated = metadata_with_table_payload(compact['metadata'], load_table_payloads(path))
        self.assertEqual(hydrated['source_contexts_json'], metadata['source_contexts_json'])
        self.assertEqual(from_docs([(Document(page_content=chunks[0].content, metadata=hydrated), 0)]), catalog(chunks))

    def test_subject_quote_reaches_executor_but_foreign_context_and_mutation_fail(self):
        from tests.narrative_address_test_support import address_program
        chunks, _, _ = self.parse(xml('<P>[Aspen]</P><P>We use partners.</P><P>[Birch]</P><P>We deliver directly.</P>'))
        rows = catalog(chunks)
        selected = next(c for c in rows if 'partners' in c['source_text'])
        heading = next(c for c in selected.get('source_contexts', []) if c['source_text'] == '[Aspen]')
        owners = [_obligation('routes', 'narrative', 'Routes')]
        evidence = [dict(candidate_id=selected['candidate_id'], evidence_text=selected['source_bundle_text']),
                    dict(candidate_id=selected['candidate_id'], context_id=heading['context_id'], evidence_text='Aspen')]
        program = {'narrative_bindings': [{'obligation_id': 'routes', 'claims': [
            {'subject': 'Aspen', 'text': 'Uses partners.', 'evidence_bindings': evidence}]}]}
        plan = _semantic_candidate_cohorts(rows, owners)
        visibility = _semantic_candidate_visibility(rows, visible_candidate_ids=plan['visible_candidate_ids'],
            candidate_ids_by_owner=plan['candidate_ids_by_owner'])
        inputs = dict(program=address_program(program, rows), candidate_catalog=rows, obligations=owners, query='Describe routes.')
        validation = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility, require_narrative_claims=True)
        self.assertEqual(validation['status'], 'ready', validation['errors'])
        envelope = CompilationEnvelopeV2.create(**inputs, validation=validation, visibility=visibility)
        result = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(result['status'], 'ok', result['validation']['errors'])
        self.assertTrue(result['outputs'][0]['claim_readings'])
        foreign = next(c for r in rows for c in r.get('source_contexts', []) if c['source_text'] == '[Birch]')
        invalid = deepcopy(program)
        invalid['narrative_bindings'][0]['claims'][0]['evidence_bindings'][1].update(context_id=foreign['context_id'], evidence_text='Birch')
        rejected = validate_semantic_calculation_program(**{**inputs, 'program': address_program(invalid, rows)}, candidate_visibility=visibility, require_narrative_claims=True)
        self.assertNotEqual(rejected['status'], 'ready')
        heading['source_text'] = '[Modified]'
        changed = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope, require_compilation_envelope=True)
        self.assertEqual(changed['validation']['errors'][0]['code'], 'execution_content_mismatch')

    def test_prompt_order_and_context_deduplication_are_deterministic(self):
        chunks, _, _ = self.parse(xml('<P>[Aspen]</P><P>We use partners.</P>' + TABLE))
        rows = catalog(chunks)
        owners = [_obligation('routes', 'narrative', 'Routes')]
        def prompt(items):
            return FinancialAgentCalculationMixin._semantic_program_prompt_payload(items, _semantic_candidate_cohorts(items, owners))
        payload = prompt(rows)
        self.assertEqual(payload, prompt(list(reversed(rows))))
        from tests.compiler_presentation_test_support import context_surfaces
        self.assertTrue(any('[Aspen]' == text for text in context_surfaces(payload).values()))
        self.assertEqual(sum(text == '[Aspen]' for text in context_surfaces(payload).values()), 1)


if __name__ == '__main__':
    unittest.main()
