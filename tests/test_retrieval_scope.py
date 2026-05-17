import unittest

from src.agent.financial_graph_helpers import _should_apply_strict_company_scope


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


if __name__ == "__main__":
    unittest.main()
