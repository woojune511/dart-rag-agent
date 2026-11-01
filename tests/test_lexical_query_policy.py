import unittest
from collections import OrderedDict
from unittest.mock import Mock, patch

from langchain_core.documents import Document

from src.storage.bm25_index import collect_bm25_results, tokenize_ko
from src.storage.lexical_query import resolve_lexical_query
from src.storage.search_merge import merge_rrf_results, search_cache_key
from src.storage.vector_store import VectorStoreManager


POLICY = "country_location_v1"


class LexicalQueryPolicyTests(unittest.TestCase):
    def test_default_preserves_original_question(self):
        query = "  어느 나라에서 활동해? 나라별 규모도 알려줘.  "
        plan = resolve_lexical_query(query)
        self.assertEqual(plan.query, query)
        self.assertIsNone(plan.policy_id)
        self.assertEqual(plan.added_terms, ())

    def test_explicit_country_forms_append_only_once(self):
        for query in ("어느 나라에서 활동해? 나라별 규모는?", "국가별로 알려줘", "나라의 위치?", "국가"):
            with self.subTest(query=query):
                plan = resolve_lexical_query(query, POLICY)
                expected = ("소재지",) if "국가" in query else ("국가", "소재지")
                self.assertEqual(plan.added_terms, expected)
                self.assertEqual(plan.query, query + " " + " ".join(expected))
                self.assertEqual(plan.matched_rules, ("country_source_fields",))

    def test_existing_terms_are_not_repeated(self):
        query = "국가별 소재지와 규모를 알려줘"
        plan = resolve_lexical_query(query, POLICY)
        self.assertEqual(plan.query, query)
        self.assertEqual(plan.added_terms, ())

    def test_unrelated_or_partial_words_do_not_trigger(self):
        for query in ("해외 매출 규모는?", "본사 소재지는?", "어디에서 돈을 벌어?",
                      "나라면 어떻게 해?", "나라장터 매출은?", "국가기관 거래액?", "국가채무 규모?"):
            with self.subTest(query=query):
                plan = resolve_lexical_query(query, POLICY)
                self.assertEqual(plan.query, query)
                self.assertEqual(plan.matched_rules, ())

    def test_unknown_policy_rejected_before_any_store_or_provider_side_effect(self):
        for invalid in ("", "country_location_v2", True, []):
            with self.subTest(policy=invalid), patch("src.storage.vector_store.os.makedirs") as mkdir, \
                    patch("src.storage.vector_store.create_embeddings") as embeddings, \
                    patch("src.storage.vector_store._chroma_cls") as backend:
                with self.assertRaisesRegex(ValueError, "Unknown experimental lexical"):
                    VectorStoreManager(experimental_lexical_policy_id=invalid)
                mkdir.assert_not_called()
                embeddings.assert_not_called()
                backend.assert_not_called()

    def manager(self):
        manager = VectorStoreManager.__new__(VectorStoreManager)
        manager.experimental_lexical_policy_id = None
        manager.vector_store = Mock()
        manager.vector_store.similarity_search_with_score.return_value = [
            (Document(page_content="dense source", metadata={"chunk_uid": "dense", "rcept_no": "A"}), 0.2)]
        manager.force_bm25_only = False
        manager.allow_query_embedding_fallback = False
        manager._structure_graph = {"nodes": {}}
        manager.search_cache_size = 20
        manager._search_cache = OrderedDict()
        manager._search_cache_telemetry = {}
        manager.bm25_docs = ["out of scope", "lexical source"]
        manager.bm25_metadatas = [{"chunk_uid": "other", "rcept_no": "B"},
                                 {"chunk_uid": "lexical", "rcept_no": "A"}]
        manager.bm25 = Mock()
        manager.bm25.get_scores.return_value = [100.0, 2.0]
        return manager

    def test_only_bm25_receives_hints_and_scope_and_rrf_remain_fixed(self):
        manager = self.manager()
        manager.experimental_lexical_policy_id = POLICY
        query, scope = "어느 나라에서 활동해?", {"rcept_no": "A"}
        with patch("src.storage.vector_store.collect_bm25_results", wraps=collect_bm25_results) as lexical, \
                patch("src.storage.search_merge.merge_rrf_results", wraps=merge_rrf_results) as merge:
            result = manager.search(query, k=8, k_rrf=60, where_filter=scope)
        manager.vector_store.similarity_search_with_score.assert_called_once_with(query, k=16, filter=scope)
        self.assertEqual(lexical.call_args.args[3], query + " 국가 소재지")
        self.assertEqual(lexical.call_args.kwargs, {"k": 8, "where_filter": scope})
        manager.bm25.get_scores.assert_called_once_with(tokenize_ko(query + " 국가 소재지"))
        self.assertEqual(merge.call_args.kwargs, {"k": 8, "k_rrf": 60})
        self.assertEqual([d.metadata["chunk_uid"] for d, _ in result], ["dense", "lexical"])
        self.assertEqual(manager.last_search_telemetry["query"], query)
        self.assertEqual(manager.last_search_telemetry["bm25_query"], query + " 국가 소재지")

    def test_cache_isolates_policy_and_preserves_trace_on_hit(self):
        manager = self.manager()
        query, scope = "어느 나라에서 활동해?", {"rcept_no": "A"}
        plain_key = manager._search_cache_key(query, k=8, k_rrf=60, where_filter=scope)
        self.assertEqual(plain_key, search_cache_key(query, k=8, k_rrf=60, where_filter=scope))
        plain = manager.search(query, k=8, where_filter=scope)
        manager.experimental_lexical_policy_id = POLICY
        manager.search(query, k=8, where_filter=scope)
        self.assertFalse(manager.last_search_telemetry["cache_hit"])
        trace = manager.last_search_telemetry["lexical_query_policy"]
        manager.search(query, k=8, where_filter=scope)
        self.assertTrue(manager.last_search_telemetry["cache_hit"])
        self.assertEqual(manager.last_search_telemetry["lexical_query_policy"], trace)
        manager.experimental_lexical_policy_id = None
        self.assertEqual(manager.search(query, k=8, where_filter=scope), plain)
        self.assertTrue(manager.last_search_telemetry["cache_hit"])
        self.assertIsNone(manager.last_search_telemetry["lexical_query_policy"]["id"])
        self.assertEqual(manager.vector_store.similarity_search_with_score.call_count, 2)

    def test_same_id_with_changed_effective_query_cannot_reuse_cached_result(self):
        manager = self.manager()
        manager.experimental_lexical_policy_id = POLICY
        before = manager._search_cache_key("나라별 규모", k=8, k_rrf=60, where_filter=None)
        with patch("src.storage.vector_store.resolve_lexical_query",
                   return_value=resolve_lexical_query("나라별 다른 규모", POLICY)):
            after = manager._search_cache_key("나라별 규모", k=8, k_rrf=60, where_filter=None)
        self.assertNotEqual(before, after)


if __name__ == "__main__":
    unittest.main()
