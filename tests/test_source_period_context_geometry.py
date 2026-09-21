"""Period geometry follows a unique owned column label in attached source text."""
from copy import deepcopy
import unittest

from src.agent.financial_calculation_execution import source_candidate_applicability
from src.agent.financial_measurement_periods import source_date_shape
import tests.test_structured_measurement_period as fixtures


def located(declaration, *, label='제 73 기', year=2042):
    candidate = fixtures.cell(label, report_year=year)
    candidate.update(source_document_sha256='a' * 64, source_table_locator='/ROOT/GROUP/TABLE[2]')
    candidate['source_contexts'] = [dict(context_id='period-context', relation='preceding_block',
        document_sha256='a' * 64, parent_locator='/ROOT/GROUP', source_locator='/ROOT/GROUP/TABLE[1]',
        source_text=declaration, source_span=[0, len(declaration)])]
    return candidate


class SourcePeriodContextGeometryTests(unittest.TestCase):
    setUp = fixtures.StructuredMeasurementPeriodTests.setUp
    plan = fixtures.StructuredMeasurementPeriodTests.plan
    finish = fixtures.StructuredMeasurementPeriodTests.finish

    def state(self, candidate, kind='year', **fields):
        spec = fixtures.period(kind, **(fields or dict(year=2042, coverage='whole_year')))
        return source_candidate_applicability(candidate, fixtures.owner('requested period', spec))['field_states']['period']

    def test_attached_point_date_matches_its_own_fiscal_column(self):
        candidate = located('제 73 기 2042.12.31 현재\n제 72 기 2041.12.31 현재')
        self.assertEqual(self.state(candidate, 'date', date='2042-12-31'), 'match')
        self.assertEqual(source_date_shape(candidate), ('date', '2042-12-31'))

    def test_attached_point_cannot_pass_as_whole_year(self):
        candidate = located('제 73 기 2042.12.31 현재')
        self.assertEqual(self.state(candidate), 'unknown')
        self.assertEqual(self.state(candidate, year=2042, coverage='within_year'), 'match')

    def test_exact_date_executes_and_carries_original_context_proof(self):
        candidate = located('제 73 기          2042.12.31 현재')
        before = deepcopy(candidate)
        agent, state, llm = self.plan([fixtures.owner('specified date', fixtures.period('date', date='2042-12-31'))])
        answer = self.finish(agent, state, llm, [candidate])
        self.assertEqual(answer['structured_result']['status'], 'ok')
        operand = answer['resolved_calculation_trace']['calculation_operands'][0]
        evidence, = operand['source_period_context_evidence']
        self.assertEqual(evidence['evidence_text'], candidate['source_contexts'][0]['source_text'])
        self.assertEqual(evidence['column_header'], '제 73 기')
        self.assertEqual(tuple(evidence['date_shape']), ('date', '2042-12-31'))
        self.assertEqual(candidate, before)
        self.assertEqual(operand['source_period_surface'], '제 73 기')

    def test_annual_interval_uses_source_dates_including_noncalendar_year(self):
        for start, end, year in (('2042-01-01', '2042-12-31', 2042), ('2041-04-01', '2042-03-31', 2042),
                                 ('2043-03-01', '2044-02-29', 2044)):
            candidate = located(f'제 73 기 {start} to {end}', year=year)
            self.assertEqual(self.state(candidate, year=year, coverage='whole_year'), 'match')
            self.assertEqual(self.state(candidate, 'date_interval', start_date=start, end_date=end), 'match')
            self.assertEqual(source_date_shape(candidate), ('date_interval', start, end))

    def test_partial_and_overlong_intervals_do_not_become_annual(self):
        for end in ('2042-03-31', '2042-12-30', '2043-01-01'):
            candidate = located(f'제 73 기 2042-01-01 to {end}')
            self.assertEqual(self.state(candidate), 'unknown')
        candidate = located('제 73 기 2042-01-01 to 2042-03-31')
        self.assertEqual(self.state(candidate, year=2042, coverage='within_year'), 'match')

    def test_missing_declaration_does_not_invent_dates_or_change_annual_compatibility(self):
        candidate = located('unrelated attached text')
        self.assertIsNone(source_date_shape(candidate))
        self.assertEqual(self.state(candidate), 'match')
        self.assertEqual(self.state(candidate, 'date', date='2042-12-31'), 'conflict')

    def test_other_columns_and_substrings_cannot_supply_geometry(self):
        for text in ('제 72 기 2042-12-31', '제 173 기 2042-12-31', 'prefix 제 73 기 2042-12-31'):
            candidate = located(text)
            self.assertIsNone(source_date_shape(candidate))
            self.assertEqual(self.state(candidate, 'date', date='2042-12-31'), 'conflict')

    def test_foreign_context_coordinates_do_not_supply_geometry(self):
        for field,value in (('document_sha256', 'b'*64), ('parent_locator','/ROOT/OTHER'),
                            ('relation','ancestor_heading')):
            candidate = located('제 73 기 2042-12-31')
            candidate['source_contexts'][0][field] = value
            self.assertIsNone(source_date_shape(candidate))

    def test_header_whitespace_is_linked_without_rewriting_original_text(self):
        candidate = located('제73기 2042-12-31', label='제 73 기')
        self.assertEqual(source_date_shape(candidate), ('date','2042-12-31'))
        self.assertEqual(candidate['column_headers'], ['제 73 기'])
        self.assertEqual(candidate['source_contexts'][0]['source_text'], '제73기 2042-12-31')

    def test_multiple_column_labels_or_conflicting_declarations_stay_unknown(self):
        candidate = located('제 73 기 2042-12-31\n제 73 기 2042-03-31')
        self.assertEqual(source_date_shape(candidate), ('unknown',))
        candidate = located('제 73 기 2042-12-31\n제 72 기 2041-12-31')
        candidate['column_headers'] = ['제 73 기', '제 72 기']
        self.assertEqual(source_date_shape(candidate), ('unknown',))

    def test_duplicate_ambiguous_quote_and_unjoined_endpoints_stay_unknown(self):
        for text in ('제 73 기 2042-12-31\n제 73 기 2042-12-31',
                     '제 73 기 2042-01-01 to\n2042-12-31',
                     '제 73 기 2042-01-01\n제 73 기 2042-12-31'):
            self.assertEqual(source_date_shape(located(text)), ('unknown',))

    def test_partial_qualifiers_and_invalid_dates_cannot_be_annual_proofs(self):
        for text in ('제 73 기 Q1 2042-01-01 to 2042-12-31',
                     '제 73 기 2042-01-01 to 2042-12-31 Q1',
                     '제 73 기 2042-02-30', '제 73 기 1분기',
                     '제 73 기 2042-01-01 to 03-31'):
            candidate = located(text)
            self.assertEqual(source_date_shape(candidate), ('unknown',))
            self.assertEqual(self.state(candidate), 'unknown')

    def test_explicit_axis_geometry_is_never_overridden_by_context(self):
        candidate = located('제 73 기 2042-12-31')
        candidate['column_headers'].append('2042-03-31')
        self.assertEqual(source_date_shape(candidate), ('unknown',))
        self.assertNotEqual(self.state(candidate, 'date', date='2042-12-31'), 'match')

    def test_calendar_year_label_is_not_a_prefix_match_inside_a_date(self):
        self.assertIsNone(source_date_shape(located('2042-12-31', label='2042')))
        candidate = located('2042 2042-01-01 to 2042-12-31', label='2042')
        self.assertEqual(source_date_shape(candidate), ('date_interval','2042-01-01','2042-12-31'))

    def test_within_year_and_different_target_year_keep_existing_boundaries(self):
        candidate = located('제 73 기 2041-04-01 to 2042-03-31')
        self.assertEqual(self.state(candidate, year=2042, coverage='within_year'), 'conflict')
        self.assertEqual(self.state(candidate, year=2041, coverage='whole_year'), 'conflict')

    def test_context_dates_outside_projected_year_remain_conflicting(self):
        for text in ('제 73 기 2043-12-31', '제 73 기 2043-01-01 to 2043-12-31'):
            candidate = located(text, year=2042)
            self.assertEqual(self.state(candidate), 'conflict')

    def test_v2_rejects_context_geometry_mutation_after_compilation(self):
        agent, state, llm = self.plan([fixtures.owner('specified date', fixtures.period('date',date='2042-12-31'))])
        self.finish(agent, state, llm, [located('제 73 기 2042-12-31')])
        state['candidates']['semantic_candidate_catalog'][0]['source_contexts'][0]['source_text'] = '제 73 기 2042-03-31'
        self.assertIn('execution_content_mismatch', str(agent._execute_numeric_phase(state)))


if __name__ == '__main__':
    unittest.main()
