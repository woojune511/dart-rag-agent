"""
LangGraph-based DART financial analysis agent.

This file is intentionally thin after the refactor:
- phase-specific node implementations live in mixins
- shared pure functions live in `financial_graph_helpers.py`
- schema/state definitions live in `financial_graph_models.py`

If you need to understand the runtime at a glance, read this file first and
then jump into the mixin that owns the phase you care about.
"""

import logging
import os
import re
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_openai import ChatOpenAI
from langgraph.graph import END, StateGraph
from src.agent.financial_graph_contextual import (
    DEFAULT_CONTEXT_BATCH_SIZE,
    DEFAULT_CONTEXT_MAX_WORKERS,
    FinancialAgentContextualMixin,
)
from src.agent.financial_graph_models import (
    AgentAnswer,
    DebugBundle,
    DebugTraceBundle,
    FinancialAgentState,
    ReviewTrace,
    RuntimeCalculationTrace,
)
from src.agent.financial_numeric_surface import extract_numeric_surface_candidates
from src.config.runtime_contract import CALCULATION_DEBUG_TRACE_FIELD
from src.config.retrieval_policy import CALCULATION_NARRATIVE_POLICY, SECTION_BIAS_BY_QUERY_TYPE
from src.routing import QueryRouter
from src.utils.gemini_usage import GeminiUsageCallbackHandler

load_dotenv()
logger = logging.getLogger(__name__)
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_helpers import (
    _attach_runtime_projection_metadata,
    _project_task_artifact_trace,
    _resolve_runtime_structured_result,
)
from src.agent.financial_graph_planning import FinancialAgentPlanningMixin
from src.agent.financial_graph_reconciliation import FinancialAgentReconciliationMixin

class FinancialAgent(FinancialAgentPlanningMixin, FinancialAgentReconciliationMixin, FinancialAgentEvidenceMixin, FinancialAgentCalculationMixin, FinancialAgentContextualMixin):
    """Top-level orchestration shell for the DART single-agent workflow.

    The actual node bodies are split across mixins so this class can stay
    focused on three things:
    1. dependency wiring
    2. graph wiring
    3. input/output normalization for external callers
    """

    _SECTION_BIAS_BY_QUERY_TYPE = SECTION_BIAS_BY_QUERY_TYPE

    def _runtime_evidence_defaults(self, final: Dict[str, Any]) -> Dict[str, Any]:
        report_scope = dict(final.get("report_scope") or {})
        company = str(report_scope.get("company") or "").strip()
        if not company:
            companies = [str(value).strip() for value in (final.get("companies") or []) if str(value).strip()]
            company = companies[0] if companies else ""
        year = report_scope.get("year")
        if year in (None, ""):
            years = list(final.get("years") or [])
            year = years[0] if years else None
        return {"company": company, "year": year}

    def _compact_runtime_evidence_metadata(self, metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Keep caller-facing evidence metadata small while preserving routing signals."""
        compacted = dict(metadata or {})
        dropped_fields: list[str] = []
        always_drop = {"table_object_json", "table_value_records_json"}
        max_field_chars = 4_000
        max_structured_row_chars = 20_000
        for key in list(compacted):
            value = compacted.get(key)
            value_text = str(value or "")
            if key in always_drop:
                compacted.pop(key, None)
                dropped_fields.append(key)
                continue
            if key == "table_row_records_json":
                if len(value_text) > max_structured_row_chars:
                    compacted.pop(key, None)
                    dropped_fields.append(key)
                continue
            if len(value_text) > max_field_chars:
                compacted.pop(key, None)
                dropped_fields.append(key)
        if dropped_fields:
            compacted["metadata_compacted_fields"] = sorted(set(dropped_fields))
        return compacted

    def _enrich_runtime_evidence_metadata(
        self,
        final: Dict[str, Any],
        evidence_items: list[Dict[str, Any]],
    ) -> list[Dict[str, Any]]:
        defaults = self._runtime_evidence_defaults(final)
        enriched: list[Dict[str, Any]] = []
        for item in list(evidence_items or []):
            row = dict(item or {})
            metadata = dict(row.get("metadata") or {})
            if defaults.get("company") and not metadata.get("company"):
                metadata["company"] = defaults["company"]
            if defaults.get("year") not in (None, "") and not metadata.get("year"):
                metadata["year"] = defaults["year"]
            if not str(row.get("source_anchor") or "").strip():
                anchor = (
                    metadata.get("source_anchor")
                    or metadata.get("section_path")
                    or metadata.get("section_title")
                    or metadata.get("section")
                )
                if anchor:
                    row["source_anchor"] = _normalise_spaces(str(anchor))
            row["metadata"] = self._compact_runtime_evidence_metadata(metadata)
            enriched.append(row)
        return enriched

    def _project_debug_traces(self, final: Dict[str, Any]) -> DebugTraceBundle:
        return {"calculation": dict(final.get(CALCULATION_DEBUG_TRACE_FIELD) or {})}

    def _project_agent_answer(
        self,
        final: Dict[str, Any],
        *,
        public_answer: str,
        citations: list[str],
        structured_result: Dict[str, Any],
        runtime_calculation_trace: RuntimeCalculationTrace,
    ) -> AgentAnswer:
        return {
            "query": final["query"],
            "report_scope": final.get("report_scope", {}),
            "query_type": final["query_type"],
            "intent": final.get("intent", final["query_type"]),
            "planner_mode": final.get("planner_mode", "initial"),
            "planner_feedback": final.get("planner_feedback", ""),
            "plan_loop_count": final.get("plan_loop_count", 0),
            "target_metric_family": final.get("target_metric_family", ""),
            "target_metric_family_hint": final.get(
                "target_metric_family_hint",
                final.get("target_metric_family", ""),
            ),
            "planned_metric_families": final.get("planned_metric_families", []),
            "format_preference": final.get("format_preference", ""),
            "routing_source": final.get("routing_source", ""),
            "routing_confidence": final.get("routing_confidence", 0.0),
            "routing_scores": final.get("routing_scores", {}),
            "companies": final["companies"],
            "years": final["years"],
            "answer": public_answer,
            "citations": citations,
            "resolved_calculation_trace": runtime_calculation_trace,
            "structured_result": structured_result,
        }

    def _structured_result_answer_for_missing_public_answer(
        self,
        public_answer: str,
        structured_result: Dict[str, Any],
    ) -> str:
        answer_text = _normalise_spaces(str(public_answer or ""))
        structured_answer = _normalise_spaces(
            str(structured_result.get("formatted_result") or structured_result.get("rendered_value") or "")
        )
        if not structured_answer or structured_answer == answer_text or not re.search(r"\d", structured_answer):
            return ""
        missing_markers = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ())
            if str(item)
        )
        if not missing_markers:
            return ""
        if any(marker in answer_text for marker in missing_markers) and not any(
            marker in structured_answer for marker in missing_markers
        ):
            return structured_answer
        return ""

    def _structured_result_projection_for_stale_public_numeric_answer(
        self,
        final: Dict[str, Any],
        *,
        public_answer: str,
        structured_result: Dict[str, Any],
        evidence_items: list[Dict[str, Any]],
    ) -> tuple[str, RuntimeCalculationTrace]:
        subtask_results = [
            dict(row)
            for row in list(structured_result.get("subtask_results") or [])
            if isinstance(row, dict)
        ]
        if not subtask_results:
            return "", {}
        replacement_answer = self._complete_numeric_projection_replacement_answer(
            final_answer=public_answer,
            ordered_results=subtask_results,
            query=str(final.get("query") or ""),
            evidence_items=evidence_items,
        )
        if not replacement_answer:
            return "", {}
        if self._answer_covers_numeric_answer(public_answer, replacement_answer) and self._answer_covers_numeric_answer(
            replacement_answer,
            public_answer,
        ):
            return "", {}
        projection = _build_aggregate_calculation_projection(subtask_results, replacement_answer)
        projection_result = dict(projection.get("calculation_result") or {})
        if not projection_result.get("subtask_results"):
            return "", {}
        projection = _attach_runtime_projection_metadata(
            projection,
            source="structured_result_subtasks",
        )
        projection["runtime_projection"] = {
            **dict(projection.get("runtime_projection") or {}),
            "public_answer_repaired": True,
        }
        return replacement_answer, projection

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
                if not row_answer or not self._answer_covers_numeric_answer(answer_text, row_answer):
                    continue
            projection = self._rebuild_aggregate_projection([row], answer_text)
            projection = _attach_runtime_projection_metadata(
                projection,
                source="retrieved_ratio_context",
            )
            return projection
        return {}

    def _project_review_trace(
        self,
        final: Dict[str, Any],
        *,
        runtime_evidence: list[Dict[str, Any]],
        task_artifact_trace: Dict[str, Any],
    ) -> ReviewTrace:
        return {
            "seed_retrieved_docs": final.get("seed_retrieved_docs", []),
            "retrieved_docs": final["retrieved_docs"],
            "retrieval_debug_trace": final.get("retrieval_debug_trace", {}),
            "retrieval_debug_trace_history": final.get("retrieval_debug_trace_history", []),
            "evidence_items": runtime_evidence,
            "selected_claim_ids": final.get("selected_claim_ids", []),
            "draft_points": final.get("draft_points", []),
            "kept_claim_ids": final.get("kept_claim_ids", []),
            "dropped_claim_ids": final.get("dropped_claim_ids", []),
            "unsupported_sentences": final.get("unsupported_sentences", []),
            "sentence_checks": final.get("sentence_checks", []),
            "numeric_debug_trace": final.get("numeric_debug_trace", {}),
            "numeric_debug_trace_history": final.get("numeric_debug_trace_history", []),
            "planner_debug_trace": final.get("planner_debug_trace", {}),
            "missing_info": final.get("missing_info", []),
            "reflection_count": final.get("reflection_count", 0),
            "retry_reason": final.get("retry_reason", ""),
            "retry_strategy": final.get("retry_strategy", ""),
            "retry_queries": final.get("retry_queries", []),
            "reconciliation_retry_count": final.get("reconciliation_retry_count", 0),
            "reflection_plan": final.get("reflection_plan", {}),
            "reflection_request": final.get("reflection_request", {}),
            "reflection_action": final.get("reflection_action", {}),
            "reflection_report": final.get("reflection_report", {}),
            "semantic_plan": final.get("semantic_plan", {}),
            "calc_subtasks": final.get("calc_subtasks", []),
            "retrieval_queries": final.get("retrieval_queries", []),
            "active_subtask_index": final.get("active_subtask_index", 0),
            "active_subtask": final.get("active_subtask", {}),
            "subtask_results": final.get("subtask_results", []),
            "subtask_debug_trace": final.get("subtask_debug_trace", {}),
            "subtask_loop_complete": bool(final.get("subtask_loop_complete", False)),
            "reconciliation_result": final.get("reconciliation_result", {}),
            "tasks": final.get("tasks", []),
            "artifacts": final.get("artifacts", []),
            "task_artifact_trace": task_artifact_trace,
        }

    def _project_debug_bundle(
        self,
        *,
        debug_traces: DebugTraceBundle,
        llm_usage: Dict[str, Any],
        llm_usage_by_phase: Dict[str, Any],
        embedding_usage: Dict[str, Any],
    ) -> DebugBundle:
        return {
            "debug_traces": debug_traces,
            "llm_usage": llm_usage,
            "llm_usage_by_phase": llm_usage_by_phase,
            "embedding_usage": embedding_usage,
        }

    def _augment_citations_from_runtime_evidence(
        self,
        citations: list[str],
        runtime_evidence: list[Dict[str, Any]],
    ) -> list[str]:
        updated = [str(item).strip() for item in (citations or []) if str(item).strip()]
        seen = {_normalise_spaces(item).lower() for item in updated}
        for item in list(runtime_evidence or []):
            row = dict(item or {})
            metadata = dict(row.get("metadata") or {})
            anchor = _normalise_spaces(
                str(
                    row.get("source_anchor")
                    or metadata.get("source_anchor")
                    or metadata.get("section_path")
                    or metadata.get("section")
                    or ""
                )
            )
            if not anchor:
                continue
            company = str(metadata.get("company") or "").strip()
            year = str(metadata.get("year") or "").strip()
            citation = anchor
            if (company or year) and not anchor.startswith("["):
                citation = "[{}]".format(" | ".join(part for part in (company, year, anchor) if part))
            key = _normalise_spaces(citation).lower()
            if key in seen:
                continue
            seen.add(key)
            updated.append(citation)
        return updated

    def _runtime_evidence_from_retrieved_docs(self, final: Dict[str, Any]) -> list[Dict[str, Any]]:
        """Preserve numeric provenance when a non-calculation path produced the final answer."""
        existing = [dict(item) for item in (final.get("evidence_items") or []) if isinstance(item, dict)]
        final_answer = _normalise_spaces(str(final.get("answer") or final.get("compressed_answer") or ""))
        answer_candidates = extract_numeric_surface_candidates(final_answer) if final_answer else []
        if answer_candidates:
            projection = self._project_runtime_calculation_trace(final)
            operands = list((projection or {}).get("calculation_operands") or [])
            evidence_items = self._append_operand_evidence_for_final_answer(
                existing,
                operands=operands,
                final_answer=final_answer,
            )
            filtered = self._filter_aggregate_evidence_for_final_answer(
                evidence_items,
                final_answer=final_answer,
                selected_claim_ids=list(final.get("selected_claim_ids") or []),
            )[:8]
            if filtered:
                return self._enrich_runtime_evidence_metadata(final, filtered)
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
                    return self._enrich_runtime_evidence_metadata(final, selected_existing)
            return self._enrich_runtime_evidence_metadata(final, existing)
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
        filtered = self._filter_aggregate_evidence_for_final_answer(
            evidence_items,
            final_answer=final_answer,
            selected_claim_ids=[],
        )[:8]
        return self._enrich_runtime_evidence_metadata(final, filtered)

    def __init__(
        self,
        vector_store_manager,
        k: int = 8,
        graph_expansion_config: Optional[Dict[str, Any]] = None,
        routing_config: Optional[Dict[str, Any]] = None,
    ):
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

        self.llm_usage_callback = GeminiUsageCallbackHandler()
        self.llm_routes = self._build_llm_routes()
        self.llm = self.llm_routes.get("default")
        if self.llm is None:
            raise ValueError("Default LLM route was not initialized.")
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

    def _build_graph(self):
        """Wire the LangGraph state machine.

        Read this top-to-bottom as the canonical execution order. The mixins
        implement the node bodies; this method only owns routing.
        """
        graph = StateGraph(FinancialAgentState)

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
        runtime_calculation_trace = self._repair_collapsed_ratio_trace_from_evidence(
            final,
            runtime_calculation_trace,
        )
        runtime_calculation_trace = self._repair_period_comparison_trace_from_evidence(
            final,
            runtime_calculation_trace,
        )
        public_answer = _normalise_spaces(str(final.get("answer") or ""))
        runtime_numeric_answer = self._late_runtime_numeric_answer(
            {
                **dict(final),
                "resolved_calculation_trace": runtime_calculation_trace,
            },
            public_answer,
        )
        if runtime_numeric_answer:
            public_answer = runtime_numeric_answer
        final_for_evidence = {**dict(final), "answer": public_answer, "compressed_answer": public_answer}
        runtime_evidence = self._runtime_evidence_from_retrieved_docs(final_for_evidence)
        runtime_calculation_trace = self._repair_collapsed_ratio_trace_from_evidence(
            {
                **final_for_evidence,
                "evidence_items": [
                    *list(final_for_evidence.get("evidence_items") or []),
                    *list(runtime_evidence or []),
                ],
                "runtime_evidence": runtime_evidence,
                "resolved_calculation_trace": runtime_calculation_trace,
            },
            runtime_calculation_trace,
        )
        runtime_calculation_trace = self._repair_period_comparison_trace_from_evidence(
            {
                **final_for_evidence,
                "evidence_items": [
                    *list(final_for_evidence.get("evidence_items") or []),
                    *list(runtime_evidence or []),
                ],
                "runtime_evidence": runtime_evidence,
                "resolved_calculation_trace": runtime_calculation_trace,
            },
            runtime_calculation_trace,
        )
        runtime_numeric_answer = self._late_runtime_numeric_answer(
            {
                **dict(final_for_evidence),
                "runtime_evidence": runtime_evidence,
                "resolved_calculation_trace": runtime_calculation_trace,
            },
            public_answer,
        )
        if runtime_numeric_answer:
            public_answer = runtime_numeric_answer
            final_for_evidence = {**dict(final_for_evidence), "answer": public_answer, "compressed_answer": public_answer}
        structured_result = _resolve_runtime_structured_result(
            {
                "structured_result": final.get("structured_result", {}),
                "resolved_calculation_trace": runtime_calculation_trace,
                "calculation_result": final.get("calculation_result", {}),
            }
        )
        structured_answer = self._structured_result_answer_for_missing_public_answer(public_answer, structured_result)
        if structured_answer:
            public_answer = structured_answer
            final_for_evidence = {**dict(final_for_evidence), "answer": public_answer, "compressed_answer": public_answer}
        structured_numeric_answer, structured_numeric_projection = (
            self._structured_result_projection_for_stale_public_numeric_answer(
                final_for_evidence,
                public_answer=public_answer,
                structured_result=structured_result,
                evidence_items=runtime_evidence,
            )
        )
        if structured_numeric_answer:
            public_answer = structured_numeric_answer
            final_for_evidence = {**dict(final_for_evidence), "answer": public_answer, "compressed_answer": public_answer}
            runtime_calculation_trace = structured_numeric_projection
        structured_public_projection = self._structured_subtask_projection_for_public_answer(
            {
                **dict(final_for_evidence),
                "answer": public_answer,
                "compressed_answer": public_answer,
                "structured_result": structured_result,
                "resolved_calculation_trace": runtime_calculation_trace,
            },
            runtime_calculation_trace,
        )
        if structured_public_projection:
            runtime_calculation_trace = structured_public_projection
            runtime_calculation_trace = self._repair_collapsed_ratio_trace_from_evidence(
                {
                    **dict(final_for_evidence),
                    "evidence_items": [
                        *list(final_for_evidence.get("evidence_items") or []),
                        *list(runtime_evidence or []),
                    ],
                    "runtime_evidence": runtime_evidence,
                    "resolved_calculation_trace": runtime_calculation_trace,
                },
                runtime_calculation_trace,
            )
        retrieved_ratio_projection = self._retrieved_ratio_context_projection_for_public_answer(
            final_for_evidence,
            public_answer=public_answer,
        )
        if retrieved_ratio_projection:
            runtime_calculation_trace = retrieved_ratio_projection
        debug_traces = self._project_debug_traces(final)
        citations = self._augment_citations_from_runtime_evidence(final["citations"], runtime_evidence)
        task_artifact_trace = _project_task_artifact_trace(
            final.get("tasks", []),
            final.get("artifacts", []),
        )
        agent_answer = self._project_agent_answer(
            final,
            public_answer=public_answer,
            citations=citations,
            structured_result=structured_result,
            runtime_calculation_trace=runtime_calculation_trace,
        )
        review_trace = self._project_review_trace(
            final,
            runtime_evidence=runtime_evidence,
            task_artifact_trace=task_artifact_trace,
        )
        debug_bundle = self._project_debug_bundle(
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
            # Compatibility bridge for callers that have not moved to
            # `debug_traces.calculation` yet.
            CALCULATION_DEBUG_TRACE_FIELD: debug_traces.get("calculation", {}),
        }



if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.INFO)

    from processing.financial_parser import FinancialParser
    from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reports_dir = os.path.join(project_root, "data", "reports")
    chroma_dir = os.path.join(project_root, "data", "chroma_dart")

    target = None
    for root_dir, _dirs, files in os.walk(reports_dir):
        for filename in files:
            if filename.endswith(".html"):
                target = os.path.join(root_dir, filename)
                break
        if target:
            break

    if not target:
        print("[SKIP] data/reports/ 아래에 .html 파일이 없습니다. dart_fetcher.py를 먼저 실행하세요.")
        sys.exit(0)

    parser = FinancialParser()
    metadata = {
        "company": "삼성전자",
        "stock_code": "005930",
        "year": 2023,
        "report_type": "사업보고서",
        "rcept_no": "20230307000542",
    }
    chunks = parser.process_document(target, metadata)
    print(f"[1] parsed {len(chunks)} chunks")

    vsm = VectorStoreManager(persist_directory=chroma_dir, collection_name=DEFAULT_COLLECTION_NAME)
    agent = FinancialAgent(vsm)
    agent.ingest(chunks)
    print("[2] indexing complete")

    for question in [
        "삼성전자의 주요 리스크 요인을 알려줘.",
        "삼성전자 2023년 매출과 영업이익은?",
    ]:
        result = agent.run(question)
        print(f"\nQ: {question}")
        print(f"type: {result['query_type']} | companies: {result['companies']} | years: {result['years']}")
        print(result["answer"][:500])
        print(result["citations"][:3])
