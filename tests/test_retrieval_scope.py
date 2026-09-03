import unittest
from unittest.mock import patch

from langchain_core.documents import Document

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_retrieval_budget import (
    apply_query_budget,
    cross_trace_reuse_candidate_diagnostics,
    summarize_executed_query_telemetry,
)
from src.agent.financial_scope_policies import should_apply_strict_company_scope


class _EvidenceBiasProbe:
    _SECTION_BIAS_BY_QUERY_TYPE = FinancialAgent._SECTION_BIAS_BY_QUERY_TYPE
    _section_bias = FinancialAgent._section_bias


class _QueryCaptureVSM:
    def __init__(self) -> None:
        self.queries = []

    def search(self, query, k=0, where_filter=None):
        self.queries.append({"query": query, "k": k, "where_filter": where_filter})
        return []


class _StaticVSM:
    def __init__(self, docs) -> None:
        self.docs = docs
        self.queries = []

    def search(self, query, k=0, where_filter=None):
        self.queries.append({"query": query, "k": k, "where_filter": where_filter})
        return list(self.docs)


class _BM25OnlyVSM:
    def __init__(self, docs, metadatas) -> None:
        self.bm25_docs = docs
        self.bm25_metadatas = metadatas


class RetrievalScopeTests(unittest.TestCase):
    def test_query_budget_preserves_period_diversity_when_truncating(self) -> None:
        selected, trace = apply_query_budget(
            [
                "2023년 current primary",
                "2023년 current statement",
                "2023년 current notes",
                "2022년 prior primary",
                "2022년 prior statement",
                "2022년 prior notes",
            ],
            4,
            dedupe=True,
        )

        self.assertEqual(len(selected), 4)
        self.assertTrue(any("2023년" in query for query in selected))
        self.assertTrue(any("2022년" in query for query in selected))
        self.assertEqual(trace["dropped_count"], 2)

    def test_query_budget_preserves_cjk_spacing_variants(self) -> None:
        selected, trace = apply_query_budget(
            [
                "2023년 커머스 매출액",
                "2023년 커머스매출액",
                "2023년 커머스 매출액 부문정보",
            ],
            8,
            dedupe=True,
        )

        self.assertEqual(
            selected,
            [
                "2023년 커머스 매출액",
                "2023년 커머스매출액",
                "2023년 커머스 매출액 부문정보",
            ],
        )
        self.assertEqual(trace["deduped_count"], 3)

    def test_executed_query_telemetry_summary_groups_by_source(self) -> None:
        summary = summarize_executed_query_telemetry(
            [
                {
                    "source": "primary",
                    "search_telemetry": {
                        "cache_hit": False,
                        "vector_attempted": True,
                        "embedding_usage": {
                            "embedding_api_calls": 1,
                            "embedding_text_count": 1,
                            "query_embedding_api_calls": 1,
                            "query_embedding_text_count": 1,
                        },
                    },
                },
                {
                    "source": "primary",
                    "search_telemetry": {
                        "cache_hit": True,
                        "vector_attempted": False,
                        "embedding_usage": {},
                    },
                },
                {
                    "source": "retry",
                    "search_telemetry": {
                        "cache_hit": False,
                        "vector_attempted": True,
                        "embedding_usage": {
                            "embedding_api_calls": 1,
                            "embedding_text_count": 1,
                            "query_embedding_api_calls": 1,
                            "query_embedding_text_count": 1,
                        },
                    },
                },
            ]
        )

        self.assertEqual(summary["executed_query_count"], 3)
        self.assertEqual(summary["cache_hit_count"], 1)
        self.assertEqual(summary["vector_attempted_count"], 2)
        self.assertEqual(summary["query_embedding_api_calls"], 2)
        self.assertEqual(summary["by_source"]["primary"]["executed_query_count"], 2)
        self.assertEqual(summary["by_source"]["primary"]["cache_hit_count"], 1)
        self.assertEqual(summary["by_source"]["retry"]["query_embedding_api_calls"], 1)

    def test_cross_trace_reuse_candidate_diagnostics_matches_prior_same_source_filter_query(self) -> None:
        diagnostics = cross_trace_reuse_candidate_diagnostics(
            [
                {
                    "source": "primary",
                    "base_query": "Revenue",
                    "executed_query": "Revenue 2023",
                    "where_filter": {"year": 2023},
                    "search_telemetry": {"cache_hit": True},
                },
                {
                    "source": "operand_focus",
                    "base_query": "Revenue",
                    "executed_query": "Revenue 2023",
                    "where_filter": {"year": 2023},
                },
            ],
            [
                {
                    "query_budget": {
                        "source": {
                            "active_subtask_id": "task_1",
                            "active_subtask_operation": "lookup",
                        }
                    },
                    "executed_queries": [
                        {
                            "source": "primary",
                            "base_query": "Revenue",
                            "executed_query": "  revenue   2023 ",
                            "where_filter": {"year": 2023},
                        },
                        {
                            "source": "primary",
                            "base_query": "Revenue",
                            "executed_query": "Revenue 2023",
                            "where_filter": {"year": 2022},
                        },
                    ],
                }
            ],
            current_trace_index=2,
        )

        self.assertEqual(diagnostics["mode"], "trace_only")
        self.assertEqual(diagnostics["scope"], "cross_trace_same_source_same_filter_exact_signature")
        self.assertEqual(diagnostics["candidate_count"], 1)
        self.assertEqual(diagnostics["prior_match_count"], 1)
        self.assertEqual(diagnostics["by_source"]["primary"]["candidate_count"], 1)
        self.assertEqual(len(diagnostics["candidates"]), 1)
        candidate = diagnostics["candidates"][0]
        self.assertEqual(candidate["source"], "primary")
        self.assertTrue(candidate["current_cache_hit"])
        self.assertEqual(candidate["prior_matches"][0]["trace_index"], 1)
        self.assertEqual(candidate["prior_matches"][0]["task_id"], "task_1")
        self.assertEqual(candidate["prior_matches"][0]["operation"], "lookup")

    def test_strict_company_scope_is_disabled_when_rcept_no_is_present(self) -> None:
        self.assertFalse(
            should_apply_strict_company_scope(
                ["네이버"],
                {"company": "네이버", "year": 2023, "rcept_no": "20240318000844"},
            )
        )

    def test_strict_company_scope_is_enabled_without_rcept_no(self) -> None:
        self.assertTrue(
            should_apply_strict_company_scope(
                ["네이버"],
                {"company": "네이버", "year": 2023},
            )
        )

    def test_strict_company_scope_is_disabled_when_multi_report_receipts_are_present(self) -> None:
        self.assertFalse(
            should_apply_strict_company_scope(
                ["네이버"],
                {
                    "company": "네이버",
                    "year": 2023,
                    "source_reports": [
                        {"corp_name": "네이버", "year": 2023, "rcept_no": "20240318000844"},
                        {"corp_name": "네이버", "year": 2022, "rcept_no": "20230314001049"},
                    ],
                },
            )
        )

    def test_risk_queries_prefer_management_discussion_section(self) -> None:
        probe = _EvidenceBiasProbe()
        mda_bias = probe._section_bias("risk", "IV. 이사의 경영진단 및 분석의견")
        board_bias = probe._section_bias(
            "risk",
            "VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항",
        )
        self.assertGreater(mda_bias, board_bias)
        self.assertGreater(mda_bias, 0.0)

    def test_business_overview_queries_prefer_management_discussion_section(self) -> None:
        probe = _EvidenceBiasProbe()
        mda_bias = probe._section_bias(
            "business_overview",
            "IV. 이사의 경영진단 및 분석의견",
        )
        board_bias = probe._section_bias(
            "business_overview",
            "VI. 이사회 등 회사의 기관에 관한 사항 > 1. 이사회에 관한 사항",
        )
        self.assertGreater(mda_bias, board_bias)
        self.assertGreater(mda_bias, 0.0)

    def test_active_subtask_retrieval_queries_override_global_query_bundle(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._hybrid_rerank = lambda docs, query, intent, companies, years, report_scope=None: docs

        state = {
            "query": "전체 subtraction 질문",
            "retrieval_queries": ["전체 subtraction 질문", "전역 쿼리"],
            "active_subtask": {
                "query": "2023년 법인세비용차감전순이익",
                "retrieval_queries": ["2023년 법인세비용차감전순이익 연결 손익계산서"],
            },
            "report_scope": {"company": "네이버", "year": 2023},
            "companies": ["네이버"],
            "years": [2023],
            "section_filter": None,
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "",
        }

        agent._retrieve(state)

        self.assertTrue(agent.vsm.queries)
        first_query = agent.vsm.queries[0]["query"]
        self.assertIn("2023년 법인세비용차감전순이익 연결 손익계산서", first_query)
        self.assertNotIn("전역 쿼리", first_query)

    def test_retrieval_query_budget_caps_primary_and_retry_searches(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 2
        agent.retry_retrieval_query_budget = 1
        agent.focused_retrieval_query_budget = 0
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "원본 질문",
                "retrieval_queries": ["전역 쿼리"],
                "active_subtask": {
                    "query": "subtask query",
                    "retrieval_queries": ["primary one", "primary two", "primary three"],
                },
                "report_scope": {"year": 2023},
                "companies": [],
                "years": [2023],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": ["retry one", "retry two"],
                "topic": "",
                "format_preference": "table",
            }
        )

        self.assertEqual(len(agent.vsm.queries), 3)
        searched = [row["query"] for row in agent.vsm.queries]
        self.assertTrue(any("primary one" in query for query in searched))
        self.assertTrue(any("primary two" in query for query in searched))
        self.assertFalse(any("primary three" in query for query in searched))
        self.assertTrue(any("retry one" in query for query in searched))
        self.assertFalse(any("retry two" in query for query in searched))
        trace = result["retrieval_debug_trace"]["query_budget"]
        self.assertEqual(trace["source"]["kind"], "active_subtask_retrieval_queries")
        self.assertEqual(trace["source"]["input_primary_query_count"], 3)
        self.assertEqual(trace["source"]["active_subtask_retrieval_query_count"], 3)
        self.assertEqual(len(result["retrieval_debug_trace_history"]), 1)
        self.assertEqual(
            result["retrieval_debug_trace_history"][0]["query_budget"]["primary"]["selected_count"],
            2,
        )
        self.assertEqual(trace["primary"]["selected_count"], 2)
        self.assertEqual(trace["primary"]["dropped_count"], 1)
        self.assertEqual(trace["retry"]["selected_count"], 1)
        self.assertEqual(trace["retry"]["dropped_count"], 1)

    def test_query_enrichment_caps_sections_in_executed_query_only(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 0
        agent.preferred_section_query_budget = 2
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "revenue",
                "active_subtask": {
                    "query": "revenue",
                    "preferred_sections": ["Income statement", "Notes", "MDA"],
                },
                "report_scope": {},
                "companies": [],
                "years": [],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": [],
                "topic": "",
                "format_preference": "table",
            }
        )

        searched = agent.vsm.queries[0]["query"]
        self.assertIn("Income statement", searched)
        self.assertIn("MDA", searched)
        self.assertNotIn("Notes", searched)
        trace = result["retrieval_debug_trace"]
        self.assertEqual(
            trace["policy_trace"]["preferred_sections"],
            ["Income statement", "Notes", "MDA"],
        )
        section_trace = trace["query_budget"]["enrichment"]["preferred_sections"]
        self.assertEqual(section_trace["selected_count"], 2)
        self.assertEqual(section_trace["selection_strategy"], "head_tail")
        self.assertEqual(section_trace["dropped_terms"], ["Notes"])

    def test_retrieve_records_cross_trace_reuse_candidates_without_skipping_search(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "Revenue 2023",
                "active_subtask": {
                    "task_id": "task_2",
                    "retrieval_queries": ["Revenue 2023"],
                },
                "report_scope": {"year": 2023},
                "companies": [],
                "years": [2023],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": [],
                "topic": "",
                "format_preference": "table",
                "retrieval_debug_trace_history": [
                    {
                        "query_budget": {
                            "source": {
                                "active_subtask_id": "task_1",
                                "answer_mode": "semantic_program",
                            }
                        },
                        "executed_queries": [
                            {
                                "source": "primary",
                                "base_query": "Revenue 2023",
                                "executed_query": (
                                    "Revenue 2023 IV. 이사의 경영진단 및 분석의견 "
                                    "II. 사업의 내용 사업의 개요 나. 영업실적"
                                ),
                                "where_filter": {"year": 2023},
                            }
                        ],
                    }
                ],
            }
        )

        self.assertEqual(len(agent.vsm.queries), 1)
        trace = result["retrieval_debug_trace"]
        reuse = trace["cross_trace_reuse_candidates"]
        self.assertEqual(reuse["candidate_count"], 1)
        self.assertEqual(reuse["prior_match_count"], 1)
        self.assertEqual(reuse["current_trace_index"], 2)
        self.assertEqual(reuse["candidates"][0]["prior_matches"][0]["task_id"], "task_1")
        self.assertEqual(len(result["retrieval_debug_trace_history"]), 2)

    def test_retrieve_reuses_state_query_result_cache_for_sibling_primary_query(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 0
        agent.preferred_section_query_budget = 0
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="cached result",
                        metadata={
                            "chunk_uid": "cached-primary",
                            "block_type": "table",
                            "year": 2023,
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        base_state = {
            "query": "shared question",
            "report_scope": {"year": 2023},
            "companies": [],
            "years": [2023],
            "section_filter": None,
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "",
            "format_preference": "table",
        }
        first = agent._retrieve(
            {
                **base_state,
                "active_subtask": {
                    "task_id": "task_1",
                    "query": "shared primary",
                    "retrieval_queries": ["shared primary"],
                },
            }
        )
        self.assertEqual(len(agent.vsm.queries), 1)

        second = agent._retrieve(
            {
                **base_state,
                "active_subtask": {
                    "task_id": "task_2",
                    "query": "shared primary",
                    "retrieval_queries": ["shared primary"],
                },
                "retrieval_debug_trace_history": first["retrieval_debug_trace_history"],
                "retrieval_query_result_cache": first["retrieval_query_result_cache"],
            }
        )

        self.assertEqual(len(agent.vsm.queries), 1)
        self.assertEqual(second["retrieval_debug_trace"]["executed_queries"], [])
        self.assertEqual(len(second["retrieval_debug_trace"]["reused_queries"]), 1)
        self.assertEqual(second["retrieval_debug_trace"]["query_result_cache"]["reuse_count"], 1)
        self.assertEqual(second["retrieval_debug_trace"]["query_result_cache"]["avoided_search_count"], 1)
        self.assertEqual(
            second["retrieval_debug_trace"]["query_result_cache"]["by_source"]["primary"]["avoided_search_count"],
            1,
        )
        reuse = second["retrieval_debug_trace"]["cross_trace_reuse_candidates"]
        self.assertEqual(reuse["candidate_count"], 1)
        self.assertTrue(reuse["candidates"][0]["current_cache_hit"])
        self.assertTrue(reuse["candidates"][0]["current_result_cache_hit"])
        self.assertEqual(len(second["retrieved_docs"]), 1)

    def test_retrieve_does_not_reuse_semantic_objective_cache_for_distinct_query(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 0
        agent.preferred_section_query_budget = 0
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="objective cached result",
                        metadata={
                            "chunk_uid": "objective-primary",
                            "block_type": "table",
                            "year": 2023,
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        base_state = {
            "query": "base question",
            "report_scope": {"year": 2023},
            "companies": [],
            "years": [2023],
            "section_filter": None,
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "",
            "format_preference": "table",
        }
        answer_obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "target metric",
                "required": True,
                "scope": {"period": "2023"},
            }
        ]
        first = agent._retrieve(
            {
                **base_state,
                "semantic_plan": {
                    "program_required": True,
                    "answer_obligations": answer_obligations,
                },
                "answer_obligations": answer_obligations,
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_label": "target metric",
                    "query": "target metric primary table",
                    "retrieval_queries": ["target metric primary table"],
                },
            }
        )
        self.assertEqual(len(agent.vsm.queries), 1)

        second = agent._retrieve(
            {
                **base_state,
                "semantic_plan": {
                    "program_required": True,
                    "answer_obligations": answer_obligations,
                },
                "answer_obligations": answer_obligations,
                "active_subtask": {
                    "task_id": "task_2",
                    "metric_label": "target metric",
                    "query": "target metric statement row",
                    "retrieval_queries": ["target metric statement row"],
                },
                "retrieval_debug_trace_history": first["retrieval_debug_trace_history"],
                "retrieval_query_result_cache": first["retrieval_query_result_cache"],
            }
        )

        self.assertEqual(len(agent.vsm.queries), 2)
        self.assertEqual(
            [item["base_query"] for item in second["retrieval_debug_trace"]["executed_queries"]],
            ["target metric statement row"],
        )
        reused_queries = second["retrieval_debug_trace"]["reused_queries"]
        self.assertEqual(reused_queries, [])
        cache_trace = second["retrieval_debug_trace"]["query_result_cache"]
        self.assertEqual(cache_trace["scope"], "state_same_filter_exact_signature")
        self.assertEqual(cache_trace["reuse_count"], 0)
        self.assertEqual(cache_trace["objective_hit_count"], 0)
        self.assertEqual(cache_trace["entry_count"], 2)
        self.assertGreaterEqual(len(second["retrieved_docs"]), 1)

    def test_semantic_program_executes_distinct_queries_with_same_obligations(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 0
        agent.preferred_section_query_budget = 0
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "target metric",
                "required": True,
                "scope": {"period": "2023"},
            }
        ]
        result = agent._retrieve(
            {
                "query": "target metric",
                "report_scope": {"year": 2023},
                "companies": [],
                "years": [2023],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": [],
                "topic": "",
                "format_preference": "table",
                "semantic_plan": {
                    "program_required": True,
                    "answer_obligations": obligations,
                },
                "answer_obligations": obligations,
                "active_subtask": {
                    "task_id": "task_1",
                    "metric_label": "target metric",
                    "query": "target metric",
                    "retrieval_queries": [
                        "target metric management table",
                        "target metric financial statement row",
                    ],
                },
            }
        )

        self.assertEqual(len(agent.vsm.queries), 2)
        trace = result["retrieval_debug_trace"]
        self.assertEqual(
            [item["base_query"] for item in trace["executed_queries"]],
            [
                "target metric management table",
                "target metric financial statement row",
            ],
        )
        self.assertEqual(trace["reused_queries"], [])
        self.assertEqual(trace["query_result_cache"]["entry_count"], 2)

    def test_semantic_program_enriches_each_retrieval_query_from_its_own_meaning(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 4
        agent.preferred_section_query_budget = 2
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        state = {
            "query": "compare the requested metric",
            "report_scope": {},
            "companies": [],
            "years": [],
            "section_filter": None,
            "intent": "comparison",
            "query_type": "comparison",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "requested metric",
            "format_preference": "table",
            "semantic_plan": {"program_required": True, "answer_obligations": []},
            "answer_obligations": [],
            "active_subtask": {
                "task_id": "task_1",
                "retrieval_queries": ["opening metric", "closing metric"],
            },
        }

        def hint_for_query(query, _topic, _intent, **_kwargs):
            return "opening-context" if query == "opening metric" else "closing-context"

        def sections_for_query(_state, query, _topic, _intent, **_kwargs):
            return ["opening-section"] if query == "opening metric" else ["closing-section"]

        with patch(
            "src.agent.financial_retrieval_pipeline.retrieval_hint_from_topic",
            side_effect=hint_for_query,
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            side_effect=sections_for_query,
        ):
            result = agent._retrieve(state)

        executed = result["retrieval_debug_trace"]["executed_queries"]
        self.assertEqual(len(executed), 2)
        self.assertEqual(
            executed[0]["query_enrichment"],
            {
                "retrieval_hint_terms": ["opening-context"],
                "preferred_sections": ["opening-section"],
            },
        )
        self.assertEqual(
            executed[1]["query_enrichment"],
            {
                "retrieval_hint_terms": ["closing-context"],
                "preferred_sections": ["closing-section"],
            },
        )
        self.assertNotIn("closing-context", executed[0]["executed_query"])
        self.assertNotIn("opening-context", executed[1]["executed_query"])

    def test_semantic_program_query_enrichment_respects_obligation_kind_ownership(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 4
        agent.preferred_section_query_budget = 2
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "derived_value",
                "label": "quantity change",
                "required": True,
                "retrieval_hints": ["quantity change"],
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_001:req_001",
                        "label": "opening quantity",
                        "required": True,
                        "retrieval_hints": ["opening metric"],
                    }
                ],
            },
            {
                "obligation_id": "ob_002",
                "kind": "narrative",
                "label": "cause explanation",
                "required": True,
                "retrieval_hints": ["cause explanation"],
                "evidence_requirements": [],
            },
        ]
        state = {
            "query": "calculate quantity change and explain the cause",
            "report_scope": {},
            "companies": [],
            "years": [],
            "section_filter": None,
            "intent": "risk",
            "query_type": "risk",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "quantity change and cause",
            "format_preference": "mixed",
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {
                "task_id": "task_1",
                "retrieval_queries": ["opening metric", "cause explanation"],
            },
        }

        def hint_for_query(
            _query,
            _topic,
            _intent,
            *,
            include_narrative_policies=True,
        ):
            return "narrative-context" if include_narrative_policies else "numeric-context"

        def sections_for_query(
            _state,
            _query,
            _topic,
            _intent,
            *,
            include_narrative_policies=True,
        ):
            return [
                "narrative-section"
                if include_narrative_policies
                else "numeric-section"
            ]

        with patch(
            "src.agent.financial_retrieval_pipeline.retrieval_hint_from_topic",
            side_effect=hint_for_query,
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            side_effect=sections_for_query,
        ):
            result = agent._retrieve(state)

        executed = result["retrieval_debug_trace"]["executed_queries"]
        self.assertEqual(len(executed), 2)
        self.assertEqual(executed[0]["query_semantics"]["mode"], "numeric")
        self.assertEqual(executed[1]["query_semantics"]["mode"], "narrative")
        self.assertIn("numeric-context", executed[0]["executed_query"])
        self.assertNotIn("narrative-context", executed[0]["executed_query"])
        self.assertIn("narrative-context", executed[1]["executed_query"])
        self.assertNotIn("numeric-context", executed[1]["executed_query"])

    def test_semantic_query_budget_reserves_later_required_groups(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 4
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 0
        agent.preferred_section_query_budget = 0
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        query = "Return the opening amount, closing amount, and source-defined summary."
        obligations = [
            {
                "obligation_id": "ob_opening",
                "kind": "direct_value",
                "label": "opening amount",
                "required": True,
                "retrieval_hints": [
                    "opening amount",
                    "opening ledger",
                    "opening note",
                ],
                "evidence_requirements": [],
            },
            {
                "obligation_id": "ob_closing",
                "kind": "direct_value",
                "label": "closing amount",
                "required": True,
                "retrieval_hints": ["closing amount"],
                "evidence_requirements": [],
            },
            {
                "obligation_id": "ob_summary",
                "kind": "narrative",
                "label": "source-defined summary",
                "required": True,
                "retrieval_hints": ["source-defined summary"],
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_summary:req_summary",
                        "label": "source-defined summary",
                        "required": True,
                        "retrieval_hints": ["source-defined summary"],
                    }
                ],
            },
        ]
        retrieval_queries = [
            query,
            "opening amount",
            "opening ledger",
            "opening note",
            "closing amount",
            "source-defined summary",
        ]
        state = {
            "query": query,
            "report_scope": {},
            "companies": [],
            "years": [],
            "section_filter": None,
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": query,
            "format_preference": "mixed",
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {
                "task_id": "task_1",
                "retrieval_queries": retrieval_queries,
            },
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.retrieval_hint_from_topic",
            return_value="",
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ):
            result = agent._retrieve(state)

        trace = result["retrieval_debug_trace"]
        self.assertEqual(
            trace["query_bundle"],
            [
                query,
                "opening amount",
                "closing amount",
                "source-defined summary",
            ],
        )
        primary = trace["query_budget"]["primary"]
        self.assertEqual(
            primary["selection_strategy"],
            "semantic_required_group_coverage_v1",
        )
        self.assertEqual(primary["unreserved_group_ids"], [])
        self.assertEqual(
            {item["group_id"] for item in primary["reserved_group_queries"]},
            {
                "ob_opening",
                "ob_closing",
                "ob_summary:req_summary",
            },
        )

    def test_narrative_supplement_keeps_table_alternatives_when_no_prose_matches(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "target venture | equity result | 10",
                "target venture | continuing result | -20 | total comprehensive result | -18",
                "unrelated table | 90",
            ],
            [
                {
                    "chunk_uid": "movement-table",
                    "company": "sample",
                    "year": 2024,
                    "statement_type": "notes",
                    "block_type": "table",
                    "table_header_context": "entity | equity result",
                },
                {
                    "chunk_uid": "summary-table",
                    "company": "sample",
                    "year": 2024,
                    "statement_type": "notes",
                    "block_type": "table",
                    "table_header_context": (
                        "entity | continuing result | total comprehensive result"
                    ),
                },
                {
                    "chunk_uid": "section-only-noise",
                    "company": "sample",
                    "year": 2024,
                    "statement_type": "notes",
                    "block_type": "table",
                    "section_path": "target venture result",
                    "table_header_context": "entity | unrelated value",
                },
            ],
        )
        obligation = {
            "obligation_id": "ob_summary",
            "kind": "narrative",
            "label": "target venture result",
            "required": True,
            "retrieval_hints": ["target venture result"],
            "evidence_requirements": [
                {
                    "requirement_id": "ob_summary:req_summary",
                    "label": "target venture result",
                    "required": True,
                    "retrieval_hints": ["target venture result"],
                }
            ],
        }
        state = {
            "query": "Summarize the target venture result.",
            "topic": "target venture result",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "companies": ["sample"],
            "years": [2024],
            "answer_obligations": [obligation],
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": [obligation],
            },
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["notes"],
        ):
            selected = agent._supplement_section_seed_docs(state)

        selected_ids = {
            doc.metadata.get("chunk_uid")
            for doc, _score in selected
        }
        self.assertEqual(
            selected_ids,
            {"movement-table", "summary-table"},
        )
        self.assertNotIn("section-only-noise", selected_ids)

    def test_semantic_program_supplement_requires_declared_input_hint_match(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "opening quantity | 120 | units",
                "unrelated total | 900 | units",
            ],
            [
                {
                    "chunk_uid": "relevant-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                },
                {
                    "chunk_uid": "unrelated-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "unrelated total",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "derived_value",
                "label": "quantity change",
                "required": True,
                "retrieval_hints": ["quantity change"],
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_001:req_001",
                        "label": "opening quantity",
                        "required": True,
                        "retrieval_hints": ["opening quantity"],
                        "scope": {
                            "company": "Example Co",
                            "period": "2024",
                            "consolidation_scope": "consolidated",
                        },
                    }
                ],
            }
        ]
        state = {
            "query": "quantity change from the primary statement",
            "topic": "quantity change",
            "intent": "comparison",
            "query_type": "comparison",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=["primary statement"],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["income_statement"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            [doc.metadata["chunk_uid"] for doc, _score in supplemented],
            ["relevant-row"],
        )

    def test_semantic_program_supplement_does_not_require_domain_section_prior(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            ["opening quantity | 120 | units"],
            [
                {
                    "chunk_uid": "declared-input-row",
                    "company": "Example Co",
                    "year": 2024,
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                }
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "opening quantity",
                "required": True,
                "retrieval_hints": ["opening quantity"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
            }
        ]
        state = {
            "query": "opening quantity",
            "topic": "opening quantity",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=[],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            [doc.metadata["chunk_uid"] for doc, _score in supplemented],
            ["declared-input-row"],
        )

    def test_semantic_program_supplement_matches_declared_hint_after_preview_prefix(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [f"{'context ' * 160}opening quantity | 120 | units"],
            [
                {
                    "chunk_uid": "late-relevant-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "context",
                }
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "derived_value",
                "label": "quantity change",
                "required": True,
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_001:req_001",
                        "label": "opening quantity",
                        "required": True,
                        "retrieval_hints": ["opening quantity"],
                        "scope": {
                            "company": "Example Co",
                            "period": "2024",
                            "consolidation_scope": "consolidated",
                        },
                    }
                ],
            }
        ]
        state = {
            "query": "quantity change from the primary statement",
            "topic": "quantity change",
            "intent": "comparison",
            "query_type": "comparison",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=["primary statement"],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["income_statement"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            [doc.metadata["chunk_uid"] for doc, _score in supplemented],
            ["late-relevant-row"],
        )

    def test_semantic_program_supplement_matches_whitespace_only_label_variant(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            ["opening quantity | 120 | units"],
            [
                {
                    "chunk_uid": "spacing-variant-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "context",
                }
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "openingquantity",
                "required": True,
                "retrieval_hints": ["openingquantity"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
            }
        ]
        state = {
            "query": "openingquantity from the primary statement",
            "topic": "openingquantity",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=["primary statement"],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["income_statement"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            [doc.metadata["chunk_uid"] for doc, _score in supplemented],
            ["spacing-variant-row"],
        )

    def test_semantic_program_supplement_honors_statement_type_priority(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "opening quantity | 120 | units",
                "opening quantity | 120 | units",
            ],
            [
                {
                    "chunk_uid": "summary-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "summary_financials",
                    "consolidation_scope": "unknown",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                },
                {
                    "chunk_uid": "primary-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "opening quantity",
                "required": True,
                "retrieval_hints": ["opening quantity"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
            }
        ]
        state = {
            "query": "opening quantity from the primary statement",
            "topic": "opening quantity",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=["primary statement"],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["income_statement", "summary_financials"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(supplemented[0][0].metadata["chunk_uid"], "primary-row")

    def test_semantic_program_numeric_supplement_prefers_atomic_declared_value_surface(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "portfolio total | 900 | units",
                "2024 consolidated target measure total is reported on the preceding row",
                "target measure aggregate | 120 | units",
            ],
            [
                {
                    "chunk_uid": "preferred-statement-generic-total",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "preferred notes",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "portfolio total",
                    "table_value_labels_text": "portfolio amount 900",
                },
                {
                    "chunk_uid": "context-only-scope-note",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "operating detail",
                    "statement_type": "unknown",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "scope note",
                    "table_value_labels_text": "",
                },
                {
                    "chunk_uid": "atomic-target-row",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "operating detail",
                    "statement_type": "unknown",
                    "consolidation_scope": "unknown",
                    "block_type": "table",
                    "table_row_labels_text": "target measure aggregate",
                    "table_value_labels_text": "target measure aggregate 120",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "2024 consolidated target measure total",
                "required": True,
                "retrieval_hints": ["target measure", "total"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
            }
        ]
        state = {
            "query": "report the 2024 consolidated target measure total",
            "topic": "target measure total",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["notes"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            [doc.metadata["chunk_uid"] for doc, _score in supplemented],
            ["atomic-target-row"],
        )

    def test_semantic_program_supplement_prefers_table_for_numeric_input(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "opening quantity is described here",
                "opening quantity | 120 | units",
            ],
            [
                {
                    "chunk_uid": "explanatory-paragraph",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "paragraph",
                    "table_row_labels_text": "opening quantity",
                },
                {
                    "chunk_uid": "structured-table",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "direct_value",
                "label": "opening quantity",
                "required": True,
                "retrieval_hints": ["opening quantity"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
            }
        ]
        state = {
            "query": "opening quantity from the primary statement",
            "topic": "opening quantity",
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=["primary statement"],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["income_statement"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(supplemented[0][0].metadata["chunk_uid"], "structured-table")

    def test_semantic_program_supplement_preserves_required_narrative_input(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "opening quantity | 120 | units",
                "stress scenario appears in a numeric appendix",
                "stress scenario explains the reported change",
            ],
            [
                {
                    "chunk_uid": "structured-table",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "primary statement",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                },
                {
                    "chunk_uid": "narrative-table-noise",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "supporting notes",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "stress scenario",
                },
                {
                    "chunk_uid": "narrative-explanation",
                    "company": "Example Co",
                    "year": 2024,
                    "section_path": "supporting notes",
                    "statement_type": "notes",
                    "consolidation_scope": "consolidated",
                    "block_type": "paragraph",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_numeric",
                "kind": "derived_value",
                "label": "quantity change",
                "required": True,
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_numeric:req_opening",
                        "label": "opening quantity",
                        "required": True,
                        "retrieval_hints": ["opening quantity"],
                    }
                ],
            },
            {
                "obligation_id": "ob_narrative",
                "kind": "narrative",
                "label": "change explanation",
                "required": True,
                "retrieval_hints": ["stress scenario"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
            },
        ]
        state = {
            "query": "calculate the quantity change and explain it",
            "topic": "quantity change",
            "intent": "comparison",
            "query_type": "comparison",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=["income_statement", "notes"],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            {doc.metadata["chunk_uid"] for doc, _score in supplemented},
            {"structured-table", "narrative-explanation"},
        )

    def test_semantic_program_narrative_requirement_owns_targeted_supplement(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "portfolio expansion provides general background",
                "a stress scenario caused the reported change",
            ],
            [
                {
                    "chunk_uid": "general-context",
                    "company": "Example Co",
                    "year": 2024,
                    "consolidation_scope": "consolidated",
                    "block_type": "paragraph",
                },
                {
                    "chunk_uid": "direct-relation",
                    "company": "Example Co",
                    "year": 2024,
                    "consolidation_scope": "consolidated",
                    "block_type": "paragraph",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_narrative",
                "kind": "narrative",
                "label": "explanation",
                "required": True,
                "retrieval_hints": ["portfolio expansion"],
                "scope": {
                    "company": "Example Co",
                    "period": "2024",
                    "consolidation_scope": "consolidated",
                },
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_narrative:req_relation",
                        "label": "reported change cause",
                        "required": True,
                        "retrieval_hints": [
                            "stress scenario caused the reported change"
                        ],
                    }
                ],
            }
        ]
        state = {
            "query": "explain the change",
            "topic": "change explanation",
            "intent": "comparison",
            "query_type": "comparison",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=[],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        self.assertEqual(
            [doc.metadata["chunk_uid"] for doc, _score in supplemented],
            ["direct-relation"],
        )

    def test_semantic_program_supplement_keeps_bounded_narrative_alternatives(self) -> None:
        narrative_ids = [f"narrative-{index}" for index in range(5)]
        period_noise_ids = [f"period-noise-{index}" for index in range(3)]
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            [
                "opening quantity | 120 | units",
                *[f"2024 annual context {index}" for index in range(3)],
                *[
                    f"risk context provides a distinct explanation {index}"
                    for index in range(5)
                ],
                "risk context | tabular cross-reference",
            ],
            [
                {
                    "chunk_uid": "structured-table",
                    "company": "Example Co",
                    "year": 2024,
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "opening quantity",
                },
                *[
                    {
                        "chunk_uid": candidate_id,
                        "company": "Example Co",
                        "year": 2024,
                        "consolidation_scope": "consolidated",
                        "block_type": "paragraph",
                    }
                    for candidate_id in period_noise_ids
                ],
                *[
                    {
                        "chunk_uid": candidate_id,
                        "company": "Example Co",
                        "year": 2024,
                        "consolidation_scope": "consolidated",
                        "block_type": "paragraph",
                    }
                    for candidate_id in narrative_ids
                ],
                {
                    "chunk_uid": "narrative-table-noise",
                    "company": "Example Co",
                    "year": 2024,
                    "consolidation_scope": "consolidated",
                    "block_type": "table",
                    "table_row_labels_text": "risk context",
                },
            ],
        )
        obligations = [
            {
                "obligation_id": "ob_numeric",
                "kind": "derived_value",
                "label": "quantity change",
                "required": True,
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_numeric:req_opening",
                        "label": "opening quantity",
                        "required": True,
                        "retrieval_hints": ["opening quantity"],
                    }
                ],
            },
            {
                "obligation_id": "ob_narrative",
                "kind": "narrative",
                "label": "change explanation",
                "required": True,
                "retrieval_hints": ["risk context", "2024"],
                "scope": {"period": "2024"},
            },
        ]
        state = {
            "query": "calculate the quantity change and explain it",
            "topic": "quantity change",
            "intent": "comparison",
            "query_type": "comparison",
            "companies": ["Example Co"],
            "years": [2024],
            "report_scope": {},
            "semantic_plan": {
                "program_required": True,
                "answer_obligations": obligations,
            },
            "answer_obligations": obligations,
            "active_subtask": {},
        }

        with patch(
            "src.agent.financial_retrieval_pipeline.supplement_section_terms_for_query",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_sections",
            return_value=[],
        ), patch(
            "src.agent.financial_retrieval_pipeline._active_preferred_statement_types",
            return_value=[],
        ):
            supplemented = agent._supplement_section_seed_docs(state)

        selected_ids = {
            doc.metadata["chunk_uid"] for doc, _score in supplemented
        }
        self.assertIn("structured-table", selected_ids)
        self.assertTrue(set(narrative_ids).issubset(selected_ids))
        self.assertTrue(set(period_noise_ids).isdisjoint(selected_ids))
        self.assertNotIn("narrative-table-noise", selected_ids)

    def test_semantic_program_preserves_targeted_supplement_in_seed_pool(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 1
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.retrieval_hint_query_token_budget = 0
        agent.preferred_section_query_budget = 0
        high_docs = [
            (
                Document(
                    page_content=f"general context {index}",
                    metadata={
                        "chunk_uid": f"general-{index}",
                        "block_type": "table",
                    },
                ),
                float(10 - index),
            )
            for index in range(6)
        ]
        targeted = Document(
            page_content="opening quantity | 120 | units",
            metadata={"chunk_uid": "targeted-input", "block_type": "table"},
        )
        agent.vsm = _StaticVSM(high_docs)
        agent._merge_retry_candidates = FinancialAgent._merge_retry_candidates.__get__(
            agent,
            FinancialAgent,
        )
        agent._rerank_docs = lambda docs, _state: sorted(
            docs,
            key=lambda item: item[1],
            reverse=True,
        )
        agent._supplement_section_seed_docs = lambda _state: [(targeted, 0.01)]

        obligations = [
            {
                "obligation_id": "ob_001",
                "kind": "derived_value",
                "label": "quantity change",
                "required": True,
                "retrieval_hints": ["quantity change"],
                "evidence_requirements": [
                    {
                        "requirement_id": "ob_001:req_001",
                        "label": "opening quantity",
                        "required": True,
                        "retrieval_hints": ["opening quantity"],
                    }
                ],
            }
        ]
        result = agent._retrieve(
            {
                "query": "quantity change",
                "report_scope": {},
                "companies": [],
                "years": [],
                "section_filter": None,
                "intent": "comparison",
                "query_type": "comparison",
                "reflection_count": 0,
                "retry_queries": [],
                "topic": "quantity change",
                "format_preference": "table",
                "semantic_plan": {
                    "program_required": True,
                    "answer_obligations": obligations,
                },
                "answer_obligations": obligations,
                "active_subtask": {
                    "task_id": "task_1",
                    "retrieval_queries": ["opening quantity"],
                },
            }
        )

        seed_ids = [
            doc.metadata.get("chunk_uid")
            for doc, _score in result["seed_retrieved_docs"]
        ]
        self.assertIn("targeted-input", seed_ids)


    def test_retry_query_budget_keeps_builtin_default_when_unset(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 0
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "원본 질문",
                "retrieval_queries": ["primary one", "primary one"],
                "active_subtask": {},
                "report_scope": {"year": 2023},
                "companies": [],
                "years": [2023],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": ["retry one", "retry two", "retry three", "retry four"],
                "topic": "",
                "format_preference": "table",
            }
        )

        searched = [row["query"] for row in agent.vsm.queries]
        self.assertEqual(len(searched), 4)
        self.assertEqual(sum(1 for query in searched if "primary one" in query), 1)
        self.assertTrue(any("retry three" in query for query in searched))
        self.assertFalse(any("retry four" in query for query in searched))
        trace = result["retrieval_debug_trace"]["query_budget"]
        self.assertFalse(trace["primary"]["dedupe_enabled"])
        self.assertEqual(trace["primary"]["selected_count"], 2)
        self.assertFalse(trace["retry"]["dedupe_enabled"])
        self.assertEqual(trace["retry"]["budget"], 3)
        self.assertEqual(trace["retry"]["selected_count"], 3)
        self.assertEqual(trace["retry"]["dropped_count"], 1)
        duplicate_guard = result["retrieval_debug_trace"]["executed_duplicate_guard"]
        self.assertTrue(duplicate_guard["enabled"])
        self.assertEqual(duplicate_guard["scope"], "same_trace_same_source_exact_signature")
        self.assertEqual(duplicate_guard["dropped_count"], 1)
        self.assertEqual(duplicate_guard["by_source"]["primary"]["dropped_count"], 1)


    def test_multi_source_receipts_override_primary_receipt_filter(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.vsm = _QueryCaptureVSM()
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        state = {
            "query": "시설투자(CAPEX) 전년 대비 증감률",
            "active_subtask": {"query": "2022년 시설투자(CAPEX)"},
            "report_scope": {
                "company": "삼성전자",
                "year": 2023,
                "rcept_no": "20240312000736",
                "source_reports": [
                    {"corp_name": "삼성전자", "year": 2023, "rcept_no": "20240312000736"},
                    {"corp_name": "삼성전자", "year": 2022, "rcept_no": "20230307000542"},
                ],
            },
            "companies": ["삼성전자"],
            "years": [2023],
            "section_filter": None,
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "",
            "format_preference": "table",
        }

        agent._retrieve(state)

        self.assertTrue(agent.vsm.queries)
        first_where = agent.vsm.queries[0]["where_filter"]
        self.assertEqual(
            first_where,
            {"rcept_no": {"$in": ["20240312000736", "20230307000542"]}},
        )

    def test_multi_source_scope_does_not_drop_prior_year_docs_on_year_filter(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="2023 시설투자 합계 531,139",
                        metadata={
                            "company": "삼성전자",
                            "year": 2023,
                            "rcept_no": "20240312000736",
                            "block_type": "table",
                        },
                    ),
                    1.0,
                ),
                (
                    Document(
                        page_content="2022 시설투자 합계 531,153",
                        metadata={
                            "company": "삼성전자",
                            "year": 2022,
                            "rcept_no": "20230307000542",
                            "block_type": "table",
                        },
                    ),
                    0.9,
                ),
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        state = {
            "query": "시설투자(CAPEX) 전년 대비 증감률",
            "active_subtask": {"query": "2022년 시설투자(CAPEX)"},
            "report_scope": {
                "company": "삼성전자",
                "year": 2023,
                "rcept_no": "20240312000736",
                "source_reports": [
                    {"corp_name": "삼성전자", "year": 2023, "rcept_no": "20240312000736"},
                    {"corp_name": "삼성전자", "year": 2022, "rcept_no": "20230307000542"},
                ],
            },
            "companies": ["삼성전자"],
            "years": [2023],
            "section_filter": None,
            "intent": "numeric_fact",
            "query_type": "numeric_fact",
            "reflection_count": 0,
            "retry_queries": [],
            "topic": "",
            "format_preference": "table",
        }

        result = agent._retrieve(state)
        retrieved_years = {int(doc.metadata.get("year", 0)) for doc, _ in result["retrieved_docs"]}

        self.assertEqual(retrieved_years, {2022, 2023})
        trace = result["retrieval_debug_trace"]
        self.assertEqual(trace["selected_count"], 2)
        self.assertEqual(trace["candidate_count"], 2)
        self.assertEqual(
            trace["executed_queries"][0]["where_filter"],
            {"rcept_no": {"$in": ["20240312000736", "20230307000542"]}},
        )
        self.assertEqual(
            [chunk["year"] for chunk in trace["selected_chunks"]],
            [2023, 2022],
        )

    def test_table_preferred_retrieval_keeps_table_when_window_is_small(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="general narrative context",
                        metadata={"chunk_id": "para-high", "block_type": "paragraph"},
                    ),
                    0.99,
                ),
                (
                    Document(
                        page_content="another paragraph",
                        metadata={"chunk_id": "para-second", "block_type": "paragraph"},
                    ),
                    0.98,
                ),
                (
                    Document(
                        page_content="metric | 2023 | 100",
                        metadata={"chunk_id": "table-low", "block_type": "table"},
                    ),
                    0.50,
                ),
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "lookup the table metric",
                "active_subtask": {},
                "report_scope": {},
                "companies": [],
                "years": [],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": [],
                "topic": "",
                "format_preference": "table",
            }
        )

        selected_ids = [
            doc.metadata.get("chunk_id")
            for doc, _score in result["retrieved_docs"]
        ]
        self.assertEqual(selected_ids, ["table-low", "para-high"])
        self.assertEqual(
            [chunk["chunk_uid"] for chunk in result["retrieval_debug_trace"]["selected_chunks"]],
            ["table-low", "para-high"],
        )
        self.assertEqual(
            result["retrieval_debug_trace"]["source_window"],
            {
                "retrieved_source_ids": ["table-low", "para-high"],
                "retrieved_unidentified_count": 0,
                "seed_source_ids": ["para-high", "para-second", "table-low"],
                "seed_unidentified_count": 0,
            },
        )


    def test_supplemental_seed_uses_preferred_statement_type_with_obligation_hints(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            docs=[
                "revenue | 1,000\ncost | 800\nadmin expense | 100",
                "unrelated table",
            ],
            metadatas=[
                {
                    "chunk_uid": "income-table",
                    "company": "ExampleCo",
                    "year": 2023,
                    "block_type": "table",
                    "statement_type": "income_statement",
                    "section_path": "Financial statements",
                    "table_context": "Financial statements",
                    "table_row_labels_text": "revenue cost admin expense",
                },
                {
                    "chunk_uid": "other-table",
                    "company": "ExampleCo",
                    "year": 2023,
                    "block_type": "table",
                    "statement_type": "notes",
                    "section_path": "Notes",
                    "table_context": "Notes",
                    "table_row_labels_text": "other",
                },
            ],
        )

        docs = agent._supplement_section_seed_docs(
            {
                "query": "손익계산서 비용률",
                "topic": "손익계산서 비용률",
                "intent": "comparison",
                "query_type": "comparison",
                "companies": ["ExampleCo"],
                "years": [2023],
                "answer_obligations": [
                    {
                        "obligation_id": "ob_001",
                        "kind": "direct_value",
                        "label": "revenue",
                        "retrieval_hints": ["revenue", "cost", "admin expense"],
                    }
                ],
                "semantic_plan": {"program_required": True},
                "active_subtask": {
                    "preferred_statement_types": ["income_statement"],
                },
            }
        )

        self.assertTrue(docs)
        self.assertEqual(docs[0][0].metadata["chunk_uid"], "income-table")

    def test_supplemental_seed_uses_top_level_statement_hint_with_quoted_row_label(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.vsm = _BM25OnlyVSM(
            docs=[
                "검증항목 | 1,000 | 800",
                "unrelated note table",
            ],
            metadatas=[
                {
                    "chunk_uid": "direct-statement-table",
                    "company": "ExampleCo",
                    "year": 2023,
                    "block_type": "table",
                    "statement_type": "income_statement",
                    "section_path": "III. 재무에 관한 사항",
                    "table_context": "연결 포괄손익계산서",
                    "table_row_labels_text": "검증항목",
                },
                {
                    "chunk_uid": "notes-table",
                    "company": "ExampleCo",
                    "year": 2023,
                    "block_type": "table",
                    "statement_type": "notes",
                    "section_path": "III. 재무에 관한 사항 > 주석",
                    "table_context": "주석",
                    "table_row_labels_text": "other",
                },
            ],
        )

        docs = agent._supplement_section_seed_docs(
            {
                "query": "2023년 연결 포괄손익계산서 상의 '검증항목' 전년 대비 변화를 요약해 줘.",
                "topic": "",
                "intent": "risk",
                "query_type": "risk",
                "companies": ["ExampleCo"],
                "years": [2023],
                "active_subtask": {},
            }
        )

        self.assertTrue(docs)
        self.assertEqual(docs[0][0].metadata["chunk_uid"], "direct-statement-table")

if __name__ == "__main__":
    unittest.main()
