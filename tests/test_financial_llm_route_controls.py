"""Explicit per-phase provider limits survive the production model factory."""

from copy import deepcopy
import unittest
from unittest.mock import patch

from src.agent.financial_graph import FinancialAgent
from src.ops.benchmark_runner import _apply_llm_route_overrides, _build_agent_routing_config


class FinancialLLMRouteControlTests(unittest.TestCase):
    def setUp(self):
        self.agent = FinancialAgent.__new__(FinancialAgent)
        self.agent.llm_usage_callback = object()
        self.network = patch("socket.socket.connect", side_effect=AssertionError("no network"))
        self.network.start()
        self.addCleanup(self.network.stop)

    def test_explicit_limits_and_zero_retry_reach_google_constructor(self):
        spec = {
            "model": "gemini-2.5-pro", "api_key": "test-only-placeholder",
            "max_output_tokens": 4096, "thinking_budget": 1024,
            "provider_client_retries": 0, "include_thoughts": False,
        }
        before = deepcopy(spec)
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as constructor:
            self.agent._create_chat_model(spec, phase="program_compilation")
        forwarded = constructor.call_args.kwargs
        self.assertEqual(forwarded.get("max_tokens"), 4096)
        self.assertEqual(forwarded.get("thinking_budget"), 1024)
        self.assertEqual(forwarded.get("retries"), 0)
        self.assertIs(forwarded.get("include_thoughts"), False)
        self.assertEqual(spec, before)

    def test_omitted_limits_do_not_change_existing_provider_defaults(self):
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as constructor:
            self.agent._create_chat_model({"api_key": "test-only-placeholder"}, phase="default")
        self.assertEqual(set(constructor.call_args.kwargs), {
            "model", "temperature", "google_api_key", "callbacks",
        })

    def test_phase_model_override_retains_profile_budgets_without_mutation(self):
        profile = {"llm_routes": {
            "default": {"api_key": "test-only-placeholder"},
            "program_compilation": {
                "api_key": "test-only-placeholder", "max_output_tokens": 4096,
                "thinking_budget": 1024, "provider_client_retries": 0,
                "include_thoughts": False,
            },
        }}
        before = deepcopy(profile)
        override = _apply_llm_route_overrides(profile, ["program_compilation=google:gemini-2.5-pro"])
        self.agent.routing_config = _build_agent_routing_config(override)
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as constructor:
            self.agent._build_llm_routes()
        default_call, compiler_call = constructor.call_args_list
        self.assertEqual(default_call.kwargs["model"], "gemini-2.5-flash")
        self.assertNotIn("max_tokens", default_call.kwargs)
        self.assertEqual(compiler_call.kwargs["model"], "gemini-2.5-pro")
        self.assertEqual(compiler_call.kwargs.get("max_tokens"), 4096)
        self.assertEqual(compiler_call.kwargs.get("retries"), 0)
        self.assertEqual(profile, before)

    def test_explicit_zero_thinking_is_not_discarded(self):
        with patch("langchain_google_genai.ChatGoogleGenerativeAI") as constructor:
            self.agent._create_chat_model({
                "api_key": "test-only-placeholder", "thinking_budget": 0,
            }, phase="default")
        self.assertEqual(constructor.call_args.kwargs.get("thinking_budget"), 0)


if __name__ == "__main__":
    unittest.main()
