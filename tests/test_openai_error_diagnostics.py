"""Safe local evidence without free-form provider text or recovery side effects."""

from copy import deepcopy
import json
import unittest

from src.ops.openai_error_diagnostics import openai_http_error_metadata
from src.utils.provider_errors import provider_error_projection


class OpenAIErrorDiagnosticsTests(unittest.TestCase):
    def project(self, *, code="server_is_overloaded", headers=None, body=None, status=503):
        return openai_http_error_metadata(status_code=status, headers=headers or {},
            body=json.dumps({"error": {"code": code}}).encode() if body is None else body)

    def test_known_codes_are_observed_without_status_inference(self):
        for status, code in ((503,"server_is_overloaded"),(429,"slow_down"),(503,"slow_down"),(429,"rate_limit_exceeded")):
            with self.subTest(status=status,code=code):
                result=self.project(status=status,code=code)
                self.assertEqual(result["http_status"],status)
                self.assertEqual(result["error_code"],code)
                self.assertEqual(result["availability"]["error_code"],"captured")

    def test_only_selected_metadata_survives_private_body_and_headers(self):
        headers={"X-Request-ID":"req_0123456789abcdef0123456789abcdef", "Retry-After":"30",
                 "Authorization":"Bearer PRIVATE_CREDENTIAL", "Set-Cookie":"PRIVATE_COOKIE", "openai-organization":"PRIVATE_ORG"}
        body=json.dumps({"error":{"code":"server_is_overloaded","message":"PRIVATE_PROMPT",
            "param":"PRIVATE_PARAMETER","details":{"credential":"PRIVATE_DETAIL"}},"other":"PRIVATE_EXTRA"}).encode()
        original=deepcopy(headers)
        result=self.project(headers=headers,body=body)
        self.assertEqual(result["request_id"],headers["X-Request-ID"])
        self.assertEqual(result["retry_after"],{"seconds":30})
        self.assertEqual(headers,original)
        self.assertNotIn("PRIVATE",json.dumps(result))

    def test_unknown_codes_and_non_string_values_are_not_copied(self):
        for code in ("sk-proj-PRIVATE", "private_response_detail", "server_is_overloaded\nPRIVATE", [], {}, 503, True):
            with self.subTest(code=code):
                result=self.project(code=code)
                self.assertIsNone(result["error_code"])
                self.assertEqual(result["availability"]["error_code"],"unrecognized")
                self.assertNotIn("PRIVATE",json.dumps(result))

    def test_missing_values_are_explicit_not_invented(self):
        result=self.project(body=b'{}')
        self.assertEqual(result["availability"],dict(error_code="absent",request_id="absent",retry_after="absent"))
        self.assertIsNone(result["retry_after"])

    def test_invalid_or_oversized_bodies_keep_valid_headers(self):
        for body,state in ((b'<html>PRIVATE</html>',"unreadable_json"),(b'\xff',"unreadable_json"),
            (b'[]',"invalid_shape"),(b'{"error":"PRIVATE"}',"invalid_shape"),
            (b'['*5000+b']'*5000,"unreadable_json"),(b'PRIVATE'*12000,"body_too_large")):
            with self.subTest(state=state):
                result=self.project(body=body,headers={"x-request-id":"req_abcdef123456"})
                self.assertEqual(result["request_id"],"req_abcdef123456")
                self.assertEqual(result["availability"]["error_code"],state)
                self.assertNotIn("PRIVATE",json.dumps(result))

    def test_unavailable_body_remains_distinct_from_missing_code(self):
        result=openai_http_error_metadata(status_code=503,headers={},body=None)
        self.assertEqual(result["availability"]["error_code"],"unavailable")

    def test_request_id_shapes_and_injection_rejection(self):
        for value in ("Bearer PRIVATE", "sk-proj-PRIVATE", "req_abc\r\nAuthorization: PRIVATE", "req_"+"a"*129,
                      "req_abc def", "req_abc_def", "req_"+"한"*32, "req_abcdef, req_123456"):
            with self.subTest(value=value):
                result=self.project(headers={"x-request-id":value})
                self.assertIsNone(result["request_id"])
                self.assertEqual(result["availability"]["request_id"],"unrecognized")
                self.assertNotIn("PRIVATE",json.dumps(result))
        self.assertEqual(self.project(headers={"X-Request-ID":"req_"+"z"*51})["request_id"],"req_"+"z"*51)

    def test_duplicate_selected_headers_are_unrecognized(self):
        result=self.project(headers={"X-Request-Id":"req_abcdef","x-request-id":"req_123456",
                                     "Retry-After":"3","retry-after":"4"})
        self.assertIsNone(result["request_id"])
        self.assertIsNone(result["retry_after"])

    def test_retry_after_seconds_and_canonical_date(self):
        for value,expected in (("0",{"seconds":0}),("604800",{"seconds":604800}),
            ("Fri, 18 Sep 2026 00:04:00 GMT",{"at_utc":"2026-09-18T00:04:00Z"})):
            self.assertEqual(self.project(headers={"Retry-After":value})["retry_after"],expected)

    def test_retry_after_invalid_values_are_not_logged_or_executed(self):
        for value in ("-1","1.5","604801","9"*300,"PRIVATE","30\r\nPRIVATE",
                      "Sat, 18 Sep 2026 00:04:00 GMT","Fri, 99 Sep 2026 00:04:00 GMT"):
            with self.subTest(value=value):
                result=self.project(headers={"Retry-After":value})
                self.assertIsNone(result["retry_after"])
                self.assertEqual(result["availability"]["retry_after"],"unrecognized")
                self.assertNotIn("PRIVATE",json.dumps(result))

    def test_success_and_non_http_statuses_have_no_error_projection(self):
        for status in (200,302,True,"503",600):
            self.assertIsNone(self.project(status=status))

    def test_public_projection_does_not_acquire_local_metadata(self):
        error=RuntimeError("PRIVATE provider error")
        error.status_code=503
        error.code="server_is_overloaded"
        error.request_id="req_abcdef"
        error.headers={"Retry-After":"30"}
        result=provider_error_projection(error)
        self.assertEqual(result,{"error_type":"RuntimeError","code":None,"http_status":503,"provider_status":None})


if __name__ == "__main__":
    unittest.main()
