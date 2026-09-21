"""Request diagnostics are bounded observations, never error-message logging."""
from copy import deepcopy
import json
import unittest

from src.ops.openai_error_diagnostics import openai_http_error_metadata, openai_request_error_metadata
from src.utils.provider_errors import provider_error_projection


class OpenAIRequestErrorDiagnosticsTests(unittest.TestCase):
    def project(self, error=None, *, body=None, headers=None, status=400):
        return openai_request_error_metadata(status_code=status, headers=headers or {},
            body=body if body is not None else json.dumps({'error': error or {}}).encode())

    def test_reviewed_schema_error_is_observed(self):
        result = self.project(dict(code='invalid_json_schema', type='invalid_request_error', param='text.format.schema'))
        self.assertEqual(result['schema_version'], 'openai_http_error_metadata_v2')
        self.assertEqual([result[key] for key in ('error_code', 'error_type', 'error_param')],
                         ['invalid_json_schema', 'invalid_request_error', 'text.format.schema'])
        self.assertTrue(all(result['availability'][key] == 'captured' for key in ('error_code', 'error_type', 'error_param')))

    def test_missing_code_does_not_hide_documented_type_and_parameter(self):
        result = self.project(dict(code=None, type='invalid_request_error', param='service_tier', message='PRIVATE'))
        self.assertIsNone(result['error_code'])
        self.assertEqual(result['availability']['error_code'], 'absent')
        self.assertEqual(result['error_type'], 'invalid_request_error')
        self.assertEqual(result['error_param'], 'service_tier')
        self.assertNotIn('PRIVATE', json.dumps(result))

    def test_known_request_codes_and_parameters_are_exact(self):
        pairs = [('invalid_value', 'model'), ('invalid_type', 'input'), ('missing_required_parameter', 'instructions'),
                 ('unknown_parameter', 'store'), ('unsupported_parameter', 'reasoning.effort'),
                 ('unsupported_value', 'text.format.type'), ('context_length_exceeded', 'max_output_tokens'),
                 ('model_not_found', 'model')]
        for code, param in pairs:
            with self.subTest(code=code):
                result = self.project(dict(code=code, param=param))
                self.assertEqual((result['error_code'], result['error_param']), (code, param))

    def test_legacy_v1_stays_unaware_of_request_diagnostics(self):
        body = json.dumps({'error': dict(code='invalid_json_schema', type='invalid_request_error', param='model')}).encode()
        result = openai_http_error_metadata(status_code=400, headers={}, body=body)
        self.assertEqual(result['schema_version'], 'openai_http_error_metadata_v1')
        self.assertIsNone(result['error_code'])
        self.assertEqual(result['availability']['error_code'], 'unrecognized')
        self.assertNotIn('error_type', result)
        self.assertNotIn('error_param', result)

    def test_headers_and_legacy_codes_survive_in_v2(self):
        result = self.project(dict(code='server_is_overloaded', type='server_error'), status=503,
                              headers={'X-Request-ID': 'req_abcdef123456', 'Retry-After': '30'})
        self.assertEqual(result['error_code'], 'server_is_overloaded')
        self.assertEqual(result['request_id'], 'req_abcdef123456')
        self.assertEqual(result['retry_after'], {'seconds': 30})

    def test_status_does_not_infer_or_replace_body_fields(self):
        result = self.project(dict(code='slow_down'), status=400)
        self.assertEqual(result['error_code'], 'slow_down')
        self.assertIsNone(result['error_type'])
        self.assertIsNone(result['error_param'])
        empty = self.project(dict(message='invalid_json_schema at text.format.schema'), status=400)
        self.assertTrue(all(empty[key] is None for key in ('error_code', 'error_type', 'error_param')))

    def test_unknown_and_private_fields_never_escape(self):
        headers = {'x-request-id': 'req_abcdef123456', 'Authorization': 'Bearer PRIVATE_KEY',
                   'Set-Cookie': 'PRIVATE_COOKIE', 'openai-organization': 'PRIVATE_ORG'}
        error = dict(code='PRIVATE_CODE', type='PRIVATE_TYPE', param='PRIVATE_PARAM',
                     message='PRIVATE_PROMPT', details={'schema': 'PRIVATE_SCHEMA'})
        before = deepcopy((headers, error))
        result = self.project(error, headers=headers)
        self.assertEqual((headers, error), before)
        self.assertNotIn('PRIVATE', json.dumps(result))
        self.assertTrue(all(result['availability'][key] == 'unrecognized' for key in ('error_code', 'error_type', 'error_param')))

    def test_no_parameter_prefix_or_schema_path_capture(self):
        for param in ('text.format.schema.PRIVATE', 'input[0].content', 'metadata.PRIVATE',
                      'model\nPRIVATE', 'model PRIVATE', ' model', 'MODEL', '$.model', 'text/format/schema'):
            with self.subTest(param=param):
                result = self.project(dict(param=param))
                self.assertIsNone(result['error_param'])
                self.assertEqual(result['availability']['error_param'], 'unrecognized')

    def test_non_string_values_are_not_coerced(self):
        for value in (True, 400, 0, [], {}, ['model']):
            with self.subTest(value=value):
                result = self.project(dict(code=value, type=value, param=value))
                self.assertTrue(all(result[key] is None for key in ('error_code', 'error_type', 'error_param')))
                self.assertTrue(all(result['availability'][key] == 'unrecognized' for key in ('error_code', 'error_type', 'error_param')))

    def test_absent_null_and_unavailable_are_distinct(self):
        for error in ({}, dict(code=None, type=None, param=None)):
            result = self.project(error)
            self.assertTrue(all(result['availability'][key] == 'absent' for key in ('error_code', 'error_type', 'error_param')))
        result = openai_request_error_metadata(status_code=400, headers={}, body=None)
        self.assertTrue(all(result['availability'][key] == 'unavailable' for key in ('error_code', 'error_type', 'error_param')))

    def test_invalid_json_shapes_retain_available_request_id(self):
        for body, state in ((b'PRIVATE', 'unreadable_json'), (b'\xff', 'unreadable_json'),
                            (b'[]', 'invalid_shape'), (b'{"error":[]}', 'invalid_shape'),
                            ('PRIVATE', 'invalid_body'), (b'{"error":null}', 'absent')):
            with self.subTest(state=state):
                result = self.project(body=body, headers={'x-request-id': 'req_abcdef'})
                self.assertEqual(result['request_id'], 'req_abcdef')
                self.assertTrue(all(result['availability'][key] == state for key in ('error_code', 'error_type', 'error_param')))
                self.assertNotIn('PRIVATE', json.dumps(result))

    def test_oversized_body_is_not_partially_parsed(self):
        result = self.project(body=b'{"error":{"code":"invalid_json_schema"},"other":"' + b'P'*65536 + b'"}')
        self.assertTrue(all(result['availability'][key] == 'body_too_large' for key in ('error_code', 'error_type', 'error_param')))

    def test_duplicate_fields_are_ambiguous_not_last_value_wins(self):
        for body in (b'{"error":{"code":"PRIVATE","code":"invalid_json_schema"}}',
                     b'{"error":{},"error":{"param":"model"}}',
                     b'{"error":{"param":"model","details":{"x":1,"x":2}}}'):
            result = self.project(body=body)
            self.assertTrue(all(result[key] is None for key in ('error_code', 'error_type', 'error_param')))
            self.assertTrue(all(result['availability'][key] == 'unreadable_json' for key in ('error_code', 'error_type', 'error_param')))

    def test_deep_json_does_not_escape_the_projection(self):
        result = self.project(body=b'['*5000 + b']'*5000)
        self.assertEqual(result['availability']['error_param'], 'unreadable_json')

    def test_header_injection_and_duplicates_remain_rejected(self):
        for headers in ({'x-request-id': 'req_abcdef\r\nPRIVATE', 'Retry-After': '30\r\nPRIVATE'},
                        {'x-request-id': 'req_abcdef', 'X-Request-ID': 'req_123456'}):
            result = self.project(dict(param='model'), headers=headers)
            self.assertIsNone(result['request_id'])
            self.assertIsNone(result['retry_after'])
            self.assertNotIn('PRIVATE', json.dumps(result))

    def test_success_and_non_http_status_have_no_projection(self):
        for status in (200, 302, True, '400', 600):
            self.assertIsNone(self.project(dict(code='invalid_json_schema'), status=status))

    def test_public_errors_do_not_acquire_private_metadata(self):
        error = RuntimeError('PRIVATE provider message')
        error.status_code, error.code, error.param = 400, 'invalid_json_schema', 'text.format.schema'
        error.type, error.request_id = 'invalid_request_error', 'req_abcdef'
        self.assertEqual(provider_error_projection(error),
                         {'error_type': 'RuntimeError', 'code': None, 'http_status': 400, 'provider_status': None})


if __name__ == '__main__':
    unittest.main()
