import ast
import builtins
import inspect
import unittest
from collections import Counter
from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agent import financial_aggregate_projection, financial_answer_slots, financial_graph_calculation


class FinancialRatioReadinessTests(unittest.TestCase):
    def test_ratio_component_scope_preserves_order_distinctness_copy_and_exceptions(self) -> None:
        events = []

        class CopyOnlyGroups(Mapping):
            def __init__(self, values):
                self._values = values

            def __getitem__(self, key):
                events.append(("group-item", key))
                return self._values[key]

            def __iter__(self):
                events.append(("group-iter",))
                return iter(self._values)

            def __len__(self):
                events.append(("group-len",))
                return len(self._values)

            def values(self):
                raise AssertionError("scope helper used the source mapping instead of its copy")

        class ScopeText:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(("scope-str", self.name))
                return self.value

        groups = CopyOnlyGroups(
            {
                "denominator": [
                    {"consolidation_scope": ScopeText("group-first", " consolidated ")},
                    {"consolidation_scope": ScopeText("group-duplicate", "consolidated")},
                    {"consolidation_scope": ScopeText("group-invalid", "unknown")},
                ],
                "numerator": [
                    {"consolidation_scope": ScopeText("group-conflict", " separate ")},
                ],
            }
        )
        operands = [
            {"consolidation_scope": ScopeText("operand-duplicate", "separate")},
            {"consolidation_scope": ScopeText("operand-invalid", "mixed")},
        ]
        calculation_result = {"answer_slots": {"components_by_group": groups}}
        with patch.object(
            financial_answer_slots,
            "_normalise_spaces",
            side_effect=lambda value: events.append(("normalize", value)) or value.strip(),
        ):
            self.assertEqual(
                financial_answer_slots.ratio_component_consolidation_scope(calculation_result, operands),
                "",
            )
        self.assertEqual(
            [event for event in events if event[0] in {"scope-str", "normalize"}],
            [
                ("scope-str", "group-first"),
                ("normalize", " consolidated "),
                ("scope-str", "group-duplicate"),
                ("normalize", "consolidated"),
                ("scope-str", "group-invalid"),
                ("normalize", "unknown"),
                ("scope-str", "group-conflict"),
                ("normalize", " separate "),
                ("scope-str", "operand-duplicate"),
                ("normalize", "separate"),
                ("scope-str", "operand-invalid"),
                ("normalize", "mixed"),
            ],
        )
        self.assertIn(("group-iter",), events)
        self.assertEqual(calculation_result["answer_slots"]["components_by_group"], groups)
        self.assertIs(calculation_result["answer_slots"]["components_by_group"], groups)
        self.assertEqual(operands[0]["consolidation_scope"].name, "operand-duplicate")

        class SourceAnswerSlots(dict):
            def get(self, key, default=None):
                if key == "components_by_group":
                    raise AssertionError("components read from the source answer-slots mapping")
                return super().get(key, default)

        copied_answer_slots = SourceAnswerSlots(
            components_by_group={"numerator": [{"consolidation_scope": "consolidated"}]}
        )
        self.assertEqual(
            financial_answer_slots.ratio_component_consolidation_scope({"answer_slots": copied_answer_slots}),
            "consolidated",
        )

        unique_result = {
            "answer_slots": {
                "components_by_group": {
                    "numerator": [
                        {"consolidation_scope": " consolidated "},
                        {"consolidation_scope": "consolidated"},
                    ],
                    "denominator": [None, {}],
                }
            }
        }
        unique_before = deepcopy(unique_result)
        self.assertEqual(
            financial_answer_slots.ratio_component_consolidation_scope(
                unique_result,
                [{"consolidation_scope": "invalid"}, {"consolidation_scope": "consolidated"}],
            ),
            "consolidated",
        )
        self.assertEqual(unique_result, unique_before)
        self.assertEqual(financial_answer_slots.ratio_component_consolidation_scope({}, None), "")

        class LaterEntryBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("later entry accessed after normalization exception")

        with patch.object(
            financial_answer_slots,
            "_normalise_spaces",
            side_effect=RuntimeError("scope normalization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "scope normalization failed"):
                financial_answer_slots.ratio_component_consolidation_scope(
                    {
                        "answer_slots": {
                            "components_by_group": {
                                "first": [{"consolidation_scope": "consolidated"}, LaterEntryBomb()],
                            }
                        }
                    },
                    [{"consolidation_scope": "separate"}],
                )

    def test_ratio_component_collapse_preserves_identity_sources_float_fallback_and_material_gate(self) -> None:
        events = []
        nested = {"preserve": True}

        class Numeric:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __float__(self):
                events.append(("float", self.name))
                return self.value

        numerator = {
            "tag": "numerator",
            "label": "target",
            "raw_value": "12.5",
            "raw_unit": "%",
            "normalized_value": Numeric("numerator", 12.5),
            "source_row_id": "row:a",
            "source_row_ids": ["row:b"],
            "nested": nested,
        }
        denominator = {
            **numerator,
            "tag": "denominator",
            "normalized_value": Numeric("denominator", 12.5),
        }
        calculation_result = {
            "answer_slots": {
                "components_by_group": {
                    "numerator": [numerator, "ignored"],
                    "denominator": [denominator, None],
                }
            }
        }

        def material(slot):
            events.append(("material", slot["tag"], slot is numerator, slot is denominator))
            self.assertIs(slot["nested"], nested)
            return True

        def clean_source_ids(values):
            events.append(("source-ids", values[0], values[1]))
            return ["row:a", "row:b"]

        def normalize(value):
            events.append(("normalize", value))
            return value.strip()

        with (
            patch.object(financial_answer_slots, "answer_slot_has_material", side_effect=material),
            patch.object(financial_answer_slots, "_clean_source_row_ids", side_effect=clean_source_ids),
            patch.object(financial_answer_slots, "_normalise_spaces", side_effect=normalize),
        ):
            self.assertTrue(financial_answer_slots.ratio_components_collapse_to_same_slot(calculation_result))
        self.assertEqual(
            events,
            [
                ("material", "numerator", False, False),
                ("source-ids", "row:a", ["row:b"]),
                ("float", "numerator"),
                ("normalize", "target"),
                ("normalize", "12.5"),
                ("normalize", "%"),
                ("material", "denominator", False, False),
                ("source-ids", "row:a", ["row:b"]),
                ("float", "denominator"),
                ("normalize", "target"),
                ("normalize", "12.5"),
                ("normalize", "%"),
            ],
        )
        self.assertIs(numerator["nested"], nested)
        self.assertIs(denominator["nested"], nested)
        self.assertNotIn("status", numerator)
        self.assertNotIn("status", denominator)

        copy_events = []

        class TrackingDictMeta(type):
            def __instancecheck__(cls, instance):
                return isinstance(instance, builtins.dict)

        class TrackingDict(builtins.dict, metaclass=TrackingDictMeta):
            def __new__(cls, value=(), *args, **kwargs):
                copied = builtins.dict(value, *args, **kwargs)
                copy_events.append(("copy", copied.get("tag", "container")))
                return copied

        copied_order_result = {
            "answer_slots": {
                "tag": "answer-slots",
                "components_by_group": {
                    "tag": "groups",
                    "numerator": [
                        {"tag": "n1", "normalized_value": 1},
                        {"tag": "n2", "normalized_value": 2},
                    ],
                    "denominator": [
                        {"tag": "d1", "normalized_value": 3},
                        {"tag": "d2", "normalized_value": 4},
                    ],
                },
            }
        }

        def copied_material(slot):
            copy_events.append(("material", slot["tag"]))
            self.assertIsNot(
                slot,
                next(
                    original
                    for group in ("numerator", "denominator")
                    for original in copied_order_result["answer_slots"]["components_by_group"][group]
                    if original["tag"] == slot["tag"]
                ),
            )
            return False

        with (
            patch.object(financial_answer_slots, "dict", TrackingDict, create=True),
            patch.object(financial_answer_slots, "answer_slot_has_material", side_effect=copied_material),
        ):
            self.assertFalse(financial_answer_slots.ratio_components_collapse_to_same_slot(copied_order_result))
        self.assertEqual(
            copy_events,
            [
                ("copy", "answer-slots"),
                ("copy", "groups"),
                ("copy", "n1"),
                ("copy", "n2"),
                ("copy", "d1"),
                ("copy", "d2"),
                ("material", "n1"),
                ("material", "n2"),
                ("material", "d1"),
                ("material", "d2"),
            ],
        )

        def result_for(numerator_slot, denominator_slot):
            return {
                "answer_slots": {
                    "components_by_group": {
                        "numerator": [numerator_slot],
                        "denominator": [denominator_slot],
                    }
                }
            }

        common = {
            "raw_value": "10",
            "raw_unit": "KRW",
            "normalized_value": 10,
            "source_row_id": "row:shared",
        }
        label_only_difference = result_for(
            {**common, "label": "numerator"},
            {**common, "label": "denominator"},
        )
        label_difference_before = deepcopy(label_only_difference)
        self.assertTrue(financial_answer_slots.ratio_components_collapse_to_same_slot(label_only_difference))
        self.assertEqual(label_only_difference, label_difference_before)
        self.assertFalse(
            financial_answer_slots.ratio_components_collapse_to_same_slot(
                result_for(
                    {**common, "label": "numerator", "source_row_id": "row:a"},
                    {**common, "label": "denominator", "source_row_id": "row:b"},
                )
            )
        )
        self.assertTrue(
            financial_answer_slots.ratio_components_collapse_to_same_slot(
                result_for(
                    {
                        "label": "rounded",
                        "raw_value": "same",
                        "raw_unit": "unit",
                        "normalized_value": 1.0000001,
                    },
                    {
                        "label": "rounded",
                        "raw_value": "same",
                        "raw_unit": "unit",
                        "normalized_value": 1.0000002,
                    },
                )
            )
        )
        self.assertFalse(
            financial_answer_slots.ratio_components_collapse_to_same_slot(
                result_for(
                    {**common, "label": "numerator", "source_row_id": ""},
                    {**common, "label": "denominator", "source_row_id": ""},
                )
            )
        )

        class FallbackValue:
            def __init__(self, name):
                self.name = name

            def __float__(self):
                events.append(("fallback-float", self.name))
                raise TypeError("not numeric")

            def __bool__(self):
                events.append(("fallback-bool", self.name))
                return True

            def __str__(self):
                events.append(("fallback-str", self.name))
                return " raw normalized "

        events.clear()
        fallback_result = result_for(
            {"label": "same", "normalized_value": FallbackValue("numerator")},
            {"label": "same", "normalized_value": FallbackValue("denominator")},
        )
        self.assertTrue(financial_answer_slots.ratio_components_collapse_to_same_slot(fallback_result))
        self.assertEqual(
            [event for event in events if event[0].startswith("fallback-")],
            [
                ("fallback-float", "numerator"),
                ("fallback-bool", "numerator"),
                ("fallback-str", "numerator"),
                ("fallback-float", "denominator"),
                ("fallback-bool", "denominator"),
                ("fallback-str", "denominator"),
            ],
        )

        class ValueFallback:
            def __float__(self):
                raise ValueError("not numeric")

            def __bool__(self):
                return True

            def __str__(self):
                return "same fallback"

        self.assertTrue(
            financial_answer_slots.ratio_components_collapse_to_same_slot(
                result_for(
                    {"label": "same", "normalized_value": ValueFallback()},
                    {"label": "same", "normalized_value": ValueFallback()},
                )
            )
        )

        class IdentityBomb:
            def __float__(self):
                raise AssertionError("identity built for a non-material slot")

            def __str__(self):
                raise AssertionError("identity stringified for a non-material slot")

        skipped = result_for(
            {"tag": "skip-a", "normalized_value": IdentityBomb()},
            {"tag": "skip-b", "normalized_value": IdentityBomb()},
        )
        with patch.object(financial_answer_slots, "answer_slot_has_material", return_value=False) as predicate:
            self.assertFalse(financial_answer_slots.ratio_components_collapse_to_same_slot(skipped))
        self.assertEqual(predicate.call_count, 2)

        with patch.object(financial_answer_slots, "answer_slot_has_material") as one_side_predicate:
            self.assertFalse(
                financial_answer_slots.ratio_components_collapse_to_same_slot(
                    result_for({"normalized_value": 1}, None)
                )
            )
        one_side_predicate.assert_not_called()

        stopped_source_ids = Mock()
        with (
            patch.object(
                financial_answer_slots,
                "answer_slot_has_material",
                side_effect=RuntimeError("material predicate failed"),
            ) as failed_material,
            patch.object(financial_answer_slots, "_clean_source_row_ids", stopped_source_ids),
        ):
            with self.assertRaisesRegex(RuntimeError, "material predicate failed"):
                financial_answer_slots.ratio_components_collapse_to_same_slot(
                    {
                        "answer_slots": {
                            "components_by_group": {
                                "numerator": [
                                    {"tag": "first", "normalized_value": 1},
                                    {"tag": "later", "normalized_value": 2},
                                ],
                                "denominator": [{"tag": "denominator", "normalized_value": 3}],
                            }
                        }
                    }
                )
        self.assertEqual(failed_material.call_count, 1)
        stopped_source_ids.assert_not_called()

        class RuntimeFloatBomb:
            def __float__(self):
                raise RuntimeError("float conversion escaped")

        with self.assertRaisesRegex(RuntimeError, "float conversion escaped"):
            financial_answer_slots.ratio_components_collapse_to_same_slot(
                result_for(
                    {"label": "same", "normalized_value": RuntimeFloatBomb()},
                    {"label": "same", "normalized_value": 1},
                )
            )

        later_float = Mock(side_effect=AssertionError("normalized value read after source failure"))

        class LaterFloat:
            def __float__(self):
                return later_float()

        with (
            patch.object(financial_answer_slots, "answer_slot_has_material", return_value=True),
            patch.object(
                financial_answer_slots,
                "_clean_source_row_ids",
                side_effect=RuntimeError("source ids failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "source ids failed"):
                financial_answer_slots.ratio_components_collapse_to_same_slot(
                    result_for(
                        {"label": "same", "normalized_value": LaterFloat()},
                        {"label": "same", "normalized_value": 1},
                    )
                )
        later_float.assert_not_called()

    def test_ratio_component_completeness_preserves_collapse_first_value_precedence_and_laziness(self) -> None:
        events = []

        class Value:
            def __init__(self, name, *, truth, text):
                self.name = name
                self.truth = truth
                self.text = text

            def __bool__(self):
                events.append(("bool", self.name))
                return self.truth

            def __str__(self):
                events.append(("str", self.name))
                return self.text

        class AccessBomb:
            def __bool__(self):
                raise AssertionError("lazy fallback value accessed")

            def __str__(self):
                raise AssertionError("lazy fallback value stringified")

        def result_for(numerators, denominators):
            return {
                "answer_slots": {
                    "components_by_group": {
                        "numerator": numerators,
                        "denominator": denominators,
                    }
                }
            }

        collapse_first = result_for(
            [{"rendered_value": AccessBomb()}],
            [{"rendered_value": AccessBomb()}],
        )
        with patch.object(financial_answer_slots, "ratio_components_collapse_to_same_slot", return_value=True) as collapse:
            self.assertFalse(financial_answer_slots.ratio_components_are_complete(collapse_first))
        collapse.assert_called_once_with(collapse_first)

        copy_events = []

        class TrackingDictMeta(type):
            def __instancecheck__(cls, instance):
                return isinstance(instance, builtins.dict)

        class TrackingDict(builtins.dict, metaclass=TrackingDictMeta):
            def __new__(cls, value=(), *args, **kwargs):
                copied = builtins.dict(value, *args, **kwargs)
                copy_events.append(("copy", copied.get("tag", "container")))
                return copied

        copy_order_result = {
            "answer_slots": {
                "tag": "answer-slots",
                "components_by_group": {
                    "tag": "groups",
                    "numerator": [{"tag": "n1"}, {"tag": "n2"}],
                    "denominator": [{"tag": "d1"}, {"tag": "d2"}],
                },
            }
        }

        def collapse_after_copies(value):
            self.assertIs(value, copy_order_result)
            copy_events.append(("collapse",))
            return True

        with (
            patch.object(financial_answer_slots, "dict", TrackingDict, create=True),
            patch.object(
                financial_answer_slots,
                "ratio_components_collapse_to_same_slot",
                side_effect=collapse_after_copies,
            ),
        ):
            self.assertFalse(financial_answer_slots.ratio_components_are_complete(copy_order_result))
        self.assertEqual(
            copy_events,
            [
                ("copy", "answer-slots"),
                ("copy", "groups"),
                ("copy", "n1"),
                ("copy", "n2"),
                ("copy", "d1"),
                ("copy", "d2"),
                ("collapse",),
            ],
        )

        events.clear()
        precedence_result = result_for(
            [
                {
                    "rendered_value": Value("numerator-rendered", truth=True, text=" 10 "),
                    "raw_value": AccessBomb(),
                    "normalized_value": AccessBomb(),
                },
                {"rendered_value": AccessBomb()},
            ],
            [
                {
                    "rendered_value": Value("denominator-rendered", truth=False, text="unused"),
                    "raw_value": Value("denominator-raw", truth=True, text=" 20 "),
                    "normalized_value": AccessBomb(),
                },
                {"rendered_value": AccessBomb()},
            ],
        )
        original_groups = precedence_result["answer_slots"]["components_by_group"]
        original_numerators = list(original_groups["numerator"])
        original_denominators = list(original_groups["denominator"])
        seen_calculation_results = []

        def collapse_false(value):
            seen_calculation_results.append(value)
            return False

        with (
            patch.object(
                financial_answer_slots,
                "ratio_components_collapse_to_same_slot",
                side_effect=collapse_false,
            ),
            patch.object(
                financial_answer_slots,
                "_normalise_spaces",
                side_effect=lambda value: events.append(("normalize", value)) or value.strip(),
            ),
        ):
            self.assertTrue(financial_answer_slots.ratio_components_are_complete(precedence_result))
        self.assertEqual(
            events,
            [
                ("bool", "numerator-rendered"),
                ("str", "numerator-rendered"),
                ("normalize", " 10 "),
                ("bool", "denominator-rendered"),
                ("bool", "denominator-raw"),
                ("str", "denominator-raw"),
                ("normalize", " 20 "),
            ],
        )
        self.assertEqual(seen_calculation_results, [precedence_result])
        self.assertIs(seen_calculation_results[0], precedence_result)
        self.assertIs(precedence_result["answer_slots"]["components_by_group"], original_groups)
        self.assertEqual(original_groups["numerator"], original_numerators)
        self.assertEqual(original_groups["denominator"], original_denominators)
        for current, original_slot in zip(original_groups["numerator"], original_numerators):
            self.assertIs(current, original_slot)
        for current, original_slot in zip(original_groups["denominator"], original_denominators):
            self.assertIs(current, original_slot)

        whitespace_rendered = result_for(
            [{"rendered_value": "   ", "raw_value": AccessBomb()}],
            [{"rendered_value": "10"}],
        )
        with patch.object(financial_answer_slots, "ratio_components_collapse_to_same_slot", return_value=False):
            self.assertFalse(financial_answer_slots.ratio_components_are_complete(whitespace_rendered))

        denominator_bomb = AccessBomb()
        zero_numerator = result_for(
            [{"rendered_value": "", "raw_value": "", "normalized_value": 0}],
            [{"rendered_value": denominator_bomb}],
        )
        with patch.object(financial_answer_slots, "ratio_components_collapse_to_same_slot", return_value=False):
            self.assertFalse(financial_answer_slots.ratio_components_are_complete(zero_numerator))

        normalized_fallback = result_for(
            [{"rendered_value": "", "raw_value": "", "normalized_value": 2}],
            [{"rendered_value": "", "raw_value": "", "normalized_value": 3}],
        )
        with patch.object(financial_answer_slots, "ratio_components_collapse_to_same_slot", return_value=False):
            self.assertTrue(financial_answer_slots.ratio_components_are_complete(normalized_fallback))

        events.clear()
        exception_result = result_for(
            [{"rendered_value": Value("never-read", truth=True, text="10")}],
            [{"rendered_value": "20"}],
        )
        with patch.object(
            financial_answer_slots,
            "ratio_components_collapse_to_same_slot",
            side_effect=RuntimeError("collapse failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "collapse failed"):
                financial_answer_slots.ratio_components_are_complete(exception_result)
        self.assertEqual(events, [])

        with (
            patch.object(financial_answer_slots, "ratio_components_collapse_to_same_slot", return_value=False),
            patch.object(
                financial_answer_slots,
                "_normalise_spaces",
                side_effect=RuntimeError("value normalization failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "value normalization failed"):
                financial_answer_slots.ratio_components_are_complete(
                    result_for([{"rendered_value": "10"}], [{"rendered_value": AccessBomb()}])
                )

    def test_ratio_readiness_callers_preserve_all_external_bindings_gates_adoption_and_stop(self) -> None:
        helper_names = {
            "ratio_component_consolidation_scope",
            "ratio_components_collapse_to_same_slot",
            "ratio_components_are_complete",
        }
        source = inspect.getsource(financial_graph_calculation)
        tree = ast.parse(source)
        parents = {}
        for node in ast.walk(tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node

        def containing_function(node):
            current = node
            while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                current = parents.get(current)
            return current

        calls = []
        for node in ast.walk(tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "financial_answer_slots"
                and node.func.attr in helper_names
            ):
                continue
            function = containing_function(node)
            calls.append(
                (
                    function.name,
                    node.func.attr,
                    tuple(ast.unparse(argument) for argument in node.args),
                    tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                    node,
                )
            )

        aggregate_tree = ast.parse(inspect.getsource(financial_aggregate_projection))
        for node in ast.walk(aggregate_tree):
            for child in ast.iter_child_nodes(node):
                parents[child] = node
        for node in ast.walk(aggregate_tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id in helper_names
            ):
                continue
            function = containing_function(node)
            calls.append(
                (
                    function.name,
                    node.func.id,
                    tuple(ast.unparse(argument) for argument in node.args),
                    tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                    node,
                )
            )

        owner_source = inspect.getsource(financial_answer_slots)
        owner_tree = ast.parse(owner_source)
        owner_parents = {}
        for node in ast.walk(owner_tree):
            for child in ast.iter_child_nodes(node):
                owner_parents[child] = node
        internal = []
        for node in ast.walk(owner_tree):
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "ratio_components_collapse_to_same_slot"
            ):
                continue
            current = node
            while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                current = owner_parents.get(current)
            if current is not None and current.name == "ratio_components_are_complete":
                internal.append(
                    (
                        current.name,
                        node.func.id,
                        tuple(ast.unparse(argument) for argument in node.args),
                        tuple((keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords),
                    )
                )
        self.assertEqual(
            internal,
            [
                (
                    "ratio_components_are_complete",
                    "ratio_components_collapse_to_same_slot",
                    ("calculation_result",),
                    (),
                )
            ],
        )
        external = calls
        expected_external = Counter(
            {
                (
                    "_compact_ratio_answer",
                    "ratio_component_consolidation_scope",
                    ("calculation_result", "resolved_calculation_operands"),
                    (),
                ): 1,
                (
                    "_render_calculation_answer",
                    "ratio_component_consolidation_scope",
                    ("calculation_result", "operands"),
                    (),
                ): 1,
                (
                    "_verify_calculation_answer",
                    "ratio_component_consolidation_scope",
                    ("calculation_result", "operands"),
                    (),
                ): 1,
                (
                    "_apply_runtime_ratio_projection_for_collapsed_rows",
                    "ratio_components_collapse_to_same_slot",
                    ("dict(row.get('calculation_result') or {})",),
                    (),
                ): 1,
                (
                    "_preferred_complete_numeric_answer",
                    "ratio_components_are_complete",
                    ("calculation_result",),
                    (),
                ): 2,
                (
                    "_numeric_projection_coverage_targets",
                    "ratio_components_are_complete",
                    ("calculation_result",),
                    (),
                ): 1,
                (
                    "_compact_ratio_answer_from_projection",
                    "ratio_components_are_complete",
                    ("result",),
                    (),
                ): 1,
                (
                    "_apply_ratio_projection_answer_if_rendered_missing",
                    "ratio_components_are_complete",
                    ("projection_result",),
                    (),
                ): 1,
                (
                    "_apply_runtime_ratio_projection_for_collapsed_rows",
                    "ratio_components_are_complete",
                    ("runtime_result",),
                    (),
                ): 1,
                (
                    "_late_runtime_numeric_answer",
                    "ratio_components_are_complete",
                    ("calculation_result",),
                    (),
                ): 1,
                (
                    "retrieved_ratio_projection_conflicts_with_existing_complete_result",
                    "ratio_components_are_complete",
                    ("calculation_result",),
                    (),
                ): 1,
                (
                    "_render_calculation_answer",
                    "ratio_components_are_complete",
                    ("calculation_result",),
                    (),
                ): 1,
                (
                    "_verify_calculation_answer",
                    "ratio_components_are_complete",
                    ("calculation_result",),
                    (),
                ): 1,
                (
                    "_append_ratio_result_from_retrieved_context",
                    "ratio_components_are_complete",
                    ("dict(row.get('calculation_result') or {})",),
                    (),
                ): 1,
            }
        )
        self.assertEqual(
            Counter((row[0], row[1], row[2], row[3]) for row in external),
            expected_external,
        )
        self.assertEqual(len(external), 15)
        self.assertEqual(
            Counter(row[1] for row in external),
            Counter(
                {
                    "ratio_component_consolidation_scope": 3,
                    "ratio_components_collapse_to_same_slot": 1,
                    "ratio_components_are_complete": 11,
                }
            ),
        )

        negative_complete_callers = {
            "_compact_ratio_answer_from_projection",
            "_apply_ratio_projection_answer_if_rendered_missing",
            "_apply_runtime_ratio_projection_for_collapsed_rows",
            "retrieved_ratio_projection_conflicts_with_existing_complete_result",
        }

        def has_not_ancestor(call):
            current = call
            while current is not None and not isinstance(current, ast.stmt):
                current = parents.get(current)
                if isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.Not):
                    return True
            return False

        for function_name, helper_name, _args, _kwargs, call in external:
            expected_negative = (
                helper_name == "ratio_components_are_complete"
                and function_name in negative_complete_callers
            )
            self.assertEqual(
                has_not_ancestor(call),
                expected_negative,
                (function_name, helper_name),
            )

        render_verify_order = {
            function_name: [
                (helper_name, call.lineno)
                for current_function, helper_name, _args, _kwargs, call in external
                if current_function == function_name
                and helper_name
                in {"ratio_components_are_complete", "ratio_component_consolidation_scope"}
            ]
            for function_name in ("_render_calculation_answer", "_verify_calculation_answer")
        }
        for function_name, ordered_calls in render_verify_order.items():
            self.assertEqual(
                [name for name, _line in sorted(ordered_calls, key=lambda item: item[1])],
                ["ratio_components_are_complete", "ratio_component_consolidation_scope"],
                function_name,
            )

        try_boundaries = []
        for function_name, helper_name, _args, _kwargs, call in external:
            current = call
            while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                current = parents.get(current)
                if isinstance(current, ast.Try):
                    try_boundaries.append((function_name, helper_name))
                    break
        self.assertEqual(
            Counter(try_boundaries),
            Counter(
                {
                    ("_verify_calculation_answer", "ratio_components_are_complete"): 1,
                    ("_verify_calculation_answer", "ratio_component_consolidation_scope"): 1,
                }
            ),
        )

        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        nested = {"preserve": True}
        operand = {"operand_id": "prepared", "nested": nested}
        scope_result = {
            "answer_slots": {
                "metric_label": "target ratio",
                "primary_value": {"rendered_value": "10%"},
            },
            "nested": nested,
        }

        def scope_owner(calculation_result, operands):
            self.assertIs(calculation_result, scope_result)
            self.assertEqual(operands, [operand])
            self.assertIsNot(operands[0], operand)
            self.assertIs(operands[0]["nested"], nested)
            return "consolidated"

        with (
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "synchronize_ratio_result_display",
                return_value=SimpleNamespace(calculation_result=scope_result),
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_component_consolidation_scope",
                side_effect=scope_owner,
            ) as scope_mock,
            patch.dict(
                financial_graph_calculation.CALCULATION_RENDER_POLICY,
                {
                    "consolidation_scope_answer_prefixes": {"consolidated": "[scope] "},
                    "ratio_answer_template": "{period_prefix}{metric_label} {rendered_value}",
                },
            ),
        ):
            self.assertEqual(
                agent._compact_ratio_answer(
                    {},
                    scope_result,
                    calculation_operands=[operand],
                ),
                "[scope] target ratio 10%",
            )
        self.assertEqual(scope_mock.call_count, 1)

        stopped_display = Mock()
        with (
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "synchronize_ratio_result_display",
                return_value=SimpleNamespace(calculation_result=scope_result),
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_component_consolidation_scope",
                side_effect=RuntimeError("scope owner failed"),
            ),
            patch.object(financial_graph_calculation, "display_operand_label", stopped_display),
        ):
            with self.assertRaisesRegex(RuntimeError, "scope owner failed"):
                agent._compact_ratio_answer({}, scope_result, calculation_operands=[operand])
        stopped_display.assert_not_called()

        projection_result = {
            "answer_slots": {"operation_family": "ratio", "metric_label": "target ratio"},
            "nested": nested,
        }
        projection = {
            "calculation_result": projection_result,
            "calculation_plan": {"operation": "ratio"},
            "calculation_operands": [operand],
        }

        def complete_owner(prepared_result):
            self.assertEqual(prepared_result, projection_result)
            self.assertIsNot(prepared_result, projection_result)
            self.assertIs(prepared_result["nested"], nested)
            return True

        with (
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                side_effect=complete_owner,
            ) as complete_mock,
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                return_value=1,
            ) as coherence_mock,
            patch.object(agent, "_compact_ratio_answer", return_value=" adopted ratio ") as compact_mock,
        ):
            self.assertEqual(agent._compact_ratio_answer_from_projection({}, projection), "adopted ratio")
        self.assertEqual(complete_mock.call_count, 1)
        self.assertEqual(
            coherence_mock.call_args.kwargs,
            {
                "operation_family": "ratio",
                "operands": [operand],
                "calculation_result": projection_result,
                "ordered_results": [],
            },
        )
        self.assertIsNot(coherence_mock.call_args.kwargs["operands"], projection["calculation_operands"])
        self.assertIs(coherence_mock.call_args.kwargs["operands"][0], operand)
        self.assertEqual(compact_mock.call_count, 1)

        stopped_coherence = Mock()
        with (
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                side_effect=RuntimeError("complete owner failed"),
            ),
            patch.object(
                financial_graph_calculation,
                "aggregate_dependency_slot_coherence_rank_for_operands",
                stopped_coherence,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "complete owner failed"):
                agent._compact_ratio_answer_from_projection({}, projection)
        stopped_coherence.assert_not_called()

        row_result = {"answer_slots": {"operation_family": "ratio"}, "nested": nested}
        runtime_result = {"answer_slots": {"operation_family": "ratio"}, "nested": nested}
        runtime_trace = {
            "calculation_result": runtime_result,
            "calculation_plan": {"operation": "ratio"},
            "calculation_operands": [operand],
        }
        row = {"calculation_result": row_result}
        aggregate_projection = {"preserve": True}

        def collapse_owner(prepared_result):
            self.assertEqual(prepared_result, row_result)
            self.assertIsNot(prepared_result, row_result)
            self.assertIs(prepared_result["nested"], nested)
            return True

        with (
            patch.object(
                financial_graph_calculation,
                "resolve_runtime_calculation_trace",
                return_value=runtime_trace,
            ),
            patch.object(agent, "_aggregate_result_operation_family", return_value="ratio"),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_collapse_to_same_slot",
                side_effect=collapse_owner,
            ) as collapse_mock,
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                return_value=False,
            ) as runtime_complete_mock,
            patch.object(
                financial_graph_calculation.calculation_rendering,
                "ratio_query_requests_absolute_magnitude",
            ) as stopped_absolute,
        ):
            projected, answer = agent._apply_runtime_ratio_projection_for_collapsed_rows(
                {}, aggregate_projection, [row], "old answer"
            )
        self.assertIs(projected, aggregate_projection)
        self.assertEqual(answer, "old answer")
        self.assertEqual(collapse_mock.call_count, 1)
        runtime_complete_mock.assert_called_once()
        self.assertEqual(runtime_complete_mock.call_args.args[0], runtime_result)
        self.assertIsNot(runtime_complete_mock.call_args.args[0], runtime_result)
        self.assertIs(runtime_complete_mock.call_args.args[0]["nested"], nested)
        stopped_absolute.assert_not_called()

        stopped_complete = Mock()
        with (
            patch.object(
                financial_graph_calculation,
                "resolve_runtime_calculation_trace",
                return_value=runtime_trace,
            ),
            patch.object(agent, "_aggregate_result_operation_family", return_value="ratio"),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_collapse_to_same_slot",
                side_effect=RuntimeError("collapse owner failed"),
            ),
            patch.object(
                financial_graph_calculation.financial_answer_slots,
                "ratio_components_are_complete",
                stopped_complete,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "collapse owner failed"):
                agent._apply_runtime_ratio_projection_for_collapsed_rows(
                    {}, aggregate_projection, [row], "old answer"
                )
        stopped_complete.assert_not_called()
