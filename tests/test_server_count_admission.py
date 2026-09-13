"""Real SDK serialization with a network-blocked transport, never provider calls."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
import asyncio
import hashlib
import json
import os
import socket
import threading
import unittest
from unittest.mock import patch

from google import genai
from google.genai import types
import httpx

from src.ops.provider_admission import BudgetStop, ProviderBudget, google_request_parameters, guarded_providers, json_bytes
from src.utils.request_diagnostics import request_diagnostic_scope
from tests.test_provider_admission import POLICY


COUNT_POLICY = {**POLICY, "google_input_counting": "server_count_tokens_v1",
                "max_google_count_calls": 4, "google_count_allowance_usd_per_call": 0.002}
PRIVATE = "private-credential-must-not-be-exported"


class ServerCountAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.external_attempts = []
        for method in ("connect", "connect_ex"):
            original = getattr(socket.socket, method)
            def forbidden(sock, address, original=original):
                if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                    return original(sock, address)
                self.external_attempts.append(address)
                raise AssertionError("external connections forbidden")
            self.enterContext(patch.object(socket.socket, method, forbidden))
        self.enterContext(patch.dict(os.environ, {
            "GOOGLE_API_KEY": PRIVATE, "GOOGLE_GENAI_USE_VERTEXAI": "false",
            "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}))
        self.requests = []

    def tearDown(self):
        self.assertEqual(self.external_attempts, [])

    def client(self, handler):
        def capture(request):
            self.requests.append((str(request.url), json.loads(request.content)))
            return handler(request)
        return self.enterContext(genai.Client(api_key=PRIVATE, vertexai=False,
            http_options=types.HttpOptions(api_version="v1beta", client_args={
                "transport": httpx.MockTransport(capture), "trust_env": False})))

    def config(self, **overrides):
        return types.GenerateContentConfig(max_output_tokens=4096,
            thinking_config=types.ThinkingConfig(thinking_budget=1024, include_thoughts=False),
            system_instruction="Preserve the exact source.",
            response_mime_type="application/json",
            response_json_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            http_options=types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1),
                                          headers={"Authorization": PRIVATE}), **overrides)

    def response(self, input_tokens=37, output_tokens=19, thoughts=23):
        return {"candidates": [{"index": 0, "finishReason": "STOP", "content": {
            "role": "model", "parts": [{"text": '{"answer":"ok"}'}]}}],
            "usageMetadata": {"promptTokenCount": input_tokens, "candidatesTokenCount": output_tokens,
                              "thoughtsTokenCount": thoughts, "totalTokenCount": input_tokens + output_tokens + thoughts}}

    def handler(self, request):
        return httpx.Response(200, json=({"totalTokens": 37} if request.url.path.endswith(":countTokens")
                                        else self.response()))

    def generate(self, client, config=None, contents=None, model="gemini-2.5-pro"):
        return client.models.generate_content(model=model,
            contents=contents if contents is not None else 'Synthetic 원문 (12), "13".', config=config or self.config())

    def test_final_sdk_body_is_counted_once_and_generation_uses_server_count(self):
        client = self.client(self.handler)
        config = self.config()
        config.http_options.extra_body = {"systemInstruction": {"parts": [{"text": "Final system override."}]}}
        original = config.model_dump()
        with request_diagnostic_scope(True) as recorder, guarded_providers(COUNT_POLICY, []) as budget:
            result = self.generate(client, config)
        self.assertEqual(result.text, '{"answer":"ok"}')
        self.assertEqual(config.model_dump(), original)
        self.assertEqual([url.rsplit(":", 1)[1] for url, _ in self.requests], ["countTokens", "generateContent"])
        counted = deepcopy(self.requests[0][1]["generateContentRequest"])
        self.assertEqual(counted.pop("model"), "models/gemini-2.5-pro")
        generated = self.requests[1][1]
        self.assertEqual(counted, generated)
        self.assertIn("responseJsonSchema", generated["generationConfig"])
        self.assertEqual(generated["systemInstruction"]["parts"][0]["text"], "Final system override.")
        record = budget.snapshot()["requests"][0]
        self.assertEqual(record["input_token_reservation"], 37)
        self.assertEqual(record["output_token_reservation"], 5120)
        self.assertEqual(record["output_tokens"], 42)
        self.assertEqual(record["request_sha256"], hashlib.sha256(json_bytes(generated)).hexdigest())
        self.assertEqual(record["input_reservation_method"], "server_count_tokens_v1")
        counts = budget.snapshot()["token_count_requests"]
        self.assertEqual(counts[0]["generation_request_sha256"], record["request_sha256"])
        self.assertEqual(counts[0]["total_tokens"], 37)
        self.assertEqual(budget.snapshot()["token_count_allowance_usd"], 0.002)
        self.assertAlmostEqual(budget.charged, (37 * 1.25 + 42 * 10) / 1_000_000)
        self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()) + json.dumps(recorder.snapshot()))

    def test_known_denial_does_not_spend_a_count_call(self):
        for overrides, code in (({"cap_usd": 0}, "budget_reservation_exceeded"),
                                ({"max_google_calls": 0}, "provider_call_limit_reached"),
                                ({"max_google_count_calls": 0}, "provider_count_call_limit_reached")):
            with self.subTest(overrides=overrides):
                client = self.client(self.handler)
                with guarded_providers({**COUNT_POLICY, **overrides}, []) as budget:
                    with self.assertRaises(BudgetStop) as raised:
                        self.generate(client)
                    self.assertEqual(raised.exception.code, code)
                    self.assertIs(raised.exception, budget.stop_reason)
        self.assertEqual(self.requests, [])

    def test_count_failure_never_falls_back_or_retries_and_keeps_first_cause(self):
        for response in (httpx.Response(429, json={"error": {"code": 429, "message": PRIVATE}}),
                         httpx.Response(400, json={"error": {"code": 400, "message": PRIVATE}}),
                         httpx.Response(200, json={}), httpx.Response(200, json={"totalTokens": 0}),
                         httpx.Response(200, json={"totalTokens": True}),
                         httpx.Response(200, json={"totalTokens": 2.5}),
                         httpx.Response(200, content=b"invalid json")):
            with self.subTest(response=response):
                self.requests.clear()
                client = self.client(lambda _: response)
                with guarded_providers(COUNT_POLICY, []) as budget:
                    for _ in range(2):
                        with self.assertRaises(BudgetStop) as raised:
                            self.generate(client)
                        self.assertIs(raised.exception, budget.stop_reason)
                        self.assertEqual(raised.exception.code, "provider_token_count_failed")
                self.assertEqual(len(self.requests), 1)
                self.assertEqual(budget.records, [])
                self.assertEqual(budget.snapshot()["token_count_allowance_usd"], 0.002)
                self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()))

    def test_count_allowance_and_measured_input_both_participate_in_cap(self):
        client = self.client(self.handler)
        # Output alone fits; measured input plus the separately held count allowance does not.
        cap = 5120 * 10 / 1_000_000 + 0.002 + 0.00001
        with guarded_providers({**COUNT_POLICY, "cap_usd": cap}, []) as budget:
            with self.assertRaises(BudgetStop) as raised:
                self.generate(client)
            self.assertEqual(raised.exception.code, "budget_reservation_exceeded")
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(budget.records, [])
        self.assertEqual(budget.charged, 0)
        self.assertEqual(budget.snapshot()["token_count_requests"][0]["status"], "completed")

    def test_observed_usage_above_count_stops_without_another_transmission(self):
        client = self.client(lambda request: httpx.Response(200, json=(
            {"totalTokens": 37} if request.url.path.endswith(":countTokens") else self.response(input_tokens=38))))
        with guarded_providers(COUNT_POLICY, []) as budget:
            for _ in range(2):
                with self.assertRaises(BudgetStop) as raised:
                    self.generate(client)
                self.assertEqual(raised.exception.code, "provider_usage_exceeded_reservation")
                self.assertIs(raised.exception, budget.stop_reason)
        self.assertEqual(len(self.requests), 2)
        self.assertTrue(budget.records[0]["reservation_exceeded"])
        self.assertEqual(budget.records[0]["input_tokens"], 38)

    def test_opt_in_requires_count_authority_and_cannot_masquerade_as_no_call_quote(self):
        for overrides in ({"google_input_counting": "guess"}, {"max_google_count_calls": None},
                          {"max_google_count_calls": True}, {"google_count_allowance_usd_per_call": None},
                          {"google_count_allowance_usd_per_call": 0},
                          {"google_count_allowance_usd_per_call": float("nan")}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                ProviderBudget({**COUNT_POLICY, **overrides})
        with self.assertRaises(ValueError):
            google_request_parameters(COUNT_POLICY, model="gemini-2.5-pro", contents="text", config=self.config())
        client = self.client(self.handler)
        with guarded_providers(POLICY, []) as budget:
            self.generate(client)
        self.assertEqual(len(self.requests), 1)
        self.assertTrue(self.requests[0][0].endswith(":generateContent"))
        self.assertNotIn("token_count_requests", budget.snapshot())
        self.assertGreater(budget.records[0]["input_token_reservation"], 16384)

    def test_real_langchain_schema_traverses_same_counted_http_boundary(self):
        from src.agent.financial_graph import FinancialAgent
        from src.agent.financial_graph_models import SemanticCalculationProgram
        from src.utils.gemini_usage import GeminiUsageCallbackHandler

        def handle(request, **kwargs):
            self.requests.append((str(request.url), json.loads(request.content)))
            response = self.response()
            response["candidates"][0]["content"]["parts"][0]["text"] = '{"status":"ready"}'
            return httpx.Response(200, request=request,
                                  json={"totalTokens": 37} if request.url.path.endswith(":countTokens") else response)

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        llm = agent._create_chat_model({"provider": "google", "model": "gemini-2.5-pro", "temperature": 0,
            "max_output_tokens": 4096, "thinking_budget": 1024,
            "provider_client_retries": 0, "include_thoughts": False}, phase="program_compilation")
        # Patch only HTTP I/O: LangChain, genai conversion and both request bodies are real.
        with patch.object(httpx.Client, "send", side_effect=handle), guarded_providers(COUNT_POLICY, []) as budget:
            result = llm.with_structured_output(SemanticCalculationProgram).invoke("Synthetic question.")
        self.assertEqual(result.status, "ready")
        self.assertEqual(len(self.requests), 2)
        self.assertEqual(self.requests[0][1]["generateContentRequest"]["generationConfig"]["responseJsonSchema"],
                         self.requests[1][1]["generationConfig"]["responseJsonSchema"])
        self.assertEqual(budget.records[0]["input_token_reservation"], 37)

    def test_timeout_and_generation_failure_are_single_attempts(self):
        for stage in ("countTokens", "generateContent"):
            with self.subTest(stage=stage):
                self.requests.clear()
                def handle(request):
                    if request.url.path.endswith(":" + stage):
                        raise httpx.ReadTimeout(PRIVATE, request=request)
                    return self.handler(request)
                client = self.client(handle)
                with guarded_providers(COUNT_POLICY, []) as budget:
                    with self.assertRaises(BudgetStop) as raised:
                        self.generate(client)
                    self.assertIs(raised.exception, budget.stop_reason)
                self.assertEqual(len(self.requests), 1 if stage == "countTokens" else 2)
                self.assertEqual(budget.snapshot()["token_count_allowance_usd"], 0.002)
                if stage == "generateContent":
                    self.assertEqual(budget.charged, budget.records[0]["reserved_usd"])
                    self.assertTrue(budget.records[0]["usage_unknown"])
                self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()))

    def test_generation_bad_usage_or_excess_output_never_returns_an_unaccounted_answer(self):
        for usage in ({}, {"promptTokenCount": True}, {"promptTokenCount": 37, "thoughtsTokenCount": -1},
                      {"promptTokenCount": 37, "candidatesTokenCount": 4096, "thoughtsTokenCount": 1025}):
            with self.subTest(usage=usage):
                self.requests.clear()
                response = self.response()
                response["usageMetadata"] = usage
                client = self.client(lambda request: httpx.Response(200, json=(
                    {"totalTokens": 37} if request.url.path.endswith(":countTokens") else response)))
                with guarded_providers(COUNT_POLICY, []) as budget:
                    with self.assertRaises(BudgetStop):
                        self.generate(client)
                    self.assertTrue(budget.closed)
                self.assertEqual(len(self.requests), 2)
                self.assertEqual(budget.pending, 0)

    def test_count_limit_and_high_context_rate_are_enforced_separately(self):
        client = self.client(self.handler)
        with guarded_providers({**COUNT_POLICY, "max_google_count_calls": 1}, []) as budget:
            self.generate(client)
            with self.assertRaises(BudgetStop) as raised:
                self.generate(client)
            self.assertEqual(raised.exception.code, "provider_count_call_limit_reached")
            self.assertEqual(len(budget.records), 1)
        self.assertEqual(len(self.requests), 2)
        self.requests.clear()
        client = self.client(lambda _: httpx.Response(200, json={"totalTokens": 200001}))
        with guarded_providers({**COUNT_POLICY, "cap_usd": 0.4}, []) as budget:
            with self.assertRaises(BudgetStop):
                self.generate(client)
        self.assertEqual(len(self.requests), 1)
        self.assertEqual(budget.blocked_requests[0]["input_token_reservation"], 200001)
        self.assertAlmostEqual(budget.blocked_requests[0]["reserved_usd"], (200001 * 2.5 + 5120 * 15) / 1_000_000)

    def test_final_body_overrides_cannot_widen_fixed_generation_budget(self):
        for extra in ({"generationConfig": {"maxOutputTokens": 8192}},
                      {"generationConfig": {"candidateCount": 2}},
                      {"generationConfig": {"thinkingConfig": {"thinkingBudget": 4096}}},
                      {"tools": [{"googleSearch": {}}]}, {"cachedContent": "unapproved-cache"},
                      {"generationConfig": {"responseModalities": ["IMAGE"]}}):
            with self.subTest(extra=extra):
                config = self.config()
                config.http_options.extra_body = extra
                client = self.client(self.handler)
                with guarded_providers(COUNT_POLICY, []) as budget:
                    with self.assertRaises(BudgetStop) as raised:
                        self.generate(client, config)
                    self.assertEqual(raised.exception.code, "unapproved_request_config")
        self.assertEqual(self.requests, [])

    def test_unscoped_count_or_different_endpoint_cannot_escape_admission(self):
        client = self.client(self.handler)
        with guarded_providers(COUNT_POLICY, []) as budget:
            with self.assertRaises(BudgetStop) as raised:
                client.models.count_tokens(model="gemini-2.5-pro", contents="unplanned count")
            self.assertEqual(raised.exception.code, "unapproved_transport")
        config = self.config()
        config.http_options.base_url = "https://unapproved.invalid"
        with guarded_providers(COUNT_POLICY, []) as budget:
            with self.assertRaises(BudgetStop) as raised:
                self.generate(client, config)
            self.assertEqual(raised.exception.code, "unapproved_transport")
        self.assertEqual(self.requests, [])

    def test_async_count_and_redirect_cannot_add_unapproved_transmissions(self):
        client = self.client(self.handler)
        with guarded_providers(COUNT_POLICY, []) as budget:
            with self.assertRaises(BudgetStop) as raised:
                asyncio.run(client.aio.models.count_tokens(model="gemini-2.5-pro", contents="unplanned count"))
            self.assertEqual(raised.exception.code, "unapproved_transport")
        self.assertEqual(self.requests, [])
        for stage in ("countTokens", "generateContent"):
            with self.subTest(stage=stage):
                self.requests.clear()
                client = self.client(lambda request: httpx.Response(307, headers={"location": "https://unapproved.invalid"})
                                     if request.url.path.endswith(":" + stage) else self.handler(request))
                with guarded_providers(COUNT_POLICY, []) as budget:
                    with self.assertRaises(BudgetStop):
                        self.generate(client)
                self.assertEqual(len(self.requests), 1 if stage == "countTokens" else 2)
                self.assertTrue(all("unapproved.invalid" not in url for url, _ in self.requests))

    def test_caller_mutation_after_count_cannot_change_generation(self):
        contents = [{"role": "user", "parts": [{"text": "Original text."}]}]
        config = self.config()
        def handle(request):
            if request.url.path.endswith(":countTokens"):
                contents[0]["parts"][0]["text"] = "Changed after count."
                config.system_instruction = "Changed system."
                config.response_json_schema.clear()
            return self.handler(request)
        client = self.client(handle)
        with guarded_providers(COUNT_POLICY, []):
            self.generate(client, config, contents)
        counted = self.requests[0][1]["generateContentRequest"]
        generated = self.requests[1][1]
        self.assertEqual(generated, {key: value for key, value in counted.items() if key != "model"})
        self.assertEqual(generated["contents"][0]["parts"][0]["text"], "Original text.")

    def test_shared_client_concurrent_requests_keep_count_identity_and_budget(self):
        barrier = threading.Barrier(2)
        counts = {"First request.": 41, "Second request.": 73}
        def handle(request):
            body = json.loads(request.content)
            is_count = request.url.path.endswith(":countTokens")
            generation = body["generateContentRequest"] if is_count else body
            count = counts[generation["contents"][0]["parts"][0]["text"]]
            if is_count:
                barrier.wait(timeout=5)
            return httpx.Response(200, json={"totalTokens": count} if is_count else self.response(input_tokens=count))
        client = self.client(handle)
        with guarded_providers({**COUNT_POLICY, "cap_usd": 1}, []) as budget, ThreadPoolExecutor(2) as pool:
            futures = [pool.submit(self.generate, client, contents=text) for text in counts]
            self.assertEqual([future.result().text for future in futures], ['{"answer":"ok"}'] * 2)
        snapshot = budget.snapshot()
        self.assertEqual(len(self.requests), 4)
        self.assertEqual(len(snapshot["requests"]), 2)
        for row in snapshot["requests"]:
            measurement = snapshot["token_count_requests"][row["token_count_index"]]
            self.assertEqual(measurement["total_tokens"], row["input_token_reservation"])
            self.assertEqual(measurement["generation_request_sha256"], row["request_sha256"])
        self.assertEqual(budget.pending, 0)
        self.assertAlmostEqual(snapshot["token_count_allowance_usd"], 0.004)


if __name__ == "__main__":
    unittest.main()
