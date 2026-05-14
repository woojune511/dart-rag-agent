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
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from src.agent.financial_graph_contextual import (
    DEFAULT_CONTEXT_BATCH_SIZE,
    DEFAULT_CONTEXT_MAX_WORKERS,
    FinancialAgentContextualMixin,
)
from src.agent.financial_graph_models import FinancialAgentState
from src.routing import QueryRouter

load_dotenv()
logger = logging.getLogger(__name__)
from src.agent.financial_graph_calculation import FinancialAgentCalculationMixin
from src.agent.financial_graph_evidence import FinancialAgentEvidenceMixin
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
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

    _SECTION_BIAS_BY_QUERY_TYPE = {
        "numeric_fact": (
            ("손익계산서", 0.08),
            ("매출 및 수주상황", 0.08),
            ("요약재무정보", 0.06),
            ("연결재무제표", 0.06),
        ),
        "comparison": (
            ("매출 및 수주상황", 0.10),
            ("연구개발 활동", 0.10),
            ("연구개발", 0.08),
            ("손익계산서", 0.08),
            ("요약재무정보", 0.10),
            ("연결재무제표", 0.06),
        ),
        "business_overview": (
            ("II. 사업의 내용 > 1. 사업의 개요", 0.14),
            ("II. 사업의 내용 > 2. 주요 제품 및 서비스", 0.10),
            ("사업의 개요", 0.06),
        ),
        "risk": (
            ("위험관리 및 파생거래", 0.18),
            ("리스크", 0.10),
        ),
        "trend": (
            ("손익계산서", 0.12),
            ("요약재무정보", 0.12),
            ("연결재무제표", 0.08),
            ("재무제표", 0.06),
        ),
    }

    def __init__(self, vector_store_manager, k: int = 8, graph_expansion_config: Optional[Dict[str, Any]] = None):
        self.vsm = vector_store_manager
        self.k = k
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

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.query_router = QueryRouter(embeddings=self.vsm.embeddings, llm=self.llm)
        self.graph = self._build_graph()

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
        graph.add_edge("numeric_extractor", "cite")
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
        graph.add_edge("prepare_retry", "retrieve")
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
            {"reconcile_plan": "reconcile_plan", "aggregate_subtasks": "aggregate_subtasks"},
        )
        graph.add_edge("aggregate_subtasks", "cite")
        graph.add_edge("compress", "validate")
        graph.add_edge("validate", "cite")
        graph.add_edge("cite", END)

        return graph.compile()

    def run(self, query: str, *, report_scope: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute the graph and return a stable caller-facing payload."""
        initial: FinancialAgentState = {
            "query": query,
            "report_scope": dict(report_scope or {}),
            "query_type": "",
            "intent": "",
            "target_metric_family": "",
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
            "calculation_operands": [],
            "calculation_plan": {},
            "calculation_result": {},
            "calculation_debug_trace": {},
            "planner_debug_trace": {},
            "missing_info": [],
            "reflection_count": 0,
            "retry_reason": "",
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
        # The runtime now stores the richest trace in the task/artifact ledger.
        # We still project legacy flat fields here while the surrounding
        # evaluator and benchmark code finishes migrating.
        legacy_projection = self._project_legacy_calculation_fields(final)
        return {
            "query": final["query"],
            "report_scope": final.get("report_scope", {}),
            "query_type": final["query_type"],
            "intent": final.get("intent", final["query_type"]),
            "target_metric_family": final.get("target_metric_family", ""),
            "format_preference": final.get("format_preference", ""),
            "routing_source": final.get("routing_source", ""),
            "routing_confidence": final.get("routing_confidence", 0.0),
            "routing_scores": final.get("routing_scores", {}),
            "companies": final["companies"],
            "years": final["years"],
            "answer": final["answer"],
            "citations": final["citations"],
            "seed_retrieved_docs": final.get("seed_retrieved_docs", []),
            "retrieved_docs": final["retrieved_docs"],
            "evidence_items": final.get("evidence_items", []),
            "selected_claim_ids": final.get("selected_claim_ids", []),
            "draft_points": final.get("draft_points", []),
            "kept_claim_ids": final.get("kept_claim_ids", []),
            "dropped_claim_ids": final.get("dropped_claim_ids", []),
            "unsupported_sentences": final.get("unsupported_sentences", []),
            "sentence_checks": final.get("sentence_checks", []),
            "numeric_debug_trace": final.get("numeric_debug_trace", {}),
            "calculation_operands": legacy_projection.get("calculation_operands", []),
            "calculation_plan": legacy_projection.get("calculation_plan", {}),
            "calculation_result": legacy_projection.get("calculation_result", {}),
            "calculation_debug_trace": final.get("calculation_debug_trace", {}),
            "planner_debug_trace": final.get("planner_debug_trace", {}),
            "missing_info": final.get("missing_info", []),
            "reflection_count": final.get("reflection_count", 0),
            "retry_reason": final.get("retry_reason", ""),
            "retry_queries": final.get("retry_queries", []),
            "reconciliation_retry_count": final.get("reconciliation_retry_count", 0),
            "reflection_plan": final.get("reflection_plan", {}),
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
