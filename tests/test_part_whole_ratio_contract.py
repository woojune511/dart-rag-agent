import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent.financial_graph import FinancialAgent, _build_semantic_numeric_plan
from src.agent.financial_graph_helpers import (
    _annotate_task_dependencies,
    _candidate_satisfies_direct_acceptance_contract,
)


class PartWholeRatioContractTests(unittest.TestCase):
    def test_explicit_part_whole_ratio_prefers_visible_concepts_over_generic_metric_family(self) -> None:
        dataset = json.loads(
            (PROJECT_ROOT / "benchmarks" / "datasets" / "single_doc_eval_full.curated.json").read_text(
                encoding="utf-8"
            )
        )
        question = next(row["question"] for row in dataset if row.get("id") == "CEL_T1_013")

        plan = _build_semantic_numeric_plan(
            question,
            question,
            "comparison",
            {"company": "celltrion", "year": 2023, "report_type": "annual"},
            "",
        )

        self.assertEqual(plan["status"], "concept_fallback")
        self.assertIn("explicit_ratio_concept_preferred", plan["planner_notes"])
        task = plan["tasks"][0]
        self.assertEqual(task["metric_family"], "concept_ratio")
        self.assertEqual(
            [(row["concept"], row["role"]) for row in task["required_operands"]],
            [
                ("research_and_development_expense", "denominator_1"),
                ("capitalized_development_cost", "numerator_1"),
            ],
        )
        self.assertNotIn("revenue", {row["concept"] for row in task["required_operands"]})

    def test_dependency_lookup_uses_part_whole_task_section_context_before_concept_defaults(self) -> None:
        dataset = json.loads(
            (PROJECT_ROOT / "benchmarks" / "datasets" / "single_doc_eval_full.curated.json").read_text(
                encoding="utf-8"
            )
        )
        question = next(row["question"] for row in dataset if row.get("id") == "CEL_T1_013")
        plan = _build_semantic_numeric_plan(
            question,
            question,
            "comparison",
            {"company": "celltrion", "year": 2023, "report_type": "annual"},
            "",
        )

        tasks = _annotate_task_dependencies(plan["tasks"], report_scope={"year": 2023})
        numerator_lookup = next(
            task
            for task in tasks
            if task.get("operation_family") == "lookup"
            and task.get("required_operands", [{}])[0].get("concept") == "capitalized_development_cost"
        )

        self.assertGreaterEqual(len(numerator_lookup["preferred_sections"]), 2)
        self.assertLess(
            numerator_lookup["preferred_sections"].index("II. 사업의 내용 > 6. 주요계약 및 연구개발활동"),
            numerator_lookup["preferred_sections"].index("무형자산"),
        )

    def test_operand_assembly_uses_table_value_context_for_sibling_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "ev_table_row",
                    "source_anchor": "[celltrion | 2023 | rnd]",
                    "raw_row_text": "연구개발비용 계 | 제33기 342,736,271 천원",
                    "claim": "연구개발비용 계 | 제33기 342,736,271 천원",
                    "metadata": {
                        "unit_hint": "천원",
                        "table_value_labels_text": (
                            "연구개발비용 계 342,736,271\n"
                            "판매비와 관리비 161,112,164\n"
                            "개발비(무형자산) 181,624,107"
                        ),
                    },
                }
            ],
            required_operands=[
                {
                    "label": "연구개발비용",
                    "concept": "research_and_development_expense",
                    "role": "denominator_1",
                    "unit_family": "KRW",
                    "aliases": ["연구개발비용 계"],
                },
                {
                    "label": "자본화된 개발비",
                    "concept": "capitalized_development_cost",
                    "role": "numerator_1",
                    "unit_family": "KRW",
                    "aliases": ["개발비(무형자산)"],
                },
            ],
            query="2023년 전체 연구개발비용 중 무형자산(개발비)으로 자본화된 금액의 비율을 계산해 줘.",
            report_scope={"year": 2023},
        )

        by_concept = {row["matched_operand_concept"]: row for row in rows}
        self.assertEqual(by_concept["research_and_development_expense"]["raw_value"], "342,736,271")
        self.assertEqual(by_concept["capitalized_development_cost"]["raw_value"], "181,624,107")

    def test_surface_unit_inference_does_not_override_known_unit_family(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "raw_value": "3,188,735",
            "raw_unit": "\ucc9c\uc6d0",
            "normalized_value": 3188735000.0,
            "normalized_unit": "KRW",
        }
        evidence_item = {
            "claim": "3,188,735 \uac1c\ubc1c\ube44",
            "metadata": {"unit_hint": "\ucc9c\uc6d0"},
        }

        coerced = agent._coerce_operand_row_from_evidence(row, evidence_item)

        self.assertEqual(coerced["raw_unit"], "\ucc9c\uc6d0")
        self.assertEqual(coerced["normalized_unit"], "KRW")

    def test_surface_contract_required_lookup_rejects_broad_column_only_match(self) -> None:
        operand = {
            "label": "\uc790\ubcf8\ud654\ub41c \uac1c\ubc1c\ube44",
            "concept": "capitalized_development_cost",
            "aliases": ["\uac1c\ubc1c\ube44", "\ubb34\ud615\uc790\uc0b0(\uac1c\ubc1c\ube44)"],
            "role": "primary_value",
            "unit_family": "KRW",
            "binding_policy": {"require_surface_contract_for_direct_lookup": True},
            "surface_contract": {
                "positive": ["\ubb34\ud615\uc790\uc0b0(\uac1c\ubc1c\ube44)", "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0)"],
                "negative": [],
            },
        }
        candidate = {
            "candidate_kind": "structured_value",
            "text": "\uac10\uac00\uc0c1\uac01\ube44, \uc720\ud615\uc790\uc0b0 | \uac1c\ubc1c\ube44 | 3,188,735",
            "metadata": {
                "semantic_label": "\uac10\uac00\uc0c1\uac01\ube44, \uc720\ud615\uc790\uc0b0",
                "semantic_aliases": ["\uac10\uac00\uc0c1\uac01\ube44, \uc720\ud615\uc790\uc0b0", "\uac1c\ubc1c\ube44"],
                "row_label": "\uac10\uac00\uc0c1\uac01\ube44, \uc720\ud615\uc790\uc0b0",
                "statement_type": "notes",
                "consolidation_scope": "consolidated",
                "period_focus": "current",
                "period_labels": ["2023"],
                "structured_cells": [
                    {
                        "column_headers": ["\uac1c\ubc1c\ube44"],
                        "value_text": "3,188,735",
                        "unit_hint": "\ucc9c\uc6d0",
                        "_report_year": 2023,
                    }
                ],
            },
        }

        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"period_focus": "current", "consolidation_scope": "consolidated"},
                query_years=[2023],
                operation_family="lookup",
                selected_cell={
                    "column_headers": ["\uac1c\ubc1c\ube44"],
                    "value_text": "3,188,735",
                    "unit_hint": "\ucc9c\uc6d0",
                    "_report_year": 2023,
                },
                report_scope={"company": "celltrion", "year": 2023, "report_type": "annual"},
            )
        )
        self.assertFalse(
            _candidate_satisfies_direct_acceptance_contract(
                candidate,
                operand=operand,
                constraints={"period_focus": "current", "consolidation_scope": "consolidated"},
                query_years=[2023],
                operation_family="ratio",
                selected_cell={
                    "column_headers": ["\uac1c\ubc1c\ube44"],
                    "value_text": "3,188,735",
                    "unit_hint": "\ucc9c\uc6d0",
                    "_report_year": 2023,
                },
                report_scope={"company": "celltrion", "year": 2023, "report_type": "annual"},
            )
        )

    def test_required_operand_assembly_requires_declared_surface_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {
            "label": "\uc790\ubcf8\ud654\ub41c \uac1c\ubc1c\ube44",
            "concept": "capitalized_development_cost",
            "aliases": ["\uac1c\ubc1c\ube44", "\ubb34\ud615\uc790\uc0b0(\uac1c\ubc1c\ube44)"],
            "role": "numerator_1",
            "unit_family": "KRW",
            "binding_policy": {"require_surface_contract_for_direct_match": True},
            "surface_contract": {
                "positive": ["\ubb34\ud615\uc790\uc0b0(\uac1c\ubc1c\ube44)", "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0)"],
                "negative": [],
            },
        }

        rows = agent._build_required_operands_from_candidates(
            [
                {
                    "evidence_id": "broad_only",
                    "source_anchor": "[company | 2023 | notes]",
                    "raw_row_text": "\uac10\uac00\uc0c1\uac01\ube44, \uc720\ud615\uc790\uc0b0 | \uac1c\ubc1c\ube44 | 3,188,735",
                    "claim": "\uac10\uac00\uc0c1\uac01\ube44, \uc720\ud615\uc790\uc0b0 | \uac1c\ubc1c\ube44 | 3,188,735",
                    "metadata": {
                        "unit_hint": "\ucc9c\uc6d0",
                        "table_value_labels_text": "\uac1c\ubc1c\uc911\uc778 \uac1c\ubc1c\ube44 96,993,303",
                    },
                }
            ],
            required_operands=[operand],
            query="2023 ratio",
            report_scope={"year": 2023},
        )

        self.assertEqual(rows, [])


if __name__ == "__main__":
    unittest.main()
