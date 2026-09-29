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
    add_reused_results, authorize_arm_request, baseline_prompt, batch_cost_ceiling, budget_policy,
    compiled_answer, encoded, fingerprint, prepare, run_arm, run_comparison,
    source_text_packet, verify_plan, write_new,
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

    def prior_result(self, plan):
        prior = self.root / "prior"
        prior.mkdir()
        write_new(prior / "plan.json", plan)
        result = prior / "00_simple_rag.json"
        write_new(result, {"case_id": plan["cases"][0]["case_id"], "arm": "simple_rag",
                  "status": "completed", "packet_sha256": plan["cases"][0]["packet_sha256"],
                  "output": {"answer": "Preserved authored answer"}, "elapsed_seconds": 1,
                  "provider_records": [{"estimated_usd": 0.01, "input_tokens": 10, "output_tokens": 5}]})
        return result

    def test_successor_reuses_answer_without_a_call_or_double_charge(self):
        plan = self.plan()
        previous = self.prior_result(plan)
        before = previous.read_bytes()
        successor = add_reused_results(plan, [previous])
        policy = budget_policy(successor, cap_usd=2, input_rate=2.5, output_rate=12)
        self.assertEqual(policy["max_openai_response_calls"], 4)
        self.assertAlmostEqual(batch_cost_ceiling(policy), 1.193216)
        def new_answer(*args):
            self.active_budget.dispatch(kind="openai_response", model=plan["model_settings"]["model"],
                request={"authored": "new response"}, input_bound=10, output_bound=10,
                invoke=lambda: object(), usage=lambda response: (5, 2))
            return {"status": "completed", "output": {"answer": "New authored answer"}}
        factory = Mock(return_value=object())
        with patch("src.ops.compare_rag_workflows.run_arm", side_effect=new_answer) as call:
            result = run_comparison(successor, self.root / "successor", policy,
                                    llm_factory=factory, guard_factory=self.guard)
        factory.assert_called_once()
        self.assertEqual(call.call_args.args[0], "planned_compiled")
        self.assertEqual(result["summary"]["completed_pairs"], 1)
        self.assertEqual(result["summary"]["arms"]["simple_rag"]["new_provider_calls"], 0)
        self.assertEqual(result["summary"]["arms"]["simple_rag"]["reused_provider_calls"], 1)
        self.assertAlmostEqual(result["budget"]["estimated_cost_usd_without_cache_discount"], (5*2.5+2*12)/1e6)
        self.assertEqual(result["results"][0]["output"]["answer"], "Preserved authored answer")
        self.assertEqual(previous.read_bytes(), before)
        self.assertNotIn("reused_results", plan)

    def test_reuse_rejects_changed_model_packet_duplicate_and_unfinished_result(self):
        plan = self.plan()
        previous = self.prior_result(plan)
        for key in ("model_settings", "comparison"):
            changed = deepcopy(plan)
            changed[key] = {**plan[key], "reasoning_effort": "medium"} if key == "model_settings" else "changed"
            with self.assertRaisesRegex(ValueError, "different"):
                add_reused_results(changed, [previous])
        changed = deepcopy(plan)
        changed["cases"][0]["packet"]["query"] = "Different request"
        changed["cases"][0]["packet_sha256"] = fingerprint(changed["cases"][0]["packet"])
        with self.assertRaisesRegex(ValueError, "identical inputs"):
            add_reused_results(changed, [previous])
        with self.assertRaisesRegex(ValueError, "unique completed"):
            add_reused_results(plan, [previous, previous])
        row = json.loads(previous.read_text())
        row["status"] = "interrupted"
        previous.write_text(json.dumps(row))
        with self.assertRaisesRegex(ValueError, "unique completed"):
            add_reused_results(plan, [previous])

    def test_reused_artifact_change_is_rejected_before_client_or_output(self):
        plan = self.plan()
        previous = self.prior_result(plan)
        successor = add_reused_results(plan, [previous])
        policy = budget_policy(successor, cap_usd=2, input_rate=2.5, output_rate=12)
        previous.write_text(previous.read_text() + " ")
        factory = Mock()
        output = self.root / "not_created"
        with self.assertRaisesRegex(ValueError, "Reused evidence changed"):
            run_comparison(successor, output, policy, llm_factory=factory, guard_factory=self.guard)
        factory.assert_not_called()
        self.assertFalse(output.exists())

    def test_exact_first_request_bounds_leave_only_compiler_slots_variable(self):
        plan = self.plan()
        planner_body = {"input": "fixed planner", "text": {"format": {"name": "RequirementPlannerOutput"}}}
        baseline_body = {"input": "fixed baseline", "text": {"format": {"name": "SimpleAnswer"}}}
        bodies = {"simple_rag": baseline_body, "planned_compiled": planner_body}
        plan["compiler_input_token_bound"] = 100000
        plan["first_request_bounds"] = [{"case_id":"case-1", "arm":arm,
            "request_sha256":fingerprint(body), "input_token_bound":len(encoded(body))+256}
            for arm,body in bodies.items()]
        policy = budget_policy(plan, cap_usd=2, input_rate=2.5, output_rate=12)
        fixed = sum(row["input_token_bound"] for row in plan["first_request_bounds"])
        self.assertAlmostEqual(batch_cost_ceiling(policy), ((fixed+3*100000)*2.5+5*8192*12)/1e6)
        active = {"case_id":"case-1", "arm":"planned_compiled", "calls":0, "limit":4}
        with self.assertRaises(BudgetStop):
            authorize_arm_request({**planner_body, "input":"changed"}, active, policy)
        self.assertEqual(active["calls"], 0)
        self.assertTrue(authorize_arm_request(planner_body, active, policy))
        with self.assertRaises(BudgetStop):
            authorize_arm_request(planner_body, active, policy)
        for _ in range(3):
            self.assertTrue(authorize_arm_request({"text":{"format":{"name":"CompilerResponseV2"}}}, active, policy))
        with self.assertRaises(BudgetStop):
            authorize_arm_request({"text":{"format":{"name":"CompilerResponseV2"}}}, active, policy)
        for changed in ([plan["first_request_bounds"][0]], plan["first_request_bounds"]*2):
            with self.assertRaises(ValueError):
                budget_policy({**plan,"first_request_bounds":changed}, cap_usd=2, input_rate=2.5, output_rate=12)

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
        # Real graph review records contain Documents, not just dictionaries.
        saved = self.root / "compiled_result.json"
        write_new(saved, result)
        restored = json.loads(saved.read_text(encoding="utf-8"))
        doc = restored["review_trace"]["retrieved_docs"][0][0]
        self.assertEqual(doc["page_content"], packet["documents"][0]["page_content"])
        self.assertEqual(doc["metadata"], packet["documents"][0]["metadata"])

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

    def test_unknown_output_type_preserves_budget_receipt_and_stops_calls(self):
        plan = self.plan()
        policy = budget_policy(plan, cap_usd=10, input_rate=2.5, output_rate=12)
        output = self.root / "bad_output"
        def unencodable_after_charge(*args):
            self.active_budget.dispatch(kind="openai_response", model=plan["model_settings"]["model"],
                request={"authored": "test"}, input_bound=10, output_bound=10,
                invoke=lambda: object(), usage=lambda response: (5, 2))
            return {"status": "completed", "output": object()}
        with patch("src.ops.compare_rag_workflows.run_arm", side_effect=unencodable_after_charge) as call:
            receipt = run_comparison(plan, output, policy,
                                     llm_factory=lambda settings, usage: object(), guard_factory=self.guard)
        self.assertEqual(call.call_count, 1)
        self.assertEqual([row["status"] for row in receipt["results"]], ["interrupted", "NOT_RUN"])
        self.assertEqual(receipt["results"][0]["stop_reason"], "result_serialization_failed")
        saved_budget = json.loads((output / "budget.json").read_text())
        self.assertEqual(len(saved_budget["requests"]), 1)
        self.assertAlmostEqual(saved_budget["estimated_cost_usd_without_cache_discount"], (5*2.5 + 2*12)/1e6)
        self.assertTrue((output / "00_simple_rag_budget.json").exists())
        self.assertEqual(json.loads((output / "results.json").read_text()), receipt)
        unsupported = self.root / "unsupported.json"
        with self.assertRaises(TypeError):
            write_new(unsupported, object())
        self.assertFalse(unsupported.exists())


if __name__ == "__main__":
    unittest.main()
