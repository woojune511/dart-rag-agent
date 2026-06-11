import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_helpers import _resolve_runtime_calculation_trace
from src.agent.financial_graph_planning import _refine_lookup_slot_unit_from_evidence


class AggregateSubtaskProjectionTests(unittest.TestCase):
    def test_active_lookup_promotes_matching_nested_result_from_aggregate(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        active_subtask = {
            "task_id": "task_prior",
            "metric_family": "concept_lookup",
            "metric_label": "2022 segment revenue",
            "operation_family": "lookup",
        }
        aggregate_result = {
            "status": "partial",
            "rendered_value": "2023 segment revenue is 100.",
            "answer_slots": {"operation_family": "aggregate_subtasks"},
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "answer": "2023 segment revenue is 100.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "100",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2023 segment revenue",
                                "period": "2023",
                                "raw_value": "100",
                                "normalized_value": 100,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "answer": "2022 segment revenue is 80.",
                    "status": "ok",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "80",
                        "formatted_result": "2022 segment revenue is 80.",
                        "answer_slots": {
                            "operation_family": "lookup",
                            "primary_value": {
                                "status": "ok",
                                "label": "2022 segment revenue",
                                "period": "2022",
                                "raw_value": "80",
                                "normalized_value": 80,
                                "normalized_unit": "KRW",
                            },
                        },
                    },
                },
            ],
        }

        answer, status, calculation_result = agent._promote_nested_subtask_result_if_more_specific(
            active_subtask=active_subtask,
            answer="2023 segment revenue is 100.",
            status="partial",
            calculation_result=aggregate_result,
        )

        self.assertEqual(answer, "2022 segment revenue is 80.")
        self.assertEqual(status, "ok")
        self.assertEqual(calculation_result["answer_slots"]["primary_value"]["period"], "2022")

    def test_dependency_rows_can_use_sibling_result_without_answer_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "revenue",
                        "period": "2023",
                        "label": "2023 segment revenue",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "operation_family": "lookup",
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 segment revenue",
                    "answer": "2023 segment revenue is 100.",
                    "calculation_result": {
                        "status": "ok",
                        "result_value": 100,
                        "result_unit": "KRW",
                        "rendered_value": "100",
                    },
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_role"], "current_period")
        self.assertEqual(rows[0]["normalized_value"], 100)

    def test_dependency_rows_synthesize_lookup_slot_from_subtask_answer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "prior_period",
                        "concept": "revenue",
                        "period": "2022",
                        "label": "segment revenue",
                        "preferred_task_id": "task_prior",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "role": "prior_period",
                            "concept": "revenue",
                            "period": "2022",
                            "label": "segment revenue",
                            "unit_family": "KRW",
                        }
                    ],
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_prior",
                    "metric_family": "concept_lookup",
                    "metric_label": "2022 segment revenue",
                    "answer": "2022 segment revenue was 1,801,079천원.",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2022 segment revenue was 1,801,079천원.",
                    },
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["matched_operand_role"], "prior_period")
        self.assertEqual(rows[0]["period"], "2022")

    def test_dependency_rows_synthesize_lookup_slot_with_billion_krw_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "active_subtask": {
                "task_id": "task_growth",
                "operation_family": "growth_rate",
                "inputs": [
                    {
                        "role": "current_period",
                        "concept": "provision_expense",
                        "period": "2023",
                        "label": "provision expense",
                        "preferred_task_id": "task_current",
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                    }
                ],
            },
            "calc_subtasks": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 provision expense",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "role": "current_period",
                            "concept": "provision_expense",
                            "period": "2023",
                            "label": "provision expense",
                            "unit_family": "KRW",
                        }
                    ],
                }
            ],
            "subtask_results": [
                {
                    "task_id": "task_current",
                    "metric_family": "concept_lookup",
                    "metric_label": "2023 provision expense",
                    "answer": "2023 provision expense was 3,146십억원.",
                    "calculation_result": {
                        "status": "ok",
                        "rendered_value": "2023 provision expense was 3,146십억원.",
                    },
                }
            ],
        }

        rows = agent._build_dependency_operand_rows(state)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["raw_value"], "3,146")
        self.assertEqual(rows[0]["raw_unit"], "십억원")
        self.assertEqual(rows[0]["normalized_unit"], "KRW")

    def test_lookup_unit_refinement_preserves_explicit_normalized_unit(self) -> None:
        slot = {
            "raw_value": "3,146",
            "raw_unit": "십억원",
            "normalized_value": 3_146_000_000_000.0,
            "normalized_unit": "KRW",
            "rendered_value": "3,146십억원",
        }
        evidence = {
            "claim": "nearby table text says 3,146억원",
            "metadata": {"table_value_labels_text": "metric 3,146억원"},
        }

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "십억원")
        self.assertEqual(refined["normalized_value"], 3_146_000_000_000.0)

    def test_dependency_projection_recalculates_from_stronger_source_task_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "calculate coverage ratio",
            "calc_subtasks": [
                {
                    "task_id": "task_source",
                    "metric_family": "concept_lookup",
                    "metric_label": "source metric",
                    "operation_family": "lookup",
                },
                {
                    "task_id": "task_ratio",
                    "metric_family": "concept_ratio",
                    "metric_label": "coverage ratio",
                    "operation_family": "ratio",
                },
            ],
        }
        ordered_results = [
            {
                "task_id": "task_source",
                "metric_family": "concept_lookup",
                "metric_label": "source metric",
                "operation_family": "lookup",
                "answer": "source metric 3,531,423백만원",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": 3_531_423_000_000.0,
                    "result_unit": "백만원",
                    "rendered_value": "3,531,423백만원",
                    "source_row_ids": ["recon::source"],
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "source metric",
                            "concept": "source_metric",
                            "period": "2023",
                            "raw_value": "3,531,423",
                            "raw_unit": "백만원",
                            "normalized_value": 3_531_423_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,531,423백만원",
                            "source_row_id": "recon::source",
                            "source_row_ids": ["recon::source"],
                            "source_anchor": "[source]",
                        },
                    },
                },
                "source_row_ids": ["recon::source"],
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "coverage ratio",
                "operation_family": "ratio",
                "answer": "coverage ratio is 0.0035배.",
                "status": "ok",
                "calculation_operands": [
                    {
                        "operand_id": "dep_task_source_001",
                        "evidence_id": "task_output:task_source",
                        "source_row_id": "task_output:task_source",
                        "source_row_ids": ["task_output:task_source", "ev_weak"],
                        "label": "source metric",
                        "raw_value": "3,531,423",
                        "raw_unit": "천원",
                        "normalized_value": 3_531_423_000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_label": "source metric",
                        "matched_operand_concept": "source_metric",
                        "matched_operand_role": "numerator_1",
                        "source_task_id": "task_source",
                        "dependency_resolved": True,
                    },
                    {
                        "operand_id": "denominator_001",
                        "evidence_id": "recon::denominator",
                        "source_row_id": "recon::denominator",
                        "source_row_ids": ["recon::denominator"],
                        "label": "denominator metric",
                        "raw_value": "1,000,000",
                        "raw_unit": "백만원",
                        "normalized_value": 1_000_000_000_000.0,
                        "normalized_unit": "KRW",
                        "period": "2023",
                        "matched_operand_label": "denominator metric",
                        "matched_operand_concept": "denominator_metric",
                        "matched_operand_role": "denominator_1",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["dep_task_source_001", "denominator_001"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "dep_task_source_001"},
                        {"variable": "B", "operand_id": "denominator_001"},
                    ],
                    "formula": "((A) / (B))",
                    "result_unit": "배",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": 0.003531423,
                    "result_unit": "배",
                    "rendered_value": "0.0035배",
                    "formatted_result": "coverage ratio is 0.0035배.",
                },
                "source_row_ids": ["task_output:task_source", "ev_weak", "recon::denominator"],
            },
        ]
        aggregate_projection = agent._build_aggregate_calculation_projection(ordered_results, "coverage ratio is 0.0035배.")

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        numerator = ratio_row["calculation_operands"][0]
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(numerator["raw_unit"], "백만원")
        self.assertEqual(numerator["normalized_value"], 3_531_423_000_000.0)
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "3.5314배")
        self.assertIn("recon::source", numerator["source_row_ids"])

    def test_dependency_projection_recalculates_planless_ratio_from_best_lookup_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_other_numerator",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator",
                            "label": "other numerator",
                            "concept": "other_numerator",
                            "raw_value": "900",
                            "raw_unit": "million",
                            "normalized_value": 900_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_other",
                        },
                    },
                },
            },
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator",
                            "label": "target numerator",
                            "concept": "target_numerator",
                            "raw_value": "180",
                            "raw_unit": "million",
                            "normalized_value": 180_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_strong_numerator",
                            "source_row_ids": ["row_strong_numerator"],
                            "value_role": "aggregate",
                            "aggregation_stage": "final",
                        },
                    },
                },
            },
            {
                "task_id": "task_denominator",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "denominator",
                            "label": "target denominator",
                            "concept": "target_denominator",
                            "raw_value": "2,000",
                            "raw_unit": "million",
                            "normalized_value": 2_000_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_denominator",
                            "source_row_ids": ["row_denominator"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "margin drag",
                "operation_family": "ratio",
                "answer": "margin drag is 7.50%p.",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": 7.5,
                    "result_unit": "%p",
                    "rendered_value": "7.50%p",
                    "formatted_result": "margin drag is 7.50%p.",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "margin drag",
                        "components_by_role": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator",
                                    "label": "target numerator",
                                    "concept": "target_numerator",
                                    "raw_value": "150",
                                    "raw_unit": "million",
                                    "normalized_value": 150_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_detail_numerator",
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator",
                                    "label": "target denominator",
                                    "concept": "target_denominator",
                                    "raw_value": "2,000",
                                    "raw_unit": "million",
                                    "normalized_value": 2_000_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_denominator",
                                }
                            ],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate margin drag",
                "calc_subtasks": [
                    {"task_id": "task_other_numerator", "operation_family": "lookup"},
                    {"task_id": "task_numerator", "operation_family": "lookup"},
                    {"task_id": "task_denominator", "operation_family": "lookup"},
                    {"task_id": "task_ratio", "operation_family": "ratio", "metric_label": "margin drag"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "9.00%p")
        numerator = ratio_row["calculation_operands"][0]
        self.assertEqual(numerator["raw_value"], "180")
        self.assertIn("task_output:task_numerator", numerator["source_row_ids"])
        self.assertNotIn("900", ratio_row["answer"])

    def test_lookup_execution_applies_ontology_magnitude_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "lookup translated gain",
            "active_subtask": {
                "task_id": "task_gain",
                "metric_family": "concept_lookup",
                "metric_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                "operation_family": "lookup",
            },
            "calculation_operands": [
                {
                    "operand_id": "op_gain",
                    "evidence_id": "gain_cell",
                    "source_row_id": "gain_cell",
                    "source_row_ids": ["gain_cell"],
                    "label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                    "raw_value": "(573,884)",
                    "raw_unit": "\ubc31\ub9cc\uc6d0",
                    "normalized_value": -573_884_000_000.0,
                    "normalized_unit": "KRW",
                    "matched_operand_label": "\uc678\ud654\ud658\uc0b0\uc774\uc775",
                    "matched_operand_concept": "foreign_currency_translation_gain",
                    "matched_operand_role": "operand",
                    "statement_type": "notes",
                }
            ],
            "calculation_plan": {
                "status": "ok",
                "mode": "single_value",
                "operation": "lookup",
                "ordered_operand_ids": ["op_gain"],
                "variable_bindings": [{"variable": "A", "operand_id": "op_gain"}],
                "formula": "A",
                "result_unit": "\ubc31\ub9cc\uc6d0",
            },
        }
        state["resolved_calculation_trace"] = {
            "calculation_operands": list(state.get("calculation_operands") or []),
            "calculation_plan": dict(state.get("calculation_plan") or {}),
            "calculation_result": {},
        }

        result = agent._execute_calculation(state)
        trace = _resolve_runtime_calculation_trace(result)
        calculation_result = trace["calculation_result"]
        operand = trace["calculation_operands"][0]

        self.assertEqual(operand["normalized_value"], 573_884_000_000.0)
        self.assertEqual(operand["rendered_value"], "573,884\ubc31\ub9cc\uc6d0")
        self.assertEqual(calculation_result["result_value"], 573_884_000_000.0)
        self.assertEqual(calculation_result["rendered_value"], "573,884\ubc31\ub9cc\uc6d0")

    def test_growth_narrative_prefers_uncovered_parenthetical_focus_variant(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = "calculate 2023 growth and summarize Acme(FooBar) impact"
        rows = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment revenue growth",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "25%",
                            "normalized_value": 25,
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2023",
                            "rendered_value": "125억원",
                            "normalized_value": 12_500_000_000,
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2022",
                            "rendered_value": "100억원",
                            "normalized_value": 10_000_000_000,
                        },
                    },
                },
            },
            {
                "task_id": "task_summary",
                "metric_family": "narrative_summary",
                "metric_label": "impact summary",
                "status": "ok",
                "answer": (
                    "Revenue impact was broad. "
                    "FooBar impact came from integration and operating improvements."
                ),
                "calculation_result": {"operation_family": "narrative_summary"},
            },
        ]

        answer = agent._compose_growth_narrative_answer(
            query=query,
            ordered_results=rows,
            existing_answer="2023 segment revenue was 125억원 versus 100억원, up 25%.",
            evidence_items=[],
        )

        self.assertIsNotNone(answer)
        self.assertIn("FooBar impact", answer["compressed_answer"])

    def test_growth_narrative_preserves_supported_focus_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        query = "calculate 2023 growth and summarize Acme(FooBar) impact"
        rows = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "segment revenue growth",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "25%",
                            "normalized_value": 25,
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2023",
                            "rendered_value": "125",
                            "normalized_value": 125,
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "segment revenue",
                            "period": "2022",
                            "rendered_value": "100",
                            "normalized_value": 100,
                        },
                    },
                },
            },
            {
                "task_id": "task_summary",
                "metric_family": "narrative_summary",
                "metric_label": "impact summary",
                "status": "ok",
                "answer": (
                    "Revenue impact was broad. "
                    "FooBar impact came from operating improvements. "
                    "Additional impact came from consolidation."
                ),
                "calculation_result": {"operation_family": "narrative_summary"},
            },
        ]

        answer = agent._compose_growth_narrative_answer(
            query=query,
            ordered_results=rows,
            existing_answer=(
                "2023 segment revenue was 125 versus 2022 100, up 25%. "
                "FooBar impact came from operating improvements."
            ),
            evidence_items=[],
        )

        self.assertIsNotNone(answer)
        self.assertIn("Additional impact came from consolidation.", answer["compressed_answer"])

    def test_lookup_unit_refinement_prefers_value_local_unit(self) -> None:
        slot = {
            "raw_value": "2,546,649",
            "raw_unit": "천원",
            "normalized_value": 2_546_649_000,
            "normalized_unit": "KRW",
            "rendered_value": "2,546,649천원",
        }
        evidence = {
            "claim": "2,546,649 (천원)",
            "metadata": {"unit_hint": "백만원"},
        }

        refined = _refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertEqual(refined["raw_unit"], "천원")
        self.assertEqual(refined["normalized_value"], 2_546_649_000)

    def test_compact_ratio_answer_lists_all_component_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "rendered_value": "42.02%",
            "answer_slots": {
                "operation_family": "ratio",
                "metric_label": "asset funding ratio",
                "primary_value": {"status": "ok", "rendered_value": "42.02%"},
                "components_by_group": {
                    "numerator": [
                        {"label": "short borrowing", "rendered_value": "4,145백만원", "normalized_value": 4_145_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                        {"label": "long borrowing", "rendered_value": "10,121백만원", "normalized_value": 10_121_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                        {"label": "bonds", "rendered_value": "9,490백만원", "normalized_value": 9_490_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                    ],
                    "denominator": [
                        {"label": "tangible assets", "rendered_value": "52,704백만원", "normalized_value": 52_704_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                        {"label": "intangible assets", "rendered_value": "3,834백만원", "normalized_value": 3_834_000_000, "normalized_unit": "KRW", "raw_unit": "백만원"},
                    ],
                },
            },
        }

        answer = agent._compact_ratio_answer({"active_subtask": {"metric_label": "asset funding ratio"}}, calculation_result)

        self.assertIn("asset funding ratio", answer)
        self.assertIn("short borrowing 4,145백만원", answer)
        self.assertIn("long borrowing 10,121백만원", answer)
        self.assertIn("bonds 9,490백만원", answer)
        self.assertIn("tangible assets 52,704백만원", answer)
        self.assertIn("intangible assets 3,834백만원", answer)

    def test_preferred_complete_numeric_answer_joins_multiple_ratio_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        def ratio_row(task_id: str, label: str, value: str, numerator: str, denominator: str) -> dict:
            return {
                "task_id": task_id,
                "metric_family": "concept_ratio",
                "metric_label": label,
                "operation_family": "ratio",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": value,
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": label,
                        "primary_value": {"status": "ok", "rendered_value": value},
                        "components_by_group": {
                            "numerator": [
                                {"label": f"{label} numerator", "rendered_value": numerator, "normalized_value": 1, "normalized_unit": "KRW", "raw_unit": "백만원"},
                            ],
                            "denominator": [
                                {"label": f"{label} denominator", "rendered_value": denominator, "normalized_value": 1, "normalized_unit": "KRW", "raw_unit": "백만원"},
                            ],
                        },
                    },
                },
            }

        answer = agent._preferred_complete_numeric_answer(
            [
                ratio_row("task_a", "debt ratio", "25.36%", "10백만원", "40백만원"),
                ratio_row("task_b", "current ratio", "258.77%", "259백만원", "100백만원"),
            ]
        )

        self.assertIn("debt ratio", answer)
        self.assertIn("25.36%", answer)
        self.assertIn("current ratio", answer)
        self.assertIn("258.77%", answer)

    def test_numeric_answer_coverage_requires_all_trace_values(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        self.assertFalse(
            agent._answer_covers_numeric_answer(
                "The final answer is 258.77% using 259백만원 and 100백만원.",
                "Debt ratio is 25.36%. Current ratio is 258.77%.",
            )
        )
        self.assertTrue(
            agent._answer_covers_numeric_answer(
                "Debt ratio is 25.4%. Current ratio is 258.77%.",
                "Debt ratio is 25.36%. Current ratio is 258.77%.",
            )
        )


if __name__ == "__main__":
    unittest.main()
