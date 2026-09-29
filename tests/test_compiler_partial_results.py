"""Terminal provider failures preserve evidence, without retrying or exposing errors."""

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
import socket
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from google.genai import errors, types
from google.genai.models import Models

from src.ops.provider_admission import BudgetStop, ProviderBudget, guarded_providers
from src.ops.replay_reviewed_compiler_selection import (
    CORPUS_SCHEMA_VERSION, _canonical_bytes, _reviewed_response_queue, _sha256_file,
    _write_new_json, build_admission_manifest, main,
)
from tests.semantic_program_test_support import _candidate, _obligation
from tests.compiler_wire_test_support import wire_fixture
from src.agent.financial_graph_model_loaders import compiler_response_model


RUNTIME = {"git_commit": "synthetic", "file_count": 1, "sha256": "synthetic"}
POLICY = {"cap_usd": 2.0, "max_google_calls": 8, "max_openai_embedding_calls": 0,
    "google_input_overhead_tokens": 16384,
    "rates": {"gemini-2.5-pro": {"input": 1.25, "output": 10.0},
              "gemini-2.5-flash": {"input": 0.30, "output": 2.50}}}
PRIVATE = "private-url-header-key-never-write"
INVALID_PROGRAM = '{"status":"ready","direct_bindings":"invalid-binding"}'


def _case(name, owners):
    candidate = _candidate("sample-value", 10)
    candidate.update(expected_normalized_value=10, expected_normalized_unit="COUNT")
    return {"case_id": name, "question_id": name, "question": "Read the quantity.",
        "candidate_catalog": [candidate],
        "obligations": [_obligation(owner, "direct_value", "quantity") for owner in owners],
        "program": {"status": "ready", "rationale": "Synthetic source reading.",
            "direct_bindings": [{"obligation_id": owner, "candidate_id": "sample-value"} for owner in owners]},
        "expected": {"selected_candidate_ids": ["sample-value"], "outputs": [
            {"obligation_id": owner, "normalized_value": 10, "normalized_unit": "COUNT"} for owner in owners]}}


def _response(text):
    return types.GenerateContentResponse(candidates=[types.Candidate(finish_reason="STOP",
        content=types.Content(role="model", parts=[
            types.Part(text=PRIVATE, thought=True, thought_signature=b"private-signature"),
            types.Part(text=text)]))],
        usage_metadata=types.GenerateContentResponseUsageMetadata(prompt_token_count=100,
            candidates_token_count=20, thoughts_token_count=10, total_token_count=130))


class CompilerPartialResultTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory(dir=Path.cwd())
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.corpus = {"schema_version": CORPUS_SCHEMA_VERSION, "fixture_origin": "synthetic_failure_capture",
            "cases": [_case("completed", ["a"]), _case("interrupted", ["b", "c"]), _case("unattempted", ["d"])]}
        self.corpus_path = self.root / "corpus.json"
        _write_new_json(self.corpus_path, self.corpus)
        self.external_attempts = []
        for method in ("connect", "connect_ex"):
            original = getattr(socket.socket, method)
            def local_only(sock, address, original=original):
                if isinstance(address, tuple) and address[0] in ("127.0.0.1", "::1"):
                    return original(sock, address)
                self.external_attempts.append(address)
                raise AssertionError("provider network forbidden")
            self.enterContext(patch.object(socket.socket, method, local_only))
        self.enterContext(patch.dict(os.environ, {"GOOGLE_API_KEY": "synthetic-not-a-credential",
            "GOOGLE_GENAI_USE_VERTEXAI": "false", "LANGSMITH_TRACING": "false", "LANGCHAIN_TRACING_V2": "false"}))
        self.enterContext(patch("src.ops.replay_reviewed_compiler_selection.dotenv_values", return_value={}))
        self.enterContext(patch("src.ops.replay_reviewed_compiler_selection._tracked_runtime_build", return_value=RUNTIME))

    def tearDown(self):
        self.assertEqual(self.external_attempts, [])

    def run_cli(self, name, *, fail_at=None, cap=2.0, malformed_second=False, comparison=False):
        directory = self.root / name
        manifest_path, output_path = directory / "manifest.json", directory / "result.json"
        manifest = build_admission_manifest(corpus_path=self.corpus_path, manifest_path=manifest_path,
            result_path=output_path, cost_cap_usd=2.0, runtime_build=RUNTIME,
            model="gemini-2.5-flash" if comparison else "gemini-2.5-pro",
            comparison_model="gemini-2.5-pro" if comparison else None)
        _write_new_json(manifest_path, manifest)
        programs = _reviewed_response_queue(self.corpus)
        texts = [program.model_dump_json() for program in programs]
        if malformed_second:
            texts.insert(1, INVALID_PROGRAM)
        invoked = []
        active_schema = None
        def capture_schema(*args, **kwargs):
            nonlocal active_schema
            active_schema = compiler_response_model(*args, **kwargs)
            return active_schema
        def transport(_client, *, model, contents, config=None):
            invoked.append(model)
            if len(invoked) == fail_at:
                raise errors.ServerError(503, {"error": {"status": "UNAVAILABLE", "message": PRIVATE,
                    "details": {"headers": {"Authorization": PRIVATE}, "url": PRIVATE}}})
            text = texts[len(invoked) - 1]
            if text != INVALID_PROGRAM:
                text = json.dumps(wire_fixture(json.loads(text), active_schema))
            return _response(text)
        with patch('src.agent.financial_graph_calculation.compiler_response_model', side_effect=capture_schema), \
                patch.object(Models, "generate_content", transport), \
                guarded_providers({**POLICY, "cap_usd": cap}, []) as budget:
            with redirect_stdout(StringIO()):
                exit_code = main(["run", "--manifest", str(manifest_path),
                    "--approved-manifest-sha256", _sha256_file(manifest_path), "--output", str(output_path)])
        self.assertTrue(output_path.is_file())
        result = json.loads(output_path.read_text(encoding="utf-8"))
        self.assertNotIn(PRIVATE, json.dumps(result))
        self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()))
        self.assertNotIn("private-signature", json.dumps(result))
        self.assertEqual(self.corpus_path.read_bytes(), _canonical_bytes(self.corpus))
        return result, budget.snapshot(), invoked, exit_code

    def test_two_responses_then_failure_preserve_completed_and_partial_case(self):
        baseline, _, _, _ = self.run_cli("baseline")
        result, budget, invoked, exit_code = self.run_cli("failed", fail_at=3)
        self.assertEqual((result["status"], exit_code), ("failed", 1))
        self.assertEqual(len(invoked), 3)
        self.assertEqual([case["question_id"] for case in result["cases"]], ["completed"])
        for key in baseline["cases"][0]:
            if key != "elapsed_seconds":
                self.assertEqual(_canonical_bytes(result["cases"][0][key]), _canonical_bytes(baseline["cases"][0][key]), key)
        partial = result["interrupted_case"]
        self.assertEqual(partial["question_id"], "interrupted")
        self.assertEqual(partial["status"], "provider_error")
        self.assertNotIn("execution", partial)
        self.assertNotIn("compiled_program", partial)
        self.assertEqual(len(partial["prompt_records"]), 2)
        self.assertEqual(partial["prompt_records"][0], baseline["cases"][1]["prompt_records"][0])
        self.assertFalse(partial["prompt_records"][1]["response"]["raw_response_available"])
        self.assertEqual(result["terminal_error"]["http_status"], 503)
        self.assertEqual(result["terminal_error"]["provider_status"], "UNAVAILABLE")
        self.assertEqual(result["terminal_error"]["code"], "provider_request_failed")
        self.assertEqual(result["summary"]["executed_case_count"], 1)
        self.assertEqual(result["summary"]["interrupted_case_count"], 1)
        self.assertEqual(result["summary"]["unattempted_case_count"], 1)
        self.assertEqual(result["summary"]["compiler_invocation_count"], 3)
        self.assertIsNone(result["summary"]["compiler_retry_count"])
        all_records = result["cases"][0]["prompt_records"] + partial["prompt_records"]
        self.assertEqual(result["summary"]["prompt_bytes"], sum(row["prompt_bytes"] for row in all_records))
        self.assertEqual(result["usage"]["api_calls"], 2)
        self.assertEqual(result["usage_scope"], "completed_responses_only")
        self.assertIsNone(result["provider_network_calls"])
        self.assertEqual(budget["requests"][-1]["http_status"], 503)
        self.assertEqual(budget["requests"][-1]["provider_status"], "UNAVAILABLE")
        self.assertTrue(budget["requests"][-1]["usage_unknown"])
        self.assertEqual(budget["blocked_requests"], [])

    def test_first_request_failure_retains_failed_attempt_without_fabricated_case(self):
        result, _, invoked, _ = self.run_cli("first", fail_at=1)
        self.assertEqual(len(invoked), 1)
        self.assertEqual(result["cases"], [])
        self.assertEqual(result["interrupted_case"]["question_id"], "completed")
        self.assertEqual(result["summary"]["unattempted_case_count"], 2)
        self.assertEqual(result["usage"]["api_calls"], 0)

    def test_budget_denial_preserves_stop_without_transport_or_http_status(self):
        result, budget, invoked, _ = self.run_cli("denied", cap=0)
        self.assertEqual(invoked, [])
        self.assertEqual(budget["requests"], [])
        self.assertEqual(len(budget["blocked_requests"]), 1)
        self.assertEqual(result["terminal_error"]["code"], "budget_reservation_exceeded")
        self.assertIsNone(result["terminal_error"]["http_status"])
        self.assertIsNone(result["terminal_error"]["provider_status"])
        self.assertEqual(result["cases"], [])

    def test_schema_failure_followed_by_provider_failure_keeps_both_attempts(self):
        result, _, invoked, _ = self.run_cli("retry-failed", fail_at=3, malformed_second=True)
        self.assertEqual(len(invoked), 3)
        records = result["interrupted_case"]["prompt_records"]
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["response"]["final_text"], INVALID_PROGRAM)
        self.assertIsNotNone(records[0]["response"]["parsing_error"])
        self.assertEqual(records[1]["invocation_error_type"], "BudgetStop")
        self.assertIsNone(result["summary"]["compiler_retry_count"])

    def test_terminal_failure_stops_model_comparison_and_keeps_prefix(self):
        result, _, invoked, _ = self.run_cli("comparison", fail_at=3, comparison=True)
        self.assertEqual(invoked, ["gemini-2.5-flash"] * 3)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(result["model_results"]), 1)
        self.assertEqual(len(result["model_results"][0]["cases"]), 1)
        self.assertEqual(result["model_results"][0]["terminal_error"]["http_status"], 503)
        self.assertIsNone(result["provider_network_calls"])
        self.assertIsNone(result["summary"]["compiler_retry_count"])

    def test_success_has_no_partial_result_fields(self):
        result, _, invoked, exit_code = self.run_cli("success")
        self.assertEqual((result["status"], len(invoked), exit_code), ("passed", 4, 0))
        for field in ("interrupted_case", "terminal_error", "usage_scope"):
            self.assertNotIn(field, result)

    def test_budget_error_capture_rejects_arbitrary_status_and_keeps_first_cause(self):
        for code, status, expected in ((429, "RESOURCE_EXHAUSTED", 429),
                                       (503, PRIVATE, 503), ("503", PRIVATE, None), (True, PRIVATE, None)):
            with self.subTest(code=code, status=status):
                error = RuntimeError(PRIVATE)
                error.code, error.status = code, status
                budget = ProviderBudget(POLICY)
                def fail():
                    raise error
                with self.assertRaises(BudgetStop) as caught:
                    budget.dispatch(kind="google", model="gemini-2.5-pro", request={},
                        input_bound=100, output_bound=100, invoke=fail, usage=lambda _: (100, 20))
                self.assertEqual(budget.records[0]["http_status"], expected)
                self.assertEqual(budget.records[0]["provider_status"], status if status == "RESOURCE_EXHAUSTED" else None)
                self.assertIs(caught.exception, budget.stop_reason)
                self.assertNotIn(PRIVATE, json.dumps(budget.snapshot()))


if __name__ == "__main__":
    unittest.main()
