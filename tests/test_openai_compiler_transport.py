"""Actual OpenAI/LangChain serialization with authored responses and blocked sockets."""

from copy import deepcopy
import hashlib
import json
import os
import socket
import unittest
from unittest.mock import patch

import httpx
from pydantic import BaseModel, ConfigDict, Field, model_validator

from src.agent.financial_graph import FinancialAgent
from src.ops.openai_provider_admission import guarded_openai_responses, openai_request_parameters
from src.ops.provider_admission import BudgetStop, ProviderBudget, json_bytes
from src.utils.gemini_usage import GeminiUsageCallbackHandler
from src.utils.gemini_usage_counts import extract_gemini_usage_counts
from src.utils.openai_structured import strict_openai_schema


ROUTE = dict(provider="openai", model="gpt-6-astra", temperature=None, max_output_tokens=5120,
             reasoning_effort="medium", provider_client_retries=0, use_responses_api=True,
             store=False, service_tier="default", timeout_seconds=90, api_key="offline-placeholder")
POLICY = dict(cap_usd=1.0, max_openai_response_calls=1, openai_input_overhead_tokens=1024,
              max_openai_input_tokens=200000, rates={"gpt-6-astra": dict(input=12.5, output=50)},
              request_settings=dict(model="gpt-6-astra", max_output_tokens=5120,
                                    reasoning={"effort": "medium"}, store=False, service_tier="default"))


def response_body(wire, *, usage=True, status="completed"):
    return dict(id="resp_offline", object="response", created_at=0, status=status, model=ROUTE["model"],
        output=[dict(type="message", id="msg_offline", role="assistant", status="completed",
                     content=[dict(type="output_text", text=json.dumps(wire), annotations=[])])],
        usage=dict(input_tokens=100, output_tokens=30, total_tokens=130,
                   input_tokens_details=dict(cached_tokens=20), output_tokens_details=dict(reasoning_tokens=10)) if usage else None,
        error=None, incomplete_details=None, parallel_tool_calls=False, tools=[])


class Payload(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: int
    comment: str | None = None
    flags: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def positive(self):
        if self.value < 0:
            raise ValueError("Authored application constraint")
        return self


class OpenAICompilerTransportTests(unittest.TestCase):
    def setUp(self):
        self.enterContext(patch.dict(os.environ, LANGSMITH_TRACING="false", LANGCHAIN_TRACING_V2="false"))
        self.enterContext(patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")))
        self.enterContext(patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network forbidden")))
        self.agent = FinancialAgent.__new__(FinancialAgent)
        self.agent.llm_usage_callback = GeminiUsageCallbackHandler()
        self.agent.llm_usage_callback.set_current_phase("program_compilation")
        self.sent = []
        self.wire = dict(value=2, comment=None, flags=[])
        self.http_status = 200
        self.response_usage = True
        self.response_status = "completed"
        self.refusal = False

    def send(self, request, **kwargs):
        self.sent.append(json.loads(request.content))
        body = response_body(self.wire, usage=self.response_usage, status=self.response_status) if self.http_status == 200 else {
            "error": {"message": "private-provider-detail", "type": "server_error", "code": "unavailable"}}
        if self.refusal:
            body["output"][0]["content"] = [{"type": "refusal", "refusal": "Offline refusal witness"}]
        return httpx.Response(self.http_status, json=body, request=request)

    def invoke(self, *, route=None, payload=Payload):
        llm = self.agent._create_chat_model(route or ROUTE, phase="program_compilation")
        return llm.with_structured_output(payload, include_raw=True).invoke("Anonymous structured request")

    def rehearse(self):
        with patch.object(httpx.Client, "send", self.send):
            result = self.invoke()
        self.assertIsNone(result["parsing_error"])
        body = self.sent.pop()
        return body, hashlib.sha256(json_bytes(body)).hexdigest()

    def test_strict_wire_requires_fields_preserves_constraints_and_original_schema(self):
        before = deepcopy(Payload.model_json_schema())
        strict = strict_openai_schema(Payload)
        self.assertEqual(strict["required"], ["value", "comment", "flags"])
        self.assertNotIn("default", strict["properties"]["comment"])
        self.assertEqual(before, Payload.model_json_schema())
        for schema in ({"type": "object", "additionalProperties": {"type": "string"}},
                       {"type": "object", "allOf": [{"type": "object"}]}):
            with self.assertRaises(ValueError):
                strict_openai_schema(schema)

    def test_sdk_wire_usage_and_accounting_match_without_reasoning_double_count(self):
        body, digest = self.rehearse()
        self.assertNotIn("temperature", body)
        self.assertEqual(body["reasoning"], {"effort": "medium"})
        self.assertEqual(body["max_output_tokens"], 5120)
        self.assertIs(body["text"]["format"]["strict"], True)
        self.agent.llm_usage_callback.reset_current_thread()
        with patch.object(httpx.Client, "send", self.send), guarded_openai_responses(POLICY, [digest]) as budget:
            reply = self.invoke()
        self.assertEqual(reply["parsed"].value, 2)
        self.assertEqual(self.sent, [body])
        self.assertEqual(budget.records[0]["output_tokens"], 30)
        self.assertAlmostEqual(budget.charged, (100 * 12.5 + 30 * 50) / 1e6)
        counts = self.agent.llm_usage_callback.snapshot_current_thread()
        self.assertEqual((counts["prompt_tokens"], counts["output_tokens"], counts["thoughts_tokens"], counts["cached_tokens"]), (100, 20, 10, 20))
        self.assertNotIn("offline-placeholder", json.dumps(budget.snapshot()))

    def test_runtime_validator_missing_required_and_extra_keys_remain_fail_closed(self):
        for wire in (dict(value=-2, comment=None, flags=[]), dict(value=2),
                     dict(value=2, comment=None, flags=[], invented=True)):
            self.wire = wire
            with self.subTest(wire=wire), patch.object(httpx.Client, "send", self.send):
                result = self.invoke()
            self.assertIsNone(result["parsed"])
            self.assertIsNotNone(result["parsing_error"])

    def test_changed_body_endpoint_retry_and_cap_stop_before_http(self):
        _, digest = self.rehearse()
        for change in (dict(base_url="https://example.invalid/v1"), dict(provider_client_retries=1),
                       dict(max_output_tokens=6000), dict(store=True)):
            with self.subTest(change=change), patch.object(httpx.Client, "send", self.send), \
                 guarded_openai_responses(POLICY, [digest]):
                with self.assertRaises(BudgetStop):
                    self.invoke(route={**ROUTE, **change})
            self.assertEqual(self.sent, [])
        with patch.object(httpx.Client, "send", self.send), guarded_openai_responses({**POLICY, "cap_usd": 0.00001}, [digest]):
            with self.assertRaises(BudgetStop):
                self.invoke()
        self.assertEqual(self.sent, [])

    def test_failed_or_missing_usage_retains_reservation_and_never_retries(self):
        body, digest = self.rehearse()
        expected = ProviderBudget(POLICY).preflight(**openai_request_parameters(POLICY, body))["reserved_usd"]
        for status, usage in ((503, True), (200, False)):
            self.http_status, self.response_usage, self.sent = status, usage, []
            with self.subTest(status=status), patch.object(httpx.Client, "send", self.send), guarded_openai_responses(POLICY, [digest]) as budget:
                with self.assertRaises(BudgetStop):
                    self.invoke()
                with self.assertRaises(BudgetStop):
                    self.invoke()
            self.assertEqual(len(self.sent), 1)
            self.assertEqual(budget.pending, 0)
            self.assertEqual(budget.charged, expected)
            self.assertNotIn("private-provider-detail", json.dumps(budget.snapshot()))

    def test_native_chat_and_responses_usage_are_disjoint(self):
        for raw in (dict(input_tokens=100, output_tokens=30, output_tokens_details={"reasoning_tokens": 10},
                         input_tokens_details={"cached_tokens": 20}),
                    dict(prompt_tokens=100, completion_tokens=30, completion_tokens_details={"reasoning_tokens": 10},
                         prompt_tokens_details={"cached_tokens": 20})):
            counts = extract_gemini_usage_counts(raw)
            self.assertEqual((counts["prompt_tokens"], counts["output_tokens"], counts["thoughts_tokens"], counts["cached_tokens"]), (100, 20, 10, 20))

    def test_incomplete_and_refused_responses_do_not_become_valid_programs(self):
        for status, refusal in (("incomplete", False), ("completed", True)):
            self.response_status, self.refusal = status, refusal
            with self.subTest(status=status, refusal=refusal), patch.object(httpx.Client, "send", self.send):
                result = self.invoke()
            self.assertIsNone(result["parsed"])
            self.assertIsNotNone(result["parsing_error"])

    def test_same_settings_with_an_unapproved_body_cannot_dispatch(self):
        self.rehearse()
        with patch.object(httpx.Client, "send", self.send), guarded_openai_responses(POLICY, ["0" * 64]):
            with self.assertRaisesRegex(BudgetStop, "unapproved_request_body"):
                self.invoke()
        self.assertEqual(self.sent, [])

    def test_current_compiler_sources_formulas_and_ledgers_survive_real_sdk_transport(self):
        from src.ops.compiler_fixture_transport import project_offline_program_to_wire
        from src.ops.replay_reviewed_compiler_selection import _CompilerOnlyAgent, _RecordingLLM, _case_state
        from tests.mixed_numeric_source_test_support import authored_program, capture_initial, execute, load_criteria, load_sources, materialize
        from tests.semantic_program_test_support import execute_compiled_fixture
        from tests.test_named_request_inputs import named_witness

        criteria = load_criteria()
        cases = [materialize(source) for source in load_sources()]
        witnesses = [(case, authored_program(case, criteria[case["case_id"]])) for case in cases]
        witnesses += [named_witness(0.5), named_witness(-2.5)]
        for case, program in witnesses:
            with self.subTest(case=case["case_id"], question=case["question"]):
                model, _ = capture_initial(case)
                # Explicit authored witness, never a repaired sampled response.
                self.wire = project_offline_program_to_wire(program, model)
                llm = self.agent._create_chat_model(ROUTE, phase="program_compilation")
                with patch.object(httpx.Client, "send", self.send):
                    compiled = _CompilerOnlyAgent(_RecordingLLM(llm))._compile_semantic_calculation_program(_case_state(case, case["candidate_catalog"]))
                self.assertEqual(compiled["semantic_program_retry_count"], 0)
                self.assertEqual(execute(case, compiled)["status"], "ok")
                final = execute_compiled_fixture(self.agent,
                    {**compiled, "query": case["question"], "answer_obligations": case["obligations"]}, case["candidate_catalog"])
                self.assertEqual(final["task_artifact_trace"]["integrity_status"], "ok")
        self.assertEqual(len(self.sent), 6)

    def test_wire_constraints_are_kept_for_source_ids_and_operation_arity(self):
        from tests.mixed_numeric_source_test_support import capture_initial
        from tests.test_named_request_inputs import named_witness

        case, _ = named_witness()
        model, _ = capture_initial(case)
        original = model.model_json_schema()
        wire = strict_openai_schema(model)
        def constraints(node):
            if isinstance(node, dict):
                own = {key: value for key, value in node.items() if key in {"enum", "const", "$ref", "minimum", "minItems", "maxItems", "minLength"}}
                return [own] + [item for value in node.values() for item in constraints(value)]
            if isinstance(node, list):
                return [item for value in node for item in constraints(value)]
            return []
        self.assertEqual([row for row in constraints(original) if row], [row for row in constraints(wire) if row])


if __name__ == "__main__":
    unittest.main()
