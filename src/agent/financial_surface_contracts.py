"""Operand surface-contract helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config.retrieval_policy import HELPER_RUNTIME_POLICY


def _operand_needles(operand: Dict[str, Any]) -> List[str]:
    label = str(operand.get("label") or "").strip()
    aliases = [str(item).strip() for item in (operand.get("aliases") or []) if str(item).strip()]
    return [needle for needle in [label, *aliases] if needle]


def _operand_segment_label(operand: Dict[str, Any]) -> str:
    binding_policy = dict(operand.get("binding_policy") or {})
    return _normalise_spaces(str(binding_policy.get("segment_label") or ""))


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

    needles = " ".join(_operand_needles(operand))
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


def _text_has_positive_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("positive") or []))


def _text_has_negative_surface(text: str, operand: Dict[str, Any]) -> bool:
    contract = _operand_surface_contract(operand)
    return _text_has_contract_term(text, list(contract.get("negative") or []))


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
    segment_label = _operand_segment_label(operand)
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
    segment_label = _operand_segment_label(operand)
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
