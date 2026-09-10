"""Exercise installed Gemini/LangChain adapters without provider network or credentials."""

from __future__ import annotations

import json
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from google.genai import _api_client, errors, types
from langchain_core.exceptions import OutputParserException
from tenacity import Retrying, wait_none

from src.agent.financial_graph import FinancialAgent
from src.agent.financial_graph_models import SemanticCalculationProgram
from src.ops.replay_reviewed_compiler_selection import (
    _RecordingLLM,
    _create_google_compiler,
    _load_corpus,
    _reviewed_response_queue,
    _sha256_file,
    _write_new_json,
    build_admission_manifest,
    evaluate_reviewed_compiler_selection,
    run_approved_manifest,
)
from src.utils.gemini_usage import GeminiUsageCallbackHandler


FIXTURE_PATH = Path(__file__).parent / "fixtures/reviewed_runtime_replay_corpus_v3.json"


def _response(text: str, *, finish_reason=types.FinishReason.STOP, thoughts=False):
    parts = [types.Part(text=text)]
    if thoughts:
        parts.insert(0, types.Part(
            text="private-thinking-not-for-artifacts", thought=True,
            thought_signature=b"private-signature-not-for-artifacts",
        ))
    return types.GenerateContentResponse(
        model_version="gemini-2.5-flash",
        candidates=[types.Candidate(
            index=0, finish_reason=finish_reason,
            content=types.Content(role="model", parts=parts),
        )],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=48,
            thoughts_token_count=2000, cached_content_token_count=40,
            total_token_count=2148,
        ),
    )


class CompilerResponseCaptureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.external_connections = []
        original_connect = socket.socket.connect

        def local_only_connect(sock, address):
            # Windows asyncio uses a loopback socketpair for its own wake-up pipe.
            if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                return original_connect(sock, address)
            self.external_connections.append(address)
            raise AssertionError("provider network prohibited")

        self.enterContext(patch("socket.socket.connect", new=local_only_connect))
        self.enterContext(patch.dict(os.environ, {
            "GOOGLE_API_KEY": "synthetic-not-a-credential",
            "GOOGLE_GENAI_USE_VERTEXAI": "false",
            "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false",
        }))
        self.enterContext(patch(
            "src.ops.replay_reviewed_compiler_selection.dotenv_values", return_value={},
        ))
        self.client_factory = self.enterContext(patch(
            "langchain_google_genai.chat_models.Client",
        ))
        self.generate = self.client_factory.return_value.models.generate_content
        self.callback = GeminiUsageCallbackHandler()
        self.llm = _create_google_compiler({
            "model": "gemini-2.5-flash", "temperature": 0,
            "max_output_tokens": 4096, "thinking_budget": 1024,
            "provider_client_retries": 0,
        }, self.callback)

    def tearDown(self) -> None:
        self.assertEqual(self.external_connections, [])

    def test_success_captures_final_text_finish_and_real_sdk_usage(self) -> None:
        text = '{"status":"ready","rationale":"synthetic"}'
        self.generate.return_value = _response(text, thoughts=True)
        recorder = _RecordingLLM(self.llm)

        parsed = recorder.with_structured_output(SemanticCalculationProgram).invoke("test")

        self.assertEqual(parsed.status, "ready")
        self.assertEqual(self.generate.call_count, 1)
        response = recorder.records[0]["response"]
        self.assertTrue(response["raw_response_available"])
        self.assertEqual(response["final_text"], text)
        self.assertEqual(response["finish_reason"], "STOP")
        self.assertIsNone(response["parsing_error"])
        expected_usage = {
            "prompt_tokens": 100, "output_tokens": 48, "thoughts_tokens": 2000,
            "cached_tokens": 40, "tool_use_prompt_tokens": 0, "total_tokens": 2148,
        }
        self.assertEqual(response["usage"], expected_usage)
        self.assertEqual(self.callback.snapshot_global(), {**expected_usage, "api_calls": 1})
        serialized = json.dumps(recorder.records)
        for excluded in ("private-thinking", "private-signature", "synthetic-not-a-credential"):
            self.assertNotIn(excluded, serialized)

    def test_request_forwards_both_manifest_budgets_without_enabling_thought_text(self) -> None:
        self.generate.return_value = _response('{"status":"ready"}')
        agent = FinancialAgent.__new__(FinancialAgent)
        agent.llm_usage_callback = self.callback
        production_llm = agent._create_chat_model({
            "model": "gemini-2.5-pro", "max_output_tokens": 4096,
            "thinking_budget": 1024, "provider_client_retries": 0,
            "include_thoughts": False,
        }, phase="program_compilation")
        for name, llm in (("compiler_only", self.llm), ("production", production_llm)):
            with self.subTest(factory=name):
                _RecordingLLM(llm).with_structured_output(SemanticCalculationProgram).invoke("test")
                config = self.generate.call_args.kwargs["config"]
                self.assertEqual(config.max_output_tokens, 4096)
                self.assertEqual(config.thinking_config.thinking_budget, 1024)
                self.assertFalse(config.thinking_config.include_thoughts)
                self.assertEqual(config.http_options.retry_options.attempts, 0)
                retry = _api_client.retry_args(config.http_options.retry_options)
                self.assertEqual(retry["stop"].max_attempt_number, 1)

    def test_zero_sdk_retries_stop_after_one_429_attempt(self) -> None:
        self.generate.return_value = _response('{"status":"ready"}')
        _RecordingLLM(self.llm).with_structured_output(SemanticCalculationProgram).invoke("test")
        config = self.generate.call_args.kwargs["config"]
        retry_options = _api_client.retry_args(config.http_options.retry_options)
        retry_options["wait"] = wait_none()
        attempts = []

        def rate_limited_request():
            attempts.append(1)
            raise errors.ClientError(429, {"error": {"message": "synthetic rate limit"}})

        with self.assertRaises(errors.ClientError):
            Retrying(**retry_options)(rate_limited_request)
        self.assertEqual(len(attempts), 1)

    def test_comparison_models_use_identical_sdk_schema_and_generation_controls(self) -> None:
        self.generate.return_value = _response('{"status":"ready"}')
        requests = []
        for model in ("gemini-2.5-flash", "gemini-2.5-pro"):
            llm = _create_google_compiler({
                "model": model, "temperature": 0, "max_output_tokens": 4096,
                "thinking_budget": 1024, "provider_client_retries": 0,
            }, GeminiUsageCallbackHandler())
            _RecordingLLM(llm).with_structured_output(SemanticCalculationProgram).invoke("same prompt")
            request = self.generate.call_args.kwargs
            self.assertEqual(request["model"], model)
            requests.append({k:v for k,v in request.items() if k != "model"})
        self.assertEqual(requests[0], requests[1])

    def test_truncated_and_missing_field_failures_remain_distinguishable(self) -> None:
        partial = '{"status":"ready","expressions":[{"obligation_id":"change","variable_bindings":[{"variable_name":"current","source_id":"'
        closed = '{"status":"ready","expressions":[{"obligation_id":"change","variable_bindings":[{"variable_name":"current","source_id":""}]}]}'
        self.generate.side_effect = [
            _response(partial, finish_reason=types.FinishReason.MAX_TOKENS, thoughts=True),
            _response(closed),
        ]
        recorder = _RecordingLLM(self.llm)
        invoker = recorder.with_structured_output(SemanticCalculationProgram)
        for _ in range(2):
            with self.assertRaises(OutputParserException):
                invoker.invoke("same prompt")

        first, second = [record["response"] for record in recorder.records]
        self.assertEqual(first["final_text"], partial)
        self.assertEqual(second["final_text"], closed)
        self.assertEqual(first["finish_reason"], "MAX_TOKENS")
        self.assertEqual(second["finish_reason"], "STOP")
        self.assertEqual(first["parsing_error"]["type"], "OutputParserException")
        self.assertEqual(first["usage"]["thoughts_tokens"], 2000)
        self.assertEqual(self.generate.call_count, 2)  # the recorder itself does not retry
        self.assertNotIn("private-thinking", json.dumps(recorder.records))
        self.assertNotIn("private-signature", json.dumps(recorder.records))

    def test_partial_json_accepted_by_sdk_still_records_max_tokens(self) -> None:
        text = '{"status":"ready","rationale":"unfinished'
        self.generate.return_value = _response(text, finish_reason=types.FinishReason.MAX_TOKENS)
        recorder = _RecordingLLM(self.llm)

        parsed = recorder.with_structured_output(SemanticCalculationProgram).invoke("test")

        self.assertEqual(parsed.status, "ready")
        response = recorder.records[0]["response"]
        self.assertEqual(response["final_text"], text)
        self.assertEqual(response["finish_reason"], "MAX_TOKENS")
        self.assertIsNone(response["parsing_error"])

    def test_failed_island_response_and_retry_both_survive_in_result(self) -> None:
        reviewed = _reviewed_response_queue(_load_corpus(FIXTURE_PATH))
        self.generate.side_effect = [
            _response(reviewed[0].model_dump_json()),
            _response('{"status":"ready","expressions":[{"obligation_id":"',
                      finish_reason=types.FinishReason.MAX_TOKENS),
            *[_response(program.model_dump_json()) for program in reviewed[1:]],
        ]

        result = evaluate_reviewed_compiler_selection(
            FIXTURE_PATH, self.llm, run_mode="provider", usage_callback=self.callback,
        )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["summary"]["compiler_invocation_count"], 7)
        self.assertEqual(result["summary"]["compiler_retry_count"], 1)
        self.assertEqual(result["cases"][0]["compiler_call_count"], 1)
        self.assertEqual(result["cases"][1]["compiler_call_count"], 2)
        first_response = result["cases"][0]["prompt_records"][0]["response"]
        self.assertEqual(first_response["final_text"], reviewed[0].model_dump_json())
        failed_response = result["cases"][1]["prompt_records"][0]["response"]
        self.assertEqual(failed_response["finish_reason"], "MAX_TOKENS")
        self.assertIsNotNone(failed_response["parsing_error"])
        self.assertEqual(self.callback.snapshot_global()["api_calls"], 7)

    def test_manifest_runner_counts_sdk_worker_usage_and_preserves_prompt_hash(self) -> None:
        reviewed = _reviewed_response_queue(_load_corpus(FIXTURE_PATH))
        self.generate.side_effect = [_response(program.model_dump_json()) for program in reviewed]
        runtime_build = {"git_commit": "test", "file_count": 1, "sha256": "test"}
        with TemporaryDirectory(dir=Path.cwd()) as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest = build_admission_manifest(
                corpus_path=FIXTURE_PATH, manifest_path=manifest_path,
                result_path=Path(temp_dir) / "result.json", cost_cap_usd=0.20,
                runtime_build=runtime_build,
            )
            _write_new_json(manifest_path, manifest)
            with patch("src.ops.replay_reviewed_compiler_selection._tracked_runtime_build",
                       return_value=runtime_build):
                result = run_approved_manifest(
                    manifest_path, approved_manifest_sha256=_sha256_file(manifest_path),
                )

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["provider_network_calls"], 6)  # mocked SDK calls, no provider network
        self.assertEqual(result["usage"]["total_tokens"], 6 * 2148)
        self.assertEqual(result["usage"]["output_tokens"], 6 * 48)
        self.assertEqual(result["usage"]["thoughts_tokens"], 6 * 2000)
        self.assertEqual(result["summary"]["prompt_fingerprint"],
                         manifest["inputs"]["rehearsal"]["prompt_fingerprint"])
        self.assertGreater(result["estimated_cost_usd"], 0)

    def test_transport_failure_records_type_without_sdk_exception_payload(self) -> None:
        self.generate.side_effect = RuntimeError("URL/headers: synthetic-not-a-credential")
        recorder = _RecordingLLM(self.llm)
        with self.assertRaises(RuntimeError):
            recorder.with_structured_output(SemanticCalculationProgram).invoke("test")
        self.assertEqual(self.generate.call_count, 1)
        self.assertEqual(recorder.records[0]["invocation_error_type"], "RuntimeError")
        self.assertFalse(recorder.records[0]["response"]["raw_response_available"])
        self.assertNotIn("synthetic-not-a-credential", json.dumps(recorder.records))


if __name__ == "__main__":
    unittest.main()
