import ast
import inspect
import re
import unittest
from collections.abc import Mapping
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock, patch

from src.agent import financial_graph_calculation, financial_numeric_surface


class FinancialRatioScaleTests(unittest.TestCase):
    def test_ratio_component_scale_preserves_nested_iteration_regex_cutoff_laziness_and_exceptions(self) -> None:
        events = []

        class CopyOnlyComponents(Mapping):
            def __init__(self, values):
                self.values_by_role = values

            def __getitem__(self, key):
                events.append(("component-item", key))
                return self.values_by_role[key]

            def __iter__(self):
                events.append(("component-iter",))
                return iter(self.values_by_role)

            def __len__(self):
                events.append(("component-len",))
                return len(self.values_by_role)

            def values(self):
                raise AssertionError("component roles iterated without making the required dict copy")

        class Text:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __str__(self):
                events.append(("str", self.name))
                return self.value

        class Entry(dict):
            def __init__(self, name, *, raw_unit, raw_value):
                super().__init__(raw_unit=raw_unit, raw_value=raw_value)
                self.name = name

            def get(self, key, default=None):
                events.append(("get", self.name, key))
                return super().get(key, default)

        class LaterEntryBomb(dict):
            def get(self, _key, _default=None):
                raise AssertionError("entry after the first suspicious component was accessed")

        unsupported = Entry(
            "unsupported",
            raw_unit=Text("unsupported-unit", " USD "),
            raw_value=Text("unsupported-value", "12,345,678"),
        )
        invalid = Entry(
            "invalid",
            raw_unit=Text("invalid-unit", " KRW "),
            raw_value=Text("invalid-value", "not numeric"),
        )
        seven_digits = Entry(
            "seven",
            raw_unit=Text("seven-unit", " KRW "),
            raw_value=Text("seven-value", "1,234,567"),
        )
        suspicious = Entry(
            "suspicious",
            raw_unit=Text("suspicious-unit", " KRW "),
            raw_value=Text("suspicious-value", " 12,345,678 "),
        )
        components = CopyOnlyComponents(
            {
                "numerator": [unsupported, invalid, seven_digits, suspicious, LaterEntryBomb()],
                "denominator": [LaterEntryBomb()],
            }
        )
        calculation_result = {"answer_slots": {"components_by_role": components}}
        original_fullmatch = re.fullmatch
        original_sub = re.sub

        def normalize(value):
            events.append(("normalize", value))
            return value.strip()

        def fullmatch(pattern, value):
            events.append(("fullmatch", pattern, value))
            return original_fullmatch(pattern, value)

        def substitute(pattern, replacement, value):
            events.append(("sub", pattern, replacement, value))
            return original_sub(pattern, replacement, value)

        with (
            patch.object(financial_numeric_surface, "_normalise_spaces", side_effect=normalize),
            patch.object(financial_numeric_surface.re, "fullmatch", side_effect=fullmatch),
            patch.object(financial_numeric_surface.re, "sub", side_effect=substitute),
        ):
            self.assertTrue(financial_numeric_surface.ratio_components_have_suspicious_scale(calculation_result))
        self.assertIn(("component-iter",), events)
        self.assertEqual(
            [event for event in events if event[0] in {"get", "str", "normalize", "fullmatch", "sub"}],
            [
                ("get", "unsupported", "raw_unit"),
                ("str", "unsupported-unit"),
                ("normalize", " USD "),
                ("get", "unsupported", "raw_value"),
                ("str", "unsupported-value"),
                ("get", "invalid", "raw_unit"),
                ("str", "invalid-unit"),
                ("normalize", " KRW "),
                ("get", "invalid", "raw_value"),
                ("str", "invalid-value"),
                ("fullmatch", r"[\(\)\-]?\d[\d,]*(?:\.\d+)?", "not numeric"),
                ("get", "seven", "raw_unit"),
                ("str", "seven-unit"),
                ("normalize", " KRW "),
                ("get", "seven", "raw_value"),
                ("str", "seven-value"),
                ("fullmatch", r"[\(\)\-]?\d[\d,]*(?:\.\d+)?", "1,234,567"),
                ("sub", r"\D", "", "1,234,567"),
                ("get", "suspicious", "raw_unit"),
                ("str", "suspicious-unit"),
                ("normalize", " KRW "),
                ("get", "suspicious", "raw_value"),
                ("str", "suspicious-value"),
                ("fullmatch", r"[\(\)\-]?\d[\d,]*(?:\.\d+)?", "12,345,678"),
                ("sub", r"\D", "", "12,345,678"),
            ],
        )
        self.assertIs(calculation_result["answer_slots"]["components_by_role"], components)

        class SourceAnswerSlots(dict):
            def get(self, key, default=None):
                if key == "components_by_role":
                    raise AssertionError("component roles read from the source answer-slots mapping")
                return super().get(key, default)

        self.assertFalse(
            financial_numeric_surface.ratio_components_have_suspicious_scale(
                {"answer_slots": SourceAnswerSlots(components_by_role={})}
            )
        )

        polarity_rows = (
            ("KRW", "1,234,567", False),
            ("KRW", "12,345,678", True),
            ("krw", "-12345678", True),
            ("KRW", ")12345678", True),
            ("KRW", "(12345678", True),
            ("KRW", "(12345678)", False),
            ("KRW", "１２３４５６７８", True),
            ("USD", "12,345,678", False),
        )
        for raw_unit, raw_value, expected in polarity_rows:
            with self.subTest(raw_unit=raw_unit, raw_value=raw_value):
                value = {
                    "answer_slots": {
                        "components_by_role": {
                            "numerator": [{"raw_unit": raw_unit, "raw_value": raw_value}],
                        }
                    }
                }
                before = deepcopy(value)
                self.assertEqual(financial_numeric_surface.ratio_components_have_suspicious_scale(value), expected)
                self.assertEqual(value, before)

        class RawValueBomb(dict):
            def get(self, key, default=None):
                if key == "raw_value":
                    raise AssertionError("raw value accessed after unit normalization exception")
                return super().get(key, default)

        with patch.object(
            financial_numeric_surface,
            "_normalise_spaces",
            side_effect=RuntimeError("unit normalization failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "unit normalization failed"):
                financial_numeric_surface.ratio_components_have_suspicious_scale(
                    {
                        "answer_slots": {
                            "components_by_role": {
                                "numerator": [RawValueBomb(raw_unit="KRW", raw_value="12,345,678")],
                            }
                        }
                    }
                )

        stopped_sub = Mock()
        with (
            patch.object(financial_numeric_surface, "_normalise_spaces", side_effect=lambda value: value.strip()),
            patch.object(financial_numeric_surface.re, "fullmatch", side_effect=RuntimeError("regex failed")),
            patch.object(financial_numeric_surface.re, "sub", stopped_sub),
        ):
            with self.assertRaisesRegex(RuntimeError, "regex failed"):
                financial_numeric_surface.ratio_components_have_suspicious_scale(
                    {
                        "answer_slots": {
                            "components_by_role": {
                                "numerator": [{"raw_unit": "KRW", "raw_value": "12,345,678"}],
                            }
                        }
                    }
                )
        stopped_sub.assert_not_called()

        with (
            patch.object(financial_numeric_surface, "_normalise_spaces", side_effect=lambda value: value.strip()),
            patch.object(financial_numeric_surface.re, "sub", side_effect=RuntimeError("digit regex failed")),
        ):
            with self.assertRaisesRegex(RuntimeError, "digit regex failed"):
                financial_numeric_surface.ratio_components_have_suspicious_scale(
                    {
                        "answer_slots": {
                            "components_by_role": {
                                "numerator": [{"raw_unit": "KRW", "raw_value": "12,345,678"}],
                            }
                        }
                    }
                )

    def test_ratio_result_krw_scale_preserves_early_gates_policy_filter_conversion_and_threshold_order(self) -> None:
        events = []

        class BombPolicy(Mapping):
            def __iter__(self):
                raise AssertionError("policy copied before an earlier gate")

            def __len__(self):
                raise AssertionError("policy sized before an earlier gate")

            def __getitem__(self, _key):
                raise AssertionError("policy read before an earlier gate")

        class TextBomb:
            def __str__(self):
                raise AssertionError("later string input accessed before an earlier gate")

        class OperandIterationBomb:
            def __iter__(self):
                raise AssertionError("operands iterated before the source-unit gate")

        with patch.object(financial_numeric_surface, "CALCULATION_RENDER_POLICY", BombPolicy()):
            self.assertFalse(
                financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                    operation_family="sum",
                    ordered_operands=OperandIterationBomb(),
                    result_value=TextBomb(),
                    result_unit=TextBomb(),
                    source_normalized_unit=TextBomb(),
                )
            )
            self.assertFalse(
                financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                    operation_family="ratio",
                    ordered_operands=OperandIterationBomb(),
                    result_value=None,
                    result_unit=TextBomb(),
                    source_normalized_unit=TextBomb(),
                )
            )
            self.assertFalse(
                financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                    operation_family="ratio",
                    ordered_operands=OperandIterationBomb(),
                    result_value=1,
                    result_unit=" %P ",
                    source_normalized_unit=TextBomb(),
                )
            )

        class Policy(Mapping):
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

        policy = Policy(
            {
                "krw_normalized_unit": " krw ",
                "ratio_krw_suspicious_percent_threshold": 10,
            }
        )
        with patch.object(financial_numeric_surface, "CALCULATION_RENDER_POLICY", policy):
            self.assertFalse(
                financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                    operation_family="ratio",
                    ordered_operands=OperandIterationBomb(),
                    result_value=11,
                    result_unit="%",
                    source_normalized_unit="USD",
                )
            )
        self.assertIn(("policy-iter",), events)

        class SourcePolicy(dict):
            def get(self, _key, _default=None):
                raise AssertionError("policy fields read from the source mapping")

        with patch.object(
            financial_numeric_surface,
            "CALCULATION_RENDER_POLICY",
            SourcePolicy(
                krw_normalized_unit="KRW",
                ratio_krw_suspicious_percent_threshold=10,
            ),
        ):
            self.assertFalse(
                financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                    operation_family="ratio",
                    ordered_operands=OperandIterationBomb(),
                    result_value=11,
                    result_unit="%",
                    source_normalized_unit="USD",
                )
            )

        class Row(dict):
            def __init__(self, name, **values):
                super().__init__(**values)
                self.name = name

            def get(self, key, default=None):
                events.append(("row-get", self.name, key))
                if self.name == "usd" and key == "normalized_value":
                    raise AssertionError("non-KRW operand value accessed")
                return super().get(key, default)

        class FloatValue:
            def __init__(self, name, value):
                self.name = name
                self.value = value

            def __float__(self):
                events.append(("float", self.name))
                if isinstance(self.value, BaseException):
                    raise self.value
                return float(self.value)

        operands = [
            Row("usd", normalized_unit="USD", normalized_value=999),
            Row("krw-zero", normalized_unit="KRW", normalized_value=0),
            Row("krw-false", normalized_unit="krw", normalized_value=False),
            Row("after-pair", normalized_unit="USD", normalized_value=999),
        ]
        result_value = FloatValue("result", -11)
        threshold = FloatValue("threshold", 10)
        events.clear()
        with (
            patch.object(
                financial_numeric_surface,
                "CALCULATION_RENDER_POLICY",
                {
                    "krw_normalized_unit": "KRW",
                    "ratio_krw_suspicious_percent_threshold": threshold,
                },
            ),
            patch.object(
                financial_numeric_surface,
                "_normalise_spaces",
                side_effect=lambda value: events.append(("normalize", value)) or value.strip(),
            ),
        ):
            self.assertTrue(
                financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                    operation_family=" ratio ",
                    ordered_operands=operands,
                    result_value=result_value,
                    result_unit=" % ",
                    source_normalized_unit=" krw ",
                )
            )
        self.assertEqual(
            events,
            [
                ("normalize", " ratio "),
                ("normalize", " % "),
                ("normalize", "KRW"),
                ("normalize", " krw "),
                ("row-get", "usd", "normalized_unit"),
                ("normalize", "USD"),
                ("row-get", "krw-zero", "normalized_unit"),
                ("normalize", "KRW"),
                ("row-get", "krw-zero", "normalized_value"),
                ("row-get", "krw-false", "normalized_unit"),
                ("normalize", "krw"),
                ("row-get", "krw-false", "normalized_value"),
                ("row-get", "after-pair", "normalized_unit"),
                ("normalize", "USD"),
                ("float", "threshold"),
                ("float", "result"),
            ],
        )

        one_operand = [Row("only", normalized_unit="KRW", normalized_value=0)]
        conversion_bomb = FloatValue("should-not-convert", RuntimeError("conversion accessed"))
        self.assertFalse(
            financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                operation_family="ratio",
                ordered_operands=one_operand,
                result_value=conversion_bomb,
                result_unit="%",
                source_normalized_unit="KRW",
            )
        )

        def evaluate(threshold_value, result, expected):
            with patch.object(
                financial_numeric_surface,
                "CALCULATION_RENDER_POLICY",
                {
                    "krw_normalized_unit": "KRW",
                    "ratio_krw_suspicious_percent_threshold": threshold_value,
                },
            ):
                self.assertEqual(
                    financial_numeric_surface.ratio_result_has_suspicious_krw_scale(
                        operation_family="ratio",
                        ordered_operands=[
                            {"normalized_unit": "KRW", "normalized_value": 0},
                            {"normalized_unit": "KRW", "normalized_value": 1},
                        ],
                        result_value=result,
                        result_unit="%p",
                        source_normalized_unit="KRW",
                    ),
                    expected,
                )

        evaluate(10, 10, False)
        evaluate(10, -10.01, True)

        events.clear()
        evaluate(FloatValue("zero-threshold", 0), FloatValue("zero-result", 999), False)
        self.assertEqual(events, [("float", "zero-threshold"), ("float", "zero-result")])

        events.clear()
        evaluate(FloatValue("bad-threshold", TypeError("bad threshold")), FloatValue("later-result", 20), False)
        self.assertEqual(events, [("float", "bad-threshold")])
        events.clear()
        evaluate(FloatValue("good-threshold", 10), FloatValue("bad-result", ValueError("bad result")), False)
        self.assertEqual(events, [("float", "good-threshold"), ("float", "bad-result")])

        with self.assertRaisesRegex(RuntimeError, "threshold escaped"):
            evaluate(FloatValue("runtime-threshold", RuntimeError("threshold escaped")), 20, False)

        with self.assertRaisesRegex(RuntimeError, "result escaped"):
            evaluate(10, FloatValue("runtime-result", RuntimeError("result escaped")), False)

    def test_ratio_scale_callers_preserve_all_bindings_args_polarity_adoption_and_exception_boundaries(self) -> None:
        helper_names = {
            "ratio_components_have_suspicious_scale",
            "ratio_result_has_suspicious_krw_scale",
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
        self.assertEqual(
            sorted((function, helper, args, kwargs) for function, helper, args, kwargs, _call in calls),
            sorted(
                [
                    (
                        "_project_prepared_calculation_candidate",
                        "ratio_result_has_suspicious_krw_scale",
                        (),
                        (
                            ("operation_family", "operation_family"),
                            ("ordered_operands", "ordered_operands"),
                            ("result_value", "result_value"),
                            ("result_unit", "result_unit"),
                            ("source_normalized_unit", "source_normalized_unit"),
                        ),
                    ),
                    (
                        "_render_calculation_answer",
                        "ratio_components_have_suspicious_scale",
                        ("calculation_result",),
                        (),
                    ),
                    (
                        "_verify_calculation_answer",
                        "ratio_components_have_suspicious_scale",
                        ("calculation_result",),
                        (),
                    ),
                ]
            ),
        )

        for function_name, helper_name, _args, _kwargs, call in calls:
            current = call
            has_not = False
            containing_try = False
            while current is not None and not isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                current = parents.get(current)
                if isinstance(current, ast.UnaryOp) and isinstance(current.op, ast.Not):
                    has_not = True
                if isinstance(current, ast.Try):
                    containing_try = True
            self.assertFalse(has_not, (function_name, helper_name))
            self.assertEqual(
                containing_try,
                function_name == "_verify_calculation_answer",
                (function_name, helper_name),
            )

        for function_name in ("_render_calculation_answer", "_verify_calculation_answer"):
            function = next(
                node for node in tree.body if isinstance(node, ast.ClassDef)
                for child in node.body
                if isinstance(child, ast.FunctionDef) and child.name == function_name
                for node in [child]
            )
            ordered_helpers = []
            for call in ast.walk(function):
                if not isinstance(call, ast.Call):
                    continue
                if (
                    isinstance(call.func, ast.Attribute)
                    and isinstance(call.func.value, ast.Name)
                    and call.func.value.id == "financial_answer_slots"
                    and call.func.attr
                    in {"ratio_components_are_complete", "ratio_component_consolidation_scope"}
                ):
                    ordered_helpers.append((call.lineno, call.func.attr))
                elif (
                    isinstance(call.func, ast.Name)
                    and call.func.id == "ratio_components_have_suspicious_scale"
                ):
                    ordered_helpers.append((call.lineno, call.func.id))
            self.assertEqual(
                [name for _line, name in sorted(ordered_helpers)],
                [
                    "ratio_components_are_complete",
                    "ratio_component_consolidation_scope",
                    "ratio_components_have_suspicious_scale",
                ],
                function_name,
            )

        agent = financial_graph_calculation.FinancialAgentCalculationMixin()
        nested = {"preserve": True}
        operand = {
            "operand_id": "operand",
            "normalized_unit": "KRW",
            "normalized_value": 1,
            "nested": nested,
        }
        execution_outcome = financial_graph_calculation.CalculationExecutionOutcome(
            status="ok",
            reason="",
            result_value=500.0,
            normalized_unit="%",
            source_normalized_unit="KRW",
            ordered_operands=(operand,),
            selected_evidence_ids=("ev_ratio",),
        )
        candidate = financial_graph_calculation._PreparedCalculationCandidate(
            status="ok",
            reason="",
            calculation_operands=(operand,),
            calculation_plan={
                "operation": "ratio",
                "mode": "single_value",
                "formula": "A / B",
                "pairwise_formula": "",
            },
            active_subtask={"metric_label": "target ratio"},
            query="target ratio",
            operation_family="ratio",
            result_unit="%",
            execution_outcome=execution_outcome,
            selected_evidence_ids=("ev_ratio",),
            source_normalized_unit="KRW",
        )

        def result_scale_owner(**kwargs):
            self.assertEqual(
                set(kwargs),
                {
                    "operation_family",
                    "ordered_operands",
                    "result_value",
                    "result_unit",
                    "source_normalized_unit",
                },
            )
            self.assertEqual(kwargs["operation_family"], "ratio")
            self.assertEqual(kwargs["result_value"], 500.0)
            self.assertEqual(kwargs["result_unit"], "%")
            self.assertEqual(kwargs["source_normalized_unit"], "KRW")
            self.assertEqual(kwargs["ordered_operands"], [operand])
            self.assertIsNot(kwargs["ordered_operands"][0], operand)
            self.assertIs(kwargs["ordered_operands"][0]["nested"], nested)
            return True

        stopped_display = Mock()
        with (
            patch.object(
                financial_graph_calculation,
                "ratio_result_has_suspicious_krw_scale",
                side_effect=result_scale_owner,
            ) as scale_owner,
            patch.object(financial_graph_calculation.calculation_rendering, "scalar_result_display", stopped_display),
        ):
            projection = agent._project_prepared_calculation_candidate(candidate)
        self.assertEqual(projection.status, "scale_mismatch")
        self.assertEqual(projection.reason, "same-unit KRW ratio produced an implausible percent result; retry with better grounded operands")
        self.assertEqual(scale_owner.call_count, 1)
        stopped_display.assert_not_called()

        with (
            patch.object(
                financial_graph_calculation,
                "ratio_result_has_suspicious_krw_scale",
                side_effect=RuntimeError("result scale owner failed"),
            ),
            patch.object(financial_graph_calculation.calculation_rendering, "scalar_result_display", stopped_display),
        ):
            with self.assertRaisesRegex(RuntimeError, "result scale owner failed"):
                agent._project_prepared_calculation_candidate(candidate)
        stopped_display.assert_not_called()

        class StructuredLLM:
            def with_structured_output(self, _model):
                return self

        class Prompt:
            def __init__(self, response):
                self.response = response

            def __or__(self, _llm):
                return self

            def invoke(self, _payload):
                return self.response

        render_result = {
            "status": "ok",
            "result_value": 25.0,
            "result_unit": "%",
            "rendered_value": "25%",
            "answer_slots": {"operation_family": "ratio"},
            "nested": nested,
        }
        plan = {"operation": "ratio"}
        render_trace = {
            "calculation_operands": [operand],
            "calculation_plan": plan,
            "calculation_result": render_result,
        }
        render_state = {"query": "target ratio", "resolved_calculation_trace": render_trace}
        render_events = []

        def component_scale_owner(value):
            render_events.append("suspicious")
            self.assertIs(value, render_result)
            return True

        def run_render(component_effect, compact_owner):
            stale_repair = SimpleNamespace(
                repair_applied=False,
                calculation_operands=[operand],
                calculation_plan=plan,
                calculation_result=render_result,
                selected_evidence_ids=(),
            )
            with (
                patch.object(financial_graph_calculation, "_resolve_runtime_calculation_trace", return_value=render_trace),
                patch.object(agent, "_repair_stale_calculation_result_from_operands", return_value=stale_repair),
                patch.object(agent, "_calc_query", side_effect=lambda state: str(state.get("query") or ""), create=True),
                patch.object(financial_graph_calculation.calculation_rendering, "direction_hint_for_result", return_value=""),
                patch.object(
                    financial_graph_calculation.calculation_rendering,
                    "coerce_rendered_value_for_direction",
                    side_effect=lambda result, **_kwargs: result,
                ),
                patch.object(
                    financial_graph_calculation.calculation_rendering,
                    "compose_slot_based_difference_answer",
                    return_value="",
                ),
                patch.object(agent, "_llm_for_phase", return_value=StructuredLLM(), create=True),
                patch.object(financial_graph_calculation, "_calculation_render_output_model", return_value=object),
                patch.object(
                    financial_graph_calculation,
                    "_chat_prompt_template_from_template",
                    return_value=Prompt(SimpleNamespace(final_answer="model ratio")),
                ),
                patch.object(
                    financial_graph_calculation.calculation_rendering,
                    "coerce_sign_aware_subtraction_answer",
                    side_effect=lambda answer, **_kwargs: answer,
                ),
                patch.object(
                    financial_graph_calculation.financial_answer_slots,
                    "ratio_components_are_complete",
                    side_effect=lambda _value: render_events.append("complete") or False,
                ),
                patch.object(
                    financial_graph_calculation.financial_answer_slots,
                    "ratio_component_consolidation_scope",
                    side_effect=lambda _value, _operands: render_events.append("scope") or "",
                ),
                patch.object(
                    financial_graph_calculation,
                    "ratio_components_have_suspicious_scale",
                    side_effect=component_effect,
                ),
                patch.object(agent, "_compact_ratio_answer", compact_owner),
            ):
                return agent._render_calculation_answer(render_state)

        render_compact = Mock(side_effect=lambda _state, result: render_events.append("compact") or "compact ratio")
        rendered = run_render(component_scale_owner, render_compact)
        self.assertEqual(rendered["answer"], "compact ratio")
        self.assertEqual(render_events, ["complete", "scope", "suspicious", "compact"])
        render_compact.assert_called_once_with(render_state, render_result)

        render_result.pop("formatted_result", None)
        stopped_compact = Mock()
        with self.assertRaisesRegex(RuntimeError, "component scale owner failed"):
            run_render(RuntimeError("component scale owner failed"), stopped_compact)
        stopped_compact.assert_not_called()

        verify_result = {
            "status": "ok",
            "result_value": 25.0,
            "result_unit": "%",
            "rendered_value": "25%",
            "formatted_result": "old ratio",
            "answer_slots": {"operation_family": "ratio"},
            "nested": nested,
        }
        verify_trace = {
            "calculation_operands": [operand],
            "calculation_plan": plan,
            "calculation_result": verify_result,
        }
        verify_state = {
            "query": "target ratio",
            "answer": "old ratio",
            "compressed_answer": "old ratio",
            "resolved_calculation_trace": verify_trace,
        }
        verify_events = []

        def run_verify(component_effect, compact_owner):
            with (
                patch.object(financial_graph_calculation, "_resolve_runtime_calculation_trace", return_value=verify_trace),
                patch.object(agent, "_calc_query", side_effect=lambda state: str(state.get("query") or ""), create=True),
                patch.object(financial_graph_calculation.calculation_rendering, "direction_hint_for_result", return_value=""),
                patch.object(agent, "_llm_for_phase", return_value=StructuredLLM(), create=True),
                patch.object(financial_graph_calculation, "_calculation_verification_output_model", return_value=object),
                patch.object(
                    financial_graph_calculation,
                    "_chat_prompt_template_from_template",
                    return_value=Prompt(
                        SimpleNamespace(verdict="keep", final_answer="verified ratio", issues=[])
                    ),
                ),
                patch.object(
                    financial_graph_calculation.calculation_rendering,
                    "coerce_sign_aware_subtraction_answer",
                    side_effect=lambda answer, **_kwargs: answer,
                ),
                patch.object(
                    financial_graph_calculation.financial_answer_slots,
                    "ratio_components_are_complete",
                    side_effect=lambda _value: verify_events.append("complete") or False,
                ),
                patch.object(
                    financial_graph_calculation.financial_answer_slots,
                    "ratio_component_consolidation_scope",
                    side_effect=lambda _value, _operands: verify_events.append("scope") or "",
                ),
                patch.object(
                    financial_graph_calculation,
                    "ratio_components_have_suspicious_scale",
                    side_effect=component_effect,
                ),
                patch.object(agent, "_compact_ratio_answer", compact_owner),
            ):
                return agent._verify_calculation_answer(verify_state)

        def verify_component_owner(value):
            verify_events.append("suspicious")
            self.assertIsNot(value, verify_result)
            self.assertEqual(value, verify_result)
            self.assertIs(value["nested"], nested)
            return True

        verify_compact = Mock(side_effect=lambda _state, _result: verify_events.append("compact") or "verified compact")
        verified = run_verify(verify_component_owner, verify_compact)
        self.assertEqual(verified["answer"], "verified compact")
        self.assertEqual(verify_events, ["complete", "scope", "suspicious", "compact"])
        self.assertEqual(verify_compact.call_count, 1)

        verify_events.clear()
        verify_result.pop("formatted_result", None)
        stopped_verify_compact = Mock()
        verification_failure = run_verify(RuntimeError("verification scale failed"), stopped_verify_compact)
        self.assertEqual(verification_failure["answer"], "old ratio")
        self.assertEqual(
            verification_failure["calculation_debug_trace"]["verification"]["verdict"],
            "error_keep",
        )
        stopped_verify_compact.assert_not_called()
