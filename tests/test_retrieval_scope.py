import unittest

from langchain_core.documents import Document

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_retrieval_budget import (
    _apply_query_budget,
    _cross_trace_reuse_candidate_diagnostics,
    _summarize_executed_query_telemetry,
)
from src.agent.financial_graph_helpers import _should_apply_strict_company_scope


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
        selected, trace = _apply_query_budget(
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
        selected, trace = _apply_query_budget(
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
        summary = _summarize_executed_query_telemetry(
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
        diagnostics = _cross_trace_reuse_candidate_diagnostics(
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
            _should_apply_strict_company_scope(
                ["네이버"],
                {"company": "네이버", "year": 2023, "rcept_no": "20240318000844"},
            )
        )

    def test_strict_company_scope_is_enabled_without_rcept_no(self) -> None:
        self.assertTrue(
            _should_apply_strict_company_scope(
                ["네이버"],
                {"company": "네이버", "year": 2023},
            )
        )

    def test_strict_company_scope_is_disabled_when_multi_report_receipts_are_present(self) -> None:
        self.assertFalse(
            _should_apply_strict_company_scope(
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
                    "operation_family": "lookup",
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
                                "active_subtask_operation": "lookup",
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
                    "operation_family": "lookup",
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
                    "operation_family": "lookup",
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
        self.assertEqual(len(second["retrieved_docs"]), 1)

    def test_focused_operand_retrieval_is_skipped_when_primary_docs_cover_required_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="2023 revenue 1,000\n2023 cost 800",
                        metadata={
                            "chunk_id": "complete-primary",
                            "block_type": "table",
                            "year": 2023,
                            "table_row_labels_text": "revenue cost",
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "2023 revenue cost ratio",
                "active_subtask": {
                    "query": "2023 revenue cost ratio",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "revenue", "role": "denominator"},
                        {"label": "cost", "role": "numerator"},
                    ],
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
            }
        )

        self.assertEqual(len(agent.vsm.queries), 1)
        focus_trace = result["retrieval_debug_trace"]["query_budget"]["operand_focus"]
        self.assertTrue(focus_trace["skipped"])
        self.assertEqual(focus_trace["skip_reason"], "primary_required_operand_coverage_complete")
        self.assertEqual(focus_trace["primary_operand_coverage"]["covered_count"], 2)
        self.assertEqual(focus_trace["selected_count"], 0)

    def test_focused_operand_retrieval_runs_when_primary_docs_miss_required_operand(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="2023 revenue 1,000",
                        metadata={
                            "chunk_id": "partial-primary",
                            "block_type": "table",
                            "year": 2023,
                            "table_row_labels_text": "revenue",
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "2023 revenue cost ratio",
                "active_subtask": {
                    "query": "2023 revenue cost ratio",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "revenue", "role": "denominator"},
                        {"label": "cost", "role": "numerator"},
                    ],
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
            }
        )

        self.assertGreater(len(agent.vsm.queries), 1)
        focus_trace = result["retrieval_debug_trace"]["query_budget"]["operand_focus"]
        self.assertFalse(focus_trace["skipped"])
        self.assertEqual(focus_trace["primary_operand_coverage"]["covered_count"], 1)
        self.assertGreater(focus_trace["selected_count"], 0)

    def test_focused_operand_retrieval_runs_when_primary_docs_only_contain_period_numbers(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="2023 revenue\n2023 cost",
                        metadata={
                            "chunk_id": "labels-only-primary",
                            "block_type": "table",
                            "year": 2023,
                            "table_row_labels_text": "revenue cost",
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "2023 revenue cost ratio",
                "active_subtask": {
                    "query": "2023 revenue cost ratio",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "revenue", "role": "denominator"},
                        {"label": "cost", "role": "numerator"},
                    ],
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
            }
        )

        focus_trace = result["retrieval_debug_trace"]["query_budget"]["operand_focus"]
        self.assertFalse(focus_trace["skipped"])
        self.assertEqual(focus_trace["primary_operand_coverage"]["covered_count"], 0)
        self.assertGreater(focus_trace["selected_count"], 0)

    def test_focused_operand_retrieval_skips_complete_primary_coverage_with_narrative_sibling(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="2023 revenue 1,000\n2023 cost 800",
                        metadata={
                            "chunk_id": "complete-primary",
                            "block_type": "table",
                            "year": 2023,
                            "table_row_labels_text": "revenue cost",
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "2023 revenue cost ratio and explain the business context",
                "active_subtask": {
                    "task_id": "task_1",
                    "query": "2023 revenue cost ratio",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "revenue", "role": "denominator"},
                        {"label": "cost", "role": "numerator"},
                    ],
                },
                "calc_subtasks": [
                    {"task_id": "task_1", "operation_family": "ratio"},
                    {"task_id": "task_2", "operation_family": "narrative_summary"},
                ],
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
        )

        focus_trace = result["retrieval_debug_trace"]["query_budget"]["operand_focus"]
        self.assertTrue(focus_trace["skipped"])
        self.assertEqual(focus_trace["skip_reason"], "primary_required_operand_coverage_complete")
        self.assertEqual(focus_trace["skip_blocked_reason"], "narrative_sibling_subtask_present")
        self.assertEqual(focus_trace["duplicate_drop_blocked_reason"], "narrative_sibling_subtask_present")
        self.assertEqual(focus_trace["primary_operand_coverage"]["covered_count"], 2)
        self.assertEqual(focus_trace["selected_count"], 0)

    def test_focused_operand_retrieval_drops_primary_duplicate_queries_without_narrative_sibling(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 0
        agent.focused_retrieval_query_budget = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="revenue 1,000",
                        metadata={
                            "chunk_id": "complete-primary",
                            "block_type": "table",
                            "table_row_labels_text": "revenue",
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "revenue cost ratio",
                "active_subtask": {
                    "task_id": "task_1",
                    "query": "revenue",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "revenue", "role": "denominator"},
                        {"label": "cost", "role": "numerator"},
                    ],
                },
                "calc_subtasks": [
                    {"task_id": "task_1", "operation_family": "ratio"},
                ],
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

        executed = result["retrieval_debug_trace"]["executed_queries"]
        self.assertEqual([row["base_query"] for row in executed], ["revenue", "cost"])
        self.assertEqual([row["source"] for row in executed], ["primary", "operand_focus"])
        focus_trace = result["retrieval_debug_trace"]["query_budget"]["operand_focus"]
        self.assertFalse(focus_trace["skipped"])
        self.assertEqual(focus_trace["selected_count_before_duplicate_drop"], 2)
        self.assertEqual(focus_trace["duplicate_selected_query_dropped_count"], 1)
        self.assertEqual(focus_trace["selected_count"], 1)

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

    def test_executed_duplicate_guard_preserves_cross_source_queries(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 4
        agent.retrieval_query_budget = 0
        agent.retry_retrieval_query_budget = 1
        agent.focused_retrieval_query_budget = 4
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="revenue 1,000",
                        metadata={
                            "chunk_id": "partial-primary",
                            "block_type": "table",
                            "table_row_labels_text": "revenue",
                        },
                    ),
                    1.0,
                )
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "revenue cost ratio",
                "active_subtask": {
                    "task_id": "task_1",
                    "query": "revenue",
                    "operation_family": "ratio",
                    "required_operands": [
                        {"label": "revenue", "role": "denominator"},
                        {"label": "cost", "role": "numerator"},
                    ],
                },
                "calc_subtasks": [
                    {"task_id": "task_1", "operation_family": "ratio"},
                    {"task_id": "task_2", "operation_family": "narrative_summary"},
                ],
                "report_scope": {},
                "companies": [],
                "years": [],
                "section_filter": None,
                "intent": "numeric_fact",
                "query_type": "numeric_fact",
                "reflection_count": 0,
                "retry_queries": ["cost"],
                "topic": "",
                "format_preference": "table",
            }
        )

        executed = result["retrieval_debug_trace"]["executed_queries"]
        self.assertEqual([row["source"] for row in executed], ["primary", "operand_focus", "operand_focus", "retry"])
        self.assertEqual([row["base_query"] for row in executed], ["revenue", "revenue", "cost", "cost"])
        duplicate_guard = result["retrieval_debug_trace"]["executed_duplicate_guard"]
        self.assertEqual(duplicate_guard["dropped_count"], 0)

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

    def test_preferred_operand_section_doc_is_preserved_over_higher_scored_noncanonical_table(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.k = 2
        preferred_table = (
            Document(
                page_content="revenue | 1,000\ncost | 800\nadmin expense | 100",
                metadata={
                    "chunk_id": "preferred-income",
                    "block_type": "table",
                    "statement_type": "income_statement",
                    "section_path": "Financial statements > Income statement",
                    "table_context": "Income statement",
                    "table_row_labels_text": "revenue cost admin expense",
                },
            ),
            0.10,
        )
        agent.vsm = _StaticVSM(
            [
                (
                    Document(
                        page_content="cost | 8\nadmin expense | 1",
                        metadata={
                            "chunk_id": "notes-high",
                            "block_type": "table",
                            "statement_type": "notes",
                            "section_path": "Financial statements > Notes",
                            "table_context": "Notes",
                            "table_row_labels_text": "cost admin expense",
                        },
                    ),
                    0.99,
                ),
                (
                    Document(
                        page_content="general paragraph",
                        metadata={"chunk_id": "para-high", "block_type": "paragraph"},
                    ),
                    0.98,
                ),
                preferred_table,
            ]
        )
        agent._merge_retry_candidates = lambda existing, new: existing + new
        agent._rerank_docs = lambda docs, state: docs
        agent._supplement_section_seed_docs = lambda state: []

        result = agent._retrieve(
            {
                "query": "Calculate the expense ratio.",
                "active_subtask": {
                    "operation_family": "ratio",
                    "required_operands": [
                        {
                            "label": "cost",
                            "role": "numerator_1",
                            "preferred_statement_types": ["income_statement"],
                            "preferred_sections": ["Income statement"],
                        },
                        {
                            "label": "admin expense",
                            "role": "numerator_2",
                            "preferred_statement_types": ["income_statement"],
                            "preferred_sections": ["Income statement"],
                        },
                        {
                            "label": "revenue",
                            "role": "denominator_1",
                            "preferred_statement_types": ["income_statement"],
                            "preferred_sections": ["Income statement"],
                        },
                    ],
                    "preferred_statement_types": ["income_statement"],
                    "preferred_sections": ["Income statement"],
                },
                "report_scope": {},
                "companies": [],
                "years": [],
                "section_filter": None,
                "intent": "comparison",
                "query_type": "comparison",
                "reflection_count": 0,
                "retry_queries": [],
                "topic": "",
                "format_preference": "table",
            }
        )

        selected_ids = [doc.metadata.get("chunk_id") for doc, _score in result["retrieved_docs"]]
        self.assertIn("preferred-income", selected_ids)
        self.assertEqual(selected_ids[0], "preferred-income")

    def test_supplemental_seed_uses_preferred_statement_type_with_operand_coverage(self) -> None:
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
                "active_subtask": {
                    "preferred_statement_types": ["income_statement"],
                    "required_operands": [
                        {"label": "revenue", "preferred_statement_types": ["income_statement"]},
                        {"label": "cost", "preferred_statement_types": ["income_statement"]},
                        {"label": "admin expense", "preferred_statement_types": ["income_statement"]},
                    ],
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
