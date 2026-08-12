"""
Calculation mixin for the financial graph agent.

This module adapts graph state across the structured numeric path:
- orchestrate operand resolution, planning, and deterministic execution owners
- project execution outcomes into canonical trace and artifact state
- advance or aggregate multi-subtask calculations

State-free matching and execution policy belong to their dedicated owner modules;
remaining repair paths stay here only until their callers and old bodies migrate.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Literal, NamedTuple, Optional, Sequence

from src.agent import financial_answer_slots
from src.agent.financial_answer_slots import (
    answer_slot_has_material,
    answer_slot_period_hint,
    period_match_key,
)
from src.agent.financial_answer_projection import (
    answer_covers_narrative_context,
    answer_looks_truncated,
    growth_answer_has_untraced_numeric_sentence,
    growth_row_has_conflicting_periods,
    growth_sentence_has_untraced_material_numeric,
    growth_uses_source_stated_result,
    material_gap_feedback_for_subtask_result,
    query_requests_explanatory_context,
    sentence_has_growth_explanatory_signal,
)
from src.agent.financial_aggregate_state import (
    AggregateCompositionState,
    _AggregateEvidenceState,
    _AggregateFeedbackState,
    _AggregateMutableState,
    _AggregateSynthesisState,
    _PreparedAggregateState,
    apply_aggregate_composition_answer,
)
from src.agent.financial_aggregate_projection import (
    AggregateArithmeticComponentSyncInput,
    AggregateAnswerCandidateApplicationInput,
    AggregateAnswerCandidatePackagingInput,
    AggregateNestedSubtaskSynchronizationInput,
    AggregateProjectionFinalAnswerSyncInput,
    AggregateProjectionProvenanceFilterInput,
    AggregateProjectionRowSurfaceSyncInput,
    AggregateRefreshedAnswerCandidatePackagingInput,
    AggregateStaleRepairProvenanceInput,
    RuntimeRatioAbsoluteMagnitudeProjectionInput,
    aggregate_artifact_payload as _aggregate_artifact_payload,
    aggregate_completion_base_payload as _aggregate_completion_base_payload,
    aggregate_extend_selected_claim_ids as _aggregate_extend_selected_claim_ids,
    aggregate_integrity_extra_refs as _aggregate_integrity_extra_refs,
    aggregate_lookup_primary_slots,
    aggregate_ordered_result_source_refs as _aggregate_ordered_result_source_refs,
    aggregate_period_context_evidence_items as _aggregate_period_context_evidence_items,
    aggregate_projection_rendered_value,
    aggregate_projection_apply_override as _aggregate_projection_apply_override,
    aggregate_projection_for_integrity as _aggregate_projection_for_integrity,
    aggregate_dependency_slot_coherence_rank_for_operands,
    aggregate_result_dependency_coherence_ranks,
    aggregate_result_operation_family as _aggregate_result_operation_family,
    aggregate_result_signature,
    aggregate_results_include_dependency_numeric_result,
    aggregate_results_include_source_task_slot_realignment,
    aggregate_selected_claim_ids as _aggregate_selected_claim_ids,
    aggregate_source_slot_by_task_id,
    aggregate_source_task_ids as _aggregate_source_task_ids,
    aggregate_synthesis_prompt_rows,
    append_final_answer_surface_operands_from_evidence,
    append_operand_evidence_for_final_answer,
    append_uncovered_lookup_numeric_items,
    apply_aggregate_answer_candidate,
    answer_reuses_narrative_summary_text,
    answer_reuses_numeric_narrative_summary_text,
    best_dependency_source_for_seed,
    component_slot_from_dependency_source,
    compose_complete_growth_numeric_answer,
    compose_lookup_list_numeric_answer,
    dedupe_aggregate_subtask_results,
    dependency_source_slot_match_score,
    ensure_complete_growth_numeric_answer,
    filter_aggregate_evidence_for_final_answer,
    filter_aggregate_projection_provenance,
    growth_slot_display_value,
    growth_slots_share_material,
    growth_answer_has_untraced_numeric_material,
    growth_narrative_numeric_incompatible_with_trace,
    row_is_narrative_summary,
    recover_growth_prior_material_from_evidence,
    safe_partial_answer_for_numeric_gap,
    growth_operand_sign_consistency_rank,
    growth_required_display_values,
    has_strong_growth_trace_for_answer_refresh,
    narrative_row_focus_context,
    narrative_row_focus_sentence,
    narrative_summary_conflicts_with_growth_trace,
    nested_aggregate_result_rank,
    package_aggregate_answer_candidate,
    package_refreshed_aggregate_answer_candidate,
    project_runtime_ratio_absolute_magnitude,
    ratio_rebuild_component_seeds,
    retrieved_ratio_projection_conflicts_with_existing_complete_result,
    select_aggregate_projection_answer_sentence,
    select_aggregate_projection_row_for_task,
    select_aggregate_stale_repair_provenance as _select_aggregate_stale_repair_provenance,
    subtask_numeric_answers_conflict,
    subtask_row_has_direct_source_refs,
    strip_untraced_numeric_material_from_growth_narrative_sentence,
    synchronize_aggregate_arithmetic_components,
    synchronize_aggregate_projection_row_surface,
    synchronize_nested_aggregate_subtask_rows,
    sync_aggregate_projection_final_answer,
)
from src.agent.financial_calculation_execution import (
    CalculationExecutionOutcome,
    assess_stale_calculation_value,
    build_deterministic_operation_plan,
    build_failed_calculation_result,
    build_scalar_calculation_state,
    build_scalar_calculation_result,
    build_success_calculation_state_payload,
    build_time_series_calculation_result,
    execute_prepared_calculation_plan,
    guard_operation_plan,
    resolve_deterministic_operation_plan,
)
from src.agent.financial_dependency_projection import (
    DependencyRatioResultProjectionInput,
    DependencyRecalculatedRowFinalizationInput,
    DependencyRecalculationCandidateProjectionInput,
    DependencyStructuredProvenanceAdoptionInput,
    LateDependencyRemergeInput,
    LateOperandFinalizationInput,
    MainOperandPrecedenceInput,
    RatioArtifactConflictSelectionInput,
    adopt_dependency_structured_provenance,
    apply_absolute_ratio_magnitude_if_requested,
    align_lookup_result_units_from_peer_source_slots,
    build_dependency_ratio_result_projection,
    build_dependency_lookup_slots_by_task,
    classify_dependency_recalculation_plan,
    collect_table_label_evidence_candidates,
    dedupe_dependency_operands_by_id,
    dependency_binding_identity,
    dependency_slot_matches_input,
    dependency_operand_from_answer_slot,
    dependency_operand_can_use_source_slot,
    dependency_operand_from_source_slot,
    dependency_operand_from_table_label_evidence,
    dependency_operand_rows_share_source_value,
    dependency_projection_slot_differs_from_operand,
    dependency_ratio_role_group,
    derive_dependency_operands_from_source_task_slots,
    fill_missing_ratio_dependency_operands,
    finalize_dependency_recalculated_row,
    filter_direct_rows_by_dependency_producer_scope,
    infer_dependency_row_unit,
    dependency_lookup_slot_match_score,
    lookup_primary_slot,
    refresh_dependency_operands_from_lookup_slots,
    realign_lookup_row_from_dependency_projection,
    rebuild_dependency_calculation_plan,
    replace_lookup_primary_slot,
    resolve_dependency_producer_scope,
    resolve_dependency_recalculation_candidate_projection,
    resolve_late_dependency_remerge,
    resolve_late_operand_finalization,
    resolve_main_operand_precedence,
    resolve_ratio_artifact_conflict_selection,
    source_task_id_for_dependency_operand,
    summarize_dependency_bindings,
    task_output_input_bindings,
    task_prefers_sibling_output_synthesis,
)
from src.agent.financial_operand_resolution import (
    DirectStructuredLookupEvidenceScoreInput,
    DirectStructuredOperandAcceptanceInput,
    DirectStructuredPreferredSlotAdoptionInput,
    PostCoercionLlmDirectSupportInput,
    PostCoercionLlmOperandSelectionInput,
    RecoveredOperandContextAdoptionInput,
    RequiredOperandCandidateMergeInput,
    _canonical_structured_reconciliation_id,
    _canonicalize_structured_operand_reconciliation_refs,
    collect_retrieval_context_docs,
    collect_retrieved_operand_evidence_candidates,
    coerce_operand_period_from_evidence_surface,
    coerce_operand_unit_from_evidence,
    dependency_task_output_has_consistent_krw_unit,
    direct_target_metric_row_conflicts_existing_units,
    direct_lookup_row_is_ambiguous_context_table,
    _evidence_item_for_operand_row,
    _evidence_items_by_id,
    _evidence_surface_contains_segment_label,
    evidence_item_conflicts_requested_scope,
    _filter_operand_rows_by_required_surface_contract,
    merge_operand_rows,
    _missing_required_operands,
    operand_prefers_aggregate_value_role as _operand_prefers_aggregate_value_role,
    _operand_rows_have_single_table_context,
    _operand_row_has_direct_evidence_surface,
    _operand_slot_has_evidence_surface_match,
    operand_row_conflicts_requested_scope,
    _operand_row_matches_requirement,
    _period_comparison_operand_rows_collapse_to_same_slot,
    _ratio_operand_rows_collapse_to_same_slot,
    operand_row_values_differ,
    operand_row_values_materially_conflict,
    align_growth_operand_units_when_raw_scale_matches,
    apply_operation_sign_policy,
    align_ratio_operand_units_with_shared_table_context,
    repair_operand_normalization_from_rendered_unit,
    resolve_direct_structured_operand_acceptance,
    resolve_direct_structured_preferred_slot_adoption,
    resolve_post_coercion_llm_direct_support,
    resolve_post_coercion_llm_operand_selection,
    resolve_recovered_operand_context_adoption,
    resolve_required_operand_candidate_merge,
    repair_krw_operand_units_from_table_metadata,
    repair_krw_normalized_values_from_raw_units,
    growth_operand_periods_conflict,
    score_direct_structured_lookup_evidence,
    surface_contract_numeric_evidence_items,
    table_label_metadata_lookup_score,
)
from src.agent import financial_graph_calculation_rendering as calculation_rendering
from src.agent.financial_graph_helpers import (
    _concept_spec_for_key,
    _operand_period_focus,
    _resolve_candidate_local_unit_hint,
    _scoped_surface_affinity_priority,
    _select_aggregate_structured_cell,
    _select_structured_cell,
)
from src.agent.financial_graph_model_loaders import (
    _aggregate_synthesis_output_model,
    _calculation_plan_model,
    _calculation_render_output_model,
    _calculation_verification_output_model,
    _operand_extraction_model,
)
from src.agent.financial_graph_state import FinancialAgentState
from src.agent.financial_langchain_loaders import _chat_prompt_template_from_template
from src.agent.financial_operation_policies import (
    _is_percent_point_difference_query,
    _is_ratio_percent_query,
    _query_requests_narrative_context,
    _requires_direct_numeric_grounding,
    _should_coerce_percent_point_unit,
)
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _display_operand_label,
    _normalise_operand_value,
    _normalise_spaces,
    _parse_number_text,
)
from src.agent.financial_scope_policies import (
    _desired_consolidation_scope,
    _extract_period_sort_key,
    known_consolidation_scope_value,
)
from src.agent.financial_text_surface import _strip_rerank_metadata, _tokenize_terms
from src.agent.financial_runtime_trace import (
    _collect_nested_result_evidence,
    _resolve_runtime_calculation_trace,
    _runtime_trace_state_update,
    overlay_calculation_operands_from_slots,
)
from src.agent.financial_reflection_projection import (
    reflection_action_from_plan as _reflection_action_from_plan,
    reflection_report_from_action as _reflection_report_from_action,
    reflection_synthesis_source_ids_from_task_outputs,
    task_artifact_integrity_feedback as _task_artifact_integrity_feedback,
)
from src.agent.financial_surface_contracts import (
    _operand_needles,
    _operand_segment_label,
    _text_has_negative_surface,
    _text_has_positive_surface,
)
from src.agent.financial_row_surfaces import (
    _extract_numeric_value_after_operand_text,
    _operand_text_match,
    _surface_match_variants,
)
from src.agent.financial_structured_cells import _structured_cell_period_text
from src.agent.financial_lookup_recovery import coerce_lookup_magnitude_record
from src.agent.financial_numeric_surface import (
    answer_covers_numeric_answer,
    answer_has_numeric_material_outside_reference,
    extract_numeric_surface_candidates,
    numeric_candidates_with_spans_from_surface,
    numeric_surface_slot_components,
    numeric_surface_candidates_equivalent,
    numeric_surface_conflicts_with_reference,
    ratio_components_have_suspicious_scale,
    ratio_result_has_suspicious_krw_scale,
    text_supports_numeric_candidates,
)
from src.agent.financial_text_surface import (
    include_narrative_context_if_needed,
    narrative_context_terms,
    narrative_context_sentence_from_evidence,
    narrative_focus_variants,
    narrative_sentence_looks_abbreviated_fragment as _narrative_sentence_looks_abbreviated_fragment,
    narrative_sentence_looks_table_noisy as _narrative_sentence_looks_table_noisy,
    parenthetical_focus_variants,
    policy_required_realized_snippet_from_doc,
    polish_korean_particle_pairs as _polish_korean_particle_pairs,
    preserve_retrieved_narrative_source_surface,
    split_narrative_sentences as _split_narrative_sentences,
    topic_particle as _topic_particle,
)
from src.agent.financial_task_artifacts import (
    AggregateArtifactProjectionPayloadSyncInput,
    aggregate_answer_artifact_update as _build_aggregate_answer_artifact_update,
    calculation_plan_artifact_update as _build_calculation_plan_artifact_update,
    evidence_items_with_runtime,
    enrich_reconciliation_artifact_refs,
    next_reflection_task_id,
    operand_set_artifact_update as _build_operand_set_artifact_update,
    project_task_artifact_trace as _project_task_artifact_trace,
    reflection_report_artifact_update as _build_reflection_report_artifact_update,
    ratio_result_rows_from_task_artifacts,
    synchronize_aggregate_artifact_projection_payload,
    synchronize_calculation_result_artifact as _synchronize_calculation_result_artifact,
    supersede_task_with_aggregate_result as _supersede_task_with_aggregate_result,
)
from src.agent.financial_graph_planning import _synthesize_lookup_answer_slot_from_prose
from src.agent.financial_lookup_recovery import (
    align_or_replace_successful_lookup_row,
    lookup_recovery_value_refinement_allowed,
    lookup_result_from_slot,
    normalize_lookup_slot_unit,
    recovered_slot_has_primary_label_match,
)
from src.config import get_financial_ontology
from src.config.runtime_contract import CALCULATION_DEBUG_TRACE_FIELD
from src.config.retrieval_policy import (
    CALCULATION_FEEDBACK_POLICY,
    CALCULATION_NARRATIVE_POLICY,
    CALCULATION_PROMPT_POLICY,
    CALCULATION_RENDER_POLICY,
    CALCULATION_SLOT_POLICY,
    CONSOLIDATION_SCOPE_POLICY,
    KOREAN_PERIOD_COMPARISON_RE_FRAGMENT,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    KOREAN_TABLE_CHANGE_HEADER_LABEL,
    KOREAN_TABLE_LABEL_ALPHA_RE_FRAGMENT,
    KOREAN_TABLE_LABEL_LEFT_BOUNDARY_RE_FRAGMENT,
    OPERAND_CANDIDATE_SCORING_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
    narrative_policy_terms,
)
from src.schema.runtime_enums import ArtifactKind, TaskStatus

logger = logging.getLogger(__name__)


class _OperandPrecisionContext(NamedTuple):
    row: Dict[str, Any]
    evidence_item: Optional[Dict[str, Any]]
    metadata: Dict[str, Any]
    records: List[Dict[str, Any]]
    operand_aliases: List[str]
    operand_spec: Dict[str, Any]
    raw_unit: str
    surface: str


class _CalculationCandidateInput(NamedTuple):
    calculation_operands: tuple[Dict[str, Any], ...]
    calculation_plan: Dict[str, Any]
    active_subtask: Dict[str, Any]
    query: str
    evidence_items: tuple[Any, ...]
    runtime_evidence: tuple[Any, ...]


class _PreparedCalculationCandidate(NamedTuple):
    status: str
    reason: str
    calculation_operands: tuple[Dict[str, Any], ...]
    calculation_plan: Dict[str, Any]
    active_subtask: Dict[str, Any]
    query: str
    operation_family: str
    result_unit: str
    execution_outcome: Optional[CalculationExecutionOutcome]
    selected_evidence_ids: tuple[str, ...]
    source_normalized_unit: str


class _CalculationCandidateProjection(NamedTuple):
    status: str
    reason: str
    calculation_operands: tuple[Dict[str, Any], ...]
    calculation_plan: Dict[str, Any]
    calculation_result: Dict[str, Any]
    selected_evidence_ids: tuple[str, ...]


class _CalculationCandidateRun(NamedTuple):
    prepared: _PreparedCalculationCandidate
    projection: _CalculationCandidateProjection


_OPERATION_PLAN_DECISION_UNSET = object()


_StaleCalculationRepairReason = Literal[
    "status_not_ok",
    "mode_not_single_value",
    "missing_formula",
    "same_slot",
    "preparation_failed",
    "current",
    "expected_value_unavailable",
    "current_value_unavailable",
    "projection_failed",
    "repaired",
]


class _StaleCalculationRepairResult(NamedTuple):
    repair_applied: bool
    reason: _StaleCalculationRepairReason
    calculation_operands: List[Dict[str, Any]]
    calculation_plan: Dict[str, Any]
    calculation_result: Dict[str, Any]
    selected_evidence_ids: tuple[str, ...]


def _calculation_debug_state_update(
    state: FinancialAgentState,
    update: Optional[Dict[str, Any]] = None,
    **entries: Any,
) -> Dict[str, Any]:
    """Return the optional internal calculation diagnostic scratch update."""
    debug_trace = dict(state.get(CALCULATION_DEBUG_TRACE_FIELD) or {})
    if update:
        debug_trace.update(dict(update))
    debug_trace.update(entries)
    return {CALCULATION_DEBUG_TRACE_FIELD: debug_trace}


def _clear_calculation_debug_state() -> Dict[str, Any]:
    """Clear the optional calculation diagnostic scratch field between attempts."""
    return {CALCULATION_DEBUG_TRACE_FIELD: {}}


def _has_duplicate_direct_lookup_rejection(state: FinancialAgentState) -> bool:
    traces = [
        *[
            dict(item)
            for item in (state.get("numeric_debug_trace_history") or [])
            if isinstance(item, dict)
        ],
        dict(state.get("numeric_debug_trace") or {}),
    ]
    return any(
        str(trace.get("skipped_reason") or "") == "duplicate_missing_direct_lookup_operand_support"
        for trace in traces
    )


class FinancialAgentCalculationMixin:
    def _operand_set_artifact_update(
        self,
        state: FinancialAgentState,
        active_subtask: Dict[str, Any],
        operand_rows: List[Dict[str, Any]],
        *,
        status: str,
        summary: str,
        payload: Dict[str, Any],
        evidence_refs: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        artifacts = list(state.get("artifacts") or [])
        tasks = list(state.get("tasks") or [])
        task_id = str(active_subtask.get("task_id") or "calc")
        artifacts = enrich_reconciliation_artifact_refs(
            artifacts,
            task_id=task_id,
            operand_rows=operand_rows,
        )
        return _build_operand_set_artifact_update(
            tasks=tasks,
            artifacts=artifacts,
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family=self._calc_metric_family(state),
            operand_rows=operand_rows,
            status=status,
            summary=summary,
            payload=payload,
            evidence_refs=evidence_refs,
        )

    def _calculation_plan_artifact_update(
        self,
        state: FinancialAgentState,
        calculation_plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        active_subtask = dict(state.get("active_subtask") or {})
        task_id = str(active_subtask.get("task_id") or "calc")
        return _build_calculation_plan_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            task_id=task_id,
            task_label=str(active_subtask.get("metric_label") or task_id),
            query=self._calc_query(state),
            metric_family=self._calc_metric_family(state),
            calculation_plan=calculation_plan,
        )

    def _slot_metric_keys(self, slot: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        concept = _normalise_spaces(str(slot.get("concept") or ""))
        if concept:
            keys.add(concept)
        label = _normalise_spaces(str(slot.get("label") or ""))
        if label:
            slot_policy = dict(CALCULATION_SLOT_POLICY)
            period_pattern = str(slot_policy.get("period_pattern") or "")
            if period_pattern:
                label = re.sub(period_pattern, " ", label)
            for needle in tuple(slot_policy.get("label_drop_terms") or ()):
                label = label.replace(needle, " ")
            for pattern in tuple(slot_policy.get("label_drop_patterns") or ()):
                label = re.sub(str(pattern), " ", label)
            label = label.replace("(", " ").replace(")", " ")
            label = _normalise_spaces(label)
            if label:
                keys.add(label)
                compact_label = label.replace(" ", "")
                if compact_label and compact_label != label:
                    keys.add(compact_label)
        return keys

    def _iter_answer_slots(self, answer_slots: Dict[str, Any]) -> List[Dict[str, Any]]:
        slots: List[Dict[str, Any]] = []
        for key in ("primary_value", "current_value", "prior_value", "delta_value"):
            slot = answer_slots.get(key)
            if isinstance(slot, dict):
                slots.append(dict(slot))

        for group_key in ("components_by_role", "components_by_group"):
            grouped = answer_slots.get(group_key)
            if not isinstance(grouped, dict):
                continue
            for entries in grouped.values():
                if isinstance(entries, list):
                    slots.extend(dict(entry) for entry in entries if isinstance(entry, dict))
                elif isinstance(entries, dict):
                    slots.append(dict(entries))
        return slots

    def _lookup_gap_is_satisfied_by_sibling_slots(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = self._aggregate_result_operation_family(row)
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        if (not operation_family or operation_family == "aggregate_subtasks") and metric_family.startswith("concept_"):
            operation_family = metric_family.removeprefix("concept_")
        if operation_family not in {"lookup", "single_value"}:
            return False

        target_slot = dict(answer_slots.get("primary_value") or {})
        target_keys = self._slot_metric_keys(target_slot)
        metric_label = _normalise_spaces(str(row.get("metric_label") or row.get("answer") or ""))
        if metric_label:
            target_keys.update(self._slot_metric_keys({"label": metric_label}))
        if not target_keys:
            return False

        target_periods = {
            period_match_key(period)
            for period in [
                answer_slot_period_hint(target_slot),
                *(
                    match.group(0)
                    for match in re.finditer(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), metric_label)
                ),
            ]
            if period_match_key(period)
        }

        target_concept = _normalise_spaces(str(target_slot.get("concept") or ""))
        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_result = dict(sibling.get("calculation_result") or {})
            sibling_slots = dict(sibling_result.get("answer_slots") or sibling.get("answer_slots") or {})
            for sibling_slot in self._iter_answer_slots(sibling_slots):
                if not answer_slot_has_material(sibling_slot):
                    continue
                if target_concept:
                    sibling_concept = _normalise_spaces(str(sibling_slot.get("concept") or ""))
                    if sibling_concept and sibling_concept != target_concept:
                        continue
                sibling_period = period_match_key(answer_slot_period_hint(sibling_slot))
                if target_periods and sibling_period and sibling_period not in target_periods:
                    continue
                if target_periods and not sibling_period:
                    continue
                sibling_keys = self._slot_metric_keys(sibling_slot)
                if target_keys & sibling_keys:
                    return True
                if any(
                    target_key and sibling_key and (target_key in sibling_key or sibling_key in target_key)
                    for target_key in target_keys
                    for sibling_key in sibling_keys
                ):
                    return True
        return False

    def _sibling_lookup_gap_is_satisfied(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = str(
            answer_slots.get("operation_family")
            or ((row.get("calculation_plan") or {}).get("operation_family"))
            or ((calculation_result.get("derived_metrics") or {}).get("operation_family"))
            or ""
        ).strip().lower()
        if operation_family not in {"difference", "growth_rate"}:
            return False

        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        current_material = answer_slot_has_material(current_slot)
        prior_material = answer_slot_has_material(prior_slot)
        if current_material and prior_material:
            return False

        target_keys = set()
        target_keys.update(self._slot_metric_keys(current_slot))
        target_keys.update(self._slot_metric_keys(prior_slot))
        if not target_keys:
            components = dict(answer_slots.get("components_by_role") or {})
            for role in ("current_period", "prior_period", "minuend", "subtrahend"):
                for slot in list(components.get(role) or []):
                    target_keys.update(self._slot_metric_keys(dict(slot or {})))
        if not target_keys:
            target_keys.add(_normalise_spaces(str(row.get("metric_label") or "")))

        current_period = answer_slot_period_hint(current_slot)
        prior_period = answer_slot_period_hint(prior_slot)
        sibling_periods: set[str] = set()

        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_result = dict(sibling.get("calculation_result") or {})
            sibling_slots = dict(sibling_result.get("answer_slots") or {})
            primary_slot = dict(sibling_slots.get("primary_value") or {})
            if not answer_slot_has_material(primary_slot):
                continue
            sibling_keys = self._slot_metric_keys(primary_slot)
            if not sibling_keys:
                continue
            if not (target_keys & sibling_keys):
                continue
            period_hint = answer_slot_period_hint(primary_slot)
            if period_hint:
                sibling_periods.add(period_hint)

        if not sibling_periods:
            return False
        if not current_material and current_period and current_period in sibling_periods:
            current_material = True
        if not prior_material and prior_period and prior_period in sibling_periods:
            prior_material = True
        if not current_material and sibling_periods:
            current_material = True
        if not prior_material:
            if current_period:
                prior_material = any(period != current_period for period in sibling_periods)
            else:
                prior_material = len(sibling_periods) >= 2
        return current_material and prior_material

    def _feedback_gap_is_satisfied_by_derived_slots(
        self,
        feedback: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        feedback_text = _normalise_spaces(str(feedback or ""))
        if not feedback_text:
            return False

        target_surface = re.split(
            r"(?:계산에 필요한|direct value|raw value|값[이가]?|재료)",
            feedback_text,
            maxsplit=1,
        )[0]
        target_keys = self._slot_metric_keys({"label": target_surface})
        if not target_keys:
            return False
        target_periods = {
            period_match_key(match.group(0))
            for match in re.finditer(r"20\d{2}\s*년?", feedback_text)
            if period_match_key(match.group(0))
        }

        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            for slot in self._iter_answer_slots(answer_slots):
                if not answer_slot_has_material(slot):
                    continue
                slot_period = period_match_key(answer_slot_period_hint(slot))
                if target_periods and slot_period and slot_period not in target_periods:
                    continue
                if target_periods and not slot_period:
                    continue
                slot_keys = self._slot_metric_keys(slot)
                if target_keys & slot_keys:
                    return True
                if any(
                    target_key and slot_key and (target_key in slot_key or slot_key in target_key)
                    for target_key in target_keys
                    for slot_key in slot_keys
                ):
                    return True
        return False

    def _final_aggregate_resolved_slots(
        self,
        aggregate_projection: Dict[str, Any],
        ordered_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        resolved_slots: List[Dict[str, Any]] = []
        calculation_result = dict(aggregate_projection.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        for slot in self._iter_answer_slots(answer_slots):
            if answer_slot_has_material(slot):
                resolved_slots.append(dict(slot))
        for row in list(ordered_results or []):
            row_result = dict(row.get("calculation_result") or {})
            row_slots = dict(row_result.get("answer_slots") or row.get("answer_slots") or {})
            for slot in self._iter_answer_slots(row_slots):
                if answer_slot_has_material(slot):
                    resolved_slots.append(dict(slot))
            for operand in list(row.get("calculation_operands") or []):
                if not isinstance(operand, dict):
                    continue
                slot = {
                    "label": operand.get("matched_operand_label") or operand.get("label"),
                    "concept": operand.get("matched_operand_concept") or operand.get("concept"),
                    "period": operand.get("period"),
                    "raw_value": operand.get("raw_value"),
                    "raw_unit": operand.get("raw_unit"),
                    "normalized_value": operand.get("normalized_value"),
                    "normalized_unit": operand.get("normalized_unit"),
                    "rendered_value": operand.get("rendered_value"),
                    "source_row_id": operand.get("evidence_id") or operand.get("source_row_id"),
                    "source_row_ids": _clean_source_row_ids(
                        [
                            operand.get("evidence_id"),
                            operand.get("source_row_id"),
                            operand.get("source_row_ids"),
                        ]
                    ),
                    "source_anchor": operand.get("source_anchor"),
                }
                if answer_slot_has_material(slot):
                    resolved_slots.append(slot)
        for operand in list(aggregate_projection.get("calculation_operands") or []):
            if not isinstance(operand, dict):
                continue
            slot = {
                "label": operand.get("matched_operand_label") or operand.get("label"),
                "concept": operand.get("matched_operand_concept") or operand.get("concept"),
                "period": operand.get("period"),
                "raw_value": operand.get("raw_value"),
                "raw_unit": operand.get("raw_unit"),
                "normalized_value": operand.get("normalized_value"),
                "normalized_unit": operand.get("normalized_unit"),
                "rendered_value": operand.get("rendered_value"),
                "source_row_id": operand.get("evidence_id") or operand.get("source_row_id"),
                "source_row_ids": _clean_source_row_ids(
                    [
                        operand.get("evidence_id"),
                        operand.get("source_row_id"),
                        operand.get("source_row_ids"),
                    ]
                ),
                "source_anchor": operand.get("source_anchor"),
            }
            if answer_slot_has_material(slot):
                resolved_slots.append(slot)
        return resolved_slots

    def _task_target_metric_keys(self, task: Dict[str, Any]) -> set[str]:
        keys: set[str] = set()
        candidate_labels = [
            str(task.get("label") or ""),
            str(task.get("metric_label") or ""),
        ]
        constraints = task.get("constraints") if isinstance(task.get("constraints"), dict) else {}
        candidate_labels.append(str(constraints.get("metric_label") or ""))
        for label in candidate_labels:
            label = _normalise_spaces(label)
            if not label:
                continue
            keys.update(self._slot_metric_keys({"label": label}))
            stripped_action = _normalise_spaces(re.sub(r"^[A-Za-z_]+\s+", " ", label, count=1))
            if stripped_action and stripped_action != label:
                keys.update(self._slot_metric_keys({"label": stripped_action}))
        return {key for key in keys if key}

    def _task_target_period_keys(self, task: Dict[str, Any]) -> set[str]:
        period_keys: set[str] = set()
        period_pattern = str(CALCULATION_SLOT_POLICY.get("period_pattern") or "")
        for value in (
            task.get("label"),
            task.get("metric_label"),
            (task.get("constraints") or {}).get("metric_label")
            if isinstance(task.get("constraints"), dict)
            else "",
        ):
            text = _normalise_spaces(str(value or ""))
            if not text or not period_pattern:
                continue
            for match in re.finditer(period_pattern, text):
                period_key = period_match_key(match.group(0))
                if period_key:
                    period_keys.add(period_key)
        return period_keys

    def _matching_resolved_slot_for_task(
        self,
        task: Dict[str, Any],
        resolved_slots: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        target_keys = self._task_target_metric_keys(task)
        if not target_keys:
            return {}
        target_periods = self._task_target_period_keys(task)
        for slot in resolved_slots:
            slot_keys = self._slot_metric_keys(slot)
            if not slot_keys:
                continue
            slot_period = period_match_key(answer_slot_period_hint(slot))
            if target_periods and slot_period and slot_period not in target_periods:
                continue
            if target_periods and not slot_period:
                continue
            if target_keys & slot_keys:
                return dict(slot)
            if any(
                target_key and slot_key and (target_key in slot_key or slot_key in target_key)
                for target_key in target_keys
                for slot_key in slot_keys
            ):
                return dict(slot)
        return {}

    def _task_target_matches_resolved_slot(
        self,
        task: Dict[str, Any],
        resolved_slots: List[Dict[str, Any]],
    ) -> bool:
        return bool(self._matching_resolved_slot_for_task(task, resolved_slots))

    def _resolved_slot_summary_for_task(
        self,
        task: Dict[str, Any],
        resolved_slots: List[Dict[str, Any]],
    ) -> str:
        slot = self._matching_resolved_slot_for_task(task, resolved_slots)
        if not slot:
            return ""
        rendered_value = _normalise_spaces(
            str(
                slot.get("rendered_value")
                or slot.get("raw_value")
                or slot.get("normalized_value")
                or ""
            )
        )
        if not rendered_value:
            return ""
        label = _normalise_spaces(
            str(slot.get("label") or slot.get("concept") or task.get("label") or "")
        )
        return _normalise_spaces(f"{label} {rendered_value}" if label else rendered_value)

    def _latest_task_artifact(
        self,
        task: Dict[str, Any],
        artifacts: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        artifact_by_id = {
            _normalise_spaces(str(item.get("artifact_id") or "")): dict(item)
            for item in artifacts
            if _normalise_spaces(str(item.get("artifact_id") or ""))
        }
        latest: Dict[str, Any] = {}
        for artifact_id in list(task.get("artifact_ids") or []):
            artifact = artifact_by_id.get(_normalise_spaces(str(artifact_id or "")))
            if artifact:
                latest = artifact
        return latest

    def _answer_preserves_task_numeric_surface(
        self,
        answer: str,
        task_summary: str,
    ) -> bool:
        if not answer_covers_numeric_answer(answer, task_summary):
            return False
        summary_candidates = extract_numeric_surface_candidates(task_summary)
        percent_surfaces = [
            _normalise_spaces(str(candidate.get("text") or ""))
            for candidate in summary_candidates
            if "%" in str(candidate.get("text") or "")
        ]
        if not percent_surfaces:
            return True
        normalized_answer = _normalise_spaces(answer)
        return all(surface and surface in normalized_answer for surface in percent_surfaces)

    def _task_aggregate_replacement_summary(
        self,
        task: Dict[str, Any],
        resolved_slots: List[Dict[str, Any]],
        *,
        ordered_results: List[Dict[str, Any]],
        aggregate_projection: Dict[str, Any],
        final_answer: str,
    ) -> str:
        task_id = _normalise_spaces(str(task.get("task_id") or ""))
        row = select_aggregate_projection_row_for_task(task_id, ordered_results, aggregate_projection)
        if row:
            sentence = select_aggregate_projection_answer_sentence(final_answer, row)
            if sentence:
                return sentence
            row_result = dict(row.get("calculation_result") or {})
            row_summary = _normalise_spaces(
                str(
                    row.get("answer")
                    or row_result.get("formatted_result")
                    or row_result.get("rendered_value")
                    or row.get("rendered_value")
                    or ""
                )
            )
            if row_summary:
                return row_summary
        slot_summary = self._resolved_slot_summary_for_task(task, resolved_slots)
        if slot_summary:
            return slot_summary
        return _normalise_spaces(final_answer)

    def _finalize_aggregate_task_ledger(
        self,
        tasks: List[Dict[str, Any]],
        artifacts: List[Dict[str, Any]],
        *,
        ordered_results: List[Dict[str, Any]],
        aggregate_projection: Dict[str, Any],
        aggregate_artifact_id: str,
        final_answer: str = "",
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        resolved_slots = self._final_aggregate_resolved_slots(aggregate_projection, ordered_results)
        updated_tasks = [dict(item) for item in tasks]
        updated_artifacts = [dict(item) for item in artifacts]
        aggregate_answer = _normalise_spaces(
            final_answer
            or str(
                (aggregate_projection.get("calculation_result") or {}).get("formatted_result")
                or (aggregate_projection.get("calculation_result") or {}).get("rendered_value")
                or ""
            )
        )

        for task in list(updated_tasks):
            task_id = str(task.get("task_id") or "").strip()
            if not task_id or task_id == "aggregate":
                continue
            status = _normalise_spaces(str(task.get("status") or "")).lower()
            if status not in {
                TaskStatus.PENDING.value,
                TaskStatus.PARTIAL.value,
                TaskStatus.COMPLETED.value,
            }:
                continue
            if not self._task_target_matches_resolved_slot(task, resolved_slots):
                continue
            replacement_summary = ""
            replacement_payload: Dict[str, Any] = {}
            if status == TaskStatus.COMPLETED.value:
                latest_artifact = self._latest_task_artifact(task, updated_artifacts)
                latest_summary = _normalise_spaces(str(latest_artifact.get("summary") or ""))
                if not latest_summary or self._answer_preserves_task_numeric_surface(
                    aggregate_answer,
                    latest_summary,
                ):
                    continue
                replacement_summary = self._task_aggregate_replacement_summary(
                    task,
                    resolved_slots,
                    ordered_results=ordered_results,
                    aggregate_projection=aggregate_projection,
                    final_answer=aggregate_answer,
                )
                if not replacement_summary or not self._answer_preserves_task_numeric_surface(
                    replacement_summary,
                    aggregate_answer,
                ):
                    replacement_summary = aggregate_answer
                if not replacement_summary:
                    continue
                replacement_conflicts = subtask_numeric_answers_conflict(
                    {"answer": replacement_summary},
                    {"answer": latest_summary},
                ) or not self._answer_preserves_task_numeric_surface(
                    replacement_summary,
                    latest_summary,
                )
                if not replacement_conflicts:
                    continue
                row = select_aggregate_projection_row_for_task(
                    task_id,
                    ordered_results,
                    aggregate_projection,
                )
                replacement_payload = {
                    "resolution_status": "superseded_by_aggregate_result",
                    "superseded_artifact_id": str(latest_artifact.get("artifact_id") or ""),
                    "superseded_by_artifact_id": aggregate_artifact_id,
                    "replacement_summary": replacement_summary,
                }
                if row:
                    replacement_payload["calculation_result"] = dict(
                        row.get("calculation_result") or {"formatted_result": replacement_summary}
                    )
            supersession_update = _supersede_task_with_aggregate_result(
                tasks=updated_tasks,
                artifacts=updated_artifacts,
                task=task,
                aggregate_artifact_id=aggregate_artifact_id,
                replacement_summary=replacement_summary,
                replacement_payload=replacement_payload,
            )
            updated_tasks = list(supersession_update["tasks"])
            updated_artifacts = list(supersession_update["artifacts"])
        return updated_tasks, updated_artifacts

    def _unresolved_structured_numeric_gap(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            if row_is_narrative_summary(row):
                continue
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family not in {"lookup", "single_value", "ratio", "sum", "difference", "growth_rate"}:
                if not metric_family.startswith("concept_"):
                    continue
            status = str(
                row.get("status")
                or (row.get("calculation_result") or {}).get("status")
                or ""
            ).strip().lower()
            gap = material_gap_feedback_for_subtask_result(row)
            if not gap and status and status != "ok":
                metric_label = _normalise_spaces(
                    str(row.get("metric_label") or row.get("task_id") or "계산 결과")
                )
                gap = f"{metric_label} 계산에 필요한 재료가 누락되었습니다."
            if not gap:
                continue
            if (
                self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                or self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results)
            ):
                continue
            return gap
        return ""

    def _lookup_value_from_table_label_metadata(
        self,
        operand: Dict[str, Any],
        evidence_item: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata = dict(evidence_item.get("metadata") or {})
        value_labels_text = _normalise_spaces(str(metadata.get("table_value_labels_text") or ""))
        if not value_labels_text:
            return {}
        binding_policy = dict(operand.get("binding_policy") or {})
        structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
        prefers_aggregate = bool(
            "aggregate"
            in {
                _normalise_spaces(str(item))
                for item in (binding_policy.get("prefer_value_roles") or [])
                if _normalise_spaces(str(item))
            }
            or {
                _normalise_spaces(str(item))
                for item in (binding_policy.get("prefer_aggregation_stages") or [])
                if _normalise_spaces(str(item))
            }
        )
        requires_exact_line_label = bool(prefers_aggregate and not structured_cells)
        if requires_exact_line_label:
            has_table_context = bool(
                _normalise_spaces(str(metadata.get("table_source_id") or ""))
                and (
                    _normalise_spaces(str(metadata.get("table_row_labels_text") or ""))
                    or _normalise_spaces(str(metadata.get("table_header_context") or ""))
                )
            )
            if not has_table_context:
                return {}
        surface_contract = dict(operand.get("surface_contract") or {})
        surfaces = list(
            dict.fromkeys(
                str(item).strip()
                for item in (
                    [operand.get("label")]
                    + list(operand.get("aliases") or [])
                    + list(surface_contract.get("positive") or [])
                )
                if str(item or "").strip()
            )
        )
        if not surfaces:
            return {}
        label_keys = [
            key
            for key in self._slot_metric_keys(
                {
                    "label": str(operand.get("label") or ""),
                    "concept": "",
                }
            )
            if key
        ]
        surfaces = list(dict.fromkeys(surfaces + label_keys))
        leading_period_strip_pattern = str(CALCULATION_SLOT_POLICY.get("leading_period_strip_pattern") or "")
        if leading_period_strip_pattern:
            periodless_surfaces = [
                _normalise_spaces(re.sub(leading_period_strip_pattern, " ", surface))
                for surface in surfaces
                if _normalise_spaces(str(surface or ""))
            ]
            surfaces = list(dict.fromkeys([*surfaces, *[surface for surface in periodless_surfaces if surface]]))
        value_pattern = r"\(?\s*[+-]?\d[\d,]*(?:\.\d+)?\s*\)?"
        percent_pattern = r"\(?\s*(?P<value>[+-]?\d[\d,]*(?:\.\d+)?)\s*%\s*\)?"

        def _operand_year_hint() -> str:
            year_candidates = re.findall(
                r"20\d{2}",
                " ".join(
                    str(operand.get(key) or "")
                    for key in ("period", "period_hint", "label", "name")
                ),
            )
            return year_candidates[0] if year_candidates else ""

        def _line_label_matches_operand(line_label: str) -> bool:
            normalized_label = _normalise_spaces(line_label)
            if not normalized_label:
                return False
            for surface in surfaces:
                normalized_surface = _normalise_spaces(surface)
                if not normalized_surface:
                    continue
                if normalized_surface == normalized_label:
                    return True
                if _operand_text_match(normalized_label, {"label": normalized_surface}):
                    return True
                if re.search(rf"(?<!\w){re.escape(normalized_label)}(?!\w)", normalized_surface):
                    return True
            return False

        matches: List[Dict[str, Any]] = []
        for line_index, line in enumerate(str(metadata.get("table_value_labels_text") or "").splitlines()):
            normalized_line = _normalise_spaces(line)
            if not normalized_line:
                continue
            matched_surface = ""
            matched_value = ""
            matched_line_label = ""
            for surface in sorted(surfaces, key=len, reverse=True):
                normalized_surface = _normalise_spaces(surface)
                if not normalized_surface:
                    continue
                match = re.search(
                    rf"(?<!\S){re.escape(normalized_surface)}\s+(?P<value>{value_pattern})(?!\S)",
                    normalized_line,
                )
                if not match:
                    continue
                matched_surface = normalized_surface
                matched_value = _normalise_spaces(match.group("value")).replace(" ", "")
                matched_line_label = _normalise_spaces(normalized_line[: match.start("value")])
                break
            if not matched_value:
                line_match = re.search(
                    rf"(?P<label>.+?)\s+(?P<value>{value_pattern})(?!\S)",
                    normalized_line,
                )
                if not line_match:
                    continue
                line_label = _normalise_spaces(line_match.group("label"))
                if not _line_label_matches_operand(line_label):
                    continue
                matched_surface = line_label
                matched_value = _normalise_spaces(line_match.group("value")).replace(" ", "")
                matched_line_label = line_label
            if matched_value:
                if requires_exact_line_label:
                    matched_line_compact = re.sub(r"\s+", "", matched_line_label)
                    exact_line_match = any(
                        matched_line_label == _normalise_spaces(surface)
                        or (
                            matched_line_compact
                            and matched_line_compact == re.sub(r"\s+", "", _normalise_spaces(surface))
                        )
                        for surface in surfaces
                    )
                    if not exact_line_match:
                        continue
                raw_value = matched_value
                raw_unit = _normalise_spaces(str(metadata.get("unit_hint") or ""))
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
                if normalized_value is None:
                    continue
                matches.append({
                    "status": "ok",
                    "role": str(operand.get("role") or "operand").strip() or "operand",
                    "label": str(operand.get("label") or normalized_surface).strip(),
                    "concept": str(operand.get("concept") or "").strip(),
                    "period": str(operand.get("period") or _operand_year_hint() or metadata.get("year") or ""),
                    "raw_value": raw_value,
                    "raw_unit": raw_unit,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "rendered_value": _normalise_spaces(f"{raw_value}{raw_unit}") if raw_unit else raw_value,
                    "source_row_id": str(evidence_item.get("evidence_id") or "").strip(),
                    "source_row_ids": [str(evidence_item.get("evidence_id") or "").strip()],
                    "source_anchor": evidence_item.get("source_anchor"),
                    "table_label_metadata_lookup": True,
                    "_semantic_label": normalized_line,
                    "_matched_surface": matched_surface,
                    "_matched_line_label": matched_line_label,
                    "_matched_line_index": line_index,
                })
        if not matches:
            return {}

        stated_change_raw_value = ""
        for line in str(metadata.get("table_value_labels_text") or "").splitlines():
            normalized_line = _normalise_spaces(line)
            if not normalized_line:
                continue
            percent_match = re.search(
                rf"(?P<label>.+?)\s+{percent_pattern}(?!\S)",
                normalized_line,
            )
            if not percent_match:
                continue
            line_label = _normalise_spaces(percent_match.group("label"))
            if not _line_label_matches_operand(line_label):
                continue
            stated_change_raw_value = _normalise_spaces(percent_match.group("value")).replace(" ", "")
            break

        role = str(operand.get("role") or "").strip()
        period_focus = _operand_period_focus(operand, "unknown")
        krw_matches = [
            match
            for match in matches
            if _normalise_spaces(str(match.get("normalized_unit") or "")).upper() == "KRW"
        ]
        candidate_pool = krw_matches or matches
        selected = candidate_pool[0]
        operand_year = _operand_year_hint()
        report_year = str(metadata.get("year") or "")
        row_label_matches_operand = _operand_text_match(
            _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("row_label"),
                        metadata.get("semantic_label"),
                        metadata.get("aggregate_label"),
                    )
                )
            ),
            operand,
        )
        if not row_label_matches_operand:
            slot_policy = dict(CALCULATION_SLOT_POLICY)
            leading_period_strip_pattern = str(slot_policy.get("leading_period_strip_pattern") or "")
            periodless_operand = dict(operand)
            for key in ("label", "name"):
                value = _normalise_spaces(str(periodless_operand.get(key) or ""))
                if value and leading_period_strip_pattern:
                    periodless_operand[key] = _normalise_spaces(re.sub(leading_period_strip_pattern, " ", value))
            aliases = []
            for alias in list(periodless_operand.get("aliases") or []):
                alias_text = _normalise_spaces(str(alias or ""))
                if alias_text and leading_period_strip_pattern:
                    alias_text = _normalise_spaces(re.sub(leading_period_strip_pattern, " ", alias_text))
                if alias_text:
                    aliases.append(alias_text)
            if aliases:
                periodless_operand["aliases"] = aliases
            row_label_matches_operand = _operand_text_match(
                _normalise_spaces(
                    " ".join(
                        str(value or "")
                        for value in (
                            metadata.get("row_label"),
                            metadata.get("semantic_label"),
                            metadata.get("aggregate_label"),
                        )
                    )
                ),
                periodless_operand,
            )
        if not row_label_matches_operand:
            selected_line_label = _normalise_spaces(
                str(selected.get("_matched_line_label") or selected.get("_matched_surface") or "")
            )
            if selected_line_label:
                row_label_matches_operand = _operand_text_match(selected_line_label, operand)
                if not row_label_matches_operand:
                    periodless_selected_line_label = selected_line_label
                    slot_policy = dict(CALCULATION_SLOT_POLICY)
                    leading_period_strip_pattern = str(slot_policy.get("leading_period_strip_pattern") or "")
                    if leading_period_strip_pattern:
                        periodless_selected_line_label = _normalise_spaces(
                            re.sub(leading_period_strip_pattern, " ", selected_line_label)
                        )
                    row_label_matches_operand = _operand_text_match(
                        periodless_selected_line_label,
                        periodless_operand if "periodless_operand" in locals() else operand,
                    )
        candidate_pool_from_single_line = len(
            {
                match.get("_matched_line_index")
                for match in candidate_pool
                if match.get("_matched_line_index") is not None
            }
        ) == 1
        period_header_text = _normalise_spaces(str(metadata.get("table_header_context") or ""))
        period_presence_pattern = str(CALCULATION_SLOT_POLICY.get("period_presence_pattern") or KOREAN_PERIOD_PREFIX_RE_FRAGMENT)
        fiscal_period_presence_pattern = str(CALCULATION_SLOT_POLICY.get("fiscal_period_presence_pattern") or "")
        table_has_period_columns = bool(
            len(metadata.get("period_labels") or []) > 1
            or re.search(period_presence_pattern, period_header_text)
            or (fiscal_period_presence_pattern and re.search(fiscal_period_presence_pattern, period_header_text))
        )
        if (
            prefers_aggregate
            and len(candidate_pool) > 1
            and not table_has_period_columns
            and not (row_label_matches_operand and candidate_pool_from_single_line)
        ):
            selected = candidate_pool[-1]
            selected["value_role"] = selected.get("value_role") or "aggregate"
            selected["aggregation_stage"] = selected.get("aggregation_stage") or "final"
        elif operand_year and report_year and operand_year.isdigit() and report_year.isdigit():
            period_offset = max(int(report_year) - int(operand_year), 0)
            if period_offset > 0:
                selected = candidate_pool[min(period_offset, len(candidate_pool) - 1)]
            else:
                selected = candidate_pool[0]
        elif role == "prior_period" or period_focus == "prior":
            selected = candidate_pool[1] if len(candidate_pool) >= 2 else candidate_pool[-1]
        elif role == "current_period" or period_focus == "current":
            selected = candidate_pool[0]
        if not operand_year and report_year and report_year.isdigit():
            if role == "prior_period" or period_focus == "prior":
                selected["period"] = str(int(report_year) - 1)
            elif role == "current_period" or period_focus == "current":
                selected["period"] = report_year
        if stated_change_raw_value:
            selected["stated_change_raw_value"] = stated_change_raw_value
            selected["stated_change_raw_unit"] = "%"

        semantic_label = str(selected.pop("_semantic_label", ""))
        return coerce_lookup_magnitude_record(
            selected,
            evidence_item,
            concept=str(operand.get("concept") or ""),
            statement_type=str(metadata.get("statement_type") or ""),
            row_label=str(operand.get("label") or selected.get("label") or ""),
            semantic_label=semantic_label,
        )

    def _lookup_row_from_direct_structured_evidence(
        self,
        operand: Dict[str, Any],
        evidence_item: Dict[str, Any],
        *,
        index: int,
    ) -> Dict[str, Any]:
        metadata = dict(evidence_item.get("metadata") or {})
        cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
        if not cells:
            return {}
        selected_cell = _select_structured_cell(
            [{**cell, "_report_year": metadata.get("year")} for cell in cells],
            operand=operand,
            query_years=[int(metadata["year"])] if str(metadata.get("year") or "").isdigit() else [],
            period_focus=_operand_period_focus(operand, "current"),
        )
        metadata_value_role = _normalise_spaces(str(metadata.get("value_role") or "")).lower()
        metadata_aggregation_stage = _normalise_spaces(str(metadata.get("aggregation_stage") or "")).lower()
        if (
            metadata_value_role == "aggregate"
            or metadata_aggregation_stage in {"direct", "final", "subtotal"}
            or _operand_prefers_aggregate_value_role(operand)
        ):
            aggregate_cells = [
                cell
                for cell in cells
                if _normalise_spaces(str(cell.get("value_role") or "")).lower() == "aggregate"
                or _normalise_spaces(str(cell.get("aggregation_stage") or "")).lower() in {"direct", "final", "subtotal"}
                or _normalise_spaces(str(cell.get("aggregate_label") or ""))
            ]
            aggregate_selected_cell = _select_aggregate_structured_cell(
                [{**cell, "_report_year": metadata.get("year")} for cell in aggregate_cells],
                operand=operand,
                query_years=[int(metadata["year"])] if str(metadata.get("year") or "").isdigit() else [],
                period_focus=_operand_period_focus(operand, "current"),
            )
            if aggregate_selected_cell:
                selected_cell = aggregate_selected_cell
        if not selected_cell:
            return {}
        raw_value = _normalise_spaces(str(selected_cell.get("value_text") or ""))
        raw_unit = _normalise_spaces(str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or ""))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        if normalized_value is None:
            return {}
        evidence_id = str(evidence_item.get("evidence_id") or "").strip()
        row = {
            "operand_id": f"direct_lookup_{index:03d}",
            "evidence_id": evidence_id,
            "source_row_id": evidence_id,
            "source_row_ids": [evidence_id] if evidence_id else [],
            "source_anchor": _normalise_spaces(str(evidence_item.get("source_anchor") or "")),
            "label": _normalise_spaces(str(operand.get("label") or metadata.get("row_label") or "")),
            "raw_value": raw_value,
            "raw_unit": raw_unit,
            "normalized_value": normalized_value,
            "normalized_unit": normalized_unit,
            "period": _normalise_spaces(str(metadata.get("year") or "")),
            "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
            "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
            "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
            "statement_type": metadata.get("statement_type"),
            "consolidation_scope": metadata.get("consolidation_scope"),
            "table_source_id": metadata.get("table_source_id"),
            "value_role": _normalise_spaces(str(selected_cell.get("value_role") or metadata.get("value_role") or "")),
            "aggregation_stage": _normalise_spaces(
                str(selected_cell.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
            ),
            "aggregate_label": _normalise_spaces(
                str(selected_cell.get("aggregate_label") or metadata.get("aggregate_label") or "")
            ),
        }
        return coerce_lookup_magnitude_record(
            row,
            evidence_item,
            concept=str(operand.get("concept") or ""),
            statement_type=str(metadata.get("statement_type") or ""),
            row_label=str(metadata.get("row_label") or operand.get("label") or ""),
            semantic_label=str(metadata.get("semantic_label") or metadata.get("row_label") or ""),
        )

    def _best_direct_lookup_slot_from_evidence_pool(
        self,
        operand: Dict[str, Any],
        evidence_pool: List[Dict[str, Any]],
        *,
        state: Optional[FinancialAgentState] = None,
        preferred_raw_units: Optional[set[str]] = None,
    ) -> tuple[Dict[str, Any], float]:
        best_slot: Dict[str, Any] = {}
        best_score = 0.0
        preferred_units = {
            _normalise_spaces(str(unit or ""))
            for unit in (preferred_raw_units or set())
            if _normalise_spaces(str(unit or ""))
        }

        def _candidate_preferred_on_tie(candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
            if not preferred_units:
                return False
            candidate_unit = _normalise_spaces(str(candidate.get("raw_unit") or ""))
            current_unit = _normalise_spaces(str(current.get("raw_unit") or ""))
            return bool(candidate_unit in preferred_units and current_unit not in preferred_units)

        def _aggregate_candidate_preferred_in_same_table(candidate: Dict[str, Any], current: Dict[str, Any]) -> bool:
            if not candidate or not current:
                return False
            candidate_table = _normalise_spaces(str(candidate.get("table_source_id") or ""))
            current_table = _normalise_spaces(str(current.get("table_source_id") or ""))
            if not candidate_table or candidate_table != current_table:
                return False
            candidate_value_role = _normalise_spaces(str(candidate.get("value_role") or "")).lower()
            current_value_role = _normalise_spaces(str(current.get("value_role") or "")).lower()
            candidate_stage = _normalise_spaces(str(candidate.get("aggregation_stage") or "")).lower()
            current_stage = _normalise_spaces(str(current.get("aggregation_stage") or "")).lower()
            candidate_is_aggregate = bool(
                candidate_value_role == "aggregate"
                or candidate_stage in {"direct", "final", "subtotal"}
                or _normalise_spaces(str(candidate.get("aggregate_label") or ""))
            )
            current_is_aggregate = bool(
                current_value_role == "aggregate"
                or current_stage in {"direct", "final", "subtotal"}
                or _normalise_spaces(str(current.get("aggregate_label") or ""))
            )
            if not candidate_is_aggregate or current_is_aggregate:
                return False
            candidate_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        candidate.get("label"),
                        candidate.get("aggregate_label"),
                        candidate.get("semantic_label"),
                    )
                )
            )
            return _operand_text_match(candidate_surface, operand)

        def _context_scope_score(evidence: Dict[str, Any]) -> float:
            if state is None:
                return 0.0
            desired_scope = _desired_consolidation_scope(
                str(state.get("query") or ""),
                dict(state.get("report_scope") or {}),
            )
            if desired_scope == "unknown":
                return 0.0
            metadata = dict(evidence.get("metadata") or {})
            metadata_scope = _normalise_spaces(str(metadata.get("consolidation_scope") or "unknown"))
            if metadata_scope == desired_scope:
                return 1.5
            context_markers = tuple(
                str(marker)
                for marker in (dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {}).get(desired_scope) or ())
                if str(marker)
            )
            if not context_markers:
                return 0.0
            primary_context = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("local_heading"),
                        metadata.get("table_context"),
                        metadata.get("section_path"),
                    )
                    if str(value or "").strip()
                )
            )
            if any(marker in primary_context for marker in context_markers):
                return 1.25
            secondary_context = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        evidence.get("claim"),
                        evidence.get("quote_span"),
                        evidence.get("raw_row_text"),
                        evidence.get("source_context"),
                    )
                    if str(value or "").strip()
                )
            )
            if any(marker in secondary_context for marker in context_markers):
                return 0.35
            return 0.0

        def _claim_visible_lookup_slot(evidence: Dict[str, Any]) -> tuple[Dict[str, Any], float]:
            evidence_id = _normalise_spaces(str(evidence.get("evidence_id") or ""))
            source_text = _normalise_spaces(
                " ".join(
                    str(evidence.get(key) or "")
                    for key in ("claim", "quote_span", "raw_row_text")
                    if str(evidence.get(key) or "").strip()
                )
            )
            if not source_text or not _text_has_positive_surface(source_text, operand):
                return {}, 0.0
            metadata = dict(evidence.get("metadata") or {})
            if _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
                row_surface = _normalise_spaces(
                    " ".join(
                        str(value or "")
                        for value in (
                            metadata.get("row_label"),
                            metadata.get("semantic_label"),
                            metadata.get("aggregate_label"),
                        )
                        if str(value or "").strip()
                    )
                )
                source_compact = re.sub(r"\s+", "", source_text)
                needle_surfaces = [
                    _normalise_spaces(str(needle))
                    for needle in _operand_needles(operand)
                    if _normalise_spaces(str(needle))
                ]
                claim_has_operand_label = any(
                    needle in source_text or re.sub(r"\s+", "", needle) in source_compact
                    for needle in needle_surfaces
                )
                row_matches_operand = bool(row_surface and _operand_text_match(row_surface, operand))
                if not claim_has_operand_label and not row_matches_operand:
                    return {}, 0.0
            best_candidate: Dict[str, Any] = {}
            for candidate in extract_numeric_surface_candidates(source_text):
                components = numeric_surface_slot_components(candidate)
                if not components or not components.get("raw_unit"):
                    continue
                best_candidate = {
                    "source_row_id": evidence_id,
                    "source_row_ids": [evidence_id] if evidence_id else [],
                    "source_anchor": _normalise_spaces(str(evidence.get("source_anchor") or "")),
                    "label": _normalise_spaces(str(operand.get("label") or metadata.get("semantic_label") or "")),
                    **components,
                    "period": _normalise_spaces(str(metadata.get("year") or "")),
                    "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
                    "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
                    "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
                }
                break
            if not best_candidate:
                return {}, 0.0
            score = 6.0
            if _normalise_spaces(str(metadata.get("unit_hint") or "")):
                score += 0.5
            if _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
                score += 0.5
            if _normalise_spaces(str(metadata.get("table_source_id") or "")):
                score += 0.5
            if _normalise_spaces(str(evidence.get("source_anchor") or "")):
                score += 0.25
            return best_candidate, score

        def _metadata_row_surface_matches_operand(evidence: Dict[str, Any]) -> bool:
            metadata = dict(evidence.get("metadata") or {})
            row_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("row_label"),
                        metadata.get("semantic_label"),
                        metadata.get("aggregate_label"),
                    )
                    if str(value or "").strip()
                )
            )
            return bool(row_surface and _operand_text_match(row_surface, operand))

        for evidence_item in evidence_pool:
            evidence = dict(evidence_item or {})
            metadata = dict(evidence.get("metadata") or {})
            evidence_id = _normalise_spaces(str(evidence.get("evidence_id") or ""))
            structured_slot_selected_for_evidence = False
            score = score_direct_structured_lookup_evidence(
                DirectStructuredLookupEvidenceScoreInput(
                    operand=operand,
                    evidence_item=evidence,
                )
            ).score
            if score > 0:
                score += _context_scope_score(evidence)
            should_consider_structured = score > best_score
            candidate_row: Dict[str, Any] = {}
            if score == best_score and best_slot:
                candidate_row = self._lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence,
                    index=1,
                )
                should_consider_structured = _candidate_preferred_on_tie(candidate_row, best_slot)
            elif score > 0 and best_slot:
                candidate_row = self._lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence,
                    index=1,
                )
                if _aggregate_candidate_preferred_in_same_table(candidate_row, best_slot):
                    should_consider_structured = True
            if should_consider_structured:
                row = candidate_row or self._lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence,
                    index=1,
                )
                if state is not None and direct_lookup_row_is_ambiguous_context_table(
                    row,
                    evidence,
                    query=str(state.get("query") or ""),
                    active_subtask=dict(state.get("active_subtask") or {}),
                    required_operands=[operand],
                ):
                    row = {}
                normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
                raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
                raw_digit_count = len(re.findall(r"\d", str(row.get("raw_value") or "")))
                if row and not (normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4):
                    adjusted_score = score - 1.5 if normalized_unit in {"", "UNKNOWN"} else score
                    best_slot = financial_answer_slots.build_operand_value_slot(
                        row,
                        default_role=str(operand.get("role") or "primary_value"),
                        preserve_source_display=True,
                    )
                    best_score = adjusted_score
                    structured_slot_selected_for_evidence = True

            table_label_slot = self._lookup_value_from_table_label_metadata(operand, evidence)
            table_label_score = table_label_metadata_lookup_score(table_label_slot, evidence)
            table_has_period_columns = bool(
                _normalise_spaces(str(metadata.get("period_labels") or ""))
                or re.search(
                    str(CALCULATION_SLOT_POLICY.get("period_presence_pattern") or KOREAN_PERIOD_PREFIX_RE_FRAGMENT),
                    _normalise_spaces(str(metadata.get("table_header_context") or "")),
                )
            )
            if (
                structured_slot_selected_for_evidence
                and table_has_period_columns
                and _metadata_row_surface_matches_operand(evidence)
            ):
                table_label_slot = {}
                table_label_score = 0.0
            if table_label_score > 0:
                table_label_score += _context_scope_score(evidence)
            if state is not None and direct_lookup_row_is_ambiguous_context_table(
                table_label_slot,
                evidence,
                query=str(state.get("query") or ""),
                active_subtask=dict(state.get("active_subtask") or {}),
                required_operands=[operand],
            ):
                table_label_slot = {}
            if table_label_slot and (
                table_label_score > best_score
                or (
                    table_label_score == best_score
                    and best_slot
                    and (
                        _candidate_preferred_on_tie(table_label_slot, best_slot)
                        or (
                            bool(table_label_slot.get("table_label_metadata_lookup"))
                            and evidence_id
                            and evidence_id
                            in set(
                                _clean_source_row_ids([
                                    best_slot.get("source_row_id"),
                                    best_slot.get("source_row_ids"),
                                ])
                            )
                        )
                    )
                )
            ):
                best_slot = table_label_slot
                best_score = table_label_score

            claim_slot, claim_score = _claim_visible_lookup_slot(evidence)
            if claim_score > 0:
                claim_score += _context_scope_score(evidence)
            if claim_slot and (
                claim_score > best_score
                or (
                    claim_score == best_score
                    and best_slot
                    and _candidate_preferred_on_tie(claim_slot, best_slot)
                )
            ):
                best_slot = claim_slot
                best_score = claim_score

        if not best_slot or best_score < 6.0:
            return {}, 0.0
        return best_slot, best_score

    def _prefer_direct_structured_evidence_rows(
        self,
        direct_structured_rows: List[Dict[str, Any]],
        *,
        evidence_items: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
        operation_family: str,
        state: Optional[FinancialAgentState] = None,
    ) -> List[Dict[str, Any]]:
        if operation_family not in {"lookup", "single_value", "ratio"} or not required_operands:
            return direct_structured_rows

        evidence_by_id = _evidence_items_by_id(evidence_items)
        refined_rows = [dict(row) for row in direct_structured_rows]

        for operand in [dict(item) for item in required_operands]:
            row_index = next(
                (
                    index
                    for index, row in enumerate(refined_rows)
                    if _operand_row_matches_requirement(row, operand)
                ),
                None,
            )
            if row_index is None:
                continue
            current = dict(refined_rows[row_index])
            peer_units = {
                _normalise_spaces(str(row.get("raw_unit") or ""))
                for index, row in enumerate(refined_rows)
                if index != row_index
                and _normalise_spaces(str(row.get("raw_unit") or ""))
                and _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
                == _normalise_spaces(str(current.get("normalized_unit") or "")).upper()
            }
            preferred_slot, best_score = self._best_direct_lookup_slot_from_evidence_pool(
                operand,
                evidence_items,
                state=state,
                preferred_raw_units=peer_units if operation_family == "ratio" else None,
            )
            if not preferred_slot:
                continue
            current_score = 0.0
            current_evidence = _evidence_item_for_operand_row(current, evidence_by_id)
            if current_evidence:
                current_score = score_direct_structured_lookup_evidence(
                    DirectStructuredLookupEvidenceScoreInput(
                        operand=operand,
                        evidence_item=current_evidence,
                    )
                ).score
            preferred_slot_adoption = resolve_direct_structured_preferred_slot_adoption(
                DirectStructuredPreferredSlotAdoptionInput(
                    operation_family=operation_family,
                    row_index=row_index,
                    current_operand_row=current,
                    required_operand=operand,
                    normalized_peer_raw_units=peer_units,
                    preferred_slot=preferred_slot,
                    preferred_score=best_score,
                    current_score=current_score,
                )
            )
            if preferred_slot_adoption.preferred_slot_adopted:
                refined_rows[row_index] = preferred_slot_adoption.selected_operand_row
        return refined_rows

    def _prefer_direct_structured_lookup_evidence_rows(
        self,
        direct_structured_rows: List[Dict[str, Any]],
        *,
        evidence_items: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
        operation_family: str,
        state: Optional[FinancialAgentState] = None,
    ) -> List[Dict[str, Any]]:
        if operation_family not in {"lookup", "single_value"} or len(required_operands) != 1:
            return direct_structured_rows
        return self._prefer_direct_structured_evidence_rows(
            direct_structured_rows,
            evidence_items=evidence_items,
            required_operands=required_operands,
            operation_family=operation_family,
            state=state,
        )

    def _recover_lookup_results_from_sibling_table_evidence(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        task_by_id = {
            str(task.get("task_id") or ""): dict(task)
            for task in (state.get("calc_subtasks") or [])
            if str(task.get("task_id") or "").strip()
        }
        evidence_pool: List[Dict[str, Any]] = _collect_nested_result_evidence(ordered_results)
        evidence_pool.extend(dict(item) for item in (state.get("evidence_items") or []) if isinstance(item, dict))
        evidence_pool.extend(dict(item) for item in (state.get("runtime_evidence") or []) if isinstance(item, dict))
        context_docs = list(state.get("seed_retrieved_docs") or []) + list(state.get("retrieved_docs") or [])

        def _row_allows_seed_context_lookup_recovery(row: Dict[str, Any]) -> bool:
            task = task_by_id.get(str(row.get("task_id") or "")) or {}
            operation_family = _normalise_spaces(
                str(row.get("operation_family") or task.get("operation_family") or "")
            ).lower()
            if operation_family not in {"lookup", "single_value"}:
                return False
            metric_family = _normalise_spaces(
                str(row.get("metric_family") or task.get("metric_family") or "")
            ).lower()
            if metric_family == "concept_lookup":
                return False
            return True

        if context_docs and any(_row_allows_seed_context_lookup_recovery(dict(row)) for row in ordered_results):
            desired_scope = _desired_consolidation_scope(
                str(state.get("query") or ""),
                dict(state.get("report_scope") or {}),
            )
            existing_ids = {
                str(item.get("evidence_id") or "").strip()
                for item in evidence_pool
                if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
            }
            for item in self._ratio_operand_context_evidence_from_docs(context_docs, max_docs=64):
                if evidence_item_conflicts_requested_scope(item, desired_scope):
                    continue
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id and evidence_id in existing_ids:
                    continue
                if evidence_id:
                    existing_ids.add(evidence_id)
                evidence_pool.append(dict(item))
        if not evidence_pool:
            return ordered_results
        evidence_by_id = _evidence_items_by_id(evidence_pool)

        desired_scope = _desired_consolidation_scope(
            str(state.get("query") or ""),
            dict(state.get("report_scope") or {}),
        )

        def _value_refinement_allowed(
            current_slot: Dict[str, Any],
            preferred_slot: Dict[str, Any],
            preferred_evidence: Optional[Dict[str, Any]],
        ) -> bool:
            current_evidence = _evidence_item_for_operand_row(current_slot, evidence_by_id)
            return lookup_recovery_value_refinement_allowed(
                current_slot,
                preferred_slot,
                preferred_evidence,
                desired_scope=desired_scope,
                current_evidence=current_evidence,
                operand=operand,
                recovered_slot_matches_primary_label=_recovered_slot_has_primary_label_match,
                operand_rows_materially_conflict=operand_row_values_materially_conflict,
            )

        def _normalize_lookup_slot_unit(slot: Dict[str, Any]) -> Dict[str, Any]:
            return normalize_lookup_slot_unit(
                slot,
                evidence_by_id=evidence_by_id,
            )

        def _lookup_result_from_slot(slot: Dict[str, Any], source_note: str) -> Dict[str, Any]:
            return lookup_result_from_slot(
                slot,
                source_note,
                normalize_slot=_normalize_lookup_slot_unit,
            )

        def _preferred_slot_has_evidence_surface_match(
            preferred_slot: Dict[str, Any],
            preferred_evidence: Optional[Dict[str, Any]],
        ) -> bool:
            return _operand_slot_has_evidence_surface_match(
                preferred_slot,
                preferred_evidence,
                operand,
                metric_label=str(row.get("metric_label") or ""),
            )

        recovered_results: List[Dict[str, Any]] = []
        for row in ordered_results:
            task = task_by_id.get(str(row.get("task_id") or "")) or {}
            operation_family = _normalise_spaces(
                str(row.get("operation_family") or task.get("operation_family") or "")
            ).lower()
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if operation_family not in {"lookup", "single_value"}:
                recovered_results.append(row)
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            current_slot = dict(answer_slots.get("primary_value") or {})
            operands = [dict(item) for item in (task.get("required_operands") or []) if bool(item.get("required", True))]
            if len(operands) != 1 and current_slot:
                fallback_operand = {
                    "label": current_slot.get("label") or row.get("metric_label"),
                    "concept": current_slot.get("concept"),
                    "role": current_slot.get("role") or "primary_value",
                    "period": current_slot.get("period"),
                    "required": True,
                }
                if _normalise_spaces(str(fallback_operand.get("label") or fallback_operand.get("concept") or "")):
                    operands = [fallback_operand]
            if len(operands) != 1:
                recovered_results.append(row)
                continue
            operand = operands[0]

            def _recovered_slot_has_primary_label_match(slot: Dict[str, Any]) -> bool:
                return recovered_slot_has_primary_label_match(
                    slot,
                    operand=operand,
                    metric_label=str(row.get("metric_label") or ""),
                    slot_metric_keys=self._slot_metric_keys,
                )

            if status == "ok":
                recovered_results.append(
                    align_or_replace_successful_lookup_row(
                        row,
                        current_slot=current_slot,
                        operand=operand,
                        evidence_by_id=evidence_by_id,
                        evidence_pool=evidence_pool,
                        state=state,
                        normalize_slot=_normalize_lookup_slot_unit,
                        lookup_result_builder=_lookup_result_from_slot,
                        best_direct_lookup_slot=self._best_direct_lookup_slot_from_evidence_pool,
                        preferred_slot_has_evidence_surface_match=_preferred_slot_has_evidence_surface_match,
                        value_refinement_allowed=_value_refinement_allowed,
                    )
                )
                continue
            sibling_surfaces = [
                _normalise_spaces(str(item))
                for item in (task.get("sibling_lookup_surfaces") or [])
                if _normalise_spaces(str(item))
            ]
            recovered_slot: Dict[str, Any] = {}
            for evidence_item in evidence_pool:
                metadata = dict(evidence_item.get("metadata") or {})
                table_value_labels = _normalise_spaces(str(metadata.get("table_value_labels_text") or ""))
                if not table_value_labels:
                    continue
                if sibling_surfaces and not any(surface in table_value_labels for surface in sibling_surfaces):
                    continue
                recovered_slot = self._lookup_value_from_table_label_metadata(operand, evidence_item)
                if recovered_slot:
                    if not _recovered_slot_has_primary_label_match(recovered_slot):
                        recovered_slot = {}
                        continue
                    if direct_lookup_row_is_ambiguous_context_table(
                        recovered_slot,
                        evidence_item,
                        query=str(state.get("query") or ""),
                        active_subtask=dict(state.get("active_subtask") or {}),
                        required_operands=[operand],
                    ):
                        recovered_slot = {}
                        continue
                    break
            if not recovered_slot:
                recovered_results.append(row)
                continue
            rendered_value = _normalise_spaces(str(recovered_slot.get("rendered_value") or ""))
            label = _normalise_spaces(str(recovered_slot.get("label") or row.get("metric_label") or ""))
            calculation_result = _lookup_result_from_slot(
                {**recovered_slot, "label": label},
                "lookup result recovered from sibling table evidence.",
            )
            recovered_results.append(
                {
                    **dict(row),
                    "status": "ok",
                    "answer": str(calculation_result.get("formatted_result") or ""),
                    "calculation_result": calculation_result,
                    "answer_slots": calculation_result["answer_slots"],
                    "runtime_evidence": list(row.get("runtime_evidence") or []),
                    "recovered_from_sibling_table_evidence": True,
                }
            )
        return recovered_results

    def _align_lookup_result_units_from_own_evidence(
        self,
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
                str(row.get("operation_family") or self._aggregate_result_operation_family(row) or "")
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

    def _align_lookup_result_units_from_peer_source_slots(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        return align_lookup_result_units_from_peer_source_slots(
            ordered_results,
            operation_family_for_result=self._aggregate_result_operation_family,
            slot_has_material=answer_slot_has_material,
        )

    def _align_lookup_results_with_dependency_projection(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        task_by_id = {
            str(task.get("task_id") or ""): dict(task)
            for task in (state.get("calc_subtasks") or [])
            if str(task.get("task_id") or "").strip()
        }
        projected_by_task: Dict[str, List[Dict[str, Any]]] = {}
        for operand in list(aggregate_projection.get("calculation_operands") or []):
            if not isinstance(operand, dict):
                continue
            source_ids = _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")])
            for source_id in source_ids:
                if not source_id.startswith("task_output:"):
                    continue
                task_id = source_id.split(":", 1)[1]
                if task_id:
                    projected_by_task.setdefault(task_id, []).append(dict(operand))
        def _projection_operand_matches_lookup(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
            if _operand_row_matches_requirement(candidate, operand):
                return True
            candidate_label = _normalise_spaces(
                str(candidate.get("matched_operand_label") or candidate.get("label") or "")
            )
            operand_label = _normalise_spaces(str(operand.get("label") or ""))
            if candidate_label and operand_label and candidate_label == operand_label:
                return True
            candidate_concept = _normalise_spaces(str(candidate.get("matched_operand_concept") or ""))
            operand_concept = _normalise_spaces(str(operand.get("concept") or ""))
            if candidate_concept and operand_concept and candidate_concept == operand_concept:
                return True
            return bool(candidate_label and _operand_text_match(candidate_label, operand))

        _slot_differs_from_operand = dependency_projection_slot_differs_from_operand
        _source_task_id_for_operand = source_task_id_for_dependency_operand
        _ratio_role_group = dependency_ratio_role_group
        _lookup_slot_match_score = dependency_lookup_slot_match_score

        def _lookup_source_for_arithmetic_slot(
            *,
            current_task_id: str,
            role: str,
            slot: Dict[str, Any],
            excluded_task_ids: Optional[set[str]] = None,
        ) -> tuple[str, Dict[str, Any]]:
            excluded = set(excluded_task_ids or set())
            best_task_id = ""
            best_slot: Dict[str, Any] = {}
            best_score = 0
            for lookup_task_id, lookup_slot in lookup_slots_by_task.items():
                if lookup_task_id == current_task_id or lookup_task_id in excluded:
                    continue
                score = _lookup_slot_match_score(lookup_slot, slot, role)
                if score > best_score:
                    best_task_id = lookup_task_id
                    best_slot = dict(lookup_slot)
                    best_score = score
            if best_score <= 0:
                return "", {}
            return best_task_id, best_slot

        lookup_slots_by_task = build_dependency_lookup_slots_by_task(
            ordered_results,
            task_by_id,
            operation_family_for_result=self._aggregate_result_operation_family,
            slot_has_material=answer_slot_has_material,
        )
        table_label_evidence_candidates = collect_table_label_evidence_candidates(ordered_results, state)
        _operand_from_source_slot = dependency_operand_from_source_slot
        _operand_from_answer_slot = dependency_operand_from_answer_slot
        _operand_rows_share_source_value = dependency_operand_rows_share_source_value

        def _operand_from_table_label_evidence(operand: Dict[str, Any]) -> Dict[str, Any]:
            return dependency_operand_from_table_label_evidence(
                operand,
                table_label_evidence_candidates,
                lookup_value_from_table_label_metadata=self._lookup_value_from_table_label_metadata,
                slot_has_material=answer_slot_has_material,
            )

        def _recalculate_row_from_source_slots(row: Dict[str, Any]) -> Dict[str, Any]:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
                return row
            if row.get("recovered_from_retrieved_ratio_context"):
                return row
            calculation_plan = dict(row.get("calculation_plan") or {})
            operands = [dict(item) for item in list(row.get("calculation_operands") or []) if isinstance(item, dict)]
            task_id = _normalise_spaces(str(row.get("task_id") or ""))
            active_subtask = {
                **dict(task_by_id.get(task_id) or {}),
                "task_id": task_id,
                "metric_family": row.get("metric_family") or (task_by_id.get(task_id) or {}).get("metric_family"),
                "metric_label": row.get("metric_label") or (task_by_id.get(task_id) or {}).get("metric_label"),
                "operation_family": operation_family,
            }
            required_operands = [
                dict(item)
                for item in list(active_subtask.get("required_operands") or [])
                if isinstance(item, dict) and bool(item.get("required", True))
            ]

            def _has_complete_direct_period_context_operands(rows: List[Dict[str, Any]]) -> bool:
                if operation_family not in {"difference", "growth_rate"} or not required_operands:
                    return False
                if not rows or _missing_required_operands(required_operands, rows):
                    return False
                if not _operand_rows_have_single_table_context(rows):
                    return False
                if _period_comparison_operand_rows_collapse_to_same_slot(rows):
                    return False
                for operand_row in rows:
                    source_ids = _clean_source_row_ids(
                        [operand_row.get("source_row_id"), operand_row.get("source_row_ids")]
                    )
                    if (
                        operand_row.get("dependency_resolved")
                        or _normalise_spaces(str(operand_row.get("source_task_id") or ""))
                        or any(source_id.startswith("task_output:") for source_id in source_ids)
                    ):
                        return False
                return True

            if _has_complete_direct_period_context_operands(operands):
                return row

            derived_from_slots = False
            if not operands:
                operands = derive_dependency_operands_from_source_task_slots(
                    row,
                    active_subtask=active_subtask,
                    operation_family=operation_family,
                    task_id=task_id,
                    lookup_slots_by_task=lookup_slots_by_task,
                    slot_has_material=answer_slot_has_material,
                    lookup_source_for_arithmetic_slot=_lookup_source_for_arithmetic_slot,
                    operand_from_source_slot=_operand_from_source_slot,
                    operand_can_use_source_slot=dependency_operand_can_use_source_slot,
                    ratio_role_group=_ratio_role_group,
                    source_task_id_for_operand=_source_task_id_for_operand,
                )
                derived_from_slots = bool(operands)
            if not operands:
                return row
            changed = derived_from_slots
            updated_operands, refreshed_any = refresh_dependency_operands_from_lookup_slots(
                operands,
                task_id=task_id,
                lookup_slots_by_task=lookup_slots_by_task,
                slot_has_material=answer_slot_has_material,
                lookup_source_for_arithmetic_slot=_lookup_source_for_arithmetic_slot,
                source_task_id_for_operand=_source_task_id_for_operand,
                slot_differs_from_operand=_slot_differs_from_operand,
                operand_can_use_source_slot=dependency_operand_can_use_source_slot,
                operand_from_source_slot=_operand_from_source_slot,
            )
            changed = changed or refreshed_any
            updated_operands = dedupe_dependency_operands_by_id(updated_operands)
            if operation_family == "ratio":
                updated_operands, filled_any = fill_missing_ratio_dependency_operands(
                    updated_operands,
                    ordered_results=ordered_results,
                    active_subtask=active_subtask,
                    task_id=task_id,
                    operation_family_for_result=self._aggregate_result_operation_family,
                    lookup_source_for_arithmetic_slot=_lookup_source_for_arithmetic_slot,
                    slot_has_material=answer_slot_has_material,
                    operand_can_use_source_slot=dependency_operand_can_use_source_slot,
                    operand_from_source_slot=_operand_from_source_slot,
                    operand_from_table_label_evidence=_operand_from_table_label_evidence,
                    operand_rows_share_source_value=_operand_rows_share_source_value,
                    ratio_role_group=_ratio_role_group,
                    source_task_id_for_operand=_source_task_id_for_operand,
                )
                changed = changed or filled_any
                if operation_family == "ratio" and _ratio_operand_rows_collapse_to_same_slot(updated_operands):
                    return row
            if not changed:
                return row

            plan_disposition = classify_dependency_recalculation_plan(calculation_plan)
            if plan_disposition == "unsupported_mode":
                return row
            raw_deterministic_plan: Dict[str, Any] = {}
            if plan_disposition == "rebuild":
                raw_deterministic_plan = self._build_deterministic_operation_plan(
                    state,
                    updated_operands,
                    active_subtask=active_subtask,
                ) or {}
            calculation_plan = rebuild_dependency_calculation_plan(
                calculation_plan,
                raw_deterministic_plan=raw_deterministic_plan,
                active_subtask=active_subtask,
                updated_operands=updated_operands,
                operation_family=operation_family,
                calculation_result=dict(row.get("calculation_result") or {}),
            )
            if not calculation_plan:
                return row
            recalculation_projection = self._run_calculation_candidate_input(
                _CalculationCandidateInput(
                    calculation_operands=tuple(dict(item) for item in updated_operands),
                    calculation_plan=dict(calculation_plan),
                    active_subtask=dict(active_subtask),
                    query=str(active_subtask.get("query") or state["query"]),
                    evidence_items=tuple(state.get("evidence_items") or []),
                    runtime_evidence=tuple(state.get("runtime_evidence") or []),
                )
            ).projection
            candidate_projection = resolve_dependency_recalculation_candidate_projection(
                DependencyRecalculationCandidateProjectionInput(
                    calculation_operands=recalculation_projection.calculation_operands,
                    calculation_plan=recalculation_projection.calculation_plan,
                    calculation_result=recalculation_projection.calculation_result,
                )
            )
            if not candidate_projection.candidate_ready:
                return row
            recalculated_trace = candidate_projection.recalculated_trace
            recalculated_result = candidate_projection.recalculated_result
            if operation_family == "ratio" and calculation_rendering.ratio_query_requests_absolute_magnitude(str(state.get("query") or "")):
                recalculated_result = apply_absolute_ratio_magnitude_if_requested(
                    recalculated_result,
                    format_calculation_value=calculation_rendering.format_calculation_value,
                )
            if operation_family == "ratio":
                artifact_row = self._preferred_ratio_artifact_row_for_conflicting_recalculation(
                    state,
                    active_subtask,
                    recalculated_result,
                )
                if artifact_row:
                    return artifact_row
            if operation_family == "ratio":
                formatted_answer = self._compact_ratio_answer(
                    state,
                    recalculated_result,
                    active_subtask=active_subtask,
                    calculation_operands=updated_operands,
                )
            else:
                formatted_answer = _normalise_spaces(
                    str(recalculated_result.get("formatted_result") or recalculated_result.get("rendered_value") or "")
            )
            return finalize_dependency_recalculated_row(
                DependencyRecalculatedRowFinalizationInput(
                    current_row=row,
                    recalculated_trace=recalculated_trace,
                    updated_operands=updated_operands,
                    fallback_calculation_plan=calculation_plan,
                    recalculated_result=recalculated_result,
                    formatted_answer=formatted_answer,
                )
            ).selected_row

        aligned_results: List[Dict[str, Any]] = []
        changed_any = False
        for row in ordered_results:
            row = _recalculate_row_from_source_slots(dict(row))
            if row.get("aligned_from_source_task_slots"):
                changed_any = True
            task_id = str(row.get("task_id") or "").strip()
            task = task_by_id.get(task_id) or {}
            operation_family = _normalise_spaces(
                str(
                    row.get("operation_family")
                    or task.get("operation_family")
                    or self._aggregate_result_operation_family(row)
                    or ""
                )
            ).lower()
            if operation_family not in {"lookup", "single_value"}:
                aligned_results.append(row)
                continue
            aligned_row, primary_slot, row_changed = realign_lookup_row_from_dependency_projection(
                row,
                task=task,
                projected_operands=list(projected_by_task.get(task_id, [])),
                slot_has_material=answer_slot_has_material,
                projection_operand_matches_lookup=_projection_operand_matches_lookup,
                slot_differs_from_operand=_slot_differs_from_operand,
                build_operand_value_slot=financial_answer_slots.build_operand_value_slot,
            )
            aligned_results.append(aligned_row)
            if row_changed:
                lookup_slots_by_task[task_id] = primary_slot
                changed_any = True
        return aligned_results if changed_any else ordered_results

    def _preferred_complete_numeric_answer(
        self,
        ordered_results: List[Dict[str, Any]],
        query: str = "",
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        query_terms = {
            token.lower()
            for token in narrative_context_terms(str(query or ""))
            if len(token) >= 2
        }

        def _label_overlap_score(label_text: str) -> tuple[int, int]:
            normalized_label = _normalise_spaces(label_text)
            label_terms = {
                token.lower()
                for token in narrative_context_terms(normalized_label)
                if len(token) >= 2
            }
            overlap = {
                label_term
                for label_term in label_terms
                if any(
                    query_term == label_term
                    or (
                        query_term in label_term
                        and len(query_term) / max(len(label_term), 1) >= 0.8
                    )
                    or (
                        label_term in query_term
                        and len(label_term) / max(len(query_term), 1) >= 0.8
                    )
                    for query_term in query_terms
                )
            }
            return len(overlap), len(normalized_label)

        def _row_focus_text(row: Dict[str, Any], calculation_result: Dict[str, Any]) -> str:
            parts = [
                str(row.get("metric_label") or ""),
                str(row.get("query") or ""),
            ]
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            for container_key in ("components_by_group", "components_by_role"):
                for entries in dict(answer_slots.get(container_key) or {}).values():
                    for slot in list(entries or []):
                        if not isinstance(slot, dict):
                            continue
                        parts.extend([str(slot.get("label") or ""), str(slot.get("concept") or "")])
            primary_slot = dict(answer_slots.get("primary_value") or {})
            parts.extend([str(primary_slot.get("label") or ""), str(primary_slot.get("concept") or "")])
            return _normalise_spaces(" ".join(part for part in parts if part))

        def _append_ranked_answer(row: Dict[str, Any], answer: str) -> None:
            calculation_result = dict(row.get("calculation_result") or {})
            focus_text = _row_focus_text(row, calculation_result)
            score, label_len = _label_overlap_score(focus_text)
            answer_parts.append((score, label_len, answer))

        source_slot_by_task_id = self._aggregate_dependency_source_slot_by_task_id(ordered_results)
        answer_parts: List[tuple[int, int, str]] = []
        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if operation_family == "ratio" and status != "ok":
                answer = self._ratio_answer_from_dependency_source_slots(row, source_slot_by_task_id, query=query)
                if answer:
                    _append_ranked_answer(row, answer)
                continue
            if status != "ok" or material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            if operation_family == "ratio" and financial_answer_slots.ratio_components_are_complete(calculation_result):
                components_by_group = dict((calculation_result.get("answer_slots") or {}).get("components_by_group") or {})
                has_multi_component_side = any(
                    len([item for item in list(components_by_group.get(group) or []) if isinstance(item, dict)]) > 1
                    for group in ("numerator", "denominator")
                )
                if has_multi_component_side or row.get("recovered_from_retrieved_ratio_context"):
                    answer = self._compact_ratio_answer(
                        {
                            "active_subtask": {
                                "metric_label": row.get("metric_label") or calculation_result.get("metric_label") or "",
                            },
                            "resolved_calculation_trace": {
                                "calculation_operands": list(row.get("calculation_operands") or []),
                                "calculation_plan": dict(row.get("calculation_plan") or {}),
                                "calculation_result": calculation_result,
                            },
                        },
                        calculation_result,
                    )
                    if answer:
                        _append_ranked_answer(row, answer)
                        continue
            if aggregate_result_dependency_coherence_ranks(row, source_slot_by_task_id)[0] == 0:
                if operation_family == "ratio":
                    answer = self._ratio_answer_from_dependency_source_slots(row, source_slot_by_task_id, query=query)
                    if answer:
                        _append_ranked_answer(row, answer)
                continue
            if operation_family == "growth_rate":
                if growth_row_has_conflicting_periods(row):
                    continue
                answer = compose_complete_growth_numeric_answer(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if answer:
                    _append_ranked_answer(row, answer)
                    continue
            if operation_family == "ratio" and financial_answer_slots.ratio_components_are_complete(calculation_result):
                answer = self._compact_ratio_answer(
                    {
                        "active_subtask": {
                            "metric_label": row.get("metric_label") or calculation_result.get("metric_label") or "",
                        },
                        "resolved_calculation_trace": {
                            "calculation_operands": list(row.get("calculation_operands") or []),
                            "calculation_plan": dict(row.get("calculation_plan") or {}),
                            "calculation_result": calculation_result,
                        },
                    },
                    calculation_result,
                )
                if answer:
                    _append_ranked_answer(row, answer)
                    continue
            answer = _normalise_spaces(
                str(
                    calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or row.get("answer")
                    or ""
                )
            )
            if answer:
                _append_ranked_answer(row, answer)
        if query_terms and answer_parts:
            best_score = max(score for score, _label_len, _answer in answer_parts)
            if best_score > 0:
                answer_parts = [item for item in answer_parts if item[0] == best_score]
        ordered_answers = [answer for _score, _label_len, answer in answer_parts]
        return _normalise_spaces(" ".join(dict.fromkeys(part for part in ordered_answers if part)))

    def _sync_ratio_result_displays_in_ordered_results(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        updated_results: List[Dict[str, Any]] = []
        changed_any = False
        for row in list(ordered_results or []):
            row_copy = dict(row)
            if self._aggregate_result_operation_family(row_copy) != "ratio":
                updated_results.append(row_copy)
                continue
            calculation_result = dict(row_copy.get("calculation_result") or {})
            if not calculation_result:
                updated_results.append(row_copy)
                continue
            before_rendered = _normalise_spaces(
                str(
                    calculation_result.get("rendered_value")
                    or (dict(calculation_result.get("answer_slots") or {}).get("primary_value") or {}).get("rendered_value")
                    or ""
                )
            )
            synced_result = financial_answer_slots.synchronize_ratio_result_display(
                financial_answer_slots.RatioResultDisplaySyncInput(
                    calculation_result=calculation_result,
                )
            ).calculation_result
            after_rendered = _normalise_spaces(
                str(
                    synced_result.get("rendered_value")
                    or (dict(synced_result.get("answer_slots") or {}).get("primary_value") or {}).get("rendered_value")
                    or ""
                )
            )
            if after_rendered and after_rendered != before_rendered:
                synced_answer = self._compact_ratio_answer(
                    {
                        "active_subtask": {
                            "metric_label": row_copy.get("metric_label")
                            or synced_result.get("metric_label")
                            or (synced_result.get("answer_slots") or {}).get("metric_label")
                            or "",
                        },
                        "resolved_calculation_trace": {
                            "calculation_operands": list(row_copy.get("calculation_operands") or []),
                            "calculation_plan": dict(row_copy.get("calculation_plan") or {}),
                            "calculation_result": synced_result,
                        },
                    },
                    synced_result,
                )
                row_copy["calculation_result"] = synced_result
                row_copy["rendered_value"] = after_rendered
                if synced_answer:
                    row_copy["answer"] = synced_answer
                    synced_result["formatted_result"] = synced_answer
                changed_any = True
            updated_results.append(row_copy)
        return updated_results if changed_any else ordered_results

    def _complete_numeric_answer_can_replace_final(
        self,
        numeric_answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        if not _normalise_spaces(str(numeric_answer or "")):
            return False
        if not self._unresolved_structured_numeric_gap(ordered_results):
            return True
        return self._answer_matches_supported_aggregate_subtask(numeric_answer, ordered_results)

    def _complete_numeric_projection_replacement_answer(
        self,
        *,
        final_answer: str,
        ordered_results: List[Dict[str, Any]],
        query: str = "",
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        operation_families = {
            self._aggregate_result_operation_family(row)
            for row in ordered_results
            if isinstance(row, dict)
        }
        if "growth_rate" in operation_families:
            return ""
        if "ratio" not in operation_families:
            return ""
        numeric_answer = self._preferred_complete_numeric_answer(
            ordered_results,
            query=query,
            evidence_items=evidence_items,
        )
        if not numeric_answer:
            return ""
        if _normalise_spaces(numeric_answer) == _normalise_spaces(final_answer):
            return ""
        if self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results):
            return ""
        if self._answer_satisfies_growth_narrative_intent(
            query=query,
            answer=final_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items or [],
        ):
            return ""
        if not self._complete_numeric_answer_can_replace_final(numeric_answer, ordered_results):
            return ""
        if self._answer_covers_numeric_projection(final_answer, ordered_results):
            return ""
        return numeric_answer

    def _numeric_projection_coverage_targets(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[str]:
        targets: List[str] = []
        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            if operation_family == "ratio":
                answer_slots = dict(calculation_result.get("answer_slots") or {})
                components_by_group = dict(answer_slots.get("components_by_group") or {})
                numerator_slots = [
                    item for item in list(components_by_group.get("numerator") or []) if isinstance(item, dict)
                ]
                denominator_slots = [
                    item for item in list(components_by_group.get("denominator") or []) if isinstance(item, dict)
                ]
                if (
                    financial_answer_slots.ratio_components_are_complete(calculation_result)
                    and numerator_slots
                    and denominator_slots
                    and (len(numerator_slots) > 1 or len(denominator_slots) > 1)
                ):
                    target = self._compact_ratio_answer(
                        {
                            "active_subtask": {
                                "metric_label": row.get("metric_label")
                                or calculation_result.get("metric_label")
                                or "",
                            },
                            "resolved_calculation_trace": {
                                "calculation_operands": list(row.get("calculation_operands") or []),
                                "calculation_plan": dict(row.get("calculation_plan") or {}),
                                "calculation_result": calculation_result,
                            },
                        },
                        calculation_result,
                    )
                else:
                    target = _normalise_spaces(
                        str(
                            calculation_result.get("rendered_value")
                            or (dict((calculation_result.get("answer_slots") or {}).get("primary_value") or {})).get(
                                "rendered_value"
                            )
                            or ""
                        )
                    )
                if target:
                    targets.append(target)
                continue
            if operation_family == "growth_rate":
                answer_slots = dict(calculation_result.get("answer_slots") or {})
                target_parts = []
                for slot_name in ("primary_value", "current_value"):
                    slot = dict(answer_slots.get(slot_name) or {})
                    rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
                    if rendered_value:
                        target_parts.append(rendered_value)
                target = _normalise_spaces(" ".join(dict.fromkeys(target_parts)))
                if target:
                    targets.append(target)
                    continue
            target = _normalise_spaces(
                str(
                    calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or row.get("answer")
                    or ""
                )
            )
            if target:
                targets.append(target)
        return list(dict.fromkeys(target for target in targets if target))

    def _answer_covers_numeric_projection(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        targets = self._numeric_projection_coverage_targets(ordered_results)
        if not targets:
            return True
        return all(answer_covers_numeric_answer(answer, target) for target in targets)

    def _preferred_existing_aggregate_artifact_candidate(
        self,
        artifacts: List[Dict[str, Any]],
        ordered_results: List[Dict[str, Any]],
        current_answer: str,
    ) -> Dict[str, Any]:
        targets = self._numeric_projection_coverage_targets(ordered_results)
        if not targets:
            return {}
        missing_markers = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ())
            if str(item)
        )

        def _score(answer: str) -> tuple[int, int, int, int]:
            normalized_answer = _normalise_spaces(str(answer or ""))
            if not normalized_answer:
                return (0, 0, 0, 0)
            covered_count = sum(
                1 for target in targets if answer_covers_numeric_answer(normalized_answer, target)
            )
            complete = int(covered_count == len(targets))
            no_missing_marker = int(
                not any(marker and marker in normalized_answer for marker in missing_markers)
            )
            numeric_count = len(extract_numeric_surface_candidates(normalized_answer))
            return (complete, covered_count, no_missing_marker, numeric_count)

        current_score = _score(current_answer)
        if current_score[0] and current_score[2]:
            return {}

        best_candidate: Dict[str, Any] = {}
        best_score = current_score
        for artifact in artifacts or []:
            if not isinstance(artifact, dict):
                continue
            if str(artifact.get("task_id") or "") != "aggregate":
                continue
            if str(artifact.get("kind") or "") != ArtifactKind.AGGREGATED_ANSWER.value:
                continue
            if _normalise_spaces(str(artifact.get("status") or "")).lower() != "ok":
                continue
            payload = dict(artifact.get("payload") or {})
            answer = _normalise_spaces(
                str(payload.get("final_answer") or payload.get("answer") or artifact.get("summary") or "")
            )
            if not answer or answer == _normalise_spaces(str(current_answer or "")):
                continue
            score = _score(answer)
            if score <= best_score or not score[0]:
                continue
            best_score = score
            best_candidate = package_aggregate_answer_candidate(
                AggregateAnswerCandidatePackagingInput(
                    answer=answer,
                    selected_claim_ids=artifact.get("evidence_refs") or [],
                    sync_projection=True,
                    sync_rendered_for_aggregate=True,
                    status_ok=True,
                )
            ).candidate
        return best_candidate

    def _final_growth_answer_without_untraced_numeric_sentences(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        sentences = _split_narrative_sentences(answer_text)
        if len(sentences) < 2:
            return answer_text

        trace_surfaces: List[str] = []
        required_values: List[str] = []
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if growth_row_has_conflicting_periods(row):
                continue
            complete_answer = compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if complete_answer:
                trace_surfaces.append(complete_answer)
            required_values.extend(
                growth_required_display_values(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
            )
        required_values = list(dict.fromkeys(value for value in required_values if value))
        trace_candidates = extract_numeric_surface_candidates(
            _normalise_spaces(" ".join([*trace_surfaces, *required_values]))
        )
        if not trace_candidates:
            return answer_text

        def _candidate_is_trace_supported(candidate: Dict[str, Any]) -> bool:
            return any(
                numeric_surface_candidates_equivalent(candidate, trace_candidate)
                for trace_candidate in trace_candidates
            )

        kept_sentences: List[str] = []
        removed_numeric_sentence = False
        for sentence in sentences:
            cleaned = _normalise_spaces(sentence)
            if not cleaned:
                continue
            sentence_candidates = extract_numeric_surface_candidates(cleaned)
            if not sentence_candidates:
                kept_sentences.append(cleaned)
                continue
            if all(_candidate_is_trace_supported(candidate) for candidate in sentence_candidates):
                kept_sentences.append(cleaned)
                continue
            if any(value and value in cleaned for value in required_values):
                cleaned = strip_untraced_numeric_material_from_growth_narrative_sentence(
                    cleaned,
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if cleaned:
                    kept_sentences.append(cleaned)
                else:
                    removed_numeric_sentence = True
                continue
            removed_numeric_sentence = True

        if not removed_numeric_sentence:
            return answer_text
        candidate_answer = ensure_complete_growth_numeric_answer(
            _normalise_spaces(" ".join(kept_sentences)),
            ordered_results,
            evidence_items=evidence_items,
        )
        if not candidate_answer:
            return answer_text
        if growth_answer_has_untraced_numeric_material(
            candidate_answer,
            ordered_results,
            evidence_items=None,
        ):
            return answer_text
        if (
            self._answer_covers_numeric_projection(candidate_answer, ordered_results)
            or self._answer_satisfies_growth_narrative_intent(
                query=query,
                answer=candidate_answer,
                ordered_results=ordered_results,
                evidence_items=evidence_items or [],
            )
        ):
            return candidate_answer
        return answer_text

    def _enforce_source_stated_growth_answer_contract(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return answer_text
        for row in reversed(ordered_results):
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if growth_row_has_conflicting_periods(row):
                continue
            if not growth_uses_source_stated_result(row):
                continue
            complete_answer = compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if not complete_answer:
                continue
            required_values = growth_required_display_values(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
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

    def _supported_aggregate_subtask_answer(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            if row_is_narrative_summary(row):
                continue
            if self._aggregate_result_operation_family(row) != "aggregate_subtasks":
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status and status not in {"ok", "ready"}:
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            row_answer = _normalise_spaces(
                str(
                    row.get("answer")
                    or calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or ""
                )
            )
            if not row_answer or not re.search(r"\d", row_answer):
                continue
            nested_rows = [
                item
                for item in [
                    *list(calculation_result.get("subtask_results") or []),
                    *list((calculation_result.get("answer_slots") or {}).get("subtask_results") or []),
                ]
                if isinstance(item, dict)
            ]
            if nested_rows and not self._answer_covers_numeric_projection(row_answer, nested_rows):
                continue
            return row_answer
        return ""

    def _answer_matches_supported_aggregate_subtask(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not re.search(r"\d", answer_text):
            return False
        row_answer = self._supported_aggregate_subtask_answer(ordered_results)
        if not row_answer or not (answer_text == row_answer or row_answer in answer_text):
            return False
        if (
            has_strong_growth_trace_for_answer_refresh(ordered_results)
            and growth_answer_has_untraced_numeric_material(answer_text, ordered_results)
        ):
            return False
        return True

    def _preferred_conflicting_growth_narrative_answer(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        for row in ordered_results:
            if not row_is_narrative_summary(row):
                continue
            row_answer = _normalise_spaces(
                str(
                    row.get("answer")
                    or (row.get("calculation_result") or {}).get("formatted_result")
                    or (row.get("calculation_result") or {}).get("rendered_value")
                    or ""
                )
            )
            if not row_answer or any(marker and marker in row_answer for marker in missing_markers):
                continue
            if not narrative_summary_conflicts_with_growth_trace(row_answer, ordered_results, evidence_items):
                continue
            clean_candidates = self._growth_narrative_sentence_candidates(
                query=query,
                ordered_results=[row],
                evidence_items=evidence_items or [],
            )
            if clean_candidates:
                _score, row_answer, candidate_claim_ids = clean_candidates[0]
                selected_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in (candidate_claim_ids or [])
                    if str(claim_id).strip()
                ]
            elif _narrative_sentence_looks_table_noisy(row_answer):
                continue
            else:
                selected_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in (row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ]
            return {
                "answer": row_answer,
                "selected_claim_ids": selected_claim_ids,
                "operation_family": self._aggregate_result_operation_family(row),
            }
        return {}

    def _uncovered_supported_growth_narrative_candidate(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        answer_lower = _normalise_spaces(str(answer or "")).lower()
        driver_groups = self._narrative_driver_groups(query)

        def _driver_group_already_covered(sentence: str) -> bool:
            sentence_lower = _normalise_spaces(str(sentence or "")).lower()
            if not sentence_lower or not answer_lower:
                return False
            for group in driver_groups:
                if group.get("query_focus"):
                    continue
                variants = [
                    _normalise_spaces(str(variant or "")).lower()
                    for variant in (group.get("variants") or [])
                    if _normalise_spaces(str(variant or ""))
                ]
                if not variants or not any(variant in sentence_lower for variant in variants):
                    continue
                if any(variant in answer_lower for variant in variants):
                    return True
            return False

        for _score, sentence, claim_ids in self._growth_narrative_sentence_candidates(
            query=query,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            candidate_sentence = _normalise_spaces(sentence)
            candidate_claim_ids = [str(claim_id).strip() for claim_id in (claim_ids or []) if str(claim_id).strip()]
            if (
                not candidate_claim_ids
                or not candidate_sentence
                or answer_covers_narrative_context(answer, candidate_sentence)
                or _driver_group_already_covered(candidate_sentence)
            ):
                continue
            cleaned = strip_untraced_numeric_material_from_growth_narrative_sentence(
                candidate_sentence,
                ordered_results,
                evidence_items=evidence_items,
            )
            if (
                not cleaned
                or not sentence_has_growth_explanatory_signal(cleaned)
                or answer_covers_narrative_context(answer, cleaned)
                or growth_answer_has_untraced_numeric_material(cleaned, ordered_results, evidence_items)
            ):
                continue
            return {"sentence": cleaned, "selected_claim_ids": candidate_claim_ids}
        return {}

    def _refresh_numeric_answer_preserving_narrative_context(
        self,
        *,
        query: str,
        current_answer: str,
        numeric_answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        numeric_text = _normalise_spaces(str(numeric_answer or ""))
        current_answer_text = _normalise_spaces(str(current_answer or ""))
        if not any(row_is_narrative_summary(row) for row in ordered_results) and not (
            current_answer_text and query_requests_explanatory_context(query)
        ):
            return {"answer": numeric_text, "selected_claim_ids": []}

        query_text = _normalise_spaces(str(query or ""))
        explanatory_markers = tuple(
            str(item)
            for item in (
                tuple(CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
                + tuple(CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ())
                + tuple(CALCULATION_NARRATIVE_POLICY.get("explanatory_markers") or ())
            )
            if str(item)
        )

        def _has_explanatory_signal(sentence: str) -> bool:
            sentence_text = _normalise_spaces(str(sentence or ""))
            return bool(sentence_text) and any(marker in sentence_text for marker in explanatory_markers)

        if (
            query_requests_explanatory_context(query_text)
            and answer_reuses_numeric_narrative_summary_text(current_answer_text, ordered_results)
            and _has_explanatory_signal(current_answer_text)
            and re.search(str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"$^"), current_answer_text)
        ):
            return {"answer": current_answer_text, "selected_claim_ids": []}

        conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        if conflicting_narrative:
            conflicting_answer = _normalise_spaces(str(conflicting_narrative.get("answer") or ""))
            if growth_narrative_numeric_incompatible_with_trace(
                narrative_answer=conflicting_answer,
                numeric_answer=numeric_text,
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            ):
                if str(conflicting_narrative.get("operation_family") or "") == "aggregate_subtasks":
                    return conflicting_narrative
            conflicting_parts = [
                sanitized_sentence
                for sentence in (_split_narrative_sentences(conflicting_answer) or [conflicting_answer])
                for sanitized_sentence in [
                    strip_untraced_numeric_material_from_growth_narrative_sentence(
                        sentence,
                        ordered_results,
                        evidence_items=evidence_items,
                    )
                ]
                if (
                    sanitized_sentence
                    and sanitized_sentence not in numeric_text
                    and _has_explanatory_signal(sanitized_sentence)
                )
            ]
            if conflicting_parts:
                combined_answer = ensure_complete_growth_numeric_answer(
                    _normalise_spaces(" ".join([numeric_text, *conflicting_parts])),
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if not growth_answer_has_untraced_numeric_material(
                    combined_answer,
                    ordered_results,
                    evidence_items,
                ) and self._answer_satisfies_growth_narrative_intent(
                    query=query_text,
                    answer=combined_answer,
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                ):
                    return {
                        "answer": combined_answer,
                        "selected_claim_ids": [
                            str(claim_id).strip()
                            for claim_id in (conflicting_narrative.get("selected_claim_ids") or [])
                            if str(claim_id).strip()
                        ],
                    }

        candidate_answer = ensure_complete_growth_numeric_answer(
            current_answer,
            ordered_results,
            evidence_items=evidence_items,
        )
        candidate_answer = self._prune_irrelevant_growth_narrative_sentences(
            query=query_text,
            answer=candidate_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        if (
            not growth_answer_has_untraced_numeric_material(candidate_answer, ordered_results, evidence_items)
            and self._answer_satisfies_growth_narrative_intent(
                query=query_text,
                answer=candidate_answer,
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
        ):
            return {"answer": candidate_answer, "selected_claim_ids": []}

        current_context_parts: List[str] = []
        narrative_markers = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
        )
        supported_context_candidates = self._supported_growth_narrative_candidate_sentences(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )

        def _matches_supported_growth_context(sentence: str) -> bool:
            if not supported_context_candidates:
                return True
            return any(
                answer_covers_narrative_context(sentence, candidate)
                or answer_covers_narrative_context(candidate, sentence)
                for candidate in supported_context_candidates
            )

        for sentence in _split_narrative_sentences(candidate_answer) or [candidate_answer]:
            cleaned_sentence = _normalise_spaces(sentence)
            if not cleaned_sentence or cleaned_sentence in numeric_text:
                continue
            if extract_numeric_surface_candidates(cleaned_sentence):
                continue
            if not (
                _has_explanatory_signal(cleaned_sentence)
                or query_requests_explanatory_context(query_text)
            ):
                continue
            if _narrative_sentence_looks_table_noisy(cleaned_sentence):
                continue
            if _narrative_sentence_looks_abbreviated_fragment(cleaned_sentence, narrative_markers):
                continue
            if not _matches_supported_growth_context(cleaned_sentence):
                continue
            current_context_parts.append(cleaned_sentence)
        current_context_answer = _normalise_spaces(" ".join([numeric_text, *current_context_parts]))
        if current_context_parts:
            return {
                "answer": current_context_answer,
                "selected_claim_ids": [],
            }

        max_driver_sentences = int(CALCULATION_NARRATIVE_POLICY.get("max_growth_driver_sentences") or 4)
        row_narrative_parts: List[str] = []
        row_selected_claim_ids: List[str] = []
        for row in ordered_results:
            if not row_is_narrative_summary(row):
                continue
            row_answer = _normalise_spaces(
                str(
                    row.get("answer")
                    or (row.get("calculation_result") or {}).get("formatted_result")
                    or (row.get("calculation_result") or {}).get("rendered_value")
                    or ""
                )
            )
            if not row_answer:
                continue
            row_claim_ids = [
                str(claim_id).strip()
                for claim_id in (row.get("selected_claim_ids") or [])
                if str(claim_id).strip()
            ]
            for row_sentence in _split_narrative_sentences(row_answer) or [row_answer]:
                candidate_sentence = _normalise_spaces(row_sentence)
                if not candidate_sentence or candidate_sentence in numeric_text:
                    continue
                if extract_numeric_surface_candidates(candidate_sentence) and not _has_explanatory_signal(
                    candidate_sentence
                ):
                    continue
                sanitized_sentence = strip_untraced_numeric_material_from_growth_narrative_sentence(
                    candidate_sentence,
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if not sanitized_sentence or not _has_explanatory_signal(sanitized_sentence):
                    continue
                if sanitized_sentence in row_narrative_parts:
                    continue
                row_narrative_parts.append(sanitized_sentence)
                row_selected_claim_ids.extend(row_claim_ids)
                if len(row_narrative_parts) >= max_driver_sentences:
                    break
            if row_narrative_parts:
                row_combined_answer = ensure_complete_growth_numeric_answer(
                    _normalise_spaces(" ".join([numeric_text, *row_narrative_parts])),
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if not growth_answer_has_untraced_numeric_material(
                    row_combined_answer,
                    ordered_results,
                    evidence_items,
                ):
                    return {
                        "answer": row_combined_answer,
                        "selected_claim_ids": list(dict.fromkeys(row_selected_claim_ids)),
                    }

        composed = self._compose_growth_narrative_answer(
            query=query_text,
            ordered_results=ordered_results,
            existing_answer=candidate_answer or numeric_text,
            evidence_items=evidence_items,
        )
        composed_answer = _normalise_spaces(str((composed or {}).get("compressed_answer") or ""))
        if growth_answer_has_untraced_numeric_material(
            composed_answer,
            ordered_results,
            evidence_items,
        ):
            composed_answer = ensure_complete_growth_numeric_answer(
                composed_answer,
                ordered_results,
                evidence_items=evidence_items,
            )
        if composed_answer and self._answer_satisfies_growth_narrative_intent(
            query=query_text,
            answer=composed_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ) and not growth_answer_has_untraced_numeric_material(
            composed_answer,
            ordered_results,
            evidence_items,
        ):
            return {
                "answer": composed_answer,
                "selected_claim_ids": [
                    str(claim_id).strip()
                    for claim_id in ((composed or {}).get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ],
            }

        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        narrative_parts: List[str] = []
        selected_claim_ids: List[str] = []
        sanitized_narrative_parts: List[tuple[str, List[str]]] = []
        for _score, sentence, claim_ids in self._growth_narrative_sentence_candidates(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            candidate_sentence = _normalise_spaces(sentence)
            if not candidate_sentence or candidate_sentence in numeric_text:
                continue
            if extract_numeric_surface_candidates(candidate_sentence) and not _has_explanatory_signal(
                candidate_sentence
            ):
                continue
            sanitized_sentence = strip_untraced_numeric_material_from_growth_narrative_sentence(
                candidate_sentence,
                ordered_results,
                evidence_items=evidence_items,
            )
            if not sanitized_sentence:
                continue
            if sanitized_sentence != candidate_sentence:
                sanitized_narrative_parts.append(
                    (
                        sanitized_sentence,
                        [
                            str(claim_id).strip()
                            for claim_id in (claim_ids or [])
                            if str(claim_id).strip()
                        ],
                    )
                )
                continue
            candidate_sentence = sanitized_sentence
            narrative_parts.append(candidate_sentence)
            selected_claim_ids.extend(str(claim_id).strip() for claim_id in (claim_ids or []) if str(claim_id).strip())
            break
        if not narrative_parts and sanitized_narrative_parts:
            candidate_sentence, claim_ids = sanitized_narrative_parts[0]
            narrative_parts.append(candidate_sentence)
            selected_claim_ids.extend(claim_ids)
        if not narrative_parts:
            sanitized_row_parts: List[tuple[str, List[str]]] = []
            for row in ordered_results:
                if not row_is_narrative_summary(row):
                    continue
                row_answer = _normalise_spaces(
                    str(
                        row.get("answer")
                        or (row.get("calculation_result") or {}).get("formatted_result")
                        or (row.get("calculation_result") or {}).get("rendered_value")
                        or ""
                    )
                )
                if not row_answer or any(marker and marker in row_answer for marker in missing_markers):
                    continue
                if row_answer in numeric_text:
                    continue
                row_claim_ids = [
                    str(claim_id).strip()
                    for claim_id in (row.get("selected_claim_ids") or [])
                    if str(claim_id).strip()
                ]
                for row_sentence in _split_narrative_sentences(row_answer) or [row_answer]:
                    candidate_sentence = _normalise_spaces(row_sentence)
                    if not candidate_sentence or candidate_sentence in numeric_text:
                        continue
                    if extract_numeric_surface_candidates(candidate_sentence) and not _has_explanatory_signal(
                        candidate_sentence
                    ):
                        continue
                    sanitized_sentence = strip_untraced_numeric_material_from_growth_narrative_sentence(
                        candidate_sentence,
                        ordered_results,
                        evidence_items=evidence_items,
                    )
                    if not sanitized_sentence:
                        continue
                    if sanitized_sentence != candidate_sentence:
                        sanitized_row_parts.append((sanitized_sentence, row_claim_ids))
                        continue
                    narrative_parts.append(sanitized_sentence)
                    selected_claim_ids.extend(row_claim_ids)
                    break
                if narrative_parts:
                    break
            if not narrative_parts and sanitized_row_parts:
                candidate_sentence, row_claim_ids = sanitized_row_parts[0]
                narrative_parts.append(candidate_sentence)
                selected_claim_ids.extend(row_claim_ids)

        if narrative_parts:
            raw_combined_answer = _normalise_spaces(" ".join([numeric_text, *narrative_parts]))
            combined_answer = ensure_complete_growth_numeric_answer(
                raw_combined_answer,
                ordered_results,
                evidence_items=evidence_items,
            )
            for candidate_combined_answer in (raw_combined_answer, combined_answer):
                if not candidate_combined_answer:
                    continue
                if growth_answer_has_untraced_numeric_material(
                    candidate_combined_answer,
                    ordered_results,
                    evidence_items,
                ):
                    continue
                contains_narrative_part = any(
                    part and part in candidate_combined_answer
                    for part in narrative_parts
                )
                if self._answer_satisfies_growth_narrative_intent(
                    query=query_text,
                    answer=candidate_combined_answer,
                    ordered_results=ordered_results,
                    evidence_items=evidence_items,
                ) or (
                    contains_narrative_part
                    and any(_has_explanatory_signal(part) for part in narrative_parts)
                ):
                    return {
                        "answer": candidate_combined_answer,
                        "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
                    }
            if query_requests_explanatory_context(query_text):
                if growth_answer_has_untraced_numeric_material(
                    combined_answer,
                    ordered_results,
                    evidence_items,
                ):
                    clean_numeric = ensure_complete_growth_numeric_answer(
                        numeric_text,
                        ordered_results,
                        evidence_items=evidence_items,
                    )
                    return {"answer": clean_numeric or numeric_text, "selected_claim_ids": []}
                return {
                    "answer": combined_answer,
                    "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
                }

        if growth_answer_has_untraced_numeric_material(numeric_text, ordered_results, evidence_items):
            clean_numeric = ensure_complete_growth_numeric_answer(
                numeric_text,
                ordered_results,
                evidence_items=evidence_items,
            )
            return {"answer": clean_numeric or candidate_answer or numeric_text, "selected_claim_ids": []}
        return {"answer": numeric_text, "selected_claim_ids": []}

    def _preferred_aggregate_fallback_answer(
        self,
        ordered_results: List[Dict[str, Any]],
        default_answer: str,
    ) -> str:
        if self._unresolved_structured_numeric_gap(ordered_results):
            safe_answer = safe_partial_answer_for_numeric_gap(ordered_results)
            return safe_answer

        supported_aggregate_answer = self._supported_aggregate_subtask_answer(ordered_results)
        if supported_aggregate_answer:
            return supported_aggregate_answer

        conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query="",
            ordered_results=ordered_results,
            evidence_items=[],
        )
        if conflicting_narrative and str(conflicting_narrative.get("operation_family") or "") == "aggregate_subtasks":
            return str(conflicting_narrative.get("answer") or default_answer)

        has_narrative_summary = any(row_is_narrative_summary(row) for row in ordered_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        if complete_numeric_answer and (
            has_narrative_summary
            or aggregate_results_include_dependency_numeric_result(ordered_results)
        ):
            return complete_numeric_answer

        for row in ordered_results:
            if not row_is_narrative_summary(row):
                continue
            sibling_answer = _normalise_spaces(str(row.get("answer") or ""))
            if sibling_answer and re.search(r"\d", sibling_answer):
                return sibling_answer
        return default_answer

    def _sync_aggregate_arithmetic_subtask_surfaces(
        self,
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
            operation_family = self._aggregate_result_operation_family(row)
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
            operation_family = self._aggregate_result_operation_family(target_row)
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

    def _rebuild_aggregate_projection(
        self,
        ordered_results: List[Dict[str, Any]],
        final_answer: str,
        *,
        kept_evidence_ids: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        projection_rows = self._projection_rows_for_final_answer(
            ordered_results,
            final_answer,
        )
        projection = self._build_aggregate_calculation_projection(projection_rows, final_answer)
        if kept_evidence_ids is not None:
            projection = filter_aggregate_projection_provenance(
                AggregateProjectionProvenanceFilterInput(
                    aggregate_projection=projection,
                    kept_evidence_ids=kept_evidence_ids,
                )
            ).aggregate_projection
        return projection

    def _projection_rows_for_final_answer(
        self,
        ordered_results: List[Dict[str, Any]],
        final_answer: str,
    ) -> List[Dict[str, Any]]:
        answer_text = _normalise_spaces(str(final_answer or ""))
        if not answer_text:
            return ordered_results
        for row in ordered_results:
            if not isinstance(row, dict) or not row.get("recovered_from_retrieved_ratio_context"):
                continue
            if self._aggregate_result_operation_family(row) != "ratio":
                continue
            if self._answer_covers_numeric_projection(answer_text, [row]):
                return [dict(row)]
            row_answer = _normalise_spaces(
                str(
                    row.get("answer")
                    or (dict(row.get("calculation_result") or {}).get("formatted_result"))
                    or (dict(row.get("calculation_result") or {}).get("rendered_value"))
                    or ""
                )
            )
            if row_answer and answer_covers_numeric_answer(answer_text, row_answer):
                return [dict(row)]
        return ordered_results

    def _compact_ratio_answer_from_projection(
        self,
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
        calculation_result: Optional[Dict[str, Any]] = None,
        *,
        operands: Optional[Sequence[Dict[str, Any]]] = None,
        plan: Optional[Dict[str, Any]] = None,
    ) -> str:
        result = dict(calculation_result or aggregate_projection.get("calculation_result") or {})
        slots = dict(result.get("answer_slots") or {})
        calculation_plan = dict(plan or aggregate_projection.get("calculation_plan") or {})
        operation = _normalise_spaces(
            str(
                slots.get("operation_family")
                or result.get("operation_family")
                or (result.get("derived_metrics") or {}).get("operation_family")
                or calculation_plan.get("operation")
                or ""
            )
        ).lower()
        if operation != "ratio" or not financial_answer_slots.ratio_components_are_complete(result):
            return ""
        trace_operands = list(operands if operands is not None else aggregate_projection.get("calculation_operands") or [])
        ordered_results = [
            dict(row)
            for row in list(result.get("subtask_results") or state.get("subtask_results") or [])
            if isinstance(row, dict)
        ]
        if (
            aggregate_dependency_slot_coherence_rank_for_operands(
                operation_family="ratio",
                operands=trace_operands,
                calculation_result=result,
                ordered_results=ordered_results,
            )
            == 0
        ):
            return ""
        answer = self._compact_ratio_answer(
            {
                **dict(state),
                "active_subtask": {
                    **dict(state.get("active_subtask") or {}),
                    "metric_label": slots.get("metric_label")
                    or (state.get("active_subtask") or {}).get("metric_label")
                    or "",
                },
                "resolved_calculation_trace": {
                    "calculation_operands": trace_operands,
                    "calculation_plan": calculation_plan,
                    "calculation_result": result,
                },
            },
            result,
        )
        return _normalise_spaces(str(answer or ""))

    def _refresh_numeric_aggregate_answer_candidate(
        self,
        *,
        query: str,
        current_answer: str,
        numeric_answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        sync_projection: bool = True,
        sync_rendered_for_aggregate: bool = True,
        status_ok: bool = False,
    ) -> Dict[str, Any]:
        refreshed_answer = self._refresh_numeric_answer_preserving_narrative_context(
            query=query,
            current_answer=current_answer,
            numeric_answer=numeric_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        return package_refreshed_aggregate_answer_candidate(
            AggregateRefreshedAnswerCandidatePackagingInput(
                refreshed_answer=refreshed_answer,
                fallback_answer=numeric_answer,
                sync_projection=sync_projection,
                sync_rendered_for_aggregate=sync_rendered_for_aggregate,
                status_ok=status_ok,
            )
        ).candidate

    def _apply_initial_aggregate_answer_composition(
        self,
        state: FinancialAgentState,
        *,
        ordered_results: List[Dict[str, Any]],
        preliminary_projection: Dict[str, Any],
        aggregate_evidence_items: List[Dict[str, Any]],
        narrative_docs: List[Any],
        narrative_context: str,
        final_answer: str,
        supported_aggregate_answer: str,
        complete_numeric_answer: str,
        has_narrative_summary: bool,
        has_growth_rate_result: bool,
        numeric_answer_locked: bool,
        planner_feedback: str,
        deterministic_feedback: str,
    ) -> tuple[AggregateCompositionState, str]:
        if (
            deterministic_feedback
            and self._unresolved_structured_numeric_gap(ordered_results)
            and answer_reuses_narrative_summary_text(final_answer, ordered_results)
        ):
            safe_partial_answer = safe_partial_answer_for_numeric_gap(ordered_results)
            final_answer = safe_partial_answer or ""
        final_answer = calculation_rendering.coerce_sign_aware_subtraction_answer(
            final_answer,
            calculation_result=dict(preliminary_projection.get("calculation_result") or {}),
            subtask_results=ordered_results,
        )
        slot_based_difference_answer = calculation_rendering.compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(preliminary_projection.get("calculation_result") or {}),
            answer_slot_has_material=answer_slot_has_material,
        )
        if slot_based_difference_answer:
            final_answer = slot_based_difference_answer
            complete_numeric_answer = slot_based_difference_answer
            planner_feedback = ""
            deterministic_feedback = ""
        if (
            has_narrative_summary
            and not supported_aggregate_answer
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            and not (
                query_requests_explanatory_context(str(state.get("query") or ""))
                and answer_reuses_numeric_narrative_summary_text(final_answer, ordered_results)
            )
        ):
            final_answer = ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        if not deterministic_feedback:
            final_answer = include_narrative_context_if_needed(
                final_answer,
                query=str(state.get("query") or ""),
                narrative_context=narrative_context,
            )

        composition_state = AggregateCompositionState(
            final_answer=final_answer,
            selected_claim_ids=[],
            calculation_projection_override=None,
            narrative_answer_locked=bool(
                supported_aggregate_answer
                and self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            ),
            planner_feedback=planner_feedback,
            deterministic_feedback=deterministic_feedback,
        )
        growth_narrative_answer = self._compose_growth_narrative_answer(
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            existing_answer=composition_state.final_answer,
            evidence_items=aggregate_evidence_items,
        )
        entity_table_answer = self._compose_entity_table_summary_answer(
            query=str(state.get("query") or ""),
            docs=narrative_docs,
            evidence_items=aggregate_evidence_items,
        )
        if growth_narrative_answer and not composition_state.narrative_answer_locked:
            growth_compressed_answer = _normalise_spaces(str(growth_narrative_answer.get("compressed_answer") or ""))
            composition_state = apply_aggregate_composition_answer(
                composition_state,
                answer=growth_compressed_answer,
                selected_claim_ids=growth_narrative_answer.get("selected_claim_ids") or [],
                narrative_answer_locked=bool(growth_compressed_answer)
                or self._answer_satisfies_growth_narrative_intent(
                    query=str(state.get("query") or ""),
                    answer=growth_compressed_answer or composition_state.final_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                ),
            )
        if entity_table_answer and not composition_state.narrative_answer_locked:
            projection = entity_table_answer.get("calculation_projection")
            composition_state = apply_aggregate_composition_answer(
                composition_state,
                answer=str(entity_table_answer.get("compressed_answer") or ""),
                selected_claim_ids=entity_table_answer.get("selected_claim_ids") or [],
                calculation_projection_override=projection if isinstance(projection, dict) else None,
            )
        business_focus_answer = self._compose_business_technology_focus_answer(
            query=str(state.get("query") or ""),
            existing_answer=composition_state.final_answer,
            docs=narrative_docs,
            evidence_items=aggregate_evidence_items,
        )
        if business_focus_answer and not composition_state.narrative_answer_locked:
            composition_state = apply_aggregate_composition_answer(
                composition_state,
                answer=str(business_focus_answer.get("compressed_answer") or ""),
                selected_claim_ids=business_focus_answer.get("selected_claim_ids") or [],
            )
        dividend_policy_answer = self._compose_dividend_policy_hybrid_answer(
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        dividend_answer = _normalise_spaces(str((dividend_policy_answer or {}).get("answer") or ""))
        if dividend_answer:
            composition_state = apply_aggregate_composition_answer(
                composition_state,
                answer=dividend_answer,
                selected_claim_ids=(dividend_policy_answer or {}).get("supporting_claim_ids") or [],
                reset_projection_override=True,
            )
        quantitative_impact_answer = self._compose_supported_quantitative_impact_answer(
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        if quantitative_impact_answer and not composition_state.narrative_answer_locked:
            composition_state = apply_aggregate_composition_answer(
                composition_state,
                answer=str(quantitative_impact_answer.get("answer") or ""),
                selected_claim_ids=quantitative_impact_answer.get("supporting_claim_ids") or [],
                narrative_answer_locked=True,
            )
        if not composition_state.deterministic_feedback:
            augmented_answer = self._augment_narrative_answer_with_supported_drivers(
                composition_state.final_answer,
                aggregate_evidence_items,
                query=str(state.get("query") or ""),
            )
            if augmented_answer and augmented_answer != composition_state.final_answer:
                composition_state = composition_state._replace(
                    final_answer=augmented_answer,
                    selected_claim_ids=self._expand_selected_claim_ids_for_narrative_drivers(
                        composition_state.selected_claim_ids,
                        aggregate_evidence_items,
                        query=str(state.get("query") or ""),
                    ),
                )
        if not supported_aggregate_answer and not self._answer_satisfies_growth_narrative_intent(
            query=str(state.get("query") or ""),
            answer=composition_state.final_answer,
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        ):
            repaired_growth_narrative_answer = self._compose_growth_narrative_answer(
                query=str(state.get("query") or ""),
                ordered_results=ordered_results,
                existing_answer=composition_state.final_answer,
                evidence_items=aggregate_evidence_items,
            )
            repaired_answer = _normalise_spaces(
                str((repaired_growth_narrative_answer or {}).get("compressed_answer") or "")
            )
            if repaired_answer and self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=repaired_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            ):
                composition_state = composition_state._replace(
                    final_answer=repaired_answer,
                    selected_claim_ids=[
                        str(claim_id).strip()
                        for claim_id in ((repaired_growth_narrative_answer or {}).get("selected_claim_ids") or [])
                        if str(claim_id).strip()
                    ],
                )
        if numeric_answer_locked:
            if has_narrative_summary and has_growth_rate_result:
                numeric_lock_candidate = self._refresh_numeric_aggregate_answer_candidate(
                    query=str(state.get("query") or ""),
                    current_answer=composition_state.final_answer,
                    numeric_answer=complete_numeric_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                    sync_projection=False,
                )
                final_answer = _normalise_spaces(str(numeric_lock_candidate.get("answer") or complete_numeric_answer))
                selected_claim_ids = list(numeric_lock_candidate.get("selected_claim_ids") or [])
            else:
                final_answer = complete_numeric_answer
                selected_claim_ids = []
            composition_state = AggregateCompositionState(
                final_answer=final_answer,
                selected_claim_ids=selected_claim_ids,
                calculation_projection_override=None,
                narrative_answer_locked=composition_state.narrative_answer_locked,
                planner_feedback="",
                deterministic_feedback="",
            )
        return composition_state, complete_numeric_answer

    def _apply_period_context_realignment_to_aggregate(
        self,
        *,
        aggregate_state: _AggregateSynthesisState,
        state: FinancialAgentState,
        evidence_items: List[Dict[str, Any]],
        kept_evidence_ids: Optional[set[str]] = None,
    ) -> _AggregateSynthesisState:
        realigned_results = self._realign_period_comparison_results_from_table_label_context(
            aggregate_state.ordered_results,
            state,
            evidence_items,
        )
        if realigned_results is aggregate_state.ordered_results:
            return aggregate_state
        ordered_results = realigned_results
        aggregate_projection = aggregate_state.aggregate_projection
        final_answer = aggregate_state.final_answer
        selected_claim_ids = aggregate_state.selected_claim_ids
        refreshed_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        if refreshed_numeric_answer and self._complete_numeric_answer_can_replace_final(
            refreshed_numeric_answer,
            ordered_results,
        ):
            aggregate_state = self._apply_numeric_answer_to_aggregate_state(
                aggregate_state=_AggregateSynthesisState(
                    ordered_results,
                    aggregate_projection,
                    final_answer,
                    selected_claim_ids,
                ),
                state=state,
                numeric_answer=refreshed_numeric_answer,
                evidence_items=evidence_items,
                sync_projection=False,
            )
            ordered_results, aggregate_projection, final_answer, selected_claim_ids = aggregate_state
        aggregate_projection = self._rebuild_aggregate_projection(
            ordered_results,
            final_answer,
            kept_evidence_ids=kept_evidence_ids,
        )
        return _AggregateSynthesisState(ordered_results, aggregate_projection, final_answer, selected_claim_ids)

    def _apply_numeric_answer_to_aggregate_state(
        self,
        *,
        aggregate_state: _AggregateSynthesisState,
        state: FinancialAgentState,
        numeric_answer: str,
        evidence_items: List[Dict[str, Any]],
        sync_projection: bool = False,
    ) -> _AggregateSynthesisState:
        candidate_application = apply_aggregate_answer_candidate(
            AggregateAnswerCandidateApplicationInput(
                aggregate_projection=aggregate_state.aggregate_projection,
                selected_claim_ids=aggregate_state.selected_claim_ids,
                candidate=self._refresh_numeric_aggregate_answer_candidate(
                    query=str(state.get("query") or ""),
                    current_answer=aggregate_state.final_answer,
                    numeric_answer=numeric_answer,
                    ordered_results=aggregate_state.ordered_results,
                    evidence_items=evidence_items,
                    sync_projection=sync_projection,
                ),
            )
        )
        aggregate_projection = candidate_application.aggregate_projection
        final_answer = candidate_application.final_answer
        selected_claim_ids = candidate_application.selected_claim_ids
        return _AggregateSynthesisState(
            aggregate_state.ordered_results,
            aggregate_projection,
            final_answer,
            selected_claim_ids,
        )

    def _replace_mutable_aggregate_answer(
        self,
        mutable_state: _AggregateMutableState,
        *,
        candidate_answer: str,
        sync_rendered_for_aggregate: bool = True,
        status_ok: bool = False,
        force: bool = False,
        refresh_operand_evidence: bool = False,
    ) -> tuple[_AggregateMutableState, bool]:
        candidate_answer = _normalise_spaces(candidate_answer)
        if candidate_answer == mutable_state.final_answer and not force:
            return mutable_state, False
        aggregate_projection = sync_aggregate_projection_final_answer(
            AggregateProjectionFinalAnswerSyncInput(
                aggregate_projection=mutable_state.aggregate_projection,
                final_answer=candidate_answer,
                sync_rendered_for_aggregate=sync_rendered_for_aggregate,
                status_ok=status_ok,
            )
        ).aggregate_projection
        evidence_items = mutable_state.evidence_items
        if refresh_operand_evidence:
            evidence_items = append_operand_evidence_for_final_answer(
                evidence_items,
                operands=list(aggregate_projection.get("calculation_operands") or []),
                final_answer=candidate_answer,
            )
        synthesis_state = _AggregateSynthesisState(
            mutable_state.ordered_results,
            aggregate_projection,
            candidate_answer,
            mutable_state.selected_claim_ids,
        )
        return _AggregateMutableState(synthesis_state, evidence_items), True

    def _replace_mutable_aggregate_results(
        self,
        mutable_state: _AggregateMutableState,
        state: FinancialAgentState,
        ordered_results: List[Dict[str, Any]],
        *,
        refresh_numeric_answer: bool = False,
        sync_projection: bool = False,
        rebuild_after_numeric_refresh: bool = True,
        kept_evidence_ids: Optional[set[str]] = None,
    ) -> _AggregateMutableState:
        synthesis_state = mutable_state.synthesis_state.with_updates(
            ordered_results=ordered_results,
            aggregate_projection=self._rebuild_aggregate_projection(
                ordered_results, mutable_state.final_answer, kept_evidence_ids=kept_evidence_ids
            ),
        )
        if refresh_numeric_answer:
            numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
            if numeric_answer and self._complete_numeric_answer_can_replace_final(numeric_answer, ordered_results):
                synthesis_state = self._apply_numeric_answer_to_aggregate_state(
                    aggregate_state=synthesis_state,
                    state=state,
                    numeric_answer=numeric_answer,
                    evidence_items=mutable_state.evidence_items,
                    sync_projection=sync_projection,
                )
                if rebuild_after_numeric_refresh:
                    synthesis_state = synthesis_state.with_updates(
                        aggregate_projection=self._rebuild_aggregate_projection(
                            synthesis_state.ordered_results,
                            synthesis_state.final_answer,
                            kept_evidence_ids=kept_evidence_ids,
                        )
                    )
        return mutable_state.with_synthesis_state(synthesis_state)

    def _apply_final_narrative_repair_pipeline(
        self,
        state: FinancialAgentState,
        *,
        mutable_state: _AggregateMutableState,
        narrative_docs: List[Any],
        has_narrative_summary: bool,
        has_growth_rate_result: bool,
        deterministic_feedback: str,
    ) -> _AggregateMutableState:
        ordered_results, aggregate_projection, final_answer, selected_claim_ids = mutable_state.synthesis_state
        aggregate_evidence_items = mutable_state.evidence_items

        def _sync_locals() -> None:
            nonlocal ordered_results, aggregate_projection, final_answer, selected_claim_ids, aggregate_evidence_items
            ordered_results, aggregate_projection, final_answer, selected_claim_ids = mutable_state.synthesis_state
            aggregate_evidence_items = mutable_state.evidence_items

        def _sync_state(**updates: Any) -> None:
            nonlocal mutable_state
            mutable_state = mutable_state.with_updates(**updates)
            _sync_locals()

        def _apply_candidate(candidate_answer: str, **kwargs: Any) -> None:
            nonlocal mutable_state
            mutable_state, _ = self._replace_mutable_aggregate_answer(
                mutable_state,
                candidate_answer=candidate_answer,
                **kwargs,
            )
            _sync_locals()

        realized_context_answer = self._preserve_policy_required_realized_context(
            final_answer,
            query=str(state.get("query") or ""),
            docs=narrative_docs,
        )
        _apply_candidate(
            realized_context_answer,
            status_ok=bool(realized_context_answer and not deterministic_feedback),
            force=True,
        )
        aggregate_evidence_items = append_operand_evidence_for_final_answer(
            aggregate_evidence_items,
            operands=list(aggregate_projection.get("calculation_operands") or []),
            final_answer=final_answer,
        )
        _sync_state(evidence_items=aggregate_evidence_items)
        aggregate_evidence_items, retrieved_narrative_claim_ids = self._append_retrieved_narrative_evidence_for_final_answer(
            aggregate_evidence_items,
            final_answer=final_answer,
            docs=narrative_docs,
        )
        _sync_state(evidence_items=aggregate_evidence_items)
        if retrieved_narrative_claim_ids:
            selected_claim_ids = _aggregate_extend_selected_claim_ids(
                selected_claim_ids,
                retrieved_narrative_claim_ids,
            )
            _sync_state(selected_claim_ids=selected_claim_ids)
        aggregate_state = self._apply_period_context_realignment_to_aggregate(
            aggregate_state=mutable_state.synthesis_state,
            state=state,
            evidence_items=aggregate_evidence_items,
        )
        mutable_state = mutable_state.with_synthesis_state(aggregate_state)
        _sync_locals()
        if has_narrative_summary and not self._answer_satisfies_growth_narrative_intent(
            query=str(state.get("query") or ""),
            answer=final_answer,
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        ):
            repaired_growth_narrative_answer = self._compose_growth_narrative_answer(
                query=str(state.get("query") or ""),
                ordered_results=ordered_results,
                existing_answer=final_answer,
                evidence_items=aggregate_evidence_items,
            )
            repaired_answer = _normalise_spaces(
                str((repaired_growth_narrative_answer or {}).get("compressed_answer") or "")
            )
            if repaired_answer and self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=repaired_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            ):
                candidate_application = apply_aggregate_answer_candidate(
                    AggregateAnswerCandidateApplicationInput(
                        aggregate_projection=aggregate_projection,
                        selected_claim_ids=selected_claim_ids,
                        candidate=package_aggregate_answer_candidate(
                            AggregateAnswerCandidatePackagingInput(
                                answer=repaired_answer,
                                selected_claim_ids=(repaired_growth_narrative_answer or {}).get(
                                    "selected_claim_ids"
                                )
                                or [],
                            )
                        ).candidate,
                    )
                )
                aggregate_projection = candidate_application.aggregate_projection
                final_answer = candidate_application.final_answer
                selected_claim_ids = candidate_application.selected_claim_ids
                aggregate_evidence_items = append_operand_evidence_for_final_answer(
                    aggregate_evidence_items,
                    operands=list(aggregate_projection.get("calculation_operands") or []),
                    final_answer=final_answer,
                )
                _sync_state(
                    aggregate_projection=aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                    evidence_items=aggregate_evidence_items,
                )
        contracted_answer = self._enforce_source_stated_growth_answer_contract(
            final_answer,
            ordered_results,
            evidence_items=aggregate_evidence_items,
        )
        if contracted_answer != final_answer:
            _apply_candidate(
                contracted_answer,
                refresh_operand_evidence=True,
            )
        source_surface_answer = preserve_retrieved_narrative_source_surface(
            final_answer,
            aggregate_evidence_items,
        )
        _apply_candidate(source_surface_answer)
        unresolved_numeric_gap = self._unresolved_structured_numeric_gap(ordered_results)
        blocked_narrative_numeric_gap = bool(
            unresolved_numeric_gap
            and answer_reuses_narrative_summary_text(final_answer, ordered_results)
        )
        if blocked_narrative_numeric_gap:
            safe_partial_answer = safe_partial_answer_for_numeric_gap(ordered_results)
            if safe_partial_answer:
                _apply_candidate(safe_partial_answer)
        if (
            final_answer
            and has_narrative_summary
            and has_growth_rate_result
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            and not (
                query_requests_explanatory_context(str(state.get("query") or ""))
                and answer_reuses_numeric_narrative_summary_text(final_answer, ordered_results)
            )
        ):
            numeric_preserved_answer = ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            if numeric_preserved_answer != final_answer:
                _apply_candidate(
                    numeric_preserved_answer,
                    refresh_operand_evidence=True,
                )
        pruned_focus_answer = self._prune_nonfocus_numeric_narrative_sentences(
            final_answer,
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        )
        _apply_candidate(pruned_focus_answer)
        polished_answer = _polish_korean_particle_pairs(final_answer)
        _apply_candidate(polished_answer)
        has_growth_narrative_intent = has_narrative_summary or query_requests_explanatory_context(
            str(state.get("query") or "")
        )
        projection_plan = dict(aggregate_projection.get("calculation_plan") or {})
        projection_result = dict(aggregate_projection.get("calculation_result") or {})
        has_growth_material = (
            has_growth_rate_result
            or str(projection_plan.get("operation") or projection_result.get("operation_family") or "").strip().lower()
            == "growth_rate"
        )
        if has_growth_narrative_intent and has_growth_material:
            final_aligned_results, _final_identity_changed, final_value_changed, _final_alignment_changed = (
                self._promote_and_align_aggregate_results(
                    ordered_results,
                    state,
                    final_answer,
                    align_without_promotion=True,
                )
            )
            if final_value_changed:
                mutable_state = self._replace_mutable_aggregate_results(
                    mutable_state,
                    state,
                    final_aligned_results,
                    refresh_numeric_answer=True,
                    sync_projection=True,
                    rebuild_after_numeric_refresh=False,
                )
                _sync_locals()
            if query_requests_explanatory_context(str(state.get("query") or "")):
                appended_explanation = False
                for row in ordered_results:
                    if not row_is_narrative_summary(row):
                        continue
                    row_answer = _normalise_spaces(
                        str(
                            row.get("answer")
                            or (row.get("calculation_result") or {}).get("formatted_result")
                            or (row.get("calculation_result") or {}).get("rendered_value")
                            or ""
                        )
                    )
                    if not row_answer or row_answer in final_answer:
                        continue
                    for sentence in _split_narrative_sentences(row_answer) or [row_answer]:
                        cleaned = strip_untraced_numeric_material_from_growth_narrative_sentence(
                            sentence,
                            ordered_results,
                            evidence_items=aggregate_evidence_items,
                        )
                        if cleaned and cleaned not in final_answer:
                            _apply_candidate(" ".join([final_answer, cleaned]))
                            appended_explanation = True
                            break
                    if appended_explanation:
                        break
        return mutable_state

    def _promote_and_align_aggregate_results(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
        final_answer: str,
        *,
        align_without_promotion: bool,
    ) -> tuple[List[Dict[str, Any]], bool, bool, bool]:
        promoted_results = self._promote_stronger_nested_aggregate_results(ordered_results)
        if not align_without_promotion and promoted_results is ordered_results:
            return promoted_results, False, False, False
        projection = self._rebuild_aggregate_projection(promoted_results, final_answer)
        aligned_results = self._align_lookup_results_with_dependency_projection(
            promoted_results,
            state,
            projection,
        )
        identity_changed = promoted_results is not ordered_results or aligned_results is not promoted_results
        alignment_value_changed = aligned_results != promoted_results
        value_changed = promoted_results != ordered_results or aligned_results != promoted_results
        return aligned_results, identity_changed, value_changed, alignment_value_changed

    def _apply_ratio_projection_answer_if_rendered_missing(
        self,
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
        *,
        final_answer: str,
        artifacts: Optional[List[Dict[str, Any]]] = None,
        artifact_id: str = "",
    ) -> tuple[Dict[str, Any], str, List[Dict[str, Any]]]:
        updated_artifacts = [dict(item) for item in (artifacts or [])]
        projection_result = dict(aggregate_projection.get("calculation_result") or {})
        projection_slots = dict(projection_result.get("answer_slots") or {})
        projection_operation = _normalise_spaces(
            str(
                projection_slots.get("operation_family")
                or projection_result.get("operation_family")
                or (aggregate_projection.get("calculation_plan") or {}).get("operation")
                or ""
            )
        ).lower()
        projection_rendered = _normalise_spaces(str(projection_result.get("rendered_value") or ""))
        if (
            projection_operation != "ratio"
            or not projection_rendered
            or projection_rendered in final_answer
            or not financial_answer_slots.ratio_components_are_complete(projection_result)
        ):
            return aggregate_projection, final_answer, updated_artifacts

        projection_answer = self._compact_ratio_answer_from_projection(
            state,
            aggregate_projection,
            projection_result,
        )
        if not projection_answer:
            return aggregate_projection, final_answer, updated_artifacts

        final_answer = projection_answer
        aggregate_projection["calculation_result"] = {
            **projection_result,
            "formatted_result": final_answer,
        }
        if artifacts is not None and artifact_id:
            updated_artifacts = synchronize_aggregate_artifact_projection_payload(
                AggregateArtifactProjectionPayloadSyncInput(
                    artifacts=updated_artifacts,
                    artifact_id=artifact_id,
                    final_answer=final_answer,
                    aggregate_projection=aggregate_projection,
                )
            ).artifacts
        return aggregate_projection, final_answer, updated_artifacts

    def _repair_stale_aggregate_projection_result(
        self,
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
    ) -> tuple[Dict[str, Any], _StaleCalculationRepairResult]:
        calculation_operands = [
            dict(row)
            for row in list(aggregate_projection.get("calculation_operands") or [])
            if isinstance(row, dict)
        ]
        calculation_plan = dict(aggregate_projection.get("calculation_plan") or {})
        calculation_result = dict(aggregate_projection.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        repair_state = {
            **dict(state),
            "active_subtask": {
                **dict(state.get("active_subtask") or {}),
                "operation_family": answer_slots.get("operation_family"),
                "metric_label": answer_slots.get("metric_label"),
            },
        }
        stale_repair = self._repair_stale_calculation_result_from_operands(
            repair_state,
            operands=calculation_operands,
            plan=calculation_plan,
            calculation_result=calculation_result,
        )
        if not stale_repair.repair_applied:
            return aggregate_projection, stale_repair
        repaired_projection = {
            **dict(aggregate_projection),
            "calculation_operands": stale_repair.calculation_operands,
            "calculation_plan": stale_repair.calculation_plan,
            "calculation_result": stale_repair.calculation_result,
        }
        return repaired_projection, stale_repair

    def _apply_stale_projection_repair_to_aggregate_state(
        self,
        *,
        state: FinancialAgentState,
        aggregate_state: _AggregateSynthesisState,
        evidence_items: List[Dict[str, Any]],
        prefer_compact_ratio_answer: bool = False,
    ) -> _AggregateSynthesisState:
        aggregate_projection, stale_repair = self._repair_stale_aggregate_projection_result(
            state,
            aggregate_state.aggregate_projection,
        )
        if not stale_repair.repair_applied:
            return aggregate_state
        repaired_operands = stale_repair.calculation_operands
        repaired_plan = stale_repair.calculation_plan
        repaired_result = stale_repair.calculation_result
        if (
            aggregate_dependency_slot_coherence_rank_for_operands(
                operation_family=_normalise_spaces(
                    str(
                        (dict(repaired_result.get("answer_slots") or {})).get("operation_family")
                        or repaired_plan.get("operation")
                        or ""
                    )
                ),
                operands=repaired_operands,
                calculation_result=repaired_result,
                ordered_results=aggregate_state.ordered_results,
            )
            == 0
        ):
            return aggregate_state
        provenance_selection = _select_aggregate_stale_repair_provenance(
            AggregateStaleRepairProvenanceInput(
                ordered_results=aggregate_state.ordered_results,
                aggregate_projection=aggregate_state.aggregate_projection,
                selected_claim_ids=aggregate_state.selected_claim_ids,
                repaired_calculation_result=stale_repair.calculation_result,
                repaired_selected_evidence_ids=stale_repair.selected_evidence_ids,
                evidence_items=evidence_items,
            )
        )
        accepted_state = aggregate_state.with_updates(
            aggregate_projection=aggregate_projection,
            selected_claim_ids=list(provenance_selection.selected_claim_ids),
        )
        repaired_answer = _normalise_spaces(
            str(repaired_result.get("formatted_result") or repaired_result.get("rendered_value") or "")
        )
        if prefer_compact_ratio_answer:
            repaired_answer = _normalise_spaces(
                self._compact_ratio_answer_from_projection(
                    state,
                    aggregate_projection,
                    repaired_result,
                    operands=repaired_operands,
                    plan=repaired_plan,
                )
                or repaired_answer
                or aggregate_state.final_answer
            )
            if self._answer_covers_numeric_projection(
                aggregate_state.final_answer,
                aggregate_state.ordered_results,
            ) and (
                not self._answer_covers_numeric_projection(
                    repaired_answer,
                    aggregate_state.ordered_results,
                )
                or not answer_has_numeric_material_outside_reference(
                    aggregate_state.final_answer,
                    repaired_answer,
                )
            ):
                aggregate_projection["calculation_result"] = {
                    **repaired_result,
                    "formatted_result": aggregate_state.final_answer,
                }
                return accepted_state.with_updates(aggregate_projection=aggregate_projection)
            replacement_answer = self._complete_numeric_projection_replacement_answer(
                final_answer=repaired_answer,
                ordered_results=aggregate_state.ordered_results,
                query=str(state.get("query") or ""),
                evidence_items=evidence_items,
            )
            if replacement_answer:
                return self._apply_numeric_answer_to_aggregate_state(
                    aggregate_state=accepted_state,
                    state=state,
                    numeric_answer=replacement_answer,
                    evidence_items=evidence_items,
                    sync_projection=True,
                )
            aggregate_projection["calculation_result"] = {
                **repaired_result,
                "formatted_result": repaired_answer,
            }
            return accepted_state.with_updates(
                aggregate_projection=aggregate_projection,
                final_answer=repaired_answer,
            )
        if not repaired_answer:
            return accepted_state
        return self._apply_numeric_answer_to_aggregate_state(
            aggregate_state=accepted_state,
            state=state,
            numeric_answer=repaired_answer,
            evidence_items=evidence_items,
            sync_projection=True,
        )

    def _apply_runtime_ratio_projection_for_collapsed_rows(
        self,
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
        final_answer: str,
    ) -> tuple[Dict[str, Any], str]:
        runtime_trace = _resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
        runtime_result = dict(runtime_trace.get("calculation_result") or {})
        runtime_plan = dict(runtime_trace.get("calculation_plan") or {})
        runtime_slots = dict(runtime_result.get("answer_slots") or {})
        runtime_operation = _normalise_spaces(
            str(
                runtime_slots.get("operation_family")
                or runtime_result.get("operation_family")
                or runtime_plan.get("operation")
                or ""
            )
        ).lower()
        has_invalid_self_ratio_row = any(
            self._aggregate_result_operation_family(row) == "ratio"
            and financial_answer_slots.ratio_components_collapse_to_same_slot(dict(row.get("calculation_result") or {}))
            for row in ordered_results
        )
        if (
            not has_invalid_self_ratio_row
            or runtime_operation != "ratio"
            or not financial_answer_slots.ratio_components_are_complete(runtime_result)
        ):
            return aggregate_projection, final_answer

        runtime_result = dict(runtime_result)
        runtime_slots = dict(runtime_slots)
        runtime_primary = dict(runtime_slots.get("primary_value") or {})
        if calculation_rendering.ratio_query_requests_absolute_magnitude(str(state.get("query") or "")):
            runtime_result = project_runtime_ratio_absolute_magnitude(
                RuntimeRatioAbsoluteMagnitudeProjectionInput(
                    calculation_result=runtime_result,
                    answer_slots=runtime_slots,
                    primary_value=runtime_primary,
                )
            ).calculation_result

        runtime_operands = list(runtime_trace.get("calculation_operands") or [])
        if (
            aggregate_dependency_slot_coherence_rank_for_operands(
                operation_family="ratio",
                operands=runtime_operands,
                calculation_result=runtime_result,
                ordered_results=ordered_results,
            )
            == 0
        ):
            return aggregate_projection, final_answer
        runtime_answer = self._compact_ratio_answer_from_projection(
            state,
            aggregate_projection,
            runtime_result,
            operands=runtime_operands,
            plan=runtime_plan,
        )
        if not runtime_answer:
            return aggregate_projection, final_answer
        if self._answer_covers_numeric_projection(final_answer, ordered_results):
            return aggregate_projection, final_answer
        final_answer = runtime_answer
        aggregate_projection["calculation_operands"] = runtime_operands
        aggregate_projection["calculation_plan"] = runtime_plan
        aggregate_projection["calculation_result"] = {
            **runtime_result,
            "formatted_result": final_answer,
        }
        return aggregate_projection, final_answer

    def _filter_final_aggregate_evidence_and_projection(
        self,
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

    def _append_retrieved_narrative_evidence_for_final_answer(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        final_answer: str,
        docs: List[Any],
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        answer_text = _normalise_spaces(str(final_answer or ""))
        if not answer_text or not docs:
            return list(evidence_items or []), []
        answer_numeric_candidates = extract_numeric_surface_candidates(answer_text)

        updated = [dict(item or {}) for item in (evidence_items or [])]
        selected_ids: List[str] = []
        existing_ids = {
            str(item.get("evidence_id") or "").strip()
            for item in updated
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        }
        existing_texts = [
            _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        item.get("claim"),
                        item.get("quote_span"),
                        item.get("raw_row_text"),
                    )
                )
            )
            for item in updated
            if isinstance(item, dict)
        ]

        def _content_terms(text: str) -> set[str]:
            return {
                term.lower()
                for term in narrative_context_terms(text)
                if len(term) >= 3
            }

        missing_markers = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ())
            if str(item)
        )

        def _sentence_already_supported(sentence: str) -> bool:
            sentence_terms = _content_terms(sentence)
            if not sentence_terms:
                return True
            sentence_lower = sentence.lower()
            for existing in existing_texts:
                existing_lower = existing.lower()
                if sentence_lower and sentence_lower in existing_lower:
                    return True
                existing_terms = _content_terms(existing)
                if not existing_terms:
                    continue
                overlap = sentence_terms & existing_terms
                if len(overlap) >= max(2, min(len(sentence_terms), len(existing_terms)) // 2):
                    return True
            return False

        def _supporting_doc_quote(page_content: str, target_sentence: str) -> str:
            content = _normalise_spaces(page_content)
            target = _normalise_spaces(target_sentence)
            if not content or not target:
                return content[:700]
            content_lower = content.lower()
            target_lower = target.lower()
            exact_index = content_lower.find(target_lower)
            if exact_index >= 0:
                start = max(0, exact_index - 120)
                end = min(len(content), exact_index + len(target) + 220)
                return _normalise_spaces(content[start:end])
            target_terms = _content_terms(target)
            best_sentence = ""
            best_score = 0
            for sentence in _split_narrative_sentences(content):
                cleaned_sentence = _normalise_spaces(sentence)
                if not cleaned_sentence:
                    continue
                sentence_terms = _content_terms(cleaned_sentence)
                score = len(target_terms & sentence_terms)
                if score > best_score:
                    best_sentence = cleaned_sentence
                    best_score = score
            if best_sentence:
                return best_sentence[:700]
            return content[:700]

        doc_rows: List[Dict[str, Any]] = []
        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            page_content = _normalise_spaces(
                str(getattr(doc, "page_content", None) or getattr(doc, "content", None) or "")
            )
            if not page_content:
                continue
            metadata = dict(getattr(doc, "metadata", {}) or {})
            source_anchor = _normalise_spaces(
                str(
                    metadata.get("source_anchor")
                    or metadata.get("section_path")
                    or metadata.get("section_title")
                    or metadata.get("section")
                    or ""
                )
            )
            doc_rows.append(
                {
                    "page_content": page_content,
                    "metadata": metadata,
                    "source_anchor": source_anchor,
                    "terms": _content_terms(page_content),
                }
            )

        for sentence in _split_narrative_sentences(answer_text):
            cleaned = _normalise_spaces(sentence)
            sentence_terms = _content_terms(cleaned)
            if (
                not cleaned
                or any(marker in cleaned for marker in missing_markers)
                or not sentence_terms
                or _sentence_already_supported(cleaned)
            ):
                continue
            if text_supports_numeric_candidates(cleaned, answer_numeric_candidates):
                continue
            scored_docs: List[tuple[int, Dict[str, Any]]] = []
            for row in doc_rows:
                doc_terms = set(row.get("terms") or set())
                overlap = sentence_terms & doc_terms
                exact_bonus = 4 if cleaned.lower() in str(row.get("page_content") or "").lower() else 0
                score = len(overlap) + exact_bonus
                if score:
                    scored_docs.append((score, row))
            scored_docs.sort(key=lambda item: item[0], reverse=True)
            if not scored_docs:
                continue
            best_score, best_doc = scored_docs[0]
            min_score = max(2, min(4, len(sentence_terms) // 2 or 1))
            if best_score < min_score:
                continue
            evidence_id = f"retrieved_narrative::{len(selected_ids) + 1:03d}"
            while evidence_id in existing_ids:
                evidence_id = f"retrieved_narrative::{len(selected_ids) + len(existing_ids) + 1:03d}"
            existing_ids.add(evidence_id)
            selected_ids.append(evidence_id)
            updated.append(
                {
                    "evidence_id": evidence_id,
                    "source_anchor": best_doc.get("source_anchor") or "",
                    "claim": cleaned,
                    "quote_span": _supporting_doc_quote(str(best_doc.get("page_content") or ""), cleaned),
                    "support_level": "direct",
                    "question_relevance": "high",
                    "metadata": dict(best_doc.get("metadata") or {}),
                }
            )
        return updated, selected_ids

    def _append_missing_decision_context_evidence(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        final_answer: str,
        selected_claim_ids: List[str],
        query: str,
        docs: List[Any],
        limit: int = 2,
    ) -> tuple[List[Dict[str, Any]], List[str]]:
        answer_text = _normalise_spaces(str(final_answer or ""))
        missing_markers = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ())
            if str(item)
        )
        if (
            not docs
            or not answer_text
            or not any(marker and marker in answer_text for marker in missing_markers)
        ):
            return [dict(item or {}) for item in (evidence_items or [])], []

        updated = [dict(item or {}) for item in (evidence_items or [])]
        existing_ids = {
            str(item.get("evidence_id") or "").strip()
            for item in updated
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        }
        seen_surfaces = {
            _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        item.get("source_anchor"),
                        item.get("claim"),
                        item.get("quote_span"),
                    )
                )
            )
            for item in updated
            if isinstance(item, dict)
        }

        focus_terms = [
            _normalise_spaces(str(term or ""))
            for term in self._query_focus_markers(query)
            if _normalise_spaces(str(term or ""))
        ]
        focus_terms_lower = {term.lower() for term in focus_terms if len(term) >= 2}
        selected_ids = {str(claim_id).strip() for claim_id in (selected_claim_ids or []) if str(claim_id).strip()}
        if selected_ids:
            if not focus_terms_lower:
                return updated, []
            selected_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for item in updated
                    if str(item.get("evidence_id") or "").strip() in selected_ids
                    for value in (
                        item.get("claim"),
                        item.get("quote_span"),
                        item.get("raw_row_text"),
                        " ".join(str(term or "") for term in (item.get("allowed_terms") or [])),
                    )
                )
            ).lower()
            selected_focus_hits = sorted(term for term in focus_terms_lower if term in selected_surface)
            required_selected_hits = max(1, min(2, len(focus_terms_lower)))
            if len(selected_focus_hits) >= required_selected_hits:
                return updated, []

        scored_candidates: List[tuple[float, int, Dict[str, Any]]] = []
        for rank, item in enumerate(docs):
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            page_content = _normalise_spaces(
                str(getattr(doc, "page_content", None) or getattr(doc, "content", None) or "")
            )
            metadata = dict(getattr(doc, "metadata", {}) or {})
            surface = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        page_content,
                        str(metadata.get("table_context") or ""),
                        str(metadata.get("table_row_labels_text") or ""),
                        str(metadata.get("table_value_labels_text") or ""),
                        str(metadata.get("table_summary_text") or ""),
                    )
                    if part
                )
            )
            surface = _strip_rerank_metadata(surface) or surface
            if not surface:
                continue
            surface_lower = surface.lower()
            matched_terms = sorted(term for term in focus_terms_lower if term in surface_lower)
            if selected_ids and focus_terms_lower and not matched_terms:
                continue
            snippet_terms = matched_terms or list(focus_terms_lower)
            snippet = self._extract_driver_snippet(surface, snippet_terms) if snippet_terms else ""
            snippet = _normalise_spaces(snippet or surface[:360])
            if not snippet:
                continue
            anchor = self._build_source_anchor(metadata)
            dedupe_key = _normalise_spaces(f"{anchor} {snippet}")
            if dedupe_key and dedupe_key in seen_surfaces:
                continue
            score = float(len(matched_terms) * 4)
            block_type = str(metadata.get("block_type") or "").strip().lower()
            if block_type == "table":
                score += 1.0
            try:
                score += min(float(item[1] or 0.0), 1.0) if isinstance(item, (tuple, list)) and len(item) > 1 else 0.0
            except (TypeError, ValueError):
                pass
            scored_candidates.append(
                (
                    score,
                    rank,
                    {
                        "source_anchor": anchor,
                        "claim": snippet,
                        "quote_span": snippet,
                        "support_level": "context",
                        "question_relevance": "medium" if matched_terms else "low",
                        "allowed_terms": sorted(_tokenize_terms(snippet))[:8],
                        "metadata": {
                            **metadata,
                            "missing_decision_context": True,
                            "query_focus_hits": matched_terms,
                        },
                    },
                )
            )

        scored_candidates.sort(key=lambda row: (-row[0], row[1]))
        selected_ids: List[str] = []
        for _score, _rank, candidate in scored_candidates[: max(1, limit)]:
            dedupe_key = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        candidate.get("source_anchor"),
                        candidate.get("claim"),
                        candidate.get("quote_span"),
                    )
                )
            )
            if dedupe_key and dedupe_key in seen_surfaces:
                continue
            if dedupe_key:
                seen_surfaces.add(dedupe_key)
            evidence_id = f"missing_decision_context::{len(selected_ids) + 1:03d}"
            while evidence_id in existing_ids:
                evidence_id = f"missing_decision_context::{len(selected_ids) + len(existing_ids) + 1:03d}"
            existing_ids.add(evidence_id)
            selected_ids.append(evidence_id)
            candidate["evidence_id"] = evidence_id
            updated.append(candidate)
        return updated, selected_ids

    def _append_retrieved_growth_driver_evidence_for_query(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        query: str,
        docs: List[Any],
    ) -> List[Dict[str, Any]]:
        query_text = _normalise_spaces(str(query or ""))
        if not query_text or not docs or not _query_requests_narrative_context(query_text):
            return [dict(item or {}) for item in (evidence_items or [])]

        driver_groups = self._narrative_driver_groups(query_text)
        if not driver_groups:
            return [dict(item or {}) for item in (evidence_items or [])]

        updated = [dict(item or {}) for item in (evidence_items or [])]
        existing_ids = {
            str(item.get("evidence_id") or "").strip()
            for item in updated
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        }
        existing_blob = _normalise_spaces(
            " ".join(
                str(value or "")
                for item in updated
                if isinstance(item, dict)
                for value in (
                    item.get("claim"),
                    item.get("quote_span"),
                    item.get("raw_row_text"),
                    " ".join(str(term or "") for term in (item.get("allowed_terms") or [])),
                )
            )
        ).lower()
        seen_surfaces = {
            _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        item.get("source_anchor"),
                        item.get("claim"),
                        item.get("quote_span"),
                    )
                )
            )
            for item in updated
            if isinstance(item, dict)
        }

        doc_rows: List[Dict[str, Any]] = []
        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            metadata = dict(getattr(doc, "metadata", {}) or {})
            text = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        getattr(doc, "page_content", None),
                        getattr(doc, "content", None),
                        metadata.get("table_context"),
                        metadata.get("table_summary_text"),
                    )
                )
            )
            if not text:
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
            doc_rows.append(
                {
                    "text": text,
                    "metadata": metadata,
                    "source_anchor": source_anchor,
                }
            )

        def _driver_surface_without_table_tail(surface: str, variants: List[str]) -> str:
            text = _normalise_spaces(str(surface or ""))
            if not text or "|" not in text:
                return text
            first_fragment = ""
            for fragment in text.split("|"):
                cleaned = _normalise_spaces(fragment)
                if cleaned and not first_fragment:
                    first_fragment = cleaned
                if cleaned and any(variant.lower() in cleaned.lower() for variant in variants):
                    return cleaned
            return first_fragment or text

        narrative_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ()))
        for group in driver_groups:
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _driver_surface_without_table_tail(str(group.get("phrase") or ""), variants)
            if not variants:
                continue
            if any(variant.lower() in existing_blob for variant in variants):
                continue

            best: Optional[tuple[int, str, Dict[str, Any]]] = None
            for row in doc_rows:
                text = str(row.get("text") or "")
                text_lower = text.lower()
                if not any(variant.lower() in text_lower for variant in variants):
                    continue
                snippet = self._extract_driver_snippet(text, variants)
                candidate_sentences = [
                    _normalise_spaces(sentence)
                    for sentence in (_split_narrative_sentences(snippet) or [snippet])
                    if _normalise_spaces(sentence)
                ]
                if not candidate_sentences:
                    continue
                for sentence in candidate_sentences:
                    sentence = _driver_surface_without_table_tail(sentence, variants)
                    sentence_lower = sentence.lower()
                    if not any(variant.lower() in sentence_lower for variant in variants):
                        continue
                    if _narrative_sentence_looks_table_noisy(sentence):
                        continue
                    if _narrative_sentence_looks_abbreviated_fragment(sentence, narrative_markers):
                        continue
                    score = sum(5 for variant in variants if variant.lower() in sentence_lower)
                    score += sum(1 for variant in variants if variant.lower() in text_lower)
                    if best is None or score > best[0]:
                        best = (score, sentence[:700], row)

            if best is None:
                continue

            _score, sentence, row = best
            dedupe_key = _normalise_spaces(f"{row.get('source_anchor') or ''} {sentence}")
            if dedupe_key and dedupe_key in seen_surfaces:
                continue
            if dedupe_key:
                seen_surfaces.add(dedupe_key)
            evidence_id = f"retrieved_driver::{len(updated) + 1:03d}"
            while evidence_id in existing_ids:
                evidence_id = f"retrieved_driver::{len(updated) + len(existing_ids) + 1:03d}"
            existing_ids.add(evidence_id)
            quote_span = sentence
            metadata = dict(row.get("metadata") or {})
            if phrase and extract_numeric_surface_candidates(sentence):
                quote_span = phrase
                metadata["raw_driver_quote_span"] = sentence
            updated.append(
                {
                    "evidence_id": evidence_id,
                    "source_anchor": str(row.get("source_anchor") or ""),
                    "claim": phrase or sentence,
                    "quote_span": quote_span,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "metadata": metadata,
                }
            )

        return updated

    def _build_dependency_operand_rows(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        input_bindings = [dict(item) for item in (active_subtask.get("inputs") or [])]
        if not input_bindings:
            return []

        producer_tasks = [
            *list(state.get("calc_subtasks") or []),
            *list(dict(state.get("semantic_plan") or {}).get("tasks") or []),
        ]
        sibling_rows = {
            str(row.get("task_id") or "").strip(): dict(row)
            for row in (state.get("subtask_results") or [])
            if str(row.get("task_id") or "").strip()
        }
        dependency_evidence_items = [
            item
            for row in sibling_rows.values()
            for item in list(row.get("runtime_evidence") or [])
        ]
        dependency_evidence_items.extend(list(state.get("evidence_items") or []))
        dependency_evidence_items.extend(list(state.get("runtime_evidence") or []))
        evidence_by_id = _evidence_items_by_id(dependency_evidence_items)
        evidence_pool = list(evidence_by_id.values())
        dependency_rows: List[Dict[str, Any]] = []
        for index, binding in enumerate(input_bindings, start=1):
            source_preference = [
                _normalise_spaces(str(item or "")).lower()
                for item in (binding.get("source_preference") or [])
                if _normalise_spaces(str(item or ""))
            ]
            if "task_output" not in source_preference:
                continue
            preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
            if not preferred_task_id:
                continue
            sibling_row = sibling_rows.get(preferred_task_id)
            if not sibling_row:
                continue
            sibling_evidence_by_id = _evidence_items_by_id(
                [dict(item) for item in (sibling_row.get("runtime_evidence") or []) if isinstance(item, dict)]
            )
            sibling_result = dict(sibling_row.get("calculation_result") or {})
            answer_slots = dict(sibling_result.get("answer_slots") or {})
            source_slot_name = _normalise_spaces(str(binding.get("source_slot") or "primary_value")) or "primary_value"
            source_slot = dict(answer_slots.get(source_slot_name) or {})
            source_slot_from_answer_slots = answer_slot_has_material(source_slot)
            producer_scope = resolve_dependency_producer_scope(
                binding,
                producer_tasks=producer_tasks,
            )
            if not answer_slot_has_material(source_slot):
                producer_task = dict(producer_scope.producer_task)
                if not producer_task:
                    producer_task = {
                        "task_id": preferred_task_id,
                        "metric_family": sibling_row.get("metric_family") or "concept_lookup",
                        "metric_label": sibling_row.get("metric_label") or binding.get("label") or "",
                        "operation_family": "lookup",
                        "required_operands": [dict(binding)],
                    }
                synthetic_result = _synthesize_lookup_answer_slot_from_prose(
                    active_subtask=producer_task,
                    answer=_normalise_spaces(
                        str(
                            sibling_row.get("answer")
                            or sibling_result.get("formatted_result")
                            or sibling_result.get("rendered_value")
                            or ""
                        )
                    ),
                    calculation_result=sibling_result,
                    selected_claim_ids=[
                        str(claim_id).strip()
                        for claim_id in (sibling_row.get("selected_claim_ids") or [])
                        if str(claim_id).strip()
                    ],
                )
                if synthetic_result:
                    sibling_result = synthetic_result
                    answer_slots = dict(sibling_result.get("answer_slots") or {})
                    source_slot = dict(answer_slots.get(source_slot_name) or answer_slots.get("primary_value") or {})
            if not answer_slot_has_material(source_slot) and sibling_result.get("result_value") is not None:
                source_slot = {
                    "status": "ok",
                    "role": source_slot_name,
                    "label": _normalise_spaces(str(binding.get("label") or sibling_row.get("metric_label") or "")),
                    "concept": _normalise_spaces(str(binding.get("concept") or "")),
                    "period": _normalise_spaces(str(binding.get("period") or "")),
                    "raw_value": _normalise_spaces(
                        str(sibling_result.get("rendered_value") or sibling_result.get("result_value") or "")
                    ),
                    "raw_unit": _normalise_spaces(str(sibling_result.get("result_unit") or "")),
                    "normalized_value": sibling_result.get("result_value"),
                    "normalized_unit": _normalise_spaces(str(sibling_result.get("normalized_unit") or "UNKNOWN")).upper()
                    or "UNKNOWN",
                    "rendered_value": _normalise_spaces(
                        str(sibling_result.get("rendered_value") or sibling_result.get("result_value") or "")
                    ),
                    "source_anchor": _normalise_spaces(str(sibling_result.get("source_anchor") or "")),
                    "source_row_ids": list(sibling_result.get("source_row_ids") or []),
                }
            if not answer_slot_has_material(source_slot):
                continue
            if not dependency_slot_matches_input(binding, source_slot, sibling_row=sibling_row, state=state):
                continue
            source_slot_from_answer_slots = True
            current_evidence = _evidence_item_for_operand_row(
                source_slot,
                sibling_evidence_by_id,
            ) or _evidence_item_for_operand_row(source_slot, evidence_by_id)
            current_metadata = dict((current_evidence or {}).get("metadata") or {})
            current_score = (
                score_direct_structured_lookup_evidence(
                    DirectStructuredLookupEvidenceScoreInput(
                        operand=binding,
                        evidence_item=current_evidence,
                    )
                ).score
                if current_evidence
                else 0.0
            )
            preferred_slot: Dict[str, Any] = {}
            preferred_score = 0.0

            def _candidate_slot_scope_conflicts_current(slot: Dict[str, Any]) -> bool:
                current_scope = known_consolidation_scope_value(
                    source_slot.get("consolidation_scope"),
                    current_metadata.get("consolidation_scope"),
                )
                if not current_scope:
                    return False
                candidate_evidence = _evidence_item_for_operand_row(slot, evidence_by_id)
                candidate_metadata = dict((candidate_evidence or {}).get("metadata") or {})
                candidate_scope = known_consolidation_scope_value(
                    slot.get("consolidation_scope"),
                    candidate_metadata.get("consolidation_scope"),
                )
                return bool(candidate_scope and candidate_scope != current_scope)

            if source_slot_from_answer_slots and "retrieval" in source_preference:
                source_raw_number = _parse_number_text(str(source_slot.get("raw_value") or ""))
                preferred_raw_number = None
                candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool(
                    binding,
                    evidence_pool,
                    state=state,
                )
                if candidate_slot and _candidate_slot_scope_conflicts_current(candidate_slot):
                    candidate_slot = {}
                    candidate_score = 0.0
                def _candidate_slot_has_sibling_input_context(slot: Dict[str, Any]) -> bool:
                    candidate_evidence = _evidence_item_for_operand_row(slot, evidence_by_id)
                    if not candidate_evidence:
                        return False
                    candidate_metadata = dict(candidate_evidence.get("metadata") or {})
                    table_surface = _normalise_spaces(
                        " ".join(
                            str(value or "")
                            for value in (
                                candidate_metadata.get("table_value_labels_text"),
                                candidate_metadata.get("table_row_labels_text"),
                                candidate_evidence.get("claim"),
                                candidate_evidence.get("quote_span"),
                                candidate_evidence.get("raw_row_text"),
                            )
                        )
                    )
                    if not table_surface:
                        return False
                    table_surface_compact = re.sub(r"\s+", "", table_surface)
                    binding_identity = dependency_binding_identity(binding)
                    for other_binding in input_bindings:
                        other_identity = dependency_binding_identity(other_binding)
                        if other_identity == binding_identity:
                            continue
                        sibling_surfaces = [
                            _normalise_spaces(str(surface or ""))
                            for surface in (
                                [other_binding.get("label")]
                                + list(other_binding.get("aliases") or [])
                                + list((other_binding.get("surface_contract") or {}).get("positive") or [])
                                + list(
                                    self._slot_metric_keys(
                                        {
                                            "label": str(other_binding.get("label") or ""),
                                            "concept": "",
                                        }
                                    )
                                )
                            )
                            if _normalise_spaces(str(surface or ""))
                        ]
                        if any(
                            surface in table_surface
                            or re.sub(r"\s+", "", surface) in table_surface_compact
                            for surface in sibling_surfaces
                        ):
                            return True
                    return False
                sibling_candidate_slot: Dict[str, Any] = {}
                sibling_candidate_score = 0.0
                for evidence_item in evidence_pool:
                    evidence = dict(evidence_item or {})
                    table_label_slot = self._lookup_value_from_table_label_metadata(binding, evidence)
                    table_label_score = table_label_metadata_lookup_score(table_label_slot, evidence)
                    if (
                        table_label_slot
                        and table_label_score > sibling_candidate_score
                        and _candidate_slot_has_sibling_input_context(table_label_slot)
                        and not _candidate_slot_scope_conflicts_current(table_label_slot)
                    ):
                        sibling_candidate_slot = table_label_slot
                        sibling_candidate_score = table_label_score
                if sibling_candidate_slot:
                    candidate_slot = sibling_candidate_slot
                    candidate_score = sibling_candidate_score
                if candidate_slot:
                    preferred_raw_number = _parse_number_text(str(candidate_slot.get("raw_value") or ""))
                candidate_has_sibling_context = bool(candidate_slot) and _candidate_slot_has_sibling_input_context(candidate_slot)
                candidate_value_matches_task_output = bool(
                    preferred_raw_number is not None
                    and source_raw_number is not None
                    and abs(float(source_raw_number) - float(preferred_raw_number)) <= 1e-6
                )
                candidate_value_compatible_with_task_output = bool(
                    candidate_slot and not operand_row_values_materially_conflict(source_slot, candidate_slot)
                )

                def _sibling_candidate_can_repair_task_output(slot: Dict[str, Any]) -> bool:
                    if not slot or not candidate_has_sibling_context:
                        return False
                    candidate_evidence = _evidence_item_for_operand_row(slot, evidence_by_id)
                    current_evidence_id = _normalise_spaces(str((current_evidence or {}).get("evidence_id") or ""))
                    candidate_evidence_id = _normalise_spaces(str((candidate_evidence or {}).get("evidence_id") or ""))
                    if (
                        current_evidence_id
                        and current_evidence_id == candidate_evidence_id
                        and _operand_slot_has_evidence_surface_match(
                            slot,
                            candidate_evidence,
                            binding,
                            metric_label=str(sibling_row.get("metric_label") or binding.get("label") or ""),
                        )
                    ):
                        return True
                    binding_role = _normalise_spaces(str(binding.get("role") or "")).lower()
                    if binding_role in {"current_period", "prior_period", "minuend", "subtrahend"}:
                        candidate_metadata = dict((candidate_evidence or {}).get("metadata") or {})
                        header_text = _normalise_spaces(str(candidate_metadata.get("table_header_context") or ""))
                        period_presence_pattern = str(
                            CALCULATION_SLOT_POLICY.get("period_presence_pattern")
                            or KOREAN_PERIOD_PREFIX_RE_FRAGMENT
                        )
                        fiscal_period_presence_pattern = str(
                            CALCULATION_SLOT_POLICY.get("fiscal_period_presence_pattern") or ""
                        )
                        has_period_table_surface = bool(
                            len(candidate_metadata.get("period_labels") or []) > 1
                            or re.search(period_presence_pattern, header_text)
                            or re.search(r"\b20\d{2}\b", header_text)
                            or (
                                fiscal_period_presence_pattern
                                and re.search(fiscal_period_presence_pattern, header_text)
                            )
                        )
                        if has_period_table_surface and _operand_slot_has_evidence_surface_match(
                            slot,
                            candidate_evidence,
                            binding,
                            metric_label=str(sibling_row.get("metric_label") or binding.get("label") or ""),
                        ):
                            return True
                    try:
                        source_normalized = source_slot.get("normalized_value")
                        candidate_normalized = slot.get("normalized_value")
                        source_is_zero = (
                            source_raw_number is not None
                            and abs(float(source_raw_number)) <= 1e-12
                        ) or (
                            source_normalized is not None
                            and abs(float(source_normalized)) <= 1e-12
                        )
                        candidate_is_nonzero = (
                            preferred_raw_number is not None
                            and abs(float(preferred_raw_number)) > 1e-12
                        ) or (
                            candidate_normalized is not None
                            and abs(float(candidate_normalized)) > 1e-12
                        )
                    except (TypeError, ValueError):
                        source_is_zero = False
                        candidate_is_nonzero = False
                    if source_is_zero and candidate_is_nonzero:
                        return True
                    render_policy = dict(CALCULATION_RENDER_POLICY)
                    krw_normalized_unit = _normalise_spaces(
                        str(render_policy.get("krw_normalized_unit") or "KRW")
                    ).upper()
                    source_normalized_unit = _normalise_spaces(
                        str(source_slot.get("normalized_unit") or "")
                    ).upper()
                    candidate_normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
                    if source_normalized_unit != krw_normalized_unit or candidate_normalized_unit != krw_normalized_unit:
                        return False
                    krw_display_units = {
                        _normalise_spaces(str(unit or ""))
                        for unit in dict(render_policy.get("krw_display_unit_scales") or {})
                        if _normalise_spaces(str(unit or ""))
                    }
                    source_unit = _normalise_spaces(str(source_slot.get("raw_unit") or ""))
                    candidate_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
                    return bool(
                        source_unit
                        and candidate_unit
                        and source_unit != candidate_unit
                        and source_unit in krw_display_units
                        and candidate_unit in krw_display_units
                    )
                allow_preferred_slot_lookup = (
                    bool(candidate_slot)
                    and source_raw_number is not None
                    and (preferred_raw_number is not None or candidate_has_sibling_context)
                    and (
                        candidate_value_matches_task_output
                        or (candidate_has_sibling_context and candidate_value_compatible_with_task_output)
                        or _sibling_candidate_can_repair_task_output(candidate_slot)
                    )
                )
                if allow_preferred_slot_lookup:
                    preferred_slot, preferred_score = candidate_slot, candidate_score
                    if candidate_has_sibling_context and preferred_score <= current_score:
                        preferred_score = current_score + 0.1
            else:
                preferred_slot, preferred_score = self._best_direct_lookup_slot_from_evidence_pool(
                    binding,
                    evidence_pool,
                    state=state,
                )
                if preferred_slot and _candidate_slot_scope_conflicts_current(preferred_slot):
                    preferred_slot = {}
                    preferred_score = 0.0
            if preferred_slot and preferred_score > current_score:
                preferred_evidence = _evidence_item_for_operand_row(preferred_slot, evidence_by_id)
                preferred_raw = _normalise_spaces(str(preferred_slot.get("raw_value") or ""))
                current_raw = _normalise_spaces(str(source_slot.get("raw_value") or ""))
                preferred_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
                current_unit = _normalise_spaces(str(source_slot.get("raw_unit") or ""))
                preferred_normalized = preferred_slot.get("normalized_value")
                current_normalized = source_slot.get("normalized_value")
                normalized_differs = False
                try:
                    if preferred_normalized is not None and current_normalized is not None:
                        normalized_differs = abs(float(preferred_normalized) - float(current_normalized)) > 1e-6
                    else:
                        normalized_differs = preferred_normalized != current_normalized
                except (TypeError, ValueError):
                    normalized_differs = preferred_normalized != current_normalized
                if preferred_raw and (
                    preferred_raw != current_raw
                    or preferred_unit != current_unit
                    or normalized_differs
                ):
                    preferred_surface_matches = _operand_slot_has_evidence_surface_match(
                        preferred_slot,
                        preferred_evidence,
                        binding,
                        metric_label=str(sibling_row.get("metric_label") or binding.get("label") or ""),
                    )
                    if preferred_surface_matches:
                        source_slot = preferred_slot
            raw_unit, normalized_unit = infer_dependency_row_unit(source_slot, sibling_result)
            normalized_value = source_slot.get("normalized_value")
            if normalized_value is None:
                normalized_value = sibling_result.get("result_value")
            matched_operand_candidate: Dict[str, Any] = {}
            for operand_row in list(sibling_row.get("calculation_operands") or []):
                operand_candidate = dict(operand_row or {})
                if not _operand_row_matches_requirement(operand_candidate, binding):
                    continue
                candidate_normalized = operand_candidate.get("normalized_value")
                candidate_raw = _normalise_spaces(str(operand_candidate.get("raw_value") or ""))
                slot_raw = _normalise_spaces(str(source_slot.get("raw_value") or source_slot.get("rendered_value") or ""))
                values_match = False
                try:
                    if normalized_value is not None and candidate_normalized is not None:
                        values_match = abs(float(normalized_value) - float(candidate_normalized)) <= 1e-6
                except (TypeError, ValueError):
                    values_match = False
                if not values_match and candidate_raw and slot_raw:
                    values_match = candidate_raw == slot_raw
                if values_match or not matched_operand_candidate:
                    matched_operand_candidate = operand_candidate
                if values_match:
                    break
            if matched_operand_candidate:
                candidate_normalized = matched_operand_candidate.get("normalized_value")
                candidate_raw = _normalise_spaces(str(matched_operand_candidate.get("raw_value") or ""))
                slot_raw = _normalise_spaces(str(source_slot.get("raw_value") or source_slot.get("rendered_value") or ""))
                candidate_conflicts = False
                try:
                    if normalized_value is not None and candidate_normalized is not None:
                        candidate_conflicts = abs(float(normalized_value) - float(candidate_normalized)) > 1e-6
                except (TypeError, ValueError):
                    candidate_conflicts = False
                if not candidate_conflicts and candidate_raw and slot_raw:
                    candidate_conflicts = candidate_raw != slot_raw
                if candidate_conflicts and (candidate_normalized is not None or candidate_raw):
                    updated_slot = dict(source_slot)
                    for key in (
                        "label",
                        "concept",
                        "period",
                        "raw_value",
                        "raw_unit",
                        "normalized_value",
                        "normalized_unit",
                        "rendered_value",
                        "source_row_id",
                        "source_row_ids",
                        "source_anchor",
                        "consolidation_scope",
                        "statement_type",
                        "table_source_id",
                    ):
                        value = matched_operand_candidate.get(key)
                        if value not in (None, "", []):
                            updated_slot[key] = value
                    updated_slot["status"] = updated_slot.get("status") or "ok"
                    updated_slot["role"] = (
                        updated_slot.get("role")
                        or matched_operand_candidate.get("matched_operand_role")
                        or binding.get("role")
                        or source_slot_name
                    )
                    source_slot = updated_slot
                    raw_unit, normalized_unit = infer_dependency_row_unit(source_slot, sibling_result)
                    normalized_value = source_slot.get("normalized_value")
                    if normalized_value is None:
                        normalized_value = sibling_result.get("result_value")
            source_row_ids = _clean_source_row_ids([
                f"task_output:{preferred_task_id}",
                source_slot.get("source_row_id"),
                source_slot.get("source_row_ids"),
                matched_operand_candidate.get("source_row_id"),
                matched_operand_candidate.get("source_row_ids"),
                sibling_result.get("source_row_ids"),
            ])
            selected_evidence = _evidence_item_for_operand_row(
                source_slot,
                sibling_evidence_by_id,
            ) or _evidence_item_for_operand_row(source_slot, evidence_by_id)
            selected_metadata = dict((selected_evidence or current_evidence or {}).get("metadata") or {})
            source_anchor = _normalise_spaces(str(source_slot.get("source_anchor") or ""))
            if not source_anchor and selected_evidence:
                source_anchor = _normalise_spaces(str(selected_evidence.get("source_anchor") or ""))
            if not source_anchor:
                for evidence_id in source_row_ids:
                    if str(evidence_id).startswith("task_output:"):
                        continue
                    evidence = evidence_by_id.get(evidence_id)
                    if not evidence:
                        continue
                    source_anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
                    if source_anchor:
                        break
            if not source_anchor:
                source_anchor = _normalise_spaces(str(matched_operand_candidate.get("source_anchor") or ""))
            if not source_anchor:
                source_anchor = _normalise_spaces(str(sibling_result.get("source_anchor") or ""))
            dependency_row = {
                "operand_id": f"dep_{preferred_task_id}_{index:03d}",
                "evidence_id": f"task_output:{preferred_task_id}",
                "source_row_id": source_row_ids[0] if source_row_ids else f"task_output:{preferred_task_id}",
                "source_row_ids": source_row_ids or [f"task_output:{preferred_task_id}"],
                "source_anchor": source_anchor,
                "label": _normalise_spaces(
                    str(binding.get("label") or source_slot.get("label") or sibling_row.get("metric_label") or "")
                ),
                "raw_value": _normalise_spaces(
                    str(
                        source_slot.get("raw_value")
                        or source_slot.get("rendered_value")
                        or sibling_result.get("rendered_value")
                        or ""
                    )
                ),
                "raw_unit": raw_unit,
                "normalized_value": normalized_value,
                "normalized_unit": normalized_unit,
                "rendered_value": _normalise_spaces(str(source_slot.get("rendered_value") or "")),
                "period": _normalise_spaces(str(source_slot.get("period") or binding.get("period") or "")),
                "consolidation_scope": _normalise_spaces(
                    str(
                        source_slot.get("consolidation_scope")
                        or matched_operand_candidate.get("consolidation_scope")
                        or known_consolidation_scope_value(selected_metadata.get("consolidation_scope"))
                        or selected_metadata.get("consolidation_scope")
                        or ""
                    )
                ),
                "statement_type": _normalise_spaces(
                    str(
                        source_slot.get("statement_type")
                        or matched_operand_candidate.get("statement_type")
                        or selected_metadata.get("statement_type")
                        or ""
                    )
                ),
                "table_source_id": _normalise_spaces(
                    str(
                        source_slot.get("table_source_id")
                        or matched_operand_candidate.get("table_source_id")
                        or selected_metadata.get("table_source_id")
                        or ""
                    )
                ),
                "value_role": _normalise_spaces(
                    str(source_slot.get("value_role") or matched_operand_candidate.get("value_role") or "")
                ),
                "aggregation_stage": _normalise_spaces(
                    str(source_slot.get("aggregation_stage") or matched_operand_candidate.get("aggregation_stage") or "")
                ),
                "aggregate_label": _normalise_spaces(
                    str(source_slot.get("aggregate_label") or matched_operand_candidate.get("aggregate_label") or "")
                ),
                "matched_operand_label": _normalise_spaces(str(binding.get("label") or "")),
                "matched_operand_concept": _normalise_spaces(str(binding.get("concept") or "")),
                "matched_operand_role": _normalise_spaces(str(binding.get("role") or "")),
                "binding_policy": dict(binding.get("binding_policy") or {}),
                "source_task_id": preferred_task_id,
                "source_slot": source_slot_name,
                "dependency_resolved": True,
            }
            dependency_row = repair_operand_normalization_from_rendered_unit(dependency_row)
            structured_provenance = self._structured_graph_provenance_for_dependency_operand(
                state,
                binding=binding,
                preferred_statement_types=producer_scope.preferred_statement_types,
                row=dependency_row,
            )
            if structured_provenance:
                dependency_row = adopt_dependency_structured_provenance(
                    DependencyStructuredProvenanceAdoptionInput(
                        dependency_row=dependency_row,
                        structured_provenance=structured_provenance,
                    )
                ).dependency_row
            source_evidence = _evidence_item_for_operand_row(dependency_row, evidence_by_id)
            dependency_rows.append(self._coerce_operand_row_from_evidence(dependency_row, source_evidence))
        return dependency_rows

    def _structured_graph_provenance_for_dependency_operand(
        self,
        state: FinancialAgentState,
        *,
        binding: Dict[str, Any],
        preferred_statement_types: Sequence[str],
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        graph = getattr(getattr(self, "vsm", None), "_structure_graph", {}) or {}
        nodes = dict(graph.get("nodes", {}) or {})
        if not nodes:
            return {}
        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if not raw_value:
            return {}
        raw_value_variants = {
            raw_value,
            re.sub(r"[,\s()]", "", raw_value),
            raw_value.replace("△", "-"),
        }
        raw_value_variants = {item for item in raw_value_variants if item}
        report_scope = dict(state.get("report_scope") or {})
        desired_scope = _desired_consolidation_scope(str(state.get("query") or ""), report_scope)
        preferred_statement_type_set = set(preferred_statement_types)
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        note_markers = tuple(str(item).lower() for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        best_payload: Dict[str, Any] = {}
        best_score = -1
        for chunk_uid, node in nodes.items():
            node_data = dict(node or {})
            metadata = dict(node_data.get("metadata") or {})
            if report_scope.get("rcept_no") and str(metadata.get("rcept_no") or "") != str(report_scope.get("rcept_no")):
                continue
            if report_scope.get("year") and str(metadata.get("year") or "") != str(report_scope.get("year")):
                continue
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("table_value_labels_text"),
                        metadata.get("table_row_labels_text"),
                        node_data.get("text"),
                    )
                )
            )
            if not surface:
                continue
            compact_surface = re.sub(r"[,\s()]", "", surface)
            if not any(value in surface or value in compact_surface for value in raw_value_variants):
                continue
            if not _operand_text_match(surface, binding):
                continue
            node_scope = _normalise_spaces(str(metadata.get("consolidation_scope") or ""))
            if desired_scope in {"consolidated", "separate"} and node_scope and node_scope != desired_scope:
                continue
            score = 10
            statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
            if statement_type and statement_type in preferred_statement_type_set:
                score += 6
            elif preferred_statement_type_set and statement_type == "notes":
                score -= 4
            if node_scope and node_scope == desired_scope:
                score += 4
            section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
            section_path_lower = section_path.lower()
            if section_path and not any(marker in section_path_lower for marker in note_markers) and "note" not in section_path_lower:
                score += 2
            if score <= best_score:
                continue
            payload = {
                "source_anchor": self._build_source_anchor(metadata),
                "chunk_uid": str(chunk_uid),
                "unit_hint": _normalise_spaces(str(metadata.get("unit_hint") or "")),
                "consolidation_scope": node_scope,
                "statement_type": statement_type,
                "table_source_id": _normalise_spaces(str(metadata.get("table_source_id") or "")),
            }
            if not payload["source_anchor"]:
                continue
            best_payload = payload
            best_score = score
        return best_payload

    def _dependency_binding_resolution_state(self, state: FinancialAgentState) -> Dict[str, Any]:
        return summarize_dependency_bindings(
            task_output_input_bindings(state),
            self._build_dependency_operand_rows(state),
        )

    def _infer_planner_feedback_from_answer_slots(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            status = str(
                row.get("status")
                or (row.get("calculation_result") or {}).get("status")
                or ""
            ).strip().lower()
            if (
                (operation_family == "narrative_summary" or metric_family == "narrative_summary")
                and _normalise_spaces(str(row.get("answer") or ""))
                and re.search(r"\d", str(row.get("answer") or ""))
            ):
                continue
            if status and status != "ok":
                if (
                    self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                    or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                ):
                    continue
                gap = material_gap_feedback_for_subtask_result(row)
                if gap:
                    if self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results):
                        continue
                    return gap
                metric_label = _normalise_spaces(
                    str(
                        row.get("metric_label")
                        or row.get("task_id")
                        or CALCULATION_FEEDBACK_POLICY.get("default_metric_label")
                        or ""
                    )
                )
                generic_gap = str(CALCULATION_FEEDBACK_POLICY.get("generic_missing_material_template") or "").format(
                    metric_label=metric_label
                )
                if self._feedback_gap_is_satisfied_by_derived_slots(generic_gap, ordered_results):
                    continue
                return generic_gap

            gap = material_gap_feedback_for_subtask_result(row)
            if gap and (
                self._sibling_lookup_gap_is_satisfied(row, ordered_results)
                or self._lookup_gap_is_satisfied_by_sibling_slots(row, ordered_results)
                or self._feedback_gap_is_satisfied_by_derived_slots(gap, ordered_results)
            ):
                continue
            if gap:
                return gap
        return ""

    def _aggregate_result_operation_family(self, row: Dict[str, Any]) -> str:
        return _aggregate_result_operation_family(row)

    def _aggregate_dependency_source_slot_by_task_id(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> Dict[str, Dict[str, Any]]:
        lookup_task_ids: set[str] = set()
        metric_label_by_task_id: Dict[str, str] = {}
        for row in ordered_results:
            if not isinstance(row, dict):
                continue
            task_id = _normalise_spaces(str(row.get("task_id") or ""))
            if not task_id:
                continue
            metric_label_by_task_id[task_id] = _normalise_spaces(str(row.get("metric_label") or ""))
            operation_family = _normalise_spaces(
                str(row.get("operation_family") or self._aggregate_result_operation_family(row) or "")
            ).lower()
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family in {"lookup", "single_value"} or metric_family in {"concept_lookup", "generic_numeric"}:
                lookup_task_ids.add(task_id)
        source_slots = {
            task_id: slot
            for task_id, slot in aggregate_source_slot_by_task_id(ordered_results).items()
            if task_id in lookup_task_ids
        }
        dependency_slots = build_dependency_lookup_slots_by_task(
            ordered_results,
            {},
            operation_family_for_result=self._aggregate_result_operation_family,
            slot_has_material=answer_slot_has_material,
        )
        source_slots.update(dependency_slots)
        for task_id, slot in list(source_slots.items()):
            metric_label = metric_label_by_task_id.get(task_id, "")
            if metric_label and not slot.get("metric_label"):
                slot = dict(slot)
                slot["metric_label"] = metric_label
                source_slots[task_id] = slot
        return source_slots

    def _ratio_answer_from_dependency_source_slots(
        self,
        row: Dict[str, Any],
        source_slot_by_task_id: Dict[str, Dict[str, Any]],
        *,
        query: str = "",
    ) -> str:
        source_slots = {
            task_id: dict(slot)
            for task_id, slot in dict(source_slot_by_task_id or {}).items()
            if task_id and answer_slot_has_material(dict(slot or {}))
        }
        if len(source_slots) < 2:
            return ""
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        metric_label = _normalise_spaces(
            str(
                answer_slots.get("metric_label")
                or calculation_result.get("metric_label")
                or row.get("metric_label")
                or ""
            )
        )

        numerator_seeds, denominator_seeds, ungrouped_seeds = ratio_rebuild_component_seeds(
            row,
            calculation_result,
            answer_slots,
        )
        if not numerator_seeds:
            numerator_seeds = list(ungrouped_seeds)
        if not denominator_seeds and metric_label:
            denominator_seeds = [{"role": "denominator_1", "label": metric_label}]
        numerator_seed = numerator_seeds[0] if numerator_seeds else {}
        denominator_seed = denominator_seeds[0] if denominator_seeds else {}
        if not numerator_seed or not denominator_seed:
            return ""
        numerator_task_id, numerator_source, numerator_seed, _numerator_score = best_dependency_source_for_seed(
            numerator_seed,
            "numerator_1",
            source_slots=source_slots,
        )
        if not numerator_task_id or not numerator_source:
            return ""
        denominator_task_id, denominator_source, denominator_seed, _denominator_score = (
            best_dependency_source_for_seed(
                denominator_seed,
                "denominator_1",
                source_slots=source_slots,
                excluded_task_ids={numerator_task_id},
            )
        )
        if not denominator_task_id or not denominator_source:
            return ""
        if metric_label:
            metric_seed = {"role": "denominator_1", "label": metric_label}
            (
                metric_denominator_task_id,
                metric_denominator_source,
                metric_denominator_seed,
                metric_denominator_score,
            ) = best_dependency_source_for_seed(
                metric_seed,
                "denominator_1",
                source_slots=source_slots,
                excluded_task_ids={numerator_task_id},
            )
            current_metric_score = dependency_source_slot_match_score(
                denominator_source,
                metric_seed,
                "denominator_1",
            )
            if (
                metric_denominator_task_id
                and metric_denominator_task_id != denominator_task_id
                and metric_denominator_score >= 3
                and current_metric_score == 0
            ):
                denominator_task_id = metric_denominator_task_id
                denominator_source = metric_denominator_source
                denominator_seed = metric_denominator_seed
        numerator_slot = component_slot_from_dependency_source(
            numerator_seed,
            numerator_source,
            numerator_task_id,
            "numerator_1",
        )
        denominator_slot = component_slot_from_dependency_source(
            denominator_seed,
            denominator_source,
            denominator_task_id,
            "denominator_1",
        )
        if _ratio_operand_rows_collapse_to_same_slot([numerator_slot, denominator_slot]):
            return ""
        numerator_value = financial_answer_slots.coerce_slot_numeric(numerator_slot.get("normalized_value"))
        denominator_value = financial_answer_slots.coerce_slot_numeric(denominator_slot.get("normalized_value"))
        if numerator_value is None or denominator_value in {None, 0}:
            return ""
        projection = calculation_rendering.ratio_result_projection(
            numerator_value=float(numerator_value),
            denominator_value=float(denominator_value),
            query=query,
            metric_label=metric_label,
        )
        result_value = float(projection["result_value"])
        result_unit = str(projection["result_unit"])
        normalized_unit = str(projection["normalized_unit"])
        rendered_value = str(projection["rendered_value"])
        source_row_ids = _clean_source_row_ids([
            numerator_slot.get("source_row_id"),
            numerator_slot.get("source_row_ids"),
            denominator_slot.get("source_row_id"),
            denominator_slot.get("source_row_ids"),
        ])
        rebuilt_result = build_dependency_ratio_result_projection(
            DependencyRatioResultProjectionInput(
                calculation_result=calculation_result,
                answer_slots=answer_slots,
                metric_label=metric_label,
                numerator_slot=numerator_slot,
                denominator_slot=denominator_slot,
                result_value=result_value,
                result_unit=result_unit,
                normalized_unit=normalized_unit,
                rendered_value=rendered_value,
                source_row_ids=source_row_ids,
            )
        ).calculation_result
        return self._compact_ratio_answer(
            {
                "active_subtask": {"metric_label": metric_label},
                "resolved_calculation_trace": {
                    "calculation_operands": [numerator_slot, denominator_slot],
                    "calculation_plan": {
                        "status": "ok",
                        "operation": "ratio",
                        "result_unit": result_unit,
                    },
                    "calculation_result": rebuilt_result,
                },
            },
            rebuilt_result,
        )

    def _promote_stronger_nested_aggregate_results(
        self,
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
            if self._aggregate_result_operation_family(row) != "aggregate_subtasks":
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            for nested_row in self._nested_subtask_rows(calculation_result):
                nested_task_id = _normalise_spaces(str(nested_row.get("task_id") or ""))
                if not nested_task_id:
                    continue
                if self._aggregate_result_operation_family(nested_row) == "aggregate_subtasks":
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
                    and self._aggregate_result_operation_family(current_row) == self._aggregate_result_operation_family(nested_row)
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

    def _sync_projection_subtask_results_with_nested_promotions(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
        final_answer: str,
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any]]:
        projection_subtask_results = [
            dict(item)
            for item in list((aggregate_projection.get("calculation_result") or {}).get("subtask_results") or [])
            if isinstance(item, dict)
        ]
        if not projection_subtask_results:
            return ordered_results, aggregate_projection
        promoted_results = self._promote_stronger_nested_aggregate_results(projection_subtask_results)
        promoted_projection = self._rebuild_aggregate_projection(promoted_results, final_answer)
        aligned_results = self._align_lookup_results_with_dependency_projection(
            promoted_results,
            state,
            promoted_projection,
        )
        if promoted_results == projection_subtask_results and aligned_results == promoted_results:
            return ordered_results, aggregate_projection
        existing_by_task_id = {
            _normalise_spaces(str(row.get("task_id") or "")): dict(row)
            for row in ordered_results
            if _normalise_spaces(str(row.get("task_id") or ""))
        }
        preserved_results: List[Dict[str, Any]] = []
        for row in aligned_results:
            task_id = _normalise_spaces(str(row.get("task_id") or ""))
            existing = dict(existing_by_task_id.get(task_id) or {})
            if not existing:
                preserved_results.append(dict(row))
                continue
            merged = dict(row)
            for key in (
                "promoted_from_nested_aggregate",
                "aligned_from_source_task_slots",
                "aligned_from_dependency_projection",
                "runtime_evidence",
                "artifact_ids",
                "selected_claim_ids",
                "source_evidence_ids",
                "source_row_ids",
            ):
                if existing.get(key) and not merged.get(key):
                    merged[key] = existing.get(key)
            preserved_results.append(merged)
        preserved_results = synchronize_nested_aggregate_subtask_rows(
            AggregateNestedSubtaskSynchronizationInput(
                ordered_results=preserved_results,
            )
        ).ordered_results
        return preserved_results, self._rebuild_aggregate_projection(preserved_results, final_answer)

    def _preserve_policy_required_realized_context(
        self,
        answer: str,
        *,
        query: str,
        docs: List[Any],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not docs or not _query_requests_narrative_context(query):
            return answer_text
        active_policies = self._active_narrative_policies_for_query(query)
        if not active_policies:
            return answer_text
        additions: List[str] = []
        for policy in active_policies:
            required_terms = narrative_policy_terms([policy], "required_realized_terms")
            if not required_terms:
                continue
            if any(term.lower() in answer_text.lower() for term in required_terms):
                continue
            focus_terms = narrative_policy_terms([policy], "focus_terms")
            realized_terms = narrative_policy_terms([policy], "realized_terms")
            scored_docs: List[tuple[int, str]] = []
            for item in docs or []:
                doc = item[0] if isinstance(item, (tuple, list)) and item else item
                metadata = dict(getattr(doc, "metadata", {}) or {})
                surface = _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            str(getattr(doc, "page_content", "") or ""),
                            str(metadata.get("table_context") or ""),
                            str(metadata.get("table_row_labels_text") or ""),
                            str(metadata.get("table_value_labels_text") or ""),
                            str(metadata.get("table_summary_text") or ""),
                        )
                        if part
                    )
                )
                surface_lower = surface.lower()
                required_hits = sum(1 for term in required_terms if term.lower() in surface_lower)
                if not required_hits:
                    continue
                focus_hits = sum(1 for term in focus_terms if term.lower() in surface_lower)
                realized_hits = sum(1 for term in realized_terms if term.lower() in surface_lower)
                snippet = policy_required_realized_snippet_from_doc(doc=doc, policy=policy)
                if not snippet:
                    continue
                score = required_hits * 8 + min(focus_hits, 4) * 2 + min(realized_hits, 4) * 3
                if str(metadata.get("block_type") or "").strip().lower() == "table":
                    score += 2
                if str(metadata.get("period_focus") or "").strip().lower() == "current":
                    score += 2
                scored_docs.append((score, snippet))
            if not scored_docs:
                continue
            scored_docs.sort(key=lambda item: item[0], reverse=True)
            addition = _normalise_spaces(scored_docs[0][1])
            if addition and addition not in answer_text and addition not in additions:
                additions.append(addition)
        if not additions:
            return answer_text
        return _normalise_spaces(" ".join([answer_text, *additions]))

    def _prune_nonfocus_numeric_narrative_sentences(
        self,
        answer: str,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not ordered_results or not _query_requests_narrative_context(query):
            return answer_text
        if not any(row_is_narrative_summary(row) for row in ordered_results):
            return answer_text
        if not any(self._aggregate_result_operation_family(row) == "growth_rate" for row in ordered_results):
            return answer_text

        active_policies = [
            policy
            for policy in self._active_narrative_policies_for_query(query)
            if narrative_policy_terms([policy], "required_realized_terms")
        ]
        if not active_policies:
            return answer_text
        focus_terms = list(
            dict.fromkeys(
                [
                    *narrative_policy_terms(active_policies, "focus_terms"),
                    *narrative_policy_terms(active_policies, "required_realized_terms"),
                ]
            )
        )
        if not focus_terms:
            return answer_text

        def _is_growth_supported_sentence(sentence: str) -> bool:
            cleaned = _normalise_spaces(sentence)
            if not cleaned:
                return False
            for row in ordered_results:
                if self._aggregate_result_operation_family(row) != "growth_rate":
                    continue
                if growth_row_has_conflicting_periods(row):
                    continue
                complete_answer = compose_complete_growth_numeric_answer(row, ordered_results)
                required_values = growth_required_display_values(row, ordered_results, evidence_items)
                if complete_answer and (cleaned in complete_answer or complete_answer in cleaned):
                    return True
                required_hits = [value for value in required_values if value and value in cleaned]
                if required_hits and not growth_sentence_has_untraced_material_numeric(
                    cleaned,
                    complete_answer,
                    required_values,
                    evidence_items,
                ):
                    return True
            return False

        kept: List[str] = []
        changed = False
        for sentence in _split_narrative_sentences(answer_text):
            cleaned = _normalise_spaces(sentence)
            if not cleaned:
                continue
            if not re.search(r"\d", cleaned):
                kept.append(cleaned)
                continue
            lowered = cleaned.lower()
            if any(term and term.lower() in lowered for term in focus_terms):
                kept.append(cleaned)
                continue
            if _is_growth_supported_sentence(cleaned):
                kept.append(cleaned)
                continue
            changed = True
        if not changed or not kept:
            return answer_text
        return _normalise_spaces(" ".join(kept))

    def _preserve_policy_required_context_in_narrative_results(
        self,
        ordered_results: List[Dict[str, Any]],
        *,
        query: str,
        docs: List[Any],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, Any]]:
        if not ordered_results or not docs or not _query_requests_narrative_context(query):
            return ordered_results
        changed = False
        updated_results: List[Dict[str, Any]] = []
        for row in ordered_results:
            row_copy = dict(row)
            if not row_is_narrative_summary(row_copy):
                updated_results.append(row_copy)
                continue
            row_answer = _normalise_spaces(
                str(
                    row_copy.get("answer")
                    or (row_copy.get("calculation_result") or {}).get("formatted_result")
                    or (row_copy.get("calculation_result") or {}).get("rendered_value")
                    or ""
                )
            )
            if not row_answer:
                updated_results.append(row_copy)
                continue
            preserved = self._preserve_policy_required_realized_context(
                row_answer,
                query=query,
                docs=docs,
            )
            pruned = self._prune_nonfocus_numeric_narrative_sentences(
                preserved,
                query=query,
                ordered_results=ordered_results,
                evidence_items=evidence_items,
            )
            if pruned != row_answer:
                row_copy["answer"] = pruned
                calculation_result = dict(row_copy.get("calculation_result") or {})
                if calculation_result:
                    calculation_result["formatted_result"] = pruned
                    calculation_result["rendered_value"] = pruned
                    row_copy["calculation_result"] = calculation_result
                changed = True
            updated_results.append(row_copy)
        return updated_results if changed else ordered_results

    def _preserve_source_visible_query_terms(
        self,
        answer: str,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        docs: List[Any],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return answer_text

        marker_groups: List[List[str]] = []
        for group in self._query_focus_marker_groups(query):
            group_markers: List[str] = []
            for variant in group.get("variants") or []:
                marker = _normalise_spaces(str(variant or ""))
                if not marker:
                    continue
                if len(marker) > 32 or not re.search(r"[A-Z]", marker):
                    continue
                group_markers.append(marker)
            if group_markers:
                marker_groups.append(group_markers)
        marker_variants: List[str] = []
        for group in marker_groups:
            for marker in group:
                if marker.lower() not in {item.lower() for item in marker_variants}:
                    marker_variants.append(marker)
        if not marker_variants:
            return answer_text

        support_parts: List[str] = []
        for item in evidence_items or []:
            evidence = dict(item or {})
            metadata = dict(evidence.get("metadata") or {})
            support_parts.extend(
                str(value or "")
                for value in (
                    evidence.get("claim"),
                    evidence.get("quote_span"),
                    evidence.get("raw_row_text"),
                    " ".join(str(term or "") for term in (evidence.get("allowed_terms") or [])),
                    metadata.get("table_context"),
                    metadata.get("table_header_context"),
                    metadata.get("table_summary_text"),
                    metadata.get("text"),
                )
            )
        for row in ordered_results or []:
            calculation_result = dict(row.get("calculation_result") or {})
            support_parts.extend(
                str(value or "")
                for value in (
                    row.get("answer"),
                    row.get("metric_label"),
                    calculation_result.get("formatted_result"),
                    calculation_result.get("rendered_value"),
                )
            )
        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) and item else item
            metadata = getattr(doc, "metadata", {}) or {}
            support_parts.extend(
                str(value or "")
                for value in (
                    getattr(doc, "page_content", ""),
                    metadata.get("table_context"),
                    metadata.get("table_header_context"),
                    metadata.get("table_summary_text"),
                    metadata.get("section_path"),
                    metadata.get("local_heading"),
                )
            )

        support_blob = _normalise_spaces(" ".join(part for part in support_parts if part)).lower()
        grounded_blob = _normalise_spaces(f"{answer_text} {support_blob}").lower()
        matched_concepts = get_financial_ontology().match_concepts(query)
        concept_surfaces_by_key: Dict[str, List[str]] = {}
        for concept in matched_concepts:
            concept_key = str(concept.get("key") or "").strip()
            if not concept_key:
                continue
            surfaces = [
                _normalise_spaces(str(surface or ""))
                for surface in [
                    concept.get("display_name"),
                    *(concept.get("aliases") or []),
                    *(concept.get("keywords") or []),
                ]
                if _normalise_spaces(str(surface or ""))
            ]
            if surfaces:
                concept_surfaces_by_key[concept_key] = list(dict.fromkeys(surfaces))

        def _marker_has_ontology_support(marker: str, siblings: List[str]) -> bool:
            marker_lower = marker.lower()
            sibling_lowers = [sibling.lower() for sibling in siblings if sibling]
            for surfaces in concept_surfaces_by_key.values():
                surface_lowers = [surface.lower() for surface in surfaces]
                if marker_lower not in surface_lowers and not any(
                    sibling and any(sibling in surface or surface in sibling for surface in surface_lowers)
                    for sibling in sibling_lowers
                ):
                    continue
                if any(surface != marker_lower and surface in grounded_blob for surface in surface_lowers):
                    return True
            return False

        answer_lower = answer_text.lower()
        missing_terms: List[str] = []
        for group in marker_groups:
            for marker in group:
                marker_lower = marker.lower()
                if marker_lower in answer_lower:
                    continue
                if marker_lower in support_blob or _marker_has_ontology_support(marker, group):
                    if marker_lower not in {item.lower() for item in missing_terms}:
                        missing_terms.append(marker)
        if not missing_terms:
            return answer_text
        template = str(CALCULATION_NARRATIVE_POLICY.get("source_visible_term_note_template") or "{terms}")
        addition = _normalise_spaces(template.format(terms=", ".join(missing_terms[:4])))
        if not addition or addition.lower() in answer_lower:
            return answer_text
        return _normalise_spaces(f"{answer_text} {addition}")

    def _supported_growth_narrative_candidate_sentences(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        min_evidence_score: Optional[int] = None,
    ) -> List[str]:
        evidence_score_floor = int(
            min_evidence_score
            if min_evidence_score is not None
            else CALCULATION_NARRATIVE_POLICY.get("growth_supported_candidate_min_score") or 12
        )
        row_sentences = [
            _normalise_spaces(sentence)
            for row in ordered_results or []
            if row_is_narrative_summary(row)
            for sentence in _split_narrative_sentences(str(row.get("answer") or ""))
            if _normalise_spaces(sentence)
        ]
        row_sentence_set = set(row_sentences)
        evidence_sentences: List[str] = []
        for score, candidate, _claim_ids in self._growth_narrative_sentence_candidates(
            query=query,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ):
            normalized_candidate = _normalise_spaces(candidate)
            if score < evidence_score_floor and normalized_candidate not in row_sentence_set:
                continue
            evidence_sentences.extend(_split_narrative_sentences(normalized_candidate))
        return list(
            dict.fromkeys(
                _normalise_spaces(sentence)
                for sentence in [*row_sentences, *evidence_sentences]
                if _normalise_spaces(sentence)
            )
        )

    def _growth_narrative_sentence_candidates(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> List[tuple[int, str, List[str]]]:
        query_terms = narrative_context_terms(query)
        driver_groups = self._narrative_driver_groups(query)
        narrative_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ()))
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        candidates: List[tuple[int, str, List[str]]] = []

        def _add_candidate(text: str, claim_ids: List[str], base_score: int) -> None:
            normalized = _normalise_spaces(text)
            if not normalized or any(marker in normalized for marker in missing_markers):
                return
            for sentence in _split_narrative_sentences(normalized):
                cleaned = _normalise_spaces(sentence)
                if not cleaned or any(marker in cleaned for marker in missing_markers):
                    continue
                if _narrative_sentence_looks_table_noisy(cleaned):
                    continue
                if _narrative_sentence_looks_abbreviated_fragment(cleaned, narrative_markers):
                    continue
                haystack = cleaned.lower()
                score = base_score
                score += sum(3 for term in query_terms if term.lower() in haystack)
                for group in driver_groups:
                    variants = [
                        str(variant).strip()
                        for variant in (group.get("variants") or [])
                        if str(variant).strip()
                    ]
                    if any(variant.lower() in haystack for variant in variants):
                        score += 4
                score += sum(2 for marker in narrative_markers if marker in cleaned)
                if score <= base_score and base_score < 8:
                    continue
                candidates.append((score, cleaned, claim_ids))

        for row in ordered_results or []:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family != "narrative_summary" and metric_family != "narrative_summary":
                continue
            claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
            _add_candidate(str(row.get("answer") or ""), claim_ids, 8)

        for item in evidence_items or []:
            evidence = dict(item or {})
            claim_id = str(evidence.get("evidence_id") or "").strip()
            seen_texts: set[str] = set()
            for key, base_score in (("claim", 2), ("quote_span", 2), ("raw_row_text", 1)):
                candidate_text = _normalise_spaces(str(evidence.get(key) or ""))
                if not candidate_text or candidate_text in seen_texts:
                    continue
                seen_texts.add(candidate_text)
                _add_candidate(candidate_text, [claim_id] if claim_id else [], base_score)

        candidates.sort(key=lambda item: item[0], reverse=True)
        return candidates

    def _supported_growth_driver_groups(
        self,
        *,
        query: str,
        narrative_candidates: List[tuple[int, str, List[str]]],
    ) -> List[Dict[str, Any]]:
        supported: List[Dict[str, Any]] = []
        for group in self._narrative_driver_groups(query):
            variants = [
                str(variant).strip()
                for variant in (group.get("variants") or [])
                if str(variant).strip()
            ]
            if not variants:
                continue
            if not any(
                any(variant.lower() in candidate_text.lower() for variant in variants)
                for _score, candidate_text, _claim_ids in narrative_candidates
            ):
                continue
            supported.append({**group, "variants": variants})
        return supported

    def _compose_growth_narrative_answer(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        existing_answer: str,
        evidence_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not _query_requests_narrative_context(query):
            return None
        existing_answer_text = _normalise_spaces(str(existing_answer or ""))
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        answer_has_missing_claim = any(marker in existing_answer_text for marker in missing_markers)
        answer_is_truncated = answer_looks_truncated(existing_answer)

        growth_row: Optional[Dict[str, Any]] = None
        growth_slots: Dict[str, Any] = {}
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if growth_row_has_conflicting_periods(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            if not (
                answer_slot_has_material(primary_slot)
                and answer_slot_has_material(current_slot)
                and answer_slot_has_material(prior_slot)
            ):
                continue
            growth_row = dict(row)
            growth_slots = {
                "primary_value": primary_slot,
                "current_value": current_slot,
                "prior_value": prior_slot,
            }
            break

        if not growth_row or not growth_slots:
            return None

        narrative_candidates = self._growth_narrative_sentence_candidates(
            query=query,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        if not narrative_candidates:
            return None
        if (
            existing_answer_text
            and self._answer_matches_supported_aggregate_subtask(existing_answer_text, ordered_results)
            and any(
                answer_covers_narrative_context(existing_answer_text, candidate_text)
                for _score, candidate_text, _claim_ids in narrative_candidates[:3]
            )
        ):
            return None
        supported_driver_groups = self._supported_growth_driver_groups(
            query=query,
            narrative_candidates=narrative_candidates,
        )

        primary_slot = growth_slots["primary_value"]
        current_slot = growth_slots["current_value"]
        prior_slot = growth_slots["prior_value"]
        growth_value = _normalise_spaces(str(primary_slot.get("rendered_value") or primary_slot.get("raw_value") or ""))
        current_value = growth_slot_display_value(current_slot, ordered_results)
        prior_value = growth_slot_display_value(prior_slot, ordered_results)
        prior_period = _normalise_spaces(
            str(prior_slot.get("period") or CALCULATION_NARRATIVE_POLICY.get("default_prior_period") or "")
        )
        current_period = _normalise_spaces(str(current_slot.get("period") or primary_slot.get("period") or ""))
        metric_label_raw = _normalise_spaces(
            str(current_slot.get("label") or primary_slot.get("label") or growth_row.get("metric_label") or "")
        )
        metric_label = metric_label_raw
        metric_label = re.sub(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), " ", metric_label)
        metric_label = _normalise_spaces(metric_label)
        if not growth_value or not current_value or not metric_label:
            return None
        if growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_value = recovered_prior_material["display"]
                prior_period = recovered_prior_material.get("period") or prior_period
        required_displays = growth_required_display_values(
            growth_row,
            ordered_results,
            evidence_items=evidence_items,
        )
        focus_variants = narrative_focus_variants(query)
        focus_required_variants = parenthetical_focus_variants(query) or focus_variants
        answer_has_focus = not focus_required_variants or any(
            variant.lower() in existing_answer_text.lower()
            for variant in focus_required_variants
        )
        row_focus_context = narrative_row_focus_context(
            query=query,
            ordered_results=ordered_results,
            focus_variants=focus_required_variants or focus_variants,
        )
        answer_has_row_context = not row_focus_context or answer_covers_narrative_context(
            existing_answer_text,
            row_focus_context[1],
        )
        answer_has_supported_driver_groups = True
        existing_answer_lower = existing_answer_text.lower()
        for group in supported_driver_groups:
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _normalise_spaces(str(group.get("phrase") or ""))
            if not variants:
                continue
            coverage_terms = variants + ([phrase] if phrase else [])
            if not any(term.lower() in existing_answer_lower for term in coverage_terms):
                answer_has_supported_driver_groups = False
                break
        if (
            not answer_is_truncated
            and not answer_has_missing_claim
            and required_displays
            and all(value in existing_answer_text for value in required_displays)
            and answer_has_focus
            and answer_has_row_context
            and answer_has_supported_driver_groups
        ):
            return None

        direction = _normalise_spaces(str(primary_slot.get("direction") or primary_slot.get("direction_hint") or "")).lower()
        if not direction:
            normalized_value = primary_slot.get("normalized_value")
            try:
                direction = "decrease" if normalized_value is not None and float(normalized_value) < 0 else "increase"
            except (TypeError, ValueError):
                direction = "decrease" if growth_value.startswith("-") else "increase"
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
        if current_period and current_period in metric_label_raw:
            period_prefix = ""
        elif current_period and year_suffix and not current_period.endswith(year_suffix):
            period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_with_year_template") or "").format(
                period=current_period
            )
        elif current_period:
            period_prefix = str(CALCULATION_NARRATIVE_POLICY.get("period_prefix_template") or "").format(
                period=current_period
            )
        else:
            period_prefix = ""
        if prior_value:
            prior_period_display = prior_period
            if prior_period_display and year_suffix and re.fullmatch(r"\d{4}", prior_period_display):
                prior_period_display = f"{prior_period_display}{year_suffix}"
            prior_phrase = str(CALCULATION_NARRATIVE_POLICY.get("prior_phrase_with_value_template") or "").format(
                period=prior_period_display,
                value=prior_value,
            )
        else:
            prior_period_display = prior_period
            if prior_period_display and year_suffix and re.fullmatch(r"\d{4}", prior_period_display):
                prior_period_display = f"{prior_period_display}{year_suffix}"
            prior_phrase = str(CALCULATION_NARRATIVE_POLICY.get("prior_phrase_template") or "").format(
                period=prior_period_display
            )
        numeric_sentence = _normalise_spaces(
            str(CALCULATION_NARRATIVE_POLICY.get("growth_numeric_sentence_template") or "").format(
                period_prefix=period_prefix,
                metric_label=metric_label,
                topic_particle=_topic_particle(metric_label),
                current_value=current_value,
                prior_phrase=prior_phrase,
                growth_value=growth_value,
                direction_word=direction_word,
            )
        )
        existing_context = f"{existing_answer_text} {numeric_sentence}".lower()
        uncovered_focus_variants = [
            variant
            for variant in focus_variants
            if variant.lower() not in existing_context
        ]
        chosen_candidate = narrative_candidates[0]
        if row_focus_context and not answer_covers_narrative_context(existing_answer_text, row_focus_context[1]):
            chosen_candidate = row_focus_context
        elif uncovered_focus_variants:
            parenthetical_variants = [
                variant
                for variant in parenthetical_focus_variants(query)
                if variant.lower() not in existing_context
            ]
            row_focus_candidate = narrative_row_focus_sentence(
                ordered_results=ordered_results,
                focus_variants=parenthetical_variants,
            )
            if row_focus_candidate:
                chosen_candidate = row_focus_candidate
            elif not parenthetical_variants:
                scored_candidates = []
                for candidate in narrative_candidates:
                    candidate_text = candidate[1].lower()
                    hits = [
                        variant
                        for variant in uncovered_focus_variants
                        if variant.lower() in candidate_text
                    ]
                    scored_candidates.append((sum(len(hit) for hit in hits), candidate))
                scored_candidates.sort(key=lambda item: item[0], reverse=True)
                if scored_candidates and scored_candidates[0][0] > 0:
                    chosen_candidate = scored_candidates[0][1]
        if uncovered_focus_variants and chosen_candidate == narrative_candidates[0]:
            for candidate in narrative_candidates:
                candidate_text = candidate[1].lower()
                if any(variant.lower() in candidate_text for variant in uncovered_focus_variants):
                    chosen_candidate = candidate
                    break
        narrative_sentence, selected_claim_ids = chosen_candidate[1], chosen_candidate[2]
        terminal_pattern = str(CALCULATION_NARRATIVE_POLICY.get("sentence_terminal_pattern") or "")
        terminal_suffix = str(CALCULATION_NARRATIVE_POLICY.get("sentence_terminal_suffix") or "")
        if narrative_sentence and terminal_pattern and not re.search(terminal_pattern, narrative_sentence):
            narrative_sentence = f"{narrative_sentence}{terminal_suffix}"
        narrative_sentences = [narrative_sentence] if narrative_sentence else []
        selected_claim_ids = list(selected_claim_ids or [])
        composed_context = _normalise_spaces(f"{numeric_sentence} {' '.join(narrative_sentences)}").lower()
        max_driver_sentences = int(CALCULATION_NARRATIVE_POLICY.get("max_growth_driver_sentences") or 4)
        max_narrative_sentences = max(1, min(max_driver_sentences, max(1, len(supported_driver_groups))))
        for group in supported_driver_groups:
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _normalise_spaces(str(group.get("phrase") or ""))
            if not variants or not phrase:
                continue
            if any(variant.lower() in composed_context for variant in variants):
                continue
            for candidate in narrative_candidates:
                candidate_sentence = _normalise_spaces(candidate[1])
                candidate_context = candidate_sentence.lower()
                if not candidate_sentence or candidate_sentence == _normalise_spaces(narrative_sentence):
                    continue
                if not any(variant.lower() in candidate_context for variant in variants):
                    continue
                narrative_sentences.append(candidate_sentence)
                selected_claim_ids.extend(candidate[2] or [])
                composed_context = _normalise_spaces(f"{numeric_sentence} {' '.join(narrative_sentences)}").lower()
                break
            if len(narrative_sentences) >= max_narrative_sentences:
                break
        return {
            "compressed_answer": _normalise_spaces(f"{numeric_sentence} {' '.join(narrative_sentences)}"),
            "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
        }

    def _answer_satisfies_growth_narrative_intent(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        query_text = _normalise_spaces(str(query or ""))
        answer_text = _normalise_spaces(str(answer or ""))
        if not query_text or not answer_text or not _query_requests_narrative_context(query_text):
            return False
        if not re.search(str(CALCULATION_NARRATIVE_POLICY.get("growth_query_pattern") or r"$^"), query_text):
            return False
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        if any(marker in answer_text for marker in missing_markers):
            return False
        if not re.search(str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"$^"), answer_text):
            return False
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if growth_row_has_conflicting_periods(row):
                continue
            required_displays = growth_required_display_values(row, ordered_results)
            if required_displays and not all(value in answer_text for value in required_displays):
                return False
            break
        impact_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ()))
        if not any(marker in answer_text for marker in impact_markers):
            return False

        generic_terms = {
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_generic_focus_terms") or ())
            if str(item)
        }
        focus_terms = [
            term
            for term in narrative_context_terms(query_text)
            if term not in generic_terms and len(term) >= 2
        ]
        parenthetical_focus_terms = parenthetical_focus_variants(query_text)
        required_focus_terms = parenthetical_focus_terms or focus_terms
        if required_focus_terms and not any(term.lower() in answer_text.lower() for term in required_focus_terms):
            return False
        narrative_candidates = self._growth_narrative_sentence_candidates(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=list(evidence_items or []),
        )
        if narrative_candidates and not any(
            answer_covers_narrative_context(answer_text, candidate_text)
            for _score, candidate_text, _claim_ids in narrative_candidates[:3]
        ):
            return False
        for group in self._supported_growth_driver_groups(
            query=query_text,
            narrative_candidates=narrative_candidates,
        ):
            variants = [
                _normalise_spaces(str(variant or ""))
                for variant in (group.get("variants") or [])
                if _normalise_spaces(str(variant or ""))
            ]
            phrase = _normalise_spaces(str(group.get("phrase") or ""))
            if not variants:
                continue
            coverage_terms = variants + ([phrase] if phrase else [])
            if not any(term.lower() in answer_text.lower() for term in coverage_terms):
                return False
        row_focus_context = narrative_row_focus_context(
            query=query_text,
            ordered_results=ordered_results,
            focus_variants=required_focus_terms,
        )
        if row_focus_context and not answer_covers_narrative_context(answer_text, row_focus_context[1]):
            return False

        has_growth_row = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            or "growth" in _normalise_spaces(str(row.get("metric_family") or "")).lower()
            or any(
                str(term) in _normalise_spaces(str(row.get("metric_label") or ""))
                for term in (CALCULATION_NARRATIVE_POLICY.get("growth_metric_label_terms") or ())
            )
            for row in ordered_results or []
        )
        has_narrative_material = any(
            self._aggregate_result_operation_family(row) == "narrative_summary"
            or _normalise_spaces(str(row.get("metric_family") or "")).lower() == "narrative_summary"
            for row in ordered_results or []
        )
        return has_growth_row and has_narrative_material

    def _prune_irrelevant_growth_narrative_sentences(
        self,
        *,
        query: str,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        sentences = _split_narrative_sentences(answer_text)
        if len(sentences) < 2 or not _query_requests_narrative_context(query):
            return answer_text
        if not re.search(str(CALCULATION_NARRATIVE_POLICY.get("growth_query_pattern") or r"$^"), query):
            return answer_text
        if not re.search(str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"$^"), answer_text):
            return answer_text

        has_growth_row = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            for row in ordered_results or []
        )
        has_narrative_row = any(row_is_narrative_summary(row) for row in ordered_results or [])
        if not has_growth_row or not has_narrative_row:
            return answer_text

        required_values: List[str] = []
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            required_values.extend(
                value
                for value in growth_required_display_values(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if value
            )
        required_values = list(dict.fromkeys(required_values))

        candidate_sentences = self._supported_growth_narrative_candidate_sentences(
            query=query,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )

        focus_variants = [_normalise_spaces(str(item)) for item in narrative_focus_variants(query) if item]
        impact_markers = [
            _normalise_spaces(str(item))
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ())
            if _normalise_spaces(str(item))
        ]
        narrative_markers = [
            _normalise_spaces(str(item))
            for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
            if _normalise_spaces(str(item))
        ]
        allowed_narrative_numeric_surface = _normalise_spaces(" ".join([*candidate_sentences, *required_values]))

        def _token_overlap_supported(sentence: str, candidate: str) -> bool:
            sentence_terms = {
                term.lower()
                for term in narrative_context_terms(sentence)
                if len(term) >= 3
            }
            candidate_terms = {
                term.lower()
                for term in narrative_context_terms(candidate)
                if len(term) >= 3
            }
            if not sentence_terms or not candidate_terms:
                return False
            overlap = sentence_terms & candidate_terms
            return len(overlap) >= max(2, min(len(sentence_terms), len(candidate_terms)) // 2)

        def _is_supported_sentence(sentence: str) -> bool:
            cleaned = _normalise_spaces(sentence)
            if not cleaned:
                return False
            if growth_sentence_has_untraced_material_numeric(
                cleaned,
                allowed_narrative_numeric_surface,
                required_values,
                evidence_items,
            ):
                return False
            if any(value and value in cleaned for value in required_values):
                return True
            cleaned_lower = cleaned.lower()
            for candidate in candidate_sentences:
                candidate_lower = candidate.lower()
                if candidate_lower and (candidate_lower in cleaned_lower or cleaned_lower in candidate_lower):
                    return True
                if _token_overlap_supported(cleaned, candidate):
                    return True
            if any(marker and marker in cleaned for marker in impact_markers + narrative_markers):
                if candidate_sentences:
                    return False
                return any(variant and variant.lower() in cleaned_lower for variant in focus_variants)
            return False

        kept_sentences = [sentence for sentence in sentences if _is_supported_sentence(sentence)]
        if len(kept_sentences) == len(sentences) or not kept_sentences:
            return answer_text
        pruned_answer = _normalise_spaces(" ".join(kept_sentences))
        has_supported_narrative_sentence = any(
            _normalise_spaces(sentence) in candidate_sentences
            for sentence in kept_sentences
            if not any(value and value in _normalise_spaces(sentence) for value in required_values)
        )
        if not self._answer_satisfies_growth_narrative_intent(
            query=query,
            answer=pruned_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ) and not has_supported_narrative_sentence:
            return answer_text
        if growth_answer_has_untraced_numeric_material(
            pruned_answer,
            ordered_results,
            evidence_items,
        ):
            return answer_text
        return pruned_answer

    def _coerce_operand_row_from_evidence(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        updated = dict(row)
        preserve_dependency_unit = dependency_task_output_has_consistent_krw_unit(updated)
        raw_value = str(updated.get("raw_value") or "")
        if preserve_dependency_unit:
            coerced_unit = str(updated.get("raw_unit") or "")
        elif updated.get("unit_realigned_from_structured_provenance") and updated.get("normalized_value") is not None:
            coerced_unit = str(updated.get("raw_unit") or "")
        else:
            coerced_unit = coerce_operand_unit_from_evidence(
                raw_value=raw_value,
                raw_unit=str(updated.get("raw_unit") or ""),
                evidence_item=evidence_item,
            )
        if coerced_unit != str(updated.get("raw_unit") or "") or updated.get("normalized_value") is None:
            normalized_value, normalized_unit = _normalise_operand_value(raw_value, coerced_unit)
            if normalized_value is not None:
                updated["raw_unit"] = coerced_unit
                updated["normalized_value"] = normalized_value
                updated["normalized_unit"] = normalized_unit
        if evidence_item:
            metadata = dict(evidence_item.get("metadata") or {})
            if updated.get("statement_type") is None:
                updated["statement_type"] = metadata.get("statement_type")
            if updated.get("consolidation_scope") is None:
                updated["consolidation_scope"] = metadata.get("consolidation_scope")
            if updated.get("table_source_id") is None:
                updated["table_source_id"] = metadata.get("table_source_id")
            updated = coerce_operand_period_from_evidence_surface(updated, evidence_item)
            updated = self._coerce_operand_value_from_direct_structured_evidence(updated, evidence_item)
        updated = coerce_lookup_magnitude_record(updated, evidence_item)
        if updated.get("structured_evidence_cell_realigned"):
            return updated
        if (
            updated.get("dependency_resolved")
            and str(updated.get("source_row_id") or "").startswith("task_output:")
            and updated.get("normalized_value") is not None
        ):
            return updated
        return self._refine_operand_precision_from_evidence_table(updated, evidence_item)

    def _coerce_operand_value_from_direct_structured_evidence(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        if not row or not evidence_item:
            return row
        metadata = dict(evidence_item.get("metadata") or {})
        cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
        if not cells:
            return row

        row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
        semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
        operand_spec = {
            "label": _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
            "concept": _normalise_spaces(str(row.get("matched_operand_concept") or row.get("concept") or "")),
            "role": _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")),
            "period": _normalise_spaces(str(row.get("period") or "")),
            "period_hint": _normalise_spaces(str(row.get("period") or "")),
            "aliases": [
                item
                for item in (
                    row.get("matched_operand_label"),
                    row.get("label"),
                    row.get("concept"),
                )
                if _normalise_spaces(str(item or ""))
            ],
        }
        authoritative_surface = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    row_label,
                    semantic_label,
                    metadata.get("aggregate_label"),
                )
            )
        )
        if authoritative_surface and not (
            _operand_text_match(authoritative_surface, operand_spec)
            or _text_has_positive_surface(authoritative_surface, operand_spec)
        ):
            return row

        query_years: List[int] = []
        for raw_year in (operand_spec.get("period"), metadata.get("year")):
            try:
                if raw_year not in (None, ""):
                    year = int(raw_year)
                    if year not in query_years:
                        query_years.append(year)
            except (TypeError, ValueError):
                continue

        enriched_cells = [
            {
                **cell,
                "_report_year": metadata.get("year"),
                "_sibling_cells": [dict(item) for item in cells],
            }
            for cell in cells
        ]
        value_role = _normalise_spaces(str(row.get("value_role") or metadata.get("value_role") or "")).lower()
        aggregation_stage = _normalise_spaces(
            str(row.get("aggregation_stage") or metadata.get("aggregation_stage") or "")
        ).lower()
        current_raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        current_value = row.get("normalized_value")
        prefers_aggregate_cell = bool(
            value_role == "aggregate"
            or aggregation_stage in {"direct", "final", "subtotal"}
            or _operand_prefers_aggregate_value_role(row)
        )
        period_specific_cell_selection_required = bool(
            operand_spec.get("period")
            and len(enriched_cells) > 1
            and any(
                re.search(
                    r"(?:19|20)\d{2}|current|prior",
                    _structured_cell_period_text(
                        cell,
                        query_years,
                        _operand_period_focus(operand_spec, "unknown"),
                    ),
                    flags=re.IGNORECASE,
                )
                for cell in enriched_cells
            )
        )
        if (
            current_raw_value
            and current_value is not None
            and not prefers_aggregate_cell
            and not period_specific_cell_selection_required
        ):
            current_compact = re.sub(r"[\s,()]", "", current_raw_value)
            for cell in enriched_cells:
                cell_value = _normalise_spaces(str(cell.get("value_text") or ""))
                if current_compact and current_compact == re.sub(r"[\s,()]", "", cell_value):
                    return row
        selected_cell: Optional[Dict[str, Any]] = None
        if prefers_aggregate_cell:
            selected_cell = _select_aggregate_structured_cell(
                enriched_cells,
                operand=operand_spec,
                query_years=query_years,
                period_focus=_operand_period_focus(operand_spec, "unknown"),
            )
        if not selected_cell:
            selected_cell = _select_structured_cell(
                enriched_cells,
                operand=operand_spec,
                query_years=query_years,
                period_focus=_operand_period_focus(operand_spec, "unknown"),
            )
        if not selected_cell:
            return row

        raw_value = _normalise_spaces(str(selected_cell.get("value_text") or ""))
        raw_unit = _normalise_spaces(str(selected_cell.get("unit_hint") or metadata.get("unit_hint") or row.get("raw_unit") or ""))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        if normalized_value is None:
            return row
        try:
            if current_value is not None and abs(float(current_value) - float(normalized_value)) <= 1e-6:
                return row
        except (TypeError, ValueError):
            pass

        updated = dict(row)
        updated["raw_value"] = raw_value
        updated["raw_unit"] = raw_unit
        updated["normalized_value"] = normalized_value
        updated["normalized_unit"] = normalized_unit
        updated["rendered_value"] = _normalise_spaces(f"{raw_value}{raw_unit}") if raw_unit else raw_value
        updated["structured_evidence_cell_realigned"] = True
        return updated

    def _operand_precision_surface(self, evidence_item: Optional[Dict[str, Any]]) -> str:
        return _normalise_spaces(
            " ".join(
                part
                for part in [
                    str((evidence_item or {}).get("claim") or ""),
                    str((evidence_item or {}).get("quote_span") or ""),
                    str((evidence_item or {}).get("raw_row_text") or ""),
                    str((evidence_item or {}).get("source_context") or ""),
                ]
                if part
            )
        )

    def _precision_cell_from_contextual_note_row(
        self,
        context: _OperandPrecisionContext,
    ) -> Optional[Dict[str, Any]]:
        row = context.row
        metadata = context.metadata
        records = context.records
        operand_aliases = context.operand_aliases
        operand_spec = context.operand_spec
        row_labels = [
            _normalise_spaces(line)
            for line in str(metadata.get("table_row_labels_text") or "").splitlines()
            if _normalise_spaces(line)
        ]
        if not row_labels:
            return None
        records_by_label: Dict[str, Dict[str, Any]] = {}
        for record in records:
            label = _normalise_spaces(str(record.get("row_label") or ""))
            if not label:
                continue
            existing = records_by_label.get(label)
            if existing is None or (not existing.get("cells") and record.get("cells")):
                records_by_label[label] = record

        def _select_period_aware_cell(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            cells = [dict(cell or {}) for cell in list(record.get("cells") or []) if isinstance(cell, dict)]
            if not cells:
                return None
            query_years: List[int] = []
            for raw_year in (
                row.get("period"),
                metadata.get("year"),
            ):
                try:
                    if raw_year not in (None, ""):
                        year = int(raw_year)
                        if year not in query_years:
                            query_years.append(year)
                except (TypeError, ValueError):
                    continue
            period_operand = dict(operand_spec)
            role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
            period_hint = _normalise_spaces(str(row.get("period") or ""))
            if role:
                period_operand["role"] = role
            if period_hint:
                period_operand["period_hint"] = period_hint
            cells = [{**cell, "_report_year": metadata.get("year")} for cell in cells]
            row_value_role = _normalise_spaces(str(row.get("value_role") or "")).lower()
            row_aggregation_stage = _normalise_spaces(str(row.get("aggregation_stage") or "")).lower()
            if (
                row_value_role == "aggregate"
                or row_aggregation_stage in {"direct", "final", "subtotal"}
                or _operand_prefers_aggregate_value_role(row)
            ):
                aggregate_selected = _select_aggregate_structured_cell(
                    cells,
                    operand=period_operand,
                    query_years=query_years,
                    period_focus=_operand_period_focus(period_operand, "unknown"),
                )
                if aggregate_selected:
                    return dict(aggregate_selected)
            selected = _select_structured_cell(
                cells,
                operand=period_operand,
                query_years=query_years,
                period_focus=_operand_period_focus(period_operand, "unknown"),
            )
            return dict(selected) if selected else None

        def _is_krw_cell(cell_data: Dict[str, Any]) -> bool:
            value_text = _normalise_spaces(str(cell_data.get("value_text") or ""))
            unit_hint = _normalise_spaces(str(cell_data.get("unit_hint") or ""))
            if not re.search(r"\d", value_text):
                return False
            cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
            return cell_value is not None and cell_unit == "KRW"

        alias_variants = [
            variant
            for alias in operand_aliases
            for variant in _surface_match_variants(alias)
            if variant
        ]

        def _label_match_score(label_text: str) -> int:
            label_variants = _surface_match_variants(label_text)
            if not label_variants or not alias_variants:
                return 0
            best = 0
            for label_variant in label_variants:
                label_compact = re.sub(r"\s+", "", label_variant)
                for alias_variant in alias_variants:
                    alias_compact = re.sub(r"\s+", "", alias_variant)
                    if not label_compact or not alias_compact:
                        continue
                    if label_variant == alias_variant or label_compact == alias_compact:
                        best = max(best, 10000 + len(label_compact))
                    elif label_variant in alias_variant or label_compact in alias_compact:
                        best = max(best, 5000 + len(label_compact))
                    elif alias_variant in label_variant or alias_compact in label_compact:
                        best = max(best, 3000 + len(alias_compact))
            if best:
                return best
            if _operand_text_match(label_text, operand_spec):
                return max(len(re.sub(r"\s+", "", variant)) for variant in label_variants)
            return 0

        best_label_index = -1
        best_label_score = 0
        for index, label_text in enumerate(row_labels):
            label_score = _label_match_score(label_text)
            if label_score <= best_label_score:
                continue
            best_label_index = index
            best_label_score = label_score

        if best_label_index >= 0:
            label_text = row_labels[best_label_index]
            current_record = records_by_label.get(label_text)
            if current_record:
                cell_data = _select_period_aware_cell(current_record)
                if cell_data and _is_krw_cell(cell_data):
                    return cell_data
            for previous_label in reversed(row_labels[:best_label_index]):
                record = records_by_label.get(previous_label)
                if not record:
                    continue
                cell_data = _select_period_aware_cell(record)
                if cell_data and _is_krw_cell(cell_data):
                    return cell_data
        return None

    def _precision_cell_from_flattened_table_surface(
        self,
        context: _OperandPrecisionContext,
    ) -> Optional[Dict[str, Any]]:
        row = context.row
        metadata = context.metadata
        operand_spec = context.operand_spec
        raw_unit = context.raw_unit
        surface_text = context.surface
        if "|" not in surface_text:
            return None
        tokens = [_normalise_spaces(token) for token in surface_text.split("|")]
        if not tokens:
            return None
        row_labels = [
            _normalise_spaces(line)
            for line in str(metadata.get("table_row_labels_text") or "").splitlines()
            if _normalise_spaces(line)
        ]
        if not row_labels:
            return None
        numeric_pattern = r"^\(?-?\d[\d,]*(?:\.\d+)?\)?$"

        def _label_position(token: str, label: str) -> int:
            if not token or not label:
                return -1
            return token.find(label)

        def _row_label_score(label: str) -> int:
            if not label:
                return 0
            if _operand_text_match(label, operand_spec):
                return 1000 + len(re.sub(r"\s+", "", label))
            affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
            metric_terms = tuple(str(item) for item in (affinity_policy.get("metric_terms") or ()) if str(item))
            operand_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        operand_spec.get("label"),
                        " ".join(str(item) for item in (operand_spec.get("aliases") or [])),
                    )
                )
            )
            if metric_terms and any(term in label and term in operand_surface for term in metric_terms):
                return 500 + len(re.sub(r"\s+", "", label))
            return 0

        ordered_row_labels = sorted(row_labels, key=_row_label_score, reverse=True)
        segment_label = _normalise_spaces(str(_operand_segment_label(row) or ""))
        segment_label = _normalise_spaces(re.sub(r"^\W+|\W+$", " ", segment_label))
        role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
        aggregate_tokens = tuple(
            str(item)
            for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_tokens") or ())
            if str(item)
        )

        for row_label in ordered_row_labels:
            if _row_label_score(row_label) <= 0:
                continue
            for start_index, token in enumerate(tokens):
                position = _label_position(token, row_label)
                if position < 0:
                    continue
                prefix = _normalise_spaces(token[:position])
                row_cells: List[str] = []
                for next_token in tokens[start_index + 1 :]:
                    next_label_positions = [
                        _label_position(next_token, other_label)
                        for other_label in row_labels
                        if _label_position(next_token, other_label) >= 0
                    ]
                    if next_label_positions:
                        first_label_position = min(next_label_positions)
                        prefix_value = _normalise_spaces(next_token[:first_label_position])
                        if prefix_value:
                            row_cells.append(prefix_value)
                        break
                    row_cells.append(next_token)
                if not row_cells:
                    continue
                header_tokens = list(tokens[:start_index])
                if prefix:
                    header_tokens.append(prefix)
                headers_for_cells = header_tokens[-len(row_cells) :] if header_tokens else []
                if len(headers_for_cells) < len(row_cells):
                    headers_for_cells = [""] * (len(row_cells) - len(headers_for_cells)) + headers_for_cells

                candidate_indexes: List[int] = []
                if segment_label:
                    compact_segment = re.sub(r"\s+", "", segment_label)
                    for index, header in enumerate(headers_for_cells):
                        compact_header = re.sub(r"\s+", "", header)
                        if segment_label in header or (compact_segment and compact_segment in compact_header):
                            candidate_indexes.append(index)
                elif role.startswith("denominator"):
                    candidate_indexes = [
                        index
                        for index, header in enumerate(headers_for_cells)
                        if any(token and token in header for token in aggregate_tokens)
                    ]
                    if not candidate_indexes:
                        candidate_indexes = list(range(len(row_cells)))
                    candidate_indexes = list(reversed(candidate_indexes))
                else:
                    candidate_indexes = list(range(len(row_cells)))

                value_label_lines = [
                    _normalise_spaces(line)
                    for line in str(metadata.get("table_value_labels_text") or "").splitlines()
                    if _normalise_spaces(line)
                ]
                row_values: List[str] = []
                value_pattern = re.compile(r"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)\s*$")
                for line in value_label_lines:
                    if row_label not in line:
                        continue
                    match = value_pattern.search(line)
                    if match:
                        row_values.append(_normalise_spaces(match.group("value")))
                numeric_header_pairs = [
                    (header, cell)
                    for header, cell in zip(headers_for_cells, row_cells)
                    if re.fullmatch(numeric_pattern, _normalise_spaces(cell))
                ]
                if row_values and len(row_values) == len(numeric_header_pairs):
                    header_value_pairs = [
                        (header, value)
                        for (header, _cell), value in zip(numeric_header_pairs, row_values)
                    ]
                    if segment_label:
                        compact_segment = re.sub(r"\s+", "", segment_label)
                        ordered_pairs = header_value_pairs
                    elif role.startswith("denominator"):
                        ordered_pairs = list(reversed(header_value_pairs))
                    else:
                        ordered_pairs = header_value_pairs
                    for header, value_text in ordered_pairs:
                        compact_header = re.sub(r"\s+", "", header)
                        if segment_label and not (
                            segment_label in header or (compact_segment and compact_segment in compact_header)
                        ):
                            continue
                        if not segment_label and role.startswith("denominator") and aggregate_tokens:
                            if not any(token and token in header for token in aggregate_tokens):
                                continue
                        unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or raw_unit or ""))
                        cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
                        if cell_value is None or cell_unit != "KRW":
                            continue
                        return {
                            "column_headers": [header] if header else [],
                            "value_text": value_text,
                            "unit_hint": unit_hint,
                            "flattened_surface_row_label": row_label,
                            "flattened_surface_value_label_fallback": True,
                        }

                for index in candidate_indexes:
                    if index < 0 or index >= len(row_cells):
                        continue
                    value_text = _normalise_spaces(row_cells[index])
                    if not re.fullmatch(numeric_pattern, value_text):
                        continue
                    unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or raw_unit or ""))
                    cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
                    if cell_value is None or cell_unit != "KRW":
                        continue
                    return {
                        "column_headers": [headers_for_cells[index]] if headers_for_cells[index] else [],
                        "value_text": value_text,
                        "unit_hint": unit_hint,
                        "flattened_surface_row_label": row_label,
                    }
        return None

    def _refine_operand_precision_from_evidence_table(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Prefer a finer structured-table cell when an LLM returned a rounded KRW surface."""
        normalized_value = row.get("normalized_value")
        normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
        raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if normalized_value is None or normalized_unit != "KRW":
            return row

        metadata = dict((evidence_item or {}).get("metadata") or {})
        records: List[Dict[str, Any]] = []
        for key in ("table_row_records_json", "table_value_records_json"):
            payload = str(metadata.get(key) or "").strip()
            if not payload:
                continue
            try:
                parsed = json.loads(payload)
            except json.JSONDecodeError:
                continue
            if isinstance(parsed, list):
                records.extend(dict(item) for item in parsed if isinstance(item, dict))

        if not records:
            return row

        target_values: List[float] = []
        render_policy = dict(CALCULATION_RENDER_POLICY)
        if raw_unit in set(render_policy.get("converted_display_units") or ()) or any(
            unit in raw_value for unit in tuple(render_policy.get("krw_value_magnitude_markers") or ())
        ):
            target_values.append(float(normalized_value))

        operand_aliases = [
            str(row.get("label") or "").strip(),
            str(row.get("matched_operand_label") or "").strip(),
        ]
        slot_policy = dict(CALCULATION_SLOT_POLICY)
        parenthetical_alias_pattern = str(slot_policy.get("parenthetical_alias_pattern") or "")
        parenthetical_strip_pattern = str(slot_policy.get("parenthetical_strip_pattern") or "")
        leading_period_strip_pattern = str(slot_policy.get("leading_period_strip_pattern") or "")
        for label_surface in list(operand_aliases):
            if parenthetical_alias_pattern:
                for match in re.finditer(parenthetical_alias_pattern, label_surface):
                    operand_aliases.append(_normalise_spaces(match.group(1)))
            without_parenthetical = (
                _normalise_spaces(re.sub(parenthetical_strip_pattern, " ", label_surface))
                if parenthetical_strip_pattern
                else _normalise_spaces(label_surface)
            )
            if without_parenthetical:
                operand_aliases.append(without_parenthetical)
                stripped_period = _normalise_spaces(
                    re.sub(leading_period_strip_pattern, " ", without_parenthetical)
                    if leading_period_strip_pattern
                    else without_parenthetical
                )
                if stripped_period:
                    operand_aliases.append(stripped_period)
        operand_spec = {
            "label": str(row.get("matched_operand_label") or row.get("label") or "").strip(),
            "aliases": [item for item in dict.fromkeys(operand_aliases) if item],
        }
        surface = self._operand_precision_surface(evidence_item)
        precision_context = _OperandPrecisionContext(
            row=row,
            evidence_item=evidence_item,
            metadata=metadata,
            records=records,
            operand_aliases=operand_aliases,
            operand_spec=operand_spec,
            raw_unit=raw_unit,
            surface=surface,
        )
        surface_value = _extract_numeric_value_after_operand_text(surface, operand_spec)
        if surface_value:
            surface_normalized, surface_unit = _normalise_operand_value(surface_value, "")
            if surface_normalized is not None and surface_unit == "KRW":
                target_values.append(float(surface_normalized))

        contextual_cell = self._precision_cell_from_contextual_note_row(precision_context)
        flattened_cell = self._precision_cell_from_flattened_table_surface(precision_context)
        best_cell: Optional[Dict[str, Any]] = None
        best_normalized: Optional[float] = None
        best_diff: Optional[float] = None
        best_target: Optional[float] = None
        if flattened_cell:
            flattened_value, flattened_unit = _normalise_operand_value(
                _normalise_spaces(str(flattened_cell.get("value_text") or "")),
                _normalise_spaces(str(flattened_cell.get("unit_hint") or "")),
            )
            if flattened_value is not None and flattened_unit == "KRW":
                best_cell = flattened_cell
                best_normalized = float(flattened_value)
        elif contextual_cell:
            contextual_value, contextual_unit = _normalise_operand_value(
                _normalise_spaces(str(contextual_cell.get("value_text") or "")),
                _normalise_spaces(str(contextual_cell.get("unit_hint") or "")),
            )
            if contextual_value is not None and contextual_unit == "KRW":
                best_cell = contextual_cell
                best_normalized = float(contextual_value)

        segment_label = _normalise_spaces(
            str(_operand_segment_label(row) or dict(row.get("binding_policy") or {}).get("segment_label") or "")
        )
        segment_label = _normalise_spaces(re.sub(r"^\W+|\W+$", " ", segment_label))
        if segment_label and "|" in surface:
            tokens = [_normalise_spaces(token) for token in surface.split("|")]
            row_labels = [
                _normalise_spaces(line)
                for line in str(metadata.get("table_row_labels_text") or "").splitlines()
                if _normalise_spaces(line)
            ]
            value_label_lines = [
                _normalise_spaces(line)
                for line in str(metadata.get("table_value_labels_text") or "").splitlines()
                if _normalise_spaces(line)
            ]
            metric_terms = tuple(
                str(item) for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("metric_terms") or ()) if str(item)
            )
            operand_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        operand_spec.get("label"),
                        " ".join(str(item) for item in (operand_spec.get("aliases") or [])),
                    )
                )
            )
            numeric_pattern = r"^\(?-?\d[\d,]*(?:\.\d+)?\)?$"
            value_pattern = re.compile(r"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)\s*$")
            for row_label in row_labels:
                if not any(term in row_label and term in operand_surface for term in metric_terms):
                    continue
                start_index = next((idx for idx, token in enumerate(tokens) if row_label in token), None)
                if start_index is None:
                    continue
                row_cells: List[str] = []
                for next_token in tokens[start_index + 1 :]:
                    positions = [next_token.find(label) for label in row_labels if next_token.find(label) >= 0]
                    if positions:
                        prefix_value = _normalise_spaces(next_token[: min(positions)])
                        if prefix_value:
                            row_cells.append(prefix_value)
                        break
                    row_cells.append(next_token)
                if not row_cells:
                    continue
                prefix = _normalise_spaces(tokens[start_index].split(row_label, 1)[0])
                header_tokens = list(tokens[:start_index])
                if prefix:
                    header_tokens.append(prefix)
                headers_for_cells = header_tokens[-len(row_cells) :] if header_tokens else []
                if len(headers_for_cells) < len(row_cells):
                    headers_for_cells = [""] * (len(row_cells) - len(headers_for_cells)) + headers_for_cells
                numeric_headers = [
                    header
                    for header, cell in zip(headers_for_cells, row_cells)
                    if re.fullmatch(numeric_pattern, _normalise_spaces(cell))
                ]
                row_values: List[str] = []
                for line in value_label_lines:
                    if row_label not in line:
                        continue
                    match = value_pattern.search(line)
                    if match:
                        row_values.append(_normalise_spaces(match.group("value")))
                if len(numeric_headers) != len(row_values):
                    continue
                compact_segment = re.sub(r"\s+", "", segment_label)
                for header, value_text in zip(numeric_headers, row_values):
                    compact_header = re.sub(r"\s+", "", header)
                    if not (segment_label in header or (compact_segment and compact_segment in compact_header)):
                        continue
                    unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or raw_unit or ""))
                    cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
                    if cell_value is None or cell_unit != "KRW":
                        continue
                    best_cell = {
                        "column_headers": [header] if header else [],
                        "value_text": value_text,
                        "unit_hint": unit_hint,
                        "flattened_surface_value_label_fallback": True,
                    }
                    best_normalized = float(cell_value)
                    break
                if best_cell is not None and best_cell.get("flattened_surface_value_label_fallback"):
                    break

        if target_values and best_cell is None:
            for record in records:
                for cell in list(record.get("cells") or []):
                    cell_data = dict(cell or {})
                    value_text = _normalise_spaces(str(cell_data.get("value_text") or ""))
                    unit_hint = _normalise_spaces(str(cell_data.get("unit_hint") or ""))
                    if unit_hint not in {"천원", "백만원"} or not re.search(r"\d", value_text):
                        continue
                    cell_value, cell_unit = _normalise_operand_value(value_text, unit_hint)
                    if cell_value is None or cell_unit != "KRW":
                        continue
                    for target_value in target_values:
                        diff = abs(float(cell_value) - target_value)
                        tolerance = max(abs(target_value) * 0.005, 100_000_000.0)
                        if diff > tolerance:
                            continue
                        if best_diff is None or diff < best_diff:
                            best_cell = cell_data
                            best_normalized = float(cell_value)
                            best_diff = diff
                            best_target = target_value

        if not best_cell or best_normalized is None:
            return row
        candidate_text = _normalise_spaces(str(best_cell.get("value_text") or ""))
        current_digits_for_header_guard = len(re.sub(r"\D", "", raw_value))
        if re.fullmatch(r"(?:19|20)\d{2}", candidate_text) and current_digits_for_header_guard > 4:
            return row
        has_visible_table_surface = "|" in surface
        value_label_fallback = bool(best_cell.get("flattened_surface_value_label_fallback"))
        if (
            best_target is None
            and not (value_label_fallback and has_visible_table_surface)
            and (not contextual_cell or (flattened_cell and not has_visible_table_surface))
        ):
            try:
                current_float = float(normalized_value)
                candidate_float = float(best_normalized)
            except (TypeError, ValueError):
                return row
            current_abs = abs(current_float)
            candidate_abs = abs(candidate_float)
            if current_abs == 0:
                return row
            relative_delta = abs(candidate_abs - current_abs) / max(current_abs, candidate_abs, 1.0)
            current_digits = len(re.sub(r"\D", "", raw_value))
            candidate_digits = len(re.sub(r"\D", "", str(best_cell.get("value_text") or "")))
            if relative_delta > 0.005 or candidate_digits <= current_digits:
                return row
        refined = dict(row)
        refined["raw_value"] = _normalise_spaces(str(best_cell.get("value_text") or ""))
        refined["raw_unit"] = _normalise_spaces(str(best_cell.get("unit_hint") or ""))
        refined["normalized_value"] = best_normalized
        refined["normalized_unit"] = "KRW"
        refined["precision_source"] = "structured_table_cell"
        if best_target is not None and abs(float(normalized_value) - best_target) > 100_000_000.0:
            refined["precision_source"] = "surface_anchored_structured_table_cell"
        if contextual_cell:
            refined["precision_source"] = "contextual_note_structured_table_cell"
        if flattened_cell:
            refined["precision_source"] = "flattened_table_surface_cell"
        if best_cell.get("flattened_surface_value_label_fallback"):
            refined["precision_source"] = "flattened_table_surface_cell"
        return refined

    def _align_ratio_operands_with_sibling_table_context(
        self,
        ordered_operands: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) < 2:
            return ordered_operands
        evidence_pool = [dict(item) for item in (evidence_items or []) if isinstance(item, dict)]
        if not evidence_pool:
            return align_ratio_operand_units_with_shared_table_context(ordered_operands)
        evidence_by_id = _evidence_items_by_id(evidence_pool)

        def _row_as_operand(row: Dict[str, Any]) -> Dict[str, Any]:
            return {
                "label": _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                "concept": _normalise_spaces(str(row.get("matched_operand_concept") or "")),
                "role": _normalise_spaces(str(row.get("matched_operand_role") or "")),
                "period": _normalise_spaces(str(row.get("period") or "")),
                "required": True,
            }

        def _row_surfaces(row: Dict[str, Any]) -> List[str]:
            return [
                surface
                for surface in (
                    _normalise_spaces(str(row.get("matched_operand_label") or "")),
                    _normalise_spaces(str(row.get("label") or "")),
                )
                if surface
            ]

        def _candidate_has_other_operand_context(slot: Dict[str, Any], current_row: Dict[str, Any]) -> bool:
            candidate_evidence = _evidence_item_for_operand_row(slot, evidence_by_id)
            if not candidate_evidence:
                return False
            metadata = dict(candidate_evidence.get("metadata") or {})
            table_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        metadata.get("table_value_labels_text"),
                        metadata.get("table_row_labels_text"),
                        candidate_evidence.get("claim"),
                        candidate_evidence.get("quote_span"),
                        candidate_evidence.get("raw_row_text"),
                    )
                )
            )
            if not table_surface:
                return False
            table_surface_compact = re.sub(r"\s+", "", table_surface)
            current_id = str(current_row.get("operand_id") or "")
            for other_row in ordered_operands:
                if str(other_row.get("operand_id") or "") == current_id:
                    continue
                for surface in _row_surfaces(other_row):
                    if surface in table_surface or re.sub(r"\s+", "", surface) in table_surface_compact:
                        return True
            return False

        def _peer_consolidation_scopes(current_row: Dict[str, Any]) -> set[str]:
            current_id = str(current_row.get("operand_id") or "")
            scopes: set[str] = set()
            for other_row in ordered_operands:
                if current_id and str(other_row.get("operand_id") or "") == current_id:
                    continue
                scope = known_consolidation_scope_value(other_row.get("consolidation_scope"))
                if scope:
                    scopes.add(scope)
            return scopes

        aligned: List[Dict[str, Any]] = []
        changed = False
        for row in ordered_operands:
            current_row = dict(row)
            operand = _row_as_operand(current_row)
            if not _normalise_spaces(str(operand.get("label") or operand.get("concept") or "")):
                aligned.append(current_row)
                continue
            candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool(
                operand,
                evidence_pool,
            )
            if not candidate_slot or candidate_score <= 0:
                aligned.append(current_row)
                continue
            candidate_identity_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        candidate_slot.get("matched_operand_label"),
                        candidate_slot.get("label"),
                        candidate_slot.get("matched_operand_concept"),
                        candidate_slot.get("concept"),
                    )
                )
            )
            if candidate_identity_surface and not _operand_text_match(candidate_identity_surface, operand):
                aligned.append(current_row)
                continue
            candidate_evidence = _evidence_item_for_operand_row(candidate_slot, evidence_by_id)
            candidate_metadata = dict((candidate_evidence or {}).get("metadata") or {})
            candidate_scope = known_consolidation_scope_value(
                candidate_slot.get("consolidation_scope"),
                candidate_metadata.get("consolidation_scope"),
            )
            current_scope = known_consolidation_scope_value(current_row.get("consolidation_scope"))
            peer_scopes = _peer_consolidation_scopes(current_row)
            if (
                candidate_scope
                and (
                    (current_scope and candidate_scope != current_scope)
                    or (len(peer_scopes) == 1 and candidate_scope not in peer_scopes)
                )
            ):
                aligned.append(current_row)
                continue
            segment_label = _normalise_spaces(
                str(
                    dict(current_row.get("binding_policy") or {}).get("segment_label")
                    or dict(operand.get("binding_policy") or {}).get("segment_label")
                    or ""
                )
            )
            segment_label = _normalise_spaces(re.sub(r"^\W+|\W+$", " ", segment_label))
            if segment_label:
                candidate_segment_surfaces = (
                    (candidate_evidence or {}).get("claim"),
                    (candidate_evidence or {}).get("quote_span"),
                    (candidate_evidence or {}).get("raw_row_text"),
                    (candidate_evidence or {}).get("source_context"),
                    candidate_metadata.get("semantic_label"),
                    candidate_metadata.get("row_label"),
                    candidate_metadata.get("aggregate_label"),
                    candidate_metadata.get("table_header_context"),
                    candidate_metadata.get("table_row_labels_text"),
                    candidate_metadata.get("table_value_labels_text"),
                )
                if not _evidence_surface_contains_segment_label(segment_label, candidate_segment_surfaces):
                    aligned.append(current_row)
                    continue
            if not _candidate_has_other_operand_context(candidate_slot, current_row):
                aligned.append(current_row)
                continue
            current_value = current_row.get("normalized_value")
            candidate_value = candidate_slot.get("normalized_value")
            try:
                differs = (
                    current_value is not None
                    and candidate_value is not None
                    and abs(float(current_value) - float(candidate_value)) > 1e-6
                )
            except (TypeError, ValueError):
                differs = current_value != candidate_value
            if not differs:
                aligned.append(current_row)
                continue
            candidate_source_ids = _clean_source_row_ids([
                candidate_slot.get("source_row_id"),
                candidate_slot.get("source_row_ids"),
            ])
            aligned.append(
                {
                    **current_row,
                    "evidence_id": candidate_source_ids[0] if candidate_source_ids else current_row.get("evidence_id"),
                    "source_row_id": candidate_source_ids[0] if candidate_source_ids else current_row.get("source_row_id"),
                    "source_row_ids": candidate_source_ids or list(current_row.get("source_row_ids") or []),
                    "source_anchor": candidate_slot.get("source_anchor") or current_row.get("source_anchor"),
                    "label": candidate_slot.get("label") or current_row.get("label"),
                    "raw_value": candidate_slot.get("raw_value"),
                    "raw_unit": candidate_slot.get("raw_unit"),
                    "normalized_value": candidate_slot.get("normalized_value"),
                    "normalized_unit": candidate_slot.get("normalized_unit"),
                    "period": candidate_slot.get("period") or current_row.get("period"),
                    "consolidation_scope": (
                        candidate_slot.get("consolidation_scope")
                        or candidate_metadata.get("consolidation_scope")
                        or current_row.get("consolidation_scope")
                    ),
                    "sibling_table_context_realigned": True,
                }
            )
            changed = True
        if changed:
            unit_aligned = align_ratio_operand_units_with_shared_table_context(aligned)
            return unit_aligned
        return align_ratio_operand_units_with_shared_table_context(ordered_operands)

    def _build_complete_ratio_operands_from_coherent_context(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        required_operands: List[Dict[str, Any]],
        query: str,
        topic: str,
        report_scope: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not evidence_items or not required_operands:
            return []

        grouped_items: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
        for item in evidence_items:
            evidence = dict(item or {})
            metadata = dict(evidence.get("metadata") or {})
            table_id = _normalise_spaces(str(metadata.get("table_source_id") or ""))
            anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
            if table_id:
                key = ("table", table_id)
            elif anchor:
                key = ("anchor", anchor)
            else:
                continue
            grouped_items.setdefault(key, []).append(evidence)

        best_rows: List[Dict[str, Any]] = []
        best_score = -1

        def _period_table_direct_operand_rows(group_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
            direct_rows: List[Dict[str, Any]] = []
            for operand_index, operand in enumerate(required_operands, start=1):
                best_row: Dict[str, Any] = {}
                best_row_score = -1.0
                for item in group_items:
                    evidence = dict(item or {})
                    metadata = dict(evidence.get("metadata") or {})
                    if not list(metadata.get("structured_cells") or []):
                        continue
                    table_has_period_columns = bool(
                        _normalise_spaces(str(metadata.get("period_labels") or ""))
                        or re.search(
                            str(CALCULATION_SLOT_POLICY.get("period_presence_pattern") or KOREAN_PERIOD_PREFIX_RE_FRAGMENT),
                            _normalise_spaces(str(metadata.get("table_header_context") or "")),
                        )
                    )
                    if not table_has_period_columns:
                        continue
                    row = self._lookup_row_from_direct_structured_evidence(
                        operand,
                        evidence,
                        index=operand_index,
                    )
                    if not row:
                        continue
                    score = score_direct_structured_lookup_evidence(
                        DirectStructuredLookupEvidenceScoreInput(
                            operand=operand,
                            evidence_item=evidence,
                        )
                    ).score
                    if score > best_row_score:
                        best_row = row
                        best_row_score = score
                if not best_row:
                    return []
                direct_rows.append(best_row)
            if _missing_required_operands(required_operands, direct_rows):
                return []
            if _ratio_operand_rows_collapse_to_same_slot(direct_rows):
                return []
            return merge_operand_rows(
                direct_rows,
                [],
                required_operands=required_operands,
            )

        for group_key, group_items in grouped_items.items():
            if len(group_items) < 2 and group_key[0] != "table":
                continue
            rows = _period_table_direct_operand_rows(group_items)
            if not rows:
                rows = self._required_operand_rows_from_candidates(
                    group_items,
                    required_operands=required_operands,
                    query=query,
                    topic=topic,
                    report_scope=report_scope,
                    require_direct_support=True,
                )
            else:
                rows = _filter_operand_rows_by_required_surface_contract(
                    rows,
                    group_items,
                    required_operands,
                    require_direct_support=True,
                )
            if _missing_required_operands(required_operands, rows):
                continue
            if _ratio_operand_rows_collapse_to_same_slot(rows):
                continue
            unit_count = len(
                {
                    _normalise_spaces(str(row.get("raw_unit") or ""))
                    for row in rows
                    if _normalise_spaces(str(row.get("raw_unit") or ""))
                }
            )
            schema_score = 0
            for row in rows:
                statement_type = _normalise_spaces(str(row.get("statement_type") or "")).lower()
                consolidation_scope = _normalise_spaces(str(row.get("consolidation_scope") or "")).lower()
                matched_role = _normalise_spaces(str(row.get("matched_operand_role") or "")).lower()
                if statement_type == "income_statement":
                    schema_score += 8
                elif statement_type == "segment_note":
                    schema_score -= 2
                if consolidation_scope == "consolidated":
                    schema_score += 3
                if matched_role:
                    schema_score += 4
                    if matched_role.startswith("denominator") and statement_type == "income_statement":
                        schema_score += 6
            schema_score += _scoped_surface_affinity_priority(
                group_items,
                query=query,
                topic=topic,
                required_operands=required_operands,
                require_segment_operand=True,
                direct_weight=12.0,
                adjustment_weight=-8.0,
            )
            score = len(rows) * 100 + schema_score - unit_count
            if score > best_score:
                best_rows = rows
                best_score = score
        return best_rows

    def _build_period_comparison_operands_from_table_label_context(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        required_operands: List[Dict[str, Any]],
        query: str,
        operation_family: str,
    ) -> List[Dict[str, Any]]:
        operation = _normalise_spaces(str(operation_family or "")).lower()
        if operation not in {"difference", "growth_rate"} or not evidence_items or not required_operands:
            return []
        role_names = {
            _normalise_spaces(str(operand.get("role") or "")).lower()
            for operand in required_operands
            if _normalise_spaces(str(operand.get("role") or ""))
        }
        if not ({"current_period", "prior_period"} <= role_names or {"minuend", "subtrahend"} <= role_names):
            return []

        query_requests_narrative = _query_requests_narrative_context(query)
        query_terms = narrative_context_terms(query) if query_requests_narrative else []

        grouped_items: Dict[tuple[str, str], List[Dict[str, Any]]] = {}
        for item in evidence_items:
            evidence = dict(item or {})
            metadata = dict(evidence.get("metadata") or {})
            if not _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
                continue
            table_id = _normalise_spaces(str(metadata.get("table_source_id") or ""))
            anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
            if table_id:
                key = ("table", table_id)
            elif anchor:
                key = ("anchor", anchor)
            else:
                continue
            grouped_items.setdefault(key, []).append(evidence)

        def _group_surface(items: List[Dict[str, Any]]) -> str:
            return _normalise_spaces(
                " ".join(
                    str(part or "")
                    for item in items
                    for metadata in [dict(item.get("metadata") or {})]
                    for part in (
                        item.get("claim"),
                        item.get("quote_span"),
                        item.get("raw_row_text"),
                        item.get("source_context"),
                        metadata.get("local_heading"),
                        metadata.get("table_context"),
                        metadata.get("table_header_context"),
                        metadata.get("table_summary_text"),
                        metadata.get("table_value_labels_text"),
                    )
                    if str(part or "").strip()
                )
            )

        best_rows: List[Dict[str, Any]] = []
        best_score = -1.0
        for _group_key, group_items in grouped_items.items():
            rows: List[Dict[str, Any]] = []
            for operand in required_operands:
                best_slot: Dict[str, Any] = {}
                best_slot_score = -1.0
                for item in group_items:
                    slot = self._lookup_value_from_table_label_metadata(operand, item)
                    if not slot:
                        continue
                    slot_score = table_label_metadata_lookup_score(slot, item)
                    if slot_score > best_slot_score:
                        best_slot = slot
                        best_slot_score = slot_score
                if not best_slot:
                    continue
                source_row_ids = _clean_source_row_ids([best_slot.get("source_row_id"), best_slot.get("source_row_ids")])
                source_id = _normalise_spaces(str(source_row_ids[0] if source_row_ids else ""))
                source_item = next(
                    (
                        dict(item)
                        for item in group_items
                        if _normalise_spaces(str(item.get("evidence_id") or "")) == source_id
                    ),
                    dict(group_items[0]),
                )
                source_metadata = dict(source_item.get("metadata") or {})
                rows.append(
                    {
                        "operand_id": _normalise_spaces(str(operand.get("role") or f"op_{len(rows) + 1:03d}")),
                        "evidence_id": source_id,
                        "source_row_id": source_id,
                        "source_row_ids": source_row_ids,
                        "source_anchor": _normalise_spaces(str(best_slot.get("source_anchor") or "")),
                        "label": _normalise_spaces(str(best_slot.get("label") or operand.get("label") or "")),
                        "raw_value": _normalise_spaces(str(best_slot.get("raw_value") or "")),
                        "raw_unit": _normalise_spaces(str(best_slot.get("raw_unit") or "")),
                        "normalized_value": best_slot.get("normalized_value"),
                        "normalized_unit": _normalise_spaces(str(best_slot.get("normalized_unit") or "")),
                        "period": _normalise_spaces(str(best_slot.get("period") or operand.get("period") or "")),
                        "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
                        "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
                        "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
                        "statement_type": best_slot.get("statement_type") or source_metadata.get("statement_type"),
                        "consolidation_scope": best_slot.get("consolidation_scope") or source_metadata.get("consolidation_scope"),
                        "table_source_id": best_slot.get("table_source_id") or source_metadata.get("table_source_id"),
                        "binding_policy": dict(operand.get("binding_policy") or {}),
                        "stated_change_raw_value": _normalise_spaces(str(best_slot.get("stated_change_raw_value") or "")),
                        "stated_change_raw_unit": _normalise_spaces(str(best_slot.get("stated_change_raw_unit") or "")),
                    }
                )
            if _missing_required_operands(required_operands, rows):
                continue
            if _period_comparison_operand_rows_collapse_to_same_slot(rows):
                continue
            surface = _group_surface(group_items)
            score = float(len(rows) * 100)
            statement_types = {
                _normalise_spaces(str((item.get("metadata") or {}).get("statement_type") or "")).lower()
                for item in group_items
            }
            if query_requests_narrative:
                if "mda" in statement_types:
                    score += 20.0
                score += min(10.0, float(sum(1 for term in query_terms if term and term in surface)))
            if any(_normalise_spaces(str(row.get("stated_change_raw_value") or "")) for row in rows):
                score += 8.0
            header_surface = _normalise_spaces(
                " ".join(
                    str((item.get("metadata") or {}).get("table_header_context") or "")
                    for item in group_items
                )
            )
            period_presence_pattern = str(
                CALCULATION_SLOT_POLICY.get("period_presence_pattern")
                or KOREAN_PERIOD_PREFIX_RE_FRAGMENT
            )
            fiscal_period_presence_pattern = str(
                CALCULATION_SLOT_POLICY.get("fiscal_period_presence_pattern") or ""
            )
            period_header_count = len(re.findall(period_presence_pattern, header_surface))
            if fiscal_period_presence_pattern:
                period_header_count += len(re.findall(fiscal_period_presence_pattern, header_surface))
            header_has_change_column = bool(
                KOREAN_TABLE_CHANGE_HEADER_LABEL in header_surface
                or re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, header_surface)
            )
            if period_header_count >= 2 and not header_has_change_column:
                score += 60.0
            elif header_has_change_column:
                score -= 40.0
            matched_labels = {
                _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or ""))
                for row in rows
                if _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or ""))
            }
            direct_claim_surface = _normalise_spaces(
                " ".join(str(item.get("claim") or item.get("quote_span") or "") for item in group_items)
            )
            for label in matched_labels:
                if label and (
                    _operand_text_match(direct_claim_surface, {"label": label, "concept": ""})
                    or _text_has_positive_surface(direct_claim_surface, {"label": label, "concept": ""})
                ):
                    score += 6.0
                    break
            source_ids = {
                source_id
                for row in rows
                for source_id in _clean_source_row_ids([row.get("source_row_id"), row.get("source_row_ids")])
            }
            if len(source_ids) == 1:
                score += 4.0
            if score > best_score:
                best_rows = rows
                best_score = score
        return best_rows

    def _realign_period_comparison_results_from_table_label_context(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
        evidence_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not ordered_results or not evidence_items:
            return ordered_results
        def _result_has_complete_period_slots(row: Dict[str, Any]) -> bool:
            calculation_result = dict(row.get("calculation_result") or {})
            status = _normalise_spaces(str(calculation_result.get("status") or row.get("status") or "")).lower()
            if status and status != "ok":
                return False
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            for slot in (current_slot, prior_slot):
                if not answer_slot_has_material(slot):
                    return False
                normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
                raw_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
                if normalized_unit in {"", "UNKNOWN"} and not raw_unit:
                    return False
                if not _clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]):
                    return False
            return True

        task_by_id = {
            str(task.get("task_id") or ""): dict(task)
            for task in (state.get("calc_subtasks") or [])
            if str(task.get("task_id") or "").strip()
        }
        changed = False
        updated_results: List[Dict[str, Any]] = []
        for row in ordered_results:
            result_row = dict(row or {})
            operation_family = self._aggregate_result_operation_family(result_row)
            if operation_family not in {"difference", "growth_rate"}:
                updated_results.append(result_row)
                continue
            has_complete_period_slots = _result_has_complete_period_slots(result_row)
            task = task_by_id.get(str(result_row.get("task_id") or "")) or {}
            required_operands = [
                dict(item)
                for item in (task.get("required_operands") or [])
                if isinstance(item, dict) and bool(item.get("required", True))
            ]
            if not required_operands:
                calculation_result = dict(result_row.get("calculation_result") or {})
                answer_slots = dict(calculation_result.get("answer_slots") or {})
                slot_candidates = [
                    dict(answer_slots.get("current_value") or {}),
                    dict(answer_slots.get("prior_value") or {}),
                ]
                required_operands = [
                    {
                        "label": slot.get("label"),
                        "concept": slot.get("concept"),
                        "role": "current_period" if index == 0 else "prior_period",
                        "required": True,
                        "unit_family": slot.get("normalized_unit"),
                    }
                    for index, slot in enumerate(slot_candidates)
                    if _normalise_spaces(str(slot.get("label") or slot.get("concept") or ""))
                ]
            context_rows = self._build_period_comparison_operands_from_table_label_context(
                evidence_items,
                required_operands=required_operands,
                query=str(state.get("query") or ""),
                operation_family=operation_family,
            )
            if _missing_required_operands(required_operands, context_rows):
                updated_results.append(result_row)
                continue
            context_has_source_stated_change = bool(
                operation_family == "growth_rate"
                and any(_normalise_spaces(str(row.get("stated_change_raw_value") or "")) for row in context_rows)
            )
            if has_complete_period_slots and not context_has_source_stated_change:
                updated_results.append(result_row)
                continue
            active_subtask = {
                **task,
                "task_id": result_row.get("task_id") or task.get("task_id") or "period_comparison",
                "metric_family": result_row.get("metric_family") or task.get("metric_family") or "",
                "metric_label": result_row.get("metric_label") or task.get("metric_label") or "",
                "operation_family": operation_family,
                "required_operands": required_operands,
            }
            plan_state = {
                **dict(state),
                "active_subtask": active_subtask,
                "resolved_calculation_trace": {
                    "calculation_operands": context_rows,
                    "calculation_plan": {},
                    "calculation_result": {},
                },
                "subtask_results": [],
                "tasks": [],
                "artifacts": [],
            }
            planning_trace = _resolve_runtime_calculation_trace(
                dict(plan_state),
                allow_legacy_top_level=False,
            )
            planning_operands = [
                dict(item)
                for item in (planning_trace.get("calculation_operands") or [])
                if isinstance(item, dict)
            ]
            operation_plan_decision = resolve_deterministic_operation_plan(
                plan=self._build_deterministic_operation_plan(plan_state, planning_operands) or {},
                operands=planning_operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            if operation_plan_decision.status == "ready":
                logger.info(
                    "[formula_plan] deterministic op-family mode=%s op=%s vars=%s",
                    operation_plan_decision.selected_plan.get("mode"),
                    operation_plan_decision.selected_plan.get("operation"),
                    len(operation_plan_decision.selected_plan.get("variable_bindings") or []),
                )
            if operation_plan_decision.status == "not_applicable":
                planned = self._plan_formula_calculation_from_operation_decision(
                    plan_state,
                    operation_plan_decision,
                )
                planned_trace = _resolve_runtime_calculation_trace(
                    planned,
                    allow_legacy_top_level=False,
                )
                plan = dict(planned_trace.get("calculation_plan") or {})
            else:
                plan = dict(operation_plan_decision.selected_plan)
            if str(plan.get("status") or "").strip().lower() != "ok":
                updated_results.append(result_row)
                continue
            recalculation_state = {
                **plan_state,
                "resolved_calculation_trace": {
                    "calculation_operands": context_rows,
                    "calculation_plan": plan,
                    "calculation_result": {},
                },
            }
            recalculation_projection = self._run_calculation_candidate(recalculation_state).projection
            recalculated_result = dict(recalculation_projection.calculation_result or {})
            if str(recalculated_result.get("status") or "").strip().lower() != "ok":
                updated_results.append(result_row)
                continue
            updated_answer = _normalise_spaces(
                str(recalculated_result.get("formatted_result") or recalculated_result.get("rendered_value") or "")
            )
            updated_results.append(
                {
                    **result_row,
                    "answer": updated_answer or result_row.get("answer") or "",
                    "status": "ok",
                    "calculation_result": recalculated_result,
                    "calculation_operands": [
                        dict(item)
                        for item in list(recalculation_projection.calculation_operands or context_rows)
                        if isinstance(item, dict)
                    ],
                    "calculation_plan": dict(recalculation_projection.calculation_plan or plan),
                    "source_row_ids": list(recalculated_result.get("source_row_ids") or []),
                    "period_comparison_recovered_from_table_label_context": True,
                }
            )
            changed = True
        return updated_results if changed else ordered_results

    def _ratio_operand_context_evidence_from_docs(
        self,
        docs: List[Any],
        *,
        max_docs: int = 16,
    ) -> List[Dict[str, Any]]:
        context_items: List[Dict[str, Any]] = []
        seen_doc_ids: set[str] = set()

        def _row_level_items_from_table_value_labels(
            *,
            base_evidence_id: str,
            metadata: Dict[str, Any],
            source_anchor: str,
        ) -> List[Dict[str, Any]]:
            value_labels = str(metadata.get("table_value_labels_text") or "").strip()
            row_labels_surface = str(metadata.get("table_row_labels_text") or "").strip()
            if not value_labels or not row_labels_surface:
                return []
            row_labels = [
                _normalise_spaces(label)
                for label in re.split(r"[\n|]+", row_labels_surface)
                if _normalise_spaces(label)
            ]
            row_labels = list(dict.fromkeys(row_labels))
            if not row_labels:
                return []
            unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
            try:
                report_year = int(metadata.get("year"))
            except (TypeError, ValueError):
                report_year = None
            period_headers: List[List[str]] = []
            period_presence_pattern = str(CALCULATION_SLOT_POLICY.get("period_presence_pattern") or KOREAN_PERIOD_PREFIX_RE_FRAGMENT)
            for header_line in str(metadata.get("table_header_context") or "").splitlines():
                header_cells = [
                    _normalise_spaces(cell)
                    for cell in header_line.split("|")
                    if _normalise_spaces(cell)
                ]
                if len(header_cells) <= 1:
                    continue
                candidate_headers = header_cells[1:]
                if not any(re.search(period_presence_pattern, header) for header in candidate_headers):
                    continue
                period_headers = [[header] for header in candidate_headers]
                break
            if not period_headers and report_year is not None:
                period_headers = [
                    [str(report_year), "current"],
                    [str(report_year - 1), "prior"],
                    [KOREAN_TABLE_CHANGE_HEADER_LABEL, "change"],
                ]
            elif not period_headers:
                period_headers = [["current"], ["prior"], ["change"]]

            def _unit_family_for_hint(unit: str) -> str:
                if not _normalise_spaces(unit):
                    return ""
                _value, family = _normalise_operand_value("1", unit)
                return _normalise_spaces(str(family or "")).upper()

            table_unit_family = _unit_family_for_hint(unit_hint)
            row_items: List[Dict[str, Any]] = []
            for row_index, row_label in enumerate(row_labels, start=1):
                if not row_label or not re.search(KOREAN_TABLE_LABEL_ALPHA_RE_FRAGMENT, row_label):
                    continue
                pattern = re.compile(
                    rf"{KOREAN_TABLE_LABEL_LEFT_BOUNDARY_RE_FRAGMENT}{re.escape(row_label)}\s+"
                    r"(?P<value>[\(\)\-+△]?\s*\d[\d,]*(?:\.\d+)?%?(?:\s*%p)?)",
                    flags=re.IGNORECASE,
                )
                cells: List[Dict[str, Any]] = []
                row_unit_hint = ""
                for value_index, match in enumerate(pattern.finditer(value_labels)):
                    raw_value = _normalise_spaces(match.group("value"))
                    if not raw_value:
                        continue
                    raw_unit = unit_hint
                    value_is_percent = "%" in raw_value
                    if value_is_percent:
                        raw_unit = "%"
                    else:
                        local_unit_hint = _resolve_candidate_local_unit_hint(
                            {"metadata": {**metadata, "row_label": row_label}},
                            raw_value,
                        )
                        local_unit_family = _unit_family_for_hint(local_unit_hint)
                        if local_unit_hint and (
                            not unit_hint
                            or table_unit_family in {"", "UNKNOWN"}
                            or local_unit_family == table_unit_family
                        ):
                            raw_unit = local_unit_hint
                            row_unit_hint = row_unit_hint or local_unit_hint
                    normalized_value, _normalized_unit = _normalise_operand_value(raw_value, raw_unit)
                    if normalized_value is None:
                        continue
                    headers = period_headers[value_index] if value_index < len(period_headers) else [f"value_{value_index + 1}"]
                    cells.append(
                        {
                            "value_text": raw_value,
                            "unit_hint": raw_unit,
                            "column_headers": headers,
                            "row_label": row_label,
                        }
                    )
                if not cells:
                    continue
                row_metadata = {
                    **metadata,
                    "unit_hint": row_unit_hint or unit_hint,
                    "row_label": row_label,
                    "semantic_label": row_label,
                    "structured_cells": cells,
                    "direct_row_from_table_value_labels": True,
                }
                quote = _normalise_spaces(
                    " ".join(
                        f"{row_label} {cell.get('value_text')}"
                        for cell in cells[:3]
                        if str(cell.get("value_text") or "").strip()
                    )
                )
                row_items.append(
                    {
                        "evidence_id": f"{base_evidence_id}::row:{row_index}",
                        "source_anchor": source_anchor,
                        "claim": quote,
                        "quote_span": quote,
                        "raw_row_text": quote,
                        "source_context": value_labels,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "metadata": row_metadata,
                    }
                )
            return row_items

        for index, doc_score in enumerate(list(docs or [])[:max_docs], start=1):
            doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
            metadata = dict(getattr(doc, "metadata", {}) or {})
            doc_id = _normalise_spaces(
                str(metadata.get("chunk_uid") or metadata.get("chunk_id") or getattr(doc, "id", "") or index)
            )
            if doc_id in seen_doc_ids:
                continue
            seen_doc_ids.add(doc_id)
            page_content = str(getattr(doc, "page_content", "") or "").strip()
            metadata_context = "\n".join(
                str(metadata.get(key) or "").strip()
                for key in (
                    "table_header_context",
                    "table_summary_text",
                    "table_value_labels_text",
                    "table_row_labels_text",
                    "row_text",
                    "raw_row_text",
                )
                if str(metadata.get(key) or "").strip()
            )
            combined_context = "\n".join(part for part in (page_content, metadata_context) if part).strip()
            normalized_context = _normalise_spaces(combined_context)
            if not normalized_context or not re.search(r"\d", normalized_context):
                continue
            evidence_id = f"ratio_doc_context_{index:03d}"
            source_anchor = self._build_source_anchor(metadata)
            context_items.append(
                {
                    "evidence_id": evidence_id,
                    "source_anchor": source_anchor,
                    "claim": normalized_context[:1200],
                    "quote_span": normalized_context[:240],
                    "raw_row_text": combined_context,
                    "source_context": combined_context,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "metadata": metadata,
                }
            )
            context_items.extend(
                _row_level_items_from_table_value_labels(
                    base_evidence_id=evidence_id,
                    metadata=metadata,
                    source_anchor=source_anchor,
                )
            )
        return context_items

    def _recover_duplicate_growth_prior_operand(
        self,
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

    def _late_runtime_numeric_answer(
        self,
        state: FinancialAgentState,
        final_answer: str,
    ) -> str:
        trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_plan = dict(trace.get("calculation_plan") or {})
        calculation_result = dict(trace.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = _normalise_spaces(
            str(
                answer_slots.get("operation_family")
                or calculation_result.get("operation_family")
                or calculation_plan.get("operation")
                or calculation_plan.get("mode")
                or ""
            )
        ).lower()
        if operation_family not in {"ratio", "growth_rate", "difference", "sum", "aggregate_subtasks"}:
            return ""
        status = _normalise_spaces(str(calculation_result.get("status") or "")).lower()
        if status != "ok":
            return ""
        if operation_family == "aggregate_subtasks":
            if calculation_result.get("stale_result_repaired_from_evidence"):
                formatted_result = _normalise_spaces(
                    str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
                )
                if formatted_result and formatted_result != _normalise_spaces(str(final_answer or "")):
                    return formatted_result
            nested_results = [
                dict(row)
                for row in list(
                    calculation_result.get("subtask_results")
                    or answer_slots.get("subtask_results")
                    or state.get("subtask_results")
                    or []
                )
                if isinstance(row, dict)
            ]
            evidence_rows = [
                dict(item)
                for item in [
                    *list(state.get("evidence_items") or []),
                    *list(state.get("runtime_evidence") or []),
                ]
                if isinstance(item, dict)
            ]
            formatted_result = _normalise_spaces(
                str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
            )
            answer_text = _normalise_spaces(str(final_answer or ""))
            supported_answer = self._supported_aggregate_subtask_answer(nested_results)
            if supported_answer and supported_answer == answer_text:
                return ""
            if (
                formatted_result
                and formatted_result != answer_text
                and self._answer_covers_numeric_projection(formatted_result, nested_results)
                and not growth_answer_has_untraced_numeric_material(
                    formatted_result,
                    nested_results,
                    evidence_rows,
                )
                and (
                    not answer_text
                    or not self._answer_covers_numeric_projection(answer_text, nested_results)
                    or growth_answer_has_untraced_numeric_material(
                        answer_text,
                        nested_results,
                        evidence_rows,
                    )
                )
            ):
                return formatted_result
            conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
                query=str(state.get("query") or ""),
                ordered_results=nested_results,
                evidence_items=evidence_rows,
            )
            conflicting_answer = _normalise_spaces(str(conflicting_narrative.get("answer") or ""))
            if (
                conflicting_answer
                and str(conflicting_narrative.get("operation_family") or "") == "aggregate_subtasks"
                and conflicting_answer != _normalise_spaces(str(final_answer or ""))
            ):
                return conflicting_answer
            if supported_answer and supported_answer != _normalise_spaces(str(final_answer or "")):
                return supported_answer
            return ""
        rendered_value = _normalise_spaces(
            str(
                (answer_slots.get("primary_value") or {}).get("rendered_value")
                or calculation_result.get("rendered_value")
                or ""
            )
        )
        if not rendered_value:
            return ""
        answer_text = _normalise_spaces(str(final_answer or ""))
        if operation_family == "ratio" and financial_answer_slots.ratio_components_are_complete(calculation_result):
            if (
                aggregate_dependency_slot_coherence_rank_for_operands(
                    operation_family="ratio",
                    operands=list(trace.get("calculation_operands") or []),
                    calculation_result=calculation_result,
                    ordered_results=[
                        dict(row) for row in list(state.get("subtask_results") or []) if isinstance(row, dict)
                    ],
                )
                == 0
            ):
                return ""
            compact_answer = self._compact_ratio_answer(
                {
                    **dict(state),
                    "active_subtask": {
                        **dict(state.get("active_subtask") or {}),
                        "metric_label": answer_slots.get("metric_label")
                        or (state.get("active_subtask") or {}).get("metric_label")
                        or "",
                    },
                },
                calculation_result,
            )
            if compact_answer and compact_answer != answer_text:
                return compact_answer
        if rendered_value in answer_text:
            return ""
        if answer_text and not re.search(r"\d", answer_text):
            return ""
        if operation_family == "ratio":
            return self._compact_ratio_answer(
                {
                    **dict(state),
                    "active_subtask": {
                        **dict(state.get("active_subtask") or {}),
                        "metric_label": answer_slots.get("metric_label")
                        or (state.get("active_subtask") or {}).get("metric_label")
                        or "",
                    },
                },
                calculation_result,
            )
        formatted_result = _normalise_spaces(
            str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
        )
        if formatted_result and rendered_value in formatted_result:
            return formatted_result
        return rendered_value

    def _repair_collapsed_ratio_trace_from_evidence(
        self,
        state: FinancialAgentState,
        trace: Dict[str, Any],
    ) -> Dict[str, Any]:
        calculation_plan = dict((trace or {}).get("calculation_plan") or {})
        calculation_result = dict((trace or {}).get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = _normalise_spaces(
            str(
                answer_slots.get("operation_family")
                or calculation_result.get("operation_family")
                or calculation_plan.get("operation")
                or ""
            )
        ).lower()
        if operation_family != "ratio":
            return trace
        if _normalise_spaces(str(calculation_result.get("status") or "")).lower() != "ok":
            return trace
        components_by_group = dict(answer_slots.get("components_by_group") or {})
        numerator_slots = [
            dict(item)
            for item in list(components_by_group.get("numerator") or [])
            if isinstance(item, dict)
        ]
        denominator_slots = [
            dict(item)
            for item in list(components_by_group.get("denominator") or [])
            if isinstance(item, dict)
        ]
        if not numerator_slots or not denominator_slots:
            return trace

        def _slot_identity(slot: Dict[str, Any]) -> tuple[str, str]:
            source_ids = "|".join(_clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]))
            try:
                normalized = f"{float(slot.get('normalized_value')):.6f}"
            except (TypeError, ValueError):
                normalized = _normalise_spaces(str(slot.get("normalized_value") or slot.get("raw_value") or ""))
            return source_ids, normalized

        numerator_identity = _slot_identity(numerator_slots[0])
        denominator_identity = _slot_identity(denominator_slots[0])
        if not all(numerator_identity) or numerator_identity != denominator_identity:
            return trace

        evidence_rows = [
            dict(item)
            for item in [
                *list(state.get("evidence_items") or []),
                *list(state.get("runtime_evidence") or []),
            ]
            if isinstance(item, dict)
        ]
        for index, item in enumerate(list(state.get("seed_retrieved_docs") or []) + list(state.get("retrieved_docs") or [])):
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
            evidence_rows.append(
                {
                    "evidence_id": f"retrieved::{index + 1:03d}",
                    "claim": page_content,
                    "quote_span": page_content,
                    "source_anchor": metadata.get("source_anchor")
                    or metadata.get("section_path")
                    or metadata.get("section")
                    or "",
                    "metadata": metadata,
                }
            )
        if not evidence_rows:
            return trace
        aggregate_tokens = tuple(
            _normalise_spaces(str(item))
            for item in (STRUCTURED_CELL_AFFINITY_POLICY.get("aggregate_tokens") or ())
            if _normalise_spaces(str(item))
        )

        def _label_terms(slot: Dict[str, Any]) -> List[str]:
            text = _normalise_spaces(str(slot.get("label") or ""))
            if not text:
                text = _normalise_spaces(str(slot.get("concept") or ""))
            terms = [
                term
                for term in narrative_context_terms(text)
                if len(term) >= 2
            ]
            return list(dict.fromkeys(terms))

        def _candidate_for_slot(slot: Dict[str, Any], role_group: str) -> Dict[str, Any]:
            terms = _label_terms(slot)
            if not terms:
                return {}
            preferred_anchor = _normalise_spaces(str(slot.get("source_anchor") or ""))

            def _anchor_compatible(evidence: Dict[str, Any]) -> bool:
                if not preferred_anchor:
                    return False
                metadata = dict(evidence.get("metadata") or {})
                candidate_anchor = _normalise_spaces(
                    str(
                        evidence.get("source_anchor")
                        or metadata.get("source_anchor")
                        or metadata.get("section_path")
                        or metadata.get("section")
                        or ""
                    )
                )
                if not candidate_anchor:
                    return False
                return preferred_anchor in candidate_anchor or candidate_anchor in preferred_anchor

            ranked: List[tuple[int, int, int, int, Dict[str, Any]]] = []
            for evidence in evidence_rows:
                metadata = dict(evidence.get("metadata") or {})
                surface = _normalise_spaces(
                    " ".join(
                        str(evidence.get(key) or "")
                        for key in ("claim", "quote_span", "raw_row_text", "source_context")
                        if str(evidence.get(key) or "").strip()
                    )
                )
                if not surface:
                    continue
                matched_terms = [term for term in terms if term in surface]
                if not matched_terms:
                    continue
                if role_group == "numerator" and len(terms) > 1 and len(matched_terms) < len(terms):
                    continue
                candidates = [
                    candidate
                    for candidate in [
                        *extract_numeric_surface_candidates(surface),
                        *numeric_candidates_with_spans_from_surface(surface, metadata),
                    ]
                    if candidate.get("normalized_value") is not None or candidate.get("value") is not None
                ]
                expected_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
                if expected_unit:
                    candidates = [
                        candidate
                        for candidate in candidates
                        if _normalise_spaces(str(candidate.get("normalized_unit") or "")).upper() == expected_unit
                    ]
                if not candidates:
                    continue
                aggregate_score = (
                    1
                    if role_group == "denominator"
                    and any(token and token in surface for token in aggregate_tokens)
                    else 0
                )
                label_score = len(matched_terms)
                evidence_id = str(evidence.get("evidence_id") or "")
                if evidence_id.startswith("retrieved::"):
                    source_score = 0
                elif evidence_id.startswith("operand::"):
                    source_score = 2
                else:
                    source_score = 3
                provenance_score = 4 if _anchor_compatible(evidence) else -3 if preferred_anchor else 0
                for candidate in candidates:
                    span_start = -1
                    span = candidate.get("span")
                    if isinstance(span, (list, tuple)) and span:
                        try:
                            span_start = int(span[0])
                        except (TypeError, ValueError):
                            span_start = -1
                    anchor_positions = [
                        surface.find(term)
                        for term in matched_terms
                        if term and surface.find(term) >= 0
                    ]
                    if role_group == "denominator":
                        aggregate_anchor_positions = [
                            surface.find(token)
                            for token in aggregate_tokens
                            if token and surface.find(token) >= 0
                        ]
                        if aggregate_anchor_positions:
                            anchor_positions = aggregate_anchor_positions
                    distance_score = 0
                    if span_start >= 0 and anchor_positions:
                        distance_score = -min(abs(span_start - position) for position in anchor_positions)
                    span_score = 1 if span_start >= 0 else 0
                    ranked.append(
                        (
                            label_score + aggregate_score + source_score + provenance_score,
                            span_score,
                            distance_score,
                            provenance_score,
                            {
                                "candidate": dict(candidate),
                                "evidence": evidence,
                            },
                        )
                    )
            if not ranked:
                return {}
            ranked.sort(key=lambda item: (item[0], item[1], item[2], item[3]), reverse=True)
            return ranked[0][4]

        numerator_match = _candidate_for_slot(numerator_slots[0], "numerator")
        denominator_match = _candidate_for_slot(denominator_slots[0], "denominator")
        if not numerator_match or not denominator_match:
            return trace
        numerator_candidate = dict(numerator_match.get("candidate") or {})
        denominator_candidate = dict(denominator_match.get("candidate") or {})
        try:
            numerator_value = float(numerator_candidate.get("normalized_value", numerator_candidate.get("value")))
            denominator_value = float(denominator_candidate.get("normalized_value", denominator_candidate.get("value")))
        except (TypeError, ValueError):
            return trace
        if denominator_value == 0 or numerator_value == denominator_value:
            return trace
        result_value = (numerator_value / denominator_value) * 100.0
        rendered_value = calculation_rendering.format_ratio_percent_result(result_value)

        def _updated_slot(slot: Dict[str, Any], match: Dict[str, Any], normalized_value: float) -> Dict[str, Any]:
            candidate = dict(match.get("candidate") or {})
            evidence = dict(match.get("evidence") or {})
            raw_value = _normalise_spaces(str(candidate.get("value_text") or candidate.get("raw_value") or ""))
            if not raw_value and candidate.get("value") is not None:
                display_step = candidate.get("display_step")
                try:
                    if display_step:
                        raw_value = f"{float(candidate.get('value')) / float(display_step):,.0f}"
                    else:
                        raw_value = f"{float(candidate.get('value')):g}"
                except (TypeError, ValueError):
                    raw_value = _normalise_spaces(str(candidate.get("value") or ""))
            raw_unit = _normalise_spaces(str(candidate.get("unit_text") or candidate.get("unit") or slot.get("raw_unit") or ""))
            rendered = _normalise_spaces(f"{raw_value}{raw_unit}") if raw_unit else raw_value
            source_ids = _clean_source_row_ids([evidence.get("evidence_id"), evidence.get("source_row_id"), evidence.get("source_row_ids")])
            return {
                **dict(slot),
                "raw_value": raw_value or slot.get("raw_value"),
                "raw_unit": raw_unit or slot.get("raw_unit"),
                "normalized_value": normalized_value,
                "normalized_unit": candidate.get("normalized_unit") or slot.get("normalized_unit"),
                "rendered_value": rendered or slot.get("rendered_value"),
                "source_row_id": source_ids[0] if source_ids else slot.get("source_row_id"),
                "source_row_ids": source_ids or slot.get("source_row_ids"),
                "source_anchor": evidence.get("source_anchor") or slot.get("source_anchor"),
            }

        updated_numerator = _updated_slot(numerator_slots[0], numerator_match, numerator_value)
        updated_denominator = _updated_slot(denominator_slots[0], denominator_match, denominator_value)
        updated_components_by_group = dict(components_by_group)
        updated_components_by_group["numerator"] = [updated_numerator, *numerator_slots[1:]]
        updated_components_by_group["denominator"] = [updated_denominator, *denominator_slots[1:]]
        updated_components_by_role = dict(answer_slots.get("components_by_role") or {})
        numerator_role = str(updated_numerator.get("role") or "numerator_1")
        denominator_role = str(updated_denominator.get("role") or "denominator_1")
        updated_components_by_role[numerator_role] = [updated_numerator]
        updated_components_by_role[denominator_role] = [updated_denominator]
        source_row_ids = _clean_source_row_ids([
            updated_numerator.get("source_row_id"),
            updated_numerator.get("source_row_ids"),
            updated_denominator.get("source_row_id"),
            updated_denominator.get("source_row_ids"),
        ])
        updated_slots = {
            **answer_slots,
            "components_by_group": updated_components_by_group,
            "components_by_role": updated_components_by_role,
            "source_row_ids": source_row_ids,
            "primary_value": {
                **dict(answer_slots.get("primary_value") or {}),
                "normalized_value": result_value,
                "normalized_unit": "PERCENT",
                "raw_unit": "%",
                "rendered_value": rendered_value,
                "source_row_id": source_row_ids[0] if source_row_ids else "",
                "source_row_ids": source_row_ids,
            },
        }
        updated_result = {
            **calculation_result,
            "result_value": result_value,
            "result_unit": "%",
            "rendered_value": rendered_value,
            "formatted_result": "",
            "source_row_ids": source_row_ids,
            "answer_slots": updated_slots,
            "stale_result_repaired_from_evidence": True,
        }
        role_updates = {
            numerator_role: updated_numerator,
            denominator_role: updated_denominator,
        }
        updated_trace = dict(trace or {})
        updated_trace["calculation_operands"] = overlay_calculation_operands_from_slots(
            trace,
            role_updates,
        )
        updated_trace["calculation_result"] = updated_result
        return updated_trace

    def _runtime_evidence_rows_with_context_docs(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        evidence_rows = [
            dict(item)
            for item in [
                *list(state.get("evidence_items") or []),
                *list(state.get("runtime_evidence") or []),
            ]
            if isinstance(item, dict)
        ]
        context_docs = collect_retrieval_context_docs(
            list(state.get("retrieved_docs") or []),
            list(state.get("seed_retrieved_docs") or []),
            seed_limit=48,
        )
        evidence_rows.extend(self._ratio_operand_context_evidence_from_docs(context_docs))
        return evidence_rows

    def _ordered_aggregate_subtask_results_for_repair(
        self,
        *,
        state: FinancialAgentState,
        calculation_result: Dict[str, Any],
        answer_slots: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        structured_result = dict(state.get("structured_result") or {})
        ordered_results: List[Dict[str, Any]] = []
        seen_result_keys: set[str] = set()
        for rows in (
            calculation_result.get("subtask_results"),
            answer_slots.get("subtask_results"),
            structured_result.get("subtask_results"),
            state.get("subtask_results"),
        ):
            for row in list(rows or []):
                if not isinstance(row, dict):
                    continue
                task_id = _normalise_spaces(str(row.get("task_id") or ""))
                dedupe_key = task_id or aggregate_result_signature(dict(row))
                if dedupe_key and dedupe_key in seen_result_keys:
                    continue
                if dedupe_key:
                    seen_result_keys.add(dedupe_key)
                ordered_results.append(dict(row))
        return ordered_results

    def _repair_period_comparison_trace_from_evidence(
        self,
        state: FinancialAgentState,
        trace: Dict[str, Any],
    ) -> Dict[str, Any]:
        calculation_plan = dict((trace or {}).get("calculation_plan") or {})
        calculation_result = dict((trace or {}).get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        operation_family = _normalise_spaces(
            str(
                answer_slots.get("operation_family")
                or calculation_result.get("operation_family")
                or calculation_plan.get("operation")
                or calculation_plan.get("mode")
                or ""
            )
        ).lower()
        if operation_family == "aggregate_subtasks":
            return self._repair_aggregate_period_comparison_trace_from_evidence(
                state=state,
                trace=trace,
                calculation_result=calculation_result,
                answer_slots=answer_slots,
            )
        if operation_family not in {"difference", "growth_rate"}:
            return trace
        if _normalise_spaces(str(calculation_result.get("status") or "")).lower() != "ok":
            return trace
        return self._repair_single_period_comparison_trace_from_evidence(
            state=state,
            trace=trace,
            calculation_plan=calculation_plan,
            calculation_result=calculation_result,
            answer_slots=answer_slots,
            operation_family=operation_family,
        )

    def _repair_aggregate_period_comparison_trace_from_evidence(
        self,
        *,
        state: FinancialAgentState,
        trace: Dict[str, Any],
        calculation_result: Dict[str, Any],
        answer_slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        evidence_rows = self._runtime_evidence_rows_with_context_docs(state)
        ordered_results = self._ordered_aggregate_subtask_results_for_repair(
            state=state,
            calculation_result=calculation_result,
            answer_slots=answer_slots,
        )
        if not ordered_results or not evidence_rows:
            return trace
        final_answer = _normalise_spaces(
            str(calculation_result.get("formatted_result") or calculation_result.get("rendered_value") or "")
        )
        realigned_results = self._realign_period_comparison_results_from_table_label_context(
            ordered_results,
            state,
            evidence_rows,
        )
        if realigned_results is ordered_results and state.get("calc_subtasks"):
            realigned_results = self._realign_period_comparison_results_from_table_label_context(
                ordered_results,
                {**dict(state), "calc_subtasks": []},
                evidence_rows,
            )
        if realigned_results is ordered_results:
            return trace
        numeric_answer = self._preferred_complete_numeric_answer(
            realigned_results,
            query=str(state.get("query") or ""),
            evidence_items=evidence_rows,
        )
        refreshed_payload = (
            self._refresh_numeric_answer_preserving_narrative_context(
                query=str(state.get("query") or ""),
                current_answer=final_answer,
                numeric_answer=numeric_answer,
                ordered_results=realigned_results,
                evidence_items=evidence_rows,
            )
            if numeric_answer
            else {}
        )
        refreshed_answer = _normalise_spaces(str((refreshed_payload or {}).get("answer") or ""))
        refreshed_answer = self._enforce_source_stated_growth_answer_contract(
            refreshed_answer or final_answer,
            realigned_results,
            evidence_items=evidence_rows,
        )
        aggregate_projection = self._rebuild_aggregate_projection(
            realigned_results,
            refreshed_answer or final_answer,
            kept_evidence_ids=None,
        )
        if refreshed_answer:
            aggregate_projection = sync_aggregate_projection_final_answer(
                AggregateProjectionFinalAnswerSyncInput(
                    aggregate_projection=aggregate_projection,
                    final_answer=refreshed_answer,
                    sync_rendered_for_aggregate=True,
                    status_ok=True,
                )
            ).aggregate_projection
        updated_trace = dict(aggregate_projection)
        updated_result = dict(updated_trace.get("calculation_result") or {})
        updated_result["stale_result_repaired_from_evidence"] = True
        updated_trace["calculation_result"] = updated_result
        return updated_trace

    def _repair_single_period_comparison_trace_from_evidence(
        self,
        *,
        state: FinancialAgentState,
        trace: Dict[str, Any],
        calculation_plan: Dict[str, Any],
        calculation_result: Dict[str, Any],
        answer_slots: Dict[str, Any],
        operation_family: str,
    ) -> Dict[str, Any]:
        evidence_rows = self._runtime_evidence_rows_with_context_docs(state)
        if not evidence_rows:
            return trace
        task_id = _normalise_spaces(
            str(
                calculation_result.get("task_id")
                or calculation_plan.get("task_id")
                or (state.get("active_subtask") or {}).get("task_id")
                or "runtime_period_comparison"
            )
        )
        ordered_result = {
            "task_id": task_id,
            "metric_family": calculation_result.get("metric_family")
            or calculation_plan.get("metric_family")
            or (state.get("active_subtask") or {}).get("metric_family")
            or "",
            "metric_label": answer_slots.get("metric_label")
            or calculation_result.get("metric_label")
            or calculation_plan.get("metric_label")
            or (state.get("active_subtask") or {}).get("metric_label")
            or "",
            "operation_family": operation_family,
            "status": "ok",
            "answer": calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or "",
            "calculation_result": calculation_result,
        }
        ordered_results = [ordered_result]
        realigned = self._realign_period_comparison_results_from_table_label_context(
            ordered_results,
            state,
            evidence_rows,
        )
        if realigned is ordered_results or not realigned:
            return trace
        realigned_row = dict(realigned[0] or {})
        if not realigned_row.get("period_comparison_recovered_from_table_label_context"):
            return trace
        updated_result = dict(realigned_row.get("calculation_result") or {})
        if _normalise_spaces(str(updated_result.get("status") or "")).lower() != "ok":
            return trace
        updated_trace = dict(trace or {})
        updated_trace["calculation_result"] = {
            **calculation_result,
            **updated_result,
            "stale_result_repaired_from_evidence": True,
        }

        slot_by_role = {
            "current_period": dict((updated_result.get("answer_slots") or {}).get("current_value") or {}),
            "prior_period": dict((updated_result.get("answer_slots") or {}).get("prior_value") or {}),
            "minuend": dict((updated_result.get("answer_slots") or {}).get("current_value") or {}),
            "subtrahend": dict((updated_result.get("answer_slots") or {}).get("prior_value") or {}),
        }
        updated_operands = overlay_calculation_operands_from_slots(
            trace,
            slot_by_role,
            normalize_role=True,
        )
        if updated_operands:
            updated_trace["calculation_operands"] = updated_operands
        return updated_trace

    def _compact_ratio_answer(
        self,
        state: FinancialAgentState,
        calculation_result: Dict[str, Any],
        *,
        active_subtask: Optional[Dict[str, Any]] = None,
        calculation_operands: Optional[Sequence[Dict[str, Any]]] = None,
    ) -> str:
        calculation_result = financial_answer_slots.synchronize_ratio_result_display(
            financial_answer_slots.RatioResultDisplaySyncInput(
                calculation_result=calculation_result,
            )
        ).calculation_result
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        resolved_active_subtask = dict(
            active_subtask
            if active_subtask is not None
            else state.get("active_subtask") or {}
        )
        metric_label = _normalise_spaces(
            str(
                answer_slots.get("metric_label")
                or resolved_active_subtask.get("metric_label")
                or resolved_active_subtask.get("task_id")
                or CALCULATION_RENDER_POLICY.get("ratio_default_metric_label")
                or ""
            )
        )
        primary_value = dict(answer_slots.get("primary_value") or {})
        rendered_value = _normalise_spaces(
            str(primary_value.get("rendered_value") or calculation_result.get("rendered_value") or "")
        )
        render_policy = dict(CALCULATION_RENDER_POLICY)
        period_suffix_pattern = str(render_policy.get("ratio_period_suffix_pattern") or "")
        periods: List[str] = []
        for entries in dict(answer_slots.get("components_by_group") or {}).values():
            for entry in entries or []:
                period = _normalise_spaces(str((entry or {}).get("period") or ""))
                period_key = re.sub(period_suffix_pattern, "", period) if period_suffix_pattern else period
                if period_key and period_key not in periods:
                    periods.append(period_key)
        period_prefix = ""
        period_pattern = str(render_policy.get("ratio_year_period_pattern") or "")
        if len(periods) == 1 and period_pattern and re.fullmatch(period_pattern, periods[0]):
            period_prefix = str(render_policy.get("ratio_period_prefix_template") or "").format(period=periods[0])
        if calculation_operands is None:
            trace = _resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
            resolved_calculation_operands = list(trace.get("calculation_operands") or [])
        else:
            resolved_calculation_operands = [dict(item) for item in calculation_operands]
        scope = financial_answer_slots.ratio_component_consolidation_scope(
            calculation_result,
            resolved_calculation_operands,
        )
        scope_prefixes = dict(render_policy.get("consolidation_scope_answer_prefixes") or {})
        if scope and str(scope_prefixes.get(scope) or ""):
            period_prefix = f"{period_prefix}{scope_prefixes[scope]}"
        components_by_group = dict(answer_slots.get("components_by_group") or {})
        numerator_slots = [
            dict(item)
            for item in list(components_by_group.get("numerator") or [])
            if isinstance(item, dict)
        ]
        denominator_slots = [
            dict(item)
            for item in list(components_by_group.get("denominator") or [])
            if isinstance(item, dict)
        ]
        numerator_slot = numerator_slots[0] if numerator_slots else {}
        denominator_slot = denominator_slots[0] if denominator_slots else {}
        component_slots = [*numerator_slots, *denominator_slots]

        def _shared_krw_component_unit(slots: List[Dict[str, Any]]) -> str:
            if len(slots) < 2:
                return ""
            scale_by_unit = {
                _normalise_spaces(str(unit)): float(scale)
                for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
                if _normalise_spaces(str(unit))
            }
            krw_unit = _normalise_spaces(str(render_policy.get("krw_normalized_unit") or "")).upper()
            units: List[str] = []
            for slot in slots:
                if _normalise_spaces(str(slot.get("normalized_unit") or "")).upper() != krw_unit:
                    return ""
                if slot.get("normalized_value") is None:
                    return ""
                unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
                if unit not in scale_by_unit:
                    return ""
                units.append(unit)
            if len(set(units)) <= 1:
                return ""
            return max(units, key=lambda unit: scale_by_unit.get(unit, 0.0))

        shared_component_unit = _shared_krw_component_unit(component_slots)

        def _component_value(slot: Dict[str, Any]) -> str:
            if shared_component_unit:
                try:
                    converted = calculation_rendering.format_calculation_value_in_display_unit(
                        float(slot.get("normalized_value")),
                        shared_component_unit,
                    )
                except (TypeError, ValueError):
                    converted = ""
                if converted:
                    return converted
            return _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))

        numerator_value = _component_value(numerator_slot)
        denominator_value = _component_value(denominator_slot)
        numerator_label = _display_operand_label(str(numerator_slot.get("label") or ""))
        denominator_label = _display_operand_label(str(denominator_slot.get("label") or ""))
        if (
            metric_label
            and rendered_value
            and numerator_slots
            and denominator_slots
            and (len(numerator_slots) > 1 or len(denominator_slots) > 1)
        ):
            def _component_expression(slots: List[Dict[str, Any]]) -> str:
                terms: List[str] = []
                for slot in slots:
                    label = _display_operand_label(str(slot.get("label") or ""))
                    value = _component_value(slot)
                    if not (label and value):
                        continue
                    terms.append(_normalise_spaces(f"{label} {value}"))
                return " + ".join(dict.fromkeys(terms))

            numerator_expression = _component_expression(numerator_slots)
            denominator_expression = _component_expression(denominator_slots)
            if numerator_expression and denominator_expression:
                return _normalise_spaces(
                    str(render_policy.get("ratio_multi_component_answer_template") or "").format(
                        period_prefix=period_prefix,
                        metric_label=metric_label,
                        rendered_value=rendered_value,
                        numerator_expression=numerator_expression,
                        denominator_expression=denominator_expression,
                    )
                )
        component_template = str(render_policy.get("ratio_component_answer_template") or "")
        if (
            component_template
            and metric_label
            and rendered_value
            and numerator_value
            and denominator_value
            and numerator_label
            and denominator_label
        ):
            return component_template.format(
                period_prefix=period_prefix,
                metric_label=metric_label,
                rendered_value=rendered_value,
                numerator_label=numerator_label,
                numerator_value=numerator_value,
                denominator_label=denominator_label,
                denominator_value=denominator_value,
            )
        if metric_label and rendered_value:
            return str(render_policy.get("ratio_answer_template") or "").format(
                period_prefix=period_prefix,
                metric_label=metric_label,
                rendered_value=rendered_value,
            )
        return rendered_value or metric_label

    def _preferred_ratio_artifact_row_for_conflicting_recalculation(
        self,
        state: FinancialAgentState,
        task: Dict[str, Any],
        recalculated_result: Dict[str, Any],
    ) -> Dict[str, Any]:
        recalculated_value = financial_answer_slots.coerce_slot_numeric(recalculated_result.get("result_value"))
        if recalculated_value is None:
            return {}
        artifact_rows = ratio_result_rows_from_task_artifacts(state, task)
        selection = resolve_ratio_artifact_conflict_selection(
            RatioArtifactConflictSelectionInput(
                artifact_rows=artifact_rows,
                recalculated_value=recalculated_value,
            )
        )
        return selection.selected_artifact_row

    def _build_deterministic_lookup_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if operation_family not in {"lookup", "single_value"}:
            return None

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        required_operands = [self._complete_required_operand_from_ontology(item) for item in required_operands]
        if required_operands:
            matched_rows = [
                row
                for row in operands
                if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
            ]
            if len(required_operands) != 1 or len(matched_rows) != 1:
                missing_info = self._infer_missing_info(state, matched_rows)
                return {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": "direct lookup requires exactly one grounded operand row.",
                    "missing_info": missing_info,
                }
            target_rows = matched_rows
        else:
            if len(operands) != 1:
                return None
            target_rows = operands

        row = dict(target_rows[0])
        operand_id = str(row.get("operand_id") or "").strip()
        if not operand_id:
            return None
        result_unit = str(row.get("raw_unit") or "").strip()
        operation_text = _display_operand_label(str(row.get("label") or active_subtask.get("metric_label") or "조회값"))
        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "lookup",
            "ordered_operand_ids": [operand_id],
            "variable_bindings": [{"variable": "A", "operand_id": operand_id}],
            "formula": "A",
            "pairwise_formula": "",
            "result_unit": result_unit,
            "operation_text": operation_text,
            "explanation": "lookup tasks use a directly grounded value row when available.",
            "missing_info": [],
        }

    def _required_operand_rows_from_candidates(
        self,
        candidate_items: List[Dict[str, Any]],
        *,
        required_operands: List[Dict[str, Any]],
        query: str,
        topic: str,
        report_scope: Dict[str, Any],
        require_direct_support: bool = False,
    ) -> List[Dict[str, Any]]:
        return _filter_operand_rows_by_required_surface_contract(
            self._build_required_operands_from_candidates(
                candidate_items,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
            ),
            candidate_items,
            required_operands,
            require_direct_support=require_direct_support,
        )

    def _merge_required_operand_fallback_rows(
        self,
        state: FinancialAgentState,
        operand_rows: List[Dict[str, Any]],
        candidate_items: List[Dict[str, Any]],
        missing_required: List[Dict[str, Any]],
        *,
        required_operands: List[Dict[str, Any]],
        query: str,
        operation_family: str,
        fallback_label: str,
    ):
        if not missing_required or not candidate_items:
            return operand_rows, missing_required
        fallback_rows = self._required_operand_rows_from_candidates(
            candidate_items,
            required_operands=missing_required,
            query=query,
            topic=state.get("topic") or "",
            report_scope=dict(state.get("report_scope") or {}),
            require_direct_support=operation_family == "ratio",
        )
        if not fallback_rows:
            return operand_rows, missing_required
        logger.info("[calc_operands] %s operand fallback rows=%s", fallback_label, len(fallback_rows))
        operand_rows = merge_operand_rows(
            operand_rows,
            fallback_rows,
            required_operands=required_operands,
        )
        return operand_rows, _missing_required_operands(required_operands, operand_rows) if required_operands else []

    def _build_deterministic_ontology_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        metric_key = self._calc_metric_family(state)

        ontology = get_financial_ontology()
        metric_info = ontology.metric_family(metric_key) or {}
        formula_family = str(metric_info.get("formula_family") or "").strip().lower()
        if not formula_family:
            formula_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if formula_family not in {"ratio", "sum"}:
            return None

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if not required_operands:
            return None

        matched_rows: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        missing_labels: List[str] = []

        def _operand_row_preference_score(row: Dict[str, Any], operand: Dict[str, Any]) -> tuple[int, int, int, int, int]:
            required_role = _normalise_spaces(str(operand.get("role") or "")).lower()
            matched_role = _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()
            role_score = 0
            if required_role and matched_role:
                if matched_role == required_role:
                    role_score = 3
                elif required_role.startswith(("numerator", "denominator")) and matched_role.startswith(
                    "numerator" if required_role.startswith("numerator") else "denominator"
                ):
                    role_score = 2
            required_scope = _normalise_spaces(str(operand.get("consolidation_scope") or "")).lower()
            row_scope = _normalise_spaces(str(row.get("consolidation_scope") or "")).lower()
            scope_score = 0
            if required_scope and row_scope == required_scope:
                scope_score = 2
            elif row_scope == "consolidated":
                scope_score = 1
            statement_type = _normalise_spaces(str(row.get("statement_type") or "")).lower()
            statement_score = 2 if statement_type == "income_statement" else 0
            stage = _normalise_spaces(str(row.get("aggregation_stage") or "")).lower()
            value_role = _normalise_spaces(str(row.get("value_role") or "")).lower()
            aggregate_score = int(value_role == "aggregate") + int(stage in {"direct", "final", "subtotal"})
            source_score = len(_clean_source_row_ids([row.get("source_row_id"), row.get("source_row_ids")]))
            return role_score, scope_score, statement_score, aggregate_score, source_score

        for operand in required_operands:
            candidate_rows = [row for row in operands if _operand_row_matches_requirement(row, operand)]
            required_role = str(operand.get("role") or "").strip()
            role_matched_rows = [
                row
                for row in candidate_rows
                if required_role
                and str(row.get("matched_operand_role") or "").strip()
                and (
                    str(row.get("matched_operand_role") or "").strip() == required_role
                    or (
                        required_role.startswith(("numerator", "denominator"))
                        and str(row.get("matched_operand_role") or "").strip().startswith(
                            "numerator" if required_role.startswith("numerator") else "denominator"
                        )
                    )
                )
            ]
            candidate_pool = role_matched_rows or candidate_rows
            matched_row = max(
                candidate_pool,
                key=lambda row: _operand_row_preference_score(row, operand),
                default=None,
            )
            if matched_row is None:
                missing_labels.append(str(operand.get("label") or "").strip() or "required_operand")
                continue
            matched_rows.append((operand, matched_row))

        if missing_labels:
            return None

        if formula_family == "ratio":
            numerator_pairs = [
                (operand, row)
                for operand, row in matched_rows
                if str(operand.get("role") or "").strip().startswith("numerator")
            ]
            denominator_pairs = [
                (operand, row)
                for operand, row in matched_rows
                if str(operand.get("role") or "").strip().startswith("denominator")
            ]
            if not numerator_pairs or not denominator_pairs:
                return None
            ordered_pairs = numerator_pairs + denominator_pairs
        else:
            numerator_pairs = []
            denominator_pairs = []
            ordered_pairs = matched_rows

        variable_bindings: List[Dict[str, str]] = []
        ordered_operand_ids: List[str] = []
        numerator_vars: List[str] = []
        denominator_vars: List[str] = []
        additive_vars: List[str] = []

        for index, (operand, row) in enumerate(ordered_pairs):
            variable = chr(ord("A") + index)
            operand_id = str(row.get("operand_id") or "").strip()
            if not operand_id:
                return None
            variable_bindings.append({"variable": variable, "operand_id": operand_id})
            ordered_operand_ids.append(operand_id)
            role = str(operand.get("role") or "").strip()
            if formula_family == "ratio":
                if role.startswith("numerator"):
                    numerator_vars.append(variable)
                elif role.startswith("denominator"):
                    denominator_vars.append(variable)
            elif formula_family == "sum":
                additive_vars.append(variable)

        metric_display = (
            str(metric_info.get("display_name") or "").strip()
            or str(active_subtask.get("metric_label") or "").strip()
            or metric_key
        )

        if formula_family == "ratio":
            if not numerator_vars or not denominator_vars:
                return None
            numerator_expr = " + ".join(numerator_vars)
            denominator_expr = " + ".join(denominator_vars)
            denominator_operation_text = " + ".join(
                str(operand.get("label") or "").strip()
                for operand, _row in denominator_pairs
            )
            denominator_aggregation = _normalise_spaces(
                str(
                    active_subtask.get("denominator_aggregation")
                    or metric_info.get("denominator_aggregation")
                    or ""
                )
            ).lower()
            if denominator_aggregation == "average" and len(denominator_vars) > 1:
                denominator_expr = f"(({denominator_expr}) / {len(denominator_vars)})"
                denominator_operation_text = f"average({denominator_operation_text})"
            result_unit = str(active_subtask.get("result_unit") or metric_info.get("result_unit") or "").strip()
            if not result_unit:
                result_unit = "%"
            if result_unit.upper() == "PERCENT":
                result_unit = "%"
            elif result_unit.upper() == "PERCENT_POINT":
                result_unit = "%p"
            percent_result = result_unit in {"%", "퍼센트"} or result_unit.upper() == "PERCENT"
            if result_unit == "%p":
                percent_result = True
            formula = f"(({numerator_expr}) / ({denominator_expr}))"
            operation_suffix = ""
            if percent_result:
                formula = f"{formula} * 100"
                operation_suffix = " * 100"

            numerator_labels = [str(operand.get("label") or "").strip() for operand, _row in numerator_pairs]

            return {
                "status": "ok",
                "mode": "single_value",
                "operation": "ratio",
                "ordered_operand_ids": ordered_operand_ids,
                "variable_bindings": variable_bindings,
                "formula": formula,
                "pairwise_formula": "",
                "result_unit": result_unit,
                "operation_text": f"({' + '.join(numerator_labels)}) / ({denominator_operation_text}){operation_suffix}",
                "explanation": f"{metric_display}의 role에 따라 분자와 분모를 결정해 비율을 계산합니다.",
                "missing_info": [],
            }

        if not additive_vars:
            return None
        additive_labels = [str(operand.get("label") or "").strip() for operand, _row in ordered_pairs]
        result_unit = str(metric_info.get("result_unit") or "").strip()
        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "add",
            "ordered_operand_ids": ordered_operand_ids,
            "variable_bindings": variable_bindings,
            "formula": " + ".join(additive_vars),
            "pairwise_formula": "",
            "result_unit": result_unit,
            "operation_text": " + ".join(additive_labels),
            "explanation": f"{metric_display}에 필요한 concept operand를 합산합니다.",
            "missing_info": [],
        }

    def _build_deterministic_operation_plan(
        self,
        state: FinancialAgentState,
        operands: List[Dict[str, Any]],
        *,
        active_subtask: Optional[Dict[str, Any]] = None,
    ) -> Optional[Dict[str, Any]]:
        resolved_active_subtask = dict(
            active_subtask
            if active_subtask is not None
            else state.get("active_subtask") or {}
        )
        operation_family = str(resolved_active_subtask.get("operation_family") or "").strip().lower()
        required_operands = [
            dict(item)
            for item in (resolved_active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        metric_label = str(
            resolved_active_subtask.get("metric_label")
            or resolved_active_subtask.get("task_id")
            or ""
        ).strip()
        plan = build_deterministic_operation_plan(
            operation_family=operation_family,
            required_operands=required_operands,
            operands=operands,
            metric_label=metric_label,
            difference_result_unit="",
        )
        if operation_family == "difference" and plan and _should_coerce_percent_point_unit(
            str(resolved_active_subtask.get("query") or state["query"]),
            operands,
            plan,
        ):
            plan = {**plan, "result_unit": "%p"}
        return plan

    def _extract_calculation_operands(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Build the operand set for the current calculation subtask.

        The flow is intentionally layered:
        1. direct structured-row extraction from reconciliation
        2. evidence-based fallback extraction
        3. merge partial direct hits with fallback rows
        """
        evidence_items = list(state.get("evidence_items", []) or [])
        evidence_bullets = list(state.get("evidence_bullets", []) or [])
        retrieved_docs = state.get("retrieved_docs", []) or []
        seed_retrieved_docs = state.get("seed_retrieved_docs", []) or []
        evidence_status = str(state.get("evidence_status") or "")
        intent = state.get("intent") or state.get("query_type", "qa")
        query = self._calc_query(state)
        topic = self._calc_topic(state)
        report_scope = dict(state.get("report_scope") or {})
        desired_consolidation_scope = _desired_consolidation_scope(query, report_scope)

        empty_result: Dict[str, Any] = {
            **_calculation_debug_state_update(state, coverage="missing"),
            "answer": "",
            "evidence_items": evidence_items,
            "evidence_bullets": evidence_bullets,
            **_runtime_trace_state_update(
                state,
                calculation_operands=[],
                calculation_plan={},
                calculation_result={},
            ),
        }
        direct_structured_rows = self._extract_structured_operands_from_reconciliation(state)
        reconciliation_evidence = self._evidence_items_from_reconciliation_matches(state)
        if reconciliation_evidence:
            existing_ids = {str(item.get("evidence_id") or "").strip() for item in evidence_items}
            appended = 0
            for item in reconciliation_evidence:
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id and evidence_id in existing_ids:
                    continue
                if evidence_id:
                    existing_ids.add(evidence_id)
                evidence_items.append(item)
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                evidence_bullets.append(f"- {item.get('source_anchor')} {raw_row[:180]} (reconciled)")
                appended += 1
            if appended:
                logger.info("[calc_operands] appended reconciled evidence items=%s", appended)
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        metric_family = str(active_subtask.get("metric_family") or "").strip().lower()
        if operation_family == "concept_lookup" or (not operation_family and metric_family == "concept_lookup"):
            operation_family = "lookup"
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        direct_numeric_grounding = _requires_direct_numeric_grounding(active_subtask)
        surface_contract_evidence = surface_contract_numeric_evidence_items(
            evidence_items,
            required_operands,
        )
        preserve_narrative_context = (
            direct_numeric_grounding
            and _query_requests_narrative_context(str(state.get("query") or ""))
        )
        if direct_numeric_grounding and reconciliation_evidence:
            if preserve_narrative_context:
                evidence_items = self._restrict_direct_numeric_evidence_items(
                    evidence_items,
                    preserve_narrative_context=True,
                )
                evidence_bullets = [
                    f"- {item.get('source_anchor')} {str(item.get('raw_row_text') or item.get('quote_span') or item.get('claim') or '')[:180]} ({'reconciled' if self._is_direct_numeric_table_backed_evidence_item(item) else 'narrative'})"
                    for item in evidence_items
                ]
                logger.info(
                    "[calc_operands] direct numeric task preserves hybrid evidence structured=%s total=%s",
                    len(reconciliation_evidence),
                    len(evidence_items),
                )
            else:
                evidence_items = list(reconciliation_evidence)
                existing_surface_keys = {
                    (
                        str(existing.get("evidence_id") or "").strip(),
                        str(existing.get("source_anchor") or "").strip(),
                        _normalise_spaces(
                            str(
                                existing.get("raw_row_text")
                                or existing.get("quote_span")
                                or existing.get("claim")
                                or ""
                            )
                        ),
                    )
                    for existing in evidence_items
                }
                for item in surface_contract_evidence:
                    evidence_id = str(item.get("evidence_id") or "").strip()
                    source_anchor = str(item.get("source_anchor") or "").strip()
                    row_text = _normalise_spaces(
                        str(item.get("raw_row_text") or item.get("quote_span") or item.get("claim") or "")
                    )
                    surface_key = (evidence_id, source_anchor, row_text)
                    if surface_key in existing_surface_keys:
                        continue
                    existing_surface_keys.add(surface_key)
                    evidence_items.append(item)
                evidence_bullets = [
                    f"- {item.get('source_anchor')} {str(item.get('raw_row_text') or item.get('quote_span') or item.get('claim') or '')[:180]} ({'reconciled' if item in reconciliation_evidence else 'surface-contract'})"
                    for item in evidence_items
                ]
                logger.info(
                    "[calc_operands] direct numeric task restricts evidence to reconciled structured candidates=%s surface_contract=%s total=%s",
                    len(reconciliation_evidence),
                    len(surface_contract_evidence),
                    len(evidence_items),
                )
        if direct_structured_rows:
            evidence_by_id = _evidence_items_by_id(evidence_items)
            direct_structured_rows = [
                self._coerce_operand_row_from_evidence(
                    row,
                    _evidence_item_for_operand_row(row, evidence_by_id),
                )
                for row in direct_structured_rows
            ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not operand_row_conflicts_requested_scope(row, desired_consolidation_scope)
            ]
        direct_target_evidence_pool = [
            dict(item)
            for item in list(evidence_items) + [dict(item) for item in (state.get("runtime_evidence") or []) if isinstance(item, dict)]
            if isinstance(item, dict) and not evidence_item_conflicts_requested_scope(
                dict(item),
                desired_consolidation_scope,
            )
        ]
        if retrieved_docs or seed_retrieved_docs:
            target_context_docs = collect_retrieval_context_docs(
                retrieved_docs,
                seed_retrieved_docs,
                seed_limit=48,
            )
            direct_target_evidence_pool.extend(
                item
                for item in self._ratio_operand_context_evidence_from_docs(target_context_docs, max_docs=48)
                if not evidence_item_conflicts_requested_scope(item, desired_consolidation_scope)
            )
        target_metric_row, target_metric_operand = self._direct_target_metric_operand_from_evidence(
            {
                **dict(state),
                "active_subtask": active_subtask,
            },
            direct_target_evidence_pool,
        )
        if target_metric_row:
            target_evidence_by_id = _evidence_items_by_id(direct_target_evidence_pool)
            target_metric_row = self._coerce_operand_row_from_evidence(
                target_metric_row,
                _evidence_item_for_operand_row(target_metric_row, target_evidence_by_id),
            )
        if target_metric_row and not operand_row_conflicts_requested_scope(
            target_metric_row,
            desired_consolidation_scope,
        ) and not direct_target_metric_row_conflicts_existing_units(
            target_metric_row,
            direct_structured_rows,
            required_operands,
        ):
            direct_structured_rows = [target_metric_row]
            required_operands = [target_metric_operand]
            operation_family = "lookup"
            target_source_ids = set(_clean_source_row_ids([
                target_metric_row.get("evidence_id"),
                target_metric_row.get("source_row_id"),
                target_metric_row.get("source_row_ids"),
            ]))
            existing_evidence_ids = {
                str(item.get("evidence_id") or "").strip()
                for item in evidence_items
                if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
            }
            for item in direct_target_evidence_pool:
                if not isinstance(item, dict):
                    continue
                evidence_id = str(item.get("evidence_id") or "").strip()
                if not evidence_id or evidence_id not in target_source_ids or evidence_id in existing_evidence_ids:
                    continue
                evidence_items.append(dict(item))
                existing_evidence_ids.add(evidence_id)
            active_subtask = {
                **active_subtask,
                "operation_family": "lookup",
                "required_operands": required_operands,
                "direct_target_metric_lookup_preferred": True,
            }
        if direct_structured_rows and (
            required_operands or operation_family in {"lookup", "single_value"}
        ):
            direct_acceptance = resolve_direct_structured_operand_acceptance(
                DirectStructuredOperandAcceptanceInput(
                    direct_operand_rows=direct_structured_rows,
                    evidence_items=evidence_items,
                    required_operands=required_operands,
                    operation_family=operation_family,
                    ambiguity_query=state.get("query") or "",
                    ambiguity_active_subtask=state.get("active_subtask") or {},
                )
            )
            direct_structured_rows = direct_acceptance.accepted_operand_rows
        if direct_structured_rows and required_operands and operation_family in {"lookup", "single_value"}:
            direct_structured_rows = self._prefer_direct_structured_lookup_evidence_rows(
                direct_structured_rows,
                evidence_items=evidence_items_with_runtime(evidence_items, state),
                required_operands=required_operands,
                operation_family=operation_family,
                state=state,
            )
        if direct_structured_rows and required_operands and operation_family == "ratio":
            direct_structured_rows = self._prefer_direct_structured_evidence_rows(
                direct_structured_rows,
                evidence_items=evidence_items_with_runtime(evidence_items, state),
                required_operands=required_operands,
                operation_family=operation_family,
                state=state,
            )
        dependency_state = self._dependency_binding_resolution_state(state)
        dependency_rows = list(dependency_state.get("rows") or [])
        dependency_bindings = list(dependency_state.get("bindings") or [])
        dependency_binding_keys = set(dependency_state.get("binding_keys") or set())
        dependency_resolved_keys = set(dependency_state.get("resolved_keys") or set())
        missing_dependency_bindings = list(dependency_state.get("missing_bindings") or [])
        producer_tasks = [
            *list(state.get("calc_subtasks") or []),
            *list(dict(state.get("semantic_plan") or {}).get("tasks") or []),
        ]
        retry_strategy = self._active_retry_strategy(state)
        synthesis_only_retry = (
            retry_strategy == "synthesize_from_task_outputs"
            and task_prefers_sibling_output_synthesis(state)
        )
        direct_rows_cover_required_operands = bool(
            required_operands
            and direct_structured_rows
            and not _missing_required_operands(required_operands, direct_structured_rows)
        )
        dependency_rows_cover_required_operands = bool(
            required_operands
            and dependency_rows
            and not _missing_required_operands(required_operands, dependency_rows)
        )
        direct_rows_have_coherent_context = bool(
            direct_rows_cover_required_operands
            and _operand_rows_have_single_table_context(direct_structured_rows)
            and not _ratio_operand_rows_collapse_to_same_slot(direct_structured_rows)
            and not _period_comparison_operand_rows_collapse_to_same_slot(direct_structured_rows)
        )

        retrieved_ratio_context_recovered = False
        if operation_family in {"difference", "growth_rate"} and required_operands:
            period_context_evidence = list(evidence_items)
            if retrieved_docs or seed_retrieved_docs:
                period_context_docs = collect_retrieval_context_docs(
                    retrieved_docs,
                    seed_retrieved_docs,
                    seed_limit=48,
                )
                period_context_evidence.extend(
                    item
                    for item in self._ratio_operand_context_evidence_from_docs(period_context_docs, max_docs=64)
                    if not evidence_item_conflicts_requested_scope(item, desired_consolidation_scope)
                )
            period_context_rows = self._build_period_comparison_operands_from_table_label_context(
                period_context_evidence,
                required_operands=required_operands,
                query=query,
                operation_family=operation_family,
            )
            if period_context_rows:
                context_adoption = resolve_recovered_operand_context_adoption(
                    RecoveredOperandContextAdoptionInput(
                        context_kind="period_comparison",
                        current_operand_rows=direct_structured_rows,
                        recovered_operand_rows=period_context_rows,
                        required_operands=required_operands,
                        evidence_items=evidence_items,
                        recovered_evidence_items=period_context_evidence,
                    )
                )
                direct_structured_rows = context_adoption.selected_operand_rows
                evidence_items = context_adoption.evidence_items
                logger.info("[calc_operands] coherent period-comparison table-label rows=%s", len(period_context_rows))
        if operation_family == "ratio" and required_operands and (
            (direct_rows_cover_required_operands and not direct_rows_have_coherent_context)
            or dependency_rows_cover_required_operands
        ):
            ratio_context_docs = collect_retrieval_context_docs(
                retrieved_docs,
                seed_retrieved_docs,
                seed_limit=32,
            )
            ratio_context_evidence = self._ratio_operand_context_evidence_from_docs(
                ratio_context_docs,
                max_docs=64,
            )
            coherent_ratio_rows = self._build_complete_ratio_operands_from_coherent_context(
                ratio_context_evidence,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
            )
            if coherent_ratio_rows:
                retrieved_ratio_context_recovered = True
                context_adoption = resolve_recovered_operand_context_adoption(
                    RecoveredOperandContextAdoptionInput(
                        context_kind="coherent_ratio",
                        current_operand_rows=direct_structured_rows,
                        recovered_operand_rows=coherent_ratio_rows,
                        required_operands=required_operands,
                        evidence_items=evidence_items,
                        recovered_evidence_items=ratio_context_evidence,
                    )
                )
                direct_structured_rows = context_adoption.selected_operand_rows
                evidence_items = context_adoption.evidence_items
                logger.info("[calc_operands] coherent ratio context rows=%s", len(coherent_ratio_rows))
        main_precedence = resolve_main_operand_precedence(
            MainOperandPrecedenceInput(
                operation_family=operation_family,
                required_operands=required_operands,
                direct_rows=direct_structured_rows,
                dependency_rows=dependency_rows,
                dependency_bindings=dependency_bindings,
                dependency_binding_keys=dependency_binding_keys,
                dependency_resolved_keys=dependency_resolved_keys,
                missing_dependency_bindings=missing_dependency_bindings,
                producer_tasks=producer_tasks,
                desired_consolidation_scope=desired_consolidation_scope,
                reconciliation_evidence_present=bool(reconciliation_evidence),
                retrieved_ratio_context_recovered=retrieved_ratio_context_recovered,
            )
        )
        source_selection = main_precedence.source_selection
        direct_structured_rows = main_precedence.selected_operand_rows
        dependency_rows = main_precedence.active_dependency_rows
        dependency_bindings = main_precedence.active_dependency_bindings
        missing_dependency_bindings = main_precedence.missing_dependency_bindings
        rejected_dependency_scope_rows = main_precedence.rejected_dependency_scope_rows
        required_prefers_aggregate_stage = main_precedence.required_prefers_aggregate_stage
        prefer_direct_rows_over_dependency = (
            source_selection.prefer_direct_rows_over_dependency
        )
        if source_selection.dependency_merge_applied:
            logger.info("[calc_operands] dependency task-output operands=%s", len(dependency_rows))
        has_retrieved_docs_for_dependency_fallback = bool(retrieved_docs or seed_retrieved_docs)
        has_active_reconciliation_fallback = bool(reconciliation_evidence)
        allow_dependency_retry_fallback = (
            operation_family in {"ratio", "difference", "growth_rate"}
            and bool(missing_dependency_bindings)
            and (
                has_active_reconciliation_fallback
                or (
                    not bool(rejected_dependency_scope_rows)
                    and (
                        int(state.get("reconciliation_retry_count") or 0) > 0
                        or has_retrieved_docs_for_dependency_fallback
                    )
                )
            )
        )
        if allow_dependency_retry_fallback:
            direct_numeric_grounding = False
        dependency_guard_active = (
            bool(dependency_bindings)
            and bool(missing_dependency_bindings)
            and not allow_dependency_retry_fallback
        )
        if dependency_guard_active:
            coverage = "partial" if direct_structured_rows else "missing"
            logger.info(
                "[calc_operands] dependency binding guard blocks fallback missing_bindings=%s operands=%s",
                len(missing_dependency_bindings),
                len(direct_structured_rows),
            )
            return {
                **_calculation_debug_state_update(
                    state,
                    coverage=coverage,
                    source="dependency_binding_guard",
                    retry_strategy=retry_strategy,
                    dependency_operands=dependency_rows,
                    missing_dependency_bindings=missing_dependency_bindings,
                    rejected_dependency_scope_rows=rejected_dependency_scope_rows,
                    operands=direct_structured_rows,
                ),
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": coverage,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=direct_structured_rows,
                    calculation_plan={},
                    calculation_result={},
                ),
            }
        if direct_structured_rows:
            direct_structured_rows = [
                _canonicalize_structured_operand_reconciliation_refs(row)
                for row in direct_structured_rows
            ]
        # If reconciliation already found every required operand as clean
        # structured rows, skip the broader fallback path entirely.
        if direct_structured_rows and (
            not required_operands or len(direct_structured_rows) >= len(required_operands)
        ):
            logger.info("[calc_operands] structured-row direct operands=%s", len(direct_structured_rows))
            artifact_update = self._operand_set_artifact_update(
                state,
                active_subtask,
                direct_structured_rows,
                status="ok",
                summary=f"{len(direct_structured_rows)} structured operand(s)",
                payload={
                    "calculation_operands": direct_structured_rows,
                    "source": "structured_row_direct",
                },
            )
            return {
                **_calculation_debug_state_update(
                    state,
                    coverage="sufficient",
                    source="structured_row_direct",
                    direct_target_metric_lookup=bool(active_subtask.get("direct_target_metric_lookup_preferred")),
                    dependency_operands=dependency_rows,
                    operands=direct_structured_rows,
                ),
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": "sufficient",
                "active_subtask": active_subtask,
                **artifact_update,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=direct_structured_rows,
                    calculation_plan={},
                    calculation_result={},
                ),
            }
        if synthesis_only_retry:
            synthesis_operands = list(direct_structured_rows)
            if not synthesis_operands and dependency_rows and dependency_state.get("all_resolved"):
                synthesis_operands = list(dependency_rows)
            coverage = "missing"
            if synthesis_operands:
                coverage = (
                    "sufficient"
                    if not _missing_required_operands(required_operands, synthesis_operands)
                    else "partial"
                )
            logger.info(
                "[calc_operands] synthesis-only retry blocks broad fallback coverage=%s operands=%s",
                coverage,
                len(synthesis_operands),
            )
            updates: Dict[str, Any] = {}
            if synthesis_operands:
                updates = self._operand_set_artifact_update(
                    state,
                    active_subtask,
                    synthesis_operands,
                    status=coverage,
                    summary=f"{len(synthesis_operands)} synthesized task-output operand(s)",
                    payload={
                        "calculation_operands": synthesis_operands,
                        "source": "dependency_synthesis_only",
                    },
                    evidence_refs=_clean_source_row_ids(
                        [
                            [
                                row.get("evidence_id"),
                                row.get("source_row_id"),
                                row.get("source_row_ids"),
                            ]
                            for row in synthesis_operands
                        ]
                    ),
                )
            return {
                **_calculation_debug_state_update(
                    state,
                    coverage=coverage,
                    source="dependency_synthesis_only",
                    retry_strategy=retry_strategy,
                    dependency_operands=dependency_rows,
                    operands=synthesis_operands,
                ),
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": coverage,
                **updates,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=synthesis_operands,
                    calculation_plan={},
                    calculation_result={},
                ),
            }
        should_augment_with_docs = (
            not direct_numeric_grounding
            and
            bool(retrieved_docs or seed_retrieved_docs)
            and intent in {"comparison", "trend"}
            and (not evidence_items or evidence_status != "sufficient")
        )
        if should_augment_with_docs:
            candidate_batch = collect_retrieved_operand_evidence_candidates(
                retrieved_docs,
                seed_retrieved_docs,
                existing_evidence_items=evidence_items,
                required_operands=required_operands,
                missing_dependency_bindings=missing_dependency_bindings,
                query=query,
                topic=topic,
                report_scope=report_scope,
                desired_consolidation_scope=desired_consolidation_scope,
                build_source_anchor=self._build_source_anchor,
                build_required_operands_from_candidates=self._build_required_operands_from_candidates,
                extract_ratio_row_candidates=self._extract_ratio_row_candidates,
                extract_ratio_component_candidates=self._extract_ratio_component_candidates,
            )
            if candidate_batch.evidence_items:
                evidence_items = evidence_items + list(candidate_batch.evidence_items)
                evidence_bullets = evidence_bullets + list(candidate_batch.evidence_bullets)
                logger.info(
                    "[calc_operands] augmenting evidence with synthesized retrieved_docs=%s existing=%s",
                    len(candidate_batch.evidence_items),
                    len(state.get("evidence_items", []) or []),
                )
        elif direct_numeric_grounding and (retrieved_docs or seed_retrieved_docs) and (not evidence_items or evidence_status != "sufficient"):
            logger.info("[calc_operands] direct numeric task skips generic retrieved-doc augmentation")
        if not evidence_items:
            return empty_result

        deterministic_required_rows: List[Dict[str, Any]] = []
        if required_operands and not direct_numeric_grounding:
            deterministic_required_rows = self._required_operand_rows_from_candidates(
                evidence_items,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
                require_direct_support=operation_family == "ratio",
            )
            if missing_dependency_bindings and deterministic_required_rows:
                deterministic_required_rows, rejected_rows = filter_direct_rows_by_dependency_producer_scope(
                    bindings=missing_dependency_bindings,
                    operand_rows=deterministic_required_rows,
                    producer_tasks=producer_tasks,
                )
                rejected_dependency_scope_rows.extend(rejected_rows)
            if deterministic_required_rows:
                coherent_required_rows: List[Dict[str, Any]] = []
                if operation_family == "ratio":
                    coherent_required_rows = self._build_complete_ratio_operands_from_coherent_context(
                        evidence_items,
                        required_operands=required_operands,
                        query=query,
                        topic=topic,
                        report_scope=report_scope,
                    )
                candidate_merge = resolve_required_operand_candidate_merge(
                    RequiredOperandCandidateMergeInput(
                        operation_family=operation_family,
                        required_operands=required_operands,
                        current_operand_rows=direct_structured_rows,
                        candidate_operand_rows=deterministic_required_rows,
                        coherent_candidate_rows=coherent_required_rows,
                    )
                )
                direct_structured_rows = candidate_merge.selected_operand_rows
                deterministic_required_rows = candidate_merge.merged_candidate_rows
                logger.info(
                    "[calc_operands] deterministic required-operand rows=%s",
                    len(deterministic_required_rows),
                )

        OperandExtraction = _operand_extraction_model()
        structured_llm = self._llm_for_phase("operand_extraction").with_structured_output(OperandExtraction)
        evidence_text = self._format_evidence_for_prompt(evidence_items, evidence_bullets)
        prompt = _chat_prompt_template_from_template(
            str(CALCULATION_PROMPT_POLICY.get("operand_extraction_prompt_template") or "")
        )
        try:
            extracted: OperandExtraction = (prompt | structured_llm).invoke(
                {"query": query, "evidence": evidence_text}
            )
            operand_rows: List[Dict[str, Any]] = []
            evidence_by_id = _evidence_items_by_id(evidence_items)
            for index, item in enumerate(extracted.operands, start=1):
                row = item.model_dump()
                evidence_item = evidence_by_id.get(str(row.get("evidence_id") or "").strip())
                if evidence_item and evidence_item_conflicts_requested_scope(
                    evidence_item,
                    desired_consolidation_scope,
                ):
                    continue
                row["operand_id"] = f"op_{index:03d}"
                row = self._coerce_operand_row_from_evidence(row, evidence_item)
                if operation_family in {"lookup", "single_value"} and required_operands:
                    direct_support = resolve_post_coercion_llm_direct_support(
                        PostCoercionLlmDirectSupportInput(
                            operand_row=row,
                            evidence_item=evidence_item,
                            required_operands=required_operands,
                        )
                    )
                    if not direct_support.direct_support_accepted:
                        continue
                operand_rows.append(row)
            if required_operands:
                llm_operand_selection = resolve_post_coercion_llm_operand_selection(
                    PostCoercionLlmOperandSelectionInput(
                        operand_rows=operand_rows,
                        evidence_by_id=evidence_by_id,
                        required_operands=required_operands,
                        direct_structured_rows=direct_structured_rows,
                        require_direct_support=operation_family == "ratio",
                        lookup_rematch_required=operation_family in {"lookup", "single_value"},
                    )
                )
                operand_rows = llm_operand_selection.selected_operand_rows

            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            operand_rows, missing_required = self._merge_required_operand_fallback_rows(
                state,
                operand_rows,
                surface_contract_evidence,
                missing_required,
                required_operands=required_operands,
                query=query,
                operation_family=operation_family,
                fallback_label="surface-contract",
            )
            if missing_required and not direct_numeric_grounding:
                operand_rows, missing_required = self._merge_required_operand_fallback_rows(
                    state,
                    operand_rows,
                    evidence_items,
                    missing_required,
                    required_operands=required_operands,
                    query=query,
                    operation_family=operation_family,
                    fallback_label="generic",
                )
            if missing_required and not direct_numeric_grounding and _is_ratio_percent_query(query):
                fallback_rows = self._build_ratio_operands_from_candidates(
                    [item for item in evidence_items if item.get("raw_row_text")],
                    query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if fallback_rows:
                    logger.info("[calc_operands] python ratio fallback operands=%s", len(fallback_rows))
                    operand_rows = merge_operand_rows(
                        operand_rows,
                        fallback_rows,
                        required_operands=required_operands,
                    )
            sibling_context_rows: List[Dict[str, Any]] = []
            coherent_context_rows: List[Dict[str, Any]] = []
            if (
                operation_family == "ratio"
                and required_operands
                and operand_rows
                and not required_prefers_aggregate_stage
            ):
                sibling_context_rows = self._required_operand_rows_from_candidates(
                    evidence_items,
                    required_operands=required_operands,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                    require_direct_support=True,
                )
                coherent_context_rows = self._build_complete_ratio_operands_from_coherent_context(
                    evidence_items,
                    required_operands=required_operands,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
            late_dependency_remerge = resolve_late_dependency_remerge(
                LateDependencyRemergeInput(
                    operation_family=operation_family,
                    required_operands=required_operands,
                    operand_rows=operand_rows,
                    dependency_rows=dependency_rows,
                    sibling_context_rows=sibling_context_rows,
                    coherent_context_rows=coherent_context_rows,
                    prefer_direct_rows_over_dependency=prefer_direct_rows_over_dependency,
                    required_prefers_aggregate_stage=required_prefers_aggregate_stage,
                )
            )
            operand_rows = late_dependency_remerge.operand_rows
            percent_point_operand_filter_applied = _is_percent_point_difference_query(query)
            late_operand_finalization = resolve_late_operand_finalization(
                LateOperandFinalizationInput(
                    operand_rows=operand_rows,
                    direct_structured_rows=direct_structured_rows,
                    dependency_rows=dependency_rows,
                    required_normalized_unit=(
                        "PERCENT" if percent_point_operand_filter_applied else None
                    ),
                )
            )
            operand_rows = late_operand_finalization.operand_rows
            preserved_operand_source = late_operand_finalization.preserved_operand_source
            if late_operand_finalization.operand_filter_applied:
                logger.info("[calc_operands] percent-diff operand filtering retained=%s", len(operand_rows))
            if preserved_operand_source:
                logger.info(
                    "[calc_operands] preserved %s fallback operands from %s",
                    len(operand_rows),
                    preserved_operand_source,
                )
            merged_coverage = extracted.coverage
            if late_operand_finalization.operand_filter_applied:
                if not operand_rows:
                    merged_coverage = "missing"
                elif required_operands:
                    merged_coverage = (
                        "sufficient"
                        if not _missing_required_operands(required_operands, operand_rows)
                        else "partial"
                    )
            elif direct_structured_rows and operand_rows and required_operands:
                merged_coverage = (
                    "sufficient"
                    if not _missing_required_operands(required_operands, operand_rows)
                    else "partial"
                )
            elif preserved_operand_source and operand_rows:
                merged_coverage = (
                    "sufficient"
                    if required_operands and not _missing_required_operands(required_operands, operand_rows)
                    else "partial"
                )
            logger.info("[calc_operands] coverage=%s operands=%s", merged_coverage, len(operand_rows))
            artifact_update = self._operand_set_artifact_update(
                state,
                active_subtask,
                operand_rows,
                status=str(merged_coverage),
                summary=f"{len(operand_rows)} operand(s) from llm/fallback extraction",
                payload={"calculation_operands": operand_rows, "coverage": merged_coverage},
            )
            return {
                **_calculation_debug_state_update(
                    state,
                    coverage=merged_coverage,
                    direct_structured_rows=direct_structured_rows,
                    operands=operand_rows,
                ),
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": str(merged_coverage),
                **artifact_update,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operand_rows,
                    calculation_plan={},
                    calculation_result={},
                ),
            }
        except Exception as exc:
            logger.warning("[calc_operands] structured output failed: %s", exc)
            return {
                **_calculation_debug_state_update(state, coverage="missing", error=str(exc)),
                "evidence_items": evidence_items,
                "evidence_bullets": evidence_bullets,
                "evidence_status": "missing",
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=[],
                    calculation_plan={},
                    calculation_result={},
                ),
            }

    def _plan_formula_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Translate normalized operands into an executable calculation plan."""
        return self._plan_formula_calculation_from_operation_decision(state)

    def _plan_formula_calculation_from_operation_decision(
        self,
        state: FinancialAgentState,
        operation_plan_decision: Any = _OPERATION_PLAN_DECISION_UNSET,
    ) -> Dict[str, Any]:
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        operands = list(runtime_trace.get("calculation_operands") or [])
        query = self._calc_query(state)
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if not operands:
            empty_plan = {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": "no operands",
                "missing_info": self._infer_missing_info(state, []),
            }
            missing_info = self._infer_missing_info(state, [])
            return {
                "missing_info": missing_info,
                "planner_debug_trace": {
                    "llm_invoked": False,
                    "guard_applied": False,
                    "reason": "no operands",
                    "missing_info": missing_info,
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=empty_plan,
                    calculation_result={},
                ),
            }

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict) and bool(item.get("required", True))
        ]
        if required_operands and operation_family in {"ratio", "difference", "growth_rate", "sum"}:
            missing_required = _missing_required_operands(required_operands, operands)
            if missing_required:
                missing_labels = [
                    _normalise_spaces(str(item.get("label") or item.get("role") or item.get("concept") or "operand"))
                    for item in missing_required
                ]
                incomplete_plan = {
                    "status": "incomplete",
                    "mode": "none",
                    "operation": "none",
                    "ordered_operand_ids": [],
                    "variable_bindings": [],
                    "formula": "",
                    "pairwise_formula": "",
                    "result_unit": "",
                    "operation_text": "",
                    "explanation": "missing required operands",
                    "missing_info": missing_labels,
                }
                return {
                    "missing_info": missing_labels,
                    "planner_debug_trace": {
                        "llm_invoked": False,
                        "guard_applied": True,
                        "reason": "missing_required_operands",
                        "missing_info": missing_labels,
                    },
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=operands,
                        calculation_plan=incomplete_plan,
                        calculation_result={},
                    ),
                }

        query_text = _normalise_spaces(query)
        ontology = get_financial_ontology()
        metric_key = self._calc_metric_family(state)
        metric_info = ontology.metric_family(metric_key) if metric_key else None
        deterministic_lookup_plan = self._build_deterministic_lookup_plan(state, operands)
        if deterministic_lookup_plan:
            logger.info(
                "[formula_plan] deterministic lookup mode=%s op=%s vars=%s",
                deterministic_lookup_plan.get("mode"),
                deterministic_lookup_plan.get("operation"),
                len(deterministic_lookup_plan.get("variable_bindings") or []),
            )
            ledger_update = self._calculation_plan_artifact_update(state, deterministic_lookup_plan)
            return {
                "missing_info": [str(item).strip() for item in (deterministic_lookup_plan.get("missing_info") or []) if str(item).strip()],
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_lookup_plan",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": True,
                    "raw_plan": deterministic_lookup_plan,
                },
                **ledger_update,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_lookup_plan,
                    calculation_result={},
                ),
            }

        if operation_plan_decision is _OPERATION_PLAN_DECISION_UNSET:
            operation_plan_decision = resolve_deterministic_operation_plan(
                plan=self._build_deterministic_operation_plan(state, operands) or {},
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            if operation_plan_decision.status == "ready":
                logger.info(
                    "[formula_plan] deterministic op-family mode=%s op=%s vars=%s",
                    operation_plan_decision.selected_plan.get("mode"),
                    operation_plan_decision.selected_plan.get("operation"),
                    len(operation_plan_decision.selected_plan.get("variable_bindings") or []),
                )
        if operation_plan_decision.status == "guarded":
            guarded_plan = dict(operation_plan_decision.selected_plan)
            return {
                "missing_info": list(guarded_plan.get("missing_info") or []),
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_operation_plan_guard",
                    "llm_invoked": False,
                    "guard_applied": True,
                    "reason": "invalid_required_operand_bindings",
                    "raw_plan": dict(operation_plan_decision.raw_plan),
                    "missing_info": list(guarded_plan.get("missing_info") or []),
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=guarded_plan,
                    calculation_result={},
                ),
            }
        if operation_plan_decision.status == "ready":
            deterministic_operation_plan = dict(operation_plan_decision.selected_plan)
            ledger_update = self._calculation_plan_artifact_update(state, deterministic_operation_plan)
            return {
                "missing_info": [],
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_operation_plan",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": True,
                    "raw_plan": deterministic_operation_plan,
                },
                **ledger_update,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_operation_plan,
                    calculation_result={},
                ),
            }

        if operation_family in {"lookup", "single_value"}:
            missing_info = self._infer_missing_info(state, operands)
            guard_plan = {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": "lookup tasks require a single directly grounded operand row.",
                "missing_info": missing_info,
            }
            return {
                "missing_info": missing_info,
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "lookup_guard_reject_non_direct",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": True,
                    "reason": "lookup_non_direct_or_ambiguous",
                    "missing_info": missing_info,
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=guard_plan,
                    calculation_result={},
                ),
            }

        deterministic_plan = self._build_deterministic_ontology_plan(state, operands)
        if deterministic_plan:
            guarded_plan = guard_operation_plan(
                plan=deterministic_plan,
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            if guarded_plan:
                return {
                    "missing_info": list(guarded_plan.get("missing_info") or []),
                    "planner_debug_trace": {
                        "active_metric_family": metric_key,
                        "ontology_context": "deterministic_ontology_plan_guard",
                        "llm_invoked": False,
                        "guard_applied": True,
                        "reason": "invalid_required_operand_bindings",
                        "raw_plan": deterministic_plan,
                        "missing_info": list(guarded_plan.get("missing_info") or []),
                    },
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=operands,
                        calculation_plan=guarded_plan,
                        calculation_result={},
                    ),
                }
            logger.info(
                "[formula_plan] deterministic mode=%s op=%s vars=%s",
                deterministic_plan.get("mode"),
                deterministic_plan.get("operation"),
                len(deterministic_plan.get("variable_bindings") or []),
            )
            ledger_update = self._calculation_plan_artifact_update(state, deterministic_plan)
            return {
                "missing_info": [],
                "planner_debug_trace": {
                    "active_metric_family": metric_key,
                    "ontology_context": "deterministic_ontology_plan",
                    "operands_text": "\n".join(
                        f"- operand_id={row.get('operand_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')}"
                        for row in operands
                    ),
                    "llm_invoked": False,
                    "guard_applied": False,
                    "raw_plan": deterministic_plan,
                },
                **ledger_update,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_plan,
                    calculation_result={},
                ),
            }
        CalculationPlan = _calculation_plan_model()
        structured_llm = self._llm_for_phase("formula_planning").with_structured_output(CalculationPlan)
        ontology_context = ""
        if metric_info:
            components = dict(metric_info.get("components") or {})
            component_lines: List[str] = []
            for role, component in components.items():
                name = str(component.get("name") or "").strip()
                keywords = ", ".join(
                    str(keyword).strip()
                    for keyword in component.get("keywords", [])
                    if str(keyword).strip()
                )
                preferred_sections = ", ".join(
                    str(section).strip()
                    for section in component.get("preferred_sections", [])
                    if str(section).strip()
                )
                bits = [f"{role}={name or '-'}"]
                if keywords:
                    bits.append(f"keywords={keywords}")
                if preferred_sections:
                    bits.append(f"preferred_sections={preferred_sections}")
                component_lines.append(" | ".join(bits))
            preferred_sections = ", ".join(
                str(section).strip()
                for section in metric_info.get("preferred_sections", [])
                if str(section).strip()
            )
            ontology_lines = [
                f"- key={metric_info.get('key', '')}",
                f"- display_name={metric_info.get('display_name', '')}",
                f"- formula_template={metric_info.get('formula_template', '')}",
                f"- result_unit={metric_info.get('result_unit', '')}",
            ]
            if preferred_sections:
                ontology_lines.append(f"- preferred_sections={preferred_sections}")
            if component_lines:
                ontology_lines.append("- components:")
                ontology_lines.extend(f"  - {line}" for line in component_lines)
            ontology_context = "\n".join(ontology_lines)
        operands_text = "\n".join(
            f"- operand_id={row.get('operand_id')} | evidence_id={row.get('evidence_id')} | label={row.get('label')} | raw={row.get('raw_value')} {row.get('raw_unit')} | normalized={row.get('normalized_value')} {row.get('normalized_unit')} | period={row.get('period', '')}"
            for row in operands
        )
        planner_trace_base = {
            "active_metric_family": metric_key,
            "ontology_context": ontology_context or "-",
            "operands_text": operands_text,
        }
        prompt = _chat_prompt_template_from_template(
            str(CALCULATION_PROMPT_POLICY.get("formula_plan_prompt_template") or "")
        )
        try:
            plan: CalculationPlan = (prompt | structured_llm).invoke(
                {
                    "query": query,
                    "operands": operands_text,
                    "ontology_context": ontology_context or "-",
                }
            )
            plan_data = plan.model_dump()
            plan_data.setdefault("status", "ok")
            bindings = plan_data.get("variable_bindings") or []
            if not plan_data.get("ordered_operand_ids") and bindings:
                plan_data["ordered_operand_ids"] = [str(binding.get("operand_id") or "") for binding in bindings if str(binding.get("operand_id") or "").strip()]
            if not bindings and plan_data.get("ordered_operand_ids"):
                plan_data["variable_bindings"] = [
                    {"variable": chr(ord("A") + index), "operand_id": operand_id}
                    for index, operand_id in enumerate(plan_data.get("ordered_operand_ids") or [])
                ]
            if (
                str(plan_data.get("mode") or "").lower() == "none"
                and not (plan_data.get("variable_bindings") or [])
            ):
                plan_data["status"] = "incomplete"
                if not plan_data.get("missing_info"):
                    plan_data["missing_info"] = self._infer_missing_info(state, operands)
            if _should_coerce_percent_point_unit(query_text, operands, plan_data):
                plan_data["result_unit"] = "%p"
            guarded_plan = guard_operation_plan(
                plan=plan_data,
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            guard_applied = False
            raw_plan_data = dict(plan_data)
            if guarded_plan:
                plan_data = guarded_plan
                guard_applied = True
            logger.info("[formula_plan] mode=%s op=%s vars=%s", plan_data.get("mode"), plan_data.get("operation"), len(plan_data.get("variable_bindings") or []))
            ledger_update = self._calculation_plan_artifact_update(state, plan_data)
            return {
                "missing_info": [str(item).strip() for item in (plan_data.get("missing_info") or []) if str(item).strip()],
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": guard_applied,
                    "reason": "invalid_required_operand_bindings" if guard_applied else "",
                    "raw_plan": raw_plan_data if guard_applied else plan_data,
                    "guarded_plan": plan_data if guard_applied else {},
                },
                **ledger_update,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan_data,
                    calculation_result={},
                ),
            }
        except Exception as exc:
            logger.warning("[formula_plan] structured output failed: %s", exc)
            failed_plan = {
                "status": "incomplete",
                "mode": "none",
                "operation": "none",
                "ordered_operand_ids": [],
                "variable_bindings": [],
                "formula": "",
                "pairwise_formula": "",
                "result_unit": "",
                "operation_text": "",
                "explanation": str(exc),
                "missing_info": self._infer_missing_info(state, operands),
            }
            return {
                "missing_info": self._infer_missing_info(state, operands),
                "planner_debug_trace": {
                    **planner_trace_base,
                    "llm_invoked": True,
                    "guard_applied": False,
                    "error": str(exc),
                },
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=failed_plan,
                    calculation_result={},
                ),
            }

    def _complete_required_operand_from_ontology(self, operand: Dict[str, Any]) -> Dict[str, Any]:
        updated = dict(operand or {})
        concept_key = _normalise_spaces(str(updated.get("concept") or ""))
        ontology = get_financial_ontology()
        if not concept_key:
            label_text = _normalise_spaces(
                " ".join(
                    [
                        str(updated.get("label") or ""),
                        str(updated.get("name") or ""),
                        *[str(alias or "") for alias in list(updated.get("aliases") or [])],
                    ]
                )
            )
            leading_period_strip_pattern = str(CALCULATION_SLOT_POLICY.get("leading_period_strip_pattern") or "")
            periodless_label_text = (
                _normalise_spaces(re.sub(leading_period_strip_pattern, " ", label_text))
                if label_text and leading_period_strip_pattern
                else label_text
            )
            matches = [
                dict(item)
                for item in ontology.match_concepts(periodless_label_text or label_text)
                if not item.get("is_group")
            ]
            if len(matches) == 1:
                concept_key = _normalise_spaces(str(matches[0].get("key") or matches[0].get("concept") or ""))
            else:
                exact_matches = []
                for match in matches:
                    aliases = [
                        str(match.get("display_name") or ""),
                        str(match.get("name") or ""),
                        *[str(alias or "") for alias in list(match.get("aliases") or [])],
                        *[str(keyword or "") for keyword in list(match.get("keywords") or [])],
                    ]
                    normalized_aliases = {
                        _normalise_spaces(str(alias))
                        for alias in aliases
                        if _normalise_spaces(str(alias))
                    }
                    if periodless_label_text in normalized_aliases or label_text in normalized_aliases:
                        exact_matches.append(match)
                if len(exact_matches) == 1:
                    concept_key = _normalise_spaces(
                        str(exact_matches[0].get("key") or exact_matches[0].get("concept") or "")
                    )
            if concept_key:
                updated["concept"] = concept_key
        if not concept_key:
            return updated
        concept_spec = _concept_spec_for_key(ontology, concept_key)
        if not concept_spec:
            return updated

        for key in ("unit_family",):
            if not _normalise_spaces(str(updated.get(key) or "")):
                updated[key] = concept_spec.get(key)
        for key in ("aliases", "keywords", "preferred_sections", "preferred_statement_types"):
            updated[key] = list(
                dict.fromkeys(
                    [
                        *[str(item).strip() for item in (updated.get(key) or []) if str(item).strip()],
                        *[str(item).strip() for item in (concept_spec.get(key) or []) if str(item).strip()],
                    ]
                )
            )
        for key in ("binding_policy", "surface_contract"):
            concept_payload = dict(concept_spec.get(key) or {})
            explicit_payload = dict(updated.get(key) or {})
            merged = dict(concept_payload)
            merged.update(explicit_payload)
            if merged:
                updated[key] = merged
        return updated

    def _direct_target_metric_operand_from_evidence(
        self,
        state: FinancialAgentState,
        evidence_items: List[Dict[str, Any]],
    ) -> tuple[Dict[str, Any], Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
        if operation_family in {"ratio", "difference", "growth_rate"}:
            return {}, {}
        metric_label = _normalise_spaces(
            str(active_subtask.get("metric_label") or active_subtask.get("task_id") or "")
        )
        if not metric_label:
            return {}, {}
        target_operand = {
            "label": metric_label,
            "concept": _normalise_spaces(str(active_subtask.get("metric_concept") or "")),
            "role": "primary_value",
            "period": _normalise_spaces(str(active_subtask.get("period") or "")),
            "required": True,
        }
        if hasattr(self, "_complete_required_operand_from_ontology"):
            target_operand = self._complete_required_operand_from_ontology(target_operand)
        candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool(
            target_operand,
            [dict(item) for item in evidence_items if isinstance(item, dict)],
            state=state,
        )
        if not candidate_slot or candidate_score <= 0:
            return {}, {}
        source_row_ids = _clean_source_row_ids([
            candidate_slot.get("source_row_id"),
            candidate_slot.get("source_row_ids"),
        ])
        canonical_source_ids = [
                _canonical_structured_reconciliation_id(source_id)
            for source_id in source_row_ids
        ]
        source_row_ids = list(dict.fromkeys(source_id for source_id in canonical_source_ids if source_id))
        canonical_source_id = source_row_ids[0] if source_row_ids else ""
        operand_id = _normalise_spaces(str(candidate_slot.get("role") or "primary_value")) or "primary_value"
        row = {
            "operand_id": operand_id,
            "evidence_id": canonical_source_id or candidate_slot.get("evidence_id"),
            "source_row_id": canonical_source_id or candidate_slot.get("source_row_id"),
            "source_row_ids": source_row_ids,
            "source_anchor": _normalise_spaces(str(candidate_slot.get("source_anchor") or "")),
            "label": _normalise_spaces(str(candidate_slot.get("label") or metric_label)),
            "raw_value": _normalise_spaces(str(candidate_slot.get("raw_value") or "")),
            "raw_unit": _normalise_spaces(str(candidate_slot.get("raw_unit") or "")),
            "normalized_value": candidate_slot.get("normalized_value"),
            "normalized_unit": _normalise_spaces(str(candidate_slot.get("normalized_unit") or "UNKNOWN")).upper()
            or "UNKNOWN",
            "rendered_value": _normalise_spaces(str(candidate_slot.get("rendered_value") or "")),
            "period": _normalise_spaces(str(candidate_slot.get("period") or target_operand.get("period") or "")),
            "matched_operand_label": metric_label,
            "matched_operand_concept": _normalise_spaces(str(candidate_slot.get("concept") or "")),
            "matched_operand_role": "primary_value",
            "statement_type": candidate_slot.get("statement_type"),
            "consolidation_scope": candidate_slot.get("consolidation_scope"),
            "table_source_id": candidate_slot.get("table_source_id"),
            "value_role": candidate_slot.get("value_role"),
            "aggregation_stage": candidate_slot.get("aggregation_stage"),
            "aggregate_label": candidate_slot.get("aggregate_label"),
            "direct_target_metric_lookup": True,
        }
        return row, target_operand

    def _prepare_calculation_candidate(
        self,
        candidate_input: _CalculationCandidateInput,
    ) -> _PreparedCalculationCandidate:
        """Prepare operands and execute one canonical calculation without state projection."""

        runtime_operands = [dict(row) for row in candidate_input.calculation_operands]
        execution_evidence_items = list(candidate_input.evidence_items) + list(candidate_input.runtime_evidence)
        execution_evidence_by_id = _evidence_items_by_id(
            [dict(item) for item in execution_evidence_items if isinstance(item, dict)]
        )
        runtime_operands = [
            self._coerce_operand_row_from_evidence(
                row,
                _evidence_item_for_operand_row(row, execution_evidence_by_id),
            )
            for row in runtime_operands
        ]
        runtime_operands = repair_krw_operand_units_from_table_metadata(
            runtime_operands,
            execution_evidence_items,
        )
        runtime_operands = repair_krw_normalized_values_from_raw_units(runtime_operands)
        operands = {row.get("operand_id"): row for row in runtime_operands}
        plan = dict(candidate_input.calculation_plan)
        active_subtask = dict(candidate_input.active_subtask)
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        operation = str(plan.get("operation") or "none")
        mode = str(plan.get("mode") or "none")
        ordered_ids = [operand_id for operand_id in (plan.get("ordered_operand_ids") or []) if operand_id in operands]
        variable_bindings = [
            binding for binding in (plan.get("variable_bindings") or [])
            if str(binding.get("operand_id") or "") in operands and str(binding.get("variable") or "").strip()
        ]
        formula = str(plan.get("formula") or "").strip()
        pairwise_formula = str(plan.get("pairwise_formula") or "").strip()
        result_unit = str(plan.get("result_unit") or "")
        explanation = str(plan.get("explanation") or "")

        def _prepared_failure(
            status: str,
            reason: str,
            *,
            calculation_plan: Optional[Dict[str, Any]] = None,
            execution_outcome: Optional[CalculationExecutionOutcome] = None,
        ) -> _PreparedCalculationCandidate:
            return _PreparedCalculationCandidate(
                status=status,
                reason=reason,
                calculation_operands=tuple(dict(row) for row in runtime_operands),
                calculation_plan=dict(calculation_plan if calculation_plan is not None else plan),
                active_subtask=dict(active_subtask),
                query=candidate_input.query,
                operation_family=operation_family,
                result_unit=result_unit,
                execution_outcome=execution_outcome,
                selected_evidence_ids=tuple(
                    execution_outcome.selected_evidence_ids if execution_outcome is not None else ()
                ),
                source_normalized_unit=(
                    execution_outcome.source_normalized_unit if execution_outcome is not None else ""
                ),
            )

        if mode == "none" or not variable_bindings:
            return _prepared_failure(
                "insufficient_operands",
                explanation or "no operation or operands",
            )

        if not ordered_ids:
            ordered_ids = [str(binding.get("operand_id") or "") for binding in variable_bindings]

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict) and bool(item.get("required", True))
        ]
        guarded_plan = guard_operation_plan(
            plan={
                **plan,
                "ordered_operand_ids": ordered_ids,
                "variable_bindings": variable_bindings,
            },
            operands=runtime_operands,
            required_operands=required_operands,
            operation_family=operation_family,
        )
        if guarded_plan:
            return _prepared_failure(
                "insufficient_operands",
                "operation plan does not satisfy required operand bindings",
                calculation_plan=guarded_plan,
            )

        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        rendered_unit_repaired_operands = [
            repair_operand_normalization_from_rendered_unit(row)
            for row in ordered_operands
        ]
        if rendered_unit_repaired_operands != ordered_operands:
            for repaired_row in rendered_unit_repaired_operands:
                repaired_id = str(repaired_row.get("operand_id") or "").strip()
                if repaired_id:
                    operands[repaired_id] = repaired_row
            runtime_operands = [
                dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                for row in runtime_operands
            ]
            ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family == "ratio":
            aligned_ratio_operands = self._align_ratio_operands_with_sibling_table_context(
                ordered_operands,
                execution_evidence_items,
            )
            if aligned_ratio_operands != ordered_operands:
                for aligned_row in aligned_ratio_operands:
                    aligned_id = str(aligned_row.get("operand_id") or "").strip()
                    if aligned_id:
                        operands[aligned_id] = aligned_row
                runtime_operands = [
                    dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                    for row in runtime_operands
                ]
                ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family in {"difference", "growth_rate"} and len(ordered_operands) == 2:
            concept_keys = {
                str(row.get("matched_operand_concept") or "").strip()
                for row in ordered_operands
                if str(row.get("matched_operand_concept") or "").strip()
            }
            if len(concept_keys) <= 1:
                known_rows = [
                    row
                    for row in ordered_operands
                    if str(row.get("normalized_unit") or "").strip().upper() not in {"", "UNKNOWN"}
                ]
                unknown_rows = [
                    row
                    for row in ordered_operands
                    if str(row.get("normalized_unit") or "").strip().upper() in {"", "UNKNOWN"}
                ]
                if len(known_rows) == 1 and len(unknown_rows) == 1:
                    donor = known_rows[0]
                    target = dict(unknown_rows[0])
                    donor_display_unit = str(donor.get("raw_unit") or donor.get("result_unit") or "").strip()
                    if donor_display_unit:
                        target["raw_unit"] = donor_display_unit
                    normalized_value, normalized_unit = _normalise_operand_value(
                        str(target.get("raw_value") or ""),
                        str(target.get("raw_unit") or ""),
                    )
                    if normalized_value is not None and str(normalized_unit or "").strip().upper() not in {"", "UNKNOWN"}:
                        target["normalized_value"] = normalized_value
                        target["normalized_unit"] = normalized_unit
                        target_id = str(target.get("operand_id") or "").strip()
                        if target_id:
                            operands[target_id] = target
                        runtime_operands = [
                            dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                            for row in runtime_operands
                        ]
                        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

                if operation_family == "growth_rate":
                    aligned_operands = align_growth_operand_units_when_raw_scale_matches(ordered_operands)
                    if aligned_operands != ordered_operands:
                        for aligned_row in aligned_operands:
                            aligned_id = str(aligned_row.get("operand_id") or "").strip()
                            if aligned_id:
                                operands[aligned_id] = aligned_row
                        runtime_operands = [
                            dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                            for row in runtime_operands
                        ]
                        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        if operation_family == "growth_rate":
            recovered_operands = self._recover_duplicate_growth_prior_operand(
                ordered_operands,
                list(candidate_input.evidence_items),
            )
            if recovered_operands != ordered_operands:
                for recovered_row in recovered_operands:
                    recovered_id = str(recovered_row.get("operand_id") or "").strip()
                    if recovered_id:
                        operands[recovered_id] = recovered_row
                runtime_operands = [
                    dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                    for row in runtime_operands
                ]
                ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

            if growth_operand_periods_conflict(ordered_operands):
                return _prepared_failure(
                    "insufficient_operands",
                    "growth operands share the same period",
                )

        sign_normalized_operands = apply_operation_sign_policy(
            ordered_operands,
            operation=operation,
            operation_family=operation_family,
        )
        if sign_normalized_operands != ordered_operands:
            for sign_normalized_row in sign_normalized_operands:
                sign_normalized_id = str(sign_normalized_row.get("operand_id") or "").strip()
                if sign_normalized_id:
                    operands[sign_normalized_id] = sign_normalized_row
            runtime_operands = [
                dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                for row in runtime_operands
            ]
            ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        coerced_lookup_operands: List[Dict[str, Any]] = []
        lookup_magnitude_changed = False
        for row in ordered_operands:
            coerced_row = coerce_lookup_magnitude_record(dict(row), None)
            coerced_lookup_operands.append(coerced_row)
            if coerced_row != row:
                lookup_magnitude_changed = True
        if lookup_magnitude_changed:
            for coerced_row in coerced_lookup_operands:
                coerced_id = str(coerced_row.get("operand_id") or "").strip()
                if coerced_id:
                    operands[coerced_id] = coerced_row
            runtime_operands = [
                dict(operands.get(str(row.get("operand_id") or "").strip()) or row)
                for row in runtime_operands
            ]

        execution_outcome = execute_prepared_calculation_plan(
            mode=mode,
            operation=operation,
            formula=formula,
            pairwise_formula=pairwise_formula,
            result_unit=result_unit,
            operands_by_id=operands,
            ordered_operand_ids=ordered_ids,
            variable_bindings=variable_bindings,
        )
        if execution_outcome.status != "ok":
            return _prepared_failure(
                execution_outcome.status,
                execution_outcome.reason,
                execution_outcome=execution_outcome,
            )
        if execution_outcome.result_value is None:
            return _prepared_failure(
                "parse_error",
                "calculation completed without a result value",
                execution_outcome=execution_outcome,
            )
        return _PreparedCalculationCandidate(
            status="ok",
            reason="",
            calculation_operands=tuple(dict(row) for row in runtime_operands),
            calculation_plan=dict(plan),
            active_subtask=dict(active_subtask),
            query=candidate_input.query,
            operation_family=operation_family,
            result_unit=result_unit,
            execution_outcome=execution_outcome,
            selected_evidence_ids=tuple(execution_outcome.selected_evidence_ids),
            source_normalized_unit=execution_outcome.source_normalized_unit,
        )

    def _project_prepared_calculation_candidate(
        self,
        candidate: _PreparedCalculationCandidate,
    ) -> _CalculationCandidateProjection:
        """Compose a deterministic calculation result without ledger or trace writes."""

        plan = dict(candidate.calculation_plan)
        active_subtask = dict(candidate.active_subtask)
        runtime_operands = [dict(row) for row in candidate.calculation_operands]
        operation_family = candidate.operation_family
        operation = str(plan.get("operation") or "none")
        mode = str(plan.get("mode") or "none")
        formula = str(plan.get("formula") or "").strip()
        pairwise_formula = str(plan.get("pairwise_formula") or "").strip()
        result_unit = candidate.result_unit
        explanation = str(plan.get("explanation") or "")
        selected_evidence_ids = list(candidate.selected_evidence_ids)
        source_normalized_unit = candidate.source_normalized_unit

        def _failed_projection(status: str, reason: str) -> _CalculationCandidateProjection:
            failed_result = build_failed_calculation_result(
                active_subtask=active_subtask,
                operation_family=operation_family or "single_value",
                runtime_operands=list(runtime_operands),
                result_unit=result_unit,
                source_normalized_unit=source_normalized_unit or "UNKNOWN",
                status=status,
                reason=reason,
            )
            return _CalculationCandidateProjection(
                status=status,
                reason=reason,
                calculation_operands=tuple(dict(row) for row in runtime_operands),
                calculation_plan=dict(plan),
                calculation_result=failed_result,
                selected_evidence_ids=tuple(selected_evidence_ids),
            )

        execution_outcome = candidate.execution_outcome
        if candidate.status != "ok":
            return _failed_projection(candidate.status, candidate.reason)
        if execution_outcome is None or execution_outcome.result_value is None:
            return _failed_projection(
                "parse_error",
                "calculation completed without a result value",
            )

        ordered_operands = [dict(row) for row in execution_outcome.ordered_operands]
        normalized_unit = execution_outcome.normalized_unit
        result_value = execution_outcome.result_value

        if mode == "time_series":
            try:
                labels = [
                    _display_operand_label(str(row.get("label") or row.get("evidence_id") or ""))
                    for row in ordered_operands
                ]
                metric_names = [re.sub(r"^\d{4}년\s*", "", label).strip() for label in labels]
                metric_name = metric_names[0] if metric_names else "지표"
                result_series = calculation_rendering.time_series_result_series(
                    ordered_operands=ordered_operands,
                    normalized_unit=source_normalized_unit,
                )
                yoy_growth_rates = list(execution_outcome.yoy_growth_rates)
                time_series_display = calculation_rendering.time_series_result_display(
                    result_value=float(result_value),
                    result_unit=result_unit,
                    normalized_unit=source_normalized_unit,
                )
                normalized_unit = time_series_display["normalized_unit"]
                rendered_value = time_series_display["rendered_value"]
                logger.info("[calculator] mode=%s op=%s result=%s", mode, operation, rendered_value)
                calc_result = build_time_series_calculation_result(
                    result_value=float(result_value),
                    result_unit=result_unit,
                    rendered_value=rendered_value,
                    result_series=result_series,
                    operation_family=operation_family,
                    operation=operation,
                    metric_name=metric_name,
                    normalized_unit=normalized_unit,
                    yoy_growth_rates=yoy_growth_rates,
                    formula=formula,
                    pairwise_formula=pairwise_formula,
                    explanation=explanation or str(plan.get("operation_text") or operation or mode),
                )
                return _CalculationCandidateProjection(
                    status="ok",
                    reason="",
                    calculation_operands=tuple(dict(row) for row in runtime_operands),
                    calculation_plan=dict(plan),
                    calculation_result=calc_result,
                    selected_evidence_ids=tuple(selected_evidence_ids),
                )
            except Exception as exc:
                if isinstance(exc, ZeroDivisionError):
                    return _failed_projection("zero_division", str(exc))
                return _failed_projection("parse_error", str(exc))

        formula_result_value = result_value
        result_display_unit = ""
        if ratio_result_has_suspicious_krw_scale(
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=result_value,
            result_unit=result_unit,
            source_normalized_unit=source_normalized_unit,
        ):
            return _failed_projection(
                "scale_mismatch",
                "same-unit KRW ratio produced an implausible percent result; retry with better grounded operands",
            )
        if operation_family == "ratio" and result_value < 0:
            if calculation_rendering.ratio_query_requests_absolute_magnitude(candidate.query):
                result_value = abs(float(result_value))
        if operation_family == "difference" and normalized_unit == "KRW":
            result_display_unit = calculation_rendering.adjusted_difference_source_display_unit(
                active_subtask=active_subtask,
                ordered_operands=ordered_operands,
            )
        display_state = calculation_rendering.scalar_result_display(
            result_value=float(result_value),
            result_unit=result_unit,
            normalized_unit=normalized_unit,
            result_display_unit=result_display_unit,
            operation_family=operation_family,
            ordered_operands=ordered_operands,
        )
        rendered_with_unit = display_state["rendered_with_unit"]
        labels = [
            _display_operand_label(str(row.get("label") or row.get("evidence_id") or ""))
            for row in ordered_operands
        ]
        result_series = calculation_rendering.scalar_result_series(
            ordered_operands=ordered_operands,
            source_normalized_unit=source_normalized_unit,
        )
        scalar_state = build_scalar_calculation_state(
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=float(result_value),
            normalized_unit=normalized_unit,
            result_unit=result_unit,
            rendered_with_unit=rendered_with_unit,
        )
        result_value = scalar_state["result_value"]
        normalized_unit = scalar_state["normalized_unit"]
        result_unit = scalar_state["result_unit"]
        rendered_with_unit = scalar_state["rendered_with_unit"]
        answer_slots = financial_answer_slots.build_answer_slots(
            active_subtask=active_subtask,
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=result_value,
            result_unit=result_display_unit or result_unit,
            normalized_unit=normalized_unit,
            source_normalized_unit=source_normalized_unit,
            current_value=scalar_state["current_value"],
            prior_value=scalar_state["prior_value"],
            delta_value=scalar_state["delta_value"],
            current_period=scalar_state["current_period"],
            prior_period=scalar_state["prior_period"],
            source_row_ids=scalar_state["source_row_ids"],
            current_row=scalar_state["current_row"],
            prior_row=scalar_state["prior_row"],
        )
        logger.info("[calculator] op=%s result=%s", operation, rendered_with_unit)
        calc_result = build_scalar_calculation_result(
            result_value=float(result_value),
            result_unit=result_display_unit or result_unit,
            rendered_with_unit=rendered_with_unit,
            result_series=result_series,
            scalar_state=scalar_state,
            answer_slots=answer_slots,
            operand_labels=labels,
            formula=formula,
            operation_family=operation_family,
            operation=operation,
            formula_result_value=float(formula_result_value),
            explanation=explanation or str(plan.get("operation_text") or operation or mode),
        )
        return _CalculationCandidateProjection(
            status="ok",
            reason="",
            calculation_operands=tuple(dict(row) for row in runtime_operands),
            calculation_plan=dict(plan),
            calculation_result=calc_result,
            selected_evidence_ids=tuple(selected_evidence_ids),
        )

    def _project_calculation_candidate_state(
        self,
        state: FinancialAgentState,
        candidate: _PreparedCalculationCandidate,
        projection: _CalculationCandidateProjection,
    ) -> Dict[str, Any]:
        """Project a candidate into graph state, including success-only ledger updates."""

        operands = [dict(row) for row in projection.calculation_operands]
        plan = dict(projection.calculation_plan)
        calculation_result = dict(projection.calculation_result)
        selected_evidence_ids = list(projection.selected_evidence_ids)

        def _failed_state(result: Dict[str, Any]) -> Dict[str, Any]:
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "selected_claim_ids": selected_evidence_ids,
                "draft_points": [],
                "kept_claim_ids": selected_evidence_ids,
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=result,
                ),
            }

        if projection.status != "ok":
            return _failed_state(calculation_result)

        try:
            return build_success_calculation_state_payload(
                state=state,
                calc_result=calculation_result,
                selected_evidence_ids=selected_evidence_ids,
                runtime_operands=operands,
                calculation_plan=plan,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
            )
        except Exception as exc:
            if str(plan.get("mode") or "none") != "time_series":
                raise
            status = "zero_division" if isinstance(exc, ZeroDivisionError) else "parse_error"
            failed_result = build_failed_calculation_result(
                active_subtask=dict(candidate.active_subtask),
                operation_family=candidate.operation_family or "single_value",
                runtime_operands=operands,
                result_unit=candidate.result_unit,
                source_normalized_unit=candidate.source_normalized_unit or "UNKNOWN",
                status=status,
                reason=str(exc),
            )
            return _failed_state(failed_result)

    def _run_calculation_candidate_input(
        self,
        candidate_input: _CalculationCandidateInput,
    ) -> _CalculationCandidateRun:
        prepared = self._prepare_calculation_candidate(candidate_input)
        projection = self._project_prepared_calculation_candidate(prepared)
        return _CalculationCandidateRun(prepared=prepared, projection=projection)

    def _run_calculation_candidate(self, state: FinancialAgentState) -> _CalculationCandidateRun:
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        return self._run_calculation_candidate_input(
            _CalculationCandidateInput(
                calculation_operands=tuple(
                    dict(row) for row in (runtime_trace.get("calculation_operands") or [])
                ),
                calculation_plan=dict(runtime_trace.get("calculation_plan") or {}),
                active_subtask=dict(state.get("active_subtask") or {}),
                query=self._calc_query(state),
                evidence_items=tuple(state.get("evidence_items") or []),
                runtime_evidence=tuple(state.get("runtime_evidence") or []),
            )
        )

    def _execute_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Execute the planned numeric operation and normalize the result."""
        candidate_run = self._run_calculation_candidate(state)
        return self._project_calculation_candidate_state(
            state,
            candidate_run.prepared,
            candidate_run.projection,
        )

    def _repair_stale_calculation_result_from_operands(
        self,
        state: FinancialAgentState,
        *,
        operands: List[Dict[str, Any]],
        plan: Dict[str, Any],
        calculation_result: Dict[str, Any],
    ) -> _StaleCalculationRepairResult:
        def _unchanged(reason: _StaleCalculationRepairReason) -> _StaleCalculationRepairResult:
            return _StaleCalculationRepairResult(
                repair_applied=False,
                reason=reason,
                calculation_operands=operands,
                calculation_plan=plan,
                calculation_result=calculation_result,
                selected_evidence_ids=(),
            )

        if str(calculation_result.get("status") or "").strip().lower() != "ok":
            return _unchanged("status_not_ok")
        if str(plan.get("mode") or "").strip() != "single_value":
            return _unchanged("mode_not_single_value")
        formula = str(plan.get("formula") or "").strip()
        if not formula:
            return _unchanged("missing_formula")

        answer_slots = dict(calculation_result.get("answer_slots") or {})
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = _normalise_spaces(
            str(answer_slots.get("operation_family") or active_subtask.get("operation_family") or plan.get("operation") or "")
        )
        metric_label = _normalise_spaces(str(answer_slots.get("metric_label") or active_subtask.get("metric_label") or ""))
        if operation_family:
            active_subtask["operation_family"] = operation_family
        if metric_label:
            active_subtask["metric_label"] = metric_label
        if operation_family in {"difference", "growth_rate"} and _period_comparison_operand_rows_collapse_to_same_slot(
            operands
        ):
            return _unchanged("same_slot")

        candidate_state = {
            **dict(state),
            "active_subtask": active_subtask,
        }
        prepared = self._prepare_calculation_candidate(
            _CalculationCandidateInput(
                calculation_operands=tuple(dict(row) for row in operands),
                calculation_plan=dict(plan),
                active_subtask=dict(active_subtask),
                query=self._calc_query(candidate_state),
                evidence_items=tuple(state.get("evidence_items") or []),
                runtime_evidence=tuple(state.get("runtime_evidence") or []),
            )
        )
        execution_outcome = prepared.execution_outcome
        if (
            prepared.status != "ok"
            or execution_outcome is None
            or execution_outcome.result_value is None
        ):
            return _unchanged("preparation_failed")
        stale_assessment = assess_stale_calculation_value(
            expected_value=execution_outcome.result_value,
            calculation_result=calculation_result,
        )
        if not stale_assessment.is_stale:
            return _unchanged(stale_assessment.reason)

        projection = self._project_prepared_calculation_candidate(prepared)
        repaired_result = dict(projection.calculation_result)
        if (
            projection.status != "ok"
            or str(repaired_result.get("status") or "").strip().lower() != "ok"
        ):
            return _unchanged("projection_failed")
        repaired_result["stale_result_repaired_from_operands"] = True
        return _StaleCalculationRepairResult(
            repair_applied=True,
            reason="repaired",
            calculation_operands=[
                dict(row) for row in list(projection.calculation_operands or tuple(operands))
            ],
            calculation_plan=dict(projection.calculation_plan or plan),
            calculation_result=repaired_result,
            selected_evidence_ids=tuple(projection.selected_evidence_ids),
        )

    def _render_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_result = dict(runtime_trace.get("calculation_result") or {})
        plan = dict(runtime_trace.get("calculation_plan") or {})
        operands = list(runtime_trace.get("calculation_operands") or [])
        if not calculation_result:
            return {"answer": "", "compressed_answer": "", "draft_points": []}

        stale_repair = self._repair_stale_calculation_result_from_operands(
            state,
            operands=[dict(row) for row in operands if isinstance(row, dict)],
            plan=plan,
            calculation_result=calculation_result,
        )
        operands = stale_repair.calculation_operands
        plan = stale_repair.calculation_plan
        calculation_result = stale_repair.calculation_result

        def _stale_repair_provenance_update() -> Dict[str, Any]:
            if not stale_repair.repair_applied:
                return {}
            selected_evidence_ids = list(stale_repair.selected_evidence_ids)
            artifact_update = _synchronize_calculation_result_artifact(
                tasks=list(state.get("tasks") or []),
                artifacts=list(state.get("artifacts") or []),
                task_id=str((state.get("active_subtask") or {}).get("task_id") or ""),
                calculation_result=calculation_result,
                evidence_refs=selected_evidence_ids,
            )
            state_update: Dict[str, Any] = {
                "selected_claim_ids": selected_evidence_ids,
                "kept_claim_ids": selected_evidence_ids,
            }
            if bool(artifact_update.get("synchronized")):
                state_update["artifacts"] = list(artifact_update.get("artifacts") or [])
            return state_update

        operation = str(plan.get("operation") or "")
        operation_family = _normalise_spaces(
            str(
                (calculation_result.get("answer_slots") or {}).get("operation_family")
                or calculation_result.get("operation_family")
                or operation
            )
        ).lower()
        result_val = float(calculation_result.get("result_value") or 0)
        direction_hint = calculation_rendering.direction_hint_for_result(
            operation=operation,
            result_value=result_val,
        )
        calculation_result = calculation_rendering.coerce_rendered_value_for_direction(
            calculation_result,
            direction_hint=direction_hint,
            result_value=result_val,
        )

        if str(calculation_result.get("status") or "") != "ok":
            fallback = str(CALCULATION_RENDER_POLICY.get("insufficient_evidence_fallback") or "")
            return {
                "answer": fallback,
                "compressed_answer": fallback,
                "draft_points": [fallback],
            }

        slot_based_difference_answer = calculation_rendering.compose_slot_based_difference_answer(
            query=self._calc_query(state),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=calculation_result,
            answer_slot_has_material=answer_slot_has_material,
        )
        if slot_based_difference_answer:
            calculation_result["formatted_result"] = slot_based_difference_answer
            return {
                "answer": slot_based_difference_answer,
                "compressed_answer": slot_based_difference_answer,
                "draft_points": [slot_based_difference_answer],
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                ),
                **_stale_repair_provenance_update(),
            }

        CalculationRenderOutput = _calculation_render_output_model()
        structured_llm = self._llm_for_phase("calculation_render").with_structured_output(CalculationRenderOutput)
        prompt = _chat_prompt_template_from_template(
            str(CALCULATION_RENDER_POLICY.get("renderer_prompt_template") or "")
        )
        try:
            rendered: CalculationRenderOutput = (prompt | structured_llm).invoke(
                {
                    "query": self._calc_query(state),
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            answer = _normalise_spaces(rendered.final_answer)
        except Exception as exc:
            logger.warning("[calc_renderer] structured output failed, using deterministic fallback: %s", exc)
            answer = str(calculation_result.get("rendered_value") or calculation_result.get("formatted_result") or "").strip()
            if not answer:
                answer = str(CALCULATION_RENDER_POLICY.get("render_generation_failed_fallback") or "")

        answer = calculation_rendering.coerce_sign_aware_subtraction_answer(
            answer,
            calculation_result=calculation_result,
        )
        if operation_family == "ratio" and (
            financial_answer_slots.ratio_components_are_complete(calculation_result)
            or financial_answer_slots.ratio_component_consolidation_scope(calculation_result, operands)
            or ratio_components_have_suspicious_scale(calculation_result)
        ):
            answer = self._compact_ratio_answer(state, calculation_result)

        calculation_result["formatted_result"] = answer
        return {
            "answer": answer,
            "compressed_answer": answer,
            "draft_points": [answer] if answer else [],
            **_runtime_trace_state_update(
                state,
                calculation_operands=operands,
                calculation_plan=plan,
                calculation_result=calculation_result,
            ),
            **_stale_repair_provenance_update(),
        }

    def _verify_calculation_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Sanity-check that the rendered answer still matches the result."""
        answer = _normalise_spaces(str(state.get("answer") or state.get("compressed_answer") or ""))
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        calculation_result = dict(runtime_trace.get("calculation_result") or {})
        plan = dict(runtime_trace.get("calculation_plan") or {})
        operands = list(runtime_trace.get("calculation_operands") or [])

        if not answer:
            return {
                "answer": answer,
                "compressed_answer": answer,
            }

        if str(calculation_result.get("status") or "") != "ok":
            return {
                "answer": answer,
                "compressed_answer": answer,
                **_calculation_debug_state_update(
                    state,
                    verification={
                        "verdict": "skip",
                        "reason": "calculation_status_not_ok",
                    },
                ),
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                ),
            }

        deterministic_fallback = str(
            calculation_result.get("formatted_result")
            or calculation_result.get("rendered_value")
            or answer
        ).strip()
        rendered_value = str(calculation_result.get("rendered_value") or "").strip()
        operation = str(plan.get("operation") or "")
        operation_family = _normalise_spaces(
            str(
                (calculation_result.get("answer_slots") or {}).get("operation_family")
                or calculation_result.get("operation_family")
                or operation
            )
        ).lower()
        result_val = float(calculation_result.get("result_value") or 0)
        render_policy = dict(CALCULATION_RENDER_POLICY)
        direction_hint = calculation_rendering.direction_hint_for_result(
            operation=operation,
            result_value=result_val,
            render_policy=render_policy,
        )
        CalculationVerificationOutput = _calculation_verification_output_model()
        structured_llm = self._llm_for_phase("calculation_verification").with_structured_output(CalculationVerificationOutput)
        prompt = _chat_prompt_template_from_template(
            str(render_policy.get("verification_prompt_template") or "")
        )
        try:
            verified: CalculationVerificationOutput = (prompt | structured_llm).invoke(
                {
                    "query": self._calc_query(state),
                    "answer": answer,
                    "fallback": deterministic_fallback,
                    "direction_hint": direction_hint,
                    "plan_json": json.dumps(plan, ensure_ascii=False, indent=2),
                    "result_json": json.dumps(calculation_result, ensure_ascii=False, indent=2),
                    "operands_json": json.dumps(operands, ensure_ascii=False, indent=2),
                }
            )
            verdict = str(verified.verdict or "keep")
            final_answer = _normalise_spaces(verified.final_answer)
            if verdict == "fallback" or not final_answer:
                final_answer = deterministic_fallback or answer
            final_answer = calculation_rendering.coerce_sign_aware_subtraction_answer(
                final_answer,
                calculation_result=calculation_result,
            )
            if operation_family == "ratio" and (
                financial_answer_slots.ratio_components_are_complete(calculation_result)
                or financial_answer_slots.ratio_component_consolidation_scope(calculation_result, operands)
                or ratio_components_have_suspicious_scale(calculation_result)
            ):
                final_answer = self._compact_ratio_answer(state, calculation_result)
            calculation_result["formatted_result"] = final_answer
            return {
                "answer": final_answer,
                "compressed_answer": final_answer,
                "draft_points": [final_answer] if final_answer else [],
                "unsupported_sentences": [] if verdict == "keep" else [answer],
                "sentence_checks": [
                    {
                        "sentence": answer,
                        "verdict": "keep" if verdict == "keep" else "drop_overextended",
                        "reason": ",".join(verified.issues or []) or verdict,
                        "supporting_claim_ids": state.get("selected_claim_ids", []),
                    }
                ] if answer else [],
                **_calculation_debug_state_update(
                    state,
                    verification={
                        "verdict": verdict,
                        "issues": list(verified.issues or []),
                        "input_answer": answer,
                        "final_answer": final_answer,
                        "rendered_value": rendered_value,
                        "direction_hint": direction_hint,
                    },
                ),
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                ),
            }
        except Exception as exc:
            logger.warning("[calc_verify] structured output failed, keeping rendered answer: %s", exc)
            return {
                "answer": answer,
                "compressed_answer": answer,
                **_calculation_debug_state_update(
                    state,
                    verification={
                        "verdict": "error_keep",
                        "error": str(exc),
                        "input_answer": answer,
                        "rendered_value": rendered_value,
                    },
                ),
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan,
                    calculation_result=calculation_result,
                ),
            }

    def _advance_calculation_subtask(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Persist the finished subtask and move to the next one, if any."""
        current_result = self._capture_current_subtask_result(state)
        subtask_results = self._upsert_subtask_result(
            list(state.get("subtask_results") or []),
            current_result,
        )
        tasks = [dict(task) for task in (state.get("calc_subtasks") or [])]
        active_index = int(state.get("active_subtask_index") or 0)
        next_index = active_index + 1
        if next_index < len(tasks):
            next_task = dict(tasks[next_index])
            return {
                "subtask_results": subtask_results,
                "active_subtask_index": next_index,
                "active_subtask": next_task,
                "subtask_loop_complete": False,
                "subtask_debug_trace": {
                    **dict(state.get("subtask_debug_trace") or {}),
                    "last_completed_task_id": str(current_result.get("task_id") or ""),
                    "next_task_id": str(next_task.get("task_id") or ""),
                },
                "selected_claim_ids": [],
                "draft_points": [],
                "compressed_answer": "",
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "answer": "",
                "citations": [],
                **_clear_calculation_debug_state(),
                "planner_debug_trace": {},
                "missing_info": [],
                "reflection_count": 0,
                "retry_reason": "",
                "retry_queries": [],
                "reconciliation_retry_count": 0,
                "reflection_plan": {},
                "reconciliation_result": {},
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=[],
                    calculation_plan={},
                    calculation_result={},
                ),
            }
        return {
            "subtask_results": subtask_results,
            "subtask_loop_complete": True,
            "subtask_debug_trace": {
                **dict(state.get("subtask_debug_trace") or {}),
                "last_completed_task_id": str(current_result.get("task_id") or ""),
                "next_task_id": "",
            },
        }

    def _prepare_initial_aggregate_state(self, state: FinancialAgentState) -> _PreparedAggregateState:
        current_result = self._capture_current_subtask_result(state)
        subtask_results = self._upsert_subtask_result(
            list(state.get("subtask_results") or []),
            current_result,
        )
        order_map = {
            str(task.get("task_id") or ""): index
            for index, task in enumerate(state.get("calc_subtasks") or [])
        }
        ordered_results = sorted(
            subtask_results,
            key=lambda row: (order_map.get(str(row.get("task_id") or ""), 10_000), str(row.get("task_id") or "")),
        )
        ordered_results = dedupe_aggregate_subtask_results(ordered_results)
        ordered_results = self._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        ordered_results = self._promote_stronger_nested_aggregate_results(ordered_results)
        ordered_results = self._align_lookup_result_units_from_peer_source_slots(ordered_results)
        ordered_results = dedupe_aggregate_subtask_results(ordered_results)
        ordered_results = self._append_ratio_result_from_retrieved_context(
            ordered_results,
            state,
        )
        ordered_results = self._append_ratio_result_from_task_outputs(
            ordered_results,
            state,
        )
        ordered_results = dedupe_aggregate_subtask_results(ordered_results)
        ordered_results = self._sync_ratio_result_displays_in_ordered_results(ordered_results)
        has_growth_rate_result = any(
            self._aggregate_result_operation_family(row) == "growth_rate"
            for row in ordered_results
        )
        answer_parts = [
            _normalise_spaces(str(row.get("answer") or ""))
            for row in ordered_results
            if _normalise_spaces(str(row.get("answer") or ""))
        ]
        fallback_answer = " ".join(answer_parts).strip() or _normalise_spaces(
            str(state.get("answer") or state.get("compressed_answer") or "")
        )
        fallback_answer = self._preferred_aggregate_fallback_answer(ordered_results, fallback_answer)
        early_projection = self._rebuild_aggregate_projection(ordered_results, fallback_answer)
        early_aligned_results = self._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            early_projection,
        )
        if early_aligned_results is not ordered_results:
            ordered_results = dedupe_aggregate_subtask_results(early_aligned_results)
            fallback_answer = self._preferred_aggregate_fallback_answer(
                ordered_results,
                self._preferred_complete_numeric_answer(ordered_results) or fallback_answer,
            )
        supported_aggregate_answer = self._supported_aggregate_subtask_answer(ordered_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        has_narrative_summary = any(row_is_narrative_summary(row) for row in ordered_results)
        if (
            complete_numeric_answer
            and not supported_aggregate_answer
            and (
                not self._answer_covers_numeric_projection(fallback_answer, ordered_results)
                or (
                    self._answer_covers_numeric_projection(complete_numeric_answer, ordered_results)
                    and answer_has_numeric_material_outside_reference(
                        fallback_answer,
                        complete_numeric_answer,
                    )
                )
            )
            and self._complete_numeric_answer_can_replace_final(
                complete_numeric_answer,
                ordered_results,
            )
        ):
            fallback_answer = complete_numeric_answer
        lookup_list_answer = compose_lookup_list_numeric_answer(ordered_results)
        if lookup_list_answer and not (
            complete_numeric_answer
            and self._complete_numeric_answer_can_replace_final(complete_numeric_answer, ordered_results)
        ):
            fallback_answer = lookup_list_answer
        numeric_answer_locked = bool(
            has_narrative_summary
            and complete_numeric_answer
            and self._complete_numeric_answer_can_replace_final(complete_numeric_answer, ordered_results)
            and not query_requests_explanatory_context(str(state.get("query") or ""))
        )
        return _PreparedAggregateState(
            ordered_results=ordered_results,
            fallback_answer=fallback_answer,
            supported_aggregate_answer=supported_aggregate_answer,
            complete_numeric_answer=complete_numeric_answer,
            has_narrative_summary=has_narrative_summary,
            has_growth_rate_result=has_growth_rate_result,
            numeric_answer_locked=numeric_answer_locked,
        )

    def _append_ratio_result_from_task_outputs(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        def _task_output_bindings(task_data: Dict[str, Any]) -> List[Dict[str, Any]]:
            bindings = [dict(item) for item in list(task_data.get("inputs") or []) if isinstance(item, dict)]
            if bindings:
                return bindings
            dependency_ids = [
                _normalise_spaces(str(item or ""))
                for item in list(task_data.get("depends_on") or [])
                if _normalise_spaces(str(item or ""))
            ]
            required_operands = [
                dict(item)
                for item in list(task_data.get("required_operands") or [])
                if isinstance(item, dict)
            ]
            if not dependency_ids or len(dependency_ids) != len(required_operands):
                return []
            synthesized: List[Dict[str, Any]] = []
            for required_operand, dependency_id in zip(required_operands, dependency_ids):
                synthesized.append(
                    {
                        **required_operand,
                        "source_slot": "primary_value",
                        "source_preference": ["task_output", "retrieval"],
                        "preferred_task_id": dependency_id,
                    }
                )
            return synthesized

        has_task_output_ratio_bindings = any(
            _normalise_spaces(str((task or {}).get("operation_family") or (task or {}).get("operation") or "")).lower()
            == "ratio"
            and bool(_task_output_bindings(dict(task or {})))
            for task in list(state.get("calc_subtasks") or [])
            if isinstance(task, dict)
        )
        if any(
            self._aggregate_result_operation_family(row) == "ratio"
            and row.get("recovered_from_retrieved_ratio_context")
            and _normalise_spaces(str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")).lower()
            == "ok"
            for row in ordered_results
            if isinstance(row, dict)
        ) and not has_task_output_ratio_bindings:
            return ordered_results
        result_by_task_id = {
            _normalise_spaces(str(row.get("task_id") or "")): dict(row)
            for row in ordered_results
            if isinstance(row, dict) and _normalise_spaces(str(row.get("task_id") or ""))
        }
        artifact_operands_by_task_id: Dict[str, List[Dict[str, Any]]] = {}
        for artifact in list(state.get("artifacts") or []):
            artifact_data = dict(artifact or {})
            if _normalise_spaces(str(artifact_data.get("kind") or "")) != ArtifactKind.OPERAND_SET.value:
                continue
            artifact_task_id = _normalise_spaces(str(artifact_data.get("task_id") or ""))
            if not artifact_task_id:
                continue
            payload = dict(artifact_data.get("payload") or {})
            artifact_operands = [
                dict(row)
                for row in list(payload.get("calculation_operands") or [])
                if isinstance(row, dict)
            ]
            if artifact_operands:
                artifact_operands_by_task_id.setdefault(artifact_task_id, []).extend(artifact_operands)
        evidence_pool: List[Dict[str, Any]] = _collect_nested_result_evidence(ordered_results)
        evidence_pool.extend(dict(item) for item in (state.get("evidence_items") or []) if isinstance(item, dict))
        evidence_pool.extend(dict(item) for item in (state.get("runtime_evidence") or []) if isinstance(item, dict))
        evidence_by_id = _evidence_items_by_id(evidence_pool)

        def _direct_operand_source_ids(row: Dict[str, Any]) -> set[str]:
            operands = [
                dict(item)
                for item in list(row.get("calculation_operands") or [])
                if isinstance(item, dict)
            ]
            if not operands:
                calculation_result = dict(row.get("calculation_result") or {})
                answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
                operands = [
                    dict(slot)
                    for group in dict(answer_slots.get("components_by_group") or {}).values()
                    for slot in list(group or [])
                    if isinstance(slot, dict)
                ]
            direct_ids: set[str] = set()
            for operand_row in operands:
                source_ids = _clean_source_row_ids([
                    operand_row.get("source_row_id"),
                    operand_row.get("source_row_ids"),
                ])
                direct_ids.update(
                    source_id
                    for source_id in source_ids
                    if source_id and not source_id.startswith("task_output:")
                )
            return direct_ids

        def _direct_operand_count(row: Dict[str, Any]) -> int:
            return len(_direct_operand_source_ids(row))

        def _existing_ratio_row_is_stronger(existing_row: Dict[str, Any], candidate_row: Dict[str, Any]) -> bool:
            if not existing_row:
                return False
            if self._aggregate_result_operation_family(existing_row) != "ratio":
                return False
            if existing_row.get("recovered_from_task_outputs"):
                return False
            existing_result = dict(existing_row.get("calculation_result") or {})
            candidate_result = dict(candidate_row.get("calculation_result") or {})
            if (
                _normalise_spaces(str(existing_result.get("status") or existing_row.get("status") or "")).lower()
                != "ok"
            ):
                return False
            existing_value = financial_answer_slots.coerce_slot_numeric(existing_result.get("result_value"))
            candidate_value = financial_answer_slots.coerce_slot_numeric(candidate_result.get("result_value"))
            if existing_value is None or candidate_value is None:
                return False
            tolerance = max(abs(float(existing_value)), abs(float(candidate_value)), 1.0) * 1e-6
            if abs(float(existing_value) - float(candidate_value)) <= tolerance:
                return False
            existing_direct_ids = _direct_operand_source_ids(existing_row)
            candidate_direct_ids = _direct_operand_source_ids(candidate_row)
            if (
                existing_row.get("recovered_from_retrieved_ratio_context")
                and candidate_row.get("recovered_from_task_outputs")
                and candidate_direct_ids
                and not candidate_direct_ids.issubset(existing_direct_ids)
            ):
                return False
            existing_formula_value = financial_answer_slots.coerce_slot_numeric(
                dict(existing_result.get("derived_metrics") or {}).get("formula_result_value")
            )
            if existing_formula_value is not None:
                existing_formula_tolerance = max(abs(float(existing_formula_value)), abs(float(existing_value)), 1.0) * 1e-6
                candidate_formula_tolerance = max(abs(float(existing_formula_value)), abs(float(candidate_value)), 1.0) * 1e-6
                if (
                    abs(float(existing_formula_value) - float(existing_value)) <= existing_formula_tolerance
                    and abs(float(existing_formula_value) - float(candidate_value)) > candidate_formula_tolerance
                ):
                    return True
            return bool(
                existing_direct_ids
                and not existing_direct_ids.issubset(candidate_direct_ids)
                and _direct_operand_count(existing_row) >= 1
            )

        def _repair_source_slot_from_direct_evidence(
            source_slot: Dict[str, Any],
            binding: Dict[str, Any],
        ) -> Dict[str, Any]:
            if not evidence_pool:
                return source_slot
            preferred_slot, _preferred_score = self._best_direct_lookup_slot_from_evidence_pool(
                binding,
                evidence_pool,
                state=state,
            )
            if not preferred_slot:
                return source_slot
            preferred_evidence = _evidence_item_for_operand_row(preferred_slot, evidence_by_id)
            source_evidence = _evidence_item_for_operand_row(source_slot, evidence_by_id)
            if direct_lookup_row_is_ambiguous_context_table(
                preferred_slot,
                preferred_evidence,
                query=str(state.get("query") or ""),
                active_subtask=dict(state.get("active_subtask") or {}),
                required_operands=[binding],
            ):
                return source_slot
            if not _operand_slot_has_evidence_surface_match(
                preferred_slot,
                preferred_evidence,
                binding,
                    metric_label=_normalise_spaces(str(binding.get("label") or "")),
                ):
                    return source_slot
            if not operand_row_values_materially_conflict(source_slot, preferred_slot):
                return source_slot
            source_slot_ids = set(
                _clean_source_row_ids([
                    source_slot.get("source_row_id"),
                    source_slot.get("source_row_ids"),
                ])
            )
            preferred_slot_ids = set(
                _clean_source_row_ids([
                    preferred_slot.get("source_row_id"),
                    preferred_slot.get("source_row_ids"),
                ])
            )
            if source_slot_ids and preferred_slot_ids and source_slot_ids.isdisjoint(preferred_slot_ids):
                return source_slot
            if source_evidence and _operand_slot_has_evidence_surface_match(
                source_slot,
                source_evidence,
                binding,
                metric_label=_normalise_spaces(str(binding.get("label") or "")),
            ):
                source_table_id = _normalise_spaces(
                    str((dict(source_evidence.get("metadata") or {})).get("table_source_id") or "")
                )
                preferred_table_id = _normalise_spaces(
                    str((dict(preferred_evidence.get("metadata") or {})).get("table_source_id") or "")
                )
                if source_table_id and preferred_table_id and source_table_id != preferred_table_id:
                    return source_slot
            return {
                **source_slot,
                "raw_value": _normalise_spaces(str(preferred_slot.get("raw_value") or "")),
                "raw_unit": _normalise_spaces(str(preferred_slot.get("raw_unit") or "")),
                "normalized_value": preferred_slot.get("normalized_value"),
                "normalized_unit": _normalise_spaces(str(preferred_slot.get("normalized_unit") or "")),
                "rendered_value": _normalise_spaces(
                    str(
                        preferred_slot.get("rendered_value")
                        or f"{preferred_slot.get('raw_value') or ''}{preferred_slot.get('raw_unit') or ''}"
                    )
                ),
                "source_row_id": preferred_slot.get("source_row_id") or source_slot.get("source_row_id"),
                "source_row_ids": _clean_source_row_ids([
                    preferred_slot.get("source_row_id"),
                    preferred_slot.get("source_row_ids"),
                    source_slot.get("source_row_ids"),
                ]),
                "source_anchor": preferred_slot.get("source_anchor") or source_slot.get("source_anchor"),
                "direct_evidence_repaired_from_task_output": True,
            }

        appended: List[Dict[str, Any]] = []
        for task in list(state.get("calc_subtasks") or []):
            task_data = dict(task or {})
            operation_family = _normalise_spaces(
                str(task_data.get("operation_family") or task_data.get("operation") or "")
            ).lower()
            if operation_family != "ratio":
                continue
            bindings = _task_output_bindings(task_data)
            if not bindings:
                continue
            dependency_rows: List[Dict[str, Any]] = []
            for index, binding in enumerate(bindings, start=1):
                source_preference = {
                    _normalise_spaces(str(item or "")).lower()
                    for item in list(binding.get("source_preference") or [])
                    if _normalise_spaces(str(item or ""))
                }
                if "task_output" not in source_preference:
                    continue
                preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
                sibling_row = result_by_task_id.get(preferred_task_id)
                if not sibling_row:
                    continue
                sibling_result = dict(sibling_row.get("calculation_result") or {})
                answer_slots = dict(sibling_result.get("answer_slots") or {})
                source_slot_name = _normalise_spaces(str(binding.get("source_slot") or "primary_value")) or "primary_value"
                source_slot = dict(answer_slots.get(source_slot_name) or answer_slots.get("primary_value") or {})
                if not answer_slot_has_material(source_slot):
                    continue
                slot_matches_binding = dependency_slot_matches_input(
                    binding,
                    source_slot,
                    sibling_row=sibling_row,
                    state=state,
                )
                if not slot_matches_binding:
                    slot_surface = _normalise_spaces(
                        " ".join(
                            str(value or "")
                            for value in (
                                source_slot.get("label"),
                                sibling_row.get("metric_label"),
                                sibling_row.get("answer"),
                            )
                        )
                    )
                    slot_matches_binding = _operand_text_match(slot_surface, binding)
                if not slot_matches_binding:
                    continue
                matched_operand_candidate: Dict[str, Any] = {}
                sibling_operand_rows = [
                    *list(sibling_row.get("calculation_operands") or []),
                    *artifact_operands_by_task_id.get(preferred_task_id, []),
                ]
                for operand_row in sibling_operand_rows:
                    operand_candidate = dict(operand_row or {})
                    if not _operand_row_matches_requirement(operand_candidate, binding):
                        continue
                    if operand_candidate.get("normalized_value") is None:
                        continue
                    matched_operand_candidate = operand_candidate
                    break
                if matched_operand_candidate and operand_row_values_materially_conflict(
                    source_slot,
                    matched_operand_candidate,
                ):
                    source_slot = {
                        **source_slot,
                        "raw_value": _normalise_spaces(str(matched_operand_candidate.get("raw_value") or "")),
                        "raw_unit": _normalise_spaces(str(matched_operand_candidate.get("raw_unit") or "")),
                        "normalized_value": matched_operand_candidate.get("normalized_value"),
                        "normalized_unit": _normalise_spaces(
                            str(matched_operand_candidate.get("normalized_unit") or "")
                        ),
                        "rendered_value": _normalise_spaces(
                            str(
                                matched_operand_candidate.get("rendered_value")
                                or f"{matched_operand_candidate.get('raw_value') or ''}{matched_operand_candidate.get('raw_unit') or ''}"
                            )
                        ),
                        "source_row_id": matched_operand_candidate.get("source_row_id") or source_slot.get("source_row_id"),
                        "source_row_ids": matched_operand_candidate.get("source_row_ids")
                        or source_slot.get("source_row_ids"),
                        "source_anchor": matched_operand_candidate.get("source_anchor") or source_slot.get("source_anchor"),
                    }
                source_slot = _repair_source_slot_from_direct_evidence(source_slot, binding)
                slot_raw_unit = _normalise_spaces(str(source_slot.get("raw_unit") or ""))
                result_unit_hint = _normalise_spaces(str(sibling_result.get("result_unit") or ""))
                render_policy = dict(CALCULATION_RENDER_POLICY)
                count_units = {
                    _normalise_spaces(str(unit or ""))
                    for unit in (render_policy.get("count_display_units") or ())
                    if _normalise_spaces(str(unit or ""))
                }
                krw_units = {
                    _normalise_spaces(str(unit or ""))
                    for unit in (render_policy.get("krw_display_units") or ())
                    if _normalise_spaces(str(unit or ""))
                }
                if slot_raw_unit in count_units and result_unit_hint in krw_units:
                    repaired_value, repaired_unit = _normalise_operand_value(
                        str(source_slot.get("raw_value") or ""),
                        result_unit_hint,
                    )
                    if repaired_value is not None and repaired_unit:
                        source_slot = {
                            **source_slot,
                            "raw_unit": result_unit_hint,
                            "normalized_value": repaired_value,
                            "normalized_unit": repaired_unit,
                            "rendered_value": _normalise_spaces(
                                f"{source_slot.get('raw_value') or ''}{result_unit_hint}"
                            ),
                            "unit_realigned_from_result_unit": True,
                        }
                raw_unit, normalized_unit = infer_dependency_row_unit(source_slot, sibling_result)
                dependency_rows.append(
                    repair_operand_normalization_from_rendered_unit(
                        {
                            "operand_id": f"aggregate_task_output_{preferred_task_id}_{index:03d}",
                            "evidence_id": f"task_output:{preferred_task_id}",
                            "source_row_id": f"task_output:{preferred_task_id}",
                            "source_row_ids": _clean_source_row_ids(
                                [
                                    f"task_output:{preferred_task_id}",
                                    source_slot.get("source_row_id"),
                                    source_slot.get("source_row_ids"),
                                    sibling_result.get("source_row_ids"),
                                ]
                            ),
                            "source_anchor": _normalise_spaces(
                                str(source_slot.get("source_anchor") or sibling_result.get("source_anchor") or "")
                            ),
                            "label": _normalise_spaces(str(binding.get("label") or source_slot.get("label") or "")),
                            "raw_value": _normalise_spaces(
                                str(source_slot.get("raw_value") or source_slot.get("rendered_value") or "")
                            ),
                            "raw_unit": raw_unit,
                            "normalized_value": source_slot.get("normalized_value") or sibling_result.get("result_value"),
                            "normalized_unit": normalized_unit,
                            "period": _normalise_spaces(str(source_slot.get("period") or binding.get("period") or "")),
                            "matched_operand_label": _normalise_spaces(str(binding.get("label") or "")),
                            "matched_operand_concept": _normalise_spaces(str(binding.get("concept") or "")),
                            "matched_operand_role": _normalise_spaces(str(binding.get("role") or "")),
                            "source_task_id": preferred_task_id,
                            "dependency_resolved": True,
                        }
                    )
                )
            if _missing_required_operands(bindings, dependency_rows):
                continue
            if _ratio_operand_rows_collapse_to_same_slot(dependency_rows):
                continue
            numerator_rows = [
                dict(row)
                for row in dependency_rows
                if _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower().startswith("numerator")
            ]
            denominator_rows = [
                dict(row)
                for row in dependency_rows
                if _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower().startswith("denominator")
            ]
            if not numerator_rows or not denominator_rows:
                continue
            numerator_values = [financial_answer_slots.coerce_slot_numeric(row.get("normalized_value")) for row in numerator_rows]
            denominator_values = [financial_answer_slots.coerce_slot_numeric(row.get("normalized_value")) for row in denominator_rows]
            if any(value is None for value in numerator_values + denominator_values):
                continue
            denominator_value = sum(float(value) for value in denominator_values if value is not None)
            if denominator_value == 0:
                continue
            numerator_value = sum(float(value) for value in numerator_values if value is not None)
            metric_label = _normalise_spaces(str(task_data.get("metric_label") or task_data.get("target_metric") or ""))
            projection = calculation_rendering.ratio_result_projection(
                numerator_value=numerator_value,
                denominator_value=denominator_value,
                query=str(state.get("query") or ""),
                metric_label=metric_label,
            )
            result_value = float(projection["result_value"])
            result_unit = str(projection["result_unit"])
            normalized_unit = str(projection["normalized_unit"])
            rendered_value = str(projection["rendered_value"])
            source_row_ids = _clean_source_row_ids(
                [row.get("source_row_id") or row.get("source_row_ids") for row in dependency_rows]
            )
            numerator_slots = [
                {
                    **financial_answer_slots.build_operand_value_slot(row, default_role=str(row.get("matched_operand_role") or "numerator")),
                    "role": str(row.get("matched_operand_role") or "numerator"),
                }
                for row in numerator_rows
            ]
            denominator_slots = [
                {
                    **financial_answer_slots.build_operand_value_slot(row, default_role=str(row.get("matched_operand_role") or "denominator")),
                    "role": str(row.get("matched_operand_role") or "denominator"),
                }
                for row in denominator_rows
            ]
            components_by_role = {
                str(slot.get("role") or f"component_{index + 1}"): [slot]
                for index, slot in enumerate(numerator_slots + denominator_slots)
            }
            calculation_result = {
                "status": "ok",
                "operation_family": "ratio",
                "result_value": result_value,
                "result_unit": result_unit,
                "rendered_value": rendered_value,
                "formatted_result": "",
                "source_row_ids": source_row_ids,
                "source_evidence_ids": source_row_ids,
                "answer_slots": {
                    "metric_label": metric_label,
                    "operation_family": "ratio",
                    "source_row_ids": source_row_ids,
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": metric_label,
                        "concept": "",
                        "period": "",
                        "raw_value": rendered_value,
                        "raw_unit": result_unit,
                        "normalized_value": result_value,
                        "normalized_unit": normalized_unit,
                        "rendered_value": rendered_value,
                        "source_row_id": source_row_ids[0] if source_row_ids else "",
                        "source_row_ids": source_row_ids,
                        "source_anchor": "",
                    },
                    "components_by_group": {
                        "numerator": numerator_slots,
                        "denominator": denominator_slots,
                    },
                    "components_by_role": components_by_role,
                },
                "derived_metrics": {
                    "operation_family": "ratio",
                    "formula_result_value": result_value,
                    "task_output_ratio_projection": True,
                },
            }
            answer = self._compact_ratio_answer(
                {
                    "active_subtask": {"metric_label": metric_label},
                    "resolved_calculation_trace": {
                        "calculation_operands": dependency_rows,
                        "calculation_plan": {"status": "ok", "operation": "ratio", "result_unit": result_unit},
                        "calculation_result": calculation_result,
                    },
                },
                calculation_result,
            )
            calculation_result["formatted_result"] = answer
            appended_row = {
                "task_id": str(task_data.get("task_id") or f"ratio_task_output_{len(appended) + 1}"),
                "metric_family": str(task_data.get("metric_family") or "concept_ratio"),
                "metric_label": metric_label,
                "operation_family": "ratio",
                "answer": answer,
                "status": "ok",
                "calculation_result": calculation_result,
                "calculation_operands": dependency_rows,
                "source_row_ids": source_row_ids,
                "source_evidence_ids": source_row_ids,
                "recovered_from_task_outputs": True,
            }
            existing_row = result_by_task_id.get(str(appended_row.get("task_id") or ""))
            if _existing_ratio_row_is_stronger(existing_row or {}, appended_row):
                continue
            appended.append(appended_row)
        if not appended:
            return ordered_results
        by_task_id = {str(row.get("task_id") or ""): dict(row) for row in ordered_results if isinstance(row, dict)}
        for row in appended:
            task_id = str(row.get("task_id") or "")
            if task_id:
                by_task_id[task_id] = row
        return [by_task_id.get(str(row.get("task_id") or ""), row) for row in ordered_results if isinstance(row, dict)] + [
            row for row in appended if str(row.get("task_id") or "") not in by_task_id
        ]

    def _append_ratio_result_from_retrieved_context(
        self,
        ordered_results: List[Dict[str, Any]],
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        if any(
            self._aggregate_result_operation_family(row) == "ratio"
            and row.get("recovered_from_retrieved_ratio_context")
            and _normalise_spaces(str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")).lower()
            == "ok"
            and financial_answer_slots.ratio_components_are_complete(dict((row.get("calculation_result") or {})))
            for row in ordered_results
            if isinstance(row, dict)
        ):
            return ordered_results
        ratio_tasks = [
            dict(task)
            for task in list(state.get("calc_subtasks") or [])
            if _normalise_spaces(str(task.get("operation_family") or task.get("operation") or "")).lower() == "ratio"
            and list(task.get("required_operands") or [])
        ]
        if not ratio_tasks:
            return ordered_results
        context_docs = collect_retrieval_context_docs(
            list(state.get("retrieved_docs") or []),
            list(state.get("seed_retrieved_docs") or []),
            seed_limit=32,
        )
        context_evidence = self._ratio_operand_context_evidence_from_docs(
            context_docs,
            max_docs=64,
        )
        if not context_evidence:
            return ordered_results

        appended: List[Dict[str, Any]] = []
        for task in ratio_tasks:
            required_operands = [dict(item) for item in list(task.get("required_operands") or []) if isinstance(item, dict)]
            context_required_operands: List[Dict[str, Any]] = []
            slot_policy = dict(CALCULATION_SLOT_POLICY)
            leading_period_strip_pattern = str(slot_policy.get("leading_period_strip_pattern") or "")
            for operand in required_operands:
                context_operand = dict(operand)
                label = _normalise_spaces(str(context_operand.get("label") or ""))
                if label and leading_period_strip_pattern:
                    periodless_label = _normalise_spaces(re.sub(leading_period_strip_pattern, " ", label))
                    if periodless_label:
                        context_operand["label"] = periodless_label
                context_required_operands.append(context_operand)
            context_rows = self._build_complete_ratio_operands_from_coherent_context(
                context_evidence,
                required_operands=context_required_operands,
                query=str(state.get("query") or ""),
                topic=str(state.get("topic") or ""),
                report_scope=dict(state.get("report_scope") or {}),
            )
            if _missing_required_operands(context_required_operands, context_rows):
                continue
            if _ratio_operand_rows_collapse_to_same_slot(context_rows):
                continue
            dependency_rows: List[Dict[str, Any]] = []
            result_by_task_id = {
                _normalise_spaces(str(row.get("task_id") or "")): dict(row)
                for row in ordered_results
                if isinstance(row, dict) and _normalise_spaces(str(row.get("task_id") or ""))
            }
            for binding in list(task.get("inputs") or []):
                binding_data = dict(binding or {})
                source_preference = {
                    _normalise_spaces(str(item or "")).lower()
                    for item in list(binding_data.get("source_preference") or [])
                    if _normalise_spaces(str(item or ""))
                }
                if "task_output" not in source_preference:
                    continue
                preferred_task_id = _normalise_spaces(str(binding_data.get("preferred_task_id") or ""))
                sibling_row = result_by_task_id.get(preferred_task_id)
                if not sibling_row:
                    continue
                sibling_result = dict(sibling_row.get("calculation_result") or {})
                answer_slots = dict(sibling_result.get("answer_slots") or {})
                source_slot_name = _normalise_spaces(str(binding_data.get("source_slot") or "primary_value")) or "primary_value"
                source_slot = dict(answer_slots.get(source_slot_name) or answer_slots.get("primary_value") or {})
                if not answer_slot_has_material(source_slot):
                    continue
                raw_unit, normalized_unit = infer_dependency_row_unit(source_slot, sibling_result)
                dependency_rows.append(
                    repair_operand_normalization_from_rendered_unit(
                        {
                            "operand_id": f"aggregate_dep_{preferred_task_id}",
                            "evidence_id": f"task_output:{preferred_task_id}",
                            "source_row_id": f"task_output:{preferred_task_id}",
                            "source_row_ids": _clean_source_row_ids([
                                f"task_output:{preferred_task_id}",
                                source_slot.get("source_row_id"),
                                source_slot.get("source_row_ids"),
                                sibling_result.get("source_row_ids"),
                            ]),
                            "source_anchor": _normalise_spaces(
                                str(source_slot.get("source_anchor") or sibling_result.get("source_anchor") or "")
                            ),
                            "label": _normalise_spaces(str(binding_data.get("label") or source_slot.get("label") or "")),
                            "raw_value": _normalise_spaces(
                                str(source_slot.get("raw_value") or source_slot.get("rendered_value") or "")
                            ),
                            "raw_unit": raw_unit,
                            "normalized_value": source_slot.get("normalized_value") or sibling_result.get("result_value"),
                            "normalized_unit": normalized_unit,
                            "period": _normalise_spaces(str(source_slot.get("period") or binding_data.get("period") or "")),
                            "matched_operand_label": _normalise_spaces(str(binding_data.get("label") or "")),
                            "matched_operand_role": _normalise_spaces(str(binding_data.get("role") or "")),
                            "source_task_id": preferred_task_id,
                            "dependency_resolved": True,
                        }
                    )
                )
            dependency_rows_cover_required = bool(
                dependency_rows
                and not _missing_required_operands(context_required_operands, dependency_rows)
            )
            if dependency_rows_cover_required:
                context_by_role: Dict[str, List[Dict[str, Any]]] = {}
                for row in context_rows:
                    role = _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()
                    if role:
                        context_by_role.setdefault(role, []).append(row)
                dependency_context_conflicts = False
                for dependency_row in dependency_rows:
                    role = _normalise_spaces(
                        str(dependency_row.get("matched_operand_role") or dependency_row.get("role") or "")
                    ).lower()
                    if not role:
                        continue
                    for context_row in context_by_role.get(role, []):
                        if operand_row_values_differ(dependency_row, context_row):
                            dependency_context_conflicts = True
                            break
                    if dependency_context_conflicts:
                        break
                dependency_units = {
                    _normalise_spaces(str(row.get("raw_unit") or ""))
                    for row in dependency_rows
                    if _normalise_spaces(str(row.get("raw_unit") or ""))
                }
                context_units = {
                    _normalise_spaces(str(row.get("raw_unit") or ""))
                    for row in context_rows
                    if _normalise_spaces(str(row.get("raw_unit") or ""))
                }
                if dependency_context_conflicts and not (
                    len(dependency_units) > 1
                    and len(context_units) <= 1
                ):
                    continue
            numerator_rows = [
                dict(row)
                for row in context_rows
                if _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower().startswith("numerator")
            ]
            denominator_rows = [
                dict(row)
                for row in context_rows
                if _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower().startswith("denominator")
            ]
            if not numerator_rows or not denominator_rows:
                continue
            numerator_values = [financial_answer_slots.coerce_slot_numeric(row.get("normalized_value")) for row in numerator_rows]
            denominator_values = [financial_answer_slots.coerce_slot_numeric(row.get("normalized_value")) for row in denominator_rows]
            if any(value is None for value in numerator_values + denominator_values):
                continue
            denominator_value = sum(float(value) for value in denominator_values if value is not None)
            if denominator_value == 0:
                continue
            numerator_value = sum(float(value) for value in numerator_values if value is not None)
            metric_label = _normalise_spaces(str(task.get("metric_label") or task.get("target_metric") or ""))
            projection = calculation_rendering.ratio_result_projection(
                numerator_value=numerator_value,
                denominator_value=denominator_value,
                query=str(state.get("query") or ""),
                metric_label=metric_label,
            )
            result_value = float(projection["result_value"])
            result_unit = str(projection["result_unit"])
            normalized_unit = str(projection["normalized_unit"])
            rendered_value = str(projection["rendered_value"])
            source_row_ids = _clean_source_row_ids([
                row.get("source_row_id") or row.get("evidence_id") or row.get("source_row_ids")
                for row in context_rows
            ])
            used_source_ids = set(source_row_ids)
            projection_evidence = [
                dict(item)
                for item in context_evidence
                if _normalise_spaces(str(item.get("evidence_id") or "")) in used_source_ids
            ]
            existing_result_rows = [
                *ordered_results,
                *ratio_result_rows_from_task_artifacts(state, task),
            ]
            if retrieved_ratio_projection_conflicts_with_existing_complete_result(
                existing_result_rows,
                task,
                result_value=result_value,
                    context_evidence=projection_evidence or context_evidence,
                ):
                    continue
            numerator_slots = [
                {**financial_answer_slots.build_operand_value_slot(row, default_role=str(row.get("matched_operand_role") or "numerator")), "role": str(row.get("matched_operand_role") or "numerator")}
                for row in numerator_rows
            ]
            denominator_slots = [
                {**financial_answer_slots.build_operand_value_slot(row, default_role=str(row.get("matched_operand_role") or "denominator")), "role": str(row.get("matched_operand_role") or "denominator")}
                for row in denominator_rows
            ]
            components_by_role = {
                str(slot.get("role") or f"component_{index + 1}"): [slot]
                for index, slot in enumerate(numerator_slots + denominator_slots)
            }
            calculation_result = {
                "status": "ok",
                "operation_family": "ratio",
                "result_value": result_value,
                "result_unit": result_unit,
                "rendered_value": rendered_value,
                "formatted_result": "",
                "source_row_ids": source_row_ids,
                "source_evidence_ids": source_row_ids,
                "answer_slots": {
                    "metric_label": metric_label,
                    "operation_family": "ratio",
                    "source_row_ids": source_row_ids,
                    "primary_value": {
                        "status": "ok",
                        "role": "primary_value",
                        "label": metric_label,
                        "concept": "",
                        "period": "",
                        "raw_value": rendered_value,
                        "raw_unit": result_unit,
                        "normalized_value": result_value,
                        "normalized_unit": normalized_unit,
                        "rendered_value": rendered_value,
                        "source_row_id": source_row_ids[0] if source_row_ids else "",
                        "source_row_ids": source_row_ids,
                        "source_anchor": "",
                    },
                    "components_by_group": {
                        "numerator": numerator_slots,
                        "denominator": denominator_slots,
                    },
                    "components_by_role": components_by_role,
                },
                "derived_metrics": {
                    "operation_family": "ratio",
                    "formula_result_value": result_value,
                    "retrieved_context_ratio_projection": True,
                },
            }
            answer = self._compact_ratio_answer(
                {
                    "active_subtask": {"metric_label": metric_label},
                    "resolved_calculation_trace": {
                        "calculation_operands": context_rows,
                        "calculation_plan": {
                            "status": "ok",
                            "operation": "ratio",
                            "result_unit": result_unit,
                        },
                        "calculation_result": calculation_result,
                    },
                },
                calculation_result,
            )
            if answer:
                calculation_result["formatted_result"] = answer
            runtime_evidence = [
                dict(item)
                for item in context_evidence
                if _normalise_spaces(str(item.get("evidence_id") or "")) in used_source_ids
            ]
            appended.append(
                {
                    "task_id": str(task.get("task_id") or f"retrieved_context_ratio_{len(appended) + 1}"),
                    "metric_family": task.get("metric_family") or "concept_ratio",
                    "metric_label": metric_label,
                    "operation_family": "ratio",
                    "answer": answer or rendered_value,
                    "status": "ok",
                    "calculation_result": calculation_result,
                    "calculation_operands": context_rows,
                    "source_row_ids": source_row_ids,
                    "source_evidence_ids": source_row_ids,
                    "runtime_evidence": runtime_evidence,
                    "recovered_from_retrieved_ratio_context": True,
                }
            )
        if not appended:
            return ordered_results
        appended_signatures = {
            aggregate_result_signature(row)
            for row in appended
            if aggregate_result_signature(row)
        }
        preserved_rows = [
            row
            for row in list(ordered_results)
            if aggregate_result_signature(row) not in appended_signatures
        ]
        return [*preserved_rows, *appended]

    def _collect_initial_aggregate_evidence_state(
        self,
        state: FinancialAgentState,
        *,
        ordered_results: List[Dict[str, Any]],
        fallback_answer: str,
        final_answer: str,
        deterministic_feedback: str,
        narrative_docs: List[Any],
    ) -> _AggregateEvidenceState:
        aggregate_evidence_items: List[Dict[str, Any]] = []
        seen_evidence_ids: set[str] = set()

        def _append_aggregate_evidence(items: List[Dict[str, Any]]) -> None:
            for item in list(items or []):
                evidence = dict(item or {})
                evidence_id = str(evidence.get("evidence_id") or "").strip()
                dedupe_key = evidence_id or "|".join(
                    [
                        str(evidence.get("source_anchor") or ""),
                        str(evidence.get("claim") or evidence.get("quote_span") or evidence.get("raw_row_text") or ""),
                    ]
                )
                if dedupe_key in seen_evidence_ids:
                    continue
                seen_evidence_ids.add(dedupe_key)
                aggregate_evidence_items.append(evidence)

        for row in ordered_results:
            _append_aggregate_evidence(list(row.get("runtime_evidence") or []))
        _append_aggregate_evidence(list(state.get("evidence_items") or []))
        _append_aggregate_evidence(list(state.get("runtime_evidence") or []))
        aggregate_evidence_items = self._append_retrieved_growth_driver_evidence_for_query(
            aggregate_evidence_items,
            query=str(state.get("query") or ""),
            docs=narrative_docs,
        )
        own_unit_aligned_results = self._align_lookup_result_units_from_own_evidence(
            ordered_results,
            aggregate_evidence_items,
        )
        own_unit_aligned_results = self._align_lookup_result_units_from_peer_source_slots(own_unit_aligned_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        if own_unit_aligned_results != ordered_results:
            ordered_results = dedupe_aggregate_subtask_results(own_unit_aligned_results)
            own_unit_projection = self._rebuild_aggregate_projection(ordered_results, fallback_answer)
            own_unit_aligned_results = self._align_lookup_results_with_dependency_projection(
                ordered_results,
                state,
                own_unit_projection,
            )
            if own_unit_aligned_results != ordered_results:
                ordered_results = dedupe_aggregate_subtask_results(own_unit_aligned_results)
            complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
            fallback_answer = self._preferred_aggregate_fallback_answer(
                ordered_results,
                complete_numeric_answer or fallback_answer,
            )
            final_answer = fallback_answer
            deterministic_feedback = self._infer_planner_feedback_from_answer_slots(ordered_results)
        return _AggregateEvidenceState(
            ordered_results=ordered_results,
            aggregate_evidence_items=aggregate_evidence_items,
            fallback_answer=fallback_answer,
            final_answer=final_answer,
            complete_numeric_answer=complete_numeric_answer,
            deterministic_feedback=deterministic_feedback,
        )

    def _resolve_aggregate_feedback_state(
        self,
        state: FinancialAgentState,
        *,
        ordered_results: List[Dict[str, Any]],
        preliminary_projection: Dict[str, Any],
        calculation_projection_override: Optional[Dict[str, Any]],
        final_answer: str,
        fallback_answer: str,
        composition_selected_claim_ids: List[str],
        planner_feedback: str,
        deterministic_feedback: str,
        plan_loop_count: int,
        max_plan_loops: int,
    ) -> _AggregateFeedbackState:
        source_task_ids = _aggregate_source_task_ids(ordered_results)
        selected_claim_ids_for_integrity = _aggregate_selected_claim_ids(
            ordered_results,
            composition_selected_claim_ids,
        )
        ordered_result_source_refs = _aggregate_ordered_result_source_refs(ordered_results)
        projection_for_integrity = _aggregate_projection_for_integrity(
            preliminary_projection,
            calculation_projection_override,
        )
        ledger_artifacts = enrich_reconciliation_artifact_refs(
            list(state.get("artifacts") or []),
            task_id="",
            task_ids=source_task_ids,
            operand_rows=list(projection_for_integrity.get("calculation_operands") or []),
            extra_refs=_aggregate_integrity_extra_refs(
                projection_for_integrity,
                ordered_result_source_refs,
                selected_claim_ids_for_integrity,
            ),
        )
        task_artifact_trace = _project_task_artifact_trace(
            state.get("tasks") or [],
            ledger_artifacts,
        )
        integrity_feedback = _task_artifact_integrity_feedback(task_artifact_trace)
        if integrity_feedback:
            planner_feedback = ""
            deterministic_feedback = integrity_feedback
        if not deterministic_feedback:
            planner_feedback = ""
        elif not planner_feedback:
            planner_feedback = deterministic_feedback
        replan_blocked_reason = ""
        if planner_feedback and plan_loop_count >= 1 and _has_duplicate_direct_lookup_rejection(state):
            replan_blocked_reason = "duplicate_missing_direct_lookup_operand_support"
        should_replan = bool(planner_feedback) and plan_loop_count < max_plan_loops and not replan_blocked_reason
        if planner_feedback and not should_replan:
            refusal_suffix = "다만 질문에 필요한 수치를 끝내 모두 확보하지 못해 원하신 답을 완전히 확정할 수는 없습니다."
            visible_partial_answer = _normalise_spaces(
                safe_partial_answer_for_numeric_gap(ordered_results)
                or self._preferred_complete_numeric_answer(ordered_results)
                or self._supported_aggregate_subtask_answer(ordered_results)
            )
            state_runtime_trace = _resolve_runtime_calculation_trace(
                dict(state),
                allow_legacy_top_level=False,
            )
            state_calculation_status = _normalise_spaces(
                str(((state_runtime_trace.get("calculation_result") or {})).get("status") or "")
            ).lower()
            has_traceable_partial_material = bool(
                selected_claim_ids_for_integrity
                or ordered_result_source_refs
                or any(
                    str((artifact or {}).get("status") or "").strip().lower() == "ok"
                    for artifact in ledger_artifacts
                )
                or state_calculation_status == "ok"
            )
            has_subtask_result_numeric_gap = any(
                not row_is_narrative_summary(row)
                and (
                    material_gap_feedback_for_subtask_result(row)
                    or str(
                        row.get("status")
                        or (row.get("calculation_result") or {}).get("status")
                        or ""
                    ).strip().lower()
                    not in {"", "ok"}
                )
                for row in (state.get("subtask_results") or [])
                if isinstance(row, dict)
            )
            if not visible_partial_answer:
                candidate_partial_answer = _normalise_spaces(
                    state.get("answer")
                    or state.get("compressed_answer")
                    or fallback_answer
                    or final_answer
                )
                if (
                    candidate_partial_answer
                    and re.search(r"\d", candidate_partial_answer)
                    and has_traceable_partial_material
                    and not has_subtask_result_numeric_gap
                ):
                    visible_partial_answer = candidate_partial_answer
            if visible_partial_answer:
                final_answer = _normalise_spaces(f"{visible_partial_answer} {refusal_suffix}")
            else:
                focus_candidates: List[str] = []
                generic_result_label = str(CALCULATION_NARRATIVE_POLICY.get("generic_result_label") or "")
                for source in [
                    *ordered_results,
                    state.get("active_subtask") or {},
                    *(state.get("calc_subtasks") or []),
                ]:
                    if not isinstance(source, dict):
                        continue
                    if row_is_narrative_summary(source):
                        continue
                    candidate_label = _normalise_spaces(
                        str(source.get("metric_label") or source.get("label") or source.get("query") or "")
                    )
                    if candidate_label and candidate_label not in {"-", "metric", generic_result_label}:
                        focus_candidates.append(candidate_label)
                unique_focus_candidates = list(dict.fromkeys(focus_candidates))
                missing_focus = unique_focus_candidates[0] if len(unique_focus_candidates) == 1 else ""
                if missing_focus:
                    final_answer = _normalise_spaces(
                        str(CALCULATION_NARRATIVE_POLICY.get("missing_focus_answer_template") or "").format(
                            missing_focus=missing_focus,
                            refusal_suffix=refusal_suffix,
                        )
                    )
                else:
                    final_answer = "질문에 필요한 수치를 끝내 충분히 확보하지 못했습니다."
        return _AggregateFeedbackState(
            final_answer=final_answer,
            planner_feedback=planner_feedback,
            deterministic_feedback=deterministic_feedback,
            ledger_artifacts=ledger_artifacts,
            task_artifact_trace=task_artifact_trace,
            should_replan=should_replan,
            replan_blocked_reason=replan_blocked_reason,
        )

    def _build_aggregate_completion_update(
        self,
        state: FinancialAgentState,
        *,
        ordered_results: List[Dict[str, Any]],
        aggregate_projection: Dict[str, Any],
        final_answer: str,
        selected_claim_ids: List[str],
        aggregate_evidence_items: List[Dict[str, Any]],
        ledger_artifacts: List[Dict[str, Any]],
        planner_feedback: str,
        should_replan: bool,
        replan_blocked_reason: str,
        aggregate_synthesis_debug: Dict[str, Any],
    ) -> Dict[str, Any]:
        aggregate_artifact_update = _build_aggregate_answer_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(ledger_artifacts),
            final_answer=final_answer,
            payload=_aggregate_artifact_payload(
                ordered_results=ordered_results,
                final_answer=final_answer,
                planner_feedback=planner_feedback,
                aggregate_projection=aggregate_projection,
            ),
            evidence_refs=selected_claim_ids,
            query=str(state.get("query") or ""),
            planner_feedback=planner_feedback,
        )
        tasks = list(aggregate_artifact_update["tasks"])
        artifacts = list(aggregate_artifact_update["artifacts"])
        artifact_id = str(aggregate_artifact_update.get("artifact_id") or "")
        tasks, artifacts = self._finalize_aggregate_task_ledger(
            tasks,
            artifacts,
            ordered_results=ordered_results,
            aggregate_projection=aggregate_projection,
            aggregate_artifact_id=artifact_id,
            final_answer=final_answer,
        )
        aggregate_projection, final_answer, artifacts = self._apply_ratio_projection_answer_if_rendered_missing(
            state,
            aggregate_projection,
            artifact_id=artifact_id,
            final_answer=final_answer,
            artifacts=artifacts,
        )
        return {
            **_aggregate_completion_base_payload(
                state=state,
                ordered_results=ordered_results,
                aggregate_projection=aggregate_projection,
                final_answer=final_answer,
                selected_claim_ids=selected_claim_ids,
                aggregate_evidence_items=aggregate_evidence_items,
                tasks=tasks,
                artifacts=artifacts,
                planner_feedback=planner_feedback,
                should_replan=should_replan,
                replan_blocked_reason=replan_blocked_reason,
                aggregate_synthesis_debug=aggregate_synthesis_debug,
            ),
            **_runtime_trace_state_update(
                state,
                calculation_operands=aggregate_projection["calculation_operands"],
                calculation_plan=aggregate_projection["calculation_plan"],
                calculation_result=aggregate_projection["calculation_result"],
            ),
        }

    def _aggregate_calculation_subtasks(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Combine completed subtask outputs into a single caller-facing view."""
        prepared_state = self._prepare_initial_aggregate_state(state)
        ordered_results = prepared_state.ordered_results
        fallback_answer = prepared_state.fallback_answer
        supported_aggregate_answer = prepared_state.supported_aggregate_answer
        complete_numeric_answer = prepared_state.complete_numeric_answer
        has_narrative_summary = prepared_state.has_narrative_summary
        has_growth_rate_result = prepared_state.has_growth_rate_result
        numeric_answer_locked = prepared_state.numeric_answer_locked
        final_answer = fallback_answer
        planner_feedback = ""
        deterministic_feedback = self._infer_planner_feedback_from_answer_slots(ordered_results)
        narrative_docs = list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or [])
        evidence_state = self._collect_initial_aggregate_evidence_state(
            state,
            ordered_results=ordered_results,
            fallback_answer=fallback_answer,
            final_answer=final_answer,
            deterministic_feedback=deterministic_feedback,
            narrative_docs=narrative_docs,
        )
        ordered_results = evidence_state.ordered_results
        aggregate_evidence_items = evidence_state.aggregate_evidence_items
        fallback_answer = evidence_state.fallback_answer
        final_answer = evidence_state.final_answer
        complete_numeric_answer = evidence_state.complete_numeric_answer
        deterministic_feedback = evidence_state.deterministic_feedback
        preliminary_projection = self._rebuild_aggregate_projection(ordered_results, fallback_answer)
        period_context_evidence_items = _aggregate_period_context_evidence_items(
            aggregate_evidence_items,
            self._runtime_evidence_rows_with_context_docs(state),
        )
        period_realigned_state = self._apply_period_context_realignment_to_aggregate(
            aggregate_state=_AggregateSynthesisState(
                ordered_results,
                preliminary_projection,
                final_answer,
                [],
            ),
            state=state,
            evidence_items=period_context_evidence_items,
        )
        if period_realigned_state.ordered_results is not ordered_results:
            ordered_results = period_realigned_state.ordered_results
            preliminary_projection = period_realigned_state.aggregate_projection
            fallback_answer = period_realigned_state.final_answer
            final_answer = period_realigned_state.final_answer
            complete_numeric_answer = self._preferred_complete_numeric_answer(
                ordered_results,
                query=str(state.get("query") or ""),
                evidence_items=period_context_evidence_items,
            )
        narrative_context = narrative_context_sentence_from_evidence(
            str(state.get("query") or ""),
            aggregate_evidence_items,
        )
        plan_loop_count = int(state.get("plan_loop_count") or 0)
        max_plan_loops = 2
        aggregate_synthesis_input_json = ""
        aggregate_synthesis_debug: Dict[str, Any] = {}
        if hasattr(self, "llm") and getattr(self, "llm", None) is not None:
            AggregateSynthesisOutput = _aggregate_synthesis_output_model()
            structured_llm = self._llm_for_phase("aggregate_synthesis").with_structured_output(AggregateSynthesisOutput)
            prompt = _chat_prompt_template_from_template(
                str(CALCULATION_PROMPT_POLICY.get("aggregate_synthesis_prompt_template") or "")
            )
            try:
                prompt_rows = aggregate_synthesis_prompt_rows(ordered_results, preliminary_projection)
                aggregate_synthesis_input_json = json.dumps(prompt_rows, ensure_ascii=False, separators=(",", ":"))
                aggregate_synthesis_debug = {
                    "row_count": len(prompt_rows),
                    "input_json_chars": len(aggregate_synthesis_input_json),
                    "source": "projection_compact_rows",
                }
                prompt_value = prompt.invoke(
                    {
                        "query": state["query"],
                        "fallback_answer": fallback_answer,
                        "deterministic_feedback": deterministic_feedback or "-",
                        "narrative_context": narrative_context or "-",
                        "subtask_results_json": aggregate_synthesis_input_json,
                    }
                )
                synthesized: AggregateSynthesisOutput = structured_llm.invoke(prompt_value)
                final_answer = _normalise_spaces(str(synthesized.final_answer or "")) or fallback_answer
                planner_feedback = _normalise_spaces(str(synthesized.planner_feedback or ""))
            except Exception as exc:
                logger.warning("[aggregate_synth] structured output failed, using fallback join: %s", exc)
        composition_state, complete_numeric_answer = self._apply_initial_aggregate_answer_composition(
            state,
            ordered_results=ordered_results,
            preliminary_projection=preliminary_projection,
            aggregate_evidence_items=aggregate_evidence_items,
            narrative_docs=narrative_docs,
            narrative_context=narrative_context,
            final_answer=final_answer,
            supported_aggregate_answer=supported_aggregate_answer,
            complete_numeric_answer=complete_numeric_answer,
            has_narrative_summary=has_narrative_summary,
            has_growth_rate_result=has_growth_rate_result,
            numeric_answer_locked=numeric_answer_locked,
            planner_feedback=planner_feedback,
            deterministic_feedback=deterministic_feedback,
        )
        final_answer = composition_state.final_answer
        composition_selected_claim_ids = composition_state.selected_claim_ids
        calculation_projection_override = composition_state.calculation_projection_override
        narrative_answer_locked = composition_state.narrative_answer_locked
        planner_feedback = composition_state.planner_feedback
        deterministic_feedback = composition_state.deterministic_feedback
        final_answer = self._preserve_source_visible_query_terms(
            final_answer,
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
            docs=list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or []),
        )
        policy_preserved_results = self._preserve_policy_required_context_in_narrative_results(
            ordered_results,
            query=str(state.get("query") or ""),
            docs=narrative_docs,
            evidence_items=aggregate_evidence_items,
        )
        if policy_preserved_results is not ordered_results:
            ordered_results = policy_preserved_results
            preliminary_projection = self._rebuild_aggregate_projection(ordered_results, fallback_answer)
        # Prefer the deterministic structured-material check over a stale
        # deterministic hint, but preserve independent synthesizer feedback for
        # replan/budget-exhausted cases.
        preliminary_status = _normalise_spaces(
            str((preliminary_projection.get("calculation_result") or {}).get("status") or "")
        ).lower()
        if (
            preliminary_status == "ok"
            and deterministic_feedback
            and (not planner_feedback or planner_feedback == deterministic_feedback)
        ):
            planner_feedback = ""
            deterministic_feedback = ""
        if (
            (planner_feedback or deterministic_feedback)
            and self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        ):
            planner_feedback = ""
            deterministic_feedback = ""
        feedback_state = self._resolve_aggregate_feedback_state(
            state,
            ordered_results=ordered_results,
            preliminary_projection=preliminary_projection,
            calculation_projection_override=calculation_projection_override,
            final_answer=final_answer,
            fallback_answer=fallback_answer,
            composition_selected_claim_ids=composition_selected_claim_ids,
            planner_feedback=planner_feedback,
            deterministic_feedback=deterministic_feedback,
            plan_loop_count=plan_loop_count,
            max_plan_loops=max_plan_loops,
        )
        final_answer = feedback_state.final_answer
        planner_feedback = feedback_state.planner_feedback
        deterministic_feedback = feedback_state.deterministic_feedback
        ledger_artifacts = feedback_state.ledger_artifacts
        should_replan = feedback_state.should_replan
        replan_blocked_reason = feedback_state.replan_blocked_reason
        selected_claim_ids = _aggregate_selected_claim_ids(
            ordered_results,
            composition_selected_claim_ids,
        )
        aggregate_projection = self._rebuild_aggregate_projection(ordered_results, final_answer)
        mutable_state = _AggregateMutableState(
            _AggregateSynthesisState(ordered_results, aggregate_projection, final_answer, selected_claim_ids),
            aggregate_evidence_items,
        )

        def _sync_aggregate_locals() -> None:
            nonlocal ordered_results, aggregate_projection, final_answer, selected_claim_ids, aggregate_evidence_items
            ordered_results, aggregate_projection, final_answer, selected_claim_ids = mutable_state.synthesis_state
            aggregate_evidence_items = mutable_state.evidence_items

        def _sync_state(**updates: Any) -> None:
            nonlocal mutable_state
            mutable_state = mutable_state.with_updates(**updates)
            _sync_aggregate_locals()

        aligned_ordered_results = self._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )
        if aligned_ordered_results is not ordered_results:
            refresh_aligned_numeric = (
                not narrative_answer_locked
                or aggregate_results_include_source_task_slot_realignment(aligned_ordered_results)
            )
            mutable_state = self._replace_mutable_aggregate_results(
                mutable_state,
                state,
                aligned_ordered_results,
                refresh_numeric_answer=refresh_aligned_numeric,
            )
            _sync_aggregate_locals()
        if calculation_projection_override:
            aggregate_projection = _aggregate_projection_apply_override(
                aggregate_projection,
                calculation_projection_override,
            )
            _sync_state(aggregate_projection=aggregate_projection)
        slot_based_difference_answer = calculation_rendering.compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(aggregate_projection.get("calculation_result") or {}),
            answer_slot_has_material=answer_slot_has_material,
        )
        if slot_based_difference_answer:
            mutable_state, _ = self._replace_mutable_aggregate_answer(
                mutable_state,
                candidate_answer=slot_based_difference_answer,
                sync_rendered_for_aggregate=False,
            )
            _sync_aggregate_locals()
        final_answer = self._preserve_source_visible_query_terms(
            final_answer,
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
            docs=list(state.get("seed_retrieved_docs", []) or []) + list(state.get("retrieved_docs", []) or []),
        )
        if has_narrative_summary:
            final_answer = self._prune_irrelevant_growth_narrative_sentences(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        _sync_state(final_answer=final_answer)
        if (
            has_narrative_summary
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            and not (
                query_requests_explanatory_context(str(state.get("query") or ""))
                and answer_reuses_numeric_narrative_summary_text(final_answer, ordered_results)
            )
        ):
            final_answer = ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            _sync_state(final_answer=final_answer)
        late_aligned_results, late_identity_changed, _late_value_changed, _late_alignment_changed = (
            self._promote_and_align_aggregate_results(
                ordered_results,
                state,
                final_answer,
                align_without_promotion=False,
            )
        )
        if late_identity_changed:
            mutable_state = self._replace_mutable_aggregate_results(
                mutable_state,
                state,
                late_aligned_results,
            )
            _sync_aggregate_locals()
            late_supported_answer = self._supported_aggregate_subtask_answer(late_aligned_results)
            late_numeric_answer = self._preferred_complete_numeric_answer(late_aligned_results)
            late_answer = late_supported_answer or (
                late_numeric_answer
                if self._complete_numeric_answer_can_replace_final(late_numeric_answer, late_aligned_results)
                else ""
            )
            if late_answer:
                mutable_state = mutable_state._replace(
                    synthesis_state=self._apply_numeric_answer_to_aggregate_state(
                        aggregate_state=mutable_state.synthesis_state,
                        state=state,
                        numeric_answer=late_answer,
                        evidence_items=mutable_state.evidence_items,
                    )
                )
                _sync_aggregate_locals()
        mutable_state = self._apply_final_narrative_repair_pipeline(
            state,
            mutable_state=mutable_state,
            narrative_docs=narrative_docs,
            has_narrative_summary=has_narrative_summary,
            has_growth_rate_result=has_growth_rate_result,
            deterministic_feedback=deterministic_feedback,
        )
        _sync_aggregate_locals()
        (
            final_consistent_aligned_results,
            _consistent_identity_changed,
            final_consistent_changed,
            final_consistent_aligned,
        ) = (
            self._promote_and_align_aggregate_results(
                ordered_results,
                state,
                final_answer,
                align_without_promotion=True,
            )
        )
        if final_consistent_changed:
            mutable_state = self._replace_mutable_aggregate_results(
                mutable_state,
                state,
                final_consistent_aligned_results,
                refresh_numeric_answer=final_consistent_aligned,
            )
            _sync_aggregate_locals()
        ordered_results, aggregate_projection = self._sync_projection_subtask_results_with_nested_promotions(
            ordered_results,
            state,
            aggregate_projection,
            final_answer,
        )
        _sync_state(ordered_results=ordered_results, aggregate_projection=aggregate_projection)
        aggregate_evidence_items, missing_context_claim_ids = self._append_missing_decision_context_evidence(
            aggregate_evidence_items,
            final_answer=final_answer,
            selected_claim_ids=selected_claim_ids,
            query=str(state.get("query") or ""),
            docs=narrative_docs,
        )
        _sync_state(evidence_items=aggregate_evidence_items)
        if missing_context_claim_ids:
            selected_claim_ids = _aggregate_extend_selected_claim_ids(
                selected_claim_ids,
                missing_context_claim_ids,
            )
            _sync_state(selected_claim_ids=selected_claim_ids)
        late_unit_aligned_results = self._align_lookup_result_units_from_own_evidence(
            ordered_results,
            aggregate_evidence_items,
        )
        late_unit_aligned_results = self._align_lookup_result_units_from_peer_source_slots(late_unit_aligned_results)
        if late_unit_aligned_results != ordered_results:
            late_unit_results = dedupe_aggregate_subtask_results(late_unit_aligned_results)
            late_unit_projection = self._rebuild_aggregate_projection(late_unit_results, final_answer)
            late_unit_aligned_results = self._align_lookup_results_with_dependency_projection(
                late_unit_results,
                {"query": str(state.get("query") or ""), "calc_subtasks": []},
                late_unit_projection,
            )
            if late_unit_aligned_results != late_unit_results:
                late_unit_results = dedupe_aggregate_subtask_results(late_unit_aligned_results)
            mutable_state = self._replace_mutable_aggregate_results(
                mutable_state,
                state,
                late_unit_results,
                refresh_numeric_answer=True,
            )
            _sync_aggregate_locals()
        consistent_numeric_answer = self._preferred_complete_numeric_answer(
            ordered_results,
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        final_answer_satisfies_requested_growth_narrative = bool(
            query_requests_explanatory_context(str(state.get("query") or ""))
            and (
                answer_reuses_numeric_narrative_summary_text(final_answer, ordered_results)
                or self._answer_satisfies_growth_narrative_intent(
                    query=str(state.get("query") or ""),
                    answer=final_answer,
                    ordered_results=ordered_results,
                    evidence_items=aggregate_evidence_items,
                )
            )
        )
        if (
            consistent_numeric_answer
            and _normalise_spaces(consistent_numeric_answer) != _normalise_spaces(final_answer)
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            and not final_answer_satisfies_requested_growth_narrative
            and self._complete_numeric_answer_can_replace_final(consistent_numeric_answer, ordered_results)
            and (
                not self._answer_covers_numeric_projection(final_answer, ordered_results)
                or growth_answer_has_untraced_numeric_material(
                    final_answer,
                    ordered_results,
                    aggregate_evidence_items,
                )
            )
        ):
            mutable_state = mutable_state._replace(
                synthesis_state=self._apply_numeric_answer_to_aggregate_state(
                    aggregate_state=mutable_state.synthesis_state,
                    state=state,
                    numeric_answer=consistent_numeric_answer,
                    evidence_items=mutable_state.evidence_items,
                )
            )
            _sync_aggregate_locals()
            aggregate_projection = self._rebuild_aggregate_projection(ordered_results, final_answer)
            _sync_state(aggregate_projection=aggregate_projection)
        projection_result = dict(aggregate_projection.get("calculation_result") or {})
        compact_ratio_answer = self._compact_ratio_answer_from_projection(
            state,
            aggregate_projection,
            projection_result,
        )
        if compact_ratio_answer and compact_ratio_answer != _normalise_spaces(final_answer):
            mutable_state, _ = self._replace_mutable_aggregate_answer(
                mutable_state,
                candidate_answer=compact_ratio_answer,
                sync_rendered_for_aggregate=False,
            )
            _sync_aggregate_locals()
        lookup_preserved_answer = append_uncovered_lookup_numeric_items(final_answer, ordered_results)
        if lookup_preserved_answer != _normalise_spaces(final_answer):
            mutable_state, _ = self._replace_mutable_aggregate_answer(
                mutable_state,
                candidate_answer=lookup_preserved_answer,
                sync_rendered_for_aggregate=False,
                refresh_operand_evidence=True,
            )
            _sync_aggregate_locals()
        stale_repair_evidence_items = list(aggregate_evidence_items)
        aggregate_evidence_items, aggregate_projection, selected_claim_ids, kept_evidence_ids = (
            self._filter_final_aggregate_evidence_and_projection(
                aggregate_evidence_items,
                aggregate_projection,
                final_answer=final_answer,
                selected_claim_ids=selected_claim_ids,
            )
        )
        _sync_state(
            aggregate_projection=aggregate_projection,
            selected_claim_ids=selected_claim_ids,
            evidence_items=aggregate_evidence_items,
        )
        aggregate_projection, final_answer = self._apply_runtime_ratio_projection_for_collapsed_rows(
            state,
            aggregate_projection,
            ordered_results,
            final_answer,
        )
        _sync_state(aggregate_projection=aggregate_projection, final_answer=final_answer)
        aggregate_state_before_stale_repair = mutable_state.synthesis_state
        aggregate_state = self._apply_stale_projection_repair_to_aggregate_state(
            state=state,
            aggregate_state=aggregate_state_before_stale_repair,
            evidence_items=stale_repair_evidence_items,
            prefer_compact_ratio_answer=True,
        )
        mutable_state = mutable_state.with_synthesis_state(aggregate_state)
        _sync_aggregate_locals()
        if aggregate_state is not aggregate_state_before_stale_repair:
            aggregate_evidence_items, aggregate_projection, selected_claim_ids, kept_evidence_ids = (
                self._filter_final_aggregate_evidence_and_projection(
                    stale_repair_evidence_items,
                    aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                )
            )
            _sync_state(
                aggregate_projection=aggregate_projection,
                selected_claim_ids=selected_claim_ids,
                evidence_items=aggregate_evidence_items,
            )
        complete_projection_answer = self._complete_numeric_projection_replacement_answer(
            final_answer=final_answer,
            ordered_results=ordered_results,
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        if complete_projection_answer:
            candidate_application = apply_aggregate_answer_candidate(
                AggregateAnswerCandidateApplicationInput(
                    aggregate_projection=aggregate_projection,
                    selected_claim_ids=selected_claim_ids,
                    candidate=package_aggregate_answer_candidate(
                        AggregateAnswerCandidatePackagingInput(
                            answer=complete_projection_answer,
                            selected_claim_ids=[],
                            status_ok=True,
                        )
                    ).candidate,
                )
            )
            aggregate_projection = candidate_application.aggregate_projection
            final_answer = candidate_application.final_answer
            selected_claim_ids = candidate_application.selected_claim_ids
            _sync_state(
                aggregate_projection=aggregate_projection,
                final_answer=final_answer,
                selected_claim_ids=selected_claim_ids,
            )
        late_conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        )
        if late_conflicting_narrative:
            conflicting_answer = _normalise_spaces(str(late_conflicting_narrative.get("answer") or ""))
            final_answer_surface = _normalise_spaces(final_answer)
            final_answer_satisfies_growth_narrative = self._answer_satisfies_growth_narrative_intent(
                query=str(state.get("query") or ""),
                answer=final_answer_surface,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            final_answer_preserves_numeric_trace = bool(
                self._answer_covers_numeric_projection(final_answer_surface, ordered_results)
                and not growth_answer_has_untraced_numeric_material(
                    final_answer_surface,
                    ordered_results,
                    aggregate_evidence_items,
                )
            )
            conflicting_numeric_tokens = set(re.findall(r"[\(\)\-+]?\d[\d,]*(?:\.\d+)?%?", conflicting_answer))
            final_numeric_tokens = set(re.findall(r"[\(\)\-+]?\d[\d,]*(?:\.\d+)?%?", final_answer_surface))
            final_contains_conflicting_answer_with_extra_numbers = bool(
                conflicting_answer
                and conflicting_answer in final_answer_surface
                and final_numeric_tokens - conflicting_numeric_tokens
            )
            final_numeric_conflicts_with_supported_aggregate = bool(
                str(late_conflicting_narrative.get("operation_family") or "") == "aggregate_subtasks"
                and numeric_surface_conflicts_with_reference(final_answer_surface, conflicting_answer)
            )
            if conflicting_answer and (
                (
                    not final_answer_satisfies_growth_narrative
                    and not final_answer_preserves_numeric_trace
                    and (
                        final_contains_conflicting_answer_with_extra_numbers
                        or growth_narrative_numeric_incompatible_with_trace(
                            narrative_answer=conflicting_answer,
                            numeric_answer=final_answer,
                            ordered_results=ordered_results,
                            evidence_items=aggregate_evidence_items,
                        )
                    )
                )
                or (
                    final_numeric_conflicts_with_supported_aggregate
                    and not _narrative_sentence_looks_table_noisy(conflicting_answer)
                )
            ):
                candidate_application = apply_aggregate_answer_candidate(
                    AggregateAnswerCandidateApplicationInput(
                        aggregate_projection=aggregate_projection,
                        selected_claim_ids=selected_claim_ids,
                        candidate=package_aggregate_answer_candidate(
                            AggregateAnswerCandidatePackagingInput(
                                answer=conflicting_answer,
                                selected_claim_ids=late_conflicting_narrative.get("selected_claim_ids") or [],
                                sync_projection=False,
                            )
                        ).candidate,
                    )
                )
                aggregate_projection = candidate_application.aggregate_projection
                final_answer = candidate_application.final_answer
                selected_claim_ids = candidate_application.selected_claim_ids
                aggregate_projection = self._rebuild_aggregate_projection(
                    ordered_results, final_answer, kept_evidence_ids=kept_evidence_ids
                )
                _sync_state(
                    aggregate_projection=aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                )
        preserved_aggregate_candidate = self._preferred_existing_aggregate_artifact_candidate(
            ledger_artifacts,
            ordered_results,
            final_answer,
        )
        if preserved_aggregate_candidate:
            candidate_application = apply_aggregate_answer_candidate(
                AggregateAnswerCandidateApplicationInput(
                    aggregate_projection=aggregate_projection,
                    selected_claim_ids=selected_claim_ids,
                    candidate=preserved_aggregate_candidate,
                )
            )
            aggregate_projection = candidate_application.aggregate_projection
            final_answer = candidate_application.final_answer
            selected_claim_ids = candidate_application.selected_claim_ids
            _sync_state(
                aggregate_projection=aggregate_projection,
                final_answer=final_answer,
                selected_claim_ids=selected_claim_ids,
            )
        projection_plan = dict(aggregate_projection.get("calculation_plan") or {})
        projection_result = dict(aggregate_projection.get("calculation_result") or {})
        has_growth_material = (
            has_growth_rate_result
            or str(projection_plan.get("operation") or projection_result.get("operation_family") or "").strip().lower()
            == "growth_rate"
        )
        if has_growth_material and query_requests_explanatory_context(str(state.get("query") or "")):
            supported_candidate = self._uncovered_supported_growth_narrative_candidate(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            supported_sentence = _normalise_spaces(str(supported_candidate.get("sentence") or ""))
            if supported_sentence:
                candidate_application = apply_aggregate_answer_candidate(
                    AggregateAnswerCandidateApplicationInput(
                        aggregate_projection=aggregate_projection,
                        selected_claim_ids=selected_claim_ids,
                        candidate=package_aggregate_answer_candidate(
                            AggregateAnswerCandidatePackagingInput(
                                answer=_normalise_spaces(" ".join([final_answer, supported_sentence])),
                                selected_claim_ids=supported_candidate.get("selected_claim_ids") or [],
                            )
                        ).candidate,
                    )
                )
                aggregate_projection = candidate_application.aggregate_projection
                final_answer = candidate_application.final_answer
                selected_claim_ids = candidate_application.selected_claim_ids
                _sync_state(
                    aggregate_projection=aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                )
        if (
            final_answer
            and has_narrative_summary
            and has_growth_rate_result
            and has_strong_growth_trace_for_answer_refresh(ordered_results)
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            and not (
                query_requests_explanatory_context(str(state.get("query") or ""))
                and (
                    answer_reuses_numeric_narrative_summary_text(final_answer, ordered_results)
                    or self._answer_satisfies_growth_narrative_intent(
                        query=str(state.get("query") or ""),
                        answer=final_answer,
                        ordered_results=ordered_results,
                        evidence_items=aggregate_evidence_items,
                    )
                )
            )
        ):
            numeric_preserved_answer = ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            if numeric_preserved_answer and numeric_preserved_answer != _normalise_spaces(final_answer):
                candidate_application = apply_aggregate_answer_candidate(
                    AggregateAnswerCandidateApplicationInput(
                        aggregate_projection=aggregate_projection,
                        selected_claim_ids=selected_claim_ids,
                        candidate=package_aggregate_answer_candidate(
                            AggregateAnswerCandidatePackagingInput(
                                answer=numeric_preserved_answer,
                                selected_claim_ids=[],
                            )
                        ).candidate,
                    )
                )
                aggregate_projection = candidate_application.aggregate_projection
                final_answer = candidate_application.final_answer
                selected_claim_ids = candidate_application.selected_claim_ids
                _sync_state(
                    aggregate_projection=aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                )
        _sync_aggregate_locals()
        final_period_context_evidence_items = _aggregate_period_context_evidence_items(
            aggregate_evidence_items,
            period_context_evidence_items,
        )
        final_period_realigned_state = self._apply_period_context_realignment_to_aggregate(
            aggregate_state=mutable_state.synthesis_state,
            state=state,
            evidence_items=final_period_context_evidence_items,
        )
        if final_period_realigned_state.ordered_results is not ordered_results:
            mutable_state = mutable_state.with_synthesis_state(final_period_realigned_state)
            _sync_aggregate_locals()
        ordered_results, aggregate_projection = self._sync_aggregate_arithmetic_subtask_surfaces(
            ordered_results,
            aggregate_projection,
            final_answer,
        )
        _sync_state(ordered_results=ordered_results, aggregate_projection=aggregate_projection)
        final_ratio_synced_results = self._sync_ratio_result_displays_in_ordered_results(ordered_results)
        if final_ratio_synced_results is not ordered_results:
            ordered_results = final_ratio_synced_results
            final_ratio_answer = self._complete_numeric_projection_replacement_answer(
                final_answer=final_answer,
                ordered_results=ordered_results,
                query=str(state.get("query") or ""),
                evidence_items=aggregate_evidence_items,
            ) or self._preferred_complete_numeric_answer(
                ordered_results,
                query=str(state.get("query") or ""),
                evidence_items=aggregate_evidence_items,
            )
            if final_ratio_answer and not self._answer_covers_numeric_projection(final_answer, ordered_results):
                final_answer = final_ratio_answer
            aggregate_projection = self._rebuild_aggregate_projection(ordered_results, final_answer)
            _sync_state(ordered_results=ordered_results, aggregate_projection=aggregate_projection, final_answer=final_answer)
        final_complete_projection_answer = self._complete_numeric_projection_replacement_answer(
            final_answer=final_answer,
            ordered_results=ordered_results,
            query=str(state.get("query") or ""),
            evidence_items=aggregate_evidence_items,
        )
        if final_complete_projection_answer:
            final_answer = final_complete_projection_answer
            aggregate_projection = self._rebuild_aggregate_projection(ordered_results, final_answer)
            _sync_state(aggregate_projection=aggregate_projection, final_answer=final_answer)
        if has_strong_growth_trace_for_answer_refresh(ordered_results) and not (
            query_requests_explanatory_context(str(state.get("query") or ""))
            and answer_reuses_numeric_narrative_summary_text(final_answer, ordered_results)
        ):
            trace_clean_growth_answer = self._final_growth_answer_without_untraced_numeric_sentences(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            if trace_clean_growth_answer and trace_clean_growth_answer != _normalise_spaces(final_answer):
                final_answer = trace_clean_growth_answer
                aggregate_projection = self._rebuild_aggregate_projection(ordered_results, final_answer)
                _sync_state(aggregate_projection=aggregate_projection, final_answer=final_answer)
        final_conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query=str(state.get("query") or ""),
            ordered_results=ordered_results,
            evidence_items=aggregate_evidence_items,
        )
        final_conflicting_answer = _normalise_spaces(str(final_conflicting_narrative.get("answer") or ""))
        if (
            final_conflicting_answer
            and str(final_conflicting_narrative.get("operation_family") or "") == "aggregate_subtasks"
            and not _narrative_sentence_looks_table_noisy(final_conflicting_answer)
            and numeric_surface_conflicts_with_reference(final_answer, final_conflicting_answer)
        ):
            candidate_application = apply_aggregate_answer_candidate(
                AggregateAnswerCandidateApplicationInput(
                    aggregate_projection=aggregate_projection,
                    selected_claim_ids=selected_claim_ids,
                    candidate=package_aggregate_answer_candidate(
                        AggregateAnswerCandidatePackagingInput(
                            answer=final_conflicting_answer,
                            selected_claim_ids=final_conflicting_narrative.get("selected_claim_ids") or [],
                            sync_projection=False,
                        )
                    ).candidate,
                )
            )
            aggregate_projection = candidate_application.aggregate_projection
            final_answer = candidate_application.final_answer
            selected_claim_ids = candidate_application.selected_claim_ids
            aggregate_projection = self._rebuild_aggregate_projection(ordered_results, final_answer)
            _sync_state(aggregate_projection=aggregate_projection, final_answer=final_answer)
        return self._build_aggregate_completion_update(
            state,
            ordered_results=ordered_results,
            aggregate_projection=aggregate_projection,
            final_answer=final_answer,
            selected_claim_ids=selected_claim_ids,
            aggregate_evidence_items=aggregate_evidence_items,
            ledger_artifacts=ledger_artifacts,
            planner_feedback=planner_feedback,
            should_replan=should_replan,
            replan_blocked_reason=replan_blocked_reason,
            aggregate_synthesis_debug=aggregate_synthesis_debug,
        )

    def _prepare_reflection_retry(self, state: FinancialAgentState) -> Dict[str, Any]:
        current_count = int(state.get("reflection_count") or 0)
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        operands = list(runtime_trace.get("calculation_operands") or [])
        plan = dict(runtime_trace.get("calculation_plan") or {})
        calc_result = dict(runtime_trace.get("calculation_result") or {})
        reflection_plan = dict(state.get("reflection_plan") or {})

        missing_info = [
            str(item).strip()
            for item in (
                reflection_plan.get("missing_info")
                or plan.get("missing_info")
                or state.get("missing_info")
                or []
            )
            if str(item).strip()
        ]
        if not missing_info:
            missing_info = self._infer_missing_info(state, operands)
        retry_queries = self._finalize_retry_queries(state, reflection_plan, missing_info)
        retry_strategy = _normalise_spaces(
            str(reflection_plan.get("retry_strategy") or state.get("retry_strategy") or "retry_retrieval")
        ).lower()
        if retry_strategy == "synthesize_from_task_outputs" and not any(
            str(item).strip() for item in (reflection_plan.get("synthesis_source_ids") or [])
        ):
            synthesis_source_ids = reflection_synthesis_source_ids_from_task_outputs(
                active_subtask=dict(state.get("active_subtask") or {}),
                subtask_results=list(state.get("subtask_results") or []),
                artifacts=list(state.get("artifacts") or []),
            )
            if synthesis_source_ids:
                reflection_plan["synthesis_source_ids"] = synthesis_source_ids
        reflection_action = _reflection_action_from_plan(
            reflection_plan,
            retry_queries=retry_queries,
            retry_strategy=retry_strategy,
        )
        reflection_report = _reflection_report_from_action(
            state,
            reflection_action=reflection_action,
            reflection_request=dict(state.get("reflection_request") or {}),
        )
        active_subtask = dict(state.get("active_subtask") or {})
        target_task_id = str(active_subtask.get("task_id") or "").strip()
        reflection_task_id = next_reflection_task_id(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            target_task_id=target_task_id,
            current_count=current_count,
        )
        reflection_artifact_update = _build_reflection_report_artifact_update(
            tasks=list(state.get("tasks") or []),
            artifacts=list(state.get("artifacts") or []),
            reflection_task_id=reflection_task_id,
            target_task_id=target_task_id,
            query=str(state.get("query") or ""),
            metric_family=str(active_subtask.get("metric_family") or ""),
            reflection_report=reflection_report,
            reflection_action=reflection_action,
            reflection_request=dict(state.get("reflection_request") or {}),
            reflection_plan=reflection_plan,
            retry_strategy=retry_strategy,
        )
        tasks = list(reflection_artifact_update["tasks"])
        artifacts = list(reflection_artifact_update["artifacts"])
        retry_reason = (
            str(reflection_plan.get("explanation") or "")
            or str(plan.get("explanation") or "")
            or str(calc_result.get("explanation") or "")
            or str(state.get("retry_reason") or "")
            or "missing operands"
        )
        logger.info(
            "[reflection] trigger retry=%s missing_info=%s retry_queries=%s reason=%s",
            current_count + 1,
            missing_info,
            retry_queries,
            retry_reason,
        )
        return {
            "missing_info": missing_info,
            "reflection_count": current_count + 1,
            "retry_reason": retry_reason,
            "retry_strategy": str(reflection_action.get("action_type") or retry_strategy),
            "retry_queries": list(reflection_action.get("retry_queries") or []),
            "reflection_action": reflection_action,
            "reflection_report": reflection_report,
            "tasks": tasks,
            "artifacts": artifacts,
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
            **_clear_calculation_debug_state(),
            "planner_debug_trace": {},
            "reflection_plan": reflection_plan,
            **_runtime_trace_state_update(
                state,
                calculation_operands=[],
                calculation_plan={},
                calculation_result={},
            ),
        }

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen = set()
        citations: List[str] = []
        selected_claim_ids = {
            str(claim_id).strip()
            for claim_id in (state.get("selected_claim_ids") or [])
            if str(claim_id).strip()
        }
        for evidence in list(state.get("evidence_items") or []):
            if not isinstance(evidence, dict):
                continue
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if selected_claim_ids and evidence_id not in selected_claim_ids:
                continue
            anchor = _normalise_spaces(str(evidence.get("source_anchor") or ""))
            metadata = dict(evidence.get("metadata") or {})
            metadata_anchor = self._build_source_anchor(metadata) if metadata else ""
            if metadata_anchor and (not anchor or len(metadata_anchor) > len(anchor)):
                anchor = metadata_anchor
            if not anchor:
                continue
            key = ("evidence", anchor)
            if key in seen:
                continue
            seen.add(key)
            citations.append(anchor)
        for doc, score in state.get("retrieved_docs", []):
            metadata = doc.metadata or {}
            key = (
                metadata.get("company"),
                metadata.get("year"),
                metadata.get("section_path"),
                metadata.get("chunk_uid"),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                f"[{metadata.get('company', '?')}] {metadata.get('year', '?')}년 "
                f"{metadata.get('report_type', '?')} / {metadata.get('section_path', metadata.get('section', '?'))} "
                f"/ {metadata.get('block_type', '?')} (score: {score:.3f})"
            )
        return {"citations": citations}
