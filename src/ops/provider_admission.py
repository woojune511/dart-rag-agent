"""Explicit experiment-only request admission; never installed by runtime defaults.

Preflight and dispatch share the same serialized-request reservation calculation.
Frozen historical admission scripts are not imported or rewritten.
"""

from contextlib import ExitStack, contextmanager
from copy import deepcopy
import hashlib
import json
import math
import threading
from unittest.mock import patch

from src.utils.provider_errors import ProviderAdmissionError, provider_error_projection


class BudgetStop(ProviderAdmissionError):
    pass


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      default=lambda obj: obj.model_dump(mode="json", exclude_none=True)).encode("utf-8")


class ProviderBudget:
    def __init__(self, policy):
        self.policy = deepcopy(policy)
        if not math.isfinite(self.policy["cap_usd"]) or self.policy["cap_usd"] < 0:
            raise ValueError("cap_usd must be finite and non-negative")
        self.charged = 0.0
        self.pending = 0.0
        self.records = []
        self.blocked_requests = []
        self.stop_reason = None
        self.lock = threading.RLock()

    @property
    def closed(self):
        return self.stop_reason is not None

    def _cost(self, model, input_tokens, output_tokens):
        rates = self.policy["rates"][model]
        high = input_tokens > 200000
        in_rate = rates.get("long_input", rates["input"]) if high else rates["input"]
        out_rate = rates.get("long_output", rates["output"]) if high else rates["output"]
        return (input_tokens * in_rate + output_tokens * out_rate) / 1_000_000

    def preflight(self, *, kind, model, request, input_bound, output_bound):
        """Quote the real request without consuming budget, calls or approval."""
        if kind not in {"google", "openai_embedding"}:
            raise ValueError("unsupported provider request kind")
        if any(type(value) is not int or value < 0 for value in (input_bound, output_bound)):
            raise ValueError("token reservations must be non-negative integers")
        reserve = self._cost(model, input_bound, output_bound)
        with self.lock:
            limit = self.policy["max_google_calls" if kind == "google" else "max_openai_embedding_calls"]
            total = self.charged + self.pending + reserve
            code = (self.stop_reason.code if self.closed else
                    "provider_call_limit_reached" if sum(row["kind"] == kind for row in self.records) >= limit else
                    "budget_reservation_exceeded" if total > self.policy["cap_usd"] else "")
            return {"kind": kind, "model": model, "request_sha256": hashlib.sha256(json_bytes(request)).hexdigest(),
                    "request_bytes": len(json_bytes(request)), "input_token_reservation": input_bound,
                    "output_token_reservation": output_bound, "reserved_usd": reserve,
                    "estimated_prior_cost_usd": self.charged, "outstanding_reservation_usd": self.pending,
                    "total_with_reservation_usd": total, "cap_usd": self.policy["cap_usd"],
                    "allowed": not code, "blocked_code": code}

    def _close(self, code, message):
        if self.stop_reason is None:
            self.stop_reason = BudgetStop(code, message)
        return self.stop_reason

    def dispatch(self, *, kind, model, request, input_bound, output_bound, invoke, usage):
        with self.lock:
            quote = self.preflight(kind=kind, model=model, request=request,
                                   input_bound=input_bound, output_bound=output_bound)
            if not quote["allowed"]:
                self.blocked_requests.append(quote)
                raise self._close(quote["blocked_code"], "request admission denied before provider transmission")
            reserve = quote["reserved_usd"]
            self.pending += reserve
            row = {**quote, "status": "started"}
            self.records.append(row)
        try:
            response = invoke()
            actual_input, actual_output = usage(response)
            if (not math.isfinite(actual_input) or not math.isfinite(actual_output)
                    or actual_input <= 0 or actual_output < 0):
                raise ValueError("provider usage unavailable")
        except Exception as exc:
            with self.lock:
                self.pending -= reserve
                self.charged += reserve
                safe_error = provider_error_projection(exc)
                row.update(status="failed", error_type=type(exc).__name__, estimated_usd=reserve, usage_unknown=True,
                           http_status=safe_error["http_status"], provider_status=safe_error["provider_status"])
                stopped = self._close("provider_request_failed", "failed or unaccounted request; reservation retained")
            raise stopped from exc
        with self.lock:
            self.pending -= reserve
            cost = self._cost(model, actual_input, actual_output)
            self.charged += cost
            row.update(status="completed", input_tokens=actual_input, output_tokens=actual_output, estimated_usd=cost)
            if actual_input > input_bound or actual_output > output_bound:
                row["reservation_exceeded"] = True
                self._close("provider_usage_exceeded_reservation", "observed usage exceeds the reserved bound")
        return response

    def snapshot(self):
        with self.lock:
            return deepcopy({"estimated_cost_usd_without_cache_discount": self.charged,
                "outstanding_reservation_usd": self.pending, "closed": self.closed,
                "stop_reason": {"code": self.stop_reason.code, "message": str(self.stop_reason)} if self.closed else None,
                "requests": self.records, "blocked_requests": self.blocked_requests, "billing_observed": False})


def google_request_parameters(policy, *, model, contents, config):
    """Identical request schema/framing for offline preflight and live dispatch."""
    if model not in {"gemini-2.5-flash", "gemini-2.5-pro"} or model not in policy["rates"]:
        raise BudgetStop("unapproved_model", "model is absent from the admission policy")
    if not (config.max_output_tokens == 4096 and config.thinking_config.thinking_budget == 1024
            and not config.thinking_config.include_thoughts
            and config.http_options.retry_options.attempts in (0, 1)
            and not config.tools and not config.cached_content):
        raise BudgetStop("unapproved_request_config", "generation settings differ from the fixed experiment contract")
    config = config.model_copy(deep=True)
    config.http_options.timeout = 90000
    request = {"contents": contents, "config": config}
    return {"kind": "google", "model": model, "request": request,
            "input_bound": len(json_bytes(request)) + policy["google_input_overhead_tokens"], "output_bound": 5120}


@contextmanager
def guarded_providers(policy, canonical_queries):
    """Opt-in SDK boundary for an explicitly approved single experiment."""
    from google.genai.models import Models, AsyncModels
    from openai.resources.embeddings import Embeddings, AsyncEmbeddings
    from src.utils.embedding_usage import TrackingEmbeddings

    budget = ProviderBudget(policy)
    google_generate, openai_create = Models.generate_content, Embeddings.create
    tracked_documents = TrackingEmbeddings.embed_documents

    def google(client, *, model, contents, config=None):
        params = google_request_parameters(policy, model=model, contents=contents, config=config)

        def usage(response):
            item = response.usage_metadata
            return int(item.prompt_token_count or 0), int(item.candidates_token_count or 0) + int(item.thoughts_token_count or 0)

        return budget.dispatch(**params,
            invoke=lambda: google_generate(client, model=model, contents=contents, config=params["request"]["config"]), usage=usage)

    def openai(client, *, input, model, **kwargs):
        if (model != "text-embedding-3-large" or model not in policy["rates"]
                or client._client.base_url.host != "api.openai.com"):
            raise BudgetStop("unapproved_embedding_target", "embedding model/endpoint is not admitted")
        client._client.max_retries = 0
        values = [input] if isinstance(input, str) else input
        if values and isinstance(values[0], int):
            values = [values]
        count = sum(len(value.encode("utf-8")) if isinstance(value, str) else len(value) for value in values)
        return budget.dispatch(kind="openai_embedding", model=model, request={"input": input, "model": model},
            input_bound=count + 128, output_bound=0,
            invoke=lambda: openai_create(client, input=input, model=model, **{**kwargs, "timeout": 60}),
            usage=lambda response: (int(response.usage.prompt_tokens), 0))

    def documents(embeddings, texts, *args, **kwargs):
        if list(texts) != list(canonical_queries):
            raise BudgetStop("document_embedding_forbidden", "only the fixed canonical routing batch is admitted")
        return tracked_documents(embeddings, texts, *args, **kwargs)

    with ExitStack() as stack:
        stack.enter_context(patch.object(Models, "generate_content", google))
        stack.enter_context(patch.object(Embeddings, "create", openai))
        stack.enter_context(patch.object(TrackingEmbeddings, "embed_documents", documents))
        for cls, name in ((Models, "generate_content_stream"), (AsyncModels, "generate_content"),
                          (AsyncModels, "generate_content_stream"), (AsyncEmbeddings, "create")):
            stack.enter_context(patch.object(cls, name, side_effect=BudgetStop("unapproved_transport", "stream/async path is not admitted")))
        yield budget
