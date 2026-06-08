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

    def test_lookup_direct_support_requires_positive_surface_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
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
        broad_row = {
            "label": "\uc790\ubcf8\ud654\ub41c \uac1c\ubc1c\ube44",
            "matched_operand_concept": "capitalized_development_cost",
            "raw_value": "3,188,735",
            "raw_unit": "\ucc9c\uc6d0",
            "normalized_value": 3188735000.0,
            "normalized_unit": "KRW",
            "source_anchor": "[celltrion | 2023 | notes]",
        }
        broad_evidence = {
            "claim": "\uac1c\ubc1c\ube44 | 3,188,735",
            "quote_span": "\uac1c\ubc1c\ube44 | 3,188,735",
            "metadata": {"unit_hint": "\ucc9c\uc6d0"},
        }
        contracted_evidence = {
            "claim": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0) | 181,624,107 \ucc9c\uc6d0",
            "quote_span": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0) | 181,624,107 \ucc9c\uc6d0",
            "metadata": {"unit_hint": "\ucc9c\uc6d0"},
        }
        contracted_row = {**broad_row, "raw_value": "181,624,107", "normalized_value": 181624107000.0}

        self.assertFalse(agent._llm_lookup_operand_has_direct_support(broad_row, broad_evidence, [operand]))
        self.assertTrue(agent._llm_lookup_operand_has_direct_support(contracted_row, contracted_evidence, [operand]))

    def test_direct_lookup_score_requires_positive_surface_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {
            "label": "\uc790\ubcf8\ud654\ub41c \uac1c\ubc1c\ube44",
            "concept": "capitalized_development_cost",
            "aliases": ["\uac1c\ubc1c\ube44", "\ubb34\ud615\uc790\uc0b0(\uac1c\ubc1c\ube44)", "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0)"],
            "role": "primary_value",
            "unit_family": "KRW",
            "binding_policy": {
                "require_surface_contract_for_direct_match": True,
                "require_surface_contract_for_direct_lookup": True,
            },
            "surface_contract": {
                "positive": ["\ubb34\ud615\uc790\uc0b0(\uac1c\ubc1c\ube44)", "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0)"],
                "negative": [],
            },
        }
        broad_evidence = {
            "claim": "\uac1c\ubc1c\ube44 | 3,188,735",
            "quote_span": "\uac1c\ubc1c\ube44 | 3,188,735",
            "metadata": {
                "row_label": "\uac1c\ubc1c\ube44",
                "semantic_label": "\uac1c\ubc1c\ube44",
                "unit_hint": "\ucc9c\uc6d0",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "3,188,735", "unit_hint": "\ucc9c\uc6d0"}
                ],
            },
        }
        contracted_evidence = {
            "claim": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0) | 181,624,107 \ucc9c\uc6d0",
            "quote_span": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0) | 181,624,107 \ucc9c\uc6d0",
            "metadata": {
                "row_label": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0)",
                "semantic_label": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0)",
                "unit_hint": "\ucc9c\uc6d0",
                "structured_cells": [
                    {"column_headers": ["2023"], "value_text": "181,624,107", "unit_hint": "\ucc9c\uc6d0"}
                ],
            },
        }

        self.assertEqual(agent._direct_structured_lookup_evidence_score(operand, broad_evidence), 0.0)
        self.assertGreaterEqual(agent._direct_structured_lookup_evidence_score(operand, contracted_evidence), 6.0)

    def test_dependency_row_prefers_better_structured_slot_when_value_surface_matches(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        binding_operand = {
            "label": "\uc601\uc5c5\uc774\uc775",
            "concept": "operating_income",
            "role": "numerator_1",
            "unit_family": "KRW",
            "source_preference": ["task_output", "retrieval"],
            "preferred_task_id": "task_2",
            "source_slot": "primary_value",
            "period": "2023",
        }
        state = {
            "active_subtask": {
                "task_id": "task_1",
                "operation_family": "ratio",
                "inputs": [binding_operand],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "metric_label": "\uc601\uc5c5\uc774\uc775",
                    "calculation_result": {
                        "answer_slots": {
                            "primary_value": {
                                "status": "ok",
                                "label": "\uc601\uc5c5\uc774\uc775",
                                "concept": "operating_income",
                                "period": "2023",
                                "raw_value": "3,531,423",
                                "raw_unit": "\ucc9c\uc6d0",
                                "normalized_value": 3531423000.0,
                                "normalized_unit": "KRW",
                                "source_row_id": "ev_weak",
                                "source_row_ids": ["ev_weak"],
                                "source_anchor": "[posco | 2023 | notes]",
                            }
                        },
                        "source_row_ids": ["ev_weak"],
                    },
                    "runtime_evidence": [
                        {
                            "evidence_id": "ev_weak",
                            "claim": "3,531,423 (\ucc9c\uc6d0)",
                            "quote_span": "3,531,423",
                            "metadata": {"unit_hint": "\ubc31\ub9cc\uc6d0"},
                            "source_anchor": "[posco | 2023 | notes]",
                        }
                    ],
                }
            ],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_strong",
                    "claim": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ubc31\ub9cc\uc6d0",
                    "quote_span": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ubc31\ub9cc\uc6d0",
                    "metadata": {
                        "row_label": "\uc601\uc5c5\uc774\uc775",
                        "semantic_label": "\uc601\uc5c5\uc774\uc775",
                        "unit_hint": "\ubc31\ub9cc\uc6d0",
                        "year": 2023,
                        "structured_cells": [
                            {
                                "column_headers": ["2023"],
                                "value_text": "3,531,423",
                                "unit_hint": "\ubc31\ub9cc\uc6d0",
                            }
                        ],
                    },
                    "source_anchor": "[posco | 2023 | summary]",
                }
            ],
            "evidence_items": [],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_unit"], "\ubc31\ub9cc\uc6d0")
        self.assertEqual(rows[0]["normalized_value"], 3531423000000.0)
        self.assertIn("ev_strong", rows[0]["source_row_ids"])

    def test_required_surface_contract_applies_to_ratio_operand_rows(self) -> None:
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
        broad_row = {
            "label": "\uc790\ubcf8\ud654\ub41c \uac1c\ubc1c\ube44",
            "matched_operand_concept": "capitalized_development_cost",
            "matched_operand_role": "numerator_1",
            "raw_value": "3,188,735",
            "raw_unit": "\ucc9c\uc6d0",
            "source_row_id": "ev_broad",
            "source_row_ids": ["ev_broad"],
        }
        contracted_row = {
            **broad_row,
            "raw_value": "181,624,107",
            "source_row_id": "ev_contract",
            "source_row_ids": ["ev_contract"],
        }
        evidence_by_id = {
            "ev_broad": {
                "evidence_id": "ev_broad",
                "claim": "\uac1c\ubc1c\ube44 | 3,188,735",
                "quote_span": "\uac1c\ubc1c\ube44 | 3,188,735",
            },
            "ev_contract": {
                "evidence_id": "ev_contract",
                "claim": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0) | 181,624,107 \ucc9c\uc6d0",
                "quote_span": "\uac1c\ubc1c\ube44(\ubb34\ud615\uc790\uc0b0) | 181,624,107 \ucc9c\uc6d0",
            },
        }

        self.assertFalse(
            agent._operand_row_satisfies_required_surface_contract(broad_row, evidence_by_id, [operand])
        )
        self.assertTrue(
            agent._operand_row_satisfies_required_surface_contract(contracted_row, evidence_by_id, [operand])
        )

    def test_lookup_recovery_replaces_same_raw_value_when_unit_differs(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {
            "label": "\uc601\uc5c5\uc774\uc775",
            "concept": "operating_income",
            "role": "primary_value",
            "unit_family": "KRW",
            "period": "2023",
        }
        ordered_results = [
            {
                "task_id": "task_2",
                "operation_family": "lookup",
                "status": "ok",
                "metric_label": "\uc601\uc5c5\uc774\uc775",
                "calculation_result": {
                    "answer_slots": {
                        "primary_value": {
                            "label": "\uc601\uc5c5\uc774\uc775",
                            "concept": "operating_income",
                            "raw_value": "3,531,423",
                            "raw_unit": "\ucc9c\uc6d0",
                            "normalized_value": 3531423000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_weak",
                            "source_row_ids": ["ev_weak"],
                        }
                    }
                },
            }
        ]
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_2",
                    "operation_family": "lookup",
                    "required_operands": [operand],
                }
            ],
            "runtime_evidence": [
                {
                    "evidence_id": "ev_weak",
                    "claim": "\uc601\uc5c5\uc774\uc775 | 3,531,423 \ucc9c\uc6d0",
                    "quote_span": "\uc601\uc5c5\uc774\uc775 | 3,531,423 \ucc9c\uc6d0",
                    "metadata": {"unit_hint": "\ucc9c\uc6d0"},
                },
                {
                    "evidence_id": "ev_strong",
                    "claim": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ubc31\ub9cc\uc6d0",
                    "quote_span": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ubc31\ub9cc\uc6d0",
                    "metadata": {
                        "row_label": "\uc601\uc5c5\uc774\uc775",
                        "semantic_label": "\uc601\uc5c5\uc774\uc775",
                        "unit_hint": "\ubc31\ub9cc\uc6d0",
                        "year": 2023,
                        "structured_cells": [
                            {
                                "column_headers": ["2023"],
                                "value_text": "3,531,423",
                                "unit_hint": "\ubc31\ub9cc\uc6d0",
                            }
                        ],
                    },
                },
            ],
        }

        recovered = agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["raw_unit"], "\ubc31\ub9cc\uc6d0")
        self.assertEqual(slot["normalized_value"], 3531423000000.0)

    def test_ratio_direct_rows_prefer_peer_unit_aligned_structured_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {
                "label": "\uc601\uc5c5\uc774\uc775",
                "concept": "operating_income",
                "role": "numerator_1",
                "unit_family": "KRW",
                "period": "2023",
            },
            {
                "label": "\uc774\uc790\ube44\uc6a9",
                "concept": "interest_expense",
                "role": "denominator_1",
                "unit_family": "KRW",
                "period": "2023",
            },
        ]
        direct_rows = [
            {
                "operand_id": "op_001",
                "label": "\uc601\uc5c5\uc774\uc775",
                "matched_operand_concept": "operating_income",
                "matched_operand_role": "numerator_1",
                "raw_value": "3,531,423",
                "raw_unit": "\ucc9c\uc6d0",
                "normalized_value": 3531423000.0,
                "normalized_unit": "KRW",
                "source_row_id": "ev_weak",
                "source_row_ids": ["ev_weak"],
            },
            {
                "operand_id": "op_002",
                "label": "\uc774\uc790\ube44\uc6a9",
                "matched_operand_concept": "interest_expense",
                "matched_operand_role": "denominator_1",
                "raw_value": "1,001,290",
                "raw_unit": "\ubc31\ub9cc\uc6d0",
                "normalized_value": 1001290000000.0,
                "normalized_unit": "KRW",
                "source_row_id": "ev_denominator",
                "source_row_ids": ["ev_denominator"],
            },
        ]
        evidence_items = [
            {
                "evidence_id": "ev_weak",
                "claim": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ucc9c\uc6d0",
                "quote_span": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ucc9c\uc6d0",
                "metadata": {
                    "row_label": "\uc601\uc5c5\uc774\uc775",
                    "semantic_label": "\uc601\uc5c5\uc774\uc775",
                    "unit_hint": "\ucc9c\uc6d0",
                    "year": 2023,
                    "structured_cells": [
                        {
                            "column_headers": ["2023"],
                            "value_text": "3,531,423",
                            "unit_hint": "\ucc9c\uc6d0",
                        }
                    ],
                },
            },
            {
                "evidence_id": "ev_strong",
                "claim": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ubc31\ub9cc\uc6d0",
                "quote_span": "\uc601\uc5c5\uc774\uc775 | 2023 3,531,423 \ubc31\ub9cc\uc6d0",
                "metadata": {
                    "row_label": "\uc601\uc5c5\uc774\uc775",
                    "semantic_label": "\uc601\uc5c5\uc774\uc775",
                    "unit_hint": "\ubc31\ub9cc\uc6d0",
                    "year": 2023,
                    "structured_cells": [
                        {
                            "column_headers": ["2023"],
                            "value_text": "3,531,423",
                            "unit_hint": "\ubc31\ub9cc\uc6d0",
                        }
                    ],
                },
            },
            {
                "evidence_id": "ev_denominator",
                "claim": "\uc774\uc790\ube44\uc6a9 | 2023 1,001,290 \ubc31\ub9cc\uc6d0",
                "quote_span": "\uc774\uc790\ube44\uc6a9 | 2023 1,001,290 \ubc31\ub9cc\uc6d0",
                "metadata": {
                    "row_label": "\uc774\uc790\ube44\uc6a9",
                    "semantic_label": "\uc774\uc790\ube44\uc6a9",
                    "unit_hint": "\ubc31\ub9cc\uc6d0",
                    "year": 2023,
                    "structured_cells": [
                        {
                            "column_headers": ["2023"],
                            "value_text": "1,001,290",
                            "unit_hint": "\ubc31\ub9cc\uc6d0",
                        }
                    ],
                },
            },
        ]

        refined_rows = agent._prefer_direct_structured_evidence_rows(
            direct_rows,
            evidence_items=evidence_items,
            required_operands=required_operands,
            operation_family="ratio",
            state={"active_subtask": {"operation_family": "ratio"}},
        )

        numerator = refined_rows[0]
        self.assertEqual(numerator["source_row_id"], "ev_strong")
        self.assertEqual(numerator["raw_unit"], "\ubc31\ub9cc\uc6d0")
        self.assertEqual(numerator["normalized_value"], 3531423000000.0)

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
