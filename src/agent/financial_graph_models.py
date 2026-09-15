"""Structured-output models for narrative evidence and semantic calculation programs."""

from typing import Annotated, Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator, create_model
from pydantic.json_schema import SkipJsonSchema

from src.agent.financial_program_projection import narrative_candidate_ids, project_narrative_claims


def _normalise_optional_planner_text(value: Any) -> str:
    """Collapse serialized null sentinels for planner fields that allow blank."""

    text = " ".join(str(value or "").split())
    if text.casefold() in {"null", "none"}:
        return ""
    return text


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
    """Request-preserving reading targets, not a source-name allowlist."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    local_subjects: List[str] = Field(
        default_factory=list,
        description=(
            "Query-written subject targets, preserving modifiers and group membership. "
            "These guide retrieval and reading, not an allowlist of source expressions. "
            "Keep the request intact; the compiler explains its correspondence to observed axes/context. "
            "Do not invent translations or source-name equivalents in the plan. "
            "Each required input identifies its own subject. The filing company in scope.company "
            "does not establish a value's local subject."
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


class SourceSectionBindingV1(_DeferredBaseModel):
    """Requested wording and observed location are distinct planner decisions."""

    model_config = ConfigDict(defer_build=True, extra="forbid")
    request_unit_id: str
    requested_text: str = Field(min_length=1, description=(
        "One unique verbatim excerpt in an owned request unit that restricts the source section. "
        "Preserve its qualifiers; do not replace the request with a formal document title."
    ))
    section_ids: List[str] = Field(description=(
        "Alternative observed section IDs selected from source_section_inventory for this restriction. "
        "Include every requested alternative; empty means unresolved, never unrestricted. "
        "Do not invent IDs or infer document-wide absence from a bounded inventory."
    ))


class EvidenceRequirement(_DeferredBaseModel):
    """One non-rendered evidence input required to produce an answer obligation."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    requirement_id: str = ""
    label: str
    required: bool = True
    scope: AnswerObligationScope = Field(default_factory=AnswerObligationScope)
    source_sections: List[str] = Field(default_factory=list, description=(
        "Explicit query-requested section titles or paths, copied from the query. "
        "Alternatives within this list; intersects the parent output's restriction. "
        "Use > between path components. Empty means no additional restriction."
    ))
    source_section_bindings: List[SourceSectionBindingV1] = Field(default_factory=list, description=(
        "Source restrictions linked to observed inventory IDs. Each binding intersects the parent "
        "and the other bindings; leave empty when there is no additional source restriction."
    ))
    retrieval_hints: List[str] = Field(default_factory=list)
    concept_hints: List[str] = Field(default_factory=list)
    semantic_target: SemanticTargetV1 = Field(default_factory=SemanticTargetV1)


class AnswerObligation(_DeferredBaseModel):
    """One user-visible output requirement, independent of an operation taxonomy."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str = ""
    kind: Literal["direct_value", "derived_value", "narrative"]
    label: str
    request_unit_ids: List[str] = Field(description=(
        "IDs of original request units this output addresses. Use provided IDs "
        "only; every output needs a reference and every unit needs an output. "
        "Units may be shared. The label is a short name, not a replacement for "
        "the referenced request text. These are instructions, not source evidence."
    ))
    required: bool = True
    display_unit: str = ""
    display_format: str = ""
    scope: AnswerObligationScope = Field(default_factory=AnswerObligationScope)
    source_sections: List[str] = Field(default_factory=list, description=(
        "Explicit query-requested section titles or paths, not inferred search hints. "
        "Copy title components from the query, using > for hierarchy. Entries are "
        "alternatives; empty means unrestricted. Applies to all supporting inputs."
    ))
    source_section_bindings: List[SourceSectionBindingV1] = Field(default_factory=list, description=(
        "Link explicit requested source restrictions to observed section IDs. "
        "Use these bindings rather than source_sections for informal or differently worded titles. "
        "An empty list means no such restriction; a binding with no selected IDs remains unresolved."
    ))
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
    depends_on: List[str] = Field(
        default_factory=list,
        description=(
            "IDs of other user-visible answer obligations whose calculated outputs "
            "feed this obligation. Do not include this obligation or any of its "
            "evidence requirement IDs; raw inputs belong in evidence_requirements."
        ),
    )

    @field_validator("display_unit", "display_format", mode="before")
    @classmethod
    def _normalise_optional_display_fields(cls, value: Any) -> str:
        return _normalise_optional_planner_text(value)

    @model_validator(mode="after")
    def _materialize_source_defined_group(self) -> "AnswerObligation":
        if self.evidence_mode != "source_defined_group":
            return self
        if self.kind != "narrative":
            raise ValueError("A source-defined group must be a narrative obligation")
        requirement = EvidenceRequirement(
            label=self.label,
            scope=self.scope.model_copy(deep=True),
            source_sections=list(self.source_sections),
            source_section_bindings=[binding.model_copy(deep=True) for binding in self.source_section_bindings],
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


class OutputRelationshipV1(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")
    kind: Literal["shared_basis"]
    output_ids: List[str] = Field(min_length=2)
    request_unit_id: str
    request_text: str = Field(min_length=1, description="Exact request substring requiring these outputs to share a basis, not merely a company or topic.")


class RequirementPlannerOutput(_DeferredBaseModel):
    """Pre-retrieval semantic requirements without a fixed calculation type."""

    model_config = ConfigDict(defer_build=True, extra="forbid")

    companies: List[str] = Field(default_factory=list)
    years: List[int] = Field(default_factory=list)
    output_relationships: List[OutputRelationshipV1] = Field(default_factory=list)
    topic: str = ""
    section_filter: Optional[str] = None
    obligations: List[AnswerObligation] = Field(default_factory=list)
    retrieval_queries: List[str] = Field(default_factory=list)
    rationale: str = ""


class SemanticProgramContextBinding(_DeferredBaseModel):
    """Compiler interpretation of an exposed, source-located context excerpt."""

    model_config = ConfigDict(defer_build=True, extra="forbid")
    context_id: str
    evidence_text: str = Field(min_length=1)
    field: Literal["period", "consolidation_scope", "segment", "basis"]
    value: str = Field(min_length=1)


class SourceInterpretationContext(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")
    context_id: str
    evidence_text: str = Field(min_length=1)


class InterpretedScopeV1(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")
    segment: str = ""
    basis: str = ""


class SourceInterpretationV1(_DeferredBaseModel):
    """Model interpretation linked to the unchanged request and own sources."""
    model_config = ConfigDict(defer_build=True, extra="forbid")
    request_unit_ids: List[str] = Field(min_length=1)
    subject: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    scope: InterpretedScopeV1 = Field(default_factory=InterpretedScopeV1)
    axis_refs: List[str] = Field(default_factory=list)
    context_evidence: List[SourceInterpretationContext] = Field(default_factory=list)
    source_evidence_text: Optional[str] = None


class SemanticProgramDirectBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str
    candidate_id: str
    source_interpretation: Optional[SourceInterpretationV1] = None
    context_bindings: List[SemanticProgramContextBinding] = Field(default_factory=list)
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
    source_interpretation: Optional[SourceInterpretationV1] = None
    context_bindings: List[SemanticProgramContextBinding] = Field(default_factory=list)
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

    value: float = Field(strict=True, allow_inf_nan=False)
    origin: Literal["query", "deterministic_cardinality"]
    source_text: str = ""
    # Historical internal programs can still be parsed, but missing request
    # evidence is rejected by validation; production requires it in its schema.
    request_unit_id: Optional[str] = None
    interpretation: str = ""


class SemanticProgramExpression(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    obligation_id: str
    # Historical/internal formulas may have no explicit comparison declaration.
    # The production wire independently requires the nullable choice.
    comparison_request_unit_id: Optional[str] = None
    variable_bindings: List[SemanticProgramVariableBinding] = Field(default_factory=list)
    formula: str
    display_unit: str = Field(
        default="",
        description=(
            "Requested display unit, including percent versus percentage-point intent. "
            "Leave blank to use the obligation display unit or the inferred base unit. "
            "Calculation dimensions and scale conversion are inferred by runtime code."
        ),
    )
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
    source_display_context_bindings: List[SemanticProgramContextBinding] = Field(default_factory=list)
    source_display_interpretation: Optional[SourceInterpretationV1] = None
    compatibility_candidate_ids: List[str] = Field(
        default_factory=list,
        description=(
            "Narrative candidate IDs that explicitly ground compatibility when "
            "the selected numeric sources use different semantic contexts"
        ),
    )
    constants: List[SemanticProgramConstant] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _discard_legacy_result_unit(cls, value: Any) -> Any:
        """Read historical programs without giving their old unit declaration authority."""
        if isinstance(value, dict) and "result_unit" in value:
            return {key: item for key, item in value.items() if key != "result_unit"}
        return value

    @field_validator("source_display_reason")
    @classmethod
    def _source_display_reason_is_nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source_display_reason must be nonblank")
        return value


class SemanticProgramNarrativeEvidenceBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    candidate_id: str
    source_requirement_id: str = Field(
        default="",
        description="Declared requirement this evidence satisfies; blank for owner-only supporting evidence.",
    )
    row_description_quote: str = Field(
        default="",
        description=(
            "For reading a physical row's description without using its scalar value, "
            "copy an exact excerpt from one row_label/row_headers surface also present in "
            "the source text. Requires document/year and physical table/row provenance. "
            "Only this quote grounds the reading, not the cell value or surrounding numbers. "
            "Leave empty for ordinary evidence, including numeric use."
        ),
    )


class SemanticProgramNarrativeClaimEvidence(SemanticProgramNarrativeEvidenceBinding):
    surface_id: str = Field(description="Visible source-reading surface attached to this candidate; never filing metadata.")
    first_piece_id: str = Field(description="First selected piece in this surface.")
    last_piece_id: str = Field(description="Last selected piece, inclusive; same partition and not before first_piece_id.")


class SemanticProgramNarrativeSubjectBinding(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    subject_binding_id: str = Field(min_length=1, description="Unique local reference within this narrative obligation.")
    subject: str = Field(min_length=1, description="Source-local subject from selected support, not filing metadata. Only whitespace layout may differ, with one unambiguous source occurrence; preserve spelling, punctuation, word boundaries and scope.")
    evidence_selections: List[SemanticProgramNarrativeClaimEvidence] = Field(min_length=1)


class SemanticProgramNarrativeClaim(_DeferredBaseModel):
    model_config = ConfigDict(defer_build=True, extra="forbid")

    subject_binding_id: str = Field(description="Explicit reference to this obligation's subject_bindings; no implicit inheritance.")
    text: str = Field(description="One source-supported statement about the declared subject; do not broaden its scope. Repeating subject is optional: code adds a subject label when absent. Do not replace it with another entity.")
    fact_evidence_selections: List[SemanticProgramNarrativeClaimEvidence] = Field(min_length=1)


class SemanticProgramNarrativeBinding(_DeferredBaseModel):
    basis_interpretation: str = ""
    # The provider schema is current-only; parsing can still inspect frozen flat programs.
    model_config = ConfigDict(defer_build=True, extra="forbid",
        json_schema_extra={"required": ["obligation_id", "subject_bindings", "claims"]})

    obligation_id: str
    subject_bindings: List[SemanticProgramNarrativeSubjectBinding] = Field(default_factory=list,
        json_schema_extra={"minItems": 1}, description="Explicit shared subject support for the claims in this output only.")
    # Internal projection / historical input, never a second model-written list.
    candidate_ids: SkipJsonSchema[List[str]] = Field(default_factory=list)
    evidence_bindings: SkipJsonSchema[List[SemanticProgramNarrativeEvidenceBinding]] = Field(
        default_factory=list
    )
    claims: List[SemanticProgramNarrativeClaim] = Field(default_factory=list, json_schema_extra={"minItems": 1},
        description="Required for every current narrative output. Statements are composed in order; omit the output if evidence is insufficient.")
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
    text: SkipJsonSchema[str] = ""

    @model_validator(mode="after")
    def _project_evidence_members(self) -> "SemanticProgramNarrativeBinding":
        if self.claims:
            projection = project_narrative_claims({
                "subject_bindings": [subject.model_dump() for subject in self.subject_bindings],
                "claims": [claim.model_dump() for claim in self.claims],
                **({"text": self.text} if "text" in self.model_fields_set else {}),
                **({"evidence_bindings": [item.model_dump() for item in self.evidence_bindings]}
                   if "evidence_bindings" in self.model_fields_set else {}),
            })
            self.text = projection["text"]
            self.evidence_bindings = [SemanticProgramNarrativeEvidenceBinding.model_validate(row)
                for row in projection["evidence_bindings"]]
        if "candidate_ids" not in self.model_fields_set:
            self.candidate_ids = narrative_candidate_ids({
                "evidence_bindings": [binding.model_dump() for binding in self.evidence_bindings],
            })
        return self


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


class WireModel(_DeferredBaseModel):
    model_config = ConfigDict(extra="forbid", defer_build=True)


class NumericInterpretation(WireModel):
    """Meaning supplied by the model; selected-cell axes are assembled by code."""

    request_unit_ids: list[str] = Field(min_length=1)
    subject: str = Field(min_length=1)
    metric: str = Field(min_length=1)
    scope: InterpretedScopeV1 = Field(default_factory=InterpretedScopeV1)


class ContextualProseInterpretation(NumericInterpretation):
    source_evidence_text: Optional[str] = Field(min_length=1, description=(
        "Exact own-body quote supporting the interpretation, or explicit null only when "
        "selection.context_evidence supplies attached interpretation support."))


class ProseInterpretation(NumericInterpretation):
    source_evidence_text: str = Field(min_length=1, description=(
        "Exact own-body quote supporting subject and metric interpretation; "
        "code separately preserves the value span addressed by source_ref."))


class ContextScopeValue(WireModel):
    field: Literal["period", "consolidation_scope", "segment", "basis"]
    value: str = Field(min_length=1)


class NumericSelection(WireModel):
    source_ref: str
    interpretation: Optional[NumericInterpretation] = None


class NumericInput(NumericSelection):
    variable: str
    scope_applicability_fields: list[Literal["segment", "basis"]] = Field(default_factory=list)


class CardinalityConstant(WireModel):
    value: float = Field(strict=True, allow_inf_nan=False)
    origin: Literal["deterministic_cardinality"]
    source_text: str = ""  # Diagnostic only; runtime counts the actual bindings.


class ReadingSelection(WireModel):
    source_ref: str
    row_description_quote: Optional[str] = None
    surface_ref: Optional[str] = None
    first_piece_ref: Optional[str] = None
    last_piece_ref: Optional[str] = None


def _selection_list(item_type):
    # No fabricated reference or invalid empty enum when an owner has no sources.
    return (list[item_type], ...) if item_type is not None else (list[None], Field(max_length=0))


def _input_groups(owner, refs, item_type, name, *, numeric_model=None):
    requirements = owner.get("evidence_requirements") or []
    fields = {refs.ref(row["requirement_id"]): _selection_list(
        numeric_model(row["requirement_id"], input=True) if numeric_model else item_type)
        for row in requirements}
    if not requirements or item_type is ReadingSelection:
        own_type = numeric_model(owner["obligation_id"], input=True,
            dependencies=owner.get("depends_on") or ()) if numeric_model else item_type
        fields["own"] = _selection_list(own_type)
    elif item_type is NumericInput and owner.get("depends_on"):
        fields["dependencies"] = _selection_list(numeric_model(owner["obligation_id"], input=True,
            dependencies=owner["depends_on"], only_dependencies=True))
    return create_model(name, __base__=WireModel, **fields)


def compiler_response_model(obligations, refs, visibility):
    """Only the active outputs and their own kinds exist in the provider schema."""
    numeric_types = {}
    allowed = visibility.candidate_ids_by_owner()
    source_kinds = dict(refs.numeric_source_kinds)
    source_kinds_by_ref = {refs.ref(key): kind for key, kind in source_kinds.items()}

    def source_variant(expected_kind):
        def check(value):
            source_ref = value.get("source_ref") if isinstance(value, dict) else None
            actual = source_kinds_by_ref.get(source_ref) if isinstance(source_ref, str) else None
            if expected_kind != "dependency" and actual is not None and actual != expected_kind:
                raise ValueError("numeric_source_variant_mismatch")
            return value
        return model_validator(mode="before")(check)

    def numeric_model(owner_id, *, input=False, dependencies=(), only_dependencies=False):
        alternatives = []
        for kind in ("cell", "prose", "dependency"):
            choices = tuple(sorted(refs.ref(key) for key in (
                dependencies if kind == "dependency" else () if only_dependencies else allowed.get(owner_id, ()))
                if kind == "dependency" or source_kinds.get(key) == kind))
            if not choices:
                continue
            contexts = () if kind == "dependency" else refs.context_refs_for_owner(owner_id)
            key = (kind, choices, contexts, input)
            if key not in numeric_types:
                name = kind.title() + ("Input_" if input else "Selection_") + refs.ref(owner_id)
                # The generation schema mirrors existing authority. Keep strings
                # for lossless parsing: lowering reports forbidden references per
                # output, so a bad address cannot discard valid sibling outputs.
                fields = {"source_ref": (str, Field(json_schema_extra={"enum": list(choices)}))}
                base = NumericInput if input else NumericSelection
                if kind == "dependency":
                    base = WireModel
                    fields.update(variable=(str, ...), scope_applicability_fields=(
                        list[Literal["segment", "basis"]], Field(default_factory=list)))
                if kind == "prose":
                    interpretation_type = ContextualProseInterpretation if contexts else ProseInterpretation
                    fields["interpretation"] = (Optional[interpretation_type], None)
                if contexts:
                    context_type = create_model("ContextEvidence_" + name, __base__=WireModel,
                        context_ref=(Literal[contexts], ...), evidence_text=(str, Field(min_length=1)),
                        supports_interpretation=(bool, False),
                        resolves=(list[ContextScopeValue], Field(default_factory=list)))
                    fields["context_evidence"] = (list[context_type], Field(default_factory=list))
                numeric_types[key] = create_model(name, __base__=base,
                    __validators__={"source_variant": source_variant(kind)}, **fields)
            alternatives.append(numeric_types[key])
        return Union[tuple(alternatives)] if alternatives else None

    output_fields = {}
    for owner in obligations:
        key = refs.ref(owner["obligation_id"])
        kind = owner["kind"]
        if kind == "direct_value":
            selection = numeric_model(owner["obligation_id"])
            result = (create_model("Direct_" + key, __base__=WireModel,
                selection=(selection, ...), compatibility_refs=(list[str], Field(default_factory=list)))
                if selection is not None else type(None))
        elif kind == "derived_value":
            inputs = _input_groups(owner, refs, NumericInput, "Inputs_" + key, numeric_model=numeric_model)
            request_constant = create_model("RequestConstant_" + key, __base__=WireModel,
                value=(float, Field(strict=True, allow_inf_nan=False)), origin=(Literal["query"], ...),
                request_unit_id=(str, Field(json_schema_extra={"enum": list(dict.fromkeys(
                    refs.ref(unit_id) for unit_id in owner.get("request_unit_ids") or []))}, description=(
                    "Select the owned instruction interpreting this scalar. Code preserves its complete exact text; "
                    "this is not a claim that it identifies a unique quantity occurrence."))),
                interpretation=(str, Field(min_length=1,
                    description="Explain how that request specifies this formula scalar; not a source value or an answer.")))
            result = create_model("Calculation_" + key, __base__=WireModel,
                comparison_request_unit_id=(Optional[str], Field(description=(
                    "For a directed comparison, select an owned request unit ID and name its endpoint inputs "
                    "reference and target in both inputs and formula. Null for other calculations. "
                    "The request, not source period labels, defines these endpoints."))),
                inputs=(inputs, ...), formula=(str, ...), display_unit=(str, ""), display_format=(str, ""),
                source_display=(Optional[numeric_model(owner["obligation_id"]) or type(None)], Field(description=(
                    "Primary source-stated display only when consistent with the linked request. "
                    "Use null for calculation-only requests; explicit intent overrides source-first defaults."))),
                source_display_reason=(str, Field(min_length=1, description=(
                    "Explain selection or null from the request's display intent, not merely the presence of a reported value."))),
                compatibility_refs=(list[str], Field(default_factory=list)),
                constants=(list[Union[request_constant, CardinalityConstant]], Field(description=(
                    "Explicit declarations for every non-neutral formula scalar. "
                    "Use [] only when no declaration is needed; never omit this field."))))
        elif kind == "narrative":
            evidence = _input_groups(owner, refs, ReadingSelection, "Evidence_" + key)
            claim = create_model("Claim_" + key, __base__=WireModel, text=(str, Field(min_length=1)), evidence=(evidence, ...))
            subject = create_model("Subject_" + key, __base__=WireModel,
                subject=(str, Field(min_length=1)), support=(evidence, ...), claims=(list[claim], Field(min_length=1)))
            result = create_model("Narrative_" + key, __base__=WireModel,
                subjects=(list[subject], Field(min_length=1)),
                basis_interpretation=(str, ""),
                scope_applicability_fields=(list[Literal["segment", "basis", "consolidation_scope"]], Field(default_factory=list)))
        else:
            raise ValueError("unknown_output_kind")
        reply = create_model("Reply_" + key, __base__=WireModel,
            status=(Literal["ready", "missing", "ambiguous"], ...), result=(Optional[result], ...))
        output_fields[key] = (reply, ...)
    outputs = create_model("CompilerOutputs", __base__=WireModel, **output_fields)
    model = create_model("CompilerResponseV2", __base__=WireModel, outputs=(outputs, ...), rationale=(str, ""))
    model.__compiler_references__ = refs
    model.__compiler_visibility__ = visibility
    return model
