import ast
import inspect
import unittest
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from unittest.mock import Mock, patch

from src.agent import (
    financial_aggregate_projection,
    financial_answer_projection,
    financial_graph_calculation,
    financial_graph_planning,
)


class FinancialAnswerProjectionMaterialPolicyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.calculation_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        self.planning_agent = financial_graph_planning.FinancialAgentPlanningMixin()

    def test_growth_period_conflict_preserves_copy_fallback_text_and_exception_contract(self) -> None:
        conflict = financial_answer_projection.growth_row_has_conflicting_periods
        nested = {"preserve": True}
        events = []

        class FallbackBomb:
            def __bool__(self):
                raise AssertionError("calculation-result period fallback accessed")

            def __str__(self):
                raise AssertionError("calculation-result period fallback stringified")

            def __deepcopy__(self, _memo):
                return self

        class LoggedRow(dict):
            def get(self, key, default=None):
                events.append(("row-get", key))
                return super().get(key, default)

        current_slot = {"period": "slot-current", "nested": nested}
        prior_slot = {"period": "slot-prior", "nested": nested}
        row_slots = {"current_value": {"period": "ignored"}}
        row = LoggedRow({
            "answer": "2023 answer",
            "formatted_result": "2023 row formatted",
            "rendered_value": "",
            "answer_slots": row_slots,
            "calculation_result": {
                "answer_slots": {
                    "current_value": current_slot,
                    "prior_value": prior_slot,
                },
                "current_period": FallbackBomb(),
                "prior_period": FallbackBomb(),
                "formatted_result": "2023 result formatted",
                "rendered_value": "",
            },
            "nested": nested,
        })
        before = deepcopy(row)

        def period_hint(slot):
            events.append(("hint", slot))
            return "2023"

        def period_key(value):
            events.append(("key", value))
            return value

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        def findall(pattern, value):
            events.append(("findall", pattern, value))
            return ["2023", "2023"]

        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                side_effect=period_hint,
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=period_key,
            ),
            patch.object(
                financial_answer_projection,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_answer_projection.re,
                "findall",
                side_effect=findall,
            ),
        ):
            self.assertTrue(conflict(row))

        self.assertEqual([event[0] for event in events], [
            "row-get",
            "hint",
            "key",
            "hint",
            "key",
            "row-get",
            "row-get",
            "row-get",
            "normalize",
            "normalize",
            "findall",
        ])
        self.assertEqual(
            [event for event in events if event[0] == "row-get"],
            [
                ("row-get", "calculation_result"),
                ("row-get", "answer"),
                ("row-get", "formatted_result"),
                ("row-get", "rendered_value"),
            ],
        )
        self.assertEqual(
            [event[1] for event in events if event[0] == "normalize"],
            [
                "2023 answer 2023 row formatted ",
                "2023 result formatted ",
            ],
        )
        self.assertEqual(
            [event[1:] for event in events if event[0] == "findall"],
            [(r"20\d{2}", "2023 answer 2023 row formatted 2023 result formatted")],
        )
        hinted_slots = [event[1] for event in events if event[0] == "hint"]
        self.assertEqual(hinted_slots, [current_slot, prior_slot])
        self.assertIsNot(hinted_slots[0], current_slot)
        self.assertIsNot(hinted_slots[1], prior_slot)
        self.assertIs(hinted_slots[0]["nested"], nested)
        self.assertIs(hinted_slots[1]["nested"], nested)
        self.assertEqual(row, before)
        self.assertIs(row["nested"], nested)
        self.assertIs(row["answer_slots"], row_slots)

        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                return_value="2023",
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=lambda value: value,
            ),
            patch.object(
                financial_answer_projection.re,
                "findall",
                return_value=["2023", "2024"],
            ),
        ):
            self.assertFalse(conflict(row))

        class TextBomb(dict):
            def get(self, key, default=None):
                if key in {"answer", "formatted_result", "rendered_value"}:
                    raise AssertionError("text accessed after unequal periods")
                return super().get(key, default)

        fallback_row = TextBomb(
            {
                "calculation_result": {
                    "answer_slots": {
                        "current_value": {},
                        "prior_value": {},
                    },
                    "current_period": "2024",
                    "prior_period": "2023",
                }
            }
        )
        events.clear()
        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                side_effect=lambda slot: events.append(("hint", slot)) or "",
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=lambda value: events.append(("key", value)) or value,
            ),
        ):
            self.assertFalse(conflict(fallback_row))
        self.assertEqual(
            events,
            [("hint", {}), ("key", "2024"), ("hint", {}), ("key", "2023")],
        )

        later = Mock()
        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                side_effect=RuntimeError("hint failed"),
            ),
            patch.object(financial_answer_projection, "period_match_key", later),
        ):
            with self.assertRaisesRegex(RuntimeError, "hint failed"):
                conflict(row)
        later.assert_not_called()

        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                return_value="2023",
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=RuntimeError("key failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "key failed"):
                conflict(row)

        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                return_value="2023",
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=lambda value: value,
            ),
            patch.object(
                financial_answer_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("normalize failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalize failed"):
                conflict(row)

        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                return_value="2023",
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=lambda value: value,
            ),
            patch.object(
                financial_answer_projection.re,
                "findall",
                side_effect=RuntimeError("regex failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                conflict(row)

    def test_material_gap_preamble_and_aggregate_recursion_preserve_order_and_copies(self) -> None:
        feedback = financial_answer_projection.material_gap_feedback_for_subtask_result
        events = []

        class LoggedPolicy(Mapping):
            values = {
                "default_metric_label": "default",
                "lookup_missing_template": "LOOKUP<{metric_label}>",
            }

            def __iter__(self):
                events.append("policy.iter")
                return iter(self.values)

            def __len__(self):
                events.append("policy.len")
                return len(self.values)

            def __getitem__(self, key):
                events.append(("policy.item", key))
                return self.values[key]

        class LoggedRow(dict):
            def get(self, key, default=None):
                events.append(("row.get", key))
                return super().get(key, default)

        with patch.object(
            financial_answer_projection,
            "CALCULATION_FEEDBACK_POLICY",
            LoggedPolicy(),
        ), patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            return_value=False,
        ):
            self.assertEqual(
                feedback(
                    LoggedRow(
                        {
                            "metric_label": " metric ",
                            "calculation_result": {
                                "answer_slots": {
                                    "operation_family": "lookup",
                                    "primary_value": {},
                                }
                            },
                        }
                    )
                ),
                "LOOKUP<metric>",
            )
        first_row_event = next(index for index, event in enumerate(events) if event == ("row.get", "metric_label"))
        self.assertGreater(first_row_event, 0)
        self.assertTrue(all(
            event == "policy.iter" or event == "policy.len" or (
                isinstance(event, tuple) and event[0] == "policy.item"
            )
            for event in events[:first_row_event]
        ))

        nested = {"preserve": True}
        ready_row = {
            "task_id": "ready",
            "metric_label": "target",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {"material": True, "nested": nested},
                }
            },
            "nested": nested,
        }
        skipped_row = {
            "task_id": "skip",
            "metric_label": "other",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {"material": True},
                }
            },
        }
        missing_row = {
            "task_id": "missing",
            "metric_label": "target",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {"material": False, "nested": nested},
                }
            },
            "nested": nested,
        }
        stale_result_row = {
            "task_id": "stale",
            "metric_label": "target",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "lookup",
                    "primary_value": {"material": False},
                }
            },
        }
        aggregate_row = {
            "metric_label": "target",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [ready_row, skipped_row, missing_row],
                },
                "subtask_results": [stale_result_row],
            },
            "nested": nested,
        }
        before = deepcopy(aggregate_row)
        material_calls = []

        def has_material(slot):
            material_calls.append(slot)
            return bool(slot.get("material"))

        original = financial_answer_projection.material_gap_feedback_for_subtask_result
        with (
            patch.object(
                financial_answer_projection,
                "CALCULATION_FEEDBACK_POLICY",
                {
                    "lookup_missing_template": "LOOKUP<{metric_label}>",
                    "default_metric_label": "default",
                },
            ),
            patch.object(
                financial_answer_projection,
                "answer_slot_has_material",
                side_effect=has_material,
            ),
            patch.object(
                financial_answer_projection,
                "material_gap_feedback_for_subtask_result",
                wraps=original,
            ) as recursive,
        ):
            self.assertEqual(original(aggregate_row), "")

        recursive_rows = [args.args[0] for args in recursive.call_args_list]
        self.assertEqual([row["task_id"] for row in recursive_rows], ["missing", "ready"])
        self.assertEqual([slot["material"] for slot in material_calls], [False, True])
        self.assertTrue(all(
            current is not original_row
            for current, original_row in zip(recursive_rows, [missing_row, ready_row])
        ))
        self.assertTrue(all(row["nested"] is nested for row in recursive_rows))
        self.assertEqual(aggregate_row, before)
        self.assertIs(aggregate_row["nested"], nested)

        all_gap_row = {
            "metric_label": "target",
            "calculation_result": {
                "answer_slots": {
                    "operation_family": "aggregate_subtasks",
                    "subtask_results": [missing_row],
                }
            },
        }
        result_fallback_row = {
            "metric_label": "target",
            "calculation_result": {
                "answer_slots": {"operation_family": "aggregate_subtasks"},
                "subtask_results": [ready_row],
            },
        }
        for aggregate_case, expected_task_id in (
            (all_gap_row, "missing"),
            (result_fallback_row, "ready"),
        ):
            with self.subTest(aggregate_fallback=expected_task_id):
                with (
                    patch.object(
                        financial_answer_projection,
                        "CALCULATION_FEEDBACK_POLICY",
                        {
                            "lookup_missing_template": "LOOKUP<{metric_label}>",
                            "default_metric_label": "default",
                        },
                    ),
                    patch.object(
                        financial_answer_projection,
                        "answer_slot_has_material",
                        side_effect=has_material,
                    ),
                    patch.object(
                        financial_answer_projection,
                        "material_gap_feedback_for_subtask_result",
                        wraps=original,
                    ) as fallback_recursive,
                ):
                    self.assertEqual(original(aggregate_case), "")
                self.assertEqual(
                    [entry.args[0]["task_id"] for entry in fallback_recursive.call_args_list],
                    [expected_task_id],
                )

        with patch.object(
            financial_answer_projection,
            "material_gap_feedback_for_subtask_result",
            side_effect=RuntimeError("nested failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "nested failed"):
                original(aggregate_row)

    def test_material_gap_family_templates_laziness_and_exceptions_preserve_contract(self) -> None:
        feedback = financial_answer_projection.material_gap_feedback_for_subtask_result
        policy = {
            "default_metric_label": "DEFAULT",
            "lookup_missing_template": "LOOKUP<{metric_label}>",
            "generic_missing_material_template": "GENERIC<{metric_label}>",
            "default_current_period": "CURRENT",
            "default_prior_period": "PRIOR",
            "missing_period_value_template": "PERIOD<{period}>",
            "difference_missing_result_label": "DELTA",
            "growth_missing_result_label": "GROWTH",
            "missing_material_template": "MISSING<{metric_label}>[{missing_labels}]",
            "missing_material_joiner": "|",
            "missing_result_template": "RESULT<{metric_label}>",
        }

        def row_for(family, slots, **updates):
            row = {
                "metric_label": " metric ",
                "status": "missing",
                "calculation_plan": {"operation_family": family},
                "calculation_result": {"answer_slots": dict(slots)},
            }
            row.update(updates)
            return row

        material_calls = []

        def has_material(slot):
            material_calls.append(slot)
            return bool(slot.get("material"))

        with (
            patch.object(financial_answer_projection, "CALCULATION_FEEDBACK_POLICY", policy),
            patch.object(
                financial_answer_projection,
                "answer_slot_has_material",
                side_effect=has_material,
            ),
        ):
            self.assertEqual(
                feedback(row_for("lookup", {"primary_value": {"material": False}})),
                "LOOKUP<metric>",
            )
            self.assertEqual(
                feedback(row_for("single_value", {"primary_value": {"material": True}})),
                "",
            )

            material_calls.clear()
            difference_row = row_for(
                "difference",
                {
                    "current_value": {"name": "current", "material": False},
                    "prior_value": {"name": "prior", "material": True},
                    "primary_value": {"name": "primary", "material": False},
                },
                calculation_result={
                    "current_period": "2024",
                    "answer_slots": {
                        "current_value": {"name": "current", "material": False},
                        "prior_value": {"name": "prior", "material": True},
                        "primary_value": {"name": "primary", "material": False},
                    },
                },
            )
            self.assertEqual(
                feedback(difference_row),
                "MISSING<metric>[PERIOD<2024>|DELTA]",
            )
            self.assertEqual(
                [slot.get("name") for slot in material_calls],
                ["current", "prior", "primary"],
            )

            material_calls.clear()
            conflict_row = row_for(
                "growth_rate",
                {
                    "current_value": {"material": True},
                    "prior_value": {"material": True},
                    "primary_value": {"material": True},
                },
            )
            with patch.object(
                financial_answer_projection,
                "growth_row_has_conflicting_periods",
                return_value=True,
            ) as conflict:
                self.assertEqual(feedback(conflict_row), "GENERIC<metric>")
            conflict.assert_called_once_with(conflict_row)
            self.assertEqual(material_calls, [])

            material_calls.clear()
            incomplete_growth_slots = {
                "current_value": {"name": "current", "material": True},
                "prior_value": {"name": "prior", "material": False},
                "primary_value": {"name": "primary", "material": False},
            }
            incomplete_growth = row_for(
                "growth_rate",
                incomplete_growth_slots,
            )
            with patch.object(
                financial_answer_projection,
                "growth_row_has_conflicting_periods",
                return_value=False,
            ):
                self.assertEqual(
                    feedback(incomplete_growth),
                    "MISSING<metric>[PERIOD<PRIOR>|GROWTH]",
                )
            self.assertEqual(
                [slot.get("name") for slot in material_calls],
                ["current", "prior", "primary"],
            )

            complete_slots = {
                "current_value": {"material": True},
                "prior_value": {"material": True},
                "primary_value": {"material": False},
            }
            rendered_growth = row_for(
                "growth_rate",
                complete_slots,
                status=" OK ",
                calculation_result={
                    "formatted_result": "growth 12.5%",
                    "answer_slots": complete_slots,
                },
            )
            with patch.object(
                financial_answer_projection,
                "growth_row_has_conflicting_periods",
                return_value=False,
            ):
                self.assertEqual(feedback(rendered_growth), "")

            ratio_slots = {"primary_value": {"material": False}}
            ratio_row = row_for(
                "ratio",
                ratio_slots,
                status="ok",
                calculation_result={
                    "rendered_value": "ratio 0",
                    "answer_slots": ratio_slots,
                },
            )
            self.assertEqual(feedback(ratio_row), "")
            ratio_row["status"] = "missing"
            self.assertEqual(feedback(ratio_row), "RESULT<metric>")

        class LowerFamilyBomb(dict):
            def get(self, key, default=None):
                if key in {"calculation_plan", "metric_family"}:
                    raise AssertionError("lower operation family accessed")
                return super().get(key, default)

        dominant = LowerFamilyBomb(
            {
                "metric_label": "metric",
                "calculation_result": {
                    "answer_slots": {
                        "operation_family": "lookup",
                        "primary_value": {"material": True},
                    }
                },
            }
        )
        with (
            patch.object(financial_answer_projection, "CALCULATION_FEEDBACK_POLICY", policy),
            patch.object(financial_answer_projection, "answer_slot_has_material", return_value=True),
        ):
            self.assertEqual(feedback(dominant), "")

        precedence_cases = [
            (
                {
                    "calculation_plan": {"operation_family": "lookup", "operation": "sum"},
                    "calculation_result": {
                        "derived_metrics": {"operation_family": "ratio"},
                        "answer_slots": {"primary_value": {}},
                    },
                },
                "LOOKUP<DEFAULT>",
            ),
            (
                {
                    "calculation_plan": {"operation": "sum"},
                    "calculation_result": {
                        "derived_metrics": {"operation_family": "single_value"},
                        "answer_slots": {"primary_value": {}},
                    },
                },
                "LOOKUP<DEFAULT>",
            ),
            (
                {
                    "calculation_plan": {"operation": "sum"},
                    "calculation_result": {"answer_slots": {"primary_value": {}}},
                },
                "RESULT<DEFAULT>",
            ),
            (
                {
                    "metric_family": "concept_single_value",
                    "calculation_result": {"answer_slots": {"primary_value": {}}},
                },
                "LOOKUP<DEFAULT>",
            ),
        ]
        with (
            patch.object(financial_answer_projection, "CALCULATION_FEEDBACK_POLICY", policy),
            patch.object(financial_answer_projection, "answer_slot_has_material", return_value=False),
        ):
            for case, expected in precedence_cases:
                with self.subTest(precedence=expected):
                    self.assertEqual(feedback(case), expected)

        later = Mock()
        with (
            patch.object(financial_answer_projection, "CALCULATION_FEEDBACK_POLICY", policy),
            patch.object(
                financial_answer_projection,
                "_normalise_spaces",
                side_effect=RuntimeError("normalize failed"),
            ),
            patch.object(financial_answer_projection, "answer_slot_has_material", later),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalize failed"):
                feedback({"metric_label": "metric"})
        later.assert_not_called()

        material_owner = Mock(side_effect=RuntimeError("material failed"))
        with (
            patch.object(financial_answer_projection, "CALCULATION_FEEDBACK_POLICY", policy),
            patch.object(financial_answer_projection, "answer_slot_has_material", material_owner),
            patch.object(financial_answer_projection.re, "search", later),
        ):
            with self.assertRaisesRegex(RuntimeError, "material failed"):
                feedback(row_for("ratio", {"primary_value": {}}))

        with (
            patch.object(financial_answer_projection, "CALCULATION_FEEDBACK_POLICY", policy),
            patch.object(financial_answer_projection, "answer_slot_has_material", return_value=False),
            patch.object(
                financial_answer_projection.re,
                "search",
                side_effect=RuntimeError("regex failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                feedback(
                    row_for(
                        "sum",
                        {"primary_value": {}},
                        status="ok",
                        calculation_result={
                            "rendered_value": "1",
                            "answer_slots": {"primary_value": {}},
                        },
                    )
                )

        malformed_policy = dict(policy, lookup_missing_template="{")
        with (
            patch.object(
                financial_answer_projection,
                "CALCULATION_FEEDBACK_POLICY",
                malformed_policy,
            ),
            patch.object(financial_answer_projection, "answer_slot_has_material", return_value=False),
        ):
            with self.assertRaises(ValueError):
                feedback(row_for("lookup", {"primary_value": {}}))

    def test_subtask_row_material_preserves_precedence_laziness_copies_and_exceptions(self) -> None:
        has_material = financial_answer_projection.subtask_row_has_material
        nested = {"preserve": True}
        result_slots = {
            "primary_value": {"name": "primary", "material": False, "nested": nested},
            "current_value": {"name": "current", "material": False, "nested": nested},
            "prior_value": {"name": "prior", "material": True, "nested": nested},
            "delta_value": {"name": "delta", "material": True, "nested": nested},
        }
        row_slots = {"primary_value": {"material": True}}
        row = {
            "answer": "unread",
            "answer_slots": row_slots,
            "calculation_result": {
                "answer_slots": result_slots,
                "rendered_value": "unread",
                "source_row_ids": ["unread"],
            },
            "nested": nested,
        }
        before = deepcopy(row)
        calls = []

        def predicate(slot):
            calls.append(slot)
            return bool(slot.get("material"))

        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            side_effect=predicate,
        ):
            self.assertTrue(has_material(row))
        self.assertEqual([slot["name"] for slot in calls], ["primary", "current", "prior"])
        self.assertTrue(all(slot is not original for slot, original in zip(
            calls,
            [
                result_slots["primary_value"],
                result_slots["current_value"],
                result_slots["prior_value"],
            ],
        )))
        self.assertTrue(all(slot["nested"] is nested for slot in calls))
        self.assertEqual(row, before)
        self.assertIs(row["nested"], nested)
        self.assertIs(row["answer_slots"], row_slots)

        class LaterBomb(dict):
            def get(self, key, default=None):
                if key in {"answer", "source_row_ids"}:
                    raise AssertionError("later material fallback accessed")
                return super().get(key, default)

        blank_slots = {name: {"name": name} for name in (
            "primary_value",
            "current_value",
            "prior_value",
            "delta_value",
        )}
        rendered_row = {
            "answer": "unread",
            "calculation_result": LaterBomb(
                {"answer_slots": blank_slots, "rendered_value": " 0 "}
            ),
        }
        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            return_value=False,
        ) as predicate_owner:
            self.assertTrue(has_material(rendered_row))
        self.assertEqual(predicate_owner.call_count, 4)
        self.assertEqual(
            [entry.args[0]["name"] for entry in predicate_owner.call_args_list],
            ["primary_value", "current_value", "prior_value", "delta_value"],
        )

        answer_row = {
            "answer": " answer fallback ",
            "calculation_result": {"answer_slots": blank_slots, "rendered_value": ""},
        }
        source_row = {
            "answer": "",
            "calculation_result": {
                "answer_slots": blank_slots,
                "rendered_value": "",
                "source_row_ids": (item for item in ["source"]),
            },
        }
        empty_row = {
            "calculation_result": {
                "answer_slots": blank_slots,
                "source_row_ids": [],
            }
        }
        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            return_value=False,
        ):
            self.assertTrue(has_material(answer_row))
            self.assertTrue(has_material(source_row))
            self.assertFalse(has_material(empty_row))

        later = Mock()
        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            side_effect=RuntimeError("predicate failed"),
        ), patch.object(financial_answer_projection, "str", later, create=True):
            with self.assertRaisesRegex(RuntimeError, "predicate failed"):
                has_material(empty_row)
        later.assert_not_called()

        class StringBomb:
            def __str__(self):
                raise RuntimeError("rendered string failed")

        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            return_value=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "rendered string failed"):
                has_material(
                    {
                        "calculation_result": {
                            "answer_slots": blank_slots,
                            "rendered_value": StringBomb(),
                        }
                    }
                )

        class SourceIterationBomb:
            def __iter__(self):
                raise RuntimeError("source iteration failed")

        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            return_value=False,
        ):
            with self.assertRaisesRegex(RuntimeError, "source iteration failed"):
                has_material(
                    {
                        "calculation_result": {
                            "answer_slots": blank_slots,
                            "source_row_ids": SourceIterationBomb(),
                        }
                    }
                )

    def test_graph_and_planning_bindings_preserve_external32_args_gates_and_stop(self) -> None:
        modules = {
            "owner": financial_answer_projection,
            "aggregate": financial_aggregate_projection,
            "graph": financial_graph_calculation,
            "planning": financial_graph_planning,
        }
        targets = {
            "growth": "growth_row_has_conflicting_periods",
            "gap": "material_gap_feedback_for_subtask_result",
            "row": "subtask_row_has_material",
        }
        calls_by_target = {key: [] for key in targets}

        for module_name, module in modules.items():
            tree = ast.parse(inspect.getsource(module))
            parents = {}
            for parent in ast.walk(tree):
                for child in ast.iter_child_nodes(parent):
                    parents[child] = parent
            for target_key, target_name in targets.items():
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    if not (
                        isinstance(node.func, ast.Name)
                        and node.func.id == target_name
                    ):
                        continue
                    owner = node
                    while owner in parents and not isinstance(owner, ast.FunctionDef):
                        owner = parents[owner]
                    statement = node
                    while statement in parents and not isinstance(statement, ast.stmt):
                        statement = parents[statement]
                    calls_by_target[target_key].append(
                        {
                            "module": module_name,
                            "caller": owner.name,
                            "arg": ast.unparse(node.args[0]),
                            "call": node,
                            "statement": statement,
                            "parents": parents,
                        }
                    )

        internal_growth = [
            entry for entry in calls_by_target["growth"]
            if entry["caller"] == targets["gap"]
        ]
        internal_gap = [
            entry for entry in calls_by_target["gap"]
            if entry["caller"] == targets["gap"]
        ]
        self.assertEqual(
            [(entry["module"], entry["caller"], entry["arg"]) for entry in internal_growth],
            [("owner", targets["gap"], "row")],
        )
        self.assertEqual(
            [(entry["module"], entry["caller"], entry["arg"]) for entry in internal_gap],
            [("owner", targets["gap"], "dict(nested_row)")],
        )

        external_growth = [entry for entry in calls_by_target["growth"] if entry not in internal_growth]
        external_gap = [entry for entry in calls_by_target["gap"] if entry not in internal_gap]
        external_row = calls_by_target["row"]
        self.assertEqual(
            Counter(
                (entry["module"], entry["caller"], entry["arg"])
                for entry in external_growth
            ),
            Counter(
                {
                    ("graph", "_preferred_complete_numeric_answer", "row"): 1,
                    ("aggregate", "ensure_complete_growth_numeric_answer", "row"): 1,
                    ("graph", "_final_growth_answer_without_untraced_numeric_sentences", "row"): 1,
                    ("graph", "_enforce_source_stated_growth_answer_contract", "row"): 1,
                    ("aggregate", "has_strong_growth_trace_for_answer_refresh", "row"): 1,
                    ("aggregate", "strip_untraced_numeric_material_from_growth_narrative_sentence", "row"): 1,
                    ("aggregate", "growth_answer_has_untraced_numeric_material", "row"): 1,
                    ("aggregate", "narrative_summary_conflicts_with_growth_trace", "row"): 1,
                    ("aggregate", "growth_narrative_numeric_incompatible_with_trace", "row"): 1,
                    ("graph", "_is_growth_supported_sentence", "row"): 1,
                    ("graph", "_compose_growth_narrative_answer", "row"): 1,
                    ("graph", "_answer_satisfies_growth_narrative_intent", "row"): 1,
                    ("aggregate", "build_aggregate_calculation_projection", "dict(row)"): 1,
                }
            ),
        )
        self.assertEqual(
            Counter(
                (entry["module"], entry["caller"], entry["arg"])
                for entry in external_gap
            ),
            Counter(
                {
                    ("graph", "_feedback_gap_is_satisfied_by_derived_slots", "row"): 1,
                    ("graph", "_unresolved_structured_numeric_gap", "row"): 1,
                    ("aggregate", "safe_partial_answer_for_numeric_gap", "row"): 1,
                    ("aggregate", "compose_lookup_list_numeric_answer", "row"): 1,
                    ("aggregate", "append_uncovered_lookup_numeric_items", "row"): 1,
                    ("graph", "_preferred_complete_numeric_answer", "row"): 1,
                    ("graph", "_numeric_projection_coverage_targets", "row"): 1,
                    ("graph", "_infer_planner_feedback_from_answer_slots", "row"): 2,
                    ("aggregate", "_aggregate_result_rank", "row"): 1,
                    ("aggregate", "nested_aggregate_result_rank", "row"): 1,
                    ("aggregate", "promote_stronger_nested_aggregate_results", "dict(nested_row)"): 1,
                    ("aggregate", "promote_stronger_nested_aggregate_results", "current_row"): 1,
                    ("graph", "_resolve_aggregate_feedback_state", "row"): 1,
                    ("aggregate", "build_aggregate_calculation_projection", "dict(row)"): 1,
                }
            ),
        )
        self.assertEqual(
            Counter(
                (entry["module"], entry["caller"], entry["arg"])
                for entry in external_row
            ),
            Counter(
                {
                    ("aggregate", "nested_aggregate_result_rank", "row"): 1,
                    ("owner", "_subtask_row_specificity_score", "row"): 1,
                    (
                        "owner",
                        "promote_nested_subtask_result_if_more_specific",
                        "{'answer': answer, 'status': status, 'metric_family': active_subtask.get('metric_family'), 'metric_label': active_subtask.get('metric_label'), 'operation_family': active_operation, 'calculation_result': calculation_result}",
                    ): 1,
                    ("aggregate", "_subtask_upsert_quality_rank", "row"): 1,
                }
            ),
        )
        self.assertEqual(
            (len(external_growth), len(external_gap), len(external_row)),
            (13, 15, 4),
        )

        projection_growth = next(
            entry
            for entry in external_growth
            if entry["caller"] == "build_aggregate_calculation_projection"
        )
        graph_growth = [entry for entry in external_growth if entry["module"] == "graph"]
        aggregate_growth = [
            entry
            for entry in external_growth
            if entry["module"] == "aggregate" and entry is not projection_growth
        ]
        self.assertEqual((len(graph_growth), len(aggregate_growth)), (6, 6))
        for entry in [*graph_growth, *aggregate_growth]:
            statement = entry["statement"]
            self.assertIsInstance(statement, ast.If)
            self.assertIsInstance(statement.body[0], ast.Continue)
            ancestor = entry["call"]
            unary_not = False
            while ancestor is not statement:
                ancestor = entry["parents"][ancestor]
                unary_not = unary_not or (
                    isinstance(ancestor, ast.UnaryOp)
                    and isinstance(ancestor.op, ast.Not)
                )
            self.assertFalse(unary_not)

        self.assertIsInstance(projection_growth["statement"], ast.Assign)
        self.assertEqual(
            ast.unparse(projection_growth["statement"].targets[0]),
            "is_conflicting_growth",
        )

        positive_continue_gap_callers = {
            "_feedback_gap_is_satisfied_by_derived_slots",
            "safe_partial_answer_for_numeric_gap",
            "compose_lookup_list_numeric_answer",
            "append_uncovered_lookup_numeric_items",
            "_preferred_complete_numeric_answer",
            "_numeric_projection_coverage_targets",
        }
        for entry in external_gap:
            if entry["caller"] not in positive_continue_gap_callers:
                continue
            self.assertIsInstance(entry["statement"], ast.If)
            self.assertIsInstance(entry["statement"].body[0], ast.Continue)

        rank_targets = {
            "_aggregate_result_rank": "material_rank",
            "nested_aggregate_result_rank": "gap_free_rank",
        }
        for caller, target in rank_targets.items():
            entry = next(item for item in external_gap if item["caller"] == caller)
            self.assertIsInstance(entry["statement"], ast.Assign)
            self.assertEqual(ast.unparse(entry["statement"].targets[0]), target)
            self.assertIsInstance(entry["statement"].value, ast.IfExp)

        nested_row_rank = next(
            entry
            for entry in external_row
            if entry["caller"] == "nested_aggregate_result_rank"
        )
        self.assertEqual(ast.unparse(nested_row_rank["statement"].targets[0]), "material_rank")
        self.assertIsInstance(nested_row_rank["statement"].value, ast.IfExp)

        row = {"task_id": "growth", "nested": {"preserve": True}}
        ordered_results = [row]
        compose_owner = Mock(return_value="replacement")
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="growth_rate",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_row_has_conflicting_periods",
                return_value=True,
            ) as growth_owner,
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                compose_owner,
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                    " keep answer ",
                    ordered_results,
                ),
                "keep answer",
            )
        growth_owner.assert_called_once_with(row)
        compose_owner.assert_not_called()

        compose_owner.reset_mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="growth_rate",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_row_has_conflicting_periods",
                side_effect=RuntimeError("growth binding failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "compose_complete_growth_numeric_answer",
                compose_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "growth binding failed"):
                financial_aggregate_projection.ensure_complete_growth_numeric_answer(
                    "answer",
                    ordered_results,
                )
        compose_owner.assert_not_called()

        rank_row = {
            "status": "ok",
            "answer": "answer 10",
            "calculation_result": {"source_row_ids": ["source"]},
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="gap",
            ) as gap_owner,
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                return_value=6,
            ),
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_dependency_coherence_ranks",
                return_value=(5, 4),
            ),
        ):
            self.assertEqual(
                financial_aggregate_projection._aggregate_result_rank(rank_row),
                (4, 0, 1, 6, 5, 4, 1),
            )
        gap_owner.assert_called_once_with(rank_row)

        later = Mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=RuntimeError("gap binding failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                later,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "gap binding failed"):
                financial_aggregate_projection._aggregate_result_rank(rank_row)
        later.assert_not_called()

        with (
            patch.object(
                financial_aggregate_projection,
                "subtask_row_has_material",
                return_value=True,
            ) as row_owner,
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ) as nested_gap_owner,
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="lookup",
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_operand_sign_consistency_rank",
                return_value=1,
            ),
        ):
            nested_rank = financial_aggregate_projection.nested_aggregate_result_rank(rank_row)
        self.assertEqual(nested_rank[:5], (4, 1, 1, 1, 1))
        row_owner.assert_called_once_with(rank_row)
        nested_gap_owner.assert_called_once_with(rank_row)

        nested_gap_owner.reset_mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "subtask_row_has_material",
                side_effect=RuntimeError("row binding failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                nested_gap_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "row binding failed"):
                financial_aggregate_projection.nested_aggregate_result_rank(rank_row)
        nested_gap_owner.assert_not_called()

        nested = {"preserve": True}
        planning_row = {"task_id": "growth", "nested": nested}
        planning_events = []

        def planning_growth_owner(prepared_row):
            planning_events.append(("growth", prepared_row))
            return True

        def planning_gap_owner(prepared_row):
            planning_events.append(("gap", prepared_row))
            return "material gap"

        built_projection = {
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
        }
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="growth_rate",
                create=True,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_row_has_conflicting_periods",
                side_effect=planning_growth_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                side_effect=planning_gap_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "_build_aggregate_calculation_projection",
                return_value=built_projection,
            ) as builder,
        ):
            projection = financial_aggregate_projection.build_aggregate_calculation_projection(
                [planning_row],
                "answer",
            )
        self.assertEqual(
            projection,
            {
                "calculation_operands": [],
                "calculation_plan": {},
                "calculation_result": {},
                "evidence_items": [],
            },
        )
        self.assertEqual([event[0] for event in planning_events], ["growth", "gap"])
        for _, prepared_row in planning_events:
            self.assertEqual(prepared_row, planning_row)
            self.assertIsNot(prepared_row, planning_row)
            self.assertIs(prepared_row["nested"], nested)
        builder.assert_called_once()

        gap_after_growth = Mock()
        builder.reset_mock()
        with (
            patch.object(
                financial_aggregate_projection,
                "aggregate_result_operation_family",
                return_value="growth_rate",
                create=True,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_row_has_conflicting_periods",
                side_effect=RuntimeError("planning growth failed"),
            ),
            patch.object(
                financial_aggregate_projection,
                "material_gap_feedback_for_subtask_result",
                gap_after_growth,
            ),
            patch.object(
                financial_aggregate_projection,
                "_build_aggregate_calculation_projection",
                builder,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "planning growth failed"):
                financial_aggregate_projection.build_aggregate_calculation_projection(
                    [planning_row],
                    "answer",
                )
        gap_after_growth.assert_not_called()
        builder.assert_not_called()

        specificity_row = {
            "task_id": "task",
            "status": "ok",
            "metric_family": "family",
            "metric_label": "label",
        }
        active_subtask = dict(specificity_row, operation_family="lookup")
        with (
            patch.object(
                financial_answer_projection,
                "_subtask_row_operation_family",
                return_value="lookup",
            ),
            patch.object(
                financial_answer_projection,
                "subtask_row_has_material",
                return_value=True,
            ) as specificity_owner,
        ):
            specificity = financial_answer_projection._subtask_row_specificity_score(
                specificity_row,
                active_subtask=active_subtask,
            )
        self.assertEqual(specificity[:2], (4, 1))
        specificity_owner.assert_called_once_with(specificity_row)

        current_result = {"subtask_results": [{"task_id": "nested"}]}
        best_row = {"task_id": "best", "calculation_result": {"status": "ok"}}
        with (
            patch.object(
                financial_answer_projection,
                "nested_subtask_rows",
                return_value=[best_row],
            ),
            patch.object(
                financial_answer_projection,
                "_subtask_row_specificity_score",
                return_value=(3, 1, 1, 1, 1, 1),
            ),
            patch.object(
                financial_answer_projection,
                "subtask_row_has_material",
                return_value=True,
            ) as current_owner,
        ):
            promoted = financial_answer_projection.promote_nested_subtask_result_if_more_specific(
                active_subtask={
                    "operation_family": "lookup",
                    "metric_family": "family",
                    "metric_label": "label",
                },
                answer="current answer",
                status="partial",
                calculation_result=current_result,
            )
        self.assertEqual(promoted, ("current answer", "partial", current_result))
        current_owner.assert_called_once_with(
            {
                "answer": "current answer",
                "status": "partial",
                "metric_family": "family",
                "metric_label": "label",
                "operation_family": "lookup",
                "calculation_result": current_result,
            }
        )

        with patch.object(
            financial_aggregate_projection,
            "subtask_row_has_material",
            return_value=False,
        ) as upsert_owner:
            upsert_rank = financial_aggregate_projection._subtask_upsert_quality_rank(
                {"status": "ok", "answer": "10"}
            )
        self.assertEqual(upsert_rank[:2], (4, 0))
        upsert_owner.assert_called_once_with({"status": "ok", "answer": "10"})

    def test_current_source_nested_rows_preserve_depth_first_copies_and_exceptions(self) -> None:
        shared = {"preserve": True}
        leaf = {"task_id": "leaf", "nested": shared}
        grandchild = {
            "task_id": "grandchild",
            "nested": shared,
            "calculation_result": {"answer_slots": {"subtask_results": [leaf]}},
        }
        direct = {
            "task_id": "direct",
            "nested": shared,
            "calculation_result": {"subtask_results": [grandchild]},
        }
        slotted = {"task_id": "slotted", "nested": shared}

        class IgnoredChild:
            def __deepcopy__(self, _memo):
                return self

        ignored = IgnoredChild()
        calculation_result = {
            "subtask_results": [direct, ignored],
            "answer_slots": {"subtask_results": [slotted]},
        }
        before = deepcopy(calculation_result)

        rows = financial_answer_projection.nested_subtask_rows(calculation_result)

        self.assertEqual(
            [row["task_id"] for row in rows],
            ["direct", "grandchild", "leaf", "slotted"],
        )
        for projected, original in zip(rows, (direct, grandchild, leaf, slotted)):
            self.assertEqual(projected, original)
            self.assertIsNot(projected, original)
            self.assertIs(projected["nested"], shared)
        self.assertEqual(calculation_result, before)
        self.assertIs(calculation_result["subtask_results"][0], direct)
        self.assertIs(calculation_result["answer_slots"]["subtask_results"][0], slotted)

        class FalsyMapping(Mapping):
            def __bool__(self):
                return False

            def __getitem__(self, _key):
                raise AssertionError("falsy mapping was copied")

            def __iter__(self):
                raise AssertionError("falsy mapping was iterated")

            def __len__(self):
                raise AssertionError("falsy mapping length was read")

        self.assertEqual(financial_answer_projection.nested_subtask_rows(FalsyMapping()), [])

        class CopyBomb(Mapping):
            def __getitem__(self, _key):
                raise AssertionError("mapping value access was unexpected")

            def __iter__(self):
                raise RuntimeError("nested root copy failed")

            def __len__(self):
                return 1

        with self.assertRaisesRegex(RuntimeError, "nested root copy failed"):
            financial_answer_projection.nested_subtask_rows(CopyBomb())

    def test_current_source_subtask_operation_and_specificity_preserve_precedence_and_ranks(self) -> None:
        class FallbackBomb:
            def __bool__(self):
                raise AssertionError("lower-priority operation family accessed")

            def __str__(self):
                raise AssertionError("lower-priority operation family stringified")

        self.assertEqual(
            financial_answer_projection._subtask_row_operation_family(
                {
                    "operation_family": " Lookup ",
                    "answer_slots": {"operation_family": FallbackBomb()},
                    "calculation_result": {"operation_family": FallbackBomb()},
                }
            ),
            "lookup",
        )
        self.assertEqual(
            financial_answer_projection._subtask_row_operation_family(
                {
                    "answer_slots": {"operation_family": " Difference "},
                    "calculation_result": {"operation_family": "growth_rate"},
                }
            ),
            "difference",
        )
        self.assertEqual(
            financial_answer_projection._subtask_row_operation_family(
                {"calculation_result": {"subtask_results": [{"task_id": "child"}]}}
            ),
            "aggregate_subtasks",
        )
        self.assertEqual(
            financial_answer_projection._subtask_row_operation_family(
                {"metric_family": " Concept_Custom_Metric "}
            ),
            "custom_metric",
        )
        self.assertEqual(financial_answer_projection._subtask_row_operation_family({}), "")

        active_subtask = {
            "task_id": "task",
            "metric_family": "family",
            "metric_label": "Revenue Growth",
            "operation_family": "lookup",
        }
        row = {
            "task_id": "task",
            "status": "ready",
            "metric_family": "family",
            "metric_label": "Revenue Growth",
        }
        with (
            patch.object(financial_answer_projection, "_subtask_row_operation_family", return_value="lookup") as operation_owner,
            patch.object(financial_answer_projection, "subtask_row_has_material", return_value=True) as material_owner,
        ):
            self.assertEqual(
                financial_answer_projection._subtask_row_specificity_score(
                    row,
                    active_subtask=active_subtask,
                ),
                (2, 1, 1, 1, 1, 3),
            )
        operation_owner.assert_called_once_with(row)
        material_owner.assert_called_once_with(row)

        for metric_label, expected_rank in (
            ("Revenue", 2),
            ("Annual Growth", 1),
            ("Unrelated Metric", 0),
        ):
            with (
                patch.object(financial_answer_projection, "_subtask_row_operation_family", return_value="aggregate_subtasks"),
                patch.object(financial_answer_projection, "subtask_row_has_material", return_value=False),
            ):
                score = financial_answer_projection._subtask_row_specificity_score(
                    {**row, "status": "ok", "metric_label": metric_label},
                    active_subtask=active_subtask,
                )
            self.assertEqual(score, (4, 0, 0, 0, 1, expected_rank))

        never_material = Mock()
        with (
            patch.object(financial_answer_projection, "_subtask_row_operation_family", return_value="lookup"),
            patch.object(financial_answer_projection, "subtask_row_has_material", never_material),
        ):
            self.assertEqual(
                financial_answer_projection._subtask_row_specificity_score(
                    {**row, "task_id": "other"},
                    active_subtask=active_subtask,
                ),
                (0, 0, 0, 0, 0, 0),
            )
        never_material.assert_not_called()

        later_material = Mock()
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=RuntimeError("specificity normalization failed")),
            patch.object(financial_answer_projection, "subtask_row_has_material", later_material),
        ):
            with self.assertRaisesRegex(RuntimeError, "specificity normalization failed"):
                financial_answer_projection._subtask_row_specificity_score(row, active_subtask=active_subtask)
        later_material.assert_not_called()

        with (
            patch.object(financial_answer_projection, "_subtask_row_operation_family", return_value="lookup"),
            patch.object(financial_answer_projection, "subtask_row_has_material", side_effect=RuntimeError("specificity material failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "specificity material failed"):
                financial_answer_projection._subtask_row_specificity_score(row, active_subtask=active_subtask)

    def test_current_source_nested_promotion_preserves_gates_stable_tie_and_identity(self) -> None:
        active_subtask = {
            "operation_family": "lookup",
            "metric_family": "family",
            "metric_label": "label",
        }
        current_result = {
            "subtask_results": [{"task_id": "nested"}],
            "nested": {"current": True},
        }
        unchanged = ("current", "partial", current_result)
        nested_owner = Mock()
        for inactive in ({}, {"operation_family": "aggregate_subtasks"}):
            with patch.object(financial_answer_projection, "nested_subtask_rows", nested_owner):
                self.assertEqual(
                    financial_answer_projection.promote_nested_subtask_result_if_more_specific(
                        active_subtask=inactive,
                        answer="current",
                        status="partial",
                        calculation_result=current_result,
                    ),
                    unchanged,
                )
        nested_owner.assert_not_called()

        no_children = {"nested": {"preserve": True}}
        with patch.object(financial_answer_projection, "nested_subtask_rows", nested_owner):
            result = financial_answer_projection.promote_nested_subtask_result_if_more_specific(
                active_subtask=active_subtask,
                answer="current",
                status="partial",
                calculation_result=no_children,
            )
        self.assertEqual(result, ("current", "partial", no_children))
        self.assertIs(result[2], no_children)
        nested_owner.assert_not_called()

        shared = {"preserve": True}
        skipped = {"task_id": "skip", "calculation_result": {"status": "ok"}}
        best_result = {"status": "ok", "formatted_result": " first answer ", "nested": shared}
        best = {"task_id": "first", "calculation_result": best_result}
        tied = {
            "task_id": "second",
            "answer": "second answer",
            "calculation_result": {"status": "ok", "nested": shared},
        }
        scores = {
            "skip": (0, 0, 1, 1, 1, 1),
            "first": (4, 1, 1, 1, 1, 3),
            "second": (4, 1, 1, 1, 1, 3),
        }
        before_current = deepcopy(current_result)
        before_rows = deepcopy([skipped, best, tied])
        with (
            patch.object(financial_answer_projection, "nested_subtask_rows", return_value=[skipped, best, tied]) as projected_rows,
            patch.object(
                financial_answer_projection,
                "_subtask_row_specificity_score",
                side_effect=lambda row, *, active_subtask: scores[row["task_id"]],
            ) as score_owner,
            patch.object(financial_answer_projection, "_subtask_row_operation_family", return_value="lookup") as operation_owner,
            patch.object(financial_answer_projection, "subtask_row_has_material", return_value=False) as material_owner,
        ):
            promoted = financial_answer_projection.promote_nested_subtask_result_if_more_specific(
                active_subtask=active_subtask,
                answer="current",
                status="partial",
                calculation_result=current_result,
            )
        self.assertEqual(promoted[:2], ("first answer", "ok"))
        self.assertEqual(promoted[2], best_result)
        self.assertIsNot(promoted[2], best_result)
        self.assertIs(promoted[2]["nested"], shared)
        projected_rows.assert_called_once_with(current_result)
        self.assertEqual([call.args[0]["task_id"] for call in score_owner.call_args_list], ["skip", "first", "second"])
        for call in score_owner.call_args_list:
            self.assertIs(call.kwargs["active_subtask"], active_subtask)
        operation_owner.assert_called_once_with(best)
        material_owner.assert_called_once()
        self.assertEqual(current_result, before_current)
        self.assertEqual([skipped, best, tied], before_rows)

        downstream_score = Mock()
        with (
            patch.object(financial_answer_projection, "nested_subtask_rows", side_effect=RuntimeError("nested projection failed")),
            patch.object(financial_answer_projection, "_subtask_row_specificity_score", downstream_score),
        ):
            with self.assertRaisesRegex(RuntimeError, "nested projection failed"):
                financial_answer_projection.promote_nested_subtask_result_if_more_specific(
                    active_subtask=active_subtask,
                    answer="current",
                    status="partial",
                    calculation_result=current_result,
                )
        downstream_score.assert_not_called()
        self.assertEqual(current_result, before_current)

    def test_current_source_nested_selection_pins_exact_bindings_dag_and_baseline(self) -> None:
        import json
        from pathlib import Path

        targets = {
            "nested_subtask_rows": 20,
            "_subtask_row_operation_family": 19,
            "_subtask_row_specificity_score": 37,
            "promote_nested_subtask_result_if_more_specific": 50,
        }
        retired_targets = {
            "_" + "nested_subtask_rows",
            "_" + "promote_nested_subtask_result_if_more_specific",
        }
        paths = {
            "planning": Path("src/agent/financial_graph_planning.py"),
            "calculation": Path("src/agent/financial_graph_calculation.py"),
            "aggregate": Path("src/agent/financial_aggregate_projection.py"),
            "owner": Path("src/agent/financial_answer_projection.py"),
        }
        trees = {
            name: ast.parse(path.read_text(encoding="utf-8-sig"))
            for name, path in paths.items()
        }
        selected_owner_defs = {
            node.name: node
            for node in trees["owner"].body
            if isinstance(node, ast.FunctionDef) and node.name in targets
        }
        self.assertEqual(
            {name: node.end_lineno - node.lineno + 1 for name, node in selected_owner_defs.items()},
            targets,
        )
        owner_defs = [node for node in trees["owner"].body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in owner_defs),
                sum(node.name.startswith("_") for node in owner_defs),
            ),
            (12, 9),
        )
        self.assertFalse(
            any(
                isinstance(node, ast.FunctionDef) and node.name in retired_targets
                for tree in trees.values()
                for node in ast.walk(tree)
            )
        )

        calls = []
        for module_name, tree in trees.items():
            parents = {
                child: parent
                for parent in ast.walk(tree)
                for child in ast.iter_child_nodes(parent)
            }
            functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                call_name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                if call_name not in targets:
                    continue
                containers = [
                    candidate
                    for candidate in functions
                    if candidate.lineno <= node.lineno <= candidate.end_lineno
                ]
                caller = min(containers, key=lambda item: item.end_lineno - item.lineno)
                current = node
                try_depth = 0
                while current in parents:
                    current = parents[current]
                    if isinstance(current, ast.Try):
                        try_depth += 1
                calls.append(
                    (
                        module_name,
                        caller.name,
                        call_name,
                        ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "",
                        tuple(ast.unparse(arg) for arg in node.args),
                        tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                        try_depth,
                    )
                )
        self.assertCountEqual(
            calls,
            [
                ("owner", "promote_nested_subtask_result_if_more_specific", "nested_subtask_rows", "", ("calculation_result",), (), 0),
                ("aggregate", "promote_stronger_nested_aggregate_results", "nested_subtask_rows", "", ("calculation_result",), (), 0),
                ("owner", "_subtask_row_specificity_score", "_subtask_row_operation_family", "", ("row",), (), 0),
                ("owner", "promote_nested_subtask_result_if_more_specific", "_subtask_row_operation_family", "", ("best_row",), (), 0),
                ("owner", "promote_nested_subtask_result_if_more_specific", "_subtask_row_specificity_score", "", ("row",), (("active_subtask", "active_subtask"),), 0),
                (
                    "planning",
                    "_capture_current_subtask_result",
                    "promote_nested_subtask_result_if_more_specific",
                    "",
                    (),
                    (("active_subtask", "active_subtask"), ("answer", "answer"), ("status", "status"), ("calculation_result", "calculation_result")),
                    0,
                ),
            ],
        )
        self.assertEqual(sum(targets.values()), 126)
        self.assertEqual(20 + 19 + 38 + 51, 128)
        self.assertEqual(
            (2, 4),
            (
                sum(call[0] != "owner" for call in calls),
                sum(call[0] == "owner" for call in calls),
            ),
        )

        module_paths = {path.stem: path for path in Path("src/agent").glob("*.py")}
        edges = {name: set() for name in module_paths}
        for name, path in module_paths.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                imported = []
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("src.agent."):
                    imported = [node.module.rsplit(".", 1)[-1]]
                elif isinstance(node, ast.Import):
                    imported = [
                        alias.name.rsplit(".", 1)[-1]
                        for alias in node.names
                        if alias.name.startswith("src.agent.")
                    ]
                edges[name].update(item for item in imported if item in module_paths)

        def reaches(source, destination):
            pending = [source]
            seen = set()
            while pending:
                current = pending.pop()
                if current == destination:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(edges[current] - seen)
            return False

        self.assertTrue(reaches("financial_graph_planning", "financial_answer_projection"))
        self.assertTrue(reaches("financial_graph_calculation", "financial_answer_projection"))
        self.assertFalse(reaches("financial_answer_projection", "financial_graph_planning"))
        self.assertFalse(reaches("financial_answer_projection", "financial_graph_calculation"))

        planning_loads = Counter(
            node.id
            for node in ast.walk(trees["planning"])
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )
        self.assertEqual(planning_loads["subtask_row_has_material"], 0)
        self.assertEqual(planning_loads["re"], 2)
        for name in ("Dict", "List", "_normalise_spaces"):
            self.assertGreater(planning_loads[name], 2)

        owner_loads = Counter(
            node.id
            for node in ast.walk(trees["owner"])
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        )
        self.assertEqual(owner_loads["subtask_row_has_material"], 2)
        planning_imports = {
            alias.name
            for node in ast.walk(trees["planning"])
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_answer_projection"
            for alias in node.names
        }
        calculation_imports = {
            alias.name
            for node in ast.walk(trees["calculation"])
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_answer_projection"
            for alias in node.names
        }
        aggregate_imports = {
            alias.name
            for node in ast.walk(trees["aggregate"])
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_answer_projection"
            for alias in node.names
        }
        self.assertIn("promote_nested_subtask_result_if_more_specific", planning_imports)
        self.assertNotIn("subtask_row_has_material", planning_imports)
        self.assertNotIn("nested_subtask_rows", calculation_imports)
        self.assertIn("nested_subtask_rows", aggregate_imports)

        baseline = json.loads(
            Path("tests/fixtures/runtime_domain_terms_baseline.json").read_text(encoding="utf-8-sig")
        )
        self.assertEqual(len(baseline["records"]), 217)
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path") == "src/agent/financial_answer_projection.py"
                and any(
                    min(node.lineno for node in selected_owner_defs.values())
                    <= int(line)
                    <= max(node.end_lineno for node in selected_owner_defs.values())
                    for line in record.get("first_lines") or []
                )
            ],
            [],
        )

    def test_current_source_capture_caller_pins_promotion_args_adoption_and_stop(self) -> None:
        shared = {"preserve": True}
        active_subtask = {
            "task_id": "task",
            "operation_family": "custom_operation",
            "metric_family": "family",
            "metric_label": "label",
            "query": "task query",
            "nested": shared,
        }
        projected_result = {"status": "partial", "nested": shared}
        projected = {
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": projected_result,
            "reconciliation_result": {},
            "artifact_ids": ["artifact"],
        }
        state = {
            "active_subtask": active_subtask,
            "query": "state query",
            "answer": " current answer ",
            "selected_claim_ids": ["claim"],
            "evidence_items": [],
        }
        before = deepcopy(state)
        promoted_result = {"status": "ok", "rendered_value": "promoted", "nested": shared}
        events = []

        def promote_owner(**kwargs):
            events.append("promote")
            self.assertEqual(set(kwargs), {"active_subtask", "answer", "status", "calculation_result"})
            self.assertEqual(kwargs["active_subtask"], active_subtask)
            self.assertIsNot(kwargs["active_subtask"], active_subtask)
            self.assertIs(kwargs["active_subtask"]["nested"], shared)
            self.assertEqual(kwargs["answer"], "current answer")
            self.assertEqual(kwargs["status"], "partial")
            self.assertEqual(kwargs["calculation_result"], projected_result)
            self.assertIsNot(kwargs["calculation_result"], projected_result)
            self.assertIs(kwargs["calculation_result"]["nested"], shared)
            return "promoted answer", "ok", promoted_result

        def material_owner(slot):
            events.append(("material", slot))
            return False

        with (
            patch.object(financial_graph_planning, "_project_task_trace_from_state", return_value=projected) as trace_owner,
            patch.object(
                financial_graph_planning,
                "promote_nested_subtask_result_if_more_specific",
                side_effect=promote_owner,
            ),
            patch.object(financial_graph_planning, "answer_slot_has_material", side_effect=material_owner),
        ):
            captured = self.planning_agent._capture_current_subtask_result(state)
        trace_owner.assert_called_once_with(state, "task")
        self.assertEqual(events, ["promote", ("material", {}), ("material", {})])
        self.assertEqual(captured["answer"], "promoted answer")
        self.assertEqual(captured["status"], "ok")
        self.assertIs(captured["calculation_result"], promoted_result)
        self.assertEqual(captured["artifact_ids"], ["artifact"])
        self.assertEqual(state, before)
        self.assertIs(state["active_subtask"], active_subtask)

        later_material = Mock()
        with (
            patch.object(financial_graph_planning, "_project_task_trace_from_state", return_value=projected),
            patch.object(
                financial_graph_planning,
                "promote_nested_subtask_result_if_more_specific",
                side_effect=RuntimeError("capture promotion failed"),
            ),
            patch.object(financial_graph_planning, "answer_slot_has_material", later_material),
        ):
            with self.assertRaisesRegex(RuntimeError, "capture promotion failed"):
                self.planning_agent._capture_current_subtask_result(state)
        later_material.assert_not_called()
        self.assertEqual(state, before)
        self.assertIs(state["active_subtask"], active_subtask)

    def test_current_source_nested_aggregate_caller_pins_args_adoption_and_stop(self) -> None:
        shared = {"preserve": True}
        current = {
            "task_id": "child",
            "status": "partial",
            "answer": "old answer",
            "runtime_evidence": [{"evidence_id": "old"}],
            "nested": shared,
        }
        nested = {
            "task_id": "child",
            "status": "ok",
            "answer": "new answer",
            "calculation_result": {"status": "ok", "nested": shared},
        }
        aggregate_result = {"subtask_results": [{"task_id": "source"}], "nested": shared}
        aggregate = {
            "task_id": "aggregate",
            "operation_family": "aggregate_subtasks",
            "calculation_result": aggregate_result,
            "nested": shared,
        }
        ordered_results = [current, aggregate]
        before = deepcopy(ordered_results)
        events = []

        def operation_owner(row):
            events.append(("operation", row.get("task_id")))
            return "aggregate_subtasks" if row.get("task_id") == "aggregate" else "lookup"

        def nested_owner(calculation_result):
            events.append("nested")
            self.assertEqual(calculation_result, aggregate_result)
            self.assertIsNot(calculation_result, aggregate_result)
            self.assertIs(calculation_result["subtask_results"], aggregate_result["subtask_results"])
            self.assertIs(calculation_result["nested"], shared)
            return [nested]

        def rank_owner(row):
            events.append(("rank", row.get("answer")))
            return (2, 1) if row is nested else (1, 1)

        with (
            patch.object(financial_aggregate_projection, "aggregate_source_slot_by_task_id", return_value={}) as source_owner,
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=operation_owner),
            patch.object(financial_aggregate_projection, "nested_subtask_rows", side_effect=nested_owner),
            patch.object(financial_aggregate_projection, "material_gap_feedback_for_subtask_result", return_value="") as gap_owner,
            patch.object(financial_aggregate_projection, "nested_aggregate_result_rank", side_effect=rank_owner),
            patch.object(financial_aggregate_projection, "aggregate_result_dependency_coherence_ranks", return_value=(1, 0)) as coherence_owner,
        ):
            promoted = financial_aggregate_projection.promote_stronger_nested_aggregate_results(ordered_results)
        source_rows = source_owner.call_args.args[0]
        self.assertEqual(source_rows, ordered_results)
        self.assertIsNot(source_rows[0], current)
        self.assertIs(source_rows[0]["nested"], shared)
        self.assertEqual(promoted[0]["answer"], "new answer")
        self.assertTrue(promoted[0]["promoted_from_nested_aggregate"])
        self.assertIs(promoted[0]["runtime_evidence"], current["runtime_evidence"])
        self.assertEqual(promoted[1], aggregate)
        self.assertIsNot(promoted[1], aggregate)
        gap_owner.assert_called_once_with(nested)
        self.assertEqual(coherence_owner.call_count, 2)
        self.assertEqual(ordered_results, before)
        self.assertIs(ordered_results[0], current)
        self.assertIs(ordered_results[1], aggregate)
        self.assertLess(events.index("nested"), events.index(("rank", "new answer")))

        later_rank = Mock()
        with (
            patch.object(financial_aggregate_projection, "aggregate_source_slot_by_task_id", return_value={}),
            patch.object(financial_aggregate_projection, "aggregate_result_operation_family", side_effect=operation_owner),
            patch.object(
                financial_aggregate_projection,
                "nested_subtask_rows",
                side_effect=RuntimeError("aggregate nesting failed"),
            ),
            patch.object(financial_aggregate_projection, "nested_aggregate_result_rank", later_rank),
        ):
            with self.assertRaisesRegex(RuntimeError, "aggregate nesting failed"):
                financial_aggregate_projection.promote_stronger_nested_aggregate_results(ordered_results)
        later_rank.assert_not_called()
        self.assertEqual(ordered_results, before)
        self.assertIs(ordered_results[0], current)
        self.assertIs(ordered_results[1], aggregate)


class FinancialAnswerProjectionNarrativeValidationTests(unittest.TestCase):
    def test_query_requests_explanatory_context_preserves_access_laziness_and_exception_contract(self) -> None:
        events = []

        class Query:
            def __bool__(self):
                events.append("query.bool")
                return True

            def __str__(self):
                events.append("query.str")
                return "WHY context"

        class SearchSurface:
            def __bool__(self):
                events.append("surface.bool")
                return True

            def __contains__(self, marker):
                events.append(f"contains:{marker}")
                return marker == "why"

        class Normalized:
            def lower(self):
                events.append("surface.lower")
                return SearchSurface()

        class Marker:
            def __init__(self, value):
                self.value = value

            def __str__(self):
                events.append(f"marker.str:{self.value}")
                return self.value

        class MarkerSource:
            def __bool__(self):
                events.append("markers.bool")
                return True

            def __iter__(self):
                events.append("markers.iter")
                return iter([Marker("miss"), Marker("why"), Marker("late")])

        class Policy:
            def get(self, key):
                events.append(f"policy.get:{key}")
                self.assert_key = key
                return MarkerSource()

        def normalize(value):
            events.append(f"normalize:{value}")
            return Normalized()

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", Policy()),
        ):
            self.assertTrue(financial_answer_projection.query_requests_explanatory_context(Query()))
        self.assertEqual(
            events,
            [
                "query.bool",
                "query.str",
                "normalize:WHY context",
                "surface.lower",
                "surface.bool",
                "policy.get:explanatory_markers",
                "markers.bool",
                "markers.iter",
                "marker.str:miss",
                "marker.str:why",
                "marker.str:late",
                "contains:miss",
                "contains:why",
            ],
        )

        class PolicyBomb:
            def get(self, _key):
                raise AssertionError("blank query accessed policy")

        blank_normalizer = Mock(return_value="")
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", blank_normalizer),
            patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", PolicyBomb()),
        ):
            self.assertFalse(financial_answer_projection.query_requests_explanatory_context(None))
        blank_normalizer.assert_called_once_with("")

        marker_policy = {"explanatory_markers": [""]}
        marker_policy_before = deepcopy(marker_policy)
        with patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", marker_policy):
            self.assertTrue(financial_answer_projection.query_requests_explanatory_context("anything"))
        self.assertEqual(marker_policy, marker_policy_before)
        with patch.object(
            financial_answer_projection,
            "CALCULATION_NARRATIVE_POLICY",
            {"explanatory_markers": ["WHY"]},
        ):
            self.assertFalse(financial_answer_projection.query_requests_explanatory_context("WHY"))

        class StrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("query str")

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("query bool")

        class LowerBomb:
            def lower(self):
                raise RuntimeError("lower")

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("marker iter")

        class MarkerBoolBomb:
            def __bool__(self):
                raise RuntimeError("marker source bool")

        class MarkerStrBomb:
            def __str__(self):
                raise RuntimeError("marker str")

        class ContainsBomb:
            def lower(self):
                return self

            def __bool__(self):
                return True

            def __contains__(self, _marker):
                raise RuntimeError("contains")

        exception_cases = [
            ("bool", BoolBomb(), Mock(), {}, "query bool"),
            ("str", StrBomb(), Mock(), {"explanatory_markers": ["why"]}, "query str"),
            ("normalize", "why", Mock(side_effect=RuntimeError("normalize")), {}, "normalize"),
            ("lower", "why", Mock(return_value=LowerBomb()), {}, "lower"),
            (
                "policy",
                "why",
                Mock(return_value="why"),
                Mock(get=Mock(side_effect=RuntimeError("policy"))),
                "policy",
            ),
            (
                "marker source bool",
                "why",
                Mock(return_value="why"),
                {"explanatory_markers": MarkerBoolBomb()},
                "marker source bool",
            ),
            ("iteration", "why", Mock(return_value="why"), {"explanatory_markers": IterBomb()}, "marker iter"),
            (
                "marker str",
                "why",
                Mock(return_value="why"),
                {"explanatory_markers": [MarkerStrBomb()]},
                "marker str",
            ),
            (
                "containment",
                "why",
                Mock(return_value=ContainsBomb()),
                {"explanatory_markers": ["why"]},
                "contains",
            ),
        ]
        for label, query, normalizer, policy, message in exception_cases:
            with self.subTest(label=label):
                with (
                    patch.object(financial_answer_projection, "_normalise_spaces", normalizer),
                    patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", policy),
                    self.assertRaisesRegex(RuntimeError, message),
                ):
                    financial_answer_projection.query_requests_explanatory_context(query)

    def test_growth_explanatory_signal_preserves_direction_exclusion_order_and_exceptions(self) -> None:
        events = []

        class Surface:
            def __bool__(self):
                events.append("surface.bool")
                return True

            def __contains__(self, marker):
                events.append(f"contains:{marker}")
                return marker == "impact"

        class Value:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(f"direction.str:{self.name}")
                return self.value

        class DirectionWords:
            def values(self):
                events.append("direction.values")
                return [Value("retained", "increase"), Value("blank", "")]

        class Marker:
            def __init__(self, value):
                self.value = value

            def __str__(self):
                events.append(f"marker.str:{self.value}")
                return self.value

        class Container:
            def __init__(self, name, values):
                self.name = name
                self.values = values

            def __bool__(self):
                events.append(f"{self.name}.bool")
                return True

            def __iter__(self):
                events.append(f"{self.name}.iter")
                return iter(self.values)

        policy_values = {
            "direction_words": DirectionWords(),
            "growth_narrative_markers": Container("narrative", [Marker("increase"), Marker("miss")]),
            "growth_impact_markers": Container("impact", [Marker("impact")]),
            "explanatory_markers": Container("explanatory", [Marker("late")]),
        }

        class Policy:
            def get(self, key):
                events.append(f"policy.get:{key}")
                return policy_values[key]

        def normalize(value):
            events.append(f"normalize:{value}")
            return Surface() if value == "sentence" else value.strip()

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", Policy()),
        ):
            self.assertTrue(financial_answer_projection.sentence_has_growth_explanatory_signal("sentence"))
        self.assertEqual(
            [event for event in events if event.startswith("policy.get:")],
            [
                "policy.get:direction_words",
                "policy.get:growth_narrative_markers",
                "policy.get:growth_impact_markers",
                "policy.get:explanatory_markers",
            ],
        )
        self.assertEqual(events.count("normalize:increase"), 2)
        self.assertEqual(events.count("normalize:"), 1)
        self.assertLess(events.index("explanatory.iter"), events.index("marker.str:increase"))
        self.assertEqual(
            [event for event in events if event.startswith("marker.str:")],
            ["marker.str:increase", "marker.str:miss", "marker.str:impact", "marker.str:late"],
        )
        self.assertEqual(
            [event for event in events if event.startswith("contains:")],
            ["contains:miss", "contains:impact"],
        )

        blank_policy = Mock()
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value=""),
            patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", blank_policy),
        ):
            self.assertFalse(financial_answer_projection.sentence_has_growth_explanatory_signal(None))
        blank_policy.get.assert_not_called()

        direction_policy = {
            "direction_words": {"up": "increase"},
            "growth_narrative_markers": ["increase", " Reason "],
            "growth_impact_markers": [],
            "explanatory_markers": ["Because"],
        }
        direction_policy_before = deepcopy(direction_policy)
        with patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", direction_policy):
            self.assertFalse(financial_answer_projection.sentence_has_growth_explanatory_signal("increase 10%"))
            self.assertFalse(financial_answer_projection.sentence_has_growth_explanatory_signal("reason"))
            self.assertTrue(financial_answer_projection.sentence_has_growth_explanatory_signal("Because demand changed"))
        self.assertEqual(direction_policy, direction_policy_before)

        class ValuesBomb:
            def values(self):
                raise RuntimeError("values")

        class MarkerIterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("marker iter")

        class MarkerStrBomb:
            def __str__(self):
                raise RuntimeError("marker str")

        class SentenceStrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("sentence str")

        class ContainsBomb:
            def __bool__(self):
                return True

            def __contains__(self, _marker):
                raise RuntimeError("contains")

        def direction_normalizer(value):
            if value == "driver":
                return value
            raise RuntimeError("direction normalize")

        exception_policies = [
            {"direction_words": ValuesBomb()},
            {
                "direction_words": {},
                "growth_narrative_markers": MarkerIterBomb(),
                "growth_impact_markers": [],
                "explanatory_markers": [],
            },
        ]
        for policy in exception_policies:
            with self.subTest(policy=type(policy.get("direction_words")).__name__):
                with (
                    patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", policy),
                    self.assertRaises(RuntimeError),
                ):
                    financial_answer_projection.sentence_has_growth_explanatory_signal("driver")

        signal_exception_cases = [
            (
                "sentence str",
                SentenceStrBomb(),
                Mock(),
                direction_policy,
                "sentence str",
            ),
            (
                "direction normalize",
                "driver",
                Mock(side_effect=direction_normalizer),
                direction_policy,
                "direction normalize",
            ),
            (
                "policy",
                "driver",
                Mock(return_value="driver"),
                Mock(get=Mock(side_effect=RuntimeError("policy"))),
                "policy",
            ),
            (
                "marker str",
                "driver",
                Mock(side_effect=lambda value: value),
                {
                    "direction_words": {},
                    "growth_narrative_markers": [MarkerStrBomb()],
                    "growth_impact_markers": [],
                    "explanatory_markers": [],
                },
                "marker str",
            ),
            (
                "containment",
                "driver",
                Mock(return_value=ContainsBomb()),
                {
                    "direction_words": {},
                    "growth_narrative_markers": ["driver"],
                    "growth_impact_markers": [],
                    "explanatory_markers": [],
                },
                "contains",
            ),
        ]
        for label, sentence, normalizer, policy, message in signal_exception_cases:
            with self.subTest(label=label):
                with (
                    patch.object(financial_answer_projection, "_normalise_spaces", normalizer),
                    patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", policy),
                    self.assertRaisesRegex(RuntimeError, message),
                ):
                    financial_answer_projection.sentence_has_growth_explanatory_signal(sentence)

    def test_narrative_validation_all_fifteen_graph_bindings_preserve_args_polarity_and_try_boundary(self) -> None:
        tree = ast.parse(inspect.getsource(financial_graph_calculation.FinancialAgentCalculationMixin))
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        public_names = {
            "query_requests_explanatory_context",
            "sentence_has_growth_explanatory_signal",
        }
        bindings = Counter()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in public_names
            ):
                continue
            cursor = node
            negative = False
            inside_try = False
            owner = None
            while cursor in parents:
                cursor = parents[cursor]
                if isinstance(cursor, ast.UnaryOp) and isinstance(cursor.op, ast.Not):
                    negative = not negative
                if isinstance(cursor, ast.Try):
                    inside_try = True
                if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner = cursor.name
                    break
            bindings[
                (
                    node.func.id,
                    owner,
                    ast.unparse(node.args[0]),
                    "negative" if negative else "positive",
                    inside_try,
                )
            ] += 1

        state_query = "str(state.get('query') or '')"
        self.assertEqual(
            bindings,
            Counter(
                {
                    ("query_requests_explanatory_context", "_refresh_numeric_answer_preserving_narrative_context", "query", "negative", False): 1,
                    ("query_requests_explanatory_context", "_refresh_numeric_answer_preserving_narrative_context", "query_text", "negative", False): 1,
                    ("query_requests_explanatory_context", "_refresh_numeric_answer_preserving_narrative_context", "query_text", "positive", False): 2,
                    ("query_requests_explanatory_context", "_apply_initial_aggregate_answer_composition", state_query, "negative", False): 1,
                    ("query_requests_explanatory_context", "_apply_final_narrative_repair_pipeline", state_query, "negative", False): 1,
                    ("query_requests_explanatory_context", "_apply_final_narrative_repair_pipeline", state_query, "positive", False): 2,
                    ("query_requests_explanatory_context", "_prepare_initial_aggregate_state", state_query, "negative", False): 1,
                    ("query_requests_explanatory_context", "_aggregate_calculation_subtasks", state_query, "negative", False): 3,
                    ("query_requests_explanatory_context", "_aggregate_calculation_subtasks", state_query, "positive", False): 2,
                    ("sentence_has_growth_explanatory_signal", "_uncovered_supported_growth_narrative_candidate", "cleaned", "negative", False): 1,
                }
            ),
        )
        self.assertEqual(sum(bindings.values()), 15)

    def test_narrative_validation_runtime_bindings_preserve_gate_adoption_order_and_exception_stop(self) -> None:
        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        downstream = Mock(side_effect=AssertionError("query gate leaked downstream"))
        with (
            patch.object(
                financial_graph_calculation,
                "query_requests_explanatory_context",
                return_value=False,
            ) as query_owner,
            patch.object(agent, "_preferred_conflicting_growth_narrative_answer", downstream),
        ):
            projected = agent._refresh_numeric_answer_preserving_narrative_context(
                query="why",
                current_answer="context",
                numeric_answer="42%",
                ordered_results=[],
                evidence_items=[],
            )
        self.assertEqual(projected, {"answer": "42%", "selected_claim_ids": []})
        query_owner.assert_called_once_with("why")
        downstream.assert_not_called()

        with (
            patch.object(
                financial_graph_calculation,
                "query_requests_explanatory_context",
                side_effect=RuntimeError("query owner"),
            ),
            patch.object(agent, "_preferred_conflicting_growth_narrative_answer", downstream),
            self.assertRaisesRegex(RuntimeError, "query owner"),
        ):
            agent._refresh_numeric_answer_preserving_narrative_context(
                query="why",
                current_answer="context",
                numeric_answer="42%",
                ordered_results=[],
                evidence_items=[],
            )
        downstream.assert_not_called()

        def configured_signal_agent():
            candidate_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            candidate_agent._narrative_driver_groups = Mock(return_value=[])
            candidate_agent._growth_narrative_sentence_candidates = Mock(
                return_value=[((1,), "raw candidate", ["claim_1"])]
            )
            return candidate_agent, Mock(return_value="cleaned candidate")

        signal_owner = Mock(return_value=True)
        coverage_owner = Mock(return_value=False)
        material_owner = Mock(return_value=False)
        candidate_agent, strip_owner = configured_signal_agent()
        with (
            patch.object(
                financial_graph_calculation,
                "sentence_has_growth_explanatory_signal",
                signal_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "answer_covers_narrative_context",
                coverage_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                material_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                strip_owner,
            ),
        ):
            candidate = candidate_agent._uncovered_supported_growth_narrative_candidate(
                query="why",
                answer="current answer",
                ordered_results=[],
                evidence_items=[],
            )
        self.assertEqual(candidate, {"sentence": "cleaned candidate", "selected_claim_ids": ["claim_1"]})
        signal_owner.assert_called_once_with("cleaned candidate")
        self.assertEqual(coverage_owner.call_count, 2)
        material_owner.assert_called_once_with("cleaned candidate", [], [])

        signal_owner = Mock(side_effect=RuntimeError("signal owner"))
        coverage_owner = Mock(return_value=False)
        material_owner = Mock(return_value=False)
        candidate_agent, strip_owner = configured_signal_agent()
        with (
            patch.object(
                financial_graph_calculation,
                "sentence_has_growth_explanatory_signal",
                signal_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "answer_covers_narrative_context",
                coverage_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                material_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                strip_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "signal owner"),
        ):
            candidate_agent._uncovered_supported_growth_narrative_candidate(
                query="why",
                answer="current answer",
                ordered_results=[],
                evidence_items=[],
            )
        signal_owner.assert_called_once_with("cleaned candidate")
        self.assertEqual(coverage_owner.call_count, 1)
        material_owner.assert_not_called()


class FinancialAnswerProjectionNarrativeSurfaceTests(unittest.TestCase):
    def test_answer_truncation_preserves_terminal_precedence_laziness_and_exceptions(self) -> None:
        owner = financial_answer_projection.answer_looks_truncated
        terminal_pattern = r"(?:다|니다|요|음|임)[.!?。]?$"
        punctuation_pattern = r"[.!?。]$"
        events = []

        class InputValue:
            def __bool__(self):
                events.append("input-bool")
                return True

            def __str__(self):
                events.append("input-str")
                return "raw answer"

        class MatchValue:
            def __init__(self, label, result):
                self.label = label
                self.result = result

            def __bool__(self):
                events.append(("match-bool", self.label))
                return self.result

        def normalize(value):
            events.append(("normalize", value))
            return "normalized answer"

        def terminal_search(pattern, value):
            events.append(("search", pattern, value))
            if pattern != terminal_pattern:
                raise AssertionError("punctuation regex should stay lazy")
            return MatchValue("terminal", True)

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection.re, "search", side_effect=terminal_search),
        ):
            self.assertFalse(owner(InputValue()))
        self.assertEqual(
            events,
            [
                "input-bool",
                "input-str",
                ("normalize", "raw answer"),
                ("search", terminal_pattern, "normalized answer"),
                ("match-bool", "terminal"),
            ],
        )

        events.clear()

        def punctuation_search(pattern, value):
            events.append(("search", pattern, value))
            if pattern == terminal_pattern:
                return MatchValue("terminal", False)
            if pattern == punctuation_pattern:
                return MatchValue("punctuation", True)
            raise AssertionError(pattern)

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value="normalized answer"),
            patch.object(financial_answer_projection.re, "search", side_effect=punctuation_search),
        ):
            self.assertFalse(owner("raw answer"))
        self.assertEqual(
            events,
            [
                ("search", terminal_pattern, "normalized answer"),
                ("match-bool", "terminal"),
                ("search", punctuation_pattern, "normalized answer"),
                ("match-bool", "punctuation"),
            ],
        )

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value="normalized answer"),
            patch.object(financial_answer_projection.re, "search", side_effect=[False, False]) as search,
        ):
            self.assertTrue(owner("raw answer"))
        self.assertEqual(
            search.call_args_list,
            [
                unittest.mock.call(terminal_pattern, "normalized answer"),
                unittest.mock.call(punctuation_pattern, "normalized answer"),
            ],
        )

        class FalseInput:
            def __bool__(self):
                return False

            def __str__(self):
                raise AssertionError("false input stringified")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value="") as normalize_owner,
            patch.object(
                financial_answer_projection.re,
                "search",
                side_effect=AssertionError("blank answer reached regex"),
            ),
        ):
            self.assertTrue(owner(FalseInput()))
        normalize_owner.assert_called_once_with("")

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("answer bool")

        class StrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("answer str")

        class MatchBomb:
            def __bool__(self):
                raise RuntimeError("match bool")

        for value, message in ((BoolBomb(), "answer bool"), (StrBomb(), "answer str")):
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                owner(value)
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=RuntimeError("normalize")),
            self.assertRaisesRegex(RuntimeError, "normalize"),
        ):
            owner("answer")
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value="answer"),
            patch.object(financial_answer_projection.re, "search", side_effect=RuntimeError("regex")),
            self.assertRaisesRegex(RuntimeError, "regex"),
        ):
            owner("answer")
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value="answer"),
            patch.object(financial_answer_projection.re, "search", return_value=MatchBomb()),
            self.assertRaisesRegex(RuntimeError, "match bool"),
        ):
            owner("answer")

    def test_narrative_context_coverage_preserves_threshold_access_laziness_and_exceptions(self) -> None:
        owner = financial_answer_projection.answer_covers_narrative_context

        def normalize(value):
            return " ".join(str(value).split())

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                side_effect=AssertionError("blank context reached splitter"),
            ),
        ):
            self.assertTrue(owner("answer", "   "))

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                side_effect=AssertionError("whole context reached splitter"),
            ),
        ):
            self.assertTrue(owner("Prefix ALPHA CONTEXT suffix", " alpha context "))

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                return_value=["covered sentence"],
            ),
            patch.object(
                financial_answer_projection.re,
                "findall",
                side_effect=AssertionError("contained sentence reached tokenization"),
            ),
        ):
            self.assertTrue(owner("prefix covered sentence suffix", "other context"))

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                return_value=["alpha beta gamma delta"],
            ),
        ):
            self.assertTrue(owner("alpha beta gamma", "source context"))
            self.assertFalse(owner("alpha beta", "source context"))

        class LaterSentenceBomb:
            def lower(self):
                raise AssertionError("later sentence accessed after failure")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_graph_calculation,
                "_split_narrative_sentences",
                return_value=["alpha beta gamma delta", LaterSentenceBomb()],
            ),
        ):
            self.assertFalse(owner("alpha", "source context"))

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=["1 22"]),
        ):
            self.assertFalse(owner("answer", "source context"))

        events = []

        class AnswerNormalized:
            def lower(self):
                events.append("answer-lower")
                return AnswerSurface()

        class AnswerSurface:
            def __contains__(self, value):
                events.append(("answer-contains", value))
                return value == "alpha"

        class Sentence:
            def lower(self):
                events.append("sentence-lower")
                return "sentence lower"

        class Token:
            def __init__(self, value):
                self.value = value

            def __len__(self):
                events.append(("token-len", self.value))
                return len(self.value)

            def lower(self):
                events.append(("token-lower", self.value))
                return self.value.lower()

        class Match:
            def __init__(self, token, result):
                self.token = token
                self.result = result

            def __bool__(self):
                events.append(("match-bool", self.token.value))
                return self.result

        tokens = [Token("xy"), Token("123"), Token("Alpha"), Token("Beta")]

        def traced_normalize(value):
            events.append(("normalize", value))
            return AnswerNormalized() if value == "answer" else "root context"

        def split_context(value):
            events.append(("split", value))
            return [Sentence()]

        def findall(pattern, value, *, flags=0):
            events.append(("findall", pattern, value, flags))
            return tokens

        def fullmatch(pattern, token):
            events.append(("fullmatch", pattern, token.value))
            return Match(token, token.value == "123")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=traced_normalize),
            patch.object(financial_answer_projection, "split_narrative_sentences", side_effect=split_context),
            patch.object(financial_answer_projection.re, "findall", side_effect=findall),
            patch.object(financial_answer_projection.re, "fullmatch", side_effect=fullmatch),
        ):
            self.assertFalse(owner("answer", "context"))
        self.assertEqual(
            events,
            [
                ("normalize", "answer"),
                "answer-lower",
                ("normalize", "context"),
                ("answer-contains", "root context"),
                ("split", "root context"),
                "sentence-lower",
                ("answer-contains", "sentence lower"),
                ("findall", r"[\w()]+", unittest.mock.ANY, financial_answer_projection.re.UNICODE),
                ("token-len", "xy"),
                ("token-len", "123"),
                ("fullmatch", r"\d+(?:\.\d+)?", "123"),
                ("match-bool", "123"),
                ("token-len", "Alpha"),
                ("fullmatch", r"\d+(?:\.\d+)?", "Alpha"),
                ("match-bool", "Alpha"),
                ("token-lower", "Alpha"),
                ("token-len", "Beta"),
                ("fullmatch", r"\d+(?:\.\d+)?", "Beta"),
                ("match-bool", "Beta"),
                ("token-lower", "Beta"),
                ("answer-contains", "alpha"),
                ("answer-contains", "beta"),
            ],
        )

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("input bool")

        class StrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("input str")

        for value, message in ((BoolBomb(), "input bool"), (StrBomb(), "input str")):
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                owner(value, "context")
            with self.subTest(message=f"context {message}"), self.assertRaisesRegex(RuntimeError, message):
                owner("answer", value)

        class BlankNormalizedContext:
            def __bool__(self):
                return False

            def lower(self):
                raise AssertionError("blank normalized context lower accessed")

        with (
            patch.object(
                financial_answer_projection,
                "_normalise_spaces",
                side_effect=["answer", BlankNormalizedContext()],
            ),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                side_effect=AssertionError("blank normalized context reached splitter"),
            ),
        ):
            self.assertTrue(owner("answer", "context"))

        class LowerBomb:
            def lower(self):
                raise RuntimeError("lower")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", return_value=LowerBomb()),
            self.assertRaisesRegex(RuntimeError, "lower"),
        ):
            owner("answer", "context")
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=["answer", "context"]),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                side_effect=RuntimeError("splitter"),
            ),
            self.assertRaisesRegex(RuntimeError, "splitter"),
        ):
            owner("answer", "context")

        class IterableBomb:
            def __iter__(self):
                raise RuntimeError("sentence iteration")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=["answer", "context"]),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=IterableBomb()),
            self.assertRaisesRegex(RuntimeError, "sentence iteration"),
        ):
            owner("answer", "context")

        class SentenceLowerBomb:
            def lower(self):
                raise RuntimeError("sentence lower")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=["answer", "context"]),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                return_value=[SentenceLowerBomb()],
            ),
            self.assertRaisesRegex(RuntimeError, "sentence lower"),
        ):
            owner("answer", "context")
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=["answer", "context"]),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=["sentence"]),
            patch.object(financial_answer_projection.re, "findall", side_effect=RuntimeError("findall")),
            self.assertRaisesRegex(RuntimeError, "findall"),
        ):
            owner("answer", "context")

        class LenBomb:
            def __len__(self):
                raise RuntimeError("token len")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=["answer", "context"]),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=["sentence"]),
            patch.object(financial_answer_projection.re, "findall", return_value=[LenBomb()]),
            self.assertRaisesRegex(RuntimeError, "token len"),
        ):
            owner("answer", "context")
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=["answer", "context"]),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=["token"]),
            patch.object(financial_answer_projection.re, "findall", return_value=["token"]),
            patch.object(financial_answer_projection.re, "fullmatch", side_effect=RuntimeError("fullmatch")),
            self.assertRaisesRegex(RuntimeError, "fullmatch"),
        ):
            owner("answer", "context")

        class ContainmentBomb:
            def __init__(self):
                self.calls = 0

            def __contains__(self, _value):
                self.calls += 1
                if self.calls == 3:
                    raise RuntimeError("token containment")
                return False

        class AnswerWithContainmentBomb:
            def __init__(self, surface):
                self.surface = surface

            def lower(self):
                return self.surface

        containment_surface = ContainmentBomb()
        with (
            patch.object(
                financial_answer_projection,
                "_normalise_spaces",
                side_effect=[AnswerWithContainmentBomb(containment_surface), "context"],
            ),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=["sentence"]),
            patch.object(financial_answer_projection.re, "findall", return_value=["token"]),
            patch.object(financial_answer_projection.re, "fullmatch", return_value=False),
            self.assertRaisesRegex(RuntimeError, "token containment"),
        ):
            owner("answer", "context")
        self.assertEqual(containment_surface.calls, 3)

    def test_narrative_surface_bindings_preserve_all_ten_args_polarities_and_try_boundaries(self) -> None:
        tree = ast.parse(inspect.getsource(financial_graph_calculation.FinancialAgentCalculationMixin))
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent

        names = {"answer_looks_truncated", "answer_covers_narrative_context"}
        bindings = Counter()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in names
            ):
                continue
            cursor = node
            negative = False
            inside_try = False
            owner = None
            while cursor in parents:
                cursor = parents[cursor]
                if isinstance(cursor, ast.UnaryOp) and isinstance(cursor.op, ast.Not):
                    negative = not negative
                if isinstance(cursor, ast.Try):
                    inside_try = True
                if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    owner = cursor.name
                    break
            bindings[
                (
                    node.func.id,
                    owner,
                    tuple(ast.unparse(arg) for arg in node.args),
                    "negative" if negative else "positive",
                    inside_try,
                )
            ] += 1

        self.assertEqual(
            bindings,
            Counter(
                {
                    ("answer_looks_truncated", "_compose_growth_narrative_answer", ("existing_answer",), "positive", False): 1,
                    ("answer_covers_narrative_context", "_uncovered_supported_growth_narrative_candidate", ("answer", "candidate_sentence"), "positive", False): 1,
                    ("answer_covers_narrative_context", "_uncovered_supported_growth_narrative_candidate", ("answer", "cleaned"), "positive", False): 1,
                    ("answer_covers_narrative_context", "_matches_supported_growth_context", ("sentence", "candidate"), "positive", False): 1,
                    ("answer_covers_narrative_context", "_matches_supported_growth_context", ("candidate", "sentence"), "positive", False): 1,
                    ("answer_covers_narrative_context", "_compose_growth_narrative_answer", ("existing_answer_text", "candidate_text"), "positive", False): 1,
                    ("answer_covers_narrative_context", "_compose_growth_narrative_answer", ("existing_answer_text", "row_focus_context[1]"), "positive", False): 1,
                    ("answer_covers_narrative_context", "_compose_growth_narrative_answer", ("existing_answer_text", "row_focus_context[1]"), "negative", False): 1,
                    ("answer_covers_narrative_context", "_answer_satisfies_growth_narrative_intent", ("answer_text", "candidate_text"), "negative", False): 1,
                    ("answer_covers_narrative_context", "_answer_satisfies_growth_narrative_intent", ("answer_text", "row_focus_context[1]"), "negative", False): 1,
                }
            ),
        )
        self.assertEqual(sum(bindings.values()), 10)

    def test_narrative_surface_runtime_bindings_preserve_adoption_and_owner_exception_stop(self) -> None:
        def configured_compose_agent():
            primary_slot = {"rendered_value": "10%"}
            current_slot = {"period": "2024", "label": "Revenue"}
            prior_slot = {"period": "2023"}
            row = {
                "calculation_result": {
                    "answer_slots": {
                        "primary_value": primary_slot,
                        "current_value": current_slot,
                        "prior_value": prior_slot,
                    }
                }
            }
            agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
            agent._growth_narrative_sentence_candidates = Mock(
                return_value=[((1,), "candidate context", ["claim_1"])]
            )
            agent._answer_matches_supported_aggregate_subtask = Mock(return_value=False)
            agent._supported_growth_driver_groups = Mock(return_value=[])
            return agent, row

        class NarrativePolicyProbe(dict):
            def __init__(self):
                super().__init__(financial_graph_calculation.CALCULATION_NARRATIVE_POLICY)
                self.events = []

            def get(self, key, default=None):
                self.events.append(key)
                if key == "direction_words":
                    raise RuntimeError("continued after truncated answer")
                return super().get(key, default)

        for truncated in (False, True):
            compose_agent, row = configured_compose_agent()
            truncation_owner = Mock(return_value=truncated)
            narrative_policy = NarrativePolicyProbe()
            display_owner = Mock(side_effect=["200", "100"])
            share_owner = Mock(return_value=False)
            contexts = (
                patch.object(
                    financial_graph_calculation,
                    "answer_looks_truncated",
                    truncation_owner,
                ),
                patch.object(financial_graph_calculation, "query_requests_narrative_context", return_value=True),
                patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
                patch.object(financial_graph_calculation, "answer_slot_has_material", return_value=True),
                patch.object(financial_graph_calculation, "CALCULATION_NARRATIVE_POLICY", narrative_policy),
                patch.object(financial_graph_calculation, "narrative_focus_variants", return_value=[]),
                patch.object(financial_graph_calculation, "parenthetical_focus_variants", return_value=[]),
                patch.object(financial_graph_calculation, "narrative_row_focus_context", return_value=None),
                patch.object(financial_graph_calculation, "growth_slot_display_value", display_owner),
                patch.object(financial_graph_calculation, "growth_slots_share_material", share_owner),
                patch.object(
                    financial_graph_calculation,
                    "growth_required_display_values",
                    return_value=["10%", "200", "100"],
                ),
            )
            if truncated:
                with (
                    contexts[0],
                    contexts[1],
                    contexts[2],
                    contexts[3],
                    contexts[4],
                    contexts[5],
                    contexts[6],
                    contexts[7],
                    contexts[8],
                    contexts[9],
                    contexts[10],
                    self.assertRaisesRegex(RuntimeError, "continued after truncated answer"),
                ):
                    compose_agent._compose_growth_narrative_answer(
                        query="why",
                        ordered_results=[row],
                        existing_answer="Revenue 10% 200 100 complete.",
                        evidence_items=[],
                    )
                self.assertEqual(narrative_policy.events[-1], "direction_words")
            else:
                with (
                    contexts[0],
                    contexts[1],
                    contexts[2],
                    contexts[3],
                    contexts[4],
                    contexts[5],
                    contexts[6],
                    contexts[7],
                    contexts[8],
                    contexts[9],
                    contexts[10],
                ):
                    result = compose_agent._compose_growth_narrative_answer(
                        query="why",
                        ordered_results=[row],
                        existing_answer="Revenue 10% 200 100 complete.",
                        evidence_items=[],
                    )
                self.assertIsNone(result)
                self.assertNotIn("direction_words", narrative_policy.events)
            truncation_owner.assert_called_once_with(
                "Revenue 10% 200 100 complete."
            )

        class IterationBomb:
            def __iter__(self):
                raise AssertionError("ordered results iterated after truncation owner exception")

        compose_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        truncation_owner = Mock(side_effect=RuntimeError("truncation owner"))
        with (
            patch.object(
                financial_graph_calculation,
                "answer_looks_truncated",
                truncation_owner,
            ),
            patch.object(financial_graph_calculation, "query_requests_narrative_context", return_value=True),
            self.assertRaisesRegex(RuntimeError, "truncation owner"),
        ):
            compose_agent._compose_growth_narrative_answer(
                query="why",
                ordered_results=IterationBomb(),
                existing_answer="existing answer",
                evidence_items=[],
            )
        truncation_owner.assert_called_once_with("existing answer")

        def configured_candidate_agent():
            candidate_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            candidate_agent._narrative_driver_groups = Mock(return_value=[])
            candidate_agent._growth_narrative_sentence_candidates = Mock(
                return_value=[((1,), "raw candidate", ["claim_1"])]
            )
            return candidate_agent, Mock(return_value="cleaned candidate")

        coverage = Mock(return_value=True)
        material_owner = Mock(return_value=False)
        candidate_agent, strip_owner = configured_candidate_agent()
        with (
            patch.object(
                financial_graph_calculation,
                "answer_covers_narrative_context",
                coverage,
            ),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                material_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                strip_owner,
            ),
        ):
            candidate = candidate_agent._uncovered_supported_growth_narrative_candidate(
                query="why",
                answer="existing answer",
                ordered_results=[],
                evidence_items=[],
            )
        self.assertEqual(candidate, {})
        coverage.assert_called_once_with("existing answer", "raw candidate")
        strip_owner.assert_not_called()
        material_owner.assert_not_called()

        coverage = Mock(side_effect=[False, False])
        material_owner = Mock(return_value=False)
        candidate_agent, strip_owner = configured_candidate_agent()
        with (
            patch.object(
                financial_graph_calculation,
                "answer_covers_narrative_context",
                coverage,
            ),
            patch.object(
                financial_graph_calculation,
                "sentence_has_growth_explanatory_signal",
                return_value=True,
            ),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                material_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                strip_owner,
            ),
        ):
            candidate = candidate_agent._uncovered_supported_growth_narrative_candidate(
                query="why",
                answer="existing answer",
                ordered_results=[],
                evidence_items=[],
            )
        self.assertEqual(candidate, {"sentence": "cleaned candidate", "selected_claim_ids": ["claim_1"]})
        self.assertEqual(
            coverage.call_args_list,
            [
                unittest.mock.call("existing answer", "raw candidate"),
                unittest.mock.call("existing answer", "cleaned candidate"),
            ],
        )
        material_owner.assert_called_once_with("cleaned candidate", [], [])

        coverage = Mock(side_effect=RuntimeError("coverage owner"))
        material_owner = Mock(return_value=False)
        candidate_agent, strip_owner = configured_candidate_agent()
        with (
            patch.object(
                financial_graph_calculation,
                "answer_covers_narrative_context",
                coverage,
            ),
            patch.object(
                financial_graph_calculation,
                "growth_answer_has_untraced_numeric_material",
                material_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "strip_untraced_numeric_material_from_growth_narrative_sentence",
                strip_owner,
            ),
            self.assertRaisesRegex(RuntimeError, "coverage owner"),
        ):
            candidate_agent._uncovered_supported_growth_narrative_candidate(
                query="why",
                answer="existing answer",
                ordered_results=[],
                evidence_items=[],
            )
        coverage.assert_called_once_with("existing answer", "raw candidate")
        strip_owner.assert_not_called()
        material_owner.assert_not_called()


class FinancialAnswerProjectionTraceGuardTests(unittest.TestCase):
    def test_source_stated_result_preserves_copy_precedence_fallback_and_exceptions(self) -> None:
        owner = financial_answer_projection.growth_uses_source_stated_result
        copy_events = []

        class CopyOnlyMapping(Mapping):
            def __init__(self, label, values):
                self.label = label
                self.values = dict(values)

            def __iter__(self):
                copy_events.append(("copy", self.label))
                return iter(self.values)

            def __len__(self):
                return len(self.values)

            def __getitem__(self, key):
                return self.values[key]

            def get(self, _key, _default=None):
                raise AssertionError(f"{self.label} used before shallow copy")

        current_slot = CopyOnlyMapping("current", {"stated_change_raw_value": "unused"})
        answer_slots = CopyOnlyMapping("slots", {"current_value": current_slot})
        derived_metrics = CopyOnlyMapping("derived", {"source_stated_result_used": True})
        calculation_result = CopyOnlyMapping(
            "calculation",
            {"answer_slots": answer_slots, "derived_metrics": derived_metrics},
        )
        row = {"calculation_result": calculation_result, "nested": {"preserve": True}}
        before = deepcopy(row)
        with patch.object(
            financial_answer_projection,
            "_normalise_spaces",
            side_effect=AssertionError("derived flag leaked to raw-value normalization"),
        ):
            self.assertTrue(owner(row))
        self.assertEqual(
            [event for event in copy_events if event[0] == "copy"],
            [("copy", "calculation"), ("copy", "slots"), ("copy", "current"), ("copy", "derived")],
        )
        self.assertEqual(row, before)

        class ResultFallbackBomb(dict):
            def get(self, key, default=None):
                if key == "calculation_operands":
                    raise AssertionError("result operand fallback accessed")
                return super().get(key, default)

        normalize = Mock(side_effect=lambda value: " ".join(str(value).split()))
        row = {
            "calculation_result": ResultFallbackBomb(
                {
                    "answer_slots": {"current_value": {"stated_change_raw_value": ""}},
                    "derived_metrics": {},
                }
            ),
            "calculation_operands": [
                {
                    "matched_operand_role": "prior_period",
                    "role": "current_period",
                    "stated_change_raw_value": "must stay ignored",
                },
                "skip non-dict",
                {"matched_operand_role": "", "role": "current_period", "stated_change_raw_value": " 7% "},
                {"matched_operand_role": "current_period", "stated_change_raw_value": "later"},
            ],
        }
        before = deepcopy(row)
        with patch.object(financial_answer_projection, "_normalise_spaces", normalize):
            self.assertTrue(owner(row))
        self.assertEqual(normalize.call_args_list, [unittest.mock.call(""), unittest.mock.call(" 7% ")])
        self.assertEqual(row, before)

        class OperandLazyRow(dict):
            def get(self, key, default=None):
                if key == "calculation_operands":
                    raise AssertionError("truthy current raw value reached operands")
                return super().get(key, default)

        row = OperandLazyRow(
            {
                "calculation_result": {
                    "answer_slots": {"current_value": {"stated_change_raw_value": " source 8% "}},
                    "derived_metrics": {},
                }
            }
        )
        with patch.object(financial_answer_projection, "_normalise_spaces", side_effect=lambda value: str(value).strip()):
            self.assertTrue(owner(row))

        class RoleAccessBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("operand role accessed before list materialization completed")

        class OperandIterable:
            def __iter__(self):
                yield RoleAccessBomb()
                raise RuntimeError("operand materialization")

        row = {
            "calculation_result": {
                "answer_slots": {"current_value": {}},
                "derived_metrics": {},
            },
            "calculation_operands": OperandIterable(),
        }
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=lambda value: str(value).strip()),
            self.assertRaisesRegex(RuntimeError, "operand materialization"),
        ):
            owner(row)

        row = {
            "calculation_result": {
                "answer_slots": {"current_value": {}},
                "derived_metrics": {},
                "calculation_operands": [
                    {"matched_operand_role": "current_period", "stated_change_raw_value": "fallback"}
                ],
            },
            "calculation_operands": [],
        }
        with patch.object(financial_answer_projection, "_normalise_spaces", side_effect=lambda value: str(value).strip()):
            self.assertTrue(owner(row))

        class RowGetBomb(dict):
            def get(self, _key, _default=None):
                raise RuntimeError("row get")

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("raw bool")

        class StrBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("raw str")

        with self.assertRaisesRegex(RuntimeError, "row get"):
            owner(RowGetBomb())
        for raw_value, message in ((BoolBomb(), "raw bool"), (StrBomb(), "raw str")):
            row = {
                "calculation_result": {
                    "answer_slots": {"current_value": {"stated_change_raw_value": raw_value}},
                    "derived_metrics": {},
                }
            }
            with self.subTest(message=message), self.assertRaisesRegex(RuntimeError, message):
                owner(row)
        row = {
            "calculation_result": {
                "answer_slots": {"current_value": {"stated_change_raw_value": "value"}},
                "derived_metrics": {},
            }
        }
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=RuntimeError("normalize")),
            self.assertRaisesRegex(RuntimeError, "normalize"),
        ):
            owner(row)

    def test_untraced_sentence_guard_preserves_evidence_display_percent_krw_order_and_exceptions(self) -> None:
        owner = financial_answer_projection.growth_sentence_has_untraced_material_numeric

        def normalize(value):
            return " ".join(str(value).split())

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection,
                "evidence_numeric_display_candidates",
                side_effect=AssertionError("blank sentence reached evidence display"),
            ),
        ):
            self.assertFalse(owner("   ", "", []))

        metadata_values = {
            "table_value_labels_text": "meta labels",
            "table_summary_text": "meta summary",
            "table_header_context": "meta header",
            "table_context": "meta context",
        }
        metadata_copy_events = []

        class SnapshotMetadata(Mapping):
            def __iter__(self):
                metadata_copy_events.append("copy")
                return iter(metadata_values)

            def __len__(self):
                return len(metadata_values)

            def __getitem__(self, key):
                return metadata_values[key]

            def get(self, _key, _default=None):
                raise AssertionError("metadata used without dict snapshot")

            def __deepcopy__(self, _memo):
                return self

        metadata = SnapshotMetadata()
        evidence_items = [
            {
                "claim": "claim 3억원",
                "quote_span": "quote",
                "raw_row_text": "raw row",
                "source_context": "source context",
                "metadata": metadata,
            }
        ]
        before = deepcopy(evidence_items)
        candidate_get_events = []

        class DisplayCandidate:
            def __init__(self, label, text):
                self.label = label
                self.text = text

            def get(self, key, default=None):
                candidate_get_events.append((self.label, key))
                return self.text if key == "text" else default

        display_candidates = Mock(
            return_value=[DisplayCandidate("retained", "99%"), DisplayCandidate("blank", "")]
        )
        evidence_normalizer = Mock(side_effect=normalize)
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", evidence_normalizer),
            patch.object(financial_answer_projection, "evidence_numeric_display_candidates", display_candidates),
            patch.object(
                financial_answer_projection,
                "CALCULATION_NARRATIVE_POLICY",
                {"percent_display_pattern": r"\d+%"},
            ),
            patch.object(
                financial_answer_projection,
                "CALCULATION_RENDER_POLICY",
                {"krw_display_units": ["억원", "원"]},
            ),
        ):
            self.assertFalse(owner("99% 3억원", "complete", ["required A", "required B"], evidence_items))
        display_candidates.assert_called_once_with(
            evidence_items,
            "claim 3억원 quote raw row source context meta labels meta summary meta header meta context",
        )
        self.assertEqual(metadata_copy_events, ["copy"])
        self.assertEqual(
            candidate_get_events,
            [("retained", "text"), ("retained", "text"), ("blank", "text")],
        )
        self.assertIn(
            unittest.mock.call(
                "complete required A required B claim 3억원 quote raw row source context meta labels meta summary meta header meta context 99%"
            ),
            evidence_normalizer.call_args_list,
        )
        self.assertEqual(evidence_items, before)

        class RenderPolicyBomb(Mapping):
            def __iter__(self):
                raise AssertionError("unallowed percent reached render policy")

            def __len__(self):
                return 0

            def __getitem__(self, _key):
                raise KeyError

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "evidence_numeric_display_candidates", return_value=[]),
            patch.object(
                financial_answer_projection,
                "CALCULATION_NARRATIVE_POLICY",
                {"percent_display_pattern": r"\d+%"},
            ),
            patch.object(financial_answer_projection, "CALCULATION_RENDER_POLICY", RenderPolicyBomb()),
        ):
            self.assertTrue(owner("77%", "10%", []))

        events = []
        unit_normalize_inputs = []

        class Match:
            def __init__(self, token):
                self.token = token

            def group(self, index):
                events.append(("group", self.token, index))
                return self.token

        def finditer(pattern, cleaned):
            events.append(("finditer", pattern, cleaned))
            if pattern == "PERCENT":
                return [Match("10%")]
            if "억원" in pattern:
                return [Match("3억원")]
            if "원" in pattern:
                return [Match("4원")]
            if "천원" in pattern:
                raise AssertionError("later unit scanned after first unallowed unit")
            raise AssertionError(pattern)

        def unit_normalize(value):
            unit_normalize_inputs.append(value)
            return normalize(value)

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=unit_normalize),
            patch.object(financial_answer_projection, "evidence_numeric_display_candidates", return_value=[]),
            patch.object(
                financial_answer_projection,
                "CALCULATION_NARRATIVE_POLICY",
                {"percent_display_pattern": "PERCENT"},
            ),
            patch.object(
                financial_answer_projection,
                "CALCULATION_RENDER_POLICY",
                {"krw_display_units": ["억원", "  ", "원", "천원"]},
            ),
            patch.object(financial_answer_projection.re, "finditer", side_effect=finditer),
        ):
            self.assertTrue(owner("10% 3억원 4원", "10% 3억원", []))
        self.assertEqual(
            [event for event in events if event[0] == "finditer"],
            [
                ("finditer", "PERCENT", "10% 3억원 4원"),
                ("finditer", r"\d[\d,]*(?:\.\d+)?\s*억원", "10% 3억원 4원"),
                ("finditer", r"\d[\d,]*(?:\.\d+)?\s*원", "10% 3억원 4원"),
            ],
        )
        self.assertEqual(unit_normalize_inputs.count("억원"), 2)
        self.assertEqual(unit_normalize_inputs.count("  "), 1)
        self.assertEqual(unit_normalize_inputs.count("원"), 2)
        self.assertEqual(unit_normalize_inputs.count("천원"), 2)

        class PolicyGetBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("empty allowed surface reached policy")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "evidence_numeric_display_candidates", return_value=[]),
            patch.object(financial_answer_projection, "CALCULATION_NARRATIVE_POLICY", PolicyGetBomb()),
        ):
            self.assertFalse(owner("narrative", "", []))

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection,
                "evidence_numeric_display_candidates",
                side_effect=RuntimeError("display helper"),
            ),
            self.assertRaisesRegex(RuntimeError, "display helper"),
        ):
            owner("10%", "10%", [], [])
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "evidence_numeric_display_candidates", return_value=[]),
            patch.object(
                financial_answer_projection,
                "CALCULATION_NARRATIVE_POLICY",
                {"percent_display_pattern": "PERCENT"},
            ),
            patch.object(financial_answer_projection.re, "finditer", side_effect=RuntimeError("finditer")),
            self.assertRaisesRegex(RuntimeError, "finditer"),
        ):
            owner("10%", "10%", [])

        class MatchGroupBomb:
            def group(self, _index):
                raise RuntimeError("match group")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection, "evidence_numeric_display_candidates", return_value=[]),
            patch.object(
                financial_answer_projection,
                "CALCULATION_NARRATIVE_POLICY",
                {"percent_display_pattern": "PERCENT"},
            ),
            patch.object(financial_answer_projection.re, "finditer", return_value=[MatchGroupBomb()]),
            self.assertRaisesRegex(RuntimeError, "match group"),
        ):
            owner("10%", "10%", [])

    def test_untraced_answer_guard_preserves_sentence_required_token_order_laziness_and_exceptions(self) -> None:
        owner = financial_answer_projection.growth_answer_has_untraced_numeric_sentence
        normalize_events = []

        def normalize(value):
            normalize_events.append(value)
            return " ".join(str(value).split())

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection.re,
                "compile",
                side_effect=AssertionError("blank answer reached compile"),
            ),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                side_effect=AssertionError("blank answer reached splitter"),
            ),
        ):
            self.assertFalse(owner("   ", "complete", ["required"]))
        self.assertEqual(normalize_events, ["   ", "complete", "complete required"])

        pattern_events = []

        class TokenBoolBomb:
            label = "88%"

            def __bool__(self):
                raise AssertionError("later materialized token inspected after first unallowed token")

        class Match:
            def __init__(self, token):
                self.token = token

            def group(self, index):
                pattern_events.append(("group", getattr(self.token, "label", self.token), index))
                return self.token

        class Pattern:
            def finditer(self, sentence):
                pattern_events.append(("finditer", sentence))
                if sentence == "required detail 10%":
                    return [Match("10%")]
                if sentence == "required detail 77% 88%":
                    return [Match("77%"), Match(TokenBoolBomb())]
                raise AssertionError(sentence)

        class LaterSentenceBomb:
            def __str__(self):
                raise AssertionError("later sentence accessed after untraced token")

        compiled = Mock(return_value=Pattern())
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection.re, "compile", compiled),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                return_value=[
                    " ",
                    "required 10%",
                    "unrelated 999%",
                    "required detail 10%",
                    "required detail 77% 88%",
                    LaterSentenceBomb(),
                ],
            ),
        ):
            self.assertTrue(owner("answer", "required 10%", ["required", "10%"]))
        compiled.assert_called_once_with(r"\d[\d,]*(?:\.\d+)?%?")
        self.assertEqual(
            pattern_events,
            [
                ("finditer", "required detail 10%"),
                ("group", "10%", 0),
                ("finditer", "required detail 77% 88%"),
                ("group", "77%", 0),
                ("group", "88%", 0),
            ],
        )

        class EmptyPattern:
            def finditer(self, sentence):
                self.sentence = sentence
                return []

        empty_pattern = EmptyPattern()
        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection.re, "compile", return_value=empty_pattern),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                return_value=["required narrative without numeric token"],
            ),
        ):
            self.assertFalse(owner("answer", "complete", ["required"]))
        self.assertEqual(empty_pattern.sentence, "required narrative without numeric token")

        with (
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(
                financial_answer_projection.re,
                "compile",
                side_effect=AssertionError("empty allowed surface reached compile"),
            ),
            patch.object(
                financial_answer_projection,
                "split_narrative_sentences",
                side_effect=AssertionError("empty allowed surface reached splitter"),
            ),
        ):
            self.assertFalse(owner("answer", "", []))

        class IterableBomb:
            def __iter__(self):
                raise RuntimeError("sentence iteration")

        with (
            self.assertRaisesRegex(RuntimeError, "sentence iteration"),
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection.re, "compile", return_value=Pattern()),
            patch.object(financial_answer_projection, "split_narrative_sentences", return_value=IterableBomb()),
        ):
            owner("answer", "complete", ["required"])
        with (
            self.assertRaisesRegex(RuntimeError, "compile"),
            patch.object(financial_answer_projection, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_answer_projection.re, "compile", side_effect=RuntimeError("compile")),
        ):
            owner("answer", "complete", ["required"])

    def test_trace_guard_bindings_preserve_all_eleven_args_polarities_adoption_and_exception_stop(self) -> None:
        graph_tree = ast.parse(inspect.getsource(financial_graph_calculation.FinancialAgentCalculationMixin))
        owner_tree = ast.parse(inspect.getsource(financial_aggregate_projection))
        tree = ast.Module(body=[*graph_tree.body, *owner_tree.body], type_ignores=[])
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        names = {
            "growth_uses_source_stated_result",
            "growth_sentence_has_untraced_material_numeric",
            "growth_answer_has_untraced_numeric_sentence",
        }
        bindings = Counter()
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in names
            ):
                continue
            cursor = node
            negative = False
            inside_try = False
            caller = None
            while cursor in parents:
                cursor = parents[cursor]
                if isinstance(cursor, ast.UnaryOp) and isinstance(cursor.op, ast.Not):
                    negative = not negative
                if isinstance(cursor, ast.Try):
                    inside_try = True
                if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    caller = cursor.name
                    break
            bindings[
                (
                    node.func.id,
                    caller,
                    tuple(ast.unparse(arg) for arg in node.args),
                    "negative" if negative else "positive",
                    inside_try,
                )
            ] += 1
        sentence = "growth_sentence_has_untraced_material_numeric"
        answer = "growth_answer_has_untraced_numeric_sentence"
        self.assertEqual(
            bindings,
            Counter(
                {
                    ("growth_uses_source_stated_result", "_enforce_source_stated_growth_answer_contract", ("row",), "negative", False): 1,
                    (answer, "ensure_complete_growth_numeric_answer", ("answer_text", "complete_answer", "required_values"), "negative", False): 1,
                    (answer, "_enforce_source_stated_growth_answer_contract", ("answer_text", "complete_answer", "required_values"), "negative", False): 1,
                    (answer, "growth_answer_has_untraced_numeric_material", ("answer_text", "complete_answer", "required_values"), "positive", False): 1,
                    (sentence, "ensure_complete_growth_numeric_answer", ("cleaned", "complete_answer", "required_values", "evidence_items"), "positive", False): 1,
                    (sentence, "_enforce_source_stated_growth_answer_contract", ("cleaned", "complete_answer", "required_values", "evidence_items"), "positive", False): 1,
                    (sentence, "strip_untraced_numeric_material_from_growth_narrative_sentence", ("cleaned", "complete_answer", "required_values", "evidence_items"), "positive", False): 1,
                    (sentence, "strip_untraced_numeric_material_from_growth_narrative_sentence", ("sanitized", "complete_answer", "required_values", "evidence_items"), "positive", False): 1,
                    (sentence, "growth_answer_has_untraced_numeric_material", ("sentence", "complete_answer", "required_values", "evidence_items"), "positive", False): 1,
                    (sentence, "_is_growth_supported_sentence", ("cleaned", "complete_answer", "required_values", "evidence_items"), "negative", False): 1,
                    (sentence, "_is_supported_sentence", ("cleaned", "allowed_narrative_numeric_surface", "required_values", "evidence_items"), "positive", False): 1,
                }
            ),
        )
        self.assertEqual(sum(bindings.values()), 11)

        row = {"row": 1, "operation_family": "growth_rate"}
        for result in (False, True):
            agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            source_owner = Mock(return_value=result)
            agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
            compose_owner = Mock(
                side_effect=RuntimeError("source gate continued")
            )
            with (
                patch.object(
                    financial_graph_calculation,
                    "compose_complete_growth_numeric_answer",
                    compose_owner,
                ),
                patch.object(
                    financial_graph_calculation,
                    "growth_uses_source_stated_result",
                    source_owner,
                ),
                patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            ):
                if result:
                    with self.assertRaisesRegex(RuntimeError, "source gate continued"):
                        agent._enforce_source_stated_growth_answer_contract("answer", [row], [])
                else:
                    self.assertEqual(
                        agent._enforce_source_stated_growth_answer_contract("answer", [row], []),
                        "answer",
                    )
            source_owner.assert_called_once_with(row)
            if result:
                compose_owner.assert_called_once()
            else:
                compose_owner.assert_not_called()

        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        source_owner = Mock(side_effect=RuntimeError("source owner"))
        agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
        compose_owner = Mock(
            side_effect=AssertionError("source exception leaked downstream")
        )
        with (
            patch.object(
                financial_graph_calculation,
                "compose_complete_growth_numeric_answer",
                compose_owner,
            ),
            patch.object(
                financial_graph_calculation,
                "growth_uses_source_stated_result",
                source_owner,
            ),
            patch.object(financial_graph_calculation, "growth_row_has_conflicting_periods", return_value=False),
            self.assertRaisesRegex(RuntimeError, "source owner"),
        ):
            agent._enforce_source_stated_growth_answer_contract("answer", [row], [])
        compose_owner.assert_not_called()

        def configured_material_agent():
            agent = financial_graph_calculation.FinancialAgentCalculationMixin()
            agent._aggregate_result_operation_family = Mock(return_value="growth_rate")
            return agent, Mock(return_value="complete 10%")

        answer_owner = Mock(return_value=True)
        sentence_owner = Mock(side_effect=AssertionError("answer guard failed to short-circuit sentence guard"))
        agent, compose_owner = configured_material_agent()
        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                answer_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                sentence_owner,
            ),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
        ):
            self.assertTrue(
                financial_aggregate_projection.growth_answer_has_untraced_numeric_material("answer", [row], [])
            )
        answer_owner.assert_called_once_with("answer", "complete 10%", ["10%"])
        sentence_owner.assert_not_called()

        answer_owner = Mock(return_value=False)
        sentence_owner = Mock(return_value=True)
        agent, compose_owner = configured_material_agent()
        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                answer_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                sentence_owner,
            ),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", return_value=["sentence"]),
        ):
            self.assertTrue(
                financial_aggregate_projection.growth_answer_has_untraced_numeric_material("answer", [row], [])
            )
        sentence_owner.assert_called_once_with("sentence", "complete 10%", ["10%"], [])

        answer_owner = Mock(side_effect=RuntimeError("answer owner"))
        sentence_owner = Mock(side_effect=AssertionError("answer exception leaked to sentence guard"))
        agent, compose_owner = configured_material_agent()
        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                answer_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                sentence_owner,
            ),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            self.assertRaisesRegex(RuntimeError, "answer owner"),
        ):
            financial_aggregate_projection.growth_answer_has_untraced_numeric_material("answer", [row], [])
        sentence_owner.assert_not_called()

        answer_owner = Mock(return_value=False)
        sentence_owner = Mock(side_effect=RuntimeError("sentence owner"))
        agent, compose_owner = configured_material_agent()
        with (
            patch.object(financial_aggregate_projection, "compose_complete_growth_numeric_answer", compose_owner),
            patch.object(financial_aggregate_projection, "growth_required_display_values", return_value=["10%"]),
            patch.object(
                financial_aggregate_projection,
                "growth_answer_has_untraced_numeric_sentence",
                answer_owner,
            ),
            patch.object(
                financial_aggregate_projection,
                "growth_sentence_has_untraced_material_numeric",
                sentence_owner,
            ),
            patch.object(financial_aggregate_projection, "growth_row_has_conflicting_periods", return_value=False),
            patch.object(financial_aggregate_projection, "_split_narrative_sentences", return_value=["sentence"]),
            self.assertRaisesRegex(RuntimeError, "sentence owner"),
        ):
            financial_aggregate_projection.growth_answer_has_untraced_numeric_material("answer", [row], [])
        sentence_owner.assert_called_once_with("sentence", "complete 10%", ["10%"], [])


if __name__ == "__main__":
    unittest.main()
