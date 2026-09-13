"""No mutable graph/exception/agent state is used as an observation sink."""

import unittest

from src.utils.request_diagnostics import (
    capture_request_diagnostics, diagnostic_location, diagnostics_enabled,
    record_diagnostic, request_diagnostic_scope,
)


class RequestDiagnosticsTests(unittest.TestCase):
    def test_nested_request_and_capture_restore_caller_without_cross_delivery(self):
        with capture_request_diagnostics() as outer:
            with request_diagnostic_scope(True):
                with diagnostic_location(phase="planning"):
                    record_diagnostic("outer", {"number": 1})
                    with capture_request_diagnostics() as inner:
                        with request_diagnostic_scope(True):
                            record_diagnostic("inner", {"number": 2})
                    with request_diagnostic_scope(False):
                        self.assertFalse(diagnostics_enabled())
                        record_diagnostic("disabled", {})
                    record_diagnostic("outer", {"number": 3})
        self.assertFalse(diagnostics_enabled())
        self.assertEqual([e["data"]["number"] for e in outer[0]["events"]], [1, 3])
        self.assertEqual(inner[0]["events"], [{"kind": "inner", "location": {}, "data": {"number": 2}}])
        self.assertTrue(all(e["location"] == {"phase": "planning"} for e in outer[0]["events"]))

    def test_unserializable_and_nonfinite_values_record_unavailable_not_repr(self):
        class Private:
            def __repr__(self):
                raise AssertionError("must not render private objects")
        with capture_request_diagnostics() as captured:
            with request_diagnostic_scope(True):
                record_diagnostic("bad", Private())
                record_diagnostic("bad", float("nan"))
                record_diagnostic("good", {"number": 1})
        self.assertEqual([e["data"] for e in captured[0]["events"]], [
            {"observation_unavailable": "TypeError"}, {"observation_unavailable": "ValueError"}, {"number": 1}])

    def test_record_and_delivery_are_independent_copies(self):
        original = {"nested": [1]}
        with capture_request_diagnostics() as captured:
            with request_diagnostic_scope(True) as recorder:
                record_diagnostic("sample", original)
                original["nested"].append(2)
                first = recorder.snapshot()
                first["events"][0]["data"]["nested"].append(3)
        self.assertEqual(captured[0]["events"][0]["data"], {"nested": [1]})
        captured[0]["events"].clear()
        self.assertTrue(recorder.snapshot()["events"])
