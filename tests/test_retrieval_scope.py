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

if __name__ == "__main__":
    unittest.main()
