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

from src.agent.financial_graph import FinancialAgent


class LookupRecoveryPolicyTests(unittest.TestCase):
    def _agent_with_preferred_slot(self, preferred_slot, preferred_score=10.0):
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool: (
            dict(preferred_slot),
            preferred_score,
        )
        agent._direct_structured_lookup_evidence_score = lambda _operand, _evidence: 0.0
        return agent

    def test_ok_lookup_rejects_different_unknown_unit_table_label_candidate(self) -> None:
        preferred_slot = {
            "status": "ok",
            "role": "current_period",
            "label": "metric",
            "concept": "revenue",
            "period": "2023",
            "raw_value": "(1,835,988)",
            "raw_unit": "",
            "normalized_value": -1835988.0,
            "normalized_unit": "UNKNOWN",
            "rendered_value": "-1835988.0",
            "source_row_id": "ev_table",
            "source_row_ids": ["ev_table"],
        }
        agent = self._agent_with_preferred_slot(preferred_slot)
        ordered_results = [
            {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "current_period",
                            "label": "metric",
                            "concept": "revenue",
                            "period": "2023",
                            "raw_value": "3,146",
                            "raw_unit": "billion",
                            "normalized_value": 3146000000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,146 billion",
                            "source_row_id": "ev_current",
                            "source_row_ids": ["ev_current"],
                        }
                    },
                },
            }
        ]
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "metric",
                            "concept": "revenue",
                            "role": "current_period",
                            "period": "2023",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {"evidence_id": "ev_current", "metadata": {"unit_hint": "billion"}},
                {
                    "evidence_id": "ev_table",
                    "metadata": {
                        "unit_hint": "",
                        "table_value_labels_text": "metric (1,835,988)",
                    },
                },
            ],
        }

        recovered = agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertFalse(recovered[0].get("recovered_from_sibling_table_evidence"))
        self.assertEqual(slot["raw_value"], "3,146")
        self.assertEqual(slot["source_row_id"], "ev_current")

    def test_ok_lookup_allows_small_same_unit_precision_refinement(self) -> None:
        preferred_slot = {
            "status": "ok",
            "role": "current_period",
            "label": "metric",
            "concept": "revenue",
            "period": "2023",
            "raw_value": "3,146,409",
            "raw_unit": "million",
            "normalized_value": 3146409000000.0,
            "normalized_unit": "KRW",
            "rendered_value": "3,146,409 million",
            "source_row_id": "ev_table",
            "source_row_ids": ["ev_table"],
        }
        agent = self._agent_with_preferred_slot(preferred_slot)
        ordered_results = [
            {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "operation_family": "lookup",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "answer_slots": {
                        "primary_value": {
                            "status": "ok",
                            "role": "current_period",
                            "label": "metric",
                            "concept": "revenue",
                            "period": "2023",
                            "raw_value": "3,146",
                            "raw_unit": "billion",
                            "normalized_value": 3146000000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,146 billion",
                            "source_row_id": "ev_current",
                            "source_row_ids": ["ev_current"],
                        }
                    },
                },
            }
        ]
        state = {
            "calc_subtasks": [
                {
                    "task_id": "task_lookup",
                    "operation_family": "lookup",
                    "required_operands": [
                        {
                            "label": "metric",
                            "concept": "revenue",
                            "role": "current_period",
                            "period": "2023",
                            "required": True,
                        }
                    ],
                }
            ],
            "evidence_items": [
                {"evidence_id": "ev_current", "metadata": {"unit_hint": "billion"}},
                {
                    "evidence_id": "ev_table",
                    "metadata": {
                        "unit_hint": "million",
                        "table_value_labels_text": "metric 3,146,409",
                    },
                },
            ],
        }

        recovered = agent._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        slot = recovered[0]["calculation_result"]["answer_slots"]["primary_value"]

        self.assertTrue(recovered[0].get("recovered_from_sibling_table_evidence"))
        self.assertEqual(slot["raw_value"], "3,146,409")
        self.assertEqual(slot["source_row_id"], "ev_table")

    def test_best_direct_lookup_ignores_unknown_unit_table_label_candidate(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {
            "label": "metric",
            "concept": "revenue",
            "role": "current_period",
            "period": "2023",
        }
        slot, score = agent._best_direct_lookup_slot_from_evidence_pool(
            operand,
            [
                {
                    "evidence_id": "ev_unknown",
                    "source_anchor": "[ExampleCo | 2023 | Notes]",
                    "metadata": {
                        "year": 2023,
                        "table_value_labels_text": "metric 9",
                    },
                },
                {
                    "evidence_id": "ev_precise",
                    "source_anchor": "[ExampleCo | 2023 | Statement]",
                    "metadata": {
                        "year": 2023,
                        "unit_hint": "million",
                        "table_source_id": "statement::table:1",
                        "table_value_labels_text": "metric 3,146,409",
                    },
                },
            ],
        )

        self.assertGreater(score, 0.0)
        self.assertEqual(slot["source_row_id"], "ev_precise")
        self.assertEqual(slot["raw_value"], "3,146,409")

    def test_growth_refresh_prefers_conflicting_narrative_summary_over_wrong_trace(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "status": "ok",
                "answer": "The metric decreased by 27.34%.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "-27.34%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "metric growth",
                            "period": "2023",
                            "rendered_value": "-27.34%",
                            "normalized_value": -27.34,
                            "normalized_unit": "PERCENT",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "metric",
                            "period": "2023",
                            "raw_value": "(303)",
                            "raw_unit": "million",
                            "normalized_value": -303.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "-303 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "metric",
                            "period": "2022",
                            "raw_value": "(417)",
                            "raw_unit": "million",
                            "normalized_value": -417.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "-417 million",
                        },
                    },
                },
            },
            {
                "task_id": "task_narrative",
                "metric_family": "narrative_summary",
                "operation_family": "aggregate_subtasks",
                "status": "ok",
                "answer": (
                    "The metric was 3,146,409 million in 2023 and 1,847,775 million in 2022, "
                    "up 70.28%. The increase reflects conservative risk provisioning."
                ),
                "selected_claim_ids": ["ev_driver"],
            },
        ]

        refreshed = agent._refresh_numeric_answer_preserving_narrative_context(
            query="Calculate the growth rate and explain the risk management context.",
            current_answer="The metric decreased by 27.34%.",
            numeric_answer="The metric decreased by 27.34%.",
            ordered_results=ordered_results,
            evidence_items=[],
        )

        self.assertIn("70.28%", refreshed["answer"])
        self.assertNotIn("27.34%", refreshed["answer"])

    def test_aggregate_fallback_prefers_conflicting_narrative_summary(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "status": "ok",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "-27.34%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "metric growth",
                            "period": "2023",
                            "rendered_value": "-27.34%",
                            "normalized_value": -27.34,
                            "normalized_unit": "PERCENT",
                        },
                        "current_value": {
                            "status": "ok",
                            "label": "metric",
                            "period": "2023",
                            "raw_value": "(303)",
                            "raw_unit": "million",
                            "normalized_value": -303.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "-303 million",
                        },
                        "prior_value": {
                            "status": "ok",
                            "label": "metric",
                            "period": "2022",
                            "raw_value": "(417)",
                            "raw_unit": "million",
                            "normalized_value": -417.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "-417 million",
                        },
                    },
                },
            },
            {
                "task_id": "task_narrative",
                "metric_family": "narrative_summary",
                "operation_family": "aggregate_subtasks",
                "status": "ok",
                "answer": (
                    "The metric was 3,146,409 million in 2023 and 1,847,775 million in 2022, "
                    "up 70.28%. The increase reflects conservative risk provisioning."
                ),
            },
        ]

        answer = agent._preferred_aggregate_fallback_answer(
            ordered_results,
            "The metric decreased by 27.34%.",
        )

        self.assertIn("70.28%", answer)
        self.assertNotIn("27.34%", answer)

    def test_aggregate_projection_skips_missing_placeholder_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        projection = agent._build_aggregate_calculation_projection(
            [
                {
                    "task_id": "task_missing",
                    "metric_family": "concept_growth_rate",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "primary_value",
                            "matched_operand_role": "primary_value",
                            "status": "missing",
                            "label": "growth rate",
                            "raw_value": "",
                            "raw_unit": "",
                            "normalized_value": None,
                            "normalized_unit": "UNKNOWN",
                            "rendered_value": "",
                        }
                    ],
                    "calculation_result": {
                        "status": "ok",
                        "answer_slots": {
                            "operation_family": "growth_rate",
                            "primary_value": {
                                "status": "missing",
                                "role": "primary_value",
                                "label": "growth rate",
                                "raw_value": "",
                                "raw_unit": "",
                                "normalized_value": None,
                                "normalized_unit": "UNKNOWN",
                            },
                        },
                    },
                },
                {
                    "task_id": "task_material",
                    "metric_family": "concept_lookup",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "current_value",
                            "matched_operand_role": "current_value",
                            "label": "metric",
                            "raw_value": "3,146",
                            "raw_unit": "billion",
                            "normalized_value": 3146000000000.0,
                            "normalized_unit": "KRW",
                            "rendered_value": "3,146 billion",
                            "source_row_id": "ev_current",
                            "source_row_ids": ["ev_current"],
                        }
                    ],
                },
            ],
            "The metric increased.",
        )

        operands = projection["calculation_operands"]
        self.assertEqual([row["operand_id"] for row in operands], ["current_value"])
        subtask_slots = projection["calculation_result"]["answer_slots"]["subtask_results"]
        self.assertEqual(subtask_slots[0]["task_id"], "task_missing")

    def test_contextual_precision_refinement_rejects_large_scale_drift(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        row = {
            "label": "metric",
            "matched_operand_label": "metric",
            "matched_operand_role": "current_period",
            "period": "2023",
            "raw_value": "3,146,409",
            "raw_unit": "million",
            "normalized_value": 3146409000000.0,
            "normalized_unit": "KRW",
        }
        evidence = {
            "metadata": {
                "year": "2023",
                "table_row_labels_text": "metric",
                "table_row_records_json": json.dumps(
                    [
                        {
                            "row_label": "metric",
                            "cells": [
                                {
                                    "value_text": "(303)",
                                    "unit_hint": "million",
                                    "column_headers": ["2023"],
                                }
                            ],
                        }
                    ]
                ),
            }
        }

        refined = agent._refine_operand_precision_from_evidence_table(row, evidence)

        self.assertEqual(refined["raw_value"], "3,146,409")
        self.assertNotIn("precision_source", refined)

    def test_final_answer_evidence_filter_drops_unselected_numeric_noise(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = [
            {
                "evidence_id": "ev_selected",
                "claim": "The current value is 3,146\uc2ed\uc5b5\uc6d0.",
            },
            {
                "evidence_id": "recon::good",
                "claim": "Metric | prior 1,847,775 | table unit \ubc31\ub9cc\uc6d0",
            },
            {
                "evidence_id": "recon::noise",
                "claim": "Metric | current 9 | prior 1",
            },
        ]

        filtered = agent._filter_aggregate_evidence_for_final_answer(
            evidence_items,
            final_answer=(
                "The metric was 3,146\uc2ed\uc5b5\uc6d0 versus "
                "1,848\uc2ed\uc5b5\uc6d0, up 70.23%."
            ),
            selected_claim_ids=["ev_selected"],
        )

        self.assertEqual(
            [row["evidence_id"] for row in filtered],
            ["ev_selected", "recon::good"],
        )

    def test_aggregate_projection_provenance_drops_pruned_recon_ids(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        projection = {
            "calculation_result": {
                "source_evidence_ids": ["ev_selected", "recon::good", "recon::noise"],
                "source_row_ids": ["ev_selected", "recon::good", "recon::noise"],
                "derived_metrics": {
                    "aggregate_source_evidence_ids": ["ev_selected", "recon::good", "recon::noise"],
                },
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "source_row_ids": ["ev_selected", "recon::noise"],
                    "subtask_results": [
                        {
                            "task_id": "task_noise",
                            "source_evidence_ids": ["recon::noise"],
                            "source_row_ids": ["recon::noise"],
                        }
                    ],
                },
            }
        }

        filtered = agent._filter_aggregate_projection_provenance(
            projection,
            ["ev_selected", "recon::good"],
        )

        result = filtered["calculation_result"]
        self.assertEqual(result["source_evidence_ids"], ["ev_selected", "recon::good"])
        self.assertEqual(result["source_row_ids"], ["ev_selected", "recon::good"])
        self.assertEqual(result["answer_slots"]["source_row_ids"], ["ev_selected"])
        self.assertEqual(result["answer_slots"]["subtask_results"][0]["source_evidence_ids"], [])

    def test_final_answer_appends_matching_operand_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = []
        operands = [
            {
                "operand_id": "prior_period",
                "label": "prior metric",
                "period": "2022",
                "raw_value": "(1,847,775)",
                "raw_unit": "\ubc31\ub9cc\uc6d0",
                "source_anchor": "[ACME | 2022 | Notes]",
            }
        ]

        updated = agent._append_operand_evidence_for_final_answer(
            evidence_items,
            operands=operands,
            final_answer="The metric was 1,848\uc2ed\uc5b5\uc6d0.",
        )

        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["evidence_id"], "operand::prior_period")
        self.assertIn("1,847,775", updated[0]["claim"])

    def test_percent_answer_preserves_formula_operand_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operands = [
            {
                "operand_id": "dep_current",
                "matched_operand_role": "current_period",
                "label": "current metric",
                "period": "2023",
                "raw_value": "(3,146,409)",
                "raw_unit": "\ubc31\ub9cc\uc6d0",
                "normalized_unit": "KRW",
                "source_anchor": "[ACME | 2023 | Notes]",
            },
            {
                "operand_id": "dep_prior",
                "matched_operand_role": "prior_period",
                "label": "prior metric",
                "period": "2022",
                "raw_value": "(1,847,775)",
                "raw_unit": "\ubc31\ub9cc\uc6d0",
                "normalized_unit": "KRW",
                "source_anchor": "[ACME | 2022 | Notes]",
            },
        ]

        updated = agent._append_operand_evidence_for_final_answer(
            [],
            operands=operands,
            final_answer="The metric increased 70.23%.",
        )
        filtered = agent._filter_aggregate_evidence_for_final_answer(
            updated,
            final_answer="The metric increased 70.23%.",
            selected_claim_ids=[],
        )

        self.assertEqual(
            [item["evidence_id"] for item in filtered],
            ["operand::dep_current", "operand::dep_prior"],
        )
        self.assertTrue(filtered[1]["metadata"]["supports_derived_percent"])


if __name__ == "__main__":
    unittest.main()
