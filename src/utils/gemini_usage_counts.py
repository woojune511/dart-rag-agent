"""Pure Gemini usage accounting helpers.

This module intentionally avoids LangChain imports so runtime and ops modules
can estimate usage/cost without paying callback-adapter import cost.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping


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
