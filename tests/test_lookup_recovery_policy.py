import ast
import json
import re
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent import (
    financial_aggregate_projection,
    financial_dependency_projection,
    financial_graph_calculation,
    financial_graph_planning,
    financial_lookup_recovery,
)
from src.agent.financial_graph import FinancialAgent


class LookupRecoveryPolicyTests(unittest.TestCase):
    def _agent_with_preferred_slot(self, preferred_slot, preferred_score=10.0):
        agent = FinancialAgent.__new__(FinancialAgent)
        agent._best_direct_lookup_slot_from_evidence_pool = lambda _operand, _pool, **_kwargs: (
            dict(preferred_slot),
            preferred_score,
        )
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
        evidence_pool = [
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
            ]
        events = []
        score_evidence = financial_graph_calculation.score_direct_structured_lookup_evidence
        table_label_lookup = agent._lookup_value_from_table_label_metadata
        table_label_score = financial_graph_calculation.table_label_metadata_lookup_score
        lookup_calls = []
        table_score_calls = []

        def _record_score(score_input):
            events.append(("score", score_input.evidence_item.get("evidence_id")))
            return score_evidence(score_input)

        def _record_table_label_lookup(scoring_operand, evidence):
            events.append(("table_label", evidence.get("evidence_id")))
            slot = table_label_lookup(scoring_operand, evidence)
            lookup_calls.append((scoring_operand, evidence, slot))
            return slot

        def _record_table_label_score(slot, evidence):
            result = table_label_score(slot, evidence)
            events.append(
                ("table_label_score", evidence.get("evidence_id"), slot.get("raw_value"), result)
            )
            table_score_calls.append((slot, evidence))
            return result

        with patch.object(
            financial_graph_calculation,
            "score_direct_structured_lookup_evidence",
            side_effect=_record_score,
        ), patch.object(
            agent,
            "_lookup_value_from_table_label_metadata",
            side_effect=_record_table_label_lookup,
        ), patch.object(
            financial_graph_calculation,
            "table_label_metadata_lookup_score",
            side_effect=_record_table_label_score,
        ):
            slot, score = agent._best_direct_lookup_slot_from_evidence_pool(operand, evidence_pool)

        self.assertGreater(score, 0.0)
        self.assertEqual(slot["source_row_id"], "ev_precise")
        self.assertEqual(slot["raw_value"], "3,146,409")
        self.assertEqual(
            events,
            [
                ("score", "ev_unknown"),
                ("table_label", "ev_unknown"),
                ("table_label_score", "ev_unknown", "9", 0.0),
                ("score", "ev_precise"),
                ("table_label", "ev_precise"),
                ("table_label_score", "ev_precise", "3,146,409", 8.25),
            ],
        )
        self.assertEqual(len(lookup_calls), 2)
        self.assertEqual(len(table_score_calls), 2)
        for index, ((scoring_operand, local_evidence, returned_slot), score_call) in enumerate(
            zip(lookup_calls, table_score_calls)
        ):
            self.assertIs(scoring_operand, operand)
            self.assertIs(score_call[0], returned_slot)
            self.assertIs(score_call[1], local_evidence)
            self.assertIsNot(local_evidence, evidence_pool[index])
            self.assertEqual(local_evidence, evidence_pool[index])

        empty_slot = {}
        with patch.object(
            agent,
            "_lookup_value_from_table_label_metadata",
            return_value=empty_slot,
        ) as stopped_lookup, patch.object(
            financial_graph_calculation,
            "table_label_metadata_lookup_score",
            side_effect=RuntimeError("table score stopped"),
        ) as stopped_scorer, self.assertRaisesRegex(RuntimeError, "table score stopped"):
            agent._best_direct_lookup_slot_from_evidence_pool(operand, evidence_pool)
        self.assertEqual(stopped_lookup.call_count, 1)
        self.assertEqual(stopped_scorer.call_count, 1)
        self.assertIs(stopped_scorer.call_args.args[0], empty_slot)
        self.assertIs(stopped_scorer.call_args.args[1], stopped_lookup.call_args.args[1])

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

    def test_growth_refresh_appends_supported_row_narrative_driver(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        ordered_results = [
            {
                "task_id": "task_growth",
                "metric_family": "concept_growth_rate",
                "operation_family": "growth_rate",
                "status": "ok",
                "answer": "The metric increased by 12.50%.",
                "calculation_result": {
                    "status": "ok",
                    "rendered_value": "12.50%",
                    "answer_slots": {
                        "operation_family": "growth_rate",
                        "primary_value": {
                            "status": "ok",
                            "label": "metric growth",
                            "period": "2023",
                            "rendered_value": "12.50%",
                            "normalized_value": 12.5,
                            "normalized_unit": "PERCENT",
                        },
                    },
                },
            },
            {
                "task_id": "task_narrative",
                "metric_family": "narrative_summary",
                "operation_family": "aggregate_subtasks",
                "status": "ok",
                "answer": "The driver was broader customer adoption.",
                "selected_claim_ids": ["ev_driver"],
            },
        ]

        refreshed = agent._refresh_numeric_answer_preserving_narrative_context(
            query="Calculate the growth rate and explain the driver.",
            current_answer="The metric increased by 12.50%.",
            numeric_answer="The metric increased by 12.50%.",
            ordered_results=ordered_results,
            evidence_items=[],
        )

        self.assertIn("12.50%", refreshed["answer"])
        self.assertIn("broader customer adoption", refreshed["answer"])
        self.assertEqual(["ev_driver"], refreshed["selected_claim_ids"])

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
        projection = financial_aggregate_projection.build_aggregate_calculation_projection(
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

    def test_aggregate_projection_skips_short_unknown_numeric_operands(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        projection = financial_aggregate_projection.build_aggregate_calculation_projection(
            [
                {
                    "task_id": "task_noise",
                    "metric_family": "concept_lookup",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "prior_value",
                            "matched_operand_role": "prior_period",
                            "label": "prior metric",
                            "raw_value": "9",
                            "raw_unit": "",
                            "normalized_value": 9.0,
                            "normalized_unit": "UNKNOWN",
                            "rendered_value": "9",
                            "source_row_id": "ev_noise",
                            "source_row_ids": ["ev_noise"],
                        }
                    ],
                },
                {
                    "task_id": "task_material",
                    "metric_family": "concept_lookup",
                    "status": "ok",
                    "calculation_operands": [
                        {
                            "operand_id": "current_value",
                            "matched_operand_role": "current_period",
                            "label": "current metric",
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
        self.assertNotIn("ev_noise", projection["calculation_result"]["source_row_ids"])

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

        filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
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

    def test_final_answer_evidence_promotes_table_numeric_support_text(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = [
            {
                "evidence_id": "ev_table",
                "claim": "3,146 (billion)",
                "quote_span": "3,146",
                "metadata": {
                    "table_header_context": "item | 2023 | change | 2022",
                    "table_value_labels_text": "\n".join(
                        [
                            "credit loss provision expense 3,146",
                            "credit loss provision expense 1,299",
                            "credit loss provision expense 1,848",
                            "net income 4,632",
                        ]
                    ),
                },
            }
        ]

        filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
            evidence_items,
            final_answer=(
                "credit loss provision expense was 3,146 billion in 2023 "
                "and 1,848 billion in 2022, up 70.24%."
            ),
            selected_claim_ids=[],
        )

        self.assertEqual(len(filtered), 1)
        self.assertIn("credit loss provision expense 3,146", filtered[0]["claim"])
        self.assertIn("credit loss provision expense 1,848", filtered[0]["claim"])
        self.assertIn("final_answer_table_numeric_support", filtered[0]["metadata"])

    def test_selected_final_answer_evidence_still_promotes_table_numeric_support_text(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = [
            {
                "evidence_id": "ev_table",
                "claim": "The provision increase was explained by risk management.",
                "quote_span": "risk management",
                "metadata": {
                    "table_header_context": "item | 2023 | change | 2022",
                    "table_value_labels_text": "\n".join(
                        [
                            "credit loss provision expense 3,146",
                            "credit loss provision expense 1,299",
                            "credit loss provision expense 1,848",
                        ]
                    ),
                },
            }
        ]

        filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
            evidence_items,
            final_answer=(
                "credit loss provision expense was 3,146 billion in 2023 "
                "and 1,848 billion in 2022, up 70.24%."
            ),
            selected_claim_ids=["ev_table"],
        )

        self.assertEqual(len(filtered), 1)
        self.assertIn("credit loss provision expense 3,146", filtered[0]["claim"])
        self.assertIn("credit loss provision expense 1,848", filtered[0]["quote_span"])
        self.assertIn("final_answer_table_numeric_support", filtered[0]["metadata"])

    def test_final_answer_evidence_filter_uses_table_numeric_support_owner(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"keep": True}
        retrieved = {
            "evidence_id": "retrieved_narrative::skip",
            "claim": "retrieved narrative 10%",
        }
        eligible = {
            "evidence_id": "ev_selected",
            "claim": "original 10%",
            "metadata": {"nested": nested},
        }
        second_nested = {"keep": "second"}
        second_eligible = {
            "evidence_id": "ev_second",
            "claim": "second 10%",
            "metadata": {"nested": second_nested},
        }
        promoted = {
            "evidence_id": "ev_selected",
            "claim": "promoted 10%",
            "metadata": {"promoted": True},
        }
        second_promoted = {
            "evidence_id": "ev_second",
            "claim": "second promoted 10%",
            "metadata": {"promoted": "second"},
        }
        final_answer = "target metric is 10%"
        expected_candidates = financial_aggregate_projection.extract_numeric_surface_candidates(
            final_answer
        )
        owner_calls = []

        def promote_owner(evidence, *, final_answer, answer_candidates):
            owner_calls.append((evidence, final_answer, answer_candidates))
            return {
                "ev_selected": promoted,
                "ev_second": second_promoted,
            }[evidence["evidence_id"]]

        with patch.object(
            financial_aggregate_projection,
            "promote_table_numeric_support_evidence",
            side_effect=promote_owner,
        ) as owner:
            filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
                [retrieved, eligible, second_eligible],
                final_answer=final_answer,
                selected_claim_ids=[
                    "retrieved_narrative::skip",
                    "ev_selected",
                    "ev_second",
                ],
            )

        self.assertEqual(owner.call_count, 2)
        for call, original, original_nested in zip(
            owner_calls,
            (eligible, second_eligible),
            (nested, second_nested),
        ):
            called_evidence, called_answer, called_candidates = call
            self.assertEqual(called_evidence, original)
            self.assertIsNot(called_evidence, original)
            self.assertIs(called_evidence["metadata"]["nested"], original_nested)
            self.assertEqual(called_answer, final_answer)
            self.assertEqual(called_candidates, expected_candidates)
        self.assertIs(owner_calls[0][2], owner_calls[1][2])
        self.assertEqual([row["evidence_id"] for row in filtered], [
            "retrieved_narrative::skip",
            "ev_selected",
            "ev_second",
        ])
        self.assertIsNot(filtered[0], retrieved)
        self.assertIs(filtered[1], promoted)
        self.assertIs(filtered[2], second_promoted)

        with (
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=RuntimeError("promotion failed"),
            ) as failing_owner,
            patch.object(
                financial_aggregate_projection,
                "evidence_supports_numeric_candidates",
            ) as later_support,
        ):
            with self.assertRaisesRegex(RuntimeError, "promotion failed"):
                financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
                    [eligible, {"evidence_id": "later", "claim": "later 10%"}],
                    final_answer=final_answer,
                    selected_claim_ids=[],
                )
        failing_owner.assert_called_once()
        later_support.assert_not_called()

    def test_final_answer_evidence_filter_binds_numeric_support_owners(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        answer_candidates = [{"kind": "percent", "value": 10.0}]
        selected = {
            "evidence_id": "ev_selected",
            "claim": "selected 10%",
            "quote_span": "selected quote 10%",
            "raw_row_text": "selected raw 10%",
        }
        operand = {
            "evidence_id": "operand::ratio",
            "claim": "operand 10%",
            "metadata": {"supports_answer_numeric_surface": True},
        }
        events = []

        def evidence_owner(evidence, candidates):
            self.assertIs(candidates, answer_candidates)
            evidence_id = evidence["evidence_id"]
            events.append(("evidence", evidence_id))
            return evidence_id.startswith("operand::")

        def text_owner(text, candidates):
            self.assertIs(candidates, answer_candidates)
            events.append(("text", text))
            return False

        def promote_owner(evidence, *, final_answer, answer_candidates):
            self.assertEqual(final_answer, "target 10%")
            self.assertIs(answer_candidates, globals_answer_candidates)
            events.append(("promote", evidence["evidence_id"]))
            return evidence

        globals_answer_candidates = answer_candidates
        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=answer_candidates,
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_supports_numeric_candidates",
                side_effect=evidence_owner,
            ) as evidence_support,
            patch.object(
                financial_aggregate_projection,
                "text_supports_numeric_candidates",
                side_effect=text_owner,
            ) as text_support,
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=promote_owner,
            ),
        ):
            filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
                [selected, operand],
                final_answer="target 10%",
                selected_claim_ids=["ev_selected"],
            )

        self.assertEqual(
            events,
            [
                ("evidence", "ev_selected"),
                ("evidence", "operand::ratio"),
                ("promote", "ev_selected"),
                ("text", "selected quote 10%"),
                ("promote", "operand::ratio"),
            ],
        )
        self.assertEqual([row["evidence_id"] for row in filtered], ["operand::ratio"])
        self.assertIsNot(filtered[0], operand)
        self.assertEqual(evidence_support.call_count, 2)
        text_support.assert_called_once_with("selected quote 10%", answer_candidates)

        generic_first = {"evidence_id": "ev_first", "claim": "first 20%"}
        generic_second = {"evidence_id": "ev_second", "claim": "second 10%"}
        events.clear()

        def generic_evidence_owner(evidence, candidates):
            self.assertIs(candidates, answer_candidates)
            events.append(("evidence", evidence["evidence_id"]))
            return evidence["evidence_id"] == "ev_second"

        def generic_promote_owner(evidence, **_kwargs):
            events.append(("promote", evidence["evidence_id"]))
            return evidence

        with (
            patch.object(
                financial_aggregate_projection,
                "extract_numeric_surface_candidates",
                return_value=answer_candidates,
            ),
            patch.object(
                financial_aggregate_projection,
                "evidence_supports_numeric_candidates",
                side_effect=generic_evidence_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "text_supports_numeric_candidates",
            ) as text_support,
            patch.object(
                financial_aggregate_projection,
                "promote_table_numeric_support_evidence",
                side_effect=generic_promote_owner,
            ),
        ):
            filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
                [generic_first, generic_second],
                final_answer="target 10%",
                selected_claim_ids=[],
            )

        self.assertEqual(
            events,
            [
                ("promote", "ev_first"),
                ("evidence", "ev_first"),
                ("promote", "ev_second"),
                ("evidence", "ev_second"),
            ],
        )
        self.assertEqual([row["evidence_id"] for row in filtered], ["ev_second"])
        text_support.assert_not_called()

    def test_final_answer_appends_matching_operand_evidence(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        evidence_items = []
        operands = [
            {
                "operand_id": "prior_period",
                "label": "prior metric",
                "period": "2022",
                "raw_value": "1,847,775",
                "raw_unit": "\ubc31\ub9cc\uc6d0",
                "source_anchor": "[ACME | 2022 | Notes]",
            }
        ]

        updated = financial_aggregate_projection.append_operand_evidence_for_final_answer(
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

        updated = financial_aggregate_projection.append_operand_evidence_for_final_answer(
            [],
            operands=operands,
            final_answer="The metric increased 70.23%.",
        )
        filtered = financial_aggregate_projection.filter_aggregate_evidence_for_final_answer(
            updated,
            final_answer="The metric increased 70.23%.",
            selected_claim_ids=[],
        )

        self.assertEqual(
            [item["evidence_id"] for item in filtered],
            ["operand::dep_current", "operand::dep_prior"],
        )
        self.assertTrue(filtered[1]["metadata"]["supports_derived_percent"])

    def test_current_source_direct_lookup_row_pins_ordinary_selection_gates_and_copy_contract(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"token": "nested"}
        operand = {
            "label": " Metric ",
            "concept": " Revenue ",
            "role": " current_period ",
            "period": "2023",
        }
        evidence = {
            "evidence_id": " ev_direct ",
            "source_anchor": " anchor ",
            "metadata": {
                "year": "2023",
                "row_label": " Row label ",
                "semantic_label": " Semantic label ",
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "table_source_id": "table::1",
                "unit_hint": "million",
                "structured_cells": [
                    {
                        "value_text": "1,234",
                        "unit_hint": "million",
                        "value_role": "detail",
                        "nested": nested,
                    }
                ],
            },
        }
        frozen = json.loads(json.dumps(evidence))
        events = []
        adopted = {"adopted": True}

        def period_focus(candidate, default):
            self.assertIs(candidate, operand)
            events.append(("period", default))
            return default

        def ordinary_selector(cells, *, operand, query_years, period_focus):
            self.assertIs(operand, globals_operand)
            self.assertEqual(query_years, [2023])
            self.assertEqual(period_focus, "current")
            self.assertIsNot(cells, evidence["metadata"]["structured_cells"])
            self.assertIsNot(cells[0], evidence["metadata"]["structured_cells"][0])
            self.assertIs(cells[0]["nested"], nested)
            self.assertEqual(cells[0]["_report_year"], "2023")
            events.append(("ordinary", cells[0]["value_text"]))
            return cells[0]

        def normalize(raw_value, raw_unit):
            events.append(("normalize", raw_value, raw_unit))
            return 1234.0, "KRW"

        def magnitude(row, evidence_item, **kwargs):
            self.assertIs(evidence_item, evidence)
            self.assertEqual(
                row,
                {
                    "operand_id": "direct_lookup_007",
                    "evidence_id": "ev_direct",
                    "source_row_id": "ev_direct",
                    "source_row_ids": ["ev_direct"],
                    "source_anchor": "anchor",
                    "label": "Metric",
                    "raw_value": "1,234",
                    "raw_unit": "million",
                    "normalized_value": 1234.0,
                    "normalized_unit": "KRW",
                    "period": "2023",
                    "matched_operand_label": "Metric",
                    "matched_operand_concept": "Revenue",
                    "matched_operand_role": "current_period",
                    "statement_type": "income_statement",
                    "consolidation_scope": "consolidated",
                    "table_source_id": "table::1",
                    "value_role": "detail",
                    "aggregation_stage": "",
                    "aggregate_label": "",
                },
            )
            self.assertEqual(
                kwargs,
                {
                    "concept": " Revenue ",
                    "statement_type": "income_statement",
                    "row_label": " Row label ",
                    "semantic_label": " Semantic label ",
                },
            )
            events.append(("magnitude", row["operand_id"]))
            return adopted

        globals_operand = operand
        with (
            patch.object(financial_lookup_recovery, "operand_period_focus", side_effect=period_focus),
            patch.object(financial_lookup_recovery, "select_structured_cell", side_effect=ordinary_selector),
            patch.object(financial_lookup_recovery, "select_aggregate_structured_cell") as aggregate_selector,
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", side_effect=normalize),
            patch.object(financial_lookup_recovery, "coerce_lookup_magnitude_record", side_effect=magnitude),
        ):
            result = financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                operand,
                evidence,
                index=7,
            )

        self.assertIs(result, adopted)
        self.assertEqual(
            events,
            [
                ("period", "current"),
                ("ordinary", "1,234"),
                ("normalize", "1,234", "million"),
                ("magnitude", "direct_lookup_007"),
            ],
        )
        aggregate_selector.assert_not_called()
        self.assertEqual(evidence, frozen)
        self.assertIs(evidence["metadata"]["structured_cells"][0]["nested"], nested)

        with patch.object(
            financial_lookup_recovery,
            "select_structured_cell",
            side_effect=AssertionError("empty cells must stop before selection"),
        ):
            self.assertEqual(
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                    operand,
                    {"metadata": {"structured_cells": []}},
                    index=1,
                ),
                {},
            )

        with (
            patch.object(financial_lookup_recovery, "select_structured_cell", return_value={}),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                side_effect=AssertionError("no selected cell must stop before normalization"),
            ),
        ):
            self.assertEqual(
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(operand, evidence, index=1),
                {},
            )

        with (
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                return_value={"value_text": "bad", "unit_hint": "million"},
            ),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", return_value=(None, "KRW")),
            patch.object(
                financial_lookup_recovery,
                "coerce_lookup_magnitude_record",
                side_effect=AssertionError("invalid normalized value must stop before magnitude coercion"),
            ),
        ):
            self.assertEqual(
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(operand, evidence, index=1),
                {},
            )

    def test_current_source_direct_lookup_row_pins_aggregate_selection_and_exceptions(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"alias": True}
        operand = {"label": "metric", "concept": "revenue", "role": "current_period"}
        detail = {"value_text": "10", "unit_hint": "million", "nested": nested}
        aggregate = {
            "value_text": "20",
            "unit_hint": "",
            "value_role": "aggregate",
            "aggregation_stage": "final",
            "aggregate_label": "total",
            "nested": nested,
        }
        evidence = {
            "evidence_id": "ev_aggregate",
            "metadata": {
                "year": 2023,
                "value_role": "aggregate",
                "unit_hint": "billion",
                "row_label": "metric",
                "structured_cells": [detail, aggregate],
            },
        }
        frozen = json.loads(json.dumps(evidence))
        events = []
        adopted = {"selected": "aggregate"}

        def ordinary(cells, **_kwargs):
            events.append("ordinary")
            return cells[0]

        def aggregate_selector(cells, *, operand, query_years, period_focus):
            self.assertIs(operand, globals_operand)
            self.assertEqual(query_years, [2023])
            self.assertEqual(period_focus, "current")
            self.assertEqual(len(cells), 1)
            self.assertEqual(cells[0]["value_text"], "20")
            self.assertIs(cells[0]["nested"], nested)
            events.append("aggregate")
            return cells[0]

        def normalize(value, unit):
            self.assertEqual((value, unit), ("20", "billion"))
            events.append("normalize")
            return 20_000_000_000.0, "KRW"

        def magnitude(row, evidence_item, **_kwargs):
            self.assertIs(evidence_item, evidence)
            self.assertEqual(row["raw_value"], "20")
            self.assertEqual(row["raw_unit"], "billion")
            self.assertEqual(row["value_role"], "aggregate")
            self.assertEqual(row["aggregation_stage"], "final")
            self.assertEqual(row["aggregate_label"], "total")
            events.append("magnitude")
            return adopted

        globals_operand = operand
        with (
            patch.object(financial_lookup_recovery, "select_structured_cell", side_effect=ordinary),
            patch.object(financial_lookup_recovery, "select_aggregate_structured_cell", side_effect=aggregate_selector),
            patch.object(
                financial_lookup_recovery,
                "operand_prefers_aggregate_value_role",
                side_effect=AssertionError("metadata aggregate role must short-circuit operand preference"),
            ),
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="current"),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", side_effect=normalize),
            patch.object(financial_lookup_recovery, "coerce_lookup_magnitude_record", side_effect=magnitude),
        ):
            result = financial_lookup_recovery.lookup_row_from_direct_structured_evidence(
                operand,
                evidence,
                index=2,
            )

        self.assertIs(result, adopted)
        self.assertEqual(events, ["ordinary", "aggregate", "normalize", "magnitude"])
        self.assertEqual(evidence, frozen)
        self.assertIs(evidence["metadata"]["structured_cells"][1]["nested"], nested)

        with (
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                side_effect=RuntimeError("ordinary selection failed"),
            ),
            patch.object(financial_lookup_recovery, "select_aggregate_structured_cell") as later,
        ):
            with self.assertRaisesRegex(RuntimeError, "ordinary selection failed"):
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(operand, evidence, index=1)
            later.assert_not_called()

        with (
            patch.object(financial_lookup_recovery, "select_structured_cell", return_value=detail),
            patch.object(financial_lookup_recovery, "select_aggregate_structured_cell", return_value=aggregate),
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="current"),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=True),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                side_effect=RuntimeError("normalization failed"),
            ),
            patch.object(financial_lookup_recovery, "coerce_lookup_magnitude_record") as later,
        ):
            with self.assertRaisesRegex(RuntimeError, "normalization failed"):
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(operand, evidence, index=1)
            later.assert_not_called()

        with (
            patch.object(financial_lookup_recovery, "select_structured_cell", return_value=detail),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="current"),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", return_value=(10.0, "KRW")),
            patch.object(
                financial_lookup_recovery,
                "coerce_lookup_magnitude_record",
                side_effect=RuntimeError("magnitude failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "magnitude failed"):
                financial_lookup_recovery.lookup_row_from_direct_structured_evidence(operand, evidence, index=1)

    def test_current_source_direct_lookup_row_static_binding_dag_and_baseline(self) -> None:
        graph_path = PROJECT_ROOT / "src" / "agent" / "financial_graph_calculation.py"
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_lookup_recovery.py"
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        public_target = "lookup_row_from_direct_structured_evidence"
        target = f"_{public_target}"

        graph_defs = [
            node
            for node in ast.walk(graph_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target
        ]
        self.assertEqual(graph_defs, [])
        owner_defs = [
            node
            for node in ast.walk(owner_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == public_target
        ]
        self.assertEqual(len(owner_defs), 1)
        self.assertEqual(owner_defs[0].end_lineno - owner_defs[0].lineno + 1, 80)
        self.assertEqual(
            [argument.arg for argument in owner_defs[0].args.args],
            ["operand", "evidence_item"],
        )
        self.assertEqual([argument.arg for argument in owner_defs[0].args.kwonlyargs], ["index"])
        self.assertFalse(
            any(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "self"
                for node in ast.walk(owner_defs[0])
            )
        )

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.stack = []
                self.try_depth = 0
                self.calls = []

            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else ""
                )
                if name in {target, public_target}:
                    receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "Name"
                    self.calls.append(
                        (
                            self.stack[-1],
                            receiver,
                            len(node.args),
                            [keyword.arg for keyword in node.keywords],
                            self.try_depth,
                            ast.unparse(node.keywords[0].value),
                        )
                    )
                self.generic_visit(node)

        visitor = BindingVisitor()
        visitor.visit(graph_tree)
        self.assertEqual(
            visitor.calls,
            [
                ("_best_direct_lookup_slot_from_evidence_pool", "Name", 2, ["index"], 0, "1"),
                ("_best_direct_lookup_slot_from_evidence_pool", "Name", 2, ["index"], 0, "1"),
                ("_best_direct_lookup_slot_from_evidence_pool", "Name", 2, ["index"], 0, "1"),
                ("_period_table_direct_operand_rows", "Name", 2, ["index"], 0, "operand_index"),
            ],
        )

        public = []
        private = []
        for node in owner_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                (private if node.name.startswith("_") else public).append(node.name)
        self.assertEqual((len(public), len(private)), (15, 13))

        modules = {
            path.stem: path
            for path in (PROJECT_ROOT / "src" / "agent").glob("*.py")
        }
        edges = {name: set() for name in modules}
        for module_name, path in modules.items():
            module_tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    dependency = node.module.rsplit(".", 1)[-1]
                    if dependency in modules:
                        edges[module_name].add(dependency)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.agent."):
                            dependency = alias.name.rsplit(".", 1)[-1]
                            if dependency in modules:
                                edges[module_name].add(dependency)

        def reaches(start, destination):
            pending = list(edges.get(start, set()))
            seen = set()
            while pending:
                current = pending.pop()
                if current == destination:
                    return True
                if current not in seen:
                    seen.add(current)
                    pending.extend(edges.get(current, set()))
            return False

        for dependency in (
            "financial_graph_helpers",
            "financial_operand_resolution",
            "financial_runtime_normalization",
        ):
            self.assertFalse(reaches(dependency, "financial_lookup_recovery"))
            self.assertFalse(reaches(dependency, "financial_graph_calculation"))
            self.assertFalse(reaches(dependency, "financial_graph"))
        self.assertFalse(reaches("financial_lookup_recovery", "financial_graph_calculation"))
        self.assertFalse(reaches("financial_lookup_recovery", "financial_graph"))

        baseline = json.loads(
            (PROJECT_ROOT / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_records = [
            record
            for record in baseline["records"]
            if record["path"] == "src/agent/financial_lookup_recovery.py"
            and any(owner_defs[0].lineno <= line <= owner_defs[0].end_lineno for line in record.get("first_lines") or [])
        ]
        self.assertEqual(selected_records, [])

    def test_current_source_direct_lookup_row_callers_pin_args_adoption_and_exception_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        operand = {"label": "metric", "role": "current_period"}
        evidence = {
            "evidence_id": "ev_pool",
            "metadata": {"structured_cells": [{"value_text": "10"}]},
        }
        row = {
            "raw_value": "1234",
            "raw_unit": "million",
            "normalized_value": 1234.0,
            "normalized_unit": "KRW",
            "source_row_id": "ev_pool",
        }
        adopted = {**row, "status": "ok", "role": "current_period"}
        events = []

        class Score:
            score = 10.0

        def row_builder(actual_operand, actual_evidence, *, index):
            self.assertIs(actual_operand, operand)
            self.assertIsNot(actual_evidence, evidence)
            self.assertIs(actual_evidence["metadata"], evidence["metadata"])
            self.assertEqual(index, 1)
            events.append("pool-row")
            return row

        def build_slot(actual_row, *, default_role, preserve_source_display):
            self.assertIs(actual_row, row)
            self.assertEqual(default_role, "current_period")
            self.assertTrue(preserve_source_display)
            events.append("pool-adopt")
            return adopted

        agent._lookup_value_from_table_label_metadata = lambda *_args: {}
        with (
            patch.object(
                financial_graph_calculation,
                "lookup_row_from_direct_structured_evidence",
                side_effect=row_builder,
            ),
            patch.object(financial_graph_calculation, "score_direct_structured_lookup_evidence", return_value=Score()),
            patch.object(financial_graph_calculation.financial_answer_slots, "build_operand_value_slot", side_effect=build_slot),
            patch.object(financial_graph_calculation, "extract_numeric_surface_candidates", return_value=[]),
        ):
            selected, score = agent._best_direct_lookup_slot_from_evidence_pool(operand, [evidence])

        self.assertIs(selected, adopted)
        self.assertEqual(score, 10.0)
        self.assertEqual(events, ["pool-row", "pool-adopt"])

        required_operands = [
            {"label": "current", "role": "current_period"},
            {"label": "prior", "role": "prior_period"},
        ]
        evidence_items = [
            {
                "evidence_id": "ev_table",
                "source_anchor": "anchor",
                "metadata": {
                    "table_source_id": "table::1",
                    "period_labels": "2023 2022",
                    "structured_cells": [{"value_text": "10"}],
                },
            }
        ]
        period_rows = []
        merged_lists = []
        events.clear()

        def period_row_builder(actual_operand, actual_evidence, *, index):
            self.assertIs(actual_operand, required_operands[index - 1])
            self.assertIsNot(actual_evidence, evidence_items[0])
            self.assertIs(actual_evidence["metadata"], evidence_items[0]["metadata"])
            events.append(("period-row", index))
            built = {
                "raw_value": str(index),
                "raw_unit": "million",
                "normalized_value": float(index),
                "normalized_unit": "KRW",
                "matched_operand_role": actual_operand["role"],
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
            }
            period_rows.append(built)
            return built

        def merge_rows(rows, existing, *, required_operands):
            self.assertEqual(existing, [])
            self.assertIs(required_operands, globals_required)
            self.assertEqual(rows, period_rows)
            merged_lists.append(rows)
            events.append("merge")
            return rows

        globals_required = required_operands
        with (
            patch.object(
                financial_graph_calculation,
                "lookup_row_from_direct_structured_evidence",
                side_effect=period_row_builder,
            ),
            patch.object(financial_graph_calculation, "score_direct_structured_lookup_evidence", return_value=Score()),
            patch.object(financial_graph_calculation, "_missing_required_operands", return_value=False),
            patch.object(financial_graph_calculation, "ratio_operand_rows_collapse_to_same_slot", return_value=False),
            patch.object(financial_graph_calculation, "merge_operand_rows", side_effect=merge_rows),
            patch.object(
                financial_graph_calculation,
                "filter_operand_rows_by_required_surface_contract",
                side_effect=lambda rows, *_args, **_kwargs: rows,
            ),
            patch.object(financial_graph_calculation, "scoped_surface_affinity_priority", return_value=0.0),
        ):
            built = agent._build_complete_ratio_operands_from_coherent_context(
                evidence_items,
                required_operands=required_operands,
                query="query",
                topic="topic",
                report_scope={},
            )

        self.assertIs(built, merged_lists[0])
        self.assertEqual(built, period_rows)
        self.assertTrue(all(actual is expected for actual, expected in zip(built, period_rows)))
        self.assertEqual(events, [("period-row", 1), ("period-row", 2), "merge"])

        downstream = []

        def fail_row(*_args, **_kwargs):
            raise RuntimeError("row owner failed")

        agent._lookup_value_from_table_label_metadata = lambda *_args: downstream.append("table") or {}
        with (
            patch.object(
                financial_graph_calculation,
                "lookup_row_from_direct_structured_evidence",
                side_effect=fail_row,
            ),
            patch.object(financial_graph_calculation, "score_direct_structured_lookup_evidence", return_value=Score()),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "build_operand_value_slot",
                side_effect=lambda *_args, **_kwargs: downstream.append("slot"),
            ),
            patch.object(financial_graph_calculation, "extract_numeric_surface_candidates", return_value=[]),
        ):
            with self.assertRaisesRegex(RuntimeError, "row owner failed"):
                agent._best_direct_lookup_slot_from_evidence_pool(operand, [evidence])
        self.assertEqual(downstream, [])

        with (
            patch.object(
                financial_graph_calculation,
                "lookup_row_from_direct_structured_evidence",
                side_effect=fail_row,
            ),
            patch.object(financial_graph_calculation, "score_direct_structured_lookup_evidence", return_value=Score()),
            patch.object(
                financial_graph_calculation,
                "merge_operand_rows",
                side_effect=lambda *_args, **_kwargs: downstream.append("merge"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "row owner failed"):
                agent._build_complete_ratio_operands_from_coherent_context(
                    evidence_items,
                    required_operands=required_operands,
                    query="query",
                    topic="topic",
                    report_scope={},
                )
        self.assertEqual(downstream, [])

    def test_current_source_direct_structured_value_pins_early_gates_surface_and_year_fallback(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"token": "nested"}
        row = {
            "label": "metric",
            "matched_operand_label": "metric",
            "matched_operand_concept": "revenue",
            "matched_operand_role": "current_period",
            "period": "not-a-year",
            "raw_value": "",
            "normalized_value": None,
            "nested": nested,
        }
        evidence = {
            "metadata": {
                "year": "also-not-a-year",
                "row_label": "metric",
                "semantic_label": "metric semantic",
                "structured_cells": [
                    {"value_text": "10", "unit_hint": "million", "nested": nested}
                ],
            }
        }
        row_frozen = json.loads(json.dumps(row))
        evidence_frozen = json.loads(json.dumps(evidence))

        empty_row = {}
        self.assertIs(
            financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(empty_row, evidence),
            empty_row,
        )
        self.assertIs(
            financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(row, None),
            row,
        )

        with patch.object(
            financial_lookup_recovery,
            "select_structured_cell",
            side_effect=AssertionError("missing cells must stop before selection"),
        ):
            no_cells_evidence = {"metadata": {"structured_cells": []}}
            self.assertIs(
                financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(
                    row,
                    no_cells_evidence,
                ),
                row,
            )

        mismatch_events = []

        def operand_match(surface, operand_spec):
            mismatch_events.append(("operand", surface, operand_spec["label"]))
            return False

        def positive_match(surface, operand_spec):
            mismatch_events.append(("positive", surface, operand_spec["concept"]))
            return False

        mismatch_evidence = {
            "metadata": {
                "row_label": "other row",
                "semantic_label": "other semantic",
                "structured_cells": [{"value_text": "20"}],
            }
        }
        with (
            patch.object(financial_lookup_recovery, "operand_text_match", side_effect=operand_match),
            patch.object(financial_lookup_recovery, "text_has_positive_surface", side_effect=positive_match),
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                side_effect=AssertionError("surface mismatch must stop before cell selection"),
            ),
        ):
            self.assertIs(
                financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(
                    row,
                    mismatch_evidence,
                ),
                row,
            )
        self.assertEqual(
            mismatch_events,
            [
                ("operand", "other row other semantic", "metric"),
                ("positive", "other row other semantic", "revenue"),
            ],
        )

        selection_events = []

        def select(cells, *, operand, query_years, period_focus):
            self.assertEqual(query_years, [])
            self.assertEqual(period_focus, "unknown")
            self.assertEqual(operand["period"], "not-a-year")
            self.assertIsNot(cells[0], evidence["metadata"]["structured_cells"][0])
            self.assertIs(cells[0]["nested"], nested)
            self.assertIsNot(cells[0]["_sibling_cells"], evidence["metadata"]["structured_cells"])
            self.assertIsNot(cells[0]["_sibling_cells"][0], evidence["metadata"]["structured_cells"][0])
            self.assertIs(cells[0]["_sibling_cells"][0]["nested"], nested)
            selection_events.append("select")
            return {}

        with (
            patch.object(financial_lookup_recovery, "operand_text_match", return_value=True),
            patch.object(
                financial_lookup_recovery,
                "text_has_positive_surface",
                side_effect=AssertionError("positive fallback must be lazy after operand match"),
            ),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(financial_lookup_recovery, "structured_cell_period_text", return_value=""),
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="unknown"),
            patch.object(financial_lookup_recovery, "select_structured_cell", side_effect=select),
        ):
            self.assertIs(
                financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(row, evidence),
                row,
            )
        self.assertEqual(selection_events, ["select"])
        self.assertEqual(row, row_frozen)
        self.assertEqual(evidence, evidence_frozen)
        self.assertIs(row["nested"], nested)
        self.assertIs(evidence["metadata"]["structured_cells"][0]["nested"], nested)

        with (
            patch.object(
                financial_lookup_recovery,
                "operand_text_match",
                side_effect=RuntimeError("surface match failed"),
            ),
            patch.object(financial_lookup_recovery, "text_has_positive_surface") as later,
            patch.object(financial_lookup_recovery, "select_structured_cell") as selector,
        ):
            with self.assertRaisesRegex(RuntimeError, "surface match failed"):
                financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(row, evidence)
            later.assert_not_called()
            selector.assert_not_called()

    def test_current_source_direct_structured_value_pins_selection_tolerance_copy_and_exceptions(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"alias": True}
        row = {
            "label": "metric",
            "matched_operand_label": "metric",
            "matched_operand_concept": "revenue",
            "matched_operand_role": "current_period",
            "period": "",
            "raw_value": "1,000",
            "raw_unit": "million",
            "normalized_value": 1000.0,
            "normalized_unit": "KRW",
            "nested": nested,
        }
        one_cell_evidence = {
            "metadata": {
                "row_label": "metric",
                "structured_cells": [{"value_text": "1,000", "unit_hint": "million"}],
            }
        }
        with (
            patch.object(financial_lookup_recovery, "operand_text_match", return_value=True),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                side_effect=AssertionError("equal current value must stop before selection"),
            ),
        ):
            self.assertIs(
                financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(
                    row,
                    one_cell_evidence,
                ),
                row,
            )

        period_row = {**row, "period": "2023"}
        period_evidence = {
            "metadata": {
                "year": "2023",
                "row_label": "metric",
                "unit_hint": "million",
                "structured_cells": [
                    {"value_text": "1,000.0000005", "unit_hint": "million"},
                    {"value_text": "900", "unit_hint": "million"},
                ],
            }
        }
        period_frozen = json.loads(json.dumps(period_evidence))
        selection_events = []

        def period_text(cell, query_years, period_focus):
            self.assertEqual(query_years, [2023])
            self.assertEqual(period_focus, "unknown")
            selection_events.append(("period", cell["value_text"]))
            return "2023"

        def ordinary(cells, *, operand, query_years, period_focus):
            self.assertEqual(query_years, [2023])
            self.assertEqual(period_focus, "unknown")
            self.assertEqual(operand["period"], "2023")
            selection_events.append(("select", len(cells)))
            return cells[0]

        with (
            patch.object(financial_lookup_recovery, "operand_text_match", return_value=True),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="unknown"),
            patch.object(financial_lookup_recovery, "structured_cell_period_text", side_effect=period_text),
            patch.object(financial_lookup_recovery, "select_structured_cell", side_effect=ordinary),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                return_value=(1000.0000005, "KRW"),
            ),
        ):
            within_tolerance = financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(
                period_row,
                period_evidence,
            )
        self.assertIs(within_tolerance, period_row)
        self.assertEqual(selection_events, [("period", "1,000.0000005"), ("select", 2)])
        self.assertEqual(period_evidence, period_frozen)

        aggregate_row = {
            **period_row,
            "period": "",
            "value_role": "aggregate",
        }
        aggregate_evidence = {
            "metadata": {
                "row_label": "metric",
                "unit_hint": "million",
                "structured_cells": [
                    {"value_text": "100", "unit_hint": "million", "nested": nested},
                    {
                        "value_text": "2,000",
                        "unit_hint": "million",
                        "value_role": "aggregate",
                        "nested": nested,
                    },
                ],
            }
        }
        row_frozen = json.loads(json.dumps(aggregate_row))
        evidence_frozen = json.loads(json.dumps(aggregate_evidence))

        def aggregate_selector(cells, *, operand, query_years, period_focus):
            self.assertEqual(query_years, [])
            self.assertEqual(period_focus, "unknown")
            self.assertEqual(operand["label"], "metric")
            self.assertIs(cells[1]["nested"], nested)
            return cells[1]

        with (
            patch.object(financial_lookup_recovery, "operand_text_match", return_value=True),
            patch.object(
                financial_lookup_recovery,
                "operand_prefers_aggregate_value_role",
                side_effect=AssertionError("row aggregate role must short-circuit operand preference"),
            ),
            patch.object(financial_lookup_recovery, "operand_period_focus", return_value="unknown"),
            patch.object(financial_lookup_recovery, "select_aggregate_structured_cell", side_effect=aggregate_selector),
            patch.object(
                financial_lookup_recovery,
                "select_structured_cell",
                side_effect=AssertionError("successful aggregate selection must suppress ordinary selection"),
            ),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", return_value=(2000.0, "KRW")),
        ):
            updated = financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(
                aggregate_row,
                aggregate_evidence,
            )

        self.assertIsNot(updated, aggregate_row)
        self.assertEqual(
            {key: updated[key] for key in (
                "raw_value",
                "raw_unit",
                "normalized_value",
                "normalized_unit",
                "rendered_value",
                "structured_evidence_cell_realigned",
            )},
            {
                "raw_value": "2,000",
                "raw_unit": "million",
                "normalized_value": 2000.0,
                "normalized_unit": "KRW",
                "rendered_value": "2,000million",
                "structured_evidence_cell_realigned": True,
            },
        )
        self.assertIs(updated["nested"], nested)
        self.assertEqual(aggregate_row, row_frozen)
        self.assertEqual(aggregate_evidence, evidence_frozen)
        self.assertIs(aggregate_row["nested"], nested)

        with (
            patch.object(financial_lookup_recovery, "operand_text_match", return_value=True),
            patch.object(financial_lookup_recovery, "operand_prefers_aggregate_value_role", return_value=False),
            patch.object(financial_lookup_recovery, "select_structured_cell", return_value={"value_text": "bad"}),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                side_effect=RuntimeError("value normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "value normalization failed"):
                financial_lookup_recovery.coerce_operand_value_from_direct_structured_evidence(
                    {**row, "raw_value": "", "normalized_value": None},
                    one_cell_evidence,
                )

    def test_current_source_direct_structured_value_static_binding_dag_and_baseline(self) -> None:
        graph_path = PROJECT_ROOT / "src" / "agent" / "financial_graph_calculation.py"
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_lookup_recovery.py"
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        public_target = "coerce_operand_value_from_direct_structured_evidence"
        target = f"_{public_target}"

        graph_defs = [
            node
            for node in ast.walk(graph_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target
        ]
        self.assertEqual(graph_defs, [])
        owner_defs = [
            node
            for node in ast.walk(owner_tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == public_target
        ]
        self.assertEqual(len(owner_defs), 1)
        self.assertEqual(owner_defs[0].end_lineno - owner_defs[0].lineno + 1, 138)
        self.assertEqual(
            [argument.arg for argument in owner_defs[0].args.args],
            ["row", "evidence_item"],
        )
        self.assertFalse(
            any(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "self"
                for node in ast.walk(owner_defs[0])
            )
        )

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self):
                self.stack = []
                self.try_depth = 0
                self.calls = []

            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else ""
                )
                if name in {target, public_target}:
                    receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "Name"
                    self.calls.append(
                        (
                            self.stack[-1],
                            receiver,
                            len(node.args),
                            [keyword.arg for keyword in node.keywords],
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        visitor = BindingVisitor()
        visitor.visit(graph_tree)
        self.assertEqual(
            visitor.calls,
            [("_coerce_operand_row_from_evidence", "Name", 2, [], 0)],
        )

        public = []
        private = []
        for node in owner_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                (private if node.name.startswith("_") else public).append(node.name)
        self.assertEqual((len(public), len(private)), (15, 13))

        modules = {
            path.stem: path
            for path in (PROJECT_ROOT / "src" / "agent").glob("*.py")
        }
        edges = {name: set() for name in modules}
        for module_name, path in modules.items():
            module_tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    dependency = node.module.rsplit(".", 1)[-1]
                    if dependency in modules:
                        edges[module_name].add(dependency)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.agent."):
                            dependency = alias.name.rsplit(".", 1)[-1]
                            if dependency in modules:
                                edges[module_name].add(dependency)

        def reaches(start, destination):
            pending = list(edges.get(start, set()))
            seen = set()
            while pending:
                current = pending.pop()
                if current == destination:
                    return True
                if current not in seen:
                    seen.add(current)
                    pending.extend(edges.get(current, set()))
            return False

        for dependency in (
            "financial_graph_helpers",
            "financial_structured_cells",
            "financial_row_surfaces",
            "financial_surface_contracts",
            "financial_operand_resolution",
        ):
            self.assertFalse(reaches(dependency, "financial_lookup_recovery"))
            self.assertFalse(reaches(dependency, "financial_graph_calculation"))
            self.assertFalse(reaches(dependency, "financial_graph"))
        self.assertFalse(reaches("financial_lookup_recovery", "financial_graph_calculation"))
        self.assertFalse(reaches("financial_lookup_recovery", "financial_graph"))

        baseline = json.loads(
            (PROJECT_ROOT / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_records = [
            record
            for record in baseline["records"]
            if record["path"] == "src/agent/financial_lookup_recovery.py"
            and any(owner_defs[0].lineno <= line <= owner_defs[0].end_lineno for line in record.get("first_lines") or [])
        ]
        self.assertEqual(selected_records, [])

    def test_current_source_direct_structured_value_caller_pins_order_adoption_and_exception_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"alias": True}
        row = {
            "raw_value": "10",
            "raw_unit": "million",
            "normalized_value": 10.0,
            "normalized_unit": "KRW",
            "statement_type": "income_statement",
            "consolidation_scope": "consolidated",
            "table_source_id": "table::1",
            "nested": nested,
        }
        evidence = {
            "metadata": {
                "statement_type": "income_statement",
                "consolidation_scope": "consolidated",
                "table_source_id": "table::1",
            }
        }
        row_frozen = json.loads(json.dumps(row))
        evidence_frozen = json.loads(json.dumps(evidence))
        period_row = {**row, "period_coerced": True}
        direct_row = {**period_row, "structured_evidence_cell_realigned": True}
        magnitude_row = {**direct_row, "magnitude": True}
        events = []

        def dependency_gate(actual_row):
            self.assertIsNot(actual_row, row)
            self.assertIs(actual_row["nested"], nested)
            events.append("dependency")
            return False

        def period_owner(actual_row, actual_evidence):
            self.assertIsNot(actual_row, row)
            self.assertIs(actual_evidence, evidence)
            events.append("period")
            return period_row

        def direct_owner(actual_row, actual_evidence):
            self.assertIs(actual_row, period_row)
            self.assertIs(actual_evidence, evidence)
            events.append("direct")
            return direct_row

        def magnitude_owner(actual_row, actual_evidence):
            self.assertIs(actual_row, direct_row)
            self.assertIs(actual_evidence, evidence)
            events.append("magnitude")
            return magnitude_row

        with (
            patch.object(
                financial_graph_calculation,
                "coerce_operand_value_from_direct_structured_evidence",
                side_effect=direct_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "dependency_task_output_has_consistent_krw_unit",
                side_effect=dependency_gate,
            ),
            patch.object(financial_graph_calculation, "coerce_operand_unit_from_evidence", return_value="million"),
            patch.object(
                financial_graph_calculation,
                "coerce_operand_period_from_evidence_surface",
                side_effect=period_owner,
            ),
            patch.object(financial_graph_calculation, "coerce_lookup_magnitude_record", side_effect=magnitude_owner),
            patch.object(
                agent,
                "_refine_operand_precision_from_evidence_table",
                side_effect=AssertionError("structured realignment must stop before precision refinement"),
            ),
        ):
            result = agent._coerce_operand_row_from_evidence(row, evidence)

        self.assertIs(result, magnitude_row)
        self.assertEqual(events, ["dependency", "period", "direct", "magnitude"])
        self.assertEqual(row, row_frozen)
        self.assertEqual(evidence, evidence_frozen)
        self.assertIs(row["nested"], nested)

        precision_input = {**period_row, "structured_evidence_cell_realigned": False}
        precision_output = {**precision_input, "precision": True}
        events.clear()

        def unchanged_direct(actual_row, actual_evidence):
            self.assertIs(actual_row, period_row)
            self.assertIs(actual_evidence, evidence)
            events.append("direct")
            return precision_input

        def unchanged_magnitude(actual_row, actual_evidence):
            self.assertIs(actual_row, precision_input)
            self.assertIs(actual_evidence, evidence)
            events.append("magnitude")
            return actual_row

        def precision_owner(actual_row, actual_evidence):
            self.assertIs(actual_row, precision_input)
            self.assertIs(actual_evidence, evidence)
            events.append("precision")
            return precision_output

        with (
            patch.object(
                financial_graph_calculation,
                "coerce_operand_value_from_direct_structured_evidence",
                side_effect=unchanged_direct,
            ),
            patch.object(financial_graph_calculation, "dependency_task_output_has_consistent_krw_unit", return_value=False),
            patch.object(financial_graph_calculation, "coerce_operand_unit_from_evidence", return_value="million"),
            patch.object(financial_graph_calculation, "coerce_operand_period_from_evidence_surface", return_value=period_row),
            patch.object(financial_graph_calculation, "coerce_lookup_magnitude_record", side_effect=unchanged_magnitude),
            patch.object(agent, "_refine_operand_precision_from_evidence_table", side_effect=precision_owner),
        ):
            result = agent._coerce_operand_row_from_evidence(row, evidence)
        self.assertIs(result, precision_output)
        self.assertEqual(events, ["direct", "magnitude", "precision"])

        downstream = []

        def fail_direct(actual_row, actual_evidence):
            self.assertIs(actual_row, period_row)
            self.assertIs(actual_evidence, evidence)
            raise RuntimeError("direct value owner failed")

        with (
            patch.object(
                financial_graph_calculation,
                "coerce_operand_value_from_direct_structured_evidence",
                side_effect=fail_direct,
            ),
            patch.object(financial_graph_calculation, "dependency_task_output_has_consistent_krw_unit", return_value=False),
            patch.object(financial_graph_calculation, "coerce_operand_unit_from_evidence", return_value="million"),
            patch.object(financial_graph_calculation, "coerce_operand_period_from_evidence_surface", return_value=period_row),
            patch.object(
                financial_graph_calculation,
                "coerce_lookup_magnitude_record",
                side_effect=lambda *_args, **_kwargs: downstream.append("magnitude"),
            ),
            patch.object(
                agent,
                "_refine_operand_precision_from_evidence_table",
                side_effect=lambda *_args, **_kwargs: downstream.append("precision"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "direct value owner failed"):
                agent._coerce_operand_row_from_evidence(row, evidence)
        self.assertEqual(downstream, [])
        self.assertEqual(row, row_frozen)
        self.assertEqual(evidence, evidence_frozen)

    def test_current_source_lookup_projection_money_and_unit_contract(self) -> None:
        class Match:
            def __init__(self, raw, unit):
                self.values = {"raw": raw, "unit": unit}

            def group(self, key):
                return self.values[key]

        events = []

        def normalize(value, unit):
            events.append((value, unit))
            return 1234.0, "KRW"

        with (
            patch.object(
                financial_lookup_recovery,
                "PLANNING_POLICY",
                {"money_surface_compound_unit_prefix": "hundred"},
            ),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", side_effect=normalize),
        ):
            compound = financial_lookup_recovery._money_match_to_slot_values(
                Match(" (1,234 ", " hundred million ")
            )
            ordinary = financial_lookup_recovery._money_match_to_slot_values(Match(" 77 ", " million "))

        self.assertEqual(
            compound,
            {
                "raw_value": "1,234",
                "raw_unit": "hundred million",
                "rendered_value": "1,234hundred million",
                "normalized_value": 1234.0,
                "normalized_unit": "KRW",
            },
        )
        self.assertEqual(ordinary["rendered_value"], "77million")
        self.assertEqual(events, [("1,234hundred million", "hundred million"), ("77", "million")])

        values = {"normalized_unit": "KRW", "nested": {"alias": True}}
        operand = {"unit_family": "KRW", "nested": {"alias": True}}
        values_frozen = json.loads(json.dumps(values))
        operand_frozen = json.loads(json.dumps(operand))
        self.assertTrue(financial_lookup_recovery._slot_values_match_operand_unit(values, operand))
        self.assertTrue(
            financial_lookup_recovery._slot_values_match_operand_unit(
                {"normalized_unit": "UNKNOWN"}, {"unit_family": "USD"}
            )
        )
        self.assertFalse(
            financial_lookup_recovery._slot_values_match_operand_unit(
                {"normalized_unit": "USD"}, {"unit_family": "KRW"}
            )
        )
        self.assertTrue(
            financial_lookup_recovery._slot_values_match_operand_unit(
                {"normalized_unit": "USD"}, {"unit_family": "RATIO"}
            )
        )
        self.assertEqual(values, values_frozen)
        self.assertEqual(operand, operand_frozen)

        with patch.object(
            financial_lookup_recovery,
            "_normalise_operand_value",
            side_effect=RuntimeError("money normalization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "money normalization failed"):
                financial_lookup_recovery._money_match_to_slot_values(Match("10", "million"))

    def test_current_source_lookup_projection_active_task_match_contract(self) -> None:
        operand = {"label": "Revenue 2023", "period": "2023", "nested": {"alias": True}}
        task = {"metric_label": "Revenue 2023", "nested": {"alias": True}}
        operand_frozen = json.loads(json.dumps(operand))
        task_frozen = json.loads(json.dumps(task))
        year_pattern = re.compile(r"\b20\d{2}\b")
        year_label_pattern = re.compile(r"20\d{2}")

        with (
            patch.object(financial_lookup_recovery, "_LOOKUP_YEAR_RE", year_pattern),
            patch.object(financial_lookup_recovery, "_LOOKUP_YEAR_LABEL_RE", year_label_pattern),
        ):
            self.assertTrue(financial_lookup_recovery.lookup_operand_matches_active_task(operand, task))
            self.assertFalse(
                financial_lookup_recovery.lookup_operand_matches_active_task(
                    {"label": "Revenue 2022", "period": "2022"},
                    {"metric_label": "Revenue 2023"},
                )
            )
            self.assertFalse(
                financial_lookup_recovery.lookup_operand_matches_active_task(
                    {"label": "Revenue"}, {"metric_label": "Revenue 2023"}
                )
            )
            self.assertTrue(
                financial_lookup_recovery.lookup_operand_matches_active_task(
                    {"matched_operand_label": "Segment Revenue 2023"},
                    {"metric_label": "Revenue 2023"},
                )
            )
            self.assertTrue(
                financial_lookup_recovery.lookup_operand_matches_active_task(
                    {"name": "Revenue prior"}, {"query": "Revenue current"}
                )
            )
            self.assertTrue(financial_lookup_recovery.lookup_operand_matches_active_task({}, {}))
            with patch.object(
                financial_lookup_recovery.re,
                "split",
                side_effect=AssertionError("year mismatch must stop before token splitting"),
            ):
                self.assertFalse(
                    financial_lookup_recovery.lookup_operand_matches_active_task(
                        {"label": "Revenue 2022", "period": "2022"},
                        {"metric_label": "Revenue 2023"},
                    )
                )

        self.assertEqual(operand, operand_frozen)
        self.assertEqual(task, task_frozen)

        class YearBomb:
            def findall(self, _value):
                raise RuntimeError("year scan failed")

        with patch.object(financial_lookup_recovery, "_LOOKUP_YEAR_RE", YearBomb()):
            with self.assertRaisesRegex(RuntimeError, "year scan failed"):
                financial_lookup_recovery.lookup_operand_matches_active_task(operand, task)

    def test_current_source_lookup_projection_refine_unit_contract(self) -> None:
        nested = {"alias": True}
        slot = {
            "raw_value": "1,234",
            "raw_unit": "",
            "normalized_unit": "UNKNOWN",
            "nested": nested,
        }
        evidence = {
            "raw_row_text": "Metric 1,234 million",
            "quote_span": "",
            "claim": "Metric 1,234",
            "metadata": {"unit_hint": "billion", "table_value_labels_text": "Metric"},
        }
        slot_frozen = json.loads(json.dumps(slot))
        evidence_frozen = json.loads(json.dumps(evidence))
        policy = {
            "inline_unit_aliases": {"mn": "million"},
            "inline_value_unit_pattern": r"(?P<value>[\d,]+)\s*(?P<unit>million|billion|mn)",
        }
        events = []

        def normalize(raw_value, raw_unit):
            events.append((raw_value, raw_unit))
            scale = {"million": 1_000_000.0, "billion": 1_000_000_000.0}[raw_unit]
            return 1234.0 * scale, "KRW"

        with (
            patch.object(financial_lookup_recovery, "NUMERIC_UNIT_NORMALIZATION_POLICY", policy),
            patch.object(financial_lookup_recovery, "_normalise_operand_value", side_effect=normalize),
        ):
            refined = financial_lookup_recovery.refine_lookup_slot_unit_from_evidence(slot, evidence)

        self.assertIsNot(refined, slot)
        self.assertIs(refined["nested"], nested)
        self.assertEqual(refined["raw_unit"], "million")
        self.assertEqual(refined["normalized_value"], 1_234_000_000.0)
        self.assertEqual(refined["normalized_unit"], "KRW")
        self.assertEqual(refined["rendered_value"], "1,234million")
        self.assertEqual(events, [("1,234", "million")])
        self.assertEqual(slot, slot_frozen)
        self.assertEqual(evidence, evidence_frozen)

        class EvidenceBomb(dict):
            def get(self, *_args, **_kwargs):
                raise AssertionError("blank raw value must not inspect evidence")

        blank = {"raw_value": "", "nested": nested}
        self.assertIs(
            financial_lookup_recovery.refine_lookup_slot_unit_from_evidence(blank, EvidenceBomb()),
            blank,
        )

        metadata_slot = {"raw_value": "10", "raw_unit": "", "normalized_unit": "UNKNOWN"}
        metadata_evidence = {"metadata": {"unit_hint": "billion"}}
        with (
            patch.object(financial_lookup_recovery, "NUMERIC_UNIT_NORMALIZATION_POLICY", policy),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                return_value=(10_000_000_000.0, "KRW"),
            ),
        ):
            metadata_refined = financial_lookup_recovery.refine_lookup_slot_unit_from_evidence(
                metadata_slot, metadata_evidence
            )
        self.assertEqual(metadata_refined["raw_unit"], "billion")

        known = {"raw_value": "10", "raw_unit": "million", "normalized_unit": "KRW"}
        with (
            patch.object(financial_lookup_recovery, "NUMERIC_UNIT_NORMALIZATION_POLICY", policy),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                side_effect=AssertionError("known unit must not be renormalized without a new surface"),
            ),
        ):
            self.assertIs(
                financial_lookup_recovery.refine_lookup_slot_unit_from_evidence(known, {"metadata": {}}),
                known,
            )

        with (
            patch.object(financial_lookup_recovery, "NUMERIC_UNIT_NORMALIZATION_POLICY", policy),
            patch.object(
                financial_lookup_recovery,
                "_normalise_operand_value",
                side_effect=RuntimeError("unit normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "unit normalization failed"):
                financial_lookup_recovery.refine_lookup_slot_unit_from_evidence(slot, evidence)

    def test_current_source_lookup_projection_extract_answer_slot_contract(self) -> None:
        money_pattern = re.compile(r"(?P<raw>\d+)\s*(?P<unit>million)")
        operand = {
            "label": "Metric",
            "concept": "revenue",
            "role": "primary_value",
            "period_hint": "2023",
            "surface_contract": {"positive": ["Metric", "Metric total"]},
            "nested": {"alias": True},
        }
        operand_frozen = json.loads(json.dumps(operand))
        selected_claim_ids = [" ev1 ", "", "ev2"]
        claim_ids_frozen = list(selected_claim_ids)
        events = []

        def convert(match):
            raw = match.group("raw")
            events.append(("convert", raw))
            return {
                "raw_value": raw,
                "raw_unit": match.group("unit"),
                "rendered_value": f"{raw} million",
                "normalized_value": float(raw) * 1_000_000.0,
                "normalized_unit": "KRW",
            }

        def unit_gate(values, actual_operand):
            self.assertIs(actual_operand, operand)
            events.append(("unit", values["raw_value"]))
            return True

        with (
            patch.object(financial_lookup_recovery, "_MONEY_SURFACE_RE", money_pattern),
            patch.object(financial_lookup_recovery, "operand_needles", return_value=[]),
            patch.object(financial_lookup_recovery, "_money_match_to_slot_values", side_effect=convert),
            patch.object(financial_lookup_recovery, "_slot_values_match_operand_unit", side_effect=unit_gate),
        ):
            slot = financial_lookup_recovery._extract_lookup_slot_from_answer_text(
                answer="Metric 10 million and Metric total 20 million",
                operand=operand,
                metric_label="Fallback metric",
                selected_claim_ids=selected_claim_ids,
            )

        self.assertEqual(slot["raw_value"], "10")
        self.assertEqual(slot["label"], "Metric")
        self.assertEqual(slot["concept"], "revenue")
        self.assertEqual(slot["role"], "primary_value")
        self.assertEqual(slot["period"], "2023")
        self.assertEqual(slot["source_row_id"], "ev1")
        self.assertEqual(slot["source_row_ids"], ["ev1"])
        self.assertEqual(slot["source_claim_ids"], ["ev1", "ev2"])
        self.assertEqual(
            events,
            [
                ("convert", "20"),
                ("unit", "20"),
                ("convert", "10"),
                ("unit", "10"),
                ("convert", "20"),
                ("unit", "20"),
                ("convert", "10"),
            ],
        )
        self.assertEqual(operand, operand_frozen)
        self.assertEqual(selected_claim_ids, claim_ids_frozen)

        no_surface = {"label": "Only metric"}
        with (
            patch.object(financial_lookup_recovery, "_MONEY_SURFACE_RE", money_pattern),
            patch.object(financial_lookup_recovery, "operand_needles", return_value=[]),
            patch.object(financial_lookup_recovery, "_money_match_to_slot_values", side_effect=convert),
            patch.object(financial_lookup_recovery, "_slot_values_match_operand_unit", return_value=True),
        ):
            single = financial_lookup_recovery._extract_lookup_slot_from_answer_text(
                answer="10 million",
                operand=no_surface,
                metric_label="Fallback",
                selected_claim_ids=[],
            )
            multiple = financial_lookup_recovery._extract_lookup_slot_from_answer_text(
                answer="10 million and 20 million",
                operand=no_surface,
                metric_label="Fallback",
                selected_claim_ids=[],
            )
        self.assertEqual(single["raw_value"], "10")
        self.assertIsNone(multiple)

        with (
            patch.object(financial_lookup_recovery, "_MONEY_SURFACE_RE", money_pattern),
            patch.object(financial_lookup_recovery, "operand_needles", return_value=[]),
            patch.object(financial_lookup_recovery, "_money_match_to_slot_values", side_effect=convert),
            patch.object(financial_lookup_recovery, "_slot_values_match_operand_unit", return_value=False),
        ):
            self.assertIsNone(
                financial_lookup_recovery._extract_lookup_slot_from_answer_text(
                    answer="10 million",
                    operand=no_surface,
                    metric_label="Fallback",
                    selected_claim_ids=[],
                )
            )

        with patch.object(
            financial_lookup_recovery,
            "operand_needles",
            side_effect=RuntimeError("surface projection failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "surface projection failed"):
                financial_lookup_recovery._extract_lookup_slot_from_answer_text(
                    answer="10 million",
                    operand=operand,
                    metric_label="Fallback",
                    selected_claim_ids=[],
                )

    def test_current_source_lookup_projection_synthesize_slot_contract(self) -> None:
        nested = {"alias": True}
        result = {"status": "partial", "answer_slots": {}, "nested": nested}
        result_frozen = {"status": "partial", "answer_slots": {}, "nested": nested}
        ordinary_task = {"operation_family": "difference", "required_operands": []}
        with patch.object(
            financial_lookup_recovery,
            "_extract_lookup_slot_from_answer_text",
            side_effect=AssertionError("non-lookup gate must stop before extraction"),
        ):
            self.assertIs(
                financial_lookup_recovery.synthesize_lookup_answer_slot_from_prose(
                    active_subtask=ordinary_task,
                    answer="Metric 10 million",
                    calculation_result=result,
                    selected_claim_ids=["ev1"],
                ),
                result,
            )

        multi_task = {
            "operation_family": "lookup",
            "required_operands": [{"label": "a"}, {"label": "b"}],
        }
        with patch.object(
            financial_lookup_recovery,
            "_extract_lookup_slot_from_answer_text",
            side_effect=AssertionError("multi-operand gate must stop before extraction"),
        ):
            self.assertIs(
                financial_lookup_recovery.synthesize_lookup_answer_slot_from_prose(
                    active_subtask=multi_task,
                    answer="Metric 10 million",
                    calculation_result=result,
                    selected_claim_ids=["ev1"],
                ),
                result,
            )

        task = {
            "operation_family": "lookup",
            "metric_family": "concept_revenue",
            "metric_label": "Metric",
            "required_operands": [
                {"label": "Metric", "concept": "revenue", "role": "primary_value", "nested": nested}
            ],
        }
        slot = {
            "status": "ok",
            "raw_value": "10",
            "raw_unit": "million",
            "rendered_value": "10 million",
            "normalized_value": 10_000_000.0,
            "normalized_unit": "KRW",
            "nested": nested,
        }
        events = []

        def material(actual_slot):
            events.append(("material", bool(actual_slot)))
            return bool(actual_slot.get("raw_value"))

        def extract(**kwargs):
            self.assertEqual(kwargs["answer"], " Metric 10 million ")
            self.assertIsNot(kwargs["operand"], task["required_operands"][0])
            self.assertEqual(kwargs["operand"], task["required_operands"][0])
            self.assertIs(kwargs["operand"]["nested"], nested)
            self.assertEqual(kwargs["metric_label"], "Metric")
            self.assertEqual(kwargs["selected_claim_ids"], ["ev1"])
            events.append(("extract", kwargs["answer"]))
            return slot

        validated = {"validated": True, "primary_value": slot}

        def validate(payload):
            self.assertIs(payload["primary_value"], slot)
            self.assertEqual(payload["operation_family"], "lookup")
            events.append(("validate", payload["operation_family"]))
            return validated

        with (
            patch.object(financial_lookup_recovery, "answer_slot_has_material", side_effect=material),
            patch.object(financial_lookup_recovery, "_extract_lookup_slot_from_answer_text", side_effect=extract),
            patch.object(financial_lookup_recovery, "validate_answer_slots_payload", side_effect=validate),
        ):
            synthesized = financial_lookup_recovery.synthesize_lookup_answer_slot_from_prose(
                active_subtask=task,
                answer=" Metric 10 million ",
                calculation_result=result,
                selected_claim_ids=["ev1"],
            )

        self.assertIsNot(synthesized, result)
        self.assertIs(synthesized["nested"], nested)
        self.assertEqual(synthesized["status"], "ok")
        self.assertEqual(synthesized["operation_family"], "lookup")
        self.assertEqual(synthesized["rendered_value"], "10 million")
        self.assertEqual(synthesized["formatted_result"], "Metric 10 million")
        self.assertIs(synthesized["answer_slots"], validated)
        self.assertEqual(events, [("material", False), ("extract", " Metric 10 million "), ("validate", "lookup")])
        self.assertEqual(result, result_frozen)
        self.assertIs(result["nested"], nested)

        existing = {"answer_slots": {"primary_value": {"raw_value": "existing"}}}
        with (
            patch.object(financial_lookup_recovery, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_lookup_recovery,
                "_extract_lookup_slot_from_answer_text",
                side_effect=AssertionError("material slot must stop before extraction"),
            ),
        ):
            self.assertIs(
                financial_lookup_recovery.synthesize_lookup_answer_slot_from_prose(
                    active_subtask=task,
                    answer="ignored",
                    calculation_result=existing,
                    selected_claim_ids=[],
                ),
                existing,
            )

        with (
            patch.object(financial_lookup_recovery, "answer_slot_has_material", return_value=False),
            patch.object(financial_lookup_recovery, "_extract_lookup_slot_from_answer_text", return_value=slot),
            patch.object(
                financial_lookup_recovery,
                "validate_answer_slots_payload",
                side_effect=RuntimeError("slot validation failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "slot validation failed"):
                financial_lookup_recovery.synthesize_lookup_answer_slot_from_prose(
                    active_subtask=task,
                    answer="Metric 10 million",
                    calculation_result=result,
                    selected_claim_ids=[],
                )

    def test_current_source_lookup_projection_supporting_doc_contract(self) -> None:
        class Doc:
            def __init__(self, text, metadata):
                self.page_content = text
                self.metadata = metadata

        nested = {"alias": True}
        docs = [
            Doc("Other 1,234 million", {"source_anchor": "wrong"}),
            Doc(
                "Revenue 1,234 million",
                {"company": "Acme", "year": "2023", "section_path": "Notes", "nested": nested},
            ),
            Doc("Revenue 1,234 million later", {"source_anchor": "later"}),
        ]
        task = {
            "task_id": "task_lookup",
            "required_operands": [{"surface_contract": {"positive": ["Revenue"]}}],
        }
        slot = {"label": "Metric", "raw_value": "1,234", "rendered_value": "1,234 million"}
        task_frozen = json.loads(json.dumps(task))
        slot_frozen = json.loads(json.dumps(slot))
        doc_texts = [doc.page_content for doc in docs]
        metadata_copies = [dict(doc.metadata) for doc in docs]

        with patch.object(financial_lookup_recovery, "operand_needles", return_value=[]):
            evidence = financial_lookup_recovery.lookup_slot_supporting_doc_evidence(
                active_subtask=task,
                slot=slot,
                docs=docs,
            )

        self.assertEqual(evidence["evidence_id"], "slot_support:task_lookup:primary_value")
        self.assertEqual(evidence["source_anchor"], "[Acme | 2023 | Notes]")
        self.assertEqual(evidence["claim"], "Revenue 1,234 million")
        self.assertEqual(evidence["quote_span"], "1,234 million")
        self.assertIsNot(evidence["metadata"], docs[1].metadata)
        self.assertIs(evidence["metadata"]["nested"], nested)
        self.assertEqual(task, task_frozen)
        self.assertEqual(slot, slot_frozen)
        self.assertEqual([doc.page_content for doc in docs], doc_texts)
        self.assertEqual([dict(doc.metadata) for doc in docs], metadata_copies)

        compact_slot = {"raw_value": "1,234", "rendered_value": "", "label": "Revenue"}
        compact_doc = Doc("Revenue 1234", {"source_anchor": "compact"})
        with patch.object(financial_lookup_recovery, "operand_needles", return_value=[]):
            compact = financial_lookup_recovery.lookup_slot_supporting_doc_evidence(
                active_subtask={"task_id": "task2"},
                slot=compact_slot,
                docs=[compact_doc],
            )
        self.assertEqual(compact["source_anchor"], "compact")

        class DocsBomb(list):
            def __iter__(self):
                raise AssertionError("blank values must stop before document iteration")

        self.assertIsNone(
            financial_lookup_recovery.lookup_slot_supporting_doc_evidence(
                active_subtask=task,
                slot={"raw_value": "", "rendered_value": ""},
                docs=DocsBomb(),
            )
        )

        downstream = []
        with (
            patch.object(
                financial_lookup_recovery,
                "_doc_page_content",
                side_effect=RuntimeError("document projection failed"),
            ),
            patch.object(
                financial_lookup_recovery,
                "_source_anchor_from_doc",
                side_effect=lambda *_args: downstream.append("anchor"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "document projection failed"):
                financial_lookup_recovery.lookup_slot_supporting_doc_evidence(
                    active_subtask=task,
                    slot=slot,
                    docs=docs,
                )
        self.assertEqual(downstream, [])

    def test_current_source_lookup_projection_static_binding_dag_and_baseline(self) -> None:
        planning_path = PROJECT_ROOT / "src" / "agent" / "financial_graph_planning.py"
        owner_path = PROJECT_ROOT / "src" / "agent" / "financial_lookup_recovery.py"
        planning_tree = ast.parse(planning_path.read_text(encoding="utf-8-sig"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8-sig"))
        targets = [
            "_money_match_to_slot_values",
            "_slot_values_match_operand_unit",
            "lookup_operand_matches_active_task",
            "refine_lookup_slot_unit_from_evidence",
            "_extract_lookup_slot_from_answer_text",
            "synthesize_lookup_answer_slot_from_prose",
            "_doc_metadata_value",
            "_doc_page_content",
            "_source_anchor_from_doc",
            "lookup_slot_supporting_doc_evidence",
        ]
        expected_spans = [16, 8, 27, 86, 91, 51, 5, 2, 14, 42]
        planning_defs = {
            node.name: node
            for node in planning_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in targets
        }
        self.assertEqual(planning_defs, {})
        owner_defs = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in targets
        }
        self.assertEqual(list(owner_defs), targets)
        self.assertEqual(
            [owner_defs[name].end_lineno - owner_defs[name].lineno + 1 for name in targets],
            expected_spans,
        )
        self.assertEqual(sum(expected_spans), 342)

        expected_signatures = {
            "_money_match_to_slot_values": (["match"], []),
            "_slot_values_match_operand_unit": (["values", "operand"], []),
            "lookup_operand_matches_active_task": (["operand", "active_subtask"], []),
            "refine_lookup_slot_unit_from_evidence": (["slot", "evidence"], []),
            "_extract_lookup_slot_from_answer_text": ([], ["answer", "operand", "metric_label", "selected_claim_ids"]),
            "synthesize_lookup_answer_slot_from_prose": (
                [],
                ["active_subtask", "answer", "calculation_result", "selected_claim_ids"],
            ),
            "_doc_metadata_value": (["doc", "key"], []),
            "_doc_page_content": (["doc"], []),
            "_source_anchor_from_doc": (["doc"], []),
            "lookup_slot_supporting_doc_evidence": ([], ["active_subtask", "slot", "docs"]),
        }
        for name, node in owner_defs.items():
            self.assertEqual(
                ([argument.arg for argument in node.args.args], [argument.arg for argument in node.args.kwonlyargs]),
                expected_signatures[name],
            )

        binding_names = ("_MONEY_SURFACE_RE", "_LOOKUP_YEAR_RE", "_LOOKUP_YEAR_LABEL_RE")
        bindings = []
        for node in owner_tree.body:
            if not isinstance(node, ast.Assign) or len(node.targets) != 1 or not isinstance(node.targets[0], ast.Name):
                continue
            if node.targets[0].id in binding_names:
                bindings.append(node)
                self.assertEqual(ast.unparse(node.value.func), "re.compile")
                self.assertIn("PLANNING_POLICY.get", ast.unparse(node.value))
        self.assertEqual([node.targets[0].id for node in bindings], list(binding_names))
        self.assertEqual([node.lineno for node in bindings], [28, 29, 30])

        class BindingVisitor(ast.NodeVisitor):
            def __init__(self, relative_path):
                self.relative_path = relative_path
                self.stack = []
                self.try_depth = 0
                self.calls = []

            def visit_FunctionDef(self, node):
                self.stack.append(node.name)
                self.generic_visit(node)
                self.stack.pop()

            def visit_Try(self, node):
                self.try_depth += 1
                self.generic_visit(node)
                self.try_depth -= 1

            def visit_Call(self, node):
                name = node.func.attr if isinstance(node.func, ast.Attribute) else (
                    node.func.id if isinstance(node.func, ast.Name) else ""
                )
                if name in targets:
                    receiver = ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "Name"
                    self.calls.append(
                        (
                            self.relative_path,
                            self.stack[-1],
                            name,
                            receiver,
                            len(node.args),
                            tuple(keyword.arg for keyword in node.keywords),
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        calls = []
        for path in sorted((PROJECT_ROOT / "src").rglob("*.py")):
            visitor = BindingVisitor(path.relative_to(PROJECT_ROOT).as_posix())
            visitor.visit(ast.parse(path.read_text(encoding="utf-8-sig")))
            calls.extend(visitor.calls)
        self.assertEqual(len(calls), 15)
        self.assertTrue(all(call[3] == "Name" and call[6] == 0 for call in calls))
        counts = {name: sum(call[2] == name for call in calls) for name in targets}
        self.assertEqual(
            counts,
            {
                "_money_match_to_slot_values": 3,
                "_slot_values_match_operand_unit": 2,
                "lookup_operand_matches_active_task": 1,
                "refine_lookup_slot_unit_from_evidence": 1,
                "_extract_lookup_slot_from_answer_text": 1,
                "synthesize_lookup_answer_slot_from_prose": 3,
                "_doc_metadata_value": 1,
                "_doc_page_content": 1,
                "_source_anchor_from_doc": 1,
                "lookup_slot_supporting_doc_evidence": 1,
            },
        )
        expected_external = {
            ("src/agent/financial_graph_planning.py", "_capture_current_subtask_result", "lookup_operand_matches_active_task"),
            ("src/agent/financial_graph_planning.py", "_capture_current_subtask_result", "refine_lookup_slot_unit_from_evidence"),
            ("src/agent/financial_graph_planning.py", "_capture_current_subtask_result", "synthesize_lookup_answer_slot_from_prose"),
            ("src/agent/financial_graph_planning.py", "_capture_current_subtask_result", "lookup_slot_supporting_doc_evidence"),
            ("src/agent/financial_graph_calculation.py", "_build_dependency_operand_rows", "synthesize_lookup_answer_slot_from_prose"),
            ("src/agent/financial_dependency_projection.py", "_dependency_lookup_slot_for_result_row", "synthesize_lookup_answer_slot_from_prose"),
        }
        external = {(call[0], call[1], call[2]) for call in calls if call[1] not in targets}
        self.assertEqual(external, expected_external)
        self.assertEqual(sum(call[1] in targets for call in calls), 9)

        public = []
        private = []
        for node in owner_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                (private if node.name.startswith("_") else public).append(node.name)
        self.assertEqual((len(public), len(private)), (15, 13))

        selected_nodes = set(bindings)
        for node in owner_defs.values():
            selected_nodes.update(ast.walk(node))
        for binding in bindings:
            selected_nodes.update(ast.walk(binding))
        planning_imports = {
            alias.name
            for node in planning_tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        for name in ("_normalise_operand_value", "operand_needles", "NUMERIC_UNIT_NORMALIZATION_POLICY"):
            self.assertNotIn(name, planning_imports)
        for name in ("re", "PLANNING_POLICY", "answer_slot_has_material", "validate_answer_slots_payload", "_normalise_spaces"):
            outside = [
                node
                for node in ast.walk(planning_tree)
                if isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == name
                and node not in selected_nodes
            ]
            self.assertTrue(outside, name)

        modules = {path.stem: path for path in (PROJECT_ROOT / "src" / "agent").glob("*.py")}
        edges = {name: set() for name in modules}
        for module_name, path in modules.items():
            module_tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(module_tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    dependency = node.module.rsplit(".", 1)[-1]
                    if dependency in modules:
                        edges[module_name].add(dependency)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("src.agent."):
                            dependency = alias.name.rsplit(".", 1)[-1]
                            if dependency in modules:
                                edges[module_name].add(dependency)
        def reaches(start, destination):
            pending = list(edges.get(start, set()))
            seen = set()
            while pending:
                current = pending.pop()
                if current == destination:
                    return True
                if current not in seen:
                    seen.add(current)
                    pending.extend(edges.get(current, set()))
            return False

        for dependency in (
            "financial_answer_slots",
            "financial_graph_model_loaders",
            "financial_graph_helpers",
            "financial_operand_resolution",
            "financial_surface_contracts",
        ):
            self.assertFalse(reaches(dependency, "financial_lookup_recovery"), dependency)
        self.assertFalse(reaches("financial_lookup_recovery", "financial_graph_planning"))
        self.assertFalse(reaches("financial_lookup_recovery", "financial_graph_calculation"))

        baseline = json.loads(
            (PROJECT_ROOT / "tests" / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_start = min(node.lineno for node in bindings)
        selected_end = max(node.end_lineno for node in owner_defs.values())
        selected_records = [
            record
            for record in baseline["records"]
            if record["path"] == "src/agent/financial_lookup_recovery.py"
            and any(selected_start <= line <= selected_end for line in record.get("first_lines") or [])
        ]
        self.assertEqual(selected_records, [])

    def test_current_source_lookup_projection_callers_pin_args_adoption_and_exception_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        nested = {"alias": True}
        operand = {
            "label": "Metric",
            "concept": "revenue",
            "matched_operand_role": "primary_value",
            "period": "2023",
            "raw_value": "10",
            "raw_unit": "",
            "normalized_value": 10.0,
            "normalized_unit": "UNKNOWN",
            "rendered_value": "10",
            "source_row_id": "operand_ev",
            "source_row_ids": ["operand_ev"],
            "nested": nested,
        }
        projected = {
            "calculation_operands": [operand],
            "calculation_plan": {"operation": "lookup"},
            "calculation_result": {},
            "reconciliation_result": {},
            "artifact_ids": ["artifact1"],
        }
        retrieved_doc = {"doc": "retrieved", "nested": nested}
        seed_doc = {"doc": "seed", "nested": nested}
        state = {
            "query": "Metric query",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "Metric",
                "operation_family": "lookup",
                "query": "Metric query",
            },
            "calc_subtasks": [{"task_id": "task_lookup"}],
            "answer": "Metric 10",
            "selected_claim_ids": ["answer_ev"],
            "retrieved_docs": [retrieved_doc],
            "seed_retrieved_docs": [seed_doc],
            "evidence_items": [],
        }
        state_frozen = json.loads(json.dumps(state))
        events = []
        active_copy = None
        support_evidence = {
            "evidence_id": "slot_ev",
            "source_anchor": "anchor",
            "claim": "Metric 10 million",
            "quote_span": "10 million",
            "metadata": {"unit_hint": "million", "nested": nested},
        }

        def promote(**kwargs):
            nonlocal active_copy
            self.assertIsNot(kwargs["active_subtask"], state["active_subtask"])
            self.assertEqual(kwargs["active_subtask"], state["active_subtask"])
            active_copy = kwargs["active_subtask"]
            events.append("promote")
            return kwargs["answer"], kwargs["status"], kwargs["calculation_result"]

        def active_match(actual_operand, actual_task):
            self.assertIsNot(actual_operand, operand)
            self.assertEqual(actual_operand, operand)
            self.assertIs(actual_operand["nested"], nested)
            self.assertIs(actual_task, active_copy)
            events.append("match")
            return True

        def validate(payload):
            self.assertEqual(payload["operation_family"], "lookup")
            self.assertEqual(payload["primary_value"]["raw_value"], "10")
            events.append("validate")
            return payload

        def support(*, active_subtask, slot, docs):
            self.assertIs(active_subtask, active_copy)
            self.assertEqual(slot["raw_value"], "10")
            self.assertIsNot(docs, state["retrieved_docs"])
            self.assertEqual(len(docs), 2)
            self.assertIs(docs[0], retrieved_doc)
            self.assertIs(docs[1], seed_doc)
            events.append("support")
            return support_evidence

        refined_slot = None

        def refine(slot, evidence):
            nonlocal refined_slot
            self.assertIs(evidence, support_evidence)
            self.assertIn("slot_ev", slot["source_row_ids"])
            events.append("refine")
            refined_slot = {
                **slot,
                "raw_unit": "million",
                "normalized_value": 10_000_000.0,
                "normalized_unit": "KRW",
                "rendered_value": "10 million",
            }
            return refined_slot

        def magnitude(slot, evidence):
            self.assertIs(slot, refined_slot)
            self.assertIs(evidence, support_evidence)
            events.append("magnitude")
            return slot

        def repair(actual_state, *, operands, plan, calculation_result):
            self.assertIs(actual_state, state)
            self.assertEqual(plan, {"operation": "lookup"})
            self.assertEqual(calculation_result["answer_slots"]["primary_value"]["raw_unit"], "million")
            self.assertEqual(operands[0]["raw_unit"], "million")
            events.append("repair")
            return SimpleNamespace(
                calculation_operands=operands,
                calculation_plan=plan,
                calculation_result=calculation_result,
                repair_applied=False,
                selected_evidence_ids=[],
            )

        with (
            patch.object(financial_graph_planning, "_project_task_trace_from_state", return_value=projected),
            patch.object(
                financial_graph_planning,
                "promote_nested_subtask_result_if_more_specific",
                side_effect=promote,
            ),
            patch.object(financial_graph_planning, "answer_slot_has_material", side_effect=lambda slot: bool(slot.get("raw_value"))),
            patch.object(financial_graph_planning, "lookup_operand_matches_active_task", side_effect=active_match),
            patch.object(financial_graph_planning, "validate_answer_slots_payload", side_effect=validate),
            patch.object(financial_graph_planning, "lookup_slot_supporting_doc_evidence", side_effect=support),
            patch.object(financial_graph_planning, "refine_lookup_slot_unit_from_evidence", side_effect=refine),
            patch.object(financial_graph_planning, "coerce_lookup_magnitude_record", side_effect=magnitude),
            patch.object(agent, "_repair_stale_calculation_result_from_operands", side_effect=repair),
        ):
            captured = agent._capture_current_subtask_result(state)

        self.assertEqual(events, ["promote", "match", "validate", "support", "refine", "magnitude", "repair"])
        self.assertEqual(captured["selected_claim_ids"], ["answer_ev", "slot_ev"])
        self.assertEqual([item["evidence_id"] for item in captured["runtime_evidence"]], ["slot_ev"])
        self.assertEqual(captured["calculation_result"]["rendered_value"], "10 million")
        self.assertIs(captured["calculation_result"]["answer_slots"]["primary_value"], refined_slot)
        self.assertEqual(captured["calculation_operands"][0]["raw_unit"], "million")
        self.assertEqual(state, state_frozen)
        self.assertIs(state["retrieved_docs"][0]["nested"], nested)
        self.assertIs(state["seed_retrieved_docs"][0]["nested"], nested)

        downstream = []
        with (
            patch.object(financial_graph_planning, "_project_task_trace_from_state", return_value=projected),
            patch.object(
                financial_graph_planning,
                "promote_nested_subtask_result_if_more_specific",
                side_effect=lambda **kwargs: (kwargs["answer"], kwargs["status"], kwargs["calculation_result"]),
            ),
            patch.object(financial_graph_planning, "answer_slot_has_material", return_value=False),
            patch.object(
                financial_graph_planning,
                "lookup_operand_matches_active_task",
                side_effect=RuntimeError("active match failed"),
            ),
            patch.object(
                financial_graph_planning,
                "synthesize_lookup_answer_slot_from_prose",
                side_effect=lambda **_kwargs: downstream.append("synthesize"),
            ),
            patch.object(
                financial_graph_planning,
                "lookup_slot_supporting_doc_evidence",
                side_effect=lambda **_kwargs: downstream.append("support"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "active match failed"):
                agent._capture_current_subtask_result(state)
        self.assertEqual(downstream, [])
        self.assertEqual(state, state_frozen)

        producer_task = {
            "task_id": "producer",
            "operation_family": "lookup",
            "metric_family": "concept_lookup",
            "metric_label": "Metric",
            "required_operands": [{"label": "Metric", "concept": "revenue"}],
        }
        result_row = {
            "task_id": "producer",
            "answer": " Metric 10 million ",
            "calculation_result": {},
            "selected_claim_ids": [" ev1 ", "", "ev2"],
        }
        result_row_frozen = json.loads(json.dumps(result_row))
        synthetic_slot = {"raw_value": "10", "rendered_value": "10 million", "nested": nested}
        synthetic_result = {"answer_slots": {"primary_value": synthetic_slot}}
        dependency_events = []

        def dependency_synth(**kwargs):
            self.assertIs(kwargs["active_subtask"], producer_task)
            self.assertEqual(kwargs["answer"], "Metric 10 million")
            self.assertEqual(kwargs["calculation_result"], {})
            self.assertEqual(kwargs["selected_claim_ids"], ["ev1", "ev2"])
            dependency_events.append("synthesize")
            return synthetic_result

        with (
            patch.object(financial_dependency_projection, "_dependency_producer_task", return_value=producer_task),
            patch.object(
                financial_dependency_projection,
                "synthesize_lookup_answer_slot_from_prose",
                side_effect=dependency_synth,
            ),
        ):
            dependency_slot = financial_dependency_projection._dependency_lookup_slot_for_result_row(
                result_row,
                task_by_id={"producer": producer_task},
                result_task_id="producer",
                slot_has_material=lambda slot: bool(slot.get("raw_value")),
            )
        self.assertEqual(dependency_events, ["synthesize"])
        self.assertEqual(dependency_slot, synthetic_slot)
        self.assertIsNot(dependency_slot, synthetic_slot)
        self.assertIs(dependency_slot["nested"], nested)
        self.assertEqual(result_row, result_row_frozen)

        with (
            patch.object(financial_dependency_projection, "_dependency_producer_task", return_value=producer_task),
            patch.object(
                financial_dependency_projection,
                "synthesize_lookup_answer_slot_from_prose",
                side_effect=RuntimeError("dependency synthesis failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "dependency synthesis failed"):
                financial_dependency_projection._dependency_lookup_slot_for_result_row(
                    result_row,
                    task_by_id={"producer": producer_task},
                    result_task_id="producer",
                    slot_has_material=lambda slot: bool(slot.get("raw_value")),
                )

        binding = {
            "label": "Metric",
            "concept": "revenue",
            "role": "primary_value",
            "source_preference": ["task_output"],
            "preferred_task_id": "producer",
        }
        calculation_state = {
            "active_subtask": {"inputs": [binding]},
            "calc_subtasks": [producer_task],
            "semantic_plan": {"tasks": []},
            "subtask_results": [result_row],
            "evidence_items": [],
            "runtime_evidence": [],
        }
        calculation_state_frozen = json.loads(json.dumps(calculation_state))
        calculation_events = []

        def calculation_synth(**kwargs):
            self.assertIsNot(kwargs["active_subtask"], producer_task)
            self.assertEqual(kwargs["active_subtask"], producer_task)
            self.assertIs(kwargs["active_subtask"]["required_operands"], producer_task["required_operands"])
            self.assertEqual(kwargs["answer"], "Metric 10 million")
            self.assertEqual(kwargs["calculation_result"], {})
            self.assertEqual(kwargs["selected_claim_ids"], ["ev1", "ev2"])
            calculation_events.append("synthesize")
            return synthetic_result

        def adopted_slot_gate(actual_binding, actual_slot, *, sibling_row, state):
            self.assertIsNot(actual_binding, binding)
            self.assertEqual(actual_binding, binding)
            self.assertEqual(actual_slot, synthetic_slot)
            self.assertIsNot(actual_slot, synthetic_slot)
            self.assertIs(actual_slot["nested"], nested)
            self.assertIsNot(sibling_row, result_row)
            self.assertEqual(sibling_row, result_row)
            self.assertIs(state, calculation_state)
            calculation_events.append("adopted")
            return False

        with (
            patch.object(
                financial_graph_calculation,
                "resolve_dependency_producer_scope",
                return_value=SimpleNamespace(producer_task=producer_task, preferred_statement_types=[]),
            ),
            patch.object(financial_graph_calculation, "answer_slot_has_material", side_effect=lambda slot: bool(slot.get("raw_value"))),
            patch.object(
                financial_graph_calculation,
                "synthesize_lookup_answer_slot_from_prose",
                side_effect=calculation_synth,
            ),
            patch.object(financial_graph_calculation, "dependency_slot_matches_input", side_effect=adopted_slot_gate),
        ):
            self.assertEqual(agent._build_dependency_operand_rows(calculation_state), [])
        self.assertEqual(calculation_events, ["synthesize", "adopted"])
        self.assertEqual(calculation_state, calculation_state_frozen)

        downstream.clear()
        with (
            patch.object(
                financial_graph_calculation,
                "resolve_dependency_producer_scope",
                return_value=SimpleNamespace(producer_task=producer_task, preferred_statement_types=[]),
            ),
            patch.object(financial_graph_calculation, "answer_slot_has_material", side_effect=lambda slot: bool(slot.get("raw_value"))),
            patch.object(
                financial_graph_calculation,
                "synthesize_lookup_answer_slot_from_prose",
                side_effect=RuntimeError("calculation synthesis failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "dependency_slot_matches_input",
                side_effect=lambda *_args, **_kwargs: downstream.append("match"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "calculation synthesis failed"):
                agent._build_dependency_operand_rows(calculation_state)
        self.assertEqual(downstream, [])
        self.assertEqual(calculation_state, calculation_state_frozen)

if __name__ == "__main__":
    unittest.main()
