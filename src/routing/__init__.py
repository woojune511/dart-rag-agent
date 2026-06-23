"""Compatibility exports for query routing helpers."""

__all__ = [
    "FORMAT_PREFERENCE_BY_INTENT",
    "ROUTER_INTENTS",
    "FormatPreference",
    "QueryIntent",
    "QueryRouteResult",
    "QueryRouter",
    "QueryRoutingDecision",
    "cosine_similarity",
    "default_canonical_queries_path",
    "default_format_preference",
    "load_canonical_routing_examples",
]

_EXPORT_MODULES = {
    "FORMAT_PREFERENCE_BY_INTENT": "src.routing.format_policy",
    "ROUTER_INTENTS": "src.routing.format_policy",
    "default_format_preference": "src.routing.format_policy",
    "FormatPreference": "src.routing.types",
    "QueryIntent": "src.routing.types",
    "QueryRouteResult": "src.routing.types",
    "QueryRoutingDecision": "src.routing.types",
    "QueryRouter": "src.routing.query_router",
    "cosine_similarity": "src.routing.query_router",
    "default_canonical_queries_path": "src.routing.query_router",
    "load_canonical_routing_examples": "src.routing.query_router",
}


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
