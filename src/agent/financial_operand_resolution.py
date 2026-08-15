"""State-free operand resolution and evidence-grounding primitives.

The graph adapter decides when document fallback is allowed.  This module owns
how operand candidates are matched, grounded, selected, and merged without
reading or mutating ``FinancialAgentState``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Callable, Dict, FrozenSet, List, Literal, Mapping, Optional, Sequence, Tuple

from src.agent.financial_answer_slots import period_match_key
from src.agent.financial_operation_policies import (
    _is_percent_point_difference_query,
    _label_implies_percent_metric,
)
from src.agent.financial_row_surfaces import (
    _extract_numeric_value_after_operand_text,
    _operand_text_match,
    _strip_financial_label_annotations,
    _surface_match_variants,
    aggregate_like_row_stage,
    candidate_aggregation_stage,
    candidate_has_operand_context_surface,
    candidate_supports_segment_metric_combo,
    candidate_value_role,
    is_delta_like_row_label,
    table_row_has_matching_structured_sibling,
)
from src.agent.financial_runtime_normalization import (
    _clean_source_row_ids,
    _normalise_operand_value,
    _normalise_spaces,
    _parse_number_text,
)
from src.agent.financial_surface_contracts import (
    operand_needles,
    operand_segment_label,
    _operand_surface_contract,
    _text_has_contract_term,
    text_has_negative_surface,
    _text_has_positive_surface,
    binding_policy_allows_candidate_shape,
    candidate_conflicts_with_operand_concept,
    candidate_consolidation_scope,
    candidate_has_numeric_value_signal,
    candidate_has_required_surface_contract,
    candidate_is_descriptor_row,
    candidate_local_aggregate_context,
    candidate_matches_segment_binding,
    candidate_segment_binding_bonus,
    candidate_selected_unit_family,
    is_balance_sheet_aggregate_operand,
    is_capex_total_operand,
    operand_prefers_contextual_aggregate_match,
    operand_prefers_note_aggregate_lookup,
)
from src.agent.financial_scope_policies import (
    _metadata_period_match_strength,
    candidate_matches_operand_target_year,
    candidate_matches_target_report_scope,
    candidate_period_table_coherence_bonus,
    candidate_report_scope_binding_bonus,
    operand_period_focus,
    operand_target_years,
)
from src.agent.financial_structured_cells import _structured_cell_period_text
from src.agent.financial_text_surface import _strip_rerank_metadata
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    CALCULATION_RENDER_POLICY,
    CONSOLIDATION_SCOPE_POLICY,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    NUMERIC_UNIT_NORMALIZATION_POLICY,
    OPERAND_CANDIDATE_SCORING_POLICY,
    PERIOD_FOCUS_POLICY,
    RECONCILIATION_POLICY, STRUCTURED_CELL_AFFINITY_POLICY,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class OperandEvidenceCandidateBatch:
    """New evidence candidates collected from retrieved documents."""

    evidence_items: Tuple[Dict[str, Any], ...] = ()
    evidence_bullets: Tuple[str, ...] = ()


RequiredOperandCandidateMergeReason = Literal[
    "no_candidate_rows",
    "current_operand_rows_preferred",
    "complete_ratio_candidate_rows_preferred",
]


@dataclass(frozen=True)
class RequiredOperandCandidateMergeInput:
    """State-free inputs for required-candidate operand precedence."""

    operation_family: str
    required_operands: List[Dict[str, Any]]
    current_operand_rows: List[Dict[str, Any]]
    candidate_operand_rows: List[Dict[str, Any]]
    coherent_candidate_rows: List[Dict[str, Any]]


@dataclass(frozen=True)
class RequiredOperandCandidateMergeResult:
    """Inspectable result of required-candidate operand precedence."""

    selected_operand_rows: List[Dict[str, Any]]
    merged_candidate_rows: List[Dict[str, Any]]
    candidate_rows_cover_required: bool
    coherent_candidate_merge_applied: bool
    reason: RequiredOperandCandidateMergeReason


@dataclass(frozen=True)
class DirectStructuredOperandAcceptanceInput:
    """State-free inputs for direct structured-row acceptance."""

    direct_operand_rows: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    required_operands: List[Dict[str, Any]]
    operation_family: str
    ambiguity_query: str
    ambiguity_active_subtask: Mapping[str, Any]


@dataclass(frozen=True)
class DirectStructuredOperandAcceptanceResult:
    """Inspectable result of ordered direct-row acceptance stages."""

    accepted_operand_rows: List[Dict[str, Any]]
    required_surface_filter_applied: bool
    pre_lookup_ambiguity_filter_applied: bool
    lookup_direct_support_filter_applied: bool
    lookup_ambiguity_filter_applied: bool


DirectStructuredLookupEvidenceScoreReason = Literal[
    "no_structured_cells",
    "surface_contract_not_satisfied",
    "evidence_scored",
]


@dataclass(frozen=True)
class DirectStructuredLookupEvidenceScoreInput:
    """One operand and structured evidence item ready for state-free scoring."""

    operand: Mapping[str, Any]
    evidence_item: Mapping[str, Any]


@dataclass(frozen=True)
class DirectStructuredLookupEvidenceScoreResult:
    """Direct structured-evidence score with an inspectable disposition."""

    score: float
    reason: DirectStructuredLookupEvidenceScoreReason


DirectStructuredPreferredSlotAdoptionReason = Literal[
    "higher_current_evidence_score",
    "equal_evidence_score",
    "preferred_slot_selected",
    "ratio_unit_alignment_selected",
]


@dataclass(frozen=True)
class DirectStructuredPreferredSlotAdoptionInput:
    """Prepared state-free inputs for one preferred-slot adoption decision."""

    operation_family: str
    row_index: int
    current_operand_row: Dict[str, Any]
    required_operand: Dict[str, Any]
    normalized_peer_raw_units: set[str]
    preferred_slot: Dict[str, Any]
    preferred_score: float
    current_score: float


@dataclass(frozen=True)
class DirectStructuredPreferredSlotAdoptionResult:
    """Inspectable decision for a graph-prepared direct evidence slot."""

    selected_operand_row: Dict[str, Any]
    preferred_slot_adopted: bool
    unit_alignment_improves: bool
    reason: DirectStructuredPreferredSlotAdoptionReason


PostCoercionLlmDirectSupportReason = Literal[
    "direct_support_present",
    "missing_direct_support",
]


@dataclass(frozen=True)
class PostCoercionLlmDirectSupportInput:
    """One graph-coerced LLM row ready for direct-support validation."""

    operand_row: Dict[str, Any]
    evidence_item: Optional[Dict[str, Any]]
    required_operands: List[Dict[str, Any]]


@dataclass(frozen=True)
class PostCoercionLlmDirectSupportResult:
    """Identity-preserving direct-support decision for one LLM row."""

    operand_row: Dict[str, Any]
    direct_support_accepted: bool
    reason: PostCoercionLlmDirectSupportReason


@dataclass(frozen=True)
class PostCoercionLlmOperandSelectionInput:
    """State-free inputs for post-loop LLM operand selection and merge."""

    operand_rows: List[Dict[str, Any]]
    evidence_by_id: Dict[str, Dict[str, Any]]
    required_operands: List[Dict[str, Any]]
    direct_structured_rows: List[Dict[str, Any]]
    require_direct_support: bool
    lookup_rematch_required: bool


@dataclass(frozen=True)
class PostCoercionLlmOperandSelectionResult:
    """Inspectable post-loop LLM selection stages."""

    selected_operand_rows: List[Dict[str, Any]]
    required_surface_filter_applied: bool
    lookup_rematch_filter_applied: bool
    direct_merge_applied: bool


RecoveredOperandContextKind = Literal[
    "period_comparison",
    "coherent_ratio",
]
RecoveredOperandContextAdoptionReason = Literal[
    "no_context_rows",
    "period_context_merged",
    "coherent_ratio_context_replaced",
]


@dataclass(frozen=True)
class RecoveredOperandContextAdoptionInput:
    """State-free inputs for recovered context and evidence adoption."""

    context_kind: RecoveredOperandContextKind
    current_operand_rows: List[Dict[str, Any]]
    recovered_operand_rows: List[Dict[str, Any]]
    required_operands: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    recovered_evidence_items: List[Dict[str, Any]]


@dataclass(frozen=True)
class RecoveredOperandContextAdoptionResult:
    """Inspectable rows and provenance adopted from recovered context."""

    selected_operand_rows: List[Dict[str, Any]]
    evidence_items: List[Dict[str, Any]]
    adopted_evidence_ids: Tuple[str, ...]
    context_applied: bool
    reason: RecoveredOperandContextAdoptionReason


SiblingDirectSelectionReason = Literal[
    "shared_source_context",
    "same_table_context",
    "only_eligible_candidate",
    "equivalent_top_rank_tiebreak",
    "ambiguous_conflicting_top_rank",
    "no_eligible_candidate",
]
SiblingDirectRejectionReason = Literal[
    "binding_mismatch",
    "incomplete_context",
    "lower_source_coherence",
    "ambiguous_conflicting_top_rank",
    "equivalent_duplicate",
]


@dataclass(frozen=True)
class OperandCandidateRejection:
    """Inspectable reason why a sibling direct candidate was not selected."""

    candidate_id: str
    reason: SiblingDirectRejectionReason


@dataclass(frozen=True)
class OperandCandidateSelection:
    """Order-independent selection result for one dependency operand row."""

    selected_row: Optional[Dict[str, Any]]
    selected_candidate_id: str
    reason: SiblingDirectSelectionReason
    rejected: Tuple[OperandCandidateRejection, ...] = ()


SupplementalOperandSelectionReason = Literal[
    "only_eligible_candidate",
    "highest_binding_specificity",
    "equivalent_top_rank_tiebreak",
    "ambiguous_conflicting_top_rank",
    "no_eligible_candidate",
]
SupplementalOperandRejectionReason = Literal[
    "requirement_mismatch",
    "lower_binding_specificity",
    "ambiguous_conflicting_top_rank",
    "equivalent_duplicate",
]


@dataclass(frozen=True)
class SupplementalOperandCandidateRejection:
    """Inspectable reason why a supplemental merge candidate lost."""

    candidate_id: str
    reason: SupplementalOperandRejectionReason


@dataclass(frozen=True)
class SupplementalOperandSelection:
    """Order-independent selection result for one missing operand."""

    selected_row: Optional[Dict[str, Any]]
    selected_candidate_id: str
    reason: SupplementalOperandSelectionReason
    rejected: Tuple[SupplementalOperandCandidateRejection, ...] = ()


def operand_row_source_ids(row: Dict[str, Any]) -> FrozenSet[str]:
    return frozenset(
        source_id
        for source_id in _clean_source_row_ids(
            [
                row.get("evidence_id"),
                row.get("source_row_id"),
                row.get("source_row_ids"),
            ]
        )
        if source_id
    )


def _canonical_structured_reconciliation_id(value: Any) -> str:
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
    row: Dict[str, Any],
) -> Dict[str, Any]:
    updated = dict(row)
    for key in ("evidence_id", "source_row_id"):
        canonical = _canonical_structured_reconciliation_id(updated.get(key))
        if canonical:
            updated[key] = canonical
    source_row_ids = _clean_source_row_ids(updated.get("source_row_ids") or [])
    canonical_source_ids = [
        _canonical_structured_reconciliation_id(source_id)
        for source_id in source_row_ids
    ]
    canonical_source_ids = [source_id for source_id in canonical_source_ids if source_id]
    if canonical_source_ids:
        updated["source_row_ids"] = list(dict.fromkeys(canonical_source_ids))
    return updated


def _operand_slot_has_evidence_surface_match(
    slot: Dict[str, Any],
    evidence_item: Optional[Dict[str, Any]],
    operand: Dict[str, Any],
    *,
    metric_label: str = "",
) -> bool:
    matched_line_label = _normalise_spaces(str(slot.get("_matched_line_label") or ""))
    if matched_line_label:
        operand_surfaces = [
            _normalise_spaces(str(value or ""))
            for value in (
                operand.get("label"),
                metric_label,
                *list(operand.get("aliases") or []),
            )
            if _normalise_spaces(str(value or ""))
        ]
        matched_compact = re.sub(r"\s+", "", matched_line_label)
        if _operand_text_match(matched_line_label, operand) or any(
            matched_line_label in surface
            or (matched_compact and matched_compact in re.sub(r"\s+", "", surface))
            for surface in operand_surfaces
        ):
            return True
    if not evidence_item:
        return False
    metadata = dict(evidence_item.get("metadata") or {})
    surface_parts: List[str] = [
        str(evidence_item.get(key) or "")
        for key in ("claim", "quote_span", "raw_row_text", "source_context")
    ]
    surface_parts.extend(
        str(metadata.get(key) or "")
        for key in (
            "row_label",
            "semantic_label",
            "aggregate_label",
            "table_value_labels_text",
            "row_text",
            "table_row_labels_text",
        )
    )
    for key in ("semantic_aliases", "row_headers"):
        surface_parts.extend(str(item or "") for item in (metadata.get(key) or []))
    for cell in list(metadata.get("structured_cells") or []):
        cell_data = dict(cell or {})
        surface_parts.append(str(cell_data.get("aggregate_label") or ""))
        surface_parts.extend(str(item or "") for item in (cell_data.get("column_headers") or []))
    evidence_surface = _normalise_spaces(" ".join(part for part in surface_parts if str(part).strip()))
    if not evidence_surface:
        return False
    return _operand_text_match(evidence_surface, operand) or _text_has_positive_surface(evidence_surface, operand)


def operand_row_values_differ(left: Dict[str, Any], right: Dict[str, Any]) -> bool:
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


def operand_row_values_materially_conflict(
    left: Dict[str, Any],
    right: Dict[str, Any],
) -> bool:
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
    return operand_row_values_differ(left, right)


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


def coerce_operand_unit_from_evidence(
    *,
    raw_value: str,
    raw_unit: str,
    evidence_item: Optional[Mapping[str, Any]],
) -> str:
    metadata = dict((evidence_item or {}).get("metadata") or {})
    unit_hint = str(metadata.get("unit_hint") or "").strip()
    current_unit = str(raw_unit or "").strip()
    surface_unit = _infer_operand_unit_from_value_surface(
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
        if _evidence_core_surface_contains_value_unit(
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
    evidence_item: Optional[Mapping[str, Any]],
) -> str:
    return _normalise_spaces(
        " ".join(
            str((evidence_item or {}).get(key) or "")
            for key in ("claim", "quote_span", "raw_row_text")
        )
    )


def _evidence_core_surface_contains_value_unit(
    *,
    raw_value: str,
    raw_unit: str,
    evidence_item: Optional[Mapping[str, Any]],
) -> bool:
    value = _normalise_spaces(str(raw_value or ""))
    unit = _normalise_spaces(str(raw_unit or ""))
    surface = _evidence_core_surface(evidence_item)
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


def coerce_operand_period_from_evidence_surface(
    row: Dict[str, Any],
    evidence_item: Optional[Mapping[str, Any]],
) -> Dict[str, Any]:
    surface = _evidence_core_surface(evidence_item)
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


def _infer_operand_unit_from_value_surface(
    *,
    raw_value: str,
    evidence_item: Optional[Mapping[str, Any]],
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


def repair_operand_normalization_from_rendered_unit(
    row: Mapping[str, Any],
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


def dependency_task_output_has_consistent_krw_unit(row: Mapping[str, Any]) -> bool:
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


def repair_krw_operand_units_from_table_metadata(
    operands: List[Dict[str, Any]],
    evidence_items: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    evidence_by_id = _evidence_items_by_id(evidence_items)
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
        surface = table_surface_text(evidence_item, metadata)
        return compact_value in re.sub(r"[,\s()]", "", surface)

    def table_surface_text(evidence_item: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> str:
        current_metadata = metadata if metadata is not None else dict(evidence_item.get("metadata") or {})
        return _normalise_spaces(
            " ".join(
                str(value or "")
                for value in [
                    evidence_item.get("raw_row_text"),
                    evidence_item.get("quote_span"),
                    evidence_item.get("claim"),
                    current_metadata.get("row_text"),
                    current_metadata.get("table_summary_text"),
                    current_metadata.get("table_value_labels_text"),
                    current_metadata.get("table_row_labels_text"),
                    current_metadata.get("semantic_label"),
                    current_metadata.get("row_label"),
                ]
            )
        )

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

    def krw_unit_from_alternate_table_surface(row: Dict[str, Any], raw_value: str) -> str:
        label = _normalise_spaces(
            str(row.get("matched_operand_label") or row.get("label") or row.get("semantic_label") or "")
        )
        compact_value = re.sub(r"[,\s()]", "", raw_value)
        if not compact_value:
            return ""
        for evidence_item in evidence_items:
            if not isinstance(evidence_item, dict) or not is_table_backed(evidence_item):
                continue
            metadata = dict(evidence_item.get("metadata") or {})
            surface = table_surface_text(evidence_item, metadata)
            if not surface or compact_value not in re.sub(r"[,\s()]", "", surface):
                continue
            if label and not _operand_text_match(surface, {"label": label, "aliases": []}):
                continue
            compact_surface = re.sub(r"[\s,()]", "", surface)
            for unit in krw_units:
                compact_unit = re.sub(r"\s+", "", unit)
                if compact_unit and f"{compact_value}{compact_unit}" in compact_surface:
                    return unit
            unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or ""))
            if unit_hint in krw_units:
                return unit_hint
        return ""

    updated: List[Dict[str, Any]] = []
    changed = False
    for row in operands:
        next_row = dict(row)
        if dependency_task_output_has_consistent_krw_unit(next_row):
            updated.append(next_row)
            continue
        raw_value = _normalise_spaces(str(next_row.get("raw_value") or ""))
        raw_unit = _normalise_spaces(str(next_row.get("raw_unit") or next_row.get("result_unit") or ""))
        normalized_unit = _normalise_spaces(str(next_row.get("normalized_unit") or "")).upper()
        if normalized_unit != "KRW":
            if normalized_unit not in {"COUNT", "UNKNOWN", ""} or not raw_value:
                updated.append(next_row)
                continue
            repaired_unit = krw_unit_from_alternate_table_surface(next_row, raw_value)
            if not repaired_unit:
                updated.append(next_row)
                continue
            repaired_value, repaired_normalized_unit = _normalise_operand_value(raw_value, repaired_unit)
            if repaired_value is None or repaired_normalized_unit != "KRW":
                updated.append(next_row)
                continue
            try:
                current_value = float(next_row.get("normalized_value"))
            except (TypeError, ValueError):
                current_value = None
            next_row["source_raw_unit"] = raw_unit
            if current_value is not None:
                next_row["source_normalized_value"] = current_value
            next_row["raw_unit"] = repaired_unit
            next_row["normalized_value"] = repaired_value
            next_row["normalized_unit"] = repaired_normalized_unit
            next_row["rendered_value"] = f"{raw_value}{repaired_unit}"
            next_row["unit_normalization_repair_source"] = "alternate_table_krw_surface"
            changed = True
            updated.append(next_row)
            continue
        if not raw_value or raw_unit not in krw_units:
            updated.append(next_row)
            continue
        evidence_item = _evidence_item_for_operand_row(next_row, evidence_by_id)
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


def repair_krw_normalized_values_from_raw_units(
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


def align_growth_operand_units_when_raw_scale_matches(
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


def growth_operand_periods_conflict(ordered_operands: List[Dict[str, Any]]) -> bool:
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
    current_period = period_match_key(str(current_row.get("period") or current_row.get("label") or ""))
    prior_period = period_match_key(str(prior_row.get("period") or prior_row.get("label") or ""))
    return bool(current_period and prior_period and current_period == prior_period)


def align_ratio_operand_units_with_shared_table_context(
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


def _binding_policy_for_operand_row(row: Dict[str, Any]) -> Dict[str, Any]:
    row_policy = dict(row.get("binding_policy") or {})
    concept_key = str(row.get("matched_operand_concept") or row.get("concept") or "").strip()
    if not concept_key:
        return row_policy
    ontology_policy = get_financial_ontology().binding_policy_for_concept(concept_key)
    merged = dict(ontology_policy or {})
    merged.update(row_policy)
    return merged


def apply_operation_sign_policy(
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
        policy = _binding_policy_for_operand_row(next_row)
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


def _operand_row_conflicts_with_requirement(row: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    operand_concept = _normalise_spaces(str(operand.get("concept") or ""))
    row_concepts = [
        _normalise_spaces(str(row.get("matched_operand_concept") or "")),
        _normalise_spaces(str(row.get("concept") or "")),
    ]
    if operand_concept and any(row_concept and row_concept != operand_concept for row_concept in row_concepts):
        return True

    operand_period_text = " ".join(
        str(value or "")
        for value in (
            operand.get("period"),
            operand.get("period_hint"),
            operand.get("label"),
            operand.get("name"),
        )
    )
    row_period_text = " ".join(
        str(value or "")
        for value in (
            row.get("period"),
            row.get("label"),
            row.get("matched_operand_label"),
        )
    )
    operand_years = set(re.findall(r"20\d{2}", operand_period_text))
    row_years = set(re.findall(r"20\d{2}", row_period_text))
    if str(row.get("period_source") or "").strip() == "evidence_surface":
        row_period_years = set(re.findall(r"20\d{2}", str(row.get("period") or "")))
        if operand_years and row_period_years and operand_years.isdisjoint(row_period_years):
            return True
    if operand_years and row_years and operand_years.isdisjoint(row_years):
        return True

    normalized_needles = [_normalise_spaces(needle) for needle in operand_needles(operand) if _normalise_spaces(needle)]
    expects_liability = any("부채" in needle for needle in normalized_needles)
    authoritative_surfaces = [
        str(row.get("matched_operand_label") or "").strip(),
        str(row.get("label") or "").strip(),
    ]
    authoritative_surfaces = [surface for surface in authoritative_surfaces if surface]
    row_unit_family = _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
    if not row_unit_family:
        _value, row_unit_family = _normalise_operand_value(
            str(row.get("raw_value") or ""),
            str(row.get("raw_unit") or ""),
        )
        row_unit_family = _normalise_spaces(str(row_unit_family or "")).upper()
    operand_unit_family = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
    operand_label = _normalise_spaces(str(operand.get("label") or ""))
    if row_unit_family == "PERCENT" and operand_unit_family in {"KRW", "CURRENCY", "MONEY", "AMOUNT"}:
        return True
    if row_unit_family in {"KRW", "CURRENCY", "MONEY", "AMOUNT"} and operand_unit_family == "PERCENT":
        return True
    if (
        row_unit_family == "PERCENT"
        and operand_unit_family != "PERCENT"
        and not _label_implies_percent_metric(operand_label)
        and any(_label_implies_percent_metric(surface) for surface in authoritative_surfaces)
    ):
        return True

    if not expects_liability and any("부채" in _normalise_spaces(surface) for surface in authoritative_surfaces):
        return True

    contract = _operand_surface_contract(operand)
    if not contract:
        return False

    if any(text_has_negative_surface(surface, operand) for surface in authoritative_surfaces):
        return True
    return False


def _operand_row_matches_requirement(row: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    if _operand_row_conflicts_with_requirement(row, operand):
        return False

    bound_role = str(row.get("matched_operand_role") or "").strip()
    operand_role = str(operand.get("role") or "").strip()
    if bound_role and operand_role and _normalise_spaces(bound_role) != _normalise_spaces(operand_role):
        return False

    bound_label = str(row.get("matched_operand_label") or "").strip()
    operand_label = str(operand.get("label") or "").strip()
    if bound_label and operand_label and _normalise_spaces(bound_label) == _normalise_spaces(operand_label):
        return True

    bound_concept = str(row.get("matched_operand_concept") or "").strip()
    operand_concept = str(operand.get("concept") or "").strip()
    if bound_concept and operand_concept and _normalise_spaces(bound_concept) == _normalise_spaces(operand_concept):
        return True

    surfaces = [
        str(row.get("label") or "").strip(),
        str(row.get("source_anchor") or "").strip(),
    ]
    return any(_operand_text_match(surface, operand) for surface in surfaces if surface)


def _missing_required_operands(
    required_operands: List[Dict[str, Any]],
    operand_rows: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    missing: List[Dict[str, Any]] = []
    for operand in required_operands:
        if any(_operand_row_matches_requirement(row, operand) for row in operand_rows):
            continue
        missing.append(dict(operand))
    return missing


def _evidence_items_by_id(
    evidence_items: List[Dict[str, Any]],
) -> Dict[str, Dict[str, Any]]:
    return {
        str(item.get("evidence_id") or "").strip(): dict(item)
        for item in evidence_items
        if str(item.get("evidence_id") or "").strip()
    }


def _evidence_item_for_operand_row(
    row: Dict[str, Any],
    evidence_by_id: Dict[str, Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    candidate_ids = _clean_source_row_ids(
        [
            row.get("evidence_id"),
            row.get("source_row_id"),
            row.get("source_row_ids"),
        ]
    )
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


def _operand_row_has_direct_evidence_surface(
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
                surfaces.append(
                    _normalise_spaces(
                        " ".join([*label_parts, value_text, str(record.get("unit_hint") or "")])
                    )
                )

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
            if text_has_negative_surface(line, operand):
                continue
            if _text_has_positive_surface(line, operand) or _operand_text_match(line, operand):
                return True
        return False

    return any(_surface_supports_operand_value(surface) for surface in surfaces if surface)


def _llm_lookup_operand_has_direct_support(
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
        if text_has_negative_surface(evidence_text, surface_operand):
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
    return _operand_row_has_direct_evidence_surface(row, evidence_item, matching_operand)


def _evidence_surface_contains_segment_label(
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
    evidence_item = _evidence_item_for_operand_row(row, evidence_by_id)
    segment_label = _normalise_spaces(
        str(
            operand_segment_label(matching_operand)
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
        if not _evidence_surface_contains_segment_label(segment_label, segment_surfaces):
            return False
    binding_policy = dict(matching_operand.get("binding_policy") or {})
    requires_surface_contract = bool(
        binding_policy.get("require_surface_contract_for_direct_match")
        or binding_policy.get("require_surface_contract_for_direct_lookup")
    )
    if not requires_surface_contract and not require_direct_support:
        return True
    if requires_surface_contract:
        return _llm_lookup_operand_has_direct_support(row, evidence_item, [matching_operand])
    if not evidence_item:
        return True
    return _operand_row_has_direct_evidence_surface(row, evidence_item, matching_operand)


def _filter_operand_rows_by_required_surface_contract(
    rows: List[Dict[str, Any]],
    evidence_items: List[Dict[str, Any]],
    required_operands: List[Dict[str, Any]],
    *,
    require_direct_support: bool = False,
) -> List[Dict[str, Any]]:
    if not rows or not required_operands:
        return rows
    evidence_by_id = _evidence_items_by_id(evidence_items)
    return [
        row
        for row in rows
        if any(_operand_row_matches_requirement(row, operand) for operand in required_operands)
        and _operand_row_satisfies_required_surface_contract(
            row,
            evidence_by_id,
            required_operands,
            require_direct_support=require_direct_support,
        )
    ]


def surface_contract_numeric_evidence_items(
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
            if text_has_negative_surface(surface, operand_dict):
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


def ratio_context_has_metric_surface(
    context_evidence: List[Dict[str, Any]],
    task: Dict[str, Any],
) -> bool:
    metric_labels = [
        _normalise_spaces(str(value or ""))
        for value in (
            task.get("metric_label"),
            task.get("target_metric"),
            task.get("label"),
            task.get("name"),
            *list(task.get("aliases") or []),
        )
        if _normalise_spaces(str(value or ""))
    ]
    if not metric_labels:
        return False
    metric_operands = [{"label": label, "aliases": []} for label in dict.fromkeys(metric_labels)]
    surfaces: List[str] = []
    for evidence in context_evidence:
        evidence_data = dict(evidence or {})
        metadata = dict(evidence_data.get("metadata") or {})
        surfaces.extend(
            str(evidence_data.get(key) or "")
            for key in ("claim", "quote_span", "raw_row_text", "source_context")
        )
        surfaces.extend(
            str(metadata.get(key) or "")
            for key in (
                "row_label",
                "semantic_label",
                "aggregate_label",
                "table_summary_text",
                "table_title",
                "table_context",
                "table_row_labels_text",
                "table_value_labels_text",
                "row_text",
            )
        )
        for key in ("semantic_aliases", "row_headers"):
            surfaces.extend(str(item or "") for item in list(metadata.get(key) or []))
    for surface in surfaces:
        normalized_surface = _normalise_spaces(surface)
        if not normalized_surface:
            continue
        if any(_operand_text_match(normalized_surface, operand) for operand in metric_operands):
            return True
    return False


def _lookup_task_requests_context_dependent_scope(
    *,
    query: str,
    active_subtask: Mapping[str, Any],
    required_operands: Sequence[Mapping[str, Any]],
) -> bool:
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    markers = tuple(
        _normalise_spaces(str(item)).lower()
        for item in (scoring_policy.get("context_dependent_lookup_scope_markers") or ())
        if _normalise_spaces(str(item))
    )
    if not markers:
        return False
    active_subtask_data = dict(active_subtask or {})
    text_parts: List[str] = [
        str(query or ""),
        str(active_subtask_data.get("query") or ""),
        str(active_subtask_data.get("metric_label") or ""),
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


def direct_lookup_row_is_ambiguous_context_table(
    row: Mapping[str, Any],
    evidence_item: Optional[Mapping[str, Any]],
    *,
    query: str,
    active_subtask: Mapping[str, Any],
    required_operands: Sequence[Mapping[str, Any]],
) -> bool:
    """Return whether an unscoped lookup row comes from a multi-context table."""

    if _lookup_task_requests_context_dependent_scope(
        query=query,
        active_subtask=active_subtask,
        required_operands=required_operands,
    ):
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


def _operand_rows_have_single_table_context(rows: List[Dict[str, Any]]) -> bool:
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


def _operand_row_display_unit_set(rows: List[Dict[str, Any]]) -> set[str]:
    return {
        _normalise_spaces(str(row.get("raw_unit") or ""))
        for row in rows
        if _normalise_spaces(str(row.get("raw_unit") or ""))
    }


def _operand_rows_conflict_by_required_role(
    left_rows: List[Dict[str, Any]],
    right_rows: List[Dict[str, Any]],
    *,
    operand_row_value_differs: Callable[[Dict[str, Any], Dict[str, Any]], bool],
) -> bool:
    right_by_role: Dict[str, List[Dict[str, Any]]] = {}
    for row in right_rows:
        role = _normalise_spaces(str(row.get("matched_operand_role") or row.get("role") or "")).lower()
        if role:
            right_by_role.setdefault(role, []).append(row)
    for left_row in left_rows:
        role = _normalise_spaces(str(left_row.get("matched_operand_role") or left_row.get("role") or "")).lower()
        if not role:
            continue
        for right_row in right_by_role.get(role, []):
            if operand_row_value_differs(left_row, right_row):
                return True
    return False


def _operand_row_groups_collapse_to_same_slot(
    role_groups: List[List[Dict[str, Any]]],
) -> bool:
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


def _ratio_operand_rows_collapse_to_same_slot(rows: List[Dict[str, Any]]) -> bool:
    return _operand_row_groups_collapse_to_same_slot([
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


def _period_comparison_operand_rows_collapse_to_same_slot(rows: List[Dict[str, Any]]) -> bool:
    return _operand_row_groups_collapse_to_same_slot([
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


def _operand_binding_key(row: Dict[str, Any]) -> Tuple[str, str]:
    return (
        _normalise_spaces(str(row.get("matched_operand_label") or row.get("label") or "")),
        _normalise_spaces(str(row.get("matched_operand_role") or "")),
    )


def _operand_context_key(row: Dict[str, Any]) -> str:
    return _normalise_spaces(
        str(
            row.get("table_source_id")
            or row.get("evidence_id")
            or row.get("source_row_id")
            or ""
        )
    )


def _operand_candidate_id(row: Dict[str, Any]) -> str:
    for value in (
        row.get("evidence_id"),
        row.get("source_row_id"),
        row.get("operand_id"),
    ):
        candidate_id = _normalise_spaces(str(value or ""))
        if candidate_id:
            return candidate_id
    source_ids = tuple(sorted(operand_row_source_ids(row)))
    if source_ids:
        return source_ids[0]
    return "|".join(
        _normalise_spaces(str(value or ""))
        for value in (
            _operand_context_key(row),
            row.get("matched_operand_label") or row.get("label"),
            row.get("matched_operand_role"),
            row.get("period"),
            row.get("normalized_value") if row.get("normalized_value") is not None else row.get("raw_value"),
            row.get("normalized_unit") or row.get("raw_unit"),
        )
    )


def _operand_candidate_semantic_signature(row: Dict[str, Any]) -> Tuple[str, ...]:
    normalized_value = row.get("normalized_value")
    value_surface = (
        repr(float(normalized_value))
        if isinstance(normalized_value, (int, float))
        else _normalise_spaces(str(normalized_value or row.get("raw_value") or ""))
    )
    return (
        value_surface,
        _normalise_spaces(str(row.get("normalized_unit") or row.get("raw_unit") or "")).upper(),
        _normalise_spaces(str(row.get("period") or "")),
        _normalise_spaces(str(row.get("consolidation_scope") or "")),
        _normalise_spaces(str(row.get("statement_type") or "")),
    )


def _operand_candidate_total_order_key(row: Dict[str, Any]) -> Tuple[str, ...]:
    """Return a deterministic tiebreak even when provenance IDs collide."""

    return (
        _operand_candidate_id(row),
        _normalise_spaces(str(row.get("source_row_id") or "")),
        _normalise_spaces(str(row.get("operand_id") or "")),
        _operand_context_key(row),
        *tuple(sorted(operand_row_source_ids(row))),
        *_operand_binding_key(row),
        *_operand_candidate_semantic_signature(row),
        json.dumps(row, ensure_ascii=False, sort_keys=True, default=str),
    )


def _supplemental_candidate_id(row: Dict[str, Any]) -> str:
    for value in (
        row.get("evidence_id"),
        row.get("source_row_id"),
    ):
        candidate_id = _normalise_spaces(str(value or ""))
        if candidate_id:
            return candidate_id
    source_ids = tuple(sorted(operand_row_source_ids(row)))
    if source_ids:
        return source_ids[0]
    return "|".join(
        _normalise_spaces(str(value or ""))
        for value in (
            _operand_context_key(row),
            row.get("matched_operand_label") or row.get("label"),
            row.get("matched_operand_role"),
            row.get("period"),
            (
                row.get("normalized_value")
                if row.get("normalized_value") is not None
                else row.get("raw_value")
            ),
            row.get("normalized_unit") or row.get("raw_unit"),
            row.get("consolidation_scope"),
            row.get("statement_type"),
        )
    )


def _supplemental_binding_specificity_rank(
    row: Dict[str, Any],
    operand: Dict[str, Any],
) -> Tuple[int, int, int, int]:
    operand_role = _normalise_spaces(str(operand.get("role") or ""))
    row_role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
    operand_label = _normalise_spaces(str(operand.get("label") or ""))
    row_label = _normalise_spaces(
        str(row.get("matched_operand_label") or row.get("label") or "")
    )
    operand_concept = _normalise_spaces(str(operand.get("concept") or ""))
    row_concept = _normalise_spaces(
        str(row.get("matched_operand_concept") or row.get("concept") or "")
    )
    operand_period = _normalise_spaces(
        str(operand.get("period") or operand.get("period_hint") or "")
    )
    row_period = _normalise_spaces(str(row.get("period") or ""))
    operand_years = set(re.findall(r"20\d{2}", operand_period))
    row_years = set(re.findall(r"20\d{2}", row_period))
    exact_period = bool(
        operand_period
        and row_period
        and (
            operand_period == row_period
            or (operand_years and operand_years == row_years)
        )
    )
    return (
        int(bool(operand_role and row_role == operand_role)),
        int(bool(operand_label and row_label == operand_label)),
        int(bool(operand_concept and row_concept == operand_concept)),
        int(exact_period),
    )


def select_supplemental_operand_candidate(
    required_operand: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
) -> SupplementalOperandSelection:
    """Select one fallback row by explicit binding, never by input position."""

    def _ordered_rejections(
        items: Sequence[SupplementalOperandCandidateRejection],
    ) -> Tuple[SupplementalOperandCandidateRejection, ...]:
        return tuple(sorted(items, key=lambda item: (item.candidate_id, item.reason)))

    eligible: List[Dict[str, Any]] = []
    rejected: List[SupplementalOperandCandidateRejection] = []
    for row in candidates:
        candidate = dict(row)
        candidate_id = _supplemental_candidate_id(candidate)
        if not _operand_row_matches_requirement(candidate, required_operand):
            rejected.append(
                SupplementalOperandCandidateRejection(
                    candidate_id,
                    "requirement_mismatch",
                )
            )
            continue
        eligible.append(candidate)

    if not eligible:
        return SupplementalOperandSelection(
            selected_row=None,
            selected_candidate_id="",
            reason="no_eligible_candidate",
            rejected=_ordered_rejections(rejected),
        )

    ranked = [
        (_supplemental_binding_specificity_rank(candidate, required_operand), candidate)
        for candidate in eligible
    ]
    top_rank = max(rank for rank, _candidate in ranked)
    top_candidates = [candidate for rank, candidate in ranked if rank == top_rank]
    lower_candidates = [candidate for rank, candidate in ranked if rank != top_rank]
    rejected.extend(
        SupplementalOperandCandidateRejection(
            _supplemental_candidate_id(candidate),
            "lower_binding_specificity",
        )
        for candidate in lower_candidates
    )

    if len(top_candidates) == 1:
        selected = top_candidates[0]
        return SupplementalOperandSelection(
            selected_row=selected,
            selected_candidate_id=_supplemental_candidate_id(selected),
            reason=(
                "only_eligible_candidate"
                if len(eligible) == 1
                else "highest_binding_specificity"
            ),
            rejected=_ordered_rejections(rejected),
        )

    semantic_signatures = {
        _operand_candidate_semantic_signature(candidate)
        for candidate in top_candidates
    }
    materially_conflicting = any(
        operand_row_values_materially_conflict(left, right)
        for index, left in enumerate(top_candidates)
        for right in top_candidates[index + 1 :]
    )
    if materially_conflicting or len(semantic_signatures) > 1:
        rejected.extend(
            SupplementalOperandCandidateRejection(
                _supplemental_candidate_id(candidate),
                "ambiguous_conflicting_top_rank",
            )
            for candidate in top_candidates
        )
        return SupplementalOperandSelection(
            selected_row=None,
            selected_candidate_id="",
            reason="ambiguous_conflicting_top_rank",
            rejected=_ordered_rejections(rejected),
        )

    selected = min(
        top_candidates,
        key=lambda candidate: (
            _supplemental_candidate_id(candidate),
            _operand_context_key(candidate),
            tuple(sorted(operand_row_source_ids(candidate))),
        ),
    )
    selected_candidate_id = _supplemental_candidate_id(selected)
    rejected.extend(
        SupplementalOperandCandidateRejection(
            _supplemental_candidate_id(candidate),
            "equivalent_duplicate",
        )
        for candidate in top_candidates
        if candidate is not selected
    )
    return SupplementalOperandSelection(
        selected_row=selected,
        selected_candidate_id=selected_candidate_id,
        reason="equivalent_top_rank_tiebreak",
        rejected=_ordered_rejections(rejected),
    )


def _operand_merge_row_key(row: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        _normalise_spaces(str(row.get("label") or "")),
        _normalise_spaces(str(row.get("period") or "")),
        _normalise_spaces(str(row.get("source_anchor") or "")),
    )


def _operand_required_key(operand: Dict[str, Any]) -> Tuple[str, str, str]:
    return (
        _normalise_spaces(str(operand.get("label") or "")),
        _normalise_spaces(str(operand.get("role") or "")),
        _normalise_spaces(
            str(operand.get("period") or operand.get("period_hint") or "")
        ),
    )


def merge_operand_rows(
    preferred_rows: List[Dict[str, Any]],
    supplemental_rows: List[Dict[str, Any]],
    *,
    required_operands: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Keep trusted rows first and fill only still-missing operands."""

    merged: List[Dict[str, Any]] = [dict(row) for row in preferred_rows]
    if not supplemental_rows:
        return merged

    seen_keys: set[Tuple[str, str, str]] = {
        _operand_merge_row_key(row)
        for row in merged
    }

    if not required_operands:
        for row in supplemental_rows:
            candidate = dict(row)
            row_key = _operand_merge_row_key(candidate)
            if row_key in seen_keys:
                continue
            seen_keys.add(row_key)
            merged.append(candidate)
        return merged

    remaining_required = _missing_required_operands(required_operands, merged)
    ordered_required: List[Tuple[Tuple[str, str, str], Dict[str, Any]]] = []
    required_by_key: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    for operand in remaining_required:
        required_key = _operand_required_key(operand)
        if required_key in required_by_key:
            continue
        required_by_key[required_key] = operand
        ordered_required.append((required_key, operand))

    candidates_by_required: Dict[
        Tuple[str, str, str],
        List[Dict[str, Any]],
    ] = {required_key: [] for required_key, _operand in ordered_required}
    for row in supplemental_rows:
        candidate = dict(row)
        if _operand_merge_row_key(candidate) in seen_keys:
            continue
        for required_key, operand in ordered_required:
            if _operand_row_matches_requirement(candidate, operand):
                candidates_by_required[required_key].append(candidate)
                break

    for required_key, operand in ordered_required:
        candidates = [
            candidate
            for candidate in candidates_by_required[required_key]
            if _operand_merge_row_key(candidate) not in seen_keys
        ]
        decision = select_supplemental_operand_candidate(operand, candidates)
        if decision.selected_row is None:
            continue
        selected = dict(decision.selected_row)
        selected_key = _operand_merge_row_key(selected)
        if selected_key in seen_keys:
            continue
        seen_keys.add(selected_key)
        merged.append(selected)

    return merged


def resolve_required_operand_candidate_merge(
    merge_input: RequiredOperandCandidateMergeInput,
) -> RequiredOperandCandidateMergeResult:
    """Merge grounded candidates without consulting or mutating graph state."""

    if not merge_input.candidate_operand_rows:
        return RequiredOperandCandidateMergeResult(
            selected_operand_rows=merge_input.current_operand_rows,
            merged_candidate_rows=merge_input.candidate_operand_rows,
            candidate_rows_cover_required=False,
            coherent_candidate_merge_applied=False,
            reason="no_candidate_rows",
        )

    merged_candidate_rows = merge_input.candidate_operand_rows
    coherent_candidate_merge_applied = bool(
        merge_input.operation_family == "ratio"
        and merge_input.coherent_candidate_rows
    )
    if coherent_candidate_merge_applied:
        merged_candidate_rows = merge_operand_rows(
            merge_input.coherent_candidate_rows,
            merged_candidate_rows,
            required_operands=merge_input.required_operands,
        )

    candidate_rows_cover_required = not _missing_required_operands(
        merge_input.required_operands,
        merged_candidate_rows,
    )
    if merge_input.operation_family == "ratio" and candidate_rows_cover_required:
        preferred_operand_rows = merged_candidate_rows
        supplemental_operand_rows = merge_input.current_operand_rows
        reason: RequiredOperandCandidateMergeReason = (
            "complete_ratio_candidate_rows_preferred"
        )
    else:
        preferred_operand_rows = merge_input.current_operand_rows
        supplemental_operand_rows = merged_candidate_rows
        reason = "current_operand_rows_preferred"
    selected_operand_rows = merge_operand_rows(
        preferred_operand_rows,
        supplemental_operand_rows,
        required_operands=merge_input.required_operands,
    )

    return RequiredOperandCandidateMergeResult(
        selected_operand_rows=selected_operand_rows,
        merged_candidate_rows=merged_candidate_rows,
        candidate_rows_cover_required=candidate_rows_cover_required,
        coherent_candidate_merge_applied=coherent_candidate_merge_applied,
        reason=reason,
    )


def operand_prefers_aggregate_value_role(operand: Mapping[str, Any]) -> bool:
    """Return whether binding policy prefers aggregate values over detail rows."""

    binding_policy = dict(operand.get("binding_policy") or {})
    preferred_value_roles = [
        _normalise_spaces(str(item)).lower()
        for item in (binding_policy.get("prefer_value_roles") or [])
        if _normalise_spaces(str(item))
    ]
    if not preferred_value_roles:
        return False
    return preferred_value_roles[0] == "aggregate" or (
        "aggregate" in preferred_value_roles and "detail" not in preferred_value_roles
    )


def preference_bonus(value: str, preferred: List[str], *, base: float = 0.4) -> float:
    ordered = [_normalise_spaces(item) for item in preferred if _normalise_spaces(item)]
    target = _normalise_spaces(value)
    if not target or target not in ordered:
        return 0.0
    index = ordered.index(target)
    return base * max(len(ordered) - index, 1)


def direct_target_metric_row_conflicts_existing_units(
    target_metric_row: Mapping[str, Any],
    existing_rows: Sequence[Mapping[str, Any]],
    required_operands: Sequence[Mapping[str, Any]],
) -> bool:
    if not target_metric_row or not existing_rows:
        return False

    matching_existing_rows = [
        dict(row)
        for row in existing_rows
        if not required_operands
        or any(_operand_row_matches_requirement(dict(row), operand) for operand in required_operands)
    ]
    if not matching_existing_rows:
        return False

    existing_units = {
        _normalise_spaces(str(row.get("normalized_unit") or "")).upper()
        for row in matching_existing_rows
        if _normalise_spaces(str(row.get("normalized_unit") or "")).upper() not in {"", "UNKNOWN"}
    }
    if not existing_units:
        return False

    target_unit = _normalise_spaces(str(target_metric_row.get("normalized_unit") or "")).upper()
    if target_unit in {"", "UNKNOWN"}:
        return True
    if target_unit not in existing_units:
        return True

    matching_target_operand = next(
        (
            dict(operand)
            for operand in required_operands
            if _operand_row_matches_requirement(target_metric_row, operand)
        ),
        {},
    )
    if operand_prefers_aggregate_value_role(matching_target_operand):
        return False

    target_value_role = _normalise_spaces(str(target_metric_row.get("value_role") or "")).lower()
    target_aggregation_stage = _normalise_spaces(str(target_metric_row.get("aggregation_stage") or "")).lower()
    target_is_aggregate_like = bool(
        target_value_role == "aggregate"
        or target_aggregation_stage in {"direct", "final", "subtotal"}
        or _normalise_spaces(str(target_metric_row.get("aggregate_label") or ""))
    )

    for existing_row in matching_existing_rows:
        existing_unit = _normalise_spaces(str(existing_row.get("normalized_unit") or "")).upper()
        if existing_unit and existing_unit != target_unit:
            continue
        if not operand_row_values_differ(existing_row, target_metric_row):
            continue
        existing_source_ids = _clean_source_row_ids([
            existing_row.get("evidence_id"),
            existing_row.get("source_row_id"),
            existing_row.get("source_row_ids"),
        ])
        existing_is_structured = bool(
            existing_source_ids
            or _normalise_spaces(str(existing_row.get("table_source_id") or ""))
            or _normalise_spaces(str(existing_row.get("statement_type") or ""))
            or _normalise_spaces(str(existing_row.get("source_anchor") or ""))
        )
        if existing_is_structured and target_is_aggregate_like:
            return True
    return False


def table_label_metadata_lookup_score(
    slot: Mapping[str, Any],
    evidence_item: Mapping[str, Any],
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
    value_role = _normalise_spaces(str(slot.get("value_role") or "")).lower()
    aggregation_stage = _normalise_spaces(str(slot.get("aggregation_stage") or "")).lower()
    if value_role == "aggregate":
        score += 2.0
    if aggregation_stage == "final":
        score += 2.5
    elif aggregation_stage in {"direct", "subtotal"}:
        score += 1.25
    matched_line_label = _normalise_spaces(str(slot.get("_matched_line_label") or ""))
    if matched_line_label:
        slot_surfaces = [
            _normalise_spaces(str(value or ""))
            for value in (
                slot.get("label"),
                slot.get("matched_operand_label"),
                slot.get("concept"),
            )
            if _normalise_spaces(str(value or ""))
        ]
        matched_line_compact = re.sub(r"\s+", "", matched_line_label)
        if matched_line_label in slot_surfaces or (
            matched_line_compact
            and matched_line_compact in {re.sub(r"\s+", "", surface) for surface in slot_surfaces}
        ):
            score += 2.0
    if normalized_unit in {"", "UNKNOWN"}:
        score -= 1.5
    else:
        score += 0.25
    return score


def score_direct_structured_lookup_evidence(
    score_input: DirectStructuredLookupEvidenceScoreInput,
) -> DirectStructuredLookupEvidenceScoreResult:
    """Score one structured evidence item without reading graph state."""

    operand = score_input.operand
    evidence_item = score_input.evidence_item
    metadata = dict(evidence_item.get("metadata") or {})
    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if not structured_cells:
        return DirectStructuredLookupEvidenceScoreResult(
            score=0.0,
            reason="no_structured_cells",
        )

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
            return DirectStructuredLookupEvidenceScoreResult(
                score=0.0,
                reason="surface_contract_not_satisfied",
            )

    normalized_operand_needles = [
        _normalise_spaces(str(needle))
        for needle in operand_needles(operand)
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
        for needle in normalized_operand_needles
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
    aggregate_label = _normalise_spaces(str(metadata.get("aggregate_label") or ""))
    preferred_value_roles = {
        _normalise_spaces(str(item)).lower()
        for item in (binding_policy.get("prefer_value_roles") or [])
        if _normalise_spaces(str(item))
    }
    preferred_aggregation_stages = {
        _normalise_spaces(str(item)).lower()
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if _normalise_spaces(str(item))
    }
    if value_role == "adjustment":
        score -= 4.0
    aggregate_like = bool(
        value_role == "aggregate"
        or aggregation_stage in {"direct", "final", "subtotal"}
        or aggregate_label
    )
    if aggregate_like and "aggregate" in preferred_value_roles:
        score += 4.0
    if aggregate_like and preferred_aggregation_stages and aggregation_stage in preferred_aggregation_stages:
        score += 2.0
    if value_role == "detail" and operand_prefers_aggregate_value_role(operand):
        score -= 1.5
    if aggregation_stage in {"direct", "final", "subtotal"}:
        score += 0.75
    return DirectStructuredLookupEvidenceScoreResult(
        score=score,
        reason="evidence_scored",
    )


def resolve_direct_structured_operand_acceptance(
    acceptance_input: DirectStructuredOperandAcceptanceInput,
) -> DirectStructuredOperandAcceptanceResult:
    """Apply direct-row grounding and ambiguity gates in runtime order."""

    accepted_operand_rows = acceptance_input.direct_operand_rows
    required_surface_filter_applied = False
    pre_lookup_ambiguity_filter_applied = False
    lookup_direct_support_filter_applied = False
    lookup_ambiguity_filter_applied = False

    def _row_is_ambiguous(
        row: Dict[str, Any],
        evidence_by_id: Dict[str, Dict[str, Any]],
    ) -> bool:
        return direct_lookup_row_is_ambiguous_context_table(
            row,
            _evidence_item_for_operand_row(row, evidence_by_id),
            query=str(acceptance_input.ambiguity_query or ""),
            active_subtask=dict(acceptance_input.ambiguity_active_subtask or {}),
            required_operands=acceptance_input.required_operands,
        )

    if accepted_operand_rows and acceptance_input.required_operands:
        evidence_by_id = _evidence_items_by_id(acceptance_input.evidence_items)
        required_surface_filter_applied = True
        accepted_operand_rows = [
            row
            for row in accepted_operand_rows
            if any(
                _operand_row_matches_requirement(row, operand)
                for operand in acceptance_input.required_operands
            )
            and _operand_row_satisfies_required_surface_contract(
                row,
                evidence_by_id,
                acceptance_input.required_operands,
                require_direct_support=acceptance_input.operation_family == "ratio",
            )
        ]
        pre_lookup_ambiguity_filter_applied = True
        accepted_operand_rows = [
            row
            for row in accepted_operand_rows
            if not _row_is_ambiguous(row, evidence_by_id)
        ]

    if accepted_operand_rows and acceptance_input.operation_family in {"lookup", "single_value"}:
        evidence_by_id = _evidence_items_by_id(acceptance_input.evidence_items)
        if acceptance_input.required_operands:
            lookup_direct_support_filter_applied = True
            accepted_operand_rows = [
                row
                for row in accepted_operand_rows
                if _llm_lookup_operand_has_direct_support(
                    row,
                    _evidence_item_for_operand_row(row, evidence_by_id),
                    acceptance_input.required_operands,
                )
            ]
        lookup_ambiguity_filter_applied = True
        accepted_operand_rows = [
            row
            for row in accepted_operand_rows
            if not _row_is_ambiguous(row, evidence_by_id)
        ]

    return DirectStructuredOperandAcceptanceResult(
        accepted_operand_rows=accepted_operand_rows,
        required_surface_filter_applied=required_surface_filter_applied,
        pre_lookup_ambiguity_filter_applied=pre_lookup_ambiguity_filter_applied,
        lookup_direct_support_filter_applied=lookup_direct_support_filter_applied,
        lookup_ambiguity_filter_applied=lookup_ambiguity_filter_applied,
    )


def resolve_direct_structured_preferred_slot_adoption(
    adoption_input: DirectStructuredPreferredSlotAdoptionInput,
) -> DirectStructuredPreferredSlotAdoptionResult:
    """Adopt one prepared evidence slot without consulting graph state."""

    current = adoption_input.current_operand_row
    operand = adoption_input.required_operand
    peer_units = adoption_input.normalized_peer_raw_units
    preferred = adoption_input.preferred_slot
    preferred_unit = _normalise_spaces(str(preferred.get("raw_unit") or ""))
    current_unit = _normalise_spaces(str(current.get("raw_unit") or ""))
    preferred_raw = _normalise_spaces(str(preferred.get("raw_value") or ""))
    current_raw = _normalise_spaces(str(current.get("raw_value") or ""))
    unit_alignment_improves = bool(
        adoption_input.operation_family == "ratio"
        and peer_units
        and preferred_raw == current_raw
        and preferred_unit in peer_units
        and current_unit not in peer_units
    )
    if (
        adoption_input.current_score > adoption_input.preferred_score
        and not unit_alignment_improves
    ):
        return DirectStructuredPreferredSlotAdoptionResult(
            selected_operand_row=current,
            preferred_slot_adopted=False,
            unit_alignment_improves=False,
            reason="higher_current_evidence_score",
        )
    if (
        adoption_input.current_score == adoption_input.preferred_score
        and not unit_alignment_improves
    ):
        return DirectStructuredPreferredSlotAdoptionResult(
            selected_operand_row=current,
            preferred_slot_adopted=False,
            unit_alignment_improves=False,
            reason="equal_evidence_score",
        )

    preferred_row = {
        **current,
        "operand_id": current.get("operand_id")
        or f"direct_lookup_{adoption_input.row_index + 1:03d}",
        "evidence_id": preferred.get("source_row_id"),
        "source_row_id": preferred.get("source_row_id"),
        "source_row_ids": preferred.get("source_row_ids") or [],
        "source_anchor": preferred.get("source_anchor"),
        "label": preferred.get("label"),
        "raw_value": preferred.get("raw_value"),
        "raw_unit": preferred.get("raw_unit"),
        "normalized_value": preferred.get("normalized_value"),
        "normalized_unit": preferred.get("normalized_unit"),
        "period": preferred.get("period"),
        "value_role": preferred.get("value_role"),
        "aggregation_stage": preferred.get("aggregation_stage"),
        "aggregate_label": preferred.get("aggregate_label"),
        "matched_operand_label": _normalise_spaces(str(operand.get("label") or "")),
        "matched_operand_concept": _normalise_spaces(str(operand.get("concept") or "")),
        "matched_operand_role": _normalise_spaces(str(operand.get("role") or "")),
    }
    return DirectStructuredPreferredSlotAdoptionResult(
        selected_operand_row=preferred_row,
        preferred_slot_adopted=True,
        unit_alignment_improves=unit_alignment_improves,
        reason=(
            "ratio_unit_alignment_selected"
            if unit_alignment_improves
            else "preferred_slot_selected"
        ),
    )


def resolve_post_coercion_llm_direct_support(
    support_input: PostCoercionLlmDirectSupportInput,
) -> PostCoercionLlmDirectSupportResult:
    """Validate direct support without copying a graph-coerced LLM row."""

    direct_support_accepted = _llm_lookup_operand_has_direct_support(
        support_input.operand_row,
        support_input.evidence_item,
        support_input.required_operands,
    )
    return PostCoercionLlmDirectSupportResult(
        operand_row=support_input.operand_row,
        direct_support_accepted=direct_support_accepted,
        reason=(
            "direct_support_present"
            if direct_support_accepted
            else "missing_direct_support"
        ),
    )


def resolve_post_coercion_llm_operand_selection(
    selection_input: PostCoercionLlmOperandSelectionInput,
) -> PostCoercionLlmOperandSelectionResult:
    """Apply post-loop required selection before direct-first merge."""

    if not selection_input.required_operands:
        return PostCoercionLlmOperandSelectionResult(
            selected_operand_rows=selection_input.operand_rows,
            required_surface_filter_applied=False,
            lookup_rematch_filter_applied=False,
            direct_merge_applied=False,
        )

    selected_operand_rows = [
        row
        for row in selection_input.operand_rows
        if any(
            _operand_row_matches_requirement(row, operand)
            for operand in selection_input.required_operands
        )
        and _operand_row_satisfies_required_surface_contract(
            row,
            selection_input.evidence_by_id,
            selection_input.required_operands,
            require_direct_support=selection_input.require_direct_support,
        )
    ]
    if selection_input.lookup_rematch_required:
        selected_operand_rows = [
            row
            for row in selected_operand_rows
            if any(
                _operand_row_matches_requirement(row, operand)
                for operand in selection_input.required_operands
            )
        ]

    direct_merge_applied = bool(selection_input.direct_structured_rows)
    if direct_merge_applied:
        selected_operand_rows = merge_operand_rows(
            selection_input.direct_structured_rows,
            selected_operand_rows,
            required_operands=selection_input.required_operands,
        )
    return PostCoercionLlmOperandSelectionResult(
        selected_operand_rows=selected_operand_rows,
        required_surface_filter_applied=True,
        lookup_rematch_filter_applied=selection_input.lookup_rematch_required,
        direct_merge_applied=direct_merge_applied,
    )


def resolve_recovered_operand_context_adoption(
    adoption_input: RecoveredOperandContextAdoptionInput,
) -> RecoveredOperandContextAdoptionResult:
    """Adopt recovered operand rows and only their referenced evidence."""

    if not adoption_input.recovered_operand_rows:
        return RecoveredOperandContextAdoptionResult(
            selected_operand_rows=adoption_input.current_operand_rows,
            evidence_items=adoption_input.evidence_items,
            adopted_evidence_ids=(),
            context_applied=False,
            reason="no_context_rows",
        )

    if adoption_input.context_kind == "period_comparison":
        supplemental_operand_rows = adoption_input.current_operand_rows
        reason: RecoveredOperandContextAdoptionReason = "period_context_merged"
    elif adoption_input.context_kind == "coherent_ratio":
        supplemental_operand_rows = []
        reason = "coherent_ratio_context_replaced"
    else:
        raise ValueError(f"unsupported recovered operand context: {adoption_input.context_kind}")

    selected_operand_rows = merge_operand_rows(
        adoption_input.recovered_operand_rows,
        supplemental_operand_rows,
        required_operands=adoption_input.required_operands,
    )
    used_evidence_ids = {
        str(row.get("evidence_id") or "")
        for row in adoption_input.recovered_operand_rows
        if str(row.get("evidence_id") or "").strip()
    }
    existing_evidence_ids = {
        str(item.get("evidence_id") or "")
        for item in adoption_input.evidence_items
        if isinstance(item, dict) and str(item.get("evidence_id") or "").strip()
    }
    adopted_evidence_items: List[Dict[str, Any]] = []
    adopted_evidence_ids: List[str] = []
    for item in adoption_input.recovered_evidence_items:
        used_candidate_id = str(item.get("evidence_id") or "")
        if used_candidate_id not in used_evidence_ids:
            continue
        if str(item.get("evidence_id") or "") in existing_evidence_ids:
            continue
        adopted_evidence_items.append(item)
        adopted_evidence_ids.append(used_candidate_id)

    return RecoveredOperandContextAdoptionResult(
        selected_operand_rows=selected_operand_rows,
        evidence_items=adoption_input.evidence_items + adopted_evidence_items,
        adopted_evidence_ids=tuple(adopted_evidence_ids),
        context_applied=True,
        reason=reason,
    )


def select_sibling_direct_operand_candidate(
    current_row: Dict[str, Any],
    direct_rows: Sequence[Dict[str, Any]],
) -> OperandCandidateSelection:
    """Select one coherent sibling candidate without using input order.

    This function only selects the direct candidate to compare.  The caller's
    provenance policy remains responsible for deciding whether that candidate
    may replace the dependency-backed current row.
    """

    def _ordered_rejections(
        items: Sequence[OperandCandidateRejection],
    ) -> Tuple[OperandCandidateRejection, ...]:
        return tuple(sorted(items, key=lambda item: (item.candidate_id, item.reason)))

    current_binding_key = _operand_binding_key(current_row)
    context_roles: Dict[str, set[str]] = {}
    for row in direct_rows:
        context_key = _operand_context_key(row)
        role = _normalise_spaces(str(row.get("matched_operand_role") or ""))
        if context_key and role:
            context_roles.setdefault(context_key, set()).add(role)

    eligible: List[Dict[str, Any]] = []
    rejected: List[OperandCandidateRejection] = []
    for row in direct_rows:
        candidate = dict(row)
        candidate_id = _operand_candidate_id(candidate)
        if _operand_binding_key(candidate) != current_binding_key:
            rejected.append(OperandCandidateRejection(candidate_id, "binding_mismatch"))
            continue
        context_key = _operand_context_key(candidate)
        if not context_key or len(context_roles.get(context_key, set())) < 2:
            rejected.append(OperandCandidateRejection(candidate_id, "incomplete_context"))
            continue
        eligible.append(candidate)

    if not eligible:
        return OperandCandidateSelection(
            selected_row=None,
            selected_candidate_id="",
            reason="no_eligible_candidate",
            rejected=_ordered_rejections(rejected),
        )

    current_non_task_sources = {
        source_id
        for source_id in operand_row_source_ids(current_row)
        if not source_id.startswith("task_output:")
    }
    current_table_id = _normalise_spaces(str(current_row.get("table_source_id") or ""))

    def _source_coherence_rank(candidate: Dict[str, Any]) -> Tuple[int, int]:
        candidate_non_task_sources = {
            source_id
            for source_id in operand_row_source_ids(candidate)
            if not source_id.startswith("task_output:")
        }
        shared_source = bool(current_non_task_sources.intersection(candidate_non_task_sources))
        candidate_table_id = _normalise_spaces(str(candidate.get("table_source_id") or ""))
        same_table = bool(
            current_table_id
            and candidate_table_id
            and current_table_id == candidate_table_id
        )
        return (int(shared_source), int(same_table))

    ranked = [(_source_coherence_rank(candidate), candidate) for candidate in eligible]
    top_rank = max(rank for rank, _candidate in ranked)
    top_candidates = [candidate for rank, candidate in ranked if rank == top_rank]
    lower_candidates = [candidate for rank, candidate in ranked if rank != top_rank]
    rejected.extend(
        OperandCandidateRejection(_operand_candidate_id(candidate), "lower_source_coherence")
        for candidate in sorted(lower_candidates, key=_operand_candidate_total_order_key)
    )

    if len(top_candidates) == 1:
        selected = top_candidates[0]
        if len(eligible) == 1:
            reason: SiblingDirectSelectionReason = "only_eligible_candidate"
        elif top_rank[0]:
            reason = "shared_source_context"
        elif top_rank[1]:
            reason = "same_table_context"
        else:
            reason = "only_eligible_candidate"
        return OperandCandidateSelection(
            selected_row=selected,
            selected_candidate_id=_operand_candidate_id(selected),
            reason=reason,
            rejected=_ordered_rejections(rejected),
        )

    semantic_signatures = {
        _operand_candidate_semantic_signature(candidate)
        for candidate in top_candidates
    }
    materially_conflicting = any(
        operand_row_values_materially_conflict(left, right)
        for index, left in enumerate(top_candidates)
        for right in top_candidates[index + 1 :]
    )
    if materially_conflicting or len(semantic_signatures) > 1:
        rejected.extend(
            OperandCandidateRejection(
                _operand_candidate_id(candidate),
                "ambiguous_conflicting_top_rank",
            )
            for candidate in sorted(top_candidates, key=_operand_candidate_total_order_key)
        )
        return OperandCandidateSelection(
            selected_row=None,
            selected_candidate_id="",
            reason="ambiguous_conflicting_top_rank",
            rejected=_ordered_rejections(rejected),
        )

    selected = min(top_candidates, key=_operand_candidate_total_order_key)
    selected_candidate_id = _operand_candidate_id(selected)
    rejected.extend(
        OperandCandidateRejection(_operand_candidate_id(candidate), "equivalent_duplicate")
        for candidate in sorted(top_candidates, key=_operand_candidate_total_order_key)
        if candidate is not selected
    )
    return OperandCandidateSelection(
        selected_row=selected,
        selected_candidate_id=selected_candidate_id,
        reason="equivalent_top_rank_tiebreak",
        rejected=_ordered_rejections(rejected),
    )


def evidence_item_conflicts_requested_scope(
    item: Dict[str, Any],
    desired_consolidation_scope: str,
) -> bool:
    """Return whether an evidence item conflicts with the requested scope."""

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
    separate_markers = tuple(
        str(marker).lower() for marker in (scope_policy.get("separate") or ()) if str(marker)
    )
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
    has_separate_context = bool(
        separate_markers and any(marker in context_text for marker in separate_markers)
    )
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


def operand_row_conflicts_requested_scope(
    row: Dict[str, Any],
    desired_consolidation_scope: str,
) -> bool:
    """Return whether an operand row has an explicit opposing scope."""

    desired_scope = _normalise_spaces(str(desired_consolidation_scope or "unknown"))
    if desired_scope == "unknown":
        return False
    scope = _normalise_spaces(str((row or {}).get("consolidation_scope") or "unknown"))
    if scope == desired_scope:
        return False
    if desired_scope == "consolidated":
        return scope == "separate"
    if desired_scope == "separate":
        return scope == "consolidated"
    return False


def collect_retrieval_context_docs(
    retrieved_docs: Sequence[Any],
    seed_retrieved_docs: Sequence[Any],
    *,
    seed_limit: int,
) -> List[Any]:
    """Append unique seed documents after the visible retrieval window."""

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


def _required_operand_context_terms(required_operands: Sequence[Dict[str, Any]]) -> List[str]:
    terms: List[str] = []
    for operand in required_operands:
        for needle in operand_needles(dict(operand)):
            normalized = _normalise_spaces(
                re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", needle)
            )
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


def _text_has_any_context_term(text: str, terms: Sequence[str]) -> bool:
    normalized = _normalise_spaces(text)
    compact = re.sub(r"\s+", "", normalized)
    return any(
        term in normalized or re.sub(r"\s+", "", term) in compact
        for term in terms
        if term
    )


def _synthesized_calculation_doc_item(
    doc: Any,
    *,
    index: int,
    evidence_id: str,
    desired_consolidation_scope: str,
    build_source_anchor: Callable[[Dict[str, Any]], str],
) -> Optional[Dict[str, Any]]:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    anchor = build_source_anchor(metadata)
    text = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
    if not text:
        return None
    display_text = _strip_rerank_metadata(text) or text
    provisional_item = {"metadata": metadata, "source_anchor": anchor, "claim": text}
    if evidence_item_conflicts_requested_scope(provisional_item, desired_consolidation_scope):
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


def collect_retrieved_operand_evidence_candidates(
    retrieved_docs: Sequence[Tuple[Any, Any]],
    seed_retrieved_docs: Sequence[Tuple[Any, Any]],
    *,
    existing_evidence_items: Sequence[Dict[str, Any]],
    required_operands: List[Dict[str, Any]],
    missing_dependency_bindings: Sequence[Dict[str, Any]],
    query: str,
    topic: str,
    report_scope: Optional[Dict[str, Any]],
    desired_consolidation_scope: str,
    build_source_anchor: Callable[[Dict[str, Any]], str],
    build_required_operands_from_candidates: Callable[..., List[Dict[str, Any]]],
    extract_ratio_row_candidates: Callable[[List[Tuple[Any, Any]], str, str], List[Dict[str, Any]]],
    extract_ratio_component_candidates: Callable[[List[Tuple[Any, Any]], str, str], List[Dict[str, Any]]],
) -> OperandEvidenceCandidateBatch:
    """Collect ordered fallback evidence without consulting graph state.

    The returned batch contains only newly collected evidence.  The caller owns
    publication into the graph state and runtime trace.
    """

    candidate_docs = list(retrieved_docs)
    seen_candidate_doc_ids = {
        str(
            (getattr(doc, "metadata", {}) or {}).get("chunk_uid")
            or (getattr(doc, "metadata", {}) or {}).get("chunk_id")
            or ""
        )
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
    seen_anchors = {
        str(item.get("source_anchor") or "") for item in existing_evidence_items
    }
    required_context_terms = _required_operand_context_terms(required_operands)

    if required_operands:
        operand_probe_items: List[Dict[str, Any]] = []
        for candidate_index, (doc, _score) in enumerate(candidate_docs, start=1):
            full_text = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
            full_text = _strip_rerank_metadata(full_text) or full_text
            item = _synthesized_calculation_doc_item(
                doc,
                index=candidate_index,
                evidence_id=f"ev_operand_doc_{candidate_index:03d}",
                desired_consolidation_scope=desired_consolidation_scope,
                build_source_anchor=build_source_anchor,
            )
            if item:
                probe_item = dict(item)
                probe_item["claim"] = full_text
                probe_item["raw_row_text"] = full_text
                operand_probe_items.append(probe_item)
        operand_probe_rows = build_required_operands_from_candidates(
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
                    missing_terms.extend(operand_needles(dict(binding)))
                    label = _normalise_spaces(str(binding.get("label") or ""))
                    if label:
                        missing_terms.append(label)
                missing_terms.extend(required_context_terms)
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
    ratio_row_candidates = extract_ratio_row_candidates(candidate_docs, query, topic)
    if ratio_row_candidates:
        logger.info(
            "[calc_operands] ratio row fallback candidates=%s",
            len(ratio_row_candidates),
        )
        synthesized_items.extend(ratio_row_candidates)
        synthesized_bullets.extend(
            f"- {item['source_anchor']} {item.get('source_context', '')} "
            f"{str(item.get('raw_row_text') or '')[:180]} (direct)"
            for item in ratio_row_candidates
        )
        seen_anchors.update(
            str(item.get("source_anchor") or "") for item in ratio_row_candidates
        )
    if not percent_point_query:
        component_candidates = extract_ratio_component_candidates(candidate_docs, query, topic)
        if component_candidates:
            logger.info(
                "[calc_operands] ratio component fallback candidates=%s",
                len(component_candidates),
            )
            synthesized_items.extend(component_candidates)
            synthesized_bullets.extend(
                f"- {item['source_anchor']} {item.get('source_context', '')} "
                f"{str(item.get('raw_row_text') or '')[:180]} (direct)"
                for item in component_candidates
            )
            seen_anchors.update(
                str(item.get("source_anchor") or "") for item in component_candidates
            )

    doc_fallback_limit = 16 if missing_dependency_bindings else 8
    for index, (doc, _score) in enumerate(
        candidate_docs[: min(doc_fallback_limit, len(candidate_docs))],
        start=1,
    ):
        item = _synthesized_calculation_doc_item(
            doc,
            index=index,
            evidence_id=f"ev_doc_{index:03d}",
            desired_consolidation_scope=desired_consolidation_scope,
            build_source_anchor=build_source_anchor,
        )
        if not item:
            continue
        anchor = str(item.get("source_anchor") or "")
        text = str(item.get("claim") or "")
        missing_terms: List[str] = []
        for binding in missing_dependency_bindings:
            missing_terms.extend(operand_needles(dict(binding)))
            label = _normalise_spaces(str(binding.get("label") or ""))
            if label:
                missing_terms.append(label)
        missing_terms.extend(required_context_terms)
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

    return OperandEvidenceCandidateBatch(
        evidence_items=tuple(synthesized_items),
        evidence_bullets=tuple(synthesized_bullets),
    )


def lookup_hints_for_concept_key(concept_key: str) -> Dict[str, Any]:
    normalized_key = _normalise_spaces(str(concept_key or ""))
    if not normalized_key:
        return {}

    ontology = get_financial_ontology()
    concept = ontology.concept(str(concept_key or "").strip())
    if concept:
        return dict(concept.get("lookup_hints") or {})

    for spec in list(getattr(ontology, "all_concept_specs", lambda: [])() or []):
        if bool(spec.get("is_group")):
            continue
        if _normalise_spaces(str(spec.get("concept") or "")) == normalized_key:
            return dict(spec.get("lookup_hints") or {})
    return {}


def lookup_prefers_canonical_statement_rows(operand: Dict[str, Any]) -> bool:
    if operand_segment_label(operand):
        return False
    lookup_hints = lookup_hints_for_concept_key(str(operand.get("concept") or ""))
    return bool(lookup_hints.get("prefer_canonical_statement_rows"))


def lookup_canonical_statement_preferences(operand: Dict[str, Any]) -> tuple[List[str], List[str]]:
    lookup_hints = lookup_hints_for_concept_key(str(operand.get("concept") or ""))
    return (
        [
            str(item).strip()
            for item in (lookup_hints.get("canonical_statement_types") or [])
            if str(item).strip()
        ],
        [
            str(item).strip()
            for item in (lookup_hints.get("canonical_sections") or [])
            if str(item).strip()
        ],
    )


def lookup_query_surface_preferences(operand: Dict[str, Any]) -> List[str]:
    lookup_hints = lookup_hints_for_concept_key(str(operand.get("concept") or ""))
    return [
        str(item).strip()
        for item in (lookup_hints.get("aggregate_query_surfaces") or [])
        if str(item).strip()
    ]


def candidate_source_priority_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    statement_type: str,
    value_role: str,
    aggregation_stage: str,
    local_heading: str,
) -> float:
    score = 0.0

    if is_balance_sheet_aggregate_operand(operand):
        if statement_type in {"summary_financials", "balance_sheet"}:
            score += 3.0
            if value_role == "aggregate":
                score += 1.25
            elif value_role == "detail":
                score -= 0.5
            if aggregation_stage in {"direct", "final"}:
                score += 0.75
            scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
            scope_markers = dict(scoring_policy.get("balance_sheet_scope_markers") or {})
            if any(marker in local_heading for marker in scope_markers.get("consolidated") or ()):
                score += 0.5
            elif any(marker in local_heading for marker in scope_markers.get("separate") or ()):
                score -= 0.5
        elif statement_type == "notes":
            score -= 1.5
            if value_role == "detail":
                score -= 1.25

    if is_capex_total_operand(operand):
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        capex_section_terms = tuple(str(item) for item in (scoring_policy.get("capex_priority_section_terms") or ()) if str(item))
        if any(token in local_heading for token in capex_section_terms):
            score += 2.75
            if value_role == "aggregate":
                score += 1.0
            if aggregation_stage in {"final", "direct", "subtotal"}:
                score += 0.75
        if statement_type == "cash_flow":
            score -= 2.5
            if value_role != "aggregate":
                score -= 0.5

    if operand_prefers_contextual_aggregate_match(operand):
        context_text = candidate_local_aggregate_context(candidate)
        if (
            value_role == "aggregate"
            and aggregation_stage in {"final", "subtotal", "direct"}
            and _text_has_positive_surface(context_text, operand)
        ):
            score += 2.0
        elif value_role == "detail" and _text_has_positive_surface(context_text, operand):
            score -= 1.0

    if operand_prefers_note_aggregate_lookup(operand):
        candidate_kind = _normalise_spaces(str(candidate.get("candidate_kind") or ""))
        metadata = dict(candidate.get("metadata") or {})
        row_context_text = str(metadata.get("row_context_text") or "")
        if statement_type == "notes":
            if candidate_kind == "structured_value":
                if value_role == "aggregate" and aggregation_stage == "final":
                    score += 2.75
                elif value_role == "aggregate" and aggregation_stage == "subtotal":
                    score += 1.5
                elif value_role == "aggregate" and aggregation_stage == "direct":
                    score += 1.0
            elif candidate_kind == "table_row":
                score -= 1.0
                if row_context_text and len(row_context_text) > 2500:
                    score -= 0.75
                if value_role != "aggregate":
                    score -= 0.5

    return score


def candidate_matches_operand(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    if candidate_conflicts_with_operand_concept(candidate, operand):
        return False

    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    structured_candidate = candidate_kind in {
        "structured_value",
        "structured_row",
        "structured_column_value",
        "table_row",
        "evidence_row",
    }
    metadata = dict(candidate.get("metadata") or {})
    row_label = str(metadata.get("row_label") or "").strip()
    if _operand_text_match(row_label, operand):
        return True
    semantic_label = str(metadata.get("semantic_label") or "").strip()
    if _operand_text_match(semantic_label, operand):
        return True
    semantic_aliases = " ".join(
        str(item).strip()
        for item in (metadata.get("semantic_aliases") or [])
        if str(item).strip()
    )
    if _operand_text_match(semantic_aliases, operand):
        return True
    row_headers = " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip())
    if _operand_text_match(row_headers, operand):
        return True
    aggregate_label = str(metadata.get("aggregate_label") or "").strip()
    if _operand_text_match(aggregate_label, operand):
        return True
    if candidate_kind != "table_row" and _operand_text_match(str(metadata.get("table_row_labels_text") or ""), operand):
        return True
    if is_capex_total_operand(operand):
        section_context = " ".join(
            part
            for part in (
                str(metadata.get("local_heading") or "").strip(),
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("row_context_text") or "").strip(),
                str(candidate.get("text") or "").strip(),
            )
            if part
        )
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (operand.get("preferred_sections") or [])
            if str(item).strip()
        ]
        if preferred_sections and any(section in _normalise_spaces(section_context) for section in preferred_sections):
            if (
                _text_has_positive_surface(section_context, operand)
                and (candidate_value_role(candidate) == "aggregate" or candidate_aggregation_stage(candidate) in {"final", "direct", "subtotal"})
            ):
                return True
    if operand_prefers_contextual_aggregate_match(operand):
        section_context = candidate_local_aggregate_context(candidate)
        aggregate_surface = _normalise_spaces(
            " ".join(
                part
                for part in (
                    str(metadata.get("aggregate_label") or "").strip(),
                    str(metadata.get("row_label") or "").strip(),
                    str(metadata.get("semantic_label") or "").strip(),
                )
                if part
            )
        )
        aggregate_like = (
            candidate_value_role(candidate) == "aggregate"
            or candidate_aggregation_stage(candidate) in {"final", "subtotal"}
            or aggregate_like_row_stage(aggregate_surface) != "none"
        )
        if (
            _text_has_positive_surface(section_context, operand)
            and aggregate_like
        ):
            return True
    if structured_candidate:
        return False
    return _operand_text_match(str(candidate.get("text") or ""), operand)


def candidate_location_entity_subject_score(candidate: Dict[str, Any], *, operand: Dict[str, Any]) -> float:
    """Prefer count candidates where a location context has an explicit subject."""
    unit_family = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
    operation_family = _normalise_spaces(str(operand.get("operation_family") or ""))
    role = _normalise_spaces(str(operand.get("role") or ""))
    if unit_family and unit_family != "COUNT":
        return 0.0
    if operation_family not in {"", "growth_rate", "lookup", "single_value"} and role not in {"current_period", "prior_period"}:
        return 0.0

    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    subject_pattern = str(scoring_policy.get("location_entity_subject_pattern") or "")
    temporal_subject_pattern = str(scoring_policy.get("location_entity_temporal_subject_pattern") or "")
    if not subject_pattern:
        return 0.0

    metadata = dict(candidate.get("metadata") or {})
    text = _normalise_spaces(
        " ".join(
            str(part or "")
            for part in (
                metadata.get("row_text"),
                metadata.get("semantic_label"),
                metadata.get("row_label"),
                metadata.get("table_context"),
                candidate.get("text"),
            )
            if str(part or "").strip()
        )
    )
    if not text:
        return 0.0

    compact = re.sub(r"\s+", "", text)
    matches = list(re.finditer(subject_pattern, compact))
    if not matches:
        return 0.0

    def _subject_is_temporal(subject: str) -> bool:
        if not subject:
            return True
        return bool(temporal_subject_pattern and re.search(temporal_subject_pattern, subject))

    if any(not _subject_is_temporal(str(match.groupdict().get("subject") or "")) for match in matches):
        try:
            return float(scoring_policy.get("location_entity_subject_bonus") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    try:
        return float(scoring_policy.get("location_entity_context_penalty") or 0.0)
    except (TypeError, ValueError):
        return 0.0


def operand_lookup_surface_match(text: str, operand: Dict[str, Any]) -> bool:
    surfaces = lookup_query_surface_preferences(operand)
    if not surfaces:
        return False
    return _text_has_contract_term(text, surfaces)


def candidate_direct_match_strength(candidate: Dict[str, Any], operand: Dict[str, Any]) -> float:
    """Score how directly a candidate label represents the requested operand."""
    if candidate_conflicts_with_operand_concept(candidate, operand):
        return 0.0

    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = _normalise_spaces(str(candidate.get("candidate_kind") or ""))
    surfaces: List[tuple[str, float]] = [
        (str(metadata.get("semantic_label") or "").strip(), 3.0),
        (str(metadata.get("row_label") or "").strip(), 2.5),
        (
            " ".join(
                str(item).strip()
                for item in (metadata.get("semantic_aliases") or [])
                if str(item).strip()
            ),
            2.0,
        ),
        (
            " ".join(
                str(item).strip()
                for item in (metadata.get("row_headers") or [])
                if str(item).strip()
            ),
            1.5,
        ),
        (str(metadata.get("aggregate_label") or "").strip(), 1.0),
    ]
    if candidate_kind != "table_row":
        surfaces.extend(
            [
                (str(metadata.get("table_row_labels_text") or "").strip(), 1.25),
                (str(metadata.get("row_text") or "").strip(), 1.0),
            ]
        )
    best = 0.0
    for surface, exact_bonus in surfaces:
        normalized_surface = _normalise_spaces(surface)
        if not normalized_surface:
            continue
        surface_variants = set(_surface_match_variants(normalized_surface))
        if any(_normalise_spaces(needle) == normalized_surface for needle in operand_needles(operand)):
            best = max(best, exact_bonus)
            continue
        if any(
            needle_variant in surface_variants
            for needle in operand_needles(operand)
            for needle_variant in _surface_match_variants(needle)
        ):
            best = max(best, exact_bonus)
            continue
        if _operand_text_match(normalized_surface, operand):
            best = max(best, exact_bonus * 0.5)
    if is_capex_total_operand(operand):
        context_text = " ".join(
            part
            for part in (
                str(metadata.get("local_heading") or "").strip(),
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("row_context_text") or "").strip(),
                str(candidate.get("text") or "").strip(),
            )
            if part
        )
        context_surfaces = [
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("section_path") or "").strip(),
        ]
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (operand.get("preferred_sections") or [])
            if str(item).strip()
        ]
        if preferred_sections and any(
            section in _normalise_spaces(surface)
            for section in preferred_sections
            for surface in context_surfaces
            if _normalise_spaces(surface)
        ):
            if (
                _text_has_positive_surface(context_text, operand)
                and (candidate_value_role(candidate) == "aggregate" or candidate_aggregation_stage(candidate) in {"final", "direct", "subtotal"})
            ):
                best = max(best, 2.25)
    if operand_prefers_contextual_aggregate_match(operand):
        context_text = candidate_local_aggregate_context(candidate)
        if (
            _text_has_positive_surface(context_text, operand)
            and (candidate_value_role(candidate) == "aggregate" or candidate_aggregation_stage(candidate) in {"final", "direct", "subtotal"})
        ):
            best = max(best, 2.0)
    aggregate_signal = _normalise_spaces(
        " ".join(
            part
            for part in (
                str(metadata.get("aggregate_label") or "").strip(),
                str(metadata.get("semantic_label") or "").strip(),
                str(metadata.get("row_label") or "").strip(),
            )
            if part
        )
    )
    if (
        aggregate_signal
        and _operand_text_match(aggregate_signal, operand)
        and candidate_value_role(candidate) == "aggregate"
        and candidate_aggregation_stage(candidate) in {"direct", "final", "subtotal"}
    ):
        best = max(best, 2.25)
    if (
        aggregate_signal
        and operand_lookup_surface_match(aggregate_signal, operand)
        and candidate_has_operand_context_surface(candidate, operand)
        and candidate_value_role(candidate) == "aggregate"
        and candidate_aggregation_stage(candidate) in {"direct", "final", "subtotal"}
    ):
        best = max(best, 2.25)
    if candidate_supports_segment_metric_combo(candidate, operand):
        best = max(best, 2.25)
    return best


def score_operand_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    constraints: Dict[str, Any],
    query_years: List[int],
    report_scope: Optional[Dict[str, Any]] = None,
) -> float:
    """Rank candidate rows/chunks for a single operand.

    The scorer is deterministic on purpose: it gives the graph a stable first
    pass before any optional LLM reranking is considered.
    """
    metadata = dict(candidate.get("metadata") or {})
    if candidate_conflicts_with_operand_concept(candidate, operand):
        return -10.0

    score = 0.0
    row_label = str(metadata.get("row_label") or "").strip()
    semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or row_label))
    operand_binding_policy = dict(operand.get("binding_policy") or {})
    if row_label:
        row_label_variants = set(_surface_match_variants(row_label))
        if any(
            needle_variant in row_label_variants
            for needle in operand_needles(operand)
            for needle_variant in _surface_match_variants(needle)
        ):
            score += 3.0
        elif _operand_text_match(row_label, operand):
            score += 1.5
    score += candidate_direct_match_strength(candidate, operand)
    candidate_kind = str(candidate.get("candidate_kind") or "")
    if candidate_kind == "structured_value":
        score += 2.5
    elif candidate_kind == "structured_row":
        score += 2.0
    elif candidate_kind == "structured_column_value":
        score += 1.75
    elif candidate_kind == "table_row":
        score += 1.0
    elif candidate_kind == "evidence_row":
        score += 0.5
    elif candidate_kind == "chunk":
        score -= 0.25

    if candidate_kind in {"structured_value", "structured_row", "structured_column_value", "table_row"}:
        direct_match_strength = candidate_direct_match_strength(candidate, operand)
        if direct_match_strength >= 2.5:
            score += 1.25
        elif direct_match_strength >= 1.5:
            score += 0.5

    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if isinstance(cell, dict)]
    numeric_cell_count = 0
    for cell in structured_cells:
        raw_value = _normalise_spaces(str(cell.get("value_text") or ""))
        raw_unit = _normalise_spaces(str(cell.get("unit_hint") or metadata.get("unit_hint") or ""))
        normalized_value, _normalized_unit = _normalise_operand_value(raw_value, raw_unit)
        if normalized_value is not None:
            numeric_cell_count += 1
    if (
        bool(metadata.get("direct_row_from_table_value_labels"))
        and numeric_cell_count == 1
        and _operand_text_match(" ".join(part for part in (row_label, semantic_label) if part), operand)
    ):
        score += 4.0

    value_role = candidate_value_role(candidate)
    aggregation_stage = candidate_aggregation_stage(candidate)
    if aggregation_stage == "final":
        score += 1.5
    elif aggregation_stage == "direct":
        score += 1.25
    elif aggregation_stage == "subtotal":
        score += 0.5
    elif value_role == "adjustment":
        score -= 1.5

    aggregate_signal = " ".join(
        part
        for part in (
            semantic_label,
            row_label,
            _normalise_spaces(str(metadata.get("aggregate_label") or "")),
            " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
        )
        if part
    )
    if value_role == "aggregate" and aggregation_stage in {"direct", "final"} and _operand_text_match(aggregate_signal, operand):
        score += 2.0
    elif value_role == "aggregate" and aggregation_stage == "subtotal" and _operand_text_match(aggregate_signal, operand):
        score += 0.75
    preferred_value_roles = [
        _normalise_spaces(str(item)).lower()
        for item in (operand_binding_policy.get("prefer_value_roles") or [])
        if _normalise_spaces(str(item))
    ]
    preferred_aggregation_stages = [
        _normalise_spaces(str(item)).lower()
        for item in (operand_binding_policy.get("prefer_aggregation_stages") or [])
        if _normalise_spaces(str(item))
    ]
    if value_role and value_role in preferred_value_roles:
        try:
            score += max(3.0 - (0.75 * preferred_value_roles.index(value_role)), 0.5)
        except ValueError:
            pass
    if aggregation_stage and aggregation_stage in preferred_aggregation_stages:
        try:
            score += max(4.0 - (0.75 * preferred_aggregation_stages.index(aggregation_stage)), 0.5)
        except ValueError:
            pass
    if value_role == "detail" and operand_prefers_aggregate_value_role(operand):
        score -= 1.5

    if candidate_has_numeric_value_signal(candidate):
        score += 1.0

    score += candidate_location_entity_subject_score(candidate, operand=operand)

    if candidate_is_descriptor_row(candidate):
        score -= 3.0

    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    operand_preferred_statement_types = [
        str(item).strip()
        for item in (operand.get("preferred_statement_types") or [])
        if str(item).strip()
    ]
    if preferred_statement_types:
        if statement_type in preferred_statement_types:
            score += 2.5
        elif statement_type != "unknown":
            score -= 0.8
    if operand_preferred_statement_types:
        if statement_type in operand_preferred_statement_types:
            score += 1.5
        elif statement_type != "unknown":
            score -= 0.35

    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
    if lookup_prefers_canonical_statement_rows(operand):
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        canonical_types, canonical_sections = lookup_canonical_statement_preferences(operand)
        canonical_section_hit = bool(canonical_sections) and any(
            _normalise_spaces(section_term) in local_heading or _normalise_spaces(section_term) in section_path
            for section_term in canonical_sections
            if _normalise_spaces(section_term)
        )
        note_markers = tuple(str(item) for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        note_context = any(marker in local_heading or marker in section_path for marker in note_markers)
        allows_note_canonical = any(
            marker in _normalise_spaces(section)
            for marker in note_markers
            for section in canonical_sections
        )
        if statement_type == "income_statement":
            score += 1.0
        elif statement_type == "summary_financials":
            score += 0.5
        elif statement_type == "notes":
            score -= 0.5
        if canonical_section_hit:
            score += 1.0
        elif note_context and not allows_note_canonical:
            score -= 2.5

        related_party_context = " ".join(
            part
            for part in (
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("table_row_labels_text") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("local_heading") or "").strip(),
                " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
                " ".join(str(item).strip() for item in (metadata.get("column_headers_chain") or []) if str(item).strip()),
            )
            if part
        )
        related_party_terms = tuple(str(item) for item in (scoring_policy.get("related_party_penalty_terms") or ()) if str(item))
        if any(token in related_party_context for token in related_party_terms):
            score -= 3.0
        stripped_row_label = _strip_financial_label_annotations(row_label)
        stripped_needles = {_strip_financial_label_annotations(needle) for needle in operand_needles(operand)}
        generic_suffix_terms = tuple(str(item) for item in (scoring_policy.get("generic_suffix_penalty_terms") or ()) if str(item))
        if stripped_row_label and any(token in stripped_row_label for token in generic_suffix_terms) and stripped_row_label not in stripped_needles:
            score -= 1.5

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    candidate_consolidation = candidate_consolidation_scope(metadata)
    desired_period_focus = operand_period_focus(operand, str((constraints or {}).get("period_focus") or "unknown").strip())
    if desired_consolidation == "unknown":
        desired_consolidation = str(operand_binding_policy.get("prefer_consolidation_scope") or "unknown").strip()
    if desired_period_focus == "unknown":
        desired_period_focus = str(operand_binding_policy.get("prefer_period_focus") or "unknown").strip()
    if desired_period_focus in {"current", "prior"} and is_delta_like_row_label(semantic_label or row_label):
        score -= 4.0
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    score += candidate_segment_binding_bonus(
        candidate,
        operand=operand,
        constraints=constraints,
        statement_type=statement_type,
        local_heading=local_heading,
        section_path=section_path,
    )
    if desired_consolidation != "unknown":
        if candidate_consolidation == desired_consolidation:
            score += 2.0
        elif candidate_consolidation != "unknown":
            score -= 2.0
        elif desired_consolidation == "consolidated":
            context_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {})
            consolidated_markers = tuple(str(item) for item in (context_markers.get("consolidated") or ()) if str(item))
            separate_markers = tuple(str(item) for item in (context_markers.get("separate") or ()) if str(item))
            if any(marker in local_heading for marker in consolidated_markers):
                score += 1.5
            elif any(marker in local_heading for marker in separate_markers):
                score -= 1.5
        elif desired_consolidation == "separate":
            context_markers = dict(CONSOLIDATION_SCOPE_POLICY.get("context_markers") or {})
            consolidated_markers = tuple(str(item) for item in (context_markers.get("consolidated") or ()) if str(item))
            separate_markers = tuple(str(item) for item in (context_markers.get("separate") or ()) if str(item))
            if any(marker in local_heading for marker in separate_markers):
                score += 1.5
            elif any(marker in local_heading for marker in consolidated_markers):
                score -= 1.5

    if desired_period_focus == "current":
        if candidate_period_focus == "current":
            score += 2.5
        elif candidate_period_focus == "prior":
            if candidate_matches_operand_target_year(candidate, operand, query_years):
                score += 0.5
            else:
                score -= 2.5
    elif desired_period_focus == "prior":
        if candidate_period_focus == "prior":
            score += 2.5
        elif candidate_period_focus == "current":
            if candidate_matches_operand_target_year(candidate, operand, query_years):
                score += 0.5
            else:
                score -= 2.5

    preferred_value_roles = [
        str(item).strip()
        for item in (operand_binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    ]
    avoid_value_roles = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_value_roles") or [])
        if str(item).strip()
    }
    preferred_aggregation_stages = [
        str(item).strip()
        for item in (operand_binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    ]
    avoid_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_aggregation_stages") or [])
        if str(item).strip()
    }
    score += preference_bonus(value_role, preferred_value_roles, base=0.6)
    score += preference_bonus(aggregation_stage, preferred_aggregation_stages, base=0.5)
    if _normalise_spaces(value_role) in avoid_value_roles:
        score -= 2.0
    if _normalise_spaces(aggregation_stage) in avoid_aggregation_stages:
        score -= 1.75

    operand_preferred_sections = [
        str(item).strip()
        for item in (operand.get("preferred_sections") or [])
        if str(item).strip()
    ]
    if operand_preferred_sections:
        if any(
            _normalise_spaces(section_term) in local_heading or _normalise_spaces(section_term) in section_path
            for section_term in operand_preferred_sections
        ):
            score += 0.75

    score += candidate_source_priority_bonus(
        candidate,
        operand=operand,
        statement_type=statement_type,
        value_role=value_role,
        aggregation_stage=aggregation_stage,
        local_heading=local_heading,
    )

    score += _metadata_period_match_strength(list(metadata.get("period_labels") or []), query_years) * 1.5
    score += candidate_period_table_coherence_bonus(
        candidate,
        operand=operand,
        query_years=query_years,
    )
    score += candidate_report_scope_binding_bonus(
        candidate,
        operand=operand,
        query_years=query_years,
        report_scope=dict(report_scope or {}),
    )

    if str(metadata.get("table_source_id") or "").strip():
        score += 0.25

    return score


def direct_candidate_semantic_priority(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    preferred_statement_types: List[str],
    query_years: List[int],
) -> tuple[int, int, int, int, int]:
    metadata = dict(candidate.get("metadata") or {})
    binding_policy = dict(operand.get("binding_policy") or {})
    normalized_preferred_types = [
        _normalise_spaces(str(item))
        for item in preferred_statement_types
        if _normalise_spaces(str(item))
    ]
    preferred_value_roles = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_value_roles") or [])
        if _normalise_spaces(str(item))
    ]
    preferred_aggregation_stages = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if _normalise_spaces(str(item))
    ]

    statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    value_role = candidate_value_role(candidate)
    aggregation_stage = candidate_aggregation_stage(candidate)
    direct_match_strength = candidate_direct_match_strength(candidate, operand)
    candidate_kind = _normalise_spaces(str(candidate.get("candidate_kind") or ""))

    statement_rank = 0
    if statement_type in normalized_preferred_types:
        statement_rank = len(normalized_preferred_types) - normalized_preferred_types.index(statement_type)

    value_role_rank = 0
    if value_role in preferred_value_roles:
        value_role_rank = len(preferred_value_roles) - preferred_value_roles.index(value_role)

    aggregation_stage_rank = 0
    if aggregation_stage in preferred_aggregation_stages:
        aggregation_stage_rank = len(preferred_aggregation_stages) - preferred_aggregation_stages.index(aggregation_stage)

    target_year_match = 1 if candidate_matches_operand_target_year(candidate, operand, query_years) else 0
    structured_value_rank = 1 if candidate_kind == "structured_value" else 0

    return (
        aggregation_stage_rank,
        value_role_rank,
        statement_rank,
        target_year_match,
        structured_value_rank + int(direct_match_strength * 10),
    )


def candidate_is_canonical_statement_winner(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    query_years: List[int],
) -> bool:
    if not lookup_prefers_canonical_statement_rows(operand):
        return False
    metadata = dict(candidate.get("metadata") or {})
    statement_type = str(metadata.get("statement_type") or "").strip()
    canonical_types, canonical_sections = lookup_canonical_statement_preferences(operand)
    if canonical_types and statement_type not in canonical_types:
        return False
    canonical_statement_type_hit = bool(canonical_types) and statement_type in canonical_types and statement_type not in {"notes", "unknown"}
    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    note_markers = tuple(str(item) for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
    note_context = any(marker in local_heading or marker in section_path for marker in note_markers)
    allows_note_canonical = any(
        marker in _normalise_spaces(section)
        for marker in note_markers
        for section in canonical_sections
    )
    if note_context and not allows_note_canonical:
        return False
    if canonical_sections and not canonical_statement_type_hit and not any(
        _normalise_spaces(section) in local_heading or _normalise_spaces(section) in section_path
        for section in canonical_sections
        if _normalise_spaces(section)
    ):
        return False
    if candidate_direct_match_strength(candidate, operand) < 2.5:
        return False
    if not candidate_matches_operand_target_year(candidate, operand, query_years):
        candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
        desired_period_focus = operand_period_focus(operand, "unknown")
        if desired_period_focus in {"current", "prior"} and candidate_period_focus != desired_period_focus:
            return False
    return True


def candidate_is_direct_grounding_candidate(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    query_years: List[int],
    operation_family: str = "",
    report_scope: Optional[Dict[str, Any]] = None,
) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    if candidate_kind not in {"structured_value", "structured_row", "structured_column_value", "table_row"}:
        return False
    if candidate_is_descriptor_row(candidate):
        return False
    if not candidate_has_numeric_value_signal(candidate):
        return False

    direct_match_strength = candidate_direct_match_strength(candidate, operand)
    if direct_match_strength < 1.0:
        return False

    operand_binding_policy = dict(operand.get("binding_policy") or {})
    value_role = candidate_value_role(candidate)
    aggregation_stage = candidate_aggregation_stage(candidate)
    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    if not binding_policy_allows_candidate_shape(
        value_role=value_role,
        aggregation_stage=aggregation_stage,
        operand_binding_policy=operand_binding_policy,
    ):
        return False

    if lookup_prefers_canonical_statement_rows(operand) and candidate_kind == "table_row":
        if statement_type not in {"income_statement", "summary_financials", "notes"}:
            return False

    desired_consolidation = str((constraints or {}).get("consolidation_scope") or "unknown").strip()
    if desired_consolidation == "unknown":
        desired_consolidation = str(operand_binding_policy.get("prefer_consolidation_scope") or "unknown").strip()
    candidate_consolidation = candidate_consolidation_scope(metadata)
    if (
        desired_consolidation != "unknown"
        and candidate_consolidation != "unknown"
        and candidate_consolidation != desired_consolidation
    ):
        return False

    desired_period_focus = operand_period_focus(
        operand,
        str((constraints or {}).get("period_focus") or "unknown").strip(),
    )
    if desired_period_focus == "unknown":
        desired_period_focus = str(operand_binding_policy.get("prefer_period_focus") or "unknown").strip()
    semantic_label = _normalise_spaces(str(metadata.get("semantic_label") or metadata.get("row_label") or ""))
    if desired_period_focus in {"current", "prior"} and is_delta_like_row_label(semantic_label):
        return False
    if not candidate_matches_segment_binding(candidate, operand, strict=True):
        return False
    if not candidate_matches_target_report_scope(
        candidate,
        operand=operand,
        query_years=query_years,
        report_scope=dict(report_scope or {}),
    ):
        return False
    candidate_period_focus = str(metadata.get("period_focus") or "unknown").strip()
    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    trust_candidate_period_focus = (
        candidate_period_focus in {"current", "prior"}
        or not (candidate_kind == "table_row" and row_text)
    )
    target_year_match = candidate_matches_operand_target_year(candidate, operand, query_years)
    if trust_candidate_period_focus:
        if desired_period_focus == "current" and candidate_period_focus == "prior" and not target_year_match:
            return False
        if desired_period_focus == "prior" and candidate_period_focus == "current" and not target_year_match:
            return False

    if operation_family in {"lookup", "single_value"} and candidate_kind == "table_row":
        if table_row_has_matching_structured_sibling(metadata, operand):
            return False
        if row_text and is_delta_like_row_label(row_text):
            return False

    return True


def candidate_satisfies_direct_acceptance_contract(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    query_years: List[int],
    operation_family: str = "",
    selected_cell: Optional[Dict[str, Any]] = None,
    report_scope: Optional[Dict[str, Any]] = None,
) -> bool:
    if not candidate_is_direct_grounding_candidate(
        candidate,
        operand=operand,
        constraints=constraints,
        query_years=query_years,
        operation_family=operation_family,
        report_scope=report_scope,
    ):
        return False

    metadata = dict(candidate.get("metadata") or {})
    desired_period_focus = operand_period_focus(
        operand,
        str((constraints or {}).get("period_focus") or "unknown").strip(),
    )
    if selected_cell:
        period_policy = dict(PERIOD_FOCUS_POLICY)
        period_presence_pattern = str(period_policy.get("period_presence_pattern") or period_policy.get("explicit_year_pattern") or r"$^")
        current_markers = tuple(str(item) for item in (period_policy.get("current_markers") or ()) if str(item))
        prior_markers = tuple(str(item) for item in (period_policy.get("prior_markers") or ()) if str(item))
        explicit_year_pattern = str(period_policy.get("explicit_year_pattern") or r"20\d{2}")
        period_text = _structured_cell_period_text(
            selected_cell,
            query_years,
            desired_period_focus,
        )
        candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
        if desired_period_focus == "current" and candidate_period_focus == "prior":
            return False
        if desired_period_focus == "prior" and candidate_period_focus == "current":
            return False
        if not re.search(period_presence_pattern, period_text):
            report_year: Optional[int] = None
            for raw_year in (
                selected_cell.get("_report_year"),
                selected_cell.get("report_year"),
                selected_cell.get("year"),
            ):
                try:
                    if raw_year not in (None, ""):
                        report_year = int(raw_year)
                        break
                except (TypeError, ValueError):
                    continue
            if report_year is not None:
                target_years = operand_target_years(operand, query_years)
                if target_years and report_year in target_years:
                    period_text = str(report_year)
                else:
                    period_text = str(report_year)
        normalized_period = _normalise_spaces(period_text)
        if desired_period_focus == "current" and normalized_period and any(
            token in normalized_period for token in prior_markers
        ):
            return False
        if desired_period_focus == "prior" and normalized_period and any(
            token in normalized_period for token in current_markers
        ):
            return False
        target_years = operand_target_years(operand, query_years)
        explicit_years = [int(token) for token in re.findall(explicit_year_pattern, period_text or "")]
        if target_years and explicit_years and not any(year in explicit_years for year in target_years):
            return False

    binding_policy = dict(operand.get("binding_policy") or {})
    if bool(
        binding_policy.get("require_surface_contract_for_direct_match")
        or binding_policy.get("require_surface_contract_for_direct_lookup")
    ) and not candidate_has_required_surface_contract(
        candidate,
        operand,
        selected_cell=selected_cell,
    ):
        return False

    if operation_family in {"lookup", "single_value"}:
        desired_unit_family = _normalise_spaces(str(operand.get("unit_family") or "")).upper()
        candidate_unit_family = candidate_selected_unit_family(candidate, selected_cell=selected_cell)
        if (
            desired_unit_family in {"KRW", "USD", "COUNT", "PERCENT"}
            and candidate_unit_family
            and candidate_unit_family != desired_unit_family
        ):
            return False
        direct_match_strength = candidate_direct_match_strength(candidate, operand)
        if direct_match_strength < 2.0:
            return False

    statement_type = str(metadata.get("statement_type") or "unknown").strip()
    value_role = candidate_value_role(candidate)
    aggregation_stage = candidate_aggregation_stage(candidate)
    local_heading = _normalise_spaces(
        str(metadata.get("local_heading") or metadata.get("table_context") or metadata.get("section_path") or "")
    )
    section_path = _normalise_spaces(str(metadata.get("section_path") or ""))
    if operation_family in {"lookup", "single_value"} and lookup_prefers_canonical_statement_rows(operand):
        canonical_types, canonical_sections = lookup_canonical_statement_preferences(operand)
        scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
        note_markers = tuple(str(item) for item in (scoring_policy.get("note_context_markers") or ()) if str(item))
        note_context = any(marker in local_heading or marker in section_path for marker in note_markers)
        allows_note_canonical = any(
            marker in _normalise_spaces(section)
            for section in canonical_sections
            for marker in note_markers
        )
        canonical_statement_type_hit = (
            bool(canonical_types)
            and statement_type in canonical_types
            and statement_type not in {"notes", "unknown"}
        )
        canonical_section_hit = bool(canonical_sections) and any(
            _normalise_spaces(section_term) in local_heading or _normalise_spaces(section_term) in section_path
            for section_term in canonical_sections
            if _normalise_spaces(section_term)
        )
        if canonical_types and statement_type not in canonical_types:
            return False
        if note_context and not allows_note_canonical and not canonical_section_hit:
            return False
        if canonical_sections and (local_heading or section_path) and not canonical_section_hit and not canonical_statement_type_hit:
            return False
    if is_balance_sheet_aggregate_operand(operand):
        if statement_type == "notes" and value_role == "detail":
            return False
    if is_capex_total_operand(operand):
        preferred_sections = [
            _normalise_spaces(str(item))
            for item in (operand.get("preferred_sections") or [])
            if str(item).strip()
        ]
        aggregate_like = value_role == "aggregate" or aggregation_stage in {"final", "direct", "subtotal"}
        if candidate.get("candidate_kind") in {"structured_value", "structured_column_value"} and not aggregate_like:
            return False
        if preferred_sections:
            in_preferred_section = any(
                section_term in local_heading or section_term in section_path
                for section_term in preferred_sections
                if section_term
            )
            if not in_preferred_section and not aggregate_like:
                return False

    metadata_periods = [str(item).strip() for item in (metadata.get("period_labels") or []) if str(item).strip()]
    target_years = operand_target_years(operand, query_years)
    if desired_period_focus == "prior" and target_years and metadata_periods:
        flattened = " ".join(metadata_periods)
        explicit_years = [int(token) for token in re.findall(r"20\d{2}", flattened)]
        if explicit_years and not any(year in explicit_years for year in target_years):
            return False

    return True


def candidate_satisfies_ratio_component_acceptance_contract(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    query_years: List[int],
    selected_cell: Optional[Dict[str, Any]] = None,
    report_scope: Optional[Dict[str, Any]] = None,
) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    candidate_kind = str(candidate.get("candidate_kind") or "").strip()
    if candidate_kind not in {"structured_value", "structured_row", "structured_column_value", "table_row", "evidence_row"}:
        return False
    if candidate_is_descriptor_row(candidate):
        return False
    if not candidate_has_numeric_value_signal(candidate):
        return False
    if not candidate_matches_segment_binding(candidate, operand, strict=True):
        return False
    if not candidate_matches_target_report_scope(
        candidate,
        operand=operand,
        query_years=query_years,
        report_scope=dict(report_scope or {}),
    ):
        return False

    value_role = candidate_value_role(candidate)
    aggregation_stage = candidate_aggregation_stage(candidate)
    direct_row_like = (
        candidate_kind in {"table_row", "evidence_row"}
        and selected_cell is not None
        and candidate_has_required_surface_contract(candidate, operand, selected_cell=selected_cell)
        and candidate_direct_match_strength(candidate, operand) >= 1.0
    )
    aggregate_like = (
        value_role == "aggregate"
        or aggregation_stage in {"final", "subtotal", "direct"}
        or direct_row_like
    )
    if not aggregate_like:
        return False
    if not binding_policy_allows_candidate_shape(
        value_role=value_role,
        aggregation_stage=aggregation_stage,
        operand_binding_policy=dict(operand.get("binding_policy") or {}),
    ):
        return False

    surface_contract = _operand_surface_contract(operand)
    positive_terms = [str(item).strip() for item in (surface_contract.get("positive") or []) if str(item).strip()]
    if positive_terms:
        if not candidate_has_required_surface_contract(candidate, operand, selected_cell=selected_cell):
            return False
    elif candidate_direct_match_strength(candidate, operand) < 1.0:
        return False

    desired_period_focus = operand_period_focus(
        operand,
        str((constraints or {}).get("period_focus") or "unknown").strip(),
    )
    candidate_period_focus = _normalise_spaces(str(metadata.get("period_focus") or ""))
    target_year_match = candidate_matches_operand_target_year(candidate, operand, query_years)
    if desired_period_focus == "current" and candidate_period_focus == "prior" and not target_year_match:
        return False
    if desired_period_focus == "prior" and candidate_period_focus == "current" and not target_year_match:
        return False
    return True


def coerce_lookup_magnitude_value(
    *,
    normalized_value: Optional[float],
    normalized_unit: str,
    raw_value: str,
    concept: str,
    statement_type: str,
    row_label: str = "",
    semantic_label: str = "",
) -> Optional[float]:
    if normalized_value is None or normalized_unit != "KRW" or normalized_value >= 0:
        return normalized_value

    lookup_hints = lookup_hints_for_concept_key(concept)
    normalized_statement_type = _normalise_spaces(statement_type).lower()
    if not bool(lookup_hints.get("coerce_parenthesized_negative_to_positive_magnitude")):
        return normalized_value
    if normalized_statement_type not in {"income_statement", "summary_financials", "notes"}:
        return normalized_value

    magnitude_surface_tokens = [
        _normalise_spaces(str(token))
        for token in (lookup_hints.get("magnitude_surface_tokens") or [])
        if _normalise_spaces(str(token))
    ]
    surface = _normalise_spaces(" ".join(part for part in (row_label, semantic_label) if part))
    if surface and magnitude_surface_tokens and not any(token in surface for token in magnitude_surface_tokens):
        return normalized_value
    raw_surface = str(raw_value or "")
    if not any(marker in raw_surface for marker in ("(", ")", "△", "▲", "-")):
        return normalized_value
    return abs(normalized_value)


def candidate_row_block_signature(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    row_context_text = str(metadata.get("row_context_text") or "").strip()
    if not row_context_text:
        return ""
    try:
        row_index = int(metadata.get("row_index"))
    except (TypeError, ValueError):
        return ""

    rows = [_normalise_spaces(line) for line in row_context_text.splitlines() if _normalise_spaces(line)]
    if row_index < 0 or row_index >= len(rows):
        return ""

    header_end: Optional[int] = None
    for current_index in range(row_index - 1, -1, -1):
        if rows[current_index].startswith("|"):
            header_end = current_index
            break
    if header_end is None:
        return ""

    header_start = header_end
    while header_start - 1 >= 0 and rows[header_start - 1].startswith("|"):
        header_start -= 1

    header_block = " || ".join(rows[header_start : header_end + 1])
    table_source_id = str(metadata.get("table_source_id") or "").strip()
    return f"{table_source_id}::{header_start}:{header_block}".strip(":")


def candidate_direct_logical_signature(
    candidate: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> tuple[str, str, str, str]:
    metadata = dict(candidate.get("metadata") or {})
    block_key = candidate_row_block_signature(candidate)
    table_source_id = _normalise_spaces(str(metadata.get("table_source_id") or ""))
    row_label = _normalise_spaces(
        str(
            metadata.get("row_label")
            or metadata.get("semantic_label")
            or metadata.get("aggregate_label")
            or ""
        )
    )
    value_text = _normalise_spaces(str((selected_cell or {}).get("value_text") or ""))
    if not value_text:
        value_text = _normalise_spaces(str(metadata.get("row_text") or str(candidate.get("text") or "")))
    period_marker = _normalise_spaces(
        " ".join(str(item).strip() for item in ((selected_cell or {}).get("column_headers") or []) if str(item).strip())
    )
    if not period_marker:
        period_marker = _normalise_spaces(str(metadata.get("period_focus") or ""))
    scope_key = block_key or table_source_id or _normalise_spaces(str(metadata.get("section_path") or ""))
    return (scope_key, row_label, value_text, period_marker)


def candidate_direct_family_signature(
    candidate: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> tuple[str, str, str, str]:
    metadata = dict(candidate.get("metadata") or {})
    block_key = candidate_row_block_signature(candidate)
    table_source_id = _normalise_spaces(str(metadata.get("table_source_id") or ""))
    row_label = _normalise_spaces(
        str(
            metadata.get("row_label")
            or metadata.get("semantic_label")
            or metadata.get("aggregate_label")
            or ""
        )
    )
    period_marker = _normalise_spaces(
        " ".join(str(item).strip() for item in ((selected_cell or {}).get("column_headers") or []) if str(item).strip())
    )
    statement_type = _normalise_spaces(str(metadata.get("statement_type") or ""))
    scope_key = block_key or table_source_id or _normalise_spaces(str(metadata.get("section_path") or ""))
    return (scope_key, row_label, period_marker, statement_type)


def repair_note_operand_units_from_same_block(
    operand_rows: List[Dict[str, Any]],
    candidate_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    if len(operand_rows) < 2:
        return operand_rows

    ambiguous_units = {str(item) for item in (RECONCILIATION_POLICY.get("ambiguous_krw_units") or ())}
    note_statement_type = str(RECONCILIATION_POLICY.get("note_statement_type") or "")
    rows = [dict(row) for row in operand_rows]
    block_groups: Dict[str, List[Dict[str, Any]]] = {}

    for row in rows:
        if str(row.get("statement_type") or "").strip().lower() != note_statement_type:
            continue
        evidence_id = str(row.get("evidence_id") or "").strip()
        candidate = candidate_map.get(evidence_id) or {}
        block_key = candidate_row_block_signature(candidate)
        if not block_key:
            continue
        block_groups.setdefault(block_key, []).append(row)

    for block_rows in block_groups.values():
        resolved_units = list(
            dict.fromkeys(
                str(row.get("raw_unit") or "").strip()
                for row in block_rows
                if str(row.get("raw_unit") or "").strip() not in ambiguous_units
            )
        )
        if len(resolved_units) != 1:
            continue
        inherited_unit = resolved_units[0]
        for row in block_rows:
            current_unit = str(row.get("raw_unit") or "").strip()
            if current_unit not in ambiguous_units:
                continue
            normalized_value, normalized_unit = _normalise_operand_value(
                str(row.get("raw_value") or "").strip(),
                inherited_unit,
            )
            normalized_value = coerce_lookup_magnitude_value(
                normalized_value=normalized_value,
                normalized_unit=normalized_unit,
                raw_value=str(row.get("raw_value") or "").strip(),
                concept=str(row.get("matched_operand_concept") or ""),
                statement_type=str(row.get("statement_type") or ""),
                row_label=str(row.get("matched_operand_label") or ""),
                semantic_label=str(row.get("matched_operand_label") or ""),
            )
            if normalized_value is None:
                continue
            row["raw_unit"] = inherited_unit
            row["normalized_value"] = normalized_value
            row["normalized_unit"] = normalized_unit

    return rows
