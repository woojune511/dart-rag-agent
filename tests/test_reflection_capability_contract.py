import ast
import json
import unittest
from collections.abc import Mapping
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import src.agent.financial_graph_calculation as financial_graph_calculation
import src.agent.financial_graph_reconciliation as financial_graph_reconciliation
import src.agent.financial_reflection_projection as financial_reflection_projection
import src.agent.financial_task_artifacts as financial_task_artifacts
from src.agent.financial_reflection_projection import (
    ALLOWED_REFLECTION_RETRY_STRATEGIES,
    build_reflection_request,
    normalise_reflection_plan_record,
    reflection_action_from_plan,
    reflection_report_from_action,
    task_artifact_integrity_feedback,
)
from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin


class ReflectionCapabilityContractTests(unittest.TestCase):
    def test_retry_preparation_helpers_have_projection_and_ledger_owners(self) -> None:
        self.assertTrue(
            hasattr(
                financial_reflection_projection,
                "reflection_synthesis_source_ids_from_task_outputs",
            )
        )
        self.assertTrue(hasattr(financial_task_artifacts, "next_reflection_task_id"))
        self.assertFalse(
            hasattr(financial_graph_calculation, "_synthesis_source_ids_from_task_outputs")
        )
        self.assertFalse(hasattr(financial_graph_calculation, "_next_reflection_task_id"))

    def test_synthesis_source_selection_preserves_precedence_and_fallbacks_without_mutation(
        self,
    ) -> None:
        state = {
            "active_subtask": {
                "depends_on": ["task_ignored"],
                "inputs": [
                    {
                        "preferred_task_id": " task_2 ",
                        "source_preference": [" retrieval ", " TASK_OUTPUT "],
                    },
                    {
                        "preferred_task_id": "task_2",
                        "source_preference": ["task_output"],
                    },
                    {
                        "preferred_task_id": "task_3",
                        "source_preference": ["task_output"],
                    },
                ],
            },
            "subtask_results": [
                {
                    "task_id": "task_2",
                    "artifact_ids": ["operand_2", "result_2"],
                    "calculation_result": {"status": "ok"},
                },
                {
                    "task_id": "task_3",
                    "artifact_ids": [],
                    "calculation_result": {"status": "ok"},
                },
                {
                    "task_id": "task_ignored",
                    "artifact_ids": ["result_ignored"],
                    "calculation_result": {"status": "ok"},
                },
            ],
            "artifacts": [
                {"artifact_id": "operand_2", "kind": "operand_set"},
                {"artifact_id": "result_2", "kind": "calculation_result"},
                {"artifact_id": "result_ignored", "kind": "calculation_result"},
            ],
        }
        original = deepcopy(state)

        source_ids = (
            financial_reflection_projection.reflection_synthesis_source_ids_from_task_outputs(
                active_subtask=state["active_subtask"],
                subtask_results=state["subtask_results"],
                artifacts=state["artifacts"],
            )
        )

        self.assertEqual(source_ids, ["result_2", "task_output:task_3"])
        self.assertEqual(state, original)

        fallback_state = {
            "active_subtask": {
                "depends_on": ["task_4", "task_4", "missing_task"],
                "inputs": [{"preferred_task_id": "ignored", "source_preference": ["retrieval"]}],
            },
            "subtask_results": [
                {
                    "task_id": "task_4",
                    "artifact_ids": ["operand_4", "plan_4", "operand_4"],
                    "calculation_result": {"status": "ok"},
                }
            ],
            "artifacts": [
                {"artifact_id": "operand_4", "kind": "operand_set"},
                {"artifact_id": "plan_4", "kind": "calculation_plan"},
            ],
        }
        fallback_original = deepcopy(fallback_state)

        fallback_source_ids = (
            financial_reflection_projection.reflection_synthesis_source_ids_from_task_outputs(
                active_subtask=fallback_state["active_subtask"],
                subtask_results=fallback_state["subtask_results"],
                artifacts=fallback_state["artifacts"],
            )
        )

        self.assertEqual(fallback_source_ids, ["operand_4", "plan_4"])
        self.assertEqual(fallback_state, fallback_original)
        self.assertEqual(
            financial_reflection_projection.reflection_synthesis_source_ids_from_task_outputs(
                active_subtask={"depends_on": ["missing_task"]},
                subtask_results=[],
                artifacts=[],
            ),
            [],
        )

    def test_next_reflection_task_id_skips_task_and_artifact_collisions(self) -> None:
        state = {
            "tasks": [{"task_id": "reflection:task_1:001"}],
            "artifacts": [
                {
                    "task_id": "reflection:task_1:002",
                    "artifact_id": "reflection:task_1:003:report",
                }
            ],
        }
        original = deepcopy(state)

        task_id = financial_task_artifacts.next_reflection_task_id(
            tasks=state["tasks"],
            artifacts=state["artifacts"],
            target_task_id=" task_1 ",
            current_count=0,
        )

        self.assertEqual(task_id, "reflection:task_1:004")
        self.assertEqual(state, original)

    def test_allowed_retry_strategies_are_bounded(self) -> None:
        self.assertEqual(
            ALLOWED_REFLECTION_RETRY_STRATEGIES,
            {
                "retry_retrieval",
                "synthesize_from_task_outputs",
                "stop_insufficient",
            },
        )

    def test_normalise_reflection_plan_rejects_unknown_strategy(self) -> None:
        plan = normalise_reflection_plan_record(
            {
                "status": "ready",
                "retry_objective": "find_missing_values",
                "retry_strategy": "unbounded_agent_loop",
                "missing_info": [" value "],
                "subqueries": [" query "],
                "preferred_sections": [],
                "explanation": "unit test",
            },
            fallback_plan={"retry_strategy": "stop_insufficient"},
            missing_info=["fallback value"],
            preferred_sections=["fallback section"],
        )

        self.assertEqual(plan["retry_strategy"], "stop_insufficient")
        self.assertEqual(plan["missing_info"], ["value"])
        self.assertEqual(plan["subqueries"], ["query"])
        self.assertEqual(plan["preferred_sections"], ["fallback section"])

    def test_normalise_reflection_plan_falls_back_without_subqueries(self) -> None:
        plan = normalise_reflection_plan_record(
            {
                "status": "ready",
                "retry_strategy": "retry_retrieval",
                "missing_info": [],
                "subqueries": [],
            },
            fallback_plan={
                "status": "ready",
                "retry_strategy": "retry_retrieval",
                "missing_info": ["fallback value"],
                "subqueries": ["fallback query"],
            },
            missing_info=["missing value"],
            preferred_sections=["section"],
        )

        self.assertEqual(plan["subqueries"], ["fallback query"])
        self.assertEqual(
            plan["explanation"],
            "fallback to heuristic because reflection planner returned no subqueries",
        )

    def test_reflection_request_uses_strict_runtime_trace_and_budget(self) -> None:
        request = build_reflection_request(
            {
                "query": "find missing value",
                "active_subtask": {"task_id": "task_1"},
                "reflection_count": 0,
                "evidence_status": "missing",
                "evidence_items": [{"evidence_id": "e1"}],
                "retrieved_docs": [object()],
                "seed_retrieved_docs": [object(), object()],
                "resolved_calculation_trace": {},
                "structured_result": {},
                "calculation_operands": [{"label": "legacy"}],
                "calculation_plan": {"status": "legacy"},
                "calculation_result": {"status": "legacy"},
            },
            missing_info=[" value "],
            failure_status="incomplete",
        )

        self.assertEqual(request["active_task_id"], "task_1")
        self.assertEqual(request["missing_info"], ["value"])
        self.assertEqual(request["remaining_retry_budget"], 1)
        self.assertEqual(request["runtime_trace_summary"]["operand_count"], 0)
        self.assertEqual(request["runtime_trace_summary"]["plan_status"], "")
        self.assertEqual(request["runtime_trace_summary"]["result_status"], "")
        self.assertEqual(request["evidence_summary"]["evidence_item_count"], 1)
        self.assertEqual(request["evidence_summary"]["retrieved_doc_count"], 1)
        self.assertEqual(request["evidence_summary"]["seed_retrieved_doc_count"], 2)

    def test_reflection_request_clamps_budget_after_one_retry(self) -> None:
        request = build_reflection_request(
            {
                "query": "find missing value",
                "active_subtask": {},
                "reflection_count": 1,
                "resolved_calculation_trace": {},
                "structured_result": {},
            },
            missing_info=[],
            failure_status="incomplete",
        )

        self.assertEqual(request["remaining_retry_budget"], 0)

    def test_current_source_reflection_plan_normalizer_pins_fallback_copy_and_exceptions(
        self,
    ) -> None:
        nested = {"keep": True}
        plan = {
            "status": "ready",
            "retry_strategy": " RETRY_RETRIEVAL ",
            "missing_info": [" value ", "", 7],
            "subqueries": [" query   one ", " "],
            "preferred_sections": [" section   one ", ""],
            "nested": nested,
        }
        original = deepcopy(plan)

        normalized = financial_reflection_projection.normalise_reflection_plan_record(
            plan,
            fallback_plan={"retry_strategy": "stop_insufficient"},
            missing_info=["fallback missing"],
            preferred_sections=["fallback section"],
        )

        self.assertIsNot(normalized, plan)
        self.assertEqual(normalized["retry_strategy"], "retry_retrieval")
        self.assertEqual(normalized["missing_info"], ["value", "7"])
        self.assertEqual(normalized["subqueries"], ["query one"])
        self.assertEqual(normalized["preferred_sections"], ["section one"])
        self.assertIs(normalized["nested"], nested)
        self.assertEqual(plan, original)
        self.assertIs(plan["nested"], nested)

        fallback_missing = object()
        fallback_missing_values = [fallback_missing]
        fallback_sections = [object(), object(), object(), object()]
        fallback_values = financial_reflection_projection.normalise_reflection_plan_record(
            {
                "retry_strategy": "unknown_strategy",
                "missing_info": [],
                "subqueries": ["kept query"],
                "preferred_sections": [],
            },
            fallback_plan={"retry_strategy": " Raw_Fallback "},
            missing_info=fallback_missing_values,
            preferred_sections=fallback_sections,
        )
        self.assertEqual(fallback_values["retry_strategy"], " Raw_Fallback ")
        self.assertIsNot(fallback_values["missing_info"], fallback_missing_values)
        self.assertEqual(fallback_values["missing_info"], [fallback_missing])
        self.assertEqual(fallback_values["preferred_sections"], fallback_sections[:3])
        self.assertIsNot(fallback_values["preferred_sections"], fallback_sections)
        for actual, expected in zip(
            fallback_values["preferred_sections"], fallback_sections[:3]
        ):
            self.assertIs(actual, expected)

        fallback_nested = {"alias": True}
        fallback_plan = {
            "status": "skip",
            "retry_strategy": "stop_insufficient",
            "missing_info": ["fallback value"],
            "subqueries": ["fallback query"],
            "preferred_sections": ["fallback section"],
            "nested": fallback_nested,
            "explanation": "old explanation",
        }
        replaced = financial_reflection_projection.normalise_reflection_plan_record(
            {
                "status": "ready",
                "retry_strategy": "retry_retrieval",
                "missing_info": [],
                "subqueries": [],
                "preferred_sections": [],
                "discarded": True,
            },
            fallback_plan=fallback_plan,
            missing_info=["filled before replacement"],
            preferred_sections=["filled before replacement"],
        )
        self.assertIsNot(replaced, fallback_plan)
        self.assertNotIn("discarded", replaced)
        self.assertEqual(replaced["missing_info"], ["fallback value"])
        self.assertEqual(replaced["subqueries"], ["fallback query"])
        self.assertEqual(
            replaced["explanation"],
            "fallback to heuristic because reflection planner returned no subqueries",
        )
        self.assertIs(replaced["nested"], fallback_nested)
        self.assertEqual(fallback_plan["explanation"], "old explanation")

        class BoolBomb:
            def __bool__(self):
                raise RuntimeError("plan truthiness")

        with self.assertRaisesRegex(RuntimeError, "plan truthiness"):
            financial_reflection_projection.normalise_reflection_plan_record(
                BoolBomb(),
                fallback_plan={},
                missing_info=[],
                preferred_sections=[],
            )

        with patch.object(
            financial_reflection_projection,
            "_normalise_spaces",
            side_effect=RuntimeError("normalizer failed"),
        ):
            with self.assertRaisesRegex(RuntimeError, "normalizer failed"):
                financial_reflection_projection.normalise_reflection_plan_record(
                    {
                        "missing_info": [],
                        "subqueries": ["query"],
                        "preferred_sections": [],
                    },
                    fallback_plan={},
                    missing_info=[],
                    preferred_sections=[],
                )

        class FallbackBomb(dict):
            def get(self, key, default=None):
                raise RuntimeError(f"fallback access: {key}")

        with self.assertRaisesRegex(RuntimeError, "fallback access: retry_strategy"):
            financial_reflection_projection.normalise_reflection_plan_record(
                {
                    "retry_strategy": "not_allowed",
                    "missing_info": ["value"],
                    "subqueries": ["query"],
                    "preferred_sections": ["section"],
                },
                fallback_plan=FallbackBomb(),
                missing_info=[],
                preferred_sections=[],
            )

    def test_current_source_reflection_runtime_summary_pins_strict_trace_copy_and_exceptions(
        self,
    ) -> None:
        nested = {"keep": True}
        state = {"nested": nested, "calculation_plan": {"status": "legacy"}}
        trace_nested = {"trace": True}
        trace = {
            "calculation_operands": [{"label": "one"}, {"label": "two"}],
            "calculation_plan": {
                "status": " planned ",
                "operation": "ratio",
                "mode": "ignored_mode",
                "nested": trace_nested,
            },
            "calculation_result": {
                "status": " ok ",
                "explanation": " grounded ",
            },
        }
        state_before = deepcopy(state)
        trace_before = deepcopy(trace)
        resolver_calls = []

        def resolve(actual_state, *, allow_legacy_top_level):
            resolver_calls.append((actual_state, allow_legacy_top_level))
            self.assertIsNot(actual_state, state)
            self.assertIs(actual_state["nested"], nested)
            actual_state["copy_only"] = True
            return trace

        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            side_effect=resolve,
        ):
            summary = financial_reflection_projection._reflection_runtime_trace_summary(
                state
            )

        self.assertEqual(
            summary,
            {
                "operand_count": 2,
                "plan_status": " planned ",
                "plan_operation": "ratio",
                "result_status": " ok ",
                "result_explanation": " grounded ",
            },
        )
        self.assertEqual(len(resolver_calls), 1)
        self.assertFalse(resolver_calls[0][1])
        self.assertEqual(state, state_before)
        self.assertIs(state["nested"], nested)
        self.assertEqual(trace, trace_before)
        self.assertIs(trace["calculation_plan"]["nested"], trace_nested)

        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            return_value={
                "calculation_operands": [],
                "calculation_plan": {"operation": "", "mode": "fallback_mode"},
                "calculation_result": {},
            },
        ):
            self.assertEqual(
                financial_reflection_projection._reflection_runtime_trace_summary({})[
                    "plan_operation"
                ],
                "fallback_mode",
            )

        class ModeBomb:
            def __bool__(self):
                raise AssertionError("mode truthiness")

            def __str__(self):
                raise AssertionError("mode string")

        mode_bomb = ModeBomb()
        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            return_value={
                "calculation_operands": [],
                "calculation_plan": {
                    "operation": "preferred_operation",
                    "mode": mode_bomb,
                },
                "calculation_result": {},
            },
        ):
            self.assertEqual(
                financial_reflection_projection._reflection_runtime_trace_summary({})[
                    "plan_operation"
                ],
                "preferred_operation",
            )

        class StateCopyBomb(Mapping):
            def __iter__(self):
                raise RuntimeError("state copy")

            def __len__(self):
                return 1

            def __getitem__(self, key):
                raise RuntimeError("state item")

        resolver = Mock()
        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            resolver,
        ):
            with self.assertRaisesRegex(RuntimeError, "state copy|state item"):
                financial_reflection_projection._reflection_runtime_trace_summary(
                    StateCopyBomb()
                )
        resolver.assert_not_called()

        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            side_effect=RuntimeError("strict resolver"),
        ):
            with self.assertRaisesRegex(RuntimeError, "strict resolver"):
                financial_reflection_projection._reflection_runtime_trace_summary({})

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("operand iteration")

        class LaterBomb(dict):
            def get(self, key, default=None):
                if key == "calculation_operands":
                    return IterBomb()
                raise AssertionError(f"later trace access: {key}")

        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            return_value=LaterBomb(calculation_operands=IterBomb()),
        ):
            with self.assertRaisesRegex(RuntimeError, "operand iteration"):
                financial_reflection_projection._reflection_runtime_trace_summary({})

        class PlanCopyBomb(Mapping):
            def __iter__(self):
                raise RuntimeError("plan copy")

            def __len__(self):
                return 1

            def __getitem__(self, key):
                raise RuntimeError("plan item")

        with patch.object(
            financial_reflection_projection,
            "_resolve_runtime_calculation_trace",
            return_value={
                "calculation_operands": [],
                "calculation_plan": PlanCopyBomb(),
                "calculation_result": {},
            },
        ):
            with self.assertRaisesRegex(RuntimeError, "plan copy|plan item"):
                financial_reflection_projection._reflection_runtime_trace_summary({})

    def test_current_source_reflection_evidence_summary_pins_access_order_and_exceptions(
        self,
    ) -> None:
        events = []
        evidence_item = {"evidence_id": "e1"}
        retrieved_doc = object()
        seed_doc = object()

        class TrackedState(dict):
            def get(self, key, default=None):
                events.append(key)
                return super().get(key, default)

        state = TrackedState(
            evidence_items=[evidence_item],
            retrieved_docs=[retrieved_doc, object()],
            seed_retrieved_docs=[seed_doc],
            evidence_status=" incomplete ",
            nested={"keep": True},
        )
        nested = state["nested"]

        summary = financial_reflection_projection._reflection_evidence_summary(state)

        self.assertEqual(
            summary,
            {
                "evidence_item_count": 1,
                "retrieved_doc_count": 2,
                "seed_retrieved_doc_count": 1,
                "evidence_status": " incomplete ",
            },
        )
        self.assertEqual(
            events,
            [
                "evidence_items",
                "retrieved_docs",
                "seed_retrieved_docs",
                "evidence_status",
            ],
        )
        self.assertIs(state["evidence_items"][0], evidence_item)
        self.assertIs(state["retrieved_docs"][0], retrieved_doc)
        self.assertIs(state["seed_retrieved_docs"][0], seed_doc)
        self.assertIs(state["nested"], nested)
        self.assertEqual(
            financial_reflection_projection._reflection_evidence_summary({}),
            {
                "evidence_item_count": 0,
                "retrieved_doc_count": 0,
                "seed_retrieved_doc_count": 0,
                "evidence_status": "",
            },
        )

        class IterBomb:
            def __bool__(self):
                return True

            def __iter__(self):
                raise RuntimeError("seed iteration")

        stopped_events = []

        class StopState(dict):
            def get(self, key, default=None):
                stopped_events.append(key)
                if key == "seed_retrieved_docs":
                    return IterBomb()
                if key == "evidence_status":
                    raise AssertionError("status accessed")
                return []

        with self.assertRaisesRegex(RuntimeError, "seed iteration"):
            financial_reflection_projection._reflection_evidence_summary(StopState())
        self.assertEqual(
            stopped_events,
            ["evidence_items", "retrieved_docs", "seed_retrieved_docs"],
        )

        class StatusStrBomb:
            def __str__(self):
                raise RuntimeError("status string")

        with self.assertRaisesRegex(RuntimeError, "status string"):
            financial_reflection_projection._reflection_evidence_summary(
                {"evidence_status": StatusStrBomb()}
            )

    def test_current_source_reflection_request_builder_pins_order_budget_and_exception_stop(
        self,
    ) -> None:
        events = []
        nested = {"keep": True}
        active_subtask = {"task_id": " task_1 ", "nested": nested}

        class TrackedState(dict):
            def get(self, key, default=None):
                events.append(("state", key))
                return super().get(key, default)

        state = TrackedState(
            query=" query ",
            active_subtask=active_subtask,
            reflection_count=3,
            nested={"state": True},
        )
        state_snapshot = dict(state)
        state_nested = state["nested"]
        runtime_summary = {"operand_count": 2}
        evidence_summary = {"evidence_item_count": 1}

        def runtime_owner(actual_state):
            events.append(("owner", "runtime"))
            self.assertIs(actual_state, state)
            return runtime_summary

        def evidence_owner(actual_state):
            events.append(("owner", "evidence"))
            self.assertIs(actual_state, state)
            return evidence_summary

        class MissingValue:
            def __init__(self, value):
                self.value = value
                self.calls = 0

            def __str__(self):
                self.calls += 1
                return self.value

        kept = MissingValue(" value ")
        blank = MissingValue(" ")
        with patch.object(
            financial_reflection_projection,
            "_reflection_runtime_trace_summary",
            side_effect=runtime_owner,
        ), patch.object(
            financial_reflection_projection,
            "_reflection_evidence_summary",
            side_effect=evidence_owner,
        ):
            request = build_reflection_request(
                state,
                missing_info=[kept, blank],
                failure_status=" failure ",
            )

        self.assertEqual(
            request,
            {
                "query": " query ",
                "active_task_id": " task_1 ",
                "failure_status": " failure ",
                "missing_info": ["value"],
                "runtime_trace_summary": runtime_summary,
                "evidence_summary": evidence_summary,
                "remaining_retry_budget": 0,
            },
        )
        self.assertIs(request["runtime_trace_summary"], runtime_summary)
        self.assertIs(request["evidence_summary"], evidence_summary)
        self.assertEqual(kept.calls, 2)
        self.assertEqual(blank.calls, 1)
        self.assertEqual(
            events,
            [
                ("state", "active_subtask"),
                ("state", "reflection_count"),
                ("state", "query"),
                ("owner", "runtime"),
                ("owner", "evidence"),
            ],
        )
        self.assertEqual(dict(state), state_snapshot)
        self.assertIs(state["active_subtask"], active_subtask)
        self.assertIs(active_subtask["nested"], nested)
        self.assertIs(state["nested"], state_nested)

        self.assertEqual(
            build_reflection_request(
                {
                    "query": "q",
                    "active_subtask": {},
                    "reflection_count": -2,
                    "resolved_calculation_trace": {},
                    "structured_result": {},
                },
                missing_info=[],
                failure_status="",
            )["remaining_retry_budget"],
            3,
        )

        class CountBomb:
            def __int__(self):
                raise RuntimeError("count conversion")

        stopped = []

        class StopState(dict):
            def get(self, key, default=None):
                stopped.append(key)
                return super().get(key, default)

        runtime_owner = Mock()
        evidence_owner = Mock()
        with patch.object(
            financial_reflection_projection,
            "_reflection_runtime_trace_summary",
            runtime_owner,
        ), patch.object(
            financial_reflection_projection,
            "_reflection_evidence_summary",
            evidence_owner,
        ):
            with self.assertRaisesRegex(RuntimeError, "count conversion"):
                build_reflection_request(
                    StopState(active_subtask={}, reflection_count=CountBomb()),
                    missing_info=[],
                    failure_status="",
                )
        self.assertEqual(stopped, ["active_subtask", "reflection_count"])
        runtime_owner.assert_not_called()
        evidence_owner.assert_not_called()

        evidence_owner = Mock()
        with patch.object(
            financial_reflection_projection,
            "_reflection_runtime_trace_summary",
            side_effect=RuntimeError("runtime summary failed"),
        ), patch.object(
            financial_reflection_projection,
            "_reflection_evidence_summary",
            evidence_owner,
        ):
            with self.assertRaisesRegex(RuntimeError, "runtime summary failed"):
                build_reflection_request(
                    {"active_subtask": {}, "reflection_count": 0},
                    missing_info=[],
                    failure_status="",
                )
        evidence_owner.assert_not_called()

    def test_current_source_reflection_request_plan_bindings_pin_exact_move_boundary(
        self,
    ) -> None:
        graph_path = Path("src/agent/financial_graph_reconciliation.py")
        owner_path = Path("src/agent/financial_reflection_projection.py")
        graph_text = graph_path.read_text(encoding="utf-8-sig")
        owner_text = owner_path.read_text(encoding="utf-8-sig")
        graph_tree = ast.parse(graph_text)
        owner_tree = ast.parse(owner_text)
        retired_normalizer = "_" + "normalise_reflection_plan_record"
        retired_builder = "_" + "build_reflection_request"
        retired_names = {
            retired_normalizer,
            retired_builder,
        }
        selected_names = {
            "normalise_reflection_plan_record",
            "_reflection_runtime_trace_summary",
            "_reflection_evidence_summary",
            "build_reflection_request",
        }
        graph_definitions = {
            node.name: node
            for node in graph_tree.body
            if isinstance(node, ast.FunctionDef)
            and node.name in (selected_names | retired_names)
        }
        graph_class = next(
            node
            for node in graph_tree.body
            if isinstance(node, ast.ClassDef)
            and node.name == "FinancialAgentReconciliationMixin"
        )
        graph_definitions.update(
            {
                node.name: node
                for node in graph_class.body
                if isinstance(node, ast.FunctionDef)
                and node.name in (selected_names | retired_names)
            }
        )
        self.assertEqual(graph_definitions, {})
        owner_definitions = {
            node.name: node
            for node in owner_tree.body
            if isinstance(node, ast.FunctionDef) and node.name in selected_names
        }
        self.assertEqual(set(owner_definitions), selected_names)
        self.assertEqual(
            {
                name: node.end_lineno - node.lineno + 1
                for name, node in owner_definitions.items()
            },
            {
                "normalise_reflection_plan_record": 35,
                "_reflection_runtime_trace_summary": 15,
                "_reflection_evidence_summary": 7,
                "build_reflection_request": 21,
            },
        )
        self.assertEqual(
            financial_reflection_projection.ALLOWED_REFLECTION_RETRY_STRATEGIES,
            {
                "retry_retrieval",
                "synthesize_from_task_outputs",
                "stop_insufficient",
            },
        )
        self.assertEqual(
            financial_reflection_projection.DEFAULT_REFLECTION_RETRY_BUDGET,
            1,
        )
        self.assertFalse(
            hasattr(
                financial_graph_reconciliation,
                "ALLOWED_REFLECTION_RETRY_STRATEGIES",
            )
        )
        self.assertFalse(
            hasattr(
                financial_graph_reconciliation,
                "DEFAULT_REFLECTION_RETRY_BUDGET",
            )
        )
        self.assertNotIn(retired_normalizer, graph_text)
        self.assertNotIn(retired_normalizer, owner_text)
        self.assertNotIn(retired_builder, graph_text)
        self.assertNotIn(retired_builder, owner_text)

        target_names = retired_names | selected_names

        def collect_calls(tree, module_label):
            parent = {
                child: node
                for node in ast.walk(tree)
                for child in ast.iter_child_nodes(node)
            }

            def enclosing_function(node):
                current = parent.get(node)
                while current is not None and not isinstance(current, ast.FunctionDef):
                    current = parent.get(current)
                return current.name if isinstance(current, ast.FunctionDef) else ""

            calls = []
            non_call_loads = []
            for node in ast.walk(tree):
                target = None
                receiver = ""
                if isinstance(node, ast.Name) and node.id in target_names:
                    target = node.id
                elif isinstance(node, ast.Attribute) and node.attr in target_names:
                    target = node.attr
                    receiver = ast.unparse(node.value)
                else:
                    continue
                parent_node = parent.get(node)
                if not (
                    isinstance(parent_node, ast.Call)
                    and parent_node.func is node
                ):
                    non_call_loads.append(
                        (target, receiver, type(parent_node).__name__)
                    )
                    continue
                try_depth = 0
                current = parent.get(parent_node)
                while current is not None:
                    if isinstance(current, ast.Try):
                        try_depth += 1
                    current = parent.get(current)
                calls.append(
                    (
                        module_label,
                        target,
                        enclosing_function(parent_node),
                        receiver,
                        tuple(ast.unparse(arg) for arg in parent_node.args),
                        tuple(
                            (keyword.arg, ast.unparse(keyword.value))
                            for keyword in parent_node.keywords
                        ),
                        try_depth,
                    )
                )
            return calls, non_call_loads

        graph_calls, graph_non_calls = collect_calls(graph_tree, "graph")
        owner_calls, owner_non_calls = collect_calls(owner_tree, "owner")
        self.assertEqual(graph_non_calls, [])
        self.assertEqual(owner_non_calls, [])
        self.assertCountEqual(
            [*graph_calls, *owner_calls],
            [
                (
                    "owner",
                    "_reflection_runtime_trace_summary",
                    "build_reflection_request",
                    "",
                    ("state",),
                    (),
                    0,
                ),
                (
                    "owner",
                    "_reflection_evidence_summary",
                    "build_reflection_request",
                    "",
                    ("state",),
                    (),
                    0,
                ),
                (
                    "graph",
                    "build_reflection_request",
                    "_plan_reflection_retry",
                    "",
                    ("state",),
                    (
                        ("missing_info", "missing_info"),
                        ("failure_status", "failure_status"),
                    ),
                    0,
                ),
                (
                    "graph",
                    "normalise_reflection_plan_record",
                    "_plan_reflection_retry",
                    "",
                    ("reflection_plan.model_dump()",),
                    (
                        ("fallback_plan", "heuristic_plan"),
                        ("missing_info", "missing_info"),
                        ("preferred_sections", "preferred_sections"),
                    ),
                    1,
                ),
            ],
        )

        self.assertEqual(len(graph_calls), 2)
        self.assertEqual(len(owner_calls), 2)
        current_owner_spans = {
            name: node.end_lineno - node.lineno + 1
            for name, node in owner_definitions.items()
        }
        self.assertEqual(
            current_owner_spans,
            {
                "normalise_reflection_plan_record": 35,
                "_reflection_runtime_trace_summary": 15,
                "_reflection_evidence_summary": 7,
                "build_reflection_request": 21,
            },
        )
        self.assertEqual(sum(current_owner_spans.values()), 78)
        self.assertEqual(
            sum(
                call[1]
                in {
                    "normalise_reflection_plan_record",
                    "build_reflection_request",
                }
                for call in graph_calls
            ),
            2,
        )
        self.assertEqual(
            sum(
                call[1]
                in {
                    "_reflection_runtime_trace_summary",
                    "_reflection_evidence_summary",
                }
                for call in owner_calls
            ),
            2,
        )

        graph_public_bindings = {
            alias.asname or alias.name
            for node in graph_tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "src.agent.financial_reflection_projection"
            for alias in node.names
        }
        self.assertTrue(
            {
                "normalise_reflection_plan_record",
                "build_reflection_request",
            }.issubset(graph_public_bindings)
        )

        module_graph = {}
        for path in Path("src/agent").glob("*.py"):
            module_name = f"src.agent.{path.stem}"
            module_graph[module_name] = set()
            module_tree = ast.parse(path.read_text(encoding="utf-8-sig"))
            for node in ast.walk(module_tree):
                if (
                    isinstance(node, ast.ImportFrom)
                    and node.module
                    and node.module.startswith("src.agent.")
                ):
                    module_graph[module_name].add(node.module)
                elif isinstance(node, ast.Import):
                    module_graph[module_name].update(
                        alias.name
                        for alias in node.names
                        if alias.name.startswith("src.agent.")
                    )

        def reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(module_graph.get(current, ()))
            return False

        owner_module = "src.agent.financial_reflection_projection"
        runtime_module = "src.agent.financial_runtime_trace"
        graph_module = "src.agent.financial_graph_reconciliation"
        self.assertFalse(reaches(runtime_module, owner_module))
        self.assertFalse(reaches(owner_module, graph_module))
        simulated_graph = {key: set(value) for key, value in module_graph.items()}
        simulated_graph[owner_module].add(runtime_module)

        def simulated_reaches(start, target):
            pending = [start]
            seen = set()
            while pending:
                current = pending.pop()
                if current == target:
                    return True
                if current in seen:
                    continue
                seen.add(current)
                pending.extend(simulated_graph.get(current, ()))
            return False

        self.assertFalse(simulated_reaches(runtime_module, owner_module))
        self.assertFalse(simulated_reaches(owner_module, graph_module))

        baseline = json.loads(
            (Path("tests") / "fixtures" / "runtime_domain_terms_baseline.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(len(baseline["records"]), 217)
        selected_lines = set()
        for node in owner_definitions.values():
            selected_lines.update(range(node.lineno, node.end_lineno + 1))
        self.assertEqual(
            [
                record
                for record in baseline["records"]
                if record.get("path")
                == "src/agent/financial_reflection_projection.py"
                and selected_lines.intersection(record.get("first_lines") or [])
            ],
            [],
        )

    def test_current_source_reflection_plan_caller_pins_args_adoption_and_exception_scope(
        self,
    ) -> None:
        events = []
        nested_state = {"keep": True}
        state = {
            "query": "reflection query",
            "topic": "reflection topic",
            "intent": "qa",
            "years": [],
            "companies": [],
            "seed_retrieved_docs": [],
            "evidence_status": "missing_evidence",
            "planner_debug_trace": {"prior": True},
            "nested": nested_state,
        }
        state_before = deepcopy(state)
        runtime_trace = {
            "calculation_operands": [],
            "calculation_plan": {
                "status": "incomplete",
                "missing_info": [" missing value "],
            },
            "calculation_result": {"status": "failed"},
        }
        reflection_request = {"request": True}
        heuristic_plan = {
            "status": "ready",
            "retry_strategy": "retry_retrieval",
            "missing_info": ["missing value"],
            "subqueries": ["fallback query"],
            "preferred_sections": ["section"],
            "explanation": "heuristic",
        }
        plan_dump = {
            "status": "ready",
            "retry_strategy": "retry_retrieval",
            "missing_info": ["missing value"],
            "subqueries": ["planned query"],
            "preferred_sections": ["section"],
            "explanation": "planned",
        }
        normalized_plan = {
            **plan_dump,
            "normalized": True,
        }
        build_calls = []
        normalize_calls = []

        def resolve(actual_state, *, allow_legacy_top_level):
            events.append("resolve")
            self.assertIsNot(actual_state, state)
            self.assertIs(actual_state["nested"], nested_state)
            self.assertFalse(allow_legacy_top_level)
            return runtime_trace

        def build_request(actual_state, *, missing_info, failure_status):
            events.append("build")
            build_calls.append((actual_state, missing_info, failure_status))
            return reflection_request

        def heuristic(actual_state, operands, *, retry_objective, explanation):
            events.append("heuristic")
            self.assertIs(actual_state, state)
            self.assertEqual(operands, runtime_trace["calculation_operands"])
            self.assertIsNot(operands, runtime_trace["calculation_operands"])
            self.assertEqual(retry_objective, "find_missing_values")
            self.assertEqual(explanation, "fallback reflection query plan")
            return heuristic_plan

        class PlanRecord:
            def model_dump(self):
                events.append("model_dump")
                return plan_dump

        class Invoker:
            def invoke(self, payload):
                events.append("invoke")
                self.payload = payload
                return PlanRecord()

        invoker = Invoker()

        class Prompt:
            def __or__(self, structured_llm):
                events.append("compose")
                self.structured_llm = structured_llm
                return invoker

        prompt = Prompt()

        class PhaseLlm:
            def with_structured_output(self, model):
                events.append("structured")
                self.model = model
                return object()

        phase_llm = PhaseLlm()
        model_type = type("ReflectionPlanModel", (), {})

        def normalize(plan, *, fallback_plan, missing_info, preferred_sections):
            events.append("normalize")
            normalize_calls.append(
                (plan, fallback_plan, missing_info, preferred_sections)
            )
            return normalized_plan

        agent = SimpleNamespace(
            _infer_missing_info=Mock(side_effect=AssertionError("inference ran")),
            _heuristic_reflection_query_plan=heuristic,
            _calc_metric_family=Mock(return_value=""),
            _llm_for_phase=Mock(return_value=phase_llm),
        )

        with patch.object(
            financial_graph_reconciliation,
            "_resolve_runtime_calculation_trace",
            side_effect=resolve,
        ), patch.object(
            financial_graph_reconciliation,
            "_preferred_calc_sections",
            return_value=["section"],
        ), patch.object(
            financial_graph_reconciliation,
            "_is_ratio_percent_query",
            return_value=False,
        ), patch.object(
            financial_graph_reconciliation,
            "_is_percent_point_difference_query",
            return_value=False,
        ), patch.object(
            financial_graph_reconciliation,
            "RECONCILIATION_POLICY",
            {
                "reflection_sum_query_markers": (),
                "reflection_binding_query_pattern": "",
                "reflection_prompt_template": "template",
            },
        ), patch.object(
            financial_graph_reconciliation,
            "get_financial_ontology",
            return_value=Mock(),
        ), patch.object(
            financial_graph_reconciliation,
            "_reflection_query_plan_model",
            return_value=model_type,
        ), patch.object(
            financial_graph_reconciliation,
            "_chat_prompt_template_from_template",
            return_value=prompt,
        ), patch.object(
            financial_graph_reconciliation,
            "build_reflection_request",
            side_effect=build_request,
        ), patch.object(
            financial_graph_reconciliation,
            "normalise_reflection_plan_record",
            side_effect=normalize,
        ):
            update = FinancialAgentReconciliationMixin._plan_reflection_retry(
                agent, state
            )

        self.assertIs(build_calls[0][0], state)
        self.assertEqual(build_calls[0][1], ["missing value"])
        self.assertEqual(build_calls[0][2], "failed")
        self.assertEqual(len(normalize_calls), 1)
        self.assertIs(normalize_calls[0][0], plan_dump)
        self.assertIs(normalize_calls[0][1], heuristic_plan)
        self.assertEqual(normalize_calls[0][2], ["missing value"])
        self.assertEqual(normalize_calls[0][3], ["section"])
        self.assertIs(update["reflection_plan"], normalized_plan)
        self.assertIs(update["reflection_request"], reflection_request)
        self.assertIs(
            update["planner_debug_trace"]["reflection_plan"], normalized_plan
        )
        self.assertIs(
            update["planner_debug_trace"]["reflection_request"],
            reflection_request,
        )
        self.assertEqual(update["missing_info"], ["missing value"])
        self.assertEqual(update["retry_reason"], "planned")
        self.assertLess(events.index("resolve"), events.index("build"))
        self.assertLess(events.index("build"), events.index("heuristic"))
        self.assertLess(events.index("heuristic"), events.index("invoke"))
        self.assertLess(events.index("invoke"), events.index("model_dump"))
        self.assertLess(events.index("model_dump"), events.index("normalize"))
        self.assertEqual(state, state_before)
        self.assertIs(state["nested"], nested_state)

        downstream_ratio = Mock()
        failing_build = Mock(side_effect=RuntimeError("request failed"))
        failing_agent = SimpleNamespace(
            _infer_missing_info=Mock(side_effect=AssertionError("inference ran")),
        )
        with patch.object(
            financial_graph_reconciliation,
            "_resolve_runtime_calculation_trace",
            return_value=runtime_trace,
        ), patch.object(
            financial_graph_reconciliation,
            "_preferred_calc_sections",
            return_value=["section"],
        ), patch.object(
            financial_graph_reconciliation,
            "_is_ratio_percent_query",
            downstream_ratio,
        ), patch.object(
            financial_graph_reconciliation,
            "build_reflection_request",
            failing_build,
        ):
            with self.assertRaisesRegex(RuntimeError, "request failed"):
                FinancialAgentReconciliationMixin._plan_reflection_retry(
                    failing_agent, state
                )
        failing_build.assert_called_once_with(
            state,
            missing_info=["missing value"],
            failure_status="failed",
        )
        downstream_ratio.assert_not_called()
        self.assertEqual(state, state_before)

        caught_heuristic = dict(heuristic_plan)

        def caught_heuristic_owner(
            actual_state, operands, *, retry_objective, explanation
        ):
            return caught_heuristic

        caught_agent = SimpleNamespace(
            _infer_missing_info=Mock(side_effect=AssertionError("inference ran")),
            _heuristic_reflection_query_plan=caught_heuristic_owner,
            _calc_metric_family=Mock(return_value=""),
            _llm_for_phase=Mock(return_value=PhaseLlm()),
        )
        normalize_failure = Mock(side_effect=RuntimeError("normalize failed"))
        with patch.object(
            financial_graph_reconciliation,
            "_resolve_runtime_calculation_trace",
            return_value=runtime_trace,
        ), patch.object(
            financial_graph_reconciliation,
            "_preferred_calc_sections",
            return_value=["section"],
        ), patch.object(
            financial_graph_reconciliation,
            "_is_ratio_percent_query",
            return_value=False,
        ), patch.object(
            financial_graph_reconciliation,
            "_is_percent_point_difference_query",
            return_value=False,
        ), patch.object(
            financial_graph_reconciliation,
            "RECONCILIATION_POLICY",
            {
                "reflection_sum_query_markers": (),
                "reflection_binding_query_pattern": "",
                "reflection_prompt_template": "template",
            },
        ), patch.object(
            financial_graph_reconciliation,
            "get_financial_ontology",
            return_value=Mock(),
        ), patch.object(
            financial_graph_reconciliation,
            "_reflection_query_plan_model",
            return_value=model_type,
        ), patch.object(
            financial_graph_reconciliation,
            "_chat_prompt_template_from_template",
            return_value=Prompt(),
        ), patch.object(
            financial_graph_reconciliation,
            "build_reflection_request",
            return_value=reflection_request,
        ), patch.object(
            financial_graph_reconciliation,
            "normalise_reflection_plan_record",
            normalize_failure,
        ):
            fallback_update = (
                FinancialAgentReconciliationMixin._plan_reflection_retry(
                    caught_agent, state
                )
            )

        normalize_failure.assert_called_once()
        self.assertIs(fallback_update["reflection_plan"], caught_heuristic)
        self.assertIs(fallback_update["reflection_request"], reflection_request)
        self.assertEqual(
            fallback_update["reflection_plan"]["explanation"],
            "heuristic fallback after reflection planner error: normalize failed",
        )
        self.assertEqual(
            fallback_update["planner_debug_trace"]["reflection_error"],
            "normalize failed",
        )
        self.assertEqual(state, state_before)
        self.assertIs(state["nested"], nested_state)

    def test_reflection_report_records_retry_handoff(self) -> None:
        action = reflection_action_from_plan(
            {
                "preferred_sections": [" 재무제표 ", ""],
                "synthesis_source_ids": ["artifact_1", ""],
                "explanation": "retry with focused evidence",
            },
            retry_queries=["find value"],
            retry_strategy="retry_retrieval",
        )

        self.assertEqual(action["action_type"], "retry_retrieval")
        self.assertEqual(action["retry_queries"], ["find value"])
        self.assertEqual(action["retrieval_scope_hints"], ["재무제표"])
        self.assertEqual(action["synthesis_source_ids"], ["artifact_1"])
        self.assertEqual(action["stop_reason"], "retry with focused evidence")

        report = reflection_report_from_action(
            {
                "active_subtask": {
                    "task_id": "task_1",
                    "result_artifact_id": "artifact_1",
                }
            },
            reflection_action={
                "action_type": "retry_retrieval",
                "retry_queries": ["find value"],
                "retrieval_scope_hints": [],
                "synthesis_source_ids": [],
                "stop_reason": "",
            },
            reflection_request={"failure_status": "incomplete"},
        )

        self.assertEqual(report["outcome"], "retry_prepared")
        self.assertEqual(report["action_taken"], "retry_retrieval")
        self.assertEqual(report["budget_consumed"], 1)
        self.assertEqual(report["target_task_ids"], ["task_1"])
        self.assertEqual(report["target_artifact_ids"], ["artifact_1"])
        self.assertEqual(report["blocking_issues"], [])

    def test_reflection_report_records_stop_reason_without_retry_budget(self) -> None:
        report = reflection_report_from_action(
            {"active_subtask": {"task_id": "task_1"}},
            reflection_action={
                "action_type": "stop_insufficient",
                "retry_queries": [],
                "retrieval_scope_hints": [],
                "synthesis_source_ids": [],
                "stop_reason": "no grounded evidence",
            },
            reflection_request={"failure_status": "missing_evidence"},
        )

        self.assertEqual(report["outcome"], "stop_requested")
        self.assertEqual(report["action_taken"], "stop_insufficient")
        self.assertEqual(report["budget_consumed"], 0)
        self.assertEqual(
            report["blocking_issues"],
            [{"type": "stop_insufficient", "reason": "no grounded evidence"}],
        )

    def test_task_artifact_integrity_feedback_projects_error_issues(self) -> None:
        feedback = task_artifact_integrity_feedback(
            {
                "integrity_status": "error",
                "integrity_issues": [
                    {
                        "severity": "warning",
                        "type": "task_without_artifacts",
                        "task_id": "task_warn",
                    },
                    {
                        "severity": "error",
                        "type": "missing_required_artifact_kind",
                        "task_id": "task_1",
                        "artifact_kind": "calculation_result",
                    },
                    {
                        "severity": "error",
                        "type": "missing_required_artifact_payload",
                        "task_id": "task_1",
                        "artifact_id": "artifact_result",
                        "payload_key": "calculation_result.rendered_value",
                    },
                ],
            }
        )

        self.assertIn("Task/artifact ledger integrity error", feedback)
        self.assertIn("missing_required_artifact_kind:task_1:calculation_result", feedback)
        self.assertIn(
            "missing_required_artifact_payload:task_1:artifact_result:calculation_result.rendered_value",
            feedback,
        )
        self.assertNotIn("task_without_artifacts", feedback)

    def test_task_artifact_integrity_feedback_ignores_non_error_status(self) -> None:
        self.assertEqual(task_artifact_integrity_feedback({"integrity_status": "ok"}), "")


if __name__ == "__main__":
    unittest.main()
