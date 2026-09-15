"""Generation choices mirror source authority, not a semantic answer oracle."""
from copy import deepcopy
import json
import unittest

from jsonschema import Draft202012Validator

from src.agent.financial_compiler_wire import lower_compiler_response
from src.agent.financial_reconciliation_candidates import build_semantic_candidate_catalog
from tests.test_numeric_compiler_grounding import wire, source, output
from tests.semantic_program_test_support import _obligation, _requirement, _scope


def calculation(inputs, **extra):
    return {'outputs': {'answer': {'status': 'ready', 'result': {
        'inputs': inputs, 'formula': 'target-reference', 'comparison_request_unit_id': 'request_001',
        'source_display': None, 'source_display_reason': 'Calculation requested.', 'constants': [], **extra}}}}


def direct(selection):
    return {'outputs': {'answer': {'status': 'ready', 'result': {'selection': selection}}}}


def prose():
    rows = build_semantic_candidate_catalog([{'candidate_id': 'prose-source', 'candidate_kind': 'chunk',
        'source_anchor': '[anonymous]', 'text': 'The reading is 23%.', 'metadata': {'is_table': False}}])
    return next(row for row in rows if row['kind'] == 'numeric')


class CompilerSourceChoiceTests(unittest.TestCase):
    def assert_schema(self, model, raw, *, valid=True):
        schema = model.model_json_schema()
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(raw))
        self.assertEqual(not errors, valid, [e.message for e in errors])

    def test_source_ref_is_an_owner_choice_not_an_unrestricted_string(self):
        owners = [_obligation('answer', 'derived_value', 'quantity', scope=_scope(period='2045'), evidence_requirements=[
            _requirement('later', 'quantity', period='2045'), _requirement('earlier', 'quantity', period='2044')])]
        catalog = [source('later-value', context=False), source('earlier-value', context=False, period='2044'),
                   source('hidden', context=False, period='2043')]
        refs, model, visibility, _ = wire(catalog, owners)
        raw = calculation({'later': [{'source_ref': refs.ref('later-value'), 'variable': 'reference'}],
                           'earlier': [{'source_ref': refs.ref('earlier-value'), 'variable': 'target'}]})
        self.assert_schema(model, raw)
        before = deepcopy(raw)
        for candidate in ('earlier-value', 'hidden'):
            invalid = deepcopy(raw)
            invalid['outputs']['answer']['result']['inputs']['later'][0]['source_ref'] = refs.ref(candidate)
            self.assert_schema(model, invalid, valid=False)
            with self.assertRaises(ValueError):
                lower_compiler_response(invalid, model=model, refs=refs, obligations=owners,
                                        catalog=catalog, visibility=visibility)
        self.assertEqual(raw, before)
        self.assertNotIn(refs.ref('hidden'), json.dumps(model.model_json_schema()))

    def test_two_period_values_cannot_both_go_in_one_input(self):
        owners = [_obligation('answer', 'derived_value', 'quantity', evidence_requirements=[
            _requirement('later', 'quantity', period='2045'), _requirement('earlier', 'quantity', period='2044')])]
        refs, model, _, _ = wire([source('a', context=False), source('b', context=False, period='2044')], owners)
        raw = calculation({'later': [{'source_ref': refs.ref('a'), 'variable': 'reference'},
                                    {'source_ref': refs.ref('b'), 'variable': 'target'}], 'earlier': []})
        self.assert_schema(model, raw, valid=False)

    def test_table_selection_has_no_prose_quote_field(self):
        refs, model, _, _ = wire([source(context=False)], [output()])
        self.assert_schema(model, direct({'source_ref': refs.ref('cell')}))
        for quote in ('23', None):
            self.assert_schema(model, direct({'source_ref': refs.ref('cell'), 'evidence_text': quote}), valid=False)
        self.assertNotIn('"evidence_text"', json.dumps(model.model_json_schema()))

    def test_prose_selection_requires_quote_and_mixed_sources_keep_both_shapes(self):
        sentence = prose()
        for catalog in ([sentence], [source(context=False), sentence]):
            refs, model, visibility, _ = wire(catalog, [output()])
            quote = {'source_ref': refs.ref(sentence['candidate_id']), 'evidence_text': '23%'}
            self.assert_schema(model, direct(quote))
            for invalid in ({'source_ref': quote['source_ref']}, {**quote, 'evidence_text': None}):
                self.assert_schema(model, direct(invalid), valid=False)
            program = lower_compiler_response(direct(quote), model=model, refs=refs, obligations=[output()],
                                             catalog=catalog, visibility=visibility)
            self.assertEqual(program['source_assertions'][0]['evidence_text'], '23%')
            if len(catalog) == 2:
                self.assert_schema(model, direct({'source_ref': refs.ref('cell')}))
                self.assert_schema(model, direct({'source_ref': refs.ref('cell'), 'evidence_text': '23'}), valid=False)

    def test_dependencies_do_not_borrow_source_grounding_or_other_output_ids(self):
        owners = [_obligation('answer', 'derived_value', 'quantity', depends_on=['base'], evidence_requirements=[
            _requirement('additional', 'quantity')])]
        refs, model, _, _ = wire([source(context=False)], owners)
        raw = calculation({'additional': [{'source_ref': refs.ref('cell'), 'variable': 'target'}],
                           'dependencies': [{'source_ref': 'base', 'variable': 'reference'}]})
        self.assert_schema(model, raw)
        for change in ({'source_ref': refs.ref('cell')}, {'source_ref': 'foreign'},
                       {'evidence_text': '23'}, {'interpretation': None}, {'context_evidence': []}):
            invalid = deepcopy(raw)
            invalid['outputs']['answer']['result']['inputs']['dependencies'][0].update(change)
            self.assert_schema(model, invalid, valid=False)

    def test_no_requirement_input_preserves_source_and_dependency_alternatives(self):
        owners = [_obligation('answer', 'derived_value', 'quantity', depends_on=['base'])]
        refs, model, _, _ = wire([source(context=False)], owners)
        self.assert_schema(model, calculation({'own': [{'source_ref': refs.ref('cell'), 'variable': 'target'},
                                                       {'source_ref': 'base', 'variable': 'reference'}]}))

    def test_empty_source_spaces_allow_explicit_missing_without_fake_enum(self):
        refs, model, _, _ = wire([source(context=False)], [output(scope=_scope(period='2044'))])
        self.assert_schema(model, {'outputs': {'answer': {'status': 'missing', 'result': None}}})
        self.assert_schema(model, direct({'source_ref': refs.ref('cell')}), valid=False)

    def test_empty_requirement_has_only_empty_array_but_dependency_is_usable(self):
        owners = [_obligation('answer', 'derived_value', 'quantity', depends_on=['base'], evidence_requirements=[
            _requirement('unavailable', 'quantity', period='2044')])]
        refs, model, _, _ = wire([source(context=False)], owners)
        raw = calculation({'unavailable': [], 'dependencies': [{'source_ref': 'base', 'variable': 'reference'}]})
        self.assert_schema(model, raw)
        raw['outputs']['answer']['result']['inputs']['unavailable'] = [{'source_ref': refs.ref('cell'), 'variable': 'target'}]
        self.assert_schema(model, raw, valid=False)

    def test_multiple_legal_members_remain_selectable_and_schema_is_not_authority(self):
        catalog = [source('one', context=False), source('two', context=False)]
        owners = [_obligation('answer', 'derived_value', 'quantity', evidence_requirements=[_requirement('items', 'quantity')])]
        refs, model, visibility, _ = wire(catalog, owners)
        self.assertIs(model.__compiler_visibility__, visibility)
        raw = calculation({'items': [{'source_ref': refs.ref(name), 'variable': variable}
                                     for name, variable in zip(('one', 'two'), ('reference', 'target'))]})
        self.assert_schema(model, raw)
        before = deepcopy((catalog, owners, visibility.to_projection()))
        # Mutating a returned JSON schema cannot authorize a made-up source.
        schema = model.model_json_schema()
        schema['$defs']['CellInput_items']['properties']['source_ref']['enum'].append('invented')
        raw['outputs']['answer']['result']['inputs']['items'][0]['source_ref'] = 'invented'
        with self.assertRaises(ValueError):
            lower_compiler_response(raw, model=model, refs=refs, obligations=owners, catalog=catalog, visibility=visibility)
        self.assertEqual((catalog, owners, visibility.to_projection()), before)

    def test_source_order_and_names_do_not_assign_comparison_roles(self):
        for names, periods in ((('a', 'b'), ('2045', '2044')),
                              (('z', 'q'), ('2081', '2080'))):
            owners = [_obligation('answer', 'derived_value', 'quantity', evidence_requirements=[
                _requirement('x', 'quantity', period=periods[0]), _requirement('y', 'quantity', period=periods[1])])]
            catalog = [source(name, context=False, period=period) for name, period in zip(names, periods)]
            # Equal values cannot determine the request's endpoint assignment.
            setup = wire(catalog, owners)
            reverse = wire(catalog[::-1], owners)
            self.assertEqual(setup[1].model_json_schema(), reverse[1].model_json_schema())
            refs, model, _, _ = setup
            for variables in (('reference', 'target'), ('target', 'reference')):
                self.assert_schema(model, calculation({key: [{'source_ref': refs.ref(name), 'variable': variable}]
                    for key, name, variable in zip(('x', 'y'), names, variables)}))


if __name__ == '__main__':
    unittest.main()
