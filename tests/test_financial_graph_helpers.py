import unittest

from src.agent.financial_runtime_normalization import _display_operand_label
from src.agent.financial_retrieval_hints import (
    _active_preferred_sections,
    _preferred_calc_sections,
    _retrieval_hint_from_topic,
)


class FinancialGraphHelperTests(unittest.TestCase):
    def test_display_operand_label_removes_generic_company_year_prefix(self) -> None:
        self.assertEqual(
            _display_operand_label("\uc0bc\uc131\uc804\uc790 2023\ub144 \uc601\uc5c5\uc774\uc775"),
            "\uc601\uc5c5\uc774\uc775",
        )
        self.assertEqual(_display_operand_label("NAVER 2023\ub144 \ub9e4\ucd9c\uc561"), "\ub9e4\ucd9c\uc561")

    def test_display_operand_label_removes_leading_year(self) -> None:
        self.assertEqual(_display_operand_label("2023\ub144 \uc601\uc5c5\uc774\uc775"), "\uc601\uc5c5\uc774\uc775")

    def test_calc_sections_are_resolved_from_ontology(self) -> None:
        sections = _preferred_calc_sections(
            "2023\ub144 \uc124\ube44\ud22c\uc790 \ucd1d\uc561\uc744 \ucc3e\uc544\uc918.",
            "",
            "comparison",
        )

        self.assertIn("\uc6d0\uc7ac\ub8cc \ubc0f \uc0dd\uc0b0\uc124\ube44", sections)

    def test_retrieval_hint_is_resolved_from_ontology(self) -> None:
        hint = _retrieval_hint_from_topic(
            "2023\ub144 \uc124\ube44\ud22c\uc790 \ucd1d\uc561\uc744 \ucc3e\uc544\uc918.",
            "",
            "comparison",
        )

        self.assertIn("\uc124\ube44\ud22c\uc790", hint)

    def test_forward_looking_questions_use_caution_section_policy(self) -> None:
        query = "2026년 1분기 예상 영업이익과 판매량을 예측해 줘."

        hint = _retrieval_hint_from_topic(query, "", "qa")
        sections = _active_preferred_sections({}, query, "", "qa")

        self.assertIn("예측정보", hint)
        self.assertIn("예측정보에 대한 주의사항", sections)


if __name__ == "__main__":
    unittest.main()
