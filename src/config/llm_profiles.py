"""Reviewed application LLM routes, independent of benchmark profiles."""

from copy import deepcopy
from typing import Any


_APP_LLM_PROFILES: dict[str, dict[str, Any]] = {
    "google": {},
    "openai_compiler": {
        "llm_routes": {
            "program_compilation": {
                "provider": "openai",
                "model": "gpt-6-astra",
                "temperature": None,
                "max_output_tokens": 5120,
                "reasoning_effort": "medium",
                "provider_client_retries": 0,
                "use_responses_api": True,
                "store": False,
                "service_tier": "default",
                "timeout_seconds": 90,
            },
        },
    },
}

# Keep the reviewed compiler route identical in both application profiles.
_APP_LLM_PROFILES["openai"] = {
    "llm_routes": {
        "default": {
            "provider": "openai",
            "model": "gpt-5.6-terra",
            "temperature": None,
            "max_output_tokens": 8192,
            "reasoning_effort": "low",
            "provider_client_retries": 0,
            "use_responses_api": True,
            "store": False,
            "service_tier": "default",
            "timeout_seconds": 90,
        },
        "program_compilation": deepcopy(
            _APP_LLM_PROFILES["openai_compiler"]["llm_routes"]["program_compilation"]
        ),
        "context_generation": {
            "provider": "openai",
            "model": "gpt-5.6-luna",
            "temperature": None,
            "max_output_tokens": 512,
            "reasoning_effort": "none",
            "provider_client_retries": 0,
            "use_responses_api": True,
            "store": False,
            "service_tier": "default",
            "timeout_seconds": 90,
        },
    },
}


def app_llm_routing_config(profile: str = "") -> dict[str, Any]:
    """Return owned configuration; absent selection preserves runtime defaults."""

    name = profile.strip() or "google"
    if name not in _APP_LLM_PROFILES:
        raise ValueError("DART_LLM_PROFILE must be 'google', 'openai_compiler' or 'openai'.")
    return deepcopy(_APP_LLM_PROFILES[name])
