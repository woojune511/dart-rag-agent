"""Mixed cell/prose/dependency integration. Authored replies do not prove semantics."""
from copy import deepcopy
import json
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_reconciliation_candidates import semantic_candidate_catalog_fingerprint
from tests.mixed_numeric_source_test_support import (
    authored_program, canonical, capture_initial, compile_case, execute, load_criteria, load_sources, materialize,
)
from tests.semantic_program_test_support import execute_compiled_fixture


class MixedNumericSourceIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.addCleanup(patch.stopall)
        patch.object(socket.socket, 'connect', side_effect=AssertionError('provider forbidden')).start()
        patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('provider forbidden')).start()
        self.sources = load_sources()
        self.criteria = load_criteria()

    def witness(self, index=0):
        case = materialize(self.sources[index])
        return case, authored_program(case, self.criteria[case['case_id']])

    def assert_outputs(self, case, result):
        self.assertEqual(result['status'], 'ok', result)
        for expected in self.criteria[case['case_id']]['expressions']:
            actual = result['outputs_by_obligation'][expected['obligation_id']]
            self.assertEqual(actual['calculated_value'], expected['expected_calculated'])
            self.assertEqual(actual['normalized_value'], expected['expected_calculated'])
            self.assertEqual(actual['answer_slot']['normalized_value'], expected['expected_display'])
            self.assertEqual(actual['normalized_unit'], expected['unit'])

    def test_real_sources_normalize_and_execute_all_mixed_paths(self):
        for index, source in enumerate(self.sources):
            with self.subTest(case=source['case_id']):
                case, program = self.witness(index)
                before = deepcopy(case)
                by_id = {c['candidate_id']: c for c in case['candidate_catalog']}
                for key, value in self.criteria[case['case_id']]['normalized_sources'].items():
                    self.assertEqual(by_id[case['fixture_candidate_ids'][key]]['normalized_value'], value)
                compiled, queue, _ = compile_case(case, [program])
                self.assertEqual(len(queue.wires), 1)
                self.assertEqual(compiled['semantic_program_retry_count'], 0)
                self.assertEqual(compiled['semantic_program_validation']['status'], 'ready')
                self.assert_outputs(case, execute(case, compiled))
                self.assertEqual(case, before)
                Draft202012Validator(queue.models[0].model_json_schema()).validate(queue.wires[0])

    def test_prose_quotes_cells_and_dependencies_keep_distinct_shapes(self):
        case, program = self.witness()
        compiled, queue, _ = compile_case(case, [program])
        model = queue.models[0]
        refs = model.__compiler_references__
        by_id = {c['candidate_id']: c for c in case['candidate_catalog']}
        kinds = set()
        for output in queue.wires[0]['outputs'].values():
            for values in output['result']['inputs'].values():
                for selection in values:
                    resolved = refs.resolve(selection['source_ref'])
                    if resolved in by_id:
                        candidate = by_id[resolved]
                        kinds.add(candidate['candidate_kind'])
                        if candidate['candidate_kind'] == 'sentence_value':
                            self.assertIn(selection['evidence_text'], candidate['source_bundle_text'])
                        else:
                            self.assertNotIn('evidence_text', selection)
                            self.assertTrue(candidate['physical_cell_id'])
                    else:
                        kinds.add('dependency')
                        self.assertEqual(set(selection), {'source_ref', 'variable', 'scope_applicability_fields'})
                        self.assertEqual(selection['scope_applicability_fields'], [])
        self.assertEqual(kinds, {'structured_row', 'sentence_value', 'dependency'})
        self.assertTrue(compiled['semantic_program']['source_assertions'])

    def test_initial_transport_does_not_depend_on_authored_answers_or_carrier_order(self):
        for index in range(len(self.sources)):
            case, program = self.witness(index)
            reverse = materialize(self.sources[index], reverse_carriers=True)
            self.assertEqual(case['fixture_candidate_ids'], reverse['fixture_candidate_ids'])
            self.assertEqual(semantic_candidate_catalog_fingerprint(case['candidate_catalog']),
                             semantic_candidate_catalog_fingerprint(reverse['candidate_catalog']))
            model, messages = capture_initial(case)
            other_model, other_messages = capture_initial(reverse)
            self.assertEqual(messages, other_messages)
            self.assertEqual(model.model_json_schema(), other_model.model_json_schema())
            _, queue, _ = compile_case(case, [program])
            self.assertEqual(messages, queue.messages[0])
            self.assertNotIn('Explicit offline witness', canonical(messages).decode())

    def test_dependency_uses_computed_value_not_reported_display(self):
        case, program = self.witness(3)
        compiled, _, _ = compile_case(case, [program])
        result = execute(case, compiled)
        self.assert_outputs(case, result)
        self.assertEqual(result['outputs_by_obligation']['growth']['calculated_value'], 20)
        self.assertEqual(result['outputs_by_obligation']['growth']['answer_slot']['normalized_value'], 21)
        self.assertEqual(result['outputs_by_obligation']['double']['calculated_value'], 40)
        self.assertNotEqual(result['outputs_by_obligation']['double']['calculated_value'], 42)

    def test_targeted_retry_preserves_accepted_prose_assertions_and_computed_dependency(self):
        for index in (0, 3):
            case, good = self.witness(index)
            clean, _, _ = compile_case(case, [good])
            first = deepcopy(good)
            target = first['expressions'][-1]['obligation_id']
            first['expressions'][-1]['formula'] = 'UNBOUND'
            repair = deepcopy(good)
            repair['expressions'] = [repair['expressions'][-1]]
            # Assertion selection is derived from the explicit retry witness's
            # referenced sources, not from validation feedback or answer values.
            used = {b['source_id'] for b in repair['expressions'][0]['variable_bindings']}
            repair['source_assertions'] = [{**a, 'candidate_ids': [c for c in a['candidate_ids'] if c in used]}
                for a in repair['source_assertions'] if any(c in used for c in a['candidate_ids'])]
            compiled, queue, captured = compile_case(case, [first, repair])
            self.assertEqual(len(queue.wires), 2)
            self.assertEqual(compiled['semantic_program_retry_count'], 1)
            self.assertEqual(set(queue.models[1].model_json_schema()['$defs']['CompilerOutputs']['properties']), {target})
            self.assert_outputs(case, execute(case, compiled))
            accepted = good['expressions'][0]['obligation_id']
            old = [r for r in clean['semantic_program']['expressions'] if r['obligation_id'] == accepted]
            new = [r for r in compiled['semantic_program']['expressions'] if r['obligation_id'] == accepted]
            self.assertEqual(canonical(old), canonical(new))
            feedback = json.loads(captured[1]['retry_feedback'])
            dependency = feedback['read_only_dependency_outputs'][accepted]
            self.assertEqual(dependency['normalized_value'], self.criteria[case['case_id']]['expressions'][0]['expected_calculated'])
            old_assertions = clean['semantic_program']['source_assertions']
            # Whole finalized assertions (including shared sentence membership)
            # must be unchanged after targeted repair.
            self.assertEqual(canonical(compiled['semantic_program']['source_assertions']), canonical(old_assertions))

    def test_wrong_or_missing_prose_quote_is_not_silently_repaired(self):
        case, good = self.witness()
        for mutation in ('missing', 'inexact', 'uncovered'):
            def corrupt(raw, attempt, model):
                selection = raw['outputs']['net']['result']['inputs']['adjustment'][0]
                if mutation == 'missing':
                    selection.pop('evidence_text')
                else:
                    selection['evidence_text'] = 'Not in this source' if mutation == 'inexact' else 'Nova'
            compiled, queue, _ = compile_case(case, [good, good], mutate=corrupt)
            self.assertEqual(len(queue.wires), 2)
            self.assertNotEqual(compiled['semantic_program_validation']['status'], 'ready')
            self.assertNotIn('net', execute(case, compiled)['outputs_by_obligation'])

    def test_source_content_and_program_tampering_remain_blocked(self):
        case, program = self.witness()
        compiled, _, _ = compile_case(case, [program])
        changed = deepcopy(case)
        candidate = next(c for c in changed['candidate_catalog'] if c['candidate_kind'] == 'sentence_value')
        candidate['source_bundle_text'] += ' '
        result = execute(changed, compiled)
        self.assertEqual(result['outputs'], [])
        self.assertEqual(result['validation']['status'], 'invalid')
        self.assertIn('execution_content_mismatch', {e['code'] for e in result['validation']['errors']})
        changed_program = deepcopy(compiled)
        changed_program['semantic_program']['expressions'][0]['formula'] = 'A+B'
        result = execute(case, changed_program)
        self.assertEqual(result['outputs'], [])
        self.assertIn('validation_drift', {e['code'] for e in result['validation']['errors']})

    def test_final_answer_and_ledger_use_the_same_mixed_results(self):
        case, program = self.witness(3)
        compiled, _, _ = compile_case(case, [program])
        agent = object.__new__(FinancialAgent)
        state = {**compiled, 'query': case['question'], 'answer_obligations': case['obligations']}
        final = execute_compiled_fixture(agent, state, case['candidate_catalog'])
        self.assertIn('structured_result', final)
        self.assertEqual(final['structured_result']['status'], 'ok')
        self.assertEqual(final['task_artifact_trace']['integrity_status'], 'ok')
        aggregate = next(a for a in final['artifacts'] if a['kind'] == 'aggregated_answer')['payload']
        self.assertEqual(aggregate['final_answer'], final['answer'])
        for field in ('structured_result', 'evidence_items', 'resolved_calculation_trace'):
            self.assertEqual(canonical(aggregate[field]), canonical(final[field]))
        self.assertIn('21%', final['answer'])
        self.assertIn('20%', final['answer'])
        self.assertIn('40%', final['answer'])
        evidence = {e['evidence_id'] for e in final['evidence_items']}
        self.assertEqual(evidence, set(case['fixture_candidate_ids'].values()))


if __name__ == '__main__':
    unittest.main()
