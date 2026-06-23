"""Compatibility exports for MAS node factories.

New experimental MAS callers should import from ``src.experimental.mas.nodes``.
The concrete node implementations still live in this package until the
implementation move has explicit compatibility coverage.
"""

__all__ = [
    "build_financial_analyst_node",
    "make_run_analyst",
    "build_financial_orchestrator_merge_node",
    "build_financial_orchestrator_plan_node",
    "make_run_orchestrator_merge",
    "make_run_orchestrator_plan",
    "build_financial_researcher_node",
    "make_run_researcher",
]

_EXPORT_MODULES = {
    "build_financial_analyst_node": "src.agent.nodes.analyst_node",
    "make_run_analyst": "src.agent.nodes.analyst_node",
    "build_financial_orchestrator_merge_node": "src.agent.nodes.orchestrator_node",
    "build_financial_orchestrator_plan_node": "src.agent.nodes.orchestrator_node",
    "make_run_orchestrator_merge": "src.agent.nodes.orchestrator_node",
    "make_run_orchestrator_plan": "src.agent.nodes.orchestrator_node",
    "build_financial_researcher_node": "src.agent.nodes.researcher_node",
    "make_run_researcher": "src.agent.nodes.researcher_node",
}


def __getattr__(name: str):
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    from importlib import import_module

    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value
