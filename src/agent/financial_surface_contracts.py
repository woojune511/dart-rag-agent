"""Operand surface-contract helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.financial_operation_policies import _label_implies_percent_metric
from src.agent.financial_runtime_normalization import _normalise_operand_value, _normalise_spaces
from src.config.retrieval_policy import (
    CAPEX_TOTAL_CONCEPT_KEY,
    CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER,
    CONSOLIDATION_SCOPE_POLICY,
    HELPER_RUNTIME_POLICY,
    OPERAND_CANDIDATE_SCORING_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
)


def operand_needles(operand: Dict[str, Any]) -> List[str]:
    label = str(operand.get("label") or "").strip()
    aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
    return [needle for needle in [label, *aliases] if needle]


def operand_segment_label(operand: Dict[str, Any]) -> str:
    binding_policy = dict(operand.get("binding_policy") or {})
    return _normalise_spaces(str(binding_policy.get("segment_label") or ""))


def scoped_surface_affinity_priority(
    items: List[Dict[str, Any]],
    *,
    query: str,
    topic: str,
    required_operands: Optional[List[Dict[str, Any]]] = None,
    require_segment_operand: bool = False,
    direct_weight: float = 0.0,
    adjustment_weight: float = 0.0,
) -> float:
    if require_segment_operand and not any(
        operand_segment_label(dict(operand or {})) for operand in list(required_operands or [])
    ):
        return 0.0
    affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
    metric_terms = tuple(str(term) for term in (affinity_policy.get("metric_terms") or ()) if str(term))
    query_surface = _normalise_spaces(f"{query} {topic}")
    if metric_terms and not any(term in query_surface for term in metric_terms):
        return 0.0
    surface = _normalise_spaces(
        " ".join(
            str(part or "")
            for item in items
            for metadata in [dict(item.get("metadata") or {})]
            for part in (
                item.get("claim"),
                item.get("raw_row_text"),
                item.get("quote_span"),
                item.get("text"),
                item.get("source_context"),
                metadata.get("row_label"),
                metadata.get("semantic_label"),
                metadata.get("table_header_context"),
                metadata.get("table_row_labels_text"),
                metadata.get("table_value_labels_text"),
                metadata.get("table_summary_text"),
            )
            if str(part or "").strip()
        )
    )
    direct_markers = tuple(
        str(marker)
        for marker in (affinity_policy.get("scoped_direct_row_markers") or ())
        if str(marker)
    )
    adjustment_markers = tuple(
        str(marker)
        for marker in (affinity_policy.get("scoped_adjustment_row_markers") or ())
        if str(marker)
    )
    score = 0.0
    if direct_markers and any(marker in surface for marker in direct_markers):
        score += direct_weight
    if adjustment_markers and any(marker in surface for marker in adjustment_markers):
        score += adjustment_weight
    return score


def _operand_surface_contract(operand: Dict[str, Any]) -> Dict[str, List[str]]:
    explicit_contract = dict(operand.get("surface_contract") or {})
    if explicit_contract:
        return {
            "positive": [str(item).strip() for item in (explicit_contract.get("positive") or []) if str(item).strip()],
            "negative": [str(item).strip() for item in (explicit_contract.get("negative") or []) if str(item).strip()],
        }

    concept_key = _normalise_spaces(str(operand.get("concept") or ""))
    legacy_contracts = {
        str(key): dict(value or {})
        for key, value in dict(HELPER_RUNTIME_POLICY.get("legacy_concept_surface_contracts") or {}).items()
    }
    if concept_key and concept_key in legacy_contracts:
        return dict(legacy_contracts[concept_key])

    needles = " ".join(operand_needles(operand))
    for contract in legacy_contracts.values():
        positive_terms = [str(item).strip() for item in (contract.get("positive") or []) if str(item).strip()]
        if any(_normalise_spaces(term) in _normalise_spaces(needles) for term in positive_terms):
            return dict(contract)
    return {}


def _text_has_contract_term(text: str, terms: List[str]) -> bool:
    haystack = _normalise_spaces(text or "")
    if not haystack:
        return False
    haystack_compact = re.sub(r"\s+", "", haystack)
    for raw_term in terms:
        normalized_term = _normalise_spaces(raw_term)
        if not normalized_term:
            continue
        term_compact = re.sub(r"\s+", "", normalized_term)
        if normalized_term in haystack or (term_compact and term_compact in haystack_compact):
            return True
    return False


def text_has_positive_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("positive") or []))


def text_has_negative_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("negative") or []))


def candidate_conflicts_with_operand_concept(candidate: Dict[str, Any], operand: Dict[str, Any]) -> bool:
    normalized_needles = [_normalise_spaces(needle) for needle in operand_needles(operand) if _normalise_spaces(needle)]
    expects_exclusive_marker = any(CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER in needle for needle in normalized_needles)

    metadata = dict(candidate.get("metadata") or {})
    authoritative_surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
    ]
    authoritative_surfaces = [surface for surface in authoritative_surfaces if surface]
    if not expects_exclusive_marker and any(CANDIDATE_CONCEPT_CONFLICT_EXCLUSIVE_MARKER in _normalise_spaces(surface) for surface in authoritative_surfaces):
        return True

    contract = _operand_surface_contract(operand)
    if not contract:
        return False

    if any(text_has_negative_surface(surface, operand) for surface in authoritative_surfaces):
        return True

    if any(text_has_positive_surface(surface, operand) for surface in authoritative_surfaces):
        return False

    return text_has_negative_surface(str(candidate.get("text") or ""), operand)


def is_balance_sheet_aggregate_operand(operand: Dict[str, Any]) -> bool:
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in operand_needles(operand)}
    needles.discard("")
    aggregate_labels = set(
        re.sub(r"\s+", "", _normalise_spaces(str(item)))
        for item in (HELPER_RUNTIME_POLICY.get("balance_sheet_aggregate_labels") or ())
        if str(item)
    )
    return any(needle in aggregate_labels for needle in needles)


def is_capex_total_operand(operand: Dict[str, Any]) -> bool:
    concept = str(operand.get("concept") or "").strip()
    if concept == CAPEX_TOTAL_CONCEPT_KEY:
        return True
    needles = {re.sub(r"\s+", "", _normalise_spaces(needle)) for needle in operand_needles(operand)}
    needles.discard("")
    scoring_policy = dict(OPERAND_CANDIDATE_SCORING_POLICY)
    capex_surfaces = {
        re.sub(r"\s+", "", _normalise_spaces(str(surface)))
        for surface in (scoring_policy.get("capex_total_surfaces") or ())
        if str(surface).strip()
    }
    return any(needle in capex_surfaces for needle in needles)


def operand_prefers_contextual_aggregate_match(operand: Dict[str, Any]) -> bool:
    binding_policy = dict(operand.get("binding_policy") or {})
    preferred_value_roles = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    ]
    preferred_aggregation_stages = [
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    ]
    if "aggregate" not in preferred_value_roles:
        return False
    if not any(stage in {"final", "subtotal", "direct"} for stage in preferred_aggregation_stages):
        return False
    return bool(_operand_surface_contract(operand).get("positive"))


def operand_prefers_note_aggregate_lookup(operand: Dict[str, Any]) -> bool:
    preferred_statement_types = {
        _normalise_spaces(str(item))
        for item in (operand.get("preferred_statement_types") or [])
        if str(item).strip()
    }
    if "notes" not in preferred_statement_types:
        return False

    binding_policy = dict(operand.get("binding_policy") or {})
    preferred_value_roles = {
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    }
    preferred_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    }
    return "aggregate" in preferred_value_roles and bool(
        {"final", "subtotal", "direct"} & preferred_aggregation_stages
    )


def candidate_local_aggregate_context(candidate: Dict[str, Any]) -> str:
    metadata = dict(candidate.get("metadata") or {})
    return " ".join(
        part
        for part in (
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("table_header_context") or "").strip(),
            str(metadata.get("table_summary_text") or "").strip(),
        )
        if part
    )


def candidate_consolidation_scope(metadata: Dict[str, Any]) -> str:
    explicit = _normalise_spaces(str(metadata.get("consolidation_scope") or "unknown"))
    if explicit and explicit != "unknown":
        return explicit

    context_text = " ".join(
        part
        for part in (
            str(metadata.get("local_heading") or "").strip(),
            str(metadata.get("table_context") or "").strip(),
            str(metadata.get("section_path") or "").strip(),
            str(metadata.get("table_header_context") or "").strip(),
        )
        if part
    )
    normalized_context = _normalise_spaces(context_text)
    scope_policy = dict(CONSOLIDATION_SCOPE_POLICY)
    context_markers = dict(scope_policy.get("context_markers") or {})
    if any(marker in normalized_context for marker in context_markers.get("consolidated") or ()):
        return "consolidated"
    if any(marker in normalized_context for marker in context_markers.get("separate") or ()):
        return "separate"
    for pattern in scope_policy.get("separate_section_patterns") or ():
        if re.search(str(pattern), normalized_context):
            return "separate"
    return explicit or "unknown"


def binding_policy_allows_candidate_shape(
    *,
    value_role: str,
    aggregation_stage: str,
    operand_binding_policy: Dict[str, Any],
) -> bool:
    normalized_value_role = _normalise_spaces(value_role)
    normalized_stage = _normalise_spaces(aggregation_stage)
    avoid_value_roles = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_value_roles") or [])
        if str(item).strip()
    }
    avoid_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("avoid_aggregation_stages") or [])
        if str(item).strip()
    }
    if normalized_value_role and normalized_value_role in avoid_value_roles:
        return False
    if normalized_stage and normalized_stage in avoid_aggregation_stages:
        return False

    preferred_value_roles = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("prefer_value_roles") or [])
        if str(item).strip()
    }
    preferred_aggregation_stages = {
        _normalise_spaces(str(item))
        for item in (operand_binding_policy.get("prefer_aggregation_stages") or [])
        if str(item).strip()
    }
    if preferred_value_roles and normalized_value_role not in preferred_value_roles:
        return False
    if preferred_aggregation_stages and normalized_stage not in preferred_aggregation_stages:
        return False
    return True


def candidate_selected_unit_family(
    candidate: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> str:
    metadata = dict(candidate.get("metadata") or {})
    raw_value = _normalise_spaces(
        str(
            (selected_cell or {}).get("value_text")
            or metadata.get("value_text")
            or metadata.get("raw_value")
            or ""
        )
    )
    raw_unit = _normalise_spaces(
        str(
            (selected_cell or {}).get("unit_hint")
            or metadata.get("unit_hint")
            or metadata.get("raw_unit")
            or ""
        )
    )
    if raw_value or raw_unit:
        _, normalized_unit = _normalise_operand_value(raw_value or "1", raw_unit)
        if normalized_unit and normalized_unit != "UNKNOWN":
            return normalized_unit
    label_text = _normalise_spaces(
        " ".join(
            str(part or "").strip()
            for part in (
                metadata.get("semantic_label"),
                metadata.get("row_label"),
                metadata.get("aggregate_label"),
            )
            if str(part or "").strip()
        )
    )
    if _label_implies_percent_metric(label_text):
        return "PERCENT"
    return ""


def candidate_has_required_surface_contract(
    candidate: Dict[str, Any],
    operand: Dict[str, Any],
    *,
    selected_cell: Optional[Dict[str, Any]] = None,
) -> bool:
    contract = _operand_surface_contract(operand)
    positive_terms = [str(item).strip() for item in (contract.get("positive") or []) if str(item).strip()]
    if not positive_terms:
        return True

    metadata = dict(candidate.get("metadata") or {})
    surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in ((selected_cell or {}).get("column_headers") or []) if str(item).strip()),
        str(metadata.get("table_row_labels_text") or "").strip(),
        str(metadata.get("table_value_labels_text") or "").strip(),
        str(metadata.get("row_text") or "").strip(),
        str(candidate.get("text") or "").strip(),
    ]
    return any(_text_has_contract_term(surface, positive_terms) for surface in surfaces if surface)


def candidate_has_numeric_value_signal(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells:
        for cell in structured_cells:
            if re.search(r"\d", str(cell.get("value_text") or "")):
                return True
        return False

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")[1:] if part.strip()]
        return any(re.search(r"\d", part) for part in parts)

    return bool(re.search(r"\d", str(candidate.get("text") or "")))


def candidate_is_descriptor_row(candidate: Dict[str, Any]) -> bool:
    metadata = dict(candidate.get("metadata") or {})
    row_label = _normalise_spaces(str(metadata.get("row_label") or ""))
    non_value_row_labels = set(str(item) for item in (HELPER_RUNTIME_POLICY.get("non_value_row_labels") or ()) if str(item))
    if row_label in non_value_row_labels:
        return True

    structured_cells = [dict(cell) for cell in (metadata.get("structured_cells") or []) if dict(cell)]
    if structured_cells and not any(re.search(r"\d", str(cell.get("value_text") or "")) for cell in structured_cells):
        return True

    row_text = _normalise_spaces(str(metadata.get("row_text") or ""))
    if row_text and "|" in row_text:
        parts = [part.strip() for part in row_text.split("|")]
        if parts and _normalise_spaces(parts[0]) in non_value_row_labels:
            numeric_parts = [part for part in parts[1:] if re.search(r"\d", part)]
            if not numeric_parts:
                return True

    return False


def _candidate_segment_surfaces(candidate: Dict[str, Any], *, strict: bool = False) -> List[str]:
    metadata = dict(candidate.get("metadata") or {})
    surfaces = [
        str(metadata.get("semantic_label") or "").strip(),
        str(metadata.get("row_label") or "").strip(),
        str(metadata.get("aggregate_label") or "").strip(),
        " ".join(str(item).strip() for item in (metadata.get("semantic_aliases") or []) if str(item).strip()),
        " ".join(str(item).strip() for item in (metadata.get("row_headers") or []) if str(item).strip()),
        str(metadata.get("row_text") or "").strip(),
    ]
    if not strict:
        surfaces.extend(
            [
                str(metadata.get("table_row_labels_text") or "").strip(),
                str(metadata.get("table_context") or "").strip(),
                str(metadata.get("local_heading") or "").strip(),
                str(metadata.get("section_path") or "").strip(),
                str(metadata.get("table_summary_text") or "").strip(),
                str(candidate.get("text") or "").strip(),
                str(candidate.get("source_anchor") or "").strip(),
            ]
        )
    return [_normalise_spaces(surface) for surface in surfaces if _normalise_spaces(surface)]


def candidate_matches_segment_binding(candidate: Dict[str, Any], operand: Dict[str, Any], *, strict: bool = False) -> bool:
    segment_label = operand_segment_label(operand)
    if not segment_label:
        return True

    normalized_segment = _normalise_spaces(segment_label)
    compact_segment = re.sub(r"\s+", "", normalized_segment)
    for surface in _candidate_segment_surfaces(candidate, strict=strict):
        compact_surface = re.sub(r"\s+", "", surface)
        if normalized_segment in surface or (compact_segment and compact_segment in compact_surface):
            return True
    return False


def candidate_segment_binding_bonus(
    candidate: Dict[str, Any],
    *,
    operand: Dict[str, Any],
    constraints: Dict[str, Any],
    statement_type: str,
    local_heading: str,
    section_path: str,
) -> float:
    segment_label = operand_segment_label(operand)
    if not segment_label:
        return 0.0

    score = 0.0
    segment_scope = _normalise_spaces(str((constraints or {}).get("segment_scope") or "none"))
    matches_segment = candidate_matches_segment_binding(candidate, operand)
    context_text = " ".join(part for part in (local_heading, section_path) if part)
    if matches_segment:
        score += 5.0
        segment_context_terms = tuple(
            str(item)
            for item in (HELPER_RUNTIME_POLICY.get("segment_context_bonus_terms") or ())
            if str(item)
        )
        if any(token in context_text for token in segment_context_terms):
            score += 1.5
        if statement_type in {"notes", "mda"}:
            score += 0.75
    else:
        score -= 4.5
        if segment_scope == "segment" and statement_type in {"summary_financials", "income_statement", "balance_sheet"}:
            score -= 1.5
    return score
