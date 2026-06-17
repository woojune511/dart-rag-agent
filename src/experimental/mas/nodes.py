"""Experimental MAS node facade."""

from src.agent.nodes.analyst_node import (
    AnalystCoreRunner,
    build_financial_analyst_node,
    make_run_analyst,
)
from src.agent.nodes.critic_node import run_critic
from src.agent.nodes.dummy_nodes import (
    run_analyst as run_dummy_analyst,
    run_orchestrator_merge as run_dummy_orchestrator_merge,
    run_orchestrator_plan as run_dummy_orchestrator_plan,
    run_researcher as run_dummy_researcher,
)
from src.agent.nodes.orchestrator_node import (
    FinancialOrchestratorMergeCore,
    FinancialOrchestratorPlannerCore,
    OrchestratorMergeCore,
    OrchestratorPlannerCore,
    build_financial_orchestrator_merge_node,
    build_financial_orchestrator_plan_node,
    make_run_orchestrator_merge,
    make_run_orchestrator_plan,
)
from src.agent.nodes.researcher_node import (
    NarrativeResearcherCore,
    ResearcherCoreRunner,
    build_financial_researcher_node,
    make_run_researcher,
)

__all__ = [
    "AnalystCoreRunner",
    "FinancialOrchestratorMergeCore",
    "FinancialOrchestratorPlannerCore",
    "NarrativeResearcherCore",
    "OrchestratorMergeCore",
    "OrchestratorPlannerCore",
    "ResearcherCoreRunner",
    "build_financial_analyst_node",
    "build_financial_orchestrator_merge_node",
    "build_financial_orchestrator_plan_node",
    "build_financial_researcher_node",
    "make_run_analyst",
    "make_run_orchestrator_merge",
    "make_run_orchestrator_plan",
    "make_run_researcher",
    "run_critic",
    "run_dummy_analyst",
    "run_dummy_orchestrator_merge",
    "run_dummy_orchestrator_plan",
    "run_dummy_researcher",
]
