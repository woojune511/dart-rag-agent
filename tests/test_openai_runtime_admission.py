"""Mixed-provider accounting for fresh runtime requests, with mocked HTTP only."""
from copy import deepcopy
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from openai import OpenAI

from src.agent.financial_graph import FinancialAgent
from src.ops.openai_provider_admission import guarded_runtime_openai_responses
from src.ops.provider_admission import BudgetStop, ProviderBudget, guarded_providers
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.test_openai_compiler_transport import Payload, POLICY, ROUTE, response_body


class OpenAIRuntimeAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, OPENAI_API_KEY="offline-not-a-key",
            GOOGLE_API_KEY="offline-not-a-key", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false"))
        self.enterContext(patch.object(socket.socket, "connect", side_effect=AssertionError("external network forbidden")))
        self.enterContext(patch.object(socket.socket, "connect_ex", side_effect=AssertionError("external network forbidden")))
        self.agent = FinancialAgent.__new__(FinancialAgent)
        self.agent.llm_usage_callback = GeminiUsageCallbackHandler()
        self.policy = {**deepcopy(POLICY), "cap_usd": 3.0, "max_google_calls": 0,
            "max_openai_embedding_calls": 1, "max_openai_response_calls": 2,
            "openai_response_binding": "runtime_generated_v1"}
        self.policy["rates"]["text-embedding-3-large"] = {"input": 0.13, "output": 0}
        self.requests, self.http_status, self.response_usage = [], 200, True
        self.enterContext(patch.object(httpx.Client, "send", self.send))

    def send(self, client_request, **kwargs):
        body = json.loads(client_request.content)
        self.requests.append((str(client_request.url), body))
        if client_request.url.path == "/v1/embeddings":
            response = {"object": "list", "data": [{"object": "embedding", "index": 0, "embedding": [0.0, 1.0]}],
                "model": "text-embedding-3-large", "usage": {"prompt_tokens": 10, "total_tokens": 10}}
        elif self.http_status != 200:
            response = {"error": {"message": "PRIVATE_PROVIDER_DETAIL", "type": "server_error", "code": "unavailable"}}
        else:
            response = response_body({"value": 2, "comment": None, "flags": []}, usage=self.response_usage)
        return httpx.Response(self.http_status, json=response, request=client_request)

    def invoke(self, text="Anonymous initial source", route=None):
        llm = self.agent._create_chat_model(route or ROUTE, phase="program_compilation")
        return llm.with_structured_output(Payload, include_raw=True).invoke(text)

    def embed(self):
        return OpenAI(api_key="offline-not-a-key", max_retries=0).embeddings.create(
            input="anonymous query", model="text-embedding-3-large", encoding_format="float")

    def test_explicit_mode_and_authorizer_required(self):
        for policy, callback in ((POLICY, lambda _: True), (self.policy, None)):
            with self.assertRaises(ValueError), guarded_runtime_openai_responses(ProviderBudget(policy), callback):
                self.fail("entry must reject missing admission")
        self.assertEqual(self.requests, [])

    def test_embedding_and_new_response_bodies_share_one_budget(self):
        seen = []
        def authorize(body):
            seen.append(deepcopy(body))
            body["input"] = []  # Inspection receives a copy, never request mutation.
            return True
        with guarded_providers(self.policy, []) as budget, guarded_runtime_openai_responses(budget, authorize):
            self.embed()
            for prompt in ("Anonymous initial source", "Another fresh source and plan"):
                self.assertIsNone(self.invoke(prompt)["parsing_error"])
            self.assertIsNone(budget.active_request_kind)
        self.assertEqual([r["kind"] for r in budget.records], ["openai_embedding", "openai_response", "openai_response"])
        self.assertEqual([b for _, b in self.requests[1:]], seen)
        self.assertNotEqual(seen[0]["input"], seen[1]["input"])
        self.assertAlmostEqual(budget.charged, (10 * 0.13 + 2 * (100 * 12.5 + 30 * 50)) / 1e6)
        self.assertEqual(budget.pending, 0)

    def test_embedding_cannot_bypass_enclosing_admission(self):
        budget = ProviderBudget(self.policy)
        with guarded_runtime_openai_responses(budget, lambda _: True), self.assertRaises(BudgetStop):
            self.embed()
        self.assertEqual(self.requests, [])
        self.assertEqual(budget.records, [])

    def test_outside_runtime_or_authorizer_error_fails_closed(self):
        def error(_):
            raise RuntimeError("PRIVATE_AUTHORIZER_DETAIL")
        for callback in (lambda _: False, error):
            with self.subTest(callback=callback):
                budget = ProviderBudget(self.policy)
                with guarded_runtime_openai_responses(budget, callback), self.assertRaises(BudgetStop) as caught:
                    self.invoke()
                self.assertEqual(caught.exception.code, "unapproved_runtime_request")
                self.assertNotIn("PRIVATE", json.dumps(budget.snapshot()))
                self.assertEqual(budget.records, [])
        self.assertEqual(self.requests, [])

    def test_shared_cap_blocks_generation_after_embedding(self):
        policy = {**self.policy, "cap_usd": 0.25}
        with guarded_providers(policy, []) as budget, guarded_runtime_openai_responses(budget, lambda _: True):
            self.embed()
            with self.assertRaises(BudgetStop) as caught:
                self.invoke()
        self.assertEqual(caught.exception.code, "budget_reservation_exceeded")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(len(budget.records), 1)

    def test_provider_failure_stops_subsequent_embedding_without_retry(self):
        self.http_status = 503
        with guarded_providers(self.policy, []) as budget, guarded_runtime_openai_responses(budget, lambda _: True):
            with self.assertRaises(BudgetStop):
                self.invoke()
            with self.assertRaises(BudgetStop):
                self.embed()
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(budget.records[0]["usage_unknown"])
        self.assertGreater(budget.charged, 0)
        self.assertIsNone(budget.active_request_kind)
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL", json.dumps(budget.snapshot()))

    def test_settings_endpoint_and_sdk_retry_rejected_before_transport(self):
        for change in ({"store": True}, {"base_url": "https://example.invalid/v1"}, {"provider_client_retries": 1}):
            with self.subTest(change=change):
                budget = ProviderBudget(self.policy)
                with guarded_runtime_openai_responses(budget, lambda _: True), self.assertRaises(BudgetStop):
                    self.invoke(route={**ROUTE, **change})
                self.assertEqual(budget.records, [])
        self.assertEqual(self.requests, [])

    def test_response_limit_and_missing_usage_fail_closed(self):
        policy = {**self.policy, "max_openai_response_calls": 1}
        with guarded_runtime_openai_responses(ProviderBudget(policy), lambda _: True):
            self.invoke()
            with self.assertRaises(BudgetStop) as caught:
                self.invoke()
        self.assertEqual(caught.exception.code, "provider_call_limit_reached")
        self.assertEqual(len(self.requests), 1)
        self.response_usage = False
        budget = ProviderBudget(self.policy)
        with guarded_runtime_openai_responses(budget, lambda _: True), self.assertRaises(BudgetStop):
            self.invoke()
        self.assertTrue(budget.records[0]["usage_unknown"])
        self.assertEqual(budget.pending, 0)


if __name__ == "__main__":
    unittest.main()
