"""Opt-in, exact-request admission for synchronous text-only OpenAI Responses.

This private SDK boundary is covered by real-SDK/mocked-HTTP tests. It is not
installed by runtime defaults and does not authorize any experiment by itself.
"""

from contextlib import contextmanager
from copy import deepcopy
import hashlib
import json
from unittest.mock import patch

from src.ops.provider_admission import BudgetStop, ProviderBudget, json_bytes


def openai_request_parameters(policy, body):
    """Reserve a conservative byte-based input estimate, never a server count."""
    settings = policy["request_settings"]
    allowed = {"model", "input", "instructions", "max_output_tokens", "reasoning", "text",
               "store", "service_tier", "stream"}
    if (not isinstance(body, dict) or set(body) - allowed
            or any(body.get(key) != value for key, value in settings.items())
            or body.get("store") is not False or body.get("stream", False) is not False
            or body.get("service_tier") != "default"
            or not body.get("input") or body.get("model") not in policy["rates"]):
        raise BudgetStop("unapproved_request_config", "OpenAI request differs from the admitted text-only settings")
    text_format = (body.get("text") or {}).get("format", {})
    if text_format.get("type") != "json_schema" or text_format.get("strict") is not True:
        raise BudgetStop("unapproved_request_config", "Strict structured output is required")
    bound = body.get("max_output_tokens")
    overhead = policy["openai_input_overhead_tokens"]
    if type(bound) is not int or bound <= 0 or type(overhead) is not int or overhead < 0:
        raise BudgetStop("unapproved_request_config", "Explicit output and input reservation bounds are required")
    input_bound = len(json_bytes(body)) + overhead
    if input_bound > policy["max_openai_input_tokens"] or policy["max_openai_input_tokens"] > 200000:
        raise BudgetStop("unapproved_input_size", "Request exceeds the admitted short-context reservation")
    return dict(kind="openai_response", model=body["model"], request=deepcopy(body),
                input_bound=input_bound, output_bound=bound)


def openai_usage(response):
    from openai._legacy_response import LegacyAPIResponse

    if isinstance(response, LegacyAPIResponse):
        response = response.parse()
    usage = getattr(response, "usage", None)
    values = (getattr(usage, "input_tokens", None), getattr(usage, "output_tokens", None))
    if any(type(value) is not int for value in values) or values[0] <= 0 or values[1] < 0:
        raise ValueError("OpenAI usage unavailable")
    # Responses output_tokens already includes reasoning; do not add it again.
    return values


@contextmanager
def guarded_openai_responses(policy, expected_request_hashes):
    """Allow only the ordered rehearsed bodies, with no SDK retry or redirect."""
    from openai._base_client import AsyncAPIClient, SyncAPIClient

    budget = ProviderBudget(policy)
    policy = budget.policy
    expected = tuple(expected_request_hashes)
    if (not expected or len(expected) != policy["max_openai_response_calls"]
            or any(not isinstance(value, str) or len(value) != 64 for value in expected)):
        raise ValueError("One exact request hash is required for every admitted call")
    original = SyncAPIClient.request

    def request(client, cast_to, options, *, stream=False, stream_cls=None):
        with budget.lock:
            if budget.closed:
                raise budget.stop_reason
            if stream or options.get_max_retries(client.max_retries) != 0:
                raise budget._close("unapproved_transport", "Streaming and SDK retries are not admitted")
            built = client._build_request(options)
            if built.method != "POST" or str(built.url) != "https://api.openai.com/v1/responses":
                raise budget._close("unapproved_transport", "Only the official Responses endpoint is admitted")
            try:
                body = json.loads(built.content)
                params = openai_request_parameters(policy, body)
            except (ValueError, BudgetStop) as error:
                code = error.code if isinstance(error, BudgetStop) else "unapproved_request_config"
                raise budget._close(code, "OpenAI request failed local admission") from error
            index = len(budget.records)
            digest = hashlib.sha256(json_bytes(body)).hexdigest()
            if index >= len(expected) or digest != expected[index]:
                raise budget._close("unapproved_request_body", "Body or order differs from the approved rehearsal")

            # Request headers, API keys and detailed provider errors are never
            # retained. Restrict redirects for this scoped client invocation.
            redirects = client._client.follow_redirects
            client._client.follow_redirects = False
            try:
                response = budget.dispatch(**params, usage=openai_usage,
                    invoke=lambda: original(client, cast_to, options, stream=False, stream_cls=stream_cls))
            finally:
                client._client.follow_redirects = redirects
            if budget.closed:
                raise budget.stop_reason
            return response

    async def blocked_async(*args, **kwargs):
        raise budget._close("unapproved_transport", "Asynchronous requests are not admitted")

    with patch.object(SyncAPIClient, "request", request), patch.object(AsyncAPIClient, "request", blocked_async):
        yield budget


@contextmanager
def guarded_runtime_openai_responses(budget, authorize_request):
    """Share a mixed-provider budget for explicitly admitted runtime-generated input.

    Unlike fixed-input comparison, future planner/retrieval output is unknown.
    The caller must bind each dispatch to its approved current run/phase. This
    separate opt-in never relaxes the ordered-hash guard above or old policies.
    Embedding calls remain owned by the enclosing mixed-provider guard.
    """
    from contextvars import ContextVar
    from openai._base_client import AsyncAPIClient, SyncAPIClient
    from openai.resources.responses import AsyncResponses, Responses

    if (budget.policy.get("openai_response_binding") != "runtime_generated_v1"
            or not callable(authorize_request)
            or type(budget.policy.get("max_openai_response_calls")) is not int
            or budget.policy["max_openai_response_calls"] <= 0):
        raise ValueError("Runtime-generated Responses need a separate policy and request authorizer")
    active = ContextVar("admitted_openai_response", default=False)
    original_create, original_request = Responses.create, SyncAPIClient.request

    def create(client, *args, **kwargs):
        token = active.set(True)
        try:
            return original_create(client, *args, **kwargs)
        finally:
            active.reset(token)

    def request(client, cast_to, options, *, stream=False, stream_cls=None):
        if not active.get():
            # The enclosing guard owns other OpenAI operations. A direct
            # Responses request cannot bypass the resource/context boundary.
            built = client._build_request(options)
            if (budget.active_request_kind == "openai_embedding" and built.method == "POST"
                    and str(built.url) == "https://api.openai.com/v1/embeddings"):
                return original_request(client, cast_to, options, stream=stream, stream_cls=stream_cls)
            raise budget._close("unapproved_transport", "OpenAI operation lacks an admitted resource context")
        with budget.lock:
            if budget.closed:
                raise budget.stop_reason
            if stream or options.get_max_retries(client.max_retries) != 0:
                raise budget._close("unapproved_transport", "Streaming and SDK retries are not admitted")
            built = client._build_request(options)
            if built.method != "POST" or str(built.url) != "https://api.openai.com/v1/responses":
                raise budget._close("unapproved_transport", "Only the official Responses endpoint is admitted")
            try:
                body = json.loads(built.content)
                params = openai_request_parameters(budget.policy, body)
                if authorize_request(deepcopy(body)) is not True:
                    raise BudgetStop("unapproved_runtime_request", "Request is outside the approved runtime phase")
            except Exception as error:
                code = error.code if isinstance(error, BudgetStop) else "unapproved_runtime_request"
                raise budget._close(code, "OpenAI runtime request failed local admission") from error
            redirects = client._client.follow_redirects
            client._client.follow_redirects = False
            try:
                response = budget.dispatch(**params, usage=openai_usage,
                    invoke=lambda: original_request(client, cast_to, options, stream=False, stream_cls=stream_cls))
            finally:
                client._client.follow_redirects = redirects
            if budget.closed:
                raise budget.stop_reason
            return response

    async def blocked_async(*args, **kwargs):
        raise budget._close("unapproved_transport", "Asynchronous requests are not admitted")

    with patch.object(Responses, "create", create), patch.object(SyncAPIClient, "request", request), \
         patch.object(AsyncResponses, "create", blocked_async), patch.object(AsyncAPIClient, "request", blocked_async):
        yield budget
