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

    def test_openai_controls_and_nullable_temperature_reach_constructor(self):
        spec = {"provider": "openai", "model": "test-reasoning-model", "api_key": "test-only-placeholder",
                "temperature": None, "max_output_tokens": 5120, "provider_client_retries": 0,
                "reasoning_effort": "medium", "use_responses_api": True,
                "store": False, "service_tier": "default", "timeout_seconds": 90}
        before = deepcopy(spec)
        with patch("src.utils.openai_structured.StrictOpenAIChatModel") as constructor:
            self.agent._create_chat_model(spec, phase="program_compilation")
        args = constructor.call_args.kwargs
        self.assertIsNone(args["temperature"])
        self.assertEqual(args["max_completion_tokens"], 5120)
        self.assertEqual(args["max_retries"], 0)
        self.assertEqual(args["callbacks"], [self.agent.llm_usage_callback])
        self.assertEqual(args["reasoning_effort"], "medium")
        self.assertEqual(args["timeout"], 90)
        self.assertIs(args["store"], False)
        self.assertIs(args["use_responses_api"], True)
        self.assertEqual(spec, before)

    def test_google_options_cannot_leak_into_an_openai_override(self):
        for extra in ({"thinking_budget": 1024}, {"include_thoughts": False}):
            with self.subTest(extra=extra), self.assertRaisesRegex(ValueError, "Google generation options"):
                self.agent._create_chat_model({"provider": "openai", "model": "test", **extra}, phase="program_compilation")

    def test_openai_route_cannot_inherit_google_model_default(self):
        with self.assertRaisesRegex(ValueError, "explicit model"):
            self.agent._create_chat_model({"provider": "openai"}, phase="program_compilation")


if __name__ == "__main__":
    unittest.main()
