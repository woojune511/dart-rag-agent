"""
Shared state and structured-output models for the financial graph agent.
"""

from typing import Annotated, Any, Dict, List, Literal, Optional, TypedDict, Union

from pydantic import BaseModel, Field, TypeAdapter


class FinancialAgentState(TypedDict):
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
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    seed_retrieved_docs: List
    retrieved_docs: List
    retrieval_debug_trace: Dict[str, Any]
    retrieval_debug_trace_history: List[Dict[str, Any]]
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
    numeric_debug_trace: Dict[str, Any]
    resolved_calculation_trace: Dict[str, Any]
    structured_result: Dict[str, Any]
    # Legacy flat calculation fields are still mirrored inside runtime state
    # while internal nodes migrate to `resolved_calculation_trace` /
    # `structured_result`. They should not be treated as source of truth.
    calculation_operands: List[Dict[str, Any]]
    calculation_plan: Dict[str, Any]
    calculation_result: Dict[str, Any]
    calculation_debug_trace: Dict[str, Any]
    planner_debug_trace: Dict[str, Any]
    missing_info: List[str]
    reflection_count: int
    retry_reason: str
    retry_strategy: str
    retry_queries: List[str]
    reconciliation_retry_count: int
    reflection_plan: Dict[str, Any]
    semantic_plan: Dict[str, Any]
    calc_subtasks: List[Dict[str, Any]]
    retrieval_queries: List[str]
    active_subtask_index: int
    active_subtask: Dict[str, Any]
    subtask_results: List[Dict[str, Any]]
    subtask_debug_trace: Dict[str, Any]
    subtask_loop_complete: bool
    reconciliation_result: Dict[str, Any]
    tasks: List[Dict[str, Any]]
    artifacts: List[Dict[str, Any]]


class EntityExtraction(BaseModel):
    companies: List[str] = Field(default_factory=list, description="질문에 등장한 기업명 목록")
    years: List[int] = Field(default_factory=list, description="질문에 등장한 연도 목록")
    topic: str = Field(description="질문의 핵심 분석 주제")
    section_filter: Optional[str] = Field(
        default=None,
        description=(
            "관련 섹션 레이블 하나. 예: 리스크, 재무제표, 연결재무제표, 요약재무, 재무주석, "
            "사업개요, 주요제품, 원재료, 매출현황, 연구개발, 경영진단, 임원현황, 이사회, 주주현황, 계열회사. "
            "단, 두 개 이상의 서로 다른 섹션 데이터가 모두 필요한 질문(비율·비중·이익률 등 분자/분모가 다른 섹션에 있는 경우)은 None을 반환하세요."
        ),
    )


class EvidenceItem(BaseModel):
    source_anchor: str = Field(description="근거 출처 앵커. 예: [삼성전자 | 2023 | 사업의 개요]")
    parent_category: Optional[str] = Field(
        default=None,
        description=(
            "해당 근거가 속한 상위 범주 레이블. "
            "예: '시장위험', 'DS부문'. 문서에 명시된 상위 범주가 없으면 None."
        ),
    )
    claim: str = Field(description="질문에 직접적으로 도움이 되는 근거 진술")
    support_level: Literal["direct", "partial", "context"] = Field(
        description="direct=직접 근거, partial=부분 근거, context=배경 설명"
    )
    quote_span: str = Field(
        default="",
        description="원문에서 발췌한 짧은 근거 구간",
    )
    question_relevance: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="질문과의 직접 관련도",
    )
    allowed_terms: List[str] = Field(
        default_factory=list,
        description="최종 답변에서 사용해도 되는 핵심 용어 목록",
    )


class EvidenceExtraction(BaseModel):
    coverage: Literal["sufficient", "sparse", "conflicting", "missing"]
    evidence: List[EvidenceItem] = Field(default_factory=list)


class CompressionOutput(BaseModel):
    selected_claim_ids: List[str] = Field(
        default_factory=list,
        description="답변 초안에 실제로 사용한 evidence_id 목록",
    )
    draft_points: List[str] = Field(
        default_factory=list,
        description="최종 초안으로 압축하기 전 핵심 포인트 목록",
    )
    draft_answer: str = Field(
        description="structured evidence만으로 압축한 답변 초안",
    )


class NumericExtraction(BaseModel):
    period_check: str = Field(
        description="질문이 요구하는 연도/기수(예: 2024년, 당기, 제56기)를 확인하고, 문서(표)에서 해당 기간의 열을 찾았는지 설명"
    )
    consolidation_check: str = Field(
        description="질문이 요구하는 기준(연결/별도)을 확인하고, 문서의 기준과 일치하는지 판단"
    )
    unit: str = Field(
        description="해당 숫자가 있는 표나 문단에 명시된 금액 단위 (예: 원, 천원, 백만원, 억원, %)"
    )
    raw_value: str = Field(
        description="문서에서 찾은 원본 숫자 텍스트 그대로 (예: '300,870,903'). 단위 변환 금지."
    )
    final_value: str = Field(
        description="질문에 대한 최종 답변 문장. raw_value와 unit을 바탕으로 자연스러운 한국어 한 문장으로 작성."
    )


class CalculationOperand(BaseModel):
    operand_id: str = Field(description="계산용 고유 피연산자 ID. 예: op_001")
    evidence_id: str = Field(description="이 숫자가 추출된 evidence_id")
    source_anchor: str = Field(description="근거 출처 앵커")
    label: str = Field(description="피연산자의 의미 있는 레이블. 예: DX부문 매출, DS부문 매출, 2024년 영업이익")
    raw_value: str = Field(description="문서에서 읽은 원본 숫자 문자열. 예: 174조 8,877억원, 16.2, 228")
    raw_unit: str = Field(description="원본 숫자의 단위. 예: 조원, 억원, 백만원, %, 개")
    normalized_value: Optional[float] = Field(
        default=None,
        description="코드에서 다시 검증 가능한 기본 단위 값. KRW는 원, PERCENT는 퍼센트포인트, COUNT는 절대 개수 기준."
    )
    normalized_unit: Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"] = Field(
        default="UNKNOWN",
        description="정규화된 단위 계열"
    )
    period: str = Field(default="", description="이 숫자가 대응하는 기간/기수. 예: 2024년, 2023년, 당기, 전기")


class OperandExtraction(BaseModel):
    coverage: Literal["sufficient", "partial", "missing"] = Field(
        description="질문 계산에 필요한 피연산자를 충분히 찾았는지 여부"
    )
    operands: List[CalculationOperand] = Field(default_factory=list)


class FormulaVariableBinding(BaseModel):
    variable: str = Field(description="수식에서 사용할 변수명. 예: A, B, C")
    operand_id: str = Field(description="이 변수에 바인딩할 operand_id")


class CalculationPlan(BaseModel):
    status: Literal["ok", "incomplete"] = Field(
        default="ok",
        description="계산 계획이 완결되었는지 여부. 부족한 정보가 있으면 incomplete"
    )
    mode: Literal["single_value", "time_series", "none"] = Field(
        description="단일 계산인지, 시계열 계산인지, 계산 불가인지"
    )
    operation: str = Field(
        default="",
        description="평가/로그용 연산 힌트. 예: subtract, growth_rate, time_series_trend"
    )
    ordered_operand_ids: List[str] = Field(
        default_factory=list,
        description="연산 순서가 중요한 경우를 위해 순서를 보존한 피연산자 목록"
    )
    variable_bindings: List[FormulaVariableBinding] = Field(
        default_factory=list,
        description="수식에서 사용할 변수와 operand_id의 매핑"
    )
    formula: str = Field(
        default="",
        description="A, B, C ... 같은 변수만 사용한 안전한 계산식"
    )
    pairwise_formula: str = Field(
        default="",
        description="time_series 모드에서 PREV와 CURR 두 변수로 인접 시점 변화를 계산하는 식"
    )
    result_unit: str = Field(
        default="",
        description="최종 답변에 사용할 단위. 예: 억원, 원, %, 개"
    )
    operation_text: str = Field(
        default="",
        description="연산 순서를 사람이 읽을 수 있게 표현한 짧은 설명. 예: current_year - previous_year"
    )
    explanation: str = Field(
        default="",
        description="이 연산을 선택한 이유를 한 문장으로 설명"
    )
    missing_info: List[str] = Field(
        default_factory=list,
        description="계획 수립에 필요한데 현재 컨텍스트에 없는 정보 목록. 예: 2023년 연구개발비용"
    )


class ReflectionQueryPlan(BaseModel):
    status: Literal["ready", "skip"] = Field(
        default="ready",
        description="재검색 계획을 만들 수 있으면 ready, 그렇지 않으면 skip"
    )
    retry_objective: Literal[
        "find_missing_values",
        "find_direct_row",
        "resolve_binding",
        "generic_retry",
    ] = Field(
        default="generic_retry",
        description="이번 retry의 목적. 세부 연산 분류보다 재검색 목적만 나타낸다"
    )
    retry_strategy: Literal[
        "retry_retrieval",
        "synthesize_from_task_outputs",
        "stop_insufficient",
    ] = Field(
        default="retry_retrieval",
        description="실패 대응 전략. 재검색을 계속할지, 기존 task output으로 합성할지, 근거 부족으로 중단할지 선택한다.",
    )
    missing_info: List[str] = Field(
        default_factory=list,
        description="현재 컨텍스트에서 부족한 정보 조각"
    )
    subqueries: List[str] = Field(
        default_factory=list,
        description="retrieval executor가 그대로 사용할 1~3개의 재검색 쿼리"
    )
    preferred_sections: List[str] = Field(
        default_factory=list,
        description="재검색에서 우선적으로 참고할 섹션 힌트"
    )
    explanation: str = Field(
        default="",
        description="왜 이 재검색 계획을 세웠는지 한 문장 설명"
    )


NormalizedUnit = Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"]
AnswerSlotStatus = Literal["ok", "missing", "derived", "ambiguous"]


class AnswerSlotValue(BaseModel):
    status: AnswerSlotStatus = Field(
        default="ok",
        description="이 슬롯 값의 상태. missing이면 synthesizer/evaluator가 재료 부족으로 해석한다.",
    )
    role: str = Field(default="", description="slot role. 예: primary_value, current_value, prior_value")
    label: str = Field(default="", description="사용자 친화적 값 레이블")
    concept: str = Field(default="", description="ontology concept key")
    period: str = Field(default="", description="이 값이 대응하는 기간 라벨")
    raw_value: str = Field(default="", description="원문에서 읽은 원본 숫자 문자열")
    raw_unit: str = Field(default="", description="원문에서 읽은 원본 단위")
    normalized_value: Optional[float] = Field(default=None, description="정규화된 숫자 값")
    normalized_unit: NormalizedUnit = Field(default="UNKNOWN", description="정규화된 단위 계열")
    rendered_value: str = Field(default="", description="답변 렌더링에 바로 쓸 수 있는 값 표현")
    source_row_id: str = Field(default="", description="대표 source row/candidate id")
    source_row_ids: List[str] = Field(default_factory=list, description="이 값의 출처 row/candidate id 목록")
    source_anchor: str = Field(default="", description="대표 evidence source anchor")


class BaseAnswerSlots(BaseModel):
    metric_label: str = Field(default="", description="이 result slot 집합이 대응하는 metric label")
    components_by_role: Dict[str, List[AnswerSlotValue]] = Field(
        default_factory=dict,
        description="역할별 피연산자/구성요소 슬롯",
    )
    components_by_group: Dict[str, List[AnswerSlotValue]] = Field(
        default_factory=dict,
        description="역할 group별 피연산자/구성요소 슬롯",
    )
    source_row_ids: List[str] = Field(default_factory=list, description="이 result 전체를 지지하는 source row/candidate ids")


class LookupAnswerSlots(BaseAnswerSlots):
    operation_family: Literal["lookup"] = "lookup"
    primary_value: AnswerSlotValue


class SingleValueAnswerSlots(BaseAnswerSlots):
    operation_family: Literal["single_value"] = "single_value"
    primary_value: AnswerSlotValue


class DifferenceAnswerSlots(BaseAnswerSlots):
    operation_family: Literal["difference"] = "difference"
    primary_value: AnswerSlotValue
    current_value: AnswerSlotValue
    prior_value: AnswerSlotValue
    delta_value: AnswerSlotValue
    direction: Optional[Literal["increase", "decrease", "flat"]] = Field(default=None)


class GrowthRateAnswerSlots(BaseAnswerSlots):
    operation_family: Literal["growth_rate"] = "growth_rate"
    primary_value: AnswerSlotValue
    current_value: AnswerSlotValue
    prior_value: AnswerSlotValue
    direction: Optional[Literal["increase", "decrease", "flat"]] = Field(default=None)


class RatioAnswerSlots(BaseAnswerSlots):
    operation_family: Literal["ratio"] = "ratio"
    primary_value: AnswerSlotValue


class SumAnswerSlots(BaseAnswerSlots):
    operation_family: Literal["sum"] = "sum"
    primary_value: AnswerSlotValue


class AggregateSubtaskAnswerSlots(BaseModel):
    task_id: str = Field(default="")
    metric_family: str = Field(default="")
    metric_label: str = Field(default="")
    operation_family: str = Field(default="")
    answer: str = Field(default="")
    answer_slots: Dict[str, Any] = Field(default_factory=dict)
    rendered_value: str = Field(default="")
    source_row_ids: List[str] = Field(default_factory=list)


class AggregateAnswerSlots(BaseModel):
    operation_family: Literal["aggregate_subtasks"] = "aggregate_subtasks"
    subtask_results: List[AggregateSubtaskAnswerSlots] = Field(default_factory=list)


AnswerSlotsPayload = Annotated[
    Union[
        LookupAnswerSlots,
        SingleValueAnswerSlots,
        DifferenceAnswerSlots,
        GrowthRateAnswerSlots,
        RatioAnswerSlots,
        SumAnswerSlots,
        AggregateAnswerSlots,
    ],
    Field(discriminator="operation_family"),
]

_ANSWER_SLOTS_ADAPTER = TypeAdapter(AnswerSlotsPayload)


def validate_answer_slots_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    validated = _ANSWER_SLOTS_ADAPTER.validate_python(payload)
    return validated.model_dump()


class CalculationResult(BaseModel):
    status: Literal["ok", "insufficient_operands", "zero_division", "unsupported_operation", "unit_mismatch", "parse_error"] = Field(
        description="계산 수행 상태"
    )
    result_value: Optional[float] = Field(default=None, description="정규화 단위 기준 계산 결과")
    result_unit: str = Field(default="", description="최종 답변 단위")
    rendered_value: str = Field(default="", description="사용자 응답에 들어갈 값 표현")
    formatted_result: str = Field(default="", description="프레젠테이션 계층에서 바로 사용할 수 있는 렌더링 결과")
    series: List[Dict[str, Any]] = Field(default_factory=list, description="기간/항목별 계산 입력 시계열 또는 순서 데이터")
    current_value: Optional[float] = Field(default=None, description="현재 기간 정규화 값")
    prior_value: Optional[float] = Field(default=None, description="직전 기간 정규화 값")
    delta_value: Optional[float] = Field(default=None, description="증감 계산 결과 정규화 값")
    current_period: str = Field(default="", description="현재 기간 라벨")
    prior_period: str = Field(default="", description="직전 기간 라벨")
    source_row_ids: List[str] = Field(default_factory=list, description="결과를 만든 evidence row/candidate id")
    answer_slots: Dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "renderer/synthesizer/evaluator가 공통으로 읽는 answer-friendly structured result slots. "
            "typed union으로 검증된 payload를 dict로 직렬화해 저장한다. "
            "예: primary_value, current_value, prior_value, delta_value, components_by_role"
        ),
    )
    derived_metrics: Dict[str, Any] = Field(default_factory=dict, description="계산 과정에서 파생된 보조 지표")
    explanation: str = Field(default="", description="계산 또는 실패 이유 설명")


class CalculationRenderOutput(BaseModel):
    final_answer: str = Field(description="CalculationResult와 operand labels만 사용해 작성한 최종 답변")


class CalculationVerificationOutput(BaseModel):
    verdict: Literal["keep", "rewrite", "fallback"] = Field(
        description="현재 계산 답변을 유지할지, 짧게 고쳐쓸지, deterministic fallback으로 돌릴지"
    )
    issues: List[str] = Field(
        default_factory=list,
        description="발견한 문제 목록. 예: wrong_unit, wrong_direction, extra_claim"
    )
    final_answer: str = Field(
        description="검증 후 최종 사용자 답변"
    )


class AggregateSynthesisOutput(BaseModel):
    final_answer: str = Field(
        description="원본 질문과 subtask 결과를 종합해 작성한 최종 답변"
    )
    planner_feedback: str = Field(
        default="",
        description="현재 재료만으로는 원본 질문을 완전히 충족하지 못할 때 planner가 추가로 모아야 할 재료를 한 문장으로 설명"
    )


class OperandRequirement(BaseModel):
    label: str = Field(description="찾아야 하는 피연산자 대표 라벨")
    concept: str = Field(default="", description="ontology concept key")
    aliases: List[str] = Field(default_factory=list, description="허용 가능한 동의어/대체 라벨")
    keywords: List[str] = Field(default_factory=list, description="추가 검색/정합성 판단용 키워드")
    role: str = Field(default="", description="numerator, denominator 등 역할")
    required: bool = Field(default=True, description="반드시 필요한 피연산자인지 여부")
    period_hint: str = Field(default="", description="특정 연도/기간 힌트가 있으면 기록")
    preferred_sections: List[str] = Field(default_factory=list, description="concept-level preferred sections")
    preferred_statement_types: List[str] = Field(default_factory=list, description="concept-level preferred statement types")
    binding_policy: Dict[str, Any] = Field(default_factory=dict, description="concept-level structured value binding preferences")


class TaskConstraints(BaseModel):
    consolidation_scope: str = Field(default="unknown")
    period_focus: str = Field(default="unknown")
    entity_scope: str = Field(default="unknown")
    segment_scope: str = Field(default="none")


class TaskInputBinding(BaseModel):
    role: str = Field(default="", description="consumer operand role. 예: current_period, prior_period")
    concept: str = Field(default="", description="required ontology concept key")
    period: str = Field(default="", description="required period hint. 예: 2023, 2022")
    label: str = Field(default="", description="human-friendly input label")
    preferred_task_id: str = Field(default="", description="이 입력을 우선 채워야 하는 producer task id")
    source_slot: str = Field(default="primary_value", description="producer answer_slots에서 읽을 slot 이름")
    source_preference: List[str] = Field(
        default_factory=lambda: ["retrieval"],
        description="입력 해석 우선순위. 예: task_output, retrieval",
    )
    segment_label: str = Field(default="", description="segment/entity-scoped binding label")


class TaskOutputSlot(BaseModel):
    slot: str = Field(default="primary_value", description="producer answer_slots slot name")
    role: str = Field(default="", description="producer operand role or semantic slot role")
    concept: str = Field(default="", description="produced ontology concept key")
    period: str = Field(default="", description="produced period hint. 예: 2023")
    label: str = Field(default="", description="human-friendly produced label")
    segment_label: str = Field(default="", description="segment/entity-scoped output label")


class RetrievalTask(BaseModel):
    task_id: str
    metric_family: str
    metric_label: str
    query: str
    operation_family: str = Field(default="", description="ratio, sum, difference, growth_rate 같은 planner-level generic operation")
    required_operands: List[OperandRequirement] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list, description="producer task ids that should complete before this task")
    inputs: List[TaskInputBinding] = Field(default_factory=list, description="typed consumer input bindings")
    produces: List[TaskOutputSlot] = Field(default_factory=list, description="typed task output slots available to downstream tasks")
    preferred_statement_types: List[str] = Field(default_factory=list)
    preferred_sections: List[str] = Field(default_factory=list)
    retrieval_queries: List[str] = Field(default_factory=list)
    constraints: TaskConstraints = Field(default_factory=TaskConstraints)


class ConceptPlannerOperand(BaseModel):
    concept: str = Field(description="ontology concept key")
    role: str = Field(default="", description="numerator_1, denominator_1, addend_1, current_period 등")


class ConceptPlannerTask(BaseModel):
    metric_label: str = Field(default="", description="사용자에게 보일 계산 라벨")
    operation_family: Literal["lookup", "sum", "difference", "ratio", "growth_rate", "single_value", "none"] = Field(
        default="none"
    )
    operands: List[ConceptPlannerOperand] = Field(default_factory=list)


class ConceptPlannerOutput(BaseModel):
    companies: List[str] = Field(default_factory=list, description="planner가 질문에서 파악한 기업명 목록")
    years: List[int] = Field(default_factory=list, description="planner가 질문에서 파악한 연도 목록")
    topic: str = Field(default="", description="planner가 정리한 핵심 주제")
    section_filter: Optional[str] = Field(default=None, description="planner가 추론한 주요 섹션 힌트")
    tasks: List[ConceptPlannerTask] = Field(default_factory=list)
    rationale: str = Field(default="", description="planner가 이렇게 분해한 이유")


class SemanticPlan(BaseModel):
    status: Literal[
        "ok",
        "needs_clarification",
        "fallback_general_search",
        "heuristic_fallback",
        "concept_fallback",
    ] = Field(default="ok")
    fallback_to_general_search: bool = Field(default=False)
    planned_metric_families: List[str] = Field(
        default_factory=list,
        description="실제로 계획된 subtask metric family 목록. multi-metric 질문에서는 이 필드를 source of truth로 본다.",
    )
    tasks: List[RetrievalTask] = Field(default_factory=list)
    planner_notes: List[str] = Field(default_factory=list)


class ReconciliationCandidateRerank(BaseModel):
    ordered_candidate_ids: List[str] = Field(
        default_factory=list,
        description="질문과 operand에 가장 잘 맞는 candidate_id를 best-first 순서로 정렬한 목록",
    )
    rationale: str = Field(default="", description="선택 이유를 간단히 설명")


class ValidationOutput(BaseModel):
    kept_claim_ids: List[str] = Field(
        default_factory=list,
        description="검증 후 최종 답변에 남긴 evidence_id 목록",
    )
    dropped_claim_ids: List[str] = Field(
        default_factory=list,
        description="검증 과정에서 제거한 evidence_id 목록",
    )
    unsupported_sentences: List[str] = Field(
        default_factory=list,
        description="근거 부족 또는 과잉 설명으로 제거한 문장 목록",
    )
    sentence_checks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="문장별 검증 결과. sentence, verdict, reason, supporting_claim_ids를 포함",
    )
    final_answer: str = Field(
        description="검증을 거친 최종 답변",
    )
