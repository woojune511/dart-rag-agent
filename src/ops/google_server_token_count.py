"""Opt-in, text-only Developer API admission at the final google-genai body.

The private SDK seam is deliberately isolated and exercised with real SDK
serialization + a mocked HTTP transport. No schema conversion or local tokenizer.
"""

from contextlib import ExitStack
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import replace
import json
from unittest.mock import patch

from google.genai import errors
from google.genai._api_client import BaseApiClient, HttpResponse


def _fixed_fields(values, names, expected, *, optional=False):
    found = [values[name] for name in names if name in values]
    return (bool(found) or optional) and all(type(value) is type(expected) and value == expected for value in found)


def _text_only(content):
    return (isinstance(content, dict) and isinstance(content.get("parts"), list)
            and bool(content["parts"]) and all(isinstance(part, dict) and set(part) == {"text"}
                                               and isinstance(part["text"], str) for part in content["parts"]))


def _fixed_generation(body):
    config = body.get("generationConfig", {})
    if not isinstance(config, dict):
        return False
    thinking = config.get("thinkingConfig", {})
    if not isinstance(thinking, dict):
        return False
    return ("model" not in body and "generation_config" not in body
            and not body.get("tools") and not body.get("cachedContent") and not body.get("cached_content")
            and isinstance(body.get("contents"), list) and bool(body["contents"])
            and all(_text_only(content) for content in body["contents"])
            and ("systemInstruction" not in body or _text_only(body["systemInstruction"]))
            and _fixed_fields(config, ("maxOutputTokens", "max_output_tokens"), 4096)
            and _fixed_fields(config, ("candidateCount", "candidate_count"), 1, optional=True)
            and all(config.get(key, ["TEXT"]) == ["TEXT"] for key in ("responseModalities", "response_modalities"))
            and _fixed_fields(thinking, ("thinkingBudget", "thinking_budget"), 1024)
            and _fixed_fields(thinking, ("includeThoughts", "include_thoughts"), False, optional=True))


def _usage(response):
    item = response.json.get("usageMetadata", {})
    values = (item.get("promptTokenCount"), item.get("candidatesTokenCount", 0), item.get("thoughtsTokenCount", 0))
    if any(type(value) is not int or value < 0 for value in values) or not values[0]:
        raise ValueError("generation usage unavailable")
    return values[0], values[1] + values[2]


def _send_once(client, request):
    """Same JSON encoding as genai, but no SDK retry or HTTP redirect dispatch."""
    response = client._httpx_client.request(method=request.method, url=request.url,
        headers=request.headers, content=json.dumps(request.data), timeout=request.timeout, follow_redirects=False)
    errors.APIError.raise_for_response(response)
    response.raise_for_status()
    return HttpResponse(response.headers, [response.text])


class ServerCountedGoogle:
    """One counted, frozen body per synchronous model invocation; no SDK retry."""

    def __init__(self, budget):
        self.budget = budget
        self.active = ContextVar("server_counted_google_request", default=None)

    def generate(self, client, generate, *, model, request):
        state = {"client": client._api_client, "model": model, "dispatched": False}
        token = self.active.set(state)
        try:
            response = generate(client, model=model, **request)
            if not state["dispatched"]:
                raise self.budget._close("unapproved_transport", "SDK bypassed the counted request boundary")
            return response
        except Exception as exc:
            if exc is self.budget.stop_reason:
                raise
            raise self.budget._close("provider_request_failed", "SDK generation failed; no retry") from exc
        finally:
            self.active.reset(token)

    def __enter__(self):
        def request(client, http_request, http_options=None, stream=False):
            state = self.active.get()
            budget = self.budget
            if budget.closed:
                raise budget.stop_reason
            if (state is None or state["client"] is not client or state["dispatched"] or stream or client.vertexai):
                raise budget._close("unapproved_transport", "only one counted synchronous generation is admitted")
            model = state["model"]
            base = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:"
            if http_request.url != base + "generateContent" or http_request.method.lower() != "post":
                raise budget._close("unapproved_transport", "generation endpoint differs from the counted admission")
            # _build_request has already applied SDK conversion and HTTP extra_body.
            # Only the copied request proceeds; caller-owned contents/config cannot drift.
            frozen = deepcopy(http_request)
            if not isinstance(frozen.data, dict) or not _fixed_generation(frozen.data):
                raise budget._close("unapproved_request_config", "final generation body differs from the text experiment contract")
            state["dispatched"] = True
            count_body = {"generateContentRequest": {"model": f"models/{model}", **deepcopy(frozen.data)}}
            count_request = replace(frozen, url=base + "countTokens", data=count_body)
            measurement = budget.count_google_input(model=model, generation_request=frozen.data,
                count_request=count_body, output_bound=5120,
                invoke=lambda: _send_once(client, count_request).json.get("totalTokens"))
            response = budget.dispatch(kind="google", model=model, request=frozen.data,
                input_bound=measurement["total_tokens"], output_bound=5120, input_measurement=measurement,
                invoke=lambda: _send_once(client, frozen), usage=_usage)
            if budget.closed:
                raise budget.stop_reason
            return response

        async def async_request(*args, **kwargs):
            raise self.budget._close("unapproved_transport", "async requests are not admitted")

        # Intercept after _build_request and before the SDK retry wrapper. Count and
        # generation share auth only in memory, not in diagnostics or receipts.
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(BaseApiClient, "_request", request))
        self.stack.enter_context(patch.object(BaseApiClient, "_async_request", async_request))
        return self

    def __exit__(self, *exc):
        self.stack.close()
