"""Deterministic dependency operand resolution and projection helpers."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Callable, Dict, List, Literal, Mapping, Optional, Sequence, Tuple

from src.agent.financial_graph_planning import _synthesize_lookup_answer_slot_from_prose
from src.agent.financial_numeric_surface import extract_numeric_surface_candidates, numeric_surface_slot_components
from src.agent.financial_operand_resolution import (
    merge_operand_rows,
    _missing_required_operands,
    _operand_row_matches_requirement,
    operand_row_source_ids,
    operand_row_values_differ,
    operand_row_values_materially_conflict,
    select_sibling_direct_operand_candidate,
)
from src.agent.financial_row_surfaces import _operand_text_match
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _normalise_operand_value,
    _normalise_spaces,
)
from src.agent.financial_scope_policies import known_consolidation_scope_value
from src.config.retrieval_policy import CALCULATION_RENDER_POLICY, OPERAND_CANDIDATE_SCORING_POLICY


OperandResolutionAction = Literal["keep_current", "use_candidate"]
OperandResolutionContext = Literal["default", "complete_period", "coherent_ratio"]
OperandResolutionReason = Literal[
    "current_not_dependency_resolved",
    "current_missing_source_task",
    "equivalent_value",
    "within_material_tolerance",
    "unit_repair_candidate",
    "no_provenance_conflict",
    "candidate_stage_not_preferred",
    "shared_source",
    "complete_period_context_override",
    "coherent_ratio_same_table_override",
    "coherent_ratio_scale_override",
    "provenance_conflict",
]


@dataclass(frozen=True)
class OperandResolutionDecision:
    """Inspectable decision for task-output versus direct-row value precedence."""

    action: OperandResolutionAction
    reason: OperandResolutionReason
    current_source_ids: Tuple[str, ...]
    candidate_source_ids: Tuple[str, ...]
    values_differ: bool
    materially_conflicting: bool
    anchor_conflict: bool
    scope_conflict: bool

    @property
    def keep_current_value(self) -> bool:
        return self.action == "keep_current"


@dataclass(frozen=True)
class DependencyProducerScope:
    """Producer task and provenance scope resolved for one dependency binding."""

    producer_task: Dict[str, Any]
    preferred_statement_types: Tuple[str, ...]
    preferred_sections: Tuple[str, ...]


def _complete_period_context_can_use_candidate(
    current: Dict[str, Any],
    candidate: Dict[str, Any],
) -> bool:
    current_source_ids = operand_row_source_ids(current)
    if not any(source_id.startswith("task_output:") for source_id in current_source_ids):
        return False
    candidate_source_ids = operand_row_source_ids(candidate)
    if not any(
        source_id and not source_id.startswith("task_output:")
        for source_id in candidate_source_ids
    ):
        candidate_source_id = _normalise_spaces(str(candidate.get("source_row_id") or ""))
        if not candidate_source_id or candidate_source_id.startswith("task_output:"):
            return False
    current_unit = _normalise_spaces(str(current.get("normalized_unit") or "")).upper()
    candidate_unit = _normalise_spaces(str(candidate.get("normalized_unit") or "")).upper()
    if not current_unit or current_unit == "UNKNOWN" or current_unit != candidate_unit:
        return False
    repair_source = _normalise_spaces(str(current.get("unit_normalization_repair_source") or ""))
    if repair_source == "alternate_table_krw_surface":
        return True
    try:
        current_value = abs(float(current.get("normalized_value")))
        candidate_value = abs(float(candidate.get("normalized_value")))
    except (TypeError, ValueError):
        return False
    if min(current_value, candidate_value) <= 0:
        return False
    return max(current_value, candidate_value) / min(current_value, candidate_value) >= 100.0


def _coherent_ratio_context_override_reason(
    current: Dict[str, Any],
    candidate: Dict[str, Any],
) -> Optional[OperandResolutionReason]:
    current_source_ids = operand_row_source_ids(current)
    if not (
        current.get("dependency_resolved")
        or _normalise_spaces(str(current.get("source_task_id") or ""))
        or any(source_id.startswith("task_output:") for source_id in current_source_ids)
    ):
        return None
    render_policy = dict(CALCULATION_RENDER_POLICY)
    krw_unit = _normalise_spaces(str(render_policy.get("krw_normalized_unit") or "")).upper()
    if _normalise_spaces(str(current.get("normalized_unit") or "")).upper() != krw_unit:
        return None
    if _normalise_spaces(str(candidate.get("normalized_unit") or "")).upper() != krw_unit:
        return None
    current_table_id = _normalise_spaces(str(current.get("table_source_id") or ""))
    candidate_table_id = _normalise_spaces(str(candidate.get("table_source_id") or ""))
    if current_table_id and current_table_id == candidate_table_id:
        candidate_source_ids = operand_row_source_ids(candidate)
        candidate_has_direct_source = any(
            source_id and not source_id.startswith("task_output:")
            for source_id in candidate_source_ids
        )
        if candidate_has_direct_source and any(
            source_id.startswith("task_output:") for source_id in current_source_ids
        ):
            return "coherent_ratio_same_table_override"
    current_unit = _normalise_spaces(str(current.get("raw_unit") or ""))
    candidate_unit = _normalise_spaces(str(candidate.get("raw_unit") or ""))
    if not current_unit or not candidate_unit or current_unit == candidate_unit:
        return None
    krw_unit_scales = {
        _normalise_spaces(str(unit or "")): float(scale)
        for unit, scale in dict(render_policy.get("krw_display_unit_scales") or {}).items()
        if _normalise_spaces(str(unit or ""))
    }
    current_scale = krw_unit_scales.get(current_unit)
    candidate_scale = krw_unit_scales.get(candidate_unit)
    if not current_scale or not candidate_scale:
        return None
    scale_distortion = max(current_scale, candidate_scale) / min(current_scale, candidate_scale)
    if scale_distortion < 100.0:
        return None
    current_raw = re.sub(r"[,\s()]", "", str(current.get("raw_value") or ""))
    candidate_raw = re.sub(r"[,\s()]", "", str(candidate.get("raw_value") or ""))
    if current_raw and candidate_raw and current_raw == candidate_raw:
        return "coherent_ratio_scale_override"
    try:
        current_value = abs(float(current.get("normalized_value")))
        candidate_value = abs(float(candidate.get("normalized_value")))
    except (TypeError, ValueError):
        return None
    if min(current_value, candidate_value) <= 0:
        return None
    value_distortion = max(current_value, candidate_value) / min(current_value, candidate_value)
    if value_distortion >= scale_distortion * 0.95:
        return "coherent_ratio_scale_override"
    return None


def decide_task_output_operand_resolution(
    current: Dict[str, Any],
    candidate: Dict[str, Any],
    *,
    context: OperandResolutionContext = "default",
) -> OperandResolutionDecision:
    """Choose value precedence without mutating either operand row."""

    current_source_ids = operand_row_source_ids(current)
    candidate_source_ids = operand_row_source_ids(candidate)
    values_differ = operand_row_values_differ(current, candidate)
    materially_conflicting = values_differ and operand_row_values_materially_conflict(current, candidate)
    current_anchor = _normalise_spaces(str(current.get("source_anchor") or ""))
    candidate_anchor = _normalise_spaces(str(candidate.get("source_anchor") or ""))
    anchor_conflict = bool(
        current_anchor
        and candidate_anchor
        and current_anchor != candidate_anchor
    )
    current_scope = known_consolidation_scope_value(current.get("consolidation_scope"))
    candidate_scope = known_consolidation_scope_value(candidate.get("consolidation_scope"))
    scope_conflict = bool(current_scope and candidate_scope and current_scope != candidate_scope)

    def _decision(
        action: OperandResolutionAction,
        reason: OperandResolutionReason,
    ) -> OperandResolutionDecision:
        return OperandResolutionDecision(
            action=action,
            reason=reason,
            current_source_ids=tuple(sorted(current_source_ids)),
            candidate_source_ids=tuple(sorted(candidate_source_ids)),
            values_differ=values_differ,
            materially_conflicting=materially_conflicting,
            anchor_conflict=anchor_conflict,
            scope_conflict=scope_conflict,
        )

    if context == "complete_period" and _complete_period_context_can_use_candidate(current, candidate):
        return _decision("use_candidate", "complete_period_context_override")
    if context == "coherent_ratio":
        override_reason = _coherent_ratio_context_override_reason(current, candidate)
        if override_reason:
            return _decision("use_candidate", override_reason)

    if not current.get("dependency_resolved"):
        return _decision("use_candidate", "current_not_dependency_resolved")
    if not _normalise_spaces(str(current.get("source_task_id") or "")):
        return _decision("use_candidate", "current_missing_source_task")
    if not values_differ:
        return _decision("use_candidate", "equivalent_value")
    if not materially_conflicting:
        return _decision("use_candidate", "within_material_tolerance")

    repair_source = _normalise_spaces(str(current.get("unit_normalization_repair_source") or ""))
    source_raw_unit = _normalise_spaces(str(current.get("source_raw_unit") or ""))
    candidate_raw_unit = _normalise_spaces(str(candidate.get("raw_unit") or ""))
    if repair_source == "alternate_table_krw_surface" and not source_raw_unit and candidate_raw_unit:
        return _decision("use_candidate", "unit_repair_candidate")

    task_output_backed = any(source_id.startswith("task_output:") for source_id in current_source_ids)
    if not (task_output_backed or anchor_conflict or scope_conflict):
        return _decision("use_candidate", "no_provenance_conflict")

    binding_policy = dict(current.get("binding_policy") or {})
    preferred_stages = {
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if _normalise_spaces(str(item))
    }
    if preferred_stages:
        candidate_stage = _normalise_spaces(str(candidate.get("aggregation_stage") or ""))
        if candidate_stage not in preferred_stages:
            return _decision("keep_current", "candidate_stage_not_preferred")
    if current_source_ids.intersection(candidate_source_ids) and not (anchor_conflict or scope_conflict):
        return _decision("use_candidate", "shared_source")
    return _decision("keep_current", "provenance_conflict")


def period_comparison_direct_rows_conflict_with_dependency_outputs(
    dependency_rows: List[Dict[str, Any]],
    direct_rows: List[Dict[str, Any]],
) -> bool:
    """Return whether protected dependency values block direct period rows."""

    if not dependency_rows or not direct_rows:
        return False
    period_roles = {"current_period", "prior_period", "minuend", "subtrahend"}

    def _role(row: Dict[str, Any]) -> str:
        return _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()

    direct_by_role: Dict[str, List[Dict[str, Any]]] = {}
    context_period_roles: Dict[str, set[str]] = {}
    for row in direct_rows:
        role = _role(row)
        if role in period_roles:
            direct_by_role.setdefault(role, []).append(dict(row))
            table_id = _normalise_spaces(str(row.get("table_source_id") or ""))
            if table_id:
                context_period_roles.setdefault(table_id, set()).add(role)
    if not direct_by_role:
        return False

    for dependency_row in dependency_rows:
        role = _role(dependency_row)
        if role not in period_roles:
            continue
        for direct_row in direct_by_role.get(role, []):
            table_id = _normalise_spaces(str(direct_row.get("table_source_id") or ""))
            if decide_task_output_operand_resolution(
                dependency_row,
                direct_row,
                context=(
                    "complete_period"
                    if table_id and len(context_period_roles.get(table_id, set())) >= 2
                    else "default"
                ),
            ).keep_current_value:
                return True
    return False


def align_dependency_rows_with_sibling_direct_context(
    dependency_rows: List[Dict[str, Any]],
    direct_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Align dependency rows only to a coherent sibling direct-row context."""

    if not dependency_rows or len(direct_rows) < 2:
        return dependency_rows

    aligned: List[Dict[str, Any]] = []
    changed = False
    for dependency_row in dependency_rows:
        candidate_selection = select_sibling_direct_operand_candidate(
            dependency_row,
            direct_rows,
        )
        candidate = candidate_selection.selected_row
        if candidate is None:
            if candidate_selection.reason == "ambiguous_conflicting_top_rank":
                aligned.append(
                    {
                        **dependency_row,
                        "sibling_table_context_realignment_blocked": True,
                        "sibling_table_context_realignment_blocked_reason": (
                            "ambiguous_direct_context_candidates"
                        ),
                    }
                )
                changed = True
                continue
            aligned.append(dependency_row)
            continue
        if not operand_row_values_differ(dependency_row, candidate):
            aligned.append(dependency_row)
            continue
        if decide_task_output_operand_resolution(
            dependency_row,
            candidate,
            context="coherent_ratio",
        ).keep_current_value:
            aligned.append(
                {
                    **dependency_row,
                    "sibling_table_context_realignment_blocked": True,
                    "sibling_table_context_realignment_blocked_reason": "task_output_value_provenance_mismatch",
                    "sibling_direct_candidate_selection_reason": candidate_selection.reason,
                }
            )
            changed = True
            continue
        aligned.append(
            {
                **dependency_row,
                "evidence_id": candidate.get("evidence_id") or dependency_row.get("evidence_id"),
                "source_row_id": (
                    candidate.get("source_row_id")
                    or candidate.get("evidence_id")
                    or dependency_row.get("source_row_id")
                ),
                "source_row_ids": _clean_source_row_ids(
                    [
                        candidate.get("source_row_id"),
                        candidate.get("source_row_ids"),
                    ]
                ),
                "source_anchor": candidate.get("source_anchor") or dependency_row.get("source_anchor"),
                "label": candidate.get("label") or dependency_row.get("label"),
                "raw_value": candidate.get("raw_value"),
                "raw_unit": candidate.get("raw_unit"),
                "normalized_value": candidate.get("normalized_value"),
                "normalized_unit": candidate.get("normalized_unit"),
                "period": candidate.get("period") or dependency_row.get("period"),
                "statement_type": candidate.get("statement_type") or dependency_row.get("statement_type"),
                "consolidation_scope": (
                    candidate.get("consolidation_scope")
                    or dependency_row.get("consolidation_scope")
                ),
                "table_source_id": candidate.get("table_source_id") or dependency_row.get("table_source_id"),
                "sibling_table_context_realigned": True,
                "sibling_direct_candidate_selection_reason": candidate_selection.reason,
            }
        )
        changed = True
    return aligned if changed else dependency_rows


def prefer_complete_ratio_direct_context_rows(
    *,
    operand_rows: List[Dict[str, Any]],
    direct_rows: List[Dict[str, Any]],
    required_operands: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Prefer complete ratio context without bypassing provenance decisions."""

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
        if (
            replacement
            and decide_task_output_operand_resolution(
                row,
                replacement,
                context=("coherent_ratio" if direct_has_coherent_context else "default"),
            ).keep_current_value
        ):
            preferred.append(
                {
                    **row,
                    "complete_ratio_direct_context_preference_blocked": True,
                    "complete_ratio_direct_context_preference_blocked_reason": (
                        "task_output_value_provenance_mismatch"
                    ),
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
    return merge_operand_rows(
        preferred,
        [],
        required_operands=required_operands,
    )


def dependency_projection_values_differ(left: Any, right: Any) -> bool:
    try:
        if left is not None and right is not None:
            return abs(float(left) - float(right)) > 1e-6
    except (TypeError, ValueError):
        pass
    return left != right


def dependency_projection_slot_differs_from_operand(
    slot: Dict[str, Any],
    operand: Dict[str, Any],
) -> bool:
    return any(
        (
            _normalise_spaces(str(slot.get("raw_value") or ""))
            != _normalise_spaces(str(operand.get("raw_value") or "")),
            _normalise_spaces(str(slot.get("raw_unit") or ""))
            != _normalise_spaces(str(operand.get("raw_unit") or "")),
            _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
            != _normalise_spaces(str(operand.get("normalized_unit") or "")).upper(),
            dependency_projection_values_differ(
                slot.get("normalized_value"),
                operand.get("normalized_value"),
            ),
        )
    )


def source_task_id_for_dependency_operand(operand: Dict[str, Any]) -> str:
    source_task_id = _normalise_spaces(str(operand.get("source_task_id") or ""))
    if source_task_id:
        return source_task_id
    for source_id in _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")]):
        if source_id.startswith("task_output:"):
            return source_id.split(":", 1)[1]
    return ""


def dependency_ratio_role_group(role: str) -> str:
    normalized = _normalise_spaces(str(role or ""))
    if normalized.startswith("numerator"):
        return "numerator"
    if normalized.startswith("denominator"):
        return "denominator"
    return ""


def dependency_lookup_slot_match_score(
    lookup_slot: Dict[str, Any],
    arithmetic_slot: Dict[str, Any],
    role: str,
) -> int:
    score = 0
    lookup_role = _normalise_spaces(str(lookup_slot.get("role") or ""))
    arithmetic_role = _normalise_spaces(str(arithmetic_slot.get("role") or role or ""))
    lookup_ratio_group = dependency_ratio_role_group(lookup_role)
    arithmetic_ratio_group = dependency_ratio_role_group(arithmetic_role)
    if lookup_ratio_group and arithmetic_ratio_group and lookup_ratio_group != arithmetic_ratio_group:
        return 0
    if lookup_role and arithmetic_role:
        if lookup_role == arithmetic_role:
            score += 2
        if lookup_role.startswith(f"{arithmetic_role}_") or arithmetic_role.startswith(f"{lookup_role}_"):
            score += 1
    lookup_concept = _normalise_spaces(str(lookup_slot.get("concept") or ""))
    arithmetic_concept = _normalise_spaces(
        str(arithmetic_slot.get("concept") or arithmetic_slot.get("matched_operand_concept") or "")
    )
    if lookup_concept and arithmetic_concept and lookup_concept == arithmetic_concept:
        score += 8
    lookup_label = _normalise_spaces(str(lookup_slot.get("label") or ""))
    arithmetic_label = _normalise_spaces(
        str(arithmetic_slot.get("label") or arithmetic_slot.get("matched_operand_label") or "")
    )
    if lookup_label and arithmetic_label:
        if lookup_label == arithmetic_label:
            score += 6
        elif _operand_text_match(lookup_label, {"label": arithmetic_label}):
            score += 4
        elif arithmetic_label in lookup_label or lookup_label in arithmetic_label:
            score += 3
    lookup_period = _normalise_spaces(str(lookup_slot.get("period") or ""))
    arithmetic_period = _normalise_spaces(str(arithmetic_slot.get("period") or ""))
    if score > 0 and lookup_period and arithmetic_period and lookup_period == arithmetic_period:
        score += 1
    return score


def dependency_operand_rows_share_source_value(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
    left_ids = set(_clean_source_row_ids([left.get("source_row_id"), left.get("source_row_ids")]))
    right_ids = set(_clean_source_row_ids([right.get("source_row_id"), right.get("source_row_ids")]))
    if not left_ids or not right_ids or not (left_ids & right_ids):
        return False
    try:
        left_value = left.get("normalized_value")
        right_value = right.get("normalized_value")
        if left_value is not None and right_value is not None:
            return abs(float(left_value) - float(right_value)) <= 1e-6
    except (TypeError, ValueError):
        pass
    return _normalise_spaces(str(left.get("raw_value") or "")) == _normalise_spaces(
        str(right.get("raw_value") or "")
    )


def dependency_source_slot_structurally_stronger(slot: Dict[str, Any]) -> bool:
    return bool(
        _normalise_spaces(str(slot.get("value_role") or "")).lower() == "aggregate"
        or _normalise_spaces(str(slot.get("aggregation_stage") or "")).lower()
        in {"final", "subtotal", "direct"}
    )


def dependency_operand_can_use_source_slot(
    operand: Dict[str, Any],
    source_slot: Dict[str, Any],
) -> bool:
    operand_source_ids = _clean_source_row_ids([operand.get("source_row_id"), operand.get("source_row_ids")])
    source_task_id = source_task_id_for_dependency_operand(operand)
    operand_role_group = dependency_ratio_role_group(
        str(operand.get("matched_operand_role") or operand.get("role") or "")
    )
    source_role_group = dependency_ratio_role_group(str(source_slot.get("role") or ""))
    if operand_role_group and source_role_group and operand_role_group != source_role_group:
        return False
    dependency_backed_operand = bool(
        source_task_id
        and (
            _normalise_spaces(str(operand.get("source_task_id") or ""))
            or any(source_id.startswith("task_output:") for source_id in operand_source_ids)
        )
    )
    source_slot_ids = _clean_source_row_ids([source_slot.get("source_row_id"), source_slot.get("source_row_ids")])
    role = _normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or ""))
    match_score = dependency_lookup_slot_match_score(source_slot, operand, role)
    strong_source_slot_match = bool(source_slot_ids and match_score >= 8)
    if operand_role_group and source_role_group != operand_role_group and match_score <= 0:
        return False
    return bool(
        dependency_backed_operand
        or dependency_source_slot_structurally_stronger(source_slot)
        or not operand_source_ids
        or strong_source_slot_match
    )


def _slot_from_single_answer_numeric(
    current_slot: Dict[str, Any],
    *,
    answer_text: str,
    result_row: Dict[str, Any],
) -> Dict[str, Any]:
    current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
    if current_raw and current_raw in answer_text:
        return {}
    candidates = [
        dict(candidate)
        for candidate in extract_numeric_surface_candidates(answer_text)
        if _normalise_spaces(str(candidate.get("text") or ""))
    ]
    if len(candidates) != 1:
        return {}
    candidate = candidates[0]
    components = numeric_surface_slot_components(candidate)
    if not components:
        return {}
    normalized_unit = _normalise_spaces(str(current_slot.get("normalized_unit") or ""))
    if not normalized_unit:
        normalized_unit = str(components.get("normalized_unit") or "UNKNOWN")
    return {
        **dict(current_slot),
        "status": "ok",
        "role": current_slot.get("role") or "primary_value",
        "label": _normalise_spaces(str(result_row.get("metric_label") or current_slot.get("label") or "")),
        "raw_value": components.get("raw_value"),
        "raw_unit": components.get("raw_unit") or _normalise_spaces(str(current_slot.get("raw_unit") or "")),
        "normalized_value": components.get("normalized_value"),
        "normalized_unit": normalized_unit,
        "rendered_value": components.get("rendered_value"),
    }


def _dependency_lookup_operation(
    result_row: Dict[str, Any],
    *,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
) -> str:
    metric_family = _normalise_spaces(str(result_row.get("metric_family") or "")).lower()
    operation = _normalise_spaces(
        str(result_row.get("operation_family") or operation_family_for_result(result_row) or "")
    ).lower()
    if metric_family in {"concept_lookup", "generic_numeric"} and operation not in {"lookup", "single_value"}:
        return "lookup"
    return operation


def resolve_dependency_producer_scope(
    binding: Mapping[str, Any],
    *,
    producer_tasks: Sequence[Mapping[str, Any]],
) -> DependencyProducerScope:
    """Resolve the first matching producer task and its binding-specific scope."""

    preferred_task_id = _normalise_spaces(str(binding.get("preferred_task_id") or ""))
    if not preferred_task_id:
        return DependencyProducerScope({}, (), ())

    producer_task: Dict[str, Any] = {}
    for task in producer_tasks:
        task_row = dict(task or {})
        if _normalise_spaces(str(task_row.get("task_id") or "")) == preferred_task_id:
            producer_task = task_row
            break
    if not producer_task:
        return DependencyProducerScope({}, (), ())

    preferred_statement_types: List[str] = []
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
        preferred_statement_types.extend(
            _normalise_spaces(str(item))
            for item in list(operand_row.get("preferred_statement_types") or [])
            if _normalise_spaces(str(item))
        )
        preferred_sections.extend(
            _normalise_spaces(str(item))
            for item in list(operand_row.get("preferred_sections") or [])
            if _normalise_spaces(str(item))
        )
    preferred_statement_types.extend(
        _normalise_spaces(str(item))
        for item in list(producer_task.get("preferred_statement_types") or [])
        if _normalise_spaces(str(item))
    )
    preferred_sections.extend(
        _normalise_spaces(str(item))
        for item in list(producer_task.get("preferred_sections") or [])
        if _normalise_spaces(str(item))
    )
    return DependencyProducerScope(
        producer_task=dict(producer_task),
        preferred_statement_types=tuple(dict.fromkeys(preferred_statement_types)),
        preferred_sections=tuple(dict.fromkeys(preferred_sections)),
    )


def _dependency_row_violates_producer_scope(
    row: Mapping[str, Any],
    *,
    preferred_statement_types: Sequence[str],
    preferred_sections: Sequence[str],
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
    note_markers = tuple(
        str(item).lower()
        for item in (scoring_policy.get("note_context_markers") or ())
        if str(item)
    )
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


def filter_direct_rows_by_dependency_producer_scope(
    *,
    bindings: Sequence[Mapping[str, Any]],
    operand_rows: Sequence[Mapping[str, Any]],
    producer_tasks: Sequence[Mapping[str, Any]],
) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Filter direct rows that violate the matched dependency producer scope."""

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
        producer_scope = resolve_dependency_producer_scope(
            matching_binding,
            producer_tasks=producer_tasks,
        )
        preferred_statement_types = list(producer_scope.preferred_statement_types)
        preferred_sections = list(producer_scope.preferred_sections)
        violates_scope, reject_reason = _dependency_row_violates_producer_scope(
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


def _dependency_producer_task(
    result_row: Dict[str, Any],
    *,
    task_by_id: Dict[str, Dict[str, Any]],
    result_task_id: str,
) -> Dict[str, Any]:
    producer_task = {
        **(
            dict(task_by_id.get(result_task_id) or {})
            or {
                "task_id": result_task_id,
                "metric_family": result_row.get("metric_family") or "concept_lookup",
                "operation_family": "lookup",
            }
        )
    }
    row_metric_label = _normalise_spaces(str(result_row.get("metric_label") or ""))
    if row_metric_label and not _normalise_spaces(str(producer_task.get("metric_label") or "")):
        producer_task["metric_label"] = row_metric_label
    if not producer_task.get("required_operands"):
        producer_task["required_operands"] = [
            {
                "label": producer_task.get("metric_label") or row_metric_label,
                "role": "primary_value",
                "period": "",
            }
        ]
    return producer_task


def _populate_answer_numeric_slot_context(
    answer_numeric_slot: Dict[str, Any],
    producer_task: Dict[str, Any],
) -> None:
    producer_required_operands = [
        dict(item)
        for item in (producer_task.get("required_operands") or [])
        if isinstance(item, dict) and bool(item.get("required", True))
    ]
    if len(producer_required_operands) != 1 or not answer_numeric_slot:
        return
    producer_operand = producer_required_operands[0]
    if not _normalise_spaces(str(answer_numeric_slot.get("concept") or "")):
        answer_numeric_slot["concept"] = _normalise_spaces(str(producer_operand.get("concept") or ""))
    if not _normalise_spaces(str(answer_numeric_slot.get("period") or "")):
        answer_numeric_slot["period"] = _normalise_spaces(str(producer_operand.get("period") or ""))


def _dependency_lookup_slot_for_result_row(
    result_row: Dict[str, Any],
    *,
    task_by_id: Dict[str, Dict[str, Any]],
    result_task_id: str,
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    result = dict(result_row.get("calculation_result") or {})
    result_slots = dict(result.get("answer_slots") or result_row.get("answer_slots") or {})
    slot = dict(result_slots.get("primary_value") or {})
    answer_text = _normalise_spaces(
        str(result_row.get("answer") or result.get("formatted_result") or result.get("rendered_value") or "")
    )
    answer_numeric_slot: Dict[str, Any] = {}
    if slot_has_material(slot) and answer_text:
        answer_numeric_slot = _slot_from_single_answer_numeric(
            slot,
            answer_text=answer_text,
            result_row=result_row,
        )
    if slot_has_material(slot) and not answer_numeric_slot:
        return slot

    producer_task = _dependency_producer_task(
        result_row,
        task_by_id=task_by_id,
        result_task_id=result_task_id,
    )
    _populate_answer_numeric_slot_context(answer_numeric_slot, producer_task)
    synthetic_result = _synthesize_lookup_answer_slot_from_prose(
        active_subtask=producer_task,
        answer=answer_text,
        calculation_result=result,
        selected_claim_ids=[
            str(claim_id).strip()
            for claim_id in (result_row.get("selected_claim_ids") or [])
            if str(claim_id).strip()
        ],
    )
    synthetic_slot_material = False
    if synthetic_result:
        synthetic_slots = dict(synthetic_result.get("answer_slots") or {})
        synthetic_slot = dict(synthetic_slots.get("primary_value") or {})
        if slot_has_material(synthetic_slot):
            slot = synthetic_slot
            synthetic_slot_material = True
    synthetic_raw = _normalise_spaces(str(slot.get("raw_value") or ""))
    synthetic_missing_concept = not _normalise_spaces(str(slot.get("concept") or ""))
    answer_numeric_has_concept = bool(_normalise_spaces(str(answer_numeric_slot.get("concept") or "")))
    if answer_numeric_slot and (
        not synthetic_slot_material
        or (synthetic_raw and synthetic_raw not in answer_text)
        or (synthetic_missing_concept and answer_numeric_has_concept)
    ):
        return answer_numeric_slot
    return slot


def build_dependency_lookup_slots_by_task(
    ordered_results: List[Dict[str, Any]],
    task_by_id: Dict[str, Dict[str, Any]],
    *,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Dict[str, Any]]:
    slots: Dict[str, Dict[str, Any]] = {}
    for result_row in ordered_results:
        result_task_id = _normalise_spaces(str(result_row.get("task_id") or ""))
        if not result_task_id:
            continue
        operation = _dependency_lookup_operation(
            result_row,
            operation_family_for_result=operation_family_for_result,
        )
        if operation not in {"lookup", "single_value"}:
            continue
        slot = _dependency_lookup_slot_for_result_row(
            result_row,
            task_by_id=task_by_id,
            result_task_id=result_task_id,
            slot_has_material=slot_has_material,
        )
        if slot_has_material(slot):
            slot = dict(slot)
            slot["source_task_id"] = result_task_id
            if not _clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]):
                slot["source_row_id"] = f"task_output:{result_task_id}"
                slot["source_row_ids"] = [f"task_output:{result_task_id}"]
            slots[result_task_id] = slot
    return slots


def collect_table_label_evidence_candidates(
    ordered_results: List[Dict[str, Any]],
    state: Dict[str, Any],
) -> List[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for evidence_source in [
        *(row.get("runtime_evidence") or [] for row in ordered_results if isinstance(row, dict)),
        state.get("evidence_items") or [],
        state.get("runtime_evidence") or [],
    ]:
        for evidence_item in list(evidence_source or []):
            if not isinstance(evidence_item, dict):
                continue
            metadata = dict(evidence_item.get("metadata") or {})
            if not _normalise_spaces(str(metadata.get("table_value_labels_text") or "")):
                continue
            evidence_key = _normalise_spaces(
                str(
                    evidence_item.get("evidence_id")
                    or metadata.get("chunk_uid")
                    or evidence_item.get("source_anchor")
                    or len(candidates)
                )
            )
            if evidence_key in seen:
                continue
            seen.add(evidence_key)
            candidates.append(dict(evidence_item))
    return candidates


def _dependency_operand_from_slot(
    operand: Dict[str, Any],
    slot: Dict[str, Any],
    *,
    source_row_ids: List[str],
    evidence_id: Any,
    source_row_id: Any,
    extra_fields: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    row = {
        **dict(operand),
        "evidence_id": evidence_id,
        "source_row_id": source_row_id,
        "source_row_ids": source_row_ids,
        "normalized_value": slot.get("normalized_value"),
        "normalized_unit": _normalise_spaces(
            str(slot.get("normalized_unit") or operand.get("normalized_unit") or "UNKNOWN")
        ).upper()
        or "UNKNOWN",
        "matched_operand_label": _normalise_spaces(
            str(operand.get("matched_operand_label") or slot.get("label") or "")
        ),
        "matched_operand_concept": _normalise_spaces(
            str(operand.get("matched_operand_concept") or slot.get("concept") or "")
        ),
        "matched_operand_role": _normalise_spaces(
            str(operand.get("matched_operand_role") or operand.get("role") or slot.get("role") or "")
        ),
        "stated_change_raw_value": _normalise_spaces(str(slot.get("stated_change_raw_value") or "")),
        "stated_change_raw_unit": _normalise_spaces(str(slot.get("stated_change_raw_unit") or "")),
    }
    for key in ("source_anchor", "label", "raw_value", "raw_unit", "period"):
        row[key] = _normalise_spaces(str(slot.get(key) or operand.get(key) or ""))
    if extra_fields:
        row.update(extra_fields)
    return row


def dependency_operand_from_source_slot(
    operand: Dict[str, Any],
    slot: Dict[str, Any],
    *,
    source_task_id: str,
) -> Dict[str, Any]:
    source_row_ids = _clean_source_row_ids([
        f"task_output:{source_task_id}",
        slot.get("source_row_id"),
        slot.get("source_row_ids"),
    ])
    task_output_id = f"task_output:{source_task_id}"
    return _dependency_operand_from_slot(
        operand,
        slot,
        source_row_ids=source_row_ids or [task_output_id],
        evidence_id=task_output_id,
        source_row_id=source_row_ids[0] if source_row_ids else task_output_id,
        extra_fields={
            "source_task_id": source_task_id,
            "source_slot": _normalise_spaces(str(operand.get("source_slot") or "primary_value")) or "primary_value",
            "dependency_resolved": True,
        },
    )


def dependency_operand_from_answer_slot(
    operand: Dict[str, Any],
    slot: Dict[str, Any],
) -> Dict[str, Any]:
    source_row_ids = _clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")])
    return _dependency_operand_from_slot(
        operand,
        slot,
        source_row_ids=source_row_ids,
        evidence_id=source_row_ids[0] if source_row_ids else operand.get("evidence_id"),
        source_row_id=source_row_ids[0] if source_row_ids else operand.get("source_row_id"),
    )


def dependency_operand_from_table_label_evidence(
    operand: Dict[str, Any],
    table_label_evidence_candidates: List[Dict[str, Any]],
    *,
    lookup_value_from_table_label_metadata: Callable[[Dict[str, Any], Dict[str, Any]], Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> Dict[str, Any]:
    for evidence_item in table_label_evidence_candidates:
        slot = lookup_value_from_table_label_metadata(operand, evidence_item)
        if not slot_has_material(slot):
            continue
        return dependency_operand_from_answer_slot(operand, slot)
    return {}


def dependency_slot_candidates_from_answer_slots(
    answer_slots: Dict[str, Any],
    active_subtask: Dict[str, Any],
    *,
    ratio_role_group: Callable[[str], str],
) -> tuple[Dict[str, Dict[str, Any]], Dict[str, Dict[str, Any]], List[tuple[str, Dict[str, Any]]]]:
    required_operands_by_role: Dict[str, Dict[str, Any]] = {}
    required_operands_by_group: Dict[str, Dict[str, Any]] = {}
    for required_operand in list(active_subtask.get("required_operands") or active_subtask.get("inputs") or []):
        if not isinstance(required_operand, dict) or not bool(required_operand.get("required", True)):
            continue
        required_role = _normalise_spaces(str(required_operand.get("role") or ""))
        if required_role:
            required_operands_by_role.setdefault(required_role, dict(required_operand))
        required_group = ratio_role_group(required_role)
        if required_group:
            required_operands_by_group.setdefault(required_group, dict(required_operand))

    slot_candidates: List[tuple[str, Dict[str, Any]]] = []
    for role, slot_key in (
        ("current_period", "current_value"),
        ("prior_period", "prior_value"),
        ("minuend", "minuend"),
        ("subtrahend", "subtrahend"),
    ):
        slot = dict(answer_slots.get(slot_key) or {})
        if slot:
            slot_candidates.append((role, slot))
    components_by_role = dict(answer_slots.get("components_by_role") or {})
    dependency_role_prefixes = (
        "current_period",
        "prior_period",
        "minuend",
        "subtrahend",
        "numerator",
        "denominator",
    )
    for role_key, entries in components_by_role.items():
        role = _normalise_spaces(str(role_key or ""))
        if not role:
            continue
        if role not in dependency_role_prefixes and not any(
            role.startswith(f"{prefix}_") for prefix in dependency_role_prefixes
        ):
            continue
        for slot in list(entries or []):
            if isinstance(slot, dict):
                slot_candidates.append((role, dict(slot)))
    components_by_group = dict(answer_slots.get("components_by_group") or {})
    for group_key, entries in components_by_group.items():
        group = _normalise_spaces(str(group_key or ""))
        if group not in {"numerator", "denominator"}:
            continue
        for slot in list(entries or []):
            if not isinstance(slot, dict):
                continue
            role = _normalise_spaces(str(slot.get("role") or group))
            if not role.startswith(group):
                role = group
            slot_candidates.append((role, dict(slot)))
    return required_operands_by_role, required_operands_by_group, slot_candidates


def derive_dependency_operands_from_source_task_slots(
    row: Dict[str, Any],
    *,
    active_subtask: Dict[str, Any],
    operation_family: str,
    task_id: str,
    lookup_slots_by_task: Dict[str, Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    ratio_role_group: Callable[[str], str],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
) -> List[Dict[str, Any]]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    required_operands_by_role, required_operands_by_group, slot_candidates = (
        dependency_slot_candidates_from_answer_slots(
            answer_slots,
            active_subtask,
            ratio_role_group=ratio_role_group,
        )
    )

    derived: List[Dict[str, Any]] = []
    seen_keys: set[str] = set()
    for role, slot in slot_candidates:
        if not slot_has_material(slot):
            continue
        required_operand = dict(
            required_operands_by_role.get(role)
            or required_operands_by_group.get(ratio_role_group(role))
            or {}
        )
        operand_seed = {
            "operand_id": _normalise_spaces(str(slot.get("operand_id") or role or f"operand_{len(derived) + 1}")),
            "matched_operand_role": role,
            "role": role,
            "label": _normalise_spaces(str(required_operand.get("label") or slot.get("label") or "")),
            "matched_operand_label": _normalise_spaces(
                str(required_operand.get("label") or slot.get("label") or "")
            ),
            "concept": _normalise_spaces(str(required_operand.get("concept") or slot.get("concept") or "")),
            "matched_operand_concept": _normalise_spaces(
                str(required_operand.get("concept") or slot.get("concept") or "")
            ),
            "source_row_id": slot.get("source_row_id"),
            "source_row_ids": slot.get("source_row_ids"),
            "source_task_id": slot.get("source_task_id"),
            "source_slot": slot.get("source_slot") or "primary_value",
        }
        source_task_id = source_task_id_for_operand(operand_seed)
        source_slot = dict(lookup_slots_by_task.get(source_task_id) or {})
        if not source_task_id or not slot_has_material(source_slot):
            excluded_source_task_ids: set[str] = set()
            if operation_family == "ratio":
                role_group = ratio_role_group(role)
                excluded_source_task_ids = {
                    source_task_id_for_operand(derived_operand)
                    for derived_operand in derived
                    if source_task_id_for_operand(derived_operand)
                    and ratio_role_group(
                        _normalise_spaces(
                            str(
                                derived_operand.get("matched_operand_role")
                                or derived_operand.get("role")
                                or ""
                            )
                        )
                    )
                    not in {"", role_group}
                }
            source_task_id, source_slot = lookup_source_for_arithmetic_slot(
                current_task_id=task_id,
                role=role,
                slot=operand_seed,
                excluded_task_ids=excluded_source_task_ids,
            )
        if (
            source_task_id
            and slot_has_material(source_slot)
            and operand_can_use_source_slot(operand_seed, source_slot)
        ):
            derived_operand = operand_from_source_slot(
                operand_seed,
                source_slot,
                source_task_id=source_task_id,
            )
        else:
            continue
        key = "|".join(
            (
                str(derived_operand.get("matched_operand_role") or ""),
                str(derived_operand.get("source_task_id") or ""),
                str(derived_operand.get("raw_value") or ""),
                str(derived_operand.get("raw_unit") or ""),
            )
        )
        if key in seen_keys:
            continue
        seen_keys.add(key)
        derived.append(derived_operand)
    return derived


def build_fallback_dependency_operation_plan(
    derived_operands: List[Dict[str, Any]],
    *,
    operation_family: str,
    active_subtask: Dict[str, Any],
    calculation_result: Dict[str, Any],
) -> Dict[str, Any]:
    def _operand_for_role_prefix(prefix: str) -> Dict[str, Any]:
        return next(
            (
                operand
                for operand in derived_operands
                if _normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or "")).startswith(prefix)
            ),
            {},
        )

    if operation_family == "ratio":
        numerator = _operand_for_role_prefix("numerator")
        denominator = _operand_for_role_prefix("denominator")
        if not numerator or not denominator:
            return {}
        numerator_id = _normalise_spaces(str(numerator.get("operand_id") or ""))
        denominator_id = _normalise_spaces(str(denominator.get("operand_id") or ""))
        if not numerator_id or not denominator_id:
            return {}
        result_unit = _normalise_spaces(str(calculation_result.get("result_unit") or ""))
        if not result_unit:
            result_unit = "%"
        formula = "((A) / (B)) * 100" if result_unit in {"%", "%p"} else "((A) / (B))"
        numerator_label = _normalise_spaces(str(numerator.get("label") or numerator.get("matched_operand_label") or "A"))
        denominator_label = _normalise_spaces(
            str(denominator.get("label") or denominator.get("matched_operand_label") or "B")
        )
        metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("task_id") or ""))
        return {
            "status": "ok",
            "mode": "single_value",
            "operation": "ratio",
            "ordered_operand_ids": [numerator_id, denominator_id],
            "variable_bindings": [
                {"variable": "A", "operand_id": numerator_id},
                {"variable": "B", "operand_id": denominator_id},
            ],
            "formula": formula,
            "pairwise_formula": "",
            "result_unit": result_unit,
            "operation_text": f"{numerator_label} / {denominator_label}",
            "explanation": f"{metric_label or 'ratio'} is recomputed from stronger dependency task outputs.",
            "missing_info": [],
        }
    if operation_family != "growth_rate":
        return {}
    current = _operand_for_role_prefix("current_period")
    prior = _operand_for_role_prefix("prior_period")
    if not current or not prior:
        return {}
    current_id = _normalise_spaces(str(current.get("operand_id") or ""))
    prior_id = _normalise_spaces(str(prior.get("operand_id") or ""))
    if not current_id or not prior_id:
        return {}
    metric_label = _normalise_spaces(str(active_subtask.get("metric_label") or active_subtask.get("task_id") or ""))
    current_label = _normalise_spaces(str(current.get("label") or current.get("matched_operand_label") or "A"))
    prior_label = _normalise_spaces(str(prior.get("label") or prior.get("matched_operand_label") or "B"))
    return {
        "status": "ok",
        "mode": "single_value",
        "operation": "growth_rate",
        "ordered_operand_ids": [current_id, prior_id],
        "variable_bindings": [
            {"variable": "A", "operand_id": current_id},
            {"variable": "B", "operand_id": prior_id},
        ],
        "formula": "((A - B) / B) * 100",
        "pairwise_formula": "",
        "result_unit": "%",
        "operation_text": f"({current_label} - {prior_label}) / {prior_label} * 100",
        "explanation": (
            f"{metric_label or 'growth rate'} is computed as ((A - B) / B) * 100 "
            "from dependency task outputs."
        ),
        "missing_info": [],
    }


def dependency_plan_is_executable(plan: Dict[str, Any]) -> bool:
    plan_status = _normalise_spaces(str(plan.get("status") or "")).lower()
    plan_operation = _normalise_spaces(str(plan.get("operation") or "")).lower()
    plan_operand_ids = [
        _normalise_spaces(str(operand_id or ""))
        for operand_id in (plan.get("ordered_operand_ids") or [])
        if _normalise_spaces(str(operand_id or ""))
    ]
    return bool(
        plan
        and plan_status not in {"incomplete", "empty", "missing"}
        and plan_operation not in {"", "none"}
        and plan_operand_ids
    )


def rebuild_dependency_calculation_plan(
    calculation_plan: Dict[str, Any],
    *,
    state: Dict[str, Any],
    active_subtask: Dict[str, Any],
    updated_operands: List[Dict[str, Any]],
    operation_family: str,
    calculation_result: Dict[str, Any],
    build_deterministic_operation_plan: Callable[[Dict[str, Any], List[Dict[str, Any]]], Dict[str, Any]],
) -> Dict[str, Any]:
    if not dependency_plan_is_executable(calculation_plan):
        calculation_plan = {}
    if calculation_plan:
        return calculation_plan
    plan_state = {
        **dict(state),
        "active_subtask": active_subtask,
        "calculation_operands": updated_operands,
        "resolved_calculation_trace": {
            "calculation_operands": updated_operands,
            "calculation_plan": {},
            "calculation_result": {},
        },
    }
    calculation_plan = build_deterministic_operation_plan(plan_state, updated_operands) or {}
    if not dependency_plan_is_executable(calculation_plan):
        calculation_plan = build_fallback_dependency_operation_plan(
            updated_operands,
            operation_family=operation_family,
            active_subtask=active_subtask,
            calculation_result=calculation_result,
        )
    return calculation_plan


def build_dependency_recalculation_state(
    state: Dict[str, Any],
    *,
    active_subtask: Dict[str, Any],
    updated_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    calculation_result: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        **dict(state),
        "active_subtask": active_subtask,
        "calculation_operands": updated_operands,
        "calculation_plan": calculation_plan,
        "calculation_result": dict(calculation_result),
        "resolved_calculation_trace": {
            "calculation_operands": updated_operands,
            "calculation_plan": calculation_plan,
            "calculation_result": dict(calculation_result),
        },
        "tasks": [],
        "artifacts": [],
    }


def apply_absolute_ratio_magnitude_if_requested(
    calculation_result: Dict[str, Any],
    *,
    format_calculation_value: Callable[[float, str, str], str],
) -> Dict[str, Any]:
    updated = dict(calculation_result)
    try:
        recalculated_value = updated.get("result_value")
        if recalculated_value is None or float(recalculated_value) >= 0:
            return updated
        absolute_value = abs(float(recalculated_value))
        updated["result_value"] = absolute_value
        result_unit = str(updated.get("result_unit") or "%")
        absolute_rendered = format_calculation_value(absolute_value, result_unit, "PERCENT")
        if result_unit in {"%", "%p"} and "%" not in absolute_rendered:
            absolute_rendered = f"{absolute_rendered}{result_unit or '%'}"
        updated["rendered_value"] = absolute_rendered
        recalculated_slots = dict(updated.get("answer_slots") or {})
        recalculated_primary = dict(recalculated_slots.get("primary_value") or {})
        recalculated_primary["normalized_value"] = absolute_value
        recalculated_primary["normalized_unit"] = "PERCENT"
        recalculated_primary["raw_unit"] = recalculated_primary.get("raw_unit") or "%"
        recalculated_primary["rendered_value"] = absolute_rendered
        recalculated_slots["primary_value"] = recalculated_primary
        updated["answer_slots"] = recalculated_slots
    except (TypeError, ValueError):
        return updated
    return updated


def build_dependency_recalculated_row(
    row: Dict[str, Any],
    *,
    recalculated_trace: Dict[str, Any],
    updated_operands: List[Dict[str, Any]],
    calculation_plan: Dict[str, Any],
    recalculated_result: Dict[str, Any],
    formatted_answer: str,
) -> Dict[str, Any]:
    return {
        **dict(row),
        "answer": formatted_answer or str(row.get("answer") or ""),
        "status": "ok",
        "calculation_operands": list(recalculated_trace.get("calculation_operands") or updated_operands),
        "calculation_plan": dict(recalculated_trace.get("calculation_plan") or calculation_plan),
        "calculation_result": recalculated_result,
        "source_row_ids": list(recalculated_result.get("source_row_ids") or row.get("source_row_ids") or []),
        "aligned_from_source_task_slots": True,
    }


def refresh_dependency_operands_from_lookup_slots(
    operands: List[Dict[str, Any]],
    *,
    task_id: str,
    lookup_slots_by_task: Dict[str, Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
    slot_differs_from_operand: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], bool]:
    updated_operands: List[Dict[str, Any]] = []
    changed = False
    for operand in operands:
        source_task_id = source_task_id_for_operand(operand)
        source_slot = dict(lookup_slots_by_task.get(source_task_id) or {})
        if not source_task_id or not slot_has_material(source_slot):
            source_task_id, source_slot = lookup_source_for_arithmetic_slot(
                current_task_id=task_id,
                role=_normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or "")),
                slot=operand,
            )
        if (
            source_task_id
            and slot_has_material(source_slot)
            and slot_differs_from_operand(source_slot, operand)
            and operand_can_use_source_slot(operand, source_slot)
        ):
            updated_operands.append(
                operand_from_source_slot(
                    operand,
                    source_slot,
                    source_task_id=source_task_id,
                )
            )
            changed = True
        else:
            updated_operands.append(operand)
    return updated_operands, changed


def dedupe_dependency_operands_by_id(operands: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped_operands: List[Dict[str, Any]] = []
    operand_index_by_id: Dict[str, int] = {}
    for operand in operands:
        operand_id = _normalise_spaces(str(operand.get("operand_id") or ""))
        if not operand_id:
            deduped_operands.append(operand)
            continue
        existing_index = operand_index_by_id.get(operand_id)
        if existing_index is None:
            operand_index_by_id[operand_id] = len(deduped_operands)
            deduped_operands.append(operand)
        else:
            deduped_operands[existing_index] = operand
    return deduped_operands


def _numeric_values_differ(left: Any, right: Any) -> bool:
    try:
        if left is not None and right is not None:
            return abs(float(left) - float(right)) > 1e-6
    except (TypeError, ValueError):
        pass
    return left != right


def _ratio_dependency_present_groups(
    operands: List[Dict[str, Any]],
    *,
    ratio_role_group: Callable[[str], str],
) -> set[str]:
    present_groups = {
        ratio_role_group(_normalise_spaces(str(operand.get("matched_operand_role") or operand.get("role") or "")))
        for operand in operands
    }
    present_groups.discard("")
    return present_groups


def _required_ratio_dependency_operands(active_subtask: Dict[str, Any]) -> List[Dict[str, Any]]:
    return [
        dict(item)
        for item in (active_subtask.get("required_operands") or active_subtask.get("inputs") or [])
        if bool(item.get("required", True))
    ]


def _lookup_like_result_for_ratio_dependency(
    result_row: Dict[str, Any],
    *,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
) -> bool:
    result_operation = _normalise_spaces(
        str(result_row.get("operation_family") or operation_family_for_result(result_row) or "")
    ).lower()
    result_metric_family = _normalise_spaces(str(result_row.get("metric_family") or "")).lower()
    return bool(
        result_operation in {"lookup", "single_value"}
        or result_metric_family in {"concept_lookup", "generic_numeric"}
    )


def _primary_answer_slot_from_result_row(result_row: Dict[str, Any]) -> Dict[str, Any]:
    return dict(
        (
            dict(result_row.get("calculation_result") or {}).get("answer_slots")
            or result_row.get("answer_slots")
            or {}
        ).get("primary_value")
        or {}
    )


def _append_inferred_denominator_requirement(
    required_operands: List[Dict[str, Any]],
    *,
    updated_operands: List[Dict[str, Any]],
    ordered_results: List[Dict[str, Any]],
    task_id: str,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    ratio_role_group: Callable[[str], str],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
) -> List[Dict[str, Any]]:
    existing_required_groups = {
        ratio_role_group(_normalise_spaces(str(operand.get("role") or "")))
        for operand in required_operands
    }
    if "denominator" in existing_required_groups:
        return required_operands
    used_source_task_ids = {
        source_task_id
        for source_task_id in (source_task_id_for_operand(operand) for operand in updated_operands)
        if source_task_id
    }
    for result_row in ordered_results:
        result_task_id = _normalise_spaces(str(result_row.get("task_id") or ""))
        if not result_task_id or result_task_id == task_id or result_task_id in used_source_task_ids:
            continue
        if not _lookup_like_result_for_ratio_dependency(
            result_row,
            operation_family_for_result=operation_family_for_result,
        ):
            continue
        result_label = _normalise_spaces(str(result_row.get("metric_label") or ""))
        if not result_label:
            continue
        result_slot = _primary_answer_slot_from_result_row(result_row)
        return [
            *required_operands,
            {
                "role": "denominator_1",
                "label": result_label,
                "concept": _normalise_spaces(str(result_slot.get("concept") or "")),
                "required": True,
            },
        ]
    return required_operands


def _ratio_dependency_operand_seed(
    required_operand: Dict[str, Any],
    *,
    required_role: str,
    operand_count: int,
) -> Dict[str, Any]:
    label = _normalise_spaces(str(required_operand.get("label") or ""))
    concept = _normalise_spaces(str(required_operand.get("concept") or ""))
    return {
        "operand_id": _normalise_spaces(
            str(required_operand.get("operand_id") or f"{required_role}_{operand_count + 1}")
        ),
        "matched_operand_role": required_role,
        "role": required_role,
        "label": label,
        "matched_operand_label": label,
        "concept": concept,
        "matched_operand_concept": concept,
    }


def _ratio_dependency_source_operand_seed(
    operand_seed: Dict[str, Any],
    required_operand: Dict[str, Any],
    source_slot: Dict[str, Any],
) -> Dict[str, Any]:
    label = _normalise_spaces(str(required_operand.get("label") or source_slot.get("label") or ""))
    concept = _normalise_spaces(str(required_operand.get("concept") or source_slot.get("concept") or ""))
    return {
        **operand_seed,
        "label": label,
        "matched_operand_label": label,
        "concept": concept,
        "matched_operand_concept": concept,
    }


def _dependency_operand_is_duplicate_source_value(
    operand: Dict[str, Any],
    existing_operands: List[Dict[str, Any]],
    *,
    operand_rows_share_source_value: Callable[[Dict[str, Any], Dict[str, Any]], bool],
) -> bool:
    return any(
        operand_rows_share_source_value(operand, existing_operand)
        for existing_operand in existing_operands
    )


def _ratio_dependency_operand_from_source(
    operand_seed: Dict[str, Any],
    required_operand: Dict[str, Any],
    *,
    task_id: str,
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
) -> Dict[str, Any]:
    required_role = _normalise_spaces(str(required_operand.get("role") or ""))
    source_task_id, source_slot = lookup_source_for_arithmetic_slot(
        current_task_id=task_id,
        role=required_role,
        slot=required_operand,
    )
    if not source_task_id or not slot_has_material(source_slot):
        return {}
    source_operand_seed = _ratio_dependency_source_operand_seed(
        operand_seed,
        required_operand,
        source_slot,
    )
    if not operand_can_use_source_slot(source_operand_seed, source_slot):
        return {}
    return operand_from_source_slot(
        source_operand_seed,
        source_slot,
        source_task_id=source_task_id,
    )


def _missing_ratio_dependency_operand(
    required_operand: Dict[str, Any],
    *,
    updated_operands: List[Dict[str, Any]],
    task_id: str,
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
    operand_from_table_label_evidence: Callable[[Dict[str, Any]], Dict[str, Any]],
    operand_rows_share_source_value: Callable[[Dict[str, Any], Dict[str, Any]], bool],
) -> Dict[str, Any]:
    required_role = _normalise_spaces(str(required_operand.get("role") or ""))
    operand_seed = _ratio_dependency_operand_seed(
        required_operand,
        required_role=required_role,
        operand_count=len(updated_operands),
    )
    source_operand = _ratio_dependency_operand_from_source(
        operand_seed,
        required_operand,
        task_id=task_id,
        lookup_source_for_arithmetic_slot=lookup_source_for_arithmetic_slot,
        slot_has_material=slot_has_material,
        operand_can_use_source_slot=operand_can_use_source_slot,
        operand_from_source_slot=operand_from_source_slot,
    )
    if source_operand and not _dependency_operand_is_duplicate_source_value(
        source_operand,
        updated_operands,
        operand_rows_share_source_value=operand_rows_share_source_value,
    ):
        return source_operand
    table_operand = operand_from_table_label_evidence(operand_seed)
    if table_operand and not _dependency_operand_is_duplicate_source_value(
        table_operand,
        updated_operands,
        operand_rows_share_source_value=operand_rows_share_source_value,
    ):
        return table_operand
    return {}


def fill_missing_ratio_dependency_operands(
    updated_operands: List[Dict[str, Any]],
    *,
    ordered_results: List[Dict[str, Any]],
    active_subtask: Dict[str, Any],
    task_id: str,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    lookup_source_for_arithmetic_slot: Callable[..., tuple[str, Dict[str, Any]]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    operand_can_use_source_slot: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    operand_from_source_slot: Callable[..., Dict[str, Any]],
    operand_from_table_label_evidence: Callable[[Dict[str, Any]], Dict[str, Any]],
    operand_rows_share_source_value: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    ratio_role_group: Callable[[str], str],
    source_task_id_for_operand: Callable[[Dict[str, Any]], str],
) -> tuple[List[Dict[str, Any]], bool]:
    present_groups = _ratio_dependency_present_groups(updated_operands, ratio_role_group=ratio_role_group)
    required_operands = _required_ratio_dependency_operands(active_subtask)
    if "denominator" not in present_groups:
        required_operands = _append_inferred_denominator_requirement(
            required_operands,
            updated_operands=updated_operands,
            ordered_results=ordered_results,
            task_id=task_id,
            operation_family_for_result=operation_family_for_result,
            ratio_role_group=ratio_role_group,
            source_task_id_for_operand=source_task_id_for_operand,
        )

    changed = False
    for required_operand in required_operands:
        required_role = _normalise_spaces(str(required_operand.get("role") or ""))
        required_group = ratio_role_group(required_role)
        if required_group not in {"numerator", "denominator"} or required_group in present_groups:
            continue
        missing_operand = _missing_ratio_dependency_operand(
            required_operand,
            updated_operands=updated_operands,
            task_id=task_id,
            lookup_source_for_arithmetic_slot=lookup_source_for_arithmetic_slot,
            slot_has_material=slot_has_material,
            operand_can_use_source_slot=operand_can_use_source_slot,
            operand_from_source_slot=operand_from_source_slot,
            operand_from_table_label_evidence=operand_from_table_label_evidence,
            operand_rows_share_source_value=operand_rows_share_source_value,
        )
        if not missing_operand:
            continue
        updated_operands.append(missing_operand)
        present_groups.add(required_group)
        changed = True
    return updated_operands, changed


def _required_operands_for_lookup_realignment(
    row: Dict[str, Any],
    task: Dict[str, Any],
    current_slot: Dict[str, Any],
) -> List[Dict[str, Any]]:
    required_operands = [
        dict(item)
        for item in (task.get("required_operands") or [])
        if bool(item.get("required", True))
    ]
    if len(required_operands) == 1 or not current_slot:
        return required_operands
    fallback_operand = {
        "label": current_slot.get("label") or row.get("metric_label"),
        "concept": current_slot.get("concept"),
        "role": current_slot.get("role") or "primary_value",
        "required": True,
    }
    if _normalise_spaces(str(fallback_operand.get("label") or fallback_operand.get("concept") or "")):
        return [fallback_operand]
    return required_operands


def _lookup_realignment_candidate(
    projected_operands: List[Dict[str, Any]],
    required_operand: Dict[str, Any],
    *,
    projection_operand_matches_lookup: Callable[[Dict[str, Any], Dict[str, Any]], bool],
) -> Dict[str, Any]:
    return next(
        (
            dict(item)
            for item in projected_operands
            if projection_operand_matches_lookup(dict(item), required_operand)
        ),
        {},
    )


def _lookup_realignment_source_context(
    task_id: str,
    candidate: Dict[str, Any],
    current_slot: Dict[str, Any],
) -> Dict[str, Any]:
    source_ids = _clean_source_row_ids([candidate.get("source_row_id"), candidate.get("source_row_ids")])
    current_source_ids = _clean_source_row_ids([current_slot.get("source_row_id"), current_slot.get("source_row_ids")])
    return {
        "source_ids": source_ids,
        "direct_source_ids": [source_id for source_id in source_ids if not source_id.startswith("task_output:")],
        "direct_current_source_ids": [
            source_id for source_id in current_source_ids if not source_id.startswith("task_output:")
        ],
        "self_task_projection": f"task_output:{task_id}" in source_ids,
    }


def _lookup_realignment_source_context_allowed(
    candidate: Dict[str, Any],
    current_slot: Dict[str, Any],
    source_context: Dict[str, Any],
) -> bool:
    direct_source_ids = source_context["direct_source_ids"]
    direct_current_source_ids = source_context["direct_current_source_ids"]
    source_overlap_required = direct_current_source_ids and direct_source_ids
    source_ids_disjoint = source_overlap_required and not (set(direct_current_source_ids) & set(direct_source_ids))
    candidate_anchor = _normalise_spaces(str(candidate.get("source_anchor") or ""))
    current_anchor = _normalise_spaces(str(current_slot.get("source_anchor") or ""))
    source_anchor_conflict = bool(candidate_anchor and current_anchor and candidate_anchor != current_anchor)
    return bool(source_context["self_task_projection"] or not (source_ids_disjoint or source_anchor_conflict))


def _self_task_lookup_realignment_allowed(
    candidate: Dict[str, Any],
    current_slot: Dict[str, Any],
    source_context: Dict[str, Any],
) -> bool:
    if not source_context["self_task_projection"]:
        return True
    candidate_raw = _normalise_spaces(str(candidate.get("raw_value") or ""))
    current_raw = _normalise_spaces(str(current_slot.get("raw_value") or ""))
    candidate_unit = _normalise_spaces(str(candidate.get("raw_unit") or ""))
    current_unit = _normalise_spaces(str(current_slot.get("raw_unit") or ""))
    direct_source_ids = source_context["direct_source_ids"]
    direct_current_source_ids = source_context["direct_current_source_ids"]
    evidence_backed_unit_realignment = bool(
        direct_source_ids
        and (not direct_current_source_ids or bool(set(direct_source_ids) & set(direct_current_source_ids)))
        and candidate_unit
        and current_unit
        and candidate_unit != current_unit
    )
    normalized_differs = _numeric_values_differ(
        candidate.get("normalized_value"),
        current_slot.get("normalized_value"),
    )
    return not (candidate_raw == current_raw and normalized_differs and not evidence_backed_unit_realignment)


def _lookup_realignment_primary_slot(
    candidate: Dict[str, Any],
    required_operand: Dict[str, Any],
    current_slot: Dict[str, Any],
    direct_source_ids: List[str],
    *,
    build_operand_value_slot: Callable[..., Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any]]:
    component_slot = build_operand_value_slot(
        candidate,
        default_role=str(
            candidate.get("matched_operand_role")
            or required_operand.get("role")
            or current_slot.get("role")
            or "primary_value"
        ),
        preserve_source_display=True,
    )
    if direct_source_ids:
        component_slot["source_row_id"] = direct_source_ids[0]
        component_slot["source_row_ids"] = direct_source_ids
    return component_slot, {**component_slot, "role": "primary_value"}


def _lookup_realignment_updated_slots(
    answer_slots: Dict[str, Any],
    component_slot: Dict[str, Any],
    primary_slot: Dict[str, Any],
) -> Dict[str, Any]:
    updated_slots = dict(answer_slots)
    updated_slots["primary_value"] = primary_slot
    role_key = _normalise_spaces(str(component_slot.get("role") or ""))
    if not role_key:
        return updated_slots
    components_by_role = dict(updated_slots.get("components_by_role") or {})
    components_by_role[role_key] = [component_slot]
    updated_slots["components_by_role"] = components_by_role
    group_key = "denominator" if role_key.startswith("denominator") else "numerator"
    components_by_group = dict(updated_slots.get("components_by_group") or {})
    components_by_group[group_key] = [component_slot]
    updated_slots["components_by_group"] = components_by_group
    return updated_slots


def _lookup_realignment_updated_result(
    calculation_result: Dict[str, Any],
    primary_slot: Dict[str, Any],
    updated_slots: Dict[str, Any],
    rendered_value: str,
    result_source_ids: List[str],
) -> Dict[str, Any]:
    return {
        **calculation_result,
        "status": "ok",
        "result_value": primary_slot.get("normalized_value"),
        "result_unit": primary_slot.get("raw_unit") or calculation_result.get("result_unit"),
        "rendered_value": rendered_value,
        "formatted_result": rendered_value,
        "series": [
            {
                "label": primary_slot.get("label"),
                "period": primary_slot.get("period"),
                "raw_value": primary_slot.get("raw_value"),
                "raw_unit": primary_slot.get("raw_unit"),
                "normalized_value": primary_slot.get("normalized_value"),
                "normalized_unit": primary_slot.get("normalized_unit"),
                "rendered_value": rendered_value,
            }
        ],
        "current_value": primary_slot.get("normalized_value"),
        "current_period": primary_slot.get("period") or calculation_result.get("current_period"),
        "source_row_ids": result_source_ids,
        "answer_slots": updated_slots,
    }


def realign_lookup_row_from_dependency_projection(
    row: Dict[str, Any],
    *,
    task: Dict[str, Any],
    projected_operands: List[Dict[str, Any]],
    slot_has_material: Callable[[Dict[str, Any]], bool],
    projection_operand_matches_lookup: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    slot_differs_from_operand: Callable[[Dict[str, Any], Dict[str, Any]], bool],
    build_operand_value_slot: Callable[..., Dict[str, Any]],
) -> tuple[Dict[str, Any], Dict[str, Any], bool]:
    task_id = _normalise_spaces(str(row.get("task_id") or ""))
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    current_slot = dict(answer_slots.get("primary_value") or {})
    required_operands = _required_operands_for_lookup_realignment(row, task, current_slot)
    if len(required_operands) != 1:
        return row, {}, False
    required_operand = required_operands[0]
    candidate = _lookup_realignment_candidate(
        projected_operands,
        required_operand,
        projection_operand_matches_lookup=projection_operand_matches_lookup,
    )
    if not candidate or not slot_has_material(current_slot):
        return row, {}, False
    candidate_raw = _normalise_spaces(str(candidate.get("raw_value") or ""))
    if not candidate_raw or not slot_differs_from_operand(candidate, current_slot):
        return row, {}, False

    source_context = _lookup_realignment_source_context(task_id, candidate, current_slot)
    if not _lookup_realignment_source_context_allowed(candidate, current_slot, source_context):
        return row, {}, False
    if not _self_task_lookup_realignment_allowed(candidate, current_slot, source_context):
        return row, {}, False

    component_slot, primary_slot = _lookup_realignment_primary_slot(
        candidate,
        required_operand,
        current_slot,
        source_context["direct_source_ids"],
        build_operand_value_slot=build_operand_value_slot,
    )
    rendered_value = _normalise_spaces(str(primary_slot.get("rendered_value") or ""))
    if not rendered_value:
        rendered_value = _normalise_spaces(f"{primary_slot.get('raw_value') or ''}{primary_slot.get('raw_unit') or ''}")
    result_source_ids = list(primary_slot.get("source_row_ids") or source_context["source_ids"])
    updated_slots = _lookup_realignment_updated_slots(answer_slots, component_slot, primary_slot)
    updated_slots["source_row_ids"] = result_source_ids
    updated_result = _lookup_realignment_updated_result(
        calculation_result,
        primary_slot,
        updated_slots,
        rendered_value,
        result_source_ids,
    )
    return (
        {
            **dict(row),
            "answer": rendered_value,
            "calculation_result": updated_result,
            "answer_slots": updated_slots,
            "aligned_from_dependency_projection": True,
        },
        primary_slot,
        True,
    )


def replace_lookup_primary_slot(
    row: Dict[str, Any],
    updated_primary: Dict[str, Any],
    *,
    marker_key: str,
    component_source_ids: set[str] | None = None,
) -> Dict[str, Any]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    updated_slots = dict(answer_slots)
    updated_slots["primary_value"] = updated_primary
    raw_value = _normalise_spaces(str(updated_primary.get("raw_value") or ""))
    raw_unit = _normalise_spaces(str(updated_primary.get("raw_unit") or ""))
    normalized_value = updated_primary.get("normalized_value")
    normalized_unit = _normalise_spaces(str(updated_primary.get("normalized_unit") or ""))
    rendered_value = _normalise_spaces(str(updated_primary.get("rendered_value") or f"{raw_value}{raw_unit}"))
    if component_source_ids:
        for container_key in ("components_by_role", "components_by_group"):
            container = dict(updated_slots.get(container_key) or {})
            if not container:
                continue
            updated_slots[container_key] = {
                key: [
                    {
                        **dict(item),
                        "raw_unit": raw_unit,
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "rendered_value": rendered_value,
                        marker_key: True,
                    }
                    if isinstance(item, dict)
                    and _normalise_spaces(str(item.get("raw_value") or "")) == raw_value
                    and (
                        not component_source_ids
                        or set(_clean_source_row_ids([item.get("source_row_id"), item.get("source_row_ids")]))
                        & component_source_ids
                    )
                    else item
                    for item in list(entries or [])
                ]
                for key, entries in container.items()
            }
    label = _normalise_spaces(str(updated_primary.get("label") or row.get("metric_label") or ""))
    updated_result = {
        **calculation_result,
        "result_value": normalized_value,
        "result_unit": raw_unit or normalized_unit,
        "rendered_value": rendered_value,
        "formatted_result": _normalise_spaces(f"{label} {rendered_value}") if label and rendered_value else rendered_value,
        "answer_slots": updated_slots,
    }
    return {
        **dict(row),
        "answer": str(updated_result.get("formatted_result") or rendered_value),
        "calculation_result": updated_result,
        "answer_slots": updated_slots,
        marker_key: True,
    }


def lookup_primary_slot(row: Dict[str, Any]) -> Dict[str, Any]:
    calculation_result = dict(row.get("calculation_result") or {})
    answer_slots = dict(calculation_result.get("answer_slots") or row.get("answer_slots") or {})
    return dict(answer_slots.get("primary_value") or {})


def align_lookup_result_units_from_peer_source_slots(
    ordered_results: List[Dict[str, Any]],
    *,
    operation_family_for_result: Callable[[Dict[str, Any]], str],
    slot_has_material: Callable[[Dict[str, Any]], bool],
) -> List[Dict[str, Any]]:
    render_policy = dict(CALCULATION_RENDER_POLICY)
    krw_units = {
        _normalise_spaces(str(item))
        for item in (render_policy.get("krw_display_units") or ())
        if _normalise_spaces(str(item))
    }

    def _source_keys(slot: Dict[str, Any]) -> set[str]:
        source_ids = set(_clean_source_row_ids([slot.get("source_row_id"), slot.get("source_row_ids")]))
        source_anchor = _normalise_spaces(str(slot.get("source_anchor") or ""))
        if source_anchor:
            source_ids.add(f"anchor::{source_anchor}")
        return source_ids

    peer_slots = [
        lookup_primary_slot(row)
        for row in ordered_results
        if isinstance(row, dict)
        and operation_family_for_result(row) in {"lookup", "single_value"}
        and slot_has_material(lookup_primary_slot(row))
    ]

    def _peer_unit_for(slot: Dict[str, Any]) -> str:
        raw_value = _normalise_spaces(str(slot.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(slot.get("raw_unit") or ""))
        normalized_unit = _normalise_spaces(str(slot.get("normalized_unit") or "")).upper()
        if (
            not raw_value
            or not raw_unit
            or raw_unit not in krw_units
            or normalized_unit != "KRW"
            or not re.fullmatch(str(render_policy.get("operand_unit_bare_numeric_pattern") or r"$^"), raw_value)
        ):
            return ""
        keys = _source_keys(slot)
        if not keys:
            return ""
        concept = _normalise_spaces(str(slot.get("concept") or ""))
        candidates: List[str] = []
        for peer in peer_slots:
            if peer is slot:
                continue
            peer_unit = _normalise_spaces(str(peer.get("raw_unit") or ""))
            if not peer_unit or peer_unit == raw_unit or peer_unit not in krw_units:
                continue
            if _normalise_spaces(str(peer.get("normalized_unit") or "")).upper() != normalized_unit:
                continue
            peer_concept = _normalise_spaces(str(peer.get("concept") or ""))
            if concept and peer_concept and concept != peer_concept:
                continue
            if _source_keys(peer) & keys:
                candidates.append(peer_unit)
        if not candidates:
            return ""
        counts = {unit: candidates.count(unit) for unit in set(candidates)}
        best_count = max(counts.values())
        best_units = [unit for unit, count in counts.items() if count == best_count]
        if len(best_units) != 1:
            return ""
        peer_value, _peer_unit = _normalise_operand_value(raw_value, best_units[0])
        try:
            if abs(float(peer_value)) <= abs(float(slot.get("normalized_value"))):
                return ""
        except (TypeError, ValueError):
            return ""
        return best_units[0]

    aligned_results: List[Dict[str, Any]] = []
    changed_any = False
    for row in ordered_results:
        if not isinstance(row, dict) or operation_family_for_result(row) not in {"lookup", "single_value"}:
            aligned_results.append(row)
            continue
        primary_slot = lookup_primary_slot(row)
        peer_unit = _peer_unit_for(primary_slot)
        if not peer_unit:
            aligned_results.append(row)
            continue
        raw_value = _normalise_spaces(str(primary_slot.get("raw_value") or ""))
        normalized_value, normalized_unit = _normalise_operand_value(raw_value, peer_unit)
        if normalized_value is None:
            aligned_results.append(row)
            continue
        aligned_results.append(
            replace_lookup_primary_slot(
                row,
                {
                    **primary_slot,
                    "raw_unit": peer_unit,
                    "normalized_value": normalized_value,
                    "normalized_unit": normalized_unit,
                    "rendered_value": f"{raw_value}{peer_unit}",
                    "unit_aligned_from_peer_source_slot": True,
                },
                marker_key="unit_aligned_from_peer_source_slot",
            )
        )
        changed_any = True
    return aligned_results if changed_any else ordered_results
