import unittest
from types import SimpleNamespace

from src.utils.gemini_usage import (
    GeminiUsageCallbackHandler,
    estimate_gemini_cost_usd,
    extract_gemini_usage_counts,
)


class GeminiUsageTests(unittest.TestCase):
    def test_extracts_langchain_and_gemini_usage_metadata(self) -> None:
        response = SimpleNamespace(
            usage_metadata={
                "input_tokens": 1200,
                "output_tokens": 300,
                "total_tokens": 1600,
                "thoughts_token_count": 100,
                "cached_content_token_count": 200,
            },
            response_metadata={"token_usage": {"tool_use_prompt_token_count": 50}},
        )

        usage = extract_gemini_usage_counts(response)

        self.assertEqual(usage["prompt_tokens"], 1200)
        self.assertEqual(usage["output_tokens"], 300)
        self.assertEqual(usage["thoughts_tokens"], 100)
        self.assertEqual(usage["cached_tokens"], 200)
        self.assertEqual(usage["tool_use_prompt_tokens"], 50)
        self.assertEqual(usage["total_tokens"], 1600)

    def test_estimates_cost_with_cached_and_thinking_tokens(self) -> None:
        usage = {
            "prompt_tokens": 1_200_000,
            "cached_tokens": 200_000,
            "output_tokens": 300_000,
            "thoughts_tokens": 100_000,
            "tool_use_prompt_tokens": 50_000,
        }
        pricing = {
            "input_per_million_tokens_usd": 1.0,
            "cached_input_per_million_tokens_usd": 0.25,
            "output_per_million_tokens_usd": 3.0,
            "thinking_per_million_tokens_usd": 2.0,
            "tool_input_per_million_tokens_usd": 0.5,
        }

        cost = estimate_gemini_cost_usd(usage, pricing)

        self.assertAlmostEqual(cost or 0.0, 2.175)

    def test_extracts_mapping_usage_metadata(self) -> None:
        usage = extract_gemini_usage_counts(
            {
                "usageMetadata": {
                    "promptTokenCount": 10,
                    "candidatesTokenCount": 3,
                    "thoughtsTokenCount": 2,
                    "cachedContentTokenCount": 4,
                    "totalTokenCount": 15,
                }
            }
        )

        self.assertEqual(usage["prompt_tokens"], 10)
        self.assertEqual(usage["output_tokens"], 3)
        self.assertEqual(usage["thoughts_tokens"], 2)
        self.assertEqual(usage["cached_tokens"], 4)
        self.assertEqual(usage["total_tokens"], 15)

    def test_callback_accumulates_thread_local_llm_usage(self) -> None:
        callback = GeminiUsageCallbackHandler()
        callback.reset_current_thread()
        response = SimpleNamespace(
            llm_output=None,
            generations=[
                [
                    SimpleNamespace(
                        message=SimpleNamespace(
                            usage_metadata={
                                "input_tokens": 100,
                                "output_tokens": 20,
                                "thoughts_token_count": 5,
                            }
                        )
                    )
                ]
            ],
        )

        callback.on_llm_end(response)

        snapshot = callback.snapshot_current_thread()
        self.assertEqual(snapshot["api_calls"], 1)
        self.assertEqual(snapshot["prompt_tokens"], 100)
        self.assertEqual(snapshot["output_tokens"], 20)
        self.assertEqual(snapshot["thoughts_tokens"], 5)

    def test_callback_accumulates_usage_by_phase(self) -> None:
        callback = GeminiUsageCallbackHandler()
        callback.reset_current_thread()
        response = SimpleNamespace(
            llm_output=None,
            generations=[
                [
                    SimpleNamespace(
                        message=SimpleNamespace(
                            usage_metadata={
                                "input_tokens": 100,
                                "output_tokens": 20,
                            }
                        )
                    )
                ]
            ],
        )

        callback.set_current_phase("numeric_extraction")
        callback.on_llm_end(response)
        callback.set_current_phase("validation")
        callback.on_llm_end(response)

        by_phase = callback.snapshot_current_thread_by_phase()
        self.assertEqual(by_phase["numeric_extraction"]["api_calls"], 1)
        self.assertEqual(by_phase["numeric_extraction"]["prompt_tokens"], 100)
        self.assertEqual(by_phase["validation"]["api_calls"], 1)
        self.assertEqual(by_phase["validation"]["output_tokens"], 20)
        self.assertEqual(callback.snapshot_current_thread()["api_calls"], 2)

        global_by_phase = callback.snapshot_global_by_phase()
        self.assertEqual(global_by_phase["numeric_extraction"]["total_tokens"], 120)


if __name__ == "__main__":
    unittest.main()
