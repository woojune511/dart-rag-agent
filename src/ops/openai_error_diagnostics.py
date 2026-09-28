"""Opt-in local HTTP error metadata; never runtime/public error projection.

No request, credential, raw message/body/header map, retry or persistence is owned
here. Unknown values are explicitly unavailable rather than copied as free text.
"""

from collections.abc import Mapping
from email.utils import format_datetime, parsedate_to_datetime
import json
import re


# Reviewed OpenAI overload/ramp-rate codes, including the earlier rate-limit code.
_ERROR_CODES = frozenset({"server_is_overloaded", "slow_down", "rate_limit_exceeded"})
_REQUEST_ID = re.compile(r"req_[A-Za-z0-9]{6,128}", re.ASCII)
_MAX_BODY_BYTES = 65536
_MAX_JSON_NESTING = 128
_MAX_RETRY_SECONDS = 604800


def _header(headers: Mapping[str, str], name: str):
    values = [value for key, value in headers.items() if isinstance(key, str) and key.lower() == name]
    if not values:
        return None, "absent"
    if len(values) != 1 or not isinstance(values[0], str) or any(c in values[0] for c in "\r\n"):
        return None, "unrecognized"
    return values[0].strip(" \t"), "present"


def _json_nesting_exceeds_limit(body: bytes) -> bool:
    """Bound nesting before decoder behavior can vary across platforms."""
    depth = 0
    in_string = False
    escaped = False
    for value in body:
        if in_string:
            if escaped:
                escaped = False
            elif value == ord("\\"):
                escaped = True
            elif value == ord('"'):
                in_string = False
            continue
        if value == ord('"'):
            in_string = True
        elif value in (ord("["), ord("{")):
            depth += 1
            if depth > _MAX_JSON_NESTING:
                return True
        elif value in (ord("]"), ord("}")) and depth:
            depth -= 1
    return False


def _error_code(body: bytes | None):
    if body is None:
        return None, "unavailable"
    if not isinstance(body, bytes):
        return None, "invalid_body"
    if len(body) > _MAX_BODY_BYTES:
        return None, "body_too_large"
    if _json_nesting_exceeds_limit(body):
        return None, "unreadable_json"
    try:
        payload = json.loads(body)
    except (ValueError, RecursionError):
        return None, "unreadable_json"
    if not isinstance(payload, dict):
        return None, "invalid_shape"
    error = payload.get("error")
    if error is None:
        return None, "absent"
    if not isinstance(error, dict):
        return None, "invalid_shape"
    code = error.get("code")
    if code is None:
        return None, "absent"
    return (code, "captured") if isinstance(code, str) and code in _ERROR_CODES else (None, "unrecognized")


def _retry_after(value: str | None, state: str):
    if state != "present":
        return None, state
    if len(value) <= 6 and value.isascii() and value.isdecimal():
        seconds = int(value)
        if seconds <= _MAX_RETRY_SECONDS:
            return {"seconds": seconds}, "captured"
    if len(value) == 29 and value.isascii():
        try:
            date = parsedate_to_datetime(value)
            if format_datetime(date, usegmt=True) == value:
                return {"at_utc": date.strftime("%Y-%m-%dT%H:%M:%SZ")}, "captured"
        except (TypeError, ValueError, OverflowError):
            pass
    return None, "unrecognized"


def openai_http_error_metadata(*, status_code: int, headers: Mapping[str, str], body: bytes | None) -> dict | None:
    """Select bounded metadata from an already received error; never send/retry.

    Only reviewed codes and req_ IDs with 6-128 ASCII alphanumerics are retained.
    Other ID formats remain unrecognized; the shape is a local disclosure rule,
    not a promise about provider formats. Retry-After accepts 0-604800 integer
    seconds or canonical GMT HTTP dates. It is observational, never a retry grant.
    """
    if type(status_code) is not int or not 400 <= status_code <= 599:
        return None
    code, code_state = _error_code(body)
    request_id, id_state = _header(headers, "x-request-id")
    if id_state == "present":
        if _REQUEST_ID.fullmatch(request_id):
            id_state = "captured"
        else:
            request_id, id_state = None, "unrecognized"
    retry, retry_state = _retry_after(*_header(headers, "retry-after"))
    return {"schema_version": "openai_http_error_metadata_v1", "http_status": status_code,
            "error_code": code, "request_id": request_id, "retry_after": retry,
            "availability": {"error_code": code_state, "request_id": id_state, "retry_after": retry_state}}


# These are local disclosure choices, not an exhaustive provider error taxonomy.
# Keep v1 and its existing callers unchanged; request diagnostics explicitly opt in.
_REQUEST_ERROR_CODES = _ERROR_CODES | frozenset({
    "invalid_json_schema", "invalid_value", "invalid_type", "missing_required_parameter",
    "unknown_parameter", "unsupported_parameter", "unsupported_value",
    "context_length_exceeded", "model_not_found",
})
_REQUEST_ERROR_TYPES = frozenset({"invalid_request_error", "server_error", "rate_limit_error"})
_REQUEST_ERROR_PARAMS = frozenset({
    "model", "input", "instructions", "reasoning", "reasoning.effort", "text", "text.format",
    "text.format.type", "text.format.name", "text.format.schema", "text.format.strict",
    "max_output_tokens", "service_tier", "store", "stream",
})


def _request_error_object(body: bytes | None):
    if body is None:
        return None, "unavailable"
    if not isinstance(body, bytes):
        return None, "invalid_body"
    if len(body) > _MAX_BODY_BYTES:
        return None, "body_too_large"
    if _json_nesting_exceeds_limit(body):
        return None, "unreadable_json"

    def unique_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Ambiguous error object")
            result[key] = value
        return result

    try:
        payload = json.loads(body, object_pairs_hook=unique_object)
    except (ValueError, RecursionError):
        return None, "unreadable_json"
    if not isinstance(payload, dict):
        return None, "invalid_shape"
    error = payload.get("error")
    if error is None:
        return None, "absent"
    return (error, "present") if isinstance(error, dict) else (None, "invalid_shape")


def _request_error_value(error, state, field, allowed):
    if error is None:
        return None, state
    value = error.get(field)
    if value is None:
        return None, "absent"
    return (value, "captured") if isinstance(value, str) and value in allowed else (None, "unrecognized")


def openai_request_error_metadata(*, status_code: int, headers: Mapping[str, str], body: bytes | None) -> dict | None:
    """Opt-in v2 request diagnostics from an already received error; no I/O.

    Keep only reviewed exact code/type/parameter values and v1's bounded headers.
    Request values, schema-internal paths, indexed input paths and messages are
    never copied. Missing/null fields stay absent; status and prose infer nothing.
    Ambiguous JSON and unknown fields remain visibly unavailable. Callers own
    persistence and must preserve the original HTTP outcome if capture fails.
    """
    result = openai_http_error_metadata(status_code=status_code, headers=headers, body=body)
    if result is None:
        return None
    error, state = _request_error_object(body)
    result["schema_version"] = "openai_http_error_metadata_v2"
    for field, output, allowed in (
        ("code", "error_code", _REQUEST_ERROR_CODES),
        ("type", "error_type", _REQUEST_ERROR_TYPES),
        ("param", "error_param", _REQUEST_ERROR_PARAMS),
    ):
        value, availability = _request_error_value(error, state, field, allowed)
        result[output] = value
        result["availability"][output] = availability
    return result
