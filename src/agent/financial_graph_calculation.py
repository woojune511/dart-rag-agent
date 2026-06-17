"""
Calculation mixin for the financial graph agent.

This module owns the structured numeric path after reconciliation:
- extract normalized operands
- plan the calculation formula
- execute and verify the numeric result
- advance or aggregate multi-subtask calculations
"""

import json
import logging
import re
from typing import Any, Dict, List, NamedTuple, Optional, Sequence

from langchain_core.prompts import ChatPromptTemplate
from src.agent import financial_answer_slots
from src.agent.financial_calculation_execution import (
    build_failed_calculation_result,
    build_scalar_calculation_state,
    build_scalar_calculation_result,
    build_success_calculation_state_payload,
    build_time_series_calculation_result,
    time_series_yoy_growth_rates,
)
from src.agent.financial_dependency_projection import (
    apply_absolute_ratio_magnitude_if_requested,
    align_lookup_result_units_from_peer_source_slots,
    build_dependency_lookup_slots_by_task,
    build_dependency_recalculated_row,
    build_dependency_recalculation_state,
    collect_table_label_evidence_candidates,
    dedupe_dependency_operands_by_id,
    dependency_operand_from_answer_slot,
    dependency_operand_from_source_slot,
    dependency_operand_from_table_label_evidence,
    derive_dependency_operands_from_source_task_slots,
    fill_missing_ratio_dependency_operands,
    lookup_primary_slot,
    refresh_dependency_operands_from_lookup_slots,
    realign_lookup_row_from_dependency_projection,
    rebuild_dependency_calculation_plan,
    replace_lookup_primary_slot,
)
from src.agent import financial_graph_calculation_rendering as calculation_rendering
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_helpers import (
    _collect_nested_result_evidence,
    _operand_row_has_material_numeric_payload,
    _operand_segment_label,
    _surface_match_variants,
)
from src.agent.financial_numeric_surface import (
    evidence_numeric_display_candidates,
    evidence_text_for_numeric_support,
    extract_numeric_surface_candidates,
    numeric_surface_slot_components,
    numeric_surface_candidates_equivalent,
)
from src.agent.financial_reflection_projection import (
    reflection_action_from_plan as _reflection_action_from_plan,
    reflection_report_from_action as _reflection_report_from_action,
    task_artifact_integrity_feedback as _task_artifact_integrity_feedback,
)
from src.agent.financial_text_surface import (
    narrative_sentence_looks_abbreviated_fragment as _narrative_sentence_looks_abbreviated_fragment,
    narrative_sentence_looks_table_noisy as _narrative_sentence_looks_table_noisy,
    polish_korean_particle_pairs as _polish_korean_particle_pairs,
    split_narrative_sentences as _split_narrative_sentences,
    topic_particle as _topic_particle,
)
from src.agent.financial_graph_models import (
    AggregateSynthesisOutput,
    CalculationPlan,
    CalculationRenderOutput,
    CalculationResult,
    CalculationVerificationOutput,
    FinancialAgentState,
    OperandExtraction,
    validate_answer_slots_payload,
)
from src.agent.financial_graph_planning import _synthesize_lookup_answer_slot_from_prose
from src.config import get_financial_ontology
from src.config.runtime_contract import CALCULATION_DEBUG_TRACE_FIELD
from src.config.retrieval_policy import (
    CALCULATION_FEEDBACK_POLICY,
    CALCULATION_NARRATIVE_POLICY,
    CALCULATION_PROMPT_POLICY,
    CALCULATION_RENDER_POLICY,
    CALCULATION_SLOT_POLICY,
    CONSOLIDATION_SCOPE_POLICY,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    KOREAN_TABLE_CHANGE_HEADER_LABEL,
    KOREAN_TABLE_LABEL_ALPHA_RE_FRAGMENT,
    KOREAN_TABLE_LABEL_LEFT_BOUNDARY_RE_FRAGMENT,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
    OPERAND_CANDIDATE_SCORING_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
    narrative_policy_terms,
)
from src.schema import ArtifactKind, TaskKind, TaskStatus

logger = logging.getLogger(__name__)


class _AggregateSynthesisState(NamedTuple):
    ordered_results: List[Dict[str, Any]]
    aggregate_projection: Dict[str, Any]
    final_answer: str
    selected_claim_ids: List[str]


class _PreparedAggregateState(NamedTuple):
    ordered_results: List[Dict[str, Any]]
    fallback_answer: str
    supported_aggregate_answer: str
    complete_numeric_answer: str
    has_narrative_summary: bool
    has_growth_rate_result: bool
    numeric_answer_locked: bool


class _AggregateEvidenceState(NamedTuple):
    ordered_results: List[Dict[str, Any]]
    aggregate_evidence_items: List[Dict[str, Any]]
    fallback_answer: str
    final_answer: str
    complete_numeric_answer: str
    deterministic_feedback: str


class _AggregateFeedbackState(NamedTuple):
    final_answer: str
    planner_feedback: str
    deterministic_feedback: str
    ledger_artifacts: List[Dict[str, Any]]
    task_artifact_trace: Dict[str, Any]
    should_replan: bool
    replan_blocked_reason: str


class _AggregateCompositionState(NamedTuple):
    final_answer: str
    selected_claim_ids: List[str]
    calculation_projection_override: Optional[Dict[str, Any]]
    narrative_answer_locked: bool
    planner_feedback: str
    deterministic_feedback: str


class _AggregateMutableState(NamedTuple):
    synthesis_state: _AggregateSynthesisState
    evidence_items: List[Dict[str, Any]]

    @property
    def ordered_results(self) -> List[Dict[str, Any]]:
        return self.synthesis_state.ordered_results

    @property
    def aggregate_projection(self) -> Dict[str, Any]:
        return self.synthesis_state.aggregate_projection

    @property
    def final_answer(self) -> str:
        return self.synthesis_state.final_answer

    @property
    def selected_claim_ids(self) -> List[str]:
        return self.synthesis_state.selected_claim_ids


def _inline_unit_match_has_right_boundary(
    text: str,
    match: re.Match[str],
    *,
    group_name: str = "unit",
) -> bool:
    try:
        unit_end = match.end(group_name)
    except IndexError:
        return True
    if unit_end >= len(text):
        return True
    render_policy = dict(CALCULATION_RENDER_POLICY)
    suffix = str(text[unit_end:])
    allowed_prefixes = tuple(
        str(item)
        for item in (render_policy.get("inline_unit_right_boundary_allowed_prefixes") or ())
        if str(item)
    )
    if any(suffix.startswith(prefix) for prefix in allowed_prefixes):
        return True
    block_pattern = str(render_policy.get("inline_unit_right_boundary_block_pattern") or "")
    return not bool(block_pattern and re.match(block_pattern, text[unit_end]))


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


def _evidence_item_conflicts_requested_scope(
    item: Dict[str, Any],
    desired_consolidation_scope: str,
) -> bool:
    desired_scope = _normalise_spaces(str(desired_consolidation_scope or "unknown"))
    if desired_scope == "unknown":
        return False
    metadata = dict((item or {}).get("metadata") or {})
    metadata_scope = _normalise_spaces(str(metadata.get("consolidation_scope") or "unknown"))
    if metadata_scope == desired_scope:
        return False
    scope_policy = dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {})
    consolidated_markers = tuple(
        str(marker).lower() for marker in (scope_policy.get("consolidated") or ()) if str(marker)
    )
    separate_markers = tuple(str(marker).lower() for marker in (scope_policy.get("separate") or ()) if str(marker))
    context_text = _normalise_spaces(
        " ".join(
            str(value or "")
            for value in (
                metadata.get("section_path"),
                metadata.get("section"),
                metadata.get("local_heading"),
                metadata.get("table_context"),
                metadata.get("caption"),
                metadata.get("table_summary_text"),
                metadata.get("table_header_context"),
                item.get("source_context"),
                item.get("claim"),
                item.get("quote_span"),
                item.get("raw_row_text"),
            )
            if str(value or "").strip()
        )
    ).lower()
    has_consolidated_context = bool(
        consolidated_markers and any(marker in context_text for marker in consolidated_markers)
    )
    has_separate_context = bool(separate_markers and any(marker in context_text for marker in separate_markers))
    if desired_scope == "consolidated":
        if metadata_scope == "separate":
            return True
        if has_consolidated_context:
            return False
        return has_separate_context
    if desired_scope == "separate":
        if metadata_scope == "consolidated":
            return True
        if has_separate_context:
            return False
        return has_consolidated_context
    return False


def _synthesis_source_ids_from_task_outputs(state: FinancialAgentState) -> List[str]:
    active_subtask = dict(state.get("active_subtask") or {})
    preferred_task_ids: List[str] = []
    for binding in active_subtask.get("inputs") or []:
        if not isinstance(binding, dict):
            continue
        source_preference = [
            _normalise_spaces(str(item or "")).lower()
            for item in (binding.get("source_preference") or [])
            if _normalise_spaces(str(item or ""))
        ]
        preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
        if "task_output" in source_preference and preferred_task_id:
            preferred_task_ids.append(preferred_task_id)
    if not preferred_task_ids:
        preferred_task_ids = [
            _normalise_spaces(str(item or ""))
            for item in (active_subtask.get("depends_on") or [])
            if _normalise_spaces(str(item or ""))
        ]

    preferred_task_ids = list(dict.fromkeys(preferred_task_ids))
    if not preferred_task_ids:
        return []

    artifacts_by_id = {
        str(artifact.get("artifact_id") or "").strip(): dict(artifact)
        for artifact in (state.get("artifacts") or [])
        if isinstance(artifact, dict) and str(artifact.get("artifact_id") or "").strip()
    }
    result_by_task_id = {
        str(row.get("task_id") or "").strip(): dict(row)
        for row in (state.get("subtask_results") or [])
        if isinstance(row, dict) and str(row.get("task_id") or "").strip()
    }

    source_ids: List[str] = []
    for task_id in preferred_task_ids:
        result_row = result_by_task_id.get(task_id)
        if not result_row:
            continue
        artifact_ids = [
            str(item).strip()
            for item in (result_row.get("artifact_ids") or [])
            if str(item).strip()
        ]
        result_artifact_ids = [
            artifact_id
            for artifact_id in artifact_ids
            if str(artifacts_by_id.get(artifact_id, {}).get("kind") or "").strip()
            == ArtifactKind.CALCULATION_RESULT.value
        ]
        source_ids.extend(result_artifact_ids or artifact_ids)
        if not artifact_ids and result_row.get("calculation_result"):
            source_ids.append(f"task_output:{task_id}")

    return list(dict.fromkeys(item for item in source_ids if item))


def _next_reflection_task_id(
    state: FinancialAgentState,
    *,
    target_task_id: str,
    current_count: int,
) -> str:
    target = _normalise_spaces(str(target_task_id or "")) or "global"
    prefix = f"reflection:{target}:"
    used_indexes: set[int] = set()
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)(?::report)?$")
    for task in state.get("tasks") or []:
        if not isinstance(task, dict):
            continue
        match = pattern.match(str(task.get("task_id") or "").strip())
        if match:
            used_indexes.add(int(match.group(1)))
    for artifact in state.get("artifacts") or []:
        if not isinstance(artifact, dict):
            continue
        for value in (artifact.get("task_id"), artifact.get("artifact_id")):
            match = pattern.match(str(value or "").strip())
            if match:
                used_indexes.add(int(match.group(1)))
    next_index = max(int(current_count or 0) + 1, 1)
    while next_index in used_indexes:
        next_index += 1
    return f"{prefix}{next_index:03d}"


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
    def _calculation_operand_source_refs(self, operand_rows: List[Dict[str, Any]]) -> List[str]:
        refs: List[str] = []
        for row in operand_rows or []:
            if not isinstance(row, dict):
                continue
            refs.extend(
                _clean_source_row_ids(
                    [
                        row.get("evidence_id"),
                        row.get("evidence_ids"),
                        row.get("source_evidence_id"),
                        row.get("source_evidence_ids"),
                        row.get("source_row_id"),
                        row.get("source_row_ids"),
                        row.get("row_id"),
                        row.get("row_ids"),
                        row.get("candidate_id"),
                        row.get("candidate_ids"),
                    ]
                )
            )
        return list(dict.fromkeys(refs))

    def _evidence_items_with_runtime(
        self,
        evidence_items: List[Dict[str, Any]],
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        combined = list(evidence_items)
        existing_ids = {
            str(item.get("evidence_id") or "").strip()
            for item in combined
            if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
        }
        for item in state.get("runtime_evidence") or []:
            if not isinstance(item, dict):
                continue
            evidence_id = str(item.get("evidence_id") or "").strip()
            if evidence_id and evidence_id in existing_ids:
                continue
            if evidence_id:
                existing_ids.add(evidence_id)
            combined.append(dict(item))
        return combined

    def _evidence_items_by_id(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            str(item.get("evidence_id") or "").strip(): dict(item)
            for item in evidence_items
            if str(item.get("evidence_id") or "").strip()
        }

    @staticmethod
    def _known_consolidation_scope_value(*values: Any) -> str:
        policy_values = {
            str(scope): tuple(str(marker).lower() for marker in (markers or ()) if str(marker))
            for scope, markers in dict(CONSOLIDATION_SCOPE_POLICY.get("metadata_values") or {}).items()
        }
        for value in values:
            scope = _normalise_spaces(str(value or "")).lower()
            if not scope:
                continue
            if scope in {"consolidated", "separate"}:
                return scope
            exact_scope = next(
                (
                    candidate_scope
                    for candidate_scope, markers in policy_values.items()
                    if scope in markers
                ),
                "",
            )
            if exact_scope:
                return exact_scope
            marker_matches = [
                (len(marker), candidate_scope)
                for candidate_scope, markers in policy_values.items()
                for marker in markers
                if marker and marker in scope
            ]
            if marker_matches:
                return max(marker_matches)[1]
        return ""

    def _enrich_reconciliation_artifact_refs(
        self,
        artifacts: List[Dict[str, Any]],
        *,
        task_id: str,
        operand_rows: List[Dict[str, Any]],
        extra_refs: Optional[List[Any]] = None,
        task_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        refs = list(
            dict.fromkeys(
                [
                    *self._calculation_operand_source_refs(operand_rows),
                    *_clean_source_row_ids(extra_refs or []),
                ]
            )
        )
        if not refs:
            return artifacts
        target_task_id = str(task_id or "").strip()
        target_task_ids = {
            str(value).strip()
            for value in [target_task_id, *(task_ids or [])]
            if str(value).strip()
        }
        updated: List[Dict[str, Any]] = []
        for artifact in artifacts or []:
            item = dict(artifact)
            if str(item.get("kind") or "").strip() != ArtifactKind.RECONCILIATION_RESULT.value:
                updated.append(item)
                continue
            if target_task_ids and str(item.get("task_id") or "").strip() not in target_task_ids:
                updated.append(item)
                continue
            payload = item.get("payload") if isinstance(item.get("payload"), dict) else {}
            result = payload.get("reconciliation_result") if isinstance(payload, dict) else {}
            status = str(result.get("status") if isinstance(result, dict) else "").strip().lower()
            if status not in {"ok", "ready"}:
                updated.append(item)
                continue
            merged_refs = list(dict.fromkeys([*(item.get("evidence_refs") or []), *refs]))
            item["evidence_refs"] = merged_refs
            updated.append(item)
        return updated

    def _answer_slot_has_material(self, slot: Dict[str, Any]) -> bool:
        if not isinstance(slot, dict) or not slot:
            return False
        status = str(slot.get("status") or "").strip().lower()
        if status == "missing":
            return False
        if slot.get("normalized_value") is not None:
            return True
        return bool(str(slot.get("rendered_value") or slot.get("raw_value") or "").strip())

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

    def _slot_period_hint(self, slot: Dict[str, Any]) -> str:
        period = _normalise_spaces(str(slot.get("period") or ""))
        if period:
            return period
        label = _normalise_spaces(str(slot.get("label") or ""))
        period_pattern = str(CALCULATION_SLOT_POLICY.get("period_pattern") or "")
        if period_pattern:
            match = re.search(period_pattern, label)
            if match:
                return _normalise_spaces(match.group(0))
        return ""

    def _period_match_key(self, value: str) -> str:
        return re.sub(r"\D", "", _normalise_spaces(str(value or "")))

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
            self._period_match_key(period)
            for period in [
                self._slot_period_hint(target_slot),
                *(
                    match.group(0)
                    for match in re.finditer(str(CALCULATION_SLOT_POLICY.get("period_pattern") or r"$^"), metric_label)
                ),
            ]
            if self._period_match_key(period)
        }

        target_concept = _normalise_spaces(str(target_slot.get("concept") or ""))
        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_result = dict(sibling.get("calculation_result") or {})
            sibling_slots = dict(sibling_result.get("answer_slots") or sibling.get("answer_slots") or {})
            for sibling_slot in self._iter_answer_slots(sibling_slots):
                if not self._answer_slot_has_material(sibling_slot):
                    continue
                if target_concept:
                    sibling_concept = _normalise_spaces(str(sibling_slot.get("concept") or ""))
                    if sibling_concept and sibling_concept != target_concept:
                        continue
                sibling_period = self._period_match_key(self._slot_period_hint(sibling_slot))
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
        current_material = self._answer_slot_has_material(current_slot)
        prior_material = self._answer_slot_has_material(prior_slot)
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

        current_period = self._slot_period_hint(current_slot)
        prior_period = self._slot_period_hint(prior_slot)
        sibling_periods: set[str] = set()

        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_result = dict(sibling.get("calculation_result") or {})
            sibling_slots = dict(sibling_result.get("answer_slots") or {})
            primary_slot = dict(sibling_slots.get("primary_value") or {})
            if not self._answer_slot_has_material(primary_slot):
                continue
            sibling_keys = self._slot_metric_keys(primary_slot)
            if not sibling_keys:
                continue
            if not (target_keys & sibling_keys):
                continue
            period_hint = self._slot_period_hint(primary_slot)
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

    def _narrative_summary_gap_is_satisfied(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        operation_family = str(
            row.get("operation_family")
            or answer_slots.get("operation_family")
            or (row.get("calculation_plan") or {}).get("operation")
            or ""
        ).strip().lower()
        if operation_family == "aggregate_subtasks":
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if metric_family.startswith("concept_"):
                operation_family = metric_family.removeprefix("concept_")
        if operation_family not in {"lookup", "single_value", "ratio", "sum"}:
            return False

        target_surfaces: List[str] = []
        metric_label = _normalise_spaces(str(row.get("metric_label") or ""))
        if metric_label:
            target_surfaces.append(metric_label)
            target_surfaces.append(_normalise_spaces(re.sub(r"^(20\d{2}년\s*)?(연결기준|별도기준)?\s*", "", metric_label)))
        primary_slot = dict(answer_slots.get("primary_value") or {})
        slot_label = _normalise_spaces(str(primary_slot.get("label") or ""))
        if slot_label:
            target_surfaces.append(slot_label)
        components_by_role = dict(answer_slots.get("components_by_role") or {})
        for entries in components_by_role.values():
            for entry in entries or []:
                label = _normalise_spaces(str((entry or {}).get("label") or ""))
                if label:
                    target_surfaces.append(label)
        target_surfaces = [surface for surface in dict.fromkeys(target_surfaces) if surface]
        if not target_surfaces:
            return False

        for sibling in ordered_results:
            if sibling is row:
                continue
            sibling_metric_family = _normalise_spaces(str(sibling.get("metric_family") or "")).lower()
            sibling_operation_family = self._aggregate_result_operation_family(sibling)
            if sibling_metric_family != "narrative_summary" and sibling_operation_family != "narrative_summary":
                continue
            sibling_answer = _normalise_spaces(str(sibling.get("answer") or ""))
            if not sibling_answer or not re.search(r"\d", sibling_answer):
                continue
            if any(surface and surface in sibling_answer for surface in target_surfaces):
                return True
        return False

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
            self._period_match_key(match.group(0))
            for match in re.finditer(r"20\d{2}\s*년?", feedback_text)
            if self._period_match_key(match.group(0))
        }

        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            for slot in self._iter_answer_slots(answer_slots):
                if not self._answer_slot_has_material(slot):
                    continue
                slot_period = self._period_match_key(self._slot_period_hint(slot))
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
            if self._answer_slot_has_material(slot):
                resolved_slots.append(dict(slot))
        for row in list(ordered_results or []):
            row_result = dict(row.get("calculation_result") or {})
            row_slots = dict(row_result.get("answer_slots") or row.get("answer_slots") or {})
            for slot in self._iter_answer_slots(row_slots):
                if self._answer_slot_has_material(slot):
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
                if self._answer_slot_has_material(slot):
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
            if self._answer_slot_has_material(slot):
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
                period_key = self._period_match_key(match.group(0))
                if period_key:
                    period_keys.add(period_key)
        return period_keys

    def _task_target_matches_resolved_slot(
        self,
        task: Dict[str, Any],
        resolved_slots: List[Dict[str, Any]],
    ) -> bool:
        target_keys = self._task_target_metric_keys(task)
        if not target_keys:
            return False
        target_periods = self._task_target_period_keys(task)
        for slot in resolved_slots:
            slot_keys = self._slot_metric_keys(slot)
            if not slot_keys:
                continue
            slot_period = self._period_match_key(self._slot_period_hint(slot))
            if target_periods and slot_period and slot_period not in target_periods:
                continue
            if target_periods and not slot_period:
                continue
            if target_keys & slot_keys:
                return True
            if any(
                target_key and slot_key and (target_key in slot_key or slot_key in target_key)
                for target_key in target_keys
                for slot_key in slot_keys
            ):
                return True
        return False

    def _finalize_aggregate_task_ledger(
        self,
        tasks: List[Dict[str, Any]],
        artifacts: List[Dict[str, Any]],
        *,
        ordered_results: List[Dict[str, Any]],
        aggregate_projection: Dict[str, Any],
        aggregate_artifact_id: str,
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        resolved_slots = self._final_aggregate_resolved_slots(aggregate_projection, ordered_results)
        updated_tasks = [dict(item) for item in tasks]
        updated_artifacts = [dict(item) for item in artifacts]

        for task in list(updated_tasks):
            task_id = str(task.get("task_id") or "").strip()
            if not task_id or task_id == "aggregate":
                continue
            status = _normalise_spaces(str(task.get("status") or "")).lower()
            if status not in {TaskStatus.PENDING.value, TaskStatus.PARTIAL.value}:
                continue
            if not self._task_target_matches_resolved_slot(task, resolved_slots):
                continue
            try:
                task_kind = TaskKind(str(task.get("kind") or TaskKind.CALCULATION.value))
            except ValueError:
                task_kind = TaskKind.CALCULATION
            constraints = dict(task.get("constraints") or {})
            constraints.update(
                {
                    "resolution_status": "superseded_by_aggregate_result",
                    "superseded_by_task_id": "aggregate",
                    "superseded_by_artifact_id": aggregate_artifact_id,
                }
            )
            notes = list(dict.fromkeys([*(task.get("notes") or []), "superseded_by_aggregate_result"]))
            updated_tasks = _upsert_task(
                updated_tasks,
                task_id=task_id,
                kind=task_kind,
                label=str(task.get("label") or task_id),
                status=TaskStatus.SUPERSEDED,
                query=str(task.get("query") or ""),
                metric_family=str(task.get("metric_family") or ""),
                constraints=constraints,
                notes=notes,
            )
        return updated_tasks, updated_artifacts

    def _row_is_narrative_summary(self, row: Dict[str, Any]) -> bool:
        metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
        operation_family = self._aggregate_result_operation_family(row)
        return metric_family == "narrative_summary" or operation_family == "narrative_summary"

    def _unresolved_structured_numeric_gap(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        for row in ordered_results:
            if self._row_is_narrative_summary(row):
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
            gap = self._material_gap_feedback_for_subtask_result(row)
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

    def _safe_partial_answer_for_numeric_gap(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        safe_parts: List[str] = []
        for row in ordered_results:
            if self._row_is_narrative_summary(row):
                continue
            status = str(
                row.get("status")
                or (row.get("calculation_result") or {}).get("status")
                or ""
            ).strip().lower()
            if status != "ok":
                continue
            if self._material_gap_feedback_for_subtask_result(row):
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

    def _compose_lookup_list_numeric_answer(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        lookup_result_count = 0
        items: List[str] = []
        for row in ordered_results:
            if self._row_is_narrative_summary(row):
                continue
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"lookup", "single_value"}:
                return ""
            lookup_result_count += 1
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            item_answer = self._lookup_numeric_item_answer(row)
            if item_answer:
                items.append(item_answer)
        items = list(dict.fromkeys(item for item in items if item))
        if lookup_result_count < 2 or len(items) < 2:
            return ""
        separator = str(CALCULATION_RENDER_POLICY.get("lookup_list_separator") or ", ")
        answer_template = str(CALCULATION_RENDER_POLICY.get("lookup_list_answer_template") or "{items}")
        return _normalise_spaces(answer_template.format(items=separator.join(items)))

    def _lookup_numeric_item_answer(
        self,
        row: Dict[str, Any],
        *,
        require_primary_slot: bool = False,
        require_numeric: bool = False,
    ) -> str:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        primary_slot = dict(answer_slots.get("primary_value") or {})
        if require_primary_slot and not self._answer_slot_has_material(primary_slot):
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
        if require_numeric and not self._answer_evidence_numeric_candidates(value):
            return ""
        item_template = str(CALCULATION_RENDER_POLICY.get("lookup_list_item_template") or "{label} {value}")
        return _normalise_spaces(item_template.format(label=label, value=value))

    def _append_uncovered_lookup_numeric_items(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return answer_text
        has_aggregate_numeric = any(
            self._aggregate_result_operation_family(row) in {"ratio", "sum", "difference", "growth_rate"}
            for row in ordered_results
            if isinstance(row, dict)
        )
        if not has_aggregate_numeric:
            return answer_text
        missing_items: List[str] = []
        for row in ordered_results:
            if not isinstance(row, dict) or self._row_is_narrative_summary(row):
                continue
            if self._aggregate_result_operation_family(row) not in {"lookup", "single_value"}:
                continue
            status = _normalise_spaces(
                str(row.get("status") or (row.get("calculation_result") or {}).get("status") or "")
            ).lower()
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            item_answer = self._lookup_numeric_item_answer(
                row,
                require_primary_slot=True,
                require_numeric=True,
            )
            if not item_answer or self._answer_covers_numeric_answer(answer_text, item_answer):
                continue
            missing_items.append(item_answer)
        missing_items = list(dict.fromkeys(item for item in missing_items if item))
        if not missing_items:
            return answer_text
        prefix = ". ".join(item.rstrip(".") for item in missing_items)
        if prefix:
            prefix = f"{prefix}."
        return _normalise_spaces(" ".join([prefix, answer_text]))

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
        structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
        if prefers_aggregate and not structured_cells:
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
                if re.search(rf"(?<!\w){re.escape(normalized_label)}(?!\w)", normalized_surface):
                    return True
            return False

        matches: List[Dict[str, Any]] = []
        for line in str(metadata.get("table_value_labels_text") or "").splitlines():
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
                    "_semantic_label": normalized_line,
                    "_matched_surface": matched_surface,
                    "_matched_line_label": matched_line_label,
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
        if prefers_aggregate and len(candidate_pool) > 1 and not row_label_matches_operand:
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
        return _coerce_lookup_magnitude_record(
            selected,
            evidence_item,
            concept=str(operand.get("concept") or ""),
            statement_type=str(metadata.get("statement_type") or ""),
            row_label=str(operand.get("label") or selected.get("label") or ""),
            semantic_label=semantic_label,
        )

    def _table_label_metadata_lookup_score(
        self,
        slot: Dict[str, Any],
        evidence_item: Dict[str, Any],
    ) -> float:
        if not slot:
            return 0.0
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
        metadata = dict(evidence_item.get("metadata") or {})
        if not _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
            return 0.0
        raw_unit = _normalise_spaces(str(slot.get("raw_unit") or metadata.get("unit_hint") or ""))
        raw_digit_count = len(re.findall(r"\d", str(slot.get("raw_value") or "")))
        if normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4:
            return 0.0
        score = 6.5
        if _normalise_spaces(str(metadata.get("unit_hint") or "")):
            score += 0.5
        if _normalise_spaces(str(metadata.get("table_source_id") or "")):
            score += 0.5
        if _normalise_spaces(str(slot.get("source_anchor") or evidence_item.get("source_anchor") or "")):
            score += 0.25
        if normalized_unit in {"", "UNKNOWN"}:
            score -= 1.5
        else:
            score += 0.25
        return score

    def _direct_structured_lookup_evidence_score(
        self,
        operand: Dict[str, Any],
        evidence_item: Dict[str, Any],
    ) -> float:
        metadata = dict(evidence_item.get("metadata") or {})
        structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
        if not structured_cells:
            return 0.0

        score = 0.0
        row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
        semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
        binding_policy = dict(operand.get("binding_policy") or {})
        requires_surface_contract = bool(
            binding_policy.get("require_surface_contract_for_direct_match")
            or binding_policy.get("require_surface_contract_for_direct_lookup")
        )
        if requires_surface_contract:
            authoritative_surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        evidence_item.get("claim"),
                        evidence_item.get("quote_span"),
                        evidence_item.get("raw_row_text"),
                        row_label,
                        semantic_label,
                    )
                )
            )
            if not _text_has_positive_surface(authoritative_surface, operand):
                return 0.0

        operand_needles = [
            _normalise_spaces(str(needle))
            for needle in _operand_needles(operand)
            if _normalise_spaces(str(needle))
        ]
        def _surface_variants(text: str) -> set[str]:
            normalized = _normalise_spaces(text)
            compact = re.sub(r"\s+", "", normalized)
            return {item for item in (normalized, compact) if item}

        row_variants = _surface_variants(row_label) if row_label else set()
        semantic_variants = _surface_variants(semantic_label) if semantic_label else set()
        needle_variants = {
            variant
            for needle in operand_needles
            for variant in _surface_variants(needle)
            if variant
        }
        if row_variants and needle_variants and row_variants & needle_variants:
            score += 8.0
        elif row_label and _operand_text_match(row_label, operand):
            score += 4.0
        if semantic_variants and needle_variants and semantic_variants & needle_variants:
            score += 3.0
        elif semantic_label and semantic_label != row_label and _operand_text_match(semantic_label, operand):
            score += 1.5

        numeric_cells = 0
        header_affinity = False
        for cell in structured_cells:
            raw_value = _normalise_spaces(str(cell.get("value_text") or ""))
            raw_unit = _normalise_spaces(str(cell.get("unit_hint") or metadata.get("unit_hint") or ""))
            normalized_value, _normalized_unit = _normalise_operand_value(raw_value, raw_unit)
            if normalized_value is None:
                continue
            numeric_cells += 1
            headers = _normalise_spaces(
                " ".join(str(header) for header in (cell.get("column_headers") or []) if str(header).strip())
            )
            if headers and _operand_text_match(headers, operand):
                header_affinity = True
        if header_affinity:
            score += 1.0
        direct_row_from_value_labels = bool(metadata.get("direct_row_from_table_value_labels"))
        if direct_row_from_value_labels:
            score += 1.0
        if numeric_cells == 1:
            score += 1.0
        elif numeric_cells > 1 and not direct_row_from_value_labels:
            score -= 2.0

        value_role = _normalise_spaces(str(metadata.get("value_role") or ""))
        aggregation_stage = _normalise_spaces(str(metadata.get("aggregation_stage") or ""))
        if value_role == "adjustment":
            score -= 4.0
        if aggregation_stage in {"direct", "final", "subtotal"}:
            score += 0.75
        return score

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
        return _coerce_lookup_magnitude_record(
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

        for evidence_item in evidence_pool:
            evidence = dict(evidence_item or {})
            score = self._direct_structured_lookup_evidence_score(operand, evidence)
            if score > 0:
                score += _context_scope_score(evidence)
            should_consider_structured = score > best_score
            if score == best_score and best_slot:
                row = self._lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence,
                    index=1,
                )
                should_consider_structured = _candidate_preferred_on_tie(row, best_slot)
            if should_consider_structured:
                row = self._lookup_row_from_direct_structured_evidence(
                    operand,
                    evidence,
                    index=1,
                )
                if state is not None and self._lookup_direct_row_is_ambiguous_context_table(
                    row,
                    evidence,
                    state=state,
                    required_operands=[operand],
                ):
                    row = {}
                normalized_unit = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
                raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
                raw_digit_count = len(re.findall(r"\d", str(row.get("raw_value") or "")))
                if row and not (normalized_unit in {"", "UNKNOWN"} and not raw_unit and raw_digit_count < 4):
                    adjusted_score = score - 1.5 if normalized_unit in {"", "UNKNOWN"} else score
                    best_slot = self._build_operand_value_slot(
                        row,
                        default_role=str(operand.get("role") or "primary_value"),
                        preserve_source_display=True,
                    )
                    best_score = adjusted_score

            table_label_slot = self._lookup_value_from_table_label_metadata(operand, evidence)
            table_label_score = self._table_label_metadata_lookup_score(table_label_slot, evidence)
            if table_label_score > 0:
                table_label_score += _context_scope_score(evidence)
            if state is not None and self._lookup_direct_row_is_ambiguous_context_table(
                table_label_slot,
                evidence,
                state=state,
                required_operands=[operand],
            ):
                table_label_slot = {}
            if table_label_slot and (
                table_label_score > best_score
                or (
                    table_label_score == best_score
                    and best_slot
                    and _candidate_preferred_on_tie(table_label_slot, best_slot)
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

    def _best_direct_lookup_slot_from_evidence_pool_compat(
        self,
        operand: Dict[str, Any],
        evidence_pool: List[Dict[str, Any]],
        *,
        state: Optional[FinancialAgentState] = None,
        preferred_raw_units: Optional[set[str]] = None,
    ) -> tuple[Dict[str, Any], float]:
        try:
            return self._best_direct_lookup_slot_from_evidence_pool(
                operand,
                evidence_pool,
                state=state,
                preferred_raw_units=preferred_raw_units,
            )
        except TypeError as exc:
            if "unexpected keyword argument 'state'" not in str(exc):
                raise
            return self._best_direct_lookup_slot_from_evidence_pool(operand, evidence_pool)

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

        evidence_by_id = self._evidence_items_by_id(evidence_items)
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
            preferred_slot, best_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                operand,
                evidence_items,
                state=state,
                preferred_raw_units=peer_units if operation_family == "ratio" else None,
            )
            if not preferred_slot:
                continue
            current_score = 0.0
            current_evidence = self._evidence_item_for_operand_row(current, evidence_by_id)
            if current_evidence:
                current_score = self._direct_structured_lookup_evidence_score(operand, current_evidence)
            preferred_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
            current_unit = _normalise_spaces(str(current.get("raw_unit") or ""))
            preferred_raw = _normalise_spaces(str(preferred_slot.get("raw_value") or ""))
            current_raw = _normalise_spaces(str(current.get("raw_value") or ""))
            unit_alignment_improves = bool(
                operation_family == "ratio"
                and peer_units
                and preferred_raw == current_raw
                and preferred_unit in peer_units
                and current_unit not in peer_units
            )
            if current_score > best_score and not unit_alignment_improves:
                continue
            if current_score == best_score and not unit_alignment_improves:
                continue
            preferred_row = {
                **current,
                "operand_id": current.get("operand_id") or f"direct_lookup_{row_index + 1:03d}",
                "evidence_id": preferred_slot.get("source_row_id"),
                "source_row_id": preferred_slot.get("source_row_id"),
                "source_row_ids": preferred_slot.get("source_row_ids") or [],
                "source_anchor": preferred_slot.get("source_anchor"),
                "label": preferred_slot.get("label"),
                "raw_value": preferred_slot.get("raw_value"),
                "raw_unit": preferred_slot.get("raw_unit"),
                "normalized_value": preferred_slot.get("normalized_value"),
                "normalized_unit": preferred_slot.get("normalized_unit"),
                "period": preferred_slot.get("period"),
                "value_role": preferred_slot.get("value_role"),
                "aggregation_stage": preferred_slot.get("aggregation_stage"),
                "aggregate_label": preferred_slot.get("aggregate_label"),
                "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
                "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
                "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
            }
            refined_rows[row_index] = preferred_row
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
                if _evidence_item_conflicts_requested_scope(item, desired_scope):
                    continue
                evidence_id = str(item.get("evidence_id") or "").strip()
                if evidence_id and evidence_id in existing_ids:
                    continue
                if evidence_id:
                    existing_ids.add(evidence_id)
                evidence_pool.append(dict(item))
        if not evidence_pool:
            return ordered_results
        evidence_by_id = self._evidence_items_by_id(evidence_pool)

        def _digit_count(value: Any) -> int:
            return len(re.findall(r"\d", str(value or "")))

        def _value_refinement_allowed(
            current_slot: Dict[str, Any],
            preferred_slot: Dict[str, Any],
            preferred_evidence: Optional[Dict[str, Any]],
        ) -> bool:
            preferred_metadata = dict((preferred_evidence or {}).get("metadata") or {})
            has_structured_surface = any(
                _normalise_spaces(str(value or ""))
                for value in (
                    preferred_metadata.get("table_value_labels_text"),
                    preferred_metadata.get("row_label"),
                    preferred_metadata.get("semantic_label"),
                    preferred_metadata.get("structured_cells"),
                )
            )
            if not has_structured_surface:
                return False
            if bool(preferred_metadata.get("table_value_labels_text")) and _recovered_slot_has_primary_label_match(
                preferred_slot
            ):
                current_raw_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                preferred_raw_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
                if preferred_raw_unit and (not current_raw_unit or preferred_raw_unit == current_raw_unit):
                    return True
            current_unit = _normalise_spaces(str(current_slot.get("normalized_unit") or "")).upper()
            preferred_unit = _normalise_spaces(str(preferred_slot.get("normalized_unit") or "")).upper()
            if not current_unit or not preferred_unit or current_unit == "UNKNOWN" or preferred_unit == "UNKNOWN":
                return False
            if current_unit != preferred_unit:
                return False
            current_value = current_slot.get("normalized_value")
            preferred_value = preferred_slot.get("normalized_value")
            try:
                current_float = float(current_value)
                preferred_float = float(preferred_value)
            except (TypeError, ValueError):
                return False
            if current_float == 0:
                return False
            if (current_float < 0) != (preferred_float < 0):
                return False
            relative_delta = abs(preferred_float - current_float) / max(abs(current_float), abs(preferred_float), 1.0)
            if relative_delta > 0.005:
                evidence_score = (
                    self._direct_structured_lookup_evidence_score(operand, preferred_evidence)
                    if preferred_evidence
                    else 0.0
                )
                direct_label = _normalise_spaces(
                    str(
                        preferred_metadata.get("row_label")
                        or preferred_metadata.get("semantic_label")
                        or ""
                    )
                )
                if evidence_score >= 6.0 and direct_label:
                    return True
                return bool(preferred_metadata.get("table_value_labels_text")) and _recovered_slot_has_primary_label_match(
                    preferred_slot
                )
            return _digit_count(preferred_slot.get("raw_value")) > _digit_count(current_slot.get("raw_value"))

        def _normalize_lookup_slot_unit(slot: Dict[str, Any]) -> Dict[str, Any]:
            updated = dict(slot)
            raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
            raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
            evidence_item = self._evidence_item_for_operand_row(updated, evidence_by_id)
            metadata = dict((evidence_item or {}).get("metadata") or {})
            unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
            source_surface = _normalise_spaces(
                " ".join(
                    str((evidence_item or {}).get(key) or "")
                    for key in ("claim", "quote_span", "raw_row_text")
                )
            )
            if raw_value and unit_hint and raw_unit != unit_hint:
                source_has_value = raw_value in source_surface or raw_value.replace(",", "") in source_surface.replace(",", "")
                source_has_raw_unit = bool(raw_unit and raw_unit in source_surface)
                if source_has_value and not source_has_raw_unit:
                    coerced_unit = unit_hint
                else:
                    coerced_unit = self._coerce_operand_unit_from_evidence(
                        raw_value=raw_value,
                        raw_unit=raw_unit,
                        evidence_item=evidence_item,
                    )
            else:
                coerced_unit = self._coerce_operand_unit_from_evidence(
                    raw_value=raw_value,
                    raw_unit=raw_unit,
                    evidence_item=evidence_item,
                )
            if coerced_unit and coerced_unit != raw_unit:
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, coerced_unit)
                updated["raw_unit"] = coerced_unit
                if normalized_value is not None:
                    updated["normalized_value"] = normalized_value
                    updated["normalized_unit"] = normalized_unit
                if raw_value:
                    updated["rendered_value"] = f"{raw_value}{coerced_unit}"
            return updated

        def _lookup_result_from_slot(slot: Dict[str, Any], source_note: str) -> Dict[str, Any]:
            slot = _normalize_lookup_slot_unit(slot)
            rendered_value = _normalise_spaces(str(slot.get("rendered_value") or ""))
            label = _normalise_spaces(str(slot.get("label") or ""))
            clean_slot = {
                key: value
                for key, value in slot.items()
                if not str(key).startswith("_")
            }
            return {
                "status": "ok",
                "result_value": clean_slot.get("normalized_value"),
                "result_unit": clean_slot.get("raw_unit") or clean_slot.get("normalized_unit"),
                "rendered_value": rendered_value,
                "formatted_result": _normalise_spaces(f"{label} {rendered_value}") if label and rendered_value else rendered_value,
                "source_row_ids": list(clean_slot.get("source_row_ids") or []),
                "answer_slots": {
                    "metric_label": label,
                    "operation_family": "lookup",
                    "primary_value": clean_slot,
                    "source_row_ids": list(clean_slot.get("source_row_ids") or []),
                },
                "explanation": source_note,
            }

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
                matched_line_label = _normalise_spaces(str(slot.get("_matched_line_label") or ""))
                if not matched_line_label:
                    return False
                primary_keys = self._slot_metric_keys({"label": str(operand.get("label") or ""), "concept": ""})
                primary_keys.update(
                    key
                    for key in (
                        _normalise_spaces(str(operand.get("label") or "")),
                        _normalise_spaces(str(row.get("metric_label") or "")),
                        *[
                            _normalise_spaces(str(alias or ""))
                            for alias in (operand.get("aliases") or [])
                        ],
                    )
                    if key
                )
                primary_surfaces = [
                    _normalise_spaces(str(value or ""))
                    for value in (
                        operand.get("label"),
                        row.get("metric_label"),
                    )
                    if _normalise_spaces(str(value or ""))
                ]
                if any(
                    matched_line_label in surface or re.sub(r"\s+", "", matched_line_label) in re.sub(r"\s+", "", surface)
                    for surface in primary_surfaces
                ):
                    return True
                return matched_line_label in primary_keys

            if status == "ok":
                normalized_current_slot = _normalize_lookup_slot_unit(current_slot)
                unit_aligned_row: Optional[Dict[str, Any]] = None
                if (
                    _normalise_spaces(str(normalized_current_slot.get("raw_unit") or ""))
                    != _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                    or normalized_current_slot.get("normalized_value") != current_slot.get("normalized_value")
                ):
                    current_slot = normalized_current_slot
                    normalized_result = _lookup_result_from_slot(
                        current_slot,
                        "lookup result unit aligned from structured evidence metadata.",
                    )
                    unit_aligned_row = {
                        **dict(row),
                        "answer": str(normalized_result.get("formatted_result") or ""),
                        "calculation_result": normalized_result,
                        "answer_slots": normalized_result["answer_slots"],
                        "unit_aligned_from_evidence_metadata": True,
                    }
                current_evidence = self._evidence_item_for_operand_row(current_slot, evidence_by_id)
                current_score = (
                    self._direct_structured_lookup_evidence_score(operand, current_evidence)
                    if current_evidence
                    else 0.0
                )
                preferred_slot, preferred_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                    operand,
                    evidence_pool,
                    state=state,
                )
                if not preferred_slot or preferred_score <= current_score:
                    recovered_results.append(unit_aligned_row or row)
                    continue
                preferred_slot = _normalize_lookup_slot_unit(preferred_slot)
                preferred_raw = _normalise_spaces(str(preferred_slot.get("raw_value") or ""))
                current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
                preferred_unit = _normalise_spaces(str(preferred_slot.get("raw_unit") or ""))
                current_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
                preferred_normalized = preferred_slot.get("normalized_value")
                current_normalized = current_slot.get("normalized_value")
                try:
                    if preferred_normalized is not None and current_normalized is not None:
                        normalized_differs = abs(float(preferred_normalized) - float(current_normalized)) > 1e-6
                    else:
                        normalized_differs = preferred_normalized != current_normalized
                except (TypeError, ValueError):
                    normalized_differs = preferred_normalized != current_normalized
                if normalized_differs:
                    preferred_evidence = self._evidence_item_for_operand_row(preferred_slot, evidence_by_id)
                    if not _value_refinement_allowed(current_slot, preferred_slot, preferred_evidence):
                        recovered_results.append(unit_aligned_row or row)
                        continue
                if preferred_raw == current_raw and preferred_unit == current_unit and not normalized_differs:
                    recovered_results.append(unit_aligned_row or row)
                    continue
                preferred_result = _lookup_result_from_slot(
                    preferred_slot,
                    "lookup result replaced with stronger direct structured evidence.",
                )
                recovered_results.append(
                    {
                        **dict(row),
                        "answer": str(preferred_result.get("formatted_result") or ""),
                        "calculation_result": preferred_result,
                        "answer_slots": preferred_result["answer_slots"],
                        "recovered_from_sibling_table_evidence": True,
                    }
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
                    if self._lookup_direct_row_is_ambiguous_context_table(
                        recovered_slot,
                        evidence_item,
                        state=state,
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
        evidence_by_id = self._evidence_items_by_id(evidence_items)
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
            if not self._answer_slot_has_material(primary_slot):
                aligned_results.append(row)
                continue
            raw_value = _normalise_spaces(str(primary_slot.get("raw_value") or ""))
            raw_unit = _normalise_spaces(str(primary_slot.get("raw_unit") or ""))
            evidence_item = self._evidence_item_for_operand_row(primary_slot, evidence_by_id)
            if not raw_value or not evidence_item:
                aligned_results.append(row)
                continue
            coerced_unit = self._coerce_operand_unit_from_evidence(
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
            slot_has_material=self._answer_slot_has_material,
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

        _slot_differs_from_operand = _dependency_projection_slot_differs_from_operand
        _source_task_id_for_operand = _source_task_id_for_dependency_operand
        _ratio_role_group = _dependency_ratio_role_group
        _lookup_slot_match_score = _dependency_lookup_slot_match_score

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
            slot_has_material=self._answer_slot_has_material,
        )
        table_label_evidence_candidates = collect_table_label_evidence_candidates(ordered_results, state)
        _operand_from_source_slot = dependency_operand_from_source_slot
        _operand_from_answer_slot = dependency_operand_from_answer_slot
        _operand_rows_share_source_value = _dependency_operand_rows_share_source_value

        def _operand_from_table_label_evidence(operand: Dict[str, Any]) -> Dict[str, Any]:
            return dependency_operand_from_table_label_evidence(
                operand,
                table_label_evidence_candidates,
                lookup_value_from_table_label_metadata=self._lookup_value_from_table_label_metadata,
                slot_has_material=self._answer_slot_has_material,
            )

        def _recalculate_row_from_source_slots(row: Dict[str, Any]) -> Dict[str, Any]:
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
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

            derived_from_slots = False
            if not operands:
                operands = derive_dependency_operands_from_source_task_slots(
                    row,
                    active_subtask=active_subtask,
                    operation_family=operation_family,
                    task_id=task_id,
                    lookup_slots_by_task=lookup_slots_by_task,
                    slot_has_material=self._answer_slot_has_material,
                    lookup_source_for_arithmetic_slot=_lookup_source_for_arithmetic_slot,
                    operand_from_source_slot=_operand_from_source_slot,
                    operand_can_use_source_slot=_dependency_operand_can_use_source_slot,
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
                slot_has_material=self._answer_slot_has_material,
                lookup_source_for_arithmetic_slot=_lookup_source_for_arithmetic_slot,
                source_task_id_for_operand=_source_task_id_for_operand,
                slot_differs_from_operand=_slot_differs_from_operand,
                operand_can_use_source_slot=_dependency_operand_can_use_source_slot,
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
                    slot_has_material=self._answer_slot_has_material,
                    operand_can_use_source_slot=_dependency_operand_can_use_source_slot,
                    operand_from_source_slot=_operand_from_source_slot,
                    operand_from_table_label_evidence=_operand_from_table_label_evidence,
                    operand_rows_share_source_value=_operand_rows_share_source_value,
                    ratio_role_group=_ratio_role_group,
                    source_task_id_for_operand=_source_task_id_for_operand,
                )
                changed = changed or filled_any
                if operation_family == "ratio" and self._ratio_operand_rows_collapse_to_same_slot(updated_operands):
                    return row
            if not changed:
                return row

            calculation_plan = rebuild_dependency_calculation_plan(
                calculation_plan,
                state=state,
                active_subtask=active_subtask,
                updated_operands=updated_operands,
                operation_family=operation_family,
                calculation_result=dict(row.get("calculation_result") or {}),
                build_deterministic_operation_plan=self._build_deterministic_operation_plan,
            )
            if not calculation_plan:
                return row
            recalculation_state = build_dependency_recalculation_state(
                state,
                active_subtask=active_subtask,
                updated_operands=updated_operands,
                calculation_plan=calculation_plan,
                calculation_result=dict(row.get("calculation_result") or {}),
            )
            recalculated = self._execute_calculation(recalculation_state)
            recalculated_trace = _resolve_runtime_calculation_trace(
                recalculated,
                allow_legacy_top_level=False,
            )
            recalculated_result = dict(recalculated_trace.get("calculation_result") or {})
            if _normalise_spaces(str(recalculated_result.get("status") or "")).lower() != "ok":
                return row
            if operation_family == "ratio" and self._ratio_query_requests_absolute_magnitude(str(state.get("query") or "")):
                recalculated_result = apply_absolute_ratio_magnitude_if_requested(
                    recalculated_result,
                    format_calculation_value=self._format_calculation_value,
                )
            if operation_family == "ratio":
                formatted_answer = self._compact_ratio_answer(recalculation_state, recalculated_result)
            else:
                formatted_answer = _normalise_spaces(
                    str(recalculated_result.get("formatted_result") or recalculated_result.get("rendered_value") or "")
            )
            if formatted_answer:
                recalculated_result["formatted_result"] = formatted_answer
            return build_dependency_recalculated_row(
                row,
                recalculated_trace=recalculated_trace,
                updated_operands=updated_operands,
                calculation_plan=calculation_plan,
                recalculated_result=recalculated_result,
                formatted_answer=formatted_answer,
            )

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
                slot_has_material=self._answer_slot_has_material,
                projection_operand_matches_lookup=_projection_operand_matches_lookup,
                slot_differs_from_operand=_slot_differs_from_operand,
                build_operand_value_slot=self._build_operand_value_slot,
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
            for token in self._narrative_context_terms(str(query or ""))
            if len(token) >= 2
        }

        def _label_overlap_score(label_text: str) -> tuple[int, int]:
            normalized_label = _normalise_spaces(label_text)
            label_terms = {
                token.lower()
                for token in self._narrative_context_terms(normalized_label)
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
                answer = self._ratio_answer_from_dependency_source_slots(row, source_slot_by_task_id)
                if answer:
                    _append_ranked_answer(row, answer)
                continue
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
                continue
            if self._aggregate_result_dependency_coherence_ranks(row, source_slot_by_task_id)[0] == 0:
                if operation_family == "ratio":
                    answer = self._ratio_answer_from_dependency_source_slots(row, source_slot_by_task_id)
                    if answer:
                        _append_ranked_answer(row, answer)
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            if operation_family == "growth_rate":
                if self._growth_row_has_conflicting_periods(row):
                    continue
                answer = self._compose_complete_growth_numeric_answer(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if answer:
                    _append_ranked_answer(row, answer)
                    continue
            if operation_family == "ratio" and self._ratio_components_are_complete(calculation_result):
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
            if status != "ok" or self._material_gap_feedback_for_subtask_result(row):
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
                    self._ratio_components_are_complete(calculation_result)
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
        return all(self._answer_covers_numeric_answer(answer, target) for target in targets)

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
                1 for target in targets if self._answer_covers_numeric_answer(normalized_answer, target)
            )
            complete = int(covered_count == len(targets))
            no_missing_marker = int(
                not any(marker and marker in normalized_answer for marker in missing_markers)
            )
            numeric_count = len(self._answer_evidence_numeric_candidates(normalized_answer))
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
            best_candidate = self._aggregate_answer_candidate(
                answer,
                selected_claim_ids=artifact.get("evidence_refs") or [],
                sync_projection=True,
                sync_rendered_for_aggregate=True,
                status_ok=True,
            )
        return best_candidate

    def _aggregate_results_include_dependency_numeric_result(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        for row in ordered_results:
            operation_family = self._aggregate_result_operation_family(row)
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

    def _slot_display_from_source_task(
        self,
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
            if self._answer_slot_has_material(source_slot):
                return _normalise_spaces(
                    str(source_slot.get("rendered_value") or source_slot.get("raw_value") or "")
                )
        return ""

    def _source_task_display_compatible_with_slot(
        self,
        slot: Dict[str, Any],
        source_display: str,
    ) -> bool:
        display = _normalise_spaces(str(source_display or ""))
        if not display:
            return False
        slot_display = _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))
        if slot_display and display == slot_display:
            return True
        source_row_id = _normalise_spaces(str(slot.get("source_row_id") or ""))
        if source_row_id.startswith("task_output:"):
            return True
        raw_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
        if not raw_unit:
            return True
        if raw_unit in display:
            return True
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
        krw_normalized_unit = str(CALCULATION_RENDER_POLICY.get("krw_normalized_unit") or "").upper()
        if normalized_unit == krw_normalized_unit:
            krw_display_units = tuple(
                str(item)
                for item in (CALCULATION_RENDER_POLICY.get("krw_display_units") or ())
                if str(item)
            )
            if any(unit in display for unit in krw_display_units):
                return False
        return True

    def _growth_slot_display_value(
        self,
        slot: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> str:
        source_display = self._slot_display_from_source_task(slot, ordered_results)
        if source_display and self._source_task_display_compatible_with_slot(slot, source_display):
            return source_display
        return _normalise_spaces(str(slot.get("rendered_value") or slot.get("raw_value") or ""))

    def _growth_slots_share_material(
        self,
        current_slot: Dict[str, Any],
        prior_slot: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        current_display = self._growth_slot_display_value(current_slot, ordered_results)
        prior_display = self._growth_slot_display_value(prior_slot, ordered_results)
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

    def _recover_growth_prior_material_from_evidence(
        self,
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

    def _growth_required_display_values(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> List[str]:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        primary_slot = dict(answer_slots.get("primary_value") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        prior_display = self._growth_slot_display_value(prior_slot, ordered_results)
        if self._growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = self._recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_display = recovered_prior_material["display"]
        required_values = [
            self._growth_slot_display_value(current_slot, ordered_results),
            prior_display,
            _normalise_spaces(
                str(
                    calculation_result.get("rendered_value")
                    or self._growth_slot_display_value(primary_slot, ordered_results)
                    or ""
                )
            ),
        ]
        return list(dict.fromkeys(value for value in required_values if value))

    def _growth_uses_source_stated_result(self, row: Dict[str, Any]) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        if dict(calculation_result.get("derived_metrics") or {}).get("source_stated_result_used"):
            return True
        if _normalise_spaces(str(current_slot.get("stated_change_raw_value") or "")):
            return True
        operands = list(row.get("calculation_operands") or calculation_result.get("calculation_operands") or [])
        return any(
            str(operand.get("matched_operand_role") or operand.get("role") or "").strip() == "current_period"
            and _normalise_spaces(str(operand.get("stated_change_raw_value") or ""))
            for operand in operands
            if isinstance(operand, dict)
        )

    def _compose_complete_growth_numeric_answer(
        self,
        row: Dict[str, Any],
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        if self._aggregate_result_operation_family(row) != "growth_rate":
            return ""
        primary_slot = dict(answer_slots.get("primary_value") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        if not self._answer_slot_has_material(primary_slot):
            return ""

        growth_value = _normalise_spaces(str(calculation_result.get("rendered_value") or ""))
        if not growth_value:
            growth_value = _normalise_spaces(str(primary_slot.get("rendered_value") or primary_slot.get("raw_value") or ""))
        current_value = self._absolute_display_value(self._growth_slot_display_value(current_slot, ordered_results))
        prior_value = self._absolute_display_value(self._growth_slot_display_value(prior_slot, ordered_results))
        recovered_prior_period = ""
        if self._growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = self._recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_value = self._absolute_display_value(str(recovered_prior_material["display"]))
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
                topic_particle=_topic_particle(metric_label),
                current_value=current_value,
                prior_phrase=prior_phrase,
                growth_value=self._absolute_display_value(growth_value),
                direction_word=direction_word,
            )
        )

    def _growth_row_has_conflicting_periods(self, row: Dict[str, Any]) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        current_slot = dict(answer_slots.get("current_value") or {})
        prior_slot = dict(answer_slots.get("prior_value") or {})
        current_period = self._period_match_key(
            self._slot_period_hint(current_slot) or str(calculation_result.get("current_period") or "")
        )
        prior_period = self._period_match_key(
            self._slot_period_hint(prior_slot) or str(calculation_result.get("prior_period") or "")
        )
        if not (current_period and prior_period and current_period == prior_period):
            return False
        row_text = _normalise_spaces(
            " ".join(
                str(row.get(key) or "")
                for key in ("answer", "formatted_result", "rendered_value")
            )
        )
        result_text = _normalise_spaces(
            " ".join(
                str(calculation_result.get(key) or "")
                for key in ("formatted_result", "rendered_value")
            )
        )
        mentioned_periods = set(re.findall(r"20\d{2}", f"{row_text} {result_text}"))
        return len(mentioned_periods) < 2

    def _ensure_complete_growth_numeric_answer(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        for row in reversed(ordered_results):
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if not complete_answer:
                continue
            required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
            if (
                required_values
                and all(value in answer_text for value in required_values)
                and not self._growth_answer_has_untraced_numeric_sentence(
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
                if self._growth_sentence_has_untraced_material_numeric(
                    cleaned,
                    complete_answer,
                    required_values,
                    evidence_items,
                ):
                    continue
                extra_sentences.append(cleaned)
            return _normalise_spaces(" ".join([complete_answer, *extra_sentences]))
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
            if self._growth_row_has_conflicting_periods(row):
                continue
            if not self._growth_uses_source_stated_result(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if not complete_answer:
                continue
            required_values = self._growth_required_display_values(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if (
                required_values
                and all(value in answer_text for value in required_values)
                and not self._growth_answer_has_untraced_numeric_sentence(
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
                if self._growth_sentence_has_untraced_material_numeric(
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
            if self._row_is_narrative_summary(row):
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

    def _has_strong_growth_trace_for_answer_refresh(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            if not all(
                self._answer_slot_has_material(slot)
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
            self._has_strong_growth_trace_for_answer_refresh(ordered_results)
            and self._growth_answer_has_untraced_numeric_material(answer_text, ordered_results)
        ):
            return False
        return True

    def _growth_sentence_has_untraced_material_numeric(
        self,
        sentence: str,
        complete_answer: str,
        required_values: List[str],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        cleaned = _normalise_spaces(str(sentence or ""))
        if not cleaned:
            return False
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
                for candidate in self._evidence_numeric_display_candidates(evidence_items or [], evidence_surface)
                if str(candidate.get("text") or "").strip()
            )
        )
        allowed_surface = _normalise_spaces(
            " ".join([str(complete_answer or ""), *required_values, evidence_surface, evidence_display_surface])
        )
        if not allowed_surface:
            return False
        percent_pattern = str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or "")
        if percent_pattern:
            for match in re.finditer(percent_pattern, cleaned):
                token = _normalise_spaces(match.group(0))
                if token and token not in allowed_surface:
                    return True
        render_policy = dict(CALCULATION_RENDER_POLICY)
        unit_terms = [
            _normalise_spaces(str(unit))
            for unit in (render_policy.get("krw_display_units") or ())
            if _normalise_spaces(str(unit))
        ]
        for unit in unit_terms:
            pattern = rf"\d[\d,]*(?:\.\d+)?\s*{re.escape(unit)}"
            for match in re.finditer(pattern, cleaned):
                token = _normalise_spaces(match.group(0))
                if token and token not in allowed_surface:
                    return True
        return False

    def _strip_untraced_numeric_material_from_growth_narrative_sentence(
        self,
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
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(
                row,
                ordered_results,
                evidence_items=evidence_items,
            )
            if complete_answer:
                complete_answers.append(complete_answer)
            required_values.extend(
                self._growth_required_display_values(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
            )
        if not complete_answers and not required_values:
            return ""

        has_untraced_numeric = any(
            self._growth_sentence_has_untraced_material_numeric(
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
            self._growth_sentence_has_untraced_material_numeric(
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
            for term in self._narrative_context_terms(sanitized)
            if len(term) >= 3
        ]
        if len(narrative_terms) < 2:
            return ""
        if _narrative_sentence_looks_table_noisy(sanitized):
            return ""
        if _narrative_sentence_looks_abbreviated_fragment(sanitized, narrative_markers):
            return ""
        return sanitized

    def _growth_answer_has_untraced_numeric_sentence(
        self,
        answer: str,
        complete_answer: str,
        required_values: List[str],
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        complete_text = _normalise_spaces(str(complete_answer or ""))
        allowed_surface = _normalise_spaces(" ".join([complete_text, *required_values]))
        if not answer_text or not allowed_surface:
            return False
        number_pattern = re.compile(r"\d[\d,]*(?:\.\d+)?%?")
        for sentence in _split_narrative_sentences(answer_text):
            cleaned = _normalise_spaces(sentence)
            if not cleaned or cleaned in complete_text:
                continue
            if not any(value and value in cleaned for value in required_values):
                continue
            numeric_tokens = [match.group(0) for match in number_pattern.finditer(cleaned)]
            if any(token and token not in allowed_surface for token in numeric_tokens):
                return True
        return False

    def _growth_answer_has_untraced_numeric_material(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return False
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(row, ordered_results)
            required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
            if not complete_answer or not required_values:
                continue
            if self._growth_answer_has_untraced_numeric_sentence(answer_text, complete_answer, required_values):
                return True
            for sentence in _split_narrative_sentences(answer_text):
                if self._growth_sentence_has_untraced_material_numeric(
                    sentence,
                    complete_answer,
                    required_values,
                    evidence_items,
                ):
                    return True
        return False

    def _narrative_summary_conflicts_with_growth_trace(
        self,
        narrative_answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> bool:
        answer_text = _normalise_spaces(str(narrative_answer or ""))
        if not answer_text:
            return False
        percent_pattern = str(CALCULATION_NARRATIVE_POLICY.get("percent_display_pattern") or r"\d[\d,]*(?:\.\d+)?%")
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            complete_answer = self._compose_complete_growth_numeric_answer(row, ordered_results)
            required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
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
                    for candidate in self._evidence_numeric_display_candidates(evidence_items or [], evidence_surface)
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

    def _preferred_conflicting_growth_narrative_answer(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        missing_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ()))
        for row in ordered_results:
            if not self._row_is_narrative_summary(row):
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
            if not self._narrative_summary_conflicts_with_growth_trace(row_answer, ordered_results, evidence_items):
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

    def _aggregate_results_include_source_task_slot_realignment(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        for row in ordered_results:
            if not row.get("aligned_from_source_task_slots"):
                continue
            operation_family = self._aggregate_result_operation_family(row)
            if operation_family in {"ratio", "sum", "difference", "growth_rate"}:
                return True
        return False

    def _growth_narrative_numeric_incompatible_with_trace(
        self,
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
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            trace_surfaces.append(
                self._compose_complete_growth_numeric_answer(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
            )
            trace_surfaces.extend(
                self._growth_required_display_values(
                    row,
                    ordered_results,
                    evidence_items=evidence_items,
                )
            )
        trace_numeric_candidates = self._answer_evidence_numeric_candidates(
            _normalise_spaces(" ".join(surface for surface in trace_surfaces if surface))
        )
        narrative_numeric_candidates = self._answer_evidence_numeric_candidates(narrative_text)
        if not trace_numeric_candidates or not narrative_numeric_candidates:
            return False
        return not all(
            any(
                self._numeric_candidates_equivalent_for_evidence(narrative_candidate, trace_candidate)
                for trace_candidate in trace_numeric_candidates
            )
            for narrative_candidate in narrative_numeric_candidates
        )

    def _query_requests_explanatory_context(
        self,
        query: str,
    ) -> bool:
        text = _normalise_spaces(str(query or "")).lower()
        if not text:
            return False
        explanatory_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("explanatory_markers") or ()))
        return any(marker in text for marker in explanatory_markers)

    def _sentence_has_growth_explanatory_signal(self, sentence: str) -> bool:
        text = _normalise_spaces(str(sentence or ""))
        if not text:
            return False
        direction_words = {
            _normalise_spaces(str(value))
            for value in (CALCULATION_NARRATIVE_POLICY.get("direction_words") or {}).values()
            if _normalise_spaces(str(value))
        }
        markers = tuple(
            marker
            for marker in (
                str(item)
                for item in (
                    tuple(CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ())
                    + tuple(CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ())
                    + tuple(CALCULATION_NARRATIVE_POLICY.get("explanatory_markers") or ())
                )
            )
            if marker and marker not in direction_words
        )
        return any(marker in text for marker in markers)

    def _answer_reuses_narrative_summary_text(
        self,
        answer: str,
        ordered_results: List[Dict[str, Any]],
    ) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return False
        for row in ordered_results:
            if not self._row_is_narrative_summary(row):
                continue
            narrative_answer = _normalise_spaces(str(row.get("answer") or ""))
            if len(narrative_answer) < 20 or not re.search(r"\d", narrative_answer):
                continue
            if narrative_answer in answer_text or answer_text in narrative_answer:
                return True
        return False

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
                or self._answer_covers_narrative_context(answer, candidate_sentence)
                or _driver_group_already_covered(candidate_sentence)
            ):
                continue
            cleaned = self._strip_untraced_numeric_material_from_growth_narrative_sentence(
                candidate_sentence,
                ordered_results,
                evidence_items=evidence_items,
            )
            if (
                not cleaned
                or not self._sentence_has_growth_explanatory_signal(cleaned)
                or self._answer_covers_narrative_context(answer, cleaned)
                or self._growth_answer_has_untraced_numeric_material(cleaned, ordered_results, evidence_items)
            ):
                continue
            return {"sentence": cleaned, "selected_claim_ids": candidate_claim_ids}
        return {}

    def _preferred_complete_nested_numeric_narrative_answer(
        self,
        *,
        current_answer: str,
        ordered_results: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        current_text = _normalise_spaces(str(current_answer or ""))
        best_answer = ""
        best_rank: tuple[int, int, int, int] = (0, 0, 0, 0)
        for row in ordered_results:
            if self._aggregate_result_operation_family(row) != "aggregate_subtasks":
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            candidate = _normalise_spaces(
                str(
                    row.get("answer")
                    or calculation_result.get("formatted_result")
                    or calculation_result.get("rendered_value")
                    or ""
                )
            )
            if not candidate:
                continue
            candidate = self._preserve_evidence_numeric_display(candidate, evidence_items or [])
            if candidate == current_text:
                continue
            candidate_numeric_candidates = self._answer_evidence_numeric_candidates(candidate)
            if not candidate_numeric_candidates:
                continue
            if not self._answer_covers_numeric_projection(candidate, ordered_results):
                continue
            if self._growth_answer_has_untraced_numeric_material(
                candidate,
                ordered_results,
                evidence_items,
            ):
                continue
            if self._narrative_summary_conflicts_with_growth_trace(
                candidate,
                ordered_results,
                evidence_items,
            ):
                continue
            if current_text:
                current_terms = {
                    term.lower()
                    for term in self._narrative_context_terms(current_text)
                    if len(term) >= 2
                }
                candidate_terms = {
                    term.lower()
                    for term in self._narrative_context_terms(candidate)
                    if len(term) >= 2
                }
                if current_terms and not (current_terms & candidate_terms):
                    continue
            rank = (
                len(candidate_numeric_candidates),
                len(_split_narrative_sentences(candidate) or [candidate]),
                len(candidate),
                len(_clean_source_row_ids([row.get("source_row_ids"), calculation_result.get("source_row_ids")])),
            )
            if rank > best_rank:
                best_answer = candidate
                best_rank = rank
        return best_answer

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
        if not any(self._row_is_narrative_summary(row) for row in ordered_results) and not (
            current_answer_text and self._query_requests_explanatory_context(query)
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

        conflicting_narrative = self._preferred_conflicting_growth_narrative_answer(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        )
        if conflicting_narrative:
            conflicting_answer = _normalise_spaces(str(conflicting_narrative.get("answer") or ""))
            if self._growth_narrative_numeric_incompatible_with_trace(
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
                    self._strip_untraced_numeric_material_from_growth_narrative_sentence(
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
                combined_answer = self._ensure_complete_growth_numeric_answer(
                    _normalise_spaces(" ".join([numeric_text, *conflicting_parts])),
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if not self._growth_answer_has_untraced_numeric_material(
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

        candidate_answer = self._ensure_complete_growth_numeric_answer(
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
            not self._growth_answer_has_untraced_numeric_material(candidate_answer, ordered_results, evidence_items)
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
                self._answer_covers_narrative_context(sentence, candidate)
                or self._answer_covers_narrative_context(candidate, sentence)
                for candidate in supported_context_candidates
            )

        for sentence in _split_narrative_sentences(candidate_answer) or [candidate_answer]:
            cleaned_sentence = _normalise_spaces(sentence)
            if not cleaned_sentence or cleaned_sentence in numeric_text:
                continue
            if self._answer_evidence_numeric_candidates(cleaned_sentence):
                continue
            if not (
                _has_explanatory_signal(cleaned_sentence)
                or self._query_requests_explanatory_context(query_text)
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
            if not self._row_is_narrative_summary(row):
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
                if self._answer_evidence_numeric_candidates(candidate_sentence) and not _has_explanatory_signal(
                    candidate_sentence
                ):
                    continue
                sanitized_sentence = self._strip_untraced_numeric_material_from_growth_narrative_sentence(
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
                row_combined_answer = self._ensure_complete_growth_numeric_answer(
                    _normalise_spaces(" ".join([numeric_text, *row_narrative_parts])),
                    ordered_results,
                    evidence_items=evidence_items,
                )
                if not self._growth_answer_has_untraced_numeric_material(
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
        if self._growth_answer_has_untraced_numeric_material(
            composed_answer,
            ordered_results,
            evidence_items,
        ):
            composed_answer = self._ensure_complete_growth_numeric_answer(
                composed_answer,
                ordered_results,
                evidence_items=evidence_items,
            )
        if composed_answer and self._answer_satisfies_growth_narrative_intent(
            query=query_text,
            answer=composed_answer,
            ordered_results=ordered_results,
            evidence_items=evidence_items,
        ) and not self._growth_answer_has_untraced_numeric_material(
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
            if self._answer_evidence_numeric_candidates(candidate_sentence) and not _has_explanatory_signal(
                candidate_sentence
            ):
                continue
            sanitized_sentence = self._strip_untraced_numeric_material_from_growth_narrative_sentence(
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
                if not self._row_is_narrative_summary(row):
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
                    if self._answer_evidence_numeric_candidates(candidate_sentence) and not _has_explanatory_signal(
                        candidate_sentence
                    ):
                        continue
                    sanitized_sentence = self._strip_untraced_numeric_material_from_growth_narrative_sentence(
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
            combined_answer = self._ensure_complete_growth_numeric_answer(
                raw_combined_answer,
                ordered_results,
                evidence_items=evidence_items,
            )
            for candidate_combined_answer in (raw_combined_answer, combined_answer):
                if not candidate_combined_answer:
                    continue
                if self._growth_answer_has_untraced_numeric_material(
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
            if self._query_requests_explanatory_context(query_text):
                if self._growth_answer_has_untraced_numeric_material(
                    combined_answer,
                    ordered_results,
                    evidence_items,
                ):
                    clean_numeric = self._ensure_complete_growth_numeric_answer(
                        numeric_text,
                        ordered_results,
                        evidence_items=evidence_items,
                    )
                    return {"answer": clean_numeric or numeric_text, "selected_claim_ids": []}
                return {
                    "answer": combined_answer,
                    "selected_claim_ids": list(dict.fromkeys(selected_claim_ids)),
                }

        if self._growth_answer_has_untraced_numeric_material(numeric_text, ordered_results, evidence_items):
            clean_numeric = self._ensure_complete_growth_numeric_answer(
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
            safe_answer = self._safe_partial_answer_for_numeric_gap(ordered_results)
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

        has_narrative_summary = any(self._row_is_narrative_summary(row) for row in ordered_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        if complete_numeric_answer and (
            has_narrative_summary
            or self._aggregate_results_include_dependency_numeric_result(ordered_results)
        ):
            return complete_numeric_answer

        for row in ordered_results:
            if not self._row_is_narrative_summary(row):
                continue
            sibling_answer = _normalise_spaces(str(row.get("answer") or ""))
            if sibling_answer and re.search(r"\d", sibling_answer):
                return sibling_answer
        return default_answer

    def _answer_evidence_numeric_candidates(self, text: str) -> List[Dict[str, Any]]:
        return extract_numeric_surface_candidates(text)

    def _sync_aggregate_projection_final_answer(
        self,
        aggregate_projection: Dict[str, Any],
        final_answer: str,
        *,
        sync_rendered_for_aggregate: bool = True,
        status_ok: bool = False,
    ) -> Dict[str, Any]:
        if not final_answer:
            return aggregate_projection
        calculation_result = aggregate_projection.setdefault("calculation_result", {})
        calculation_result["formatted_result"] = final_answer
        if (
            sync_rendered_for_aggregate
            and str((aggregate_projection.get("calculation_plan") or {}).get("mode") or "") == "aggregate_subtasks"
        ):
            calculation_result["rendered_value"] = final_answer
        if status_ok:
            calculation_result["status"] = "ok"
        return aggregate_projection

    def _answer_sentence_for_projection_subtask_row(
        self,
        final_answer: str,
        row: Dict[str, Any],
    ) -> str:
        final_answer = _normalise_spaces(final_answer)
        if not final_answer:
            return ""
        row_label = _normalise_spaces(str(row.get("metric_label") or "")).lower()
        operation_family = self._aggregate_result_operation_family(row)
        sentences = _split_narrative_sentences(final_answer) or [final_answer]

        def _score(sentence: str) -> tuple[int, int, int, int]:
            normalized = _normalise_spaces(sentence)
            if not normalized or not self._answer_evidence_numeric_candidates(normalized):
                return (0, 0, 0, 0)
            lower = normalized.lower()
            label_score = int(bool(row_label and row_label in lower))
            percent_score = int(operation_family in {"ratio", "growth_rate"} and "%" in normalized)
            conflict_score = int(self._subtask_numeric_answers_conflict({"answer": normalized}, row))
            return (label_score, percent_score, conflict_score, len(normalized))

        best_sentence = max(sentences, key=_score, default="")
        return _normalise_spaces(best_sentence) if _score(best_sentence)[:3] != (0, 0, 0) else ""

    def _rendered_value_from_answer_sentence(
        self,
        answer_sentence: str,
        operation_family: str,
    ) -> str:
        sentence = _normalise_spaces(answer_sentence)
        if not sentence:
            return ""
        if operation_family in {"ratio", "growth_rate"}:
            match = re.search(r"[\(\)\-+]?\d[\d,]*(?:\.\d+)?\s*%p?", sentence)
            return _normalise_spaces(match.group(0)) if match else ""
        candidates = self._answer_evidence_numeric_candidates(sentence)
        if not candidates:
            return ""
        return _normalise_spaces(str(candidates[0].get("surface") or ""))

    def _with_synced_projection_row_surface(
        self,
        row: Dict[str, Any],
        *,
        answer: str,
        rendered_value: str,
    ) -> Dict[str, Any]:
        updated = {
            **dict(row),
            "answer": answer,
            "projection_surface_synced_from_final_answer": True,
        }
        if rendered_value:
            updated["rendered_value"] = rendered_value

        calculation_result = dict(row.get("calculation_result") or {})
        if not calculation_result:
            return updated
        calculation_result["formatted_result"] = answer
        if rendered_value:
            calculation_result["rendered_value"] = rendered_value
            answer_slots = dict(calculation_result.get("answer_slots") or {})
            primary_value = dict(answer_slots.get("primary_value") or {})
            if primary_value:
                primary_value["rendered_value"] = rendered_value
                answer_slots["primary_value"] = primary_value
                calculation_result["answer_slots"] = answer_slots
        updated["calculation_result"] = calculation_result
        return updated

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
            if operation_family not in arithmetic_families:
                continue
            if planned_arithmetic_task_ids and task_id not in planned_arithmetic_task_ids:
                continue
            row_surface = _normalise_spaces(
                str(
                    row.get("answer")
                    or (row.get("calculation_result") or {}).get("formatted_result")
                    or (row.get("calculation_result") or {}).get("rendered_value")
                    or ""
                )
            )
            if not row_surface or not self._subtask_numeric_answers_conflict({"answer": final_answer}, row):
                continue
            if self._answer_covers_numeric_answer(final_answer, row_surface):
                continue
            candidate_indexes.append(index)
        if len(candidate_indexes) != 1:
            return ordered_results, aggregate_projection

        target_index = candidate_indexes[0]
        target_row = projection_rows[target_index]
        synced_answer = self._answer_sentence_for_projection_subtask_row(final_answer, target_row)
        if not synced_answer:
            return ordered_results, aggregate_projection
        operation_family = self._aggregate_result_operation_family(target_row)
        rendered_value = self._rendered_value_from_answer_sentence(synced_answer, operation_family)
        updated_row = self._with_synced_projection_row_surface(
            target_row,
            answer=synced_answer,
            rendered_value=rendered_value,
        )
        projection_rows[target_index] = updated_row

        target_task_id = _normalise_spaces(str(updated_row.get("task_id") or ""))
        ordered_results = [
            dict(updated_row) if _normalise_spaces(str(row.get("task_id") or "")) == target_task_id else dict(row)
            for row in ordered_results
        ]
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        slot_rows = [dict(row) for row in list(answer_slots.get("subtask_results") or []) if isinstance(row, dict)]
        if slot_rows:
            answer_slots["subtask_results"] = [
                self._with_synced_projection_row_surface(
                    row,
                    answer=synced_answer,
                    rendered_value=rendered_value,
                )
                if _normalise_spaces(str(row.get("task_id") or "")) == target_task_id
                else row
                for row in slot_rows
            ]
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
        projection = self._build_aggregate_calculation_projection(ordered_results, final_answer)
        if kept_evidence_ids is not None:
            projection = self._filter_aggregate_projection_provenance(projection, kept_evidence_ids)
        return projection

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
        if operation != "ratio" or not self._ratio_components_are_complete(result):
            return ""
        trace_operands = list(operands if operands is not None else aggregate_projection.get("calculation_operands") or [])
        ordered_results = [
            dict(row)
            for row in list(result.get("subtask_results") or state.get("subtask_results") or [])
            if isinstance(row, dict)
        ]
        if (
            self._aggregate_dependency_slot_coherence_rank_for_operands(
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

    def _aggregate_answer_candidate(
        self,
        answer: str,
        *,
        selected_claim_ids: Optional[Sequence[Any]] = None,
        sync_projection: bool = True,
        sync_rendered_for_aggregate: bool = True,
        status_ok: bool = False,
    ) -> Dict[str, Any]:
        return {
            "answer": _normalise_spaces(str(answer or "")),
            "selected_claim_ids": [
                str(claim_id).strip()
                for claim_id in (selected_claim_ids or [])
                if str(claim_id).strip()
            ],
            "sync_projection": bool(sync_projection),
            "sync_rendered_for_aggregate": bool(sync_rendered_for_aggregate),
            "status_ok": bool(status_ok),
        }

    def _aggregate_answer_candidate_from_refresh(
        self,
        refreshed_answer: Dict[str, Any],
        fallback_answer: str,
        *,
        sync_projection: bool = True,
        sync_rendered_for_aggregate: bool = True,
        status_ok: bool = False,
    ) -> Dict[str, Any]:
        payload = dict(refreshed_answer or {})
        return self._aggregate_answer_candidate(
            str(payload.get("answer") or fallback_answer or ""),
            selected_claim_ids=payload.get("selected_claim_ids") or [],
            sync_projection=sync_projection,
            sync_rendered_for_aggregate=sync_rendered_for_aggregate,
            status_ok=status_ok,
        )

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
        return self._aggregate_answer_candidate_from_refresh(
            refreshed_answer,
            numeric_answer,
            sync_projection=sync_projection,
            sync_rendered_for_aggregate=sync_rendered_for_aggregate,
            status_ok=status_ok,
        )

    def _apply_aggregate_answer_candidate(
        self,
        aggregate_projection: Dict[str, Any],
        selected_claim_ids: List[str],
        candidate: Dict[str, Any],
    ) -> tuple[Dict[str, Any], str, List[str]]:
        final_answer = _normalise_spaces(str((candidate or {}).get("answer") or ""))
        if bool((candidate or {}).get("sync_projection", True)):
            aggregate_projection = self._sync_aggregate_projection_final_answer(
                aggregate_projection,
                final_answer,
                sync_rendered_for_aggregate=bool(
                    (candidate or {}).get("sync_rendered_for_aggregate", True)
                ),
                status_ok=bool((candidate or {}).get("status_ok", False)),
            )
        merged_claim_ids = list(
            dict.fromkeys(
                [
                    *[str(claim_id).strip() for claim_id in (selected_claim_ids or []) if str(claim_id).strip()],
                    *[
                        str(claim_id).strip()
                        for claim_id in ((candidate or {}).get("selected_claim_ids") or [])
                        if str(claim_id).strip()
                    ],
                ]
            )
        )
        return aggregate_projection, final_answer, merged_claim_ids

    def _apply_aggregate_composition_answer(
        self,
        composition_state: _AggregateCompositionState,
        *,
        answer: str = "",
        selected_claim_ids: Optional[Sequence[Any]] = None,
        calculation_projection_override: Optional[Dict[str, Any]] = None,
        reset_projection_override: bool = False,
        narrative_answer_locked: Optional[bool] = None,
        clear_feedback: bool = True,
    ) -> _AggregateCompositionState:
        final_answer = _normalise_spaces(answer) or composition_state.final_answer
        merged_claim_ids = list(
            dict.fromkeys(
                [
                    *[
                        str(claim_id).strip()
                        for claim_id in (composition_state.selected_claim_ids or [])
                        if str(claim_id).strip()
                    ],
                    *[
                        str(claim_id).strip()
                        for claim_id in (selected_claim_ids or [])
                        if str(claim_id).strip()
                    ],
                ]
            )
        )
        projection_override = composition_state.calculation_projection_override
        if reset_projection_override:
            projection_override = None
        elif isinstance(calculation_projection_override, dict):
            projection_override = calculation_projection_override
        locked = (
            composition_state.narrative_answer_locked
            if narrative_answer_locked is None
            else bool(narrative_answer_locked)
        )
        return _AggregateCompositionState(
            final_answer=final_answer,
            selected_claim_ids=merged_claim_ids,
            calculation_projection_override=projection_override,
            narrative_answer_locked=locked,
            planner_feedback="" if clear_feedback else composition_state.planner_feedback,
            deterministic_feedback="" if clear_feedback else composition_state.deterministic_feedback,
        )

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
    ) -> tuple[_AggregateCompositionState, str]:
        if (
            deterministic_feedback
            and self._unresolved_structured_numeric_gap(ordered_results)
            and self._answer_reuses_narrative_summary_text(final_answer, ordered_results)
        ):
            safe_partial_answer = self._safe_partial_answer_for_numeric_gap(ordered_results)
            final_answer = safe_partial_answer or ""
        final_answer = self._coerce_sign_aware_subtraction_answer(
            final_answer,
            calculation_result=dict(preliminary_projection.get("calculation_result") or {}),
            subtask_results=ordered_results,
        )
        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(preliminary_projection.get("calculation_result") or {}),
        )
        if slot_based_difference_answer:
            final_answer = slot_based_difference_answer
            complete_numeric_answer = slot_based_difference_answer
            planner_feedback = ""
            deterministic_feedback = ""
        if has_narrative_summary and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results):
            final_answer = self._ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
        if not deterministic_feedback:
            final_answer = self._include_narrative_context_if_needed(
                final_answer,
                query=str(state.get("query") or ""),
                narrative_context=narrative_context,
            )

        composition_state = _AggregateCompositionState(
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
            composition_state = self._apply_aggregate_composition_answer(
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
            composition_state = self._apply_aggregate_composition_answer(
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
            composition_state = self._apply_aggregate_composition_answer(
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
            composition_state = self._apply_aggregate_composition_answer(
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
            composition_state = self._apply_aggregate_composition_answer(
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
        if not self._answer_satisfies_growth_narrative_intent(
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
            composition_state = _AggregateCompositionState(
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
        aggregate_projection, final_answer, selected_claim_ids = self._apply_aggregate_answer_candidate(
            aggregate_state.aggregate_projection,
            aggregate_state.selected_claim_ids,
            self._refresh_numeric_aggregate_answer_candidate(
                query=str(state.get("query") or ""),
                current_answer=aggregate_state.final_answer,
                numeric_answer=numeric_answer,
                ordered_results=aggregate_state.ordered_results,
                evidence_items=evidence_items,
                sync_projection=sync_projection,
            ),
        )
        return _AggregateSynthesisState(
            aggregate_state.ordered_results,
            aggregate_projection,
            final_answer,
            selected_claim_ids,
        )

    def _replace_aggregate_final_answer(
        self,
        *,
        aggregate_state: _AggregateSynthesisState,
        evidence_items: List[Dict[str, Any]],
        candidate_answer: str,
        sync_rendered_for_aggregate: bool = True,
        status_ok: bool = False,
        force: bool = False,
        refresh_operand_evidence: bool = False,
    ) -> tuple[_AggregateSynthesisState, List[Dict[str, Any]], bool]:
        candidate_answer = _normalise_spaces(candidate_answer)
        if candidate_answer == aggregate_state.final_answer and not force:
            return aggregate_state, evidence_items, False
        aggregate_projection = self._sync_aggregate_projection_final_answer(
            aggregate_state.aggregate_projection,
            candidate_answer,
            sync_rendered_for_aggregate=sync_rendered_for_aggregate,
            status_ok=status_ok,
        )
        if refresh_operand_evidence:
            evidence_items = self._append_operand_evidence_for_final_answer(
                evidence_items,
                operands=list(aggregate_projection.get("calculation_operands") or []),
                final_answer=candidate_answer,
            )
        return (
            _AggregateSynthesisState(
                aggregate_state.ordered_results,
                aggregate_projection,
                candidate_answer,
                aggregate_state.selected_claim_ids,
            ),
            evidence_items,
            True,
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
        synthesis_state, evidence_items, changed = self._replace_aggregate_final_answer(
            aggregate_state=mutable_state.synthesis_state,
            evidence_items=mutable_state.evidence_items,
            candidate_answer=candidate_answer,
            sync_rendered_for_aggregate=sync_rendered_for_aggregate,
            status_ok=status_ok,
            force=force,
            refresh_operand_evidence=refresh_operand_evidence,
        )
        return _AggregateMutableState(synthesis_state, evidence_items), changed

    def _sync_mutable_aggregate_state(
        self,
        mutable_state: _AggregateMutableState,
        *,
        ordered_results: Optional[List[Dict[str, Any]]] = None,
        aggregate_projection: Optional[Dict[str, Any]] = None,
        final_answer: Optional[str] = None,
        selected_claim_ids: Optional[List[str]] = None,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> _AggregateMutableState:
        synthesis_state = mutable_state.synthesis_state._replace(
            ordered_results=mutable_state.ordered_results if ordered_results is None else ordered_results,
            aggregate_projection=mutable_state.aggregate_projection
            if aggregate_projection is None
            else aggregate_projection,
            final_answer=mutable_state.final_answer if final_answer is None else final_answer,
            selected_claim_ids=mutable_state.selected_claim_ids
            if selected_claim_ids is None
            else selected_claim_ids,
        )
        return _AggregateMutableState(
            synthesis_state,
            mutable_state.evidence_items if evidence_items is None else evidence_items,
        )

    def _replace_aggregate_results(
        self,
        aggregate_state: _AggregateSynthesisState,
        state: FinancialAgentState,
        ordered_results: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        *,
        refresh_numeric_answer: bool = False,
        sync_projection: bool = False,
        rebuild_after_numeric_refresh: bool = True,
        kept_evidence_ids: Optional[set[str]] = None,
    ) -> _AggregateSynthesisState:
        aggregate_state = aggregate_state._replace(
            ordered_results=ordered_results,
            aggregate_projection=self._rebuild_aggregate_projection(
                ordered_results, aggregate_state.final_answer, kept_evidence_ids=kept_evidence_ids
            ),
        )
        if not refresh_numeric_answer:
            return aggregate_state
        numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        if not (numeric_answer and self._complete_numeric_answer_can_replace_final(numeric_answer, ordered_results)):
            return aggregate_state
        aggregate_state = self._apply_numeric_answer_to_aggregate_state(
            aggregate_state=aggregate_state,
            state=state,
            numeric_answer=numeric_answer,
            evidence_items=evidence_items,
            sync_projection=sync_projection,
        )
        if rebuild_after_numeric_refresh:
            aggregate_state = aggregate_state._replace(
                aggregate_projection=self._rebuild_aggregate_projection(
                    aggregate_state.ordered_results, aggregate_state.final_answer, kept_evidence_ids=kept_evidence_ids
                )
            )
        return aggregate_state

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
        synthesis_state = self._replace_aggregate_results(
            mutable_state.synthesis_state,
            state,
            ordered_results,
            mutable_state.evidence_items,
            refresh_numeric_answer=refresh_numeric_answer,
            sync_projection=sync_projection,
            rebuild_after_numeric_refresh=rebuild_after_numeric_refresh,
            kept_evidence_ids=kept_evidence_ids,
        )
        return mutable_state._replace(synthesis_state=synthesis_state)

    def _apply_mutable_numeric_answer(
        self,
        mutable_state: _AggregateMutableState,
        state: FinancialAgentState,
        numeric_answer: str,
        *,
        sync_projection: bool = False,
    ) -> _AggregateMutableState:
        synthesis_state = self._apply_numeric_answer_to_aggregate_state(
            aggregate_state=mutable_state.synthesis_state,
            state=state,
            numeric_answer=numeric_answer,
            evidence_items=mutable_state.evidence_items,
            sync_projection=sync_projection,
        )
        return mutable_state._replace(synthesis_state=synthesis_state)

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
            mutable_state = self._sync_mutable_aggregate_state(mutable_state, **updates)
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
        aggregate_evidence_items = self._append_operand_evidence_for_final_answer(
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
            selected_claim_ids = list(dict.fromkeys([*selected_claim_ids, *retrieved_narrative_claim_ids]))
            _sync_state(selected_claim_ids=selected_claim_ids)
        aggregate_state = self._apply_period_context_realignment_to_aggregate(
            aggregate_state=mutable_state.synthesis_state,
            state=state,
            evidence_items=aggregate_evidence_items,
        )
        mutable_state = mutable_state._replace(synthesis_state=aggregate_state)
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
                aggregate_projection, final_answer, selected_claim_ids = self._apply_aggregate_answer_candidate(
                    aggregate_projection,
                    selected_claim_ids,
                    self._aggregate_answer_candidate(
                        repaired_answer,
                        selected_claim_ids=(repaired_growth_narrative_answer or {}).get("selected_claim_ids") or [],
                    ),
                )
                aggregate_evidence_items = self._append_operand_evidence_for_final_answer(
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
        source_surface_answer = self._preserve_retrieved_narrative_source_surface(
            final_answer,
            aggregate_evidence_items,
        )
        _apply_candidate(source_surface_answer)
        unresolved_numeric_gap = self._unresolved_structured_numeric_gap(ordered_results)
        blocked_narrative_numeric_gap = bool(
            unresolved_numeric_gap
            and self._answer_reuses_narrative_summary_text(final_answer, ordered_results)
        )
        if blocked_narrative_numeric_gap:
            safe_partial_answer = self._safe_partial_answer_for_numeric_gap(ordered_results)
            if safe_partial_answer:
                _apply_candidate(safe_partial_answer)
        if (
            final_answer
            and has_narrative_summary
            and has_growth_rate_result
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
        ):
            numeric_preserved_answer = self._ensure_complete_growth_numeric_answer(
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
        has_growth_narrative_intent = has_narrative_summary or self._query_requests_explanatory_context(
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
            if self._query_requests_explanatory_context(str(state.get("query") or "")):
                appended_explanation = False
                for row in ordered_results:
                    if not self._row_is_narrative_summary(row):
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
                        cleaned = self._strip_untraced_numeric_material_from_growth_narrative_sentence(
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

    def _sync_aggregate_artifact_projection_payload(
        self,
        artifacts: List[Dict[str, Any]],
        *,
        artifact_id: str,
        final_answer: str,
        aggregate_projection: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        updated_artifacts = [dict(item) for item in (artifacts or [])]
        for index, artifact in enumerate(updated_artifacts):
            if str((artifact or {}).get("artifact_id") or "") != artifact_id:
                continue
            payload = dict((artifact or {}).get("payload") or {})
            payload.update(
                {
                    "final_answer": final_answer,
                    "calculation_operands": list(aggregate_projection.get("calculation_operands") or []),
                    "calculation_plan": dict(aggregate_projection.get("calculation_plan") or {}),
                    "calculation_result": dict(aggregate_projection.get("calculation_result") or {}),
                }
            )
            updated_artifacts[index] = {
                **dict(artifact),
                "summary": final_answer[:200],
                "payload": payload,
            }
            break
        return updated_artifacts

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
            or not self._ratio_components_are_complete(projection_result)
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
            updated_artifacts = self._sync_aggregate_artifact_projection_payload(
                updated_artifacts,
                artifact_id=artifact_id,
                final_answer=final_answer,
                aggregate_projection=aggregate_projection,
            )
        return aggregate_projection, final_answer, updated_artifacts

    def _repair_stale_aggregate_projection_result(
        self,
        state: FinancialAgentState,
        aggregate_projection: Dict[str, Any],
    ) -> tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        aggregate_projection = {
            **dict(aggregate_projection),
            "calculation_operands": [
                dict(row)
                for row in list(aggregate_projection.get("calculation_operands") or [])
                if isinstance(row, dict)
            ],
            "calculation_plan": dict(aggregate_projection.get("calculation_plan") or {}),
            "calculation_result": dict(aggregate_projection.get("calculation_result") or {}),
        }
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
        operands, plan, repaired_result = self._repair_stale_calculation_result_from_operands(
            repair_state,
            operands=[dict(row) for row in list(aggregate_projection.get("calculation_operands") or [])],
            plan=dict(aggregate_projection.get("calculation_plan") or {}),
            calculation_result=calculation_result,
        )
        if repaired_result.get("stale_result_repaired_from_operands"):
            aggregate_projection["calculation_operands"] = operands
            aggregate_projection["calculation_plan"] = plan
            aggregate_projection["calculation_result"] = repaired_result
        return aggregate_projection, operands, plan, repaired_result

    def _apply_stale_projection_repair_to_aggregate_state(
        self,
        *,
        state: FinancialAgentState,
        aggregate_state: _AggregateSynthesisState,
        evidence_items: List[Dict[str, Any]],
        prefer_compact_ratio_answer: bool = False,
    ) -> _AggregateSynthesisState:
        aggregate_projection, repaired_operands, repaired_plan, repaired_result = (
            self._repair_stale_aggregate_projection_result(
                state,
                aggregate_state.aggregate_projection,
            )
        )
        if not repaired_result.get("stale_result_repaired_from_operands"):
            return aggregate_state._replace(aggregate_projection=aggregate_projection)
        if (
            self._aggregate_dependency_slot_coherence_rank_for_operands(
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
            aggregate_projection["calculation_result"] = {
                **repaired_result,
                "formatted_result": repaired_answer,
            }
            return aggregate_state._replace(
                aggregate_projection=aggregate_projection,
                final_answer=repaired_answer,
            )
        if not repaired_answer:
            return aggregate_state._replace(aggregate_projection=aggregate_projection)
        return self._apply_numeric_answer_to_aggregate_state(
            aggregate_state=aggregate_state._replace(aggregate_projection=aggregate_projection),
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
            and self._ratio_components_collapse_to_same_slot(dict(row.get("calculation_result") or {}))
            for row in ordered_results
        )
        if (
            not has_invalid_self_ratio_row
            or runtime_operation != "ratio"
            or not self._ratio_components_are_complete(runtime_result)
        ):
            return aggregate_projection, final_answer

        runtime_result = dict(runtime_result)
        runtime_slots = dict(runtime_slots)
        runtime_primary = dict(runtime_slots.get("primary_value") or {})
        if self._ratio_query_requests_absolute_magnitude(str(state.get("query") or "")):
            try:
                runtime_value = runtime_result.get("result_value")
                if runtime_value is not None and float(runtime_value) < 0:
                    absolute_value = abs(float(runtime_value))
                    runtime_result["result_value"] = absolute_value
                    runtime_primary["normalized_value"] = absolute_value
                    runtime_primary["normalized_unit"] = runtime_primary.get("normalized_unit") or "PERCENT"
                    runtime_primary["raw_unit"] = runtime_primary.get("raw_unit") or runtime_result.get("result_unit") or "%"
                    runtime_rendered = self._format_calculation_value(
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

        runtime_operands = list(runtime_trace.get("calculation_operands") or [])
        if (
            self._aggregate_dependency_slot_coherence_rank_for_operands(
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
        filtered_evidence_items = self._filter_aggregate_evidence_for_final_answer(
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
        aggregate_projection = self._filter_aggregate_projection_provenance(
            aggregate_projection,
            kept_evidence_ids,
        )
        return filtered_evidence_items, aggregate_projection, selected_claim_ids, kept_evidence_ids

    def _preserve_evidence_numeric_display(
        self,
        answer: str,
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not evidence_items:
            return answer_text
        evidence_surface = _normalise_spaces(
            " ".join(self._evidence_text_for_final_support(item) for item in evidence_items if isinstance(item, dict))
        )
        if not evidence_surface:
            return answer_text
        answer_candidates = self._answer_evidence_numeric_candidates(answer_text)
        evidence_candidates = self._evidence_numeric_display_candidates(evidence_items, evidence_surface)
        if not answer_candidates or not evidence_candidates:
            return answer_text
        replacements: List[tuple[int, int, str]] = []
        for answer_candidate in answer_candidates:
            if str(answer_candidate.get("kind") or "") != "currency":
                continue
            candidate_text = _normalise_spaces(str(answer_candidate.get("text") or ""))
            span = answer_candidate.get("span")
            if not candidate_text or not isinstance(span, tuple) or len(span) != 2:
                continue
            supported_displays = [
                evidence_candidate
                for evidence_candidate in evidence_candidates
                if str(evidence_candidate.get("kind") or "") == "currency"
                and _normalise_spaces(str(evidence_candidate.get("text") or ""))
                and self._numeric_candidates_equivalent_for_evidence(answer_candidate, evidence_candidate)
            ]
            if not supported_displays:
                continue
            supported_displays.sort(
                key=lambda item: (
                    float(item.get("display_step") or 1.0),
                    -len(_normalise_spaces(str(item.get("text") or ""))),
                )
            )
            replacement = _normalise_spaces(str(supported_displays[0].get("text") or ""))
            candidate_in_evidence = candidate_text in evidence_surface
            if candidate_in_evidence:
                try:
                    if float(supported_displays[0].get("display_step") or 1.0) >= float(
                        answer_candidate.get("display_step") or 1.0
                    ):
                        continue
                except (TypeError, ValueError):
                    continue
            if replacement and replacement != candidate_text:
                if candidate_text.startswith("(") and int(span[1]) < len(answer_text) and answer_text[int(span[1])] == ")":
                    replacement = f"({replacement}"
                replacements.append((int(span[0]), int(span[1]), replacement))
        if not replacements:
            return answer_text
        updated = answer_text
        for start, end, replacement in sorted(replacements, reverse=True):
            updated = f"{updated[:start]}{replacement}{updated[end:]}"
        return _normalise_spaces(updated)

    def _evidence_numeric_display_candidates(
        self,
        evidence_items: List[Dict[str, Any]],
        evidence_surface: str,
    ) -> List[Dict[str, Any]]:
        return evidence_numeric_display_candidates(evidence_items, evidence_surface)

    def _numeric_candidates_equivalent_for_evidence(
        self,
        left: Dict[str, Any],
        right: Dict[str, Any],
    ) -> bool:
        return numeric_surface_candidates_equivalent(left, right)

    def _answer_covers_numeric_answer(
        self,
        answer: str,
        numeric_answer: str,
    ) -> bool:
        answer_candidates = self._answer_evidence_numeric_candidates(_normalise_spaces(str(answer or "")))
        numeric_candidates = self._answer_evidence_numeric_candidates(_normalise_spaces(str(numeric_answer or "")))
        if not numeric_candidates:
            return True
        if not answer_candidates:
            return False
        return all(
            any(
                self._numeric_candidates_equivalent_for_evidence(answer_candidate, numeric_candidate)
                for answer_candidate in answer_candidates
            )
            for numeric_candidate in numeric_candidates
        )

    def _evidence_text_for_final_support(self, evidence: Dict[str, Any]) -> str:
        return evidence_text_for_numeric_support(evidence)

    def _evidence_supports_final_answer_numeric_material(
        self,
        evidence: Dict[str, Any],
        answer_candidates: List[Dict[str, Any]],
    ) -> bool:
        evidence_candidates = self._answer_evidence_numeric_candidates(
            self._evidence_text_for_final_support(evidence)
        )
        if not evidence_candidates:
            return False
        return any(
            self._numeric_candidates_equivalent_for_evidence(answer_candidate, evidence_candidate)
            for answer_candidate in answer_candidates
            for evidence_candidate in evidence_candidates
        )

    def _text_supports_final_answer_numeric_material(
        self,
        text: str,
        answer_candidates: List[Dict[str, Any]],
    ) -> bool:
        text_candidates = self._answer_evidence_numeric_candidates(text)
        if not text_candidates:
            return False
        return any(
            self._numeric_candidates_equivalent_for_evidence(answer_candidate, text_candidate)
            for answer_candidate in answer_candidates
            for text_candidate in text_candidates
        )

    def _table_numeric_support_text_for_final_answer(
        self,
        evidence: Dict[str, Any],
        *,
        final_answer: str,
        answer_candidates: List[Dict[str, Any]],
    ) -> str:
        metadata = dict(evidence.get("metadata") or {})
        table_lines = [
            _normalise_spaces(line)
            for line in str(metadata.get("table_value_labels_text") or "").splitlines()
            if _normalise_spaces(line)
        ]
        if not table_lines:
            return ""
        answer_surface = re.sub(r"\s+", "", _normalise_spaces(final_answer))
        unit_terms = sorted(
            {
                *[str(unit) for unit in dict(CALCULATION_RENDER_POLICY.get("krw_display_unit_scales") or {})],
                *[str(unit) for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())],
            },
            key=len,
            reverse=True,
        )
        unit_pattern = "|".join(re.escape(unit) for unit in unit_terms if unit)

        def _line_label(line: str) -> str:
            label = re.sub(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", " ", line)
            if unit_pattern:
                label = re.sub(unit_pattern, " ", label)
            label = re.sub(r"[|:;()\[\]/,]+", " ", label)
            return re.sub(r"\s+", "", _normalise_spaces(label))

        support_lines: List[str] = []
        for line in table_lines:
            label = _line_label(line)
            if len(label) < 2 or label not in answer_surface:
                continue
            line_candidates = self._answer_evidence_numeric_candidates(line)
            if not line_candidates:
                continue
            if any(
                self._numeric_candidates_equivalent_for_evidence(answer_candidate, line_candidate)
                for answer_candidate in answer_candidates
                for line_candidate in line_candidates
            ):
                support_lines.append(line)
            if len(support_lines) >= 4:
                break
        if not support_lines:
            return ""
        header = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    metadata.get("table_header_context"),
                    metadata.get("table_context"),
                )
            )
        )
        return _normalise_spaces(" ; ".join([header, *support_lines] if header else support_lines))

    def _promote_table_numeric_support_evidence(
        self,
        evidence: Dict[str, Any],
        *,
        final_answer: str,
        answer_candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        support_text = self._table_numeric_support_text_for_final_answer(
            evidence,
            final_answer=final_answer,
            answer_candidates=answer_candidates,
        )
        if not support_text:
            return evidence
        promoted = dict(evidence)
        claim = _normalise_spaces(str(promoted.get("claim") or ""))
        quote_span = _normalise_spaces(str(promoted.get("quote_span") or ""))
        promoted["claim"] = _normalise_spaces(" | ".join(part for part in (claim, support_text) if part))
        promoted["quote_span"] = _normalise_spaces(" | ".join(part for part in (quote_span, support_text) if part))
        metadata = dict(promoted.get("metadata") or {})
        metadata["final_answer_table_numeric_support"] = support_text
        promoted["metadata"] = metadata
        return promoted

    def _filter_aggregate_evidence_for_final_answer(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        final_answer: str,
        selected_claim_ids: List[str],
    ) -> List[Dict[str, Any]]:
        answer_candidates = self._answer_evidence_numeric_candidates(final_answer)
        if not evidence_items or not answer_candidates:
            return list(evidence_items or [])
        answer_has_percent = any(str(candidate.get("kind") or "") == "percent" for candidate in answer_candidates)
        selected = {str(value).strip() for value in (selected_claim_ids or []) if str(value).strip()}
        selected_or_operand_numeric_support = any(
            (
                str((item or {}).get("evidence_id") or "").strip() in selected
                or str((item or {}).get("evidence_id") or "").strip().startswith("operand::")
            )
            and self._evidence_supports_final_answer_numeric_material(dict(item or {}), answer_candidates)
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
                evidence = self._promote_table_numeric_support_evidence(
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
                    and not self._text_supports_final_answer_numeric_material(quote_span, answer_candidates)
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
            if self._evidence_supports_final_answer_numeric_material(evidence, answer_candidates):
                filtered.append(evidence)
        return filtered or list(evidence_items or [])

    def _append_operand_evidence_for_final_answer(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        operands: List[Dict[str, Any]],
        final_answer: str,
    ) -> List[Dict[str, Any]]:
        answer_candidates = self._answer_evidence_numeric_candidates(final_answer)
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
            operand_candidates = self._answer_evidence_numeric_candidates(operand_text)
            supports_answer_numeric = any(
                self._numeric_candidates_equivalent_for_evidence(answer_candidate, operand_candidate)
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
        answer_numeric_candidates = self._answer_evidence_numeric_candidates(answer_text)

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
                for term in self._narrative_context_terms(text)
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
            if self._text_supports_final_answer_numeric_material(cleaned, answer_numeric_candidates):
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
            if phrase and self._answer_evidence_numeric_candidates(sentence):
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

    def _filter_aggregate_projection_provenance(
        self,
        projection: Dict[str, Any],
        kept_evidence_ids: List[str],
    ) -> Dict[str, Any]:
        kept = {str(value).strip() for value in (kept_evidence_ids or []) if str(value).strip()}
        if not kept:
            return projection

        def _filter_ids(values: Any) -> List[str]:
            current = _clean_source_row_ids([values])
            return [
                value
                for value in current
                if not (value.startswith("ev_") or value.startswith("recon::")) or value in kept
            ]

        updated = dict(projection)
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
        return updated

    def _dependency_slot_matches_input(
        self,
        binding: Dict[str, Any],
        slot: Dict[str, Any],
        *,
        sibling_row: Dict[str, Any],
        state: Optional[FinancialAgentState] = None,
    ) -> bool:
        binding_concept = _normalise_spaces(str(binding.get("concept") or ""))
        slot_concept = _normalise_spaces(str(slot.get("concept") or ""))
        if binding_concept and slot_concept and binding_concept != slot_concept:
            return False

        binding_period = _normalise_spaces(str(binding.get("period") or ""))
        slot_period = _normalise_spaces(str(slot.get("period") or ""))
        if binding_period and slot_period and binding_period != slot_period:
            binding_focus = _operand_period_focus(
                {
                    "period_hint": binding_period,
                    "role": binding.get("role") or "",
                },
                "unknown",
            )
            if binding_focus not in {"current", "prior"}:
                return False
            report_scope = dict((state or {}).get("report_scope") or {})
            report_year: Optional[int] = None
            try:
                if report_scope.get("year") not in (None, ""):
                    report_year = int(report_scope.get("year"))
            except (TypeError, ValueError):
                report_year = None
            slot_years = [int(match) for match in re.findall(r"20\d{2}", slot_period)]
            if report_year is not None and slot_years:
                if binding_focus == "current" and report_year not in slot_years:
                    return False
                if binding_focus == "prior" and (report_year - 1) not in slot_years:
                    return False
            elif _operand_period_focus({"period_hint": slot_period}, "unknown") != binding_focus:
                return False

        binding_label = _normalise_spaces(str(binding.get("label") or ""))
        slot_label = _normalise_spaces(str(slot.get("label") or ""))
        sibling_label = _normalise_spaces(str(sibling_row.get("metric_label") or ""))
        if binding_label and slot_label and binding_label != slot_label:
            if binding_label not in slot_label and binding_label not in sibling_label:
                return False

        binding_segment = _normalise_spaces(str(binding.get("segment_label") or ""))
        if binding_segment:
            label_text = " ".join(
                part
                for part in [
                    slot_label.lower(),
                    sibling_label.lower(),
                ]
                if part
            )
            if binding_segment.lower() not in label_text:
                return False

        return True

    def _infer_dependency_row_unit(
        self,
        slot: Dict[str, Any],
        sibling_result: Dict[str, Any],
    ) -> tuple[str, str]:
        raw_unit = _normalise_spaces(
            str(
                slot.get("raw_unit")
                or sibling_result.get("result_unit")
                or ""
            )
        )
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "UNKNOWN")).upper() or "UNKNOWN"
        if normalized_unit == "UNKNOWN":
            render_policy = dict(CALCULATION_RENDER_POLICY)
            if raw_unit in set(render_policy.get("percent_display_units") or ()):
                normalized_unit = "PERCENT"
            elif raw_unit in set(render_policy.get("krw_display_units") or ()):
                normalized_unit = str(render_policy.get("krw_normalized_unit") or "KRW").upper()
            elif raw_unit in set(render_policy.get("count_display_units") or ()):
                normalized_unit = "COUNT"
        return raw_unit, normalized_unit

    def _build_dependency_operand_rows(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        input_bindings = [dict(item) for item in (active_subtask.get("inputs") or [])]
        if not input_bindings:
            return []

        sibling_rows = {
            str(row.get("task_id") or "").strip(): dict(row)
            for row in (state.get("subtask_results") or [])
            if str(row.get("task_id") or "").strip()
        }
        evidence_by_id = {
            str(item.get("evidence_id") or "").strip(): dict(item)
            for row in sibling_rows.values()
            for item in list(row.get("runtime_evidence") or [])
            if str(item.get("evidence_id") or "").strip()
        }
        evidence_by_id.update(
            {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in list(state.get("evidence_items") or [])
                if str(item.get("evidence_id") or "").strip()
            }
        )
        evidence_by_id.update(
            {
                str(item.get("evidence_id") or "").strip(): dict(item)
                for item in list(state.get("runtime_evidence") or [])
                if str(item.get("evidence_id") or "").strip()
            }
        )
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
            sibling_evidence_by_id = self._evidence_items_by_id(
                [dict(item) for item in (sibling_row.get("runtime_evidence") or []) if isinstance(item, dict)]
            )
            sibling_result = dict(sibling_row.get("calculation_result") or {})
            answer_slots = dict(sibling_result.get("answer_slots") or {})
            source_slot_name = _normalise_spaces(str(binding.get("source_slot") or "primary_value")) or "primary_value"
            source_slot = dict(answer_slots.get(source_slot_name) or {})
            source_slot_from_answer_slots = self._answer_slot_has_material(source_slot)
            if not self._answer_slot_has_material(source_slot):
                producer_task = self._producer_task_for_dependency_binding(state, binding)
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
            if not self._answer_slot_has_material(source_slot) and sibling_result.get("result_value") is not None:
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
            if not self._answer_slot_has_material(source_slot):
                continue
            if not self._dependency_slot_matches_input(binding, source_slot, sibling_row=sibling_row, state=state):
                continue
            source_slot_from_answer_slots = True
            current_evidence = self._evidence_item_for_operand_row(
                source_slot,
                sibling_evidence_by_id,
            ) or self._evidence_item_for_operand_row(source_slot, evidence_by_id)
            current_metadata = dict((current_evidence or {}).get("metadata") or {})
            current_score = (
                self._direct_structured_lookup_evidence_score(binding, current_evidence)
                if current_evidence
                else 0.0
            )
            preferred_slot: Dict[str, Any] = {}
            preferred_score = 0.0

            def _candidate_slot_scope_conflicts_current(slot: Dict[str, Any]) -> bool:
                current_scope = self._known_consolidation_scope_value(
                    source_slot.get("consolidation_scope"),
                    current_metadata.get("consolidation_scope"),
                )
                if not current_scope:
                    return False
                candidate_evidence = self._evidence_item_for_operand_row(slot, evidence_by_id)
                candidate_metadata = dict((candidate_evidence or {}).get("metadata") or {})
                candidate_scope = self._known_consolidation_scope_value(
                    slot.get("consolidation_scope"),
                    candidate_metadata.get("consolidation_scope"),
                )
                return bool(candidate_scope and candidate_scope != current_scope)

            if source_slot_from_answer_slots and "retrieval" in source_preference:
                source_raw_number = _parse_number_text(str(source_slot.get("raw_value") or ""))
                preferred_raw_number = None
                candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                    binding,
                    evidence_pool,
                    state=state,
                )
                if candidate_slot and _candidate_slot_scope_conflicts_current(candidate_slot):
                    candidate_slot = {}
                    candidate_score = 0.0
                def _candidate_slot_has_sibling_input_context(slot: Dict[str, Any]) -> bool:
                    candidate_evidence = self._evidence_item_for_operand_row(slot, evidence_by_id)
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
                    binding_identity = self._dependency_binding_identity(binding)
                    for other_binding in input_bindings:
                        other_identity = self._dependency_binding_identity(other_binding)
                        if other_identity == binding_identity:
                            continue
                        sibling_surfaces = [
                            _normalise_spaces(str(surface or ""))
                            for surface in (
                                [other_binding.get("label")]
                                + list(other_binding.get("aliases") or [])
                                + list((other_binding.get("surface_contract") or {}).get("positive") or [])
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
                    table_label_score = self._table_label_metadata_lookup_score(table_label_slot, evidence)
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
                allow_preferred_slot_lookup = (
                    bool(candidate_slot)
                    and source_raw_number is not None
                    and preferred_raw_number is not None
                    and (
                        abs(float(source_raw_number) - float(preferred_raw_number)) <= 1e-6
                        or candidate_has_sibling_context
                    )
                )
                if allow_preferred_slot_lookup:
                    preferred_slot, preferred_score = candidate_slot, candidate_score
                    if candidate_has_sibling_context and preferred_score <= current_score:
                        preferred_score = current_score + 0.1
            else:
                preferred_slot, preferred_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
                    binding,
                    evidence_pool,
                    state=state,
                )
                if preferred_slot and _candidate_slot_scope_conflicts_current(preferred_slot):
                    preferred_slot = {}
                    preferred_score = 0.0
            if preferred_slot and preferred_score > current_score:
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
                    source_slot = preferred_slot
            raw_unit, normalized_unit = self._infer_dependency_row_unit(source_slot, sibling_result)
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
                    raw_unit, normalized_unit = self._infer_dependency_row_unit(source_slot, sibling_result)
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
            selected_evidence = self._evidence_item_for_operand_row(
                source_slot,
                sibling_evidence_by_id,
            ) or self._evidence_item_for_operand_row(source_slot, evidence_by_id)
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
                "period": _normalise_spaces(str(source_slot.get("period") or binding.get("period") or "")),
                "consolidation_scope": _normalise_spaces(
                    str(
                        source_slot.get("consolidation_scope")
                        or matched_operand_candidate.get("consolidation_scope")
                        or self._known_consolidation_scope_value(selected_metadata.get("consolidation_scope"))
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
            dependency_row = self._repair_operand_normalization_from_rendered_unit(dependency_row)
            structured_provenance = self._structured_graph_provenance_for_dependency_operand(
                state,
                binding=binding,
                row=dependency_row,
            )
            if structured_provenance:
                structured_anchor = _normalise_spaces(str(structured_provenance.get("source_anchor") or ""))
                structured_chunk_uid = _normalise_spaces(str(structured_provenance.get("chunk_uid") or ""))
                if structured_anchor:
                    dependency_row["source_anchor"] = structured_anchor
                if structured_chunk_uid:
                    dependency_row["source_row_ids"] = _clean_source_row_ids([
                        dependency_row.get("source_row_ids"),
                        structured_chunk_uid,
                    ])
                structured_unit_hint = _normalise_spaces(str(structured_provenance.get("unit_hint") or ""))
                current_raw_unit = _normalise_spaces(str(dependency_row.get("raw_unit") or ""))
                current_raw_value = _normalise_spaces(str(dependency_row.get("raw_value") or ""))
                current_rendered_value = _normalise_spaces(str(dependency_row.get("rendered_value") or ""))
                converted_units = {
                    _normalise_spaces(str(unit or ""))
                    for unit in (CALCULATION_RENDER_POLICY.get("converted_display_units") or ())
                    if _normalise_spaces(str(unit or ""))
                }
                current_value_consistent = False
                if current_raw_value and current_raw_unit:
                    expected_value, expected_unit = _normalise_operand_value(current_raw_value, current_raw_unit)
                    try:
                        current_normalized_value = float(dependency_row.get("normalized_value"))
                    except (TypeError, ValueError):
                        current_normalized_value = None
                    current_value_consistent = bool(
                        expected_value is not None
                        and current_normalized_value is not None
                        and _normalise_spaces(str(expected_unit or "")).upper()
                        == _normalise_spaces(str(dependency_row.get("normalized_unit") or "")).upper()
                        and abs(float(expected_value) - current_normalized_value) <= max(
                            1e-6,
                            abs(float(expected_value)) * 1e-9,
                        )
                    )
                high_magnitude_converted_value = bool(
                    current_raw_unit in converted_units
                    and current_value_consistent
                    and len(re.sub(r"\D", "", current_raw_value)) >= 8
                )
                source_visible_converted_unit = bool(
                    current_raw_value
                    and current_raw_unit
                    and current_raw_unit in converted_units
                    and (
                        high_magnitude_converted_value
                        or (
                            current_raw_value in current_rendered_value
                            and current_raw_unit in current_rendered_value
                        )
                    )
                )
                if (
                    structured_unit_hint
                    and structured_unit_hint != current_raw_unit
                    and not source_visible_converted_unit
                ):
                    structured_value, structured_unit = _normalise_operand_value(
                        str(dependency_row.get("raw_value") or ""),
                        structured_unit_hint,
                    )
                    if structured_value is not None and structured_unit:
                        dependency_row["raw_unit"] = structured_unit_hint
                        dependency_row["normalized_value"] = structured_value
                        dependency_row["normalized_unit"] = structured_unit
                        dependency_row["rendered_value"] = _normalise_spaces(
                            f"{dependency_row.get('raw_value')}{structured_unit_hint}"
                        )
                        dependency_row["unit_realigned_from_structured_provenance"] = True
                for key in ("consolidation_scope", "statement_type", "table_source_id"):
                    value = _normalise_spaces(str(structured_provenance.get(key) or ""))
                    if value:
                        dependency_row[key] = value
            source_evidence = self._evidence_item_for_operand_row(dependency_row, evidence_by_id)
            dependency_rows.append(self._coerce_operand_row_from_evidence(dependency_row, source_evidence))
        return dependency_rows

    def _structured_graph_provenance_for_dependency_operand(
        self,
        state: FinancialAgentState,
        *,
        binding: Dict[str, Any],
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
        preferred_statement_types = set(self._producer_statement_types_for_dependency_binding(state, binding))
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
            if statement_type and statement_type in preferred_statement_types:
                score += 6
            elif preferred_statement_types and statement_type == "notes":
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

    def _task_prefers_sibling_output_synthesis(self, state: FinancialAgentState) -> bool:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = _normalise_spaces(str(active_subtask.get("operation_family") or "")).lower()
        if operation_family not in {"difference", "growth_rate", "ratio", "sum"}:
            return False
        for binding in (active_subtask.get("inputs") or []):
            binding_data = dict(binding)
            source_preference = [
                _normalise_spaces(str(item or "")).lower()
                for item in (binding_data.get("source_preference") or [])
                if _normalise_spaces(str(item or ""))
            ]
            if "task_output" in source_preference and _normalise_spaces(str(binding_data.get("preferred_task_id") or "")):
                return True
        return False

    def _task_output_input_bindings(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        bindings: List[Dict[str, Any]] = []
        for binding in (active_subtask.get("inputs") or []):
            binding_data = dict(binding)
            source_preference = [
                _normalise_spaces(str(item or "")).lower()
                for item in (binding_data.get("source_preference") or [])
                if _normalise_spaces(str(item or ""))
            ]
            if "task_output" not in source_preference:
                continue
            if not _normalise_spaces(str(binding_data.get("preferred_task_id") or "")):
                continue
            bindings.append(binding_data)
        return bindings

    def _dependency_binding_resolution_state(self, state: FinancialAgentState) -> Dict[str, Any]:
        dependency_bindings = self._task_output_input_bindings(state)
        dependency_rows = self._build_dependency_operand_rows(state)
        dependency_binding_keys = {
            self._dependency_binding_identity(binding)
            for binding in dependency_bindings
            if any(self._dependency_binding_identity(binding))
        }
        resolved_dependency_keys = {
            (
                _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                _normalise_spaces(str(row.get("matched_operand_role") or "")),
            )
            for row in dependency_rows
        }
        missing_dependency_bindings = [
            dict(binding)
            for binding in dependency_bindings
            if self._dependency_binding_identity(binding) not in resolved_dependency_keys
        ]
        resolved_binding_count = max(len(dependency_bindings) - len(missing_dependency_bindings), 0)
        return {
            "bindings": dependency_bindings,
            "rows": dependency_rows,
            "binding_keys": dependency_binding_keys,
            "resolved_keys": resolved_dependency_keys,
            "missing_bindings": missing_dependency_bindings,
            "binding_count": len(dependency_bindings),
            "resolved_binding_count": resolved_binding_count,
            "has_bindings": bool(dependency_bindings),
            "has_rows": bool(dependency_rows),
            "all_resolved": bool(dependency_bindings) and not missing_dependency_bindings and bool(dependency_rows),
        }

    def _direct_rows_resolved_dependency_keys(
        self,
        bindings: List[Dict[str, Any]],
        operand_rows: List[Dict[str, Any]],
    ) -> set[tuple[str, str]]:
        resolved_keys: set[tuple[str, str]] = set()
        for binding in bindings:
            binding_key = self._dependency_binding_identity(binding)
            if not any(binding_key):
                continue
            if any(_operand_row_matches_requirement(row, binding) for row in (operand_rows or [])):
                resolved_keys.add(binding_key)
        return resolved_keys

    def _producer_task_for_dependency_binding(
        self,
        state: FinancialAgentState,
        binding: Dict[str, Any],
    ) -> Dict[str, Any]:
        preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
        if not preferred_task_id:
            return {}
        for task in list(state.get("calc_subtasks") or []):
            task_row = dict(task or {})
            if _normalise_spaces(str(task_row.get("task_id") or "")) == preferred_task_id:
                return task_row
        for task in list((dict(state.get("semantic_plan") or {}).get("tasks") or [])):
            task_row = dict(task or {})
            if _normalise_spaces(str(task_row.get("task_id") or "")) == preferred_task_id:
                return task_row
        return {}

    def _producer_statement_types_for_dependency_binding(
        self,
        state: FinancialAgentState,
        binding: Dict[str, Any],
    ) -> List[str]:
        producer_task = self._producer_task_for_dependency_binding(state, binding)
        if not producer_task:
            return []
        preferred_types: List[str] = []
        binding_role = _normalise_spaces(str(binding.get("role") or ""))
        binding_concept = _normalise_spaces(str(binding.get("concept") or ""))
        for operand in list(producer_task.get("required_operands") or []):
            operand_row = dict(operand or {})
            operand_role = _normalise_spaces(str(operand_row.get("role") or ""))
            operand_concept = _normalise_spaces(str(operand_row.get("concept") or ""))
            if binding_role and operand_role and binding_role != operand_role:
                continue
            if binding_concept and operand_concept and binding_concept != operand_concept:
                continue
            preferred_types.extend(
                _normalise_spaces(str(item))
                for item in list(operand_row.get("preferred_statement_types") or [])
                if _normalise_spaces(str(item))
            )
        preferred_types.extend(
            _normalise_spaces(str(item))
            for item in list(producer_task.get("preferred_statement_types") or [])
            if _normalise_spaces(str(item))
        )
        return list(dict.fromkeys(preferred_types))

    def _producer_sections_for_dependency_binding(
        self,
        state: FinancialAgentState,
        binding: Dict[str, Any],
    ) -> List[str]:
        producer_task = self._producer_task_for_dependency_binding(state, binding)
        if not producer_task:
            return []
        preferred_sections: List[str] = []
        binding_role = _normalise_spaces(str(binding.get("role") or ""))
        binding_concept = _normalise_spaces(str(binding.get("concept") or ""))
        for operand in list(producer_task.get("required_operands") or []):
            operand_row = dict(operand or {})
            operand_role = _normalise_spaces(str(operand_row.get("role") or ""))
            operand_concept = _normalise_spaces(str(operand_row.get("concept") or ""))
            if binding_role and operand_role and binding_role != operand_role:
                continue
            if binding_concept and operand_concept and binding_concept != operand_concept:
                continue
            preferred_sections.extend(
                _normalise_spaces(str(item))
                for item in list(operand_row.get("preferred_sections") or [])
                if _normalise_spaces(str(item))
            )
        preferred_sections.extend(
            _normalise_spaces(str(item))
            for item in list(producer_task.get("preferred_sections") or [])
            if _normalise_spaces(str(item))
        )
        return list(dict.fromkeys(preferred_sections))

    def _dependency_row_violates_producer_scope(
        self,
        row: Dict[str, Any],
        *,
        preferred_statement_types: List[str],
        preferred_sections: List[str],
    ) -> tuple[bool, str]:
        row_statement_type = _normalise_spaces(str(row.get("statement_type") or ""))
        if (
            preferred_statement_types
            and row_statement_type
            and row_statement_type not in preferred_statement_types
        ):
            return True, "statement_type"

        row_scope_text = _normalise_spaces(
            " ".join(
                str(row.get(key) or "")
                for key in ("source_anchor", "table_source_id", "source_context")
            )
        ).lower()
        if not row_scope_text:
            return False, ""
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        note_markers = tuple(str(item).lower() for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        row_is_note_scoped = any(marker in row_scope_text for marker in note_markers) or "note" in row_scope_text
        producer_allows_notes = (
            "notes" in preferred_statement_types
            or any(
                any(marker in _normalise_spaces(str(section)).lower() for marker in note_markers)
                or "note" in _normalise_spaces(str(section)).lower()
                for section in preferred_sections
            )
        )
        if row_is_note_scoped and not producer_allows_notes:
            return True, "section_scope"
        return False, ""

    def _filter_direct_rows_by_dependency_producer_scope(
        self,
        state: FinancialAgentState,
        *,
        bindings: List[Dict[str, Any]],
        operand_rows: List[Dict[str, Any]],
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not bindings or not operand_rows:
            return list(operand_rows or []), []
        filtered_rows: List[Dict[str, Any]] = []
        rejected_rows: List[Dict[str, Any]] = []
        for row in list(operand_rows or []):
            row_data = dict(row or {})
            matching_binding = next(
                (
                    dict(binding)
                    for binding in bindings
                    if _operand_row_matches_requirement(row_data, dict(binding))
                ),
                {},
            )
            if not matching_binding:
                filtered_rows.append(row_data)
                continue
            preferred_statement_types = self._producer_statement_types_for_dependency_binding(
                state,
                matching_binding,
            )
            preferred_sections = self._producer_sections_for_dependency_binding(
                state,
                matching_binding,
            )
            violates_scope, reject_reason = self._dependency_row_violates_producer_scope(
                row_data,
                preferred_statement_types=preferred_statement_types,
                preferred_sections=preferred_sections,
            )
            if violates_scope:
                rejected_rows.append(
                    {
                        "binding": matching_binding,
                        "row": row_data,
                        "reject_reason": reject_reason,
                        "preferred_statement_types": preferred_statement_types,
                        "preferred_sections": preferred_sections,
                        "row_statement_type": _normalise_spaces(str(row_data.get("statement_type") or "")),
                    }
                )
                continue
            filtered_rows.append(row_data)
        return filtered_rows, rejected_rows

    def _dependency_binding_identity(self, binding: Dict[str, Any]) -> tuple[str, str]:
        return (
            _normalise_spaces(str(binding.get("label") or "")),
            _normalise_spaces(str(binding.get("role") or "")),
        )

    def _material_gap_feedback_for_subtask_result(self, row: Dict[str, Any]) -> str:
        feedback_policy = dict(CALCULATION_FEEDBACK_POLICY)
        metric_label = _normalise_spaces(
            str(
                row.get("metric_label")
                or row.get("answer")
                or row.get("task_id")
                or feedback_policy.get("default_metric_label")
                or ""
            )
        )
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        status = str(
            row.get("status")
            or calculation_result.get("status")
            or ""
        ).strip().lower()
        rendered_material = _normalise_spaces(
            str(
                calculation_result.get("formatted_result")
                or calculation_result.get("rendered_value")
                or row.get("answer")
                or ""
            )
        )
        operation_family = str(
            answer_slots.get("operation_family")
            or ((row.get("calculation_plan") or {}).get("operation_family"))
            or ((calculation_result.get("derived_metrics") or {}).get("operation_family"))
            or ""
        ).strip().lower()
        if not operation_family:
            operation_family = str((row.get("calculation_plan") or {}).get("operation") or "").strip().lower()
        if not operation_family:
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if metric_family.startswith("concept_"):
                operation_family = metric_family.removeprefix("concept_")

        if operation_family == "aggregate_subtasks":
            nested_results = list(
                answer_slots.get("subtask_results")
                or calculation_result.get("subtask_results")
                or []
            )
            for nested_row in reversed(nested_results):
                nested_metric_label = _normalise_spaces(
                    str(
                        nested_row.get("metric_label")
                        or nested_row.get("task_id")
                        or ""
                    )
                )
                if metric_label and nested_metric_label and nested_metric_label != metric_label:
                    continue
                if not self._material_gap_feedback_for_subtask_result(dict(nested_row)):
                    return ""

        if operation_family in {"lookup", "single_value"}:
            if not self._answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
                return str(feedback_policy.get("lookup_missing_template") or "").format(metric_label=metric_label)
            return ""

        if operation_family in {"difference", "growth_rate"}:
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            if operation_family == "growth_rate" and self._growth_row_has_conflicting_periods(row):
                return str(feedback_policy.get("generic_missing_material_template") or "").format(
                    metric_label=metric_label
                )
            missing_labels: List[str] = []
            if not self._answer_slot_has_material(current_slot):
                period = str(
                    current_slot.get("period")
                    or calculation_result.get("current_period")
                    or feedback_policy.get("default_current_period")
                    or ""
                )
                missing_labels.append(
                    str(feedback_policy.get("missing_period_value_template") or "").format(period=period)
                )
            if not self._answer_slot_has_material(prior_slot):
                period = str(
                    prior_slot.get("period")
                    or calculation_result.get("prior_period")
                    or feedback_policy.get("default_prior_period")
                    or ""
                )
                missing_labels.append(
                    str(feedback_policy.get("missing_period_value_template") or "").format(period=period)
                )
            if operation_family == "difference":
                if not self._answer_slot_has_material(dict(answer_slots.get("delta_value") or primary_slot)):
                    missing_labels.append(str(feedback_policy.get("difference_missing_result_label") or ""))
            else:
                if not self._answer_slot_has_material(primary_slot):
                    if not (status == "ok" and rendered_material and re.search(r"\d", rendered_material)):
                        missing_labels.append(str(feedback_policy.get("growth_missing_result_label") or ""))
            if missing_labels:
                return str(feedback_policy.get("missing_material_template") or "").format(
                    metric_label=metric_label,
                    missing_labels=str(feedback_policy.get("missing_material_joiner") or "").join(missing_labels),
                )
            return ""

        if operation_family in {"ratio", "sum"}:
            if not self._answer_slot_has_material(dict(answer_slots.get("primary_value") or {})):
                if status == "ok" and rendered_material and re.search(r"\d", rendered_material):
                    return ""
                return str(feedback_policy.get("missing_result_template") or "").format(metric_label=metric_label)
            return ""

        return ""

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
                gap = self._material_gap_feedback_for_subtask_result(row)
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

            gap = self._material_gap_feedback_for_subtask_result(row)
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
        return operation_family

    def _aggregate_result_signature(self, row: Dict[str, Any]) -> str:
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
        operation_family = self._aggregate_result_operation_family(row)
        if operation_family:
            return f"{operation_family}:{metric_label}"
        return metric_label

    def _growth_operand_sign_consistency_rank(self, row: Dict[str, Any]) -> int:
        if self._aggregate_result_operation_family(row) != "growth_rate":
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

    def _aggregate_row_primary_answer_slot(self, row: Dict[str, Any]) -> Dict[str, Any]:
        calculation_result = dict(row.get("calculation_result") or {})
        answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
        return dict(answer_slots.get("primary_value") or {})

    def _aggregate_source_slot_by_task_id(self, ordered_results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        source_slot_by_task_id: Dict[str, Dict[str, Any]] = {}
        for row in ordered_results:
            if not isinstance(row, dict):
                continue
            task_id = _normalise_spaces(str(row.get("task_id") or ""))
            if not task_id:
                continue
            slot = self._aggregate_row_primary_answer_slot(dict(row))
            if not slot:
                continue
            scope = self._known_consolidation_scope_value(
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
            for task_id, slot in self._aggregate_source_slot_by_task_id(ordered_results).items()
            if task_id in lookup_task_ids
        }
        dependency_slots = build_dependency_lookup_slots_by_task(
            ordered_results,
            {},
            operation_family_for_result=self._aggregate_result_operation_family,
            slot_has_material=self._answer_slot_has_material,
        )
        source_slots.update(dependency_slots)
        for task_id, slot in list(source_slots.items()):
            metric_label = metric_label_by_task_id.get(task_id, "")
            if metric_label and not slot.get("metric_label"):
                slot = dict(slot)
                slot["metric_label"] = metric_label
                source_slots[task_id] = slot
        return source_slots

    def _ratio_rebuild_component_seeds(
        self,
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
            group = _dependency_ratio_role_group(role)
            if group == "numerator":
                numerator.append(seed)
            elif group == "denominator":
                denominator.append(seed)
            elif self._answer_slot_has_material(seed):
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

    def _dependency_source_text_match_score(self, left: str, right: str) -> int:
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
            for token in self._narrative_context_terms(left)
            if len(token) >= 2
        }
        right_terms = {
            token.lower()
            for token in self._narrative_context_terms(right)
            if len(token) >= 2
        }
        return score + len(left_terms & right_terms)

    def _dependency_source_slot_match_score(
        self,
        slot: Dict[str, Any],
        seed: Dict[str, Any],
        role: str,
    ) -> int:
        score = _dependency_lookup_slot_match_score(slot, seed, role)
        slot_text = " ".join(
            str(slot.get(key) or "")
            for key in ("label", "metric_label", "concept", "period")
        )
        seed_text = " ".join(
            str(seed.get(key) or seed.get(f"matched_operand_{key}") or "")
            for key in ("label", "concept", "period")
        )
        return score + self._dependency_source_text_match_score(slot_text, seed_text)

    def _best_dependency_source_for_seed(
        self,
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
        inferred_task_ids = set(self._aggregate_source_task_ids_for_operand(seed, source_slots))
        ranked: List[tuple[int, str, Dict[str, Any]]] = []
        for task_id, slot in source_slots.items():
            if task_id in excluded:
                continue
            score = self._dependency_source_slot_match_score(slot, seed, role)
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

    def _component_slot_from_dependency_source(
        self,
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
        slot = self._build_operand_value_slot(source_operand, default_role=role)
        slot["role"] = role
        slot["source_task_id"] = source_task_id
        slot["dependency_resolved"] = True
        return slot

    def _format_ratio_percent_result(self, result_value: float) -> str:
        rendered_value = self._format_calculation_value(result_value, "%", "PERCENT")
        return rendered_value if "%" in rendered_value else f"{result_value:.2f}".rstrip("0").rstrip(".") + "%"

    def _rebuilt_ratio_result_from_dependency_slots(
        self,
        *,
        calculation_result: Dict[str, Any],
        answer_slots: Dict[str, Any],
        metric_label: str,
        numerator_slot: Dict[str, Any],
        denominator_slot: Dict[str, Any],
        result_value: float,
        rendered_value: str,
        source_row_ids: List[str],
    ) -> Dict[str, Any]:
        return {
            **calculation_result,
            "status": "ok",
            "operation_family": "ratio",
            "result_value": result_value,
            "result_unit": "%",
            "rendered_value": rendered_value,
            "formatted_result": "",
            "source_row_ids": source_row_ids,
            "source_evidence_ids": source_row_ids,
            "answer_slots": {
                **answer_slots,
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
                    "raw_unit": "%",
                    "normalized_value": result_value,
                    "normalized_unit": "PERCENT",
                    "rendered_value": rendered_value,
                    "source_row_id": source_row_ids[0] if source_row_ids else "",
                    "source_row_ids": source_row_ids,
                    "source_anchor": "",
                },
                "components_by_group": {
                    "numerator": [numerator_slot],
                    "denominator": [denominator_slot],
                },
                "components_by_role": {
                    "numerator_1": [numerator_slot],
                    "denominator_1": [denominator_slot],
                },
            },
        }

    def _ratio_answer_from_dependency_source_slots(
        self,
        row: Dict[str, Any],
        source_slot_by_task_id: Dict[str, Dict[str, Any]],
    ) -> str:
        source_slots = {
            task_id: dict(slot)
            for task_id, slot in dict(source_slot_by_task_id or {}).items()
            if task_id and self._answer_slot_has_material(dict(slot or {}))
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

        numerator_seeds, denominator_seeds, ungrouped_seeds = self._ratio_rebuild_component_seeds(
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
        numerator_task_id, numerator_source, numerator_seed, _numerator_score = self._best_dependency_source_for_seed(
            numerator_seed,
            "numerator_1",
            source_slots=source_slots,
        )
        if not numerator_task_id or not numerator_source:
            return ""
        denominator_task_id, denominator_source, denominator_seed, _denominator_score = (
            self._best_dependency_source_for_seed(
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
            ) = self._best_dependency_source_for_seed(
                metric_seed,
                "denominator_1",
                source_slots=source_slots,
                excluded_task_ids={numerator_task_id},
            )
            current_metric_score = self._dependency_source_slot_match_score(
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
        numerator_slot = self._component_slot_from_dependency_source(
            numerator_seed,
            numerator_source,
            numerator_task_id,
            "numerator_1",
        )
        denominator_slot = self._component_slot_from_dependency_source(
            denominator_seed,
            denominator_source,
            denominator_task_id,
            "denominator_1",
        )
        if self._ratio_operand_rows_collapse_to_same_slot([numerator_slot, denominator_slot]):
            return ""
        numerator_value = self._coerce_slot_numeric(numerator_slot.get("normalized_value"))
        denominator_value = self._coerce_slot_numeric(denominator_slot.get("normalized_value"))
        if numerator_value is None or denominator_value in {None, 0}:
            return ""
        result_value = float(numerator_value) / float(denominator_value) * 100.0
        rendered_value = self._format_ratio_percent_result(result_value)
        source_row_ids = _clean_source_row_ids([
            numerator_slot.get("source_row_id"),
            numerator_slot.get("source_row_ids"),
            denominator_slot.get("source_row_id"),
            denominator_slot.get("source_row_ids"),
        ])
        rebuilt_result = self._rebuilt_ratio_result_from_dependency_slots(
            calculation_result=calculation_result,
            answer_slots=answer_slots,
            metric_label=metric_label,
            numerator_slot=numerator_slot,
            denominator_slot=denominator_slot,
            result_value=result_value,
            rendered_value=rendered_value,
            source_row_ids=source_row_ids,
        )
        return self._compact_ratio_answer(
            {
                "active_subtask": {"metric_label": metric_label},
                "resolved_calculation_trace": {
                    "calculation_operands": [numerator_slot, denominator_slot],
                    "calculation_plan": {
                        "status": "ok",
                        "operation": "ratio",
                        "result_unit": "%",
                    },
                    "calculation_result": rebuilt_result,
                },
            },
            rebuilt_result,
        )

    def _aggregate_result_candidate_operands(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
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

    def _aggregate_source_task_ids_for_operand(
        self,
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
            if not self._answer_slot_has_material(slot):
                continue
            if _dependency_lookup_slot_match_score(slot, operand, role) >= 12:
                inferred_task_ids.append(task_id)
        return inferred_task_ids

    def _aggregate_result_dependency_coherence_ranks(
        self,
        row: Dict[str, Any],
        source_slot_by_task_id: Optional[Dict[str, Dict[str, Any]]] = None,
    ) -> tuple[int, int]:
        operation_family = self._aggregate_result_operation_family(row)
        if operation_family not in {"ratio", "sum", "difference", "growth_rate"}:
            return 1, 1
        source_slots = dict(source_slot_by_task_id or {})
        saw_source_slot = False
        saw_source_scope = False
        for operand in self._aggregate_result_candidate_operands(row):
            source_task_ids = self._aggregate_source_task_ids_for_operand(operand, source_slots)
            source_task_id = source_task_ids[0] if source_task_ids else ""
            if source_task_id and source_slots:
                source_slot = dict(source_slots.get(source_task_id) or {})
                if self._answer_slot_has_material(source_slot):
                    saw_source_slot = True
                    source_anchor = _normalise_spaces(str(source_slot.get("source_anchor") or ""))
                    operand_anchor = _normalise_spaces(str(operand.get("source_anchor") or ""))
                    if (
                        (source_anchor and operand_anchor and source_anchor != operand_anchor)
                        or _dependency_projection_slot_differs_from_operand(source_slot, operand)
                    ):
                        return 0, 2 if saw_source_scope else 1
            if operation_family == "ratio" and source_slots and source_task_ids:
                source_scope = next(
                    (
                        self._known_consolidation_scope_value(source_slots.get(task_id, {}).get("consolidation_scope"))
                        for task_id in source_task_ids
                        if source_slots.get(task_id)
                    ),
                    "",
                )
                if source_scope:
                    saw_source_scope = True
                    operand_scope = self._known_consolidation_scope_value(operand.get("consolidation_scope"))
                    if operand_scope and operand_scope != source_scope:
                        return 2 if saw_source_slot else 1, 0
        return 2 if saw_source_slot else 1, 2 if saw_source_scope else 1

    def _aggregate_dependency_slot_coherence_rank_for_operands(
        self,
        *,
        operation_family: str,
        operands: List[Any],
        ordered_results: List[Dict[str, Any]],
        calculation_result: Optional[Dict[str, Any]] = None,
    ) -> int:
        return self._aggregate_result_dependency_coherence_ranks(
            {
                "operation_family": operation_family,
                "calculation_operands": [
                    dict(item)
                    for item in list(operands or [])
                    if isinstance(item, dict)
                ],
                "calculation_result": dict(calculation_result or {}),
            },
            self._aggregate_source_slot_by_task_id(ordered_results),
        )[0]

    def _aggregate_result_rank(
        self,
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
        material_rank = 0 if self._material_gap_feedback_for_subtask_result(row) else 1
        answer_rank = 1 if _normalise_spaces(str(row.get("answer") or "")) else 0
        growth_sign_rank = self._growth_operand_sign_consistency_rank(row)
        dependency_slot_rank, scope_coherence_rank = self._aggregate_result_dependency_coherence_ranks(
            row,
            source_slot_by_task_id,
        )
        operand_rank = len(list(calculation_result.get("source_row_ids") or []))
        return status_rank, material_rank, answer_rank, growth_sign_rank, dependency_slot_rank, scope_coherence_rank, operand_rank

    def _nested_aggregate_result_rank(self, row: Dict[str, Any]) -> tuple[int, int, int, int, int, int, int, int]:
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
        material_rank = 1 if self._subtask_row_has_material(row) else 0
        gap_free_rank = 0 if self._material_gap_feedback_for_subtask_result(row) else 1
        operation_family = self._aggregate_result_operation_family(row)
        non_aggregate_rank = 0 if operation_family == "aggregate_subtasks" else 1
        growth_sign_rank = self._growth_operand_sign_consistency_rank(row)
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

    def _subtask_numeric_answers_conflict(
        self,
        candidate_row: Dict[str, Any],
        current_row: Dict[str, Any],
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
        candidate_numbers = self._answer_evidence_numeric_candidates(candidate_answer)
        current_numbers = self._answer_evidence_numeric_candidates(current_answer)
        if not candidate_numbers or not current_numbers:
            return False
        return not all(
            any(
                self._numeric_candidates_equivalent_for_evidence(candidate_number, current_number)
                for current_number in current_numbers
            )
            for candidate_number in candidate_numbers
        )

    def _subtask_row_has_direct_source_refs(self, row: Dict[str, Any]) -> bool:
        calculation_result = dict(row.get("calculation_result") or {})
        source_ids = _clean_source_row_ids([
            row.get("source_row_ids"),
            calculation_result.get("source_row_ids"),
            row.get("selected_claim_ids"),
            calculation_result.get("source_evidence_ids"),
        ])
        return any(source_id and not source_id.startswith("task_output:") for source_id in source_ids)

    def _promote_stronger_nested_aggregate_results(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        by_task_id = {
            _normalise_spaces(str(row.get("task_id") or "")): dict(row)
            for row in ordered_results
            if _normalise_spaces(str(row.get("task_id") or ""))
        }
        source_slot_by_task_id = self._aggregate_source_slot_by_task_id(list(by_task_id.values()))
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
                if self._material_gap_feedback_for_subtask_result(dict(nested_row)):
                    continue
                current_row = replacements.get(nested_task_id) or by_task_id.get(nested_task_id)
                if not current_row:
                    continue
                current_status = _normalise_spaces(
                    str(current_row.get("status") or (current_row.get("calculation_result") or {}).get("status") or "")
                ).lower()
                if (
                    current_status == "ok"
                    and not self._material_gap_feedback_for_subtask_result(current_row)
                    and self._subtask_row_has_direct_source_refs(current_row)
                    and self._aggregate_result_operation_family(current_row) == self._aggregate_result_operation_family(nested_row)
                    and self._subtask_numeric_answers_conflict(nested_row, current_row)
                    and self._growth_operand_sign_consistency_rank(nested_row)
                    <= self._growth_operand_sign_consistency_rank(current_row)
                ):
                    continue
                if self._nested_aggregate_result_rank(nested_row) <= self._nested_aggregate_result_rank(current_row):
                    continue
                if self._aggregate_result_dependency_coherence_ranks(
                    nested_row,
                    source_slot_by_task_id,
                )[0] < self._aggregate_result_dependency_coherence_ranks(
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
        preserved_results = self._sync_nested_subtask_rows_with_current_results(preserved_results)
        return preserved_results, self._rebuild_aggregate_projection(preserved_results, final_answer)

    def _sync_nested_subtask_rows_with_current_results(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
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

        return [_sync_row(dict(row), set()) for row in ordered_results]

    def _dedupe_aggregate_subtask_results(
        self,
        ordered_results: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        source_slot_by_task_id = self._aggregate_source_slot_by_task_id(ordered_results)
        winners: Dict[str, tuple[int, tuple[int, int, int, int, int, int, int], Dict[str, Any]]] = {}
        passthrough: List[tuple[int, Dict[str, Any]]] = []
        for index, row in enumerate(ordered_results):
            signature = self._aggregate_result_signature(row)
            if not signature:
                passthrough.append((index, row))
                continue
            rank = self._aggregate_result_rank(row, source_slot_by_task_id)
            incumbent = winners.get(signature)
            if incumbent is None or rank > incumbent[1] or (rank == incumbent[1] and index > incumbent[0]):
                winners[signature] = (index, rank, row)
        deduped = sorted(
            [item for item in winners.values()] + [(index, (0, 0, 0, 0, 0, 0, 0), row) for index, row in passthrough],
            key=lambda item: item[0],
        )
        return [dict(item[2]) for item in deduped]

    def _narrative_context_terms(self, query: str) -> List[str]:
        tokens = re.findall(r"[가-힣A-Za-z0-9()]+", _normalise_spaces(str(query or "")))
        stopwords = {
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("context_stopwords") or ())
            if str(item)
        }
        terms: List[str] = []
        for token in tokens:
            cleaned = token.strip()
            if len(cleaned) < 2 or cleaned in stopwords:
                continue
            if re.search(r"\d", cleaned):
                continue
            if re.fullmatch(r"\d+", cleaned):
                continue
            terms.append(cleaned)
        return list(dict.fromkeys(terms))

    def _narrative_focus_variants(self, query: str) -> List[str]:
        generic_terms = {
            _normalise_spaces(str(item)).lower()
            for item in (
                tuple(CALCULATION_NARRATIVE_POLICY.get("growth_generic_focus_terms") or ())
                + tuple(CALCULATION_NARRATIVE_POLICY.get("context_reuse_excluded_terms") or ())
            )
            if _normalise_spaces(str(item))
        }
        variants: List[str] = []
        for term in self._narrative_context_terms(query):
            cleaned = _normalise_spaces(str(term))
            if not cleaned or cleaned.lower() in generic_terms:
                continue
            candidates = [cleaned]
            candidates.extend(
                _normalise_spaces(match)
                for match in re.findall(r"\(([^)]+)\)", cleaned)
                if _normalise_spaces(match)
            )
            outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
            if outside_parentheses:
                candidates.append(outside_parentheses)
            for candidate in candidates:
                if len(candidate) < 2:
                    continue
                if candidate.lower() in generic_terms:
                    continue
                variants.append(candidate)
        return list(dict.fromkeys(variants))

    def _parenthetical_focus_variants(self, query: str) -> List[str]:
        variants: List[str] = []
        for term in self._narrative_context_terms(query):
            cleaned = _normalise_spaces(str(term))
            if not cleaned or "(" not in cleaned:
                continue
            variants.extend(
                _normalise_spaces(match)
                for match in re.findall(r"\(([^)]+)\)", cleaned)
                if _normalise_spaces(match)
            )
            outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
            if outside_parentheses:
                variants.append(outside_parentheses)
        return list(dict.fromkeys(variant for variant in variants if len(variant) >= 2))

    def _narrative_context_sentence_from_evidence(
        self,
        query: str,
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        if not _query_requests_narrative_context(query):
            return ""
        query_terms = self._narrative_context_terms(query)
        if not query_terms:
            return ""

        best_score = 0
        best_sentence = ""
        for item in evidence_items or []:
            evidence = dict(item or {})
            source_text = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in [
                        evidence.get("source_anchor"),
                        (evidence.get("metadata") or {}).get("section_path"),
                        (evidence.get("metadata") or {}).get("section"),
                    ]
                )
            )
            claim = _normalise_spaces(
                str(
                    evidence.get("claim")
                    or evidence.get("quote_span")
                    or evidence.get("raw_row_text")
                    or ""
                )
            )
            if not claim:
                continue
            haystack = f"{source_text} {claim}".lower()
            term_score = sum(1 for term in query_terms if term.lower() in haystack)
            if any(
                str(term) in source_text
                for term in (CALCULATION_NARRATIVE_POLICY.get("context_priority_section_terms") or ())
            ):
                term_score += 2
            if str(evidence.get("support_level") or "").lower() in {
                str(item).lower()
                for item in (CALCULATION_NARRATIVE_POLICY.get("context_support_levels") or ())
                if str(item)
            }:
                term_score += 1
            if term_score <= best_score:
                continue
            best_score = term_score
            best_sentence = claim

        if best_score <= 0 or not best_sentence:
            return ""
        split_sentences = _split_narrative_sentences(best_sentence)
        best_sentence = split_sentences[0] if split_sentences else best_sentence
        return best_sentence[:220].rstrip()

    def _include_narrative_context_if_needed(
        self,
        answer: str,
        *,
        query: str,
        narrative_context: str,
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        context = _normalise_spaces(str(narrative_context or ""))
        if not answer_text or not context or not _query_requests_narrative_context(query):
            return answer_text
        key_terms = [
            term
            for term in self._narrative_context_terms(query)
            if term not in {
                str(item)
                for item in (CALCULATION_NARRATIVE_POLICY.get("context_reuse_excluded_terms") or ())
                if str(item)
            }
        ]
        context_terms = [term for term in key_terms if term in context]
        if context_terms and any(term in answer_text for term in context_terms):
            return answer_text
        if context in answer_text:
            return answer_text
        return _normalise_spaces(f"{context} {answer_text}")

    def _policy_required_realized_snippet_from_doc(
        self,
        *,
        doc: Any,
        policy: Dict[str, Any],
    ) -> str:
        metadata = dict(getattr(doc, "metadata", {}) or {})
        required_terms = narrative_policy_terms([policy], "required_realized_terms")
        if not required_terms:
            return ""
        surface_parts = [
            str(metadata.get("table_value_labels_text") or ""),
            str(metadata.get("table_row_labels_text") or ""),
            str(metadata.get("table_summary_text") or ""),
            str(metadata.get("table_context") or ""),
            str(getattr(doc, "page_content", "") or ""),
        ]
        surface = _normalise_spaces(" ".join(part for part in surface_parts if part))
        if not surface:
            return ""
        lowered = surface.lower()
        matched_term = next((term for term in required_terms if term.lower() in lowered), "")
        if not matched_term:
            return ""
        term_index = lowered.find(matched_term.lower())
        window = surface[term_index : min(len(surface), term_index + 520)]
        unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
        numbers = re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?", window)
        numeric_values = [
            value
            for value in numbers
            if not re.fullmatch(r"20\d{2}", value)
            and not (re.fullmatch(r"\d+\)?", value) and len(value.strip("()")) <= 2)
        ]
        label_match = re.search(re.escape(matched_term) + r"(?:\([^)]*\))?", window)
        label = _normalise_spaces(label_match.group(0) if label_match else matched_term)
        footnote_suffix_pattern = str(
            CALCULATION_NARRATIVE_POLICY.get("policy_required_realized_footnote_suffix_pattern") or ""
        )
        if footnote_suffix_pattern:
            label = re.sub(footnote_suffix_pattern, "", label).strip() or matched_term
        if len(numeric_values) >= 2 and unit_hint:
            template = str(
                CALCULATION_NARRATIVE_POLICY.get("policy_required_realized_current_change_template") or ""
            )
            return _normalise_spaces(
                template.format(
                    label=label,
                    topic_particle=_topic_particle(label),
                    current_value=numeric_values[0],
                    change_value=numeric_values[1],
                    unit=unit_hint,
                )
            )
        if numeric_values and unit_hint:
            template = str(CALCULATION_NARRATIVE_POLICY.get("policy_required_realized_current_template") or "")
            return _normalise_spaces(
                template.format(
                    label=label,
                    topic_particle=_topic_particle(label),
                    current_value=numeric_values[0],
                    unit=unit_hint,
                )
            )
        for sentence in _split_narrative_sentences(surface):
            cleaned = _normalise_spaces(sentence)
            if matched_term.lower() in cleaned.lower() and re.search(r"\d", cleaned):
                return cleaned[:220].rstrip()
        return window[:220].rstrip()

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
                snippet = self._policy_required_realized_snippet_from_doc(doc=doc, policy=policy)
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
        if not any(self._row_is_narrative_summary(row) for row in ordered_results):
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
                if self._growth_row_has_conflicting_periods(row):
                    continue
                complete_answer = self._compose_complete_growth_numeric_answer(row, ordered_results)
                required_values = self._growth_required_display_values(row, ordered_results, evidence_items)
                if complete_answer and (cleaned in complete_answer or complete_answer in cleaned):
                    return True
                required_hits = [value for value in required_values if value and value in cleaned]
                if required_hits and not self._growth_sentence_has_untraced_material_numeric(
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
            if not self._row_is_narrative_summary(row_copy):
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

    def _preserve_retrieved_narrative_source_surface(
        self,
        answer: str,
        evidence_items: List[Dict[str, Any]],
    ) -> str:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text or not evidence_items:
            return answer_text
        answer_numeric_candidates = self._answer_evidence_numeric_candidates(answer_text)
        sentences = [_normalise_spaces(sentence) for sentence in _split_narrative_sentences(answer_text)]
        if not sentences:
            return answer_text

        def _content_terms(text: str) -> set[str]:
            return {
                term.lower()
                for term in self._narrative_context_terms(text)
                if len(term) >= 3
            }

        missing_markers = tuple(
            str(item)
            for item in (CALCULATION_NARRATIVE_POLICY.get("missing_answer_markers") or ())
            if str(item)
        )
        replacements: Dict[str, str] = {}
        for item in evidence_items or []:
            evidence = dict(item or {})
            evidence_id = str(evidence.get("evidence_id") or "").strip()
            if not evidence_id.startswith("retrieved_narrative::"):
                continue
            claim = _normalise_spaces(str(evidence.get("claim") or ""))
            quote = _normalise_spaces(str(evidence.get("quote_span") or evidence.get("raw_row_text") or ""))
            if not claim or not quote or claim == quote:
                continue
            if any(marker in claim for marker in missing_markers):
                continue
            claim_terms = _content_terms(claim)
            if not claim_terms:
                continue
            best_quote_sentence = ""
            best_score = 0
            for quote_sentence in _split_narrative_sentences(quote) or [quote]:
                quote_sentence = _normalise_spaces(quote_sentence)
                quote_terms = _content_terms(quote_sentence)
                if not quote_terms:
                    continue
                score = len(claim_terms & quote_terms)
                if score > best_score:
                    best_score = score
                    best_quote_sentence = quote_sentence
            if not best_quote_sentence:
                continue
            min_score = max(2, min(4, len(claim_terms) // 2 or 1))
            if best_score < min_score:
                continue
            for sentence in sentences:
                if not sentence or sentence in replacements:
                    continue
                if any(marker in sentence for marker in missing_markers):
                    continue
                if self._text_supports_final_answer_numeric_material(sentence, answer_numeric_candidates):
                    continue
                sentence_terms = _content_terms(sentence)
                if not sentence_terms:
                    continue
                if sentence == claim or len(sentence_terms & claim_terms) >= min_score:
                    replacements[sentence] = best_quote_sentence
                    break
        if not replacements:
            return answer_text
        return _normalise_spaces(" ".join(replacements.get(sentence, sentence) for sentence in sentences))

    def _answer_looks_truncated(self, answer: str) -> bool:
        answer_text = _normalise_spaces(str(answer or ""))
        if not answer_text:
            return True
        if re.search(r"(?:다|니다|요|음|임)[.!?。]?$", answer_text):
            return False
        if re.search(r"[.!?。]$", answer_text):
            return False
        return True

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
            if self._row_is_narrative_summary(row)
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
        query_terms = self._narrative_context_terms(query)
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

    def _narrative_row_focus_sentence(
        self,
        *,
        ordered_results: List[Dict[str, Any]],
        focus_variants: List[str],
    ) -> Optional[tuple[int, str, List[str]]]:
        if not focus_variants:
            return None
        for row in ordered_results or []:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family != "narrative_summary" and metric_family != "narrative_summary":
                continue
            claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
            narrative_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_narrative_markers") or ()))
            for sentence in _split_narrative_sentences(str(row.get("answer") or "")):
                cleaned = _normalise_spaces(sentence)
                if not cleaned:
                    continue
                if _narrative_sentence_looks_table_noisy(cleaned):
                    continue
                if _narrative_sentence_looks_abbreviated_fragment(cleaned, narrative_markers):
                    continue
                haystack = cleaned.lower()
                if any(variant.lower() in haystack for variant in focus_variants):
                    return (0, cleaned, claim_ids)
        return None

    def _answer_covers_narrative_context(self, answer: str, context: str) -> bool:
        answer_text = _normalise_spaces(str(answer or "")).lower()
        context_text = _normalise_spaces(str(context or ""))
        if not context_text:
            return True
        if context_text.lower() in answer_text:
            return True
        sentences = _split_narrative_sentences(context_text)
        for sentence in sentences:
            sentence_text = sentence.lower()
            if sentence_text in answer_text:
                continue
            tokens = [
                token.lower()
                for token in re.findall(r"[\w()]+", sentence, flags=re.UNICODE)
                if len(token) >= 3 and not re.fullmatch(r"\d+(?:\.\d+)?", token)
            ]
            if not tokens:
                return False
            covered = sum(1 for token in tokens if token in answer_text)
            if covered / max(len(tokens), 1) < 0.75:
                return False
        return True

    def _narrative_row_focus_context(
        self,
        *,
        query: str,
        ordered_results: List[Dict[str, Any]],
        focus_variants: List[str],
        max_sentences: int = 2,
    ) -> Optional[tuple[int, str, List[str]]]:
        if not focus_variants:
            return None
        query_terms = self._narrative_context_terms(query)
        impact_markers = tuple(str(item) for item in (CALCULATION_NARRATIVE_POLICY.get("growth_impact_markers") or ()))
        for row in ordered_results or []:
            operation_family = self._aggregate_result_operation_family(row)
            metric_family = _normalise_spaces(str(row.get("metric_family") or "")).lower()
            if operation_family != "narrative_summary" and metric_family != "narrative_summary":
                continue
            claim_ids = [str(value).strip() for value in (row.get("selected_claim_ids") or []) if str(value).strip()]
            sentences = [
                sentence
                for sentence in _split_narrative_sentences(str(row.get("answer") or ""))
                if not _narrative_sentence_looks_table_noisy(sentence)
                and not _narrative_sentence_looks_abbreviated_fragment(sentence, impact_markers)
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
        answer_is_truncated = self._answer_looks_truncated(existing_answer)

        growth_row: Optional[Dict[str, Any]] = None
        growth_slots: Dict[str, Any] = {}
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            if self._growth_row_has_conflicting_periods(row):
                continue
            calculation_result = dict(row.get("calculation_result") or {})
            answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
            primary_slot = dict(answer_slots.get("primary_value") or {})
            current_slot = dict(answer_slots.get("current_value") or {})
            prior_slot = dict(answer_slots.get("prior_value") or {})
            if not (
                self._answer_slot_has_material(primary_slot)
                and self._answer_slot_has_material(current_slot)
                and self._answer_slot_has_material(prior_slot)
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
                self._answer_covers_narrative_context(existing_answer_text, candidate_text)
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
        current_value = self._growth_slot_display_value(current_slot, ordered_results)
        prior_value = self._growth_slot_display_value(prior_slot, ordered_results)
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
        if self._growth_slots_share_material(current_slot, prior_slot, ordered_results):
            recovered_prior_material = self._recover_growth_prior_material_from_evidence(
                current_slot=current_slot,
                prior_slot=prior_slot,
                evidence_items=evidence_items,
            )
            if recovered_prior_material.get("display"):
                prior_value = recovered_prior_material["display"]
                prior_period = recovered_prior_material.get("period") or prior_period
        required_displays = self._growth_required_display_values(
            growth_row,
            ordered_results,
            evidence_items=evidence_items,
        )
        focus_variants = self._narrative_focus_variants(query)
        focus_required_variants = self._parenthetical_focus_variants(query) or focus_variants
        answer_has_focus = not focus_required_variants or any(
            variant.lower() in existing_answer_text.lower()
            for variant in focus_required_variants
        )
        row_focus_context = self._narrative_row_focus_context(
            query=query,
            ordered_results=ordered_results,
            focus_variants=focus_required_variants or focus_variants,
        )
        answer_has_row_context = not row_focus_context or self._answer_covers_narrative_context(
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
        if row_focus_context and not self._answer_covers_narrative_context(existing_answer_text, row_focus_context[1]):
            chosen_candidate = row_focus_context
        elif uncovered_focus_variants:
            parenthetical_variants = [
                variant
                for variant in self._parenthetical_focus_variants(query)
                if variant.lower() not in existing_context
            ]
            row_focus_candidate = self._narrative_row_focus_sentence(
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
            if self._growth_row_has_conflicting_periods(row):
                continue
            required_displays = self._growth_required_display_values(row, ordered_results)
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
            for term in self._narrative_context_terms(query_text)
            if term not in generic_terms and len(term) >= 2
        ]
        parenthetical_focus_terms = self._parenthetical_focus_variants(query_text)
        required_focus_terms = parenthetical_focus_terms or focus_terms
        if required_focus_terms and not any(term.lower() in answer_text.lower() for term in required_focus_terms):
            return False
        narrative_candidates = self._growth_narrative_sentence_candidates(
            query=query_text,
            ordered_results=ordered_results,
            evidence_items=list(evidence_items or []),
        )
        if narrative_candidates and not any(
            self._answer_covers_narrative_context(answer_text, candidate_text)
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
        row_focus_context = self._narrative_row_focus_context(
            query=query_text,
            ordered_results=ordered_results,
            focus_variants=required_focus_terms,
        )
        if row_focus_context and not self._answer_covers_narrative_context(answer_text, row_focus_context[1]):
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
        has_narrative_row = any(self._row_is_narrative_summary(row) for row in ordered_results or [])
        if not has_growth_row or not has_narrative_row:
            return answer_text

        required_values: List[str] = []
        for row in ordered_results or []:
            if self._aggregate_result_operation_family(row) != "growth_rate":
                continue
            required_values.extend(
                value
                for value in self._growth_required_display_values(
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

        focus_variants = [_normalise_spaces(str(item)) for item in self._narrative_focus_variants(query) if item]
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
                for term in self._narrative_context_terms(sentence)
                if len(term) >= 3
            }
            candidate_terms = {
                term.lower()
                for term in self._narrative_context_terms(candidate)
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
            if self._growth_sentence_has_untraced_material_numeric(
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
        if self._growth_answer_has_untraced_numeric_material(
            pruned_answer,
            ordered_results,
            evidence_items,
        ):
            return answer_text
        return pruned_answer

    def _coerce_operand_unit_from_evidence(
        self,
        *,
        raw_value: str,
        raw_unit: str,
        evidence_item: Optional[Dict[str, Any]],
    ) -> str:
        metadata = dict((evidence_item or {}).get("metadata") or {})
        unit_hint = str(metadata.get("unit_hint") or "").strip()
        current_unit = str(raw_unit or "").strip()
        surface_unit = self._infer_operand_unit_from_value_surface(
            raw_value=raw_value,
            evidence_item=evidence_item,
        )
        if surface_unit:
            surface_value, surface_family = _normalise_operand_value(raw_value or "1", surface_unit)
            current_value, current_family = _normalise_operand_value(raw_value or "1", current_unit)
            hint_value, hint_family = _normalise_operand_value(raw_value or "1", unit_hint)
            surface_family = _normalise_spaces(str(surface_family or "")).upper()
            current_family = _normalise_spaces(str(current_family or "")).upper()
            hint_family = _normalise_spaces(str(hint_family or "")).upper()
            known_current_family = current_unit and current_family and current_family != "UNKNOWN"
            known_hint_family = unit_hint and hint_family and hint_family != "UNKNOWN"
            known_surface_family = surface_family and surface_family != "UNKNOWN" and surface_value is not None
            if self._evidence_core_surface_contains_value_unit(
                raw_value=raw_value,
                raw_unit=surface_unit,
                evidence_item=evidence_item,
            ):
                if current_unit and _normalise_spaces(current_unit) == _normalise_spaces(surface_unit):
                    return current_unit
                return surface_unit
            if known_surface_family and (
                (known_current_family and current_value is not None and surface_family != current_family)
                or (known_hint_family and hint_value is not None and surface_family != hint_family)
            ):
                return current_unit or unit_hint
            return surface_unit
        if not unit_hint:
            return current_unit
        if not current_unit:
            return unit_hint
        normalized_current = _normalise_spaces(current_unit).lower()
        normalized_hint = _normalise_spaces(unit_hint).lower()
        if normalized_current == normalized_hint:
            return current_unit
        render_policy = dict(CALCULATION_RENDER_POLICY)
        bare_numeric_pattern = str(render_policy.get("operand_unit_bare_numeric_pattern") or "")
        bare_numeric = bool(bare_numeric_pattern and re.fullmatch(bare_numeric_pattern, str(raw_value or "").strip()))
        ambiguous_krw_units = {
            _normalise_spaces(str(item)).lower()
            for item in (render_policy.get("operand_unit_ambiguous_krw_units") or ())
            if str(item).strip()
        }
        krw_display_units = {
            _normalise_spaces(str(item)).lower()
            for item in (render_policy.get("krw_display_units") or ())
            if str(item).strip()
        }
        if bare_numeric and normalized_current in ambiguous_krw_units and normalized_hint in krw_display_units:
            return unit_hint
        return current_unit

    def _evidence_core_surface(
        self,
        evidence_item: Optional[Dict[str, Any]],
    ) -> str:
        return _normalise_spaces(
            " ".join(
                str((evidence_item or {}).get(key) or "")
                for key in ("claim", "quote_span", "raw_row_text")
            )
        )

    def _evidence_core_surface_contains_value_unit(
        self,
        *,
        raw_value: str,
        raw_unit: str,
        evidence_item: Optional[Dict[str, Any]],
    ) -> bool:
        value = _normalise_spaces(str(raw_value or ""))
        unit = _normalise_spaces(str(raw_unit or ""))
        surface = self._evidence_core_surface(evidence_item)
        if not value or not unit or not surface:
            return False
        compact_value = re.sub(r"[,\s()]", "", value)
        compact_unit = re.sub(r"\s+", "", unit)
        unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
        aliases = dict(unit_policy.get("inline_unit_aliases") or {})
        unit_pattern = str(unit_policy.get("inline_value_unit_pattern") or "")
        for match in re.finditer(unit_pattern, surface):
            if not _inline_unit_match_has_right_boundary(surface, match):
                continue
            matched_value = re.sub(r"[,\s()]", "", str(match.group("value") or ""))
            matched_unit = re.sub(r"\s+", "", str(match.group("unit") or ""))
            matched_unit = str(aliases.get(matched_unit) or matched_unit)
            if matched_value == compact_value and matched_unit == compact_unit:
                return True
        return False

    def _coerce_operand_period_from_evidence_surface(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        surface = self._evidence_core_surface(evidence_item)
        if not surface:
            return row
        explicit_years = list(dict.fromkeys(re.findall(r"20\d{2}", surface)))
        if len(explicit_years) != 1:
            return row
        evidence_year = explicit_years[0]
        period_years = set(re.findall(r"20\d{2}", str(row.get("period") or "")))
        if period_years and evidence_year in period_years:
            return row
        if period_years and evidence_year not in period_years:
            updated = dict(row)
            updated["period"] = evidence_year
            updated["period_source"] = "evidence_surface"
            return updated
        row_years = set(
            re.findall(
                r"20\d{2}",
                " ".join(
                    str(row.get(key) or "")
                    for key in ("period", "label", "matched_operand_label")
                ),
            )
        )
        if row_years and evidence_year in row_years:
            return row
        updated = dict(row)
        updated["period"] = evidence_year
        updated["period_source"] = "evidence_surface"
        return updated

    def _evidence_item_for_operand_row(
        self,
        row: Dict[str, Any],
        evidence_by_id: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        candidate_ids = _clean_source_row_ids([
            row.get("evidence_id"),
            row.get("source_row_id"),
            row.get("source_row_ids"),
        ])
        for candidate_id in [item for item in candidate_ids if item]:
            evidence_item = evidence_by_id.get(candidate_id)
            if evidence_item:
                return evidence_item
            evidence_item = evidence_by_id.get(f"recon::{candidate_id}")
            if evidence_item:
                return evidence_item
            if candidate_id.startswith("recon::"):
                evidence_item = evidence_by_id.get(candidate_id.removeprefix("recon::"))
                if evidence_item:
                    return evidence_item
        return None

    def _coerce_operand_row_from_evidence(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        updated = dict(row)
        preserve_dependency_unit = self._dependency_task_output_has_consistent_krw_unit(updated)
        raw_value = str(updated.get("raw_value") or "")
        if preserve_dependency_unit:
            coerced_unit = str(updated.get("raw_unit") or "")
        elif updated.get("unit_realigned_from_structured_provenance") and updated.get("normalized_value") is not None:
            coerced_unit = str(updated.get("raw_unit") or "")
        else:
            coerced_unit = self._coerce_operand_unit_from_evidence(
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
            updated = self._coerce_operand_period_from_evidence_surface(updated, evidence_item)
        updated = _coerce_lookup_magnitude_record(updated, evidence_item)
        if (
            updated.get("dependency_resolved")
            and str(updated.get("source_row_id") or "").startswith("task_output:")
            and updated.get("normalized_value") is not None
        ):
            return updated
        return self._refine_operand_precision_from_evidence_table(updated, evidence_item)

    def _infer_operand_unit_from_value_surface(
        self,
        *,
        raw_value: str,
        evidence_item: Optional[Dict[str, Any]],
    ) -> str:
        value = _normalise_spaces(str(raw_value or ""))
        if not value or not re.search(r"\d", value):
            return ""
        surfaces = [
            str((evidence_item or {}).get("claim") or ""),
            str((evidence_item or {}).get("quote_span") or ""),
            str((evidence_item or {}).get("raw_row_text") or ""),
            str((evidence_item or {}).get("source_context") or ""),
        ]
        surface = _normalise_spaces(" ".join(part for part in surfaces if part))
        if not surface:
            return ""
        aliases = dict(NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_unit_aliases") or {})
        render_policy = dict(CALCULATION_RENDER_POLICY)
        unit_candidates = [
            _normalise_spaces(str(item))
            for item in (
                tuple(render_policy.get("krw_display_units") or ())
                + tuple(render_policy.get("percent_display_units") or ())
                + tuple(render_policy.get("count_or_percent_normalized_units") or ())
            )
            if str(item).strip()
        ]
        value_pattern = re.escape(value)
        parenthetical_unit_pattern = (
            rf"{value_pattern}\s*\(?\s*"
            rf"(?P<surface_unit>{'|'.join(re.escape(unit) for unit in sorted(set(unit_candidates), key=len, reverse=True))})"
            rf"\s*\)?"
        )
        for match in re.finditer(parenthetical_unit_pattern, surface, flags=re.IGNORECASE):
            if not _inline_unit_match_has_right_boundary(surface, match, group_name="surface_unit"):
                continue
            unit_text = _normalise_spaces(str(match.group("surface_unit") or ""))
            if unit_text:
                return str(aliases.get(unit_text, unit_text))
        unit_pattern = str(
            NUMERIC_UNIT_NORMALIZATION_POLICY.get("inline_value_unit_pattern") or ""
        )
        if not unit_pattern:
            return ""
        compact_value = re.sub(r"[,\s()]", "", value)
        if not compact_value:
            return ""
        for match in re.finditer(unit_pattern, surface):
            if not _inline_unit_match_has_right_boundary(surface, match):
                continue
            matched_value = str(match.group("value") or "")
            matched_compact = re.sub(r"[,\s()]", "", matched_value)
            if matched_compact != compact_value:
                continue
            unit_text = _normalise_spaces(str(match.group("unit") or ""))
            return str(aliases.get(unit_text, unit_text))
        return ""

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
        def _cell_from_contextual_note_row() -> Optional[Dict[str, Any]]:
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

        def _cell_from_flattened_table_surface() -> Optional[Dict[str, Any]]:
            surface_text = _normalise_spaces(
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

        surface = _normalise_spaces(
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
        surface_value = _extract_numeric_value_after_operand_text(surface, operand_spec)
        if surface_value:
            surface_normalized, surface_unit = _normalise_operand_value(surface_value, "")
            if surface_normalized is not None and surface_unit == "KRW":
                target_values.append(float(surface_normalized))

        contextual_cell = _cell_from_contextual_note_row()
        flattened_cell = _cell_from_flattened_table_surface()
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

    def _surface_contract_numeric_evidence_items(
        self,
        evidence_items: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Keep prose evidence that directly names an ontology surface and a nearby number."""
        if not evidence_items or not required_operands:
            return []

        preserved: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for item in evidence_items:
            evidence = dict(item or {})
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in (
                        evidence.get("claim"),
                        evidence.get("quote_span"),
                        evidence.get("raw_row_text"),
                    )
                )
            )
            if not surface or not re.search(r"\d", surface):
                continue
            for operand in required_operands:
                operand_dict = dict(operand or {})
                if not _text_has_positive_surface(surface, operand_dict):
                    continue
                if _text_has_negative_surface(surface, operand_dict):
                    continue
                if not _extract_numeric_value_after_operand_text(surface, operand_dict):
                    continue
                key = str(evidence.get("evidence_id") or evidence.get("source_anchor") or surface[:120])
                if key in seen:
                    continue
                seen.add(key)
                preserved.append(evidence)
                break
        return preserved

    def _ratio_components_have_suspicious_scale(
        self,
        calculation_result: Dict[str, Any],
    ) -> bool:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        components_by_role = dict(answer_slots.get("components_by_role") or {})
        for entries in components_by_role.values():
            for entry in entries or []:
                raw_unit = _normalise_spaces(str((entry or {}).get("raw_unit") or "")).lower()
                raw_value = str((entry or {}).get("raw_value") or "").strip()
                if raw_unit not in {"원", "krw"}:
                    continue
                if not re.fullmatch(r"[\(\)\-]?\d[\d,]*(?:\.\d+)?", raw_value):
                    continue
                digit_count = len(re.sub(r"\D", "", raw_value))
                if digit_count >= 8:
                    return True
        return False

    def _ratio_result_has_suspicious_krw_scale(
        self,
        *,
        operation_family: str,
        ordered_operands: List[Dict[str, Any]],
        result_value: Optional[float],
        result_unit: str,
        source_normalized_unit: str,
    ) -> bool:
        if _normalise_spaces(operation_family).lower() != "ratio":
            return False
        if result_value is None:
            return False
        if _normalise_spaces(result_unit) not in {"%", "%p"}:
            return False
        render_policy = dict(CALCULATION_RENDER_POLICY)
        krw_unit = _normalise_spaces(str(render_policy.get("krw_normalized_unit") or "")).upper()
        if _normalise_spaces(source_normalized_unit).upper() != krw_unit:
            return False
        krw_operands = [
            row
            for row in ordered_operands
            if _normalise_spaces(str(row.get("normalized_unit") or "")).upper() == krw_unit
            and row.get("normalized_value") is not None
        ]
        if len(krw_operands) < 2:
            return False
        try:
            threshold = float(render_policy.get("ratio_krw_suspicious_percent_threshold") or 0.0)
            numeric_result = abs(float(result_value))
        except (TypeError, ValueError):
            return False
        return bool(threshold > 0 and numeric_result > threshold)

    def _align_ratio_operand_units_with_shared_table_context(
        self,
        ordered_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) < 2:
            return ordered_operands
        render_policy = dict(CALCULATION_RENDER_POLICY)
        krw_unit = str(render_policy.get("krw_normalized_unit") or "").strip().upper()
        if not krw_unit:
            return ordered_operands
        source_units = {
            _normalise_spaces(str(item or ""))
            for item in (render_policy.get("source_display_units") or ())
            if _normalise_spaces(str(item or ""))
        }
        scale_by_unit = {
            _normalise_spaces(str(unit or "")): float(scale)
            for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
            if _normalise_spaces(str(unit or ""))
        }
        eligible_units = {unit for unit in source_units if unit in scale_by_unit}
        if len(eligible_units) < 2:
            return ordered_operands

        def _context_key(row: Dict[str, Any]) -> tuple[str, ...]:
            table_id = _normalise_spaces(str(row.get("table_source_id") or row.get("source_table_id") or ""))
            if table_id:
                return ("table", table_id)
            source_section = _normalise_spaces(str(row.get("source_section") or ""))
            statement_type = _normalise_spaces(str(row.get("statement_type") or ""))
            consolidation_scope = _normalise_spaces(str(row.get("consolidation_scope") or ""))
            if source_section and statement_type and consolidation_scope:
                return ("section", source_section, statement_type, consolidation_scope)
            return ()

        grouped_indexes: Dict[tuple[str, ...], List[int]] = {}
        for index, row in enumerate(ordered_operands):
            if _normalise_spaces(str(row.get("normalized_unit") or "")).upper() != krw_unit:
                continue
            raw_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
            if raw_unit not in eligible_units:
                continue
            key = _context_key(row)
            if not key:
                continue
            grouped_indexes.setdefault(key, []).append(index)

        aligned = [dict(row) for row in ordered_operands]
        changed = False
        for indexes in grouped_indexes.values():
            if len(indexes) < 2:
                continue
            group_units = {
                _normalise_spaces(str(aligned[index].get("raw_unit") or ""))
                for index in indexes
                if _normalise_spaces(str(aligned[index].get("raw_unit") or "")) in eligible_units
            }
            if len(group_units) < 2:
                continue
            target_unit = max(group_units, key=lambda unit: scale_by_unit.get(unit, 0.0))
            for index in indexes:
                row = aligned[index]
                raw_value = str(row.get("raw_value") or "").strip()
                current_unit = _normalise_spaces(str(row.get("raw_unit") or ""))
                if not raw_value or current_unit == target_unit:
                    continue
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, target_unit)
                if normalized_value is None or _normalise_spaces(str(normalized_unit or "")).upper() != krw_unit:
                    continue
                row["original_raw_unit"] = row.get("original_raw_unit") or current_unit
                row["raw_unit"] = target_unit
                row["normalized_value"] = normalized_value
                row["normalized_unit"] = normalized_unit
                row["rendered_value"] = f"{raw_value}{target_unit}"
                row["ratio_unit_aligned_from_sibling_table"] = True
                changed = True
        return aligned if changed else ordered_operands

    def _repair_operand_normalization_from_rendered_unit(
        self,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = dict(row or {})
        raw_value = _normalise_spaces(str(updated.get("raw_value") or ""))
        rendered_value = _normalise_spaces(str(updated.get("rendered_value") or ""))
        if not raw_value or not rendered_value:
            return updated
        normalized_unit = _normalise_spaces(str(updated.get("normalized_unit") or "")).upper()
        krw_unit = _normalise_spaces(str(CALCULATION_RENDER_POLICY.get("krw_normalized_unit") or "")).upper()
        if normalized_unit and normalized_unit not in {krw_unit, "UNKNOWN"}:
            return updated

        inline_value, inline_unit = _normalise_operand_value(raw_value, "")
        if inline_value is not None and _normalise_spaces(str(inline_unit or "")).upper() == krw_unit:
            try:
                current_value = float(updated.get("normalized_value"))
            except (TypeError, ValueError):
                current_value = None
            if current_value is None or abs(current_value - float(inline_value)) > max(
                1e-6,
                abs(float(inline_value)) * 1e-9,
            ):
                unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
                unit_pattern = str(unit_policy.get("inline_value_unit_pattern") or "")
                inline_raw_unit = _normalise_spaces(str(updated.get("raw_unit") or ""))
                if unit_pattern:
                    match = re.fullmatch(unit_pattern, raw_value)
                    if match:
                        aliases = dict(unit_policy.get("inline_unit_aliases") or {})
                        matched_unit = re.sub(r"\s+", "", str(match.group("unit") or ""))
                        inline_raw_unit = _normalise_spaces(str(aliases.get(matched_unit) or matched_unit))
                updated["original_raw_unit"] = updated.get("original_raw_unit") or updated.get("raw_unit")
                updated["original_normalized_value"] = (
                    updated.get("original_normalized_value")
                    if updated.get("original_normalized_value") is not None
                    else updated.get("normalized_value")
                )
                if inline_raw_unit:
                    updated["raw_unit"] = inline_raw_unit
                updated["normalized_value"] = inline_value
                updated["normalized_unit"] = inline_unit
                updated["unit_repaired_from_rendered_value"] = True
                return updated

        unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
        unit_pattern = str(unit_policy.get("inline_value_unit_pattern") or "")
        if not unit_pattern:
            return updated
        aliases = dict(unit_policy.get("inline_unit_aliases") or {})
        krw_display_units = {
            _normalise_spaces(str(unit or ""))
            for unit in (CALCULATION_RENDER_POLICY.get("krw_display_units") or ())
            if _normalise_spaces(str(unit or ""))
        }
        compact_raw_value = re.sub(r"[,\s()]", "", raw_value)
        if not compact_raw_value:
            return updated

        current_value: Optional[float]
        try:
            current_value = float(updated.get("normalized_value"))
        except (TypeError, ValueError):
            current_value = None
        for match in re.finditer(unit_pattern, rendered_value):
            matched_raw = re.sub(r"[,\s()]", "", str(match.group("value") or ""))
            if matched_raw != compact_raw_value:
                continue
            rendered_unit = re.sub(r"\s+", "", str(match.group("unit") or ""))
            rendered_unit = _normalise_spaces(str(aliases.get(rendered_unit) or rendered_unit))
            if rendered_unit not in krw_display_units:
                continue
            repaired_value, repaired_unit = _normalise_operand_value(raw_value, rendered_unit)
            if repaired_value is None or _normalise_spaces(str(repaired_unit or "")).upper() != krw_unit:
                continue
            if current_value is not None and abs(current_value - float(repaired_value)) <= max(
                1e-6,
                abs(float(repaired_value)) * 1e-9,
            ):
                return updated
            updated["original_raw_unit"] = updated.get("original_raw_unit") or updated.get("raw_unit")
            updated["original_normalized_value"] = (
                updated.get("original_normalized_value")
                if updated.get("original_normalized_value") is not None
                else updated.get("normalized_value")
            )
            updated["raw_unit"] = rendered_unit
            updated["normalized_value"] = repaired_value
            updated["normalized_unit"] = repaired_unit
            updated["unit_repaired_from_rendered_value"] = True
            return updated
        return updated

    def _align_ratio_operands_with_sibling_table_context(
        self,
        ordered_operands: List[Dict[str, Any]],
        evidence_items: Optional[List[Dict[str, Any]]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) < 2:
            return ordered_operands
        evidence_pool = [dict(item) for item in (evidence_items or []) if isinstance(item, dict)]
        if not evidence_pool:
            return self._align_ratio_operand_units_with_shared_table_context(ordered_operands)
        evidence_by_id = self._evidence_items_by_id(evidence_pool)

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
            candidate_evidence = self._evidence_item_for_operand_row(slot, evidence_by_id)
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
                scope = self._known_consolidation_scope_value(other_row.get("consolidation_scope"))
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
            candidate_evidence = self._evidence_item_for_operand_row(candidate_slot, evidence_by_id)
            candidate_metadata = dict((candidate_evidence or {}).get("metadata") or {})
            candidate_scope = self._known_consolidation_scope_value(
                candidate_slot.get("consolidation_scope"),
                candidate_metadata.get("consolidation_scope"),
            )
            current_scope = self._known_consolidation_scope_value(current_row.get("consolidation_scope"))
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
                if not self._evidence_surface_contains_segment_label(segment_label, candidate_segment_surfaces):
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
            unit_aligned = self._align_ratio_operand_units_with_shared_table_context(aligned)
            return unit_aligned
        return self._align_ratio_operand_units_with_shared_table_context(ordered_operands)

    def _operand_row_source_id_set(self, row: Dict[str, Any]) -> set[str]:
        return {
            source_id
            for source_id in _clean_source_row_ids([
                row.get("evidence_id"),
                row.get("source_row_id"),
                row.get("source_row_ids"),
            ])
            if source_id
        }

    def _operand_row_value_differs(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_value = left.get("normalized_value")
        right_value = right.get("normalized_value")
        try:
            if left_value is not None and right_value is not None:
                return abs(float(left_value) - float(right_value)) > 1e-6
        except (TypeError, ValueError):
            pass
        left_raw = _normalise_spaces(str(left.get("raw_value") or ""))
        right_raw = _normalise_spaces(str(right.get("raw_value") or ""))
        if left_raw and right_raw:
            return left_raw != right_raw
        return left_value != right_value

    def _operand_row_values_materially_conflict(self, left: Dict[str, Any], right: Dict[str, Any]) -> bool:
        left_value = left.get("normalized_value")
        right_value = right.get("normalized_value")
        try:
            if left_value is not None and right_value is not None:
                left_float = float(left_value)
                right_float = float(right_value)
                tolerance = max(max(abs(left_float), abs(right_float), 1.0) * 5e-4, 1e-6)
                return abs(left_float - right_float) > tolerance
        except (TypeError, ValueError):
            pass
        return self._operand_row_value_differs(left, right)

    def _canonical_structured_reconciliation_id(self, value: Any) -> str:
        source_id = _normalise_spaces(str(value or ""))
        if not source_id.startswith("recon::"):
            return source_id
        stripped = source_id.removeprefix("recon::")
        if stripped and not stripped.endswith("::raw_row") and any(
            marker in stripped
            for marker in ("::value:", "::rowrec:", "::colrec:")
        ):
            return stripped
        return source_id

    def _canonicalize_structured_operand_reconciliation_refs(
        self,
        row: Dict[str, Any],
    ) -> Dict[str, Any]:
        updated = dict(row)
        for key in ("evidence_id", "source_row_id"):
            canonical = self._canonical_structured_reconciliation_id(updated.get(key))
            if canonical:
                updated[key] = canonical
        source_row_ids = _clean_source_row_ids(updated.get("source_row_ids") or [])
        canonical_source_ids = [
            self._canonical_structured_reconciliation_id(source_id)
            for source_id in source_row_ids
        ]
        canonical_source_ids = [source_id for source_id in canonical_source_ids if source_id]
        if canonical_source_ids:
            updated["source_row_ids"] = list(dict.fromkeys(canonical_source_ids))
        return updated

    def _task_output_operand_row_should_keep_value(
        self,
        row: Dict[str, Any],
        replacement: Dict[str, Any],
    ) -> bool:
        if not row.get("dependency_resolved"):
            return False
        if not _normalise_spaces(str(row.get("source_task_id") or "")):
            return False
        if not self._operand_row_value_differs(row, replacement):
            return False
        if not self._operand_row_values_materially_conflict(row, replacement):
            return False
        row_source_ids = self._operand_row_source_id_set(row)
        task_output_backed = any(source_id.startswith("task_output:") for source_id in row_source_ids)
        row_anchor = _normalise_spaces(str(row.get("source_anchor") or ""))
        replacement_anchor = _normalise_spaces(str(replacement.get("source_anchor") or ""))
        anchor_conflicts = bool(row_anchor and replacement_anchor and row_anchor != replacement_anchor)
        row_scope = self._known_consolidation_scope_value(row.get("consolidation_scope"))
        replacement_scope = self._known_consolidation_scope_value(replacement.get("consolidation_scope"))
        scope_conflicts = bool(row_scope and replacement_scope and row_scope != replacement_scope)
        if not (task_output_backed or anchor_conflicts or scope_conflicts):
            return False
        replacement_source_ids = self._operand_row_source_id_set(replacement)
        binding_policy = dict(row.get("binding_policy") or {})
        preferred_stages = {
            _normalise_spaces(str(item))
            for item in (binding_policy.get("prefer_aggregation_stages") or [])
            if _normalise_spaces(str(item))
        }
        if preferred_stages:
            replacement_stage = _normalise_spaces(str(replacement.get("aggregation_stage") or ""))
            if replacement_stage not in preferred_stages:
                return True
        if row_source_ids.intersection(replacement_source_ids) and not (anchor_conflicts or scope_conflicts):
            return False
        return True

    def _period_comparison_direct_rows_conflict_with_dependency_outputs(
        self,
        dependency_rows: List[Dict[str, Any]],
        direct_rows: List[Dict[str, Any]],
    ) -> bool:
        if not dependency_rows or not direct_rows:
            return False
        period_roles = {"current_period", "prior_period", "minuend", "subtrahend"}

        def _role(row: Dict[str, Any]) -> str:
            return _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()

        direct_by_role: Dict[str, List[Dict[str, Any]]] = {}
        for row in direct_rows:
            role = _role(row)
            if role in period_roles:
                direct_by_role.setdefault(role, []).append(dict(row))
        if not direct_by_role:
            return False

        for dependency_row in dependency_rows:
            role = _role(dependency_row)
            if role not in period_roles:
                continue
            for direct_row in direct_by_role.get(role, []):
                if self._task_output_operand_row_should_keep_value(dependency_row, direct_row):
                    return True
        return False

    def _align_dependency_rows_with_sibling_direct_context(
        self,
        dependency_rows: List[Dict[str, Any]],
        direct_rows: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not dependency_rows or len(direct_rows) < 2:
            return dependency_rows

        def _row_binding_key(row: Dict[str, Any]) -> tuple[str, str]:
            return (
                _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                _normalise_spaces(str(row.get("matched_operand_role") or "")),
            )

        def _context_key(row: Dict[str, Any]) -> str:
            return _normalise_spaces(
                str(row.get("table_source_id") or row.get("evidence_id") or row.get("source_row_id") or "")
            )

        context_roles: Dict[str, set[str]] = {}
        for row in direct_rows:
            key = _context_key(row)
            role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
            if not key or not role:
                continue
            context_roles.setdefault(key, set()).add(role)

        aligned: List[Dict[str, Any]] = []
        changed = False
        for dependency_row in dependency_rows:
            dep_key = _row_binding_key(dependency_row)
            if not any(dep_key):
                aligned.append(dependency_row)
                continue
            candidates = [
                dict(row)
                for row in direct_rows
                if _row_binding_key(row) == dep_key
                and _context_key(row)
                and len(context_roles.get(_context_key(row), set())) >= 2
            ]
            if not candidates:
                aligned.append(dependency_row)
                continue
            candidate = candidates[0]
            if not self._operand_row_value_differs(dependency_row, candidate):
                aligned.append(dependency_row)
                continue
            if self._task_output_operand_row_should_keep_value(dependency_row, candidate):
                aligned.append(
                    {
                        **dependency_row,
                        "sibling_table_context_realignment_blocked": True,
                        "sibling_table_context_realignment_blocked_reason": "task_output_value_provenance_mismatch",
                    }
                )
                changed = True
                continue
            aligned.append(
                {
                    **dependency_row,
                    "evidence_id": candidate.get("evidence_id") or dependency_row.get("evidence_id"),
                    "source_row_id": candidate.get("source_row_id") or candidate.get("evidence_id") or dependency_row.get("source_row_id"),
                    "source_row_ids": _clean_source_row_ids([
                        candidate.get("source_row_id"),
                        candidate.get("source_row_ids"),
                    ]),
                    "source_anchor": candidate.get("source_anchor") or dependency_row.get("source_anchor"),
                    "label": candidate.get("label") or dependency_row.get("label"),
                    "raw_value": candidate.get("raw_value"),
                    "raw_unit": candidate.get("raw_unit"),
                    "normalized_value": candidate.get("normalized_value"),
                    "normalized_unit": candidate.get("normalized_unit"),
                    "period": candidate.get("period") or dependency_row.get("period"),
                    "statement_type": candidate.get("statement_type") or dependency_row.get("statement_type"),
                    "consolidation_scope": candidate.get("consolidation_scope") or dependency_row.get("consolidation_scope"),
                    "table_source_id": candidate.get("table_source_id") or dependency_row.get("table_source_id"),
                    "sibling_table_context_realigned": True,
                }
            )
            changed = True
        return aligned if changed else dependency_rows

    def _prefer_complete_ratio_direct_context_rows(
        self,
        *,
        operand_rows: List[Dict[str, Any]],
        direct_rows: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if not operand_rows or not direct_rows or not required_operands:
            return operand_rows
        if _missing_required_operands(required_operands, direct_rows):
            return operand_rows

        def _row_key(row: Dict[str, Any]) -> tuple[str, str]:
            return (
                _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                _normalise_spaces(str(row.get("matched_operand_role") or "")),
            )

        direct_by_key = {
            _row_key(row): dict(row)
            for row in direct_rows
            if all(_row_key(row))
        }
        if not direct_by_key:
            return operand_rows

        def _context_key(row: Dict[str, Any]) -> tuple[str, str]:
            table_id = _normalise_spaces(str(row.get("table_source_id") or row.get("source_table_id") or ""))
            if table_id:
                return ("table", table_id)
            anchor = _normalise_spaces(str(row.get("source_anchor") or ""))
            if anchor:
                return ("anchor", anchor)
            return ("", "")

        direct_contexts = {
            _context_key(row)
            for row in direct_rows
            if any(_context_key(row))
        }
        direct_has_coherent_context = len(direct_contexts) == 1

        changed = False
        preferred: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        for row in operand_rows:
            row_key = _row_key(row)
            replacement = direct_by_key.get(row_key)
            if replacement and self._task_output_operand_row_should_keep_value(row, replacement):
                preferred.append(
                    {
                        **row,
                        "complete_ratio_direct_context_preference_blocked": True,
                        "complete_ratio_direct_context_preference_blocked_reason": "task_output_value_provenance_mismatch",
                    }
                )
                changed = True
                if all(row_key):
                    seen_keys.add(row_key)
                continue
            if replacement and (direct_has_coherent_context or bool(row.get("dependency_resolved"))):
                preferred.append(replacement)
                changed = True
            else:
                preferred.append(row)
            if all(row_key):
                seen_keys.add(row_key)

        for row_key, replacement in direct_by_key.items():
            if row_key in seen_keys:
                continue
            preferred.append(replacement)
            changed = True

        if not changed:
            return operand_rows
        return _merge_operand_rows(
            preferred,
            [],
            required_operands=required_operands,
        )

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
        for group_key, group_items in grouped_items.items():
            if len(group_items) < 2 and group_key[0] != "table":
                continue
            rows = self._build_required_operands_from_candidates(
                group_items,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
            )
            rows = self._filter_operand_rows_by_required_surface_contract(
                rows,
                group_items,
                required_operands,
                require_direct_support=True,
            )
            if _missing_required_operands(required_operands, rows):
                continue
            if self._ratio_operand_rows_collapse_to_same_slot(rows):
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
        query_terms = self._narrative_context_terms(query) if query_requests_narrative else []

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
                    slot_score = self._table_label_metadata_lookup_score(slot, item)
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
            if self._period_comparison_operand_rows_collapse_to_same_slot(rows):
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
                if not self._answer_slot_has_material(slot):
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
            planned = self._plan_formula_calculation(plan_state)
            planned_trace = _resolve_runtime_calculation_trace(planned, allow_legacy_top_level=False)
            plan = dict(planned_trace.get("calculation_plan") or {})
            if str(plan.get("status") or "").strip().lower() != "ok":
                updated_results.append(result_row)
                continue
            executed = self._execute_calculation(
                {
                    **plan_state,
                    "resolved_calculation_trace": {
                        "calculation_operands": context_rows,
                        "calculation_plan": plan,
                        "calculation_result": {},
                    },
                }
            )
            recalculated_trace = _resolve_runtime_calculation_trace(
                executed,
                allow_legacy_top_level=False,
            )
            recalculated_result = dict(recalculated_trace.get("calculation_result") or {})
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
                    "source_row_ids": list(recalculated_result.get("source_row_ids") or []),
                    "period_comparison_recovered_from_table_label_context": True,
                }
            )
            changed = True
        return updated_results if changed else ordered_results

    def _retrieval_context_docs(
        self,
        retrieved_docs: List[Any],
        seed_retrieved_docs: List[Any],
        *,
        seed_limit: int,
    ) -> List[Any]:
        context_docs = list(retrieved_docs or [])
        seen_doc_ids: set[str] = set()
        for doc_score in context_docs:
            doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
            metadata = dict(getattr(doc, "metadata", {}) or {})
            doc_id = _normalise_spaces(
                str(metadata.get("chunk_uid") or metadata.get("chunk_id") or getattr(doc, "id", "") or "")
            )
            if doc_id:
                seen_doc_ids.add(doc_id)
        for doc_score in list(seed_retrieved_docs or [])[:seed_limit]:
            doc = doc_score[0] if isinstance(doc_score, tuple) else doc_score
            metadata = dict(getattr(doc, "metadata", {}) or {})
            doc_id = _normalise_spaces(
                str(metadata.get("chunk_uid") or metadata.get("chunk_id") or getattr(doc, "id", "") or "")
            )
            if doc_id and doc_id in seen_doc_ids:
                continue
            if doc_id:
                seen_doc_ids.add(doc_id)
            context_docs.append(doc_score)
        return context_docs

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
            if report_year is not None:
                period_headers = [
                    [str(report_year), "current"],
                    [str(report_year - 1), "prior"],
                    [KOREAN_TABLE_CHANGE_HEADER_LABEL, "change"],
                ]
            else:
                period_headers = [["current"], ["prior"], ["change"]]

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
                for value_index, match in enumerate(pattern.finditer(value_labels)):
                    raw_value = _normalise_spaces(match.group("value"))
                    if not raw_value:
                        continue
                    raw_unit = unit_hint
                    value_is_percent = "%" in raw_value
                    if value_is_percent:
                        raw_unit = "%"
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

    def _align_growth_operand_units_when_raw_scale_matches(
        self,
        ordered_operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        if len(ordered_operands) != 2:
            return ordered_operands
        current_index = next(
            (
                index
                for index, row in enumerate(ordered_operands)
                if str(row.get("matched_operand_role") or "").strip() == "current_period"
            ),
            None,
        )
        prior_index = next(
            (
                index
                for index, row in enumerate(ordered_operands)
                if str(row.get("matched_operand_role") or "").strip() == "prior_period"
            ),
            None,
        )
        if current_index is None and prior_index is None:
            current_index, prior_index = 0, 1
        elif current_index is None and prior_index is not None:
            current_index = next((index for index in range(len(ordered_operands)) if index != prior_index), None)
        elif prior_index is None and current_index is not None:
            prior_index = next((index for index in range(len(ordered_operands)) if index != current_index), None)
        if current_index is None or prior_index is None or current_index == prior_index:
            return ordered_operands
        current_row = dict(ordered_operands[current_index])
        prior_row = dict(ordered_operands[prior_index])
        current_concept = _normalise_spaces(str(current_row.get("matched_operand_concept") or ""))
        prior_concept = _normalise_spaces(str(prior_row.get("matched_operand_concept") or ""))
        if current_concept and prior_concept and current_concept != prior_concept:
            return ordered_operands

        current_unit = _normalise_spaces(str(current_row.get("raw_unit") or ""))
        prior_unit = _normalise_spaces(str(prior_row.get("raw_unit") or ""))
        if not current_unit or not prior_unit or current_unit == prior_unit:
            return ordered_operands
        if str(current_row.get("normalized_unit") or "").upper() != "KRW":
            return ordered_operands
        if str(prior_row.get("normalized_unit") or "").upper() != "KRW":
            return ordered_operands

        current_raw_number = _parse_number_text(str(current_row.get("raw_value") or ""))
        prior_raw_number = _parse_number_text(str(prior_row.get("raw_value") or ""))
        current_normalized = current_row.get("normalized_value")
        prior_normalized = prior_row.get("normalized_value")
        if (
            current_raw_number is None
            or prior_raw_number is None
            or not current_raw_number
            or not prior_raw_number
            or current_normalized is None
            or prior_normalized is None
        ):
            return ordered_operands
        try:
            raw_ratio = abs(float(current_raw_number) / float(prior_raw_number))
            normalized_ratio = abs(float(current_normalized) / float(prior_normalized))
        except (TypeError, ValueError, ZeroDivisionError):
            return ordered_operands
        if raw_ratio <= 0 or normalized_ratio <= 0:
            return ordered_operands
        scale_distortion = max(raw_ratio, normalized_ratio) / min(raw_ratio, normalized_ratio)
        if not (0.01 <= raw_ratio <= 100.0 and scale_distortion >= 100.0):
            return ordered_operands

        aligned_prior_value, aligned_prior_unit = _normalise_operand_value(
            str(prior_row.get("raw_value") or ""),
            current_unit,
        )
        if aligned_prior_value is None or aligned_prior_unit != "KRW":
            return ordered_operands
        updated_prior = {
            **prior_row,
            "raw_unit": current_unit,
            "normalized_value": aligned_prior_value,
            "normalized_unit": aligned_prior_unit,
            "unit_alignment_source": "growth_raw_scale_match",
        }
        updated_rows = []
        for index, row in enumerate(ordered_operands):
            if index == prior_index:
                updated_rows.append(updated_prior)
            else:
                updated_rows.append(row)
        return updated_rows

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
        if not self._growth_slots_share_material(current_row, prior_row, []):
            return ordered_operands

        recovered = self._recover_growth_prior_material_from_evidence(
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

    def _growth_operand_periods_conflict(self, ordered_operands: List[Dict[str, Any]]) -> bool:
        if len(ordered_operands) != 2:
            return False
        current_row = next(
            (
                dict(row)
                for row in ordered_operands
                if str(row.get("matched_operand_role") or "").strip() == "current_period"
            ),
            None,
        )
        prior_row = next(
            (
                dict(row)
                for row in ordered_operands
                if str(row.get("matched_operand_role") or "").strip() == "prior_period"
            ),
            None,
        )
        if current_row is None or prior_row is None:
            return False
        current_period = self._period_match_key(str(current_row.get("period") or current_row.get("label") or ""))
        prior_period = self._period_match_key(str(prior_row.get("period") or prior_row.get("label") or ""))
        return bool(current_period and prior_period and current_period == prior_period)

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
            supported_answer = self._supported_aggregate_subtask_answer(nested_results)
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
        if operation_family == "ratio" and self._ratio_components_are_complete(calculation_result):
            if (
                self._aggregate_dependency_slot_coherence_rank_for_operands(
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

    def _numeric_candidates_with_spans_from_surface(
        self,
        surface: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        text = str(surface or "")
        if not text:
            return []
        render_policy = dict(CALCULATION_RENDER_POLICY)
        unit_scale = {
            str(unit): float(scale)
            for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
            if str(unit)
        }
        percent_units = [
            str(unit)
            for unit in (NUMERIC_UNIT_NORMALIZATION_POLICY.get("percent_units") or ())
            if str(unit)
        ]
        unit_terms = sorted([*unit_scale.keys(), *percent_units], key=len, reverse=True)
        unit_pattern = "|".join(re.escape(unit) for unit in unit_terms)
        pattern = re.compile(
            rf"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)(?:\s*(?P<unit>{unit_pattern}))?"
            if unit_pattern
            else r"(?P<value>\(?-?\d[\d,]*(?:\.\d+)?\)?)"
        )
        metadata = dict(metadata or {})
        context_unit = _normalise_spaces(str(metadata.get("unit_hint") or ""))
        if context_unit not in unit_scale:
            context_unit = next((unit for unit in unit_terms if unit in unit_scale and unit in text), "")
        candidates: List[Dict[str, Any]] = []
        for match in pattern.finditer(text):
            raw_value = match.group("value")
            parsed = _parse_number_text(raw_value)
            if parsed is None:
                continue
            unit = _normalise_spaces(str(match.groupdict().get("unit") or ""))
            digit_count = len(re.sub(r"\D", "", raw_value))
            if not unit and digit_count == 4 and 1900 <= abs(parsed) <= 2100:
                continue
            normalized_value = parsed
            normalized_unit = ""
            display_step = 1.0
            if unit in unit_scale:
                normalized_value = parsed * unit_scale[unit]
                normalized_unit = "KRW"
                display_step = unit_scale[unit]
            elif not unit and context_unit in unit_scale:
                if digit_count < 4 and "," not in raw_value:
                    continue
                normalized_value = parsed * unit_scale[context_unit]
                normalized_unit = "KRW"
                unit = context_unit
                display_step = unit_scale[context_unit]
            elif unit in percent_units:
                normalized_unit = "PERCENT"
            candidates.append(
                {
                    "kind": "currency" if normalized_unit == "KRW" else "percent" if normalized_unit == "PERCENT" else "generic",
                    "value": normalized_value,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "value_text": raw_value,
                    "unit": unit,
                    "unit_text": unit,
                    "display_step": display_step,
                    "span": [match.start("value"), match.end("value")],
                }
            )
        return candidates

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
                for term in self._narrative_context_terms(text)
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
                        *self._answer_evidence_numeric_candidates(surface),
                        *self._numeric_candidates_with_spans_from_surface(surface, metadata),
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
        rendered_value = self._format_ratio_percent_result(result_value)

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
        updated_trace["calculation_operands"] = self._updated_operands_from_slots(
            trace,
            role_updates,
        )
        updated_trace["calculation_result"] = updated_result
        return updated_trace

    def _updated_operands_from_slots(
        self,
        trace: Dict[str, Any],
        slot_by_role: Dict[str, Dict[str, Any]],
        *,
        normalize_role: bool = False,
    ) -> List[Dict[str, Any]]:
        updated_operands: List[Dict[str, Any]] = []
        for operand in list((trace or {}).get("calculation_operands") or []):
            row = dict(operand)
            role = str(row.get("matched_operand_role") or row.get("role") or "")
            if normalize_role:
                role = _normalise_spaces(role).lower()
            slot = slot_by_role.get(role)
            if slot:
                row.update(
                    {
                        "raw_value": slot.get("raw_value"),
                        "raw_unit": slot.get("raw_unit"),
                        "normalized_value": slot.get("normalized_value"),
                        "normalized_unit": slot.get("normalized_unit"),
                        "source_row_id": slot.get("source_row_id"),
                        "source_row_ids": slot.get("source_row_ids"),
                        "source_anchor": slot.get("source_anchor"),
                    }
                )
            updated_operands.append(row)
        return updated_operands

    def _runtime_evidence_rows_with_context_docs(self, state: FinancialAgentState) -> List[Dict[str, Any]]:
        evidence_rows = [
            dict(item)
            for item in [
                *list(state.get("evidence_items") or []),
                *list(state.get("runtime_evidence") or []),
            ]
            if isinstance(item, dict)
        ]
        context_docs = self._retrieval_context_docs(
            list(state.get("retrieved_docs") or []),
            list(state.get("seed_retrieved_docs") or []),
            seed_limit=8,
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
                dedupe_key = task_id or self._aggregate_result_signature(dict(row))
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
            aggregate_projection = self._sync_aggregate_projection_final_answer(
                aggregate_projection,
                refreshed_answer,
                sync_rendered_for_aggregate=True,
                status_ok=True,
            )
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
        updated_operands = self._updated_operands_from_slots(
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
    ) -> str:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        metric_label = _normalise_spaces(
            str(
                answer_slots.get("metric_label")
                or (state.get("active_subtask") or {}).get("metric_label")
                or (state.get("active_subtask") or {}).get("task_id")
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
        trace = _resolve_runtime_calculation_trace(dict(state), allow_legacy_top_level=False)
        scope = self._ratio_component_consolidation_scope(
            calculation_result,
            list(trace.get("calculation_operands") or []),
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
                    converted = self._format_calculation_value_in_display_unit(
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

    def _ratio_component_consolidation_scope(
        self,
        calculation_result: Dict[str, Any],
        operands: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        scopes: List[str] = []
        for entries in dict(answer_slots.get("components_by_group") or {}).values():
            for entry in entries or []:
                scope = _normalise_spaces(str((entry or {}).get("consolidation_scope") or ""))
                if scope in {"consolidated", "separate"} and scope not in scopes:
                    scopes.append(scope)
        for operand in operands or []:
            scope = _normalise_spaces(str((operand or {}).get("consolidation_scope") or ""))
            if scope in {"consolidated", "separate"} and scope not in scopes:
                scopes.append(scope)
        return scopes[0] if len(scopes) == 1 else ""

    def _ratio_components_collapse_to_same_slot(self, calculation_result: Dict[str, Any]) -> bool:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        components_by_group = dict(answer_slots.get("components_by_group") or {})
        numerator_slots = [dict(item) for item in list(components_by_group.get("numerator") or []) if isinstance(item, dict)]
        denominator_slots = [
            dict(item) for item in list(components_by_group.get("denominator") or []) if isinstance(item, dict)
        ]

        def _slot_identity(slot: Dict[str, Any]) -> tuple[str, str, str, str, str]:
            source_ids = "|".join(_clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]))
            normalized_value = slot.get("normalized_value")
            try:
                normalized_text = f"{float(normalized_value):.6f}" if normalized_value is not None else ""
            except (TypeError, ValueError):
                normalized_text = _normalise_spaces(str(normalized_value or ""))
            return (
                _normalise_spaces(str(slot.get("label") or "")),
                _normalise_spaces(str(slot.get("raw_value") or "")),
                _normalise_spaces(str(slot.get("raw_unit") or "")),
                normalized_text,
                source_ids,
            )

        if numerator_slots and denominator_slots:
            numerator_identities = {_slot_identity(slot) for slot in numerator_slots if self._answer_slot_has_material(slot)}
            denominator_identities = {_slot_identity(slot) for slot in denominator_slots if self._answer_slot_has_material(slot)}
            if numerator_identities and numerator_identities == denominator_identities:
                return True
            numerator_value_identities = {identity[1:] for identity in numerator_identities if identity[-1]}
            denominator_value_identities = {identity[1:] for identity in denominator_identities if identity[-1]}
            if numerator_value_identities and numerator_value_identities & denominator_value_identities:
                return True
        return False

    def _operand_row_groups_collapse_to_same_slot(self, role_groups: List[List[Dict[str, Any]]]) -> bool:
        if not all(role_groups):
            return False

        def _row_has_material(row: Dict[str, Any]) -> bool:
            return bool(
                _normalise_spaces(
                    str(row.get("raw_value") or row.get("normalized_value") or row.get("rendered_value") or "")
                )
            )

        def _row_identity(row: Dict[str, Any]) -> tuple[str, str, str]:
            source_ids = "|".join(
                _clean_source_row_ids([row.get("evidence_id"), row.get("source_row_id"), row.get("source_row_ids")])
            )
            normalized_value = row.get("normalized_value")
            try:
                normalized_text = f"{float(normalized_value):.6f}" if normalized_value is not None else ""
            except (TypeError, ValueError):
                normalized_text = _normalise_spaces(str(normalized_value or ""))
            raw_text = _normalise_spaces(str(row.get("raw_value") or row.get("rendered_value") or ""))
            return source_ids, normalized_text, raw_text

        left_identities = {_row_identity(row) for row in role_groups[0] if _row_has_material(row)}
        right_identities = {_row_identity(row) for row in role_groups[1] if _row_has_material(row)}
        if not left_identities or not right_identities:
            return False
        for source_ids, normalized_text, raw_text in left_identities:
            if not source_ids:
                continue
            if (source_ids, normalized_text, raw_text) in right_identities:
                return True
            if any(
                right_source_ids == source_ids
                and bool(normalized_text or raw_text)
                and (right_normalized == normalized_text or right_raw == raw_text)
                for right_source_ids, right_normalized, right_raw in right_identities
            ):
                return True
        return False

    def _ratio_operand_rows_collapse_to_same_slot(self, rows: List[Dict[str, Any]]) -> bool:
        return self._operand_row_groups_collapse_to_same_slot([
            [
                dict(row)
                for row in rows or []
                if _normalise_spaces(str((row or {}).get("matched_operand_role") or "")).startswith("numerator")
            ],
            [
                dict(row)
                for row in rows or []
                if _normalise_spaces(str((row or {}).get("matched_operand_role") or "")).startswith("denominator")
            ],
        ])

    def _period_comparison_operand_rows_collapse_to_same_slot(self, rows: List[Dict[str, Any]]) -> bool:
        return self._operand_row_groups_collapse_to_same_slot([
            [
                dict(row)
                for row in rows or []
                if _normalise_spaces(str((row or {}).get("matched_operand_role") or "")) in {"current_period", "minuend"}
            ],
            [
                dict(row)
                for row in rows or []
                if _normalise_spaces(str((row or {}).get("matched_operand_role") or "")) in {"prior_period", "subtrahend"}
            ],
        ])

    def _ratio_components_are_complete(self, calculation_result: Dict[str, Any]) -> bool:
        answer_slots = dict(calculation_result.get("answer_slots") or {})
        components_by_group = dict(answer_slots.get("components_by_group") or {})
        numerator_slots = [dict(item) for item in list(components_by_group.get("numerator") or []) if isinstance(item, dict)]
        denominator_slots = [
            dict(item) for item in list(components_by_group.get("denominator") or []) if isinstance(item, dict)
        ]

        def _slot_has_value(slot: Dict[str, Any]) -> bool:
            return bool(
                _normalise_spaces(
                    str(slot.get("rendered_value") or slot.get("raw_value") or slot.get("normalized_value") or "")
                )
            )

        if self._ratio_components_collapse_to_same_slot(calculation_result):
            return False

        return any(_slot_has_value(slot) for slot in numerator_slots) and any(
            _slot_has_value(slot) for slot in denominator_slots
        )

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

    def _ratio_query_requests_absolute_magnitude(self, query: str) -> bool:
        query_text = _normalise_spaces(str(query or "")).lower()
        markers = tuple(
            _normalise_spaces(str(marker or "")).lower()
            for marker in (CALCULATION_RENDER_POLICY.get("ratio_absolute_magnitude_markers") or ())
            if _normalise_spaces(str(marker or ""))
        )
        return bool(query_text and markers and any(marker in query_text for marker in markers))

    def _llm_lookup_operand_has_direct_support(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        """Reject lookup operands that are inferred from aggregate prose, not directly stated."""
        if not required_operands:
            return True

        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if not raw_value:
            return False

        matching_operand = next(
            (
                operand
                for operand in required_operands
                if _operand_row_matches_requirement(row, operand)
            ),
            None,
        )
        if matching_operand is None:
            return False

        binding_policy = dict(matching_operand.get("binding_policy") or {})
        requires_surface_contract = bool(
            binding_policy.get("require_surface_contract_for_direct_match")
            or binding_policy.get("require_surface_contract_for_direct_lookup")
        )
        if not evidence_item:
            return False if requires_surface_contract else bool(str(row.get("source_anchor") or "").strip())

        support_raw_value = raw_value
        unit_policy = dict(NUMERIC_UNIT_NORMALIZATION_POLICY)
        inline_unit_match = re.fullmatch(
            str(unit_policy.get("inline_value_unit_pattern") or ""),
            raw_value,
        )
        if inline_unit_match:
            support_raw_value = _normalise_spaces(str(inline_unit_match.group("value") or raw_value))
        raw_compact = re.sub(r"[\s,]", "", support_raw_value)
        if not raw_compact:
            return False

        def _text_supports_operand(text: str) -> bool:
            evidence_text = _normalise_spaces(text)
            if not evidence_text:
                return False
            surface_operand = matching_operand
            positive_surface_match = _text_has_positive_surface(evidence_text, surface_operand)
            if requires_surface_contract and not positive_surface_match:
                return False
            if not (positive_surface_match or _operand_text_match(evidence_text, surface_operand)):
                periodless_label = _normalise_spaces(
                    re.sub(
                        rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+",
                        "",
                        str(matching_operand.get("label") or ""),
                    )
                )
                if periodless_label and periodless_label != str(matching_operand.get("label") or ""):
                    surface_operand = dict(matching_operand)
                    surface_operand["label"] = periodless_label
                    positive_surface_match = _text_has_positive_surface(evidence_text, surface_operand)
            if requires_surface_contract and not positive_surface_match:
                return False
            if not (positive_surface_match or _operand_text_match(evidence_text, surface_operand)):
                return False
            if _text_has_negative_surface(evidence_text, surface_operand):
                return False
            for match in re.finditer(r"\(?-?\d[\d,]*(?:\.\d+)?\)?", evidence_text):
                if re.sub(r"[\s,]", "", match.group(0)) == raw_compact:
                    return True
            return False

        direct_text = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    evidence_item.get("claim"),
                    evidence_item.get("quote_span"),
                    evidence_item.get("raw_row_text"),
                )
            )
        )
        if direct_text:
            return _text_supports_operand(direct_text)

        source_context = _normalise_spaces(str(evidence_item.get("source_context") or ""))
        if source_context:
            if _text_supports_operand(source_context):
                return True
        return self._operand_row_has_direct_evidence_surface(row, evidence_item, matching_operand)

    def _operand_row_has_direct_evidence_surface(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
        operand: Dict[str, Any],
    ) -> bool:
        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        if not raw_value or not evidence_item:
            return False
        raw_compact = re.sub(r"[\s,()]", "", raw_value)
        if not raw_compact:
            return False

        metadata = dict(evidence_item.get("metadata") or {})
        surfaces: List[str] = []
        surfaces.extend(
            str(evidence_item.get(key) or "")
            for key in ("claim", "quote_span", "raw_row_text", "source_context")
        )
        surfaces.extend(
            str(metadata.get(key) or "")
            for key in (
                "row_text",
                "table_value_labels_text",
                "table_row_labels_text",
                "semantic_label",
                "row_label",
            )
        )

        def _append_record_surfaces(records: Any) -> None:
            for record in records if isinstance(records, list) else []:
                if not isinstance(record, dict):
                    continue
                label_parts = [
                    str(record.get("semantic_label") or ""),
                    str(record.get("row_label") or ""),
                    " ".join(str(item) for item in (record.get("row_headers") or [])),
                    " ".join(str(item) for item in (record.get("semantic_aliases") or [])),
                ]
                for cell in list(record.get("cells") or []):
                    if not isinstance(cell, dict):
                        continue
                    surfaces.append(
                        _normalise_spaces(
                            " ".join(
                                [
                                    *label_parts,
                                    " ".join(str(item) for item in (cell.get("column_headers") or [])),
                                    str(cell.get("value_text") or ""),
                                    str(cell.get("unit_hint") or ""),
                                ]
                            )
                        )
                    )
                value_text = str(record.get("value_text") or "")
                if value_text:
                    surfaces.append(_normalise_spaces(" ".join([*label_parts, value_text, str(record.get("unit_hint") or "")])))

        for key in ("table_row_records_json", "table_value_records_json"):
            payload = str(metadata.get(key) or "").strip()
            if not payload:
                continue
            try:
                records = json.loads(payload)
            except json.JSONDecodeError:
                continue
            _append_record_surfaces(records)

        table_object_payload = str(metadata.get("table_object_json") or "").strip()
        if table_object_payload:
            try:
                table_object = json.loads(table_object_payload)
            except json.JSONDecodeError:
                table_object = {}
            if isinstance(table_object, dict):
                _append_record_surfaces(table_object.get("rows") or [])
                _append_record_surfaces(table_object.get("values") or [])

        def _surface_supports_operand_value(surface: str) -> bool:
            normalized = _normalise_spaces(surface)
            if not normalized:
                return False
            lines = [normalized, *[_normalise_spaces(line) for line in normalized.splitlines()]]
            for line in lines:
                if not line:
                    continue
                if raw_compact not in re.sub(r"[\s,()]", "", line):
                    continue
                if _text_has_negative_surface(line, operand):
                    continue
                if _text_has_positive_surface(line, operand) or _operand_text_match(line, operand):
                    return True
            return False

        return any(_surface_supports_operand_value(surface) for surface in surfaces if surface)

    def _evidence_surface_contains_segment_label(
        self,
        segment_label: str,
        surfaces: Sequence[Any],
    ) -> bool:
        segment_variants = [
            _normalise_spaces(re.sub(r"^\W+|\W+$", " ", variant))
            for variant in _surface_match_variants(segment_label)
        ]
        segment_variants = list(dict.fromkeys(variant for variant in segment_variants if variant))
        if not segment_variants:
            return True

        affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
        scope_terms = [
            _normalise_spaces(str(term))
            for term in (affinity_policy.get("entity_surface_drop_terms") or ())
            if _normalise_spaces(str(term))
        ]
        for surface_value in surfaces:
            surface = _normalise_spaces(str(surface_value or ""))
            if not surface:
                continue
            for segment in segment_variants:
                escaped_segment = re.escape(segment)
                if re.search(rf"(?<!\w){escaped_segment}(?!\w)", surface):
                    return True
                for scope_term in scope_terms:
                    escaped_scope = re.escape(scope_term)
                    if re.search(rf"(?<!\w){escaped_segment}\s*{escaped_scope}(?!\w)", surface):
                        return True
        return False

    def _operand_row_satisfies_required_surface_contract(
        self,
        row: Dict[str, Any],
        evidence_by_id: Dict[str, Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
        *,
        require_direct_support: bool = False,
    ) -> bool:
        matching_operand = next(
            (
                operand
                for operand in required_operands
                if _operand_row_matches_requirement(row, operand)
            ),
            None,
        )
        if matching_operand is None:
            return False
        evidence_item = self._evidence_item_for_operand_row(row, evidence_by_id)
        segment_label = _normalise_spaces(
            str(
                _operand_segment_label(matching_operand)
                or dict(row.get("binding_policy") or {}).get("segment_label")
                or ""
            )
        )
        segment_label = _normalise_spaces(re.sub(r"^\W+|\W+$", " ", segment_label))
        if segment_label and evidence_item:
            metadata = dict(evidence_item.get("metadata") or {})
            segment_surfaces = (
                evidence_item.get("claim"),
                evidence_item.get("quote_span"),
                evidence_item.get("raw_row_text"),
                evidence_item.get("source_context"),
                metadata.get("semantic_label"),
                metadata.get("row_label"),
                metadata.get("aggregate_label"),
                metadata.get("table_header_context"),
                metadata.get("table_row_labels_text"),
                metadata.get("table_value_labels_text"),
            )
            if not self._evidence_surface_contains_segment_label(segment_label, segment_surfaces):
                return False
        binding_policy = dict(matching_operand.get("binding_policy") or {})
        requires_surface_contract = bool(
            binding_policy.get("require_surface_contract_for_direct_match")
            or binding_policy.get("require_surface_contract_for_direct_lookup")
        )
        if not requires_surface_contract and not require_direct_support:
            return True
        if requires_surface_contract:
            return self._llm_lookup_operand_has_direct_support(row, evidence_item, [matching_operand])
        if not evidence_item:
            return True
        return self._operand_row_has_direct_evidence_surface(row, evidence_item, matching_operand)

    def _filter_operand_rows_by_required_surface_contract(
        self,
        rows: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
        *,
        require_direct_support: bool = False,
    ) -> List[Dict[str, Any]]:
        if not rows or not required_operands:
            return rows
        evidence_by_id = self._evidence_items_by_id(evidence_items)
        return [
            row
            for row in rows
            if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
            and self._operand_row_satisfies_required_surface_contract(
                row,
                evidence_by_id,
                required_operands,
                require_direct_support=require_direct_support,
            )
        ]

    def _lookup_task_requests_context_dependent_scope(
        self,
        state: FinancialAgentState,
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        markers = tuple(
            _normalise_spaces(str(item)).lower()
            for item in (scoring_policy.get("context_dependent_lookup_scope_markers") or ())
            if _normalise_spaces(str(item))
        )
        if not markers:
            return False
        active_subtask = dict(state.get("active_subtask") or {})
        text_parts: List[str] = [
            str(state.get("query") or ""),
            str(active_subtask.get("query") or ""),
            str(active_subtask.get("metric_label") or ""),
        ]
        for operand in required_operands:
            operand_data = dict(operand or {})
            binding_policy = dict(operand_data.get("binding_policy") or {})
            constraints = dict(operand_data.get("constraints") or {})
            text_parts.extend(
                str(value or "")
                for value in (
                    operand_data.get("label"),
                    operand_data.get("concept"),
                    binding_policy.get("segment_label"),
                    binding_policy.get("entity_label"),
                    constraints.get("segment_scope"),
                )
            )
            text_parts.extend(str(alias or "") for alias in (operand_data.get("aliases") or []))
        task_text = _normalise_spaces(" ".join(text_parts)).lower()
        return any(marker in task_text for marker in markers)

    def _lookup_direct_row_is_ambiguous_context_table(
        self,
        row: Dict[str, Any],
        evidence_item: Optional[Dict[str, Any]],
        *,
        state: FinancialAgentState,
        required_operands: List[Dict[str, Any]],
    ) -> bool:
        if self._lookup_task_requests_context_dependent_scope(state, required_operands):
            return False
        if not evidence_item:
            return False
        metadata = dict(evidence_item.get("metadata") or {})
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        context_table_views = {
            _normalise_spaces(str(item)).lower()
            for item in (scoring_policy.get("context_dependent_table_views") or ())
            if _normalise_spaces(str(item))
        }
        table_view = _normalise_spaces(str(metadata.get("table_view") or "")).lower()
        if context_table_views and table_view not in context_table_views:
            return False
        try:
            min_cell_count = int(scoring_policy.get("ambiguous_lookup_min_structured_cells") or 4)
        except (TypeError, ValueError):
            min_cell_count = 4
        try:
            min_header_count = int(scoring_policy.get("ambiguous_lookup_min_distinct_column_headers") or 3)
        except (TypeError, ValueError):
            min_header_count = 3
        structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
        if len(structured_cells) < min_cell_count:
            return False
        scope_markers = tuple(
            _normalise_spaces(str(item)).lower()
            for item in (scoring_policy.get("context_dependent_lookup_scope_markers") or ())
            if _normalise_spaces(str(item))
        )
        distinct_context_headers: set[str] = set()
        for cell in structured_cells:
            headers = [
                _normalise_spaces(str(header)).lower()
                for header in (cell.get("column_headers") or [])
                if _normalise_spaces(str(header))
            ]
            header_text = " ".join(headers)
            if not header_text:
                continue
            if scope_markers and not any(marker in header_text for marker in scope_markers):
                continue
            distinct_context_headers.add(header_text)
        if len(distinct_context_headers) >= min_header_count:
            return True
        raw_surface = _normalise_spaces(
            " ".join(
                str(value or "")
                for value in (
                    row.get("source_context"),
                    evidence_item.get("source_context"),
                    evidence_item.get("claim"),
                    evidence_item.get("quote_span"),
                    metadata.get("table_header_context"),
                )
            )
        ).lower()
        return bool(scope_markers and any(marker in raw_surface for marker in scope_markers))

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
    ) -> Optional[Dict[str, Any]]:
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        if operation_family not in {"difference", "growth_rate"}:
            return None

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if not required_operands:
            return None

        matched_rows: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        for operand in required_operands:
            matched_row = next((row for row in operands if _operand_row_matches_requirement(row, operand)), None)
            if matched_row is None:
                return None
            matched_rows.append((operand, matched_row))

        def _first_pair(role: str) -> Optional[tuple[Dict[str, Any], Dict[str, Any]]]:
            for operand, row in matched_rows:
                if str(operand.get("role") or "").strip() == role:
                    return operand, row
            return None

        ordered_pairs: List[tuple[Dict[str, Any], Dict[str, Any]]] = []
        if operation_family == "difference":
            left_pair = _first_pair("current_period") or _first_pair("minuend") or _first_pair("numerator")
            right_pair = _first_pair("prior_period") or _first_pair("subtrahend") or _first_pair("denominator")
            if left_pair and right_pair:
                ordered_pairs = [left_pair, right_pair]
            elif len(matched_rows) == 2:
                ordered_pairs = matched_rows
        else:
            current_pair = _first_pair("current_period")
            prior_pair = _first_pair("prior_period")
            if current_pair and prior_pair:
                ordered_pairs = [current_pair, prior_pair]

        if len(ordered_pairs) != 2:
            return None

        variable_bindings: List[Dict[str, str]] = []
        ordered_operand_ids: List[str] = []
        ordered_labels: List[str] = []
        for index, (operand, row) in enumerate(ordered_pairs):
            operand_id = str(row.get("operand_id") or "").strip()
            if not operand_id:
                return None
            variable_bindings.append({"variable": chr(ord("A") + index), "operand_id": operand_id})
            ordered_operand_ids.append(operand_id)
            ordered_labels.append(str(operand.get("label") or row.get("label") or "").strip())

        metric_label = str(active_subtask.get("metric_label") or active_subtask.get("task_id") or "").strip()
        if operation_family == "difference":
            result_unit = ""
            if _should_coerce_percent_point_unit(self._calc_query(state), operands, {"operation": "subtract"}):
                result_unit = "%p"
            right_role = str(ordered_pairs[1][0].get("role") or "").strip()
            right_value = ordered_pairs[1][1].get("normalized_value")
            formula = "A - B"
            operation_text = f"{ordered_labels[0]} - {ordered_labels[1]}"
            explanation = f"{metric_label or 'difference'} is computed as A - B."
            if right_role in {"subtrahend", "denominator"} and right_value is not None and float(right_value) < 0:
                formula = "A + B"
                operation_text = f"{ordered_labels[0]} + {ordered_labels[1]}"
                explanation = f"{metric_label or 'difference'} uses sign-aware subtraction because B is already negative."
            return {
                "status": "ok",
                "mode": "single_value",
                "operation": "subtract",
                "ordered_operand_ids": ordered_operand_ids,
                "variable_bindings": variable_bindings,
                "formula": formula,
                "pairwise_formula": "",
                "result_unit": result_unit,
                "operation_text": operation_text,
                "explanation": explanation,
                "missing_info": [],
            }

        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "growth_rate",
            "ordered_operand_ids": ordered_operand_ids,
            "variable_bindings": variable_bindings,
            "formula": "((A - B) / B) * 100",
            "pairwise_formula": "",
            "result_unit": "%",
            "operation_text": f"({ordered_labels[0]} - {ordered_labels[1]}) / {ordered_labels[1]} * 100",
            "explanation": f"{metric_label or 'growth rate'} is computed as ((A - B) / B) * 100.",
            "missing_info": [],
        }

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

        def evidence_conflicts_requested_scope(item: Dict[str, Any]) -> bool:
            return _evidence_item_conflicts_requested_scope(item, desired_consolidation_scope)

        def operand_conflicts_requested_scope(row: Dict[str, Any]) -> bool:
            if desired_consolidation_scope == "unknown":
                return False
            scope = _normalise_spaces(str(row.get("consolidation_scope") or "unknown"))
            if scope == desired_consolidation_scope:
                return False
            if desired_consolidation_scope == "consolidated":
                return scope == "separate"
            if desired_consolidation_scope == "separate":
                return scope == "consolidated"
            return False

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
                include_compatibility_mirrors=False,
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
        surface_contract_evidence = self._surface_contract_numeric_evidence_items(
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
            evidence_by_id = self._evidence_items_by_id(evidence_items)
            direct_structured_rows = [
                self._coerce_operand_row_from_evidence(
                    row,
                    self._evidence_item_for_operand_row(row, evidence_by_id),
                )
                for row in direct_structured_rows
            ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not operand_conflicts_requested_scope(row)
            ]
        direct_target_evidence_pool = [
            dict(item)
            for item in list(evidence_items) + [dict(item) for item in (state.get("runtime_evidence") or []) if isinstance(item, dict)]
            if isinstance(item, dict) and not evidence_conflicts_requested_scope(dict(item))
        ]
        if retrieved_docs or seed_retrieved_docs:
            target_context_docs = self._retrieval_context_docs(
                retrieved_docs,
                seed_retrieved_docs,
                seed_limit=48,
            )
            direct_target_evidence_pool.extend(
                item
                for item in self._ratio_operand_context_evidence_from_docs(target_context_docs, max_docs=48)
                if not evidence_conflicts_requested_scope(item)
            )
        target_metric_row, target_metric_operand = self._direct_target_metric_operand_from_evidence(
            {
                **dict(state),
                "active_subtask": active_subtask,
            },
            direct_target_evidence_pool,
        )
        if target_metric_row and not operand_conflicts_requested_scope(target_metric_row):
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
        if direct_structured_rows and required_operands:
            evidence_by_id = self._evidence_items_by_id(evidence_items)
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
                and self._operand_row_satisfies_required_surface_contract(
                    row,
                    evidence_by_id,
                    required_operands,
                    require_direct_support=operation_family == "ratio",
                )
            ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not self._lookup_direct_row_is_ambiguous_context_table(
                    row,
                    self._evidence_item_for_operand_row(row, evidence_by_id),
                    state=state,
                    required_operands=required_operands,
                )
            ]
        if direct_structured_rows and operation_family in {"lookup", "single_value"}:
            evidence_by_id = self._evidence_items_by_id(evidence_items)
            if required_operands:
                direct_structured_rows = [
                    row
                    for row in direct_structured_rows
                    if self._llm_lookup_operand_has_direct_support(
                        row,
                        self._evidence_item_for_operand_row(row, evidence_by_id),
                        required_operands,
                    )
                ]
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not self._lookup_direct_row_is_ambiguous_context_table(
                    row,
                    self._evidence_item_for_operand_row(row, evidence_by_id),
                    state=state,
                    required_operands=required_operands,
                )
            ]
        if direct_structured_rows and required_operands and operation_family in {"lookup", "single_value"}:
            direct_structured_rows = self._prefer_direct_structured_lookup_evidence_rows(
                direct_structured_rows,
                evidence_items=self._evidence_items_with_runtime(evidence_items, state),
                required_operands=required_operands,
                operation_family=operation_family,
                state=state,
            )
        if direct_structured_rows and required_operands and operation_family == "ratio":
            direct_structured_rows = self._prefer_direct_structured_evidence_rows(
                direct_structured_rows,
                evidence_items=self._evidence_items_with_runtime(evidence_items, state),
                required_operands=required_operands,
                operation_family=operation_family,
                state=state,
            )
        dependency_state = self._dependency_binding_resolution_state(state)
        dependency_rows = list(dependency_state.get("rows") or [])
        dependency_bindings = list(dependency_state.get("bindings") or [])
        dependency_resolved_keys = set(dependency_state.get("resolved_keys") or set())
        missing_dependency_bindings = list(dependency_state.get("missing_bindings") or [])
        rejected_dependency_scope_rows: List[Dict[str, Any]] = []
        retry_strategy = self._active_retry_strategy(state)
        synthesis_only_retry = (
            retry_strategy == "synthesize_from_task_outputs"
            and self._task_prefers_sibling_output_synthesis(state)
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
        required_prefers_aggregate_stage = any(
            bool(dict(row.get("binding_policy") or {}).get("prefer_aggregation_stages"))
            for row in required_operands
        )
        def _rows_have_single_table_context(rows: List[Dict[str, Any]]) -> bool:
            contexts = {
                _normalise_spaces(
                    str(row.get("table_source_id") or row.get("source_table_id") or row.get("source_anchor") or "")
                )
                for row in rows
                if _normalise_spaces(
                    str(row.get("table_source_id") or row.get("source_table_id") or row.get("source_anchor") or "")
                )
            }
            return len(contexts) == 1

        direct_rows_have_coherent_context = bool(
            direct_rows_cover_required_operands
            and _rows_have_single_table_context(direct_structured_rows)
            and not self._ratio_operand_rows_collapse_to_same_slot(direct_structured_rows)
            and not self._period_comparison_operand_rows_collapse_to_same_slot(direct_structured_rows)
        )
        if operation_family in {"difference", "growth_rate"} and required_operands:
            period_context_evidence = list(evidence_items)
            if retrieved_docs or seed_retrieved_docs:
                period_context_docs = self._retrieval_context_docs(
                    retrieved_docs,
                    seed_retrieved_docs,
                    seed_limit=48,
                )
                period_context_evidence.extend(
                    item
                    for item in self._ratio_operand_context_evidence_from_docs(period_context_docs, max_docs=64)
                    if not evidence_conflicts_requested_scope(item)
                )
            period_context_rows = self._build_period_comparison_operands_from_table_label_context(
                period_context_evidence,
                required_operands=required_operands,
                query=query,
                operation_family=operation_family,
            )
            if period_context_rows:
                direct_structured_rows = _merge_operand_rows(
                    period_context_rows,
                    direct_structured_rows,
                    required_operands=required_operands,
                )
                direct_rows_cover_required_operands = not _missing_required_operands(
                    required_operands,
                    direct_structured_rows,
                )
                direct_rows_have_coherent_context = bool(
                    direct_rows_cover_required_operands
                    and _rows_have_single_table_context(direct_structured_rows)
                    and not self._ratio_operand_rows_collapse_to_same_slot(direct_structured_rows)
                    and not self._period_comparison_operand_rows_collapse_to_same_slot(direct_structured_rows)
                )
                used_period_evidence_ids = {
                    str(row.get("evidence_id") or "")
                    for row in period_context_rows
                    if str(row.get("evidence_id") or "").strip()
                }
                existing_evidence_ids = {
                    str(item.get("evidence_id") or "")
                    for item in evidence_items
                    if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
                }
                evidence_items = evidence_items + [
                    item
                    for item in period_context_evidence
                    if str(item.get("evidence_id") or "") in used_period_evidence_ids
                    and str(item.get("evidence_id") or "") not in existing_evidence_ids
                ]
                logger.info("[calc_operands] coherent period-comparison table-label rows=%s", len(period_context_rows))
        if operation_family == "ratio" and required_operands and (
            (direct_rows_cover_required_operands and not direct_rows_have_coherent_context)
            or dependency_rows_cover_required_operands
        ):
            ratio_context_docs = self._retrieval_context_docs(
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
                direct_structured_rows = _merge_operand_rows(
                    coherent_ratio_rows,
                    direct_structured_rows,
                    required_operands=required_operands,
                )
                used_context_evidence_ids = {
                    str(row.get("evidence_id") or "")
                    for row in coherent_ratio_rows
                    if str(row.get("evidence_id") or "").strip()
                }
                existing_evidence_ids = {
                    str(item.get("evidence_id") or "")
                    for item in evidence_items
                    if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
                }
                evidence_items = evidence_items + [
                    item
                    for item in ratio_context_evidence
                    if str(item.get("evidence_id") or "") in used_context_evidence_ids
                    and str(item.get("evidence_id") or "") not in existing_evidence_ids
                ]
                logger.info("[calc_operands] coherent ratio context rows=%s", len(coherent_ratio_rows))
                direct_rows_cover_required_operands = not _missing_required_operands(
                    required_operands,
                    direct_structured_rows,
                )
        direct_period_context_conflicts_with_dependency = bool(
            operation_family in {"difference", "growth_rate"}
            and dependency_rows_cover_required_operands
            and direct_rows_cover_required_operands
            and direct_rows_have_coherent_context
            and not reconciliation_evidence
            and self._period_comparison_direct_rows_conflict_with_dependency_outputs(
                dependency_rows,
                direct_structured_rows,
            )
        )
        prefer_direct_rows_over_dependency = bool(
            operation_family in {"ratio", "difference", "growth_rate"}
            and direct_rows_cover_required_operands
            and (
                reconciliation_evidence
                or (
                    operation_family in {"difference", "growth_rate"}
                    and direct_rows_have_coherent_context
                )
            )
            and not (
                operation_family == "ratio"
                and dependency_rows_cover_required_operands
                and required_prefers_aggregate_stage
            )
            and not direct_period_context_conflicts_with_dependency
        )
        if dependency_rows:
            if operation_family == "ratio":
                dependency_rows = self._align_dependency_rows_with_sibling_direct_context(
                    dependency_rows,
                    direct_structured_rows,
                )
            if prefer_direct_rows_over_dependency:
                direct_structured_rows = _merge_operand_rows(
                    direct_structured_rows,
                    dependency_rows,
                    required_operands=required_operands,
                )
            else:
                direct_structured_rows = _merge_operand_rows(
                    dependency_rows,
                    direct_structured_rows,
                    required_operands=required_operands,
                )
            direct_structured_rows = [
                row
                for row in direct_structured_rows
                if not operand_conflicts_requested_scope(row)
            ]
            logger.info("[calc_operands] dependency task-output operands=%s", len(dependency_rows))
        if dependency_bindings and direct_structured_rows and not prefer_direct_rows_over_dependency:
            direct_structured_rows, rejected_resolved_dependency_scope_rows = self._filter_direct_rows_by_dependency_producer_scope(
                state,
                bindings=dependency_bindings,
                operand_rows=direct_structured_rows,
            )
            rejected_dependency_scope_rows.extend(rejected_resolved_dependency_scope_rows)
        if missing_dependency_bindings and direct_structured_rows and not prefer_direct_rows_over_dependency:
            direct_structured_rows, rejected_missing_dependency_scope_rows = self._filter_direct_rows_by_dependency_producer_scope(
                state,
                bindings=missing_dependency_bindings,
                operand_rows=direct_structured_rows,
            )
            rejected_dependency_scope_rows.extend(rejected_missing_dependency_scope_rows)
        dependency_binding_keys = set(dependency_state.get("binding_keys") or set())
        direct_dependency_fill_allowed = operation_family in {"difference", "growth_rate"} or prefer_direct_rows_over_dependency
        if dependency_binding_keys and direct_structured_rows:
            duplicate_guard_keys = dependency_resolved_keys
            if prefer_direct_rows_over_dependency:
                duplicate_guard_keys = set()
            if not direct_dependency_fill_allowed:
                duplicate_guard_keys = dependency_binding_keys
            filtered_rows: List[Dict[str, Any]] = []
            for row in direct_structured_rows:
                if bool(row.get("dependency_resolved")):
                    filtered_rows.append(row)
                    continue
                row_key = (
                    _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
                    _normalise_spaces(str(row.get("matched_operand_role") or "")),
                )
                if row_key in duplicate_guard_keys:
                    continue
                filtered_rows.append(row)
            direct_structured_rows = filtered_rows
        if direct_dependency_fill_allowed and missing_dependency_bindings and direct_structured_rows:
            direct_resolved_keys = self._direct_rows_resolved_dependency_keys(
                missing_dependency_bindings,
                direct_structured_rows,
            )
            if direct_resolved_keys:
                missing_dependency_bindings = [
                    dict(binding)
                    for binding in missing_dependency_bindings
                    if self._dependency_binding_identity(binding) not in direct_resolved_keys
                ]
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
                    include_compatibility_mirrors=False,
                ),
            }
        if direct_structured_rows:
            direct_structured_rows = [
                self._canonicalize_structured_operand_reconciliation_refs(row)
                for row in direct_structured_rows
            ]
        # If reconciliation already found every required operand as clean
        # structured rows, skip the broader fallback path entirely.
        if direct_structured_rows and (
            not required_operands or len(direct_structured_rows) >= len(required_operands)
        ):
            logger.info("[calc_operands] structured-row direct operands=%s", len(direct_structured_rows))
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifacts = self._enrich_reconciliation_artifact_refs(
                artifacts,
                task_id=task_id,
                operand_rows=direct_structured_rows,
            )
            artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                status="ok",
                summary=f"{len(direct_structured_rows)} structured operand(s)",
                payload={"calculation_operands": direct_structured_rows, "source": "structured_row_direct"},
                evidence_refs=[str(row.get("evidence_id") or "") for row in direct_structured_rows if str(row.get("evidence_id") or "").strip()],
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
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
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=direct_structured_rows,
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
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
                artifacts = list(state.get("artifacts") or [])
                tasks = list(state.get("tasks") or [])
                task_id = str(active_subtask.get("task_id") or "calc")
                artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
                artifacts = _append_artifact(
                    artifacts,
                    artifact_id=artifact_id,
                    task_id=task_id,
                    kind=ArtifactKind.OPERAND_SET,
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
                tasks = _upsert_task(
                    tasks,
                    task_id=task_id,
                    kind=TaskKind.CALCULATION,
                    label=str(active_subtask.get("metric_label") or task_id),
                    status=TaskStatus.IN_PROGRESS,
                    query=self._calc_query(state),
                    metric_family=self._calc_metric_family(state),
                    artifact_id=artifact_id,
                )
                updates = {"tasks": tasks, "artifacts": artifacts}
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
                    include_compatibility_mirrors=False,
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
            candidate_docs = list(retrieved_docs)
            seen_candidate_doc_ids = {
                str((getattr(doc, "metadata", {}) or {}).get("chunk_uid") or (getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                for doc, _score in candidate_docs
            }
            for doc, score in seed_retrieved_docs:
                metadata = dict(getattr(doc, "metadata", {}) or {})
                doc_id = str(metadata.get("chunk_uid") or metadata.get("chunk_id") or "")
                if doc_id and doc_id in seen_candidate_doc_ids:
                    continue
                if doc_id:
                    seen_candidate_doc_ids.add(doc_id)
                candidate_docs.append((doc, score))
            synthesized_items: List[Dict[str, Any]] = []
            synthesized_bullets: List[str] = []
            seen_anchors = {str(item.get("source_anchor") or "") for item in evidence_items}

            def _required_operand_context_terms() -> List[str]:
                terms: List[str] = []
                for operand in required_operands:
                    for needle in _operand_needles(operand):
                        normalized = _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", needle))
                        if not normalized:
                            continue
                        terms.append(normalized)
                        tokens = normalized.split()
                        if len(tokens) >= 2:
                            terms.append(" ".join(tokens[:-1]))
                expanded: List[str] = []
                for term in terms:
                    expanded.append(term)
                    if re.search(r"[가-힣]", term) and " " in term:
                        expanded.append(re.sub(r"\s+", "", term))
                return list(dict.fromkeys(item for item in expanded if item))

            def _text_has_any_context_term(text: str, terms: List[str]) -> bool:
                normalized = _normalise_spaces(text)
                compact = re.sub(r"\s+", "", normalized)
                return any(
                    term in normalized or re.sub(r"\s+", "", term) in compact
                    for term in terms
                    if term
                )

            def _synthesized_doc_item(
                doc: Any,
                *,
                index: int,
                evidence_id: str,
            ) -> Optional[Dict[str, Any]]:
                metadata = dict(getattr(doc, "metadata", {}) or {})
                anchor = self._build_source_anchor(metadata)
                text = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
                if not text:
                    return None
                display_text = _strip_rerank_metadata(text) or text
                provisional_item = {"metadata": metadata, "source_anchor": anchor, "claim": text}
                if evidence_conflicts_requested_scope(provisional_item):
                    return None
                claim = display_text[:1200]
                return {
                    "evidence_id": evidence_id,
                    "source_anchor": anchor,
                    "claim": claim,
                    "quote_span": claim[:240],
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [],
                    "metadata": metadata,
                    "_candidate_index": index,
                }

            if required_operands:
                operand_probe_items: List[Dict[str, Any]] = []
                for candidate_index, (doc, _score) in enumerate(candidate_docs, start=1):
                    full_text = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
                    full_text = _strip_rerank_metadata(full_text) or full_text
                    item = _synthesized_doc_item(
                        doc,
                        index=candidate_index,
                        evidence_id=f"ev_operand_doc_{candidate_index:03d}",
                    )
                    if item:
                        probe_item = dict(item)
                        probe_item["claim"] = full_text
                        probe_item["raw_row_text"] = full_text
                        operand_probe_items.append(probe_item)
                operand_probe_rows = self._build_required_operands_from_candidates(
                    operand_probe_items,
                    required_operands=required_operands,
                    query=query,
                    topic=topic,
                    report_scope=report_scope,
                )
                operand_evidence_ids = {
                    str(row.get("evidence_id") or "")
                    for row in operand_probe_rows
                    if row.get("evidence_id")
                }
                if operand_evidence_ids:
                    max_operand_docs = max(4, len(required_operands) * 2)
                    for item in operand_probe_items:
                        if str(item.get("evidence_id") or "") not in operand_evidence_ids:
                            continue
                        anchor = str(item.get("source_anchor") or "")
                        claim = str(item.get("claim") or "")
                        missing_terms: List[str] = []
                        for binding in missing_dependency_bindings:
                            missing_terms.extend(_operand_needles(dict(binding)))
                            label = _normalise_spaces(str(binding.get("label") or ""))
                            if label:
                                missing_terms.append(label)
                        missing_terms.extend(_required_operand_context_terms())
                        missing_terms = [term for term in dict.fromkeys(missing_terms) if term]
                        duplicate_anchor_has_missing_term = bool(
                            anchor in seen_anchors
                            and missing_terms
                            and _text_has_any_context_term(claim, missing_terms)
                        )
                        if anchor in seen_anchors and not duplicate_anchor_has_missing_term:
                            continue
                        evidence_item = dict(item)
                        evidence_item.pop("raw_row_text", None)
                        evidence_item.pop("_candidate_index", None)
                        evidence_item["claim"] = claim[:1200]
                        evidence_item["quote_span"] = claim[:240]
                        evidence_item["raw_row_text"] = claim
                        synthesized_items.append(evidence_item)
                        synthesized_bullets.append(f"- {anchor} {claim[:180]} (direct)")
                        seen_anchors.add(anchor)
                        if len(
                            [
                                existing
                                for existing in synthesized_items
                                if str(existing.get("evidence_id") or "").startswith("ev_operand_doc_")
                            ]
                        ) >= max_operand_docs:
                            break

            percent_point_query = _is_percent_point_difference_query(query)
            ratio_row_candidates = self._extract_ratio_row_candidates(candidate_docs, query, topic)
            if ratio_row_candidates:
                logger.info("[calc_operands] ratio row fallback candidates=%s", len(ratio_row_candidates))
                synthesized_items.extend(ratio_row_candidates)
                synthesized_bullets.extend(
                    f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                    for item in ratio_row_candidates
                )
                seen_anchors.update(str(item.get("source_anchor") or "") for item in ratio_row_candidates)
            if not percent_point_query:
                component_candidates = self._extract_ratio_component_candidates(candidate_docs, query, topic)
                if component_candidates:
                    logger.info("[calc_operands] ratio component fallback candidates=%s", len(component_candidates))
                    synthesized_items.extend(component_candidates)
                    synthesized_bullets.extend(
                        f"- {item['source_anchor']} {item.get('source_context', '')} {str(item.get('raw_row_text') or '')[:180]} (direct)"
                        for item in component_candidates
                    )
                    seen_anchors.update(str(item.get("source_anchor") or "") for item in component_candidates)
            doc_fallback_limit = 16 if missing_dependency_bindings else 8
            for index, (doc, _score) in enumerate(candidate_docs[: min(doc_fallback_limit, len(candidate_docs))], start=1):
                item = _synthesized_doc_item(doc, index=index, evidence_id=f"ev_doc_{index:03d}")
                if not item:
                    continue
                metadata = dict(item.get("metadata") or {})
                anchor = str(item.get("source_anchor") or "")
                text = str(item.get("claim") or "")
                missing_terms: List[str] = []
                for binding in missing_dependency_bindings:
                    missing_terms.extend(_operand_needles(dict(binding)))
                    label = _normalise_spaces(str(binding.get("label") or ""))
                    if label:
                        missing_terms.append(label)
                missing_terms.extend(_required_operand_context_terms())
                missing_terms = [term for term in dict.fromkeys(missing_terms) if term]
                duplicate_anchor_has_missing_term = bool(
                    anchor in seen_anchors
                    and missing_terms
                    and _text_has_any_context_term(text, missing_terms)
                )
                if anchor in seen_anchors and not duplicate_anchor_has_missing_term:
                    continue
                item.pop("_candidate_index", None)
                synthesized_items.append(item)
                synthesized_bullets.append(f"- {anchor} {text[:180]} (direct)")
            if synthesized_items:
                evidence_items = evidence_items + synthesized_items
                evidence_bullets = evidence_bullets + synthesized_bullets
                logger.info(
                    "[calc_operands] augmenting evidence with synthesized retrieved_docs=%s existing=%s",
                    len(synthesized_items),
                    len(state.get("evidence_items", []) or []),
                )
        elif direct_numeric_grounding and (retrieved_docs or seed_retrieved_docs) and (not evidence_items or evidence_status != "sufficient"):
            logger.info("[calc_operands] direct numeric task skips generic retrieved-doc augmentation")
        if not evidence_items:
            return empty_result

        deterministic_required_rows: List[Dict[str, Any]] = []
        if required_operands and not direct_numeric_grounding:
            deterministic_required_rows = self._build_required_operands_from_candidates(
                evidence_items,
                required_operands=required_operands,
                query=query,
                topic=topic,
                report_scope=report_scope,
            )
            deterministic_required_rows = self._filter_operand_rows_by_required_surface_contract(
                deterministic_required_rows,
                evidence_items,
                required_operands,
                require_direct_support=operation_family == "ratio",
            )
            if missing_dependency_bindings and deterministic_required_rows:
                deterministic_required_rows, rejected_rows = self._filter_direct_rows_by_dependency_producer_scope(
                    state,
                    bindings=missing_dependency_bindings,
                    operand_rows=deterministic_required_rows,
                )
                rejected_dependency_scope_rows.extend(rejected_rows)
            if deterministic_required_rows:
                if operation_family == "ratio":
                    coherent_required_rows = self._build_complete_ratio_operands_from_coherent_context(
                        evidence_items,
                        required_operands=required_operands,
                        query=query,
                        topic=topic,
                        report_scope=report_scope,
                    )
                    if coherent_required_rows:
                        deterministic_required_rows = _merge_operand_rows(
                            coherent_required_rows,
                            deterministic_required_rows,
                            required_operands=required_operands,
                        )
                deterministic_rows_cover_required = not _missing_required_operands(
                    required_operands,
                    deterministic_required_rows,
                )
                if operation_family == "ratio" and deterministic_rows_cover_required:
                    direct_structured_rows = _merge_operand_rows(
                        deterministic_required_rows,
                        direct_structured_rows,
                        required_operands=required_operands,
                    )
                else:
                    direct_structured_rows = _merge_operand_rows(
                        direct_structured_rows,
                        deterministic_required_rows,
                        required_operands=required_operands,
                    )
                logger.info(
                    "[calc_operands] deterministic required-operand rows=%s",
                    len(deterministic_required_rows),
                )

        structured_llm = self._llm_for_phase("operand_extraction").with_structured_output(OperandExtraction)
        evidence_text = self._format_evidence_for_prompt(evidence_items, evidence_bullets)
        prompt = ChatPromptTemplate.from_template(
            str(CALCULATION_PROMPT_POLICY.get("operand_extraction_prompt_template") or "")
        )
        try:
            extracted: OperandExtraction = (prompt | structured_llm).invoke(
                {"query": query, "evidence": evidence_text}
            )
            operand_rows: List[Dict[str, Any]] = []
            evidence_by_id = self._evidence_items_by_id(evidence_items)
            for index, item in enumerate(extracted.operands, start=1):
                row = item.model_dump()
                evidence_item = evidence_by_id.get(str(row.get("evidence_id") or "").strip())
                if evidence_item and evidence_conflicts_requested_scope(evidence_item):
                    continue
                row["operand_id"] = f"op_{index:03d}"
                row = self._coerce_operand_row_from_evidence(row, evidence_item)
                if operation_family in {"lookup", "single_value"} and required_operands:
                    if not self._llm_lookup_operand_has_direct_support(row, evidence_item, required_operands):
                        continue
                operand_rows.append(row)
            if required_operands:
                operand_rows = [
                    row
                    for row in operand_rows
                    if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
                    and self._operand_row_satisfies_required_surface_contract(
                        row,
                        evidence_by_id,
                        required_operands,
                        require_direct_support=operation_family == "ratio",
                    )
                ]
            if operation_family in {"lookup", "single_value"} and required_operands:
                operand_rows = [
                    row
                    for row in operand_rows
                    if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
                ]
            if direct_structured_rows and required_operands:
                operand_rows = _merge_operand_rows(
                    direct_structured_rows,
                    operand_rows,
                    required_operands=required_operands,
                )

            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and surface_contract_evidence:
                surface_fallback_rows = self._build_required_operands_from_candidates(
                    surface_contract_evidence,
                    required_operands=missing_required,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                surface_fallback_rows = self._filter_operand_rows_by_required_surface_contract(
                    surface_fallback_rows,
                    surface_contract_evidence,
                    missing_required,
                    require_direct_support=operation_family == "ratio",
                )
                if surface_fallback_rows:
                    logger.info("[calc_operands] surface-contract operand fallback rows=%s", len(surface_fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        surface_fallback_rows,
                        required_operands=required_operands,
                    )
                    missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and not direct_numeric_grounding:
                generic_fallback_rows = self._build_required_operands_from_candidates(
                    evidence_items,
                    required_operands=missing_required,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                generic_fallback_rows = self._filter_operand_rows_by_required_surface_contract(
                    generic_fallback_rows,
                    evidence_items,
                    missing_required,
                    require_direct_support=operation_family == "ratio",
                )
                if generic_fallback_rows:
                    logger.info("[calc_operands] generic operand fallback rows=%s", len(generic_fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        generic_fallback_rows,
                        required_operands=required_operands,
                    )
            missing_required = _missing_required_operands(required_operands, operand_rows) if required_operands else []
            if missing_required and not direct_numeric_grounding and _is_ratio_percent_query(query):
                fallback_rows = self._build_ratio_operands_from_candidates(
                    [item for item in evidence_items if item.get("raw_row_text")],
                    query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if fallback_rows:
                    logger.info("[calc_operands] python ratio fallback operands=%s", len(fallback_rows))
                    operand_rows = _merge_operand_rows(
                        operand_rows,
                        fallback_rows,
                        required_operands=required_operands,
                    )
            if operation_family == "ratio" and required_operands and operand_rows:
                sibling_context_rows = self._build_required_operands_from_candidates(
                    evidence_items,
                    required_operands=required_operands,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                sibling_context_rows = self._filter_operand_rows_by_required_surface_contract(
                    sibling_context_rows,
                    evidence_items,
                    required_operands,
                    require_direct_support=True,
                )
                coherent_context_rows = self._build_complete_ratio_operands_from_coherent_context(
                    evidence_items,
                    required_operands=required_operands,
                    query=query,
                    topic=state.get("topic") or "",
                    report_scope=dict(state.get("report_scope") or {}),
                )
                if coherent_context_rows:
                    sibling_context_rows = _merge_operand_rows(
                        coherent_context_rows,
                        sibling_context_rows,
                        required_operands=required_operands,
                    )
                if sibling_context_rows:
                    operand_rows = self._align_dependency_rows_with_sibling_direct_context(
                        operand_rows,
                        sibling_context_rows,
                    )
                    operand_rows = self._prefer_complete_ratio_direct_context_rows(
                        operand_rows=operand_rows,
                        direct_rows=sibling_context_rows,
                        required_operands=required_operands,
                    )
            if _is_percent_point_difference_query(query):
                operand_rows = [
                    row for row in operand_rows
                    if str(row.get("normalized_unit") or "") == "PERCENT" and row.get("normalized_value") is not None
                ]
                logger.info("[calc_operands] percent-diff operand filtering retained=%s", len(operand_rows))
            preserved_operand_source = ""
            if not operand_rows:
                if direct_structured_rows:
                    operand_rows = [dict(row) for row in direct_structured_rows]
                    preserved_operand_source = "structured_rows"
                elif dependency_rows:
                    operand_rows = [dict(row) for row in dependency_rows]
                    preserved_operand_source = "dependency_outputs"
                if preserved_operand_source:
                    logger.info(
                        "[calc_operands] preserved %s fallback operands from %s",
                        len(operand_rows),
                        preserved_operand_source,
                    )
            merged_coverage = extracted.coverage
            if direct_structured_rows and operand_rows and required_operands:
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
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifacts = self._enrich_reconciliation_artifact_refs(
                artifacts,
                task_id=task_id,
                operand_rows=operand_rows,
            )
            artifact_id = f"operands:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.OPERAND_SET,
                status=str(merged_coverage),
                summary=f"{len(operand_rows)} operand(s) from llm/fallback extraction",
                payload={"calculation_operands": operand_rows, "coverage": merged_coverage},
                evidence_refs=[str(row.get("evidence_id") or "") for row in operand_rows if str(row.get("evidence_id") or "").strip()],
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
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
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operand_rows,
                    calculation_plan={},
                    calculation_result={},
                    include_compatibility_mirrors=False,
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
                    include_compatibility_mirrors=False,
                ),
            }

    def _operation_plan_guard(
        self,
        *,
        plan: Dict[str, Any],
        operands: List[Dict[str, Any]],
        required_operands: List[Dict[str, Any]],
        operation_family: str,
    ) -> Optional[Dict[str, Any]]:
        """Reject executable plans that do not bind distinct required roles."""
        family = str(operation_family or plan.get("operation") or "").strip().lower()
        if family not in {"ratio", "difference", "growth_rate"}:
            return None

        operand_by_id = {
            str(row.get("operand_id") or "").strip(): row
            for row in operands
            if str(row.get("operand_id") or "").strip()
        }
        ordered_ids = [
            str(operand_id or "").strip()
            for operand_id in (plan.get("ordered_operand_ids") or [])
            if str(operand_id or "").strip() in operand_by_id
        ]
        if not ordered_ids:
            ordered_ids = [
                str(binding.get("operand_id") or "").strip()
                for binding in (plan.get("variable_bindings") or [])
                if str(binding.get("operand_id") or "").strip() in operand_by_id
            ]
        unique_ids = list(dict.fromkeys(ordered_ids))
        missing_info: List[str] = []

        if len(unique_ids) < 2:
            missing_info.append("distinct_operands")

        selected_rows = [operand_by_id[operand_id] for operand_id in unique_ids]
        if family == "ratio" and required_operands:
            missing_required = _missing_required_operands(required_operands, selected_rows)
            missing_info.extend(
                _normalise_spaces(str(item.get("label") or item.get("role") or item.get("concept") or "operand"))
                for item in missing_required
            )

        if family == "ratio":
            numerator_ids: set[str] = set()
            denominator_ids: set[str] = set()
            ratio_requirements = [
                dict(item)
                for item in required_operands
                if str(item.get("role") or "").strip().startswith(("numerator", "denominator"))
            ]
            for row in selected_rows:
                operand_id = str(row.get("operand_id") or "").strip()
                row_role = str(row.get("matched_operand_role") or "").strip()
                if row_role.startswith("numerator"):
                    numerator_ids.add(operand_id)
                elif row_role.startswith("denominator"):
                    denominator_ids.add(operand_id)
                elif ratio_requirements:
                    for requirement in ratio_requirements:
                        role = str(requirement.get("role") or "").strip()
                        if _operand_row_matches_requirement(row, requirement):
                            if role.startswith("numerator"):
                                numerator_ids.add(operand_id)
                            elif role.startswith("denominator"):
                                denominator_ids.add(operand_id)

            if not numerator_ids:
                missing_info.append("numerator")
            if not denominator_ids:
                missing_info.append("denominator")
            if numerator_ids and denominator_ids and not (numerator_ids - denominator_ids or denominator_ids - numerator_ids):
                missing_info.append("distinct_ratio_roles")
            if self._ratio_operand_rows_collapse_to_same_slot(selected_rows):
                missing_info.append("distinct_ratio_roles")

        if not missing_info:
            return None

        missing_info = list(dict.fromkeys(item for item in missing_info if item))
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
            "explanation": "operation plan does not satisfy required operand bindings",
            "missing_info": missing_info,
        }

    def _plan_formula_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Translate normalized operands into an executable calculation plan."""
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
                    include_compatibility_mirrors=False,
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
                        include_compatibility_mirrors=False,
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
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str(active_subtask.get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(deterministic_lookup_plan.get("status") or "ok"),
                summary=f"mode={deterministic_lookup_plan.get('mode')} op={deterministic_lookup_plan.get('operation')}",
                payload={"calculation_plan": deterministic_lookup_plan},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str(active_subtask.get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
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
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_lookup_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }

        deterministic_operation_plan = self._build_deterministic_operation_plan(state, operands)
        if deterministic_operation_plan:
            guarded_plan = self._operation_plan_guard(
                plan=deterministic_operation_plan,
                operands=operands,
                required_operands=required_operands,
                operation_family=operation_family,
            )
            if guarded_plan:
                return {
                    "missing_info": list(guarded_plan.get("missing_info") or []),
                    "planner_debug_trace": {
                        "active_metric_family": metric_key,
                        "ontology_context": "deterministic_operation_plan_guard",
                        "llm_invoked": False,
                        "guard_applied": True,
                        "reason": "invalid_required_operand_bindings",
                        "raw_plan": deterministic_operation_plan,
                        "missing_info": list(guarded_plan.get("missing_info") or []),
                    },
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=operands,
                        calculation_plan=guarded_plan,
                        calculation_result={},
                        include_compatibility_mirrors=False,
                    ),
                }
            logger.info(
                "[formula_plan] deterministic op-family mode=%s op=%s vars=%s",
                deterministic_operation_plan.get("mode"),
                deterministic_operation_plan.get("operation"),
                len(deterministic_operation_plan.get("variable_bindings") or []),
            )
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(deterministic_operation_plan.get("status") or "ok"),
                summary=f"mode={deterministic_operation_plan.get('mode')} op={deterministic_operation_plan.get('operation')}",
                payload={"calculation_plan": deterministic_operation_plan},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
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
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_operation_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
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
                    include_compatibility_mirrors=False,
                ),
            }

        deterministic_plan = self._build_deterministic_ontology_plan(state, operands)
        if deterministic_plan:
            guarded_plan = self._operation_plan_guard(
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
                        include_compatibility_mirrors=False,
                    ),
                }
            logger.info(
                "[formula_plan] deterministic mode=%s op=%s vars=%s",
                deterministic_plan.get("mode"),
                deterministic_plan.get("operation"),
                len(deterministic_plan.get("variable_bindings") or []),
            )
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(deterministic_plan.get("status") or "ok"),
                summary=f"mode={deterministic_plan.get('mode')} op={deterministic_plan.get('operation')}",
                payload={"calculation_plan": deterministic_plan},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
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
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=deterministic_plan,
                    calculation_result={},
                    include_compatibility_mirrors=False,
                ),
            }
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
        prompt = ChatPromptTemplate.from_template(
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
            guarded_plan = self._operation_plan_guard(
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
            artifacts = list(state.get("artifacts") or [])
            tasks = list(state.get("tasks") or [])
            task_id = str((state.get("active_subtask") or {}).get("task_id") or "calc")
            artifact_id = f"plan:{task_id}:{len(artifacts) + 1:03d}"
            artifacts = _append_artifact(
                artifacts,
                artifact_id=artifact_id,
                task_id=task_id,
                kind=ArtifactKind.CALCULATION_PLAN,
                status=str(plan_data.get("status") or "ok"),
                summary=f"mode={plan_data.get('mode')} op={plan_data.get('operation')}",
                payload={"calculation_plan": plan_data},
            )
            tasks = _upsert_task(
                tasks,
                task_id=task_id,
                kind=TaskKind.CALCULATION,
                label=str((state.get("active_subtask") or {}).get("metric_label") or task_id),
                status=TaskStatus.IN_PROGRESS,
                query=self._calc_query(state),
                metric_family=self._calc_metric_family(state),
                artifact_id=artifact_id,
            )
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
                "tasks": tasks,
                "artifacts": artifacts,
                **_runtime_trace_state_update(
                    state,
                    calculation_operands=operands,
                    calculation_plan=plan_data,
                    calculation_result={},
                    include_compatibility_mirrors=False,
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
                    include_compatibility_mirrors=False,
                ),
            }

    def _format_calculation_value(self, value: float, result_unit: str, normalized_unit: str) -> str:
        return calculation_rendering.format_calculation_value(value, result_unit, normalized_unit)

    def _format_calculation_value_in_display_unit(self, value: float, display_unit: str) -> str:
        return calculation_rendering.format_calculation_value_in_display_unit(value, display_unit)

    def _adjusted_difference_source_display_unit(
        self,
        *,
        active_subtask: Dict[str, Any],
        ordered_operands: List[Dict[str, Any]],
    ) -> str:
        return calculation_rendering.adjusted_difference_source_display_unit(
            active_subtask=active_subtask,
            ordered_operands=ordered_operands,
        )

    def _render_value_with_unit(self, value: float, display_unit: str, normalized_unit: str) -> str:
        return calculation_rendering.render_value_with_unit(value, display_unit, normalized_unit)

    def _render_grounded_operand_display(self, row: Dict[str, Any]) -> str:
        return calculation_rendering.render_grounded_operand_display(row)

    def _absolute_display_value(self, value: str) -> str:
        return calculation_rendering.absolute_display_value(value)

    def _collect_negative_subtrahend_slots(
        self,
        *,
        calculation_result: Optional[Dict[str, Any]] = None,
        subtask_results: Optional[List[Dict[str, Any]]] = None,
    ) -> List[Dict[str, str]]:
        return calculation_rendering.collect_negative_subtrahend_slots(
            calculation_result=calculation_result,
            subtask_results=subtask_results,
        )

    def _coerce_sign_aware_subtraction_answer(
        self,
        answer: str,
        *,
        calculation_result: Optional[Dict[str, Any]] = None,
        subtask_results: Optional[List[Dict[str, Any]]] = None,
    ) -> str:
        return calculation_rendering.coerce_sign_aware_subtraction_answer(
            answer,
            calculation_result=calculation_result,
            subtask_results=subtask_results,
        )

    def _first_material_slot_for_role(self, answer_slots: Dict[str, Any], role: str) -> Dict[str, Any]:
        return calculation_rendering.first_material_slot_for_role(
            answer_slots,
            role,
            answer_slot_has_material=self._answer_slot_has_material,
        )

    def _infer_company_from_answer_slots(self, answer_slots: Dict[str, Any]) -> str:
        return calculation_rendering.infer_company_from_answer_slots(answer_slots)

    def _compose_slot_based_difference_answer(
        self,
        *,
        query: str,
        report_scope: Dict[str, Any],
        calculation_result: Dict[str, Any],
    ) -> str:
        return calculation_rendering.compose_slot_based_difference_answer(
            query=query,
            report_scope=report_scope,
            calculation_result=calculation_result,
            answer_slot_has_material=self._answer_slot_has_material,
        )

    def _slot_status(
        self,
        *,
        normalized_value: Optional[float],
        rendered_value: str,
        raw_value: str,
    ) -> str:
        return financial_answer_slots.slot_status(
            normalized_value=normalized_value,
            rendered_value=rendered_value,
            raw_value=raw_value,
        )

    def _coerce_slot_numeric(self, value: Any) -> Optional[float]:
        return financial_answer_slots.coerce_slot_numeric(value)

    def _build_missing_value_slot(
        self,
        *,
        role: str,
        label: str,
        concept: str = "",
        period: str = "",
        raw_unit: str = "",
        normalized_unit: str = "UNKNOWN",
        source_row_ids: Optional[List[str]] = None,
        source_anchor: str = "",
    ) -> Dict[str, Any]:
        return financial_answer_slots.build_missing_value_slot(
            role=role,
            label=label,
            concept=concept,
            period=period,
            raw_unit=raw_unit,
            normalized_unit=normalized_unit,
            source_row_ids=source_row_ids,
            source_anchor=source_anchor,
        )

    def _build_operand_value_slot(
        self,
        row: Dict[str, Any],
        *,
        default_role: str = "operand",
        preserve_source_display: bool = False,
    ) -> Dict[str, Any]:
        return financial_answer_slots.build_operand_value_slot(
            row,
            default_role=default_role,
            preserve_source_display=preserve_source_display,
        )

    def _build_calculated_value_slot(
        self,
        *,
        label: str,
        normalized_value: Optional[float],
        normalized_unit: str,
        display_unit: str,
        period: str = "",
        source_row_ids: Optional[List[str]] = None,
        role: str = "primary_value",
        source_anchor: str = "",
    ) -> Dict[str, Any]:
        return financial_answer_slots.build_calculated_value_slot(
            label=label,
            normalized_value=normalized_value,
            normalized_unit=normalized_unit,
            display_unit=display_unit,
            period=period,
            source_row_ids=source_row_ids,
            role=role,
            source_anchor=source_anchor,
        )

    def _build_answer_slots(
        self,
        *,
        active_subtask: Dict[str, Any],
        operation_family: str,
        ordered_operands: List[Dict[str, Any]],
        result_value: Optional[float],
        result_unit: str,
        normalized_unit: str,
        source_normalized_unit: str,
        current_value: Optional[float],
        prior_value: Optional[float],
        delta_value: Optional[float],
        current_period: str,
        prior_period: str,
        source_row_ids: List[str],
        current_row: Optional[Dict[str, Any]] = None,
        prior_row: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return financial_answer_slots.build_answer_slots(
            active_subtask=active_subtask,
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=result_value,
            result_unit=result_unit,
            normalized_unit=normalized_unit,
            source_normalized_unit=source_normalized_unit,
            current_value=current_value,
            prior_value=prior_value,
            delta_value=delta_value,
            current_period=current_period,
            prior_period=prior_period,
            source_row_ids=source_row_ids,
            current_row=current_row,
            prior_row=prior_row,
        )

    def _binding_policy_for_operand_row(self, row: Dict[str, Any]) -> Dict[str, Any]:
        row_policy = dict(row.get("binding_policy") or {})
        concept_key = str(row.get("matched_operand_concept") or row.get("concept") or "").strip()
        if not concept_key:
            return row_policy
        ontology_policy = get_financial_ontology().binding_policy_for_concept(concept_key)
        merged = dict(ontology_policy or {})
        merged.update(row_policy)
        return merged

    def _apply_operation_sign_policy(
        self,
        operands: List[Dict[str, Any]],
        *,
        operation: str,
        operation_family: str,
    ) -> List[Dict[str, Any]]:
        if _normalise_spaces(operation) != "ratio" and _normalise_spaces(operation_family) != "ratio":
            return operands
        updated: List[Dict[str, Any]] = []
        changed = False
        for row in operands:
            next_row = dict(row)
            role = _normalise_spaces(str(next_row.get("matched_operand_role") or next_row.get("role") or ""))
            if not role.startswith("denominator"):
                updated.append(next_row)
                continue
            policy = self._binding_policy_for_operand_row(next_row)
            denominator_sign = _normalise_spaces(str(policy.get("ratio_denominator_sign") or ""))
            if denominator_sign != "magnitude":
                updated.append(next_row)
                continue
            value = next_row.get("normalized_value")
            if value is None:
                updated.append(next_row)
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                updated.append(next_row)
                continue
            if numeric_value < 0:
                next_row["normalized_value"] = abs(numeric_value)
                next_row["sign_policy_applied"] = "ratio_denominator_magnitude"
                next_row["source_normalized_value"] = numeric_value
                next_row["binding_policy"] = policy
                changed = True
            updated.append(next_row)
        return updated if changed else operands

    def _repair_krw_normalized_values_from_raw_units(
        self,
        operands: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        updated: List[Dict[str, Any]] = []
        changed = False
        for row in operands:
            next_row = dict(row)
            if _normalise_spaces(str(next_row.get("normalized_unit") or "")).upper() != "KRW":
                updated.append(next_row)
                continue
            raw_unit = _normalise_spaces(str(next_row.get("raw_unit") or next_row.get("result_unit") or ""))
            raw_value = _normalise_spaces(str(next_row.get("raw_value") or ""))
            if not raw_unit or not raw_value:
                updated.append(next_row)
                continue
            expected_value, expected_unit = _normalise_operand_value(raw_value, raw_unit)
            if expected_value is None or expected_unit != "KRW":
                updated.append(next_row)
                continue
            current_value = next_row.get("normalized_value")
            try:
                current_numeric = float(current_value)
                expected_numeric = float(expected_value)
            except (TypeError, ValueError):
                updated.append(next_row)
                continue
            if current_numeric == expected_numeric:
                updated.append(next_row)
                continue
            if not current_numeric or not expected_numeric:
                updated.append(next_row)
                continue
            distortion = max(abs(current_numeric), abs(expected_numeric)) / min(
                abs(current_numeric),
                abs(expected_numeric),
            )
            if distortion < 100.0:
                updated.append(next_row)
                continue
            next_row["source_normalized_value"] = current_numeric
            next_row["normalized_value"] = expected_numeric
            next_row["normalized_unit"] = expected_unit
            next_row["unit_normalization_repair_source"] = "raw_unit_scale"
            changed = True
            updated.append(next_row)
        return updated if changed else operands

    def _dependency_task_output_has_consistent_krw_unit(self, row: Dict[str, Any]) -> bool:
        if not (
            row.get("dependency_resolved")
            and str(row.get("source_row_id") or "").startswith("task_output:")
            and _normalise_spaces(str(row.get("normalized_unit") or "")).upper() == "KRW"
        ):
            return False
        raw_value = _normalise_spaces(str(row.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(row.get("raw_unit") or row.get("result_unit") or ""))
        if not raw_value or not raw_unit:
            return False
        expected_value, expected_unit = _normalise_operand_value(raw_value, raw_unit)
        if expected_value is None or expected_unit != "KRW":
            return False
        try:
            current_value = float(row.get("normalized_value"))
            expected_numeric = float(expected_value)
        except (TypeError, ValueError):
            return False
        return abs(current_value - expected_numeric) <= max(1e-6, abs(expected_numeric) * 1e-9)

    def _repair_krw_operand_units_from_table_metadata(
        self,
        operands: List[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        evidence_by_id = self._evidence_items_by_id(evidence_items)
        if not evidence_by_id:
            return operands

        render_policy = dict(CALCULATION_RENDER_POLICY)
        krw_units = {
            _normalise_spaces(str(item))
            for item in (render_policy.get("krw_display_units") or ())
            if str(item).strip()
        }
        scales = {
            _normalise_spaces(str(key)): float(value)
            for key, value in dict(render_policy.get("krw_display_unit_scales") or {}).items()
            if str(key).strip()
        }

        def table_surface_contains_value(evidence_item: Dict[str, Any], raw_value: str) -> bool:
            compact_value = re.sub(r"[,\s()]", "", raw_value)
            if not compact_value:
                return False
            metadata = dict(evidence_item.get("metadata") or {})
            surface = _normalise_spaces(
                " ".join(
                    str(value or "")
                    for value in [
                        evidence_item.get("raw_row_text"),
                        evidence_item.get("quote_span"),
                        evidence_item.get("claim"),
                        metadata.get("row_text"),
                        metadata.get("table_summary_text"),
                        metadata.get("table_value_labels_text"),
                        metadata.get("table_row_labels_text"),
                    ]
                )
            )
            return compact_value in re.sub(r"[,\s()]", "", surface)

        def is_table_backed(evidence_item: Dict[str, Any]) -> bool:
            metadata = dict(evidence_item.get("metadata") or {})
            return any(
                [
                    _normalise_spaces(str(metadata.get("block_type") or "")).lower() == "table",
                    bool(_normalise_spaces(str(metadata.get("table_source_id") or ""))),
                    bool(metadata.get("structured_cells")),
                    bool(_normalise_spaces(str(metadata.get("table_summary_text") or ""))),
                    bool(_normalise_spaces(str(metadata.get("table_value_labels_text") or ""))),
                ]
            )

        updated: List[Dict[str, Any]] = []
        changed = False
        for row in operands:
            next_row = dict(row)
            if self._dependency_task_output_has_consistent_krw_unit(next_row):
                updated.append(next_row)
                continue
            if _normalise_spaces(str(next_row.get("normalized_unit") or "")).upper() != "KRW":
                updated.append(next_row)
                continue
            raw_value = _normalise_spaces(str(next_row.get("raw_value") or ""))
            raw_unit = _normalise_spaces(str(next_row.get("raw_unit") or next_row.get("result_unit") or ""))
            if not raw_value or raw_unit not in krw_units:
                updated.append(next_row)
                continue
            evidence_item = self._evidence_item_for_operand_row(next_row, evidence_by_id)
            if not evidence_item or not is_table_backed(evidence_item):
                updated.append(next_row)
                continue
            metadata = dict(evidence_item.get("metadata") or {})
            unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
            if not unit_hint or unit_hint == raw_unit or unit_hint not in krw_units:
                updated.append(next_row)
                continue
            current_scale = scales.get(raw_unit)
            hint_scale = scales.get(unit_hint)
            if not current_scale or not hint_scale:
                updated.append(next_row)
                continue
            scale_distortion = max(current_scale, hint_scale) / min(current_scale, hint_scale)
            if scale_distortion < 100.0:
                updated.append(next_row)
                continue
            if not table_surface_contains_value(evidence_item, raw_value):
                updated.append(next_row)
                continue
            hinted_value, hinted_unit = _normalise_operand_value(raw_value, unit_hint)
            if hinted_value is None or hinted_unit != "KRW":
                updated.append(next_row)
                continue
            try:
                current_value = float(next_row.get("normalized_value"))
            except (TypeError, ValueError):
                current_value = None
            next_row["source_raw_unit"] = raw_unit
            if current_value is not None:
                next_row["source_normalized_value"] = current_value
            next_row["raw_unit"] = unit_hint
            next_row["normalized_value"] = hinted_value
            next_row["normalized_unit"] = hinted_unit
            next_row["rendered_value"] = f"{raw_value}{unit_hint}"
            next_row["unit_normalization_repair_source"] = "table_metadata_unit_hint"
            changed = True
            updated.append(next_row)
        return updated if changed else operands

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
        candidate_slot, candidate_score = self._best_direct_lookup_slot_from_evidence_pool_compat(
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
            self._canonical_structured_reconciliation_id(source_id)
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

    def _execute_calculation(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Execute the planned numeric operation and normalize the result."""
        runtime_trace = _resolve_runtime_calculation_trace(
            dict(state),
            allow_legacy_top_level=False,
        )
        runtime_operands = [dict(row) for row in (runtime_trace.get("calculation_operands") or [])]
        runtime_operands = self._repair_krw_operand_units_from_table_metadata(
            runtime_operands,
            list(state.get("evidence_items") or []) + list(state.get("runtime_evidence") or []),
        )
        runtime_operands = self._repair_krw_normalized_values_from_raw_units(runtime_operands)
        operands = {row.get("operand_id"): row for row in runtime_operands}
        plan = dict(runtime_trace.get("calculation_plan") or {})
        active_subtask = dict(state.get("active_subtask") or {})
        query = self._calc_query(state)
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
        selected_evidence_ids: List[str] = []
        source_normalized_unit = ""

        def _fail(status: str, reason: str, calculation_plan: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
            fallback = "질문에 필요한 수치를 계산할 수 있는 근거를 충분히 확보하지 못했습니다."
            failed_result = build_failed_calculation_result(
                active_subtask=active_subtask,
                operation_family=operation_family or "single_value",
                runtime_operands=list(runtime_operands),
                result_unit=result_unit,
                source_normalized_unit=source_normalized_unit or "UNKNOWN",
                status=status,
                reason=reason,
            )
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
                    calculation_operands=runtime_operands,
                    calculation_plan=calculation_plan if calculation_plan is not None else plan,
                    calculation_result=failed_result,
                    include_compatibility_mirrors=False,
                ),
            }

        if mode == "none" or not variable_bindings:
            return _fail("insufficient_operands", explanation or "no operation or operands")

        if not ordered_ids:
            ordered_ids = [str(binding.get("operand_id") or "") for binding in variable_bindings]

        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict) and bool(item.get("required", True))
        ]
        guarded_plan = self._operation_plan_guard(
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
            return _fail(
                "insufficient_operands",
                "operation plan does not satisfy required operand bindings",
                calculation_plan=guarded_plan,
            )

        ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        rendered_unit_repaired_operands = [
            self._repair_operand_normalization_from_rendered_unit(row)
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
                list(state.get("evidence_items") or []) + list(state.get("runtime_evidence") or []),
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
                    aligned_operands = self._align_growth_operand_units_when_raw_scale_matches(ordered_operands)
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
                list(state.get("evidence_items") or []),
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

            if self._growth_operand_periods_conflict(ordered_operands):
                return _fail("insufficient_operands", "growth operands share the same period")

        sign_normalized_operands = self._apply_operation_sign_policy(
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
            coerced_row = _coerce_lookup_magnitude_record(dict(row), None)
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
            ordered_operands = [operands[operand_id] for operand_id in ordered_ids]

        selected_evidence_ids = list(
            dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
        )
        units = {row.get("normalized_unit") for row in ordered_operands}
        if len(units) != 1:
            return _fail("unit_mismatch", f"unit families differ: {sorted(str(unit) for unit in units)}")
        normalized_unit = str(next(iter(units)))
        source_normalized_unit = normalized_unit
        values = [row.get("normalized_value") for row in ordered_operands]
        if any(value is None for value in values):
            return _fail("parse_error", "one or more operands could not be normalized")

        try:
            result_value: Optional[float]
            derived_metrics: Dict[str, Any] = {}
            result_series: List[Dict[str, Any]] = []
            env: Dict[str, float] = {}
            for binding in variable_bindings:
                variable = str(binding.get("variable") or "").strip()
                operand_id = str(binding.get("operand_id") or "").strip()
                operand = operands.get(operand_id)
                if not variable or operand is None or operand.get("normalized_value") is None:
                    return _fail("parse_error", f"invalid variable binding: {binding}")
                env[variable] = float(operand.get("normalized_value"))

            if mode == "time_series":
                if len(variable_bindings) < 2:
                    return _fail("insufficient_operands", "time_series needs at least 2 operands")
                ordered_operands = sorted(
                    [operands[str(binding.get("operand_id"))] for binding in variable_bindings],
                    key=lambda row: _extract_period_sort_key(str(row.get("period") or "")),
                )
                selected_evidence_ids = list(
                    dict.fromkeys(str(row.get("evidence_id")) for row in ordered_operands if row.get("evidence_id"))
                )
                labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
                metric_names = [re.sub(r"^\d{4}년\s*", "", label).strip() for label in labels]
                metric_name = metric_names[0] if metric_names else "지표"
                result_series = calculation_rendering.time_series_result_series(
                    ordered_operands=ordered_operands,
                    normalized_unit=normalized_unit,
                )
                yoy_growth_rates = time_series_yoy_growth_rates(
                    ordered_operands=ordered_operands,
                    pairwise_formula=pairwise_formula,
                )
                if not formula:
                    return _fail("parse_error", "missing trend formula")
                result_value = _safe_eval_formula(formula, env)
                if result_unit in {"%", "%p"}:
                    normalized_unit = "PERCENT"
                _is_percent = (normalized_unit or "").upper() in {"PERCENT", "%", "퍼센트"}
                if _is_percent:
                    rendered_value = f"{result_value:.1f}%"
                else:
                    rendered_value = f"{result_value:,.4f}".rstrip("0").rstrip(".")
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
                return {
                    "answer": "",
                    "compressed_answer": "",
                    "selected_claim_ids": selected_evidence_ids,
                    "draft_points": [],
                    "kept_claim_ids": selected_evidence_ids,
                    "dropped_claim_ids": [],
                    "unsupported_sentences": [],
                    "sentence_checks": [],
                    **_runtime_trace_state_update(
                        state,
                        calculation_operands=runtime_operands,
                        calculation_plan=plan,
                        calculation_result=calc_result,
                        include_compatibility_mirrors=False,
                    ),
                }

            if not formula:
                return _fail("parse_error", "missing scalar formula")
            result_value = _safe_eval_formula(formula, env)
            if result_unit in {"%", "%p"}:
                normalized_unit = "PERCENT"
            elif operation == "ratio":
                normalized_unit = "COUNT"
        except Exception as exc:
            if isinstance(exc, ZeroDivisionError):
                return _fail("zero_division", str(exc))
            return _fail("parse_error", str(exc))

        formula_result_value = result_value
        source_stated_result_used = False
        result_display_unit = ""
        if self._ratio_result_has_suspicious_krw_scale(
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=result_value,
            result_unit=result_unit,
            source_normalized_unit=source_normalized_unit,
        ):
            return _fail(
                "scale_mismatch",
                "same-unit KRW ratio produced an implausible percent result; retry with better grounded operands",
            )
        if operation_family == "ratio" and result_value is not None and result_value < 0:
            if self._ratio_query_requests_absolute_magnitude(query):
                result_value = abs(float(result_value))
        if operation_family == "difference" and normalized_unit == "KRW":
            result_display_unit = self._adjusted_difference_source_display_unit(
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
        rendered_value = display_state["rendered_value"]
        rendered_with_unit = display_state["rendered_with_unit"]
        labels = [_display_operand_label(str(row.get("label") or row.get("evidence_id") or "")) for row in ordered_operands]
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
        source_stated_result_used = scalar_state["source_stated_result_used"]
        current_value = scalar_state["current_value"]
        prior_value = scalar_state["prior_value"]
        delta_value = scalar_state["delta_value"]
        current_period = scalar_state["current_period"]
        prior_period = scalar_state["prior_period"]
        current_row = scalar_state["current_row"]
        prior_row = scalar_state["prior_row"]
        source_row_ids = scalar_state["source_row_ids"]
        answer_slots = self._build_answer_slots(
            active_subtask=active_subtask,
            operation_family=operation_family,
            ordered_operands=ordered_operands,
            result_value=result_value,
            result_unit=result_display_unit or result_unit,
            normalized_unit=normalized_unit,
            source_normalized_unit=source_normalized_unit,
            current_value=current_value,
            prior_value=prior_value,
            delta_value=delta_value,
            current_period=current_period,
            prior_period=prior_period,
            source_row_ids=source_row_ids,
            current_row=current_row,
            prior_row=prior_row,
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
        return build_success_calculation_state_payload(
            state=state,
            calc_result=calc_result,
            selected_evidence_ids=selected_evidence_ids,
            runtime_operands=runtime_operands,
            calculation_plan=plan,
            query=self._calc_query(state),
            metric_family=self._calc_metric_family(state),
        )

    def _repair_stale_calculation_result_from_operands(
        self,
        state: FinancialAgentState,
        *,
        operands: List[Dict[str, Any]],
        plan: Dict[str, Any],
        calculation_result: Dict[str, Any],
    ) -> tuple[List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
        if str(calculation_result.get("status") or "").strip().lower() != "ok":
            return operands, plan, calculation_result
        if str(plan.get("mode") or "").strip() != "single_value":
            return operands, plan, calculation_result
        formula = str(plan.get("formula") or "").strip()
        if not formula:
            return operands, plan, calculation_result
        operands_by_id = {
            str(row.get("operand_id") or "").strip(): dict(row)
            for row in operands
            if str(row.get("operand_id") or "").strip()
        }
        env: Dict[str, float] = {}
        for binding in list(plan.get("variable_bindings") or []):
            variable = str((binding or {}).get("variable") or "").strip()
            operand_id = str((binding or {}).get("operand_id") or "").strip()
            operand = operands_by_id.get(operand_id)
            if not variable or operand is None:
                return operands, plan, calculation_result
            try:
                env[variable] = float(operand.get("normalized_value"))
            except (TypeError, ValueError):
                return operands, plan, calculation_result
        if not env:
            return operands, plan, calculation_result
        try:
            expected_value = float(_safe_eval_formula(formula, env))
            current_value = float(calculation_result.get("result_value"))
        except Exception:
            return operands, plan, calculation_result
        tolerance = max(1e-6, abs(expected_value) * 1e-9)
        if abs(expected_value - current_value) <= tolerance:
            return operands, plan, calculation_result

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
        if operation_family in {"difference", "growth_rate"} and self._period_comparison_operand_rows_collapse_to_same_slot(
            operands
        ):
            return operands, plan, calculation_result

        recalculated = self._execute_calculation(
            {
                **dict(state),
                "active_subtask": active_subtask,
                "resolved_calculation_trace": {
                    "calculation_operands": operands,
                    "calculation_plan": plan,
                    "calculation_result": {},
                },
                "tasks": [],
                "artifacts": [],
            }
        )
        recalculated_trace = _resolve_runtime_calculation_trace(
            recalculated,
            allow_legacy_top_level=False,
        )
        repaired_result = dict(recalculated_trace.get("calculation_result") or {})
        if str(repaired_result.get("status") or "").strip().lower() != "ok":
            return operands, plan, calculation_result
        repaired_result["stale_result_repaired_from_operands"] = True
        return (
            [dict(row) for row in list(recalculated_trace.get("calculation_operands") or operands)],
            dict(recalculated_trace.get("calculation_plan") or plan),
            repaired_result,
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

        operands, plan, calculation_result = self._repair_stale_calculation_result_from_operands(
            state,
            operands=[dict(row) for row in operands if isinstance(row, dict)],
            plan=plan,
            calculation_result=calculation_result,
        )

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

        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=self._calc_query(state),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=calculation_result,
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
                    include_compatibility_mirrors=False,
                ),
            }

        structured_llm = self._llm_for_phase("calculation_render").with_structured_output(CalculationRenderOutput)
        prompt = ChatPromptTemplate.from_template(
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

        answer = self._coerce_sign_aware_subtraction_answer(
            answer,
            calculation_result=calculation_result,
        )
        if operation_family == "ratio" and (
            self._ratio_components_are_complete(calculation_result)
            or self._ratio_component_consolidation_scope(calculation_result, operands)
            or self._ratio_components_have_suspicious_scale(calculation_result)
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
                include_compatibility_mirrors=False,
            ),
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
                    include_compatibility_mirrors=False,
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
        structured_llm = self._llm_for_phase("calculation_verification").with_structured_output(CalculationVerificationOutput)
        prompt = ChatPromptTemplate.from_template(
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
            final_answer = self._coerce_sign_aware_subtraction_answer(
                final_answer,
                calculation_result=calculation_result,
            )
            if operation_family == "ratio" and (
                self._ratio_components_are_complete(calculation_result)
                or self._ratio_component_consolidation_scope(calculation_result, operands)
                or self._ratio_components_have_suspicious_scale(calculation_result)
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
                    include_compatibility_mirrors=False,
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
                    include_compatibility_mirrors=False,
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
                    include_compatibility_mirrors=False,
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

    def _aggregate_synthesis_prompt_rows(
        self,
        ordered_results: List[Dict[str, Any]],
        aggregate_projection: Dict[str, Any],
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
            if not _operand_row_has_material_numeric_payload(operand_row):
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
        ordered_results = self._dedupe_aggregate_subtask_results(ordered_results)
        ordered_results = self._recover_lookup_results_from_sibling_table_evidence(ordered_results, state)
        ordered_results = self._promote_stronger_nested_aggregate_results(ordered_results)
        ordered_results = self._align_lookup_result_units_from_peer_source_slots(ordered_results)
        ordered_results = self._dedupe_aggregate_subtask_results(ordered_results)
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
            ordered_results = self._dedupe_aggregate_subtask_results(early_aligned_results)
            fallback_answer = self._preferred_aggregate_fallback_answer(
                ordered_results,
                self._preferred_complete_numeric_answer(ordered_results) or fallback_answer,
            )
        supported_aggregate_answer = self._supported_aggregate_subtask_answer(ordered_results)
        complete_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
        has_narrative_summary = any(self._row_is_narrative_summary(row) for row in ordered_results)
        lookup_list_answer = self._compose_lookup_list_numeric_answer(ordered_results)
        if lookup_list_answer:
            fallback_answer = lookup_list_answer
        numeric_answer_locked = bool(
            has_narrative_summary
            and complete_numeric_answer
            and self._complete_numeric_answer_can_replace_final(complete_numeric_answer, ordered_results)
            and not self._query_requests_explanatory_context(str(state.get("query") or ""))
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
            ordered_results = self._dedupe_aggregate_subtask_results(own_unit_aligned_results)
            own_unit_projection = self._rebuild_aggregate_projection(ordered_results, fallback_answer)
            own_unit_aligned_results = self._align_lookup_results_with_dependency_projection(
                ordered_results,
                state,
                own_unit_projection,
            )
            if own_unit_aligned_results != ordered_results:
                ordered_results = self._dedupe_aggregate_subtask_results(own_unit_aligned_results)
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

    def _aggregate_selected_claim_ids(
        self,
        ordered_results: List[Dict[str, Any]],
        composition_selected_claim_ids: List[str],
    ) -> List[str]:
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
        source_task_ids = [
            str(row.get("task_id") or "").strip()
            for row in ordered_results
            if str(row.get("task_id") or "").strip()
        ]
        selected_claim_ids_for_integrity = self._aggregate_selected_claim_ids(
            ordered_results,
            composition_selected_claim_ids,
        )
        ordered_result_source_refs = _clean_source_row_ids(
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
        projection_for_integrity = (
            calculation_projection_override
            if isinstance(calculation_projection_override, dict) and calculation_projection_override
            else preliminary_projection
        )
        projection_result_for_integrity = dict(projection_for_integrity.get("calculation_result") or {})
        projection_slots_for_integrity = dict(projection_result_for_integrity.get("answer_slots") or {})
        ledger_artifacts = self._enrich_reconciliation_artifact_refs(
            list(state.get("artifacts") or []),
            task_id="",
            task_ids=source_task_ids,
            operand_rows=list(projection_for_integrity.get("calculation_operands") or []),
            extra_refs=[
                projection_result_for_integrity.get("source_row_id"),
                projection_result_for_integrity.get("source_row_ids"),
                projection_slots_for_integrity.get("source_row_id"),
                projection_slots_for_integrity.get("source_row_ids"),
                ordered_result_source_refs,
                selected_claim_ids_for_integrity,
            ],
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
                self._safe_partial_answer_for_numeric_gap(ordered_results)
                or self._preferred_complete_numeric_answer(ordered_results)
                or self._supported_aggregate_subtask_answer(ordered_results)
            )
            state_calculation_status = _normalise_spaces(
                str((state.get("calculation_result") or {}).get("status") or "")
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
                not self._row_is_narrative_summary(row)
                and (
                    self._material_gap_feedback_for_subtask_result(row)
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
                    if self._row_is_narrative_summary(source):
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
        artifacts = list(ledger_artifacts)
        tasks = list(state.get("tasks") or [])
        artifact_id = f"aggregate:{len(artifacts) + 1:03d}"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id="aggregate",
            kind=ArtifactKind.AGGREGATED_ANSWER,
            status="ok",
            summary=final_answer[:200],
            payload={
                "subtask_results": ordered_results,
                "final_answer": final_answer,
                "planner_feedback": planner_feedback,
                **aggregate_projection,
            },
            evidence_refs=selected_claim_ids,
        )
        tasks = _upsert_task(
            tasks,
            task_id="aggregate",
            kind=TaskKind.SYNTHESIS,
            label="Aggregate subtask results",
            status=TaskStatus.PARTIAL if planner_feedback else TaskStatus.COMPLETED,
            query=str(state.get("query") or ""),
            metric_family="aggregate",
            artifact_id=artifact_id,
        )
        tasks, artifacts = self._finalize_aggregate_task_ledger(
            tasks,
            artifacts,
            ordered_results=ordered_results,
            aggregate_projection=aggregate_projection,
            aggregate_artifact_id=artifact_id,
        )
        aggregate_projection, final_answer, artifacts = self._apply_ratio_projection_answer_if_rendered_missing(
            state,
            aggregate_projection,
            artifact_id=artifact_id,
            final_answer=final_answer,
            artifacts=artifacts,
        )
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
            **_runtime_trace_state_update(
                state,
                calculation_operands=aggregate_projection["calculation_operands"],
                calculation_plan=aggregate_projection["calculation_plan"],
                calculation_result=aggregate_projection["calculation_result"],
                include_compatibility_mirrors=False,
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
        narrative_context = self._narrative_context_sentence_from_evidence(
            str(state.get("query") or ""),
            aggregate_evidence_items,
        )
        plan_loop_count = int(state.get("plan_loop_count") or 0)
        max_plan_loops = 2
        aggregate_synthesis_input_json = ""
        aggregate_synthesis_debug: Dict[str, Any] = {}
        if hasattr(self, "llm") and getattr(self, "llm", None) is not None:
            structured_llm = self._llm_for_phase("aggregate_synthesis").with_structured_output(AggregateSynthesisOutput)
            prompt = ChatPromptTemplate.from_template(
                str(CALCULATION_PROMPT_POLICY.get("aggregate_synthesis_prompt_template") or "")
            )
            try:
                prompt_rows = self._aggregate_synthesis_prompt_rows(ordered_results, preliminary_projection)
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
        task_artifact_trace = feedback_state.task_artifact_trace
        should_replan = feedback_state.should_replan
        replan_blocked_reason = feedback_state.replan_blocked_reason
        selected_claim_ids = self._aggregate_selected_claim_ids(
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
            mutable_state = self._sync_mutable_aggregate_state(mutable_state, **updates)
            _sync_aggregate_locals()

        aligned_ordered_results = self._align_lookup_results_with_dependency_projection(
            ordered_results,
            state,
            aggregate_projection,
        )
        if aligned_ordered_results is not ordered_results:
            refresh_aligned_numeric = (
                not narrative_answer_locked
                or self._aggregate_results_include_source_task_slot_realignment(aligned_ordered_results)
            )
            mutable_state = self._replace_mutable_aggregate_results(
                mutable_state,
                state,
                aligned_ordered_results,
                refresh_numeric_answer=refresh_aligned_numeric,
            )
            _sync_aggregate_locals()
        if calculation_projection_override:
            for key in ("calculation_operands", "calculation_plan", "calculation_result"):
                if calculation_projection_override.get(key):
                    aggregate_projection[key] = calculation_projection_override[key]
            mutable_state = mutable_state._replace(
                synthesis_state=mutable_state.synthesis_state._replace(aggregate_projection=aggregate_projection)
            )
        slot_based_difference_answer = self._compose_slot_based_difference_answer(
            query=str(state.get("query") or ""),
            report_scope=dict(state.get("report_scope") or {}),
            calculation_result=dict(aggregate_projection.get("calculation_result") or {}),
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
        ):
            final_answer = self._ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            mutable_state = mutable_state._replace(
                synthesis_state=mutable_state.synthesis_state._replace(final_answer=final_answer)
            )
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
            late_supported_answer = self._supported_aggregate_subtask_answer(ordered_results)
            late_numeric_answer = self._preferred_complete_numeric_answer(ordered_results)
            late_answer = late_supported_answer or (
                late_numeric_answer
                if self._complete_numeric_answer_can_replace_final(late_numeric_answer, ordered_results)
                else ""
            )
            if late_answer:
                mutable_state = self._apply_mutable_numeric_answer(
                    mutable_state,
                    state=state,
                    numeric_answer=late_answer,
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
            selected_claim_ids = list(dict.fromkeys([*selected_claim_ids, *missing_context_claim_ids]))
            _sync_state(selected_claim_ids=selected_claim_ids)
        late_unit_aligned_results = self._align_lookup_result_units_from_own_evidence(
            ordered_results,
            aggregate_evidence_items,
        )
        late_unit_aligned_results = self._align_lookup_result_units_from_peer_source_slots(late_unit_aligned_results)
        if late_unit_aligned_results != ordered_results:
            late_unit_results = self._dedupe_aggregate_subtask_results(late_unit_aligned_results)
            late_unit_projection = self._rebuild_aggregate_projection(late_unit_results, final_answer)
            late_unit_aligned_results = self._align_lookup_results_with_dependency_projection(
                late_unit_results,
                {"query": str(state.get("query") or ""), "calc_subtasks": []},
                late_unit_projection,
            )
            if late_unit_aligned_results != late_unit_results:
                late_unit_results = self._dedupe_aggregate_subtask_results(late_unit_aligned_results)
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
        if (
            consistent_numeric_answer
            and _normalise_spaces(consistent_numeric_answer) != _normalise_spaces(final_answer)
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
            and self._complete_numeric_answer_can_replace_final(consistent_numeric_answer, ordered_results)
            and (
                not self._answer_covers_numeric_projection(final_answer, ordered_results)
                or self._growth_answer_has_untraced_numeric_material(
                    final_answer,
                    ordered_results,
                    aggregate_evidence_items,
                )
            )
        ):
            mutable_state = self._apply_mutable_numeric_answer(
                mutable_state,
                state=state,
                numeric_answer=consistent_numeric_answer,
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
        lookup_preserved_answer = self._append_uncovered_lookup_numeric_items(final_answer, ordered_results)
        if lookup_preserved_answer != _normalise_spaces(final_answer):
            mutable_state, _ = self._replace_mutable_aggregate_answer(
                mutable_state,
                candidate_answer=lookup_preserved_answer,
                sync_rendered_for_aggregate=False,
                refresh_operand_evidence=True,
            )
            _sync_aggregate_locals()
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
        aggregate_state = self._apply_stale_projection_repair_to_aggregate_state(
            state=state,
            aggregate_state=mutable_state.synthesis_state,
            evidence_items=aggregate_evidence_items,
            prefer_compact_ratio_answer=True,
        )
        mutable_state = mutable_state._replace(synthesis_state=aggregate_state)
        ordered_results, aggregate_projection, final_answer, selected_claim_ids = aggregate_state
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
                and not self._growth_answer_has_untraced_numeric_material(
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
            if conflicting_answer and (
                not final_answer_satisfies_growth_narrative
                and not final_answer_preserves_numeric_trace
                and (
                    final_contains_conflicting_answer_with_extra_numbers
                    or self._growth_narrative_numeric_incompatible_with_trace(
                        narrative_answer=conflicting_answer,
                        numeric_answer=final_answer,
                        ordered_results=ordered_results,
                        evidence_items=aggregate_evidence_items,
                    )
                )
            ):
                aggregate_projection, final_answer, selected_claim_ids = self._apply_aggregate_answer_candidate(
                    aggregate_projection,
                    selected_claim_ids,
                    self._aggregate_answer_candidate(
                        conflicting_answer,
                        selected_claim_ids=late_conflicting_narrative.get("selected_claim_ids") or [],
                        sync_projection=False,
                    ),
                )
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
            aggregate_projection, final_answer, selected_claim_ids = self._apply_aggregate_answer_candidate(
                aggregate_projection,
                selected_claim_ids,
                preserved_aggregate_candidate,
            )
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
        if has_growth_material and self._query_requests_explanatory_context(str(state.get("query") or "")):
            supported_candidate = self._uncovered_supported_growth_narrative_candidate(
                query=str(state.get("query") or ""),
                answer=final_answer,
                ordered_results=ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            supported_sentence = _normalise_spaces(str(supported_candidate.get("sentence") or ""))
            if supported_sentence:
                aggregate_projection, final_answer, selected_claim_ids = self._apply_aggregate_answer_candidate(
                    aggregate_projection,
                    selected_claim_ids,
                    self._aggregate_answer_candidate(
                        _normalise_spaces(" ".join([final_answer, supported_sentence])),
                        selected_claim_ids=supported_candidate.get("selected_claim_ids") or [],
                    ),
                )
                _sync_state(
                    aggregate_projection=aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                )
        if (
            final_answer
            and has_narrative_summary
            and has_growth_rate_result
            and self._has_strong_growth_trace_for_answer_refresh(ordered_results)
            and not self._answer_matches_supported_aggregate_subtask(final_answer, ordered_results)
        ):
            numeric_preserved_answer = self._ensure_complete_growth_numeric_answer(
                final_answer,
                ordered_results,
                evidence_items=aggregate_evidence_items,
            )
            if numeric_preserved_answer and numeric_preserved_answer != _normalise_spaces(final_answer):
                aggregate_projection, final_answer, selected_claim_ids = self._apply_aggregate_answer_candidate(
                    aggregate_projection,
                    selected_claim_ids,
                    self._aggregate_answer_candidate(
                        numeric_preserved_answer,
                        selected_claim_ids=[],
                    ),
                )
                _sync_state(
                    aggregate_projection=aggregate_projection,
                    final_answer=final_answer,
                    selected_claim_ids=selected_claim_ids,
                )
        _sync_aggregate_locals()
        ordered_results, aggregate_projection = self._sync_aggregate_arithmetic_subtask_surfaces(
            ordered_results,
            aggregate_projection,
            final_answer,
        )
        _sync_state(ordered_results=ordered_results, aggregate_projection=aggregate_projection)
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
            synthesis_source_ids = _synthesis_source_ids_from_task_outputs(state)
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
        reflection_task_id = _next_reflection_task_id(
            state,
            target_task_id=target_task_id,
            current_count=current_count,
        )
        artifacts = list(state.get("artifacts") or [])
        artifact_id = f"{reflection_task_id}:report"
        artifacts = _append_artifact(
            artifacts,
            artifact_id=artifact_id,
            task_id=reflection_task_id,
            kind=ArtifactKind.REFLECTION_REPORT,
            status=str(reflection_report.get("outcome") or "retry_prepared"),
            summary=f"reflection={reflection_report.get('action_taken') or retry_strategy}",
            payload={
                "reflection_report": reflection_report,
                "reflection_action": reflection_action,
                "reflection_request": dict(state.get("reflection_request") or {}),
                "reflection_plan": reflection_plan,
            },
            evidence_refs=[],
        )
        tasks = _upsert_task(
            list(state.get("tasks") or []),
            task_id=reflection_task_id,
            kind=TaskKind.REFLECTION,
            label=f"reflect {target_task_id or 'global'}",
            status=TaskStatus.COMPLETED,
            query=str(state.get("query") or ""),
            metric_family=str(active_subtask.get("metric_family") or ""),
            constraints={
                "target_task_ids": list(reflection_report.get("target_task_ids") or []),
                "target_artifact_ids": list(reflection_report.get("target_artifact_ids") or []),
                "action_taken": str(reflection_report.get("action_taken") or ""),
            },
            artifact_id=artifact_id,
        )
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
                include_compatibility_mirrors=False,
            ),
        }

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
            if required_operands and has_retrieved_docs and not _requires_direct_numeric_grounding(active_subtask):
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
            _resolve_runtime_calculation_trace(
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
            _resolve_runtime_calculation_trace(
                dict(state),
                allow_legacy_top_level=False,
            ).get("calculation_result") or {}
        )
        status = str(result.get("status") or "")
        if status in {"insufficient_operands", "parse_error"}:
            return "reflection_replan"
        return "calc_render"

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
