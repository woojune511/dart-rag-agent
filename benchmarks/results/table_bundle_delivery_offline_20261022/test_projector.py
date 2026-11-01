"""Synthetic provider-free contracts; they do not measure answer quality."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from lxml import etree

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("table_bundle_projector", HERE / "projector.py")
projector = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = projector
spec.loader.exec_module(projector)
SHA = "1" * 64


def fixture():
    tree = etree.ElementTree(etree.fromstring(b'<DOCUMENT><BODY><TITLE>Report</TITLE><P>Currency: million; percentages keep %</P><TABLE><THEAD><TR><TH>Item</TH><TH>Current</TH><TH>Prior</TH></TR></THEAD><TBODY><TR><TD>Operating result</TD><TD>10</TD><TD>20</TD></TR></TBODY></TABLE><P>Next unrelated heading</P></BODY></DOCUMENT>'))
    table = tree.xpath('/DOCUMENT/BODY/TABLE')[0]
    preceding = table.getprevious()
    obj = {
        'table_id': 's::table:1', 'source_document_sha256': SHA,
        'source_table_locator': tree.getpath(table), 'row_count': 2, 'column_count': 3,
        'header_rows': [['Item', 'Current', 'Prior']], 'header_scope_source': 'thead',
        'rows': [{'row_id': '2:0', 'row_label': 'Operating result', 'row_headers': ['Operating result'], 'cells': [
            {'column_index': 1, 'column_headers': ['Current'], 'value_text': '10', 'unit_hint': '%'},
            {'column_index': 2, 'column_headers': ['Prior'], 'value_text': '20', 'unit_hint': '%'},
        ]}],
        'source_contexts': [context(preceding, tree, 'preceding_block')],
        'unit_hint': '%', 'period_text': '1900',
    }
    return tree, obj


def context(node, tree, relation, end=None):
    text = ''.join(node.itertext())
    end = len(text) if end is None else end
    c = {'source_locator': tree.getpath(node), 'parent_locator': tree.getpath(node.getparent()),
         'source_text': text[:end], 'source_span': [0, end], 'relation': relation, 'document_sha256': SHA}
    if relation == 'table_text_row':
        c['source_segments'] = projector._slice_segments(projector._text_partition(node, tree), 0, end)
    return c


def run_bundle(tree, obj):
    return projector.build_bundle({'table_object_json': json.dumps(obj), 'table_source_id': obj['table_id'],
                                   'chunk_uid': 'test:1:0', 'company': 'Unrelated issuer'}, tree, SHA)


class ProjectorContracts(unittest.TestCase):
    def reject(self, tree, obj, reason):
        bundle, receipt = run_bundle(tree, obj)
        self.assertIsNone(bundle)
        self.assertEqual(reason, receipt['reason'], receipt)

    def test_literal_grid_admitted_without_scalar_axis_inference(self):
        tree, obj = fixture()
        bundle, receipt = run_bundle(tree, obj)
        self.assertEqual('ADMITTED', receipt['status'])
        self.assertEqual([['Item', 'Current', 'Prior'], ['Operating result', '10', '20']], bundle['grid'])
        self.assertEqual([0], bundle['declared_header_row_indices'])
        self.assertNotIn('company', bundle)
        self.assertNotIn('unit_hint', bundle)
        self.assertNotIn('period_text', bundle)
        self.assertEqual(6, receipt['covered_nonempty_physical_cells'])

    def test_changed_stored_value_rejected(self):
        tree, obj = fixture(); obj['rows'][0]['cells'][0]['value_text'] = '99'
        self.reject(tree, obj, 'cell_value_or_column_mismatch')

    def test_wrong_column_rejected(self):
        tree, obj = fixture(); obj['rows'][0]['cells'][0]['column_index'] = 2
        self.reject(tree, obj, 'cell_value_or_column_mismatch')

    def test_wrong_header_prefix_rejected(self):
        tree, obj = fixture(); obj['header_rows'][0][1] = 'Prior'
        self.reject(tree, obj, 'header_prefix_mismatch')

    def test_wrong_cell_header_rejected_even_if_value_repeats(self):
        tree, obj = fixture(); tree.xpath('//TBODY/TR/TD[3]')[0].text = '10'
        obj['rows'][0]['cells'][1]['value_text'] = '10'
        obj['rows'][0]['cells'][0]['column_headers'] = ['Prior']
        self.reject(tree, obj, 'column_header_mismatch')

    def test_wrong_hash_rejected(self):
        tree, obj = fixture(); obj['source_document_sha256'] = '2' * 64
        self.reject(tree, obj, 'table_document_hash_mismatch')

    def test_wrong_context_hash_rejected(self):
        tree, obj = fixture(); obj['source_contexts'][0]['document_sha256'] = '2' * 64
        self.reject(tree, obj, 'context_hash_mismatch')

    def test_wrong_context_span_rejected(self):
        tree, obj = fixture(); obj['source_contexts'][0]['source_span'][0] = 1
        self.reject(tree, obj, 'context_text_span_mismatch')

    def test_same_text_wrong_relation_rejected(self):
        tree, obj = fixture(); after=tree.xpath('/DOCUMENT/BODY/TABLE')[0].getnext()
        after.text=obj['source_contexts'][0]['source_text']
        obj['source_contexts']=[context(after,tree,'preceding_block')]
        self.reject(tree, obj, 'context_relation_mismatch')

    def test_following_context_excluded(self):
        tree, obj=fixture(); after=tree.xpath('/DOCUMENT/BODY/TABLE')[0].getnext()
        obj['source_contexts'].append(context(after,tree,'following_block'))
        bundle,receipt=run_bundle(tree,obj)
        self.assertEqual('ADMITTED',receipt['status'])
        self.assertEqual(1,len(bundle['literal_source_contexts']))
        self.assertEqual('EXCLUDED',receipt['contexts'][-1]['status'])

    def test_missing_cell_not_filled_from_original(self):
        tree,obj=fixture();obj['rows'][0]['cells'].pop()
        self.reject(tree,obj,'payload_incomplete')

    def test_same_number_other_period_does_not_cover_missing_cell(self):
        tree,obj=fixture();tree.xpath('//TBODY/TR/TD[3]')[0].text='10'
        obj['rows'][0]['cells'].pop()
        self.reject(tree,obj,'payload_incomplete')

    def test_nested_table_rejected(self):
        tree,obj=fixture();td=tree.xpath('//TBODY/TR/TD[1]')[0]
        td.append(etree.fromstring(b'<TABLE><TR><TD>x</TD></TR></TABLE>'))
        self.reject(tree,obj,'nested_table')

    def test_invalid_span_rejected(self):
        tree,obj=fixture();tree.xpath('//TBODY/TR/TD[1]')[0].set('COLSPAN','zero')
        self.reject(tree,obj,'invalid_cell_span')

    def test_rowspan_beyond_table_rejected(self):
        tree,obj=fixture();tree.xpath('//TBODY/TR/TD[1]')[0].set('ROWSPAN','2')
        self.reject(tree,obj,'rowspan_beyond_table')

    def test_wrong_row_id_rejected(self):
        tree,obj=fixture();obj['rows'][0]['row_id']='2:1'
        self.reject(tree,obj,'duplicate_or_outside_row_id')

    def test_text_only_relation_table_covered_by_original_cell_segments(self):
        tree=etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TD>Company</TD><TD>Event</TD></TR><TR><TD>India</TD><TD>2023 production</TD></TR></TABLE></DOCUMENT>'))
        table=tree.xpath('//TABLE')[0];row=table.xpath('./TR[2]')[0]
        obj={'table_id':'s::table:1','source_document_sha256':SHA,'source_table_locator':tree.getpath(table),
             'row_count':2,'column_count':2,'header_rows':[['Company','Event']], 'rows':[],
             'source_contexts':[context(row,tree,'table_text_row')]}
        bundle,receipt=run_bundle(tree,obj)
        self.assertEqual('ADMITTED',receipt['status'])
        self.assertEqual([],bundle['declared_header_row_indices'])
        self.assertEqual(['India','2023 production'],bundle['grid'][1])

    def test_clipped_text_cell_does_not_cover_full_original_cell(self):
        tree=etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TD>India</TD><TD>2023 production</TD></TR></TABLE></DOCUMENT>'))
        table=tree.xpath('//TABLE')[0];row=table[0]
        obj={'table_id':'s::table:1','source_document_sha256':SHA,'source_table_locator':tree.getpath(table),
             'row_count':1,'column_count':2,'header_rows':[], 'rows':[],
             'source_contexts':[context(row,tree,'table_text_row',9)]}
        self.reject(tree,obj,'payload_incomplete')

    def test_forged_cell_segment_with_repeated_text_is_rejected(self):
        tree=etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TD>Same</TD><TD>Same</TD></TR></TABLE></DOCUMENT>'))
        table=tree.xpath('//TABLE')[0];row=table[0];c=context(row,tree,'table_text_row')
        c['source_segments'][0]['cell_locator']=c['source_segments'][1]['cell_locator']
        obj={'table_id':'s::table:1','source_document_sha256':SHA,'source_table_locator':tree.getpath(table),
             'row_count':1,'column_count':2,'header_rows':[], 'rows':[], 'source_contexts':[c]}
        self.reject(tree,obj,'context_cell_segments_mismatch')

    def test_inferred_data_in_header_prefix_is_preserved_but_not_declared(self):
        tree,obj=fixture()
        for th in tree.xpath('//TH'):th.tag='TD'
        thead=tree.xpath('//THEAD')[0];thead.tag='TBODY'
        obj['header_rows'].append(['Operating result','10','20']);obj['rows']=[]
        bundle,receipt=run_bundle(tree,obj)
        self.assertEqual('ADMITTED',receipt['status'])
        self.assertEqual([],bundle['declared_header_row_indices'])
        self.assertEqual(['Operating result','10','20'],bundle['grid'][1])

    def test_colspan_has_one_physical_owner(self):
        tree=etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TH COLSPAN="2">Both</TH></TR><TR><TD>1</TD><TD>2</TD></TR></TABLE></DOCUMENT>'))
        table=tree.xpath('//TABLE')[0]
        obj={'table_id':'s::table:1','source_document_sha256':SHA,'source_table_locator':tree.getpath(table),
             'row_count':2,'column_count':2,'header_rows':[['Both','Both'],['1','2']], 'rows':[], 'source_contexts':[]}
        bundle,receipt=run_bundle(tree,obj)
        self.assertEqual('ADMITTED',receipt['status'])
        self.assertEqual(3,receipt['nonempty_physical_cells'])
        self.assertEqual([[0,0],[0,1]],receipt['cell_mapping'][0]['expanded_coordinates'])

    def test_ambiguous_repeated_row_axis_rejected(self):
        tree=etree.ElementTree(etree.fromstring(b'<DOCUMENT><TABLE><TR><TD>Same</TD><TD>Same</TD><TD>1</TD></TR></TABLE></DOCUMENT>'))
        table=tree.xpath('//TABLE')[0]
        obj={'table_id':'s::table:1','source_document_sha256':SHA,'source_table_locator':tree.getpath(table),
             'row_count':1,'column_count':3,'header_rows':[],
             'rows':[{'row_id':'1:0','row_headers':['Same'],'cells':[{'column_index':2,'column_headers':[],'value_text':'1'}]}], 'source_contexts':[]}
        self.reject(tree,obj,'row_axis_not_unique_or_missing')


if __name__=='__main__':
    unittest.main(verbosity=2)
