from copy import deepcopy
import json
import os
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from src.ops.provider_admission import BudgetStop, ProviderBudget, google_request_parameters, guarded_providers, json_bytes
from src.utils.provider_errors import ProviderAdmissionError
from src.utils.request_diagnostics import capture_request_diagnostics, request_diagnostic_scope, diagnostic_location


POLICY = {"cap_usd": 0.20, "max_google_calls": 16, "max_openai_embedding_calls": 32,
          "google_input_overhead_tokens": 16384,
          "rates": {"gemini-2.5-flash": {"input": 0.30, "output": 2.50},
                    "gemini-2.5-pro": {"input": 1.25, "output": 10.0, "long_input": 2.50, "long_output": 15.0},
                    "text-embedding-3-large": {"input": 0.13, "output": 0.0}}}


class ProviderAdmissionTests(unittest.TestCase):
    def setUp(self):
        self.external_attempts = []
        original_connect = socket.socket.connect

        def local_only(sock, address):
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original_connect(sock, address)
            self.external_attempts.append(address)
            raise AssertionError("external connections forbidden")

        self.enterContext(patch.object(socket.socket, "connect", local_only))
        self.enterContext(patch.dict(os.environ, {
            "GOOGLE_API_KEY": "synthetic-not-a-credential", "OPENAI_API_KEY": "synthetic-not-a-credential",
            "GOOGLE_GENAI_USE_VERTEXAI": "false", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}))

    def tearDown(self):
        self.assertEqual(self.external_attempts, [])

    def params(self, **overrides):
        return {"kind": "google", "model": "gemini-2.5-pro", "request": {"contents": "test"},
                "input_bound": 1000, "output_bound": 100, **overrides}

    def dispatch(self, budget, invoke=lambda: (100, 20), **overrides):
        return budget.dispatch(**self.params(**overrides), invoke=invoke, usage=lambda response: response)

    def test_preflight_quotes_actual_request_without_consuming_or_closing(self):
        budget = ProviderBudget({**POLICY, "cap_usd": 0.001})
        before = budget.snapshot()
        quote = budget.preflight(**self.params())
        self.assertFalse(quote["allowed"])
        self.assertEqual(quote["blocked_code"], "budget_reservation_exceeded")
        self.assertEqual(budget.snapshot(), before)
        self.assertEqual(quote, budget.preflight(**self.params()))

    def test_first_budget_cause_survives_repeated_attempt_without_dispatch(self):
        budget = ProviderBudget({**POLICY, "cap_usd": 0.001})
        invoked = []
        for _ in range(2):
            with self.assertRaises(BudgetStop) as raised:
                self.dispatch(budget, lambda: invoked.append(True))
            self.assertEqual(raised.exception.code, "budget_reservation_exceeded")
        self.assertEqual(invoked, [])
        self.assertEqual(budget.records, [])
        self.assertEqual(budget.snapshot()["stop_reason"]["code"], "budget_reservation_exceeded")
        self.assertEqual(len(budget.blocked_requests), 2)

    def test_call_limit_is_distinct_from_spending_limit(self):
        budget = ProviderBudget({**POLICY, "max_google_calls": 1})
        self.dispatch(budget)
        with self.assertRaises(BudgetStop) as raised:
            self.dispatch(budget)
        self.assertEqual(raised.exception.code, "provider_call_limit_reached")
        self.assertEqual(len(budget.records), 1)

    def test_usage_settlement_and_failed_request_reservation(self):
        budget = ProviderBudget(POLICY)
        quote = budget.preflight(**self.params())
        self.dispatch(budget)
        self.assertEqual(budget.records[0]["reserved_usd"], quote["reserved_usd"])
        self.assertAlmostEqual(budget.charged, 0.000325)
        for invoke in (lambda: (0, 0), lambda: (float("nan"), 0),
                       lambda: (_ for _ in ()).throw(RuntimeError("private error payload"))):
            budget = ProviderBudget(POLICY)
            with self.assertRaises(ProviderAdmissionError):
                self.dispatch(budget, invoke)
            self.assertAlmostEqual(budget.charged, 0.00225)
            self.assertEqual(budget.pending, 0)
            self.assertTrue(budget.closed)
            self.assertNotIn("private error payload", json.dumps(budget.snapshot()))

    def test_policy_and_snapshot_are_copied(self):
        policy = deepcopy(POLICY)
        budget = ProviderBudget(policy)
        policy["cap_usd"] = 100
        self.assertEqual(budget.policy["cap_usd"], 0.2)
        self.dispatch(budget)
        snapshot = budget.snapshot()
        snapshot["requests"][0]["estimated_usd"] = 0
        self.assertNotEqual(budget.records[0]["estimated_usd"], 0)

    def test_installed_sdk_preflight_matches_dispatch_including_schema_and_thinking(self):
        from google.genai import types
        from google.genai.models import Models
        from src.agent.financial_graph import FinancialAgent
        from src.agent.financial_graph_models import SemanticCalculationProgram
        from src.utils.gemini_usage import GeminiUsageCallbackHandler

        response = types.GenerateContentResponse(
            candidates=[types.Candidate(index=0, finish_reason=types.FinishReason.STOP,
                content=types.Content(role="model", parts=[types.Part(text='{"status":"ready"}')]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=100, candidates_token_count=20, thoughts_token_count=30,
                cached_content_token_count=40, total_token_count=150))
        with patch.object(Models, "generate_content", return_value=response) as transport:
            with guarded_providers(POLICY, ["canonical query"]) as budget:
                agent = FinancialAgent.__new__(FinancialAgent)
                agent.llm_usage_callback = GeminiUsageCallbackHandler()
                llm = agent._create_chat_model({"provider": "google", "model": "gemini-2.5-pro", "temperature": 0,
                    "max_output_tokens": 4096, "thinking_budget": 1024,
                    "provider_client_retries": 0, "include_thoughts": False}, phase="program_compilation")
                result = llm.with_structured_output(SemanticCalculationProgram).invoke("synthetic question")
                self.assertEqual(result.status, "ready")
                self.assertEqual(transport.call_count, 1)
                params = google_request_parameters(POLICY, **transport.call_args.kwargs)
                quote = ProviderBudget(POLICY).preflight(**params)
                for key in ("request_sha256", "request_bytes", "reserved_usd", "input_token_reservation"):
                    self.assertEqual(quote[key], budget.records[0][key])
                self.assertEqual(budget.records[0]["output_tokens"], 50)
                self.assertNotIn("synthetic-not-a-credential", json.dumps(budget.snapshot()))
                self.assertIn("response_json_schema", params["request"]["config"].model_dump(exclude_none=True))

    def test_openai_endpoint_and_retry_controls(self):
        from openai.resources.embeddings import Embeddings

        client = SimpleNamespace(_client=SimpleNamespace(max_retries=2, base_url=SimpleNamespace(host="api.openai.com")))
        response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=3))
        with patch.object(Embeddings, "create", return_value=response) as transport:
            with guarded_providers(POLICY, ["canonical query"]) as budget:
                Embeddings.create(client, input=[[1, 2, 3]], model="text-embedding-3-large", dimensions=3072)
                self.assertEqual(client._client.max_retries, 0)
                self.assertEqual(transport.call_count, 1)
                self.assertEqual(transport.call_args.kwargs["timeout"], 60)
                self.assertEqual(budget.records[0]["input_tokens"], 3)
                client._client.base_url.host = "unexpected.invalid"
                with self.assertRaises(BudgetStop):
                    Embeddings.create(client, input="text", model="text-embedding-3-large")
                self.assertEqual(transport.call_count, 1)

    def test_compiler_preserves_sdk_budget_denial_without_retry(self):
        from google.genai.models import Models
        from src.agent.financial_graph import FinancialAgent
        from src.utils.gemini_usage import GeminiUsageCallbackHandler
        from tests.semantic_program_test_support import _candidate, _obligation

        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm_routes = {}
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        agent.llm = agent._create_chat_model({"provider": "google", "model": "gemini-2.5-pro", "temperature": 0,
            "max_output_tokens": 4096, "thinking_budget": 1024,
            "provider_client_retries": 0, "include_thoughts": False}, phase="program_compilation")
        catalog = [_candidate("quantity", 10)]
        with patch.object(Models, "generate_content") as transport:
            with guarded_providers({**POLICY, "cap_usd": 0}, []) as budget:
                with self.assertRaises(BudgetStop) as raised:
                    agent._compile_semantic_calculation_program({
                        "query": "quantity", "answer_obligations": [_obligation("amount", "direct_value", "quantity")],
                        "semantic_candidate_catalog_prebuilt": True,
                        "semantic_source_candidates": catalog, "semantic_candidate_catalog": catalog,
                    })
                self.assertIs(raised.exception, budget.stop_reason)
                self.assertEqual(raised.exception.code, "budget_reservation_exceeded")
                self.assertEqual(len(budget.blocked_requests), 1)
                self.assertEqual(budget.records, [])
                transport.assert_not_called()

    def test_only_router_canonical_document_batch_allowed(self):
        from src.utils.embedding_usage import TrackingEmbeddings

        tracked = TrackingEmbeddings(SimpleNamespace(embed_documents=lambda texts: [[1.0] for _ in texts]))
        with guarded_providers(POLICY, ["canonical query"]):
            self.assertEqual(tracked.embed_documents(["canonical query"]), [[1.0]])
            with self.assertRaises(BudgetStop):
                tracked.embed_documents(["filing document text"])

    def test_observer_copies_safe_components_without_changing_reservation_or_settlement(self):
        from google.genai import types

        config = types.GenerateContentConfig(response_json_schema={"type": "object", "properties": {"answer": {"type": "string"}}},
            system_instruction="Interpret exact sources.",
            http_options=types.HttpOptions(headers={"Authorization": "private-header-sentinel"}))
        request = {"contents": [{"role": "user", "parts": [{"text": 'Text 한글 "12".'}]}], "config": config}
        params = self.params(request=request)
        reference = ProviderBudget(POLICY)
        self.dispatch(reference, request=request)
        budget = ProviderBudget(POLICY)
        with request_diagnostic_scope(True) as recorder:
            with diagnostic_location(phase="compilation", island_id="island_a", attempt=2):
                self.dispatch(budget, request=request)
        self.assertEqual(budget.snapshot(), reference.snapshot())
        request_event, outcome_event = recorder.snapshot()["events"]
        self.assertEqual(request_event["location"], outcome_event["location"])
        observation = request_event["data"]
        quote = ProviderBudget(POLICY).preflight(**params)
        self.assertTrue(all(observation[key] == value for key, value in quote.items()))
        self.assertEqual(observation["request_bytes"], len(json_bytes(request)))
        self.assertEqual(observation["components_json"]["response_json_schema"], json_bytes(config.response_json_schema).decode("utf-8"))
        self.assertEqual(observation["component_bytes"]["contents"], len(json_bytes(request["contents"])))
        self.assertEqual(outcome_event["data"], budget.records[0])
        self.assertNotIn("private-header-sentinel", json.dumps(recorder.snapshot()))
        self.assertNotIn("Authorization", json.dumps(recorder.snapshot()))
        budget.records[0]["estimated_usd"] = 999
        request["contents"].clear()
        self.assertEqual(recorder.snapshot()["events"][1], outcome_event)

    def test_guard_events_survive_real_full_agent_retry_stop_and_preserve_first_cause(self):
        from google.genai import types
        from google.genai.models import Models
        from src.utils.gemini_usage import GeminiUsageCallbackHandler
        from tests.test_interrupted_run_diagnostics import InterruptedRunDiagnosticsTests

        agent, _, _ = InterruptedRunDiagnosticsTests().agent()
        program = agent.llm.responses[0]
        response = types.GenerateContentResponse(
            candidates=[types.Candidate(index=0, finish_reason=types.FinishReason.STOP,
                content=types.Content(role="model", parts=[types.Part(text=program.model_dump_json())]))],
            usage_metadata=types.GenerateContentResponseUsageMetadata(
                prompt_token_count=100, candidates_token_count=20, thoughts_token_count=30, total_token_count=150))
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        agent.llm = agent._create_chat_model({"provider": "google", "model": "gemini-2.5-pro", "temperature": 0,
            "max_output_tokens": 4096, "thinking_budget": 1024,
            "provider_client_retries": 0, "include_thoughts": False}, phase="program_compilation")
        with patch.object(Models, "generate_content", return_value=response) as transport:
            with guarded_providers({**POLICY, "cap_usd": 10, "max_google_calls": 1}, []) as budget:
                with capture_request_diagnostics() as captured:
                    with self.assertRaises(BudgetStop) as raised:
                        agent.run("Describe activity.", include_debug_bundle=True)
                self.assertIs(raised.exception, budget.stop_reason)
                self.assertEqual(raised.exception.code, "provider_call_limit_reached")
                transport.assert_called_once()
                events = captured[0]["events"]
                requests = [e for e in events if e["kind"] == "provider_request"]
                self.assertEqual([e["location"]["attempt"] for e in requests], [1, 2])
                self.assertTrue(all(e["location"]["phase"] == "compilation" for e in requests))
                self.assertEqual(requests[0]["location"]["island_id"], requests[1]["location"]["island_id"])
                self.assertEqual([e["data"]["allowed"] for e in requests], [True, False])
                self.assertEqual(sum(e["kind"] == "compiler_attempt" for e in events), 1)
                self.assertEqual(sum(e["kind"] == "provider_outcome" for e in events), 1)
                self.assertNotIn("synthetic-not-a-credential", json.dumps(captured))
                agent._execute_semantic_calculation_program.assert_not_called()


if __name__ == "__main__":
    unittest.main()
