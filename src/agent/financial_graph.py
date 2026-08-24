"""
LangGraph-based DART financial analysis agent.

This file is intentionally thin after the refactor:
- phase-specific node implementations live in mixins
- shared pure functions live in `financial_graph_helpers.py`
- lightweight state definitions live in `financial_graph_state.py`
- structured-output schema definitions live in `financial_graph_models.py`

If you need to understand the runtime at a glance, read this file first and
then jump into the mixin that owns the phase you care about.
"""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any, Dict, Optional

from dotenv import load_dotenv
from src.agent.financial_graph_contextual import FinancialAgentContextualMixin
from src.agent.financial_agent_run_projection import (
    augment_citations_from_runtime_evidence,
    complete_aggregate_public_answer_projection,
    enrich_runtime_evidence_metadata,
    public_projection_state,
    project_agent_answer,
    project_debug_bundle,
    project_debug_traces,
    project_review_trace,
    structured_result_answer_for_missing_public_answer,
    with_public_answer,
)
from src.agent.financial_graph_state import FinancialAgentState
if TYPE_CHECKING:
    from src.agent.financial_graph_state import (
        RuntimeCalculationTrace,
    )
from src.agent.financial_numeric_surface import answer_covers_numeric_answer, extract_numeric_surface_candidates
from src.agent.financial_operation_policies import requires_direct_numeric_grounding
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


from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_aggregate_projection import (
    append_final_answer_surface_operands_from_evidence,
    append_operand_evidence_for_final_answer,
    filter_aggregate_evidence_for_final_answer,
    structured_subtask_projection_for_public_answer,
)
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_retrieval_pipeline import FinancialRetrievalPipelineMixin
from src.agent.financial_answer_projection import preferred_complete_aggregate_subtask_answer
from src.agent.financial_graph_planning import FinancialAgentPlanningMixin
from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.agent.financial_runtime_trace import (
    attach_runtime_projection_metadata,
    build_runtime_aggregate_calculation_projection,
    resolve_runtime_calculation_trace,
    structured_result_subtask_rows_and_answer,
    repair_collapsed_ratio_trace_from_evidence,
)
from src.agent.financial_task_artifacts import project_task_artifact_trace as _project_task_artifact_trace

class FinancialAgent(
    FinancialAgentPlanningMixin,
    FinancialAgentReconciliationMixin,
    FinancialRetrievalPipelineMixin,
    FinancialAgentEvidenceMixin,
    FinancialAgentCalculationMixin,
    FinancialAgentContextualMixin,
):
    """Top-level orchestration shell for the DART single-agent workflow.

    The actual node bodies are split across mixins so this class can stay
    focused on three things:
    1. dependency wiring
    2. graph wiring
    3. input/output normalization for external callers
    """

    _SECTION_BIAS_BY_QUERY_TYPE = SECTION_BIAS_BY_QUERY_TYPE

    def _structured_result_projection_for_stale_public_numeric_answer(
        self,
        final: Dict[str, Any],
        *,
        public_answer: str,
        structured_result: Dict[str, Any],
        evidence_items: list[Dict[str, Any]],
    ) -> tuple[str, RuntimeCalculationTrace]:
        subtask_results, structured_answer = structured_result_subtask_rows_and_answer(structured_result)
        if not subtask_results:
            return "", {}
        preferred_complete_answer = preferred_complete_aggregate_subtask_answer(
            subtask_results,
            structured_answer or public_answer,
        )
        if preferred_complete_answer and _normalise_spaces(public_answer) == preferred_complete_answer:
            return "", {}
        replacement_answer = self._complete_numeric_projection_replacement_answer(
            final_answer=public_answer,
            ordered_results=subtask_results,
            query=str(final.get("query") or ""),
            evidence_items=evidence_items,
        )
        if not replacement_answer:
            return "", {}
        if answer_covers_numeric_answer(public_answer, replacement_answer) and answer_covers_numeric_answer(
            replacement_answer,
            public_answer,
        ):
            return "", {}
        projection = build_runtime_aggregate_calculation_projection(subtask_results, replacement_answer)
        projection_result = dict(projection.get("calculation_result") or {})
        if not projection_result.get("subtask_results"):
            return "", {}
        projection = attach_runtime_projection_metadata(
            projection,
            source="structured_result_subtasks",
        )
        projection["runtime_projection"] = {
            **dict(projection.get("runtime_projection") or {}),
            "public_answer_repaired": True,
        }
        return replacement_answer, projection

    def _apply_stale_structured_numeric_public_answer_repair(
        self,
        final: Dict[str, Any],
        *,
        public_answer: str,
        structured_result: Dict[str, Any],
        runtime_calculation_trace: RuntimeCalculationTrace,
        runtime_evidence: list[Dict[str, Any]],
    ) -> tuple[str, Dict[str, Any], RuntimeCalculationTrace]:
        structured_numeric_answer, structured_numeric_projection = (
            self._structured_result_projection_for_stale_public_numeric_answer(
                final,
                public_answer=public_answer,
                structured_result=structured_result,
                evidence_items=runtime_evidence,
            )
        )
        if not structured_numeric_answer:
            return public_answer, final, runtime_calculation_trace
        return (
            structured_numeric_answer,
            with_public_answer(final, structured_numeric_answer),
            structured_numeric_projection,
        )

    def _structured_public_answer_trace_projection(
        self,
        final: Dict[str, Any],
        *,
        public_answer: str,
        structured_result: Dict[str, Any],
        runtime_calculation_trace: RuntimeCalculationTrace,
        runtime_evidence: list[Dict[str, Any]],
    ) -> RuntimeCalculationTrace:
        projection_state = {
            **with_public_answer(final, public_answer),
            "structured_result": structured_result,
            "resolved_calculation_trace": runtime_calculation_trace,
        }
        structured_public_projection = structured_subtask_projection_for_public_answer(
            projection_state,
            runtime_calculation_trace,
        )
        if not structured_public_projection:
            return {}
        return repair_collapsed_ratio_trace_from_evidence(
            public_projection_state(
                final,
                public_answer=public_answer,
                runtime_calculation_trace=structured_public_projection,
                runtime_evidence=runtime_evidence,
            ),
            structured_public_projection,
        )

    def _retrieved_ratio_context_projection_for_public_answer(
        self,
        final: Dict[str, Any],
        *,
        public_answer: str,
    ) -> RuntimeCalculationTrace:
        answer_text = _normalise_spaces(str(public_answer or ""))
        if not answer_text:
            return {}
        recovered_rows = self._append_ratio_result_from_retrieved_context(
            [],
            final,
        )
        ratio_rows = [
            dict(row)
            for row in recovered_rows
            if isinstance(row, dict)
            and row.get("recovered_from_retrieved_ratio_context")
            and self._aggregate_result_operation_family(row) == "ratio"
        ]
        for row in ratio_rows:
            if not self._answer_covers_numeric_projection(answer_text, [row]):
                row_answer = _normalise_spaces(
                    str(
                        row.get("answer")
                        or (dict(row.get("calculation_result") or {}).get("formatted_result"))
                        or (dict(row.get("calculation_result") or {}).get("rendered_value"))
                        or ""
                    )
                )
                if not row_answer or not answer_covers_numeric_answer(answer_text, row_answer):
                    continue
            projection = self._rebuild_aggregate_projection([row], answer_text)
            projection = attach_runtime_projection_metadata(
                projection,
                source="retrieved_ratio_context",
            )
            return projection
        return {}

    def _runtime_evidence_from_retrieved_docs(self, final: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Preserve numeric provenance when a non-calculation path produced the final answer."""
        existing = [dict(item) for item in (final.get("evidence_items") or []) if isinstance(item, dict)]
        final_answer = _normalise_spaces(str(final.get("answer") or final.get("compressed_answer") or ""))
        answer_candidates = extract_numeric_surface_candidates(final_answer) if final_answer else []
        if answer_candidates:
            projection = self._project_runtime_calculation_trace(final)
            operands = list((projection or {}).get("calculation_operands") or [])
            evidence_items = append_operand_evidence_for_final_answer(
                existing,
                operands=operands,
                final_answer=final_answer,
            )
            filtered = filter_aggregate_evidence_for_final_answer(
                evidence_items,
                final_answer=final_answer,
                selected_claim_ids=list(final.get("selected_claim_ids") or []),
            )[:8]
            if filtered:
                return enrich_runtime_evidence_metadata(final, filtered)
        if existing:
            selected_ids = [
                str(value).strip()
                for value in (final.get("kept_claim_ids") or final.get("selected_claim_ids") or [])
                if str(value).strip()
            ]
            if selected_ids:
                wanted = set(selected_ids)
                selected_existing = [
                    item
                    for item in existing
                    if str(item.get("evidence_id") or "").strip() in wanted
                ]
                if selected_existing:
                    return enrich_runtime_evidence_metadata(final, selected_existing)
            return enrich_runtime_evidence_metadata(final, existing)
        if not final_answer or not answer_candidates:
            return []

        evidence_items: list[Dict[str, Any]] = []
        seen: set[str] = set()
        retrieved_items = list(final.get("seed_retrieved_docs") or []) + list(final.get("retrieved_docs") or [])
        for item in retrieved_items:
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            if isinstance(doc, dict):
                page_content = _normalise_spaces(
                    str(doc.get("page_content") or doc.get("content") or doc.get("text") or "")
                )
                metadata = dict(doc.get("metadata") or {})
            else:
                page_content = _normalise_spaces(
                    str(getattr(doc, "page_content", None) or getattr(doc, "content", None) or "")
                )
                metadata = dict(getattr(doc, "metadata", {}) or {})
            if not page_content:
                continue
            source_anchor = _normalise_spaces(
                str(
                    metadata.get("source_anchor")
                    or metadata.get("section_path")
                    or metadata.get("section_title")
                    or metadata.get("section")
                    or ""
                )
            )
            dedupe_key = "|".join([source_anchor, page_content[:240]])
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            evidence_items.append(
                {
                    "evidence_id": f"retrieved::{len(evidence_items) + 1:03d}",
                    "source_anchor": source_anchor,
                    "claim": page_content,
                    "quote_span": page_content,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "metadata": metadata,
                }
            )

        if not evidence_items:
            return []
        filtered = filter_aggregate_evidence_for_final_answer(
            evidence_items,
            final_answer=final_answer,
            selected_claim_ids=[],
        )[:8]
        return enrich_runtime_evidence_metadata(final, filtered)

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
        self.report_cache_index_path = str(self.routing_config.get("report_cache_index_path") or "").strip()
        try:
            self.retrieval_query_budget = int(self.routing_config.get("retrieval_query_budget") or 0)
        except (TypeError, ValueError):
            self.retrieval_query_budget = 0
        try:
            self.focused_retrieval_query_budget = int(self.routing_config.get("focused_retrieval_query_budget") or 0)
        except (TypeError, ValueError):
            self.focused_retrieval_query_budget = 0
        try:
            self.retry_retrieval_query_budget = int(self.routing_config.get("retry_retrieval_query_budget") or 0)
        except (TypeError, ValueError):
            self.retry_retrieval_query_budget = 0
        try:
            self.retrieval_hint_query_token_budget = int(
                self.routing_config.get("retrieval_hint_query_token_budget") or 16
            )
        except (TypeError, ValueError):
            self.retrieval_hint_query_token_budget = 16
        try:
            self.preferred_section_query_budget = int(
                self.routing_config.get("preferred_section_query_budget") or 8
            )
        except (TypeError, ValueError):
            self.preferred_section_query_budget = 8
        # Expansion keeps the initial retrieval hits intact and selectively
        # appends nearby structural context such as parent paragraphs or table
        # descriptions.
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
            if phase == "default" or not isinstance(spec, dict):
                continue
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
            default_key_name = "OPENROUTER_API_KEY" if provider == "openrouter" else "OPENAI_API_KEY"
            api_key = str(spec.get("api_key") or os.environ.get(default_key_name) or "").strip()
            if not api_key:
                raise ValueError(f"{default_key_name} environment variable is required for LLM route '{phase}'.")
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

    def _active_retry_strategy(self, state: FinancialAgentState) -> str:
        for candidate in (
            state.get("retry_strategy"),
            dict(state.get("reconciliation_result") or {}).get("retry_strategy"),
            dict(state.get("reflection_plan") or {}).get("retry_strategy"),
        ):
            cleaned = _normalise_spaces(str(candidate or "")).lower()
            if cleaned:
                return cleaned
        return ""

    def _is_reflection_eligible(self, state: FinancialAgentState) -> bool:
        intent = state.get("intent") or state.get("query_type", "qa")
        return intent in {"comparison", "trend"}

    def _route_after_prepare_retry(self, state: FinancialAgentState) -> str:
        if self._active_retry_strategy(state) == "synthesize_from_task_outputs":
            return "operand_extractor"
        return "retrieve"

    def _route_after_expand(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
        if active_operation == "narrative_summary":
            return "evidence"
        if list(state.get("calc_subtasks") or []):
            if active_operation in {"lookup", "single_value"}:
                return "numeric_extractor"
            return "evidence"
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent == "numeric_fact":
            return "numeric_extractor"
        return "evidence"

    def _route_after_numeric_extractor(self, state: FinancialAgentState) -> str:
        if list(state.get("calc_subtasks") or []):
            active_subtask = dict(state.get("active_subtask") or {})
            active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
            evidence_status = str(state.get("evidence_status") or "").strip().lower()
            has_retrieved_docs = bool(state.get("retrieved_docs") or state.get("seed_retrieved_docs"))
            if active_operation in {"lookup", "single_value"} and evidence_status == "missing" and has_retrieved_docs:
                return "reconcile_plan"
            return "advance_subtask"
        return "cite"

    def _route_after_evidence(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
        if active_operation == "narrative_summary":
            return "compress"
        if list(state.get("calc_subtasks") or []):
            return "reconcile_plan"
        intent = state.get("intent") or state.get("query_type", "qa")
        if intent in {"comparison", "trend"}:
            return "reconcile_plan"
        return "compress"

    def _route_after_reconcile_plan(self, state: FinancialAgentState) -> str:
        result = dict(state.get("reconciliation_result") or {})
        status = str(result.get("status") or "ready")
        retry_strategy = _normalise_spaces(str(result.get("retry_strategy") or "")).lower()
        if status == "ready":
            return "operand_extractor"
        if retry_strategy == "synthesize_from_task_outputs":
            return "operand_extractor"
        if status == "retry_retrieval":
            return "retrieve"
        if status == "insufficient_operands":
            active_subtask = dict(state.get("active_subtask") or {})
            required_operands = [
                item
                for item in (active_subtask.get("required_operands") or [])
                if isinstance(item, dict) and bool(item.get("required", True))
            ]
            has_retrieved_docs = bool(state.get("retrieved_docs") or state.get("seed_retrieved_docs"))
            if required_operands and has_retrieved_docs and not requires_direct_numeric_grounding(active_subtask):
                return "operand_extractor"
        return "advance_subtask"

    def _route_after_advance_subtask(self, state: FinancialAgentState) -> str:
        if bool(state.get("subtask_loop_complete")):
            return "aggregate_subtasks"
        active_subtask = dict(state.get("active_subtask") or {})
        active_operation = str(active_subtask.get("operation_family") or "").strip().lower()
        if active_operation in {"lookup", "single_value", "narrative_summary"}:
            return "retrieve"
        return "reconcile_plan"

    def _route_after_aggregate_subtasks(self, state: FinancialAgentState) -> str:
        semantic_status = _normalise_spaces(
            str((state.get("semantic_plan") or {}).get("status") or "")
        ).lower()
        if semantic_status == "narrative_policy_exclusive":
            return "cite"
        planner_feedback = _normalise_spaces(str(state.get("planner_feedback") or ""))
        if (
            planner_feedback
            and int(state.get("plan_loop_count") or 0) < 2
            and not _normalise_spaces(str(state.get("replan_blocked_reason") or ""))
        ):
            return "pre_calc_planner"
        return "cite"

    def _route_after_validate(self, state: FinancialAgentState) -> str:
        active_subtask = dict(state.get("active_subtask") or {})
        if str(active_subtask.get("operation_family") or "").strip().lower() == "narrative_summary" and list(state.get("calc_subtasks") or []):
            return "advance_subtask"
        return "cite"

    def _route_after_formula_planner(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calculator"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calculator"
        plan = dict(
            resolve_runtime_calculation_trace(
                dict(state),
                allow_legacy_top_level=False,
            ).get("calculation_plan") or {}
        )
        status = str(plan.get("status") or "ok").lower()
        if status == "incomplete":
            return "reflection_replan"
        return "calculator"

    def _route_after_calculator(self, state: FinancialAgentState) -> str:
        if not self._is_reflection_eligible(state):
            return "calc_render"
        if int(state.get("reflection_count") or 0) >= 1:
            return "calc_render"
        result = dict(
            resolve_runtime_calculation_trace(
                dict(state),
                allow_legacy_top_level=False,
            ).get("calculation_result") or {}
        )
        status = str(result.get("status") or "")
        if status in {"insufficient_operands", "parse_error"}:
            return "reflection_replan"
        return "calc_render"

    def _build_graph(self):
        """Wire the LangGraph state machine.

        Read this top-to-bottom as the canonical execution order. The mixins
        implement the node bodies; this method only owns routing.
        """
        from langgraph.graph import END, StateGraph

        graph = StateGraph(_financial_agent_state_model())

        # Planning and retrieval
        graph.add_node("classify", self._classify_query)
        graph.add_node("extract", self._extract_entities)
        graph.add_node("pre_calc_planner", self._plan_semantic_numeric_tasks)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("expand", self._expand_via_structure_graph)

        # Evidence / numeric extraction
        graph.add_node("numeric_extractor", self._extract_numeric_fact)
        graph.add_node("evidence", self._extract_evidence)
        graph.add_node("reconcile_plan", self._reconcile_retrieved_evidence)

        # Calculation subgraph
        graph.add_node("operand_extractor", self._extract_calculation_operands)
        graph.add_node("formula_planner", self._plan_formula_calculation)
        graph.add_node("reflection_replan", self._plan_reflection_retry)
        graph.add_node("prepare_retry", self._prepare_reflection_retry)
        graph.add_node("calculator", self._execute_calculation)
        graph.add_node("calc_render", self._render_calculation_answer)
        graph.add_node("calc_verify", self._verify_calculation_answer)
        graph.add_node("advance_subtask", self._advance_calculation_subtask)
        graph.add_node("aggregate_subtasks", self._aggregate_calculation_subtasks)

        # Narrative answer path
        graph.add_node("compress", self._compress_answer)
        graph.add_node("validate", self._validate_answer)
        graph.add_node("cite", self._format_citations)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "extract")
        graph.add_edge("extract", "pre_calc_planner")
        graph.add_edge("pre_calc_planner", "retrieve")
        graph.add_edge("retrieve", "expand")
        graph.add_conditional_edges(
            "expand",
            self._route_after_expand,
            {"numeric_extractor": "numeric_extractor", "evidence": "evidence"},
        )
        graph.add_conditional_edges(
            "numeric_extractor",
            self._route_after_numeric_extractor,
            {"reconcile_plan": "reconcile_plan", "advance_subtask": "advance_subtask", "cite": "cite"},
        )
        graph.add_conditional_edges(
            "evidence",
            self._route_after_evidence,
            {"reconcile_plan": "reconcile_plan", "compress": "compress"},
        )
        graph.add_conditional_edges(
            "reconcile_plan",
            self._route_after_reconcile_plan,
            {"operand_extractor": "operand_extractor", "retrieve": "retrieve", "advance_subtask": "advance_subtask"},
        )
        graph.add_edge("operand_extractor", "formula_planner")
        graph.add_conditional_edges(
            "formula_planner",
            self._route_after_formula_planner,
            {"reflection_replan": "reflection_replan", "calculator": "calculator"},
        )
        graph.add_edge("reflection_replan", "prepare_retry")
        graph.add_conditional_edges(
            "prepare_retry",
            self._route_after_prepare_retry,
            {"operand_extractor": "operand_extractor", "retrieve": "retrieve"},
        )
        graph.add_conditional_edges(
            "calculator",
            self._route_after_calculator,
            {"reflection_replan": "reflection_replan", "calc_render": "calc_render"},
        )
        graph.add_edge("calc_render", "calc_verify")
        graph.add_edge("calc_verify", "advance_subtask")
        graph.add_conditional_edges(
            "advance_subtask",
            self._route_after_advance_subtask,
            {
                "reconcile_plan": "reconcile_plan",
                "retrieve": "retrieve",
                "evidence": "evidence",
                "aggregate_subtasks": "aggregate_subtasks",
            },
        )
        graph.add_conditional_edges(
            "aggregate_subtasks",
            self._route_after_aggregate_subtasks,
            {"pre_calc_planner": "pre_calc_planner", "cite": "cite"},
        )
        graph.add_edge("compress", "validate")
        graph.add_conditional_edges(
            "validate",
            self._route_after_validate,
            {"advance_subtask": "advance_subtask", "cite": "cite"},
        )
        graph.add_edge("cite", END)

        return graph.compile()

    def _repair_public_runtime_calculation_trace(
        self,
        final: Dict[str, Any],
        runtime_calculation_trace: RuntimeCalculationTrace,
        *,
        public_answer: str,
        runtime_evidence: Optional[list[Dict[str, Any]]] = None,
    ) -> RuntimeCalculationTrace:
        projection_state = public_projection_state(
            final,
            public_answer=public_answer,
            runtime_calculation_trace=runtime_calculation_trace,
            runtime_evidence=runtime_evidence,
        )
        repaired = repair_collapsed_ratio_trace_from_evidence(
            projection_state,
            runtime_calculation_trace,
        )
        return self._repair_period_comparison_trace_from_evidence(
            projection_state,
            repaired,
        )

    def run(self, query: str, *, report_scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the graph and return a stable caller-facing payload."""
        usage_callback = getattr(self, "llm_usage_callback", None)
        if usage_callback is not None:
            usage_callback.reset_current_thread()
        vsm = getattr(self, "vsm", None)
        reset_embedding_usage = getattr(vsm, "reset_current_thread_embedding_usage", None)
        if callable(reset_embedding_usage):
            reset_embedding_usage()
        initial: FinancialAgentState = {
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
        final = self.graph.invoke(initial)
        llm_usage = usage_callback.snapshot_current_thread() if usage_callback is not None else {}
        llm_usage_by_phase = (
            usage_callback.snapshot_current_thread_by_phase() if usage_callback is not None else {}
        )
        embedding_snapshot = getattr(vsm, "get_current_thread_embedding_usage_snapshot", None)
        embedding_usage = embedding_snapshot() if callable(embedding_snapshot) else {}
        runtime_calculation_trace = self._project_runtime_calculation_trace(final)
        public_answer = _normalise_spaces(str(final.get("answer") or ""))
        runtime_calculation_trace = self._repair_public_runtime_calculation_trace(
            final,
            runtime_calculation_trace,
            public_answer=public_answer,
        )
        runtime_numeric_answer = self._late_runtime_numeric_answer(
            public_projection_state(
                final,
                public_answer=public_answer,
                runtime_calculation_trace=runtime_calculation_trace,
            ),
            public_answer,
        )
        if runtime_numeric_answer:
            public_answer = runtime_numeric_answer
        final_for_evidence = with_public_answer(final, public_answer)
        runtime_evidence = self._runtime_evidence_from_retrieved_docs(final_for_evidence)
        runtime_calculation_trace = self._repair_public_runtime_calculation_trace(
            final_for_evidence,
            runtime_calculation_trace,
            public_answer=public_answer,
            runtime_evidence=runtime_evidence,
        )
        runtime_numeric_answer = self._late_runtime_numeric_answer(
            public_projection_state(
                final_for_evidence,
                public_answer=public_answer,
                runtime_calculation_trace=runtime_calculation_trace,
                runtime_evidence=runtime_evidence,
            ),
            public_answer,
        )
        if runtime_numeric_answer:
            public_answer = runtime_numeric_answer
            final_for_evidence = with_public_answer(final_for_evidence, public_answer)
        structured_result = dict(
            final.get("structured_result")
            or runtime_calculation_trace.get("calculation_result")
            or {}
        )
        structured_subtask_results, structured_base_answer = structured_result_subtask_rows_and_answer(
            structured_result
        )
        complete_aggregate_answer, complete_aggregate_projection = (
            complete_aggregate_public_answer_projection(
                subtask_results=structured_subtask_results,
                base_answer=structured_base_answer,
                public_answer=public_answer,
            )
        )
        if complete_aggregate_answer:
            public_answer = complete_aggregate_answer
            final_for_evidence = with_public_answer(final_for_evidence, public_answer)
            if complete_aggregate_projection:
                runtime_calculation_trace = complete_aggregate_projection
        structured_answer = structured_result_answer_for_missing_public_answer(public_answer, structured_result)
        if structured_answer:
            public_answer = structured_answer
            final_for_evidence = with_public_answer(final_for_evidence, public_answer)
        public_answer, final_for_evidence, runtime_calculation_trace = (
            self._apply_stale_structured_numeric_public_answer_repair(
                final_for_evidence,
                public_answer=public_answer,
                structured_result=structured_result,
                runtime_calculation_trace=runtime_calculation_trace,
                runtime_evidence=runtime_evidence,
            )
        )
        structured_public_projection = self._structured_public_answer_trace_projection(
            final_for_evidence,
            public_answer=public_answer,
            structured_result=structured_result,
            runtime_calculation_trace=runtime_calculation_trace,
            runtime_evidence=runtime_evidence,
        )
        if structured_public_projection:
            runtime_calculation_trace = structured_public_projection
        retrieved_ratio_projection = self._retrieved_ratio_context_projection_for_public_answer(
            final_for_evidence,
            public_answer=public_answer,
        )
        if retrieved_ratio_projection:
            runtime_calculation_trace = retrieved_ratio_projection
        runtime_calculation_trace = append_final_answer_surface_operands_from_evidence(
            runtime_calculation_trace,
            [
                *list(final_for_evidence.get("evidence_items") or []),
                *list(runtime_evidence or []),
            ],
            final_answer=public_answer,
        )
        debug_traces = project_debug_traces(final)
        citations = augment_citations_from_runtime_evidence(final["citations"], runtime_evidence)
        task_artifact_trace = _project_task_artifact_trace(
            final.get("tasks", []),
            final.get("artifacts", []),
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
            debug_traces=debug_traces,
            llm_usage=llm_usage,
            llm_usage_by_phase=llm_usage_by_phase,
            embedding_usage=embedding_usage,
        )
        return {
            **agent_answer,
            **review_trace,
            **debug_bundle,
            # Preferred named projections for new callers. Flat keys above stay
            # as the compatibility adapter for existing API/eval code.
            "agent_answer": agent_answer,
            "review_trace": review_trace,
            "debug_bundle": debug_bundle,
        }
