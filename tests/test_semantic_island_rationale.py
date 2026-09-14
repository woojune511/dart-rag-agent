"""Global compilation explanations do not concatenate island-local model claims."""

from copy import deepcopy
import hashlib
import json
import unittest
from unittest.mock import patch

from src.agent.financial_calculation_execution import execute_semantic_calculation_program
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def direct(owner, *, rationale="", **extra):
    return {"status": "ready", "direct_bindings": [{"obligation_id": owner, "candidate_id": "source-value"}],
            "rationale": rationale, **extra}


class RecordingAgent(_CompilerOnlyAgent):
    def __init__(self, llm):
        super().__init__(llm)
        self.island_programs = []

    def _compile_semantic_calculation_island(self, *args, **kwargs):
        result = super()._compile_semantic_calculation_island(*args, **kwargs)
        self.island_programs.append(deepcopy(result["semantic_program"]))
        return result


class SemanticIslandRationaleTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("provider forbidden")))

    def compile(self, owners, programs):
        catalog = [_candidate("source-value", 10)]
        obligations = [_obligation(owner, "direct_value", "quantity") for owner in owners]
        state = _case_state({"question": "Read the requested quantities.", "obligations": obligations}, catalog)
        before = deepcopy((state, programs))
        llm = _StructuredQueueLLM(*[SemanticCalculationProgram.model_validate(program) for program in programs])
        agent = RecordingAgent(llm)
        compiled = agent._compile_semantic_calculation_program(state)
        self.assertEqual((state, programs), before)
        execution = execute_semantic_calculation_program(program=compiled["semantic_program"],
            obligations=obligations, candidate_catalog=catalog, query=state["query"],
            compilation_envelope=compiled["semantic_compilation_envelope"])
        return compiled, execution, agent, llm

    def assert_summary(self, compiled, execution):
        validation = compiled["semantic_program_validation"]
        explanation = compiled["semantic_program"]["rationale"]
        summary = json.loads(explanation)
        self.assertEqual(summary["validation_status"], validation["status"])
        self.assertEqual(summary["missing_obligation_ids"], validation["missing_obligation_ids"])
        self.assertEqual(summary["ambiguous_obligation_ids"], validation["ambiguous_obligation_ids"])
        self.assertEqual(summary["error_codes"], list(dict.fromkeys(row["code"] for row in validation["errors"])))
        plan = compiled["resolved_calculation_trace"]["calculation_plan"]
        self.assertEqual(plan["explanation"], explanation)
        # Successful/partial execution carries the same authorized explanation.
        if "explanation" in execution.get("calculation_result", {}):
            self.assertEqual(execution["calculation_result"]["explanation"], explanation)
        self.assertNotIn("validation_drift", str(execution.get("execution_errors", [])))
        return summary

    def test_other_island_missing_claim_is_not_the_global_explanation(self):
        stale = "The second requested output is unavailable."
        first = direct("first", rationale=stale)
        second = direct("second", rationale="The second output is directly reported.")
        compiled, execution, agent, llm = self.compile(["first", "second"], [first, second])
        self.assertEqual(execution["status"], "ok")
        self.assertEqual(len(llm.prompts), 2)
        self.assertEqual(compiled["semantic_program_retry_count"], 0)
        self.assertNotIn(stale, compiled["semantic_program"]["rationale"])
        summary = self.assert_summary(compiled, execution)
        self.assertEqual(summary["valid_obligation_ids"], ["first", "second"])
        self.assertEqual(summary["missing_obligation_ids"], [])
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["islands"]
        self.assertEqual([row["program_rationale"] for row in diagnostics], [stale, second["rationale"]])
        for row, program in zip(diagnostics, agent.island_programs, strict=True):
            self.assertEqual(row["accepted_program_fingerprint"], hashlib.sha256(canonical(program)).hexdigest())
        control, control_execution, _, control_llm = self.compile(["first", "second"],
            [direct("first", rationale="First output is reported."), second])
        self.assertEqual(compiled["semantic_program"], control["semantic_program"])
        self.assertEqual(execution, control_execution)
        self.assertEqual([str(prompt) for prompt in llm.prompts], [str(prompt) for prompt in control_llm.prompts])

    def test_real_missing_and_ambiguous_owners_remain_in_summary(self):
        compiled, execution, _, llm = self.compile(["withheld", "uncertain", "bound"], [
            {"status": "incomplete", "missing_obligation_ids": ["withheld"], "rationale": "No matching period."},
            {"status": "ambiguous", "ambiguous_obligation_ids": ["uncertain"], "rationale": "Sources disagree."},
            direct("bound")])
        self.assertEqual(len(llm.prompts), 3)
        summary = self.assert_summary(compiled, execution)
        self.assertEqual(summary["valid_obligation_ids"], ["bound"])
        self.assertIn("withheld", summary["missing_obligation_ids"])
        self.assertEqual(summary["ambiguous_obligation_ids"], ["uncertain"])

    def test_retry_updates_summary_without_rewriting_other_island_program(self):
        accepted = direct("stable", rationale="Peer output is not supplied to this invocation.")
        compiled, execution, agent, llm = self.compile(["stable", "repair"], [accepted,
            {"status": "ready", "direct_bindings": [{"obligation_id": "repair", "candidate_id": "hidden"}],
             "rationale": "Initial unsupported selection."},
            direct("repair", rationale="Use the visible source.")])
        self.assertEqual(len(llm.prompts), 3)
        self.assertEqual(compiled["semantic_program_retry_count"], 1)
        summary = self.assert_summary(compiled, execution)
        self.assertEqual(summary["valid_obligation_ids"], ["stable", "repair"])
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["islands"]
        self.assertEqual(diagnostics[0]["program_rationale"], accepted["rationale"])
        self.assertEqual(diagnostics[0]["accepted_program_fingerprint"], hashlib.sha256(canonical(agent.island_programs[0])).hexdigest())
        self.assertEqual(diagnostics[1]["program_rationale"], "Use the visible source.")

    def test_blocked_islands_have_no_success_claim_or_model_call(self):
        compiled, execution, _, llm = self.compile([f"owner-{index}" for index in range(9)], [])
        self.assertEqual(llm.prompts, [])
        summary = self.assert_summary(compiled, execution)
        self.assertEqual(summary["valid_obligation_ids"], [])
        self.assertEqual(len(summary["missing_obligation_ids"]), 9)
        self.assertNotEqual(summary["validation_status"], "ready")
        diagnostics = compiled["resolved_calculation_trace"]["calculation_plan"]["candidate_stage_diagnostics"]["islands"]
        self.assertTrue(all(row["program_rationale"] == row["blocked_reason"] for row in diagnostics))

    def test_single_island_keeps_its_original_rationale_and_abstention(self):
        for program in [direct("single", rationale="Exact source reading."),
                        {"status": "incomplete", "missing_obligation_ids": ["single"],
                         "rationale": "The requested source period is unavailable."}]:
            with self.subTest(status=program["status"]):
                compiled, _, _, llm = self.compile(["single"], [program])
                self.assertEqual(len(llm.prompts), 1)
                self.assertEqual(compiled["semantic_program"]["rationale"], program["rationale"])


if __name__ == "__main__":
    unittest.main()
