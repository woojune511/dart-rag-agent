import unittest
from types import SimpleNamespace

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_calculation import _evidence_item_conflicts_requested_scope
from src.agent.financial_graph_helpers import _resolve_runtime_calculation_trace
from src.agent.financial_graph_planning import _refine_lookup_slot_unit_from_evidence


class AggregateSubtaskProjectionTests(unittest.TestCase):
    def test_ordered_aggregate_subtask_results_for_repair_preserves_trace_priority(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "subtask_results": [
                {"task_id": "task_growth", "answer": "fresh trace growth", "status": "ok"},
            ]
        }
        answer_slots = {
            "subtask_results": [
                {"task_id": "task_growth", "answer": "slot duplicate growth", "status": "ok"},
                {"task_id": "task_narrative", "answer": "slot narrative", "status": "ok"},
            ]
        }
        state = {
            "structured_result": {
                "subtask_results": [
                    {"task_id": "task_narrative", "answer": "structured duplicate narrative", "status": "ok"},
                    {"task_id": "task_lookup", "answer": "structured lookup", "status": "ok"},
                ]
            },
            "subtask_results": [
                {"task_id": "task_growth", "answer": "stale state growth", "status": "ok"},
                {"task_id": "task_lookup", "answer": "stale state lookup", "status": "ok"},
            ],
        }

        ordered = agent._ordered_aggregate_subtask_results_for_repair(
            state=state,
            calculation_result=calculation_result,
            answer_slots=answer_slots,
        )

        self.assertEqual(
            [(row["task_id"], row["answer"]) for row in ordered],
            [
                ("task_growth", "fresh trace growth"),
                ("task_narrative", "slot narrative"),
                ("task_lookup", "structured lookup"),
            ],
        )

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

    def test_dependency_projection_does_not_cross_ratio_role_groups(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "numerator_1",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "ok",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_numerator",
                        "source_row_ids": ["task_output:task_numerator", "row_segment"],
                        "source_task_id": "task_numerator",
                        "label": "segment operating income",
                        "raw_value": "(581,816)",
                        "raw_unit": "million",
                        "normalized_value": -581_816_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                    },
                    {
                        "operand_id": "den",
                        "source_row_id": "row_total",
                        "source_row_ids": ["row_total"],
                        "label": "total operating income",
                        "raw_value": "1,903,886",
                        "raw_unit": "million",
                        "normalized_value": 1_903_886_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "denominator_1",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "((A) / (B)) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {
                    "status": "ok",
                    "result_value": 30.56,
                    "result_unit": "%",
                    "rendered_value": "30.56%",
                    "formatted_result": "segment share is 30.56%.",
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share",
                "calc_subtasks": [
                    {"task_id": "task_numerator", "operation_family": "lookup"},
                    {"task_id": "task_ratio", "operation_family": "ratio"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "1,903,886")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "30.56%")

    def test_stale_difference_result_repairs_from_current_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operands = [
            {
                "operand_id": "op_a",
                "label": "current value",
                "raw_value": "1000",
                "raw_unit": "",
                "normalized_value": 1000.0,
                "normalized_unit": "COUNT",
                "matched_operand_role": "minuend",
            },
            {
                "operand_id": "op_b",
                "label": "adjustment",
                "raw_value": "250",
                "raw_unit": "",
                "normalized_value": 250.0,
                "normalized_unit": "COUNT",
                "matched_operand_role": "subtrahend",
            },
        ]
        plan = {
            "status": "ok",
            "mode": "single_value",
            "operation": "subtract",
            "ordered_operand_ids": ["op_a", "op_b"],
            "variable_bindings": [
                {"variable": "A", "operand_id": "op_a"},
                {"variable": "B", "operand_id": "op_b"},
            ],
            "formula": "A - B",
            "result_unit": "",
        }

        repaired_operands, repaired_plan, repaired_result = agent._repair_stale_calculation_result_from_operands(
            {
                "query": "calculate adjusted value",
                "active_subtask": {
                    "task_id": "task_difference",
                    "metric_family": "concept_difference",
                    "metric_label": "adjusted value",
                    "operation_family": "difference",
                },
            },
            operands=operands,
            plan=plan,
            calculation_result={
                "status": "ok",
                "result_value": 990.0,
                "result_unit": "",
                "rendered_value": "990",
            },
        )

        self.assertEqual(repaired_operands, operands)
        self.assertEqual(repaired_plan, plan)
        self.assertEqual(repaired_result["result_value"], 750.0)
        self.assertTrue(repaired_result["stale_result_repaired_from_operands"])

    def test_dependency_output_preserves_consistent_krw_unit_over_table_hint(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        numerator = 1_992_636_000_000.0
        denominator = 9_670_643_576_585.0
        state = {
            "query": "calculate expense to revenue ratio",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "expense ratio",
                "operation_family": "ratio",
            },
            "evidence_items": [
                {
                    "evidence_id": "ev_denominator",
                    "raw_row_text": "revenue 9,670,643,576,585",
                    "metadata": {
                        "block_type": "table",
                        "unit_hint": "천원",
                        "table_value_labels_text": "revenue 9,670,643,576,585",
                    },
                }
            ],
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "op_numerator",
                        "label": "expense",
                        "raw_value": "1,992,636",
                        "raw_unit": "백만원",
                        "normalized_value": numerator,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "numerator",
                    },
                    {
                        "operand_id": "op_denominator",
                        "label": "revenue",
                        "raw_value": "9,670,643,576,585",
                        "raw_unit": "원",
                        "normalized_value": denominator,
                        "normalized_unit": "KRW",
                        "matched_operand_role": "denominator",
                        "source_row_id": "task_output:task_revenue",
                        "source_row_ids": ["task_output:task_revenue", "ev_denominator"],
                        "dependency_resolved": True,
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["op_numerator", "op_denominator"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "op_numerator"},
                        {"variable": "B", "operand_id": "op_denominator"},
                    ],
                    "formula": "((A) / (B)) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {},
            },
        }

        result_state = agent._execute_calculation(state)
        trace = result_state["resolved_calculation_trace"]
        result = trace["calculation_result"]
        denominator_row = next(
            row for row in trace["calculation_operands"] if row["operand_id"] == "op_denominator"
        )

        self.assertAlmostEqual(result["result_value"], (numerator / denominator) * 100, places=6)
        self.assertEqual(denominator_row["raw_unit"], "원")
        self.assertEqual(denominator_row["normalized_value"], denominator)

    def test_formula_task_can_recover_direct_target_metric_row(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_target",
            "source_anchor": "[company | year | management discussion]",
            "claim": "target metric 1,701,152",
            "quote_span": "target metric 1,701,152",
            "metadata": {
                "block_type": "table",
                "row_label": "target metric",
                "semantic_label": "target metric",
                "unit_hint": "백만원",
                "year": 2023,
                "structured_cells": [
                    {
                        "value_text": "1,701,152",
                        "unit_hint": "백만원",
                        "column_headers": ["2023"],
                    }
                ],
            },
        }

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                }
            },
            [evidence],
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["raw_unit"], "백만원")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_formula_task_can_recover_direct_target_metric_from_retrieved_doc_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        doc = SimpleNamespace(
            page_content="target metric 1,701,152",
            metadata={
                "section_path": "management discussion",
                "block_type": "table",
                "row_label": "target metric",
                "semantic_label": "target metric",
                "unit_hint": "백만원",
                "year": 2023,
                "structured_cells": [
                    {
                        "value_text": "1,701,152",
                        "unit_hint": "백만원",
                        "column_headers": ["2023"],
                    }
                ],
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs([(doc, 1.0)], max_docs=1)

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                }
            },
            evidence_pool,
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["raw_unit"], "백만원")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_formula_task_can_recover_direct_target_metric_from_table_value_labels(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065 | 398,087",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_row_labels_text": "증감\ntarget metric\noperating income",
                "table_value_labels_text": (
                    "target metric 1,701,152\n"
                    "target metric 1,303,065\n"
                    "target metric 398,087\n"
                    "operating income 1,163,112"
                ),
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs([(doc, 1.0)], max_docs=1)

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                }
            },
            evidence_pool,
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["raw_unit"], "백만원")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_direct_target_metric_prefers_context_matching_consolidation_scope(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        generic_doc = SimpleNamespace(
            page_content="target metric | 43,248 | 52,927 | -9,679",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "major performance indicators",
                "table_row_labels_text": "증감\ntarget metric",
                "table_value_labels_text": "target metric 43,248\ntarget metric 52,927\ntarget metric -9,679",
            },
        )
        consolidated_doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065 | 398,087",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "연결 영업실적",
                "table_context": "연결회사의 주요 경영지표",
                "table_row_labels_text": "증감\ntarget metric",
                "table_value_labels_text": (
                    "target metric 1,701,152\n"
                    "target metric 1,303,065\n"
                    "target metric 398,087"
                ),
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs(
            [(generic_doc, 1.0), (consolidated_doc, 0.9)],
            max_docs=2,
        )

        row, _operand = agent._direct_target_metric_operand_from_evidence(
            {
                "query": "2023년 연결기준 target metric을 답해 줘.",
                "report_scope": {},
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "concept_sum",
                    "metric_label": "target metric",
                    "operation_family": "sum",
                },
            },
            evidence_pool,
        )

        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertEqual(row["normalized_value"], 1_701_152_000_000.0)

    def test_scope_filter_uses_table_context_for_unknown_metadata_scope(self) -> None:
        matching_context = {
            "metadata": {
                "consolidation_scope": "unknown",
                "section_path": "management discussion",
                "local_heading": "operating performance",
                "table_context": "연결 기준 주요 지표",
            }
        }
        opposing_context = {
            "metadata": {
                "consolidation_scope": "unknown",
                "section_path": "management discussion",
                "local_heading": "별도 기준 주요 지표",
            }
        }

        self.assertFalse(_evidence_item_conflicts_requested_scope(matching_context, "consolidated"))
        self.assertTrue(_evidence_item_conflicts_requested_scope(opposing_context, "consolidated"))

    def test_lookup_preference_uses_requested_scope_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        current_rows = [
            {
                "operand_id": "primary_value",
                "evidence_id": "ev_generic",
                "source_row_id": "ev_generic",
                "source_row_ids": ["ev_generic"],
                "label": "target metric",
                "raw_value": "43,248",
                "raw_unit": "백만원",
                "normalized_value": 43_248_000_000.0,
                "normalized_unit": "KRW",
                "matched_operand_label": "target metric",
                "matched_operand_role": "primary_value",
            }
        ]
        evidence_items = [
            {
                "evidence_id": "ev_generic",
                "claim": "target metric 43,248",
                "metadata": {
                    "block_type": "table",
                    "unit_hint": "백만원",
                    "year": 2023,
                    "local_heading": "major performance indicators",
                    "table_value_labels_text": "target metric 43,248\ntarget metric 52,927",
                },
            },
            {
                "evidence_id": "ev_consolidated",
                "claim": "target metric 1,701,152",
                "metadata": {
                    "block_type": "table",
                    "unit_hint": "백만원",
                    "year": 2023,
                    "local_heading": "연결 기준 operating performance",
                    "table_value_labels_text": "target metric 1,701,152\ntarget metric 1,303,065",
                },
            },
        ]

        rows = agent._prefer_direct_structured_lookup_evidence_rows(
            current_rows,
            evidence_items=evidence_items,
            required_operands=[{"label": "target metric", "role": "primary_value", "required": True}],
            operation_family="lookup",
            state={"query": "2023년 연결기준 target metric을 답해 줘.", "report_scope": {}},
        )

        self.assertEqual(rows[0]["source_row_id"], "ev_consolidated")
        self.assertEqual(rows[0]["raw_value"], "1,701,152")

    def test_lookup_recovery_can_use_seed_retrieved_doc_context(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        generic_doc = SimpleNamespace(
            page_content="target metric | 43,248 | 52,927",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "major performance indicators",
                "table_value_labels_text": "target metric 43,248\ntarget metric 52,927",
            },
        )
        consolidated_doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "local_heading": "연결 기준 operating performance",
                "table_value_labels_text": "target metric 1,701,152\ntarget metric 1,303,065",
            },
        )
        ordered_results = [
            {
                "task_id": "task_metric",
                "metric_family": "source_stated_metric",
                "metric_label": "target metric",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "target metric 43,248백만원",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "label": "target metric",
                            "role": "primary_value",
                            "raw_value": "43,248",
                            "raw_unit": "백만원",
                            "normalized_value": 43_248_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_generic",
                            "source_row_ids": ["ev_generic"],
                        }
                    },
                },
            }
        ]
        state = {
            "query": "2023년 연결기준 target metric을 답해 줘.",
            "report_scope": {},
            "calc_subtasks": [
                {
                    "task_id": "task_metric",
                    "metric_family": "source_stated_metric",
                    "metric_label": "target metric",
                    "operation_family": "lookup",
                    "required_operands": [
                        {"label": "target metric", "role": "primary_value", "required": True}
                    ],
                }
            ],
            "seed_retrieved_docs": [(generic_doc, 1.0), (consolidated_doc, 0.9)],
            "retrieved_docs": [],
            "evidence_items": [],
            "runtime_evidence": [],
        }

        recovered = agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertEqual(slot["raw_value"], "1,701,152")
        self.assertTrue(recovered[0]["recovered_from_sibling_table_evidence"])

    def test_lookup_task_can_recover_direct_target_metric_from_table_value_labels(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        doc = SimpleNamespace(
            page_content="target metric | 1,701,152 | 1,303,065 | 398,087",
            metadata={
                "company": "Example",
                "year": 2023,
                "section_path": "management discussion",
                "block_type": "table",
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_row_labels_text": "증감\ntarget metric",
                "table_value_labels_text": "target metric 1,701,152\ntarget metric 1,303,065\ntarget metric 398,087",
            },
        )
        evidence_pool = agent._ratio_operand_context_evidence_from_docs([(doc, 1.0)], max_docs=1)

        row, operand = agent._direct_target_metric_operand_from_evidence(
            {
                "active_subtask": {
                    "task_id": "task_metric",
                    "metric_family": "source_stated_metric",
                    "metric_label": "target metric",
                    "operation_family": "lookup",
                }
            },
            evidence_pool,
        )

        self.assertEqual(operand["label"], "target metric")
        self.assertEqual(row["raw_value"], "1,701,152")
        self.assertTrue(row["direct_target_metric_lookup"])

    def test_ratio_ontology_plan_prefers_matching_operand_role(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "calculate business loss as a percentage of total operating income",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "loss to operating income ratio",
                "operation_family": "ratio",
                "required_operands": [
                    {
                        "role": "numerator_1",
                        "concept": "operating_loss",
                        "label": "business operating loss",
                    },
                    {
                        "role": "denominator_1",
                        "concept": "operating_income",
                        "label": "operating income",
                    },
                ],
            },
        }
        operands = [
            {
                "operand_id": "num",
                "label": "business operating loss",
                "matched_operand_role": "numerator_1",
                "matched_operand_concept": "operating_loss",
                "normalized_value": -580.0,
            },
            {
                "operand_id": "generic",
                "label": "business operating loss",
                "normalized_value": -1070.0,
            },
            {
                "operand_id": "den",
                "label": "operating income",
                "matched_operand_label": "operating income",
                "matched_operand_role": "denominator_1",
                "matched_operand_concept": "operating_income",
                "normalized_value": 1900.0,
            },
        ]

        plan = agent._build_deterministic_ontology_plan(state, operands)

        self.assertIsNotNone(plan)
        self.assertEqual(plan["ordered_operand_ids"], ["num", "den"])

    def test_absolute_ratio_query_renders_positive_magnitude(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        state = {
            "query": "calculate the absolute magnitude as a percentage",
            "active_subtask": {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "loss to income ratio",
                "operation_family": "ratio",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "label": "loss",
                        "raw_value": "(580)",
                        "raw_unit": "",
                        "normalized_value": -580.0,
                        "normalized_unit": "COUNT",
                        "matched_operand_role": "numerator_1",
                    },
                    {
                        "operand_id": "den",
                        "label": "income",
                        "raw_value": "1900",
                        "raw_unit": "",
                        "normalized_value": 1900.0,
                        "normalized_unit": "COUNT",
                        "matched_operand_role": "denominator_1",
                    },
                ],
                "calculation_plan": {
                    "status": "ok",
                    "mode": "single_value",
                    "operation": "ratio",
                    "ordered_operand_ids": ["num", "den"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "num"},
                        {"variable": "B", "operand_id": "den"},
                    ],
                    "formula": "((A) / (B)) * 100",
                    "result_unit": "%",
                },
                "calculation_result": {},
            },
        }

        result_state = agent._execute_calculation(state)
        result = result_state["resolved_calculation_trace"]["calculation_result"]

        self.assertAlmostEqual(result["result_value"], 30.526315789473685)
        self.assertEqual(result["rendered_value"], "30.53%")

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

    def test_dependency_projection_recalculates_partial_ratio_from_late_lookup_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating loss",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating loss",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "(581,816)million",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "1,903,886",
                            "raw_unit": "million",
                            "normalized_value": 1_903_886_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "1,903,886million",
                            "source_row_id": "row_total",
                            "source_row_ids": ["row_total"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment loss to total income ratio",
                "operation_family": "ratio",
                "answer": "insufficient operands",
                "status": "insufficient_operands",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_segment",
                        "source_row_ids": ["task_output:task_segment", "row_segment"],
                        "source_task_id": "task_segment",
                        "label": "segment operating loss",
                        "raw_value": "(581,816)",
                        "raw_unit": "million",
                        "normalized_value": -581_816_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                        "dependency_resolved": True,
                    },
                ],
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "segment loss to total income ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating loss",
                                    "concept": "operating_income",
                                    "raw_value": "(581,816)",
                                    "raw_unit": "million",
                                    "normalized_value": -581_816_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "task_output:task_segment",
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
                "query": "calculate segment loss to total income ratio",
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {"task_id": "task_total", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "metric_label": "segment loss to total income ratio",
                        "required_operands": [
                            {
                                "role": "numerator_1",
                                "label": "segment operating loss",
                                "concept": "operating_income",
                            },
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "-30.56%")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "1,903,886")
        self.assertIn("task_output:task_total", denominator["source_row_ids"])

    def test_dependency_projection_uses_table_label_for_missing_ratio_role_before_polluted_lookup_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_table",
            "source_anchor": "[source]",
            "metadata": {
                "unit_hint": "백만원",
                "table_value_labels_text": "total operating income 1,903,886\nother metric 100",
            },
        }
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating loss",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating loss",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating loss",
                            "concept": "operating_income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "task_output:task_segment",
                            "source_row_ids": ["task_output:task_segment", "row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment loss to total income ratio",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_segment",
                        "source_row_ids": ["task_output:task_segment", "row_segment"],
                        "source_task_id": "task_segment",
                        "label": "segment operating loss",
                        "raw_value": "(581,816)",
                        "raw_unit": "million",
                        "normalized_value": -581_816_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                    },
                ],
                "calculation_result": {"status": "insufficient_operands"},
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate the absolute segment loss to total income ratio",
                "runtime_evidence": [evidence],
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {"task_id": "task_total", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "metric_label": "segment loss to total income ratio",
                        "required_operands": [
                            {
                                "role": "numerator_1",
                                "label": "segment operating loss",
                                "concept": "operating_income",
                            },
                            {
                                "role": "denominator_1",
                                "label": "total operating income",
                                "concept": "operating_income",
                            },
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        self.assertEqual(ratio_row["status"], "ok")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "1,903,886")
        self.assertEqual(denominator["source_row_id"], "ev_table")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "30.56%")

    def test_dependency_projection_prefers_valid_late_lookup_over_table_label_for_missing_ratio_role(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_table",
            "source_anchor": "[source]",
            "metadata": {
                "unit_hint": "million",
                "table_value_labels_text": "total operating income 100\nother metric 50",
            },
        }
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "백만원",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "1,000",
                            "raw_unit": "million",
                            "normalized_value": 1_000_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_total",
                            "source_row_ids": ["row_total"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_operands": [
                    {
                        "operand_id": "num",
                        "source_row_id": "task_output:task_segment",
                        "source_row_ids": ["task_output:task_segment", "row_segment"],
                        "source_task_id": "task_segment",
                        "label": "segment operating income",
                        "raw_value": "250",
                        "raw_unit": "million",
                        "normalized_value": 250_000_000.0,
                        "normalized_unit": "KRW",
                        "matched_operand_concept": "operating_income",
                        "matched_operand_role": "numerator_1",
                    },
                ],
                "calculation_result": {"status": "insufficient_operands"},
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                "runtime_evidence": [evidence],
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {"task_id": "task_total", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "metric_label": "segment share of total operating income",
                        "required_operands": [
                            {
                                "role": "numerator_1",
                                "label": "segment operating income",
                                "concept": "operating_income",
                            },
                            {
                                "role": "denominator_1",
                                "label": "total operating income",
                                "concept": "operating_income",
                            },
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = aligned[-1]
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row.get("aligned_from_source_task_slots"))
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertIn("task_output:task_total", denominator["source_row_ids"])
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

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

    def test_ratio_components_are_not_complete_when_groups_are_same_slot(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "rendered_value": "100%",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_group": {
                    "numerator": [
                        {
                            "label": "segment operating income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "source_row_id": "task_output:task_source",
                            "source_row_ids": ["task_output:task_source", "row_segment"],
                        }
                    ],
                    "denominator": [
                        {
                            "label": "segment operating income",
                            "raw_value": "(581,816)",
                            "raw_unit": "million",
                            "normalized_value": -581_816_000_000.0,
                            "source_row_id": "task_output:task_source",
                            "source_row_ids": ["task_output:task_source", "row_segment"],
                        }
                    ],
                },
            },
        }

        self.assertFalse(agent._ratio_components_are_complete(calculation_result))

    def test_ratio_components_are_not_complete_when_same_source_value_has_different_labels(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        calculation_result = {
            "status": "ok",
            "rendered_value": "100%",
            "answer_slots": {
                "operation_family": "ratio",
                "components_by_group": {
                    "numerator": [
                        {
                            "label": "segment operating income",
                            "raw_value": "1,064,063",
                            "raw_unit": "million",
                            "normalized_value": 1_064_063_000_000.0,
                            "source_row_id": "row_same",
                            "source_row_ids": ["row_same"],
                        }
                    ],
                    "denominator": [
                        {
                            "label": "total operating income",
                            "raw_value": "1,064,063",
                            "raw_unit": "million",
                            "normalized_value": 1_064_063_000_000.0,
                            "source_row_id": "row_same",
                            "source_row_ids": ["row_same"],
                        }
                    ],
                },
            },
        }

        self.assertFalse(agent._ratio_components_are_complete(calculation_result))

    def test_ratio_operand_rows_collapse_when_roles_share_source_value(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        rows = [
            {
                "matched_operand_role": "numerator_1",
                "matched_operand_label": "segment revenue",
                "raw_value": "100",
                "raw_unit": "million",
                "normalized_value": 100_000_000.0,
                "evidence_id": "row_total",
                "source_row_id": "row_total",
            },
            {
                "matched_operand_role": "denominator_1",
                "matched_operand_label": "total revenue",
                "raw_value": "100",
                "raw_unit": "million",
                "normalized_value": 100_000_000.0,
                "evidence_id": "row_total",
                "source_row_id": "row_total",
            },
        ]

        self.assertTrue(agent._ratio_operand_rows_collapse_to_same_slot(rows))

    def test_operation_plan_guard_rejects_ratio_roles_sharing_source_value(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operands = [
            {
                "operand_id": "op_num",
                "matched_operand_role": "numerator_1",
                "matched_operand_label": "segment operating income",
                "raw_value": "100",
                "raw_unit": "million",
                "normalized_value": 100_000_000.0,
                "evidence_id": "row_same",
            },
            {
                "operand_id": "op_den",
                "matched_operand_role": "denominator_1",
                "matched_operand_label": "total operating income",
                "raw_value": "100",
                "raw_unit": "million",
                "normalized_value": 100_000_000.0,
                "evidence_id": "row_same",
            },
        ]
        plan = {
            "operation": "ratio",
            "ordered_operand_ids": ["op_num", "op_den"],
            "variable_bindings": [
                {"variable": "A", "operand_id": "op_num"},
                {"variable": "B", "operand_id": "op_den"},
            ],
        }
        required_operands = [
            {"label": "segment operating income", "role": "numerator_1", "required": True},
            {"label": "total operating income", "role": "denominator_1", "required": True},
        ]

        guarded_plan = agent._operation_plan_guard(
            plan=plan,
            operands=operands,
            required_operands=required_operands,
            operation_family="ratio",
        )

        self.assertIsNotNone(guarded_plan)
        self.assertIn("distinct_ratio_roles", guarded_plan["missing_info"])

    def test_dependency_projection_replaces_collapsed_ratio_role_from_sibling_lookup(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "250",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "million",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_plan": {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "missing_info": ["distinct_ratio_roles"],
                },
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "metric_label": "segment share of total operating income",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "백만원",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "total operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "백만원",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "전체 영업이익은 1,000 백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "",
                    "formatted_result": "전체 영업이익은 1,000 백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "900",
                            "raw_unit": "million",
                            "normalized_value": 900_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_stale_total",
                            "source_row_ids": ["row_stale_total"],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "total operating income",
                                "concept": "operating_income",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {"task_id": "task_total", "operation_family": "lookup"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_dependency_projection_uses_required_label_when_collapsed_ratio_slot_label_is_generic(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "million",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "Total operating income is 1,000 백만원.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "Total operating income is 1,000 백만원.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "total operating income",
                            "concept": "operating_income",
                            "raw_value": "1,000",
                            "raw_unit": "million",
                            "normalized_value": 1_000_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_total",
                            "source_row_ids": ["row_total"],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "total operating income",
                                "concept": "operating_income",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {"task_id": "task_total", "operation_family": "lookup"},
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_dependency_projection_repairs_stale_lookup_slot_label_from_answer_text(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_segment",
                "metric_family": "concept_lookup",
                "metric_label": "segment operating income",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "operating_income",
                            "raw_value": "250",
                            "raw_unit": "million",
                            "normalized_value": 250_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "row_segment",
                            "source_row_ids": ["row_segment"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share of total operating income",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "segment operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "operating income",
                                    "concept": "operating_income",
                                    "raw_value": "50",
                                    "raw_unit": "million",
                                    "normalized_value": 50_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "row_same",
                                    "source_row_ids": ["row_same"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "total operating income",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "Total operating income is 1,000 million.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "Total operating income is 1,000 million.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "segment operating income",
                            "concept": "",
                            "raw_value": "900",
                            "raw_unit": "백만원",
                            "normalized_value": 900_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "",
                            "source_row_ids": [],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "calculate segment share of total operating income",
                    "calc_subtasks": [
                    {"task_id": "task_segment", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "segment operating income",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "operating income",
                                "concept": "",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {
                        "task_id": "task_total",
                        "operation_family": "lookup",
                        "required_operands": [
                            {
                                "label": "total operating income",
                                "concept": "operating_income",
                                "role": "primary_value",
                                "required": True,
                            }
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertTrue(ratio_row["aligned_from_source_task_slots"])
        self.assertEqual(denominator["raw_value"], "1,000")
        self.assertEqual(denominator["label"], "total operating income")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "25%")

    def test_dependency_projection_repairs_qualified_denominator_lookup_with_blank_slot_metadata(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_vehicle",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 차량 부문 영업이익",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "차량 부문의 영업이익은 12,677,300 백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "차량 부문의 영업이익은 12,677,300 백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "차량 영업이익",
                            "concept": "operating_income",
                            "raw_value": "12,677,300",
                            "raw_unit": "백만원",
                            "normalized_value": 12_677_300_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "ev_001",
                            "source_row_ids": ["ev_001"],
                        },
                    },
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "전체 영업이익에서 차량 부문이 차지하는 비중",
                "operation_family": "ratio",
                "status": "insufficient_operands",
                "calculation_result": {
                    "status": "insufficient_operands",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "components_by_group": {
                            "numerator": [
                                {
                                    "status": "ok",
                                    "role": "numerator_1",
                                    "label": "차량 영업이익",
                                    "concept": "operating_income",
                                    "raw_value": "1,064,063",
                                    "raw_unit": "백만원",
                                    "normalized_value": 1_064_063_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "ev_001",
                                    "source_row_ids": ["ev_001"],
                                }
                            ],
                            "denominator": [
                                {
                                    "status": "ok",
                                    "role": "denominator_1",
                                    "label": "영업이익",
                                    "concept": "operating_income",
                                    "raw_value": "1,064,063",
                                    "raw_unit": "백만원",
                                    "normalized_value": 1_064_063_000_000.0,
                                    "normalized_unit": "KRW",
                                    "source_row_id": "ev_001",
                                    "source_row_ids": ["ev_001"],
                                }
                            ],
                        },
                    },
                },
            },
            {
                "task_id": "task_total",
                "metric_family": "concept_lookup",
                "metric_label": "2023년 전체 영업이익",
                "operation_family": "lookup",
                "status": "ok",
                "answer": "전체 영업이익은 15,126,901 백만원입니다.",
                "calculation_result": {
                    "status": "ok",
                    "formatted_result": "전체 영업이익은 15,126,901 백만원입니다.",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "2023년 차량 부문 영업이익",
                            "concept": "",
                            "raw_value": "12,969,227",
                            "raw_unit": "백만원",
                            "normalized_value": 12_969_227_000_000.0,
                            "normalized_unit": "KRW",
                            "source_row_id": "",
                            "source_row_ids": [],
                        },
                    },
                },
            },
        ]

        aligned = agent._align_lookup_results_with_dependency_projection(
            ordered_results,
            {
                "query": "차량 부문이 전체 영업이익에서 차지하는 비중을 계산",
                "calc_subtasks": [
                    {"task_id": "task_vehicle", "operation_family": "lookup"},
                    {
                        "task_id": "task_ratio",
                        "operation_family": "ratio",
                        "required_operands": [
                            {
                                "label": "차량 영업이익",
                                "concept": "operating_income",
                                "role": "numerator_1",
                                "required": True,
                            },
                            {
                                "label": "영업이익",
                                "concept": "operating_income",
                                "role": "denominator_1",
                                "required": True,
                            },
                        ],
                    },
                    {
                        "task_id": "task_total",
                        "operation_family": "lookup",
                        "required_operands": [
                            {
                                "label": "영업이익",
                                "concept": "operating_income",
                                "role": "primary_value",
                                "required": True,
                            }
                        ],
                    },
                ],
            },
            {"calculation_operands": []},
        )

        ratio_row = next(row for row in aligned if row["task_id"] == "task_ratio")
        denominator = next(
            operand
            for operand in ratio_row["calculation_operands"]
            if operand["matched_operand_role"] == "denominator_1"
        )
        self.assertEqual(denominator["raw_value"], "15,126,901")
        self.assertEqual(denominator["source_task_id"], "task_total")
        self.assertEqual(ratio_row["calculation_result"]["rendered_value"], "83.81%")

    def test_coherent_ratio_context_skips_collapsed_candidate_group(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        required_operands = [
            {"label": "segment revenue", "role": "numerator_1", "required": True},
            {"label": "total revenue", "role": "denominator_1", "required": True},
        ]
        evidence_items = [
            {
                "evidence_id": "wrong_context",
                "source_anchor": "wrong",
                "metadata": {"table_source_id": "wrong"},
            },
            {
                "evidence_id": "right_context",
                "source_anchor": "right",
                "metadata": {"table_source_id": "right"},
            },
        ]

        def build_rows(group_items, **_kwargs):
            group_id = group_items[0]["evidence_id"]
            if group_id == "wrong_context":
                return [
                    {
                        "operand_id": "numerator_1",
                        "matched_operand_role": "numerator_1",
                        "matched_operand_label": "segment revenue",
                        "raw_value": "100",
                        "raw_unit": "million",
                        "normalized_value": 100_000_000.0,
                        "evidence_id": "row_total",
                        "source_row_id": "row_total",
                    },
                    {
                        "operand_id": "denominator_1",
                        "matched_operand_role": "denominator_1",
                        "matched_operand_label": "total revenue",
                        "raw_value": "100",
                        "raw_unit": "million",
                        "normalized_value": 100_000_000.0,
                        "evidence_id": "row_total",
                        "source_row_id": "row_total",
                    },
                ]
            return [
                {
                    "operand_id": "numerator_1",
                    "matched_operand_role": "numerator_1",
                    "matched_operand_label": "segment revenue",
                    "raw_value": "25",
                    "raw_unit": "million",
                    "normalized_value": 25_000_000.0,
                    "evidence_id": "row_segment",
                    "source_row_id": "row_segment",
                },
                {
                    "operand_id": "denominator_1",
                    "matched_operand_role": "denominator_1",
                    "matched_operand_label": "total revenue",
                    "raw_value": "100",
                    "raw_unit": "million",
                    "normalized_value": 100_000_000.0,
                    "evidence_id": "row_total",
                    "source_row_id": "row_total",
                },
            ]

        agent._build_required_operands_from_candidates = build_rows
        agent._filter_operand_rows_by_required_surface_contract = lambda rows, *_args, **_kwargs: rows

        rows = agent._build_complete_ratio_operands_from_coherent_context(
            evidence_items,
            required_operands=required_operands,
            query="segment revenue ratio",
            topic="segment revenue ratio",
            report_scope={},
        )

        self.assertEqual([row["raw_value"] for row in rows], ["25", "100"])

    def test_period_comparison_table_label_context_builds_current_and_prior_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_mda",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:1",
                "table_row_labels_text": "Revenue\nOperating profit",
                "table_value_labels_text": (
                    "Revenue 1,000\n"
                    "Revenue 900\n"
                    "Revenue 800\n"
                    "Revenue 11.1%\n"
                    "Operating profit 409,219\n"
                    "Operating profit 2,600,786\n"
                    "Operating profit 712,064\n"
                    "Operating profit -84.3%"
                ),
            },
        }
        required_operands = [
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "current_period",
                "required": True,
                "unit_family": "KRW",
            },
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "prior_period",
                "required": True,
                "unit_family": "KRW",
            },
        ]

        rows = agent._build_period_comparison_operands_from_table_label_context(
            [evidence],
            required_operands=required_operands,
            query="calculate year-over-year operating profit growth and summarize the MD&A impact",
            operation_family="growth_rate",
        )

        self.assertEqual([row["matched_operand_role"] for row in rows], ["current_period", "prior_period"])
        self.assertEqual([row["raw_value"] for row in rows], ["409,219", "2,600,786"])
        self.assertEqual(rows[0]["stated_change_raw_value"], "-84.3")
        self.assertEqual(rows[0]["table_source_id"], "mda::table:1")

    def test_period_comparison_table_label_context_prefers_source_stated_mda_change(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        broad_evidence = {
            "evidence_id": "ev_broad",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "The market spread was volatile during the year.",
            "quote_span": "The market spread was volatile during the year.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:broad",
                "table_row_labels_text": "Operating profit",
                "table_value_labels_text": "Operating profit 810,900\nOperating profit 3,390,092",
            },
        }
        direct_evidence = {
            "evidence_id": "ev_direct",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:direct",
                "table_row_labels_text": "Operating profit",
                "table_value_labels_text": (
                    "Operating profit 409,219\n"
                    "Operating profit 2,600,786\n"
                    "Operating profit 712,064\n"
                    "Operating profit -84.3%"
                ),
            },
        }
        required_operands = [
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "current_period",
                "required": True,
                "unit_family": "KRW",
            },
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "prior_period",
                "required": True,
                "unit_family": "KRW",
            },
        ]

        rows = agent._build_period_comparison_operands_from_table_label_context(
            [broad_evidence, direct_evidence],
            required_operands=required_operands,
            query="calculate year-over-year operating profit growth and summarize the MD&A impact",
            operation_family="growth_rate",
        )

        self.assertEqual([row["raw_value"] for row in rows], ["409,219", "2,600,786"])
        self.assertTrue(all(row["table_source_id"] == "mda::table:direct" for row in rows))

    def test_period_comparison_realigns_growth_result_from_late_table_label_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_mda",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:1",
                "table_row_labels_text": "Operating profit",
                "table_value_labels_text": (
                    "Operating profit 409,219\n"
                    "Operating profit 2,600,786\n"
                    "Operating profit 712,064\n"
                    "Operating profit -84.3%"
                ),
            },
        }
        required_operands = [
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "current_period",
                "required": True,
                "unit_family": "KRW",
            },
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "prior_period",
                "required": True,
                "unit_family": "KRW",
            },
        ]
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "refining operating profit growth",
                "operation_family": "growth_rate",
                "answer": "-76.08%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": -76.08,
                    "rendered_value": "-76.08%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "metric_label": "refining operating profit growth",
                    },
                },
            }
        ]
        state = {
            "query": "calculate year-over-year operating profit growth and summarize the MD&A impact",
            "report_scope": {"year": 2023},
            "calc_subtasks": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "refining operating profit growth",
                    "operation_family": "growth_rate",
                    "required_operands": required_operands,
                }
            ],
        }

        rows = agent._realign_period_comparison_results_from_table_label_context(
            ordered_results,
            state,
            [evidence],
        )

        result = rows[0]["calculation_result"]
        self.assertEqual(result["rendered_value"], "-84.3%")
        self.assertTrue(result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(result["answer_slots"]["current_value"]["raw_value"], "409,219")
        self.assertEqual(result["answer_slots"]["prior_value"]["raw_value"], "2,600,786")

    def test_period_comparison_realign_does_not_replace_complete_growth_slots(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_weak_table",
            "source_anchor": "company | 2023 | Notes",
            "claim": "target metric 193,270 target metric 2023",
            "quote_span": "target metric 193,270 target metric 2023",
            "metadata": {
                "year": 2023,
                "statement_type": "notes",
                "table_source_id": "notes::table:1",
                "table_row_labels_text": "target metric",
                "table_value_labels_text": "target metric 193,270\ntarget metric 2023",
            },
        }
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "target metric growth",
                "operation_family": "growth_rate",
                "answer": "4.51%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "4.51%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {"status": "ok", "rendered_value": "4.51%"},
                        "current_value": {
                            "status": "ok",
                            "role": "current_value",
                            "label": "target metric",
                            "raw_value": "3,673,524",
                            "raw_unit": "백만원",
                            "normalized_value": 3_673_524_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,673,524백만원",
                            "source_row_id": "task_output:current",
                            "source_row_ids": ["task_output:current", "row_current"],
                        },
                        "prior_value": {
                            "status": "ok",
                            "role": "prior_value",
                            "label": "target metric",
                            "raw_value": "3,514,902",
                            "raw_unit": "백만원",
                            "normalized_value": 3_514_902_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,514,902백만원",
                            "source_row_id": "task_output:prior",
                            "source_row_ids": ["task_output:prior", "row_prior"],
                        },
                    },
                },
            }
        ]
        state = {
            "query": "calculate year-over-year target metric growth",
            "calc_subtasks": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "target metric growth",
                    "operation_family": "growth_rate",
                    "required_operands": [
                        {"label": "target metric", "role": "current_period", "required": True},
                        {"label": "target metric", "role": "prior_period", "required": True},
                    ],
                }
            ],
        }

        rows = agent._realign_period_comparison_results_from_table_label_context(
            ordered_results,
            state,
            [evidence],
        )

        self.assertIs(rows, ordered_results)
        self.assertEqual(rows[0]["calculation_result"]["rendered_value"], "4.51%")

    def test_period_comparison_realigns_complete_growth_slots_from_source_stated_change(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence = {
            "evidence_id": "ev_mda",
            "source_anchor": "company | 2023 | MD&A",
            "claim": "Operating profit decreased because the product-price spread narrowed.",
            "quote_span": "Operating profit decreased because the product-price spread narrowed.",
            "metadata": {
                "year": 2023,
                "statement_type": "mda",
                "unit_hint": "백만원",
                "table_source_id": "mda::table:1",
                "table_row_labels_text": "Operating profit",
                "table_value_labels_text": (
                    "Operating profit 409,219\n"
                    "Operating profit 2,600,786\n"
                    "Operating profit 712,064\n"
                    "Operating profit -84.3%"
                ),
            },
        }
        required_operands = [
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "current_period",
                "required": True,
                "unit_family": "KRW",
            },
            {
                "label": "refining operating profit",
                "aliases": ["Operating profit"],
                "concept": "operating_income",
                "role": "prior_period",
                "required": True,
                "unit_family": "KRW",
            },
        ]
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "metric_label": "refining operating profit growth",
                "operation_family": "growth_rate",
                "answer": "-76.08%",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "result_value": -76.08,
                    "rendered_value": "-76.08%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {"status": "ok", "rendered_value": "-76.08%"},
                        "current_value": {
                            "status": "ok",
                            "role": "current_value",
                            "label": "refining operating profit",
                            "raw_value": "810,900",
                            "raw_unit": "백만원",
                            "normalized_value": 810_900_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "810,900백만원",
                            "source_row_id": "task_output:current",
                            "source_row_ids": ["task_output:current", "row_current"],
                        },
                        "prior_value": {
                            "status": "ok",
                            "role": "prior_value",
                            "label": "refining operating profit",
                            "raw_value": "3,390,092",
                            "raw_unit": "백만원",
                            "normalized_value": 3_390_092_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,390,092백만원",
                            "source_row_id": "task_output:prior",
                            "source_row_ids": ["task_output:prior", "row_prior"],
                        },
                    },
                },
            }
        ]
        state = {
            "query": "calculate year-over-year operating profit growth and summarize the MD&A impact",
            "calc_subtasks": [
                {
                    "task_id": "task_growth",
                    "metric_family": "concept_growth_rate",
                    "metric_label": "refining operating profit growth",
                    "operation_family": "growth_rate",
                    "required_operands": required_operands,
                }
            ],
        }

        rows = agent._realign_period_comparison_results_from_table_label_context(
            ordered_results,
            state,
            [evidence],
        )

        result = rows[0]["calculation_result"]
        self.assertEqual(result["rendered_value"], "-84.3%")
        self.assertTrue(result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(result["answer_slots"]["current_value"]["raw_value"], "409,219")
        self.assertEqual(result["answer_slots"]["prior_value"]["raw_value"], "2,600,786")

    def test_period_comparison_operand_recovery_uses_seed_table_context_before_dependency_rows(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._extract_structured_operands_from_reconciliation = lambda _state: []
        agent._evidence_items_from_reconciliation_matches = lambda _state: []
        agent._surface_contract_numeric_evidence_items = lambda _items, _operands: []
        agent._direct_target_metric_operand_from_evidence = lambda _state, _items: ({}, {})
        agent._dependency_binding_resolution_state = lambda _state: {
            "rows": [
                {
                    "operand_id": "current_period",
                    "matched_operand_role": "current_period",
                    "matched_operand_label": "target metric",
                    "raw_value": "900",
                    "raw_unit": "million",
                    "normalized_value": 900_000_000.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                    "source_anchor": "lookup output",
                },
                {
                    "operand_id": "prior_period",
                    "matched_operand_role": "prior_period",
                    "matched_operand_label": "target metric",
                    "raw_value": "700",
                    "raw_unit": "million",
                    "normalized_value": 700_000_000.0,
                    "normalized_unit": "KRW",
                    "period": "2022",
                    "source_anchor": "lookup output",
                },
            ],
            "bindings": [],
            "resolved_keys": set(),
            "missing_bindings": [],
        }
        stale_visible_doc = SimpleNamespace(
            page_content="summary table",
            metadata={
                "company": "ExampleCo",
                "year": 2022,
                "section_path": "III. Financial statements > Summary",
                "statement_type": "summary_financials",
                "table_source_id": "summary::table:1",
                "table_row_labels_text": "target metric",
                "table_value_labels_text": "target metric 900\ntarget metric 700",
                "unit_hint": "million",
            },
        )
        seed_comparison_doc = SimpleNamespace(
            page_content="comparison table",
            metadata={
                "company": "ExampleCo",
                "year": 2023,
                "section_path": "IV. Management discussion",
                "statement_type": "mda",
                "table_source_id": "mda::table:1",
                "table_row_labels_text": "target metric",
                "table_value_labels_text": (
                    "target metric 1,200\n"
                    "target metric 1,000\n"
                    "target metric 200\n"
                    "target metric 20%"
                ),
                "unit_hint": "million",
            },
        )
        required_operands = [
            {
                "label": "2023 target metric",
                "aliases": ["target metric"],
                "concept": "target_metric",
                "role": "current_period",
                "required": True,
                "unit_family": "KRW",
            },
            {
                "label": "2022 target metric",
                "aliases": ["target metric"],
                "concept": "target_metric",
                "role": "prior_period",
                "required": True,
                "unit_family": "KRW",
            },
        ]

        result = agent._extract_calculation_operands(
            {
                "query": "calculate year-over-year target metric growth and summarize the impact",
                "report_scope": {"year": 2023},
                "active_subtask": {
                    "task_id": "task_growth",
                    "metric_family": "generic_numeric",
                    "metric_label": "target metric growth",
                    "operation_family": "growth_rate",
                    "required_operands": required_operands,
                },
                "retrieved_docs": [(stale_visible_doc, 1.0)],
                "seed_retrieved_docs": [(seed_comparison_doc, 0.9)],
                "evidence_items": [],
                "evidence_bullets": [],
                "artifacts": [],
                "tasks": [],
            }
        )

        rows = _resolve_runtime_calculation_trace(result)["calculation_operands"]
        by_role = {row["matched_operand_role"]: row for row in rows}
        self.assertEqual(by_role["current_period"]["raw_value"], "1,200")
        self.assertEqual(by_role["prior_period"]["raw_value"], "1,000")
        self.assertEqual(by_role["current_period"]["table_source_id"], "mda::table:1")
        self.assertEqual(by_role["prior_period"]["table_source_id"], "mda::table:1")

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

    def test_aggregate_projection_skips_operands_for_hidden_subtask_result(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_numerator",
                "metric_family": "concept_lookup",
                "metric_label": "reported numerator",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "120백만원",
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {
                            "status": "ok",
                            "role": "primary_value",
                            "label": "reported numerator",
                            "raw_value": "120",
                            "raw_unit": "백만원",
                            "normalized_value": 120_000_000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "120백만원",
                            "source_row_id": "ev_numerator",
                        },
                    },
                    "source_row_ids": ["ev_numerator"],
                },
            },
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share",
                "operation_family": "ratio",
                "status": "ok",
                "answer": "Segment share is 481.47%.",
                "calculation_operands": [
                    {
                        "operand_id": "numerator_1",
                        "matched_operand_role": "numerator_1",
                        "label": "stale numerator",
                        "raw_value": "6,670,971",
                        "raw_unit": "백만원",
                        "normalized_value": 6_670_971_000_000.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "denominator_1",
                        "matched_operand_role": "denominator_1",
                        "label": "stale denominator",
                        "raw_value": "1,385,538",
                        "raw_unit": "백만원",
                        "normalized_value": 1_385_538_000_000.0,
                        "normalized_unit": "KRW",
                    },
                ],
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "481.47%",
                    "formatted_result": "Segment share is 481.47%.",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {"status": "ok", "rendered_value": "481.47%"},
                    },
                },
            }
        ]

        projection = agent._build_aggregate_calculation_projection(
            ordered_results,
            "Reported numerator is 1.2억원. Segment share is 83.81%.",
        )

        operands = projection["calculation_operands"]
        self.assertEqual(len(operands), 1)
        self.assertEqual(operands[0]["task_id"], "task_numerator")
        self.assertEqual(operands[0]["raw_value"], "120")

    def test_complete_numeric_answer_does_not_replace_unresolved_ratio_final_answer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share",
                "operation_family": "ratio",
                "status": "in_progress",
                "calculation_result": {
                    "status": "incomplete",
                    "answer_slots": {"operation_family": "ratio"},
                },
            },
            {
                "task_id": "task_sum",
                "metric_family": "concept_sum",
                "metric_label": "combined amount",
                "operation_family": "sum",
                "status": "ok",
                "answer": "Combined amount is 1,250 million.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "1,250 million",
                    "formatted_result": "Combined amount is 1,250 million.",
                    "answer_slots": {
                        "operation_family": "sum",
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "1,250 million",
                            "raw_value": "1,250",
                            "raw_unit": "million",
                            "normalized_value": 1_250_000_000.0,
                            "normalized_unit": "KRW",
                        },
                    },
                },
            },
        ]

        numeric_answer = agent._preferred_complete_numeric_answer(ordered_results)

        self.assertIn("1,250", numeric_answer)
        self.assertFalse(
            agent._complete_numeric_answer_can_replace_final(
                numeric_answer,
                ordered_results,
            )
        )

        resolved_results = [
            {
                **ordered_results[0],
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "25.00%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {
                            "status": "ok",
                            "rendered_value": "25.00%",
                            "raw_value": "25.00",
                            "raw_unit": "%",
                            "normalized_value": 25.0,
                            "normalized_unit": "PERCENT",
                        },
                    },
                },
            },
            ordered_results[1],
        ]

        self.assertTrue(
            agent._complete_numeric_answer_can_replace_final(
                agent._preferred_complete_numeric_answer(resolved_results),
                resolved_results,
            )
        )

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

    def test_existing_complete_aggregate_artifact_beats_late_partial_answer(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_ratio",
                "metric_family": "concept_ratio",
                "metric_label": "segment share",
                "operation_family": "ratio",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "25.00%",
                    "answer_slots": {
                        "operation_family": "ratio",
                        "primary_value": {"status": "ok", "rendered_value": "25.00%"},
                    },
                },
            }
        ]
        current_answer = (
            "Segment amount is 250 million and total amount is 1,000 million. "
            "However, the required value was not sufficiently confirmed."
        )
        artifacts = [
            {
                "artifact_id": "aggregate:001",
                "task_id": "aggregate",
                "kind": "aggregated_answer",
                "status": "ok",
                "summary": "Segment amount is 250 million, total amount is 1,000 million, and the share is 25.00%.",
                "payload": {
                    "final_answer": (
                        "Segment amount is 250 million, total amount is 1,000 million, "
                        "and the share is 25.00%."
                    )
                },
                "evidence_refs": ["ev_001"],
            }
        ]

        candidate = agent._preferred_existing_aggregate_artifact_candidate(
            artifacts,
            ordered_results,
            current_answer,
        )

        self.assertEqual(
            candidate["answer"],
            "Segment amount is 250 million, total amount is 1,000 million, and the share is 25.00%.",
        )
        self.assertEqual(candidate["selected_claim_ids"], ["ev_001"])

    def test_table_metadata_source_stated_change_is_allowed_narrative_numeric_material(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "operation_family": "growth_rate",
                    "rendered_value": "-76.08%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {"status": "ok", "rendered_value": "-76.08%"},
                    },
                },
            }
        ]
        evidence_items = [
            {
                "claim": "Operating profit decreased because product spreads narrowed.",
                "quote_span": "Operating profit recorded 4,092억원 due to lower spreads.",
                "metadata": {
                    "table_value_labels_text": "Operating profit 409,219\nOperating profit -84.3%",
                },
            }
        ]
        answer = "Operating profit decreased 84.3% to 4,092억원 due to lower spreads."

        self.assertFalse(
            agent._growth_answer_has_untraced_numeric_material(
                answer,
                ordered_results,
                evidence_items,
            )
        )
        self.assertFalse(
            agent._narrative_summary_conflicts_with_growth_trace(
                answer,
                ordered_results,
                evidence_items,
            )
        )


if __name__ == "__main__":
    unittest.main()
