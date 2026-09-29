"""Explicit counted admission for synchronous, stateless text Responses.

The private SDK boundary builds each request once and sends that frozen request.
Counts are separate attempts, never local estimates or default runtime calls.
"""

from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import json
from unittest.mock import patch

from src.ops.openai_provider_admission import _openai_request, openai_usage
from src.ops.provider_admission import BudgetStop, json_bytes


def _text_input(value):
    if isinstance(value, str):
        return bool(value)
    if not isinstance(value, list) or not value:
        return False
    for message in value:
        if (not isinstance(message, dict) or set(message) - {"type", "role", "content"}
                or message.get("type", "message") != "message"
                or message.get("role") not in {"user", "assistant", "system", "developer"}):
            return False
        content = message.get("content")
        if isinstance(content, str):
            continue
        if (not isinstance(content, list) or not content
                or any(not isinstance(part, dict) or set(part) != {"type", "text"}
                       or part["type"] != "input_text" or not isinstance(part["text"], str) for part in content)):
            return False
    return True


def counted_openai_request(policy, body):
    """Validate bounded text input and project every model-visible count field.

    This returns an unmeasured descriptor, never a generation input reservation.
    Only generation controls absent from the count API are omitted from its body.
    """
    if policy.get("openai_input_counting") != "responses_input_tokens_v1":
        raise ValueError("explicit OpenAI input counting is required")
    if "request_settings_by_model" in policy:
        settings = policy["request_settings_by_model"].get(body.get("model"))
        if not isinstance(settings, dict):
            raise BudgetStop("unapproved_model", "Model is outside the counted admission")
        policy = {**policy, "request_settings": settings}
    params = _openai_request(policy, body)
    if (not _text_input(body["input"])
            or ("instructions" in body and not isinstance(body["instructions"], str))):
        raise BudgetStop("unapproved_request_config", "Only explicit stateless text messages are admitted")
    if len(json_bytes(body)) > policy["max_openai_request_bytes"]:
        raise BudgetStop("unapproved_input_size", "Body exceeds the explicit byte limit before counting")
    count_body = {key: deepcopy(body[key]) for key in ("model", "input", "instructions", "reasoning", "text") if key in body}
    return params, count_body


def _prepared(client, cast_to, options, *, stream):
    """Finish SDK conversion/hooks once; HTTP hooks/auth cannot rewrite the body."""
    frozen_options = client._prepare_options(deepcopy(options))
    if (stream or frozen_options.get_max_retries(client.max_retries) != 0
            or client.custom_auth is not None or client._client.auth is not None
            or any(client._client.event_hooks.values())):
        raise BudgetStop("unapproved_transport", "Counted requests require single-attempt transport without HTTP hooks")
    cast_to = client._maybe_override_cast_to(cast_to, frozen_options)
    built = client._build_request(frozen_options)
    client._prepare_request(built)
    if client._should_stream_response_body(built):
        raise BudgetStop("unapproved_transport", "Streaming response bodies are not admitted")
    return built, frozen_options, cast_to


def _send_once(client, built, options, cast_to):
    # Bypass the SDK request/rebuild/retry loop, keeping its normal response parser.
    response = client._client.send(built, stream=False, follow_redirects=False)
    if response.status_code >= 400:
        raise client._make_status_error_from_response(response)
    response.raise_for_status()
    return client._process_response(cast_to=cast_to, options=options, response=response,
        stream=False, stream_cls=None, retries_taken=0)


@contextmanager
def guarded_counted_runtime_openai_responses(budget, authorize_request):
    """Count then generate under one shared budget, with caller-owned authority.

    Generation/count pairs serialize on this experiment budget. Embeddings still
    require the enclosing provider guard; old byte-bound contexts are untouched.
    """
    from openai._base_client import AsyncAPIClient, SyncAPIClient
    from openai._legacy_response import LegacyAPIResponse

    policy = deepcopy(budget.policy)
    if (not budget.openai_server_counting or policy.get("openai_response_binding") != "runtime_generated_v1"
            or not callable(authorize_request)
            or type(policy.get("max_openai_response_calls")) is not int or policy["max_openai_response_calls"] <= 0
            or type(policy.get("max_openai_input_tokens")) is not int or not 0 < policy["max_openai_input_tokens"] <= 200000
            or type(policy.get("max_openai_request_bytes")) is not int or policy["max_openai_request_bytes"] <= 0):
        raise ValueError("Counted runtime Responses require explicit call, input, byte and authority limits")
    active = ContextVar("counted_openai_generation", default=None)
    counting = ContextVar("counted_openai_input_request", default=None)
    original_request = SyncAPIClient.request

    def request(client, cast_to, options, *, stream=False, stream_cls=None):
        with budget.lock:
            if budget.closed:
                raise budget.stop_reason
            state, count_state = active.get(), counting.get()
            if state is None and budget.active_request_kind == "openai_embedding":
                built = client._build_request(options)
                if built.method == "POST" and str(built.url) == "https://api.openai.com/v1/embeddings":
                    return original_request(client, cast_to, options, stream=stream, stream_cls=stream_cls)
            if count_state is not None:
                if state is None or state["client"] is not client or count_state["sent"]:
                    raise budget._close("unapproved_transport", "Only one count request is admitted")
                built, frozen_options, cast_to = _prepared(client, cast_to, options, stream=stream)
                if (built.method != "POST" or str(built.url) != "https://api.openai.com/v1/responses/input_tokens"
                        or json_bytes(json.loads(built.content)) != json_bytes(count_state["body"])):
                    raise budget._close("unapproved_request_body", "Count input or endpoint differs from the frozen generation")
                count_state["sent"] = True
                return _send_once(client, built, frozen_options, cast_to)
            if state is not None:
                raise budget._close("unapproved_transport", "Nested generation is not admitted")
            try:
                built, frozen_options, cast_to = _prepared(client, cast_to, options, stream=stream)
                if built.method != "POST" or str(built.url) != "https://api.openai.com/v1/responses":
                    raise BudgetStop("unapproved_transport", "Only the official Responses endpoint is admitted")
                body = json.loads(built.content)
                params, count_body = counted_openai_request(policy, body)
                if authorize_request(deepcopy(body)) is not True:
                    raise BudgetStop("unapproved_runtime_request", "Request is outside the admitted runtime phase")
            except Exception as error:
                code = error.code if isinstance(error, BudgetStop) else "unapproved_runtime_request"
                raise budget._close(code, "Counted request failed local admission") from error

            def count():
                count_state = {"body": count_body, "sent": False}
                token = counting.set(count_state)
                try:
                    result = client.responses.input_tokens.count(**deepcopy(count_body), timeout=frozen_options.timeout)
                    if isinstance(result, LegacyAPIResponse):
                        result = result.parse()
                    if not count_state["sent"] or getattr(result, "object", None) != "response.input_tokens":
                        raise ValueError("Input count response identity is unavailable")
                    return getattr(result, "input_tokens", None)
                finally:
                    counting.reset(token)

            # SDK raw-response wrappers may cache a bound create method before
            # guard entry. Authorize at request(), which all those wrappers use.
            token = active.set({"client": client})
            try:
                measurement = budget.count_openai_input(model=params["model"], generation_request=body,
                    count_request=count_body, output_bound=params["output_bound"], invoke=count)
                if measurement["total_tokens"] > policy["max_openai_input_tokens"]:
                    raise budget._close("unapproved_input_size", "Measured input exceeds the admitted token limit")
                response = budget.dispatch(**params, input_bound=measurement["total_tokens"], input_measurement=measurement,
                    invoke=lambda: _send_once(client, built, frozen_options, cast_to), usage=openai_usage)
                if budget.closed:
                    raise budget.stop_reason
                return response
            finally:
                active.reset(token)

    async def blocked_async(*args, **kwargs):
        raise budget._close("unapproved_transport", "Asynchronous requests are not admitted")

    with patch.object(SyncAPIClient, "request", request), patch.object(AsyncAPIClient, "request", blocked_async):
        yield budget
