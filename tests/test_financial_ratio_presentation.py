import ast
import inspect
import unittest
from collections import Counter
from collections.abc import Mapping
from unittest.mock import Mock, patch

from src.agent import (
    financial_graph_calculation,
    financial_graph_calculation_rendering as calculation_rendering,
    financial_graph_helpers,
    financial_graph_planning,
)


class FinancialRatioPresentationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.agent = financial_graph_calculation.FinancialAgentCalculationMixin()

    def test_infer_ratio_unit_preserves_policy_copy_marker_order_and_exceptions(self) -> None:
        infer = calculation_rendering.infer_concept_ratio_result_unit
        events = []

        class FormatBomb:
            def __format__(self, _spec):
                raise AssertionError("query or label formatted for a non-ratio operation")

        class PolicyBomb(Mapping):
            def __iter__(self):
                raise AssertionError("policy copied for a non-ratio operation")

            def __len__(self):
                raise AssertionError("policy sized for a non-ratio operation")

            def __getitem__(self, _key):
                raise AssertionError("policy read for a non-ratio operation")

        with (
            patch.object(
                calculation_rendering,
                "_normalise_spaces",
                side_effect=lambda value: events.append(("normalize", value)) or "lookup",
            ),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", PolicyBomb()),
        ):
            self.assertEqual(infer(FormatBomb(), FormatBomb(), " lookup "), "")
        self.assertEqual(events, [("normalize", " lookup ")])

        class Formatted:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __format__(self, spec):
                events.append(("format", self.name, spec))
                return self.value

        class Marker:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(("marker-str", self.name))
                return self.value

        class LoggedText(str):
            def __contains__(self, item):
                events.append(("contains", item))
                return super().__contains__(item)

        class CopiedPolicy(Mapping):
            def __init__(self, values):
                self.values = values

            def __iter__(self):
                events.append(("policy-iter",))
                return iter(self.values)

            def __len__(self):
                events.append(("policy-len",))
                return len(self.values)

            def __getitem__(self, key):
                events.append(("policy-item", key))
                return self.values[key]

            def get(self, _key, _default=None):
                raise AssertionError("source policy used instead of a copied dict")

        values = {
            "multiplier_markers": (Marker("times", "times"), Marker("blank", "")),
            "percent_markers": (Marker("percent", "%"),),
            "multiplier_unit": "x",
            "percent_unit": "%",
        }
        policy = CopiedPolicy(values)
        before = dict(values)

        def normalize(value):
            events.append(("normalize", value))
            normalized = " ".join(str(value).split())
            return LoggedText(normalized)

        events.clear()
        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
        ):
            self.assertEqual(
                infer(Formatted("query", "coverage times"), Formatted("label", "ratio"), " ratio "),
                "x",
            )
        self.assertEqual(values.keys(), before.keys())
        for key, value in before.items():
            self.assertIs(values[key], value)
        self.assertEqual(
            [event for event in events if event[0] == "format"],
            [("format", "query", ""), ("format", "label", "")],
        )
        self.assertLess(events.index(("normalize", " ratio ")), events.index(("format", "query", "")))
        self.assertLess(events.index(("format", "query", "")), events.index(("format", "label", "")))
        self.assertLess(events.index(("format", "label", "")), events.index(("normalize", "coverage times ratio")))
        self.assertLess(events.index(("normalize", "coverage times ratio")), events.index(("policy-iter",)))
        self.assertEqual(
            [event for event in events if event[0] == "marker-str"],
            [
                ("marker-str", "times"),
                ("marker-str", "times"),
                ("marker-str", "blank"),
                ("marker-str", "percent"),
                ("marker-str", "percent"),
            ],
        )
        first_contains = next(index for index, event in enumerate(events) if event[0] == "contains")
        self.assertTrue(all(event[0] != "contains" for event in events[:first_contains]))
        self.assertEqual(
            [event for event in events if event[0] == "contains"],
            [("contains", "times"), ("contains", "%")],
        )

        class UnitBomb:
            def __bool__(self):
                raise AssertionError("multiplier unit truth-tested on percent override")

            def __str__(self):
                raise AssertionError("multiplier unit stringified on percent override")

            def __deepcopy__(self, _memo):
                return self

        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                {
                    "multiplier_markers": ("times",),
                    "percent_markers": ("%",),
                    "multiplier_unit": UnitBomb(),
                    "percent_unit": "%",
                },
            ),
        ):
            self.assertEqual(infer("coverage times %", "ratio", "ratio"), "%")

        class PercentUnitBomb:
            def __bool__(self):
                raise AssertionError("percent unit truth-tested after multiplier win")

            def __str__(self):
                raise AssertionError("percent unit stringified after multiplier win")

        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                {
                    "multiplier_markers": ("times",),
                    "percent_markers": ("%",),
                    "multiplier_unit": "x",
                    "percent_unit": PercentUnitBomb(),
                },
            ),
        ):
            self.assertEqual(infer("coverage times", "ratio", "ratio"), "x")

        events.clear()
        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                {
                    "multiplier_markers": ("times",),
                    "percent_markers": ("%",),
                    "multiplier_unit": "x",
                    "percent_unit": "%",
                },
            ),
        ):
            self.assertEqual(infer("plain ratio", "label", "ratio"), "%")
        self.assertEqual(
            [event for event in events if event[0] == "contains"],
            [("contains", "times")],
        )

        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                {"multiplier_markers": (), "percent_markers": ()},
            ),
        ):
            self.assertEqual(infer("plain ratio", "label", "ratio"), "")

        class PercentUnitFailure:
            def __bool__(self):
                raise RuntimeError("percent unit failed")

        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                {
                    "multiplier_markers": ("times",),
                    "percent_markers": (),
                    "multiplier_unit": "x",
                    "percent_unit": PercentUnitFailure(),
                },
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "percent unit failed"):
                infer("plain ratio", "label", "ratio")

        class MarkerBomb:
            def __str__(self):
                raise RuntimeError("marker string failed")

        class LaterMarker:
            def __str__(self):
                raise AssertionError("percent tuple materialized after multiplier failure")

        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                {
                    "multiplier_markers": (MarkerBomb(),),
                    "percent_markers": (LaterMarker(),),
                },
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "marker string failed"):
                infer("ratio", "label", "ratio")

    def test_absolute_ratio_query_preserves_materialization_laziness_and_exceptions(self) -> None:
        requests_absolute = calculation_rendering.ratio_query_requests_absolute_magnitude
        events = []

        class Query:
            def __init__(self, value, truth=True):
                self.value = value
                self.truth = truth

            def __bool__(self):
                events.append(("query-bool", self.truth))
                return self.truth

            def __str__(self):
                events.append(("query-str", self.value))
                if not self.truth:
                    raise AssertionError("falsy query stringified")
                return self.value

        class Marker:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __bool__(self):
                events.append(("marker-bool", self.name))
                return bool(self.value)

            def __str__(self):
                events.append(("marker-str", self.name))
                return self.value

        class ContainsText(str):
            def __contains__(self, item):
                events.append(("contains", item))
                return super().__contains__(item)

        class Normalized:
            def __init__(self, value):
                self.value = value

            def __bool__(self):
                events.append(("normalized-bool", self.value))
                return bool(self.value)

            def lower(self):
                events.append(("lower", self.value))
                return ContainsText(self.value.lower())

        class Policy(dict):
            def get(self, key, default=None):
                events.append(("policy-get", key))
                return super().get(key, default)

        def normalize(value):
            events.append(("normalize", value))
            return Normalized(" ".join(str(value).split()))

        policy = Policy(
            ratio_absolute_magnitude_markers=(
                Marker("absolute", " ABSOLUTE "),
                Marker("blank", ""),
                Marker("magnitude", "magnitude"),
            )
        )
        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(calculation_rendering, "CALCULATION_RENDER_POLICY", policy),
        ):
            self.assertTrue(requests_absolute(Query("show absolute ratio")))
        self.assertEqual(
            events[:5],
            [
                ("query-bool", True),
                ("query-str", "show absolute ratio"),
                ("normalize", "show absolute ratio"),
                ("lower", "show absolute ratio"),
                ("policy-get", "ratio_absolute_magnitude_markers"),
            ],
        )
        self.assertLess(events.index(("query-str", "show absolute ratio")), events.index(("policy-get", "ratio_absolute_magnitude_markers")))
        marker_events = [event for event in events if event[0] in {"marker-bool", "marker-str"}]
        self.assertEqual(
            marker_events,
            [
                ("marker-bool", "absolute"),
                ("marker-str", "absolute"),
                ("marker-bool", "absolute"),
                ("marker-str", "absolute"),
                ("marker-bool", "blank"),
                ("marker-bool", "magnitude"),
                ("marker-str", "magnitude"),
                ("marker-bool", "magnitude"),
                ("marker-str", "magnitude"),
            ],
        )
        first_contains = next(index for index, event in enumerate(events) if event[0] == "contains")
        last_marker = max(index for index, event in enumerate(events) if event[0] in {"marker-bool", "marker-str"})
        self.assertGreater(first_contains, last_marker)
        self.assertEqual([event for event in events if event[0] == "contains"], [("contains", "absolute")])

        events.clear()
        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(calculation_rendering, "CALCULATION_RENDER_POLICY", policy),
        ):
            self.assertFalse(requests_absolute(Query("ignored", truth=False)))
        self.assertNotIn(("query-str", "ignored"), events)
        self.assertIn(("policy-get", "ratio_absolute_magnitude_markers"), events)
        self.assertTrue(any(event[0] == "marker-str" for event in events))
        self.assertFalse(any(event[0] == "contains" for event in events))

        class PolicyFailure(dict):
            def get(self, _key, _default=None):
                events.append(("policy-failure",))
                raise RuntimeError("policy read failed")

        events.clear()
        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(calculation_rendering, "CALCULATION_RENDER_POLICY", PolicyFailure()),
        ):
            with self.assertRaisesRegex(RuntimeError, "policy read failed"):
                requests_absolute(Query("absolute"))
        self.assertGreater(events.index(("policy-failure",)), events.index(("lower", "absolute")))

        class IterationFailure:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("marker iteration failed")

        with (
            patch.object(calculation_rendering, "_normalise_spaces", side_effect=normalize),
            patch.object(
                calculation_rendering,
                "CALCULATION_RENDER_POLICY",
                {"ratio_absolute_magnitude_markers": IterationFailure()},
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "marker iteration failed"):
                requests_absolute("absolute")

        class ContainsFailure(str):
            def __contains__(self, _item):
                raise RuntimeError("marker containment failed")

        class QueryNormalized:
            def lower(self):
                return ContainsFailure("absolute")

        def contains_failure_normalize(value):
            if value == "absolute":
                return QueryNormalized()
            return Normalized(" ".join(str(value).split()))

        with (
            patch.object(
                calculation_rendering,
                "_normalise_spaces",
                side_effect=contains_failure_normalize,
            ),
            patch.object(
                calculation_rendering,
                "CALCULATION_RENDER_POLICY",
                {"ratio_absolute_magnitude_markers": ("absolute",)},
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "marker containment failed"):
                requests_absolute("absolute")

    def test_ratio_result_projection_preserves_unit_math_magnitude_render_and_exceptions(self) -> None:
        projection = calculation_rendering.ratio_result_projection
        events = []

        class Result(float):
            def __new__(cls, value):
                return super().__new__(cls, value)

            def __lt__(self, other):
                events.append(("negative-check", float(self), other))
                return super().__lt__(other)

            def __mul__(self, other):
                events.append(("multiply", float(self), other))
                return Result(super().__mul__(other))

            def __abs__(self):
                events.append(("absolute", float(self)))
                return abs(float(self))

        class Numerator:
            def __init__(self, quotient):
                self.quotient = quotient

            def __truediv__(self, denominator):
                events.append(("divide", denominator))
                if denominator == 0:
                    raise ZeroDivisionError("division by zero")
                return Result(self.quotient)

        class Policy(dict):
            def get(self, key, default=None):
                events.append(("policy-get", key))
                return super().get(key, default)

        policy = Policy(multiplier_unit="x")

        def infer(query, metric_label, operation_family):
            events.append(("infer", query, metric_label, operation_family))
            return "x"

        def magnitude(query):
            events.append(("magnitude", query))
            return True

        def render(value, unit):
            events.append(("render", value, unit))
            return f"{value}{unit}"

        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", side_effect=infer),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", side_effect=magnitude),
            patch.object(calculation_rendering, "format_ratio_result", side_effect=render),
        ):
            multiplier = projection(
                numerator_value=Numerator(3.5),
                denominator_value=2,
                query="times query",
                metric_label="coverage",
            )
        self.assertEqual(
            multiplier,
            {
                "result_value": 3.5,
                "result_unit": "x",
                "normalized_unit": "COUNT",
                "rendered_value": "3.5x",
            },
        )
        self.assertEqual(
            events,
            [
                ("infer", "times query", "coverage", "ratio"),
                ("policy-get", "multiplier_unit"),
                ("divide", 2),
                ("negative-check", 3.5, 0),
                ("render", 3.5, "x"),
            ],
        )

        events.clear()
        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value="points"),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", side_effect=magnitude),
            patch.object(calculation_rendering, "format_ratio_result", side_effect=render),
        ):
            percent = projection(
                numerator_value=Numerator(0.25),
                denominator_value=4,
                query="percent query",
                metric_label="margin",
            )
        self.assertEqual(percent["result_value"], 25.0)
        self.assertEqual(percent["result_unit"], "%")
        self.assertEqual(percent["normalized_unit"], "PERCENT")
        self.assertEqual(
            events,
            [
                ("policy-get", "multiplier_unit"),
                ("divide", 4),
                ("multiply", 0.25, 100.0),
                ("negative-check", 25.0, 0),
                ("render", 25.0, "%"),
            ],
        )

        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value=""),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", return_value=False),
            patch.object(calculation_rendering, "format_ratio_result", return_value="25%"),
        ):
            fallback_percent = projection(
                numerator_value=1.0,
                denominator_value=4.0,
                query="plain ratio",
                metric_label="margin",
            )
        self.assertEqual(
            fallback_percent,
            {
                "result_value": 25.0,
                "result_unit": "%",
                "normalized_unit": "PERCENT",
                "rendered_value": "25%",
            },
        )

        events.clear()
        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", side_effect=infer),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", side_effect=magnitude),
            patch.object(calculation_rendering, "format_ratio_result", side_effect=render),
        ):
            negative = projection(
                numerator_value=Numerator(-2.0),
                denominator_value=5,
                query="absolute query",
                metric_label="coverage",
            )
        self.assertEqual(negative["result_value"], 2.0)
        self.assertEqual(
            events,
            [
                ("infer", "absolute query", "coverage", "ratio"),
                ("policy-get", "multiplier_unit"),
                ("divide", 5),
                ("negative-check", -2.0, 0),
                ("magnitude", "absolute query"),
                ("absolute", -2.0),
                ("render", 2.0, "x"),
            ],
        )

        render_negative = Mock(return_value="-2x")
        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value="x"),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", return_value=False) as magnitude_false,
            patch.object(calculation_rendering, "format_ratio_result", render_negative),
        ):
            retained_negative = projection(
                numerator_value=-2.0,
                denominator_value=1.0,
                query="signed ratio",
                metric_label="coverage",
            )
        magnitude_false.assert_called_once_with("signed ratio")
        render_negative.assert_called_once_with(-2.0, "x")
        self.assertEqual(retained_negative["result_value"], -2.0)

        render_after_magnitude = Mock(return_value="never")
        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value="x"),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(
                calculation_rendering,
                "ratio_query_requests_absolute_magnitude",
                side_effect=RuntimeError("magnitude failed"),
            ),
            patch.object(
                calculation_rendering,
                "format_ratio_result",
                render_after_magnitude,
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "magnitude failed"):
                projection(numerator_value=-1.0, denominator_value=1.0, query="q", metric_label="m")
        render_after_magnitude.assert_not_called()

        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value="x"),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", return_value=False),
            patch.object(calculation_rendering, "format_ratio_result", return_value="same"),
        ):
            first = projection(numerator_value=2.0, denominator_value=1.0, query="q", metric_label="m")
            second = projection(numerator_value=2.0, denominator_value=1.0, query="q", metric_label="m")
        self.assertEqual(first, second)
        self.assertIsNot(first, second)

        magnitude_owner = Mock(return_value=True)
        render_owner = Mock(return_value="never")
        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value="x"),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", magnitude_owner),
            patch.object(calculation_rendering, "format_ratio_result", render_owner),
        ):
            with self.assertRaises(ZeroDivisionError):
                projection(numerator_value=1.0, denominator_value=0.0, query="q", metric_label="m")
        magnitude_owner.assert_not_called()
        render_owner.assert_not_called()

        with (
            patch.object(calculation_rendering, "infer_concept_ratio_result_unit", return_value="x"),
            patch.object(calculation_rendering, "CONCEPT_RATIO_RESULT_UNIT_POLICY", policy),
            patch.object(calculation_rendering, "ratio_query_requests_absolute_magnitude", return_value=True),
            patch.object(
                calculation_rendering,
                "format_ratio_result",
                side_effect=RuntimeError("render failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "render failed"):
                projection(numerator_value=-1.0, denominator_value=1.0, query="q", metric_label="m")

        class PolicyAccessBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("policy accessed after inference failure")

        with (
            patch.object(
                calculation_rendering,
                "infer_concept_ratio_result_unit",
                side_effect=RuntimeError("inference failed"),
            ),
            patch.object(
                calculation_rendering,
                "CONCEPT_RATIO_RESULT_UNIT_POLICY",
                PolicyAccessBomb(),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "inference failed"):
                projection(numerator_value=1.0, denominator_value=1.0, query="q", metric_label="m")

    def test_ratio_presentation_external_bindings_preserve_args_adoption_and_stop(self) -> None:
        modules = (
            financial_graph_helpers,
            financial_graph_planning,
            financial_graph_calculation,
        )
        trees = {module: ast.parse(inspect.getsource(module)) for module in modules}
        parents = {
            module: {
                child: node
                for node in ast.walk(tree)
                for child in ast.iter_child_nodes(node)
            }
            for module, tree in trees.items()
        }

        def target_name(call):
            if isinstance(call.func, ast.Name):
                return call.func.id
            if isinstance(call.func, ast.Attribute):
                return call.func.attr
            return ""

        def nearest_function(module, node):
            current = node
            while current in parents[module]:
                current = parents[module][current]
                if isinstance(current, ast.FunctionDef):
                    return current
            raise AssertionError("call has no containing function")

        def ancestors_until_function(module, node):
            current = node
            result = []
            while current in parents[module]:
                current = parents[module][current]
                if isinstance(current, ast.FunctionDef):
                    return result, current
                result.append(current)
            raise AssertionError("call has no containing function")

        infer_calls = []
        for module in (financial_graph_helpers, financial_graph_planning):
            for node in ast.walk(trees[module]):
                if isinstance(node, ast.Call) and target_name(node) == "infer_concept_ratio_result_unit":
                    infer_calls.append((module, nearest_function(module, node), node))
        self.assertEqual(
            Counter((module.__name__, function.name) for module, function, _ in infer_calls),
            Counter(
                {
                    (financial_graph_helpers.__name__, "_compose_concept_numeric_task"): 1,
                    (financial_graph_planning.__name__, "_build_llm_concept_numeric_plan"): 1,
                }
            ),
        )
        for module, _function, call in infer_calls:
            self.assertIsInstance(call.func, ast.Name)
            self.assertEqual(
                [ast.unparse(argument) for argument in call.args],
                ["query", "metric_label", "operation_family"],
            )
            self.assertEqual(call.keywords, [])
            ancestors, _ = ancestors_until_function(module, call)
            self.assertFalse(any(isinstance(node, ast.Try) for node in ancestors))
            if module is financial_graph_helpers:
                assignment = next(node for node in ancestors if isinstance(node, ast.Assign))
                self.assertEqual([ast.unparse(target) for target in assignment.targets], ["result_unit"])
            else:
                result_dict = next(node for node in ancestors if isinstance(node, ast.Dict))
                result_unit_values = [
                    value
                    for key, value in zip(result_dict.keys, result_dict.values)
                    if isinstance(key, ast.Constant) and key.value == "result_unit"
                ]
                self.assertEqual(result_unit_values, [call])

        graph_calls = {
            target: [
                node
                for node in ast.walk(trees[financial_graph_calculation])
                if isinstance(node, ast.Call) and target_name(node) == target
            ]
            for target in ("ratio_query_requests_absolute_magnitude", "ratio_result_projection")
        }
        external_absolute = [
            node
            for node in graph_calls["ratio_query_requests_absolute_magnitude"]
        ]
        self.assertEqual(
            Counter(nearest_function(financial_graph_calculation, node).name for node in external_absolute),
            Counter(
                {
                    "_recalculate_row_from_source_slots": 1,
                    "_apply_runtime_ratio_projection_for_collapsed_rows": 1,
                    "_project_prepared_calculation_candidate": 1,
                }
            ),
        )
        self.assertEqual(
            sorted(ast.unparse(node.args[0]) for node in external_absolute),
            ["candidate.query", "str(state.get('query') or '')", "str(state.get('query') or '')"],
        )
        for node in external_absolute:
            self.assertIsInstance(node.func, ast.Attribute)
            self.assertEqual(ast.unparse(node.func.value), "calculation_rendering")
            ancestors, _ = ancestors_until_function(financial_graph_calculation, node)
            self.assertFalse(any(isinstance(item, ast.Try) for item in ancestors))
            conditional = next(item for item in ancestors if isinstance(item, ast.If))
            adopted_call_names = {
                target_name(item)
                for statement in conditional.body
                for item in ast.walk(statement)
                if isinstance(item, ast.Call)
            }
            expected_adoption = {
                "_recalculate_row_from_source_slots": "apply_absolute_ratio_magnitude_if_requested",
                "_apply_runtime_ratio_projection_for_collapsed_rows": "project_runtime_ratio_absolute_magnitude",
                "_project_prepared_calculation_candidate": "abs",
            }[nearest_function(financial_graph_calculation, node).name]
            self.assertIn(expected_adoption, adopted_call_names)

        projection_calls = graph_calls["ratio_result_projection"]
        self.assertEqual(
            Counter(nearest_function(financial_graph_calculation, node).name for node in projection_calls),
            Counter(
                {
                    "_ratio_answer_from_dependency_source_slots": 1,
                    "_append_ratio_result_from_task_outputs": 1,
                    "_append_ratio_result_from_retrieved_context": 1,
                }
            ),
        )
        for node in projection_calls:
            self.assertIsInstance(node.func, ast.Attribute)
            self.assertEqual(ast.unparse(node.func.value), "calculation_rendering")
            self.assertEqual(
                [keyword.arg for keyword in node.keywords],
                ["numerator_value", "denominator_value", "query", "metric_label"],
            )
            function_name = nearest_function(financial_graph_calculation, node).name
            expected_values = {
                "_ratio_answer_from_dependency_source_slots": [
                    "float(numerator_value)",
                    "float(denominator_value)",
                    "query",
                    "metric_label",
                ],
                "_append_ratio_result_from_task_outputs": [
                    "numerator_value",
                    "denominator_value",
                    "str(state.get('query') or '')",
                    "metric_label",
                ],
                "_append_ratio_result_from_retrieved_context": [
                    "numerator_value",
                    "denominator_value",
                    "str(state.get('query') or '')",
                    "metric_label",
                ],
            }[function_name]
            self.assertEqual([ast.unparse(keyword.value) for keyword in node.keywords], expected_values)
            ancestors, function = ancestors_until_function(financial_graph_calculation, node)
            self.assertFalse(any(isinstance(item, ast.Try) for item in ancestors))
            assignment = next(item for item in ancestors if isinstance(item, ast.Assign))
            self.assertEqual([ast.unparse(target) for target in assignment.targets], ["projection"])
            adopted_keys = {
                item.slice.value
                for item in ast.walk(function)
                if isinstance(item, ast.Subscript)
                and isinstance(item.value, ast.Name)
                and item.value.id == "projection"
                and isinstance(item.slice, ast.Constant)
                and isinstance(item.slice.value, str)
                and item.lineno > node.lineno
            }
            self.assertTrue(
                {"result_value", "result_unit", "normalized_unit", "rendered_value"}.issubset(adopted_keys)
            )

        self.assertEqual(len(infer_calls) + len(external_absolute) + len(projection_calls), 8)

        sentinel = object()
        infer_owner = Mock(return_value=sentinel)
        with (
            patch.object(financial_graph_helpers, "infer_statement_and_section_hints", return_value=([], [])),
            patch.object(financial_graph_helpers, "build_concept_task_constraints", return_value={"ready": True}),
            patch.object(financial_graph_helpers, "_build_generic_retrieval_queries", return_value=["retrieval"]),
            patch.object(financial_graph_helpers, "_build_metric_task_query", return_value="task query"),
            patch.object(financial_graph_helpers, "infer_concept_ratio_result_unit", infer_owner),
        ):
            task = financial_graph_helpers._compose_concept_numeric_task(
                query="ratio query",
                report_scope={"year": 2023},
                ontology=object(),
                metric_label="coverage",
                operation_family="ratio",
                operand_specs=[{"label": "value"}],
            )
        infer_owner.assert_called_once_with("ratio query", "coverage", "ratio")
        self.assertIs(task["result_unit"], sentinel)

        with (
            patch.object(financial_graph_helpers, "infer_statement_and_section_hints", return_value=([], [])),
            patch.object(financial_graph_helpers, "build_concept_task_constraints", return_value={}),
            patch.object(financial_graph_helpers, "_build_generic_retrieval_queries", return_value=[]),
            patch.object(financial_graph_helpers, "_build_metric_task_query", return_value="task query"),
            patch.object(
                financial_graph_helpers,
                "infer_concept_ratio_result_unit",
                side_effect=RuntimeError("unit inference failed"),
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "unit inference failed"):
                financial_graph_helpers._compose_concept_numeric_task(
                    query="ratio query",
                    report_scope={},
                    ontology=object(),
                    metric_label="coverage",
                    operation_family="ratio",
                    operand_specs=[{"label": "value"}],
                )
