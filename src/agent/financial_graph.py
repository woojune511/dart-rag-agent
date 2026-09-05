"""LangGraph orchestration for DART financial question answering."""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, Mapping, Optional, cast

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
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_graph_planning import FinancialAgentPlanningMixin
from src.agent.financial_graph_state import (
    CandidateInput, CandidatesUpdate, CompilationInput, CompilationPhase,
    CompilationUpdate, FinancialAgentState, FinancialAgentStateV2,
    FinalResultUpdate, LedgerUpdate, NarrativeInput, NarrativeResultUpdate,
    NumericExecutionInput, NumericResultPhase, NumericResultUpdate,
    PlanningInput, RequirementsPhase, RequirementsUpdate, RetrievalInput,
    RetrievalUpdate, RoutingInput, RoutingUpdate,
)
from src.agent.financial_run_result import (
    FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
    FinancialRunResultV1,
)
from src.agent.financial_retrieval_pipeline import FinancialRetrievalPipelineMixin
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_task_artifacts import (
    aggregate_answer_artifact_update,
    calculation_plan_artifact_update,
    calculation_result_artifact_update,
    operand_set_artifact_update,
    project_task_artifact_trace,
    semantic_plan_artifact_update,
)
from src.config.retrieval_policy import EVIDENCE_RUNTIME_POLICY, SECTION_BIAS_BY_QUERY_TYPE


logger = logging.getLogger(__name__)
_ENV_LOADED = False

FINANCIAL_GRAPH_PHASE_WRITERS = {
    "request": "initial_input",
    "routing": "route_request",
    "requirements": "plan_requirements",
    "retrieval": "retrieve_evidence",
    "candidates": "build_candidates",
    "compilation": "compile_program",
    "numeric_result": "execute_numeric",
    "narrative_result": "build_narrative",
    "final_result": "assemble_final",
    "ledger": "assemble_ledger",
}


def _load_env_once() -> None:
    global _ENV_LOADED
    if not _ENV_LOADED:
        load_dotenv()
        _ENV_LOADED = True


def _financial_agent_state_model() -> Any:
    from src.agent.financial_graph_state import FinancialAgentStateV2

    return FinancialAgentStateV2


def routing_phase_input(state: FinancialAgentStateV2) -> RoutingInput:
    request = state["request"]
    return {"query": request["query"], "report_scope": dict(request["report_scope"])}


def planning_phase_input(state: FinancialAgentStateV2) -> PlanningInput:
    request, routing = state["request"], state.get("routing", {})
    return {
        "query": request["query"],
        "report_scope": dict(request["report_scope"]),
        "query_type": routing.get("query_type", "qa"),
        "intent": routing.get("intent", routing.get("query_type", "qa")),
        "format_preference": routing.get("format_preference", ""),
        "companies": list(routing.get("companies", [])),
        "years": list(routing.get("years", [])),
        "topic": routing.get("topic", request["query"]),
        "section_filter": routing.get("section_filter"),
        "plan_loop_count": 0,
    }


def retrieval_phase_input(state: FinancialAgentStateV2) -> RetrievalInput:
    request = state["request"]
    routing, requirements = state.get("routing", {}), state.get("requirements", {})
    return {
        "query": request["query"],
        "report_scope": dict(request["report_scope"]),
        "query_type": routing.get("query_type", "qa"),
        "intent": routing.get("intent", routing.get("query_type", "qa")),
        "format_preference": routing.get("format_preference", ""),
        "companies": list(requirements.get("companies", routing.get("companies", []))),
        "years": list(requirements.get("years", routing.get("years", []))),
        "topic": requirements.get("topic", routing.get("topic", request["query"])),
        "section_filter": requirements.get("section_filter", routing.get("section_filter")),
        "semantic_plan": dict(requirements.get("semantic_plan", {})),
        "answer_obligations": list(requirements.get("answer_obligations", [])),
        "active_subtask": dict(requirements.get("active_subtask", {})),
        "retrieval_queries": list(requirements.get("retrieval_queries", [request["query"]])),
    }


def candidate_phase_input(state: FinancialAgentStateV2) -> CandidateInput:
    retrieval = state.get("retrieval", {})
    return {
        "retrieved_docs": list(retrieval.get("retrieved_docs", [])),
        "seed_retrieved_docs": list(retrieval.get("seed_retrieved_docs", [])),
        "evidence_items": [],
    }


def compilation_phase_input(state: FinancialAgentStateV2) -> CompilationInput:
    request = state["request"]
    requirements, candidates = state.get("requirements", {}), state["candidates"]
    retrieval = state.get("retrieval", {})
    return {
        "query": request["query"],
        "report_scope": dict(request["report_scope"]),
        "answer_obligations": list(requirements.get("answer_obligations", [])),
        "semantic_plan": dict(requirements.get("semantic_plan", {})),
        "active_subtask": dict(requirements.get("active_subtask", {})),
        "semantic_source_candidates": list(candidates["semantic_source_candidates"]),
        "semantic_candidate_catalog": list(candidates["semantic_candidate_catalog"]),
        "semantic_candidate_catalog_prebuilt": True,
        "retrieved_docs": list(retrieval.get("retrieved_docs", [])),
        "seed_retrieved_docs": list(retrieval.get("seed_retrieved_docs", [])),
        "retrieval_debug_trace": dict(retrieval.get("retrieval_debug_trace", {})),
    }


def numeric_phase_input(state: FinancialAgentStateV2) -> NumericExecutionInput:
    request = state["request"]
    requirements, compilation = state.get("requirements", {}), state.get("compilation", {})
    result: NumericExecutionInput = {
        "query": request["query"],
        "report_scope": dict(request["report_scope"]),
        "answer_obligations": list(requirements.get("answer_obligations", [])),
        "active_subtask": dict(requirements.get("active_subtask", {})),
        "semantic_candidate_catalog": list(state["candidates"]["semantic_candidate_catalog"]),
        "semantic_program": dict(compilation.get("semantic_program", {})),
        "resolved_calculation_trace": dict(compilation.get("resolved_calculation_trace", {})),
    }
    if "semantic_compilation_envelope" in compilation:
        result["semantic_compilation_envelope"] = compilation["semantic_compilation_envelope"]
    return result


def narrative_phase_input(state: FinancialAgentStateV2) -> NarrativeInput:
    request = state["request"]
    routing, requirements = state.get("routing", {}), state.get("requirements", {})
    return {
        "query": request["query"],
        "query_type": routing.get("query_type", "qa"),
        "intent": routing.get("intent", routing.get("query_type", "qa")),
        "format_preference": routing.get("format_preference", ""),
        "topic": requirements.get("topic", routing.get("topic", request["query"])),
        "semantic_plan": dict(requirements.get("semantic_plan", {})),
        "active_subtask": dict(requirements.get("active_subtask", {})),
        "retrieved_docs": list(state.get("retrieval", {}).get("retrieved_docs", [])),
    }


class FinancialAgent(
    FinancialAgentPlanningMixin,
    FinancialRetrievalPipelineMixin,
    FinancialAgentEvidenceMixin,
    FinancialAgentCalculationMixin,
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
            embedding_spec=dict(getattr(self.vsm, "embedding_spec", {}) or {}),
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

    @staticmethod
    def _route_after_retrieval_v2(state: FinancialAgentStateV2) -> str:
        requirements = dict(state.get("requirements") or {})
        semantic_plan = dict(requirements.get("semantic_plan") or {})
        return (
            "build_candidates"
            if bool(semantic_plan.get("program_required"))
            else "build_narrative"
        )

    def _route_request_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> RoutingUpdate:
        phase_input = routing_phase_input(state)
        classified = self._classify_query(phase_input)
        extracted = self._extract_entities(phase_input)
        return {"routing": {**classified, **extracted}}

    def _plan_requirements_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> RequirementsUpdate:
        planned = self._plan_answer_obligation_program(
            planning_phase_input(state)
        )
        return {"requirements": cast(RequirementsPhase, planned)}

    def _retrieve_evidence_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> RetrievalUpdate:
        retrieved = self._retrieve(retrieval_phase_input(state))
        expanded = self._expand_via_structure_graph(
            {"retrieved_docs": list(retrieved.get("retrieved_docs") or [])}
        )
        return {
            "retrieval": {**retrieved, **expanded}
        }

    def _build_candidates_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> CandidatesUpdate:
        phase_input = candidate_phase_input(state)
        source_candidates = self._semantic_source_candidates_for_state(phase_input)
        catalog = self._semantic_candidate_catalog_for_state(
            phase_input,
            source_candidates=source_candidates,
        )
        return {
            "candidates": {
                "semantic_source_candidates": source_candidates,
                "semantic_candidate_catalog": catalog,
                "semantic_candidate_catalog_prebuilt": True,
            }
        }

    def _compile_program_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> CompilationUpdate:
        compiled = self._compile_semantic_calculation_program(
            compilation_phase_input(state)
        )
        return {"compilation": cast(CompilationPhase, compiled)}

    def _execute_numeric_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> NumericResultUpdate:
        executed = self._execute_semantic_calculation_program(
            numeric_phase_input(state)
        )
        return {"numeric_result": cast(NumericResultPhase, executed)}

    def _build_narrative_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> NarrativeResultUpdate:
        phase_input = narrative_phase_input(state)
        evidence = self._extract_evidence(phase_input)
        draft_input: NarrativeInput = {
            **phase_input,
            "evidence_items": list(evidence.get("evidence_items") or []),
            "evidence_bullets": list(evidence.get("evidence_bullets") or []),
            "evidence_status": str(evidence.get("evidence_status") or "missing"),
        }
        compressed = self._compress_answer(draft_input)
        validation_input: NarrativeInput = {
            **draft_input,
            "evidence_items": list(compressed.get("evidence_items", draft_input["evidence_items"]) or []),
            "selected_claim_ids": list(compressed.get("selected_claim_ids") or []),
            "draft_points": list(compressed.get("draft_points") or []),
            "compressed_answer": str(compressed.get("compressed_answer") or ""),
        }
        validated = self._validate_answer(validation_input)
        return {
            "narrative_result": {
                "evidence_items": validation_input["evidence_items"],
                "evidence_status": draft_input["evidence_status"],
                "selected_claim_ids": validation_input["selected_claim_ids"],
                "draft_points": validation_input["draft_points"],
                "validated_sentences": list(validated.get("validated_sentences") or []),
                "sentence_checks": list(validated.get("sentence_checks") or []),
                "kept_claim_ids": list(validated.get("kept_claim_ids") or []),
                "dropped_claim_ids": list(validated.get("dropped_claim_ids") or []),
                "unsupported_sentences": list(validated.get("unsupported_sentences") or []),
                "calculation_projection": dict(compressed.get("calculation_projection") or {}),
            }
        }

    def _assemble_ledger_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> LedgerUpdate:
        requirements = state.get("requirements", {})
        final_result = state["final_result"]
        agent_answer = final_result["agent_answer"]
        tasks: list[Dict[str, Any]] = []
        artifacts: list[Dict[str, Any]] = []
        semantic_plan = dict(requirements.get("semantic_plan") or {})
        planned_tasks = [
            dict(item)
            for item in (
                semantic_plan.get("tasks")
                or requirements.get("calc_subtasks")
                or []
            )
            if isinstance(item, Mapping)
        ]
        if planned_tasks:
            plan_ledger = semantic_plan_artifact_update(
                tasks=tasks,
                artifacts=artifacts,
                artifact_task_id=str(
                    planned_tasks[0].get("task_id") or "task_1"
                ),
                semantic_plan=semantic_plan,
                retrieval_queries=list(requirements.get("retrieval_queries") or []),
                summary="planned runtime answer obligations",
                calculation_tasks=planned_tasks,
            )
            tasks = list(plan_ledger["tasks"])
            artifacts = list(plan_ledger["artifacts"])

        numeric_result = dict(state.get("numeric_result") or {})
        if numeric_result:
            runtime_trace = dict(agent_answer.get("resolved_calculation_trace") or {})
            operands = [
                dict(item)
                for item in (runtime_trace.get("calculation_operands") or [])
                if isinstance(item, Mapping)
            ]
            calculation_plan = dict(
                runtime_trace.get("calculation_plan") or {}
            )
            calculation_result = dict(
                runtime_trace.get("calculation_result") or {}
            )
            active_task = dict(requirements.get("active_subtask") or {})
            task_id = str(active_task.get("task_id") or "task_1")
            task_label = str(
                active_task.get("metric_label")
                or active_task.get("metric_family")
                or task_id
            )
            query = state["request"]["query"]
            metric_family = str(
                active_task.get("metric_family") or "semantic_program"
            )
            selected_ids = list(final_result.get("selected_claim_ids") or [])
            operand_ledger = operand_set_artifact_update(
                tasks=tasks,
                artifacts=artifacts,
                task_id=task_id,
                task_label=task_label,
                query=query,
                metric_family=metric_family,
                operand_rows=operands,
                status=(
                    "sufficient"
                    if str(calculation_result.get("semantic_status") or "")
                    == "ok"
                    else "partial"
                ),
                summary=f"{len(operands)} grounded semantic-program operand(s)",
                payload={"calculation_operands": operands},
                evidence_refs=selected_ids,
            )
            tasks = list(operand_ledger["tasks"])
            artifacts = list(operand_ledger["artifacts"])
            plan_ledger = calculation_plan_artifact_update(
                tasks=tasks,
                artifacts=artifacts,
                task_id=task_id,
                task_label=task_label,
                query=query,
                metric_family=metric_family,
                calculation_plan=calculation_plan,
            )
            tasks = list(plan_ledger["tasks"])
            artifacts = list(plan_ledger["artifacts"])
            result_ledger = calculation_result_artifact_update(
                tasks=tasks,
                artifacts=artifacts,
                task_id=task_id,
                task_label=task_label,
                query=query,
                metric_family=metric_family,
                calculation_result=calculation_result,
                evidence_refs=selected_ids,
            )
            tasks = list(result_ledger["tasks"])
            artifacts = list(result_ledger["artifacts"])

        final_answer = str(agent_answer.get("answer") or "")
        selected_ids = list(
            final_result.get("kept_claim_ids")
            or final_result.get("selected_claim_ids")
            or []
        )
        aggregate_ledger = aggregate_answer_artifact_update(
            tasks=tasks,
            artifacts=artifacts,
            final_answer=final_answer,
            payload={
                "final_answer": final_answer,
                "evidence_items": list(final_result["review_trace"].get("evidence_items") or []),
                "structured_result": dict(agent_answer.get("structured_result") or {}),
                "resolved_calculation_trace": dict(
                    agent_answer.get("resolved_calculation_trace") or {}
                ),
            },
            evidence_refs=selected_ids,
            planner_feedback=str(requirements.get("planner_feedback") or ""),
            query=state["request"]["query"],
        )
        tasks = list(aggregate_ledger["tasks"])
        artifacts = list(aggregate_ledger["artifacts"])
        return {
            "ledger": {
                "tasks": tasks,
                "artifacts": artifacts,
                "task_artifact_trace": project_task_artifact_trace(
                    tasks,
                    artifacts,
                ),
            }
        }

    def _assemble_final_phase(
        self,
        state: FinancialAgentStateV2,
    ) -> FinalResultUpdate:
        request = state["request"]
        routing, requirements = state.get("routing", {}), state.get("requirements", {})
        retrieval, compilation = state.get("retrieval", {}), state.get("compilation", {})
        narrative = state.get("narrative_result", {})
        numeric = state.get("numeric_result")
        obligations = list(requirements.get("answer_obligations") or [])
        if numeric is not None:
            from src.agent.financial_calculation_execution import assemble_semantic_execution_result

            execution = numeric["execution"]
            assembled = assemble_semantic_execution_result(
                execution=execution,
                obligations=obligations,
                calculation_plan=numeric["calculation_plan"],
                query=request["query"],
            )
            evidence_items = list(numeric["evidence_items"])
            selected_ids = list(execution.get("selected_candidate_ids") or [])
            kept_ids = list(selected_ids)
            missing_info = list(execution.get("missing_obligation_ids") or [])
        else:
            answer = _normalise_spaces(" ".join(narrative.get("validated_sentences") or []))
            if not answer:
                answer = str(EVIDENCE_RUNTIME_POLICY.get("no_direct_evidence_answer") or "")
            assembled = {
                "answer": answer,
                "structured_result": {},
                "resolved_calculation_trace": dict(narrative.get("calculation_projection") or {}),
                "subtask_results": [],
            }
            evidence_items = list(narrative.get("evidence_items") or [])
            selected_ids = list(narrative.get("selected_claim_ids") or [])
            kept_ids = list(narrative.get("kept_claim_ids") or [])
            missing_info = []

        # Explicit caller projection: no phase dictionary can overwrite another.
        context = {
            "query": request["query"],
            "report_scope": dict(request["report_scope"]),
            "query_type": routing.get("query_type", "qa"),
            "intent": routing.get("intent", routing.get("query_type", "qa")),
            "format_preference": routing.get("format_preference", ""),
            "routing_source": routing.get("routing_source", ""),
            "routing_confidence": routing.get("routing_confidence", 0.0),
            "routing_scores": dict(routing.get("routing_scores", {})),
            "routing_degraded_reason": routing.get("routing_degraded_reason", ""),
            "companies": list(requirements.get("companies", routing.get("companies", []))),
            "years": list(requirements.get("years", routing.get("years", []))),
            "topic": requirements.get("topic", routing.get("topic", request["query"])),
            "planner_mode": requirements.get("planner_mode", "initial"),
            "planner_feedback": requirements.get("planner_feedback", ""),
            "plan_loop_count": requirements.get("plan_loop_count", 0),
            "target_metric_family": routing.get("target_metric_family", ""),
            "target_metric_family_hint": routing.get("target_metric_family_hint", ""),
            "planned_metric_families": list(requirements.get("planned_metric_families", [])),
            "semantic_plan": dict(requirements.get("semantic_plan", {})),
            "answer_obligations": obligations,
            "calc_subtasks": list(requirements.get("calc_subtasks", [])),
            "retrieval_queries": list(requirements.get("retrieval_queries", [])),
            "active_subtask": dict(requirements.get("active_subtask", {})),
            "active_subtask_index": requirements.get("active_subtask_index", 0),
            "subtask_debug_trace": dict(requirements.get("subtask_debug_trace", {})),
            "subtask_loop_complete": True,
            "seed_retrieved_docs": list(retrieval.get("seed_retrieved_docs", [])),
            "retrieved_docs": list(retrieval.get("retrieved_docs", [])),
            "retrieval_debug_trace": dict(retrieval.get("retrieval_debug_trace", {})),
            "retrieval_debug_trace_history": list(retrieval.get("retrieval_debug_trace_history", [])),
            "semantic_candidate_catalog": list(state.get("candidates", {}).get("semantic_candidate_catalog", [])),
            "semantic_program": dict(compilation.get("semantic_program", {})),
            "semantic_program_validation": dict(compilation.get("semantic_program_validation", {})),
            "semantic_program_retry_count": compilation.get("semantic_program_retry_count", 0),
            "planner_debug_trace": dict(compilation.get("planner_debug_trace", {})),
            "calculation_debug_trace": dict(compilation.get("calculation_debug_trace", {})),
            "answer": str(assembled.get("answer") or ""),
            "structured_result": dict(assembled.get("structured_result") or {}),
            "resolved_calculation_trace": dict(assembled.get("resolved_calculation_trace") or {}),
            "subtask_results": list(assembled.get("subtask_results") or []),
            "evidence_items": evidence_items,
            "runtime_evidence": evidence_items,
            "selected_claim_ids": selected_ids,
            "kept_claim_ids": kept_ids,
            "draft_points": list(narrative.get("draft_points") or []),
            "dropped_claim_ids": list(narrative.get("dropped_claim_ids") or []),
            "unsupported_sentences": list(narrative.get("unsupported_sentences") or []),
            "sentence_checks": list(narrative.get("sentence_checks") or []),
            "missing_info": missing_info,
        }
        runtime_trace = self._project_runtime_calculation_trace(context)
        structured_result = dict(context["structured_result"] or runtime_trace.get("calculation_result") or {})
        public_answer = _normalise_spaces(context["answer"])
        structured_answer = structured_result_answer_for_missing_public_answer(public_answer, structured_result)
        if structured_answer:
            public_answer = structured_answer
        runtime_evidence = self._runtime_evidence_from_retrieved_docs(context)
        citation_update = self._format_citations(context)
        citations = augment_citations_from_runtime_evidence(
            list(citation_update.get("citations") or []), runtime_evidence
        )
        agent_answer = project_agent_answer(
            context, public_answer=public_answer, citations=citations,
            structured_result=structured_result, runtime_calculation_trace=runtime_trace,
        )
        return {
            "final_result": {
                "agent_answer": agent_answer,
                "review_trace": project_review_trace(
                    context, runtime_evidence=runtime_evidence, task_artifact_trace={}
                ),
                "debug_traces": project_debug_traces(context),
                "selected_claim_ids": selected_ids,
                "kept_claim_ids": kept_ids,
            }
        }

    def _build_graph(self):
        """Wire the phase-owned requirement-to-answer execution order."""

        from langgraph.graph import END, StateGraph

        graph = StateGraph(_financial_agent_state_model())
        graph.add_node("route_request", self._route_request_phase)
        graph.add_node("plan_requirements", self._plan_requirements_phase)
        graph.add_node("retrieve_evidence", self._retrieve_evidence_phase)
        graph.add_node("build_candidates", self._build_candidates_phase)
        graph.add_node("compile_program", self._compile_program_phase)
        graph.add_node("execute_numeric", self._execute_numeric_phase)
        graph.add_node("build_narrative", self._build_narrative_phase)
        graph.add_node("assemble_ledger", self._assemble_ledger_phase)
        graph.add_node("assemble_final", self._assemble_final_phase)

        graph.set_entry_point("route_request")
        graph.add_edge("route_request", "plan_requirements")
        graph.add_edge("plan_requirements", "retrieve_evidence")
        graph.add_conditional_edges(
            "retrieve_evidence",
            self._route_after_retrieval_v2,
            {
                "build_candidates": "build_candidates",
                "build_narrative": "build_narrative",
            },
        )
        graph.add_edge("build_candidates", "compile_program")
        graph.add_edge("compile_program", "execute_numeric")
        graph.add_edge("execute_numeric", "assemble_final")
        graph.add_edge("build_narrative", "assemble_final")
        graph.add_edge("assemble_final", "assemble_ledger")
        graph.add_edge("assemble_ledger", END)
        return graph.compile()

    @staticmethod
    def _initial_state(
        query: str,
        report_scope: Optional[Dict[str, Any]],
    ) -> FinancialAgentStateV2:
        return {
            "request": {
                "query": query,
                "report_scope": dict(report_scope or {}),
            }
        }

    def run(
        self,
        query: str,
        *,
        report_scope: Optional[Dict[str, Any]] = None,
        include_review_trace: bool = False,
        include_debug_bundle: bool = False,
    ) -> FinancialRunResultV1:
        """Execute the graph and expose its canonical result without numeric repair."""

        usage_callback = getattr(self, "llm_usage_callback", None)
        if usage_callback is not None:
            usage_callback.reset_current_thread()
        vsm = getattr(self, "vsm", None)
        reset_embedding_usage = getattr(vsm, "reset_current_thread_embedding_usage", None)
        if callable(reset_embedding_usage):
            reset_embedding_usage()

        graph_final = self.graph.invoke(self._initial_state(query, report_scope))
        final = graph_final["final_result"]
        llm_usage = usage_callback.snapshot_current_thread() if usage_callback is not None else {}
        llm_usage_by_phase = (
            usage_callback.snapshot_current_thread_by_phase() if usage_callback is not None else {}
        )
        embedding_snapshot = getattr(vsm, "get_current_thread_embedding_usage_snapshot", None)
        embedding_usage = embedding_snapshot() if callable(embedding_snapshot) else {}

        review_trace = None
        if include_review_trace:
            ledger = graph_final["ledger"]
            review_trace = {
                **final["review_trace"],
                "tasks": list(ledger["tasks"]),
                "artifacts": list(ledger["artifacts"]),
                "task_artifact_trace": dict(ledger["task_artifact_trace"]),
            }
        debug_bundle = (
            project_debug_bundle(
                debug_traces=final["debug_traces"],
                llm_usage=llm_usage,
                llm_usage_by_phase=llm_usage_by_phase,
                embedding_usage=embedding_usage,
            )
            if include_debug_bundle
            else None
        )
        return FinancialRunResultV1(
            schema_version=FINANCIAL_RUN_RESULT_SCHEMA_VERSION,
            agent_answer=final["agent_answer"],
            review_trace=review_trace,
            debug_bundle=debug_bundle,
        )
