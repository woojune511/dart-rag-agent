"""Explicit experiment-only request admission; never installed by runtime defaults.

Legacy preflight/dispatch retain their serialized-request reservation calculation.
Server counting requires an explicit policy, call limit and separate allowance.
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
from src.utils.request_diagnostics import diagnostics_enabled, record_diagnostic


class BudgetStop(ProviderAdmissionError):
    pass


def json_bytes(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      default=lambda obj: obj.model_dump(mode="json", exclude_none=True)).encode("utf-8")


def _request_observation(kind, request):
    """SDK-call JSON, not wire bytes or token counts; never retain HTTP options.

    Component sizes are separate serializations, not an additive byte breakdown.
    Only source/schema fields may be retained, not arbitrary SDK configuration.
    """
    if kind == "openai_response":
        fields = {key: request[key] for key in ("input", "instructions", "text") if key in request}
        encoded = {key: json_bytes(value) for key, value in fields.items()}
        return {"representation": "openai_responses_body_json", "component_sizes_additive": False,
                "components_json": {key: value.decode("utf-8") for key, value in encoded.items()},
                "component_bytes": {key: len(value) for key, value in encoded.items()}}
    if kind == "google" and "generationConfig" in request:
        config = request["generationConfig"]
        fields = {key: request[key] for key in ("contents", "systemInstruction") if key in request}
        fields.update({key: config[key] for key in ("responseJsonSchema", "responseSchema") if key in config})
        encoded = {key: json_bytes(value) for key, value in fields.items()}
        return {"representation": "google_generate_content_body_json", "component_sizes_additive": False,
                "components_json": {key: value.decode("utf-8") for key, value in encoded.items()},
                "component_bytes": {key: len(value) for key, value in encoded.items()}}
    config = request.get("config")
    config_values = (config.model_dump(mode="json", exclude_none=True)
                     if config is not None and not isinstance(config, dict) else config or {})
    fields = ({"contents": request.get("contents"), **{
        key: config_values[key] for key in (
            "system_instruction", "response_json_schema", "response_schema",
        ) if key in config_values
    }} if kind == "google" else {"input": request.get("input")})
    encoded = {key: json_bytes(value) for key, value in fields.items()}
    return {"representation": "sdk_call_json", "component_sizes_additive": False,
            "components_json": {key: value.decode("utf-8") for key, value in encoded.items()},
            "component_bytes": {key: len(value) for key, value in encoded.items()},
            "config_bytes": len(json_bytes(config)) if config is not None else 0}


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
        mode = self.policy.get("google_input_counting")
        if mode not in (None, "server_count_tokens_v1"):
            raise ValueError("unsupported google_input_counting policy")
        self.server_counting = mode == "server_count_tokens_v1"
        if self.server_counting:
            limit = self.policy.get("max_google_count_calls")
            allowance = self.policy.get("google_count_allowance_usd_per_call")
            if type(limit) is not int or limit < 0:
                raise ValueError("server counting requires an explicit non-negative call limit")
            if (type(allowance) not in (int, float) or not math.isfinite(allowance) or allowance <= 0):
                raise ValueError("server counting requires an explicit positive finite count allowance")
        self.count_allowance = 0.0
        self.count_records = []
        self.blocked_counts = []

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
        limits = {"google": "max_google_calls", "openai_embedding": "max_openai_embedding_calls",
                  "openai_response": "max_openai_response_calls"}
        if kind not in limits:
            raise ValueError("unsupported provider request kind")
        if limits[kind] not in self.policy:
            raise ValueError("provider request kind is absent from the admission policy")
        if any(type(value) is not int or value < 0 for value in (input_bound, output_bound)):
            raise ValueError("token reservations must be non-negative integers")
        reserve = self._cost(model, input_bound, output_bound)
        with self.lock:
            limit = self.policy[limits[kind]]
            total = self.charged + self.pending + self.count_allowance + reserve
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
        with self.lock:
            if self.stop_reason is None:
                self.stop_reason = BudgetStop(code, message)
            return self.stop_reason

    def dispatch(self, *, kind, model, request, input_bound, output_bound, invoke, usage, input_measurement=None):
        with self.lock:
            quote = self.preflight(kind=kind, model=model, request=request,
                                   input_bound=input_bound, output_bound=output_bound)
            if input_measurement is not None:
                quote.update(input_reservation_method="server_count_tokens_v1",
                             token_count_request_sha256=input_measurement["request_sha256"],
                             token_count_index=input_measurement["index"])
            if diagnostics_enabled():
                record_diagnostic("provider_request", {**quote, **_request_observation(kind, request)})
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
                record_diagnostic("provider_outcome", row)
            raise stopped from exc
        with self.lock:
            self.pending -= reserve
            cost = self._cost(model, actual_input, actual_output)
            self.charged += cost
            row.update(status="completed", input_tokens=actual_input, output_tokens=actual_output, estimated_usd=cost)
            if actual_input > input_bound or actual_output > output_bound:
                row["reservation_exceeded"] = True
                self._close("provider_usage_exceeded_reservation", "observed usage exceeds the reserved bound")
            record_diagnostic("provider_outcome", row)
        return response

    def count_google_input(self, *, model, generation_request, count_request, output_bound, invoke):
        """One count attempt, with an allowance rather than invented billed usage.

        Check known generation denial before counting; check the full generation
        reservation again after counting. Count failure never releases the allowance.
        """
        if not self.server_counting:
            raise ValueError("server counting is not enabled")
        with self.lock:
            quote = self.preflight(kind="google", model=model, request=generation_request,
                                   input_bound=0, output_bound=output_bound)
            allowance = self.policy["google_count_allowance_usd_per_call"]
            total = quote["total_with_reservation_usd"] + allowance
            code = (quote["blocked_code"] or
                    ("provider_count_call_limit_reached" if len(self.count_records) >= self.policy["max_google_count_calls"] else
                     "budget_reservation_exceeded" if total > self.policy["cap_usd"] else ""))
            row = {"model": model, "index": len(self.count_records),
                   "request_sha256": hashlib.sha256(json_bytes(count_request)).hexdigest(),
                   "request_bytes": len(json_bytes(count_request)),
                   "generation_request_sha256": quote["request_sha256"],
                   "allowance_usd": allowance, "allowance_is_not_observed_billing": True,
                   "minimum_total_with_generation_usd": total,
                   "allowed": not code, "blocked_code": code}
            record_diagnostic("provider_token_count_request", row)
            if code:
                self.blocked_counts.append(row)
                raise self._close(code, "token count denied before provider transmission")
            self.count_allowance += allowance
            row["status"] = "started"
            self.count_records.append(row)
        try:
            total_tokens = invoke()
            if type(total_tokens) is not int or total_tokens <= 0:
                raise ValueError("provider token count unavailable")
        except Exception as exc:
            with self.lock:
                safe_error = provider_error_projection(exc)
                row.update(status="failed", error_type=type(exc).__name__,
                           http_status=safe_error["http_status"], provider_status=safe_error["provider_status"])
                stopped = self._close("provider_token_count_failed", "token count failed; no generation or fallback")
                record_diagnostic("provider_token_count_outcome", row)
            raise stopped from exc
        with self.lock:
            row.update(status="completed", total_tokens=total_tokens)
            record_diagnostic("provider_token_count_outcome", row)
            return deepcopy(row)

    def snapshot(self):
        with self.lock:
            snapshot = {"estimated_cost_usd_without_cache_discount": self.charged,
                "outstanding_reservation_usd": self.pending, "closed": self.closed,
                "stop_reason": {"code": self.stop_reason.code, "message": str(self.stop_reason)} if self.closed else None,
                "requests": self.records, "blocked_requests": self.blocked_requests, "billing_observed": False}
            if self.server_counting:
                snapshot.update(google_input_counting="server_count_tokens_v1",
                    token_count_allowance_usd=self.count_allowance,
                    token_count_allowance_is_not_observed_billing=True,
                    total_with_allowance_and_pending_usd=self.charged + self.pending + self.count_allowance,
                    token_count_requests=self.count_records, blocked_token_count_requests=self.blocked_counts)
            return deepcopy(snapshot)


def _google_request(policy, *, model, contents, config):
    if model not in {"gemini-2.5-flash", "gemini-2.5-pro"} or model not in policy["rates"]:
        raise BudgetStop("unapproved_model", "model is absent from the admission policy")
    if not (config is not None and config.thinking_config is not None and config.http_options is not None
            and config.http_options.retry_options is not None
            and config.max_output_tokens == 4096 and config.thinking_config.thinking_budget == 1024
            and not config.thinking_config.include_thoughts
            and config.http_options.retry_options.attempts in (0, 1)
            and not config.tools and not config.cached_content):
        raise BudgetStop("unapproved_request_config", "generation settings differ from the fixed experiment contract")
    config = config.model_copy(deep=True)
    config.http_options.timeout = 90000
    return {"contents": deepcopy(contents), "config": config}


def google_request_parameters(policy, *, model, contents, config):
    """Legacy no-call estimate; a server count cannot be fabricated in preflight."""
    if policy.get("google_input_counting") is not None:
        raise ValueError("server-count reservations require the exact SDK body and a live count")
    request = _google_request(policy, model=model, contents=contents, config=config)
    return {"kind": "google", "model": model, "request": request,
            "input_bound": len(json_bytes(request)) + policy["google_input_overhead_tokens"], "output_bound": 5120}


@contextmanager
def guarded_providers(policy, canonical_queries):
    """Opt-in SDK boundary for an explicitly approved single experiment."""
    from google.genai.models import Models, AsyncModels
    from openai.resources.embeddings import Embeddings, AsyncEmbeddings
    from src.utils.embedding_usage import TrackingEmbeddings

    budget = ProviderBudget(policy)
    policy = budget.policy
    google_generate, openai_create = Models.generate_content, Embeddings.create
    tracked_documents = TrackingEmbeddings.embed_documents

    def google(client, *, model, contents, config=None):
        if budget.server_counting:
            if budget.closed:
                raise budget.stop_reason
            try:
                request = _google_request(policy, model=model, contents=contents, config=config)
            except BudgetStop as exc:
                raise budget._close(exc.code, str(exc)) from exc
            return counted_google.generate(client, google_generate, model=model, request=request)
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
        if budget.server_counting:
            from src.ops.google_server_token_count import ServerCountedGoogle
            counted_google = stack.enter_context(ServerCountedGoogle(budget))
        stack.enter_context(patch.object(Models, "generate_content", google))
        stack.enter_context(patch.object(Embeddings, "create", openai))
        stack.enter_context(patch.object(TrackingEmbeddings, "embed_documents", documents))
        for cls, name in ((Models, "generate_content_stream"), (AsyncModels, "generate_content"),
                          (AsyncModels, "generate_content_stream"), (AsyncEmbeddings, "create")):
            stack.enter_context(patch.object(cls, name, side_effect=BudgetStop("unapproved_transport", "stream/async path is not admitted")))
        yield budget
