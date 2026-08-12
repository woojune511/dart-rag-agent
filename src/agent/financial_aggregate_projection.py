"""Pure projection helpers for aggregate-subtask closure."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Literal, Mapping, Optional, Sequence

from src.agent import financial_graph_calculation_rendering as calculation_rendering
from src.agent.financial_answer_slots import (
    answer_slot_has_material,
    build_operand_value_slot,
    coerce_slot_numeric,
    ratio_components_are_complete,
    source_task_display_compatible_with_slot,
)
from src.agent.financial_answer_projection import (
    _preferred_complete_aggregate_subtask_answer,
    growth_answer_has_untraced_numeric_sentence,
    growth_row_has_conflicting_periods,
    growth_sentence_has_untraced_material_numeric,
    material_gap_feedback_for_subtask_result,
    nested_subtask_rows,
    subtask_row_has_material,
)
from src.agent.financial_dependency_projection import (
    dependency_lookup_slot_match_score,
    dependency_operand_from_source_slot,
    dependency_projection_slot_differs_from_operand,
    dependency_ratio_role_group,
    lookup_primary_slot,
    replace_lookup_primary_slot,
    structured_unit_realigned_operand_matches_source_slot,
)
from src.agent.financial_numeric_surface import (
    answer_covers_numeric_answer,
    evidence_text_for_numeric_support,
    evidence_supports_numeric_candidates,
    evidence_numeric_display_candidates,
    extract_numeric_surface_candidates,
    numeric_evidence_relevance_score,
    numeric_surface_candidates_equivalent,
    numeric_surface_slot_components,
    promote_table_numeric_support_evidence,
    text_supports_numeric_candidates,
)
from src.agent.financial_operand_resolution import (
    _evidence_item_for_operand_row,
    _evidence_items_by_id,
    coerce_operand_unit_from_evidence,
    ratio_context_has_metric_surface,
)
from src.agent.financial_row_surfaces import _operand_text_match, _strip_leading_period_qualifiers
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _normalise_operand_value,
    _normalise_spaces,
)
from src.agent.financial_runtime_trace import (
    _attach_runtime_projection_metadata,
    _build_aggregate_calculation_projection,
    _structured_result_subtask_rows_and_answer,
    operand_row_has_material_numeric_payload,
)
from src.agent.financial_scope_policies import known_consolidation_scope_value
from src.agent.financial_text_surface import (
    _tokenize_terms,
    narrative_context_terms,
    narrative_sentence_looks_abbreviated_fragment,
    narrative_sentence_looks_table_noisy,
    split_narrative_sentences as _split_narrative_sentences,
    topic_particle,
)
from src.config.retrieval_policy import (
    CALCULATION_NARRATIVE_POLICY,
    CALCULATION_RENDER_POLICY,
    CALCULATION_SLOT_POLICY,
)

if TYPE_CHECKING:
    from src.agent.financial_graph_state import FinancialAgentState


AggregateStaleRepairTargetResolution = Literal[
    "unique_overlap",
    "single_identity_candidate",
    "ambiguous_target",
    "no_target",
]


def build_aggregate_calculation_projection(
    ordered_results: List[Dict[str, Any]],
    final_answer: str,
) -> Dict[str, Any]:
    projection_rows: List[Dict[str, Any]] = []
    for row in ordered_results:
        is_conflicting_growth = (
            aggregate_result_operation_family(dict(row)) == "growth_rate"
            and growth_row_has_conflicting_periods(dict(row))
        )
        if not is_conflicting_growth:
            projection_rows.append(row)
            continue
        material_gap = material_gap_feedback_for_subtask_result(dict(row))
        row_copy = dict(row)
        calculation_result = dict(row_copy.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row_copy.get("answer_slots") or {})
        answer_slots["source_row_ids"] = []
        calculation_result.update(
            {
                "answer_slots": answer_slots,
                "source_row_ids": [],
                "source_evidence_ids": [],
                "material_gap_feedback": material_gap,
            }
        )
        row_copy.update(
            {
                "calculation_operands": [],
                "calculation_result": calculation_result,
                "source_row_ids": [],
                "source_evidence_ids": [],
                "material_gap_feedback": material_gap,
            }
        )
        projection_rows.append(row_copy)

    aggregate_projection = _build_aggregate_calculation_projection(projection_rows, final_answer)
    aggregate_evidence: List[Dict[str, Any]] = []
    seen_evidence_ids: set[str] = set()

    for row in projection_rows:
        for evidence in list(row.get("runtime_evidence") or []):
            evidence_row = dict(evidence)
            evidence_id = str(evidence_row.get("evidence_id") or "").strip()
            dedupe_key = evidence_id or _normalise_spaces(
                " ".join(
                    part
                    for part in [
                        str(evidence_row.get("source_anchor") or "").strip(),
                        str(evidence_row.get("quote_span") or "").strip(),
                        str(evidence_row.get("raw_row_text") or "").strip(),
                        str(evidence_row.get("claim") or "").strip(),
                    ]
                    if part
                )
            )
            if dedupe_key and dedupe_key in seen_evidence_ids:
                continue
            if dedupe_key:
                seen_evidence_ids.add(dedupe_key)
            aggregate_evidence.append(evidence_row)
    return {
        "calculation_operands": aggregate_projection["calculation_operands"],
        "calculation_plan": aggregate_projection["calculation_plan"],
        "calculation_result": aggregate_projection["calculation_result"],
        "evidence_items": aggregate_evidence,
    }


def structured_subtask_projection_for_public_answer(
    state: FinancialAgentState,
    trace: Dict[str, Any],
) -> Dict[str, Any]:
    structured_result = dict(state.get("structured_result") or {})
    public_answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
    subtask_results, structured_answer = _structured_result_subtask_rows_and_answer(structured_result)
    if not public_answer or public_answer != structured_answer:
        return {}
    if not subtask_results:
        return {}
    current_result = dict((trace or {}).get("calculation_result") or {})
    current_primary = dict((current_result.get("answer_slots") or {}).get("primary_value") or {})
    current_rendered = _normalise_spaces(
        str(
            current_result.get("formatted_result")
            or current_result.get("rendered_value")
            or current_primary.get("rendered_value")
            or ""
        )
    )
    projection_answer = _preferred_complete_aggregate_subtask_answer(
        subtask_results,
        public_answer,
    ) or public_answer
    if current_rendered and current_rendered == public_answer and projection_answer == public_answer:
        return {}
    projection = _build_aggregate_calculation_projection(subtask_results, projection_answer)
    projection_result = dict(projection.get("calculation_result") or {})
    if not projection_result.get("subtask_results"):
        return {}
    return _attach_runtime_projection_metadata(
        projection,
        source="structured_result_subtasks",
    )


def upsert_subtask_result(
    existing: List[Dict[str, Any]],
    current: Dict[str, Any],
) -> List[Dict[str, Any]]:
    if not current:
        return list(existing or [])
    current_task_id = str(current.get("task_id") or "").strip()
    rows: List[Dict[str, Any]] = []
    replaced = False
    for row in existing or []:
        row_task_id = str(row.get("task_id") or "").strip()
        if current_task_id and row_task_id == current_task_id:
            if _subtask_upsert_quality_rank(dict(row)) > _subtask_upsert_quality_rank(current):
                rows.append(row)
            else:
                rows.append(current)
            replaced = True
        else:
            rows.append(row)
    if not replaced:
        rows.append(current)
    return rows


def _subtask_upsert_quality_rank(row: Dict[str, Any]) -> tuple[int, int, int, int, int, int]:
    calculation_result = dict(row.get("calculation_result") or {})
    status = _normalise_spaces(str(row.get("status") or calculation_result.get("status") or "")).lower()
    status_rank = {"ok": 4, "ready": 3, "partial": 2}.get(status, 0)
    has_material = 1 if subtask_row_has_material(row) else 0
    has_structured_payload = 1 if (
        calculation_result.get("answer_slots")
        or calculation_result.get("subtask_results")
        or calculation_result.get("source_row_ids")
        or calculation_result.get("formatted_result")
        or calculation_result.get("rendered_value")
    ) else 0
    source_count = len(_clean_source_row_ids([
        row.get("source_row_ids"),
        calculation_result.get("source_row_ids"),
        row.get("selected_claim_ids"),
        calculation_result.get("source_evidence_ids"),
    ]))
    answer_text = _normalise_spaces(
        str(
            row.get("answer")
            or calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or ""
        )
    )
    digit_count = len(re.findall(r"\d", answer_text))
    return status_rank, has_material, has_structured_payload, source_count, digit_count, len(answer_text)


def aggregate_synthesis_prompt_rows(
    ordered_results: Sequence[Any],
    aggregate_projection: Mapping[str, Any],
) -> List[Dict[str, Any]]:
    """Project subtask rows into the compact contract needed by final synthesis."""
    calculation_result = dict(aggregate_projection.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    projected_rows = list(calculation_result.get("subtask_results") or answer_slots.get("subtask_results") or [])
    if not projected_rows:
        projected_rows = list(ordered_results or [])

    operands_by_task_id: Dict[str, List[Dict[str, Any]]] = {}
    for operand in list(aggregate_projection.get("calculation_operands") or []):
        operand_row = dict(operand or {})
        if not operand_row_has_material_numeric_payload(operand_row):
            continue
        task_id = str(operand_row.get("task_id") or "").strip()
        compact_operand = {
            key: operand_row.get(key)
            for key in (
                "operand_id",
                "matched_operand_role",
                "label",
                "label_kr",
                "raw_value",
                "value",
                "raw_unit",
                "normalized_value",
                "normalized_unit",
                "period",
                "source_row_id",
                "source_row_ids",
                "source_evidence_ids",
            )
            if operand_row.get(key) not in (None, "", [], {})
        }
        if compact_operand:
            operands_by_task_id.setdefault(task_id, []).append(compact_operand)

    compact_rows: List[Dict[str, Any]] = []
    for row in projected_rows:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("task_id") or "").strip()
        compact_row: Dict[str, Any] = {
            key: row.get(key)
            for key in (
                "task_id",
                "metric_family",
                "metric_label",
                "operation_family",
                "answer",
                "rendered_value",
                "status",
                "source_row_ids",
                "source_evidence_ids",
            )
            if row.get(key) not in (None, "", [], {})
        }
        row_answer_slots = dict(row.get("answer_slots") or {})
        if row_answer_slots:
            compact_row["answer_slots"] = row_answer_slots
        row_result = dict(row.get("calculation_result") or {})
        if row_result:
            compact_result = {
                key: row_result.get(key)
                for key in (
                    "status",
                    "rendered_value",
                    "formatted_result",
                    "answer_slots",
                    "source_row_ids",
                    "source_evidence_ids",
                )
                if row_result.get(key) not in (None, "", [], {})
            }
            if compact_result:
                compact_row["calculation_result"] = compact_result
        row_operands = operands_by_task_id.get(task_id) or []
        if row_operands:
            compact_row["calculation_operands"] = row_operands
        if compact_row:
            compact_rows.append(compact_row)
    return compact_rows


@dataclass(frozen=True)
class AggregateStaleRepairProvenanceInput:
    ordered_results: Sequence[Mapping[str, Any]]
    aggregate_projection: Mapping[str, Any]
    selected_claim_ids: Sequence[Any]
    repaired_calculation_result: Mapping[str, Any]
    repaired_selected_evidence_ids: Sequence[str]
    evidence_items: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateStaleRepairProvenanceResult:
    selected_claim_ids: tuple[str, ...]
    target_resolution: AggregateStaleRepairTargetResolution


@dataclass(frozen=True)
class RuntimeRatioAbsoluteMagnitudeProjectionInput:
    """Prepared mutable copies for query-approved ratio magnitude projection."""

    calculation_result: Dict[str, Any]
    answer_slots: Dict[str, Any]
    primary_value: Dict[str, Any]


@dataclass(frozen=True)
class RuntimeRatioAbsoluteMagnitudeProjectionResult:
    """The same prepared calculation-result object after attempted projection."""

    calculation_result: Dict[str, Any]


@dataclass(frozen=True)
class AggregateProjectionFinalAnswerSyncInput:
    """Prepared aggregate projection and final-answer synchronization flags."""

    aggregate_projection: Dict[str, Any]
    final_answer: str
    sync_rendered_for_aggregate: bool = True
    status_ok: bool = False


@dataclass(frozen=True)
class AggregateProjectionFinalAnswerSyncResult:
    """The same aggregate projection after attempted final-answer synchronization."""

    aggregate_projection: Dict[str, Any]


@dataclass(frozen=True)
class AggregateAnswerCandidatePackagingInput:
    """Prepared fields for one normalized aggregate-answer candidate payload."""

    answer: Any
    selected_claim_ids: Optional[Iterable[Any]] = None
    sync_projection: bool = True
    sync_rendered_for_aggregate: bool = True
    status_ok: bool = False


@dataclass(frozen=True)
class AggregateRefreshedAnswerCandidatePackagingInput:
    """Prepared refresh payload and fallback for candidate packaging."""

    refreshed_answer: Optional[Mapping[str, Any]]
    fallback_answer: Any
    sync_projection: bool = True
    sync_rendered_for_aggregate: bool = True
    status_ok: bool = False


@dataclass(frozen=True)
class AggregateAnswerCandidatePackagingResult:
    """Fresh normalized candidate payload for aggregate answer application."""

    candidate: Dict[str, Any]


@dataclass(frozen=True)
class AggregateAnswerCandidateApplicationInput:
    """Graph-prepared candidate inputs for state-free aggregate application."""

    aggregate_projection: Dict[str, Any]
    selected_claim_ids: Sequence[Any]
    candidate: Optional[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateAnswerCandidateApplicationResult:
    """Applied projection, normalized answer, and newly merged claim ids."""

    aggregate_projection: Dict[str, Any]
    final_answer: str
    selected_claim_ids: List[str]


@dataclass(frozen=True)
class AggregateProjectionProvenanceFilterInput:
    """Prepared aggregate projection and the evidence ids retained by the graph."""

    aggregate_projection: Dict[str, Any]
    kept_evidence_ids: Sequence[Any]


@dataclass(frozen=True)
class AggregateProjectionProvenanceFilterResult:
    """The original or shallow-filtered aggregate projection."""

    aggregate_projection: Dict[str, Any]


@dataclass(frozen=True)
class AggregateNestedSubtaskSynchronizationInput:
    """Graph-prepared ordered rows for recursive nested-result synchronization."""

    ordered_results: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateNestedSubtaskSynchronizationResult:
    """New ordered rows whose nested task results use current row authorities."""

    ordered_results: List[Dict[str, Any]]


@dataclass(frozen=True)
class AggregateProjectionRowSurfaceSyncInput:
    """One graph-prepared aggregate row and its selected answer surface."""

    projection_row: Mapping[str, Any]
    answer: str
    rendered_value: str


@dataclass(frozen=True)
class AggregateProjectionRowSurfaceSyncResult:
    """Fresh row with the prepared answer surface synchronized into its result."""

    projection_row: Dict[str, Any]


@dataclass(frozen=True)
class AggregateArithmeticComponentSyncInput:
    """One prepared projection row and the available lookup primary slots."""

    projection_row: Dict[str, Any]
    lookup_slots: Sequence[Mapping[str, Any]]


@dataclass(frozen=True)
class AggregateArithmeticComponentSyncResult:
    """The original or synchronized aggregate arithmetic projection row."""

    projection_row: Dict[str, Any]


def filter_aggregate_evidence_for_final_answer(
    evidence_items: List[Dict[str, Any]],
    *,
    final_answer: str,
    selected_claim_ids: List[str],
) -> List[Dict[str, Any]]:
    answer_candidates = extract_numeric_surface_candidates(final_answer)
    if not evidence_items or not answer_candidates:
        return list(evidence_items or [])
    answer_has_percent = any(str(candidate.get("kind") or "") == "percent" for candidate in answer_candidates)
    selected = {str(value).strip() for value in (selected_claim_ids or []) if str(value).strip()}
    selected_or_operand_numeric_support = any(
        (
            str((item or {}).get("evidence_id") or "").strip() in selected
            or str((item or {}).get("evidence_id") or "").strip().startswith("operand::")
        )
        and evidence_supports_numeric_candidates(dict(item or {}), answer_candidates)
        for item in list(evidence_items or [])
    )
    operand_surface_support = any(
        str((item or {}).get("evidence_id") or "").strip().startswith("operand::")
        and bool(dict((item or {}).get("metadata") or {}).get("supports_answer_numeric_surface"))
        for item in list(evidence_items or [])
    )
    filtered: List[Dict[str, Any]] = []
    for item in list(evidence_items or []):
        evidence = dict(item or {})
        evidence_id = str(evidence.get("evidence_id") or "").strip()
        metadata = dict(evidence.get("metadata") or {})
        if not evidence_id.startswith("retrieved_narrative::"):
            evidence = promote_table_numeric_support_evidence(
                evidence,
                final_answer=final_answer,
                answer_candidates=answer_candidates,
            )
        if evidence_id and evidence_id in selected:
            quote_span = _normalise_spaces(str(evidence.get("quote_span") or ""))
            raw_row_text = _normalise_spaces(str(evidence.get("raw_row_text") or ""))
            if (
                operand_surface_support
                and raw_row_text
                and quote_span
                and not evidence_id.startswith("retrieved_narrative::")
                and not text_supports_numeric_candidates(quote_span, answer_candidates)
            ):
                continue
            filtered.append(evidence)
            continue
        if (
            selected
            and selected_or_operand_numeric_support
            and evidence_id
            and not evidence_id.startswith("operand::")
            and not evidence_id.startswith("recon::")
        ):
            continue
        if answer_has_percent and evidence_id.startswith("operand::") and metadata.get("supports_derived_percent"):
            filtered.append(evidence)
            continue
        if evidence_id.startswith("operand::") and metadata.get("supports_answer_numeric_surface"):
            filtered.append(evidence)
            continue
        if evidence_supports_numeric_candidates(evidence, answer_candidates):
            filtered.append(evidence)
    return filtered or list(evidence_items or [])


def filter_final_aggregate_evidence_and_projection(
    aggregate_evidence_items: List[Dict[str, Any]],
    aggregate_projection: Dict[str, Any],
    *,
    final_answer: str,
    selected_claim_ids: List[str],
) -> tuple[List[Dict[str, Any]], Dict[str, Any], List[str], List[str]]:
    filtered_evidence_items = filter_aggregate_evidence_for_final_answer(
        aggregate_evidence_items,
        final_answer=final_answer,
        selected_claim_ids=selected_claim_ids,
    )
    kept_evidence_ids = [
        str(item.get("evidence_id") or "").strip()
        for item in filtered_evidence_items
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    ]
    if kept_evidence_ids:
        kept_evidence_id_set = set(kept_evidence_ids)
        selected_claim_ids = list(
            dict.fromkeys(
                [
                    *[
                        claim_id
                        for claim_id in selected_claim_ids
                        if claim_id in kept_evidence_id_set
                    ],
                    *[
                        evidence_id
                        for evidence_id in kept_evidence_ids
                        if evidence_id.startswith("operand::")
                    ],
                ]
            )
        )
    aggregate_projection = filter_aggregate_projection_provenance(
        AggregateProjectionProvenanceFilterInput(
            aggregate_projection=aggregate_projection,
            kept_evidence_ids=kept_evidence_ids,
        )
    ).aggregate_projection
    aggregate_projection = append_final_answer_surface_operands_from_evidence(
        aggregate_projection,
        filtered_evidence_items,
        final_answer=final_answer,
    )
    return filtered_evidence_items, aggregate_projection, selected_claim_ids, kept_evidence_ids


def append_operand_evidence_for_final_answer(
    evidence_items: List[Dict[str, Any]],
    *,
    operands: List[Dict[str, Any]],
    final_answer: str,
) -> List[Dict[str, Any]]:
    answer_candidates = extract_numeric_surface_candidates(final_answer)
    if not operands or not answer_candidates:
        return list(evidence_items or [])
    answer_has_percent = any(str(candidate.get("kind") or "") == "percent" for candidate in answer_candidates)
    derivation_roles = {
        "current_period",
        "prior_period",
        "numerator",
        "denominator",
        "numerator_1",
        "denominator_1",
        "minuend",
        "subtrahend",
    }
    updated = [dict(item or {}) for item in (evidence_items or [])]
    seen_ids = {
        str(item.get("evidence_id") or "").strip()
        for item in updated
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    }
    for operand in list(operands or []):
        row = dict(operand or {})
        raw_value = _normalise_spaces(str(row.get("raw_value") or row.get("value") or ""))
        raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
        rendered_value = _normalise_spaces(str(row.get("rendered_value") or row.get("display") or ""))
        source_anchor = _normalise_spaces(str(row.get("source_anchor") or ""))
        source_quote = _normalise_spaces(
            str(row.get("source_quote") or row.get("quote_span") or row.get("raw_row_text") or "")
        )
        if (not raw_value and not rendered_value) or not source_anchor:
            continue
        display_value = rendered_value or _normalise_spaces(f"{raw_value}{raw_unit}")
        operand_text = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    row.get("label"),
                    row.get("period"),
                    display_value,
                )
            )
        )
        operand_candidates = extract_numeric_surface_candidates(operand_text)
        supports_answer_numeric = any(
            numeric_surface_candidates_equivalent(answer_candidate, operand_candidate)
            for answer_candidate in answer_candidates
            for operand_candidate in operand_candidates
        )
        supports_answer_numeric_surface = False
        answer_surface = re.sub(r"[\s,]", "", _normalise_spaces(final_answer))
        raw_surface = re.sub(r"[\s,]", "", raw_value)
        raw_unit_surface = re.sub(r"[\s,]", "", f"{raw_value}{raw_unit}")
        rendered_surface = re.sub(r"[\s,]", "", rendered_value)
        if raw_surface and raw_surface in answer_surface:
            supports_answer_numeric = True
            supports_answer_numeric_surface = True
        if raw_unit_surface and raw_unit_surface in answer_surface:
            supports_answer_numeric = True
            supports_answer_numeric_surface = True
        if rendered_surface and rendered_surface in answer_surface:
            supports_answer_numeric = True
            supports_answer_numeric_surface = True
        role = _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or ""))
        normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
        supports_derived_percent = bool(
            answer_has_percent
            and role in derivation_roles
            and normalized_unit == "KRW"
            and operand_candidates
        )
        if not supports_answer_numeric and not supports_derived_percent:
            continue
        operand_id = _normalise_spaces(str(row.get("operand_id") or row.get("matched_operand_role") or "operand"))
        evidence_id = f"operand::{operand_id}"
        if evidence_id in seen_ids:
            continue
        seen_ids.add(evidence_id)
        updated.append(
            {
                "evidence_id": evidence_id,
                "source_anchor": source_anchor,
                "claim": operand_text,
                "quote_span": source_quote or operand_text,
                "support_level": "direct",
                "question_relevance": "high",
                "metadata": {
                    "section_path": source_anchor,
                    "unit_hint": raw_unit,
                    "operand_role": role,
                    "supports_derived_percent": supports_derived_percent,
                    "supports_answer_numeric_surface": supports_answer_numeric_surface,
                },
            }
        )
    return updated


def append_final_answer_surface_operands_from_evidence(
    projection: Dict[str, Any],
    evidence_items: List[Dict[str, Any]],
    *,
    final_answer: str,
) -> Dict[str, Any]:
    answer_candidates = [
        dict(candidate)
        for candidate in extract_numeric_surface_candidates(final_answer)
        if str(candidate.get("kind") or "") != "percent"
    ]
    if not answer_candidates or not evidence_items:
        return projection

    updated = dict(projection or {})
    operands = [dict(row or {}) for row in list(updated.get("calculation_operands") or [])]

    def _operand_text(row: Dict[str, Any]) -> str:
        return _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    row.get("label"),
                    row.get("period"),
                    row.get("raw_value"),
                    row.get("raw_unit"),
                    row.get("rendered_value"),
                    row.get("source_quote"),
                )
            )
        )

    def _operand_supports(candidate: Dict[str, Any]) -> bool:
        for operand in operands:
            for operand_candidate in extract_numeric_surface_candidates(_operand_text(operand)):
                if numeric_surface_candidates_equivalent(candidate, operand_candidate):
                    return True
        return False

    calculation_result = dict(updated.get("calculation_result") or {})
    current_period = _normalise_spaces(str(calculation_result.get("current_period") or ""))
    prior_period = _normalise_spaces(str(calculation_result.get("prior_period") or ""))
    existing_period_roles: Dict[str, str] = {}
    label_hint = ""
    concept_hint = ""
    for operand in operands:
        period = _normalise_spaces(str(operand.get("period") or ""))
        role = _normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or ""))
        if period and role:
            existing_period_roles.setdefault(period, role)
        if not label_hint:
            label_hint = _normalise_spaces(str(operand.get("label") or ""))
        if not concept_hint:
            concept_hint = _normalise_spaces(str(operand.get("concept") or ""))

    def _collect_period_roles(value: Any) -> None:
        if isinstance(value, dict):
            current = _normalise_spaces(str(value.get("current_period") or ""))
            prior = _normalise_spaces(str(value.get("prior_period") or ""))
            if current:
                existing_period_roles.setdefault(current, "current_period")
            if prior:
                existing_period_roles.setdefault(prior, "prior_period")
            for nested in value.values():
                if isinstance(nested, (dict, list)):
                    _collect_period_roles(nested)
        elif isinstance(value, list):
            for nested in value:
                if isinstance(nested, (dict, list)):
                    _collect_period_roles(nested)

    _collect_period_roles(calculation_result)

    def _period_near_answer_candidate(candidate: Dict[str, Any]) -> str:
        span = candidate.get("span")
        if not isinstance(span, (list, tuple)) or len(span) != 2:
            return ""
        try:
            start = max(0, int(span[0]) - 80)
            end = min(len(final_answer), int(span[1]) + 30)
            candidate_start = int(span[0]) - start
        except (TypeError, ValueError):
            return ""
        matches = list(re.finditer(r"20\d{2}", final_answer[start:end]))
        if not matches:
            return ""
        before = [match.group(0) for match in matches if match.start() <= candidate_start]
        return before[-1] if before else matches[0].group(0)

    def _role_for_period(period: str) -> str:
        if period in existing_period_roles:
            return existing_period_roles[period]
        if current_period and period == current_period:
            return "current_period"
        if prior_period and period == prior_period:
            return "prior_period"
        if any(role == "current_period" for role in existing_period_roles.values()):
            existing_current_periods = {
                period_value
                for period_value, role in existing_period_roles.items()
                if role == "current_period"
            }
            if period and period not in existing_current_periods:
                return "prior_period"
        return "answer_numeric_surface"

    def _best_evidence_for_candidate(candidate: Dict[str, Any]) -> tuple[Dict[str, Any], Dict[str, Any]]:
        best: tuple[int, Dict[str, Any], Dict[str, Any]] | None = None
        period_hint = _period_near_answer_candidate(candidate)
        for evidence in list(evidence_items or []):
            item = dict(evidence or {})
            text = evidence_text_for_numeric_support(item)
            if not text:
                continue
            for evidence_candidate in extract_numeric_surface_candidates(text):
                if not numeric_surface_candidates_equivalent(candidate, evidence_candidate):
                    continue
                metadata = dict(item.get("metadata") or {})
                score = 0
                if str(item.get("evidence_id") or "").startswith("operand::"):
                    score += 3
                if metadata.get("supports_answer_numeric_surface"):
                    score += 2
                if str(item.get("evidence_id") or "").startswith("recon::"):
                    score += 1
                score += numeric_evidence_relevance_score(
                    item,
                    answer_text=final_answer,
                    answer_candidate=candidate,
                    label_hints=(label_hint, concept_hint),
                    period_hint=period_hint,
                )
                if best is None or score > best[0]:
                    best = (score, item, dict(evidence_candidate))
        if best is None:
            return {}, {}
        return best[1], best[2]

    def _slot_numeric_abs(row: Dict[str, Any]) -> Optional[float]:
        value = coerce_slot_numeric(row.get("normalized_value"))
        if value is None:
            raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
            raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
            value, _unit = _normalise_operand_value(raw_value, raw_unit)
        if value is None:
            return None
        return abs(float(value))

    def _with_abs_normalized_value(row: Dict[str, Any]) -> Dict[str, Any]:
        updated_row = dict(row)
        value = _slot_numeric_abs(updated_row)
        if value is not None:
            updated_row["normalized_value"] = value
        return updated_row

    def _sync_growth_result_from_answer_surface() -> bool:
        current_rows = [
            dict(row)
            for row in operands
            if _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()
            == "current_period"
        ]
        prior_rows = [
            dict(row)
            for row in operands
            if _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()
            == "prior_period"
        ]
        if not current_rows or not prior_rows:
            return False
        current_row = current_rows[0]
        prior_row = prior_rows[0]
        current_value = _slot_numeric_abs(current_row)
        prior_value = _slot_numeric_abs(prior_row)
        if current_value is None or prior_value in (None, 0):
            return False
        result_value = ((current_value - float(prior_value)) / float(prior_value)) * 100.0
        percent_candidates = [
            dict(candidate)
            for candidate in extract_numeric_surface_candidates(final_answer)
            if str(candidate.get("kind") or "") == "percent"
        ]
        matched_percent: Dict[str, Any] = {}
        for candidate in percent_candidates:
            candidate_value = coerce_slot_numeric(
                candidate.get("normalized_value") if candidate.get("normalized_value") is not None else candidate.get("value")
            )
            if candidate_value is None:
                continue
            tolerance = max(abs(result_value), abs(float(candidate_value)), 1.0) * 1e-3
            if abs(result_value - float(candidate_value)) <= tolerance:
                matched_percent = candidate
                break
        if not matched_percent:
            return False
        display_value = _normalise_spaces(str(matched_percent.get("value_text") or matched_percent.get("text") or ""))
        if not display_value:
            display_value = f"{result_value:.2f}%"
        source_row_ids = _clean_source_row_ids(
            [
                current_row.get("source_row_id"),
                current_row.get("source_row_ids"),
                prior_row.get("source_row_id"),
                prior_row.get("source_row_ids"),
            ]
        )
        current_slot = build_operand_value_slot(
            _with_abs_normalized_value(current_row),
            default_role="current_period",
            preserve_source_display=True,
        )
        prior_slot = build_operand_value_slot(
            _with_abs_normalized_value(prior_row),
            default_role="prior_period",
            preserve_source_display=True,
        )
        calculation_result = dict(updated.get("calculation_result") or {})
        calculation_result.update(
            {
                "status": "ok",
                "operation_family": "growth_rate",
                "result_value": result_value,
                "result_unit": "%",
                "rendered_value": display_value,
                "formatted_result": final_answer,
                "current_value": current_value,
                "prior_value": float(prior_value),
                "current_period": _normalise_spaces(str(current_row.get("period") or current_period or "")),
                "prior_period": _normalise_spaces(str(prior_row.get("period") or prior_period or "")),
                "source_row_ids": source_row_ids,
                "source_evidence_ids": source_row_ids,
                "answer_slots": {
                    "metric_label": label_hint,
                    "operation_family": "growth_rate",
                    "source_row_ids": source_row_ids,
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": label_hint,
                        "concept": concept_hint,
                        "period": "",
                        "raw_value": display_value,
                        "raw_unit": "%",
                        "normalized_value": result_value,
                        "normalized_unit": "PERCENT",
                        "rendered_value": display_value,
                        "source_row_id": source_row_ids[0] if source_row_ids else "",
                        "source_row_ids": source_row_ids,
                        "source_anchor": "",
                    },
                    "components_by_role": {
                        "current_period": [current_slot],
                        "prior_period": [prior_slot],
                    },
                    "components_by_group": {
                        "current": [current_slot],
                        "prior": [prior_slot],
                    },
                },
                "derived_metrics": {
                    **dict(calculation_result.get("derived_metrics") or {}),
                    "operation_family": "growth_rate",
                    "formula_result_value": result_value,
                    "final_answer_surface_trace_sync": True,
                },
            }
        )
        updated["calculation_result"] = calculation_result
        calculation_plan = dict(updated.get("calculation_plan") or {})
        calculation_plan.update({"status": "ok", "operation": "growth_rate", "result_unit": "%"})
        updated["calculation_plan"] = calculation_plan
        return True

    appended = False
    for candidate in answer_candidates:
        if _operand_supports(candidate):
            continue
        evidence, evidence_candidate = _best_evidence_for_candidate(candidate)
        if not evidence or not evidence_candidate:
            continue
        slot_components = numeric_surface_slot_components(candidate) or numeric_surface_slot_components(evidence_candidate)
        if not slot_components:
            continue
        metadata = dict(evidence.get("metadata") or {})
        evidence_id = _normalise_spaces(str(evidence.get("evidence_id") or ""))
        period = _period_near_answer_candidate(candidate)
        role = _normalise_spaces(str(metadata.get("operand_role") or "")) or _role_for_period(period)
        operand_id = role
        if any(_normalise_spaces(str(row.get("operand_id") or "")) == operand_id for row in operands):
            operand_id = f"answer_surface_{len(operands) + 1:03d}"
        row = {
            "status": "ok",
            "role": role,
            "matched_operand_role": role,
            "operand_id": operand_id,
            "label": label_hint,
            "concept": concept_hint,
            "period": period,
            **slot_components,
            "source_row_id": evidence_id,
            "source_row_ids": [evidence_id] if evidence_id else [],
            "source_anchor": _normalise_spaces(str(evidence.get("source_anchor") or "")),
            "source_quote": _normalise_spaces(str(evidence.get("quote_span") or evidence.get("claim") or "")),
            "projection_backfilled_from_final_evidence": True,
        }
        operands.append(row)
        appended = True

    synced_growth_result = _sync_growth_result_from_answer_surface()
    if appended or synced_growth_result:
        updated["calculation_operands"] = operands
    return updated


def filter_aggregate_projection_provenance(
    filter_input: AggregateProjectionProvenanceFilterInput,
) -> AggregateProjectionProvenanceFilterResult:
    """Remove pruned generated evidence refs from a prepared aggregate projection."""

    kept = {
        str(value).strip()
        for value in (filter_input.kept_evidence_ids or [])
        if str(value).strip()
    }
    if not kept:
        return AggregateProjectionProvenanceFilterResult(
            aggregate_projection=filter_input.aggregate_projection,
        )

    def _filter_ids(values: Any) -> List[str]:
        current = _clean_source_row_ids([values])
        return [
            value
            for value in current
            if not (value.startswith("ev_") or value.startswith("recon::")) or value in kept
        ]

    updated = dict(filter_input.aggregate_projection)
    calculation_result = dict(updated.get("calculation_result") or {})
    calculation_result["source_evidence_ids"] = _filter_ids(calculation_result.get("source_evidence_ids"))
    calculation_result["source_row_ids"] = _filter_ids(calculation_result.get("source_row_ids"))
    derived_metrics = dict(calculation_result.get("derived_metrics") or {})
    for key in ("aggregate_source_evidence_ids", "aggregate_source_row_ids"):
        if key in derived_metrics:
            derived_metrics[key] = _filter_ids(derived_metrics.get(key))
    calculation_result["derived_metrics"] = derived_metrics
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    if answer_slots:
        answer_slots["source_row_ids"] = _filter_ids(answer_slots.get("source_row_ids"))
        subtask_results: List[Dict[str, Any]] = []
        for subtask in list(answer_slots.get("subtask_results") or []):
            if not isinstance(subtask, dict):
                continue
            row = dict(subtask)
            row["source_evidence_ids"] = _filter_ids(row.get("source_evidence_ids"))
            row["source_row_ids"] = _filter_ids(row.get("source_row_ids"))
            subtask_results.append(row)
        if subtask_results:
            answer_slots["subtask_results"] = subtask_results
        calculation_result["answer_slots"] = answer_slots
    updated["calculation_result"] = calculation_result
    return AggregateProjectionProvenanceFilterResult(
        aggregate_projection=updated,
    )


def synchronize_nested_aggregate_subtask_rows(
    sync_input: AggregateNestedSubtaskSynchronizationInput,
) -> AggregateNestedSubtaskSynchronizationResult:
    """Recursively synchronize nested task rows from current ordered results."""

    ordered_results = sync_input.ordered_results
    by_task_id = {
        _normalise_spaces(str(row.get("task_id") or "")): dict(row)
        for row in ordered_results
        if _normalise_spaces(str(row.get("task_id") or ""))
    }

    def _sync_rows(rows: List[Any], stack: set[str], depth: int) -> List[Dict[str, Any]]:
        synced: List[Dict[str, Any]] = []
        for item in rows:
            if not isinstance(item, dict):
                continue
            task_id = _normalise_spaces(str(item.get("task_id") or ""))
            source = dict(item)
            if task_id and task_id not in stack and by_task_id.get(task_id):
                source = dict(by_task_id[task_id])
            synced.append(_sync_row(source, stack, depth + 1))
        return synced

    def _sync_row(row: Dict[str, Any], stack: set[str], depth: int = 0) -> Dict[str, Any]:
        if depth > 8:
            return dict(row)
        synced = dict(row)
        task_id = _normalise_spaces(str(synced.get("task_id") or ""))
        child_stack = set(stack)
        if task_id:
            child_stack.add(task_id)

        calculation_result = dict(synced.get("calculation_result") or {})
        if calculation_result:
            nested_rows = list(calculation_result.get("subtask_results") or [])
            if nested_rows:
                calculation_result["subtask_results"] = _sync_rows(nested_rows, child_stack, depth)
            answer_slots = dict(calculation_result.get("answer_slots") or {})
            nested_slot_rows = list(answer_slots.get("subtask_results") or [])
            if nested_slot_rows:
                answer_slots["subtask_results"] = _sync_rows(nested_slot_rows, child_stack, depth)
                calculation_result["answer_slots"] = answer_slots
            synced["calculation_result"] = calculation_result

        row_answer_slots = dict(synced.get("answer_slots") or {})
        row_nested_slot_rows = list(row_answer_slots.get("subtask_results") or [])
        if row_nested_slot_rows:
            row_answer_slots["subtask_results"] = _sync_rows(row_nested_slot_rows, child_stack, depth)
            synced["answer_slots"] = row_answer_slots
        return synced

    return AggregateNestedSubtaskSynchronizationResult(
        ordered_results=[_sync_row(dict(row), set()) for row in ordered_results],
    )


def sync_aggregate_projection_final_answer(
    sync_input: AggregateProjectionFinalAnswerSyncInput,
) -> AggregateProjectionFinalAnswerSyncResult:
    """Synchronize one prepared answer onto the same aggregate projection."""

    aggregate_projection = sync_input.aggregate_projection
    final_answer = sync_input.final_answer
    if not final_answer:
        return AggregateProjectionFinalAnswerSyncResult(
            aggregate_projection=aggregate_projection,
        )
    calculation_result = aggregate_projection.setdefault("calculation_result", {})
    calculation_result["formatted_result"] = final_answer
    if (
        sync_input.sync_rendered_for_aggregate
        and str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks"
    ):
        calculation_result["rendered_value"] = final_answer
    if sync_input.status_ok:
        calculation_result["status"] = "ok"
    return AggregateProjectionFinalAnswerSyncResult(
        aggregate_projection=aggregate_projection,
    )


def package_aggregate_answer_candidate(
    packaging_input: AggregateAnswerCandidatePackagingInput,
) -> AggregateAnswerCandidatePackagingResult:
    """Build one normalized aggregate-answer candidate payload."""

    return AggregateAnswerCandidatePackagingResult(
        candidate={
            "answer": _normalise_spaces(str(packaging_input.answer or "")),
            "selected_claim_ids": [
                str(claim_id).strip()
                for claim_id in (packaging_input.selected_claim_ids or [])
                if str(claim_id).strip()
            ],
            "sync_projection": bool(packaging_input.sync_projection),
            "sync_rendered_for_aggregate": bool(packaging_input.sync_rendered_for_aggregate),
            "status_ok": bool(packaging_input.status_ok),
        }
    )


def package_refreshed_aggregate_answer_candidate(
    packaging_input: AggregateRefreshedAnswerCandidatePackagingInput,
) -> AggregateAnswerCandidatePackagingResult:
    """Package a prepared refreshed answer with the existing fallback order."""

    payload = dict(packaging_input.refreshed_answer or {})
    return package_aggregate_answer_candidate(
        AggregateAnswerCandidatePackagingInput(
            answer=str(payload.get("answer") or packaging_input.fallback_answer or ""),
            selected_claim_ids=payload.get("selected_claim_ids") or [],
            sync_projection=packaging_input.sync_projection,
            sync_rendered_for_aggregate=packaging_input.sync_rendered_for_aggregate,
            status_ok=packaging_input.status_ok,
        )
    )


def apply_aggregate_answer_candidate(
    application_input: AggregateAnswerCandidateApplicationInput,
) -> AggregateAnswerCandidateApplicationResult:
    """Apply one graph-prepared candidate without selecting or refreshing it."""

    candidate = application_input.candidate
    aggregate_projection = application_input.aggregate_projection
    final_answer = _normalise_spaces(str((candidate or {}).get("answer") or ""))
    if bool((candidate or {}).get("sync_projection", True)):
        sync_rendered_for_aggregate = bool(
            (candidate or {}).get("sync_rendered_for_aggregate", True)
        )
        status_ok = bool((candidate or {}).get("status_ok", False))
        aggregate_projection = sync_aggregate_projection_final_answer(
            AggregateProjectionFinalAnswerSyncInput(
                aggregate_projection=aggregate_projection,
                final_answer=final_answer,
                sync_rendered_for_aggregate=sync_rendered_for_aggregate,
                status_ok=status_ok,
            )
        ).aggregate_projection
    merged_claim_ids = list(
        dict.fromkeys(
            [
                *[
                    str(claim_id).strip()
                    for claim_id in (application_input.selected_claim_ids or [])
                    if str(claim_id).strip()
                ],
                *[
                    str(claim_id).strip()
                    for claim_id in ((candidate or {}).get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
            ]
        )
    )
    return AggregateAnswerCandidateApplicationResult(
        aggregate_projection=aggregate_projection,
        final_answer=final_answer,
        selected_claim_ids=merged_claim_ids,
    )


def subtask_numeric_answers_conflict(
    candidate_row: Mapping[str, Any],
    current_row: Mapping[str, Any],
) -> bool:
    candidate_answer = _normalise_spaces(
        str(
            candidate_row.get("answer")
            or (candidate_row.get("calculation_result") or {}).get("formatted_result")
            or (candidate_row.get("calculation_result") or {}).get("rendered_value")
            or ""
        )
    )
    current_answer = _normalise_spaces(
        str(
            current_row.get("answer")
            or (current_row.get("calculation_result") or {}).get("formatted_result")
            or (current_row.get("calculation_result") or {}).get("rendered_value")
            or ""
        )
    )
    candidate_numbers = extract_numeric_surface_candidates(candidate_answer)
    current_numbers = extract_numeric_surface_candidates(current_answer)
    if not candidate_numbers or not current_numbers:
        return False
    return not all(
        any(
            numeric_surface_candidates_equivalent(candidate_number, current_number)
            for current_number in current_numbers
        )
        for candidate_number in candidate_numbers
    )


def subtask_row_has_direct_source_refs(row: Mapping[str, Any]) -> bool:
    calculation_result = dict(row.get("calculation_result") or {})
    source_ids = _clean_source_row_ids([
        row.get("source_row_ids"),
        calculation_result.get("source_row_ids"),
        row.get("selected_claim_ids"),
        calculation_result.get("source_evidence_ids"),
    ])
    return any(source_id and not source_id.startswith("task_output:") for source_id in source_ids)


def aggregate_result_operation_family(row: Mapping[str, Any]) -> str:
    """Return the normalized operation family projected by an aggregate row."""

    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    operation_family = _normalise_spaces(
        str(
            row.get("operation_family")
            or answer_slots.get("operation_family")
            or (row.get("calculation_plan") or {}).get("operation")
            or ""
        )
    ).lower()
    if not operation_family:
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if metric_family.startswith("concept_"):
            operation_family = metric_family.removeprefix("concept_")
        elif metric_family.endswith("_ratio"):
            operation_family = "ratio"
        elif metric_family.endswith("_growth_rate"):
            operation_family = "growth_rate"
        elif metric_family.endswith("_difference"):
            operation_family = "difference"
        elif metric_family.endswith("_sum"):
            operation_family = "sum"
    operation_aliases = {
        "divide": "ratio",
        "division": "ratio",
        "subtract": "difference",
        "subtraction": "difference",
        "add": "sum",
        "addition": "sum",
    }
    return operation_aliases.get(operation_family, operation_family)


def align_lookup_result_units_from_own_evidence(
    ordered_results: List[Dict[str, Any]],
    evidence_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    evidence_by_id = _evidence_items_by_id(evidence_items)
    if not evidence_by_id:
        return ordered_results

    aligned_results: List[Dict[str, Any]] = []
    changed_any = False
    for row in ordered_results:
        operation_family = _normalise_spaces(
            str(row.get("operation_family") or aggregate_result_operation_family(row) or "")
        ).lower()
        if operation_family not in {"lookup", "single_value"}:
            aligned_results.append(row)
            continue
        primary_slot = lookup_primary_slot(row)
        if not answer_slot_has_material(primary_slot):
            aligned_results.append(row)
            continue
        raw_value = _normalise_spaces(str(primary_slot.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(primary_slot.get("raw_unit") or ""))
        evidence_item = _evidence_item_for_operand_row(primary_slot, evidence_by_id)
        if not raw_value or not evidence_item:
            aligned_results.append(row)
            continue
        coerced_unit = coerce_operand_unit_from_evidence(
            raw_value=raw_value,
            raw_unit=raw_unit,
            evidence_item=evidence_item,
        )
        if not coerced_unit or coerced_unit == raw_unit:
            aligned_results.append(row)
            continue
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, coerced_unit)
        if normalized_value is None:
            aligned_results.append(row)
            continue

        source_ids = set(
            _clean_source_row_ids([primary_slot.get("source_row_id"), primary_slot.get("source_row_ids")])
        )
        updated_primary = {
            **primary_slot,
            "raw_unit": coerced_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "rendered_value": f"{raw_value}{coerced_unit}",
            "unit_aligned_from_own_evidence": True,
        }
        aligned_results.append(
            replace_lookup_primary_slot(
                row,
                updated_primary,
                marker_key="unit_aligned_from_own_evidence",
                component_source_ids=source_ids,
            )
        )
        changed_any = True
    return aligned_results if changed_any else ordered_results


def row_is_narrative_summary(row: Dict[str, Any]) -> bool:
    metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
    operation_family = aggregate_result_operation_family(row)
    return metric_family == "narrative_summary" or operation_family == "narrative_summary"


def aggregate_results_include_dependency_numeric_result(
    ordered_results: List[Dict[str, Any]],
) -> bool:
    for row in ordered_results:
        operation_family = aggregate_result_operation_family(row)
        if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
            continue
        calculation_result = dict(row.get("calculation_result") or {})
        candidate_sources = _clean_source_row_ids([
            calculation_result.get("source_row_ids"),
            row.get("source_row_ids"),
            [
                [
                    operand.get("evidence_id"),
                    operand.get("source_row_id"),
                    operand.get("source_row_ids"),
                ]
                for operand in list(row.get("calculation_operands") or [])
                if isinstance(operand, dict)
            ],
            [
                [
                    operand.get("evidence_id"),
                    operand.get("source_row_id"),
                    operand.get("source_row_ids"),
                ]
                for operand in list(calculation_result.get("calculation_operands") or [])
                if isinstance(operand, dict)
            ],
        ])
        if any(str(source_id).startswith("task_output:") for source_id in candidate_sources):
            return True
        if any(
            bool((operand or {}).get("dependency_resolved"))
            for operand in list(row.get("calculation_operands") or [])
            if isinstance(operand, dict)
        ):
            return True
    return False


def aggregate_results_include_source_task_slot_realignment(
    ordered_results: List[Dict[str, Any]],
) -> bool:
    for row in ordered_results:
        if not row.get("aligned_from_source_task_slots"):
            continue
        operation_family = aggregate_result_operation_family(row)
        if operation_family in {"ratio", "sum", "difference", "growth_rate"}:
            return True
    return False


def answer_reuses_narrative_summary_text(
    answer: str,
    ordered_results: List[Dict[str, Any]],
) -> bool:
    answer_text = _normalise_spaces(str(answer or ""))
    if not answer_text:
        return False
    for row in ordered_results:
        if not row_is_narrative_summary(row):
            continue
        narrative_answer = _normalise_spaces(str(row.get("answer") or ""))
        if len(narrative_answer) < 20 or not re.search(r"\d", narrative_answer):
            continue
        if narrative_answer in answer_text or answer_text in narrative_answer:
            return True
    return False


def answer_reuses_numeric_narrative_summary_text(
    answer: str,
    ordered_results: List[Dict[str, Any]],
) -> bool:
    if not answer_reuses_narrative_summary_text(answer, ordered_results):
        return False
    non_percent_candidates = [
        candidate
        for candidate in extract_numeric_surface_candidates(answer)
        if str(candidate.get("kind") or "") != "percent"
    ]
    return len(non_percent_candidates) >= 2


def narrative_row_focus_sentence(
    *,
    ordered_results: List[Dict[str, Any]],
    focus_variants: List[str],
) -> Optional[tuple[int, str, List[str]]]:
    if not focus_variants:
        return None
    for row in ordered_results or []:
        operation_family = aggregate_result_operation_family(row)
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if operation_family != "narrative_summary" and metric_family != "narrative_summary":
            continue
        claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
        narrative_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ()))
        for sentence in _split_narrative_sentences(str(row.get("answer") or "")):
            cleaned = _normalise_spaces(sentence)
            if not cleaned:
                continue
            if narrative_sentence_looks_table_noisy(cleaned):
                continue
            if narrative_sentence_looks_abbreviated_fragment(cleaned, narrative_markers):
                continue
            haystack = cleaned.lower()
            if any(variant.lower() in haystack for variant in focus_variants):
                return (0, cleaned, claim_ids)
    return None


def narrative_row_focus_context(
    *,
    query: str,
    ordered_results: List[Dict[str, Any]],
    focus_variants: List[str],
    max_sentences: int = 2,
) -> Optional[tuple[int, str, List[str]]]:
    if not focus_variants:
        return None
    query_terms = narrative_context_terms(query)
    impact_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ()))
    for row in ordered_results or []:
        operation_family = aggregate_result_operation_family(row)
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if operation_family != "narrative_summary" and metric_family != "narrative_summary":
            continue
        claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
        sentences = [
            sentence
            for sentence in _split_narrative_sentences(str(row.get("answer") or ""))
            if not narrative_sentence_looks_table_noisy(sentence)
            and not narrative_sentence_looks_abbreviated_fragment(sentence, impact_markers)
        ]
        scored_focus_indexes: List[tuple[int, int]] = []
        for index, sentence in enumerate(sentences):
            haystack = sentence.lower()
            focus_hits = sum(1 for variant in focus_variants if variant.lower() in haystack)
            if not focus_hits:
                continue
            marker_hits = sum(1 for marker in impact_markers if marker in sentence)
            query_hits = sum(1 for term in query_terms if term.lower() in haystack)
            numeric_hits = len(re.findall(r"\d[\d,]*(?:\.\d+)?%?", sentence))
            score = focus_hits * 5 + marker_hits * 3 + query_hits - numeric_hits
            scored_focus_indexes.append((score, index))
        scored_focus_indexes.sort(key=lambda item: item[0], reverse=True)
        focus_indexes = [index for _, index in scored_focus_indexes]
        if not focus_indexes:
            continue
        selected: List[str] = []
        selected_indexes: set[int] = set()

        def _select(index: int) -> None:
            if index in selected_indexes or index < 0 or index >= len(sentences):
                return
            selected_indexes.add(index)
            selected.append(sentences[index])

        focus_index = focus_indexes[0]
        _select(focus_index)
        if any(marker in sentences[focus_index] for marker in impact_markers):
            return (0, _normalise_spaces(" ".join(selected)), claim_ids)
        ordered_indexes = [
            *range(focus_index + 1, len(sentences)),
            *range(0, focus_index),
        ]
        for index in ordered_indexes:
            if len(selected) >= max_sentences:
                break
            if index in selected_indexes:
                continue
            sentence = sentences[index]
            haystack = sentence.lower()
            if any(term.lower() in haystack for term in query_terms) or any(marker in sentence for marker in impact_markers):
                _select(index)
        if selected:
            return (0, _normalise_spaces(" ".join(selected)), claim_ids)
    return None


def _slot_display_from_source_task(
    slot: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
) -> str:
    source_task_id = _normalise_spaces(str(slot.get("source_task_id") or ""))
    if not source_task_id:
        source_row_id = _normalise_spaces(str(slot.get("source_row_id") or ""))
        if source_row_id.startswith("task_output:"):
            source_task_id = source_row_id.split(":", 1)[1]
    if not source_task_id:
        return ""
    source_slot_name = _normalise_spaces(str(slot.get("source_slot") or "primary_value")) or "primary_value"
    for row in ordered_results:
        if _normalise_spaces(str(row.get("task_id") or "")) != source_task_id:
            continue
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        source_slot = dict(answer_slots.get(source_slot_name) or answer_slots.get("primary_value") or {})
        if answer_slot_has_material(source_slot):
            return _normalise_spaces(
                str(source_slot.get("rendered_value") or source_slot.get("raw_value") or "")
            )
    return ""


def growth_slot_display_value(
    slot: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
) -> str:
    source_display = _slot_display_from_source_task(slot, ordered_results)
    if source_display and source_task_display_compatible_with_slot(slot, source_display):
        return source_display
    return _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))


def growth_slots_share_material(
    current_slot: Dict[str, Any],
    prior_slot: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
) -> bool:
    current_display = growth_slot_display_value(current_slot, ordered_results)
    prior_display = growth_slot_display_value(prior_slot, ordered_results)
    if current_display and prior_display and current_display == prior_display:
        return True
    current_value = current_slot.get("normalized_value")
    prior_value = prior_slot.get("normalized_value")
    if current_value is None or prior_value is None:
        return False
    try:
        return float(current_value) == float(prior_value)
    except (TypeError, ValueError):
        return False


def recover_growth_prior_material_from_evidence(
    *,
    current_slot: Dict[str, Any],
    prior_slot: Dict[str, Any],
    evidence_items: Optional[List[Dict[str, Any]]],
) -> Dict[str, str]:
    if not evidence_items:
        return {}
    current_year_match = re.search(r"\d{4}", str(current_slot.get("period") or current_slot.get("label") or ""))
    if not current_year_match:
        return {}
    current_year = int(current_year_match.group(0))
    current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
    current_raw_compact = re.sub(r"[^\d.]", "", current_raw)
    raw_unit = _normalise_spaces(str(prior_slot.get("raw_unit") or current_slot.get("raw_unit") or ""))
    if raw_unit:
        unit_pattern = r"\s*".join(re.escape(part) for part in re.split(r"\s+", raw_unit) if part)
    else:
        unit_pattern = r"[^\s\d,.;:()]{0,12}"
    number_with_unit_pattern = re.compile(
        rf"(?P<value>\d[\d,]*(?:\.\d+)?)\s*(?P<unit>{unit_pattern})"
    )
    for item in evidence_items:
        surface = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    (item or {}).get("claim"),
                    (item or {}).get("quote_span"),
                    (item or {}).get("raw_row_text"),
                )
            )
        )
        if not surface:
            continue
        for sentence in _split_narrative_sentences(surface) or [surface]:
            years = [int(match.group(0)) for match in re.finditer(r"\d{4}", sentence)]
            if not years or min(years) >= current_year:
                continue
            prior_year = max(year for year in years if year < current_year)
            for match in number_with_unit_pattern.finditer(sentence):
                value_text = _normalise_spaces(match.group("value"))
                value_compact = re.sub(r"[^\d.]", "", value_text)
                if current_raw_compact and value_compact == current_raw_compact:
                    continue
                display = _normalise_spaces(match.group(0))
                if display:
                    year_suffix = str(CALCULATION_NARRATIVE_POLICY.get("period_year_suffix") or "")
                    return {
                        "display": display,
                        "period": f"{prior_year}{year_suffix}" if year_suffix else str(prior_year),
                        "raw_value": value_text,
                        "source_quote": _normalise_spaces(sentence),
                    }
    return {}


def recover_duplicate_growth_prior_operand(
    ordered_operands: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    if len(ordered_operands) != 2:
        return ordered_operands
    current_row = next(
        (dict(row) for row in ordered_operands if str(row.get("matched_operand_role") or "").strip() == "current_period"),
        None,
    )
    prior_row = next(
        (dict(row) for row in ordered_operands if str(row.get("matched_operand_role") or "").strip() == "prior_period"),
        None,
    )
    if not current_row or not prior_row:
        return ordered_operands
    if not growth_slots_share_material(current_row, prior_row, []):
        return ordered_operands

    recovered = recover_growth_prior_material_from_evidence(
        current_slot=current_row,
        prior_slot=prior_row,
        evidence_items=evidence_items,
    )
    display = _normalise_spaces(str(recovered.get("display") or ""))
    raw_value = _normalise_spaces(str(recovered.get("raw_value") or ""))
    if not display or not raw_value:
        return ordered_operands

    raw_unit = _normalise_spaces(str(prior_row.get("raw_unit") or current_row.get("raw_unit") or ""))
    normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
    if normalized_value is None:
        return ordered_operands

    updated_prior = {
        **prior_row,
        "period": recovered.get("period") or prior_row.get("period") or "",
        "raw_value": raw_value,
        "raw_unit": raw_unit,
        "normalized_value": normalized_value,
        "normalized_unit": normalized_unit or prior_row.get("normalized_unit") or "",
        "rendered_value": display,
        "source_quote": recovered.get("source_quote") or prior_row.get("source_quote") or "",
        "prior_recovery_source": "evidence_period_display",
    }
    updated_rows = []
    for row in ordered_operands:
        if str(row.get("operand_id") or "") == str(updated_prior.get("operand_id") or ""):
            updated_rows.append(updated_prior)
        else:
            updated_rows.append(row)
    return updated_rows


def growth_required_display_values(
    row: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> List[str]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    primary_slot = dict(answer_slots.get("primary_value") or {})
    current_slot = dict(answer_slots.get("current_value") or {})
    prior_slot = dict(answer_slots.get("prior_value") or {})
    prior_display = growth_slot_display_value(prior_slot, ordered_results)
    if growth_slots_share_material(current_slot, prior_slot, ordered_results):
        recovered_prior_material = recover_growth_prior_material_from_evidence(
            current_slot=current_slot,
            prior_slot=prior_slot,
            evidence_items=evidence_items,
        )
        if recovered_prior_material.get("display"):
            prior_display = recovered_prior_material["display"]
    required_values = [
        growth_slot_display_value(current_slot, ordered_results),
        prior_display,
        _normalise_spaces(
            str(
                calculation_result.get("rendered_value")
                or growth_slot_display_value(primary_slot, ordered_results)
                or ""
            )
        ),
    ]
    return list(dict.fromkeys(value for value in required_values if value))


def compose_complete_growth_numeric_answer(
    row: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> str:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    if aggregate_result_operation_family(row) != "growth_rate":
        return ""
    primary_slot = dict(answer_slots.get("primary_value") or {})
    current_slot = dict(answer_slots.get("current_value") or {})
    prior_slot = dict(answer_slots.get("prior_value") or {})
    if not answer_slot_has_material(primary_slot):
        return ""

    growth_value = _normalise_spaces(str(calculation_result.get("rendered_value") or ""))
    if not growth_value:
        growth_value = _normalise_spaces(str(primary_slot.get("rendered_value") or primary_slot.get("raw_value") or ""))
    current_value = calculation_rendering.absolute_display_value(growth_slot_display_value(current_slot, ordered_results))
    prior_value = calculation_rendering.absolute_display_value(growth_slot_display_value(prior_slot, ordered_results))
    recovered_prior_period = ""
    if growth_slots_share_material(current_slot, prior_slot, ordered_results):
        recovered_prior_material = recover_growth_prior_material_from_evidence(
            current_slot=current_slot,
            prior_slot=prior_slot,
            evidence_items=evidence_items,
        )
        if recovered_prior_material.get("display"):
            prior_value = calculation_rendering.absolute_display_value(str(recovered_prior_material["display"]))
            recovered_prior_period = _normalise_spaces(str(recovered_prior_material.get("period") or ""))
    if not (growth_value and current_value and prior_value):
        return ""

    metric_label = _normalise_spaces(
        str(current_slot.get("label") or primary_slot.get("label") or row.get("metric_label") or "")
    )
    metric_label = re.sub(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), " ", metric_label)
    metric_label = _normalise_spaces(metric_label)
    if not metric_label:
        return ""

    current_period = _normalise_spaces(str(current_slot.get("period") or primary_slot.get("period") or ""))
    prior_period = _normalise_spaces(
        str(prior_slot.get("period") or CALCULATION_NARRATIVE_POLICY.get("default_prior_period") or "")
    )
    if recovered_prior_period:
        prior_period = recovered_prior_period
    direction = _normalise_spaces(str(primary_slot.get("direction") or primary_slot.get("direction_hint") or "")).lower()
    if not direction:
        normalized_value = primary_slot.get("normalized_value")
        if normalized_value is not None:
            try:
                direction = "decrease" if float(normalized_value) < 0 else "increase"
            except (TypeError, ValueError):
                direction = ""
        if not direction:
            direction = "decrease" if str(primary_slot.get("rendered_value") or "").strip().startswith("-") else "increase"
    direction_words = dict(CALCULATION_NARRATIVE_POLICY.get("direction_words") or {})
    growth_direction_metric_terms = tuple(
        str(item)
        for item in (CALCULATION_NARRATIVE_POLICY.get("growth_direction_metric_terms") or ())
        if str(item)
    )
    if direction == "decrease":
        direction_word = str(direction_words.get("decrease") or "decrease")
    elif any(term in metric_label for term in growth_direction_metric_terms):
        direction_word = str(direction_words.get("growth") or direction_words.get("increase") or "increase")
    else:
        direction_word = str(direction_words.get("increase") or "increase")

    year_suffix = str(CALCULATION_NARRATIVE_POLICY.get("period_year_suffix") or "")
    if current_period and year_suffix and not current_period.endswith(year_suffix):
        period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_with_year_template") or "").format(
            period=current_period
        )
    elif current_period:
        period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_template") or "").format(
            period=current_period
        )
    else:
        period_prefix = ""
    prior_period_display = prior_period
    if prior_period_display and year_suffix and re.fullmatch(r"\d{4}", prior_period_display):
        prior_period_display = f"{prior_period_display}{year_suffix}"
    prior_phrase = str(CALCULATION_NARRATIVE_POLICY.get("prior_phrase_with_value_template") or "").format(
        period=prior_period_display,
        value=prior_value,
    )
    return _normalise_spaces(
        str(CALCULATION_NARRATIVE_POLICY.get("growth_numeric_sentence_template") or "").format(
            period_prefix=period_prefix,
            metric_label=metric_label,
            topic_particle=topic_particle(metric_label),
            current_value=current_value,
            prior_phrase=prior_phrase,
            growth_value=calculation_rendering.absolute_display_value(growth_value),
            direction_word=direction_word,
        )
    )


def growth_answer_has_untraced_numeric_material(
    answer: str,
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    answer_text = _normalise_spaces(str(answer or ""))
    if not answer_text:
        return False
    for row in ordered_results:
        if aggregate_result_operation_family(row) != "growth_rate":
            continue
        if growth_row_has_conflicting_periods(row):
            continue
        complete_answer = compose_complete_growth_numeric_answer(row, ordered_results)
        required_values = growth_required_display_values(row, ordered_results, evidence_items)
        if not complete_answer or not required_values:
            continue
        if growth_answer_has_untraced_numeric_sentence(answer_text, complete_answer, required_values):
            return True
        for sentence in _split_narrative_sentences(answer_text):
            if growth_sentence_has_untraced_material_numeric(
                sentence,
                complete_answer,
                required_values,
                evidence_items,
            ):
                return True
    return False


def ensure_complete_growth_numeric_answer(
    answer: str,
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> str:
    answer_text = _normalise_spaces(str(answer or ""))
    for row in reversed(ordered_results):
        if aggregate_result_operation_family(row) != "growth_rate":
            continue
        if growth_row_has_conflicting_periods(row):
            continue
        complete_answer = compose_complete_growth_numeric_answer(
            row,
            ordered_results,
            evidence_items=evidence_items,
        )
        if not complete_answer:
            continue
        required_values = growth_required_display_values(row, ordered_results, evidence_items)
        if (
            required_values
            and all(value in answer_text for value in required_values)
            and not growth_answer_has_untraced_numeric_sentence(
                answer_text,
                complete_answer,
                required_values,
            )
        ):
            return answer_text
        extra_sentences: List[str] = []
        for sentence in _split_narrative_sentences(answer_text):
            cleaned = _normalise_spaces(sentence)
            if not cleaned or cleaned in complete_answer:
                continue
            if any(value and value in cleaned for value in required_values):
                continue
            if growth_sentence_has_untraced_material_numeric(
                cleaned,
                complete_answer,
                required_values,
                evidence_items,
            ):
                continue
            extra_sentences.append(cleaned)
        return _normalise_spaces(" ".join([complete_answer, *extra_sentences]))
    return answer_text


def strip_untraced_numeric_material_from_growth_narrative_sentence(
    sentence: str,
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> str:
    cleaned = _normalise_spaces(str(sentence or ""))
    if not cleaned:
        return ""

    complete_answers: List[str] = []
    required_values: List[str] = []
    for row in ordered_results or []:
        if aggregate_result_operation_family(row) != "growth_rate":
            continue
        if growth_row_has_conflicting_periods(row):
            continue
        complete_answer = compose_complete_growth_numeric_answer(
            row,
            ordered_results,
            evidence_items=evidence_items,
        )
        if complete_answer:
            complete_answers.append(complete_answer)
        required_values.extend(
            growth_required_display_values(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
        )
    if not complete_answers and not required_values:
        return ""

    has_untraced_numeric = any(
        growth_sentence_has_untraced_material_numeric(
            cleaned,
            complete_answer,
            required_values,
            evidence_items,
        )
        for complete_answer in complete_answers
    )
    if not has_untraced_numeric:
        return cleaned

    allowed_surface = _normalise_spaces(" ".join([*complete_answers, *required_values]))
    sanitized = cleaned

    def _remove_unallowed_token(match: re.Match[str]) -> str:
        token = _normalise_spaces(match.group(0))
        return token if token and token in allowed_surface else " "

    percent_pattern = str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or "")
    if percent_pattern:
        sanitized = re.sub(percent_pattern, _remove_unallowed_token, sanitized)

    unit_terms = sorted(
        {
            _normalise_spaces(str(unit))
            for unit in (CALCULATION_RENDER_POLICY.get("krw_display_units") or ())
            if _normalise_spaces(str(unit))
        },
        key=len,
        reverse=True,
    )
    if unit_terms:
        joined_units = "|".join(re.escape(unit) for unit in unit_terms)
        sanitized = re.sub(
            rf"\d[\d,]*(?:\.\d+)?\s*(?:{joined_units})",
            _remove_unallowed_token,
            sanitized,
        )

    sanitized = re.sub(r"\s+([,.;:!?。])", r"\1", sanitized)
    sanitized = re.sub(r"([,;:])\s*([,;:])+", r"\1", sanitized)
    sanitized = re.sub(r"[(（]\s*[)）]", " ", sanitized)
    sanitized = _normalise_spaces(sanitized)
    if not sanitized or sanitized == cleaned:
        return ""
    if any(
        growth_sentence_has_untraced_material_numeric(
            sanitized,
            complete_answer,
            required_values,
            evidence_items,
        )
        for complete_answer in complete_answers
    ):
        return ""
    narrative_markers = tuple(
        str(item)
        for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
    )
    if not any(marker and marker in sanitized for marker in narrative_markers):
        return ""
    narrative_terms = [
        term
        for term in narrative_context_terms(sanitized)
        if len(term) >= 3
    ]
    if len(narrative_terms) < 2:
        return ""
    if narrative_sentence_looks_table_noisy(sanitized):
        return ""
    if narrative_sentence_looks_abbreviated_fragment(sanitized, narrative_markers):
        return ""
    return sanitized


def narrative_summary_conflicts_with_growth_trace(
    narrative_answer: str,
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    answer_text = _normalise_spaces(str(narrative_answer or ""))
    if not answer_text:
        return False
    percent_pattern = str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"\d[\d,]*(?:\.\d+)?%")
    for row in ordered_results:
        if aggregate_result_operation_family(row) != "growth_rate":
            continue
        if growth_row_has_conflicting_periods(row):
            continue
        complete_answer = compose_complete_growth_numeric_answer(row, ordered_results)
        required_values = growth_required_display_values(row, ordered_results, evidence_items)
        if not complete_answer or not required_values:
            continue
        evidence_surface = _normalise_spaces(
            " ".join(
                str(value or "")
                for item in (evidence_items or [])
                if isinstance(item, dict)
                for metadata in [dict(item.get("metadata") or {})]
                for value in [
                    *(item.get(key) for key in ("claim", "quote_span", "raw_row_text", "source_context")),
                    *(
                        metadata.get(key)
                        for key in (
                            "table_value_labels_text",
                            "table_summary_text",
                            "table_header_context",
                            "table_context",
                        )
                    ),
                ]
            )
        )
        evidence_display_surface = _normalise_spaces(
            " ".join(
                str(candidate.get("text") or "")
                for candidate in evidence_numeric_display_candidates(evidence_items or [], evidence_surface)
                if str(candidate.get("text") or "").strip()
            )
        )
        allowed_surface = _normalise_spaces(
            " ".join([complete_answer, *required_values, evidence_surface, evidence_display_surface])
        )
        percent_tokens = [
            _normalise_spaces(match.group(0))
            for match in re.finditer(percent_pattern, answer_text)
            if _normalise_spaces(match.group(0))
        ]
        if percent_tokens and any(token not in allowed_surface for token in percent_tokens):
            return True
    return False


def growth_narrative_numeric_incompatible_with_trace(
    *,
    narrative_answer: str,
    numeric_answer: str,
    ordered_results: List[Dict[str, Any]],
    evidence_items: Optional[List[Dict[str, Any]]] = None,
) -> bool:
    narrative_text = _normalise_spaces(str(narrative_answer or ""))
    if not narrative_text:
        return False
    trace_surfaces = [_normalise_spaces(str(numeric_answer or ""))]
    for row in ordered_results or []:
        if aggregate_result_operation_family(row) != "growth_rate":
            continue
        if growth_row_has_conflicting_periods(row):
            continue
        trace_surfaces.append(
            compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
        )
        trace_surfaces.extend(
            growth_required_display_values(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
        )
    trace_numeric_candidates = extract_numeric_surface_candidates(
        _normalise_spaces(" ".join(surface for surface in trace_surfaces if surface))
    )
    narrative_numeric_candidates = extract_numeric_surface_candidates(narrative_text)
    if not trace_numeric_candidates or not narrative_numeric_candidates:
        return False
    return not all(
        any(
            numeric_surface_candidates_equivalent(narrative_candidate, trace_candidate)
            for trace_candidate in trace_numeric_candidates
        )
        for narrative_candidate in narrative_numeric_candidates
    )


def has_strong_growth_trace_for_answer_refresh(
    ordered_results: List[Dict[str, Any]],
) -> bool:
    for row in ordered_results:
        if aggregate_result_operation_family(row) != "growth_rate":
            continue
        if growth_row_has_conflicting_periods(row):
            continue
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        primary_slot = dict(answer_slots.get("primary_value") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        if not all(
            answer_slot_has_material(slot)
            for slot in (primary_slot, current_slot, prior_slot)
        ):
            continue
        direct_operand_count = 0
        for slot in (current_slot, prior_slot):
            source_ids = _clean_source_row_ids([
                slot.get("source_row_id"),
                slot.get("source_row_ids"),
            ])
            if slot.get("normalized_value") is not None and any(
                source_id and not source_id.startswith("task_output:")
                for source_id in source_ids
            ):
                direct_operand_count += 1
        if direct_operand_count >= 2:
            return True
    return False


def aggregate_lookup_primary_slots(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    slots: List[Dict[str, Any]] = []
    for row in rows or []:
        if not isinstance(row, dict) or aggregate_result_operation_family(row) != "lookup": continue
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        primary_slot = dict(answer_slots.get("primary_value") or {})
        if not answer_slot_has_material(primary_slot):
            continue
        slots.append(primary_slot)
    return slots


def safe_partial_answer_for_numeric_gap(
    ordered_results: List[Dict[str, Any]],
) -> str:
    safe_parts: List[str] = []
    for row in ordered_results:
        if row_is_narrative_summary(row):
            continue
        status = str(
            row.get("status")
            or (row.get("calculation_result") or {}).get("status")
            or ""
        ).strip().lower()
        if status != "ok":
            continue
        if material_gap_feedback_for_subtask_result(row):
            continue
        answer = _normalise_spaces(str(row.get("answer") or ""))
        if not answer:
            calculation_result = dict(row.get("calculation_result") or {})
            answer = _normalise_spaces(
                str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
            )
        if answer:
            safe_parts.append(answer)
    return " ".join(dict.fromkeys(safe_parts)).strip()


def aggregate_row_primary_answer_slot(row: Dict[str, Any]) -> Dict[str, Any]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    return dict(answer_slots.get("primary_value") or {})


def compose_lookup_list_numeric_answer(
    ordered_results: List[Dict[str, Any]],
) -> str:
    lookup_result_count = 0
    items: List[str] = []
    for row in ordered_results:
        if row_is_narrative_summary(row):
            continue
        operation_family = aggregate_result_operation_family(row)
        if operation_family not in {"lookup", "single_value"}:
            return ""
        lookup_result_count += 1
        status = _normalise_spaces(
            str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
        ).lower()
        if status != "ok" or material_gap_feedback_for_subtask_result(row):
            continue
        item_answer = _lookup_numeric_item_answer(row)
        if item_answer:
            items.append(item_answer)
    items = list(dict.fromkeys(item for item in items if item))
    if lookup_result_count < 2 or len(items) < 2:
        return ""
    separator = str(CALCULATION_RENDER_POLICY.get("lookup_list_separator") or ", ")
    answer_template = str(CALCULATION_RENDER_POLICY.get("lookup_list_answer_template") or "{items}")
    return _normalise_spaces(answer_template.format(items=separator.join(items)))


def _lookup_numeric_item_answer(
    row: Dict[str, Any],
    *,
    require_primary_slot: bool = False,
    require_numeric: bool = False,
) -> str:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    primary_slot = dict(answer_slots.get("primary_value") or {})
    if require_primary_slot and not answer_slot_has_material(primary_slot):
        return ""
    value = _normalise_spaces(
        str(
            primary_slot.get("rendered_value")
            or calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or row.get("answer")
            or ""
        )
    )
    try:
        normalized_value = float(primary_slot.get("normalized_value"))
    except (TypeError, ValueError):
        normalized_value = None
    if normalized_value is not None and normalized_value >= 0 and value.startswith("("):
        value = _normalise_spaces(value[1:].replace(")", "", 1))
    label = _normalise_spaces(str(primary_slot.get("label") or row.get("metric_label") or ""))
    if not (label and value):
        return ""
    if require_numeric and not extract_numeric_surface_candidates(value):
        return ""
    item_template = str(CALCULATION_RENDER_POLICY.get("lookup_list_item_template") or "{label} {value}")
    return _normalise_spaces(item_template.format(label=label, value=value))


def append_uncovered_lookup_numeric_items(
    answer: str,
    ordered_results: List[Dict[str, Any]],
) -> str:
    answer_text = _normalise_spaces(str(answer or ""))
    if not answer_text:
        return answer_text
    has_aggregate_numeric = any(
        aggregate_result_operation_family(row) in {"ratio", "sum", "difference", "growth_rate"}
        for row in ordered_results
        if isinstance(row, dict)
    )
    if not has_aggregate_numeric:
        return answer_text
    ratio_component_slots: List[Dict[str, Any]] = []
    for result_row in ordered_results:
        if not isinstance(result_row, dict) or aggregate_result_operation_family(result_row) != "ratio":
            continue
        calculation_result = dict(result_row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        components_by_group = dict(answer_slots.get("components_by_group") or {})
        for slots in components_by_group.values():
            ratio_component_slots.extend(dict(slot) for slot in list(slots or []) if isinstance(slot, dict))

    def _lookup_conflicts_with_ratio_component(result_row: Dict[str, Any]) -> bool:
        if not ratio_component_slots:
            return False
        lookup_slot = aggregate_row_primary_answer_slot(result_row)
        lookup_label = _normalise_spaces(str(lookup_slot.get("label") or result_row.get("metric_label") or ""))
        if not lookup_label:
            return False
        lookup_unit = _normalise_spaces(str(lookup_slot.get("normalized_unit") or "")).upper()
        lookup_value = lookup_slot.get("normalized_value")
        try:
            lookup_float = float(lookup_value)
        except (TypeError, ValueError):
            return False
        for component in ratio_component_slots:
            component_label = _normalise_spaces(str(component.get("label") or ""))
            if not component_label:
                continue
            if not _operand_text_match(component_label, {"label": lookup_label, "concept": ""}):
                continue
            component_unit = _normalise_spaces(str(component.get("normalized_unit") or "")).upper()
            if lookup_unit and component_unit and lookup_unit != component_unit:
                continue
            try:
                component_float = float(component.get("normalized_value"))
            except (TypeError, ValueError):
                continue
            tolerance = max(abs(component_float), abs(lookup_float), 1.0) * 5e-4
            if abs(component_float - lookup_float) > tolerance:
                return True
        return False

    missing_items: List[str] = []
    for row in ordered_results:
        if not isinstance(row, dict) or row_is_narrative_summary(row):
            continue
        if aggregate_result_operation_family(row) not in {"lookup", "single_value"}:
            continue
        status = _normalise_spaces(
            str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
        ).lower()
        if status != "ok" or material_gap_feedback_for_subtask_result(row):
            continue
        if _lookup_conflicts_with_ratio_component(row):
            continue
        item_answer = _lookup_numeric_item_answer(
            row,
            require_primary_slot=True,
            require_numeric=True,
        )
        if not item_answer or answer_covers_numeric_answer(answer_text, item_answer):
            continue
        lookup_slot = aggregate_row_primary_answer_slot(row)
        lookup_label = _normalise_spaces(str(lookup_slot.get("label") or row.get("metric_label") or ""))
        if (
            lookup_label
            and extract_numeric_surface_candidates(answer_text)
            and _operand_text_match(answer_text, {"label": lookup_label, "aliases": []})
        ):
            continue
        missing_items.append(item_answer)
    missing_items = list(dict.fromkeys(item for item in missing_items if item))
    if not missing_items:
        return answer_text
    prefix = ". ".join(item.rstrip(".") for item in missing_items)
    if prefix:
        prefix = f"{prefix}."
    return _normalise_spaces(" ".join([prefix, answer_text]))


def aggregate_source_slot_by_task_id(ordered_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    source_slot_by_task_id: Dict[str, Dict[str, Any]] = {}
    for row in ordered_results:
        if not isinstance(row, dict):
            continue
        task_id = _normalise_spaces(str(row.get("task_id") or ""))
        if not task_id:
            continue
        slot = aggregate_row_primary_answer_slot(dict(row))
        if not slot:
            continue
        scope = known_consolidation_scope_value(
            slot.get("consolidation_scope"),
            row.get("consolidation_scope"),
        )
        if scope and not slot.get("consolidation_scope"):
            slot["consolidation_scope"] = scope
        metric_label = _normalise_spaces(str(row.get("metric_label") or ""))
        if metric_label and not slot.get("metric_label"):
            slot["metric_label"] = metric_label
        source_slot_by_task_id[task_id] = slot
    return source_slot_by_task_id


def aggregate_source_task_ids_for_operand(
    operand: Dict[str, Any],
    source_slots: Dict[str, Dict[str, Any]],
) -> List[str]:
    source_task_ids = [
        _normalise_spaces(str(operand.get("source_task_id") or "")),
        *[
            source_id.removeprefix("task_output:")
            for source_id in _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")])
            if source_id.startswith("task_output:")
        ],
    ]
    source_task_ids = [task_id for task_id in source_task_ids if task_id]
    if source_task_ids or not source_slots:
        return list(dict.fromkeys(source_task_ids))
    role = _normalise_spaces(str(operand.get("role") or operand.get("matched_operand_role") or ""))
    inferred_task_ids = []
    for task_id, source_slot in source_slots.items():
        slot = dict(source_slot or {})
        if not answer_slot_has_material(slot):
            continue
        if dependency_lookup_slot_match_score(slot, operand, role) >= 12:
            inferred_task_ids.append(task_id)
    return inferred_task_ids


def ratio_rebuild_component_seeds(
    row: Dict[str, Any],
    calculation_result: Dict[str, Any],
    answer_slots: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    numerator: List[Dict[str, Any]] = []
    denominator: List[Dict[str, Any]] = []
    ungrouped: List[Dict[str, Any]] = []

    def _add_seed(seed: Dict[str, Any], fallback_role: str = "") -> None:
        seed = dict(seed)
        role = _normalise_spaces(
            str(seed.get("matched_operand_role") or seed.get("role") or fallback_role or "")
        )
        if role and not seed.get("matched_operand_role"):
            seed["matched_operand_role"] = role
        group = dependency_ratio_role_group(role)
        if group == "numerator":
            numerator.append(seed)
        elif group == "denominator":
            denominator.append(seed)
        elif answer_slot_has_material(seed):
            ungrouped.append(seed)

    for container_key in ("components_by_group", "components_by_role"):
        for role, entries in dict(answer_slots.get(container_key) or {}).items():
            for entry in list(entries or []):
                if isinstance(entry, dict):
                    _add_seed(entry, str(role or ""))
    for operand in list(row.get("calculation_operands") or calculation_result.get("calculation_operands") or []):
        if isinstance(operand, dict):
            _add_seed(operand)
    return numerator, denominator, ungrouped


def _dependency_source_text_match_score(left: str, right: str) -> int:
    left = _normalise_spaces(left)
    right = _normalise_spaces(right)
    if not left or not right:
        return 0
    score = 0
    if left == right:
        score += 6
    elif left in right or right in left:
        score += 3
    left_terms = {
        token.lower()
        for token in narrative_context_terms(left)
        if len(token) >= 2
    }
    right_terms = {
        token.lower()
        for token in narrative_context_terms(right)
        if len(token) >= 2
    }
    return score + len(left_terms & right_terms)


def dependency_source_slot_match_score(
    slot: Dict[str, Any],
    seed: Dict[str, Any],
    role: str,
) -> int:
    score = dependency_lookup_slot_match_score(slot, seed, role)
    slot_text = " ".join(
        str(slot.get(key) or "")
        for key in ("label", "metric_label", "concept", "period")
    )
    seed_text = " ".join(
        str(seed.get(key) or seed.get(f"matched_operand_{key}") or "")
        for key in ("label", "concept", "period")
    )
    return score + _dependency_source_text_match_score(slot_text, seed_text)


def best_dependency_source_for_seed(
    seed: Dict[str, Any],
    role: str,
    *,
    source_slots: Dict[str, Dict[str, Any]],
    excluded_task_ids: Optional[set[str]] = None,
) -> tuple[str, Dict[str, Any], Dict[str, Any], int]:
    seed = {
        **dict(seed),
        "role": role,
        "matched_operand_role": role,
        "matched_operand_label": _normalise_spaces(
            str(seed.get("matched_operand_label") or seed.get("label") or "")
        ),
        "matched_operand_concept": _normalise_spaces(
            str(seed.get("matched_operand_concept") or seed.get("concept") or "")
        ),
    }
    excluded = set(excluded_task_ids or set())
    inferred_task_ids = set(aggregate_source_task_ids_for_operand(seed, source_slots))
    ranked: List[tuple[int, str, Dict[str, Any]]] = []
    for task_id, slot in source_slots.items():
        if task_id in excluded:
            continue
        score = dependency_source_slot_match_score(slot, seed, role)
        if task_id in inferred_task_ids:
            score = max(score, 12)
        if score <= 0:
            continue
        ranked.append((score, task_id, slot))
    if not ranked:
        return "", {}, {}, 0
    ranked.sort(key=lambda item: (item[0], item[1]), reverse=True)
    score, task_id, slot = ranked[0]
    return task_id, dict(slot), seed, score


def component_slot_from_dependency_source(
    seed: Dict[str, Any],
    source_slot: Dict[str, Any],
    source_task_id: str,
    role: str,
) -> Dict[str, Any]:
    source_operand = dependency_operand_from_source_slot(
        {
            **dict(seed),
            "role": role,
            "matched_operand_role": role,
            "label": seed.get("label") or source_slot.get("label"),
            "matched_operand_label": seed.get("matched_operand_label") or source_slot.get("label"),
            "matched_operand_concept": seed.get("matched_operand_concept") or source_slot.get("concept"),
        },
        source_slot,
        source_task_id=source_task_id,
    )
    slot = build_operand_value_slot(source_operand, default_role=role)
    slot["role"] = role
    slot["source_task_id"] = source_task_id
    slot["dependency_resolved"] = True
    return slot


def _aggregate_result_candidate_operands(row: Dict[str, Any]) -> List[Dict[str, Any]]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    candidate_operands = [dict(item) for item in list(row.get("calculation_operands") or []) if isinstance(item, dict)]
    candidate_operands.extend(
        dict(item) for item in list(calculation_result.get("calculation_operands") or []) if isinstance(item, dict)
    )
    for container_key in ("components_by_group", "components_by_role"):
        for entries in dict(answer_slots.get(container_key) or {}).values():
            candidate_operands.extend(dict(item) for item in list(entries or []) if isinstance(item, dict))
    return candidate_operands


def aggregate_result_dependency_coherence_ranks(
    row: Dict[str, Any],
    source_slot_by_task_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[int, int]:
    operation_family = aggregate_result_operation_family(row)
    if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
        return 1, 1
    source_slots = dict(source_slot_by_task_id or {})
    saw_source_slot = False
    saw_source_scope = False
    candidate_operands = _aggregate_result_candidate_operands(row)
    structured_realigned_operands = [
        dict(operand)
        for operand in candidate_operands
        if isinstance(operand, dict) and operand.get("unit_realigned_from_structured_provenance")
    ]
    for operand in candidate_operands:
        source_task_ids = aggregate_source_task_ids_for_operand(operand, source_slots)
        source_task_id = source_task_ids[0] if source_task_ids else ""
        if source_task_id and source_slots:
            source_slot = dict(source_slots.get(source_task_id) or {})
            if answer_slot_has_material(source_slot):
                saw_source_slot = True
                source_anchor = _normalise_spaces(str(source_slot.get("source_anchor") or ""))
                operand_anchor = _normalise_spaces(str(operand.get("source_anchor") or ""))
                source_mismatch = bool(source_anchor and operand_anchor and source_anchor != operand_anchor)
                projection_mismatch = dependency_projection_slot_differs_from_operand(source_slot, operand)
                if (
                    (source_mismatch or projection_mismatch)
                    and not structured_unit_realigned_operand_matches_source_slot(
                        source_slot,
                        operand,
                        structured_realigned_operands=structured_realigned_operands,
                    )
                ):
                    return 0, 2 if saw_source_scope else 1
        if operation_family == "ratio" and source_slots and source_task_ids:
            source_scope = next(
                (
                    known_consolidation_scope_value(source_slots.get(task_id, {}).get("consolidation_scope"))
                    for task_id in source_task_ids
                    if source_slots.get(task_id)
                ),
                "",
            )
            if source_scope:
                saw_source_scope = True
                operand_scope = known_consolidation_scope_value(operand.get("consolidation_scope"))
                if operand_scope and operand_scope != source_scope:
                    return 2 if saw_source_slot else 1, 0
    return 2 if saw_source_slot else 1, 2 if saw_source_scope else 1


def aggregate_dependency_slot_coherence_rank_for_operands(
    *,
    operation_family: str,
    operands: List[Any],
    ordered_results: List[Dict[str, Any]],
    calculation_result: Optional[Dict[str, Any]] = None,
) -> int:
    return aggregate_result_dependency_coherence_ranks(
        {
            "operation_family": operation_family,
            "calculation_operands": [
                dict(item)
                for item in list(operands or [])
                if isinstance(item, dict)
            ],
            "calculation_result": dict(calculation_result or {}),
        },
        aggregate_source_slot_by_task_id(ordered_results),
    )[0]


def select_aggregate_projection_row_for_task(
    task_id: str,
    ordered_results: List[Dict[str, Any]],
    aggregate_projection: Dict[str, Any],
) -> Dict[str, Any]:
    target_task_id = _normalise_spaces(str(task_id or ""))
    if not target_task_id:
        return {}
    calculation_result = dict(aggregate_projection.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    candidate_groups = [
        calculation_result.get("subtask_results"),
        answer_slots.get("subtask_results"),
        ordered_results,
    ]
    for rows in candidate_groups:
        for row in list(rows or []):
            if not isinstance(row, dict):
                continue
            if _normalise_spaces(str(row.get("task_id") or "")) == target_task_id:
                return dict(row)
    return {}


def select_aggregate_projection_answer_sentence(
    final_answer: str,
    row: Dict[str, Any],
) -> str:
    final_answer = _normalise_spaces(final_answer)
    if not final_answer:
        return ""
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    primary_slot = dict(answer_slots.get("primary_value") or {})
    raw_labels = [
        row.get("metric_label"),
        row.get("label"),
        primary_slot.get("label"),
    ]
    row_labels: List[str] = []
    for label in raw_labels:
        normalized = _normalise_spaces(str(label or "")).lower()
        if not normalized:
            continue
        row_labels.append(normalized)
        stripped = _normalise_spaces(_strip_leading_period_qualifiers(normalized)).lower()
        if stripped and stripped != normalized:
            row_labels.append(stripped)
    row_labels = list(dict.fromkeys(row_labels))
    operation_family = aggregate_result_operation_family(row)
    sentences = _split_narrative_sentences(final_answer) or [final_answer]

    def _label_match_score(sentence: str) -> int:
        normalized = _normalise_spaces(sentence).lower()
        if not normalized:
            return 0
        sentence_tokens = _tokenize_terms(normalized)
        score = 0
        for label in row_labels:
            if not label:
                continue
            if label in normalized:
                score = max(score, 3)
                continue
            label_tokens = _tokenize_terms(label)
            if not label_tokens:
                continue
            overlap = len(label_tokens & sentence_tokens)
            required_overlap = len(label_tokens)
            if len(label_tokens) >= 3:
                required_overlap = max(2, len(label_tokens) - 1)
            if overlap >= required_overlap and _operand_text_match(normalized, {"label": label, "aliases": []}):
                score = max(score, 1)
        return score

    def _score(sentence: str) -> tuple[int, int, int, int, int]:
        normalized = _normalise_spaces(sentence)
        numeric_candidates = extract_numeric_surface_candidates(normalized)
        if not normalized or not numeric_candidates:
            return (0, 0, 0, 0, 0)
        label_score = _label_match_score(normalized)
        percent_score = int(operation_family in {"ratio", "growth_rate"} and "%" in normalized)
        arithmetic_score = len(numeric_candidates) if operation_family in {"difference", "sum"} else 0
        conflict_score = int(subtask_numeric_answers_conflict({"answer": normalized}, row))
        return (label_score, percent_score, arithmetic_score, conflict_score, len(normalized))

    best_sentence = max(sentences, key=_score, default="")
    return _normalise_spaces(best_sentence) if _score(best_sentence)[:3] != (0, 0, 0) else ""


def aggregate_projection_rendered_value(
    answer_sentence: str,
    operation_family: str,
) -> str:
    sentence = _normalise_spaces(answer_sentence)
    if not sentence:
        return ""
    if operation_family in {"ratio", "growth_rate"}:
        match = re.search(r"[\(\)\-+]?\d[\d,]*(?:\.\d+)?\s*%p?", sentence)
        return _normalise_spaces(match.group(0)) if match else ""
    candidates = extract_numeric_surface_candidates(sentence)
    if not candidates:
        return ""
    return _normalise_spaces(str(candidates[-1].get("text") or ""))


def aggregate_result_signature(row: Mapping[str, Any]) -> str:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    metric_label = _normalise_spaces(
        str(
            row.get("metric_label")
            or answer_slots.get("metric_label")
            or row.get("task_id")
            or ""
        )
    )
    if not metric_label:
        return ""
    operation_family = aggregate_result_operation_family(row)
    if operation_family:
        return f"{operation_family}:{metric_label}"
    return metric_label


def _ratio_result_numeric_value(row: Dict[str, Any]) -> Optional[float]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    primary_value = dict(answer_slots.get("primary_value") or {})
    for value in (
        calculation_result.get("result_value"),
        primary_value.get("normalized_value"),
        primary_value.get("raw_value"),
        row.get("result_value"),
    ):
        numeric_value = coerce_slot_numeric(value)
        if numeric_value is not None: return numeric_value
    return None


def retrieved_ratio_projection_conflicts_with_existing_complete_result(
    ordered_results: List[Dict[str, Any]],
    task: Dict[str, Any],
    *,
    result_value: float,
    context_evidence: List[Dict[str, Any]],
) -> bool:
    task_id = _normalise_spaces(str(task.get("task_id") or ""))
    metric_label = _normalise_spaces(str(task.get("metric_label") or task.get("target_metric") or ""))
    candidate_signature = aggregate_result_signature(
        {
            "task_id": task_id,
            "metric_label": metric_label,
            "operation_family": "ratio",
        }
    )
    for row in ordered_results:
        if not isinstance(row, dict):
            continue
        if aggregate_result_operation_family(row) != "ratio":
            continue
        row_task_id = _normalise_spaces(str(row.get("task_id") or ""))
        row_signature = aggregate_result_signature(row)
        if task_id and row_task_id and row_task_id != task_id:
            if not candidate_signature or row_signature != candidate_signature:
                continue
        elif candidate_signature and row_signature != candidate_signature:
            continue
        calculation_result = dict(row.get("calculation_result") or {})
        status = _normalise_spaces(str(row.get("status") or calculation_result.get("status") or "")).lower()
        artifact_backed_complete_result = bool(row.get("artifact_backed_complete_result"))
        if status != "ok":
            continue
        existing_value = _ratio_result_numeric_value(row)
        if existing_value is None:
            continue
        if not artifact_backed_complete_result and not ratio_components_are_complete(calculation_result):
            continue
        tolerance = max(max(abs(float(existing_value)), abs(float(result_value)), 1.0) * 5e-4, 1e-6)
        if abs(float(existing_value) - float(result_value)) <= tolerance:
            continue
        return not ratio_context_has_metric_surface(context_evidence, task)
    return False


def growth_operand_sign_consistency_rank(row: Mapping[str, Any]) -> int:
    if aggregate_result_operation_family(row) != "growth_rate":
        return 1
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    current_slot = dict(answer_slots.get("current_value") or {})
    prior_slot = dict(answer_slots.get("prior_value") or {})

    def _sign(slot: Dict[str, Any]) -> int:
        value = slot.get("normalized_value")
        if value is None:
            return 0
        try:
            numeric_value = float(value)
        except (TypeError, ValueError):
            return 0
        if numeric_value > 0:
            return 1
        if numeric_value < 0:
            return -1
        return 0

    current_sign = _sign(current_slot)
    prior_sign = _sign(prior_slot)
    if current_sign and prior_sign:
        return 2 if current_sign == prior_sign else 0
    return 1


def _aggregate_result_rank(
    row: Dict[str, Any],
    source_slot_by_task_id: Optional[Dict[str, Dict[str, Any]]] = None,
) -> tuple[int, int, int, int, int, int, int]:
    calculation_result = dict(row.get("calculation_result") or {})
    status = _normalise_spaces(
        str(
            row.get("status")
            or calculation_result.get("status")
            or ""
        )
    ).lower()
    status_rank = {
        "ok": 4,
        "partial": 3,
        "ready": 3,
        "insufficient_operands": 1,
        "retry_retrieval": 1,
        "missing": 0,
    }.get(status, 0)
    material_rank = 0 if material_gap_feedback_for_subtask_result(row) else 1
    answer_rank = 1 if _normalise_spaces(str(row.get("answer") or "")) else 0
    growth_sign_rank = growth_operand_sign_consistency_rank(row)
    dependency_slot_rank, scope_coherence_rank = aggregate_result_dependency_coherence_ranks(
        row,
        source_slot_by_task_id,
    )
    operand_rank = len(list(calculation_result.get("source_row_ids") or []))
    return status_rank, material_rank, answer_rank, growth_sign_rank, dependency_slot_rank, scope_coherence_rank, operand_rank


def nested_aggregate_result_rank(row: Dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
    calculation_result = dict(row.get("calculation_result") or {})
    status = _normalise_spaces(
        str(row.get("status") or calculation_result.get("status") or "")
    ).lower()
    status_rank = {
        "ok": 4,
        "partial": 3,
        "ready": 3,
        "insufficient_operands": 1,
        "retry_retrieval": 1,
        "missing": 0,
    }.get(status, 0)
    material_rank = 1 if subtask_row_has_material(row) else 0
    gap_free_rank = 0 if material_gap_feedback_for_subtask_result(row) else 1
    operation_family = aggregate_result_operation_family(row)
    non_aggregate_rank = 0 if operation_family == "aggregate_subtasks" else 1
    growth_sign_rank = growth_operand_sign_consistency_rank(row)
    source_count = len(_clean_source_row_ids([
        row.get("source_row_ids"),
        calculation_result.get("source_row_ids"),
        row.get("selected_claim_ids"),
        calculation_result.get("source_evidence_ids"),
    ]))
    answer_text = _normalise_spaces(
        str(
            row.get("answer")
            or calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or ""
        )
    )
    digit_count = len(re.findall(r"\d", answer_text))
    return (
        status_rank,
        material_rank,
        gap_free_rank,
        non_aggregate_rank,
        growth_sign_rank,
        source_count,
        digit_count,
        len(answer_text),
    )


def promote_stronger_nested_aggregate_results(
    ordered_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_task_id = {
        _normalise_spaces(str(row.get("task_id") or "")): dict(row)
        for row in ordered_results
        if _normalise_spaces(str(row.get("task_id") or ""))
    }
    source_slot_by_task_id = aggregate_source_slot_by_task_id(list(by_task_id.values()))
    replacements: Dict[str, Dict[str, Any]] = {}
    for row in ordered_results:
        if aggregate_result_operation_family(row) != "aggregate_subtasks":
            continue
        calculation_result = dict(row.get("calculation_result") or {})
        for nested_row in nested_subtask_rows(calculation_result):
            nested_task_id = _normalise_spaces(str(nested_row.get("task_id") or ""))
            if not nested_task_id:
                continue
            if aggregate_result_operation_family(nested_row) == "aggregate_subtasks":
                continue
            if material_gap_feedback_for_subtask_result(dict(nested_row)):
                continue
            current_row = replacements.get(nested_task_id) or by_task_id.get(nested_task_id)
            if not current_row:
                continue
            current_status = _normalise_spaces(
                str(current_row.get("status") or (current_row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if (
                current_status == "ok"
                and not material_gap_feedback_for_subtask_result(current_row)
                and subtask_row_has_direct_source_refs(current_row)
                and aggregate_result_operation_family(current_row) == aggregate_result_operation_family(nested_row)
                and subtask_numeric_answers_conflict(nested_row, current_row)
                and growth_operand_sign_consistency_rank(nested_row)
                <= growth_operand_sign_consistency_rank(current_row)
            ):
                continue
            if nested_aggregate_result_rank(nested_row) <= nested_aggregate_result_rank(current_row):
                continue
            if aggregate_result_dependency_coherence_ranks(
                nested_row,
                source_slot_by_task_id,
            )[0] < aggregate_result_dependency_coherence_ranks(
                current_row,
                source_slot_by_task_id,
            )[0]:
                continue
            promoted = {
                **dict(current_row),
                **dict(nested_row),
                "promoted_from_nested_aggregate": True,
            }
            for key in ("runtime_evidence", "artifact_ids", "selected_claim_ids", "source_evidence_ids"):
                if not promoted.get(key) and current_row.get(key):
                    promoted[key] = current_row.get(key)
            replacements[nested_task_id] = promoted
    if not replacements:
        return ordered_results
    return [
        dict(replacements.get(_normalise_spaces(str(row.get("task_id") or ""))) or row)
        for row in ordered_results
    ]


def dedupe_aggregate_subtask_results(
    ordered_results: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    source_slot_by_task_id = aggregate_source_slot_by_task_id(ordered_results)
    winners: Dict[str, tuple[int, tuple[int, int, int, int, int, int, int], Dict[str, Any]]] = {}
    passthrough: List[tuple[int, Dict[str, Any]]] = []
    for index, row in enumerate(ordered_results):
        signature = aggregate_result_signature(row)
        if not signature:
            passthrough.append((index, row))
            continue
        rank = _aggregate_result_rank(row, source_slot_by_task_id)
        incumbent = winners.get(signature)
        if incumbent is None or rank > incumbent[1] or (rank == incumbent[1] and index > incumbent[0]):
            winners[signature] = (index, rank, row)
    deduped = sorted(
        [item for item in winners.values()] + [(index, (0, 0, 0, 0, 0, 0, 0), row) for index, row in passthrough],
        key=lambda item: item[0],
    )
    return [dict(item[2]) for item in deduped]


def _replacement_lookup_slot_for_component(
    component: Dict[str, Any],
    lookup_slots: Sequence[Mapping[str, Any]],
) -> Mapping[str, Any]:
    label = _normalise_spaces(str(component.get("label") or ""))
    concept = _normalise_spaces(str(component.get("concept") or ""))
    if not (label or concept):
        return {}
    for slot in lookup_slots:
        slot_label = _normalise_spaces(str(slot.get("label") or ""))
        slot_concept = _normalise_spaces(str(slot.get("concept") or ""))
        if concept and slot_concept and concept == slot_concept:
            return slot
        if label and slot_label and (
            _operand_text_match(label, {"label": slot_label, "aliases": []})
            or _operand_text_match(slot_label, {"label": label, "aliases": []})
        ):
            return slot
    return {}


def _sync_component_slot_from_lookup_slot(
    component: Dict[str, Any],
    lookup_slots: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    replacement = _replacement_lookup_slot_for_component(component, lookup_slots)
    if not replacement:
        return component
    value_keys = (
        "raw_value",
        "raw_unit",
        "normalized_value",
        "normalized_unit",
        "rendered_value",
    )
    return {
        **component,
        **{key: replacement.get(key) for key in value_keys if replacement.get(key) is not None},
        "source_row_id": replacement.get("source_row_id") or component.get("source_row_id"),
        "source_row_ids": replacement.get("source_row_ids") or component.get("source_row_ids"),
        "source_anchor": replacement.get("source_anchor") or component.get("source_anchor"),
    }


def synchronize_aggregate_arithmetic_components(
    sync_input: AggregateArithmeticComponentSyncInput,
) -> AggregateArithmeticComponentSyncResult:
    """Synchronize prepared lookup slots into one aggregate arithmetic row."""

    row = sync_input.projection_row
    lookup_slots = sync_input.lookup_slots
    if not lookup_slots or aggregate_result_operation_family(row) not in {
        "ratio",
        "growth_rate",
        "difference",
        "sum",
    }:
        return AggregateArithmeticComponentSyncResult(projection_row=row)
    updated = dict(row)
    calculation_result = dict(updated.get("calculation_result") or {})
    if not calculation_result:
        return AggregateArithmeticComponentSyncResult(projection_row=updated)
    answer_slots = dict(calculation_result.get("answer_slots") or {})

    for container_key in ("components_by_role", "components_by_group"):
        container = dict(answer_slots.get(container_key) or {})
        if not container:
            continue
        synced_container: Dict[str, Any] = {}
        for key, values in container.items():
            synced_container[key] = [
                _sync_component_slot_from_lookup_slot(dict(item), lookup_slots)
                if isinstance(item, dict)
                else item
                for item in list(values or [])
            ]
        answer_slots[container_key] = synced_container

    series = [dict(item) for item in list(calculation_result.get("series") or []) if isinstance(item, dict)]
    if series:
        calculation_result["series"] = [
            _sync_component_slot_from_lookup_slot(item, lookup_slots)
            for item in series
        ]

    primary_value = dict(answer_slots.get("primary_value") or {})
    operation_family = aggregate_result_operation_family(row)
    if primary_value and operation_family in {"difference", "sum"}:
        answer_slots["delta_value"] = dict(primary_value)
    if answer_slots:
        calculation_result["answer_slots"] = answer_slots
    updated["calculation_result"] = calculation_result
    return AggregateArithmeticComponentSyncResult(projection_row=updated)


def _numeric_slot_from_synced_answer_sentence(
    answer_sentence: str,
    operation_family: str,
) -> Dict[str, Any]:
    sentence = _normalise_spaces(answer_sentence)
    if not sentence:
        return {}
    candidates = extract_numeric_surface_candidates(sentence)
    if not candidates:
        return {}
    candidate = candidates[0]
    if operation_family not in {"ratio", "growth_rate"}:
        candidate = candidates[-1]
    return numeric_surface_slot_components(candidate)


def synchronize_aggregate_projection_row_surface(
    sync_input: AggregateProjectionRowSurfaceSyncInput,
) -> AggregateProjectionRowSurfaceSyncResult:
    """Synchronize one graph-selected answer surface into a prepared result row."""

    row = sync_input.projection_row
    answer = sync_input.answer
    rendered_value = sync_input.rendered_value
    updated = {
        **dict(row),
        "answer": answer,
        "projection_surface_synced_from_final_answer": True,
    }
    if rendered_value:
        updated["rendered_value"] = rendered_value

    calculation_result = dict(row.get("calculation_result") or {})
    if not calculation_result:
        return AggregateProjectionRowSurfaceSyncResult(projection_row=updated)
    slot_components = _numeric_slot_from_synced_answer_sentence(
        answer,
        aggregate_result_operation_family(row),
    )
    calculation_result["formatted_result"] = answer
    if rendered_value:
        calculation_result["rendered_value"] = rendered_value
    if slot_components:
        calculation_result["result_value"] = slot_components.get("normalized_value")
        raw_unit = _normalise_spaces(str(slot_components.get("raw_unit") or ""))
        if raw_unit:
            calculation_result["result_unit"] = raw_unit
        operation_family = aggregate_result_operation_family(row)
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        primary_value = dict(answer_slots.get("primary_value") or {})
        if primary_value or operation_family in {"difference", "sum", "lookup"}:
            primary_value = {
                **primary_value,
                "status": primary_value.get("status") or "ok",
                "role": primary_value.get("role") or "primary_value",
                "label": primary_value.get("label") or row.get("metric_label") or "",
                "raw_value": slot_components.get("raw_value"),
                "raw_unit": slot_components.get("raw_unit"),
                "normalized_value": slot_components.get("normalized_value"),
                "normalized_unit": slot_components.get("normalized_unit"),
                "rendered_value": slot_components.get("rendered_value") or rendered_value,
            }
            primary_value["rendered_value"] = rendered_value
            answer_slots["primary_value"] = primary_value
            if operation_family == "lookup":
                calculation_result["current_value"] = slot_components.get("normalized_value")
                calculation_result["current_period"] = calculation_result.get("current_period") or primary_value.get("period") or ""
                series = [
                    dict(item)
                    for item in list(calculation_result.get("series") or [])
                    if isinstance(item, dict)
                ]
                if series:
                    series[0] = {**series[0], **slot_components, "rendered_value": rendered_value}
                else:
                    series = [dict(primary_value)]
                calculation_result["series"] = series

                for container_key in ("components_by_role", "components_by_group"):
                    container = dict(answer_slots.get(container_key) or {})
                    target_keys = ["primary_value"] if container_key == "components_by_role" else ["primary", "primary_value"]
                    for target_key in target_keys:
                        if target_key not in container:
                            continue
                        values = [
                            dict(item)
                            for item in list(container.get(target_key) or [])
                            if isinstance(item, dict)
                        ]
                        if values:
                            values[0] = {**values[0], **slot_components, "rendered_value": rendered_value}
                        else:
                            values = [dict(primary_value)]
                        container[target_key] = values
                    if container:
                        answer_slots[container_key] = container
                derived_metrics = dict(calculation_result.get("derived_metrics") or {})
                if derived_metrics:
                    derived_metrics["formula_result_value"] = slot_components.get("normalized_value")
                    calculation_result["derived_metrics"] = derived_metrics
            calculation_result["answer_slots"] = answer_slots
    updated["calculation_result"] = calculation_result
    return AggregateProjectionRowSurfaceSyncResult(projection_row=updated)


def sync_aggregate_arithmetic_subtask_surfaces(
    ordered_results: List[Dict[str, Any]],
    aggregate_projection: Dict[str, Any],
    final_answer: str,
) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
    calculation_result = dict(aggregate_projection.get("calculation_result") or {})
    projection_rows = [
        dict(row)
        for row in list(calculation_result.get("subtask_results") or [])
        if isinstance(row, dict)
    ]
    if not projection_rows:
        return ordered_results, aggregate_projection
    arithmetic_families = {"ratio", "growth_rate", "difference", "sum"}
    syncable_families = {*arithmetic_families, "lookup"}
    plan = dict(aggregate_projection.get("calculation_plan") or {})
    planned_arithmetic_task_ids = {
        _normalise_spaces(str(item.get("task_id") or ""))
        for item in list(plan.get("subtasks") or [])
        if _normalise_spaces(
            str(
                (dict(item.get("calculation_plan") or {})).get("operation")
                or item.get("operation_family")
                or ""
            )
        ).lower()
        in {"ratio", "growth_rate", "subtract", "difference", "add", "sum"}
    }

    candidate_indexes: List[int] = []
    for index, row in enumerate(projection_rows):
        task_id = _normalise_spaces(str(row.get("task_id") or ""))
        operation_family = aggregate_result_operation_family(row)
        if operation_family not in syncable_families:
            continue
        if (
            operation_family in arithmetic_families
            and planned_arithmetic_task_ids
            and task_id not in planned_arithmetic_task_ids
        ):
            continue
        row_surface = _normalise_spaces(
            str(
                row.get("answer")
                or (row.get("calculation_result") or {}).get("formatted_result")
                or (row.get("calculation_result") or {}).get("rendered_value")
                or ""
            )
        )
        if not row_surface:
            continue
        if operation_family == "lookup" and answer_covers_numeric_answer(final_answer, row_surface):
            continue
        synced_answer = select_aggregate_projection_answer_sentence(final_answer, row)
        if not synced_answer:
            continue
        if not subtask_numeric_answers_conflict({"answer": synced_answer}, row):
            continue
        if operation_family in {"ratio", "growth_rate"} and answer_covers_numeric_answer(final_answer, row_surface):
            continue
        if operation_family == "lookup" and len(extract_numeric_surface_candidates(synced_answer)) != 1:
            continue
        candidate_indexes.append(index)
    if not candidate_indexes:
        return ordered_results, aggregate_projection

    updated_rows_by_task_id: Dict[str, Dict[str, Any]] = {}
    for target_index in candidate_indexes:
        target_row = projection_rows[target_index]
        synced_answer = select_aggregate_projection_answer_sentence(final_answer, target_row)
        if not synced_answer:
            continue
        operation_family = aggregate_result_operation_family(target_row)
        rendered_value = aggregate_projection_rendered_value(synced_answer, operation_family)
        updated_row = synchronize_aggregate_projection_row_surface(
            AggregateProjectionRowSurfaceSyncInput(
                projection_row=target_row,
                answer=synced_answer,
                rendered_value=rendered_value,
            )
        ).projection_row
        projection_rows[target_index] = updated_row
        target_task_id = _normalise_spaces(str(updated_row.get("task_id") or ""))
        if target_task_id:
            updated_rows_by_task_id[target_task_id] = updated_row

    if not updated_rows_by_task_id:
        return ordered_results, aggregate_projection

    lookup_slots = aggregate_lookup_primary_slots(projection_rows)
    if lookup_slots:
        for index, row in enumerate(projection_rows):
            synced_row = synchronize_aggregate_arithmetic_components(
                AggregateArithmeticComponentSyncInput(
                    projection_row=row,
                    lookup_slots=lookup_slots,
                )
            ).projection_row
            projection_rows[index] = synced_row
            task_id = _normalise_spaces(str(synced_row.get("task_id") or ""))
            if task_id and synced_row != row:
                updated_rows_by_task_id[task_id] = synced_row

    ordered_results = [
        dict(updated_rows_by_task_id.get(_normalise_spaces(str(row.get("task_id") or ""))) or row)
        for row in ordered_results
    ]
    answer_slots = dict(calculation_result.get("answer_slots") or {})
    slot_rows = [dict(row) for row in list(answer_slots.get("subtask_results") or []) if isinstance(row, dict)]
    if slot_rows:
        synced_slot_rows: List[Dict[str, Any]] = []
        for row in slot_rows:
            task_id = _normalise_spaces(str(row.get("task_id") or ""))
            updated_row = updated_rows_by_task_id.get(task_id)
            synced_slot_rows.append(dict(updated_row) if updated_row else row)
        answer_slots["subtask_results"] = synced_slot_rows
        calculation_result["answer_slots"] = answer_slots
    calculation_result["subtask_results"] = projection_rows
    aggregate_projection = {
        **dict(aggregate_projection),
        "calculation_result": calculation_result,
    }
    return ordered_results, aggregate_projection


def project_runtime_ratio_absolute_magnitude(
    projection_input: RuntimeRatioAbsoluteMagnitudeProjectionInput,
) -> RuntimeRatioAbsoluteMagnitudeProjectionResult:
    """Project a negative runtime ratio onto graph-prepared result and slot copies."""

    runtime_result = projection_input.calculation_result
    runtime_slots = projection_input.answer_slots
    runtime_primary = projection_input.primary_value
    try:
        runtime_value = runtime_result.get("result_value")
        if runtime_value is not None and float(runtime_value) < 0:
            absolute_value = abs(float(runtime_value))
            runtime_result["result_value"] = absolute_value
            runtime_primary["normalized_value"] = absolute_value
            runtime_primary["normalized_unit"] = runtime_primary.get("normalized_unit") or "PERCENT"
            runtime_primary["raw_unit"] = (
                runtime_primary.get("raw_unit") or runtime_result.get("result_unit") or "%"
            )
            runtime_rendered = calculation_rendering.format_calculation_value(
                absolute_value,
                str(runtime_result.get("result_unit") or "%"),
                str(runtime_primary.get("normalized_unit") or "PERCENT"),
            )
            runtime_result["rendered_value"] = runtime_rendered
            runtime_primary["rendered_value"] = runtime_rendered
            runtime_slots["primary_value"] = runtime_primary
            runtime_result["answer_slots"] = runtime_slots
    except (TypeError, ValueError):
        pass
    return RuntimeRatioAbsoluteMagnitudeProjectionResult(
        calculation_result=runtime_result,
    )


def _aggregate_stale_repair_provenance_refs(payload: Mapping[str, Any]) -> set[str]:
    calculation_result = dict(payload.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or payload.get("answer_slots") or {})
    calculation_operands = [
        dict(row)
        for row in list(payload.get("calculation_operands") or [])
        if isinstance(row, dict)
    ]
    return set(
        _clean_source_row_ids(
            [
                payload.get("selected_claim_ids"),
                payload.get("source_row_id"),
                payload.get("source_row_ids"),
                payload.get("source_evidence_ids"),
                calculation_result.get("source_row_id"),
                calculation_result.get("source_row_ids"),
                calculation_result.get("source_evidence_ids"),
                answer_slots.get("source_row_id"),
                answer_slots.get("source_row_ids"),
                answer_slots.get("source_evidence_ids"),
                *[
                    value
                    for operand in calculation_operands
                    for value in (
                        operand.get("evidence_id"),
                        operand.get("source_row_id"),
                        operand.get("source_row_ids"),
                        operand.get("source_claim_ids"),
                    )
                ],
            ]
        )
    )


def select_aggregate_stale_repair_provenance(
    selection_input: AggregateStaleRepairProvenanceInput,
) -> AggregateStaleRepairProvenanceResult:
    """Replace only a uniquely identified stale target's selected provenance."""

    repaired_slots = dict(
        selection_input.repaired_calculation_result.get("answer_slots") or {}
    )
    target_operation = _normalise_spaces(
        str(repaired_slots.get("operation_family") or "")
    ).lower()
    target_metric = _normalise_spaces(
        str(repaired_slots.get("metric_label") or "")
    ).casefold()
    matching_rows: List[Mapping[str, Any]] = []
    if target_operation and target_metric:
        for row in selection_input.ordered_results:
            row_result = dict(row.get("calculation_result") or {})
            row_slots = dict(row_result.get("answer_slots") or row.get("answer_slots") or {})
            row_metric = _normalise_spaces(
                str(row.get("metric_label") or row_slots.get("metric_label") or "")
            ).casefold()
            if (
                aggregate_result_operation_family(row) != target_operation
                or row_metric != target_metric
            ):
                continue
            matching_rows.append(row)
    projection_refs = _aggregate_stale_repair_provenance_refs(
        selection_input.aggregate_projection
    )
    overlapping_rows = [
        row
        for row in matching_rows
        if projection_refs.intersection(_aggregate_stale_repair_provenance_refs(row))
    ]
    target_rows: List[Mapping[str, Any]] = []
    target_resolution: AggregateStaleRepairTargetResolution = "no_target"
    if len(overlapping_rows) == 1:
        target_rows = overlapping_rows
        target_resolution = "unique_overlap"
    elif not overlapping_rows and len(matching_rows) == 1:
        target_rows = matching_rows
        target_resolution = "single_identity_candidate"
    elif matching_rows:
        target_resolution = "ambiguous_target"

    superseded_claim_ids: set[str] = set()
    for row in target_rows:
        superseded_claim_ids.update(
            str(claim_id).strip()
            for claim_id in (row.get("selected_claim_ids") or [])
            if str(claim_id).strip()
        )

    evidence_ids = {
        str(item.get("evidence_id") or "").strip()
        for item in selection_input.evidence_items
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    }
    repaired_claim_ids = [
        claim_id
        for claim_id in selection_input.repaired_selected_evidence_ids
        if claim_id in evidence_ids
    ]
    selected_claim_ids = tuple(
        dict.fromkeys(
            [
                *[
                    str(claim_id).strip()
                    for claim_id in selection_input.selected_claim_ids
                    if str(claim_id).strip()
                    and str(claim_id).strip() not in superseded_claim_ids
                ],
                *repaired_claim_ids,
            ]
        )
    )
    return AggregateStaleRepairProvenanceResult(
        selected_claim_ids=selected_claim_ids,
        target_resolution=target_resolution,
    )


def aggregate_selected_claim_ids(
    ordered_results: List[Dict[str, Any]],
    composition_selected_claim_ids: List[str],
) -> List[str]:
    """Return ordered, de-duplicated evidence ids used by aggregate synthesis."""
    return list(
        dict.fromkeys(
            [
                *[
                    claim_id
                    for row in ordered_results
                    for claim_id in (row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
                *composition_selected_claim_ids,
            ]
        )
    )


def aggregate_extend_selected_claim_ids(
    selected_claim_ids: List[str],
    additional_claim_ids: Iterable[str],
) -> List[str]:
    """Append selected claim ids while preserving first-seen order."""
    return list(dict.fromkeys([*selected_claim_ids, *additional_claim_ids]))


def aggregate_ordered_result_source_refs(ordered_results: List[Dict[str, Any]]) -> List[str]:
    """Collect source refs from aggregate subtask rows for ledger integrity."""
    return _clean_source_row_ids(
        [
            value
            for row in ordered_results
            for value in [
                row.get("source_row_id"),
                row.get("source_row_ids"),
                (row.get("calculation_result") or {}).get("source_row_id")
                if isinstance(row.get("calculation_result"), dict)
                else None,
                (row.get("calculation_result") or {}).get("source_row_ids")
                if isinstance(row.get("calculation_result"), dict)
                else None,
                (row.get("answer_slots") or {}).get("source_row_id")
                if isinstance(row.get("answer_slots"), dict)
                else None,
                (row.get("answer_slots") or {}).get("source_row_ids")
                if isinstance(row.get("answer_slots"), dict)
                else None,
            ]
        ]
    )


def aggregate_source_task_ids(ordered_results: List[Dict[str, Any]]) -> List[str]:
    """Return non-empty task ids represented by aggregate subtask rows."""
    return [
        str(row.get("task_id") or "").strip()
        for row in ordered_results
        if str(row.get("task_id") or "").strip()
    ]


def aggregate_period_context_evidence_items(
    aggregate_evidence_items: List[Dict[str, Any]],
    runtime_context_items: Iterable[Any],
) -> List[Dict[str, Any]]:
    """Append context evidence rows while preserving existing evidence ids."""
    period_context_evidence_items = list(aggregate_evidence_items)
    seen_period_context_ids = {
        _normalise_spaces(str(item.get("evidence_id") or ""))
        for item in period_context_evidence_items
        if isinstance(item, dict) and _normalise_spaces(str(item.get("evidence_id") or ""))
    }
    for item in runtime_context_items:
        if not isinstance(item, dict):
            continue
        evidence_id = _normalise_spaces(str(item.get("evidence_id") or ""))
        if evidence_id and evidence_id in seen_period_context_ids:
            continue
        if evidence_id:
            seen_period_context_ids.add(evidence_id)
        period_context_evidence_items.append(dict(item))
    return period_context_evidence_items


def aggregate_projection_for_integrity(
    preliminary_projection: Dict[str, Any],
    calculation_projection_override: Any,
) -> Dict[str, Any]:
    """Choose the projection that should back ledger integrity checks."""
    if isinstance(calculation_projection_override, dict) and calculation_projection_override:
        return calculation_projection_override
    return preliminary_projection


def aggregate_projection_apply_override(
    aggregate_projection: Dict[str, Any],
    calculation_projection_override: Any,
) -> Dict[str, Any]:
    """Apply supported calculation projection override fields in place."""
    if not isinstance(calculation_projection_override, dict):
        return aggregate_projection
    for key in ("calculation_operands", "calculation_plan", "calculation_result"):
        if calculation_projection_override.get(key):
            aggregate_projection[key] = calculation_projection_override[key]
    return aggregate_projection


def aggregate_integrity_extra_refs(
    projection_for_integrity: Dict[str, Any],
    ordered_result_source_refs: List[str],
    selected_claim_ids_for_integrity: List[str],
) -> List[Any]:
    """Build extra provenance refs for aggregate ledger artifact enrichment."""
    projection_result_for_integrity = dict(projection_for_integrity.get("calculation_result") or {})
    projection_slots_for_integrity = dict(projection_result_for_integrity.get("answer_slots") or {})
    return [
        projection_result_for_integrity.get("source_row_id"),
        projection_result_for_integrity.get("source_row_ids"),
        projection_slots_for_integrity.get("source_row_id"),
        projection_slots_for_integrity.get("source_row_ids"),
        ordered_result_source_refs,
        selected_claim_ids_for_integrity,
    ]


def aggregate_completion_base_payload(
    *,
    state: Dict[str, Any],
    ordered_results: List[Dict[str, Any]],
    aggregate_projection: Dict[str, Any],
    final_answer: str,
    selected_claim_ids: List[str],
    aggregate_evidence_items: List[Dict[str, Any]],
    tasks: List[Dict[str, Any]],
    artifacts: List[Dict[str, Any]],
    planner_feedback: str,
    should_replan: bool,
    replan_blocked_reason: str,
    aggregate_synthesis_debug: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the non-trace fields returned after aggregate subtask closure."""
    return {
        "subtask_results": ordered_results,
        "subtask_loop_complete": True,
        "answer": final_answer,
        "compressed_answer": final_answer,
        "planner_mode": "replan" if should_replan else "initial",
        "planner_feedback": planner_feedback,
        "replan_blocked_reason": replan_blocked_reason,
        "draft_points": [final_answer] if final_answer else [],
        "selected_claim_ids": selected_claim_ids,
        "kept_claim_ids": selected_claim_ids,
        "dropped_claim_ids": [],
        "unsupported_sentences": [],
        "sentence_checks": [],
        "tasks": tasks,
        "artifacts": artifacts,
        "evidence_items": aggregate_evidence_items or aggregate_projection.get("evidence_items", []),
        "subtask_debug_trace": {
            **dict(state.get("subtask_debug_trace") or {}),
            "aggregate_synthesis_prompt": aggregate_synthesis_debug,
        },
    }


def aggregate_artifact_payload(
    *,
    ordered_results: List[Dict[str, Any]],
    final_answer: str,
    planner_feedback: str,
    aggregate_projection: Dict[str, Any],
) -> Dict[str, Any]:
    """Build the payload stored on the aggregate synthesis artifact."""
    return {
        "subtask_results": ordered_results,
        "final_answer": final_answer,
        "planner_feedback": planner_feedback,
        **aggregate_projection,
    }


def aggregate_task_status_value(*, planner_feedback: str, completed_value: Any, partial_value: Any) -> Any:
    """Choose aggregate task status without coupling projection code to enums."""
    return partial_value if planner_feedback else completed_value
