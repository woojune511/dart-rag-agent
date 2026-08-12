import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
for path in (PROJECT_ROOT, SRC_ROOT):
    path_text = str(path)
    if path_text not in sys.path:
        sys.path.insert(0, path_text)

from src.agent import financial_aggregate_projection, financial_graph_calculation
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

if __name__ == "__main__":
    unittest.main()
