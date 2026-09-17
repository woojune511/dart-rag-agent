"""Caller persistence preserves runtime outcomes and reports unavailable artifacts."""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from src.ops.application_diagnostics import persist_request_diagnostics
from src.utils.provider_errors import ProviderAdmissionError
from src.utils.request_diagnostics import record_diagnostic, request_diagnostic_scope
from tests import test_interrupted_run_diagnostics as interrupted_fixture


_events = interrupted_fixture._events


class ApplicationDiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.directory = Path(self.enterContext(tempfile.TemporaryDirectory()))
        self.path = self.directory / "case" / "request_diagnostics.json"

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def test_success_preserves_result_prompt_and_exact_debug_snapshot(self):
        fixture = interrupted_fixture.InterruptedRunDiagnosticsTests()
        plain, _, _ = fixture.agent(stop_at="none")
        captured, _, _ = fixture.agent(stop_at="none")
        expected = plain.run("Describe activity.", include_debug_bundle=True, include_review_trace=True)
        with persist_request_diagnostics(self.path):
            actual = captured.run("Describe activity.", include_debug_bundle=True, include_review_trace=True)
        self.assertEqual(actual, expected)
        self.assertEqual(plain.llm.prompts[0].to_messages(), captured.llm.prompts[0].to_messages())
        self.assertEqual(self.read(), [actual.debug_bundle["request_diagnostics"]])
        self.assertNotIn("request_diagnostics", json.dumps(actual.review_trace))

    def test_stops_keep_earlier_program_pending_attempt_and_original_exception(self):
        for position in ("first", "retry", "island"):
            with self.subTest(position=position):
                path = self.directory / position / "request_diagnostics.json"
                agent, stop, _ = interrupted_fixture.InterruptedRunDiagnosticsTests().agent(stop_at=position)
                with self.assertRaises(ProviderAdmissionError) as raised:
                    with persist_request_diagnostics(path):
                        agent.run("Describe activity and size.", include_debug_bundle=True)
                self.assertIs(raised.exception, stop)
                snapshot, = json.loads(path.read_text(encoding="utf-8"))
                self.assertEqual(_events(snapshot, "run_interrupted")[0]["data"]["code"], stop.code)
                attempts = _events(snapshot, "compiler_attempt")
                self.assertEqual(len(attempts), 0 if position == "first" else 1)
                requests = _events(snapshot, "compiler_request")
                self.assertEqual(len(requests), 1 if position == "first" else 2)
                for attempt in attempts:
                    program = attempt["data"]["model_program_json"]
                    self.assertEqual(hashlib.sha256(program.encode()).hexdigest(), attempt["data"]["model_program_sha256"])
                self.assertEqual(_events(snapshot, "run_completed"), [])
                agent._execute_semantic_calculation_program.assert_not_called()
                agent._assemble_final_phase.assert_not_called()
                self.assertEqual([p.name for p in path.parent.iterdir()], ["request_diagnostics.json"])

    def test_debug_off_and_no_run_create_no_artifact(self):
        with persist_request_diagnostics(self.path):
            pass
        self.assertFalse(self.path.exists())
        agent, stop, _ = interrupted_fixture.InterruptedRunDiagnosticsTests().agent(stop_at="first")
        with self.assertRaises(ProviderAdmissionError) as raised:
            with persist_request_diagnostics(self.path):
                agent.run("Describe activity.", include_debug_bundle=False)
        self.assertIs(raised.exception, stop)
        self.assertFalse(self.path.parent.exists())

    def test_existing_file_is_preserved_and_failure_does_not_replace_stop(self):
        self.path.parent.mkdir()
        self.path.write_bytes(b"immutable predecessor")
        agent, stop, _ = interrupted_fixture.InterruptedRunDiagnosticsTests().agent(stop_at="first")
        with self.assertLogs("src.ops.application_diagnostics", level="ERROR") as logs:
            with self.assertRaises(ProviderAdmissionError) as raised:
                with persist_request_diagnostics(self.path):
                    agent.run("Describe activity.", include_debug_bundle=True)
        self.assertIs(raised.exception, stop)
        self.assertEqual(self.path.read_bytes(), b"immutable predecessor")
        self.assertIn("FileExistsError", logs.output[0])
        self.assertNotIn(str(self.path), logs.output[0])

    def test_write_failure_is_reported_without_changing_success_or_stop(self):
        for failure in (False, True):
            with self.subTest(failure=failure):
                stop = ProviderAdmissionError("budget_reservation_exceeded", "private stop body")
                outcome = object()
                def run():
                    with request_diagnostic_scope(True):
                        record_diagnostic("observed", {"value": 12})
                        if failure:
                            raise stop
                        return outcome
                with patch.object(Path, "open", side_effect=PermissionError("private filesystem detail")), \
                        self.assertLogs("src.ops.application_diagnostics", level="ERROR") as logs:
                    if failure:
                        with self.assertRaises(ProviderAdmissionError) as raised:
                            with persist_request_diagnostics(self.path):
                                run()
                        self.assertIs(raised.exception, stop)
                    else:
                        with persist_request_diagnostics(self.path):
                            self.assertIs(run(), outcome)
                self.assertIn("PermissionError", logs.output[0])
                self.assertNotIn("private", "\n".join(logs.output))

    def test_nested_paths_preserve_separate_deliveries(self):
        inner = self.directory / "inner.json"
        with persist_request_diagnostics(self.path):
            with request_diagnostic_scope(True):
                record_diagnostic("outer", {"value": 1})
                with persist_request_diagnostics(inner):
                    with request_diagnostic_scope(True):
                        record_diagnostic("inner", {"value": 2})
        self.assertEqual([e["kind"] for e in self.read()[0]["events"]], ["outer"])
        self.assertEqual([e["kind"] for e in json.loads(inner.read_text(encoding="utf-8"))[0]["events"]], ["inner"])


if __name__ == "__main__":
    unittest.main()
