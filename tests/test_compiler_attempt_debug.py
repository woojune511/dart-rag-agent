"""Authored compiler responses test observability, not model interpretation."""

from copy import deepcopy
from tests.narrative_address_test_support import model_program, selection
import hashlib
import json
import unittest
from unittest.mock import Mock, patch

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.agent.financial_agent_run_projection import project_debug_bundle
from src.agent.financial_graph import FinancialAgent, compilation_phase_input, numeric_phase_input
from src.agent.financial_run_result import FinancialRunResultV1, FINANCIAL_RUN_RESULT_SCHEMA_VERSION
from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _case_state
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests.test_narrative_claim_grounding import claim, source
from tests.test_narrative_retry_context import prompt_json


class CompilerAttemptDebugTests(unittest.TestCase):
    def setUp(self):
        self.body = "We serve through distributors."
        self.catalog = [source("note", self.body, source_contexts=[{
            "context_id": "heading", "relation": "ancestor_heading",
            "source_text": "Larch", "source_span": [10, 15],
        }])]
        self.owner = _obligation("activity", "narrative", "Describe activity.")
        self.bad = model_program({"narrative_bindings": [{
            "obligation_id": "activity", "claims": [
                claim("We", self.body, "note", self.body),
                claim("Larch", "In this section, We refers to Larch.", "note", self.body),
            ],
        }]}, self.catalog)
        good = self.bad.model_dump()
        good["narrative_bindings"][0]["subject_bindings"][1]["evidence_selections"].append(
            selection(self.catalog, "note", "Larch", context_id="heading"))
        self.good = SemanticCalculationProgram.model_validate(good)

    def compile(self, responses, *, debug=True, owners=None, catalog=None):
        llm = _StructuredQueueLLM(*responses)
        state = _case_state({"question": "Describe activity and size.",
            "obligations": owners or [self.owner]}, catalog or self.catalog)
        if debug:
            state["include_debug_bundle"] = True
        before = deepcopy(state)
        result = _CompilerOnlyAgent(llm)._compile_semantic_calculation_program(state)
        self.assertEqual(state, before)
        return result, llm

    def test_failed_drafts_survive_pruning_with_exact_validation_locations(self):
        result, llm = self.compile([self.bad, self.bad])
        self.assertEqual(result["semantic_program"]["narrative_bindings"], [])
        attempts = result["compiler_attempts"]
        self.assertEqual(len(attempts), len(llm.prompts))
        self.assertEqual([row["attempt"] for row in attempts], [1, 2])
        for index, row in enumerate(attempts):
            self.assertEqual(row["schema_version"], "compiler_attempt_debug_v1")
            self.assertEqual(row["response_status"], "parsed")
            from tests.compiler_wire_test_support import wire_fixture
            model = llm.model_instances[index]
            self.assertEqual(json.loads(row["model_program_json"]), model.model_validate(wire_fixture(self.bad, model)).model_dump())
            self.assertEqual(json.loads(row["validation_input_program_json"]), self.bad.model_dump())
            self.assertEqual(row["compile_valid_obligation_ids"], [])
            self.assertTrue(row["island_id"])
            self.assertTrue(any(error.get("location") for error in row["validation_errors"]))
            for key in ("model_program", "validation_input_program"):
                self.assertEqual(row[key + "_sha256"],
                    hashlib.sha256(row[key + "_json"].encode("utf-8")).hexdigest())
        self.assertEqual(attempts[0]["retry_feedback_text"], "-")
        self.assertEqual(llm.prompts[1].fixture_references.project(json.loads(attempts[1]["retry_feedback_text"]), reverse=True),
            prompt_json(llm.prompts[1], "재시도 피드백(없으면 -):"))

    def test_debug_toggle_changes_no_prompt_validation_or_accepted_island(self):
        accepted = SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": "size-cell"}])
        owners = [_obligation("size", "direct_value", "Size"), self.owner]
        catalog = [_candidate("size-cell", 12), *self.catalog]
        plain, plain_llm = self.compile([accepted, self.bad, self.good],
            debug=False, owners=owners, catalog=catalog)
        debug, debug_llm = self.compile([accepted, self.bad, self.good],
            owners=owners, catalog=catalog)
        attempts = debug.pop("compiler_attempts")
        self.assertNotIn("compiler_attempts", plain)
        self.assertEqual(debug, plain)
        self.assertEqual([p.to_messages() for p in debug_llm.prompts],
            [p.to_messages() for p in plain_llm.prompts])
        self.assertEqual([row["active_obligation_ids"] for row in attempts],
            [["size"], ["activity"], ["activity"]])
        self.assertNotEqual(attempts[0]["island_id"], attempts[1]["island_id"])
        self.assertEqual(attempts[1]["island_id"], attempts[2]["island_id"])
        self.assertEqual(attempts[0]["compile_valid_obligation_ids"], ["size"])
        self.assertEqual(attempts[2]["compile_valid_obligation_ids"], ["activity"])
        self.assertNotIn("size-cell", json.dumps(
            json.loads(attempts[2]["retry_feedback_text"])["unvalidated_narrative_drafts"]))
        self.assertEqual(debug["semantic_program"]["direct_bindings"],
            accepted.model_dump()["direct_bindings"])
        self.assertNotIn("compiler_attempts", debug["resolved_calculation_trace"]["calculation_plan"])

    def test_targeted_model_response_and_merged_validation_input_are_distinct(self):
        accepted = {"obligation_id": "reference", "claims": [
            claim("Cedar", "Cedar uses direct delivery.", "reference-note", "Cedar uses direct delivery.")]}
        initial = model_program({"narrative_bindings": [accepted, *self.bad.model_dump()["narrative_bindings"]]},
            [source("reference-note", "Cedar uses direct delivery."), *self.catalog])
        owners = [_obligation("reference", "narrative", "Reference"),
            {**self.owner, "depends_on": ["reference"]}]
        result, llm = self.compile([initial, self.good], owners=owners,
            catalog=[source("reference-note", "Cedar uses direct delivery."), *self.catalog])
        first, retry = result["compiler_attempts"]
        self.assertEqual(first["compile_valid_obligation_ids"], ["reference"])
        self.assertEqual(retry["active_obligation_ids"], ["activity"])
        from tests.compiler_wire_test_support import wire_fixture
        model = llm.model_instances[1]
        self.assertEqual(json.loads(retry["model_program_json"]), model.model_validate(wire_fixture(self.good, model)).model_dump())
        merged = json.loads(retry["validation_input_program_json"])
        original = initial.model_dump()["narrative_bindings"][0]
        self.assertEqual(merged["narrative_bindings"][0], original)
        self.assertEqual(result["semantic_program"]["narrative_bindings"][0], original)
        self.assertNotEqual(retry["model_program_sha256"], retry["validation_input_program_sha256"])
        self.assertNotIn("reference-note", retry["model_program_json"])
        self.assertEqual(retry["compile_valid_obligation_ids"], ["reference", "activity"])

    def test_unavailable_schema_response_is_not_a_fabricated_program_or_exception_body(self):
        broken = Mock()
        broken.model_dump.side_effect = ValueError("private provider response body")
        result, llm = self.compile([broken, self.good])
        self.assertEqual(len(llm.prompts), 2)
        failed, repaired = result["compiler_attempts"]
        self.assertEqual(failed["response_status"], "unavailable")
        self.assertEqual(failed["response_error_type"], "ValueError")
        for key in ("model_program_json", "model_program_sha256",
                    "validation_input_program_json", "validation_input_program_sha256"):
            self.assertIsNone(failed[key])
        self.assertEqual(repaired["response_status"], "parsed")
        self.assertNotIn("private provider response body", json.dumps(result["compiler_attempts"]))

    def test_preflight_failure_records_no_invented_attempt(self):
        result, llm = self.compile([], owners=[{**self.owner, "depends_on": ["unknown"]}])
        self.assertEqual(llm.prompts, [])
        self.assertEqual(result["compiler_attempts"], [])

    def test_snapshots_and_debug_export_own_their_data(self):
        result, _ = self.compile([self.bad, self.bad])
        before = deepcopy(result["compiler_attempts"])
        projected = project_debug_bundle(debug_traces={}, llm_usage={},
            llm_usage_by_phase={}, embedding_usage={}, compiler_attempts=result["compiler_attempts"])
        projected["compiler_attempts"][0]["validation_errors"][0]["location"] = "edited"
        self.bad.narrative_bindings[0].claims[0].text = "Edited after compilation"
        result["planner_debug_trace"]["program_validation_history"][0]["errors"][0]["detail"] = "edited"
        self.assertEqual(result["compiler_attempts"], before)
        self.assertEqual(json.loads(json.dumps(before)), before)

    def test_only_debug_request_routes_capture_and_exports_attempts(self):
        compiled, _ = self.compile([self.bad, self.bad])
        graph_state = {"request": {"query": "q", "report_scope": {}}, "candidates": {
            "semantic_source_candidates": [], "semantic_candidate_catalog": self.catalog},
            "compilation": compiled}
        self.assertNotIn("include_debug_bundle", compilation_phase_input(graph_state))
        graph_state["request"]["include_debug_bundle"] = True
        before = deepcopy(graph_state)
        self.assertTrue(compilation_phase_input(graph_state)["include_debug_bundle"])
        self.assertNotIn("compiler_attempts", numeric_phase_input(graph_state))
        self.assertEqual(graph_state, before)

        agent = object.__new__(FinancialAgent)
        agent.vsm = None
        agent.llm_usage_callback = None
        final = {"final_result": {"agent_answer": {"answer": "No accepted output."},
            "review_trace": {}, "debug_traces": {}}, "compilation": compiled,
            "ledger": {"tasks": [], "artifacts": [], "task_artifact_trace": {}}}
        agent.graph = Mock()
        agent.graph.invoke.return_value = final
        plain = agent.run("q", include_review_trace=True)
        self.assertNotIn("include_debug_bundle", agent.graph.invoke.call_args.args[0]["request"])
        with_debug = agent.run("q", include_review_trace=True, include_debug_bundle=True)
        self.assertTrue(agent.graph.invoke.call_args.args[0]["request"]["include_debug_bundle"])
        self.assertEqual(plain.agent_answer, with_debug.agent_answer)
        self.assertEqual(plain.review_trace, with_debug.review_trace)
        self.assertIsNone(plain.debug_bundle)
        self.assertEqual(with_debug.debug_bundle["compiler_attempts"], compiled["compiler_attempts"])
        self.assertNotIn("compiler_attempts", json.dumps(plain.to_projection()))

    def test_eval_and_benchmark_export_do_not_feed_drafts_to_judges(self):
        from src.ops.evaluator import EvalExample, RAGEvaluator
        from src.ops.benchmark_runner import _serialise_eval_results

        compiled, _ = self.compile([self.bad, self.bad])
        run_result = FinancialRunResultV1(schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
            agent_answer={"answer": "No accepted output."}, review_trace={},
            debug_bundle={"compiler_attempts": compiled["compiler_attempts"]})
        agent = Mock()
        agent.run.return_value = run_result
        evaluator = RAGEvaluator(agent, skip_llm_judges=True)
        example = EvalExample(id="anon", question="Describe activity.", ground_truth="",
            company="Larch", year=2024, section="Activity")
        with patch("src.ops.evaluator._compute_completeness", return_value=0.0) as judge:
            evaluated = evaluator.evaluate_one(example)
        judge.assert_called_once_with(example, "No accepted output.")
        self.assertTrue(agent.run.call_args.kwargs["include_debug_bundle"])
        self.assertEqual(evaluated.compiler_attempts, compiled["compiler_attempts"])
        exported = _serialise_eval_results([evaluated])[0]
        self.assertEqual(exported["compiler_attempts"], compiled["compiler_attempts"])
        self.assertNotIn("compiler_attempts", json.dumps(evaluated.resolved_calculation_trace))
        self.assertNotIn(self.body, evaluated.answer)
        exported["compiler_attempts"][0]["validation_errors"].clear()
        self.assertTrue(evaluated.compiler_attempts[0]["validation_errors"])
        self.assertTrue(compiled["compiler_attempts"][0]["validation_errors"])

    def test_real_graph_keeps_capture_per_request_and_out_of_final_ledger(self):
        from tests.test_financial_phase_contract import FinancialPhaseContractTests

        agent = FinancialPhaseContractTests._agent()
        owner = _obligation("size", "direct_value", "Size")
        agent._plan_answer_obligation_program = Mock(return_value={
            "semantic_plan": {"program_required": True}, "answer_obligations": [owner],
            "retrieval_queries": ["Size?"]})
        agent._semantic_source_candidates_for_state = Mock(return_value=[])
        agent._semantic_candidate_catalog_for_state = Mock(return_value=[_candidate("cell", 12)])
        response = SemanticCalculationProgram(direct_bindings=[{
            "obligation_id": "size", "candidate_id": "cell"}])
        agent.llm = _StructuredQueueLLM(response, response, response)
        agent.llm_routes = {}
        agent.graph = agent._build_graph()
        results = [agent.run("Size?", include_review_trace=True, include_debug_bundle=flag)
            for flag in (False, True, False)]
        self.assertEqual(len(agent.llm.prompts), 3)
        self.assertIsNone(results[0].debug_bundle)
        self.assertIsNone(results[2].debug_bundle)
        self.assertEqual(len(results[1].debug_bundle["compiler_attempts"]), 1)
        for result in results:
            self.assertEqual(result.agent_answer, results[0].agent_answer)
            self.assertEqual(result.review_trace["task_artifact_trace"]["integrity_status"], "ok")
            self.assertNotIn("compiler_attempts", json.dumps(result.review_trace))
            self.assertNotIn("model_program_json", json.dumps(result.agent_answer))


if __name__ == "__main__":
    unittest.main()
