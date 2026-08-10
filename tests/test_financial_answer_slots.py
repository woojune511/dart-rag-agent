import ast
import inspect
import math
import unittest
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from unittest.mock import patch

from src.agent import (
    financial_answer_projection,
    financial_answer_slots,
    financial_graph_calculation,
    financial_operand_resolution,
)
from src.agent.financial_answer_slots import (
    RatioResultDisplaySyncInput,
    build_answer_slots,
    build_calculated_value_slot,
    build_missing_value_slot,
    build_operand_value_slot,
    coerce_slot_numeric,
    slot_status,
    synchronize_ratio_result_display,
)


class FinancialAnswerSlotTests(unittest.TestCase):
    def test_answer_slot_material_predicate_preserves_value_contract(self) -> None:
        predicates = (
            ("owner", financial_answer_slots.answer_slot_has_material),
        )
        cases = (
            ("non-dict", None, False),
            ("empty", {}, False),
            ("missing status wins", {"status": " MiSsInG ", "normalized_value": 1.0}, False),
            ("zero is material", {"normalized_value": 0}, True),
            ("false is material", {"normalized_value": False}, True),
            ("empty normalized surface is material", {"normalized_value": ""}, True),
            ("rendered surface", {"normalized_value": None, "rendered_value": " 17 "}, True),
            (
                "raw fallback",
                {"normalized_value": None, "rendered_value": "", "raw_value": " 17 "},
                True,
            ),
            (
                "truthy whitespace rendered surface suppresses raw fallback",
                {"normalized_value": None, "rendered_value": " ", "raw_value": "17"},
                False,
            ),
            (
                "blank surfaces",
                {"normalized_value": None, "rendered_value": " ", "raw_value": "\t"},
                False,
            ),
        )

        nested = {"preserve": True}
        stable_slot = {
            "status": "ok",
            "normalized_value": None,
            "rendered_value": " 17 ",
            "nested": nested,
        }
        for owner, predicate in predicates:
            for case, slot, expected in cases:
                with self.subTest(owner=owner, case=case):
                    self.assertEqual(predicate(slot), expected)
            before = deepcopy(stable_slot)
            self.assertTrue(predicate(stable_slot))
            self.assertEqual(stable_slot, before)
            self.assertIs(stable_slot["nested"], nested)

    def test_answer_slot_material_predicate_preserves_lazy_access_and_exceptions(self) -> None:
        predicates = (
            ("owner", financial_answer_slots.answer_slot_has_material),
        )

        class NonDictBomb:
            def __bool__(self):
                raise RuntimeError("non-dict truth-tested")

        class AccessDict(dict):
            def __init__(self, values, events, *, failure_key=None):
                super().__init__(values)
                self.events = events
                self.failure_key = failure_key

            def __len__(self):
                self.events.append("len")
                return super().__len__()

            def get(self, key, default=None):
                self.events.append(key)
                if key == self.failure_key:
                    raise RuntimeError(f"{key} accessed")
                return super().get(key, default)

        class StringBomb:
            def __str__(self):
                raise RuntimeError("slot string failed")

        for owner, predicate in predicates:
            with self.subTest(owner=owner, path="strict dict gate"):
                self.assertFalse(predicate(NonDictBomb()))

            events = []
            with self.subTest(owner=owner, path="empty"):
                self.assertFalse(predicate(AccessDict({}, events, failure_key="status")))
                self.assertEqual(events, ["len"])

            events = []
            with self.subTest(owner=owner, path="missing status"):
                self.assertFalse(
                    predicate(
                        AccessDict(
                            {"status": " missing ", "normalized_value": 1.0},
                            events,
                            failure_key="normalized_value",
                        )
                    )
                )
                self.assertEqual(events, ["len", "status"])

            events = []
            with self.subTest(owner=owner, path="normalized"):
                self.assertTrue(
                    predicate(
                        AccessDict(
                            {"normalized_value": 0, "rendered_value": "unused"},
                            events,
                            failure_key="rendered_value",
                        )
                    )
                )
                self.assertEqual(events, ["len", "status", "normalized_value"])

            events = []
            with self.subTest(owner=owner, path="rendered"):
                self.assertTrue(
                    predicate(
                        AccessDict(
                            {"normalized_value": None, "rendered_value": " 17 ", "raw_value": "unused"},
                            events,
                            failure_key="raw_value",
                        )
                    )
                )
                self.assertEqual(
                    events,
                    ["len", "status", "normalized_value", "rendered_value"],
                )

            events = []
            with self.subTest(owner=owner, path="raw"):
                self.assertTrue(
                    predicate(
                        AccessDict(
                            {"normalized_value": None, "rendered_value": "", "raw_value": " 17 "},
                            events,
                        )
                    )
                )
                self.assertEqual(
                    events,
                    ["len", "status", "normalized_value", "rendered_value", "raw_value"],
                )

            events = []
            with self.subTest(owner=owner, path="exception"):
                with self.assertRaisesRegex(RuntimeError, "normalized_value accessed"):
                    predicate(
                        AccessDict(
                            {"status": "ok", "normalized_value": 1.0},
                            events,
                            failure_key="normalized_value",
                        )
                    )
                self.assertEqual(events, ["len", "status", "normalized_value"])

            events = []
            with self.subTest(owner=owner, path="string exception"):
                with self.assertRaisesRegex(RuntimeError, "slot string failed"):
                    predicate(
                        AccessDict(
                            {"status": StringBomb(), "normalized_value": 1.0},
                            events,
                            failure_key="normalized_value",
                        )
                    )
                self.assertEqual(events, ["len", "status"])

    def test_answer_slot_material_predicate_bindings_preserve_plain_callback(self) -> None:
        calculation_agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        ordered_results = [{"task_id": "lookup"}]
        delegated_result = [{"task_id": "aligned"}]
        captured = {}

        def align(rows, **kwargs):
            captured["rows"] = rows
            captured.update(kwargs)
            captured["material_result"] = kwargs["slot_has_material"](
                {"normalized_value": 0}
            )
            return delegated_result

        with patch.object(
            financial_graph_calculation,
            "align_lookup_result_units_from_peer_source_slots",
            side_effect=align,
        ):
            actual = calculation_agent._align_lookup_result_units_from_peer_source_slots(
                ordered_results
            )

        self.assertIs(actual, delegated_result)
        self.assertIs(captured["rows"], ordered_results)
        self.assertTrue(captured["material_result"])
        material_callback = captured["slot_has_material"]
        self.assertIs(
            material_callback,
            financial_answer_slots.answer_slot_has_material,
        )

        primary_slot = {"normalized_value": 0, "nested": {"preserve": True}}
        predicate_calls = []

        def material(slot):
            predicate_calls.append(slot)
            return True

        with patch.object(
            financial_answer_projection,
            "answer_slot_has_material",
            side_effect=material,
        ):
            self.assertTrue(
                financial_answer_projection.subtask_row_has_material(
                    {
                        "answer_slots": {
                            "primary_value": primary_slot,
                            "current_value": {"normalized_value": 1},
                        }
                    }
                )
            )
        self.assertEqual(predicate_calls, [primary_slot])
        self.assertIsNot(predicate_calls[0], primary_slot)

    def test_answer_slot_period_helpers_preserve_value_and_immutability_contract(self) -> None:
        period_hint = financial_answer_slots.answer_slot_period_hint
        period_key = financial_answer_slots.period_match_key

        nested = {"preserve": True}
        explicit_slot = {
            "period": " 2024   년 ",
            "label": "ignored 2023년",
            "nested": nested,
        }
        explicit_before = deepcopy(explicit_slot)

        class PolicyBomb:
            def get(self, _key, _default=None):
                raise AssertionError("policy accessed for explicit period")

        with patch.object(
            financial_answer_slots,
            "CALCULATION_SLOT_POLICY",
            PolicyBomb(),
        ):
            self.assertEqual(period_hint(explicit_slot), "2024 년")
        self.assertEqual(explicit_slot, explicit_before)
        self.assertIs(explicit_slot["nested"], nested)

        label_slot = {
            "period": " ",
            "label": " 실적   2023 년 및 2024 년 기준 ",
            "nested": nested,
        }
        label_before = deepcopy(label_slot)
        with patch.object(
            financial_answer_slots,
            "CALCULATION_SLOT_POLICY",
            {"period_pattern": r"20\d{2}\s*년?"},
        ):
            self.assertEqual(period_hint(label_slot), "2023 년")
            self.assertEqual(period_hint({"label": "no matching period"}), "")
        with patch.object(
            financial_answer_slots,
            "CALCULATION_SLOT_POLICY",
            {"period_pattern": ""},
        ), patch.object(
            financial_answer_slots.re,
            "search",
            side_effect=AssertionError("regex accessed for blank pattern"),
        ):
            self.assertEqual(period_hint({"label": "2023년"}), "")
        self.assertEqual(label_slot, label_before)
        self.assertIs(label_slot["nested"], nested)

        for value, expected in (
            (None, ""),
            ("", ""),
            (0, ""),
            (" 2023년 1분기 ", "20231"),
            ("20 23", "2023"),
            ("２０２３년", "２０２３"),
            ("period", ""),
        ):
            with self.subTest(period_match_value=value):
                self.assertEqual(period_key(value), expected)

    def test_answer_slot_period_helpers_preserve_access_laziness_and_exceptions(self) -> None:
        period_hint = financial_answer_slots.answer_slot_period_hint
        period_key = financial_answer_slots.period_match_key

        events = []

        class LoggedSlot(dict):
            def get(self, key, default=None):
                events.append(("get", key))
                return super().get(key, default)

        class LoggedText:
            def __bool__(self):
                events.append(("bool", "period"))
                return True

            def __str__(self):
                events.append(("str", "period"))
                return " 2024 "

        class PolicyBomb:
            def get(self, _key, _default=None):
                raise AssertionError("policy accessed")

        def normalize(value):
            events.append(("normalize", value))
            return " ".join(str(value).split())

        explicit_slot = LoggedSlot({"period": LoggedText(), "label": "unread"})
        with (
            patch.object(
                financial_answer_slots,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_answer_slots,
                "CALCULATION_SLOT_POLICY",
                PolicyBomb(),
            ),
        ):
            self.assertEqual(period_hint(explicit_slot), "2024")
        self.assertEqual(
            events,
            [
                ("get", "period"),
                ("bool", "period"),
                ("str", "period"),
                ("normalize", " 2024 "),
            ],
        )

        events.clear()

        class LoggedPolicy:
            def get(self, key, default=None):
                events.append(("policy", key))
                return r"20\d{2}"

        class LoggedMatch:
            def __bool__(self):
                events.append(("match-bool",))
                return True

            def group(self, index):
                events.append(("match-group", index))
                return "2023"

        def search(pattern, value):
            events.append(("search", pattern, value))
            return LoggedMatch()

        label_slot = LoggedSlot({"period": "", "label": " label   2023 "})
        with (
            patch.object(
                financial_answer_slots,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_answer_slots,
                "CALCULATION_SLOT_POLICY",
                LoggedPolicy(),
            ),
            patch.object(financial_answer_slots.re, "search", side_effect=search),
        ):
            self.assertEqual(period_hint(label_slot), "2023")
        self.assertEqual(
            events,
            [
                ("get", "period"),
                ("normalize", ""),
                ("get", "label"),
                ("normalize", " label   2023 "),
                ("policy", "period_pattern"),
                ("search", r"20\d{2}", "label 2023"),
                ("match-bool",),
                ("match-group", 0),
                ("normalize", "2023"),
            ],
        )

        class GetBomb:
            def get(self, _key, _default=None):
                raise RuntimeError("period get failed")

        with self.assertRaisesRegex(RuntimeError, "period get failed"):
            period_hint(GetBomb())

        class StringBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("period str failed")

        with self.assertRaisesRegex(RuntimeError, "period str failed"):
            period_hint({"period": StringBomb(), "label": "unread"})

        class PeriodBoolBomb:
            def __bool__(self):
                raise RuntimeError("period bool failed")

        with self.assertRaisesRegex(RuntimeError, "period bool failed"):
            period_hint({"period": PeriodBoolBomb(), "label": "unread"})

        with patch.object(
            financial_answer_slots,
            "_normalise_spaces",
            side_effect=RuntimeError("period normalize failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "period normalize failed"):
                period_hint({"period": "2023", "label": "unread"})

        class LabelGetBomb(dict):
            def get(self, key, default=None):
                if key == "label":
                    raise RuntimeError("period label failed")
                return super().get(key, default)

        with self.assertRaisesRegex(RuntimeError, "period label failed"):
            period_hint(LabelGetBomb({"period": ""}))

        class FailingPolicy:
            def get(self, _key, _default=None):
                raise RuntimeError("period policy failed")

        with patch.object(
            financial_answer_slots,
            "CALCULATION_SLOT_POLICY",
            FailingPolicy(),
        ):
            with self.assertRaisesRegex(RuntimeError, "period policy failed"):
                period_hint({"period": "", "label": "2023"})

        with (
            patch.object(
                financial_answer_slots,
                "CALCULATION_SLOT_POLICY",
                {"period_pattern": r"20\d{2}"},
            ),
            patch.object(
                financial_answer_slots.re,
                "search",
                side_effect=RuntimeError("period regex failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "period regex failed"):
                period_hint({"period": "", "label": "2023"})

        class GroupBomb:
            def __bool__(self):
                return True

            def group(self, _index):
                raise RuntimeError("period group failed")

        with (
            patch.object(
                financial_answer_slots,
                "CALCULATION_SLOT_POLICY",
                {"period_pattern": r"20\d{2}"},
            ),
            patch.object(financial_answer_slots.re, "search", return_value=GroupBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "period group failed"):
                period_hint({"period": "", "label": "2023"})

        events.clear()

        class LoggedKeyValue:
            def __bool__(self):
                events.append(("bool", "key"))
                return True

            def __str__(self):
                events.append(("str", "key"))
                return " 20 23 "

        def substitute(pattern, replacement, value):
            events.append(("sub", pattern, replacement, value))
            return "2023"

        with (
            patch.object(
                financial_answer_slots,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(financial_answer_slots.re, "sub", side_effect=substitute),
        ):
            self.assertEqual(period_key(LoggedKeyValue()), "2023")
        self.assertEqual(
            events,
            [
                ("bool", "key"),
                ("str", "key"),
                ("normalize", " 20 23 "),
                ("sub", r"\D", "", "20 23"),
            ],
        )

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("key bool failed")

        with self.assertRaisesRegex(RuntimeError, "key bool failed"):
            period_key(BoolBomb())

        class KeyStringBomb:
            def __bool__(self):
                return True

            def __str__(self):
                raise RuntimeError("key str failed")

        with self.assertRaisesRegex(RuntimeError, "key str failed"):
            period_key(KeyStringBomb())

        events.clear()

        class FalsyKeyValue:
            def __bool__(self):
                events.append(("bool", "falsy-key"))
                return False

            def __str__(self):
                raise AssertionError("falsy key stringified")

        def blank_substitute(pattern, replacement, value):
            events.append(("sub", pattern, replacement, value))
            return ""

        with (
            patch.object(
                financial_answer_slots,
                "_normalise_spaces",
                side_effect=normalize,
            ),
            patch.object(
                financial_answer_slots.re,
                "sub",
                side_effect=blank_substitute,
            ),
        ):
            self.assertEqual(period_key(FalsyKeyValue()), "")
        self.assertEqual(
            events,
            [
                ("bool", "falsy-key"),
                ("normalize", ""),
                ("sub", r"\D", "", ""),
            ],
        )

        with patch.object(
            financial_answer_slots,
            "_normalise_spaces",
            side_effect=RuntimeError("key normalize failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "key normalize failed"):
                period_key("2023")

        with patch.object(
            financial_answer_slots.re,
            "sub",
            side_effect=RuntimeError("key regex failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "key regex failed"):
                period_key("2023")

    def test_answer_slot_period_helper_bindings_preserve_static21_and_growth_polarity(self) -> None:
        def public_callers(name):
            callers = []
            for module_name, module in (
                ("graph", financial_graph_calculation),
                ("owner", financial_answer_projection),
                ("operand", financial_operand_resolution),
            ):
                tree = ast.parse(inspect.getsource(module))
                parents = {}
                for parent in ast.walk(tree):
                    for child in ast.iter_child_nodes(parent):
                        parents[child] = parent
                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue
                    if not isinstance(node.func, ast.Name) or node.func.id != name:
                        continue
                    owner = node
                    while owner in parents and not isinstance(owner, ast.FunctionDef):
                        owner = parents[owner]
                    callers.append((module_name, owner.name))
            return Counter(callers)

        self.assertEqual(
            public_callers("answer_slot_period_hint"),
            Counter(
                {
                    ("graph", "_lookup_gap_is_satisfied_by_sibling_slots"): 2,
                    ("graph", "_sibling_lookup_gap_is_satisfied"): 3,
                    ("graph", "_feedback_gap_is_satisfied_by_derived_slots"): 1,
                    ("graph", "_matching_resolved_slot_for_task"): 1,
                    ("owner", "growth_row_has_conflicting_periods"): 2,
                }
            ),
        )
        self.assertEqual(
            public_callers("period_match_key"),
            Counter(
                {
                    ("graph", "_lookup_gap_is_satisfied_by_sibling_slots"): 3,
                    ("graph", "_feedback_gap_is_satisfied_by_derived_slots"): 3,
                    ("graph", "_task_target_period_keys"): 1,
                    ("graph", "_matching_resolved_slot_for_task"): 1,
                    ("owner", "growth_row_has_conflicting_periods"): 2,
                    ("operand", "growth_operand_periods_conflict"): 2,
                }
            ),
        )

        nested = {"preserve": True}
        current_slot = {"period": "current", "nested": nested}
        prior_slot = {"period": "prior", "nested": nested}
        row = {
            "answer": "2023 result",
            "calculation_result": {
                "answer_slots": {
                    "current_value": current_slot,
                    "prior_value": prior_slot,
                }
            },
        }
        events = []

        def same_hint(slot):
            events.append(("hint", slot))
            return "2023"

        def key(value):
            events.append(("key", value))
            return value

        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                side_effect=same_hint,
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=key,
            ),
        ):
            self.assertTrue(financial_answer_projection.growth_row_has_conflicting_periods(row))
        self.assertEqual([event[0] for event in events], ["hint", "key", "hint", "key"])
        self.assertEqual([event[1] for event in events if event[0] == "key"], ["2023", "2023"])
        prepared_slots = [event[1] for event in events if event[0] == "hint"]
        self.assertEqual(prepared_slots, [current_slot, prior_slot])
        self.assertIsNot(prepared_slots[0], current_slot)
        self.assertIsNot(prepared_slots[1], prior_slot)
        self.assertIs(prepared_slots[0]["nested"], nested)
        self.assertIs(prepared_slots[1]["nested"], nested)

        class RowTextBomb(dict):
            def get(self, key, default=None):
                if key in {"answer", "formatted_result", "rendered_value"}:
                    raise AssertionError("row text accessed after period mismatch")
                return super().get(key, default)

        mismatch_row = RowTextBomb(row)
        events.clear()
        with (
            patch.object(
                financial_answer_projection,
                "answer_slot_period_hint",
                side_effect=lambda slot: events.append(("hint", slot))
                or ("2023" if slot.get("period") == "current" else "2022"),
            ),
            patch.object(
                financial_answer_projection,
                "period_match_key",
                side_effect=lambda value: events.append(("key", value)) or value,
            ),
        ):
            self.assertFalse(
                financial_answer_projection.growth_row_has_conflicting_periods(mismatch_row)
            )
        self.assertEqual([event[0] for event in events], ["hint", "key", "hint", "key"])

    def test_source_task_display_compatibility_preserves_behavior_contract(self) -> None:
        compatible = financial_answer_slots.source_task_display_compatible_with_slot

        class SlotBomb:
            def get(self, _key, _default=None):
                raise RuntimeError("slot accessed for blank source display")

        self.assertFalse(compatible(SlotBomb(), "  "))  # type: ignore[arg-type]

        nested = {"preserve": True}

        def slot(**updates):
            row = {
                "rendered_value": "slot 100 million",
                "raw_value": "100",
                "source_row_id": "source:row",
                "raw_unit": "million",
                "normalized_unit": "KRW",
                "nested": nested,
            }
            row.update(updates)
            return row

        policy = {
            "krw_normalized_unit": "KRW",
            "krw_display_units": ["won", "thousand won"],
        }
        cases = [
            ("normalized exact rendered", slot(rendered_value="slot   100 million"), " slot 100  million ", True),
            ("raw display fallback", slot(rendered_value="", raw_value="raw 100"), "raw 100", True),
            ("task output source", slot(source_row_id="task_output:lookup"), "100 won", True),
            ("blank raw unit", slot(raw_unit=""), "100 items", True),
            ("raw unit present", slot(raw_unit="million"), "100 million", True),
            ("krw display conflicts", slot(normalized_unit="krw"), "100 won", False),
            ("non-krw display tolerated", slot(normalized_unit="COUNT"), "100 won", True),
            ("krw non-display tolerated", slot(normalized_unit="KRW"), "100 items", True),
        ]
        with patch.object(financial_answer_slots, "CALCULATION_RENDER_POLICY", policy):
            for name, slot_row, source_display, expected in cases:
                with self.subTest(case=name):
                    before = deepcopy(slot_row)
                    self.assertEqual(compatible(slot_row, source_display), expected)
                    self.assertEqual(slot_row, before)
                    self.assertIs(slot_row["nested"], nested)

    def test_source_task_display_compatibility_preserves_access_lazy_and_exception_contract(self) -> None:
        compatible = financial_answer_slots.source_task_display_compatible_with_slot

        class AccessDict(dict):
            def __init__(self, values, events, *, failure_key=None):
                super().__init__(values)
                self.events = events
                self.failure_key = failure_key

            def get(self, key, default=None):
                self.events.append(key)
                if key == self.failure_key:
                    raise RuntimeError(f"{key} accessed")
                return super().get(key, default)

        events = []
        self.assertTrue(
            compatible(
                AccessDict({"rendered_value": "same", "raw_value": "unused"}, events, failure_key="raw_value"),
                " same ",
            )
        )
        self.assertEqual(events, ["rendered_value"])

        events = []
        self.assertTrue(
            compatible(
                AccessDict(
                    {"rendered_value": "", "raw_value": "slot", "source_row_id": "task_output:lookup"},
                    events,
                    failure_key="raw_unit",
                ),
                "source",
            )
        )
        self.assertEqual(events, ["rendered_value", "raw_value", "source_row_id"])

        for name, values, failure_key, source_display, expected_events in (
            (
                "blank raw unit",
                {"rendered_value": "slot", "source_row_id": "source", "raw_unit": ""},
                "normalized_unit",
                "source",
                ["rendered_value", "source_row_id", "raw_unit"],
            ),
            (
                "contained raw unit",
                {"rendered_value": "slot", "source_row_id": "source", "raw_unit": "million"},
                "normalized_unit",
                "source million",
                ["rendered_value", "source_row_id", "raw_unit"],
            ),
        ):
            with self.subTest(case=name):
                events = []
                self.assertTrue(
                    compatible(
                        AccessDict(values, events, failure_key=failure_key),
                        source_display,
                    )
                )
                self.assertEqual(events, expected_events)

        class AccessPolicy(dict):
            def __init__(self, values, events, *, failure_key=None):
                super().__init__(values)
                self.events = events
                self.failure_key = failure_key

            def get(self, key, default=None):
                self.events.append(key)
                if key == self.failure_key:
                    raise RuntimeError(f"policy {key} accessed")
                return super().get(key, default)

        policy_events = []
        lazy_policy = AccessPolicy(
            {"krw_normalized_unit": "KRW"},
            policy_events,
            failure_key="krw_display_units",
        )
        with patch.object(financial_answer_slots, "CALCULATION_RENDER_POLICY", lazy_policy):
            self.assertTrue(
                compatible(
                    {
                        "rendered_value": "slot",
                        "source_row_id": "source",
                        "raw_unit": "million",
                        "normalized_unit": "COUNT",
                    },
                    "source won",
                )
            )
        self.assertEqual(policy_events, ["krw_normalized_unit"])

        ordered_events = []

        class OrderedSlot(dict):
            def get(self, key, default=None):
                ordered_events.append(f"slot:{key}")
                return super().get(key, default)

        class OrderedPolicy(dict):
            def get(self, key, default=None):
                ordered_events.append(f"policy:{key}")
                return super().get(key, default)

        with patch.object(
            financial_answer_slots,
            "CALCULATION_RENDER_POLICY",
            OrderedPolicy(krw_normalized_unit="KRW", krw_display_units=[]),
        ):
            self.assertTrue(
                compatible(
                    OrderedSlot(
                        rendered_value="slot",
                        source_row_id="source",
                        raw_unit="million",
                        normalized_unit="KRW",
                    ),
                    "source",
                )
            )
        self.assertEqual(
            ordered_events,
            [
                "slot:rendered_value",
                "slot:source_row_id",
                "slot:raw_unit",
                "slot:normalized_unit",
                "policy:krw_normalized_unit",
                "policy:krw_display_units",
            ],
        )

        class CountingString:
            def __init__(self, value):
                self.value = value
                self.calls = 0

            def __str__(self):
                self.calls += 1
                return self.value

        retained_unit = CountingString("won")
        blank_unit = CountingString("")
        policy_events = []
        counted_policy = AccessPolicy(
            {"krw_normalized_unit": "KRW", "krw_display_units": [retained_unit, blank_unit]},
            policy_events,
        )
        with patch.object(financial_answer_slots, "CALCULATION_RENDER_POLICY", counted_policy):
            self.assertFalse(
                compatible(
                    {
                        "rendered_value": "slot",
                        "source_row_id": "source",
                        "raw_unit": "million",
                        "normalized_unit": "KRW",
                    },
                    "source won",
                )
            )
        self.assertEqual(policy_events, ["krw_normalized_unit", "krw_display_units"])
        self.assertEqual((retained_unit.calls, blank_unit.calls), (2, 1))

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("truthiness failed")

        class StringBomb:
            def __str__(self):
                raise RuntimeError("string failed")

        class GetBomb(Mapping):
            def __len__(self):
                return 1

            def __iter__(self):
                return iter(("rendered_value",))

            def __getitem__(self, key):
                raise KeyError(key)

            def get(self, _key, _default=None):
                raise RuntimeError("mapping get failed")

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("iteration failed")

        with self.assertRaisesRegex(RuntimeError, "truthiness failed"):
            compatible({}, BoolBomb())
        with self.assertRaisesRegex(RuntimeError, "string failed"):
            compatible({}, StringBomb())
        with self.assertRaisesRegex(RuntimeError, "mapping get failed"):
            compatible(GetBomb(), "source")  # type: ignore[arg-type]
        with patch.object(
            financial_answer_slots,
            "_normalise_spaces",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                compatible({}, "source")
        with patch.object(
            financial_answer_slots,
            "CALCULATION_RENDER_POLICY",
            {"krw_normalized_unit": "KRW", "krw_display_units": IterBomb()},
        ):
            with self.assertRaisesRegex(RuntimeError, "iteration failed"):
                compatible(
                    {
                        "rendered_value": "slot",
                        "source_row_id": "source",
                        "raw_unit": "million",
                        "normalized_unit": "KRW",
                    },
                    "source won",
                )

    def test_ratio_display_sync_preserves_gate_copy_and_exception_contract(self) -> None:
        def sync(payload):
            return synchronize_ratio_result_display(
                RatioResultDisplaySyncInput(calculation_result=payload)
            ).calculation_result

        untouched_cases = [
            ("status", {"status": "partial", "result_value": 10.0, "result_unit": "%"}),
            (
                "operation",
                {"status": "ok", "operation_family": "difference", "result_value": 10.0, "result_unit": "%"},
            ),
            (
                "source_stated",
                {
                    "status": "ok",
                    "result_value": 10.0,
                    "result_unit": "%",
                    "derived_metrics": {"source_stated_result_used": True},
                },
            ),
            ("missing_result", {"status": "ok", "result_unit": "%"}),
            ("invalid_result", {"status": "ok", "result_value": "invalid", "result_unit": "%"}),
            ("non_percent", {"status": "ok", "result_value": 10.0, "result_unit": "COUNT"}),
        ]
        for case_name, payload in untouched_cases:
            with self.subTest(case_name=case_name), patch.object(
                financial_answer_slots,
                "format_ratio_percent_result",
                wraps=financial_answer_slots.format_ratio_percent_result,
            ) as formatter:
                before = deepcopy(payload)
                result = sync(payload)
                self.assertIs(result, payload)
                self.assertEqual(payload, before)
                formatter.assert_not_called()

        marker = {"preserve": True}
        original_primary = {
            "status": "derived",
            "raw_value": "old",
            "raw_unit": "old-unit",
            "normalized_value": 1.0,
            "normalized_unit": "OLD",
            "rendered_value": "1%",
            "nested": marker,
        }
        original_slots = {"primary_value": original_primary, "nested": marker}
        within_tolerance = {
            "status": "ok",
            "result_value": 10.0,
            "result_unit": "%",
            "rendered_value": "1%",
            "answer_slots": original_slots,
            "derived_metrics": {"formula_result_value": 10.000005},
            "nested": marker,
        }
        result = sync(within_tolerance)
        self.assertIs(result, within_tolerance)
        self.assertEqual(result["result_value"], 10.0)
        self.assertEqual(result["rendered_value"], "10%")
        self.assertTrue(result["ratio_display_synced_from_result_value"])
        self.assertIsNot(result["answer_slots"], original_slots)
        self.assertIsNot(result["answer_slots"]["primary_value"], original_primary)
        self.assertEqual(
            {
                key: result["answer_slots"]["primary_value"][key]
                for key in ("status", "raw_value", "raw_unit", "normalized_value", "normalized_unit", "rendered_value")
            },
            {
                "status": "derived",
                "raw_value": "10%",
                "raw_unit": "%",
                "normalized_value": 10.0,
                "normalized_unit": "PERCENT",
                "rendered_value": "10%",
            },
        )
        self.assertIs(result["answer_slots"]["nested"], marker)
        self.assertIs(result["answer_slots"]["primary_value"]["nested"], marker)
        self.assertIs(result["nested"], marker)

        invalid_formula = {
            "status": "ok",
            "result_value": 7.0,
            "result_unit": "%",
            "rendered_value": "1%",
            "derived_metrics": {"formula_result_value": "invalid"},
        }
        self.assertIs(sync(invalid_formula), invalid_formula)
        self.assertEqual(invalid_formula["rendered_value"], "7%")

        copied_marker = {"preserve": "copy"}
        outside_tolerance = {
            "status": "ok",
            "result_value": 10.0,
            "result_unit": "%",
            "rendered_value": "1%",
            "answer_slots": {"primary_value": {"rendered_value": "1%", "nested": copied_marker}},
            "derived_metrics": {"formula_result_value": 20.0, "nested": copied_marker},
            "nested": copied_marker,
        }
        outside_before = deepcopy(outside_tolerance)
        copied = sync(outside_tolerance)
        self.assertIsNot(copied, outside_tolerance)
        self.assertEqual(outside_tolerance, outside_before)
        self.assertEqual((copied["result_value"], copied["rendered_value"]), (20.0, "20%"))
        self.assertTrue(copied["derived_metrics"]["result_value_synced_from_formula_trace"])
        self.assertTrue(copied["ratio_display_synced_from_result_value"])
        self.assertIs(copied["nested"], copied_marker)
        self.assertIs(copied["derived_metrics"]["nested"], copied_marker)
        self.assertIs(copied["answer_slots"]["primary_value"]["nested"], copied_marker)

        copied_then_veto = {
            "status": "ok",
            "result_value": 10.0,
            "result_unit": "%",
            "rendered_value": "20%",
            "derived_metrics": {"formula_result_value": 20.0},
        }
        veto_before = deepcopy(copied_then_veto)
        vetoed = sync(copied_then_veto)
        self.assertIsNot(vetoed, copied_then_veto)
        self.assertEqual(copied_then_veto, veto_before)
        self.assertEqual((vetoed["result_value"], vetoed["rendered_value"]), (20.0, "20%"))
        self.assertTrue(vetoed["derived_metrics"]["result_value_synced_from_formula_trace"])
        self.assertNotIn("ratio_display_synced_from_result_value", vetoed)

        equivalent = {
            "status": "ok",
            "result_value": 12.345,
            "result_unit": "%",
            "rendered_value": "12.35%",
        }
        equivalent_before = deepcopy(equivalent)
        with patch.object(
            financial_answer_slots,
            "numeric_surface_candidates_equivalent",
            wraps=financial_answer_slots.numeric_surface_candidates_equivalent,
        ) as equivalence:
            self.assertIs(sync(equivalent), equivalent)
        equivalence.assert_called_once()
        self.assertEqual(equivalent, equivalent_before)

        target_parse_veto = {
            "status": "ok",
            "result_value": 9.0,
            "result_unit": "%",
            "rendered_value": "old",
        }
        with patch.object(
            financial_answer_slots,
            "format_ratio_percent_result",
            return_value="not numeric",
        ) as formatter, patch.object(
            financial_answer_slots,
            "extract_numeric_surface_candidates",
            return_value=[],
        ) as parser:
            self.assertIs(sync(target_parse_veto), target_parse_veto)
        formatter.assert_called_once_with(9.0)
        parser.assert_called_once_with("not numeric")

        class TrackingUnit:
            def __init__(self):
                self.str_calls = 0

            def __str__(self):
                self.str_calls += 1
                return "%"

        policy_unit = TrackingUnit()
        with patch.object(
            financial_answer_slots,
            "NUMERIC_UNIT_NORMALIZATION_POLICY",
            {"percent_units": [policy_unit]},
        ):
            non_policy_result = {"status": "ok", "result_value": 9.0, "result_unit": "COUNT"}
            self.assertIs(sync(non_policy_result), non_policy_result)
        self.assertEqual(policy_unit.str_calls, 2)

        surface_priority = {
            "status": "ok",
            "result_value": 9.0,
            "result_unit": "%",
            "rendered_value": "22%",
            "formatted_result": "33%",
            "answer_slots": {"primary_value": {"rendered_value": "11%"}},
        }
        with patch.object(
            financial_answer_slots,
            "extract_numeric_surface_candidates",
            wraps=financial_answer_slots.extract_numeric_surface_candidates,
        ) as parser:
            sync(surface_priority)
        self.assertEqual([item.args[0] for item in parser.call_args_list], ["9%", "11%"])

        nan_result = {"status": "ok", "result_value": float("nan"), "result_unit": "%"}
        self.assertIs(sync(nan_result), nan_result)
        self.assertTrue(math.isnan(nan_result["result_value"]))
        self.assertNotIn("ratio_display_synced_from_result_value", nan_result)

        class FailingFloat:
            def __init__(self, exception_type):
                self.exception_type = exception_type
                self.calls = 0

            def __float__(self):
                self.calls += 1
                raise self.exception_type("cannot coerce")

        for exception_type in (TypeError, ValueError):
            with self.subTest(caught=exception_type.__name__):
                value = FailingFloat(exception_type)
                payload = {"status": "ok", "result_value": value, "result_unit": "%"}
                self.assertIs(sync(payload), payload)
                self.assertEqual(value.calls, 2)

        ordered_payload = {
            "status": "ok",
            "result_value": 8.0,
            "result_unit": "%",
            "rendered_value": "old",
        }
        events = []
        real_parser = financial_answer_slots.extract_numeric_surface_candidates

        def parser(surface):
            events.append(f"parse:{surface}")
            if sum(event.startswith("parse:") for event in events) == 2:
                raise RuntimeError("current parse failed")
            return real_parser(surface)

        with patch.object(
            financial_answer_slots,
            "format_ratio_percent_result",
            side_effect=lambda value: events.append(f"format:{value}") or "8%",
        ), patch.object(
            financial_answer_slots,
            "extract_numeric_surface_candidates",
            side_effect=parser,
        ):
            with self.assertRaisesRegex(RuntimeError, "current parse failed"):
                sync(ordered_payload)
        self.assertEqual(events, ["format:8.0", "parse:8%", "parse:old"])
        self.assertNotIn("ratio_display_synced_from_result_value", ordered_payload)

        with patch.object(
            financial_answer_slots,
            "format_ratio_percent_result",
            side_effect=RuntimeError("format failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "format failed"):
                sync(dict(ordered_payload))

        class TrackingResult(dict):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                self.accessed = []

            def get(self, key, default=None):
                self.accessed.append(key)
                if key == "result_unit":
                    raise RuntimeError("unit access failed")
                return super().get(key, default)

        tracked = TrackingResult(status="ok", result_value=5.0)
        with self.assertRaisesRegex(RuntimeError, "unit access failed"):
            sync(tracked)
        self.assertEqual(
            tracked.accessed,
            ["status", "operation_family", "derived_metrics", "result_value", "result_unit"],
        )

    def test_slot_status_uses_numeric_then_surface_material(self) -> None:
        self.assertEqual(slot_status(normalized_value=1.0, rendered_value="", raw_value=""), "ok")
        self.assertEqual(slot_status(normalized_value=None, rendered_value="123", raw_value=""), "derived")
        self.assertEqual(slot_status(normalized_value=None, rendered_value="", raw_value=""), "missing")

    def test_coerce_slot_numeric_returns_none_for_unparseable_values(self) -> None:
        self.assertEqual(coerce_slot_numeric("12.5"), 12.5)
        self.assertIsNone(coerce_slot_numeric("not numeric"))

    def test_build_missing_value_slot_preserves_source_ids_and_policy_defaults(self) -> None:
        slot = build_missing_value_slot(
            role="primary_value",
            label=" 매출 ",
            concept="revenue",
            source_row_ids=["", "row_1", "row_1"],
        )

        self.assertEqual(slot["status"], "missing")
        self.assertEqual(slot["role"], "primary_value")
        self.assertEqual(slot["label"], "매출")
        self.assertEqual(slot["concept"], "revenue")
        self.assertEqual(slot["normalized_unit"], "UNKNOWN")
        self.assertEqual(slot["source_row_id"], "row_1")
        self.assertEqual(slot["source_row_ids"], ["row_1"])

    def test_build_operand_value_slot_renders_normalized_value(self) -> None:
        slot = build_operand_value_slot(
            {
                "label": "자본",
                "matched_operand_role": "denominator",
                "matched_operand_concept": "equity",
                "raw_value": "100",
                "raw_unit": "%",
                "normalized_value": 100.0,
                "normalized_unit": "PERCENT",
                "source_row_ids": ["row_a"],
                "source_anchor": "anchor",
            },
            default_role="operand",
        )

        self.assertEqual(slot["status"], "ok")
        self.assertEqual(slot["role"], "denominator")
        self.assertEqual(slot["label"], "자본")
        self.assertEqual(slot["concept"], "equity")
        self.assertEqual(slot["rendered_value"], "100%")
        self.assertEqual(slot["source_row_id"], "row_a")
        self.assertEqual(slot["source_anchor"], "anchor")

    def test_build_calculated_value_slot_uses_display_unit_renderer(self) -> None:
        slot = build_calculated_value_slot(
            label="차이",
            normalized_value=1_000_000.0,
            normalized_unit="KRW",
            display_unit="백만원",
            period="2023",
            source_row_ids=["row_a", "row_b"],
            role="delta_value",
        )

        self.assertEqual(slot["status"], "ok")
        self.assertEqual(slot["role"], "delta_value")
        self.assertEqual(slot["rendered_value"], "1백만원")
        self.assertEqual(slot["source_row_ids"], ["row_a", "row_b"])

    def test_build_answer_slots_creates_missing_lookup_primary_value(self) -> None:
        slots = build_answer_slots(
            active_subtask={
                "operation_family": "lookup",
                "metric_label": "법인세비용차감전순이익",
                "required_operands": [
                    {
                        "role": "operand",
                        "label": "법인세비용차감전순이익",
                        "concept": "income_before_income_taxes",
                        "period_hint": "2023년",
                    }
                ],
            },
            operation_family="lookup",
            ordered_operands=[],
            result_value=None,
            result_unit="",
            normalized_unit="UNKNOWN",
            source_normalized_unit="UNKNOWN",
            current_value=None,
            prior_value=None,
            delta_value=None,
            current_period="2023",
            prior_period="",
            source_row_ids=[],
        )

        self.assertEqual(slots["operation_family"], "lookup")
        self.assertEqual(slots["primary_value"]["status"], "missing")
        self.assertEqual(slots["primary_value"]["concept"], "income_before_income_taxes")
        self.assertEqual(slots["primary_value"]["period"], "2023년")

    def test_build_answer_slots_creates_difference_period_slots(self) -> None:
        slots = build_answer_slots(
            active_subtask={
                "operation_family": "difference",
                "metric_label": "증감액",
                "required_operands": [
                    {"role": "current_period", "label": "당기"},
                    {"role": "prior_period", "label": "전기"},
                ],
            },
            operation_family="difference",
            ordered_operands=[
                {
                    "evidence_id": "row_current",
                    "label": "당기",
                    "matched_operand_role": "current_period",
                    "raw_value": "3",
                    "raw_unit": "%",
                    "normalized_value": 3.0,
                    "normalized_unit": "PERCENT",
                    "period": "2023",
                },
                {
                    "evidence_id": "row_prior",
                    "label": "전기",
                    "matched_operand_role": "prior_period",
                    "raw_value": "1",
                    "raw_unit": "%",
                    "normalized_value": 1.0,
                    "normalized_unit": "PERCENT",
                    "period": "2022",
                },
            ],
            result_value=2.0,
            result_unit="%p",
            normalized_unit="PERCENT",
            source_normalized_unit="PERCENT",
            current_value=3.0,
            prior_value=1.0,
            delta_value=2.0,
            current_period="2023",
            prior_period="2022",
            source_row_ids=["row_current", "row_prior"],
        )

        self.assertEqual(slots["operation_family"], "difference")
        self.assertEqual(slots["primary_value"]["role"], "delta_value")
        self.assertEqual(slots["current_value"]["rendered_value"], "3%")
        self.assertEqual(slots["prior_value"]["rendered_value"], "1%")
        self.assertEqual(slots["delta_value"]["rendered_value"], "2.00%p")
        self.assertEqual(slots["direction"], "increase")


if __name__ == "__main__":
    unittest.main()
