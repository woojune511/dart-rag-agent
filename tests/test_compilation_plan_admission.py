"""Plan capacity and real counted SDK boundaries with external sockets blocked."""
from copy import deepcopy
from decimal import Decimal
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx

from src.agent.financial_graph import FinancialAgent
from src.agent import financial_graph_calculation as compilation
from src.ops.compilation_plan_admission import (
    CompilationPlanAdmission, guarded_compilation_plan, response_batch_ceiling,
)
from src.ops.openai_server_token_count import guarded_counted_runtime_openai_responses
from src.ops.provider_admission import BudgetStop, ProviderBudget
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.test_openai_compiler_transport import Payload, ROUTE, response_body


MODEL = ROUTE['model']
POLICY = dict(cap_usd=3.0, max_openai_response_calls=5, max_openai_count_calls=5,
    max_google_calls=0, max_openai_embedding_calls=0, max_openai_input_tokens=30000,
    max_openai_request_bytes=100000, openai_count_allowance_usd_per_call=.01,
    openai_response_binding='runtime_generated_v1', openai_input_counting='responses_input_tokens_v1',
    rates={MODEL: dict(input=12.5, output=50)}, request_settings_by_model={MODEL: dict(
        model=MODEL, max_output_tokens=5120, reasoning={'effort':'medium'}, store=False, service_tier='default')})


def plan(*groups):
    return dict(schema='semantic_compilation_islands_v2', status='ok', islands=[
        dict(island_id=f'island_{i}', obligation_ids=list(group), errors=[]) for i, group in enumerate(groups)])


class CompilationPlanAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, OPENAI_API_KEY='offline-only', LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'))
        for name in ('connect', 'connect_ex'):
            self.enterContext(patch.object(socket.socket, name, side_effect=AssertionError('external network forbidden')))

    def gate(self, *, limit=3, spent_responses=2, spent_counts=2, **policy_changes):
        budget = ProviderBudget({**deepcopy(POLICY), **policy_changes})
        budget.records = [dict(kind='openai_response') for _ in range(spent_responses)]
        budget.count_records = [dict(kind='openai_response') for _ in range(spent_counts)]
        return CompilationPlanAdmission(budget, compiler_model=MODEL, max_first_responses=limit)

    def test_three_independent_groups_reject_before_first_compiler_when_limit_is_two(self):
        gate = self.gate(limit=2)
        before = deepcopy(gate.budget.snapshot())
        with self.assertRaisesRegex(BudgetStop, 'compilation_first_response_limit'):
            gate.bind(plan(['a'], ['b'], ['c']))
        self.assertEqual(gate.budget.records, before['requests'])
        self.assertEqual(gate.budget.count_records, before['token_count_requests'])
        self.assertEqual(gate.budget.charged, 0)
        self.assertEqual(gate.snapshot()['admitted_groups'], [])

    def test_three_funded_first_groups_are_allowed_without_authorizing_repairs(self):
        gate = self.gate()
        original = plan(['a'], ['b'], ['c'])
        saved = deepcopy(original)
        gate.bind(original)
        for group in (['a'], ['b'], ['c']): self.assertTrue(gate.authorize(group))
        self.assertEqual(original, saved)
        with self.assertRaisesRegex(BudgetStop, 'unapproved_compilation_group'):
            gate.authorize(['c'])

    def test_actual_builder_dependency_group_counts_once_and_restores_on_exit(self):
        owners = [dict(obligation_id=name, kind='narrative', depends_on=[] if name == 'a' else ['a'])
                  for name in ('a', 'b', 'c')]
        before = deepcopy(owners)
        original = compilation.build_semantic_compilation_islands
        expected = original(owners)
        with guarded_compilation_plan(self.gate(limit=1).budget, compiler_model=MODEL, max_first_responses=1) as gate:
            actual = compilation.build_semantic_compilation_islands(owners)
            self.assertEqual(actual, expected)
            self.assertTrue(gate.authorize(['a', 'b', 'c']))
        self.assertIs(compilation.build_semantic_compilation_islands, original)
        self.assertEqual(owners, before)

    def test_actual_physical_bundle_group_is_preserved(self):
        owners = [dict(obligation_id=name, kind='direct_value') for name in ('a', 'b')]
        constraints = [dict(constraint_id='row-group', owner_ids=['a', 'b'])]
        before = deepcopy((owners, constraints))
        with guarded_compilation_plan(self.gate(limit=1).budget, compiler_model=MODEL, max_first_responses=1) as gate:
            result = compilation.build_semantic_compilation_islands(owners, evidence_bundle_constraints=constraints)
            self.assertEqual(len(result['islands']), 1)
            self.assertTrue(gate.authorize(['a', 'b']))
        self.assertEqual((owners, constraints), before)

    def test_generation_and_count_capacity_use_independent_remaining_slots(self):
        for changes, expected in (({'max_openai_response_calls':4}, 'compilation_response_slots_exceeded'),
                                  ({'max_openai_count_calls':4}, 'compilation_count_slots_exceeded')):
            with self.subTest(changes=changes), self.assertRaisesRegex(BudgetStop, expected):
                self.gate(**changes).bind(plan(['a'], ['b'], ['c']))

    def test_full_ceiling_and_existing_accounting_are_checked_before_dispatch(self):
        self.assertEqual(response_batch_ceiling(POLICY, MODEL, 3), Decimal('1.923'))
        for cap, expected in ((2.033, True), (2.032999, False)):
            gate = self.gate(cap_usd=cap)
            gate.budget.charged, gate.budget.count_allowance = .09, .02
            if expected: gate.bind(plan(['a'], ['b'], ['c']))
            else:
                with self.assertRaisesRegex(BudgetStop, 'compilation_batch_not_funded'):
                    gate.bind(plan(['a'], ['b'], ['c']))
            self.assertEqual(gate.budget.pending, 0)
            self.assertEqual(gate.budget.charged, .09)

    def test_policy_drift_and_outstanding_request_fail_closed(self):
        gate = self.gate()
        gate.bind(plan(['a']))
        gate.budget.policy['cap_usd'] += 1
        with self.assertRaisesRegex(BudgetStop, 'compilation_policy_changed'): gate.authorize(['a'])
        gate = self.gate()
        gate.budget.pending = .01
        with self.assertRaisesRegex(BudgetStop, 'compilation_pending_request'): gate.bind(plan(['a']))

    def test_missing_rebound_foreign_partial_and_reordered_groups_are_not_allowed(self):
        with self.assertRaisesRegex(BudgetStop, 'compilation_plan_missing'):
            self.gate().authorize(['a'])
        for group in (['a'], ['b', 'a'], ['a', 'b', 'foreign'], ['foreign']):
            gate = self.gate()
            gate.bind(plan(['a', 'b']))
            with self.subTest(group=group), self.assertRaisesRegex(BudgetStop, 'unapproved_compilation_group'):
                gate.authorize(group)
        gate = self.gate()
        gate.bind(plan(['a']))
        with self.assertRaisesRegex(BudgetStop, 'compilation_plan_rebound'): gate.bind(plan(['b']))

    def test_malformed_or_overlapping_schedule_rejected(self):
        for value in ({}, plan(['a'], ['a']), plan(['a', 'a']), plan(['']), plan([])):
            with self.subTest(value=value), self.assertRaisesRegex(BudgetStop, 'invalid_compilation_schedule'):
                self.gate().bind(value)

    def test_invalid_island_is_not_granted_a_compiler_call(self):
        value = plan(['invalid'], ['valid'])
        value['status'] = 'invalid'
        value['islands'][0]['errors'] = [{'code':'dependency_cycle'}]
        gate = self.gate(limit=1)
        before = deepcopy(value)
        gate.bind(value)
        self.assertTrue(gate.authorize(['valid']))
        self.assertEqual(value, before)
        with self.assertRaisesRegex(BudgetStop, 'unapproved_compilation_group'): gate.authorize(['invalid'])

    def test_existing_terminal_cause_is_preserved(self):
        gate = self.gate()
        error = gate.budget._close('provider_request_failed', 'prior failure')
        with self.assertRaises(BudgetStop) as caught: gate.bind(plan(['a']))
        self.assertIs(caught.exception, error)
        self.assertEqual(gate.snapshot()['quotes'], [])

    def test_invalid_limit_and_cost_inputs_fail_without_transport(self):
        for limit in (0, -1, True, 2.5):
            with self.subTest(limit=limit), self.assertRaises(ValueError): self.gate(limit=limit)
        for value in (float('nan'), float('inf'), -1, True):
            policy = deepcopy(POLICY)
            policy['rates'][MODEL]['input'] = value
            with self.subTest(value=value), self.assertRaises(ValueError): response_batch_ceiling(policy, MODEL, 3)

    def sdk_run(self, *, fail_third_count=False):
        gate = self.gate(spent_responses=0, spent_counts=0)
        gate.bind(plan(['a'], ['b'], ['c']))
        sent = []
        def send(client, request, **kwargs):
            body = json.loads(request.content)
            sent.append((request.url.path, body))
            is_count = request.url.path.endswith('/input_tokens')
            if fail_third_count and len(sent) == 5:
                return httpx.Response(503, request=request, json={'error':{'message':'private failure','type':'server_error'}})
            return httpx.Response(200, request=request, json={'object':'response.input_tokens', 'input_tokens':100} if is_count
                else response_body(dict(value=2, comment=None, flags=[])))
        def authorize(body): return gate.authorize(json.loads(body['input'][0]['content'])['owners'])
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        with patch.object(httpx.Client, 'send', send), guarded_counted_runtime_openai_responses(gate.budget, authorize):
            llm = agent._create_chat_model(ROUTE, phase='program_compilation').with_structured_output(Payload, include_raw=True)
            for name in ('a', 'b'):
                self.assertIsNone(llm.invoke(json.dumps({'owners':[name]}))['parsing_error'])
            if fail_third_count:
                with self.assertRaisesRegex(BudgetStop, 'provider_token_count_failed'):
                    llm.invoke(json.dumps({'owners':['c']}))
            else:
                self.assertIsNone(llm.invoke(json.dumps({'owners':['c']}))['parsing_error'])
                with self.assertRaisesRegex(BudgetStop, 'unapproved_compilation_group'):
                    llm.invoke(json.dumps({'owners':['c']}))
        self.assertNotIn('private failure', json.dumps(gate.budget.snapshot()))
        self.assertEqual(gate.budget.pending, 0)
        return gate, sent

    def test_real_sdk_three_first_count_generation_pairs_and_no_repair_http(self):
        gate, sent = self.sdk_run()
        self.assertEqual(len(sent), 6)
        for i in (0, 2, 4):
            self.assertEqual(sent[i][1], {k:sent[i+1][1][k] for k in ('model','input','instructions','reasoning','text') if k in sent[i+1][1]})
        self.assertEqual(len(gate.budget.records), 3)
        self.assertEqual(len(gate.budget.count_records), 3)

    def test_third_count_failure_is_terminal_without_generation_or_retry(self):
        gate, sent = self.sdk_run(fail_third_count=True)
        self.assertEqual(len(sent), 5)
        self.assertEqual(len(gate.budget.records), 2)
        self.assertEqual(len(gate.budget.count_records), 3)
        self.assertEqual(gate.budget.stop_reason.code, 'provider_token_count_failed')


if __name__ == '__main__': unittest.main()
