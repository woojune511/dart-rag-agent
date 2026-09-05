"""Lightweight TypedDict state contracts for the financial graph agent."""

from typing import Any, Dict, List, Literal, NotRequired, Optional, TypedDict

from src.agent.financial_runtime_contracts import CompilationEnvelopeV2


class RuntimeProjectionMetadata(TypedDict, total=False):
    source: str
    legacy_fallback: bool
    source_task_id: str


class RuntimeCalculationTrace(TypedDict, total=False):
    calculation_operands: List[Dict[str, Any]]
    calculation_plan: Dict[str, Any]
    calculation_result: Dict[str, Any]
    report_cache_candidate: Dict[str, Any]
    runtime_projection: RuntimeProjectionMetadata


class DebugTraceBundle(TypedDict, total=False):
    calculation: Dict[str, Any]


class AgentAnswer(TypedDict, total=False):
    query: str
    report_scope: Dict[str, Any]
    query_type: str
    intent: str
    planner_mode: str
    planner_feedback: str
    plan_loop_count: int
    target_metric_family: str
    target_metric_family_hint: str
    planned_metric_families: List[str]
    format_preference: str
    routing_source: str
    routing_confidence: float
    routing_scores: Dict[str, float]
    routing_degraded_reason: str
    retrieval_status: Dict[str, Any]
    companies: List[str]
    years: List[int]
    answer: str
    citations: List[str]
    structured_result: Dict[str, Any]
    resolved_calculation_trace: RuntimeCalculationTrace


class DebugBundle(TypedDict, total=False):
    debug_traces: DebugTraceBundle
    llm_usage: Dict[str, Any]
    llm_usage_by_phase: Dict[str, Any]
    embedding_usage: Dict[str, Any]


class TaskResultRecord(TypedDict, total=False):
    task_id: str
    metric_family: str
    metric_label: str
    status: str
    answer: str
    calculation_operands: List[Dict[str, Any]]
    calculation_plan: Dict[str, Any]
    calculation_result: Dict[str, Any]
    runtime_evidence: List[Dict[str, Any]]
    selected_claim_ids: List[str]


ReflectionRetryStrategy = Literal[
    "retry_retrieval",
    "synthesize_from_task_outputs",
    "stop_insufficient",
]


class ReflectionRequest(TypedDict, total=False):
    query: str
    active_task_id: str
    failure_status: str
    missing_info: List[str]
    runtime_trace_summary: Dict[str, Any]
    evidence_summary: Dict[str, Any]
    remaining_retry_budget: int


class ReflectionPlanRecord(TypedDict, total=False):
    status: str
    retry_objective: str
    retry_strategy: ReflectionRetryStrategy
    missing_info: List[str]
    subqueries: List[str]
    preferred_sections: List[str]
    explanation: str


class ReflectionAction(TypedDict, total=False):
    action_type: ReflectionRetryStrategy
    retry_queries: List[str]
    retrieval_scope_hints: List[str]
    synthesis_source_ids: List[str]
    stop_reason: str


class ReflectionReport(TypedDict, total=False):
    outcome: str
    action_taken: str
    budget_consumed: int
    target_task_ids: List[str]
    target_artifact_ids: List[str]
    blocking_issues: List[Dict[str, Any]]


class ReviewTrace(TypedDict, total=False):
    seed_retrieved_docs: List[Any]
    retrieved_docs: List[Any]
    retrieval_debug_trace: Dict[str, Any]
    retrieval_debug_trace_history: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    selected_claim_ids: List[str]
    draft_points: List[str]
    kept_claim_ids: List[str]
    dropped_claim_ids: List[str]
    unsupported_sentences: List[str]
    sentence_checks: List[Dict[str, Any]]
    numeric_debug_trace: Dict[str, Any]
    numeric_debug_trace_history: List[Dict[str, Any]]
    planner_debug_trace: Dict[str, Any]
    missing_info: List[str]
    reflection_count: int
    retry_reason: str
    retry_strategy: str
    retry_queries: List[str]
    reconciliation_retry_count: int
    reflection_plan: Dict[str, Any]
    reflection_request: ReflectionRequest
    reflection_action: ReflectionAction
    reflection_report: ReflectionReport
    semantic_plan: Dict[str, Any]
    answer_obligations: List[Dict[str, Any]]
    semantic_candidate_catalog: List[Dict[str, Any]]
    semantic_program: Dict[str, Any]
    semantic_program_validation: Dict[str, Any]
    semantic_program_retry_count: int
    calc_subtasks: List[Dict[str, Any]]
    retrieval_queries: List[str]
    active_subtask_index: int
    active_subtask: Dict[str, Any]
    subtask_results: List[TaskResultRecord]
    subtask_debug_trace: Dict[str, Any]
    subtask_loop_complete: bool
    reconciliation_result: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    task_artifact_trace: Dict[str, Any]


class RoutingState(TypedDict):
    query: str
    report_scope: Dict[str, Any]
    query_type: str
    intent: str
    planner_mode: str
    planner_feedback: str
    plan_loop_count: int
    target_metric_family: str
    target_metric_family_hint: str
    planned_metric_families: List[str]
    format_preference: str
    routing_source: str
    routing_confidence: float
    routing_scores: Dict[str, float]
    routing_degraded_reason: str
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]


class RetrievalState(TypedDict):
    seed_retrieved_docs: List
    retrieved_docs: List
    retrieval_debug_trace: Dict[str, Any]
    retrieval_debug_trace_history: List[Dict[str, Any]]
    retrieval_query_result_cache: NotRequired[Dict[str, Dict[str, Any]]]


class EvidenceState(TypedDict):
    evidence_bullets: List[str]
    evidence_items: List[Dict[str, Any]]
    evidence_status: str
    selected_claim_ids: List[str]
    draft_points: List[str]
    compressed_answer: str
    kept_claim_ids: List[str]
    dropped_claim_ids: List[str]
    unsupported_sentences: List[str]
    sentence_checks: List[Dict[str, Any]]
    answer: str
    citations: List[str]


class CalculationState(TypedDict):
    numeric_debug_trace: Dict[str, Any]
    numeric_debug_trace_history: List[Dict[str, Any]]
    resolved_calculation_trace: RuntimeCalculationTrace
    structured_result: Dict[str, Any]
    calculation_debug_trace: NotRequired[Dict[str, Any]]
    debug_traces: NotRequired[DebugTraceBundle]
    planner_debug_trace: Dict[str, Any]
    semantic_plan: Dict[str, Any]
    answer_obligations: List[Dict[str, Any]]
    semantic_candidate_catalog: List[Dict[str, Any]]
    semantic_program: Dict[str, Any]
    semantic_program_validation: Dict[str, Any]
    semantic_compilation_envelope: NotRequired[CompilationEnvelopeV2]
    semantic_program_retry_count: int
    calc_subtasks: List[Dict[str, Any]]
    retrieval_queries: List[str]
    active_subtask_index: int
    active_subtask: Dict[str, Any]
    subtask_results: List[TaskResultRecord]
    subtask_debug_trace: Dict[str, Any]
    subtask_loop_complete: bool
    reconciliation_result: Dict[str, Any]


class ReflectionState(TypedDict):
    missing_info: List[str]
    reflection_count: int
    retry_reason: str
    retry_strategy: str
    retry_queries: List[str]
    reconciliation_retry_count: int
    reflection_plan: Dict[str, Any]
    reflection_request: NotRequired[ReflectionRequest]
    reflection_action: NotRequired[ReflectionAction]
    reflection_report: NotRequired[ReflectionReport]
    replan_blocked_reason: NotRequired[str]


class LedgerState(TypedDict):
    tasks: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]


class RequestPhase(TypedDict):
    query: str
    report_scope: Dict[str, Any]


class LedgerSnapshot(TypedDict, total=False):
    tasks: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]
    task_artifact_trace: Dict[str, Any]


class RoutingPhase(TypedDict, total=False):
    query_type: str
    intent: str
    format_preference: str
    routing_source: str
    routing_confidence: float
    routing_scores: Dict[str, float]
    routing_degraded_reason: str
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    target_metric_family: str
    target_metric_family_hint: str


class RequirementsPhase(TypedDict, total=False):
    semantic_plan: Dict[str, Any]
    answer_obligations: List[Dict[str, Any]]
    planner_mode: str
    planner_feedback: str
    plan_loop_count: int
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    calc_subtasks: List[Dict[str, Any]]
    planned_metric_families: List[str]
    retrieval_queries: List[str]
    active_subtask_index: int
    active_subtask: Dict[str, Any]
    subtask_results: List[TaskResultRecord]
    subtask_debug_trace: Dict[str, Any]
    subtask_loop_complete: bool


class RetrievalPhase(TypedDict, total=False):
    seed_retrieved_docs: List[Any]
    retrieved_docs: List[Any]
    retrieval_debug_trace: Dict[str, Any]
    retrieval_debug_trace_history: List[Dict[str, Any]]
    retrieval_query_result_cache: Dict[str, Dict[str, Any]]


class CandidatesPhase(TypedDict):
    semantic_source_candidates: List[Dict[str, Any]]
    semantic_candidate_catalog: List[Dict[str, Any]]
    semantic_candidate_catalog_prebuilt: bool


class CompilationPhase(TypedDict, total=False):
    semantic_program: Dict[str, Any]
    semantic_program_validation: Dict[str, Any]
    semantic_compilation_envelope: CompilationEnvelopeV2
    semantic_program_retry_count: int
    planner_debug_trace: Dict[str, Any]
    resolved_calculation_trace: RuntimeCalculationTrace
    calculation_debug_trace: Dict[str, Any]
    missing_info: List[str]


class SemanticExecutionResult(TypedDict, total=False):
    status: str
    outputs: List[Dict[str, Any]]
    outputs_by_obligation: Dict[str, Dict[str, Any]]
    missing_obligation_ids: List[str]
    selected_candidate_ids: List[str]
    calculation_operands: List[Dict[str, Any]]
    calculation_result: Dict[str, Any]
    validation: Dict[str, Any]
    execution_errors: List[Dict[str, Any]]


class NumericResultPhase(TypedDict):
    execution: SemanticExecutionResult
    calculation_plan: Dict[str, Any]
    evidence_items: List[Dict[str, Any]]


class NarrativeResultPhase(TypedDict, total=False):
    evidence_items: List[Dict[str, Any]]
    evidence_status: str
    selected_claim_ids: List[str]
    draft_points: List[str]
    validated_sentences: List[str]
    sentence_checks: List[Dict[str, Any]]
    kept_claim_ids: List[str]
    dropped_claim_ids: List[str]
    unsupported_sentences: List[str]
    calculation_projection: RuntimeCalculationTrace


class FinalResultPhase(TypedDict):
    agent_answer: AgentAnswer
    review_trace: ReviewTrace
    debug_traces: DebugTraceBundle
    selected_claim_ids: List[str]
    kept_claim_ids: List[str]


class RoutingInput(RequestPhase):
    pass


class PlanningInput(RequestPhase, total=False):
    query_type: str
    intent: str
    format_preference: str
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    plan_loop_count: int


class RetrievalInput(PlanningInput, total=False):
    semantic_plan: Dict[str, Any]
    answer_obligations: List[Dict[str, Any]]
    active_subtask: Dict[str, Any]
    retrieval_queries: List[str]


class CandidateInput(TypedDict):
    retrieved_docs: List[Any]
    seed_retrieved_docs: List[Any]
    evidence_items: List[Dict[str, Any]]


class CompilationInput(RequestPhase, total=False):
    answer_obligations: List[Dict[str, Any]]
    semantic_plan: Dict[str, Any]
    active_subtask: Dict[str, Any]
    semantic_source_candidates: List[Dict[str, Any]]
    semantic_candidate_catalog: List[Dict[str, Any]]
    semantic_candidate_catalog_prebuilt: bool
    retrieved_docs: List[Any]
    seed_retrieved_docs: List[Any]
    retrieval_debug_trace: Dict[str, Any]


class NumericExecutionInput(RequestPhase, total=False):
    answer_obligations: List[Dict[str, Any]]
    active_subtask: Dict[str, Any]
    semantic_candidate_catalog: List[Dict[str, Any]]
    semantic_program: Dict[str, Any]
    semantic_compilation_envelope: CompilationEnvelopeV2
    resolved_calculation_trace: RuntimeCalculationTrace


class NarrativeInput(TypedDict, total=False):
    query: str
    query_type: str
    intent: str
    format_preference: str
    topic: str
    semantic_plan: Dict[str, Any]
    active_subtask: Dict[str, Any]
    retrieved_docs: List[Any]
    evidence_items: List[Dict[str, Any]]
    evidence_bullets: List[str]
    evidence_status: str
    selected_claim_ids: List[str]
    draft_points: List[str]
    compressed_answer: str


class FinancialAgentStateV2(TypedDict, total=False):
    """Graph state with one top-level writer for every runtime phase."""

    request: RequestPhase
    routing: RoutingPhase
    requirements: RequirementsPhase
    retrieval: RetrievalPhase
    candidates: CandidatesPhase
    compilation: CompilationPhase
    numeric_result: NumericResultPhase
    narrative_result: NarrativeResultPhase
    final_result: FinalResultPhase
    ledger: LedgerSnapshot


class RoutingUpdate(TypedDict):
    routing: RoutingPhase


class RequirementsUpdate(TypedDict):
    requirements: RequirementsPhase


class RetrievalUpdate(TypedDict):
    retrieval: RetrievalPhase


class CandidatesUpdate(TypedDict):
    candidates: CandidatesPhase


class CompilationUpdate(TypedDict):
    compilation: CompilationPhase


class NumericResultUpdate(TypedDict):
    numeric_result: NumericResultPhase


class NarrativeResultUpdate(TypedDict):
    narrative_result: NarrativeResultPhase


class FinalResultUpdate(TypedDict):
    final_result: FinalResultPhase


class LedgerUpdate(TypedDict):
    ledger: LedgerSnapshot


class FinancialAgentState(
    RoutingState,
    RetrievalState,
    EvidenceState,
    CalculationState,
    ReflectionState,
    LedgerState,
):
    pass
