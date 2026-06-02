import unittest

from langchain_core.documents import Document

from src.agent.financial_graph import FinancialAgent
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
        self.assertEqual(trace["primary"]["selected_count"], 2)
        self.assertEqual(trace["primary"]["dropped_count"], 1)
        self.assertEqual(trace["retry"]["selected_count"], 1)
        self.assertEqual(trace["retry"]["dropped_count"], 1)

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
        self.assertEqual(len(searched), 5)
        self.assertEqual(sum(1 for query in searched if "primary one" in query), 2)
        self.assertTrue(any("retry three" in query for query in searched))
        self.assertFalse(any("retry four" in query for query in searched))
        trace = result["retrieval_debug_trace"]["query_budget"]
        self.assertFalse(trace["primary"]["dedupe_enabled"])
        self.assertEqual(trace["primary"]["selected_count"], 2)
        self.assertFalse(trace["retry"]["dedupe_enabled"])
        self.assertEqual(trace["retry"]["budget"], 3)
        self.assertEqual(trace["retry"]["selected_count"], 3)
        self.assertEqual(trace["retry"]["dropped_count"], 1)

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

if __name__ == "__main__":
    unittest.main()
