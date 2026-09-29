"""Copied request observations, independent of graph writers and answer authority."""

from dataclasses import replace
from functools import wraps

from src.utils.provider_errors import provider_error_projection
from src.utils.request_diagnostics import (
    diagnostic_location, diagnostics_enabled, record_diagnostic, request_diagnostic_scope,
)


def _phase_projection(phase, value):
    if phase in {"routing", "requirements", "candidates"}:
        return value
    if phase == "retrieval":
        projected = {key: value[key] for key in (
            "retrieval_debug_trace", "retrieval_debug_trace_history",
        ) if key in value}
        for key in ("retrieved_docs", "seed_retrieved_docs"):
            projected[key] = []
            for item in value.get(key, []):
                doc = item[0] if isinstance(item, (tuple, list)) else item
                projected[key].append({
                    "page_content": doc.page_content, "metadata": doc.metadata,
                    "score": item[1] if isinstance(item, (tuple, list)) and len(item) > 1 else None,
                })
        return projected
    if phase == "compilation":
        # Actual parsed programs are retained at each attempt. The phase result
        # can contain a fabricated failure program with an SDK exception message.
        return {key: value[key] for key in (
            "semantic_program_retry_count",
        ) if key in value}
    # Finalized output already has public/review projections; do not duplicate it.
    return {"completed": True}


def observe_phase(phase):
    def decorate(method):
        @wraps(method)
        def observed(self, state):
            if not diagnostics_enabled():
                return method(self, state)
            with diagnostic_location(phase=phase):
                record_diagnostic("phase_started", {})
                update = method(self, state)
                record_diagnostic("phase_completed", _phase_projection(phase, update[phase]))
                return update
        return observed
    return decorate


def _interrupted_usage(agent):
    usage = {}
    callback, store = getattr(agent, "llm_usage_callback", None), getattr(agent, "vsm", None)
    for key, owner, method in (
        ("llm_usage", callback, "snapshot_current_thread"),
        ("llm_usage_by_phase", callback, "snapshot_current_thread_by_phase"),
        ("embedding_usage", store, "get_current_thread_embedding_usage_snapshot"),
    ):
        snapshot = getattr(owner, method, None)
        try:
            usage[key] = snapshot() if callable(snapshot) else None
        except Exception as error:
            # A telemetry failure cannot replace the original admission/runtime stop.
            usage[key] = {"observation_unavailable": type(error).__name__}
    return usage


def observe_financial_run(method):
    @wraps(method)
    def observed(self, query, **kwargs):
        with request_diagnostic_scope(bool(kwargs.get("include_debug_bundle"))) as recorder:
            if recorder is None:
                return method(self, query, **kwargs)
            record_diagnostic("run_started", {"query": query, "report_scope": kwargs.get("report_scope")})
            try:
                result = method(self, query, **kwargs)
            except Exception as error:
                record_diagnostic("usage_snapshot", _interrupted_usage(self))
                record_diagnostic("run_interrupted", provider_error_projection(error))
                raise
            debug = dict(result.debug_bundle or {})
            record_diagnostic("usage_snapshot", {key: debug.get(key) for key in (
                "llm_usage", "llm_usage_by_phase", "embedding_usage",
            )})
            record_diagnostic("run_completed", {})
            return replace(result, debug_bundle={**debug, "request_diagnostics": recorder.snapshot()})
    return observed
