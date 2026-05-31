import unittest

from src.agent.financial_graph import FinancialAgent
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

    def test_lookup_unit_refinement_prefers_structured_unit_hint(self) -> None:
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

        self.assertEqual(refined["raw_unit"], "백만원")
        self.assertEqual(refined["normalized_value"], 2_546_649_000_000)


if __name__ == "__main__":
    unittest.main()
