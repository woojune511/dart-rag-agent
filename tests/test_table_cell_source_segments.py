"""Physical cell boundaries are source structure, not inferred word separators."""

from copy import deepcopy
from tests.narrative_address_test_support import address_program, model_program
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lxml import etree

from src.agent.financial_calculation_execution import execute_semantic_calculation_program, validate_semantic_calculation_program, _resolve_source_context_bindings
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin, _semantic_candidate_cohorts, _semantic_candidate_visibility
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from src.agent.financial_runtime_contracts import CompilationEnvelopeV2
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from src.processing.financial_parser import FinancialParser
from src.processing.source_context import bounded_source_contexts, collect_table_source_contexts, source_fragment
from src.storage.metadata_payloads import compact_node_for_storage, metadata_with_table_payload
from tests.test_located_heading_context import catalog
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_retry_context import prompt_json


def document(cells='<TD>Goods</TD><TD>Aspen uses partners.</TD>'):
    return ('<DOCUMENT><SECTION-1><TITLE ATOC="Y">Overview</TITLE>'
            '<TABLE><THEAD><TR><TH>Item</TH><TH>Description</TH></TR></THEAD>'
            f'<TBODY><TR>{cells}</TR><TR><TD>Count</TD><TD>17</TD></TR></TBODY>'
            '</TABLE></SECTION-1></DOCUMENT>')


def parse(text=None):
    with TemporaryDirectory() as directory:
        path = Path(directory) / 'source.xml'
        path.write_text(text or document(), encoding='utf-8')
        parser = FinancialParser()
        return parser.process_document(str(path), {'company': 'Issuer', 'year': 2042, 'rcept_no': 'anonymous'})


def row_reading(rows):
    return next(r for r in rows if r.get('source_context_provenance', {}).get('relation') == 'table_text_row')


def payload(rows, *, narrative=False):
    return FinancialAgentCalculationMixin._semantic_program_prompt_payload(rows, {
        'visible_candidate_ids': [r['candidate_id'] for r in rows],
        'cohorts': ([{'owner_type': 'obligation', 'candidate_kind': 'evidence'}] if narrative else []),
    })


class TableCellSourceSegmentsTests(unittest.TestCase):
    def test_whitespace_tails_comments_and_cdata_do_not_shift_cell_offsets(self):
        row = etree.fromstring(b'<TR>\n<TD>A<!--ignored-->B<![CDATA[C]]></TD> \n<TD>D<B>E</B>F</TD>\n</TR>')
        context = source_fragment(row, 'table_text_row')
        self.assertEqual(context['source_text'], '\nABC \nDEF\n')
        parts = [context['source_text'][slice(*s['text_span'])] for s in context['source_segments']]
        self.assertEqual(parts, ['\n', 'ABC', ' \n', 'DEF', '\n'])
        window = source_fragment(row, 'table_text_row', [2, 8])
        self.assertEqual(window['source_text'], 'BC \nDE')
        self.assertEqual([s['text_span'] for s in window['source_segments']], [[0, 2], [2, 4], [4, 6]])

    def test_adjacent_cells_stay_separate_but_inline_text_and_xml_offsets_are_exact(self):
        for left, name in (('Goods', 'Aspen'), ('항목', '오로라'), ('X', 'Mizu &amp; Co.')):
            with self.subTest(left=left, name=name):
                root = etree.fromstring(document(f'<TD>{left}</TD><TD>{name} <B>uses</B> partners.</TD>').encode())
                table = root.find('.//TABLE')
                context = next(c for c in collect_table_source_contexts(table) if c['relation'] == 'table_text_row')
                segments = context['source_segments']
                self.assertEqual(len(segments), 2)
                text = context['source_text']
                self.assertEqual(text, ''.join(root.xpath(context['source_locator'])[0].itertext()))
                self.assertEqual([text[s['text_span'][0]:s['text_span'][1]] for s in segments],
                                 [left, name.replace('&amp;', '&') + ' uses partners.'])
                for segment in segments:
                    cell, = root.xpath(segment['cell_locator'])
                    self.assertEqual(text[slice(*segment['text_span'])], ''.join(cell.itertext()))
                    self.assertEqual(segment['row_locator'], context['source_locator'])

    def test_empty_spanned_and_nested_cells_keep_physical_order_without_expansion(self):
        row = etree.fromstring(b'<TR><TD ROWSPAN="2" COLSPAN="3">A</TD><TD/><TD>pre<TABLE><TR><TD>B</TD><TD>C</TD></TR></TABLE>post</TD></TR>')
        context = source_fragment(row, 'table_text_row')
        text = context['source_text']
        segments = context['source_segments']
        self.assertEqual([text[slice(*s['text_span'])] for s in segments], ['A', '', 'pre', 'B', 'C', 'post'])
        self.assertEqual(text, 'ApreBCpost')
        self.assertEqual(segments[0]['cell_locator'], '/TR/TD[1]')
        self.assertEqual(segments[2]['cell_locator'], segments[-1]['cell_locator'])
        self.assertNotEqual(segments[2]['row_locator'], segments[3]['row_locator'])

    def test_context_windows_clip_segments_without_changing_source_coordinates(self):
        row = etree.fromstring(('<TR><TD>' + 'A' * 1195 + '</TD><TD>' + 'B' * 40 + '</TD></TR>').encode())
        context = source_fragment(row, 'table_text_row')
        self.assertEqual(context['source_span'], [0, 1200])
        self.assertEqual([s['text_span'] for s in context['source_segments']], [[0, 1195], [1195, 1200]])
        preceding = [source_fragment(etree.fromstring(('<P>' + 'x' * 1200 + '</P>').encode()), 'preceding_block') for _ in range(3)]
        for index, part in enumerate(preceding):
            part['source_locator'] += str(index)
        preceding.append(source_fragment(etree.fromstring(b'<P>padding</P>'), 'preceding_block'))
        clipped = bounded_source_contexts([*preceding, context])[-1]
        self.assertEqual(clipped['source_span'], [0, 1193])
        self.assertEqual([s['text_span'] for s in clipped['source_segments']], [[0, 1193]])
        self.assertEqual(context['source_span'], [0, 1200])

    def test_prompt_has_separate_quote_surfaces_and_no_joined_cell_text(self):
        rows = catalog(parse())
        before = deepcopy(rows)
        output = payload(rows, narrative=True)
        reading = row_reading(rows)
        bundle_id = output['candidates_by_id'][reading['candidate_id']]['source_bundle_id']
        body = next(b for r in output['source_readings'] for b in r['bodies'] if b['source_bundle_id'] == bundle_id)
        self.assertNotIn('source_text', body)
        self.assertEqual([s['text'] for s in body['pieces']], ['Goods', 'Aspen uses partners.'])
        self.assertEqual([s['partition'] for s in body['pieces']], [0, 1])
        self.assertNotIn('GoodsAspen', json.dumps(output, ensure_ascii=False))
        self.assertEqual(output, payload(list(reversed(rows)), narrative=True))
        numeric_body = next(b for r in payload(rows)['source_readings'] for b in r['bodies'] if b['source_bundle_id'] == bundle_id)
        self.assertEqual([s['source_text'] for s in numeric_body['source_segments']], ['Goods', 'Aspen uses partners.'])
        self.assertEqual(rows, before)

    def test_segments_roundtrip_sidecar_without_changing_catalog_or_numeric_records(self):
        chunks = parse()
        enriched = catalog(chunks)
        legacy = deepcopy(chunks)
        for chunk in legacy:
            table = json.loads(chunk.metadata['table_object_json'])
            for context in table['source_contexts']:
                context.pop('source_segments', None)
            chunk.metadata['table_object_json'] = json.dumps(table)
        stripped = catalog(legacy)
        self.assertEqual(semantic_candidate_catalog_fingerprint(enriched), semantic_candidate_catalog_fingerprint(stripped))
        self.assertEqual([r['candidate_id'] for r in enriched], [r['candidate_id'] for r in stripped])
        for left, right in zip(enriched, stripped):
            for key in ('raw_value', 'normalized_value', 'source_text', 'source_bundle_text',
                        'physical_table_id', 'physical_row_id', 'physical_cell_id', 'context_fingerprint'):
                self.assertEqual(left.get(key), right.get(key))
        metadata = chunks[0].metadata
        payloads = {}
        compact = compact_node_for_storage({'metadata': metadata}, payloads)
        hydrated = metadata_with_table_payload(compact['metadata'], payloads)
        self.assertEqual(json.loads(hydrated['table_object_json']), json.loads(metadata['table_object_json']))
        self.assertTrue(any(c.get('source_segments') for c in json.loads(hydrated['table_object_json'])['source_contexts']))

    def test_cross_cell_quotes_fail_while_separate_quotes_execute_and_mutation_is_blocked(self):
        rows = catalog(parse())
        selected = row_reading(rows)
        owners = [_obligation('routes', 'narrative', 'Routes')]
        context = selected['source_context_provenance']
        plan = _semantic_candidate_cohorts(rows, owners)
        visibility = _semantic_candidate_visibility(rows, visible_candidate_ids=plan['visible_candidate_ids'],
            candidate_ids_by_owner=plan['candidate_ids_by_owner'])
        for context_id in ('', context['context_id']):
            with self.subTest(context_id=context_id):
                link = dict(candidate_id=selected['candidate_id'], context_id=context_id,
                            evidence_text='GoodsAspen uses partners.')
                program = {'narrative_bindings': [{'obligation_id': 'routes', 'claims': [
                    {'subject': 'Aspen', 'text': 'Uses partners for goods.', 'evidence_bindings': [link]}]}]}
                inputs = dict(program=address_program(program, rows), candidate_catalog=rows, obligations=owners, query='Describe routes.')
                invalid = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility, require_narrative_claims=True)
                errors = [e for e in invalid['errors'] if e['code'] == 'cross_partition_narrative_selection']
                self.assertTrue(errors, invalid['errors'])
                self.assertEqual(errors[0]['repair_action'], 'repair_program')
                program['narrative_bindings'][0]['claims'][0]['evidence_bindings'] = [
                    {**link, 'evidence_text': text} for text in ('Goods', 'Aspen uses partners.')]
                inputs['program'] = address_program(program, rows)
                valid = validate_semantic_calculation_program(**inputs, candidate_visibility=visibility, require_narrative_claims=True)
                self.assertEqual(valid['status'], 'ready', valid['errors'])
                envelope = CompilationEnvelopeV2.create(**inputs, validation=valid, visibility=visibility)
                result = execute_semantic_calculation_program(**inputs, compilation_envelope=envelope, require_compilation_envelope=True)
                self.assertEqual(result['status'], 'ok', result['validation']['errors'])
                changed = deepcopy(rows)
                row_reading(changed)['source_context_provenance']['source_segments'][0]['text_span'][1] += 1
                rejected = execute_semantic_calculation_program(**{**inputs, 'candidate_catalog': changed},
                    compilation_envelope=envelope, require_compilation_envelope=True)
                self.assertEqual(rejected['validation']['errors'][0]['code'], 'execution_content_mismatch')

    def test_scope_binding_cannot_bypass_the_same_cell_quote_boundary(self):
        selected = next(c for c in catalog(parse()) if c['kind'] == 'numeric')
        context = next(c for c in selected['source_contexts'] if c['relation'] == 'table_text_row')
        binding = dict(context_id=context['context_id'], field='basis', value='example',
                       evidence_text='GoodsAspen uses partners.')
        with self.assertRaisesRegex(ValueError, '^context_quote_not_exact$'):
            _resolve_source_context_bindings(selected, [binding])
        resolved, _ = _resolve_source_context_bindings(selected, [{**binding, 'evidence_text': 'Aspen uses partners.'}])
        self.assertEqual(resolved['basis'], 'example')

    def test_boundary_error_retries_same_cohort_and_preserves_accepted_island(self):
        rows = catalog(parse())
        selected = row_reading(rows)
        accepted = SemanticCalculationProgram(direct_bindings=[{'obligation_id': 'size', 'candidate_id': 'size-cell'}])
        link = dict(candidate_id=selected['candidate_id'], evidence_text='GoodsAspen uses partners.')
        bad = {'narrative_bindings': [{'obligation_id': 'routes', 'claims': [
            {'subject': 'Aspen', 'text': 'Uses partners for goods.', 'evidence_bindings': [link]}]}]}
        good = deepcopy(bad)
        good['narrative_bindings'][0]['claims'][0]['evidence_bindings'] = [
            {**link, 'evidence_text': text} for text in ('Goods', 'Aspen uses partners.')]
        llm = _StructuredQueueLLM(accepted, model_program(bad, rows),
                                  model_program(good, rows))
        state = _case_state({'question': 'Report size and describe routes.', 'obligations': [
            _obligation('size', 'direct_value', 'Size'), _obligation('routes', 'narrative', 'Routes')]},
            [_candidate('size-cell', 12), *rows])
        before = deepcopy(state)
        compiled = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
        self.assertEqual(json.dumps(compiled['semantic_program']['direct_bindings'], sort_keys=True),
                         json.dumps(accepted.model_dump()['direct_bindings'], sort_keys=True))
        marker = 'Source bundles, candidate cohorts, and candidates_by_id:'
        self.assertEqual(prompt_json(llm.prompts[1], marker), prompt_json(llm.prompts[2], marker))
        feedback = prompt_json(llm.prompts[2], '재시도 피드백(없으면 -):')
        self.assertEqual([d['obligation_id'] for d in feedback['unvalidated_narrative_drafts']], ['routes'])
        self.assertEqual(state, before)


if __name__ == '__main__':
    unittest.main()
