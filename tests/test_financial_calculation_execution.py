import ast
import unittest
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock, patch

import src.agent.financial_graph_calculation as graph_calculation
import src.agent.financial_calculation_execution as calculation_execution
from src.agent.financial_calculation_execution import (
    CalculationExecutionOutcome,
    DeterministicOperationPlanDecision,
    StaleCalculationValueAssessment,
    assess_stale_calculation_value,
    build_deterministic_operation_plan,
    build_failed_calculation_result,
    build_scalar_calculation_result,
    build_scalar_calculation_state,
    build_success_calculation_state_payload,
    build_time_series_calculation_result,
    execute_prepared_calculation_plan,
    guard_operation_plan,
    resolve_deterministic_operation_plan,
    time_series_yoy_growth_rates,
)
from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import CalculationResult

class FinancialCalculationExecutionTests(unittest.TestCase):
    def test_prepare_candidate_binds_growth_raw_scale_alignment_once_in_exact_gate_order(self) -> None:
        tree = ast.parse(Path(graph_calculation.__file__).read_text(encoding="utf-8"))
        target = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_prepare_calculation_candidate"
        )
        parents = {
            child: parent
            for parent in ast.walk(target)
            for child in ast.iter_child_nodes(parent)
        }
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "align_growth_operand_units_when_raw_scale_matches"
        ]
        self.assertEqual(len(calls), 1)
        owner_call = calls[0]
        self.assertIn(owner_call, list(ast.walk(target)))
        self.assertEqual(len(owner_call.args), 1)
        self.assertEqual(ast.unparse(owner_call.args[0]), "ordered_operands")
        self.assertEqual(owner_call.keywords, [])
        ancestor_tests = []
        parent = parents[owner_call]
        while parent is not target:
            if isinstance(parent, ast.If):
                ancestor_tests.append(ast.unparse(parent.test))
            self.assertNotIsInstance(parent, ast.Try)
            parent = parents[parent]
        self.assertTrue(any("operation_family == 'growth_rate'" in test for test in ancestor_tests))
        self.assertTrue(any("len(concept_keys) <= 1" in test for test in ancestor_tests))
        self.assertTrue(
            any("operation_family in {'difference', 'growth_rate'}" in test and "len(ordered_operands) == 2" in test for test in ancestor_tests)
        )

        donor_calls = [
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_normalise_operand_value"
            and node.lineno < owner_call.lineno
        ]
        duplicate_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "recover_duplicate_growth_prior_operand"
        )
        conflict_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "growth_operand_periods_conflict"
        )
        sign_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "apply_operation_sign_policy"
        )
        self.assertTrue(donor_calls)
        self.assertLess(max(node.lineno for node in donor_calls), owner_call.lineno)
        self.assertLess(owner_call.lineno, duplicate_call.lineno)
        self.assertLess(duplicate_call.lineno, conflict_call.lineno)
        self.assertLess(conflict_call.lineno, sign_call.lineno)

    def test_prepare_candidate_adopts_growth_raw_scale_alignment_after_donor_and_stops_on_exception(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        def candidate_input(*, operation_family="growth_rate", concepts=("revenue", "revenue")):
            return graph_calculation._CalculationCandidateInput(
                calculation_operands=(
                    {
                        "operand_id": "current",
                        "matched_operand_role": "current_period",
                        "matched_operand_concept": concepts[0],
                        "raw_value": "20",
                        "raw_unit": "백만원",
                        "normalized_value": 20.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "prior",
                        "matched_operand_role": "prior_period",
                        "matched_operand_concept": concepts[1],
                        "raw_value": "10",
                        "raw_unit": "",
                        "normalized_value": None,
                        "normalized_unit": "UNKNOWN",
                    },
                ),
                calculation_plan={
                    "mode": "scalar",
                    "operation": operation_family,
                    "ordered_operand_ids": ["current", "prior"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "current"},
                        {"variable": "B", "operand_id": "prior"},
                    ],
                    "formula": "(A - B) / B * 100",
                    "pairwise_formula": "",
                    "result_unit": "PERCENT",
                },
                active_subtask={"operation_family": operation_family, "required_operands": []},
                query="growth",
                evidence_items=(),
                runtime_evidence=(),
            )

        def execute(**kwargs):
            ordered = tuple(kwargs["operands_by_id"][item] for item in kwargs["ordered_operand_ids"])
            return CalculationExecutionOutcome(
                status="ok",
                reason="",
                result_value=100.0,
                normalized_unit="PERCENT",
                source_normalized_unit="PERCENT",
                ordered_operands=ordered,
                selected_evidence_ids=(),
            )

        def invoke(
            owner_effect,
            *,
            operation_family="growth_rate",
            concepts=("revenue", "revenue"),
            events=None,
        ):
            events = [] if events is None else events

            def donor_normalizer(raw_value, raw_unit):
                events.append(("donor", raw_value, raw_unit))
                return 10.0, "KRW"

            def duplicate(rows, _evidence):
                events.append(("duplicate", rows))
                return rows

            def conflict(rows):
                events.append(("conflict", rows))
                return False

            def sign(rows, **_kwargs):
                events.append(("sign", rows))
                return rows

            def tracked_execute(**kwargs):
                events.append(("execute", kwargs["operands_by_id"]))
                return execute(**kwargs)

            with (
                patch.object(agent, "_coerce_operand_row_from_evidence", side_effect=lambda row, _evidence: row),
                patch.object(
                    graph_calculation,
                    "repair_krw_operand_units_from_table_metadata",
                    side_effect=lambda rows, _evidence: rows,
                ),
                patch.object(graph_calculation, "repair_krw_normalized_values_from_raw_units", side_effect=lambda rows: rows),
                patch.object(graph_calculation, "guard_operation_plan", return_value={}),
                patch.object(graph_calculation, "repair_operand_normalization_from_rendered_unit", side_effect=lambda row: row),
                patch.object(graph_calculation, "_normalise_operand_value", side_effect=donor_normalizer),
                patch.object(
                    graph_calculation,
                    "align_growth_operand_units_when_raw_scale_matches",
                    side_effect=owner_effect,
                ) as owner,
                patch.object(
                    graph_calculation,
                    "recover_duplicate_growth_prior_operand",
                    side_effect=duplicate,
                ) as duplicate_mock,
                patch.object(
                    graph_calculation,
                    "growth_operand_periods_conflict",
                    side_effect=conflict,
                ) as conflict_mock,
                patch.object(graph_calculation, "apply_operation_sign_policy", side_effect=sign) as sign_mock,
                patch.object(graph_calculation, "coerce_lookup_magnitude_record", side_effect=lambda row, _evidence: row),
                patch.object(graph_calculation, "execute_prepared_calculation_plan", side_effect=tracked_execute) as executor,
            ):
                result = agent._prepare_calculation_candidate(
                    candidate_input(operation_family=operation_family, concepts=concepts)
                )
            return result, events, owner, duplicate_mock, conflict_mock, sign_mock, executor

        def align(rows):
            prior = dict(rows[1])
            self.assertEqual(prior["raw_unit"], "백만원")
            self.assertEqual(prior["normalized_value"], 10.0)
            self.assertEqual(prior["normalized_unit"], "KRW")
            prior["aligned_by_owner"] = True
            return [rows[0], prior]

        result, events, owner, duplicate, conflict, sign, executor = invoke(align)
        owner.assert_called_once()
        self.assertEqual(result.status, "ok")
        self.assertTrue(result.calculation_operands[1]["aligned_by_owner"])
        event_names = [event[0] for event in events]
        self.assertLess(event_names.index("donor"), event_names.index("duplicate"))
        self.assertLess(event_names.index("duplicate"), event_names.index("conflict"))
        self.assertLess(event_names.index("conflict"), event_names.index("sign"))
        self.assertLess(event_names.index("sign"), event_names.index("execute"))
        self.assertTrue(events[event_names.index("duplicate")][1][1]["aligned_by_owner"])
        self.assertTrue(events[event_names.index("execute")][1]["prior"]["aligned_by_owner"])
        duplicate.assert_called_once()
        conflict.assert_called_once()
        sign.assert_called_once()
        executor.assert_called_once()

        gated, _events, gated_owner, *_ = invoke(
            lambda _rows: (_ for _ in ()).throw(AssertionError("difference owner call")),
            operation_family="difference",
        )
        self.assertEqual(gated.status, "ok")
        gated_owner.assert_not_called()

        concept_gated, _events, concept_owner, *_ = invoke(
            lambda _rows: (_ for _ in ()).throw(AssertionError("concept owner call")),
            concepts=("revenue", "profit"),
        )
        self.assertEqual(concept_gated.status, "ok")
        concept_owner.assert_not_called()

        owner_input_rows = []
        equal_return_rows = []

        def equal_owner(rows):
            owner_input_rows.extend(rows)
            equal_return_rows.extend(dict(row) for row in rows)
            return equal_return_rows

        _equal_result, equal_events, equal_owner_mock, *_ = invoke(equal_owner)
        equal_owner_mock.assert_called_once()
        duplicate_rows = next(event[1] for event in equal_events if event[0] == "duplicate")
        self.assertIs(duplicate_rows[0], owner_input_rows[0])
        self.assertIs(duplicate_rows[1], owner_input_rows[1])
        self.assertIsNot(duplicate_rows[0], equal_return_rows[0])
        self.assertIsNot(duplicate_rows[1], equal_return_rows[1])

        stop_events = []

        def owner_failure(rows):
            stop_events.append(("owner", rows))
            raise RuntimeError("growth alignment")

        with self.assertRaisesRegex(RuntimeError, "growth alignment"):
            invoke(owner_failure, events=stop_events)
        self.assertEqual([event[0] for event in stop_events], ["donor", "owner"])

    def test_prepare_candidate_binds_growth_period_conflict_once_after_recovery(self) -> None:
        tree = ast.parse(Path(graph_calculation.__file__).read_text(encoding="utf-8"))
        target = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_prepare_calculation_candidate"
        )
        parents = {
            child: parent
            for parent in ast.walk(target)
            for child in ast.iter_child_nodes(parent)
        }
        calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "growth_operand_periods_conflict"
        ]
        self.assertEqual(len(calls), 1)
        owner_call = calls[0]
        self.assertIn(owner_call, list(ast.walk(target)))
        self.assertEqual(len(owner_call.args), 1)
        self.assertEqual(ast.unparse(owner_call.args[0]), "ordered_operands")
        self.assertEqual(owner_call.keywords, [])

        owner_if = parents[owner_call]
        self.assertIsInstance(owner_if, ast.If)
        failure_calls = [
            node
            for node in ast.walk(owner_if)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_prepared_failure"
        ]
        self.assertEqual(len(failure_calls), 1)
        self.assertEqual(
            [ast.literal_eval(arg) for arg in failure_calls[0].args],
            ["insufficient_operands", "growth operands share the same period"],
        )

        ancestor_tests = []
        parent = owner_if
        while parent is not target:
            if isinstance(parent, ast.If):
                ancestor_tests.append(ast.unparse(parent.test))
            self.assertNotIsInstance(parent, ast.Try)
            parent = parents[parent]
        self.assertTrue(any("operation_family == 'growth_rate'" in test for test in ancestor_tests))

        duplicate_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "recover_duplicate_growth_prior_operand"
        )
        adoption_assignments = [
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Assign)
            and duplicate_call.lineno < node.lineno < owner_call.lineno
            and any(
                isinstance(name, ast.Name) and name.id == "ordered_operands"
                for target_node in node.targets
                for name in ast.walk(target_node)
            )
        ]
        sign_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "apply_operation_sign_policy"
        )
        executor_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "execute_prepared_calculation_plan"
        )
        self.assertTrue(adoption_assignments)
        self.assertLess(duplicate_call.lineno, min(node.lineno for node in adoption_assignments))
        self.assertLess(max(node.lineno for node in adoption_assignments), owner_call.lineno)
        self.assertLess(owner_call.lineno, sign_call.lineno)
        self.assertLess(sign_call.lineno, executor_call.lineno)

    def test_prepare_candidate_applies_growth_period_conflict_boolean_and_exception_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)

        def candidate_input(*, operation_family="growth_rate"):
            return graph_calculation._CalculationCandidateInput(
                calculation_operands=(
                    {
                        "operand_id": "current",
                        "matched_operand_role": "current_period",
                        "matched_operand_concept": "revenue",
                        "period": "2024",
                        "raw_value": "20",
                        "raw_unit": "KRW",
                        "normalized_value": 20.0,
                        "normalized_unit": "KRW",
                    },
                    {
                        "operand_id": "prior",
                        "matched_operand_role": "prior_period",
                        "matched_operand_concept": "revenue",
                        "period": "2023",
                        "raw_value": "10",
                        "raw_unit": "KRW",
                        "normalized_value": 10.0,
                        "normalized_unit": "KRW",
                    },
                ),
                calculation_plan={
                    "mode": "scalar",
                    "operation": operation_family,
                    "ordered_operand_ids": ["current", "prior"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "current"},
                        {"variable": "B", "operand_id": "prior"},
                    ],
                    "formula": "(A - B) / B * 100",
                    "pairwise_formula": "",
                    "result_unit": "PERCENT",
                },
                active_subtask={"operation_family": operation_family, "required_operands": []},
                query="growth",
                evidence_items=(),
                runtime_evidence=(),
            )

        def execute(**kwargs):
            ordered = tuple(kwargs["operands_by_id"][item] for item in kwargs["ordered_operand_ids"])
            return CalculationExecutionOutcome(
                status="ok",
                reason="",
                result_value=100.0,
                normalized_unit="PERCENT",
                source_normalized_unit="PERCENT",
                ordered_operands=ordered,
                selected_evidence_ids=(),
            )

        def invoke(conflict_effect, *, operation_family="growth_rate", events=None):
            events = [] if events is None else events

            def duplicate(rows, _evidence):
                recovered_prior = dict(rows[1])
                recovered_prior["duplicate_recovered"] = True
                recovered = [rows[0], recovered_prior]
                events.append(("duplicate", recovered))
                return recovered

            def conflict(rows):
                events.append(("conflict", rows))
                return conflict_effect(rows)

            def sign(rows, **_kwargs):
                events.append(("sign", rows))
                return rows

            def magnitude(row, _evidence):
                events.append(("magnitude", row))
                return row

            def tracked_execute(**kwargs):
                events.append(("execute", kwargs["operands_by_id"]))
                return execute(**kwargs)

            with (
                patch.object(agent, "_coerce_operand_row_from_evidence", side_effect=lambda row, _evidence: row),
                patch.object(
                    graph_calculation,
                    "repair_krw_operand_units_from_table_metadata",
                    side_effect=lambda rows, _evidence: rows,
                ),
                patch.object(graph_calculation, "repair_krw_normalized_values_from_raw_units", side_effect=lambda rows: rows),
                patch.object(graph_calculation, "guard_operation_plan", return_value={}),
                patch.object(graph_calculation, "repair_operand_normalization_from_rendered_unit", side_effect=lambda row: row),
                patch.object(graph_calculation, "align_growth_operand_units_when_raw_scale_matches", side_effect=lambda rows: rows),
                patch.object(
                    graph_calculation,
                    "recover_duplicate_growth_prior_operand",
                    side_effect=duplicate,
                ) as duplicate_mock,
                patch.object(
                    graph_calculation,
                    "growth_operand_periods_conflict",
                    side_effect=conflict,
                ) as owner,
                patch.object(graph_calculation, "apply_operation_sign_policy", side_effect=sign) as sign_mock,
                patch.object(graph_calculation, "coerce_lookup_magnitude_record", side_effect=magnitude) as magnitude_mock,
                patch.object(graph_calculation, "execute_prepared_calculation_plan", side_effect=tracked_execute) as executor,
            ):
                result = agent._prepare_calculation_candidate(candidate_input(operation_family=operation_family))
            return result, events, duplicate_mock, owner, sign_mock, magnitude_mock, executor

        continued, events, duplicate, owner, sign, magnitude, executor = invoke(lambda _rows: False)
        self.assertEqual(continued.status, "ok")
        duplicate.assert_called_once()
        owner.assert_called_once()
        sign.assert_called_once()
        self.assertEqual(magnitude.call_count, 2)
        executor.assert_called_once()
        event_names = [event[0] for event in events]
        self.assertEqual(event_names, ["duplicate", "conflict", "sign", "magnitude", "magnitude", "execute"])
        self.assertTrue(events[1][1][1]["duplicate_recovered"])
        self.assertTrue(events[-1][1]["prior"]["duplicate_recovered"])
        self.assertTrue(continued.calculation_operands[1]["duplicate_recovered"])

        failed, events, duplicate, owner, sign, magnitude, executor = invoke(lambda _rows: True)
        self.assertEqual(failed.status, "insufficient_operands")
        self.assertEqual(failed.reason, "growth operands share the same period")
        self.assertEqual([event[0] for event in events], ["duplicate", "conflict"])
        self.assertTrue(events[1][1][1]["duplicate_recovered"])
        duplicate.assert_called_once()
        owner.assert_called_once()
        sign.assert_not_called()
        magnitude.assert_not_called()
        executor.assert_not_called()

        gated, events, duplicate, owner, sign, magnitude, executor = invoke(
            lambda _rows: (_ for _ in ()).throw(AssertionError("difference conflict call")),
            operation_family="difference",
        )
        self.assertEqual(gated.status, "ok")
        self.assertEqual([event[0] for event in events], ["sign", "magnitude", "magnitude", "execute"])
        duplicate.assert_not_called()
        owner.assert_not_called()
        sign.assert_called_once()
        self.assertEqual(magnitude.call_count, 2)
        executor.assert_called_once()

        stop_events: List[Any] = []
        with self.assertRaisesRegex(RuntimeError, "period conflict"):
            invoke(
                lambda _rows: (_ for _ in ()).throw(RuntimeError("period conflict")),
                events=stop_events,
            )
        self.assertEqual([event[0] for event in stop_events], ["duplicate", "conflict"])

    def test_prepare_candidate_binds_krw_raw_unit_repair_once_in_exact_order(self) -> None:
        tree = ast.parse(Path(graph_calculation.__file__).read_text(encoding="utf-8"))
        target = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_prepare_calculation_candidate"
        )
        parents = {
            child: parent
            for parent in ast.walk(target)
            for child in ast.iter_child_nodes(parent)
        }
        module_owner_calls = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "repair_krw_normalized_values_from_raw_units"
        ]
        self.assertEqual(len(module_owner_calls), 1)
        owner_call = module_owner_calls[0]
        self.assertIn(owner_call, list(ast.walk(target)))
        self.assertEqual(len(owner_call.args), 1)
        self.assertEqual(ast.dump(owner_call.args[0]), ast.dump(ast.Name(id="runtime_operands", ctx=ast.Load())))
        self.assertEqual(owner_call.keywords, [])

        def top_level_statement(node):
            while parents.get(node) is not target:
                node = parents[node]
            return node

        def statement_index_for_call(attribute):
            call = next(
                node
                for node in ast.walk(target)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "self"
                and node.func.attr == attribute
            )
            return target.body.index(top_level_statement(call))

        table_call = next(
            node
            for node in ast.walk(target)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "repair_krw_operand_units_from_table_metadata"
        )
        table_index = target.body.index(top_level_statement(table_call))
        owner_index = target.body.index(top_level_statement(owner_call))
        operands_index = next(
            index
            for index, statement in enumerate(target.body)
            if isinstance(statement, ast.Assign)
            and any(isinstance(item, ast.Name) and item.id == "operands" for item in statement.targets)
        )
        plan_index = next(
            index
            for index, statement in enumerate(target.body)
            if isinstance(statement, ast.Assign)
            and any(isinstance(item, ast.Name) and item.id == "plan" for item in statement.targets)
        )
        self.assertEqual((owner_index - table_index, operands_index - owner_index, plan_index - operands_index), (1, 1, 1))
        self.assertFalse(any(isinstance(parent, ast.Try) for parent in parents if owner_call in ast.walk(parent)))

    def test_prepare_candidate_adopts_krw_raw_unit_repair_before_plan_gate_and_stops_on_exception(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        shared = {"preserve": True}

        class RowProbe(dict):
            def __init__(self, *args, events, **kwargs):
                super().__init__(*args, **kwargs)
                self._events = events

            def get(self, key, default=None):
                if key == "operand_id":
                    self._events.append(("operand_index", self))
                return super().get(key, default)

        class PlanProbe(Mapping):
            def __init__(self, events):
                self._events = events
                self._data = {
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "result_unit": "",
                }

            def __getitem__(self, key):
                self._events.append(("plan_item", key))
                return self._data[key]

            def __iter__(self):
                self._events.append(("plan_iter", None))
                return iter(self._data)

            def __len__(self):
                return len(self._data)

        def candidate_input(events):
            return graph_calculation._CalculationCandidateInput(
                calculation_operands=({"operand_id": "input", "nested": shared},),
                calculation_plan=PlanProbe(events),
                active_subtask={"operation_family": "lookup", "required_operands": []},
                query="lookup",
                evidence_items=(),
                runtime_evidence=(),
            )

        events = []
        table_rows = [{"operand_id": "table", "normalized_value": 1.0, "nested": shared}]
        owner_rows = [RowProbe(
            {"operand_id": "owner", "normalized_value": 2.0, "nested": shared},
            events=events,
        )]

        def coerce(row, evidence):
            events.append(("coerce", row, evidence))
            return row

        def table_repair(rows, evidence_items):
            events.append(("table_repair", rows, evidence_items))
            return table_rows

        def owner_repair(rows):
            events.append(("owner_repair", rows))
            self.assertIs(rows, table_rows)
            return owner_rows

        with (
            patch.object(agent, "_coerce_operand_row_from_evidence", side_effect=coerce),
            patch.object(
                graph_calculation,
                "repair_krw_operand_units_from_table_metadata",
                side_effect=table_repair,
            ),
            patch.object(
                graph_calculation,
                "repair_krw_normalized_values_from_raw_units",
                side_effect=owner_repair,
            ) as owner,
            patch.object(graph_calculation, "apply_operation_sign_policy") as sign_policy,
            patch.object(graph_calculation, "execute_prepared_calculation_plan") as executor,
        ):
            result = agent._prepare_calculation_candidate(candidate_input(events))

        self.assertEqual(result.status, "insufficient_operands")
        owner.assert_called_once_with(table_rows)
        self.assertEqual(result.calculation_operands[0]["operand_id"], "owner")
        self.assertEqual(result.calculation_operands[0]["normalized_value"], 2.0)
        self.assertIs(result.calculation_operands[0]["nested"], shared)
        event_names = [event[0] for event in events]
        self.assertLess(event_names.index("coerce"), event_names.index("table_repair"))
        self.assertLess(event_names.index("table_repair"), event_names.index("owner_repair"))
        self.assertLess(event_names.index("owner_repair"), event_names.index("operand_index"))
        self.assertLess(event_names.index("operand_index"), event_names.index("plan_iter"))
        sign_policy.assert_not_called()
        executor.assert_not_called()

        stop_events = []
        stop_table_rows = [RowProbe({"operand_id": "table"}, events=stop_events)]
        with (
            patch.object(agent, "_coerce_operand_row_from_evidence", side_effect=lambda row, _evidence: row),
            patch.object(
                graph_calculation,
                "repair_krw_operand_units_from_table_metadata",
                side_effect=lambda _rows, _evidence: (stop_events.append(("table_repair", None)) or stop_table_rows),
            ),
            patch.object(
                graph_calculation,
                "repair_krw_normalized_values_from_raw_units",
                side_effect=lambda rows: (
                    stop_events.append(("owner_repair", rows)),
                    (_ for _ in ()).throw(RuntimeError("raw-unit repair")),
                )[1],
            ),
            patch.object(graph_calculation, "apply_operation_sign_policy") as stopped_sign,
            patch.object(graph_calculation, "execute_prepared_calculation_plan") as stopped_executor,
            self.assertRaisesRegex(RuntimeError, "raw-unit repair"),
        ):
            agent._prepare_calculation_candidate(candidate_input(stop_events))
        self.assertEqual([event[0] for event in stop_events], ["table_repair", "owner_repair"])
        stopped_sign.assert_not_called()
        stopped_executor.assert_not_called()

    def test_prepare_candidate_binds_operation_sign_policy_before_execution(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        numerator = {
            "operand_id": "numerator",
            "matched_operand_role": "numerator",
            "normalized_value": 300.0,
            "normalized_unit": "KRW",
        }
        denominator = {
            "operand_id": "denominator",
            "matched_operand_role": "denominator",
            "normalized_value": -100.0,
            "normalized_unit": "KRW",
        }

        def candidate_input(*, mode: str = "scalar", operation_family: str = "ratio"):
            return graph_calculation._CalculationCandidateInput(
                calculation_operands=(deepcopy(numerator), deepcopy(denominator)),
                calculation_plan={
                    "mode": mode,
                    "operation": operation_family,
                    "ordered_operand_ids": ["numerator", "denominator"],
                    "variable_bindings": [
                        {"variable": "A", "operand_id": "numerator"},
                        {"variable": "B", "operand_id": "denominator"},
                    ],
                    "formula": "A / B",
                    "pairwise_formula": "",
                    "result_unit": "NUMBER",
                },
                active_subtask={"operation_family": operation_family, "required_operands": []},
                query="calculate the ratio",
                evidence_items=(),
                runtime_evidence=(),
            )

        def execute(**kwargs):
            ordered = tuple(
                kwargs["operands_by_id"][operand_id]
                for operand_id in kwargs["ordered_operand_ids"]
            )
            return CalculationExecutionOutcome(
                status="ok",
                reason="",
                result_value=3.0,
                normalized_unit="NUMBER",
                source_normalized_unit="NUMBER",
                ordered_operands=ordered,
                selected_evidence_ids=(),
            )

        latest_mocks = {}

        def invoke(
            owner_side_effect,
            *,
            mode: str = "scalar",
            operation_family: str = "ratio",
            period_conflict: bool = False,
        ):
            with (
                patch.object(
                    agent,
                    "_coerce_operand_row_from_evidence",
                    side_effect=lambda row, _evidence: row,
                ),
                patch.object(
                    graph_calculation,
                    "repair_krw_operand_units_from_table_metadata",
                    side_effect=lambda rows, _evidence: rows,
                ),
                patch.object(
                    graph_calculation,
                    "repair_krw_normalized_values_from_raw_units",
                    side_effect=lambda rows: rows,
                ),
                patch.object(
                    agent,
                    "_align_ratio_operands_with_sibling_table_context",
                    side_effect=lambda rows, _evidence: rows,
                ),
                patch.object(
                    graph_calculation,
                    "align_growth_operand_units_when_raw_scale_matches",
                    side_effect=lambda rows: rows,
                ),
                patch.object(
                    graph_calculation,
                    "recover_duplicate_growth_prior_operand",
                    side_effect=lambda rows, _evidence: rows,
                ),
                patch.object(
                    graph_calculation,
                    "growth_operand_periods_conflict",
                    return_value=period_conflict,
                ),
                patch.object(
                    graph_calculation,
                    "apply_operation_sign_policy",
                    side_effect=owner_side_effect,
                ) as owner,
                patch.object(graph_calculation, "guard_operation_plan", return_value={}),
                patch.object(
                    graph_calculation,
                    "repair_operand_normalization_from_rendered_unit",
                    side_effect=lambda row: row,
                ),
                patch.object(
                    graph_calculation,
                    "coerce_lookup_magnitude_record",
                    side_effect=lambda row, _evidence: row,
                ) as magnitude,
                patch.object(
                    graph_calculation,
                    "execute_prepared_calculation_plan",
                    side_effect=execute,
                ) as executor,
            ):
                latest_mocks.update(owner=owner, magnitude=magnitude, executor=executor)
                result = agent._prepare_calculation_candidate(
                    candidate_input(mode=mode, operation_family=operation_family)
                )
            return result, owner, magnitude, executor

        early, owner, magnitude, executor = invoke(
            lambda rows, **_kwargs: rows,
            operation_family="growth_rate",
            period_conflict=True,
        )
        self.assertEqual(early.status, "insufficient_operands")
        self.assertEqual(early.reason, "growth operands share the same period")
        owner.assert_not_called()
        magnitude.assert_not_called()
        executor.assert_not_called()

        equal_rows = []
        owner_inputs = []

        def equal_owner(rows, *, operation, operation_family):
            owner_inputs.append(rows)
            self.assertEqual((operation, operation_family), ("ratio", "ratio"))
            equal_rows.extend(dict(row) for row in rows)
            return equal_rows

        unchanged, owner, magnitude, executor = invoke(equal_owner)
        owner.assert_called_once()
        self.assertEqual(magnitude.call_count, 2)
        executor.assert_called_once()
        executor_operands = executor.call_args.kwargs["operands_by_id"]
        self.assertIs(executor_operands["denominator"], owner_inputs[0][1])
        self.assertIsNot(executor_operands["denominator"], equal_rows[1])
        self.assertEqual(unchanged.calculation_operands[1]["normalized_value"], -100.0)

        changed_rows = []

        def changed_owner(rows, *, operation, operation_family):
            self.assertEqual((operation, operation_family), ("ratio", "ratio"))
            changed_rows.extend(dict(row) for row in rows)
            changed_rows[1]["normalized_value"] = 100.0
            changed_rows[1]["sign_policy_applied"] = "ratio_denominator_magnitude"
            return changed_rows

        changed, owner, magnitude, executor = invoke(changed_owner)
        owner.assert_called_once()
        self.assertEqual(magnitude.call_count, 2)
        executor.assert_called_once()
        executor_operands = executor.call_args.kwargs["operands_by_id"]
        self.assertIs(executor_operands["denominator"], changed_rows[1])
        self.assertEqual(changed.calculation_operands[1]["normalized_value"], 100.0)

        with self.assertRaisesRegex(RuntimeError, "sign-owner"):
            invoke(
                lambda _rows, **_kwargs: (_ for _ in ()).throw(RuntimeError("sign-owner"))
            )
        latest_mocks["owner"].assert_called_once()
        latest_mocks["magnitude"].assert_not_called()
        latest_mocks["executor"].assert_not_called()

    def test_graph_difference_plan_adapter_preserves_percent_point_unit(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        def operand(operand_id: str, role: str, value: float) -> dict:
            return {
                "operand_id": operand_id, "label": "margin", "matched_operand_role": role,
                "normalized_value": value, "normalized_unit": "PERCENT",
            }

        state = {
            "query": "calculate the margin difference in %p",
            "active_subtask": {
                "operation_family": "difference",
                "required_operands": [
                    {"label": "margin", "role": "subtrahend"},
                    {"label": "margin", "role": "minuend"},
                ],
            },
        }
        operands = [
            operand("prior", "subtrahend", -0.1),
            operand("current", "minuend", 1.8),
        ]
        original_inputs = deepcopy((state, operands))

        plan = calculation_execution.build_runtime_deterministic_operation_plan(state, operands)

        self.assertEqual(
            (plan["ordered_operand_ids"], plan["formula"], plan["result_unit"]),
            (["current", "prior"], "A + B", "%p"),
        )
        self.assertEqual((state, operands), original_inputs)

    def test_build_deterministic_operation_plan_preserves_role_order_units_and_inputs(self) -> None:
        difference_required = [
            {"label": "cost", "role": "subtrahend"},
            {"label": "revenue", "role": "minuend"},
        ]
        difference_operands = [
            {"operand_id": "cost", "label": "cost", "normalized_value": -25.0},
            {"operand_id": "revenue", "label": "revenue", "normalized_value": 100.0},
        ]
        growth_required = [
            {"label": "prior", "role": "prior_period"},
            {"label": "current", "role": "current_period"},
        ]
        growth_operands = [
            {"operand_id": "prior", "label": "prior", "normalized_value": 100.0},
            {"operand_id": "current", "label": "current", "normalized_value": 120.0},
        ]
        inputs = (difference_required, difference_operands, growth_required, growth_operands)
        original_inputs = deepcopy(inputs)

        difference = build_deterministic_operation_plan(
            operation_family="difference",
            required_operands=difference_required,
            operands=difference_operands,
            metric_label="margin change",
            difference_result_unit="%p",
        )
        growth = build_deterministic_operation_plan(
            operation_family="growth_rate",
            required_operands=growth_required,
            operands=growth_operands,
            metric_label="revenue growth",
            difference_result_unit="ignored",
        )

        self.assertEqual(
            (difference["ordered_operand_ids"], difference["formula"], difference["result_unit"]),
            (["revenue", "cost"], "A + B", "%p"),
        )
        self.assertEqual(
            (growth["ordered_operand_ids"], growth["formula"], growth["result_unit"]),
            (["current", "prior"], "((A - B) / B) * 100", "%"),
        )
        for operation_family, required_operands, operands in (
            ("ratio", difference_required, difference_operands),
            ("growth_rate", [], growth_operands),
            ("growth_rate", growth_required, growth_operands[:1]),
        ):
            self.assertIsNone(
                build_deterministic_operation_plan(
                    operation_family=operation_family,
                    required_operands=required_operands,
                    operands=operands,
                    metric_label="metric",
                    difference_result_unit="",
                )
            )
        self.assertEqual(inputs, original_inputs)

    def test_resolve_deterministic_operation_plan_types_ready_guarded_and_not_applicable(self) -> None:
        operands = [{"operand_id": "current"}, {"operand_id": "prior"}]
        plan = {
            "status": "ok",
            "operation": "subtract",
            "ordered_operand_ids": ["current", "prior"],
            "variable_bindings": [
                {"variable": "A", "operand_id": "current"},
                {"variable": "B", "operand_id": "prior"},
            ],
        }
        original_inputs = deepcopy((plan, operands))
        ready = resolve_deterministic_operation_plan(
            plan=plan,
            operands=operands,
            required_operands=[],
            operation_family="difference",
        )
        invalid_plan = {
            **plan,
            "ordered_operand_ids": ["current"],
            "variable_bindings": [{"variable": "A", "operand_id": "current"}],
        }
        guarded = resolve_deterministic_operation_plan(
            plan=invalid_plan,
            operands=operands,
            required_operands=[],
            operation_family="difference",
        )
        not_applicable = resolve_deterministic_operation_plan(
            plan={},
            operands=operands,
            required_operands=[],
            operation_family="difference",
        )

        self.assertEqual(ready.status, "ready")
        self.assertEqual(ready.raw_plan, plan)
        self.assertEqual(ready.selected_plan, plan)
        self.assertEqual(guarded.status, "guarded")
        self.assertEqual(guarded.raw_plan, invalid_plan)
        self.assertEqual(guarded.selected_plan["status"], "incomplete")
        self.assertEqual(
            not_applicable,
            DeterministicOperationPlanDecision(
                status="not_applicable",
                raw_plan={},
                selected_plan={},
            ),
        )
        self.assertEqual((plan, operands), original_inputs)

    def test_assess_stale_calculation_value_classifies_current_stale_and_nan_without_mutation(self) -> None:
        current_result = {"status": "ok", "result_value": 750.0}
        original_result = deepcopy(current_result)

        current = assess_stale_calculation_value(
            expected_value=750.0,
            calculation_result=current_result,
        )
        stale = assess_stale_calculation_value(
            expected_value=750.0,
            calculation_result={**current_result, "result_value": 990.0},
        )
        nan_current = assess_stale_calculation_value(
            expected_value=750.0,
            calculation_result={**current_result, "result_value": float("nan")},
        )
        nan_expected = assess_stale_calculation_value(
            expected_value=float("nan"),
            calculation_result=current_result,
        )
        scaled_tolerance = assess_stale_calculation_value(
            expected_value=2_000_000.0,
            calculation_result={"result_value": 2_000_000.001},
        )

        self.assertEqual(
            current,
            StaleCalculationValueAssessment(
                is_stale=False,
                reason="current",
                expected_value=750.0,
                current_value=750.0,
                tolerance=1e-6,
            ),
        )
        self.assertEqual(
            stale,
            StaleCalculationValueAssessment(
                is_stale=True,
                reason="stale",
                expected_value=750.0,
                current_value=990.0,
                tolerance=1e-6,
            ),
        )
        self.assertTrue(nan_current.is_stale)
        self.assertEqual(nan_current.reason, "stale")
        self.assertTrue(nan_expected.is_stale)
        self.assertEqual(nan_expected.reason, "stale")
        self.assertFalse(scaled_tolerance.is_stale)
        self.assertEqual(scaled_tolerance.tolerance, 0.002)
        self.assertEqual(current_result, original_result)

    def test_assess_stale_calculation_value_uses_formula_trace_only_for_source_stated_result(self) -> None:
        source_stated = assess_stale_calculation_value(
            expected_value=750.0,
            calculation_result={
                "result_value": 800.0,
                "derived_metrics": {
                    "formula_result_value": 750.0,
                    "source_stated_result_used": True,
                },
            },
        )
        ordinary = assess_stale_calculation_value(
            expected_value=750.0,
            calculation_result={
                "result_value": 800.0,
                "derived_metrics": {
                    "formula_result_value": 750.0,
                    "source_stated_result_used": False,
                },
            },
        )

        self.assertFalse(source_stated.is_stale)
        self.assertEqual(source_stated.reason, "current")
        self.assertEqual(source_stated.current_value, 750.0)
        self.assertTrue(ordinary.is_stale)
        self.assertEqual(ordinary.reason, "stale")
        self.assertEqual(ordinary.current_value, 800.0)

    def test_assess_stale_calculation_value_classifies_unavailable_values(self) -> None:
        expected_unavailable = assess_stale_calculation_value(
            expected_value=None,
            calculation_result={"result_value": 2.0},
        )
        current_unavailable = assess_stale_calculation_value(
            expected_value=2.0,
            calculation_result={"result_value": None},
        )

        self.assertEqual(
            expected_unavailable,
            StaleCalculationValueAssessment(
                is_stale=False,
                reason="expected_value_unavailable",
            ),
        )
        self.assertEqual(
            current_unavailable,
            StaleCalculationValueAssessment(
                is_stale=False,
                reason="current_value_unavailable",
                expected_value=2.0,
            ),
        )

    def test_guard_operation_plan_accepts_distinct_ratio_bindings(self) -> None:
        guarded_plan = guard_operation_plan(
            plan={
                "operation": "ratio",
                "ordered_operand_ids": ["op_num", "op_den"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "op_num"},
                    {"variable": "B", "operand_id": "op_den"},
                ],
            },
            operands=[
                {
                    "operand_id": "op_num",
                    "matched_operand_role": "numerator_1",
                    "matched_operand_label": "segment operating income",
                    "normalized_value": 100.0,
                    "evidence_id": "row_num",
                },
                {
                    "operand_id": "op_den",
                    "matched_operand_role": "denominator_1",
                    "matched_operand_label": "total operating income",
                    "normalized_value": 200.0,
                    "evidence_id": "row_den",
                },
            ],
            required_operands=[
                {"label": "segment operating income", "role": "numerator_1", "required": True},
                {"label": "total operating income", "role": "denominator_1", "required": True},
            ],
            operation_family="ratio",
        )

        self.assertIsNone(guarded_plan)

    def test_guard_operation_plan_uses_variable_bindings_when_ordered_ids_are_absent(self) -> None:
        guarded_plan = guard_operation_plan(
            plan={
                "operation": "difference",
                "ordered_operand_ids": [],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "current"},
                    {"variable": "B", "operand_id": "prior"},
                ],
            },
            operands=[
                {"operand_id": "current", "normalized_value": 30.0},
                {"operand_id": "prior", "normalized_value": 20.0},
            ],
            required_operands=[],
            operation_family="difference",
        )

        self.assertIsNone(guarded_plan)

    def test_guard_operation_plan_rejects_ratio_roles_sharing_source_value(self) -> None:
        guarded_plan = guard_operation_plan(
            plan={
                "operation": "ratio",
                "ordered_operand_ids": ["op_num", "op_den"],
                "variable_bindings": [
                    {"variable": "A", "operand_id": "op_num"},
                    {"variable": "B", "operand_id": "op_den"},
                ],
            },
            operands=[
                {
                    "operand_id": "op_num",
                    "matched_operand_role": "numerator_1",
                    "matched_operand_label": "segment operating income",
                    "raw_value": "100",
                    "raw_unit": "million",
                    "normalized_value": 100_000_000.0,
                    "evidence_id": "row_same",
                },
                {
                    "operand_id": "op_den",
                    "matched_operand_role": "denominator_1",
                    "matched_operand_label": "total operating income",
                    "raw_value": "100",
                    "raw_unit": "million",
                    "normalized_value": 100_000_000.0,
                    "evidence_id": "row_same",
                },
            ],
            required_operands=[
                {"label": "segment operating income", "role": "numerator_1", "required": True},
                {"label": "total operating income", "role": "denominator_1", "required": True},
            ],
            operation_family="ratio",
        )

        self.assertEqual(
            guarded_plan,
            {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": "operation plan does not satisfy required operand bindings",
                "missing_info": ["distinct_ratio_roles"],
            },
        )

    def test_calculation_result_schema_accepts_runtime_scale_mismatch_status(self) -> None:
        result = CalculationResult(status="scale_mismatch")

        self.assertEqual(result.status, "scale_mismatch")

    def test_execute_prepared_calculation_plan_runs_scalar_formula_without_graph_state(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="subtract",
            formula="A - B",
            pairwise_formula="",
            result_unit="KRW",
            operands_by_id={
                "current": {
                    "operand_id": "current",
                    "normalized_value": 30.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_current",
                },
                "prior": {
                    "operand_id": "prior",
                    "normalized_value": 20.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_prior",
                },
                "distractor": {
                    "operand_id": "distractor",
                    "normalized_value": 999.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_distractor",
                },
            },
            ordered_operand_ids=["current", "prior"],
            variable_bindings=[
                {"variable": "A", "operand_id": "current"},
                {"variable": "B", "operand_id": "prior"},
            ],
        )

        self.assertEqual(outcome.status, "ok")
        self.assertEqual(outcome.result_value, 10.0)
        self.assertEqual(outcome.normalized_unit, "KRW")
        self.assertEqual(outcome.source_normalized_unit, "KRW")
        self.assertEqual(outcome.selected_evidence_ids, ("ev_current", "ev_prior"))

    def test_execute_prepared_calculation_plan_rejects_divergent_operand_sets_without_mutation(
        self,
    ) -> None:
        operands_by_id = {
            "left": {
                "operand_id": "left",
                "normalized_value": 30.0,
                "normalized_unit": "KRW",
                "evidence_id": "ev_left",
            },
            "right": {
                "operand_id": "right",
                "normalized_value": 2.0,
                "normalized_unit": "COUNT",
                "evidence_id": "ev_right",
            },
        }
        ordered_operand_ids = ["left"]
        variable_bindings = [
            {"variable": "A", "operand_id": "left"},
            {"variable": "B", "operand_id": "right"},
        ]
        original_operands = deepcopy(operands_by_id)
        original_ordered_ids = list(ordered_operand_ids)
        original_bindings = deepcopy(variable_bindings)

        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="sum",
            formula="A + B",
            pairwise_formula="",
            result_unit="",
            operands_by_id=operands_by_id,
            ordered_operand_ids=ordered_operand_ids,
            variable_bindings=variable_bindings,
        )

        self.assertEqual(outcome.status, "parse_error")
        self.assertEqual(operands_by_id, original_operands)
        self.assertEqual(ordered_operand_ids, original_ordered_ids)
        self.assertEqual(variable_bindings, original_bindings)

    def test_graph_adapter_projects_executor_failures_only_to_canonical_trace(self) -> None:
        statuses = (
            "insufficient_operands",
            "unit_mismatch",
            "zero_division",
            "parse_error",
        )
        operand = {
            "operand_id": "value",
            "evidence_id": "ev_value",
            "label": "value",
            "raw_value": "10",
            "raw_unit": "",
            "normalized_value": 10.0,
            "normalized_unit": "COUNT",
            "matched_operand_role": "primary_value",
        }
        plan = {
            "status": "ok",
            "mode": "single_value",
            "operation": "lookup",
            "ordered_operand_ids": ["value"],
            "variable_bindings": [{"variable": "A", "operand_id": "value"}],
            "formula": "A",
            "pairwise_formula": "",
            "result_unit": "",
        }
        state = {
            "query": "Return the supported value.",
            "active_subtask": {
                "task_id": "task_lookup",
                "metric_family": "concept_lookup",
                "metric_label": "value",
                "operation_family": "lookup",
            },
            "resolved_calculation_trace": {
                "calculation_operands": [operand],
                "calculation_plan": plan,
                "calculation_result": {},
            },
            "evidence_items": [],
            "runtime_evidence": [],
            "tasks": [],
            "artifacts": [],
        }
        agent = FinancialAgent.__new__(FinancialAgent)

        for status in statuses:
            with self.subTest(status=status):
                original_state = deepcopy(state)
                execution_outcome = CalculationExecutionOutcome(
                    status=status,
                    reason=f"{status} from deterministic executor",
                    result_value=None,
                    normalized_unit="",
                    source_normalized_unit="COUNT",
                    ordered_operands=(deepcopy(operand),),
                    selected_evidence_ids=("ev_value",),
                )
                with (
                    patch(
                        "src.agent.financial_graph_calculation.execute_prepared_calculation_plan",
                        return_value=execution_outcome,
                    ) as executor,
                    patch.object(
                        agent,
                        "_prepare_calculation_candidate",
                        wraps=agent._prepare_calculation_candidate,
                    ) as candidate_preparation,
                    patch.object(
                        agent,
                        "_project_prepared_calculation_candidate",
                        wraps=agent._project_prepared_calculation_candidate,
                    ) as candidate_projection,
                    patch.object(
                        agent,
                        "_project_calculation_candidate_state",
                        wraps=agent._project_calculation_candidate_state,
                    ) as state_projection,
                ):
                    result = agent._execute_calculation(state)

                executor.assert_called_once()
                candidate_preparation.assert_called_once()
                candidate_projection.assert_called_once()
                state_projection.assert_called_once()
                trace = result["resolved_calculation_trace"]
                self.assertEqual(trace["calculation_result"]["status"], status)
                self.assertEqual(
                    trace["calculation_result"]["explanation"],
                    execution_outcome.reason,
                )
                self.assertEqual(trace["calculation_plan"], plan)
                self.assertEqual(result["selected_claim_ids"], ["ev_value"])
                self.assertNotIn("calculation_operands", result)
                self.assertNotIn("calculation_plan", result)
                self.assertNotIn("calculation_result", result)
                self.assertEqual(state, original_state)

    def test_execute_prepared_calculation_plan_sorts_time_series_and_projects_growth_rates(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="time_series",
            operation="time_series_trend",
            formula="CURRENT - PRIOR",
            pairwise_formula="((CURR - PREV) / PREV) * 100",
            result_unit="KRW",
            operands_by_id={
                "current": {
                    "operand_id": "current",
                    "period": "2024",
                    "normalized_value": 115.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_current",
                },
                "prior": {
                    "operand_id": "prior",
                    "period": "2023",
                    "normalized_value": 100.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_prior",
                },
            },
            ordered_operand_ids=["current", "prior"],
            variable_bindings=[
                {"variable": "CURRENT", "operand_id": "current"},
                {"variable": "PRIOR", "operand_id": "prior"},
            ],
        )

        self.assertEqual(outcome.status, "ok")
        self.assertEqual(outcome.result_value, 15.0)
        self.assertEqual([row["period"] for row in outcome.ordered_operands], ["2023", "2024"])
        self.assertEqual(outcome.selected_evidence_ids, ("ev_prior", "ev_current"))
        self.assertEqual(outcome.yoy_growth_rates, (None, 15.0))

    def test_execute_prepared_calculation_plan_rejects_mixed_unit_families(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="ratio",
            formula="(A / B) * 100",
            pairwise_formula="",
            result_unit="%",
            operands_by_id={
                "numerator": {
                    "normalized_value": 10.0,
                    "normalized_unit": "KRW",
                    "evidence_id": "ev_numerator",
                },
                "denominator": {
                    "normalized_value": 20.0,
                    "normalized_unit": "COUNT",
                    "evidence_id": "ev_denominator",
                },
            },
            ordered_operand_ids=["numerator", "denominator"],
            variable_bindings=[
                {"variable": "A", "operand_id": "numerator"},
                {"variable": "B", "operand_id": "denominator"},
            ],
        )

        self.assertEqual(outcome.status, "unit_mismatch")
        self.assertIn("unit families differ", outcome.reason)
        self.assertIsNone(outcome.result_value)
        self.assertEqual(outcome.selected_evidence_ids, ("ev_numerator", "ev_denominator"))

    def test_execute_prepared_calculation_plan_classifies_zero_division(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="ratio",
            formula="A / B",
            pairwise_formula="",
            result_unit="%",
            operands_by_id={
                "numerator": {"normalized_value": 10.0, "normalized_unit": "KRW"},
                "denominator": {"normalized_value": 0.0, "normalized_unit": "KRW"},
            },
            ordered_operand_ids=["numerator", "denominator"],
            variable_bindings=[
                {"variable": "A", "operand_id": "numerator"},
                {"variable": "B", "operand_id": "denominator"},
            ],
        )

        self.assertEqual(outcome.status, "zero_division")
        self.assertIsNone(outcome.result_value)

    def test_execute_prepared_calculation_plan_requires_scalar_formula(self) -> None:
        outcome = execute_prepared_calculation_plan(
            mode="single_value",
            operation="lookup",
            formula="",
            pairwise_formula="",
            result_unit="KRW",
            operands_by_id={
                "value": {"normalized_value": 10.0, "normalized_unit": "KRW"},
            },
            ordered_operand_ids=["value"],
            variable_bindings=[{"variable": "A", "operand_id": "value"}],
        )

        self.assertEqual(outcome.status, "parse_error")
        self.assertEqual(outcome.reason, "missing scalar formula")

    def test_build_failed_calculation_result_uses_missing_primary_slot_without_operands(self) -> None:
        result = build_failed_calculation_result(
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
            runtime_operands=[],
            result_unit="",
            source_normalized_unit="UNKNOWN",
            status="insufficient_operands",
            reason="no operation or operands",
        )

        self.assertEqual(result["status"], "insufficient_operands")
        self.assertEqual(result["result_value"], None)
        self.assertEqual(result["series"], [])
        self.assertEqual(result["explanation"], "no operation or operands")
        self.assertEqual(result["answer_slots"]["operation_family"], "lookup")
        self.assertEqual(result["answer_slots"]["primary_value"]["status"], "missing")
        self.assertEqual(result["answer_slots"]["primary_value"]["concept"], "income_before_income_taxes")

    def test_build_failed_calculation_result_preserves_operand_components_when_available(self) -> None:
        result = build_failed_calculation_result(
            active_subtask={"operation_family": "ratio", "metric_label": "ratio"},
            operation_family="ratio",
            runtime_operands=[
                {
                    "operand_id": "op_1",
                    "label": "분자",
                    "matched_operand_role": "numerator",
                    "raw_value": "10",
                    "raw_unit": "%",
                    "normalized_value": 10.0,
                    "normalized_unit": "PERCENT",
                    "evidence_id": "ev_1",
                }
            ],
            result_unit="%",
            source_normalized_unit="PERCENT",
            status="unit_mismatch",
            reason="unit families differ",
        )

        self.assertEqual(result["status"], "unit_mismatch")
        self.assertEqual(result["answer_slots"]["components_by_role"]["numerator"][0]["source_row_id"], "ev_1")

    def test_build_success_calculation_state_payload_appends_result_artifact_and_trace(self) -> None:
        payload = build_success_calculation_state_payload(
            state={
                "active_subtask": {"task_id": "task_1", "metric_label": "Metric"},
                "tasks": [],
                "artifacts": [],
            },
            calc_result={
                "status": "ok",
                "result_value": 1.0,
                "rendered_value": "1",
                "formatted_result": "",
            },
            selected_evidence_ids=["ev_1"],
            runtime_operands=[{"operand_id": "op_1", "normalized_value": 1.0}],
            calculation_plan={"mode": "single_value", "formula": "A"},
            query="query",
            metric_family="metric",
        )

        self.assertEqual(payload["answer"], "")
        self.assertEqual(payload["selected_claim_ids"], ["ev_1"])
        self.assertEqual(payload["kept_claim_ids"], ["ev_1"])
        self.assertEqual(payload["artifacts"][0]["artifact_id"], "result:task_1:001")
        self.assertEqual(payload["artifacts"][0]["kind"], "calculation_result")
        self.assertEqual(payload["artifacts"][0]["payload"]["calculation_result"]["rendered_value"], "1")
        self.assertEqual(payload["tasks"][0]["task_id"], "task_1")
        self.assertEqual(payload["tasks"][0]["artifact_ids"], ["result:task_1:001"])
        trace = payload["resolved_calculation_trace"]
        self.assertEqual(trace["calculation_operands"][0]["operand_id"], "op_1")
        self.assertEqual(trace["calculation_plan"]["formula"], "A")
        self.assertEqual(trace["calculation_result"]["result_value"], 1.0)

    def test_build_success_calculation_state_payload_upserts_existing_task(self) -> None:
        payload = build_success_calculation_state_payload(
            state={
                "active_subtask": {"task_id": "task_1", "metric_label": "Metric"},
                "tasks": [
                    {
                        "task_id": "task_1",
                        "kind": "calculation",
                        "label": "Metric",
                        "status": "in_progress",
                        "query": "old query",
                        "metric_family": "old metric",
                        "constraints": {},
                        "artifact_ids": ["artifact:operand_set"],
                        "notes": [],
                    }
                ],
                "artifacts": [{"artifact_id": "artifact:operand_set"}],
            },
            calc_result={"status": "ok", "rendered_value": "2", "formatted_result": ""},
            selected_evidence_ids=[],
            runtime_operands=[],
            calculation_plan={},
            query="new query",
            metric_family="new metric",
        )

        self.assertEqual(payload["artifacts"][1]["artifact_id"], "result:task_1:002")
        self.assertEqual(payload["tasks"][0]["query"], "new query")
        self.assertEqual(payload["tasks"][0]["metric_family"], "new metric")
        self.assertEqual(payload["tasks"][0]["artifact_ids"], ["artifact:operand_set", "result:task_1:002"])

    def test_build_scalar_calculation_state_sets_lookup_current_value(self) -> None:
        state = build_scalar_calculation_state(
            operation_family="lookup",
            ordered_operands=[
                {
                    "evidence_id": "ev_1",
                    "source_row_ids": ["row_1"],
                    "normalized_value": 10.0,
                    "period": "p1",
                }
            ],
            result_value=10.0,
            normalized_unit="COUNT",
            result_unit="",
            rendered_with_unit="10",
        )

        self.assertEqual(state["current_value"], 10.0)
        self.assertEqual(state["current_period"], "p1")
        self.assertEqual(state["source_row_ids"], ["ev_1", "row_1"])
        self.assertFalse(state["source_stated_result_used"])

    def test_build_scalar_calculation_state_sets_difference_period_components(self) -> None:
        state = build_scalar_calculation_state(
            operation_family="difference",
            ordered_operands=[
                {
                    "matched_operand_role": "current_period",
                    "normalized_value": 30.0,
                    "period": "current",
                    "evidence_id": "ev_current",
                },
                {
                    "matched_operand_role": "prior_period",
                    "normalized_value": 20.0,
                    "period": "prior",
                    "evidence_id": "ev_prior",
                },
            ],
            result_value=10.0,
            normalized_unit="COUNT",
            result_unit="",
            rendered_with_unit="10",
        )

        self.assertEqual(state["current_value"], 30.0)
        self.assertEqual(state["prior_value"], 20.0)
        self.assertEqual(state["delta_value"], 10.0)
        self.assertEqual(state["current_period"], "current")
        self.assertEqual(state["prior_period"], "prior")
        self.assertEqual(state["source_row_ids"], ["ev_current", "ev_prior"])

    def test_build_scalar_calculation_state_preserves_source_stated_growth_display(self) -> None:
        state = build_scalar_calculation_state(
            operation_family="growth_rate",
            ordered_operands=[
                {
                    "matched_operand_role": "current_period",
                    "normalized_value": 112.0,
                    "period": "current",
                    "stated_change_raw_value": "12.3",
                    "stated_change_raw_unit": "%",
                },
                {
                    "matched_operand_role": "prior_period",
                    "normalized_value": 100.0,
                    "period": "prior",
                },
            ],
            result_value=12.0,
            normalized_unit="PERCENT",
            result_unit="%",
            rendered_with_unit="12%",
        )

        self.assertEqual(state["result_value"], 12.3)
        self.assertEqual(state["normalized_unit"], "PERCENT")
        self.assertEqual(state["result_unit"], "%")
        self.assertEqual(state["rendered_with_unit"], "12.3%")
        self.assertTrue(state["source_stated_result_used"])
        self.assertEqual(state["current_value"], 112.0)
        self.assertEqual(state["prior_value"], 100.0)

    def test_build_scalar_calculation_result_projects_state_slots_and_metrics(self) -> None:
        result = build_scalar_calculation_result(
            result_value=12.3,
            result_unit="%",
            rendered_with_unit="12.3%",
            result_series=[{"label": "current", "normalized_value": 112.0}],
            scalar_state={
                "current_value": 112.0,
                "prior_value": 100.0,
                "delta_value": None,
                "current_period": "current",
                "prior_period": "prior",
                "source_row_ids": ["ev_1"],
                "source_stated_result_used": True,
            },
            answer_slots={"operation_family": "growth_rate"},
            operand_labels=["current", "prior"],
            formula="((A - B) / B) * 100",
            operation_family="growth_rate",
            operation="growth_rate",
            formula_result_value=12.0,
            explanation="calculated",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result_value"], 12.3)
        self.assertEqual(result["result_unit"], "%")
        self.assertEqual(result["rendered_value"], "12.3%")
        self.assertEqual(result["series"][0]["label"], "current")
        self.assertEqual(result["current_value"], 112.0)
        self.assertEqual(result["prior_value"], 100.0)
        self.assertEqual(result["current_period"], "current")
        self.assertEqual(result["source_row_ids"], ["ev_1"])
        self.assertEqual(result["answer_slots"]["operation_family"], "growth_rate")
        self.assertEqual(result["derived_metrics"]["operand_labels"], ["current", "prior"])
        self.assertEqual(result["derived_metrics"]["formula"], "((A - B) / B) * 100")
        self.assertEqual(result["derived_metrics"]["operation_family"], "growth_rate")
        self.assertEqual(result["derived_metrics"]["formula_result_value"], 12.0)
        self.assertTrue(result["derived_metrics"]["source_stated_result_used"])
        self.assertEqual(result["explanation"], "calculated")

    def test_build_time_series_calculation_result_projects_series_slots_and_metrics(self) -> None:
        result = build_time_series_calculation_result(
            result_value=15.0,
            result_unit="%",
            rendered_value="15.0%",
            result_series=[
                {"label": "p1", "normalized_value": 100.0},
                {"label": "p2", "normalized_value": 115.0},
            ],
            operation_family="trend",
            operation="time_series_trend",
            metric_name="Metric",
            normalized_unit="PERCENT",
            yoy_growth_rates=[None, 15.0],
            formula="((B - A) / A) * 100",
            pairwise_formula="((CURR - PREV) / PREV) * 100",
            explanation="calculated trend",
        )

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["result_value"], 15.0)
        self.assertEqual(result["result_unit"], "%")
        self.assertEqual(result["rendered_value"], "15.0%")
        self.assertEqual(result["series"][1]["label"], "p2")
        self.assertEqual(result["answer_slots"]["operation_family"], "trend")
        self.assertEqual(result["answer_slots"]["metric_label"], "Metric")
        self.assertEqual(result["answer_slots"]["primary_value"]["normalized_value"], 15.0)
        self.assertEqual(result["answer_slots"]["primary_value"]["normalized_unit"], "PERCENT")
        self.assertEqual(result["answer_slots"]["primary_value"]["rendered_value"], "15%")
        self.assertEqual(result["derived_metrics"]["metric_name"], "Metric")
        self.assertEqual(result["derived_metrics"]["yoy_growth_rates"], [None, 15.0])
        self.assertEqual(result["derived_metrics"]["formula"], "((B - A) / A) * 100")
        self.assertEqual(result["derived_metrics"]["pairwise_formula"], "((CURR - PREV) / PREV) * 100")
        self.assertEqual(result["explanation"], "calculated trend")

    def test_time_series_yoy_growth_rates_evaluates_pairwise_formula(self) -> None:
        rates = time_series_yoy_growth_rates(
            ordered_operands=[
                {"normalized_value": 100.0},
                {"normalized_value": 115.0},
                {"normalized_value": 138.0},
            ],
            pairwise_formula="((CURR - PREV) / PREV) * 100",
        )

        self.assertEqual(rates, [None, 15.0, 20.0])

    def test_time_series_yoy_growth_rates_keeps_none_for_zero_division(self) -> None:
        rates = time_series_yoy_growth_rates(
            ordered_operands=[
                {"normalized_value": 0.0},
                {"normalized_value": 10.0},
            ],
            pairwise_formula="((CURR - PREV) / PREV) * 100",
        )

        self.assertEqual(rates, [None, None])

    def test_time_series_yoy_growth_rates_without_formula_returns_initial_gap(self) -> None:
        rates = time_series_yoy_growth_rates(
            ordered_operands=[
                {"normalized_value": 100.0},
                {"normalized_value": 115.0},
            ],
            pairwise_formula="",
        )

        self.assertEqual(rates, [None])

    def test_current_source_runtime_plan_adapter_pins_task_fallback_copy_and_laziness(self) -> None:
        target = calculation_execution.build_runtime_deterministic_operation_plan
        shared = {"nested": True}
        operands = [{"operand_id": "op", "nested": shared}]
        explicit_task = {
            "operation_family": " SUM ",
            "required_operands": [
                {"label": "kept", "required": True, "nested": shared},
                {"label": "dropped", "required": False},
            ],
            "metric_label": "",
            "task_id": " task-fallback ",
            "nested": shared,
        }
        explicit_before = deepcopy(explicit_task)
        operands_before = deepcopy(operands)

        class StateBomb(Mapping):
            def __getitem__(self, key):
                raise RuntimeError(f"state item accessed: {key}")

            def __iter__(self):
                raise RuntimeError("state iterated")

            def __len__(self):
                raise RuntimeError("state sized")

            def get(self, key, default=None):
                raise RuntimeError(f"state get accessed: {key}")

        base_plan = {"status": "ok", "nested": shared}
        with (
            patch.object(
                calculation_execution,
                "build_deterministic_operation_plan",
                return_value=base_plan,
            ) as base_owner,
            patch.object(
                calculation_execution,
                "should_coerce_percent_point_unit",
                side_effect=RuntimeError("percent policy must stay lazy"),
            ) as percent_policy,
        ):
            result = target(
                StateBomb(),
                operands,
                active_subtask=explicit_task,
            )

        self.assertIs(result, base_plan)
        base_owner.assert_called_once()
        kwargs = base_owner.call_args.kwargs
        self.assertEqual(
            kwargs,
            {
                "operation_family": "sum",
                "required_operands": [
                    {"label": "kept", "required": True, "nested": shared}
                ],
                "operands": operands,
                "metric_label": "task-fallback",
                "difference_result_unit": "",
            },
        )
        self.assertIs(kwargs["operands"], operands)
        self.assertIsNot(kwargs["required_operands"][0], explicit_task["required_operands"][0])
        self.assertIs(kwargs["required_operands"][0]["nested"], shared)
        percent_policy.assert_not_called()
        self.assertEqual(explicit_task, explicit_before)
        self.assertEqual(operands, operands_before)
        self.assertIs(explicit_task["nested"], shared)
        self.assertIs(operands[0]["nested"], shared)

        state_task = {
            "operation_family": " growth_rate ",
            "required_operands": [{"label": "current"}],
            "metric_label": " metric ",
        }
        state = {"query": "state query", "active_subtask": state_task}
        state_before = deepcopy(state)
        fallback_plan = {"status": "ok"}
        with (
            patch.object(
                calculation_execution,
                "build_deterministic_operation_plan",
                return_value=fallback_plan,
            ) as fallback_owner,
            patch.object(
                calculation_execution,
                "should_coerce_percent_point_unit",
            ) as fallback_policy,
        ):
            fallback = target(state, operands)
        self.assertIs(fallback, fallback_plan)
        self.assertEqual(fallback_owner.call_args.kwargs["operation_family"], "growth_rate")
        self.assertEqual(fallback_owner.call_args.kwargs["metric_label"], "metric")
        self.assertIsNot(
            fallback_owner.call_args.kwargs["required_operands"][0],
            state_task["required_operands"][0],
        )
        fallback_policy.assert_not_called()
        self.assertEqual(state, state_before)

        later_policy = Mock()
        with (
            patch.object(
                calculation_execution,
                "build_deterministic_operation_plan",
                side_effect=RuntimeError("base plan failed"),
            ),
            patch.object(
                calculation_execution,
                "should_coerce_percent_point_unit",
                later_policy,
            ),
            self.assertRaisesRegex(RuntimeError, "base plan failed"),
        ):
            target(state, operands)
        later_policy.assert_not_called()

    def test_current_source_runtime_plan_adapter_pins_difference_query_and_exception_order(self) -> None:
        target = calculation_execution.build_runtime_deterministic_operation_plan
        shared = {"nested": True}
        operands = [{"operand_id": "current", "nested": shared}]
        plan = {"status": "ok", "result_unit": "%", "nested": shared}
        task = {
            "operation_family": " Difference ",
            "query": " task query ",
            "required_operands": [],
        }
        state_events = []

        class RecordingState(dict):
            def __getitem__(self, key):
                state_events.append(("item", key))
                return super().__getitem__(key)

        state = RecordingState(query="state query", active_subtask=task)
        state_before = deepcopy(dict(state))
        events = []

        def base_owner(**kwargs):
            events.append("base")
            self.assertEqual(kwargs["operation_family"], "difference")
            self.assertIs(kwargs["operands"], operands)
            return plan

        def percent_owner(query, owner_operands, owner_plan):
            events.append("percent")
            self.assertEqual(query, " task query ")
            self.assertIs(owner_operands, operands)
            self.assertIs(owner_plan, plan)
            return True

        with (
            patch.object(
                calculation_execution,
                "build_deterministic_operation_plan",
                side_effect=base_owner,
            ),
            patch.object(
                calculation_execution,
                "should_coerce_percent_point_unit",
                side_effect=percent_owner,
            ),
        ):
            changed = target(state, operands)

        self.assertEqual(events, ["base", "percent"])
        self.assertEqual(state_events, [])
        self.assertIsNot(changed, plan)
        self.assertEqual(changed["result_unit"], "%p")
        self.assertIs(changed["nested"], shared)
        self.assertEqual(plan["result_unit"], "%")
        self.assertEqual(dict(state), state_before)
        self.assertIs(operands[0]["nested"], shared)

        task_without_query = {**task, "query": ""}
        fallback_state = RecordingState(query="fallback query", active_subtask=task_without_query)
        state_events.clear()
        with (
            patch.object(
                calculation_execution,
                "build_deterministic_operation_plan",
                return_value=plan,
            ),
            patch.object(
                calculation_execution,
                "should_coerce_percent_point_unit",
                return_value=False,
            ) as policy,
        ):
            unchanged = target(fallback_state, operands)
        self.assertIs(unchanged, plan)
        self.assertEqual(state_events, [("item", "query")])
        policy.assert_called_once_with("fallback query", operands, plan)

        for returned_plan in ({}, None):
            with (
                patch.object(
                    calculation_execution,
                    "build_deterministic_operation_plan",
                    return_value=returned_plan,
                ),
                patch.object(
                    calculation_execution,
                    "should_coerce_percent_point_unit",
                    side_effect=RuntimeError("policy must stay lazy"),
                ) as lazy_policy,
            ):
                result = target(fallback_state, operands)
            self.assertIs(result, returned_plan)
            lazy_policy.assert_not_called()

        downstream = Mock()
        with (
            patch.object(
                calculation_execution,
                "build_deterministic_operation_plan",
                return_value=plan,
            ),
            patch.object(
                calculation_execution,
                "should_coerce_percent_point_unit",
                side_effect=RuntimeError("percent policy failed"),
            ),
            patch("builtins.dict", wraps=dict) as dict_owner,
            self.assertRaisesRegex(RuntimeError, "percent policy failed"),
        ):
            target(fallback_state, operands)
        downstream.assert_not_called()
        self.assertGreaterEqual(dict_owner.call_count, 1)

    def test_current_source_runtime_plan_adapter_pins_static_binding_dag_and_dead_import(self) -> None:
        from src.ops.audit_runtime_domain_terms import collect_runtime_domain_term_occurrences

        graph_path = Path(graph_calculation.__file__)
        owner_path = Path("src/agent/financial_calculation_execution.py")
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        private_name = "_build_deterministic_operation_plan"
        public_name = "build_runtime_deterministic_operation_plan"
        definition = next(
            node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == public_name
        )
        self.assertEqual(definition.end_lineno - definition.lineno + 1, 36)
        self.assertEqual(
            [argument.arg for argument in definition.args.args],
            ["state", "operands"],
        )
        self.assertEqual(
            [argument.arg for argument in definition.args.kwonlyargs],
            ["active_subtask"],
        )
        self.assertEqual(
            [
                node
                for node in ast.walk(graph_tree)
                if isinstance(node, ast.FunctionDef) and node.name == private_name
            ],
            [],
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
                name = (
                    node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else node.func.id
                    if isinstance(node.func, ast.Name)
                    else ""
                )
                if name in {private_name, public_name}:
                    self.calls.append(
                        (
                            self.stack[-1],
                            name,
                            ast.unparse(node.func.value) if isinstance(node.func, ast.Attribute) else "",
                            [ast.unparse(argument) for argument in node.args],
                            [(keyword.arg, ast.unparse(keyword.value)) for keyword in node.keywords],
                            self.try_depth,
                        )
                    )
                self.generic_visit(node)

        visitor = BindingVisitor()
        visitor.visit(graph_tree)
        self.assertEqual(
            visitor.calls,
            [
                (
                    "_recalculate_row_from_source_slots",
                    public_name,
                    "",
                    ["state", "updated_operands"],
                    [("active_subtask", "active_subtask")],
                    0,
                ),
                (
                    "_realign_period_comparison_results_from_table_label_context",
                    public_name,
                    "",
                    ["plan_state", "planning_operands"],
                    [],
                    0,
                ),
                (
                    "_plan_formula_calculation_from_operation_decision",
                    public_name,
                    "",
                    ["state", "operands"],
                    [],
                    0,
                ),
            ],
        )

        graph_imports = {
            alias.name
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            for alias in node.names
        }
        self.assertNotIn("build_deterministic_operation_plan", graph_imports)
        self.assertIn(public_name, graph_imports)
        self.assertEqual(
            sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "build_deterministic_operation_plan"
                for node in ast.walk(graph_tree)
            ),
            0,
        )
        self.assertEqual(
            sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "should_coerce_percent_point_unit"
                for node in ast.walk(graph_tree)
            ),
            1,
        )
        self.assertEqual(
            sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "build_deterministic_operation_plan"
                for node in ast.walk(definition)
            ),
            1,
        )
        self.assertEqual(
            sum(
                isinstance(node, ast.Name)
                and isinstance(node.ctx, ast.Load)
                and node.id == "should_coerce_percent_point_unit"
                for node in ast.walk(definition)
            ),
            1,
        )
        owner_defs = [node for node in owner_tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in owner_defs),
                sum(node.name.startswith("_") for node in owner_defs),
            ),
            (13, 0),
        )

        modules = {
            f"src.agent.{path.stem}": path
            for path in Path("src/agent").glob("*.py")
        }
        imports = {name: set() for name in modules}
        for module_name, path in modules.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in modules:
                    imports[module_name].add(node.module)

        def reaches(source, target):
            pending = [source]
            visited = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in visited:
                    continue
                visited.add(current)
                pending.extend(imports.get(current, set()) - visited)
            return False

        owner_module = "src.agent.financial_calculation_execution"
        policy_module = "src.agent.financial_operation_policies"
        self.assertFalse(reaches(policy_module, owner_module))
        self.assertEqual(
            [
                row
                for row in collect_runtime_domain_term_occurrences()
                if row.get("symbol", "").endswith(private_name)
            ],
            [],
        )

    def test_current_source_runtime_plan_adapter_callers_pin_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = None
        shared = {"nested": True}

        row = {
            "task_id": "task_sum",
            "operation_family": "sum",
            "calculation_operands": [{"operand_id": "op", "nested": shared}],
            "calculation_plan": {},
        }
        state = {
            "query": "sum query",
            "calc_subtasks": [{"task_id": "task_sum", "operation_family": "sum"}],
            "evidence_items": [],
            "runtime_evidence": [],
            "nested": shared,
        }
        state_before = deepcopy(state)
        row_before = deepcopy(row)
        events = []
        marker_plan = {"status": "ok", "marker": "source-slot"}

        def source_slot_target(owner_state, owner_operands, *, active_subtask=None):
            events.append("source-target")
            self.assertIs(owner_state, state)
            self.assertEqual(owner_operands, row["calculation_operands"])
            self.assertIs(owner_operands[0]["nested"], shared)
            self.assertEqual(active_subtask["task_id"], "task_sum")
            return marker_plan

        def stop_rebuild(_plan, *, raw_deterministic_plan, **_kwargs):
            events.append("source-rebuild")
            self.assertIs(raw_deterministic_plan, marker_plan)
            raise RuntimeError("source rebuild stop")

        with (
            patch.object(
                graph_calculation,
                "build_dependency_lookup_slots_by_task",
                return_value={},
            ),
            patch.object(
                graph_calculation,
                "collect_table_label_evidence_candidates",
                return_value=[],
            ),
            patch.object(
                graph_calculation,
                "refresh_dependency_operands_from_lookup_slots",
                side_effect=lambda operands, **_kwargs: (operands, True),
            ),
            patch.object(
                graph_calculation,
                "classify_dependency_recalculation_plan",
                return_value="rebuild",
            ),
            patch.object(
                graph_calculation,
                "build_runtime_deterministic_operation_plan",
                side_effect=source_slot_target,
            ),
            patch.object(
                graph_calculation,
                "rebuild_dependency_calculation_plan",
                side_effect=stop_rebuild,
            ),
            self.assertRaisesRegex(RuntimeError, "source rebuild stop"),
        ):
            agent._align_lookup_results_with_dependency_projection([row], state, {})
        self.assertEqual(events, ["source-target", "source-rebuild"])
        self.assertEqual(state, state_before)
        self.assertEqual(row, row_before)
        self.assertIs(state["nested"], shared)
        self.assertIs(row["calculation_operands"][0]["nested"], shared)

        period_row = {
            "task_id": "task_period",
            "operation_family": "difference",
            "status": "partial",
        }
        period_state = {
            "query": "period query",
            "calc_subtasks": [
                {
                    "task_id": "task_period",
                    "operation_family": "difference",
                    "required_operands": [{"label": "metric", "required": True}],
                }
            ],
            "nested": shared,
        }
        planning_operands = [{"operand_id": "period", "nested": shared}]
        period_events = []
        period_plan = {"status": "ok", "marker": "period"}

        def period_target(plan_state, owner_operands):
            period_events.append("period-target")
            self.assertEqual(plan_state["active_subtask"]["task_id"], "task_period")
            self.assertIs(owner_operands[0]["nested"], shared)
            return period_plan

        def stop_resolution(*, plan, **_kwargs):
            period_events.append("period-resolve")
            self.assertIs(plan, period_plan)
            raise RuntimeError("period resolve stop")

        with (
            patch.object(
                agent,
                "_build_period_comparison_operands_from_table_label_context",
                return_value=planning_operands,
            ),
            patch.object(graph_calculation, "missing_required_operands", return_value=[]),
            patch.object(
                graph_calculation,
                "resolve_runtime_calculation_trace",
                return_value={"calculation_operands": planning_operands},
            ),
            patch.object(
                graph_calculation,
                "build_runtime_deterministic_operation_plan",
                side_effect=period_target,
            ),
            patch.object(
                graph_calculation,
                "resolve_deterministic_operation_plan",
                side_effect=stop_resolution,
            ),
            self.assertRaisesRegex(RuntimeError, "period resolve stop"),
        ):
            agent._realign_period_comparison_results_from_table_label_context(
                [period_row],
                period_state,
                [{"evidence_id": "ev"}],
            )
        self.assertEqual(period_events, ["period-target", "period-resolve"])
        self.assertIs(planning_operands[0]["nested"], shared)

        formula_state = {
            "query": "formula query",
            "active_subtask": {"operation_family": "sum"},
            "nested": shared,
        }
        formula_operands = [{"operand_id": "formula", "nested": shared}]
        formula_events = []
        formula_plan = {"status": "ok", "marker": "formula"}

        def formula_target(owner_state, owner_operands):
            formula_events.append("formula-target")
            self.assertIs(owner_state, formula_state)
            self.assertIsNot(owner_operands, formula_operands)
            self.assertIs(owner_operands[0], formula_operands[0])
            return formula_plan

        def stop_formula_resolution(*, plan, **_kwargs):
            formula_events.append("formula-resolve")
            self.assertIs(plan, formula_plan)
            raise RuntimeError("formula resolve stop")

        ontology = Mock()
        ontology.metric_family.return_value = None
        with (
            patch.object(
                graph_calculation,
                "resolve_runtime_calculation_trace",
                return_value={"calculation_operands": formula_operands},
            ),
            patch.object(agent, "_calc_query", return_value="formula query"),
            patch.object(agent, "_calc_metric_family", return_value=""),
            patch.object(agent, "_build_deterministic_lookup_plan", return_value=None),
            patch.object(graph_calculation, "get_financial_ontology", return_value=ontology),
            patch.object(
                graph_calculation,
                "build_runtime_deterministic_operation_plan",
                side_effect=formula_target,
            ),
            patch.object(
                graph_calculation,
                "resolve_deterministic_operation_plan",
                side_effect=stop_formula_resolution,
            ),
            self.assertRaisesRegex(RuntimeError, "formula resolve stop"),
        ):
            agent._plan_formula_calculation_from_operation_decision(formula_state)
        self.assertEqual(formula_events, ["formula-target", "formula-resolve"])
        self.assertIs(formula_operands[0]["nested"], shared)

    def test_current_source_ontology_plan_pins_gates_preference_and_stable_ties(self) -> None:
        target = calculation_execution.build_deterministic_ontology_plan
        shared = {"nested": True}
        required = [
            {
                "label": "numerator",
                "concept": "num",
                "role": "numerator_1",
                "consolidation_scope": "consolidated",
                "nested": shared,
            },
            {
                "label": "denominator",
                "concept": "den",
                "role": "denominator_1",
                "nested": shared,
            },
        ]
        weak = {
            "operand_id": "weak",
            "concept": "num",
            "matched_operand_role": "numerator_1",
            "source_row_ids": ["weak"],
        }
        winner = {
            "operand_id": "winner",
            "concept": "num",
            "matched_operand_role": "numerator_1",
            "consolidation_scope": "consolidated",
            "statement_type": "income_statement",
            "aggregation_stage": "direct",
            "value_role": "aggregate",
            "source_row_ids": ["winner-a", "winner-b"],
            "nested": shared,
        }
        later_tie = {**winner, "operand_id": "later-tie"}
        denominator = {
            "operand_id": "denominator",
            "concept": "den",
            "matched_operand_role": "denominator_1",
            "consolidation_scope": "consolidated",
            "source_row_id": "den-source",
        }
        operands = [weak, winner, later_tie, denominator]
        state = {
            "query": "ratio query",
            "active_subtask": {
                "operation_family": "ignored",
                "required_operands": required,
                "metric_label": "active label",
            },
            "nested": shared,
        }
        inputs_before = deepcopy((state, operands))
        ontology = Mock()
        ontology.metric_family.return_value = {
            "formula_family": " Ratio ",
            "display_name": "Ontology Ratio",
            "result_unit": "PERCENT",
        }

        def matches(row, operand):
            return row.get("concept") == operand.get("concept")

        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
            patch.object(
                calculation_execution,
                "operand_row_matches_requirement",
                side_effect=matches,
            ) as matcher,
        ):
            plan = target(state["active_subtask"], operands, metric_key="ratio_metric")

        ontology.metric_family.assert_called_once_with("ratio_metric")
        self.assertEqual(matcher.call_count, len(required) * len(operands))
        self.assertEqual(plan["ordered_operand_ids"], ["winner", "denominator"])
        self.assertEqual(plan["variable_bindings"], [
            {"variable": "A", "operand_id": "winner"},
            {"variable": "B", "operand_id": "denominator"},
        ])
        self.assertEqual(plan["formula"], "((A) / (B)) * 100")
        self.assertEqual(plan["result_unit"], "%")
        self.assertEqual(plan["explanation"], "Ontology Ratio의 role에 따라 분자와 분모를 결정해 비율을 계산합니다.")
        self.assertEqual((state, operands), inputs_before)
        self.assertIs(state["nested"], shared)
        self.assertIs(operands[1]["nested"], shared)

        unsupported = Mock()
        unsupported.metric_family.return_value = {"formula_family": "difference"}
        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=unsupported),
            patch.object(
                calculation_execution,
                "operand_row_matches_requirement",
                side_effect=RuntimeError("matcher must stay lazy"),
            ) as lazy_matcher,
        ):
            self.assertIsNone(target(state["active_subtask"], operands, metric_key="ratio_metric"))
        lazy_matcher.assert_not_called()

        no_required_state = {"active_subtask": {"operation_family": "ratio"}}
        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
            patch.object(
                calculation_execution,
                "operand_row_matches_requirement",
                side_effect=RuntimeError("matcher must stay lazy"),
            ) as lazy_matcher,
        ):
            self.assertIsNone(
                target(no_required_state["active_subtask"], operands, metric_key="ratio_metric")
            )
        lazy_matcher.assert_not_called()

    def test_current_source_ontology_plan_pins_ratio_average_units_and_formula_surfaces(self) -> None:
        target = calculation_execution.build_deterministic_ontology_plan
        required = [
            {"label": "numerator", "concept": "num", "role": "numerator_1"},
            {"label": "denominator one", "concept": "den1", "role": "denominator_1"},
            {"label": "denominator two", "concept": "den2", "role": "denominator_2"},
        ]
        operands = [
            {"operand_id": "num", "concept": "num", "matched_operand_role": "numerator_1"},
            {"operand_id": "den1", "concept": "den1", "matched_operand_role": "denominator_1"},
            {"operand_id": "den2", "concept": "den2", "matched_operand_role": "denominator_2"},
        ]
        ontology = Mock()
        ontology.metric_family.return_value = {
            "formula_family": "ratio",
            "display_name": "Average Ratio",
            "denominator_aggregation": "average",
            "result_unit": "PERCENT",
        }

        def matches(row, operand):
            return row.get("concept") == operand.get("concept")

        state = {
            "query": "ratio query",
            "active_subtask": {"required_operands": required},
        }
        before = deepcopy((state, operands))
        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
            patch.object(calculation_execution, "operand_row_matches_requirement", side_effect=matches),
        ):
            plan = target(state["active_subtask"], operands, metric_key="ratio_metric")
        self.assertEqual(plan["ordered_operand_ids"], ["num", "den1", "den2"])
        self.assertEqual(plan["formula"], "((A) / (((B + C) / 2))) * 100")
        self.assertEqual(
            plan["operation_text"],
            "(numerator) / (average(denominator one + denominator two)) * 100",
        )
        self.assertEqual(plan["result_unit"], "%")
        self.assertEqual((state, operands), before)

        for requested_unit, expected_unit, expected_suffix in (
            ("PERCENT_POINT", "%p", True),
            ("퍼센트", "퍼센트", True),
            ("COUNT", "COUNT", False),
            ("", "%", True),
        ):
            task = {
                "required_operands": required,
                "denominator_aggregation": "average",
                "result_unit": requested_unit,
            }
            with (
                patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
                patch.object(calculation_execution, "operand_row_matches_requirement", side_effect=matches),
            ):
                result = target(task, operands, metric_key="ratio_metric")
            self.assertEqual(result["result_unit"], expected_unit)
            self.assertEqual(result["formula"].endswith(" * 100"), expected_suffix)
            self.assertEqual(result["operation_text"].endswith(" * 100"), expected_suffix)

        missing_denominator = required[:1]
        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
            patch.object(calculation_execution, "operand_row_matches_requirement", side_effect=matches),
        ):
            self.assertIsNone(
                target(
                    {"required_operands": missing_denominator},
                    operands,
                    metric_key="ratio_metric",
                )
            )

    def test_current_source_ontology_plan_pins_sum_fallback_missing_ids_and_exceptions(self) -> None:
        target = calculation_execution.build_deterministic_ontology_plan
        shared = {"nested": True}
        required = [
            {"label": "first", "concept": "one", "required": True, "nested": shared},
            {"label": "ignored", "concept": "ignored", "required": False},
            {"label": "second", "concept": "two", "required": True},
        ]
        operands = [
            {"operand_id": "one", "concept": "one", "nested": shared},
            {"operand_id": "two", "concept": "two"},
        ]
        state = {
            "active_subtask": {
                "operation_family": " SUM ",
                "metric_label": "Active Sum",
                "required_operands": required,
            },
            "nested": shared,
        }
        before = deepcopy((state, operands))
        ontology = Mock()
        ontology.metric_family.return_value = {"formula_family": "", "result_unit": "KRW"}

        def matches(row, operand):
            return row.get("concept") == operand.get("concept")

        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
            patch.object(calculation_execution, "operand_row_matches_requirement", side_effect=matches),
        ):
            plan = target(state["active_subtask"], operands, metric_key="sum_metric")
        self.assertEqual(plan["operation"], "add")
        self.assertEqual(plan["ordered_operand_ids"], ["one", "two"])
        self.assertEqual(plan["formula"], "A + B")
        self.assertEqual(plan["operation_text"], "first + second")
        self.assertEqual(plan["result_unit"], "KRW")
        self.assertEqual(plan["explanation"], "Active Sum에 필요한 concept operand를 합산합니다.")
        self.assertEqual((state, operands), before)
        self.assertIs(state["nested"], shared)
        self.assertIs(operands[0]["nested"], shared)

        for changed_operands in (
            operands[:1],
            [{**operands[0], "operand_id": ""}, operands[1]],
        ):
            with (
                patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
                patch.object(calculation_execution, "operand_row_matches_requirement", side_effect=matches),
            ):
                self.assertIsNone(
                    target(state["active_subtask"], changed_operands, metric_key="sum_metric")
                )

        later_matcher = Mock()
        with (
            patch.object(
                calculation_execution,
                "get_financial_ontology",
                side_effect=RuntimeError("ontology failed"),
            ),
            patch.object(calculation_execution, "operand_row_matches_requirement", later_matcher),
            self.assertRaisesRegex(RuntimeError, "ontology failed"),
        ):
            target(state["active_subtask"], operands, metric_key="sum_metric")
        later_matcher.assert_not_called()

        with (
            patch.object(calculation_execution, "get_financial_ontology", return_value=ontology),
            patch.object(
                calculation_execution,
                "operand_row_matches_requirement",
                side_effect=RuntimeError("matcher failed"),
            ),
            self.assertRaisesRegex(RuntimeError, "matcher failed"),
        ):
            target(state["active_subtask"], operands, metric_key="sum_metric")

    def test_current_source_ontology_plan_pins_static_binding_dag_and_baseline(self) -> None:
        import json

        graph_path = Path(graph_calculation.__file__)
        owner_path = Path("src/agent/financial_calculation_execution.py")
        graph_tree = ast.parse(graph_path.read_text(encoding="utf-8"))
        owner_tree = ast.parse(owner_path.read_text(encoding="utf-8"))
        private_name = "_build_deterministic_ontology_plan"
        public_name = "build_deterministic_ontology_plan"
        definition = next(
            node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name == public_name
        )
        self.assertEqual(definition.end_lineno - definition.lineno + 1, 195)
        self.assertEqual(
            [argument.arg for argument in definition.args.args],
            ["active_subtask", "operands"],
        )
        self.assertEqual(
            [argument.arg for argument in definition.args.kwonlyargs],
            ["metric_key"],
        )
        self.assertEqual(
            [
                node
                for node in ast.walk(graph_tree)
                if isinstance(node, ast.FunctionDef) and node.name == private_name
            ],
            [],
        )

        parents = {
            child: parent
            for parent in ast.walk(graph_tree)
            for child in ast.iter_child_nodes(parent)
        }
        calls = [
            node
            for node in ast.walk(graph_tree)
            if isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == public_name
        ]
        self.assertEqual(len(calls), 1)
        call = calls[0]
        self.assertEqual(
            [ast.unparse(arg) for arg in call.args],
            ["dict(state.get('active_subtask') or {})", "operands"],
        )
        self.assertEqual(
            [(keyword.arg, ast.unparse(keyword.value)) for keyword in call.keywords],
            [("metric_key", "self._calc_metric_family(state)")],
        )
        parent = parents[call]
        while not (isinstance(parent, ast.FunctionDef) and parent.name == "_plan_formula_calculation_from_operation_decision"):
            self.assertNotIsInstance(parent, ast.Try)
            parent = parents[parent]

        owner_defs = [node for node in owner_tree.body if isinstance(node, ast.FunctionDef)]
        self.assertEqual(
            (
                sum(not node.name.startswith("_") for node in owner_defs),
                sum(node.name.startswith("_") for node in owner_defs),
            ),
            (13, 0),
        )
        baseline = json.loads(
            (Path(__file__).parent / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        selected_texts = {
            "퍼센트",
            "의 role에 따라 분자와 분모를 결정해 비율을 계산합니다.",
            "에 필요한 concept operand를 합산합니다.",
        }
        selected_records = [
            record
            for record in baseline["records"]
            if record.get("path") == owner_path.as_posix()
            and record.get("text") in selected_texts
        ]
        self.assertEqual({record["text"] for record in selected_records}, selected_texts)
        self.assertTrue(all(record["category"] == "runtime_literal" for record in selected_records))
        self.assertTrue(all(record["count"] == 1 for record in selected_records))
        self.assertEqual(len(baseline["records"]), 217)

        modules = {
            f"src.agent.{path.stem}": path
            for path in Path("src/agent").glob("*.py")
        }
        imports = {name: set() for name in modules}
        for module_name, path in modules.items():
            tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module in modules:
                    imports[module_name].add(node.module)

        def reaches(source, target):
            pending = [source]
            visited = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in visited:
                    continue
                visited.add(current)
                pending.extend(imports.get(current, set()) - visited)
            return False

        owner_module = "src.agent.financial_calculation_execution"
        operand_module = "src.agent.financial_operand_resolution"
        self.assertIn(operand_module, imports[owner_module])
        self.assertFalse(reaches(operand_module, owner_module))

    def test_current_source_ontology_plan_caller_pins_dynamic_dispatch_args_adoption_and_stop(self) -> None:
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm = None
        shared = {"nested": True}
        task = {
            "operation_family": "ratio",
            "metric_family": "ratio_metric",
            "required_operands": [
                {"label": "num", "role": "numerator_1", "nested": shared},
                {"label": "den", "role": "denominator_1"},
            ],
            "nested": shared,
        }
        state = {"query": "ratio query", "active_subtask": task, "nested": shared}
        operands = [{"operand_id": "num", "nested": shared}, {"operand_id": "den"}]
        state_before = deepcopy(state)
        operands_before = deepcopy(operands)
        events = []
        marker_plan = {"status": "ok", "marker": "ontology"}
        ontology = Mock()
        ontology.metric_family.return_value = None

        def metric_owner(owner_state):
            events.append("metric")
            self.assertIs(owner_state, state)
            return "ratio_metric"

        def ontology_owner(owner_active_subtask, owner_operands, *, metric_key):
            events.append("ontology-owner")
            self.assertIsNot(owner_active_subtask, task)
            self.assertEqual(owner_active_subtask, task)
            self.assertIs(owner_active_subtask["nested"], shared)
            self.assertIsNot(owner_operands, operands)
            self.assertIs(owner_operands[0], operands[0])
            self.assertEqual(metric_key, "ratio_metric")
            return marker_plan

        def stop_guard(*, plan, **_kwargs):
            events.append("guard")
            self.assertIs(plan, marker_plan)
            raise RuntimeError("ontology guard stop")

        decision = DeterministicOperationPlanDecision(
            status="not_applicable",
            raw_plan={},
            selected_plan={},
        )
        with (
            patch.object(
                graph_calculation,
                "resolve_runtime_calculation_trace",
                return_value={"calculation_operands": operands},
            ),
            patch.object(agent, "_calc_query", return_value="ratio query"),
            patch.object(agent, "_calc_metric_family", side_effect=metric_owner),
            patch.object(agent, "_build_deterministic_lookup_plan", return_value=None),
            patch.object(graph_calculation, "missing_required_operands", return_value=[]),
            patch.object(graph_calculation, "get_financial_ontology", return_value=ontology),
            patch.object(
                graph_calculation,
                "build_deterministic_ontology_plan",
                side_effect=ontology_owner,
            ),
            patch.object(graph_calculation, "guard_operation_plan", side_effect=stop_guard),
            self.assertRaisesRegex(RuntimeError, "ontology guard stop"),
        ):
            agent._plan_formula_calculation_from_operation_decision(state, decision)

        self.assertEqual(events, ["metric", "metric", "ontology-owner", "guard"])
        self.assertEqual(state, state_before)
        self.assertEqual(operands, operands_before)
        self.assertIs(state["nested"], shared)
        self.assertIs(state["active_subtask"]["nested"], shared)
        self.assertIs(operands[0]["nested"], shared)

        later_guard = Mock()
        with (
            patch.object(
                graph_calculation,
                "resolve_runtime_calculation_trace",
                return_value={"calculation_operands": operands},
            ),
            patch.object(agent, "_calc_query", return_value="ratio query"),
            patch.object(agent, "_calc_metric_family", side_effect=RuntimeError("metric failed")),
            patch.object(agent, "_build_deterministic_lookup_plan", return_value=None),
            patch.object(graph_calculation, "missing_required_operands", return_value=[]),
            patch.object(graph_calculation, "get_financial_ontology", return_value=ontology),
            patch.object(graph_calculation, "guard_operation_plan", later_guard),
            self.assertRaisesRegex(RuntimeError, "metric failed"),
        ):
            agent._plan_formula_calculation_from_operation_decision(state, decision)
        later_guard.assert_not_called()


if __name__ == "__main__":
    unittest.main()
