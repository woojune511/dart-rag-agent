"""Planner normalization and compiler retries through their real owner boundaries."""

from __future__ import annotations

import unittest

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate


class PlannerUnitBoundaryTests(unittest.TestCase):
    def _plan_and_compile(self, raw_obligations, *compiler_responses):
        planner = RequirementPlannerOutput.model_validate({
            "topic": "requested quantities", "obligations": raw_obligations,
        })
        llm = _StructuredQueueLLM(planner, *compiler_responses)
        agent = object.__new__(FinancialAgent)
        agent.llm = llm
        agent.llm_routes = {}
        agent.llm_usage_callback = None
        request = {
            "query": "Return the requested quantities.", "report_scope": {},
            "query_type": "numeric_fact", "intent": "numeric_fact",
            "topic": "requested quantities", "companies": [], "years": [],
        }
        planned = agent._plan_answer_obligation_program(request)
        compiled = agent._compile_semantic_calculation_program({
            "query": request["query"], "report_scope": request["report_scope"],
            "semantic_plan": planned["semantic_plan"],
            "answer_obligations": planned["answer_obligations"],
            "active_subtask": planned["active_subtask"],
            "semantic_source_candidates": [],
            "semantic_candidate_catalog": [_candidate("cand_quantity", 10)],
            "semantic_candidate_catalog_prebuilt": True,
        })
        self.assertEqual(llm.responses, [])
        self.assertEqual(compiled["planner_debug_trace"]["program_invocation_errors"], [])
        return llm, planned, compiled

    @staticmethod
    def _direct_response(obligation_id):
        return SemanticCalculationProgram.model_validate({
            "direct_bindings": [{"obligation_id": obligation_id, "candidate_id": "cand_quantity"}],
        })

    def test_unsupported_planner_unit_is_retained_and_only_affected_island_is_blocked(self):
        llm, planned, compiled = self._plan_and_compile(
            [
                {"obligation_id": "bad", "kind": "direct_value", "label": "quantity", "display_unit": "unsupported-unit"},
                {"obligation_id": "good", "kind": "direct_value", "label": "quantity", "display_unit": "COUNT"},
            ],
            self._direct_response("ob_002"),
        )
        obligations = planned["answer_obligations"]
        self.assertEqual([row["obligation_id"] for row in obligations], ["ob_001", "ob_002"])
        self.assertEqual(obligations[0]["display_unit"], "unsupported-unit")
        self.assertTrue(obligations[0]["required"])
        self.assertEqual(planned["semantic_plan"]["requirement_errors"], [{
            "code": "invalid_obligation_unit", "obligation_id": "ob_001",
            "owner_id": "ob_001", "candidate_id": "",
            "location": "obligation.display_unit", "repair_action": "repair_requirements",
            "detail": "unsupported-unit",
        }])
        islands = compiled["planner_debug_trace"]["compilation_islands"]
        self.assertEqual([item["obligation_ids"] for item in islands], [["ob_001"], ["ob_002"]])
        self.assertEqual([item["call_count"] for item in islands], [0, 1])
        self.assertEqual([item["retry_count"] for item in islands], [0, 0])
        self.assertEqual(islands[0]["preflight_errors"], planned["semantic_plan"]["requirement_errors"])
        self.assertEqual(islands[1]["preflight_errors"], [])
        self.assertEqual(llm.models, ["RequirementPlannerOutput", "SemanticCalculationProgram"])
        self.assertEqual(compiled["semantic_program"]["missing_obligation_ids"], ["ob_001"])
        self.assertEqual([row["obligation_id"] for row in compiled["semantic_program"]["direct_bindings"]], ["ob_002"])

    def test_compiler_unit_format_error_retries_same_visible_candidates_once(self):
        def response(result_unit):
            return SemanticCalculationProgram.model_validate({
                "expressions": [{
                    "obligation_id": "ob_001", "formula": "VALUE + VALUE",
                    "result_unit": result_unit, "display_unit": "COUNT",
                    "variable_bindings": [{
                        "variable": "VALUE", "source_id": "cand_quantity",
                        "source_requirement_id": "ob_001:req_001",
                    }],
                    "source_display_candidate_id": None,
                    "source_display_reason": "The source reports the operand only.",
                }],
            })

        llm, planned, compiled = self._plan_and_compile(
            [{
                "obligation_id": "double", "kind": "derived_value", "label": "double quantity",
                "display_unit": "COUNT", "evidence_requirements": [{
                    "requirement_id": "input", "label": "quantity", "required": True,
                }],
            }],
            response("unsupported-unit"), response("COUNT"),
        )
        self.assertEqual(planned["semantic_plan"]["requirement_errors"], [])
        trace = compiled["resolved_calculation_trace"]["calculation_plan"]
        history = trace["program_validation_history"]
        self.assertEqual(len(history), 2)
        self.assertTrue(history[0]["errors"])
        self.assertEqual(
            {(error["code"], error["location"]) for error in history[0]["errors"]},
            {("result_unit_mismatch", "expression.result_unit")},
        )
        for error in history[0]["errors"]:
            self.assertEqual(error["repair_action"], "repair_program")
            self.assertEqual(error["owner_id"], "ob_001")
            self.assertEqual(error["candidate_id"], "")
            self.assertTrue(error["location"])
        self.assertEqual(history[1]["errors"], [])
        self.assertEqual(history[0]["visible_candidate_ids"], ["cand_quantity"])
        self.assertEqual(history[1]["visible_candidate_ids"], history[0]["visible_candidate_ids"])
        self.assertEqual(history[1]["visible_candidate_id_fingerprint"], history[0]["visible_candidate_id_fingerprint"])
        attempts = trace["candidate_stage_diagnostics"]["attempts"]
        self.assertEqual(attempts[1]["source_bundle_fingerprint"], attempts[0]["source_bundle_fingerprint"])
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        self.assertEqual(compiled["planner_debug_trace"]["program_compiler_call_count"], 2)
        self.assertEqual(compiled["semantic_program_validation"]["status"], "ready")
        self.assertEqual(llm.models, ["RequirementPlannerOutput", "SemanticCalculationProgram"])
        self.assertEqual(len(llm.prompts), 3)

    def test_planner_preserves_unknown_and_self_dependencies_for_preflight(self):
        llm, planned, compiled = self._plan_and_compile(
            [
                {"obligation_id": "unknown_owner", "kind": "direct_value", "label": "quantity", "depends_on": ["absent-owner"]},
                {"obligation_id": "self_owner", "kind": "direct_value", "label": "quantity", "depends_on": ["self_owner"]},
                {"obligation_id": "good", "kind": "direct_value", "label": "quantity"},
            ],
            self._direct_response("ob_003"),
        )
        self.assertEqual([row["depends_on"] for row in planned["answer_obligations"]], [["absent-owner"], ["ob_002"], []])
        islands = compiled["planner_debug_trace"]["compilation_islands"]
        self.assertEqual([item["call_count"] for item in islands], [0, 0, 1])
        self.assertEqual([item["retry_count"] for item in islands], [0, 0, 0])
        self.assertEqual(islands[0]["preflight_errors"], [{
            "code": "unknown_dependency", "obligation_id": "ob_001", "detail": "absent-owner",
        }])
        self.assertEqual(islands[1]["preflight_errors"], [{
            "code": "self_dependency", "obligation_id": "ob_002", "detail": "ob_002",
        }])
        self.assertEqual(compiled["semantic_program"]["missing_obligation_ids"], ["ob_001", "ob_002"])
        self.assertEqual([row["obligation_id"] for row in compiled["semantic_program"]["direct_bindings"]], ["ob_003"])
        self.assertEqual(llm.models, ["RequirementPlannerOutput", "SemanticCalculationProgram"])


if __name__ == "__main__":
    unittest.main()
