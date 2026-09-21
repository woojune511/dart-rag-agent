"""Explicit filing selection stays separate from measurement-period hints."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.storage.bm25_index import metadata_matches_filter
from tests.test_retrieval_scope_isolation import _Pipeline, _doc, _state


def scoped_state(**overrides):
    return _state(**{
        'companies': ['Example Parent'], 'years': [2040, 2041],
        'report_scope': {'company': 'Example Parent', 'year': 2042, 'report_type': 'annual'},
        **overrides,
    })


def source(source_id, year=None, **metadata):
    fields = dict(company='Example Parent', report_type='annual', **metadata)
    if year is not None:
        fields['year'] = year
    return (_doc(source_id, **fields), .5)


class DocumentYearScopeTests(unittest.TestCase):
    def test_explicit_document_year_restricts_hints_for_every_intent(self):
        for year in (2042, 2089):
            for intent in ('numeric_fact', 'comparison', 'trend', 'qa'):
                with self.subTest(year=year, intent=intent):
                    state = scoped_state(intent=intent, years=[year-2, year-1],
                        report_scope={'company':'Example Parent', 'year':year})
                    before = deepcopy(state)
                    plan = _Pipeline()._build_scope_plan(state)
                    accepted = [candidate for candidate in (year-2, year-1, year, year+1)
                        if metadata_matches_filter({'company':'Example Parent', 'year':candidate}, plan['where_filter'])]
                    self.assertEqual(accepted, [year])
                    self.assertEqual(state, before)
                    self.assertEqual(plan['years'], [year, year-2, year-1])

    def test_explicit_year_survives_missing_hints_and_supported_string_input(self):
        for year in (2042, '2042'):
            state = scoped_state(years=[], report_scope={'year':year})
            self.assertEqual(_Pipeline()._build_scope_plan(state)['where_filter'],
                             {'$and':[{'company':'Example Parent'}, {'year':2042}]})

    def test_subtask_comparison_override_cannot_remove_explicit_year(self):
        for intent in ('comparison', 'trend'):
            state = scoped_state(intent='qa', active_subtask={'intent_override':intent})
            plan = _Pipeline()._build_plan(state)
            self.assertFalse(metadata_matches_filter(source('foreign', 2040)[0].metadata, plan['where_filter']))
            self.assertTrue(metadata_matches_filter(source('selected', 2042)[0].metadata, plan['where_filter']))

    def test_absent_document_year_preserves_unscoped_multi_period_behavior(self):
        for scope_year in (None, '', 'unknown'):
            for intent in ('numeric_fact', 'comparison', 'trend'):
                state = scoped_state(intent=intent, report_scope={'year':scope_year})
                where = _Pipeline()._build_scope_plan(state)['where_filter']
                self.assertTrue(metadata_matches_filter(source('requested', 2040)[0].metadata, where))
                self.assertEqual(metadata_matches_filter(source('later-filing', 2042)[0].metadata, where),
                                 intent != 'numeric_fact')

    def test_multiple_receipts_override_primary_year_for_both_inventory_shapes(self):
        for key in ('source_reports', 'report_inventory'):
            state = scoped_state(report_scope={
                'company':'Caller Alias', 'year':2042, 'rcept_no':'primary-only',
                key:[{'rcept_no':'filing-A', 'year':2042},
                     {'metadata':{'rcept_no':'filing-B', 'year':2040}}],
            })
            plan = _Pipeline()._build_scope_plan(state)
            self.assertEqual(plan['where_filter'], {'rcept_no':{'$in':['filing-A','filing-B']}})
            self.assertTrue(metadata_matches_filter({'rcept_no':'filing-B', 'year':2040}, plan['where_filter']))
            self.assertFalse(metadata_matches_filter({'rcept_no':'primary-only', 'year':2042}, plan['where_filter']))

    def test_single_receipt_keeps_explicit_year_and_receipt_intersection(self):
        for receipt_fields in ({'rcept_no':'filing-A'},
                               {'source_reports':[{'rcept_no':'filing-A'}]},
                               {'source_reports':[{'rcept_no':'filing-A'}, {'rcept_no':'filing-A'}]}):
            state = scoped_state(report_scope={'year':2042, **receipt_fields})
            where = _Pipeline()._build_scope_plan(state)['where_filter']
            self.assertEqual(where, {'$and':[{'year':2042}, {'rcept_no':'filing-A'}]})
            self.assertTrue(metadata_matches_filter({'rcept_no':'filing-A', 'year':2042}, where))
            self.assertFalse(metadata_matches_filter({'rcept_no':'filing-A', 'year':2040}, where))
            self.assertFalse(metadata_matches_filter({'rcept_no':'filing-B', 'year':2042}, where))

    def test_measurement_constraints_and_query_hints_are_preserved(self):
        state = scoped_state(answer_obligations=[{
            'obligation_id':'change', 'kind':'derived_value', 'request_unit_ids':['request_001'],
            'scope':{'period':'earlier to later', 'measurement_period':{'kind':'unresolved','request_unit_ids':['request_001']}},
            'evidence_requirements':[
                {'requirement_id':f'input-{year}', 'label':str(year), 'scope':{'period':str(year),
                 'measurement_period':{'kind':'year','year':year,'request_unit_ids':['request_001']}}}
                for year in (2040, 2041)
            ],
        }], retrieval_queries=['2040 measurement', '2041 measurement'])
        before = deepcopy(state)
        _Pipeline()._build_plan(state)
        self.assertEqual(state, before)

    def test_main_supplement_seed_and_final_selection_share_explicit_year(self):
        pipeline = _Pipeline()
        state = scoped_state()
        rows = [source('earlier',2040), source('later',2041), source('unknown'), source('selected',2042)]
        selection = pipeline._select_evidence(state, pipeline._build_plan(state),
            {'docs':rows, 'supplemental_docs':rows, 'retry_queries':[]})
        for key in ('docs', 'seed_docs'):
            self.assertEqual([d.metadata['chunk_uid'] for d,_ in selection[key]], ['selected'])
        self.assertEqual(selection['scope_filter']['excluded_count'], 3)
        self.assertEqual(selection['scope_filter']['supplemental_retained_count'], 1)

    def test_empty_explicit_year_result_does_not_restore_other_filings(self):
        pipeline = _Pipeline()
        state = scoped_state()
        rows = [source('other',2040), source('unknown')]
        selection = pipeline._select_evidence(state, pipeline._build_plan(state),
            {'docs':rows, 'supplemental_docs':rows, 'retry_queries':[]})
        self.assertEqual(selection['docs'], [])
        self.assertEqual(selection['seed_docs'], [])

    def test_local_supplement_filters_year_before_bounded_ranking(self):
        pipeline = _Pipeline()
        rows = [source(f'foreign-{i}',2040) for i in range(8)] + [source('selected',2042)]
        metadata = [{**d.metadata,'section_path':'Measurements'} for d,_ in rows]
        pipeline.vsm = SimpleNamespace(bm25_docs=['measurement 42']*len(rows), bm25_metadatas=metadata)
        with patch('src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query', return_value=['Measurements']), \
             patch('src.agent.financial_retrieval_pipeline._active_preferred_sections', return_value=[]), \
             patch('src.agent.financial_retrieval_pipeline._active_preferred_statement_types', return_value=[]):
            selected = pipeline._supplement_section_seed_docs(scoped_state(answer_obligations=[]))
        self.assertEqual([d.metadata['chunk_uid'] for d,_ in selected], ['selected'])

    def test_primary_retry_cache_and_trace_keep_the_same_explicit_year(self):
        pipeline = _Pipeline()
        calls = []
        rows = [source('foreign',2040), source('selected',2042)]
        def search(query, **kwargs):
            calls.append(deepcopy(kwargs))
            return deepcopy(rows)
        pipeline.vsm = SimpleNamespace(search=search)
        pipeline._supplement_section_seed_docs = lambda state: []
        state = scoped_state(reflection_count=1, retry_queries=['separate operand'],
            seed_retrieved_docs=[source('old-seed',2041)])
        with patch('src.agent.financial_retrieval_pipeline.retrieval_hint_from_topic', return_value=''), \
             patch('src.agent.financial_retrieval_pipeline._active_preferred_sections', return_value=[]):
            first = pipeline._retrieve(state)
            count = len(calls)
            state['retrieval_query_result_cache'] = first['retrieval_query_result_cache']
            second = pipeline._retrieve(state)
        self.assertGreaterEqual(count, 2)
        self.assertEqual(len(calls), count)
        for result in (first,second):
            trace = result['retrieval_debug_trace']
            self.assertEqual([d.metadata['chunk_uid'] for d,_ in result['retrieved_docs']], ['selected'])
            self.assertEqual([d.metadata['chunk_uid'] for d,_ in result['seed_retrieved_docs']], ['selected'])
            for query in trace['executed_queries']+trace['reused_queries']:
                self.assertEqual(query['where_filter'], trace['where_filter'])
                self.assertFalse(metadata_matches_filter(rows[0][0].metadata, query['where_filter']))
        self.assertTrue(second['retrieval_debug_trace']['reused_queries'])


if __name__ == '__main__':
    unittest.main()
