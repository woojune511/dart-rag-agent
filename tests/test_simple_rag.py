"""Application boundaries: scoped evidence, one generation, honest validation."""

from copy import deepcopy
from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import httpx
from langchain_core.documents import Document

from src.agent.simple_rag import SimpleRagAgent
from src.config.llm_profiles import simple_rag_llm_routing_config
from src.config.simple_rag import RagAnswer
from src.storage.bm25_index import metadata_matches_filter
from src.storage.report_scope_filter import report_scope_filter
from src.utils.request_diagnostics import capture_request_diagnostics


def hit(*, text="Quantity: 12 units.", receipt="r1", chunk="c1", company="Issuer", year=2040):
    return (Document(page_content=text, metadata={"rcept_no": receipt, "chunk_uid": chunk,
                    "company": company, "year": year, "consolidation_scope": "separate"}), 0.7)


class Store:
    def __init__(self, hits):
        self.hits, self.calls = hits, []
        self.last_search_telemetry = {"retrieval_mode": "hybrid"}

    @property
    def embeddings(self):
        raise AssertionError("No classification embeddings")

    def search(self, query, **kwargs):
        self.calls.append((query, deepcopy(kwargs)))
        return self.hits


class LLM:
    def __init__(self, transform=lambda value: value):
        self.calls, self.transform = [], transform

    def with_structured_output(self, schema):
        assert schema is RagAnswer
        return self

    def invoke(self, messages):
        self.calls.append(deepcopy(messages))
        packet = json.loads(messages[1][1])
        result = self.transform(dict(answer="12 units", cited_source_ids=[packet["documents"][0]["source_id"]], abstained=False))
        return RagAnswer.model_validate(result)


class SimpleRagTests(unittest.TestCase):
    def agent(self, hits=None, transform=lambda value: value, **kwargs):
        self.store = Store([hit()] if hits is None else hits)
        self.llm = LLM(transform)
        with patch.object(SimpleRagAgent, "_build_llm_routes", return_value={"default": self.llm}):
            return SimpleRagAgent(self.store, **kwargs)

    def test_one_search_one_answer_and_no_compiler_claims(self):
        agent = self.agent()
        result = agent.run("Compare 2041 and 2042.\nKeep the original units.", report_scope={"year": 2040},
                           include_review_trace=True, include_debug_bundle=True)
        self.assertEqual(len(self.store.calls), 1)
        self.assertEqual(len(self.llm.calls), 1)
        self.assertEqual(self.store.calls[0][1]["where_filter"], {"year": 2040})
        packet = json.loads(self.llm.calls[0][1][1])
        self.assertEqual(packet["query"], self.store.calls[0][0])
        self.assertEqual(packet["documents"][0]["text"], "Quantity: 12 units.")
        answer = result.agent_answer
        self.assertEqual(answer["workflow"], "simple_rag")
        self.assertEqual(answer["citations"], ["r1:c1"])
        self.assertEqual(answer["cited_sources"][0]["document_id"], "r1")
        self.assertEqual(answer["validation"]["arithmetic"], "not_executed")
        self.assertEqual(answer["validation"]["semantic_support"], "not_checked")
        self.assertEqual(answer["structured_result"], {})
        self.assertEqual(answer["resolved_calculation_trace"], {})
        self.assertNotIn("tasks", result.review_trace)
        json.dumps(result.to_projection(), allow_nan=False)
        self.assertIn("request_diagnostics", result.debug_bundle)

    def test_query_years_never_become_filters_and_diagnostics_are_opt_in(self):
        result = self.agent().run("2041 and 2042")
        self.assertIsNone(self.store.calls[0][1]["where_filter"])
        self.assertIsNone(result.review_trace)
        self.assertIsNone(result.debug_bundle)

    def test_empty_or_unaddressable_search_abstains_without_model(self):
        for hits in ([], [hit(receipt="")], [hit(chunk="")], [hit(text=" ")]):
            with self.subTest(hits=hits):
                result = self.agent(hits).run("Quantity?")
                self.assertTrue(result.agent_answer["abstained"])
                self.assertEqual(result.agent_answer["citations"], [])
                self.assertEqual(self.llm.calls, [])

    def test_unknown_or_missing_citation_is_rejected_without_retry(self):
        for ids in (["foreign"], []):
            agent = self.agent(transform=lambda row: {**row, "cited_source_ids": ids})
            with self.subTest(ids=ids), self.assertRaises(ValueError):
                agent.run("Quantity?")
            self.assertEqual(len(self.llm.calls), 1)

    def test_blank_or_malformed_answer_is_not_repaired(self):
        for values in ({"answer": " "}, {"abstained": "false"}, {"extra": 1}):
            agent = self.agent(transform=lambda row: {**row, **values})
            with self.subTest(values=values), self.assertRaises(ValueError):
                agent.run("Quantity?")
            self.assertEqual(len(self.llm.calls), 1)

    def test_model_abstention_is_preserved(self):
        result = self.agent(transform=lambda row: {**row, "answer": "Missing the requested detail.",
                                                   "abstained": True, "cited_source_ids": []}).run("Detail?")
        self.assertTrue(result.agent_answer["abstained"])
        self.assertEqual(result.agent_answer["answer"], "Missing the requested detail.")

    def test_context_budget_excludes_whole_sources_and_their_citations(self):
        agent = self.agent([hit(text="x" * 2500), hit(chunk="c2")], max_context_bytes=700)
        result = agent.run("Quantity?", include_review_trace=True)
        packet = json.loads(self.llm.calls[0][1][1])
        self.assertEqual([row["chunk_id"] for row in packet["documents"]], ["c2"])
        self.assertEqual(result.review_trace["retrieval_debug_trace"]["omitted"][0]["reason"], "context_byte_limit")
        self.assertLessEqual(result.review_trace["retrieval_debug_trace"]["context_bytes"], 700)
        agent = self.agent(max_context_bytes=10)
        with self.assertRaises(ValueError):
            agent.run("Large question")
        self.assertEqual(self.store.calls, [])

    def test_scope_leak_and_conflicting_source_identity_stop_before_generation(self):
        cases = [([hit(company="Other")], {"company": "Issuer"}),
                 ([hit(), hit(text="Conflicting text")], {})]
        for hits, scope in cases:
            agent = self.agent(hits)
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                agent.run("Quantity?", report_scope=scope)
            self.assertEqual(self.llm.calls, [])

    def test_repeated_chunk_ids_across_reports_do_not_collide(self):
        result = self.agent([hit(), hit(receipt="r2")]).run("Quantity?", include_review_trace=True)
        self.assertEqual([row["source_id"] for row in result.review_trace["retrieved_sources"]], ["r1:c1", "r2:c1"])
        result.review_trace["retrieved_sources"][0]["context"]["company"] = "mutated"
        self.assertEqual(self.store.hits[0][0].metadata["company"], "Issuer")

    def test_abandoned_provider_call_preserves_exception_and_opt_in_diagnostics(self):
        agent = self.agent()
        with capture_request_diagnostics() as delivered, patch.object(self.llm, "invoke", side_effect=RuntimeError("private-error")) as invoke:
            with self.assertRaisesRegex(RuntimeError, "private-error"):
                agent.run("Quantity?", include_debug_bundle=True)
        self.assertEqual(invoke.call_count, 1)
        self.assertEqual(delivered[0]["events"][-1]["kind"], "run_interrupted")
        self.assertNotIn("private-error", json.dumps(delivered))

    def test_cached_degraded_search_remains_visible(self):
        agent = self.agent()
        self.store.last_search_telemetry = {"retrieval_mode": "cache", "cached_retrieval_mode": "bm25_fallback"}
        self.assertTrue(agent.run("Quantity?").agent_answer["retrieval_status"]["degraded"])

    def test_explicit_scope_filters_intersect_and_keep_report_tuples(self):
        where = report_scope_filter({"consolidation": "separate", "source_reports": [
            {"company": "A", "year": 2040}, {"company": "B", "year": 2041}]})
        self.assertTrue(metadata_matches_filter({"company": "A", "year": 2040, "consolidation_scope": "separate"}, where))
        self.assertFalse(metadata_matches_filter({"company": "A", "year": 2041, "consolidation_scope": "separate"}, where))
        self.assertFalse(metadata_matches_filter({"company": "B", "year": 2041, "consolidation_scope": "consolidated"}, where))
        for scope in ({"source_reports": [{}]}, {"source_companies": "A"}, {"year": True}, {"unknown": "A"}):
            with self.subTest(scope=scope), self.assertRaises(ValueError):
                report_scope_filter(scope)

    def test_compiler_only_application_profile_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "comparison-only"):
            simple_rag_llm_routing_config("openai_compiler")
        self.assertNotIn("program_compilation", simple_rag_llm_routing_config("openai")["llm_routes"])

    def test_streamlit_passes_explicit_scope_and_displays_cited_text(self):
        import streamlit as st
        from streamlit.testing.v1 import AppTest

        agent = self.agent()
        services = SimpleNamespace(agent=agent, serialized_sync_operation=nullcontext,
                                   readiness=SimpleNamespace(ready=True, reason=""))
        original_path = list(sys.path)
        st.cache_resource.clear()
        try:
            with patch("src.api.services.build_app_services", return_value=services), patch("dotenv.load_dotenv"):
                app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py")).run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.tabs), 2)
                app.text_area(key="custom_question").set_value("Quantity?")
                app.text_input(key="query_scope_company").set_value("Issuer")
                app.text_input(key="query_scope_year").set_value("2040")
                app.run()
                next(button for button in app.button if button.label == "🔍 분석 실행").click().run()
                self.assertEqual(len(app.exception), 0)
                self.assertEqual(len(app.error), 0)
                self.assertTrue(any(item.value == "12 units" for item in app.markdown))
                self.assertTrue(any(item.value == "Quantity: 12 units." for item in app.text))
            self.assertEqual(len(self.llm.calls), 1)
            self.assertEqual(self.store.calls[0][1]["where_filter"], {"$and": [{"company": "Issuer"}, {"year": 2040}]})
        finally:
            st.cache_resource.clear()
            sys.path[:] = original_path

    def test_application_execution_does_not_import_compiled_runtime_or_ops(self):
        script = '''
import sys
from unittest.mock import patch
from tests.test_simple_rag import Store, LLM, hit
from src.agent.simple_rag import SimpleRagAgent
with patch.object(SimpleRagAgent, "_build_llm_routes", return_value={"default": LLM()}):
    SimpleRagAgent(Store([hit()])).run("Quantity?", include_review_trace=True, include_debug_bundle=True)
for name in sys.modules:
    assert name not in {"src.agent.financial_graph", "src.agent.financial_graph_models", "src.agent.financial_graph_calculation"}, name
    assert not name.startswith("src.ops."), name
'''
        subprocess.run([sys.executable, "-B", "-c", script], cwd=Path(__file__).resolve().parents[1],
                       check=True, capture_output=True, text=True)

    def test_actual_sdk_and_http_contract_use_one_answer_call(self):
        from fastapi import FastAPI
        from src.api.financial_router import get_router
        from src.api.services import AppServices
        from src.storage.store_manifest import StoreReadiness, canonical_store_manifest
        from tests.test_openai_compiler_transport import response_body
        import socket

        store = Store([hit()])
        with patch.dict(os.environ, OPENAI_API_KEY="offline-only"), patch.object(socket, "create_connection", side_effect=AssertionError("External network forbidden")):
            agent = SimpleRagAgent(store, routing_config=simple_rag_llm_routing_config("openai"))
            manifest = canonical_store_manifest(collection_name="simple-rag-test")
            app = FastAPI()
            app.state.services = AppServices(manifest, StoreReadiness("compatible", True, "", manifest), agent=agent)
            app.include_router(get_router())
            calls = []

            def send(client, request, **kwargs):
                self.assertEqual(request.url.host, "api.openai.com")
                body = json.loads(request.content)
                calls.append(body)
                return httpx.Response(200, request=request, json=response_body(
                    dict(answer="12 units", cited_source_ids=["r1:c1"], abstained=False)))

            # Patch only the provider client's transport; ASGI TestClient stays real.
            provider_client = agent.llm.root_client._client
            with patch.object(provider_client, "send", side_effect=lambda request, **kwargs: send(provider_client, request, **kwargs)), TestClient(app) as client:
                response = client.post("/api/query", json={"question": "Quantity?", "include_review_trace": True, "include_debug_bundle": True})
                for scope in ({"unsupported": "value"}, {"source_reports": [{}]}):
                    rejected = client.post("/api/query", json={"question": "Quantity?", "report_scope": scope})
                    self.assertEqual(rejected.status_code, 422)
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0]["model"], "gpt-5.6-terra")
        self.assertEqual(set(calls[0]["text"]["format"]["schema"]["properties"]), {"answer", "cited_source_ids", "abstained"})
        payload = response.json()
        self.assertEqual(payload["workflow"], "simple_rag")
        self.assertEqual(payload["validation"]["arithmetic"], "not_executed")
        self.assertEqual(payload["structured_result"], {})
        self.assertEqual(payload["cited_sources"][0]["text"], "Quantity: 12 units.")
        self.assertEqual(payload["debug_bundle"]["llm_usage"]["api_calls"], 1)
