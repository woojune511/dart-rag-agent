import unittest

from src.api.financial_router import _query_response_from_agent_result


def _dump_excluding_none(model):
    if hasattr(model, "model_dump"):
        return model.model_dump(exclude_none=True)
    return model.dict(exclude_none=True)


class FinancialRouterResponseTests(unittest.TestCase):
    def test_query_response_prefers_agent_answer_projection_and_stays_slim_by_default(self) -> None:
        response = _query_response_from_agent_result(
            "question",
            {
                "answer": "stale flat answer",
                "query_type": "flat",
                "companies": ["flat company"],
                "years": [1999],
                "citations": ["flat citation"],
                "structured_result": {"status": "flat"},
                "resolved_calculation_trace": {"source": "flat"},
                "agent_answer": {
                    "answer": "projection answer",
                    "query_type": "projection",
                    "companies": ["projection company"],
                    "years": [2023],
                    "citations": ["projection citation"],
                    "structured_result": {"status": "ok"},
                    "resolved_calculation_trace": {"source": "projection"},
                },
                "review_trace": {"retrieval_debug_trace": {"selected_count": 1}},
                "debug_bundle": {"llm_usage": {"total_tokens": 10}},
            },
        )

        payload = _dump_excluding_none(response)

        self.assertEqual(payload["answer"], "projection answer")
        self.assertEqual(payload["query_type"], "projection")
        self.assertEqual(payload["companies"], ["projection company"])
        self.assertEqual(payload["years"], [2023])
        self.assertEqual(payload["citations"], ["projection citation"])
        self.assertEqual(payload["structured_result"], {"status": "ok"})
        self.assertEqual(payload["resolved_calculation_trace"], {"source": "projection"})
        self.assertNotIn("review_trace", payload)
        self.assertNotIn("debug_bundle", payload)

    def test_query_response_preserves_empty_agent_answer_projection(self) -> None:
        response = _query_response_from_agent_result(
            "question",
            {
                "answer": "stale flat answer",
                "query_type": "flat",
                "companies": ["flat company"],
                "years": [1999],
                "citations": ["flat citation"],
                "structured_result": {"status": "flat"},
                "resolved_calculation_trace": {"source": "flat"},
                "agent_answer": {
                    "answer": "",
                    "query_type": "",
                    "companies": [],
                    "years": [],
                    "citations": [],
                    "structured_result": {},
                    "resolved_calculation_trace": {},
                },
            },
        )

        payload = _dump_excluding_none(response)

        self.assertEqual(payload["answer"], "")
        self.assertEqual(payload["query_type"], "unknown")
        self.assertEqual(payload["companies"], [])
        self.assertEqual(payload["years"], [])
        self.assertEqual(payload["citations"], [])
        self.assertEqual(payload["structured_result"], {})
        self.assertEqual(payload["resolved_calculation_trace"], {})

    def test_query_response_can_include_review_and_debug_bundles_explicitly(self) -> None:
        response = _query_response_from_agent_result(
            "question",
            {
                "agent_answer": {
                    "answer": "projection answer",
                    "query_type": "lookup",
                    "companies": [],
                    "years": [],
                    "citations": [],
                },
                "review_trace": {"task_artifact_trace": {"integrity_status": "ok"}},
                "debug_bundle": {"llm_usage": {"total_tokens": 10}},
            },
            include_review_trace=True,
            include_debug_bundle=True,
        )

        payload = _dump_excluding_none(response)

        self.assertEqual(payload["review_trace"]["task_artifact_trace"]["integrity_status"], "ok")
        self.assertEqual(payload["debug_bundle"]["llm_usage"]["total_tokens"], 10)

    def test_query_response_falls_back_to_flat_payload_for_legacy_agent_results(self) -> None:
        response = _query_response_from_agent_result(
            "question",
            {
                "answer": "flat answer",
                "query_type": "lookup",
                "companies": ["company"],
                "years": [2023],
                "citations": ["citation"],
                "structured_result": {"status": "ok"},
                "resolved_calculation_trace": {"source": "flat"},
            },
        )

        payload = _dump_excluding_none(response)

        self.assertEqual(payload["answer"], "flat answer")
        self.assertEqual(payload["query_type"], "lookup")
        self.assertEqual(payload["structured_result"], {"status": "ok"})
        self.assertEqual(payload["resolved_calculation_trace"], {"source": "flat"})


if __name__ == "__main__":
    unittest.main()
