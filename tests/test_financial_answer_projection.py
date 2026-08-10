import ast
import inspect
import unittest
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from unittest.mock import Mock, patch

from src.agent import (
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
                    ("graph", "_ensure_complete_growth_numeric_answer", "row"): 1,
                    ("graph", "_final_growth_answer_without_untraced_numeric_sentences", "row"): 1,
                    ("graph", "_enforce_source_stated_growth_answer_contract", "row"): 1,
                    ("graph", "_has_strong_growth_trace_for_answer_refresh", "row"): 1,
                    ("graph", "_strip_untraced_numeric_material_from_growth_narrative_sentence", "row"): 1,
                    ("graph", "_growth_answer_has_untraced_numeric_material", "row"): 1,
                    ("graph", "_narrative_summary_conflicts_with_growth_trace", "row"): 1,
                    ("graph", "_growth_narrative_numeric_incompatible_with_trace", "row"): 1,
                    ("graph", "_is_growth_supported_sentence", "row"): 1,
                    ("graph", "_compose_growth_narrative_answer", "row"): 1,
                    ("graph", "_answer_satisfies_growth_narrative_intent", "row"): 1,
                    ("planning", "_build_aggregate_calculation_projection", "dict(row)"): 1,
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
                    ("graph", "_safe_partial_answer_for_numeric_gap", "row"): 1,
                    ("graph", "_compose_lookup_list_numeric_answer", "row"): 1,
                    ("graph", "_append_uncovered_lookup_numeric_items", "row"): 1,
                    ("graph", "_preferred_complete_numeric_answer", "row"): 1,
                    ("graph", "_numeric_projection_coverage_targets", "row"): 1,
                    ("graph", "_infer_planner_feedback_from_answer_slots", "row"): 2,
                    ("graph", "_aggregate_result_rank", "row"): 1,
                    ("graph", "_nested_aggregate_result_rank", "row"): 1,
                    ("graph", "_promote_stronger_nested_aggregate_results", "dict(nested_row)"): 1,
                    ("graph", "_promote_stronger_nested_aggregate_results", "current_row"): 1,
                    ("graph", "_resolve_aggregate_feedback_state", "row"): 1,
                    ("planning", "_build_aggregate_calculation_projection", "dict(row)"): 1,
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
                    ("graph", "_nested_aggregate_result_rank", "row"): 1,
                    ("planning", "_subtask_row_specificity_score", "row"): 1,
                    (
                        "planning",
                        "_promote_nested_subtask_result_if_more_specific",
                        "{'answer': answer, 'status': status, 'metric_family': active_subtask.get('metric_family'), 'metric_label': active_subtask.get('metric_label'), 'operation_family': active_operation, 'calculation_result': calculation_result}",
                    ): 1,
                    ("planning", "_subtask_upsert_quality_rank", "row"): 1,
                }
            ),
        )
        self.assertEqual(
            (len(external_growth), len(external_gap), len(external_row)),
            (13, 15, 4),
        )

        graph_growth = [entry for entry in external_growth if entry["module"] == "graph"]
        self.assertEqual(len(graph_growth), 12)
        for entry in graph_growth:
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

        planning_growth = next(
            entry for entry in external_growth if entry["module"] == "planning"
        )
        self.assertIsInstance(planning_growth["statement"], ast.Assign)
        self.assertEqual(
            ast.unparse(planning_growth["statement"].targets[0]),
            "is_conflicting_growth",
        )

        positive_continue_gap_callers = {
            "_feedback_gap_is_satisfied_by_derived_slots",
            "_safe_partial_answer_for_numeric_gap",
            "_compose_lookup_list_numeric_answer",
            "_append_uncovered_lookup_numeric_items",
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
            "_nested_aggregate_result_rank": "gap_free_rank",
        }
        for caller, target in rank_targets.items():
            entry = next(item for item in external_gap if item["caller"] == caller)
            self.assertIsInstance(entry["statement"], ast.Assign)
            self.assertEqual(ast.unparse(entry["statement"].targets[0]), target)
            self.assertIsInstance(entry["statement"].value, ast.IfExp)

        nested_row_rank = next(
            entry for entry in external_row if entry["module"] == "graph"
        )
        self.assertEqual(ast.unparse(nested_row_rank["statement"].targets[0]), "material_rank")
        self.assertIsInstance(nested_row_rank["statement"].value, ast.IfExp)

        row = {"task_id": "growth", "nested": {"preserve": True}}
        ordered_results = [row]
        compose_owner = Mock(return_value="replacement")
        with (
            patch.object(
                self.calculation_agent,
                "_aggregate_result_operation_family",
                return_value="growth_rate",
            ),
            patch.object(
                financial_graph_calculation,
                "growth_row_has_conflicting_periods",
                return_value=True,
            ) as growth_owner,
            patch.object(
                self.calculation_agent,
                "_compose_complete_growth_numeric_answer",
                compose_owner,
            ),
        ):
            self.assertEqual(
                self.calculation_agent._ensure_complete_growth_numeric_answer(
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
                self.calculation_agent,
                "_aggregate_result_operation_family",
                return_value="growth_rate",
            ),
            patch.object(
                financial_graph_calculation,
                "growth_row_has_conflicting_periods",
                side_effect=RuntimeError("growth binding failed"),
            ),
            patch.object(
                self.calculation_agent,
                "_compose_complete_growth_numeric_answer",
                compose_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "growth binding failed"):
                self.calculation_agent._ensure_complete_growth_numeric_answer(
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
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                return_value="gap",
            ) as gap_owner,
            patch.object(
                financial_graph_calculation,
                "growth_operand_sign_consistency_rank",
                return_value=6,
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_result_dependency_coherence_ranks",
                return_value=(5, 4),
            ),
        ):
            self.assertEqual(
                self.calculation_agent._aggregate_result_rank(rank_row),
                (4, 0, 1, 6, 5, 4, 1),
            )
        gap_owner.assert_called_once_with(rank_row)

        later = Mock()
        with (
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                side_effect=RuntimeError("gap binding failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "growth_operand_sign_consistency_rank",
                later,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "gap binding failed"):
                self.calculation_agent._aggregate_result_rank(rank_row)
        later.assert_not_called()

        with (
            patch.object(
                financial_graph_calculation,
                "subtask_row_has_material",
                return_value=True,
            ) as row_owner,
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                return_value="",
            ) as nested_gap_owner,
            patch.object(
                self.calculation_agent,
                "_aggregate_result_operation_family",
                return_value="lookup",
            ),
            patch.object(
                financial_graph_calculation,
                "growth_operand_sign_consistency_rank",
                return_value=1,
            ),
        ):
            nested_rank = self.calculation_agent._nested_aggregate_result_rank(rank_row)
        self.assertEqual(nested_rank[:5], (4, 1, 1, 1, 1))
        row_owner.assert_called_once_with(rank_row)
        nested_gap_owner.assert_called_once_with(rank_row)

        nested_gap_owner.reset_mock()
        with (
            patch.object(
                financial_graph_calculation,
                "subtask_row_has_material",
                side_effect=RuntimeError("row binding failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "material_gap_feedback_for_subtask_result",
                nested_gap_owner,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "row binding failed"):
                self.calculation_agent._nested_aggregate_result_rank(rank_row)
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
                self.planning_agent,
                "_aggregate_result_operation_family",
                return_value="growth_rate",
                create=True,
            ),
            patch.object(
                financial_graph_planning,
                "growth_row_has_conflicting_periods",
                side_effect=planning_growth_owner,
            ),
            patch.object(
                financial_graph_planning,
                "material_gap_feedback_for_subtask_result",
                side_effect=planning_gap_owner,
            ),
            patch.object(
                financial_graph_planning,
                "_build_aggregate_calculation_projection",
                return_value=built_projection,
            ) as builder,
        ):
            projection = self.planning_agent._build_aggregate_calculation_projection(
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
                self.planning_agent,
                "_aggregate_result_operation_family",
                return_value="growth_rate",
                create=True,
            ),
            patch.object(
                financial_graph_planning,
                "growth_row_has_conflicting_periods",
                side_effect=RuntimeError("planning growth failed"),
            ),
            patch.object(
                financial_graph_planning,
                "material_gap_feedback_for_subtask_result",
                gap_after_growth,
            ),
            patch.object(
                financial_graph_planning,
                "_build_aggregate_calculation_projection",
                builder,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "planning growth failed"):
                self.planning_agent._build_aggregate_calculation_projection(
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
                self.planning_agent,
                "_subtask_row_operation_family",
                return_value="lookup",
            ),
            patch.object(
                financial_graph_planning,
                "subtask_row_has_material",
                return_value=True,
            ) as specificity_owner,
        ):
            specificity = self.planning_agent._subtask_row_specificity_score(
                specificity_row,
                active_subtask=active_subtask,
            )
        self.assertEqual(specificity[:2], (4, 1))
        specificity_owner.assert_called_once_with(specificity_row)

        current_result = {"subtask_results": [{"task_id": "nested"}]}
        best_row = {"task_id": "best", "calculation_result": {"status": "ok"}}
        with (
            patch.object(
                self.planning_agent,
                "_nested_subtask_rows",
                return_value=[best_row],
            ),
            patch.object(
                self.planning_agent,
                "_subtask_row_specificity_score",
                return_value=(3, 1, 1, 1, 1, 1),
            ),
            patch.object(
                financial_graph_planning,
                "subtask_row_has_material",
                return_value=True,
            ) as current_owner,
        ):
            promoted = self.planning_agent._promote_nested_subtask_result_if_more_specific(
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
            financial_graph_planning,
            "subtask_row_has_material",
            return_value=False,
        ) as upsert_owner:
            upsert_rank = self.planning_agent._subtask_upsert_quality_rank(
                {"status": "ok", "answer": "10"}
            )
        self.assertEqual(upsert_rank[:2], (4, 0))
        upsert_owner.assert_called_once_with({"status": "ok", "answer": "10"})

if __name__ == "__main__":
    unittest.main()
