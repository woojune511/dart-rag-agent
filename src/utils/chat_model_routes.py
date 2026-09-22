"""Shared model construction; no question planning or answer execution."""

import os
from typing import Any, Dict


class ChatModelRoutes:
    def _build_llm_routes(self) -> Dict[str, Any]:
        route_config = self.routing_config.get("llm_routes")
        routes = dict(route_config) if isinstance(route_config, dict) else {}
        default_spec = routes.get("default") if isinstance(routes.get("default"), dict) else {}
        built: Dict[str, Any] = {
            "default": self._create_chat_model(dict(default_spec), phase="default"),
        }
        for phase, spec in routes.items():
            if phase != "default" and isinstance(spec, dict):
                built[str(phase)] = self._create_chat_model(dict(spec), phase=str(phase))
        return built

    def _create_chat_model(self, spec: Dict[str, Any], *, phase: str) -> Any:
        provider = str(spec.get("provider") or "google").strip().lower()
        model = str(spec.get("model") or spec.get("model_name") or "gemini-2.5-flash").strip()
        temperature = float(spec.get("temperature", 0) or 0)
        if provider in {"google", "gemini", "google_genai"}:
            api_key = str(spec.get("api_key") or os.environ.get("GOOGLE_API_KEY") or "").strip()
            if not api_key:
                raise ValueError(f"GOOGLE_API_KEY environment variable is required for LLM route '{phase}'.")
            from langchain_google_genai import ChatGoogleGenerativeAI

            generation_options = {
                target: spec[source]
                for source, target in (
                    ("max_output_tokens", "max_tokens"),
                    ("thinking_budget", "thinking_budget"),
                    ("provider_client_retries", "retries"),
                    ("include_thoughts", "include_thoughts"),
                )
                if source in spec
            }
            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                google_api_key=api_key,
                callbacks=[self.llm_usage_callback],
                **generation_options,
            )
        if provider in {"openai", "openrouter"}:
            if provider == "openai" and not (spec.get("model") or spec.get("model_name")):
                raise ValueError(f"An explicit model is required for LLM route '{phase}'.")
            if provider == "openai" and any(key in spec for key in ("thinking_budget", "include_thoughts")):
                raise ValueError("Google generation options cannot configure an OpenAI route.")
            key_name = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
            api_key = str(spec.get("api_key") or os.environ.get(key_name) or "").strip()
            if not api_key:
                raise ValueError(f"{key_name} environment variable is required for LLM route '{phase}'.")
            base_url = spec.get("base_url")
            if provider == "openrouter" and not base_url:
                base_url = os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
            from langchain_openai import ChatOpenAI

            if provider == "openrouter":
                return ChatOpenAI(model=model, temperature=temperature, api_key=api_key,
                                  base_url=str(base_url) if base_url else None)
            from src.utils.openai_structured import StrictOpenAIChatModel

            generation_options = {
                target: spec[source]
                for source, target in (
                    ("max_output_tokens", "max_completion_tokens"),
                    ("provider_client_retries", "max_retries"),
                    ("reasoning_effort", "reasoning_effort"),
                    ("use_responses_api", "use_responses_api"),
                    ("store", "store"),
                    ("service_tier", "service_tier"),
                    ("timeout_seconds", "timeout"),
                )
                if source in spec
            }
            return StrictOpenAIChatModel(
                model=model,
                temperature=None if spec.get("temperature", 0) is None else temperature,
                api_key=api_key,
                base_url=str(base_url) if base_url else None,
                callbacks=[self.llm_usage_callback],
                **generation_options,
            )
        raise ValueError(f"Unsupported LLM provider for route '{phase}': {provider}")

    def _llm_for_phase(self, phase: str) -> Any:
        usage_callback = getattr(self, "llm_usage_callback", None)
        if usage_callback is not None:
            set_phase = getattr(usage_callback, "set_current_phase", None)
            if callable(set_phase):
                set_phase(phase)
        routes = getattr(self, "llm_routes", None)
        if isinstance(routes, dict) and routes:
            return routes.get(phase) or routes["default"]
        llm = getattr(self, "llm", None)
        if llm is None:
            raise ValueError(f"LLM route '{phase}' is not initialized.")
        return llm
