"""Structured-output models for narrative evidence and semantic calculation programs."""

import hashlib
from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


_SEMANTIC_COUPLING_KEY_MAX_CHARS = 128


def _bounded_semantic_coupling_key(value: Any) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= _SEMANTIC_COUPLING_KEY_MAX_CHARS:
        return text
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    prefix_length = _SEMANTIC_COUPLING_KEY_MAX_CHARS - len(digest) - 1
    return f"{text[:prefix_length]}:{digest}"


class _DeferredBaseModel(BaseModel):
    model_config = ConfigDict(defer_build=True)


class EvidenceItem(_DeferredBaseModel):
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


class EvidenceExtraction(_DeferredBaseModel):
    coverage: Literal["sufficient", "sparse", "conflicting", "missing"]
    evidence: List[EvidenceItem] = Field(default_factory=list)


class CompressionOutput(_DeferredBaseModel):
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


class AnswerObligationScope(_DeferredBaseModel):
    """Semantic scope that every grounded answer obligation must preserve."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    company: str = ""
    period: str = ""
    consolidation_scope: Literal["consolidated", "separate", "unknown"] = "unknown"
    segment: str = ""
    basis: str = ""


class SemanticTargetV1(_DeferredBaseModel):
    """Typed semantic identity used to admit evidence for one owner."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    local_subjects: List[str] = Field(
        default_factory=list,
        description=(
            "Entities whose local row or sentence is requested. These are distinct "
            "from the filing company in scope.company."
        ),
    )
    concept_keys: List[str] = Field(
        default_factory=list,
        description="Ontology concept keys that describe the requested metric.",
    )
    metric_surfaces: List[str] = Field(
        default_factory=list,
        description="Query-visible metric phrases preserved when no ontology key is exact.",
    )


class EvidenceRequirement(_DeferredBaseModel):
    """One non-rendered evidence input required to produce an answer obligation."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    requirement_id: str = ""
    label: str
    required: bool = True
    scope: AnswerObligationScope = Field(default_factory=AnswerObligationScope)
    retrieval_hints: List[str] = Field(default_factory=list)
    concept_hints: List[str] = Field(default_factory=list)
    semantic_target: SemanticTargetV1 = Field(default_factory=SemanticTargetV1)


class AnswerObligation(_DeferredBaseModel):
    """One user-visible output requirement, independent of an operation taxonomy."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str = ""
    kind: Literal["direct_value", "derived_value", "narrative"]
    label: str
    required: bool = True
    display_unit: str = ""
    display_format: str = ""
    scope: AnswerObligationScope = Field(default_factory=AnswerObligationScope)
    retrieval_hints: List[str] = Field(default_factory=list)
    concept_hints: List[str] = Field(default_factory=list)
    semantic_target: SemanticTargetV1 = Field(default_factory=SemanticTargetV1)
    evidence_mode: Literal["declared_inputs", "source_defined_group"] = Field(
        default="declared_inputs",
        description=(
            "Use source_defined_group only for a narrative summary whose members "
            "are defined by the source, not named by the query. Leave "
            "evidence_requirements empty: the runtime creates one source-group "
            "requirement from this obligation's label, scope, and search hints. "
            "Use declared_inputs for required raw inputs or query-defined facts "
            "and relationships."
        ),
    )
    evidence_requirements: List[EvidenceRequirement] = Field(default_factory=list)
    depends_on: List[str] = Field(default_factory=list)
    coupling_key: str = Field(
        default="",
        max_length=_SEMANTIC_COUPLING_KEY_MAX_CHARS,
        description=(
            "Share a key only when outputs require a common semantic basis. "
            "Leave empty for independently requested outputs; sharing a query, "
            "company, or report does not establish coupling."
        ),
    )

    @field_validator("coupling_key", mode="before")
    @classmethod
    def _bound_coupling_key(cls, value: Any) -> str:
        return _bounded_semantic_coupling_key(value)

    @model_validator(mode="after")
    def _materialize_source_defined_group(self) -> "AnswerObligation":
        if self.evidence_mode != "source_defined_group":
            return self
        if self.kind != "narrative":
            raise ValueError("A source-defined group must be a narrative obligation")
        requirement = EvidenceRequirement(
            label=self.label,
            scope=self.scope.model_copy(deep=True),
            retrieval_hints=list(self.retrieval_hints),
            concept_hints=list(self.concept_hints),
            semantic_target=self.semantic_target.model_copy(deep=True),
        )
        if not self.evidence_requirements:
            self.evidence_requirements = [requirement]
        elif (
            len(self.evidence_requirements) != 1
            or self.evidence_requirements[0].model_dump(exclude={"requirement_id"})
            != requirement.model_dump(exclude={"requirement_id"})
        ):
            raise ValueError(
                "A source-defined group must preserve one required source-group "
                "requirement with its obligation's label, scope, and search hints"
            )
        return self


class RequirementPlannerOutput(_DeferredBaseModel):
    """Pre-retrieval semantic requirements without a fixed calculation type."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    companies: List[str] = Field(default_factory=list)
    years: List[int] = Field(default_factory=list)
    topic: str = ""
    section_filter: Optional[str] = None
    obligations: List[AnswerObligation] = Field(default_factory=list)
    retrieval_queries: List[str] = Field(default_factory=list)
    rationale: str = ""


class SemanticProgramDirectBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str
    candidate_id: str
    compatibility_candidate_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Narrative candidate IDs from the same source context that ground "
            "otherwise unknown direct-value scope metadata or explicitly "
            "establish compatibility for coupled outputs"
        ),
    )


class SemanticProgramVariableBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    variable: str
    source_id: str = Field(description="A candidate_id or a previously produced obligation_id")
    source_requirement_id: str = Field(
        default="",
        description=(
            "The declared evidence requirement satisfied by a candidate source. "
            "Leave empty when source_id is a previously produced obligation_id."
        ),
    )
    scope_applicability_fields: List[Literal["segment", "basis"]] = Field(
        default_factory=list,
        description=(
            "Soft scope fields that the compiler judges applicable when a local "
            "numeric candidate leaves only segment or basis metadata unknown. "
            "Explicit conflicts, company, period, and consolidation scope cannot "
            "be bridged."
        ),
    )


class SemanticProgramConstant(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    value: float
    origin: Literal["query", "deterministic_cardinality"]
    source_text: str = ""


class SemanticProgramExpression(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str
    variable_bindings: List[SemanticProgramVariableBinding] = Field(default_factory=list)
    formula: str
    result_unit: str = ""
    display_unit: str = ""
    display_format: str = ""
    source_display_candidate_id: Optional[str] = Field(
        description=(
            "Visible candidate reporting the same derived result as this obligation, "
            "or null when no matching source-stated result is selected."
        ),
    )
    source_display_reason: str = Field(
        min_length=1,
        description="Explain why the source-stated result was selected or not selected.",
    )
    compatibility_candidate_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Narrative candidate IDs that explicitly ground compatibility when "
            "the selected numeric sources use different semantic contexts"
        ),
    )
    constants: List[SemanticProgramConstant] = Field(default_factory=list)

    @field_validator("source_display_reason")
    @classmethod
    def _source_display_reason_is_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_display_reason must be nonblank")
        return value


class SemanticProgramNarrativeEvidenceBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    candidate_id: str
    source_requirement_id: str


class SemanticProgramNarrativeBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str
    candidate_ids: List[str] = Field(default_factory=list)
    evidence_bindings: List[SemanticProgramNarrativeEvidenceBinding] = Field(
        default_factory=list
    )
    scope_applicability_fields: List[
        Literal["consolidation_scope", "segment", "basis"]
    ] = Field(
        default_factory=list,
        description=(
            "Soft scope fields that the compiler judges applicable even though "
            "the selected narrative evidence leaves their metadata unknown. "
            "Explicit conflicts, company, and period cannot be bridged."
        ),
    )
    text: str


class SemanticProgramSourceAssertion(_DeferredBaseModel):
    """Exact source excerpt grounding one or more selected prose values."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    source_bundle_id: str
    candidate_ids: List[str] = Field(default_factory=list)
    evidence_text: str


class SemanticCalculationProgram(_DeferredBaseModel):
    """Post-evidence semantic selection plus restricted deterministic expressions."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    status: Literal["ready", "incomplete", "ambiguous"] = "ready"
    direct_bindings: List[SemanticProgramDirectBinding] = Field(default_factory=list)
    expressions: List[SemanticProgramExpression] = Field(default_factory=list)
    narrative_bindings: List[SemanticProgramNarrativeBinding] = Field(default_factory=list)
    source_assertions: List[SemanticProgramSourceAssertion] = Field(
        default_factory=list
    )
    missing_obligation_ids: List[str] = Field(default_factory=list)
    ambiguous_obligation_ids: List[str] = Field(default_factory=list)
    rationale: str = ""


NormalizedUnit = Literal["KRW", "PERCENT", "COUNT", "USD", "UNKNOWN"]


AnswerSlotStatus = Literal["ok", "missing", "derived", "ambiguous"]


class AnswerSlotValue(_DeferredBaseModel):
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


class BaseAnswerSlots(_DeferredBaseModel):
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
    result_semantics: Optional[Literal["derived_value", "period_delta"]] = Field(
        default=None,
        description=(
            "derived_value means a value produced by subtracting components; "
            "period_delta means a change between current and prior periods. "
            "None is reserved for legacy traces whose structure must be inferred."
        ),
    )
    primary_value: AnswerSlotValue
    current_value: Optional[AnswerSlotValue] = Field(default=None)
    prior_value: Optional[AnswerSlotValue] = Field(default=None)
    delta_value: Optional[AnswerSlotValue] = Field(default=None)
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


class AggregateSubtaskAnswerSlots(_DeferredBaseModel):
    task_id: str = Field(default="")
    metric_family: str = Field(default="")
    metric_label: str = Field(default="")
    operation_family: str = Field(default="")
    answer: str = Field(default="")
    answer_slots: Dict[str, Any] = Field(default_factory=dict)
    rendered_value: str = Field(default="")
    source_row_ids: List[str] = Field(default_factory=list)
    source_evidence_ids: List[str] = Field(default_factory=list)


class AggregateAnswerSlots(_DeferredBaseModel):
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


_ANSWER_SLOTS_ADAPTER: Any = None


def _answer_slots_adapter() -> Any:
    global _ANSWER_SLOTS_ADAPTER
    if _ANSWER_SLOTS_ADAPTER is None:
        from pydantic import TypeAdapter

        _ANSWER_SLOTS_ADAPTER = TypeAdapter(AnswerSlotsPayload)
    return _ANSWER_SLOTS_ADAPTER


def validate_answer_slots_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    validated = _answer_slots_adapter().validate_python(payload)
    return validated.model_dump()


class ValidationOutput(_DeferredBaseModel):
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
