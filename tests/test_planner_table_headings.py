"""Located table headings help planning without becoming section authority."""
from copy import deepcopy
import hashlib
import json
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.agent.financial_graph_models import RequirementPlannerOutput
from src.agent.financial_source_scope import (
    build_source_section_inventory, resolve_source_section_bindings,
    source_section_applicability, source_section_requirement_errors,
)
from tests.semantic_program_test_support import FinancialAgent, _StructuredQueueLLM
from tests.test_planner_subject_projection import authored_owner


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')


def heading(text='2-4. Birch movements, excluding transfers', parent='/DOCUMENT/SECTION[1]/GROUP[1]'):
    context = dict(document_sha256='a' * 64, source_locator=parent + '/TITLE', parent_locator=parent,
        source_text=text, source_span=[0, len(text)], relation='ancestor_heading')
    identity = {key: context[key] for key in ['document_sha256', 'source_locator', 'source_span', 'source_text']}
    context['context_id'] = 'ctx_' + hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    return context


def metadata(*, path='II. Activities > 1. Records', receipt='filing-A', table_id='table-A', contexts=None):
    contexts = [heading()] if contexts is None else contexts
    table = dict(table_id=table_id, source_section_path=path, source_document_sha256='a' * 64,
        source_table_locator='/DOCUMENT/SECTION[1]/GROUP[1]/TABLE[1]', source_contexts=contexts,
        rows=[dict(row_label='Never expose body', cells=[dict(value_text='987654321')])])
    return dict(company='Issuer', year=2042, rcept_no=receipt, section_path=path,
        table_source_id=table_id, table_object_json=json.dumps(table, ensure_ascii=False))


def changed_table(row, **changes):
    table = json.loads(row['table_object_json'])
    table.update(changes)
    return {**row, 'table_object_json': json.dumps(table, ensure_ascii=False)}


def selected_owner(section_ids):
    owner = authored_owner(['Birch'])
    owner['source_section_bindings'] = [dict(first_request_unit_id='request_001',
        last_request_unit_id='request_001', section_ids=section_ids)]
    return owner


class PlannerTableHeadingTests(unittest.TestCase):
    def setUp(self):
        for target in ['socket.socket.connect', 'socket.create_connection']:
            guard = patch(target, side_effect=AssertionError('Provider-free test attempted network'))
            guard.start()
            self.addCleanup(guard.stop)

    def test_heading_keeps_exact_qualified_text_and_source_reference_without_values(self):
        context = heading('🗂 2-4. Birch movements, excluding transfers')
        row = metadata(contexts=[context])
        before = deepcopy(row)
        inventory = build_source_section_inventory([row])
        hints = inventory['table_heading_hints']
        hint, = hints['headings']
        parent = next(s for s in inventory['sections'] if s['path'][-1] == '1. Records')
        self.assertEqual(hint['section_id'], parent['section_id'])
        self.assertEqual(hint['heading'], context['source_text'])
        reference = hint['example_reference']
        for key in ['context_id', 'document_sha256', 'source_locator', 'parent_locator', 'source_span', 'relation']:
            self.assertEqual(reference[key], context[key])
        self.assertEqual(reference['table_source_id'], 'table-A')
        self.assertEqual(reference['source_table_locator'], '/DOCUMENT/SECTION[1]/GROUP[1]/TABLE[1]')
        self.assertEqual(hints['authority'], 'planning_hint_only')
        self.assertNotIn('987654321', json.dumps(inventory))
        self.assertNotIn('Never expose body', json.dumps(inventory))
        hint['example_reference']['source_span'][0] = 5
        self.assertEqual(row, before)

    def test_nearest_attached_ancestor_is_kept_without_promoting_its_path(self):
        contexts = [heading('Outer heading', '/DOCUMENT'), heading('Inner heading')]
        inventory = build_source_section_inventory([metadata(contexts=contexts)])
        self.assertEqual([h['heading'] for h in inventory['table_heading_hints']['headings']], ['Inner heading'])
        self.assertFalse(any('Inner heading' in s['path'] for s in inventory['sections']))
        duplicate = build_source_section_inventory([metadata(contexts=[heading('1. Records')])])
        self.assertEqual(duplicate['table_heading_hints']['headings'], [])

    def test_bad_context_identity_attachment_span_and_relation_never_supply_hints(self):
        changes = [dict(document_sha256='b' * 64), dict(context_id='invented'),
            dict(source_text='Rewritten'), dict(source_span=[0, 1]), dict(source_span=[False, 2]),
            dict(source_span=[-1, 38]), dict(source_locator='/DOCUMENT/ELSEWHERE/TITLE'),
            dict(parent_locator='/DOCUMENT/SECTION[1]/GROUP[10]'), dict(parent_locator=''),
            dict(relation='preceding_block'), dict(relation='table_text_row')]
        for change in changes:
            with self.subTest(change=change):
                row = metadata(contexts=[{**heading(), **change}])
                self.assertEqual(build_source_section_inventory([row])['table_heading_hints']['headings'], [])

    def test_mismatched_table_section_identifier_or_document_is_not_repaired(self):
        row = metadata()
        variants = [changed_table(row, source_section_path='III. Other'),
            changed_table(row, table_id='foreign-table'), changed_table(row, source_table_locator=''),
            changed_table(row, source_document_sha256='b' * 64),
            {**row, 'source_document_sha256': 'b' * 64},
            {**row, 'source_table_locator': '/DOCUMENT/OTHER/TABLE'},
            {**row, 'rcept_no': ''}, {**row, 'section_path': ''}]
        for variant in variants:
            with self.subTest(variant=variant):
                self.assertEqual(build_source_section_inventory([variant])['table_heading_hints']['headings'], [])

    def test_well_hashed_body_fragment_is_not_a_title_and_unknown_tables_are_omitted(self):
        context = heading()
        context['source_locator'] = context['parent_locator'] + '/P[1]'
        identity = {key: context[key] for key in ['document_sha256', 'source_locator', 'source_span', 'source_text']}
        context['context_id'] = 'ctx_' + hashlib.sha256(json.dumps(identity, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
        rows = [metadata(contexts=[context]), metadata(table_id='unknown'), metadata(table_id='?')]
        self.assertEqual(build_source_section_inventory(rows)['table_heading_hints']['headings'], [])

    def test_missing_malformed_and_non_table_contexts_do_not_invent_headings(self):
        row = metadata()
        for payload in ['', 'invalid', '[]', 'null', '{}', '{"source_contexts":"wrong"}']:
            with self.subTest(payload=payload):
                self.assertEqual(build_source_section_inventory([{**row, 'table_object_json': payload}])['table_heading_hints']['headings'], [])
        prose = {k: v for k, v in row.items() if k != 'table_object_json'}
        prose.update(local_heading='Invented', source_contexts_json=json.dumps([heading()]), source_text='Invented')
        self.assertEqual(build_source_section_inventory([prose])['table_heading_hints']['headings'], [])

    def test_duplicate_payloads_are_decoded_once_and_order_cannot_change_hints(self):
        rows = [metadata()] * 20
        loads = json.loads
        with patch('src.agent.financial_source_scope.json.loads', wraps=loads) as decode:
            inventory = build_source_section_inventory(rows)
        self.assertEqual(decode.call_count, 1)
        self.assertEqual(inventory, build_source_section_inventory(list(reversed(rows))))
        self.assertEqual(inventory['table_heading_hints']['observed_heading_count'], 1)

    def test_repeated_heading_keeps_one_deterministic_table_example(self):
        rows = [metadata(table_id='table-B'), metadata(table_id='table-A')]
        inventory = build_source_section_inventory(rows)
        hint, = inventory['table_heading_hints']['headings']
        self.assertEqual(hint['example_reference']['table_source_id'], 'table-A')
        self.assertEqual(inventory, build_source_section_inventory(list(reversed(rows))))

    def test_same_heading_in_other_section_or_filing_keeps_separate_parent_ids(self):
        rows = [metadata(), metadata(receipt='filing-B'), metadata(path='III. Other')]
        hints = build_source_section_inventory(rows)['table_heading_hints']['headings']
        self.assertEqual(len(hints), 3)
        self.assertEqual(len({h['section_id'] for h in hints}), 3)

    def test_count_budget_shares_exposure_between_sections_instead_of_filling_one(self):
        rows = [metadata(contexts=[heading(f'Title {i}', f'/DOCUMENT/SECTION[1]/GROUP[1]')],
            table_id=f'table-{i}') for i in range(8)]
        rows.append(metadata(path='III. Other', contexts=[heading('Other heading')]))
        inventory = build_source_section_inventory(rows, max_heading_hints=2)
        hints = inventory['table_heading_hints']
        self.assertEqual(len({h['section_id'] for h in hints['headings']}), 2)
        self.assertEqual(hints['observed_heading_count'], 9)
        self.assertEqual(hints['omitted_heading_count'], 7)
        self.assertTrue(hints['truncated'])
        self.assertEqual(inventory, build_source_section_inventory(list(reversed(rows)), max_heading_hints=2))

    def test_byte_budget_omits_whole_headings_without_changing_section_capacity(self):
        normal = build_source_section_inventory([metadata()])
        tiny = build_source_section_inventory([metadata()], max_heading_bytes=2)
        self.assertEqual(tiny['sections'], normal['sections'])
        self.assertEqual(tiny['fingerprint'], normal['fingerprint'])
        self.assertEqual(tiny['table_heading_hints']['headings'], [])
        self.assertEqual(tiny['table_heading_hints']['omitted_heading_count'], 1)
        hints = normal['table_heading_hints']
        self.assertEqual(hints['serialized_heading_bytes'], len(encoded(hints['headings'])))
        exact = build_source_section_inventory([metadata()], max_heading_bytes=hints['serialized_heading_bytes'])
        self.assertEqual(exact, normal)

    def test_heading_cannot_select_an_omitted_parent_section(self):
        inventory = build_source_section_inventory([metadata()], max_sections=1)
        self.assertEqual(inventory['table_heading_hints']['headings'], [])
        self.assertEqual(inventory['table_heading_hints']['omitted_heading_count'], 1)

    def test_hint_changes_leave_section_fingerprint_resolutions_and_authority_unchanged(self):
        old = build_source_section_inventory([metadata(contexts=[heading('Old title')])])
        new = build_source_section_inventory([metadata(contexts=[heading('New title')])])
        self.assertEqual(old['sections'], new['sections'])
        self.assertEqual(old['fingerprint'], new['fingerprint'])
        self.assertNotEqual(old['table_heading_hints']['fingerprint'], new['table_heading_hints']['fingerprint'])
        section_id = new['table_heading_hints']['headings'][0]['section_id']
        query = 'Use the named table, excluding transfers.'
        owner = selected_owner([section_id])
        a = resolve_source_section_bindings([owner], query=query, inventory=old)
        b = resolve_source_section_bindings([owner], query=query, inventory=new)
        self.assertEqual(a, b)
        self.assertEqual(a[0]['source_section_bindings'][0]['requested_text'], query)
        self.assertEqual(source_section_requirement_errors(b, query), [])
        self.assertEqual(source_section_applicability(metadata(receipt='filing-B'), b[0])['state'], 'conflict')
        # Membership stays at the selected parent; the model/Compiler must still
        # interpret the requested table and qualifiers. Hints do not prove it.
        self.assertEqual(source_section_applicability(metadata(contexts=[heading('Sibling table')]), b[0])['state'], 'match')

    def test_unresolved_and_context_ids_remain_invalid_after_heading_exposure(self):
        inventory = build_source_section_inventory([metadata()])
        for ids, code in [([], 'unresolved_source_section_request'),
                          ([heading()['context_id']], 'unknown_source_section_id')]:
            owner, = resolve_source_section_bindings([selected_owner(ids)], query='Use the named table.', inventory=inventory)
            self.assertEqual(source_section_requirement_errors([owner], 'Use the named table.')[0]['code'], code)
            self.assertEqual(source_section_applicability(metadata(), owner)['state'], 'invalid')

    def test_existing_planner_call_exposes_only_report_scoped_hints_and_keeps_authored_choice(self):
        rows = [metadata(), metadata(receipt='filing-B', contexts=[heading('Foreign secret heading')])]
        inventory = build_source_section_inventory(rows[:1])
        section_id = inventory['table_heading_hints']['headings'][0]['section_id']
        response = RequirementPlannerOutput.model_validate({'obligations': [selected_owner([section_id])]})
        before = deepcopy((rows, response.model_dump()))
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm, agent.llm_routes, agent.llm_usage_callback = _StructuredQueueLLM(response), {}, None
        agent.vsm = SimpleNamespace(bm25_metadatas=rows)
        query = 'Return the quantity from Birch movements, excluding transfers.'
        planned = agent._plan_answer_obligation_program({'query': query,
            'report_scope': {'company': 'Issuer', 'year': 2042, 'rcept_no': 'filing-A'}})
        self.assertEqual(len(agent.llm.prompts), 1)
        prompt = agent.llm.prompts[0].to_messages()[0].content
        self.assertIn(json.dumps(inventory, ensure_ascii=False), prompt)
        self.assertIn(heading()['source_text'], prompt)
        self.assertNotIn('Foreign secret heading', prompt)
        self.assertNotIn('987654321', prompt)
        self.assertEqual((rows, response.model_dump()), before)
        self.assertEqual(planned['semantic_plan']['requirement_errors'], [])
        actual = planned['answer_obligations'][0]['source_section_bindings'][0]
        self.assertEqual(actual['section_ids'], [section_id])
        self.assertEqual(actual['requested_text'], query)
        self.assertTrue(all('heading' not in row for row in actual['resolved_sections']))


if __name__ == '__main__':
    unittest.main()
