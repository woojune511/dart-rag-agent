from __future__ import annotations

import copy
import json
import unittest
from types import SimpleNamespace
from typing import get_type_hints
from unittest.mock import Mock

from src.agent.financial_graph import (
    FINANCIAL_GRAPH_PHASE_WRITERS,
    FinancialAgent,
    candidate_phase_input,
    compilation_phase_input,
    numeric_phase_input,
    planning_phase_input,
    retrieval_phase_input,
)
from src.agent.financial_graph_state import (
    CandidateInput,
    CompilationInput,
    FinancialAgentStateV2,
    NumericExecutionInput,
    PlanningInput,
    RetrievalInput,
)
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_reconciliation_candidates import semantic_candidate_stage_diagnostics
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate, _obligation


class FinancialPhaseContractTests(unittest.TestCase):
    @staticmethod
    def _state():
        return {
            "request": {"query": "requested value", "report_scope": {"year": 2024}},
            "routing": {"query_type": "qa", "companies": ["scope"], "years": [2024]},
            "requirements": {
                "semantic_plan": {"program_required": True},
                "answer_obligations": [{"obligation_id": "ob_value"}],
                "topic": "planned topic", "retrieval_queries": ["evidence query"],
            },
            "retrieval": {"retrieved_docs": [], "seed_retrieved_docs": []},
            "candidates": {
                "semantic_source_candidates": [{"evidence_id": "source_1"}],
                "semantic_candidate_catalog": [{"candidate_id": "cand_1"}],
                "semantic_candidate_catalog_prebuilt": True,
            },
            "compilation": {"semantic_program": {"status": "ready"}},
        }

    @staticmethod
    def _agent():
        agent = object.__new__(FinancialAgent)
        agent._plan_answer_obligation_program = Mock(return_value={
            "semantic_plan": {"program_required": True},
            "answer_obligations": [], "retrieval_queries": ["query"],
        })
        agent._retrieve = Mock(return_value={"retrieved_docs": [], "seed_retrieved_docs": []})
        agent._expand_via_structure_graph = Mock(return_value={"retrieved_docs": []})
        agent._format_citations = Mock(return_value={"citations": []})
        agent.llm_usage_callback = None
        agent.vsm = None
        return agent

    def test_phase_inputs_are_typed_explicit_projections_not_phase_merges(self):
        state = self._state()
        state["compilation"]["query"] = "late phase must not overwrite request"
        state["compilation"]["semantic_candidate_catalog"] = [{"candidate_id": "hidden"}]
        state["numeric_result"] = {"query": "another collision", "answer": "unowned answer"}
        state["ledger"] = {"query": "ledger collision", "semantic_program": {"status": "tampered"}}
        original = copy.deepcopy(state)
        projections = (
            (planning_phase_input, PlanningInput),
            (retrieval_phase_input, RetrievalInput),
            (candidate_phase_input, CandidateInput),
            (compilation_phase_input, CompilationInput),
            (numeric_phase_input, NumericExecutionInput),
        )
        for project, contract in projections:
            with self.subTest(project=project.__name__):
                projected = project(state)
                self.assertLessEqual(set(projected), set(get_type_hints(contract)))
                if "query" in projected:
                    self.assertEqual(projected["query"], "requested value")
                self.assertNotIn("tasks", projected)
                self.assertNotIn("artifacts", projected)
                self.assertNotIn("answer", projected)
        self.assertEqual(numeric_phase_input(state)["semantic_candidate_catalog"], [{"candidate_id": "cand_1"}])
        self.assertEqual(numeric_phase_input(state)["semantic_program"], {"status": "ready"})
        self.assertEqual(state, original)

    def test_actual_node_update_annotations_declare_exactly_one_phase_writer(self):
        phase_fields = get_type_hints(FinancialAgentStateV2)
        self.assertEqual(set(phase_fields), set(FINANCIAL_GRAPH_PHASE_WRITERS))
        agent = self._agent()
        agent._semantic_source_candidates_for_state = Mock(return_value=[])
        agent._semantic_candidate_catalog_for_state = Mock(return_value=[])
        agent._compile_semantic_calculation_program = Mock(return_value={"semantic_program": {}})
        agent._execute_semantic_calculation_program = Mock(return_value={"execution": {"status": "ok"}, "calculation_plan": {}, "evidence_items": []})
        phase_methods = {
            "requirements": "_plan_requirements_phase",
            "retrieval": "_retrieve_evidence_phase", "candidates": "_build_candidates_phase",
            "compilation": "_compile_program_phase", "numeric_result": "_execute_numeric_phase",
        }
        for phase, name in phase_methods.items():
            with self.subTest(phase=phase):
                method = getattr(agent, name)
                self.assertEqual(set(get_type_hints(get_type_hints(method)["return"])), {phase})
                update = method(self._state())
                self.assertEqual(set(update), {phase})
                self.assertNotIn("answer", update[phase])
                self.assertNotIn("structured_result", update[phase])
                self.assertNotIn("tasks", update[phase])
                self.assertNotIn("artifacts", update[phase])
        for name, phase in (("_assemble_final_phase", "final_result"), ("_assemble_ledger_phase", "ledger")):
            self.assertEqual(set(get_type_hints(get_type_hints(getattr(agent, name))["return"])), {phase})

    def test_compilation_projection_preserves_source_window_and_attached_cell_diagnostics(self):
        state = self._state()
        doc = SimpleNamespace(page_content="quantity 10", metadata={
            "chunk_uid": "source_1",
            "table_row_records_json": json.dumps([{"cells": [{"value_text": "10", "unit_hint": "COUNT"}]}]),
        })
        source_window = {
            "retrieved_source_ids": ["source_1"], "retrieved_unidentified_count": 0,
            "seed_source_ids": ["source_1"], "seed_unidentified_count": 0,
        }
        state["retrieval"] = {
            "retrieved_docs": [(doc, 1.0)], "seed_retrieved_docs": [(doc, 1.0)],
            "retrieval_debug_trace": {"source_window": source_window},
        }
        projected = compilation_phase_input(state)
        diagnostics = semantic_candidate_stage_diagnostics(
            state=projected, source_candidates=[], catalog=[], prompt_catalog=[],
        )
        self.assertEqual(diagnostics["source_window_origin"], "retrieval_debug_trace")
        self.assertEqual(diagnostics["source_window"], source_window)
        self.assertEqual(diagnostics["physical_deduplication"]["structured_table_attachment_count"], 2)
        self.assertEqual(diagnostics["physical_deduplication"]["attached_physical_cell_projection_count"], 2)

    def test_numeric_graph_keeps_execution_facts_and_final_ledger_consistent(self):
        agent = self._agent()
        obligation = _obligation("ob_value", "direct_value", "quantity")
        task = {"task_id": "task_1", "metric_family": "semantic_program", "metric_label": "quantity", "query": "query", "constraints": {}}
        agent._plan_answer_obligation_program = Mock(return_value={
            "semantic_plan": {"program_required": True, "tasks": [task]},
            "answer_obligations": [obligation], "retrieval_queries": ["query"],
            "active_subtask": task,
        })
        agent._semantic_source_candidates_for_state = Mock(return_value=[])
        agent._semantic_candidate_catalog_for_state = Mock(return_value=[_candidate("cand_1", 10)])
        agent.llm = _StructuredQueueLLM(SemanticCalculationProgram.model_validate({
            "direct_bindings": [{"obligation_id": "ob_value", "candidate_id": "cand_1"}],
        }))
        agent.llm_routes = {}
        graph = agent._build_graph()
        updates = list(graph.stream(agent._initial_state("query", {})))
        ordered_nodes = [next(iter(update)) for update in updates]
        self.assertEqual(ordered_nodes[-4:], ["compile_program", "execute_numeric", "assemble_final", "assemble_ledger"])
        phase_contracts = get_type_hints(FinancialAgentStateV2)
        for update in updates:
            for phase, payload in next(iter(update.values())).items():
                self.assertLessEqual(set(payload), set(get_type_hints(phase_contracts[phase])))
        compiled = updates[-4]["compile_program"]["compilation"]
        numeric = updates[-3]["execute_numeric"]["numeric_result"]
        final = updates[-2]["assemble_final"]["final_result"]
        ledger = updates[-1]["assemble_ledger"]["ledger"]
        self.assertEqual(set(numeric), {"execution", "calculation_plan", "evidence_items"})
        self.assertNotIn("answer", numeric["execution"])
        self.assertNotIn("formatted_result", numeric["execution"]["calculation_result"])
        self.assertEqual(numeric["execution"]["status"], "ok")
        self.assertEqual(compiled["semantic_program_validation"], compiled["semantic_compilation_envelope"].validation_projection())
        self.assertEqual(final["agent_answer"]["answer"], "quantity: 10items")
        self.assertEqual(final["agent_answer"]["structured_result"]["answer"], final["agent_answer"]["answer"])
        self.assertEqual([item["evidence_id"] for item in final["review_trace"]["evidence_items"]], ["cand_1"])
        artifact = next(item for item in ledger["artifacts"] if item["kind"] == "aggregated_answer")
        self.assertEqual(artifact["payload"]["final_answer"], final["agent_answer"]["answer"])
        self.assertEqual(artifact["payload"]["resolved_calculation_trace"], final["agent_answer"]["resolved_calculation_trace"])
        self.assertEqual(ledger["task_artifact_trace"]["integrity_status"], "ok")
        agent.graph = Mock()
        agent.graph.invoke.return_value = {
            "request": {"query": "query", "report_scope": {}},
            "final_result": final, "ledger": ledger,
        }
        result = agent.run("query", include_review_trace=True)
        self.assertEqual(result.agent_answer["answer"], final["agent_answer"]["answer"])
        self.assertEqual(result.agent_answer["citations"], final["agent_answer"]["citations"])
        self.assertEqual(result.review_trace["task_artifact_trace"], ledger["task_artifact_trace"])


if __name__ == "__main__":
    unittest.main()
