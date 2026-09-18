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
_MAX_RETRY_SECONDS = 604800


def _header(headers: Mapping[str, str], name: str):
    values = [value for key, value in headers.items() if isinstance(key, str) and key.lower() == name]
    if not values:
        return None, "absent"
    if len(values) != 1 or not isinstance(values[0], str) or any(c in values[0] for c in "\r\n"):
        return None, "unrecognized"
    return values[0].strip(" \t"), "present"


def _error_code(body: bytes | None):
    if body is None:
        return None, "unavailable"
    if not isinstance(body, bytes):
        return None, "invalid_body"
    if len(body) > _MAX_BODY_BYTES:
        return None, "body_too_large"
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
