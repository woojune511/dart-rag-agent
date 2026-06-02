"""Utilities for normalizing Gemini usage metadata and estimating cost."""

from __future__ import annotations

import threading
from typing import Any, Dict, Mapping

from langchain_core.callbacks import BaseCallbackHandler


def _as_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _lookup_int(*sources: Mapping[str, Any], keys: tuple[str, ...]) -> int:
    for source in sources:
        for key in keys:
            value = source.get(key)
            if value is None:
                continue
            try:
                return int(value or 0)
            except (TypeError, ValueError):
                continue
    return 0


def extract_gemini_usage_counts(response: Any) -> Dict[str, int]:
    """Return normalized token counts from Gemini/LangChain response metadata."""
    response_mapping = _as_mapping(response)
    usage = _as_mapping(response_mapping.get("usage_metadata") or response_mapping.get("usageMetadata"))
    if not usage:
        usage = _as_mapping(getattr(response, "usage_metadata", None))
    if not usage and response_mapping:
        usage = response_mapping

    response_metadata = _as_mapping(response_mapping.get("response_metadata"))
    if not response_metadata:
        response_metadata = _as_mapping(getattr(response, "response_metadata", None))
    token_usage = _as_mapping(response_metadata.get("token_usage"))
    raw_usage = _as_mapping(response_metadata.get("usageMetadata"))

    prompt_tokens = _lookup_int(
        usage,
        token_usage,
        raw_usage,
        keys=("input_tokens", "prompt_token_count", "promptTokenCount"),
    )
    output_tokens = _lookup_int(
        usage,
        token_usage,
        raw_usage,
        keys=("output_tokens", "candidates_token_count", "candidatesTokenCount"),
    )
    thoughts_tokens = _lookup_int(
        usage,
        token_usage,
        raw_usage,
        keys=("thoughts_tokens", "thoughts_token_count", "thoughtsTokenCount"),
    )
    cached_tokens = _lookup_int(
        usage,
        token_usage,
        raw_usage,
        keys=("cached_tokens", "cached_content_token_count", "cachedContentTokenCount"),
    )
    tool_use_prompt_tokens = _lookup_int(
        usage,
        token_usage,
        raw_usage,
        keys=("tool_use_prompt_tokens", "tool_use_prompt_token_count", "toolUsePromptTokenCount"),
    )
    total_tokens = _lookup_int(
        usage,
        token_usage,
        raw_usage,
        keys=("total_tokens", "total_token_count", "totalTokenCount"),
    )
    if total_tokens <= 0:
        total_tokens = prompt_tokens + output_tokens + thoughts_tokens + tool_use_prompt_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "output_tokens": output_tokens,
        "thoughts_tokens": thoughts_tokens,
        "cached_tokens": cached_tokens,
        "tool_use_prompt_tokens": tool_use_prompt_tokens,
        "total_tokens": total_tokens,
    }


def zero_gemini_usage_counts() -> Dict[str, int]:
    return {
        "prompt_tokens": 0,
        "output_tokens": 0,
        "thoughts_tokens": 0,
        "cached_tokens": 0,
        "tool_use_prompt_tokens": 0,
        "total_tokens": 0,
    }


def add_gemini_usage_counts(target: Dict[str, int], usage: Mapping[str, Any]) -> None:
    for key in zero_gemini_usage_counts():
        try:
            target[key] = int(target.get(key, 0) or 0) + int(usage.get(key, 0) or 0)
        except (TypeError, ValueError):
            target[key] = int(target.get(key, 0) or 0)


def estimate_gemini_cost_usd(usage: Mapping[str, Any], pricing: Mapping[str, Any] | None) -> float | None:
    """Estimate Gemini cost from normalized usage counts and per-million-token rates."""
    if not pricing:
        return None

    input_rate = float(pricing.get("input_per_million_tokens_usd", 0.0) or 0.0)
    output_rate = float(pricing.get("output_per_million_tokens_usd", 0.0) or 0.0)
    cached_rate = float(pricing.get("cached_input_per_million_tokens_usd", input_rate) or 0.0)
    thinking_rate = float(pricing.get("thinking_per_million_tokens_usd", output_rate) or 0.0)
    tool_input_rate = float(pricing.get("tool_input_per_million_tokens_usd", input_rate) or 0.0)

    if input_rate == output_rate == cached_rate == thinking_rate == tool_input_rate == 0.0:
        return None

    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    cached_tokens = int(usage.get("cached_tokens", 0) or 0)
    output_tokens = int(usage.get("output_tokens", 0) or 0)
    thoughts_tokens = int(usage.get("thoughts_tokens", 0) or 0)
    tool_use_prompt_tokens = int(usage.get("tool_use_prompt_tokens", 0) or 0)

    uncached_prompt_tokens = max(prompt_tokens - cached_tokens, 0)
    return (
        (uncached_prompt_tokens / 1_000_000.0) * input_rate
        + (cached_tokens / 1_000_000.0) * cached_rate
        + (output_tokens / 1_000_000.0) * output_rate
        + (thoughts_tokens / 1_000_000.0) * thinking_rate
        + (tool_use_prompt_tokens / 1_000_000.0) * tool_input_rate
    )


def has_gemini_usage_counts(usage: Mapping[str, Any]) -> bool:
    return any(int(usage.get(key, 0) or 0) > 0 for key in zero_gemini_usage_counts())


class GeminiUsageCallbackHandler(BaseCallbackHandler):
    """Thread-local LangChain callback that accumulates Gemini token usage."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._local = threading.local()
        self._global_usage = zero_gemini_usage_counts()
        self._global_api_calls = 0

    def _local_usage(self) -> Dict[str, int]:
        usage = getattr(self._local, "usage", None)
        if usage is None:
            usage = zero_gemini_usage_counts()
            self._local.usage = usage
        return usage

    def reset_current_thread(self) -> None:
        self._local.usage = zero_gemini_usage_counts()
        self._local.api_calls = 0

    def snapshot_current_thread(self) -> Dict[str, int]:
        usage = dict(self._local_usage())
        usage["api_calls"] = int(getattr(self._local, "api_calls", 0) or 0)
        return usage

    def reset_global(self) -> None:
        with self._lock:
            self._global_usage = zero_gemini_usage_counts()
            self._global_api_calls = 0

    def snapshot_global(self) -> Dict[str, int]:
        with self._lock:
            usage = dict(self._global_usage)
            usage["api_calls"] = int(self._global_api_calls)
        return usage

    def _record_usage(self, usage: Mapping[str, Any]) -> None:
        add_gemini_usage_counts(self._local_usage(), usage)
        self._local.api_calls = int(getattr(self._local, "api_calls", 0) or 0) + 1
        with self._lock:
            add_gemini_usage_counts(self._global_usage, usage)
            self._global_api_calls += 1

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
