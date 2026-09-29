"""Context ingest reads real SDK text blocks without storing reasoning or refusals."""

import json
import os
import socket
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import httpx
from langchain_core.messages import AIMessage

from src.agent.financial_graph import FinancialAgent
from src.config.llm_profiles import app_llm_routing_config
from src.ingestion.context_generator import ContextGenerator
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from tests.test_openai_compiler_transport import response_body


class ContextResponseTransportTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, OPENAI_API_KEY="offline-placeholder", LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false"))
        self.enterContext(patch.object(socket.socket, "connect", side_effect=AssertionError("External IO forbidden")))
        self.enterContext(patch.object(socket.socket, "connect_ex", side_effect=AssertionError("External IO forbidden")))
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm_usage_callback = GeminiUsageCallbackHandler()
        route = app_llm_routing_config("openai")["llm_routes"]["context_generation"]
        self.llm = agent._create_chat_model(route, phase="context_generation")
        self.store = Mock()
        self.store.add_documents.return_value = {"added_chunks": 1}
        self.generator = ContextGenerator(self.llm, self.store)
        self.chunk = SimpleNamespace(content="An anonymous source paragraph.", metadata={"company": "Anonymous", "year": 2023, "section": "Overview"})
        self.calls = []
        self.body = response_body({})
        self.body["model"] = "gpt-5.6-luna"
        self.body["output"][0]["content"][0]["text"] = " An anonymous source context. "

    def send(self, request, **kwargs):
        self.assertEqual(str(request.url), "https://api.openai.com/v1/responses")
        self.calls.append(json.loads(request.content))
        return httpx.Response(200, request=request, json=self.body)

    def test_single_and_batch_use_text_with_plain_responses_and_usage(self):
        with patch.object(httpx.Client, "send", side_effect=self.send):
            single = self.generator._generate_context(self.chunk.content, self.chunk.metadata)
            with patch("src.processing.financial_parser.FinancialParser.build_parents", return_value=[]):
                metrics = self.generator.contextual_ingest([self.chunk], max_workers=1, batch_size=1)
        self.assertEqual(single, "An anonymous source context.")
        self.assertIn(single, self.store.add_documents.call_args.args[0][0])
        self.assertTrue(self.store.add_documents.call_args.args[0][0].endswith(self.chunk.content))
        self.assertEqual(metrics["fallback_count"], 0)
        self.assertEqual((metrics["prompt_tokens"], metrics["output_tokens"], metrics["thoughts_tokens"]), (100, 20, 10))
        self.assertEqual(len(self.calls), 2)
        for body in self.calls:
            self.assertEqual(body["model"], "gpt-5.6-luna")
            self.assertEqual(body["reasoning"], {"effort": "none"})
            self.assertEqual(body["max_output_tokens"], 512)
            self.assertFalse(body["store"])
            self.assertNotIn("temperature", body)
            self.assertNotIn("json_schema", json.dumps(body))

    def test_incomplete_refused_and_empty_sdk_outputs_fall_back_without_retry(self):
        for kind in ("incomplete", "refusal", "empty"):
            with self.subTest(kind=kind):
                self.body = response_body({})
                self.body["output"][0]["content"][0]["text"] = "partial text"
                if kind == "incomplete":
                    self.body["status"] = "incomplete"
                    self.body["incomplete_details"] = {"reason": "max_output_tokens"}
                elif kind == "refusal":
                    self.body["output"][0]["content"] = [{"type": "refusal", "refusal": "Offline refusal"}]
                else:
                    self.body["output"][0]["content"][0]["text"] = " "
                self.calls.clear()
                with patch.object(httpx.Client, "send", side_effect=self.send):
                    contexts, metrics = self.generator._generate_contexts_for_chunks(
                        [self.chunk], workers=1, request_batch_size=1, collect_usage=True)
                self.assertEqual(contexts[0], self.generator._fallback_context(self.chunk.metadata))
                self.assertEqual(metrics["fallback_count"], 1)
                self.assertEqual(metrics["prompt_tokens"], 100)
                self.assertEqual(len(self.calls), 1)

    def test_legacy_string_and_mixed_blocks_keep_only_completed_text(self):
        responses = [
            AIMessage(content=" context "),
            AIMessage(content=[{"type": "reasoning", "text": "private"}, {"type": "text", "text": " context "}]),
            AIMessage(content=[{"type": "output_text", "text": " context "}]),
        ]
        for response in responses:
            self.assertEqual(self.generator._response_text(response), "context")
        for response in (
            AIMessage(content="partial", response_metadata={"finish_reason": "length"}),
            AIMessage(content="partial", additional_kwargs={"refusal": "refused"}),
            AIMessage(content=[{"type": "reasoning", "text": "private"}]),
            AIMessage(content=[{"type": "text", "text": "partial"}, {"type": "refusal", "refusal": "no"}]),
        ):
            self.assertEqual(self.generator._response_text(response), "")


if __name__ == "__main__":
    unittest.main()
