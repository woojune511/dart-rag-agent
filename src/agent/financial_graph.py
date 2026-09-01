"""LangGraph orchestration for DART financial question answering."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Optional

from dotenv import load_dotenv

from src.agent.financial_agent_run_projection import (
    augment_citations_from_runtime_evidence,
    enrich_runtime_evidence_metadata,
    project_agent_answer,
    project_debug_bundle,
    project_debug_traces,
    project_review_trace,
    structured_result_answer_for_missing_public_answer,
)
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_graph_contextual import FinancialAgentContextualMixin
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_graph_planning import FinancialAgentPlanningMixin
from src.agent.financial_graph_state import FinancialAgentState
from src.agent.financial_retrieval_pipeline import FinancialRetrievalPipelineMixin
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_task_artifacts import project_task_artifact_trace
from src.config.retrieval_policy import SECTION_BIAS_BY_QUERY_TYPE


logger = logging.getLogger(__name__)
_ENV_LOADED = False


def _load_env_once() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv()
        _ENV_LOADED = True


def _financial_agent_state_model() -> Any:
    from src.agent.financial_graph_state import FinancialAgentState

    return FinancialAgentState


class FinancialAgent(
    FinancialAgentPlanningMixin,
    FinancialRetrievalPipelineMixin,
    FinancialAgentEvidenceMixin,
    FinancialAgentCalculationMixin,
    FinancialAgentContextualMixin,
):
    """Top-level dependency, graph, and public projection owner."""

    _SECTION_BIAS_BY_QUERY_TYPE = SECTION_BIAS_BY_QUERY_TYPE

    @staticmethod
    def _runtime_evidence_from_retrieved_docs(final: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Return only evidence selected by the active answer path.

        Numeric evidence is created by the semantic executor from registered
        candidate IDs. Narrative evidence is created by the narrative evidence
        path. This adapter never reconstructs provenance from answer text.
        """

        existing = [
            dict(item)
            for item in (final.get("runtime_evidence") or final.get("evidence_items") or [])
            if isinstance(item, dict)
        ]
        if not existing:
            return []
        selected_ids = {
            str(value).strip()
            for value in (final.get("kept_claim_ids") or final.get("selected_claim_ids") or [])
            if str(value).strip()
        }
        if selected_ids:
            selected = [
                item
                for item in existing
                if str(item.get("evidence_id") or "").strip() in selected_ids
            ]
            if selected:
                existing = selected
        return enrich_runtime_evidence_metadata(final, existing)

    def __init__(
        self,
        vector_store_manager,
        k: int = 8,
        graph_expansion_config: Optional[Dict[str, Any]] = None,
        routing_config: Optional[Dict[str, Any]] = None,
    ):
        _load_env_once()
        self.vsm = vector_store_manager
        self.k = k
        self.routing_config = dict(routing_config or {})
        self.report_cache_index_path = str(
            self.routing_config.get("report_cache_index_path") or ""
        ).strip()
        for attribute, config_key, default in (
            ("retrieval_query_budget", "retrieval_query_budget", 0),
            ("focused_retrieval_query_budget", "focused_retrieval_query_budget", 0),
            ("retry_retrieval_query_budget", "retry_retrieval_query_budget", 0),
            ("retrieval_hint_query_token_budget", "retrieval_hint_query_token_budget", 16),
            ("preferred_section_query_budget", "preferred_section_query_budget", 8),
        ):
            try:
                value = int(self.routing_config.get(config_key) or default)
            except (TypeError, ValueError):
                value = default
            setattr(self, attribute, value)

        self.graph_expansion_config = {
            "enabled": False,
            "include_parent_context": True,
            "include_section_lead": True,
            "include_reference_notes": True,
            "include_described_by_paragraph": True,
            "include_table_context": True,
            "include_sibling_prev": True,
            "include_sibling_next": False,
            "table_sibling_prev_paragraph_only": True,
            "sibling_window": 1,
            "max_docs": k,
        }
        if graph_expansion_config:
            self.graph_expansion_config.update(graph_expansion_config)

        from src.utils.gemini_usage import GeminiUsageCallbackHandler

        self.llm_usage_callback = GeminiUsageCallbackHandler()
        self.llm_routes = self._build_llm_routes()
        self.llm = self.llm_routes.get("default")
        if self.llm is None:
            raise ValueError("Default LLM route was not initialized.")

        from src.routing import QueryRouter

        self.query_router = QueryRouter(
            embeddings=self.vsm.embeddings,
            llm=self.llm,
            enable_semantic_router=bool(self.routing_config.get("enable_semantic_router", True)),
            enable_llm_fallback=bool(self.routing_config.get("enable_llm_fallback", True)),
        )
        self.graph = self._build_graph()

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

            return ChatGoogleGenerativeAI(
                model=model,
                temperature=temperature,
                google_api_key=api_key,
                callbacks=[self.llm_usage_callback],
            )
        if provider in {"openai", "openrouter"}:
            key_name = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
            api_key = str(spec.get("api_key") or os.environ.get(key_name) or "").strip()
            if not api_key:
                raise ValueError(f"{key_name} environment variable is required for LLM route '{phase}'.")
            base_url = spec.get("base_url")
            if provider == "openrouter" and not base_url:
                base_url = os.environ.get("OPENROUTER_BASE_URL") or "https://openrouter.ai/api/v1"
            from langchain_openai import ChatOpenAI

            return ChatOpenAI(
                model=model,
                temperature=temperature,
                api_key=api_key,
                base_url=str(base_url) if base_url else None,
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

    @staticmethod
    def _route_after_expand(state: FinancialAgentState) -> str:
        return (
            "program_compiler"
            if bool(dict(state.get("semantic_plan") or {}).get("program_required"))
            else "evidence"
        )

    def _build_graph(self):
        """Wire the canonical requirement-to-answer execution order."""

        from langgraph.graph import END, StateGraph

        graph = StateGraph(_financial_agent_state_model())
        graph.add_node("classify", self._classify_query)
        graph.add_node("extract", self._extract_entities)
        graph.add_node("requirement_planner", self._plan_answer_obligation_program)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("expand", self._expand_via_structure_graph)
        graph.add_node("evidence", self._extract_evidence)
        graph.add_node("program_compiler", self._compile_semantic_calculation_program)
        graph.add_node("program_executor", self._execute_semantic_calculation_program)
        graph.add_node("compress", self._compress_answer)
        graph.add_node("validate", self._validate_answer)
        graph.add_node("cite", self._format_citations)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "extract")
        graph.add_edge("extract", "requirement_planner")
        graph.add_edge("requirement_planner", "retrieve")
        graph.add_edge("retrieve", "expand")
        graph.add_conditional_edges(
            "expand",
            self._route_after_expand,
            {"program_compiler": "program_compiler", "evidence": "evidence"},
        )
        graph.add_edge("program_compiler", "program_executor")
        graph.add_edge("program_executor", "cite")
        graph.add_edge("evidence", "compress")
        graph.add_edge("compress", "validate")
        graph.add_edge("validate", "cite")
        graph.add_edge("cite", END)
        return graph.compile()

    @staticmethod
    def _initial_state(query: str, report_scope: Optional[Dict[str, Any]]) -> FinancialAgentState:
        return {
            "query": query,
            "report_scope": dict(report_scope or {}),
            "query_type": "",
            "intent": "",
            "planner_mode": "initial",
            "planner_feedback": "",
            "plan_loop_count": 0,
            "target_metric_family": "",
            "target_metric_family_hint": "",
            "planned_metric_families": [],
            "format_preference": "",
            "routing_source": "",
            "routing_confidence": 0.0,
            "routing_scores": {},
            "companies": [],
            "years": [],
            "topic": "",
            "section_filter": None,
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
            "retrieval_debug_trace": {},
            "retrieval_debug_trace_history": [],
            "evidence_bullets": [],
            "evidence_items": [],
            "evidence_status": "missing",
            "selected_claim_ids": [],
            "draft_points": [],
            "compressed_answer": "",
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "answer": "",
            "citations": [],
            "numeric_debug_trace": {},
            "numeric_debug_trace_history": [],
            "resolved_calculation_trace": {},
            "structured_result": {},
            "planner_debug_trace": {},
            "missing_info": [],
            "reflection_count": 0,
            "retry_reason": "",
            "retry_strategy": "",
            "retry_queries": [],
            "reconciliation_retry_count": 0,
            "reflection_plan": {},
            "semantic_plan": {},
            "answer_obligations": [],
            "semantic_candidate_catalog": [],
            "semantic_program": {},
            "semantic_program_validation": {},
            "semantic_program_retry_count": 0,
            "calc_subtasks": [],
            "retrieval_queries": [],
            "active_subtask_index": 0,
            "active_subtask": {},
            "subtask_results": [],
            "subtask_debug_trace": {},
            "subtask_loop_complete": False,
            "reconciliation_result": {},
            "tasks": [],
            "artifacts": [],
        }

    def run(self, query: str, *, report_scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the graph and expose its canonical result without numeric repair."""

        usage_callback = getattr(self, "llm_usage_callback", None)
        if usage_callback is not None:
            usage_callback.reset_current_thread()
        vsm = getattr(self, "vsm", None)
        reset_embedding_usage = getattr(vsm, "reset_current_thread_embedding_usage", None)
        if callable(reset_embedding_usage):
            reset_embedding_usage()

        final = self.graph.invoke(self._initial_state(query, report_scope))
        llm_usage = usage_callback.snapshot_current_thread() if usage_callback is not None else {}
        llm_usage_by_phase = (
            usage_callback.snapshot_current_thread_by_phase() if usage_callback is not None else {}
        )
        embedding_snapshot = getattr(vsm, "get_current_thread_embedding_usage_snapshot", None)
        embedding_usage = embedding_snapshot() if callable(embedding_snapshot) else {}

        runtime_calculation_trace = self._project_runtime_calculation_trace(final)
        public_answer = _normalise_spaces(str(final.get("answer") or ""))
        structured_result = dict(
            final.get("structured_result")
            or runtime_calculation_trace.get("calculation_result")
            or {}
        )
        structured_answer = structured_result_answer_for_missing_public_answer(
            public_answer,
            structured_result,
        )
        if structured_answer:
            public_answer = structured_answer
        runtime_evidence = self._runtime_evidence_from_retrieved_docs(final)
        citations = augment_citations_from_runtime_evidence(
            list(final.get("citations") or []),
            runtime_evidence,
        )
        task_artifact_trace = project_task_artifact_trace(
            list(final.get("tasks") or []),
            list(final.get("artifacts") or []),
        )
        agent_answer = project_agent_answer(
            final,
            public_answer=public_answer,
            citations=citations,
            structured_result=structured_result,
            runtime_calculation_trace=runtime_calculation_trace,
        )
        review_trace = project_review_trace(
            final,
            runtime_evidence=runtime_evidence,
            task_artifact_trace=task_artifact_trace,
        )
        debug_bundle = project_debug_bundle(
            debug_traces=project_debug_traces(final),
            llm_usage=llm_usage,
            llm_usage_by_phase=llm_usage_by_phase,
            embedding_usage=embedding_usage,
        )
        return {
            **agent_answer,
            **review_trace,
            **debug_bundle,
            "agent_answer": agent_answer,
            "review_trace": review_trace,
            "debug_bundle": debug_bundle,
        }
