import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_helpers import _should_apply_strict_company_scope


class _EvidenceBiasProbe:
    _SECTION_BIAS_BY_QUERY_TYPE = FinancialAgent._SECTION_BIAS_BY_QUERY_TYPE
    _section_bias = FinancialAgent._section_bias


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


if __name__ == "__main__":
    unittest.main()
