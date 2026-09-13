"""Anonymous fault injection: observations survive; no interrupted answer exists."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
import json
from threading import Barrier
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.benchmark_runner import _serialise_eval_results
from src.ops.evaluator import EvalExample, RAGEvaluator
from src.utils.provider_errors import ProviderAdmissionError
from src.utils.request_diagnostics import capture_request_diagnostics
from tests.semantic_program_test_support import _candidate, _obligation, _StructuredQueueLLM
from tests import test_compiler_attempt_debug as attempt_fixture
from tests import test_financial_phase_contract as phase_fixture


class _StopQueue(_StructuredQueueLLM):
    def invoke(self, prompt):
        response = super().invoke(prompt)
        if isinstance(response, BaseException):
            raise response
        return response


def _events(snapshot, kind):
    return [event for event in snapshot["events"] if event["kind"] == kind]


class InterruptedRunDiagnosticsTests(unittest.TestCase):
    def agent(self, *, stop_at="retry", name="Larch"):
        fixture = attempt_fixture.CompilerAttemptDebugTests()
        fixture.setUp()
        stop = ProviderAdmissionError("budget_reservation_exceeded", "synthetic stop")
        accepted = SemanticCalculationProgram(direct_bindings=[{"obligation_id": "size", "candidate_id": "size-cell"}])
        owners, catalog = [fixture.owner], fixture.catalog
        responses = [fixture.bad, stop]
        if stop_at == "first":
            responses = [stop]
        elif stop_at == "island":
            owners, catalog = [_obligation("size", "direct_value", "Size"), fixture.owner], [_candidate("size-cell", 12), *catalog]
            responses = [accepted, stop]
        elif stop_at == "none":
            responses = [fixture.good]
        agent = phase_fixture.FinancialPhaseContractTests._narrative_agent()
        del agent._project_runtime_calculation_trace
        agent._plan_answer_obligation_program = Mock(return_value={
            "semantic_plan": {"program_required": True}, "answer_obligations": owners,
            "retrieval_queries": [name]})
        agent._semantic_source_candidates_for_state = Mock(return_value=[])
        agent._semantic_candidate_catalog_for_state = Mock(return_value=catalog)
        agent.llm, agent.llm_routes = _StopQueue(*responses), {}
        if stop_at != "none":
            agent._execute_semantic_calculation_program = Mock(side_effect=AssertionError("must not execute"))
            agent._assemble_final_phase = Mock(side_effect=AssertionError("must not assemble"))
        agent.graph = agent._build_graph()
        return agent, stop, accepted

    def test_stop_before_first_response_keeps_plan_and_pending_attempt_not_fake_response(self):
        agent, stop, _ = self.agent(stop_at="first")
        with capture_request_diagnostics() as captured:
            with self.assertRaises(ProviderAdmissionError) as raised:
                agent.run("Describe activity.", include_debug_bundle=True)
        self.assertIs(raised.exception, stop)
        self.assertEqual(len(captured), 1)
        snapshot = captured[0]
        phases = _events(snapshot, "phase_completed")
        self.assertEqual([e["location"]["phase"] for e in phases], ["routing", "requirements", "retrieval", "candidates"])
        self.assertTrue(phases[1]["data"]["answer_obligations"])
        self.assertEqual(len(_events(snapshot, "compiler_request")), 1)
        self.assertEqual(_events(snapshot, "compiler_attempt"), [])
        self.assertEqual(_events(snapshot, "run_interrupted")[0]["data"]["code"], stop.code)
        agent._execute_semantic_calculation_program.assert_not_called()
        agent._assemble_final_phase.assert_not_called()

    def test_retry_and_next_island_keep_observed_programs_and_no_final_result(self):
        for at in ("retry", "island"):
            with self.subTest(at=at):
                agent, stop, accepted = self.agent(stop_at=at)
                with capture_request_diagnostics() as captured:
                    with self.assertRaises(ProviderAdmissionError) as raised:
                        agent.run("Describe activity and size.", include_debug_bundle=True)
                self.assertIs(raised.exception, stop)
                attempts = _events(captured[0], "compiler_attempt")
                self.assertEqual(len(attempts), 1)
                self.assertIsNotNone(attempts[0]["data"]["model_program_json"])
                calls = _events(captured[0], "compiler_request")
                self.assertEqual(len(calls), 2)
                self.assertEqual(len(agent.llm.prompts), 2)
                self.assertEqual(calls[0]["location"]["island_id"] == calls[1]["location"]["island_id"], at == "retry")
                self.assertEqual([c["location"]["attempt"] for c in calls], [1, 2] if at == "retry" else [1, 1])
                if at == "retry":
                    self.assertTrue(attempts[0]["data"]["validation_errors"])
                    self.assertTrue(all(e.get("location") for e in attempts[0]["data"]["validation_errors"]))
                else:
                    island = _events(captured[0], "compiler_island_completed")[0]
                    self.assertEqual(island["data"]["program_json"],
                        json.dumps(accepted.model_dump(), ensure_ascii=False, separators=(",", ":")))
                self.assertEqual(_events(captured[0], "run_completed"), [])
                agent._execute_semantic_calculation_program.assert_not_called()

    def test_evaluator_exports_interrupted_only_and_does_not_feed_draft_to_judge(self):
        agent, _, _ = self.agent()
        evaluator = RAGEvaluator(agent, skip_llm_judges=True)
        example = EvalExample(id="anonymous", question="Describe activity.", ground_truth="", company="Larch", year=2024, section="Activity")
        with patch("src.ops.evaluator._compute_completeness", return_value=0.0) as judge:
            result = evaluator.evaluate_one(example)
        self.assertEqual(result.answer, "")
        self.assertEqual(result.compiler_attempts, [])
        self.assertEqual(result.resolved_calculation_trace, {})
        self.assertEqual(result.task_artifact_trace, {})
        judge.assert_called_once_with(example, "")
        self.assertEqual(len(_events(result.interrupted_run, "compiler_attempt")), 1)
        exported = _serialise_eval_results([result])[0]
        self.assertEqual(exported["interrupted_run"], result.interrupted_run)
        exported["interrupted_run"]["events"].clear()
        self.assertTrue(result.interrupted_run["events"])

    def test_unavailable_responses_do_not_resurrect_failure_program_or_sdk_body(self):
        agent, stop, _ = self.agent(stop_at="island")
        broken = Mock()
        broken.model_dump.side_effect = ValueError("private-sdk-body-sentinel")
        agent.llm = _StopQueue(broken, broken, stop)
        with capture_request_diagnostics() as captured:
            with self.assertRaises(ProviderAdmissionError):
                agent.run("Describe activity and size.", include_debug_bundle=True)
        attempts = _events(captured[0], "compiler_attempt")
        self.assertEqual([event["data"]["model_program_json"] for event in attempts], [None, None])
        self.assertIsNone(_events(captured[0], "compiler_island_completed")[0]["data"]["program_json"])
        self.assertNotIn("private-sdk-body-sentinel", json.dumps(captured))

    def test_debug_off_and_sequential_runs_cannot_reuse_old_observations(self):
        with capture_request_diagnostics() as captured:
            for debug in (True, False, True):
                agent, _, _ = self.agent(stop_at="first")
                with self.assertRaises(ProviderAdmissionError):
                    agent.run("Describe activity.", include_debug_bundle=debug)
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0], captured[1])
        captured[0]["events"].clear()
        self.assertTrue(captured[1]["events"])

    def test_concurrent_requests_and_shared_exception_keep_separate_records(self):
        barrier = Barrier(2)
        shared = ProviderAdmissionError("budget_reservation_exceeded", "shared guard")
        def run(name):
            agent, _, _ = self.agent(stop_at="first", name=name)
            def wait_then_stop(prompt):
                barrier.wait(timeout=10)
                raise shared
            agent.llm.invoke = wait_then_stop
            with capture_request_diagnostics() as captured:
                with self.assertRaises(ProviderAdmissionError) as raised:
                    agent.run(name, include_debug_bundle=True)
            self.assertIs(raised.exception, shared)
            return captured[0]
        with ThreadPoolExecutor(max_workers=2) as executor:
            first, second = list(executor.map(run, ["Larch request", "Cedar request"]))
        self.assertIn("Larch request", json.dumps(first))
        self.assertNotIn("Cedar request", json.dumps(first))
        self.assertIn("Cedar request", json.dumps(second))
        self.assertNotIn("Larch request", json.dumps(second))
        self.assertNotIn("interrupted_run", vars(shared))

    def test_success_preserves_answer_prompt_ledger_and_opt_in_only(self):
        plain, _, _ = self.agent(stop_at="none")
        debug, _, _ = self.agent(stop_at="none")
        result = plain.run("Describe activity.", include_review_trace=True)
        with capture_request_diagnostics() as captured:
            observed = debug.run("Describe activity.", include_review_trace=True, include_debug_bundle=True)
        self.assertIsNone(result.debug_bundle)
        self.assertEqual(result.agent_answer, observed.agent_answer)
        self.assertEqual(result.review_trace, observed.review_trace)
        self.assertEqual(plain.llm.prompts[0].to_messages(), debug.llm.prompts[0].to_messages())
        self.assertEqual(observed.debug_bundle["request_diagnostics"], captured[0])
        self.assertNotIn("request_diagnostics", json.dumps(observed.review_trace))
        self.assertNotIn("model_program_json", json.dumps(observed.agent_answer))

    def test_available_usage_survives_and_snapshot_failure_does_not_replace_stop(self):
        for unavailable in (False, True):
            with self.subTest(unavailable=unavailable):
                agent, stop, _ = self.agent(stop_at="first")
                llm_usage = {"api_calls": 1, "input_tokens": 100}
                embedding_usage = {"api_calls": 2, "input_tokens": 20}
                agent.llm_usage_callback = SimpleNamespace(
                    reset_current_thread=Mock(), set_current_phase=Mock(),
                    snapshot_current_thread=Mock(return_value=llm_usage),
                    snapshot_current_thread_by_phase=Mock(return_value={"planning": llm_usage}))
                agent.vsm = SimpleNamespace(reset_current_thread_embedding_usage=Mock(),
                    get_current_thread_embedding_usage_snapshot=Mock(return_value=embedding_usage))
                if unavailable:
                    agent.llm_usage_callback.snapshot_current_thread.side_effect = ValueError("private snapshot body")
                with capture_request_diagnostics() as captured:
                    with self.assertRaises(ProviderAdmissionError) as raised:
                        agent.run("Describe activity.", include_debug_bundle=True)
                self.assertIs(raised.exception, stop)
                usage = _events(captured[0], "usage_snapshot")[0]["data"]
                self.assertEqual(usage["embedding_usage"], embedding_usage)
                self.assertEqual(usage["llm_usage_by_phase"], {"planning": llm_usage})
                self.assertEqual(usage["llm_usage"],
                    {"observation_unavailable": "ValueError"} if unavailable else llm_usage)
                llm_usage["api_calls"] = 99
                self.assertEqual(usage["llm_usage_by_phase"]["planning"]["api_calls"], 1)
                self.assertNotIn("private snapshot body", json.dumps(captured))

    def test_phase_observation_preserves_inputs_and_copies_retrieved_sources_not_cache(self):
        from langchain_core.documents import Document
        from src.utils.request_diagnostics import request_diagnostic_scope

        agent, _, _ = self.agent(stop_at="none")
        doc = Document(page_content="Exact source (12).", metadata={"source_span": [10, 28]})
        state = {"request": {"query": "q", "report_scope": {}}}
        before = deepcopy(state)
        source = [(doc, 0.75)]
        agent._retrieve.return_value = {"seed_retrieved_docs": source,
            "retrieval_query_result_cache": {"private": object()}}
        agent._expand_via_structure_graph.return_value = {"retrieved_docs": source}
        with request_diagnostic_scope(True) as recorder:
            update = agent._retrieve_evidence_phase(state)
        self.assertEqual(state, before)
        self.assertEqual(list(update), ["retrieval"])
        observed = _events(recorder.snapshot(), "phase_completed")[0]["data"]
        self.assertNotIn("retrieval_query_result_cache", observed)
        self.assertEqual(observed["retrieved_docs"][0], {
            "page_content": doc.page_content, "metadata": doc.metadata, "score": 0.75})
        doc.metadata["source_span"][0] = 99
        self.assertEqual(observed["seed_retrieved_docs"][0]["metadata"]["source_span"], [10, 28])


if __name__ == "__main__":
    unittest.main()
