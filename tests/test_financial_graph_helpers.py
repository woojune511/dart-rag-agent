import unittest

from src.agent.financial_graph_helpers import _display_operand_label


class FinancialGraphHelperTests(unittest.TestCase):
    def test_display_operand_label_removes_generic_company_year_prefix(self) -> None:
        self.assertEqual(
            _display_operand_label("\uc0bc\uc131\uc804\uc790 2023\ub144 \uc601\uc5c5\uc774\uc775"),
            "\uc601\uc5c5\uc774\uc775",
        )
        self.assertEqual(_display_operand_label("NAVER 2023\ub144 \ub9e4\ucd9c\uc561"), "\ub9e4\ucd9c\uc561")

    def test_display_operand_label_removes_leading_year(self) -> None:
        self.assertEqual(_display_operand_label("2023\ub144 \uc601\uc5c5\uc774\uc775"), "\uc601\uc5c5\uc774\uc775")


if __name__ == "__main__":
    unittest.main()
