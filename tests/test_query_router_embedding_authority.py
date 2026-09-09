"""Canonical vectors are reusable only with complete, finite provider identity."""

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import Mock, patch

from src.routing.query_router import QueryRouter, _CANONICAL_EMBEDDING_CACHE
from src.utils.provider_errors import ProviderAdmissionError


class QueryRouterEmbeddingAuthorityTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "canonical.json"
        self.path.write_text(json.dumps([
            {"id": "qa", "queries": ["question one"]},
            {"id": "risk", "queries": ["question two"]},
        ]), encoding="utf-8")
        self.cache_patch = patch.dict(_CANONICAL_EMBEDDING_CACHE, {}, clear=True)
        self.cache_patch.start()
        self.addCleanup(self.cache_patch.stop)
        self.spec = {"provider": "synthetic", "model_name": "test-model", "dimension": 2}

    def _router(self, vectors, *, spec=None):
        embeddings = Mock()
        embeddings.embed_documents.return_value = vectors
        embeddings.embed_query.return_value = [1.0, 0.0]
        return QueryRouter(
            embeddings, Mock(), canonical_queries_path=self.path,
            embedding_spec=self.spec if spec is None else spec, enable_llm_fallback=False,
        )

    def test_bad_canonical_batch_never_enables_or_populates_success_cache(self):
        for vectors in (
            [], [[1.0, 0.0]], [[1.0, 0.0]] * 3,
            [[], []], [[0.0, 0.0], [0.0, 1.0]],
            [[float("nan"), 1.0], [0.0, 1.0]],
            [[float("inf"), 1.0], [0.0, 1.0]],
            [[1.0], [0.0, 1.0]],
        ):
            with self.subTest(vectors=vectors):
                _CANONICAL_EMBEDDING_CACHE.clear()
                router = self._router(vectors)
                self.assertFalse(router._semantic_router["enabled"])
                self.assertTrue(router._semantic_router["degraded_reason"])
                self.assertFalse(_CANONICAL_EMBEDDING_CACHE)
                corrected = self._router([[1.0, 0.0], [0.0, 1.0]])
                self.assertTrue(corrected._semantic_router["enabled"])
                self.assertEqual(corrected.embeddings.embed_documents.call_count, 1)

    def test_unknown_cache_identity_never_shares_another_adapter_vectors(self):
        for spec in ({}, {**self.spec, "provider": "unknown"},
                     {**self.spec, "model_name": ""}, {**self.spec, "dimension": None},
                     {**self.spec, "dimension": True}):
            with self.subTest(spec=spec):
                _CANONICAL_EMBEDDING_CACHE.clear()
                first = self._router([[1.0, 0.0], [0.0, 1.0]], spec=spec)
                second = self._router([[0.0, 1.0], [1.0, 0.0]], spec=spec)
                self.assertTrue(first._semantic_router["enabled"])
                self.assertTrue(second._semantic_router["enabled"])
                self.assertEqual(second.embeddings.embed_documents.call_count, 1)
                self.assertEqual(second._semantic_router["examples"][0]["embedding"], [0.0, 1.0])
                self.assertFalse(_CANONICAL_EMBEDDING_CACHE)

    def test_complete_success_cache_copies_input_and_is_invalidated_by_identity(self):
        values = [[1.0, 0.0], [0.0, 1.0]]
        self._router(values)
        values[0][0] = 99
        cached = self._router([[0.0, 1.0], [1.0, 0.0]])
        cached.embeddings.embed_documents.assert_not_called()
        self.assertEqual(cached._semantic_router["examples"][0]["embedding"], [1.0, 0.0])
        for field, value in (("provider", "other"), ("model_name", "other"), ("dimension", 3)):
            vectors = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]] if field == "dimension" else [[1.0, 0.0], [0.0, 1.0]]
            changed = self._router(vectors, spec={**self.spec, field: value})
            self.assertEqual(changed.embeddings.embed_documents.call_count, 1)
        self.path.write_text(self.path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
        changed_file = self._router([[1.0, 0.0], [0.0, 1.0]])
        self.assertEqual(changed_file.embeddings.embed_documents.call_count, 1)

    def test_terminal_admission_cannot_be_cached_or_fallback_to_another_provider(self):
        failure = ProviderAdmissionError("budget_exceeded", "synthetic stop")
        embeddings = Mock()
        embeddings.embed_documents.side_effect = failure
        with self.assertRaises(ProviderAdmissionError) as caught:
            QueryRouter(embeddings, Mock(), canonical_queries_path=self.path, embedding_spec=self.spec)
        self.assertIs(caught.exception, failure)
        self.assertFalse(_CANONICAL_EMBEDDING_CACHE)
        router = self._router([[1.0, 0.0], [0.0, 1.0]])
        router.enable_llm_fallback = True
        router.embeddings.embed_query.side_effect = failure
        with self.assertRaises(ProviderAdmissionError) as caught:
            router.route("synthetic question")
        self.assertIs(caught.exception, failure)
        router.llm.with_structured_output.assert_not_called()

    def test_invalid_query_vector_degrades_instead_of_selecting_arbitrary_intent(self):
        router = self._router([[1.0, 0.0], [0.0, 1.0]])
        for vector in ([], [1.0], [0.0, 0.0], [float("nan"), 1.0], [float("inf"), 1.0]):
            with self.subTest(vector=vector):
                router.embeddings.embed_query.return_value = vector
                result = router.semantic_route("question")
                self.assertIsNone(result["intent"])
                self.assertFalse(result["fast_path"])
                self.assertTrue(result["degraded_reason"])

    def test_finite_vector_magnitude_does_not_overflow_or_underflow_similarity(self):
        for magnitude in (1e308, 1e-300):
            with self.subTest(magnitude=magnitude):
                _CANONICAL_EMBEDDING_CACHE.clear()
                router = self._router([[magnitude, 0.0], [0.0, magnitude]])
                router.embeddings.embed_query.return_value = [magnitude, 0.0]
                result = router.semantic_route("question")
                self.assertEqual(result["intent"], "qa")
                self.assertAlmostEqual(result["confidence"], 1.0)
                self.assertTrue(result["fast_path"])

    def test_anonymous_prompt_policy_preserves_intents_and_query_at_invocation(self):
        from langchain_core.runnables import RunnableLambda
        from src.config.query_routing_prompt import QUERY_ROUTING_PROMPT
        from src.routing.types import QueryRoutingDecision

        self.assertNotIn("삼성전자", QUERY_ROUTING_PROMPT)
        self.assertNotIn("Harman", QUERY_ROUTING_PROMPT)
        for intent in ("numeric_fact", "business_overview", "risk", "comparison", "trend", "qa"):
            self.assertEqual(QUERY_ROUTING_PROMPT.count(f"A: intent={intent},"), 1)
        captured = []
        def respond(prompt):
            captured.append(prompt.to_string())
            return QueryRoutingDecision(intent="comparison", format_preference="table", confidence=0.8)
        llm = Mock()
        llm.with_structured_output.return_value = RunnableLambda(respond)
        router = QueryRouter(Mock(), llm, enable_semantic_router=False)
        query = "익명 조직의 두 수치를 비교해주세요."
        result = router.route(query)
        self.assertEqual(result.intent, "comparison")
        self.assertEqual(len(captured), 1)
        self.assertIn(query, captured[0])
        self.assertEqual(captured[0], "Human: " + QUERY_ROUTING_PROMPT.format(
            query=query, semantic_intent="unknown", semantic_confidence="0.000"))


if __name__ == "__main__":
    unittest.main()
