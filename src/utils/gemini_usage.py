"""LangChain callback adapter for Gemini usage accounting."""

from __future__ import annotations

import threading
from typing import Any, Dict, Mapping

from langchain_core.callbacks import BaseCallbackHandler

from src.utils.gemini_usage_counts import (
    _as_mapping,
    add_gemini_usage_counts,
    estimate_gemini_cost_usd,
    extract_gemini_usage_counts,
    has_gemini_usage_counts,
    zero_gemini_usage_counts,
)


class GeminiUsageCallbackHandler(BaseCallbackHandler):
    """Thread-local LangChain callback that accumulates Gemini token usage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._local = threading.local()
        self._global_usage = zero_gemini_usage_counts()
        self._global_api_calls = 0
        self._global_usage_by_phase: Dict[str, Dict[str, int]] = {}
        self._global_api_calls_by_phase: Dict[str, int] = {}

    def _local_usage(self) -> Dict[str, int]:
        usage = getattr(self._local, "usage", None)
        if usage is None:
            usage = zero_gemini_usage_counts()
            self._local.usage = usage
        return usage

    def reset_current_thread(self) -> None:
        self._local.usage = zero_gemini_usage_counts()
        self._local.api_calls = 0
        self._local.current_phase = "default"
        self._local.usage_by_phase = {}
        self._local.api_calls_by_phase = {}

    def snapshot_current_thread(self) -> Dict[str, int]:
        usage = dict(self._local_usage())
        usage["api_calls"] = int(getattr(self._local, "api_calls", 0) or 0)
        return usage

    def set_current_phase(self, phase: str) -> None:
        clean_phase = str(phase or "").strip() or "default"
        self._local.current_phase = clean_phase

    def _current_phase(self) -> str:
        return str(getattr(self._local, "current_phase", "default") or "default")

    def _local_usage_by_phase(self) -> Dict[str, Dict[str, int]]:
        usage_by_phase = getattr(self._local, "usage_by_phase", None)
        if not isinstance(usage_by_phase, dict):
            usage_by_phase = {}
            self._local.usage_by_phase = usage_by_phase
        return usage_by_phase

    def _local_api_calls_by_phase(self) -> Dict[str, int]:
        api_calls_by_phase = getattr(self._local, "api_calls_by_phase", None)
        if not isinstance(api_calls_by_phase, dict):
            api_calls_by_phase = {}
            self._local.api_calls_by_phase = api_calls_by_phase
        return api_calls_by_phase

    def snapshot_current_thread_by_phase(self) -> Dict[str, Dict[str, int]]:
        usage_by_phase = self._local_usage_by_phase()
        api_calls_by_phase = self._local_api_calls_by_phase()
        snapshot: Dict[str, Dict[str, int]] = {}
        for phase in sorted(set(usage_by_phase) | set(api_calls_by_phase)):
            usage = dict(usage_by_phase.get(phase) or zero_gemini_usage_counts())
            usage["api_calls"] = int(api_calls_by_phase.get(phase, 0) or 0)
            snapshot[phase] = usage
        return snapshot

    def reset_global(self) -> None:
        with self._lock:
            self._global_usage = zero_gemini_usage_counts()
            self._global_api_calls = 0
            self._global_usage_by_phase = {}
            self._global_api_calls_by_phase = {}

    def snapshot_global(self) -> Dict[str, int]:
        with self._lock:
            usage = dict(self._global_usage)
            usage["api_calls"] = int(self._global_api_calls)
        return usage

    def snapshot_global_by_phase(self) -> Dict[str, Dict[str, int]]:
        with self._lock:
            phases = sorted(set(self._global_usage_by_phase) | set(self._global_api_calls_by_phase))
            snapshot: Dict[str, Dict[str, int]] = {}
            for phase in phases:
                usage = dict(self._global_usage_by_phase.get(phase) or zero_gemini_usage_counts())
                usage["api_calls"] = int(self._global_api_calls_by_phase.get(phase, 0) or 0)
                snapshot[phase] = usage
        return snapshot

    def _record_usage(self, usage: Mapping[str, Any]) -> None:
        add_gemini_usage_counts(self._local_usage(), usage)
        self._local.api_calls = int(getattr(self._local, "api_calls", 0) or 0) + 1
        phase = self._current_phase()
        phase_usage = self._local_usage_by_phase().setdefault(phase, zero_gemini_usage_counts())
        add_gemini_usage_counts(phase_usage, usage)
        phase_api_calls = self._local_api_calls_by_phase()
        phase_api_calls[phase] = int(phase_api_calls.get(phase, 0) or 0) + 1
        with self._lock:
            add_gemini_usage_counts(self._global_usage, usage)
            self._global_api_calls += 1
            global_phase_usage = self._global_usage_by_phase.setdefault(phase, zero_gemini_usage_counts())
            add_gemini_usage_counts(global_phase_usage, usage)
            self._global_api_calls_by_phase[phase] = int(self._global_api_calls_by_phase.get(phase, 0) or 0) + 1

    def _usage_from_llm_result(self, response: Any) -> Dict[str, int]:
        llm_output = _as_mapping(getattr(response, "llm_output", None))
        for candidate in (
            llm_output,
            _as_mapping(llm_output.get("token_usage")),
            _as_mapping(llm_output.get("usage_metadata")),
            _as_mapping(llm_output.get("usageMetadata")),
        ):
            usage = extract_gemini_usage_counts(candidate)
            if has_gemini_usage_counts(usage):
                return usage

        for generation_group in getattr(response, "generations", []) or []:
            for generation in generation_group or []:
                message = getattr(generation, "message", None)
                usage = extract_gemini_usage_counts(message or generation)
                if has_gemini_usage_counts(usage):
                    return usage
        return zero_gemini_usage_counts()

    def on_llm_end(self, response: Any, **_: Any) -> None:
        self._record_usage(self._usage_from_llm_result(response))
