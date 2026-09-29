"""Counted admission controls: installed SDK, authored totals, no external network."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import hashlib
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from openai import AsyncOpenAI, OpenAI

from src.agent.financial_graph import FinancialAgent
from src.ops.openai_provider_admission import openai_request_parameters
from src.ops.openai_server_token_count import counted_openai_request, guarded_counted_runtime_openai_responses
from src.ops.provider_admission import BudgetStop, ProviderBudget, guarded_providers, json_bytes
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from src.utils.request_diagnostics import request_diagnostic_scope
from tests.test_openai_compiler_transport import Payload, POLICY, ROUTE, response_body


COUNT_POLICY = {**POLICY, 'openai_input_counting': 'responses_input_tokens_v1',
    'openai_response_binding': 'runtime_generated_v1', 'max_openai_count_calls': 4,
    'openai_count_allowance_usd_per_call': 0.01, 'max_openai_response_calls': 4,
    'max_openai_request_bytes': 300000, 'max_google_calls': 0, 'max_openai_embedding_calls': 1}
PRIVATE = 'private-credential-and-provider-detail'


class OpenAIServerCountTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, OPENAI_API_KEY=PRIVATE, GOOGLE_API_KEY=PRIVATE,
            LANGSMITH_TRACING='false', LANGCHAIN_TRACING_V2='false'))
        original_connect = socket.socket.connect

        def local_only(sock, address):
            if isinstance(address, tuple) and address[0] in ('127.0.0.1', '::1'):
                return original_connect(sock, address)
            raise AssertionError('External network forbidden')

        self.enterContext(patch.object(socket.socket, 'connect', local_only))
        self.enterContext(patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('External network forbidden')))
        self.agent = FinancialAgent.__new__(FinancialAgent)
        self.agent.llm_usage_callback = GeminiUsageCallbackHandler()
        self.policy = deepcopy(COUNT_POLICY)
        self.policy['rates']['text-embedding-3-large'] = dict(input=.13, output=0)
        self.sent = []
        self.count_response = dict(object='response.input_tokens', input_tokens=100)
        self.after_count = lambda: None
        self.generation_wire = lambda body: dict(value=2, comment=None, flags=[])
        self.status = {}
        self.timeout_stage = None
        self.generation_usage = dict(input_tokens=100, output_tokens=30, total_tokens=130,
            input_tokens_details=dict(cached_tokens=20), output_tokens_details=dict(reasoning_tokens=10))
        self.enterContext(patch.object(httpx.Client, 'send', self.send))

    def send(self, request, **kwargs):
        body = json.loads(request.content)
        stage = 'count' if request.url.path.endswith('/input_tokens') else 'embedding' if request.url.path.endswith('/embeddings') else 'generation'
        self.sent.append(dict(stage=stage, body=deepcopy(body), url=str(request.url), redirects=kwargs.get('follow_redirects')))
        if stage == self.timeout_stage:
            raise httpx.ReadTimeout(PRIVATE, request=request)
        status = self.status.get(stage, 200)
        if status != 200:
            return httpx.Response(status, request=request, headers={'location': 'https://unapproved.invalid'},
                json={'error': {'message': PRIVATE, 'type': 'server_error', 'code': 'unavailable'}})
        if stage == 'count':
            self.after_count()
            value = self.count_response
        elif stage == 'embedding':
            value = dict(object='list', model=body['model'], data=[dict(object='embedding', index=0, embedding=[0., 1.])],
                usage=dict(prompt_tokens=10, total_tokens=10))
        else:
            value = response_body(self.generation_wire(body))
            value.update(model=body['model'], usage=self.generation_usage)
        return httpx.Response(status, request=request, json=value)

    def invoke(self, text='Anonymous source: 나무 12\r\nnext line.', route=None):
        llm = self.agent._create_chat_model(route or ROUTE, phase='program_compilation')
        return llm.with_structured_output(Payload, include_raw=True).invoke(text)

    def client(self, **kwargs):
        return self.enterContext(OpenAI(api_key=PRIVATE, max_retries=0, timeout=90, **kwargs))

    def raw_body(self):
        return {**deepcopy(POLICY['request_settings']), 'input': 'Exact source.',
            'text': {'format': {'type': 'json_schema', 'name': 'Anonymous', 'strict': True,
                'schema': {'type': 'object', 'properties': {'value': {'type': 'integer'},
                    'comment': {'type': ['string', 'null']}, 'flags': {'type': 'array', 'items': {'type': 'string'}}},
                    'required': ['value', 'comment', 'flags'], 'additionalProperties': False}}}}

    def test_installed_sdk_count_and_generation_share_all_input_and_response_schema(self):
        before = self.invoke()
        original = deepcopy(self.sent.pop()['body'])
        seen = []

        def authorize(body):
            seen.append(deepcopy(body))
            body['input'] = 'Authorizer copy only.'
            return True

        with request_diagnostic_scope(True) as recorder, guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), authorize) as budget:
            result = self.invoke()
        self.assertEqual(result['parsed'], before['parsed'])
        self.assertIsNone(result['parsing_error'])
        count, generation = self.sent
        self.assertEqual(generation['body'], original)
        self.assertEqual(seen, [original])
        self.assertEqual(count['body'], {key: original[key] for key in ('model', 'input', 'reasoning', 'text')})
        self.assertEqual([r['redirects'] for r in self.sent], [False, False])
        snapshot = budget.snapshot()
        record, measurement = snapshot['requests'][0], snapshot['token_count_requests'][0]
        self.assertEqual(record['input_token_reservation'], 100)
        self.assertEqual(record['output_token_reservation'], 5120)
        self.assertEqual(record['input_reservation_method'], 'responses_input_tokens_v1')
        self.assertEqual(record['request_sha256'], measurement['generation_request_sha256'])
        self.assertEqual(record['token_count_request_sha256'], hashlib.sha256(json_bytes(count['body'])).hexdigest())
        self.assertAlmostEqual(budget.charged, (100 * 12.5 + 30 * 50) / 1e6)
        self.assertEqual(snapshot['token_count_allowance_usd'], .01)
        self.assertNotIn('google_input_counting', snapshot)
        self.assertNotIn(PRIVATE, json.dumps(snapshot) + json.dumps(recorder.snapshot()))

    def test_explicit_policy_limits_and_authorizer_are_required(self):
        changes = [{'openai_input_counting': 'unknown'}, {'max_openai_count_calls': True}, {'max_openai_count_calls': -1}]
        changes += [{'openai_count_allowance_usd_per_call': value} for value in (None, True, 0, -1, float('nan'))]
        changes += [{'max_openai_input_tokens': value} for value in (True, 0, 200001)]
        changes += [{'max_openai_request_bytes': value} for value in (None, True, 0)]
        changes += [{'openai_response_binding': None}, {'openai_input_counting': None}]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(ValueError):
                with guarded_counted_runtime_openai_responses(ProviderBudget({**self.policy, **change}), lambda _: True):
                    self.fail('Invalid policy entered')
        with self.assertRaises(ValueError), guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), None):
            self.fail('Missing authorizer')
        with self.assertRaises(ValueError):
            openai_request_parameters(self.policy, self.raw_body())
        params, count = counted_openai_request(self.policy, self.raw_body())
        self.assertNotIn('input_bound', params)
        self.assertEqual(params['output_bound'], 5120)
        self.assertEqual(count['input'], 'Exact source.')
        self.assertEqual(self.sent, [])

    def test_known_denial_prevents_even_the_count_call(self):
        for change, code in (({'cap_usd': .265}, 'budget_reservation_exceeded'),
                             ({'max_openai_count_calls': 0}, 'provider_count_call_limit_reached')):
            with self.subTest(change=change), guarded_counted_runtime_openai_responses(ProviderBudget({**self.policy, **change}), lambda _: True) as budget:
                with self.assertRaises(BudgetStop) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(budget.count_allowance, 0)
                self.assertEqual(len(budget.snapshot()['blocked_token_count_requests']), 1)
        self.assertEqual(self.sent, [])

    def test_full_measured_budget_and_input_token_limit_block_generation(self):
        for change, count, code in (({'cap_usd': .2665}, 100, 'budget_reservation_exceeded'),
                                    ({'max_openai_input_tokens': 99}, 100, 'unapproved_input_size')):
            self.sent.clear()
            self.count_response['input_tokens'] = count
            with self.subTest(change=change), guarded_counted_runtime_openai_responses(ProviderBudget({**self.policy, **change}), lambda _: True) as budget:
                with self.assertRaises(BudgetStop) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(budget.count_allowance, .01)
                self.assertEqual(budget.records, [])
                self.assertEqual(budget.pending, 0)
            self.assertEqual([r['stage'] for r in self.sent], ['count'])

    def test_exact_full_reservation_threshold_keeps_count_allowance_and_output_bound(self):
        required = ProviderBudget(self.policy)._cost(ROUTE['model'], 100, 5120) + .01
        for delta in (-.00000001, 0, .00000001):
            self.sent.clear()
            with self.subTest(delta=delta), guarded_counted_runtime_openai_responses(ProviderBudget({**self.policy, 'cap_usd': required + delta}), lambda _: True) as budget:
                if delta < 0:
                    with self.assertRaises(BudgetStop):
                        self.invoke()
                    self.assertEqual(budget.blocked_requests[0]['output_token_reservation'], 5120)
                else:
                    self.invoke()
                    self.assertEqual(budget.records[0]['output_token_reservation'], 5120)
                self.assertEqual(budget.count_allowance, .01)
            self.assertEqual(len(self.sent), 1 if delta < 0 else 2)

    def test_bad_count_response_stops_without_fallback_or_second_attempt(self):
        values = [dict(object='response.input_tokens', input_tokens=n) for n in (None, True, 0, -1, 100.5, '100')]
        values += [dict(object='different', input_tokens=100), {}]
        for value in values:
            self.sent.clear()
            self.count_response = value
            with self.subTest(value=value), guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True) as budget:
                with self.assertRaises(BudgetStop) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, 'provider_token_count_failed')
                with self.assertRaises(BudgetStop) as again:
                    self.invoke()
                self.assertIs(again.exception, caught.exception)
                self.assertEqual(budget.count_records[0]['status'], 'failed')
                self.assertEqual(budget.count_allowance, .01)
            self.assertEqual([r['stage'] for r in self.sent], ['count'])

    def test_http_errors_timeouts_and_redirects_never_retry(self):
        for stage in ('count', 'generation'):
            for status in (404, 429, 503, 307, 'timeout'):
                self.sent.clear()
                self.status = {} if status == 'timeout' else {stage: status}
                self.timeout_stage = stage if status == 'timeout' else None
                with self.subTest(stage=stage, status=status), guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True) as budget:
                    with self.assertRaises(BudgetStop):
                        self.invoke()
                    self.assertEqual(budget.count_allowance, .01)
                    self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()))
                    if stage == 'generation':
                        self.assertEqual(budget.charged, budget.records[0]['reserved_usd'])
                self.assertEqual(len(self.sent), 1 if stage == 'count' else 2)
                self.assertTrue(all(row['redirects'] is False for row in self.sent))

    def test_unknown_or_excess_generation_usage_retains_stop_and_correct_accounting(self):
        for usage in (None, {}, {'input_tokens': True, 'output_tokens': 30},
                      {'input_tokens': 101, 'output_tokens': 30}, {'input_tokens': 100, 'output_tokens': 5121}):
            self.sent.clear()
            self.generation_usage = usage
            with self.subTest(usage=usage), guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True) as budget:
                with self.assertRaises(BudgetStop):
                    self.invoke()
                self.assertEqual(budget.pending, 0)
                self.assertEqual(budget.count_allowance, .01)
                self.assertTrue(budget.closed)
                self.assertGreater(budget.charged, 0)
            self.assertEqual(len(self.sent), 2)

    def test_caller_mutation_and_extra_body_do_not_change_counted_generation(self):
        body = self.raw_body()
        contents = [{'role': 'user', 'content': [{'type': 'input_text', 'text': 'Extra body: 원문\r\n12.'}]}]
        schema = deepcopy(body['text'])
        original_contents, original_schema = deepcopy(contents), deepcopy(schema)

        def mutate():
            contents[0]['content'][0]['text'] = 'Changed after counting.'
            schema['format']['schema'].clear()

        self.after_count = mutate
        client = self.client()
        with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True):
            client.responses.create(**body, instructions='  Exact instructions.\n', extra_body={'input': contents, 'text': schema})
        count, generation = [row['body'] for row in self.sent]
        self.assertEqual(count['input'], original_contents)
        self.assertEqual(generation['input'], original_contents)
        self.assertEqual(count['text'], original_schema)
        self.assertEqual(generation['text'], original_schema)
        self.assertEqual(count['instructions'], generation['instructions'])

    def test_count_sdk_body_drift_is_rejected_before_http(self):
        from openai._base_client import SyncAPIClient

        def prepare(client, request):
            if request.url.path.endswith('/input_tokens'):
                value = json.loads(request.content)
                value['text']['format']['schema'].clear()
                request._content = json_bytes(value)

        with patch.object(SyncAPIClient, '_prepare_request', prepare), guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True) as budget:
            with self.assertRaises(BudgetStop) as caught:
                self.invoke()
            self.assertEqual(caught.exception.code, 'unapproved_request_body')
            self.assertEqual(budget.count_allowance, .01)
        self.assertEqual(self.sent, [])

    def test_state_tools_media_and_changed_settings_are_rejected_before_count(self):
        client = self.client()
        changes = [{'previous_response_id': 'unowned'}, {'tools': []}, {'store': True}, {'max_output_tokens': 8192},
            {'input': [{'role': 'user', 'content': [{'type': 'input_image', 'image_url': 'https://example.invalid'}]}]},
            {'input': [{'type': 'item_reference', 'id': 'unowned'}]}, {'stream': True}]
        for change in changes:
            with self.subTest(change=change), guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True):
                with self.assertRaises(BudgetStop):
                    client.responses.create(**{**self.raw_body(), **change})
        with guarded_counted_runtime_openai_responses(ProviderBudget({**self.policy, 'max_openai_request_bytes': 1}), lambda _: True):
            with self.assertRaises(BudgetStop) as caught:
                self.invoke()
            self.assertEqual(caught.exception.code, 'unapproved_input_size')
        self.assertEqual(self.sent, [])

    def test_authorizer_denial_cannot_spend_and_receives_no_mutation_authority(self):
        def fail(_):
            raise RuntimeError(PRIVATE)
        for authorize in (lambda _: False, fail):
            with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), authorize) as budget:
                with self.assertRaises(BudgetStop) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, 'unapproved_runtime_request')
                self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()))
        self.assertEqual(self.sent, [])

    def test_direct_count_async_and_alternate_transport_cannot_bypass_context(self):
        client = self.client()
        with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True):
            with self.assertRaises(BudgetStop):
                client.responses.input_tokens.count(model=ROUTE['model'], input='Unscoped count')

        async def invoke_async():
            async with AsyncOpenAI(api_key=PRIVATE, max_retries=0) as async_client:
                await async_client.responses.input_tokens.count(model=ROUTE['model'], input='Unscoped count')

        with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True):
            with self.assertRaises(BudgetStop):
                asyncio.run(invoke_async())
        for route in ({**ROUTE, 'base_url': 'https://example.invalid/v1'}, {**ROUTE, 'provider_client_retries': 1}):
            with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True):
                with self.assertRaises(BudgetStop):
                    self.invoke(route=route)
        self.assertEqual(self.sent, [])

    def test_http_hooks_are_rejected_and_scope_restores_after_exception(self):
        hooks = []
        transport = self.enterContext(httpx.Client(event_hooks={'request': [lambda r: hooks.append(r)]}))
        client = self.client(http_client=transport)
        with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True):
            with self.assertRaises(BudgetStop):
                client.responses.create(**self.raw_body())
        self.assertEqual(hooks, [])
        self.assertEqual(self.sent, [])
        # Outside the opt-in context the existing SDK call has no added count.
        self.invoke()
        self.assertEqual([r['stage'] for r in self.sent], ['generation'])

    def test_separate_generation_and_count_limits_each_stop_future_transmissions(self):
        for limit, code in (('max_openai_count_calls', 'provider_count_call_limit_reached'),
                             ('max_openai_response_calls', 'provider_call_limit_reached')):
            self.sent.clear()
            with guarded_counted_runtime_openai_responses(ProviderBudget({**self.policy, limit: 1}), lambda _: True) as budget:
                self.invoke()
                with self.assertRaises(BudgetStop) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, code)
                self.assertEqual(len(budget.records), 1)
                self.assertEqual(budget.count_allowance, .01)
            self.assertEqual(len(self.sent), 2)

    def test_multiple_models_and_embeddings_share_cost_without_changing_settings(self):
        terra = {**ROUTE, 'model': 'gpt-5.6-terra', 'reasoning_effort': 'low', 'max_output_tokens': 8192}
        policy = deepcopy(self.policy)
        policy['rates'][terra['model']] = dict(input=2.5, output=12)
        policy['request_settings_by_model'] = {ROUTE['model']: policy.pop('request_settings'), terra['model']: dict(
            model=terra['model'], max_output_tokens=8192, reasoning={'effort': 'low'}, store=False, service_tier='default')}
        with guarded_providers(policy, []) as budget, guarded_counted_runtime_openai_responses(budget, lambda _: True):
            self.client().embeddings.create(input='Anonymous query', model='text-embedding-3-large', encoding_format='float')
            for route in (terra, ROUTE):
                self.assertIsNone(self.invoke(route=route)['parsing_error'])
        self.assertEqual([r['kind'] for r in budget.records], ['openai_embedding', 'openai_response', 'openai_response'])
        self.assertEqual([r['output_token_reservation'] for r in budget.records[1:]], [8192, 5120])
        self.assertEqual(budget.count_allowance, .02)
        self.assertAlmostEqual(budget.charged, (10 * .13 + 100 * 2.5 + 30 * 12 + 100 * 12.5 + 30 * 50) / 1e6)
        self.assertIsNone(budget.active_request_kind)

    def test_concurrent_shared_client_keeps_each_count_bound_to_its_generation(self):
        client = self.client()
        with guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True) as budget, ThreadPoolExecutor(2) as pool:
            bodies = [{**self.raw_body(), 'input': text} for text in ('First source.', 'Second source.')]
            results = list(pool.map(lambda body: client.responses.create(**body), bodies))
        self.assertEqual(len(results), 2)
        self.assertEqual([r['stage'] for r in self.sent], ['count', 'generation', 'count', 'generation'])
        for row in budget.records:
            measurement = budget.count_records[row['token_count_index']]
            self.assertEqual(row['request_sha256'], measurement['generation_request_sha256'])
            self.assertEqual(row['input_token_reservation'], measurement['total_tokens'])
        self.assertEqual(budget.pending, 0)
        self.assertEqual(budget.count_allowance, .02)

    def test_google_and_openai_count_limits_remain_independent_in_one_ledger(self):
        policy = {**self.policy, 'google_input_counting': 'server_count_tokens_v1', 'max_google_count_calls': 1,
            'google_count_allowance_usd_per_call': .002, 'max_google_calls': 1, 'max_openai_count_calls': 1}
        policy['rates'] = {**policy['rates'], 'gemini-2.5-pro': dict(input=1.25, output=10)}
        with guarded_counted_runtime_openai_responses(ProviderBudget(policy), lambda _: True) as budget:
            old = budget.count_google_input(model='gemini-2.5-pro', generation_request={'contents': 'Authored'},
                count_request={'contents': 'Authored'}, output_bound=5120, invoke=lambda: 37)
            self.invoke()
            with self.assertRaises(BudgetStop) as caught:
                self.invoke()
        self.assertEqual(caught.exception.code, 'provider_count_call_limit_reached')
        self.assertNotIn('kind', old)
        self.assertNotIn('method', old)
        self.assertEqual(budget.records[0]['token_count_index'], 1)
        self.assertAlmostEqual(budget.count_allowance, .012)
        self.assertEqual(len(self.sent), 2)

    def test_compiler_feedback_retry_preserves_v2_program_execution_and_request_bodies(self):
        from src.agent.financial_calculation_execution import execute_semantic_calculation_program
        from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
        from tests.compiler_wire_test_support import wire_fixture
        from tests.narrative_address_test_support import model_program
        from tests.semantic_program_test_support import _obligation
        from tests.test_narrative_claim_grounding import claim, source

        catalog = [source('note', 'Birch serves 17 regions.')]
        owners = [_obligation('reach', 'narrative', 'Describe reach.')]
        good = model_program({'narrative_bindings': [{'obligation_id': 'reach', 'claims': [
            claim('Birch', 'Serves 17 regions.', 'note', 'Birch serves 17 regions.')]}]}, catalog)
        bad = good.model_copy(deep=True)
        bad.narrative_bindings[0].claims[0].text = 'Serves 93 regions.'
        state = _case_state({'question': 'Describe reach.', 'obligations': owners}, catalog)
        state['include_debug_bundle'] = True
        llm = self.agent._create_chat_model(ROUTE, phase='program_compilation')

        class Recorder:
            def with_structured_output(self, model):
                self.model = model
                return llm.with_structured_output(model)

        recorder = Recorder()
        agent = _CompilerOnlyAgent(recorder, usage_callback=self.agent.llm_usage_callback)

        def compile_once():
            programs = iter([bad, good])
            self.generation_wire = lambda body: recorder.model.model_validate(wire_fixture(next(programs), recorder.model)).model_dump()
            return agent._compile_semantic_calculation_program(deepcopy(state))

        old = compile_once()
        old_bodies = [r['body'] for r in self.sent]
        self.sent.clear()
        with request_diagnostic_scope(True) as diagnostics, guarded_counted_runtime_openai_responses(ProviderBudget(self.policy), lambda _: True) as budget:
            new = compile_once()
        self.assertEqual(new['semantic_program_retry_count'], 1)
        for key in ('semantic_program', 'semantic_program_validation', 'semantic_compilation_envelope', 'missing_info'):
            self.assertEqual(new[key], old[key], key)
        executed = execute_semantic_calculation_program(program=new['semantic_program'], candidate_catalog=catalog,
            obligations=state['answer_obligations'], query=state['query'], compilation_envelope=new['semantic_compilation_envelope'],
            require_compilation_envelope=True)
        self.assertEqual(executed['status'], 'ok')
        self.assertEqual([r['body'] for r in self.sent if r['stage'] == 'generation'], old_bodies)
        self.assertEqual([r['stage'] for r in self.sent], ['count', 'generation', 'count', 'generation'])
        self.assertEqual(len(budget.count_records), 2)
        self.assertEqual(len(budget.records), 2)
        attempts = [event['data']['validation_status'] for event in diagnostics.snapshot()['events'] if event['kind'] == 'compiler_attempt']
        self.assertEqual(attempts, ['invalid', 'ready'])


if __name__ == '__main__':
    unittest.main()
