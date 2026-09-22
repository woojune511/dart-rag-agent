from contextlib import contextmanager
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

import httpx

from src.ops.compare_rag_workflows import (
    baseline_prompt, batch_cost_ceiling, budget_policy,
    compiled_answer, encoded, fingerprint, prepare, run_arm, run_comparison,
    source_text_packet, verify_plan,
)
from src.ops.provider_admission import BudgetStop, ProviderBudget
from src.utils.gemini_usage import GeminiUsageCallbackHandler


class WorkflowComparisonTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false"))
        self.enterContext(patch("socket.socket.connect", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch("socket.socket.connect_ex", side_effect=AssertionError("network forbidden")))
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.store = self.root / "store"
        self.store.mkdir()
        nodes = {
            key: {"chunk_uid": key, "text": ("orchard" if i == 0 else "activity measurement") + " source " + key,
                  "metadata": {"chunk_uid": key, "rcept_no": receipt, "company": "Entity",
                               "block_type": "paragraph", "year": 2031, "chunk_id": i}}
            for i, (key, receipt) in enumerate((("filing-a:1", "filing-a"),
                                               ("filing-b:1", "filing-b"),
                                               ("filing-c:1", "filing-c")))
        }
        for name, value in (("store_manifest.json", {"test": "source snapshot"}),
                            ("document_structure_graph.json", {"nodes": nodes}),
                            ("table_payloads.json", {})):
            (self.store / name).write_text(json.dumps(value), encoding="utf-8")
        self.dataset = {"split": "development", "cases": [{
            "id": "case-1", "task_type": "explanation", "query": "Explain activity measurement.",
            "report_scope": {"rcept_no": "filing-a"},
            "review_criteria": {"required_facts": ["SECRET_GOLD_ANSWER"]},
        }]}
        # Unique token in three documents gives positive BM25 IDF.
        self.dataset["cases"][0]["query"] = "orchard"

    def plan(self):
        return prepare(self.dataset, self.store)

    @contextmanager
    def guard(self, budget, authorize):
        self.active_budget = budget
        yield budget

    def test_preparation_is_read_only_and_gold_never_reaches_common_input(self):
        before = {p.name: p.read_bytes() for p in self.store.iterdir()}
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")):
            plan = self.plan()
        packet = plan["cases"][0]["packet"]
        self.assertNotIn("SECRET_GOLD_ANSWER", baseline_prompt(packet))
        self.assertNotIn("review_criteria", packet)
        self.assertEqual(plan["cases"][0]["packet_sha256"], fingerprint(packet))
        self.assertEqual([row["source_id"] for row in packet["documents"]], ["filing-a:1"])
        self.assertTrue(all(row["metadata"]["rcept_no"] == "filing-a" for row in packet["documents"]))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.store.iterdir()})
        verify_plan(plan)

    def test_context_budget_preserves_whole_sources_and_records_exclusion(self):
        packet = self.plan()["cases"][0]["packet"]
        limit = len(encoded(source_text_packet(packet)))
        exact = prepare(self.dataset, self.store, context_bytes=limit)["cases"][0]
        short = prepare(self.dataset, self.store, context_bytes=limit-1)["cases"][0]
        self.assertEqual(len(exact["packet"]["documents"]), 1)
        self.assertEqual(short["packet"]["documents"], [])
        self.assertEqual(short["excluded"][0]["source_id"], "filing-a:1")

    def test_final_split_duplicate_ids_and_invalid_bounds_are_rejected(self):
        for changed in ({**self.dataset, "split": "final"},
                        {**self.dataset, "cases": self.dataset["cases"] * 2}):
            with self.assertRaises(ValueError):
                prepare(changed, self.store)
        with self.assertRaises(ValueError):
            prepare(self.dataset, self.store, context_bytes=0)

    def test_changed_source_and_packet_are_rejected_before_run(self):
        plan = self.plan()
        plan["cases"][0]["packet"]["query"] = "changed"
        with self.assertRaisesRegex(ValueError, "packet changed"):
            verify_plan(plan)
        plan = self.plan()
        (self.store / "table_payloads.json").write_text('{"changed": {}}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "snapshot changed"):
            verify_plan(plan)

    def test_actual_compiler_adapter_keeps_failed_planning_incomplete(self):
        packet = self.plan()["cases"][0]["packet"]
        original = deepcopy(packet)
        llm = Mock()
        llm.with_structured_output.return_value.invoke.side_effect = ValueError("invalid plan")
        result = compiled_answer(packet, llm, GeminiUsageCallbackHandler())
        self.assertEqual(result["answer"]["structured_result"]["status"], "incomplete")
        self.assertEqual(llm.with_structured_output.call_count, 1)
        self.assertEqual(packet, original)

    def test_actual_compiler_adapter_executes_authored_lookup_without_extra_calls(self):
        from src.agent.financial_graph import FinancialAgent
        from src.agent.financial_graph_models import RequirementPlannerOutput, SemanticCalculationProgram
        from tests.semantic_program_test_support import _StructuredQueueLLM, _candidate, _obligation
        from tests.source_interpretation_fixture_support import authored_source_program

        packet = self.plan()["cases"][0]["packet"]
        packet["query"] = "Return the quantity."
        catalog = [{**_candidate("quantity-1", 12), "rcept_no": "filing-a"}]
        obligation = _obligation("ob_001", "direct_value", "quantity")
        planner = RequirementPlannerOutput.model_validate({"topic": "quantity", "obligations": [obligation]})
        program = authored_source_program({"direct_bindings": [
            {"obligation_id": "ob_001", "candidate_id": "quantity-1"}]},
            [obligation], catalog, packet["query"])
        llm = _StructuredQueueLLM(planner, SemanticCalculationProgram.model_validate(program))
        with patch.object(FinancialAgent, "_semantic_candidate_catalog_for_state", return_value=catalog):
            result = compiled_answer(packet, llm, GeminiUsageCallbackHandler())
        self.assertEqual(len(llm.models), 2)
        self.assertEqual(llm.models[-1], "CompilerResponseV2")
        self.assertEqual(result["answer"]["structured_result"]["status"], "ok")
        self.assertIn("12", result["answer"]["answer"])
        self.assertEqual(result["review_trace"]["retrieval_debug_trace"]["packet_sha256"], fingerprint(packet))

    def test_baseline_real_sdk_admission_and_usage_with_mocked_http(self):
        from src.agent.financial_graph import FinancialAgent
        from src.ops.openai_provider_admission import guarded_runtime_openai_responses
        from tests.test_openai_compiler_transport import response_body

        plan = self.plan()
        policy = budget_policy(plan, cap_usd=10, input_rate=2.5, output_rate=12)
        self.assertAlmostEqual(batch_cost_ceiling(policy), 1.49152)
        usage = GeminiUsageCallbackHandler()
        agent = object.__new__(FinancialAgent)
        agent.llm_usage_callback = usage
        llm = agent._create_chat_model({**plan["model_settings"], "api_key": "offline-placeholder"}, phase="comparison")
        sent = []
        def send(_client, request, **kwargs):
            sent.append(json.loads(request.content))
            body = response_body({"answer": "Authored baseline answer", "cited_source_ids": ["filing-a:1"], "abstained": False})
            body["model"] = plan["model_settings"]["model"]
            return httpx.Response(200, json=body, request=request)
        budget = ProviderBudget(policy)
        authorize = Mock(return_value=True)
        with patch.object(httpx.Client, "send", send), guarded_runtime_openai_responses(budget, authorize):
            result = run_arm("simple_rag", plan["cases"][0]["packet"], llm, usage)
        authorize.assert_called_once()
        self.assertEqual(len(sent), 1)
        self.assertTrue(sent[0]["text"]["format"]["strict"])
        self.assertEqual(sent[0]["model"], plan["model_settings"]["model"])
        self.assertNotIn("SECRET_GOLD_ANSWER", json.dumps(sent))
        self.assertEqual(result["output"]["unknown_citations"], [])
        self.assertEqual(budget.snapshot()["requests"][0]["input_tokens"], 100)
        self.assertAlmostEqual(budget.charged, (100*2.5 + 30*12) / 1_000_000)

    def test_underfunding_and_invalid_rates_make_no_calls_or_output(self):
        plan = self.plan()
        policy = budget_policy(plan, cap_usd=0.01, input_rate=2.5, output_rate=12)
        factory = Mock(side_effect=AssertionError("must not create provider"))
        output = self.root / "unfunded"
        with self.assertRaisesRegex(ValueError, "not funded"):
            run_comparison(plan, output, policy, llm_factory=factory, guard_factory=self.guard)
        factory.assert_not_called()
        self.assertFalse(output.exists())
        for value in (0, -1, float("nan"), float("inf")):
            with self.assertRaises(ValueError):
                budget_policy(plan, cap_usd=value, input_rate=2.5, output_rate=12)
        plan["model_settings"]["provider"] = "google"
        with self.assertRaisesRegex(ValueError, "OpenAI Responses"):
            budget_policy(plan, cap_usd=10, input_rate=2.5, output_rate=12)

    def test_paired_inputs_and_model_are_identical_and_output_cannot_resume(self):
        plan = self.plan()
        policy = budget_policy(plan, cap_usd=10, input_rate=2.5, output_rate=12)
        calls = []
        def factory(settings, usage):
            calls.append(deepcopy(settings))
            return object()
        seen = []
        def arm(name, packet, llm, usage):
            seen.append(deepcopy(packet))
            packet["query"] = "mutation must not reach the other arm"
            return {"status": "completed", "output": {"answer": "fixture response"}, "answer_correct": None}
        output = self.root / "paired"
        with patch("src.ops.compare_rag_workflows.run_arm", side_effect=arm):
            receipt = run_comparison(plan, output, policy, llm_factory=factory, guard_factory=self.guard)
        self.assertEqual(calls[0], calls[1])
        self.assertEqual(seen[0], seen[1])
        self.assertEqual(plan["cases"][0]["packet"], seen[0])
        self.assertEqual(receipt["quality_review_status"], "NOT_REVIEWED")
        self.assertEqual(receipt["summary"]["completed_pairs"], 1)
        self.assertTrue(all(row["answer_correct"] is None for row in receipt["results"]))
        with self.assertRaises(FileExistsError):
            run_comparison(plan, output, policy, llm_factory=factory, guard_factory=self.guard)
        self.assertEqual(len(calls), 2)

    def test_terminal_stop_keeps_prior_answer_and_remaining_arm_not_run(self):
        plan = self.plan()
        second = deepcopy(plan["cases"][0]); second["case_id"] = "case-2"
        plan["cases"].append(second)
        policy = budget_policy(plan, cap_usd=10, input_rate=2.5, output_rate=12)
        with patch("src.ops.compare_rag_workflows.run_arm", side_effect=[
            {"status": "completed", "output": {"answer": "preserved"}},
            BudgetStop("synthetic_budget_stop", "test stop"),
        ]) as call:
            receipt = run_comparison(plan, self.root / "stopped", policy,
                                     llm_factory=lambda settings, usage: object(), guard_factory=self.guard)
        self.assertEqual(call.call_count, 2)
        self.assertEqual([row["status"] for row in receipt["results"]],
                         ["completed", "interrupted", "NOT_RUN", "NOT_RUN"])
        self.assertEqual(receipt["results"][0]["output"]["answer"], "preserved")
        self.assertTrue((self.root / "stopped" / "results.json").exists())

    def test_caught_provider_failure_still_stops_the_remaining_batch(self):
        plan = self.plan()
        policy = budget_policy(plan, cap_usd=10, input_rate=2.5, output_rate=12)
        def swallowed_failure(*args):
            self.active_budget._close("synthetic_provider_failure", "authored failure")
            return {"status": "completed", "output": {"status": "incomplete"}}
        with patch("src.ops.compare_rag_workflows.run_arm", side_effect=swallowed_failure) as call:
            receipt = run_comparison(plan, self.root / "caught", policy,
                                     llm_factory=lambda settings, usage: object(), guard_factory=self.guard)
        self.assertEqual(call.call_count, 1)
        self.assertEqual([row["status"] for row in receipt["results"]], ["interrupted", "NOT_RUN"])
        self.assertEqual(receipt["results"][0]["stop_reason"], "synthetic_provider_failure")
        self.assertEqual(receipt["summary"]["completed_pairs"], 0)


if __name__ == "__main__":
    unittest.main()
