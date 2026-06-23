"""Retrieval and statement hint helpers for financial graph runtime."""

from __future__ import annotations

import re
from typing import Any, Dict, List

from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES,
    FINANCIAL_NUMERIC_STATEMENT_HINT_POLICIES,
    FINANCIAL_SEGMENT_SECTION_HINT_POLICY,
    active_narrative_policies,
    active_numeric_section_hint_policies,
    narrative_policy_preferred_sections,
    narrative_policy_terms,
    numeric_section_policy_preferred_sections,
    numeric_section_policy_statement_types,
)


def _section_hint_alias(section: str) -> str:
    text = _normalise_spaces(section)
    if not text:
        return ""
    if ">" in text:
        text = text.split(">")[-1].strip()
    text = re.sub(r"^\d+\.\s*", "", text)
    return text


def _matched_ontology_concept_specs(query: str, topic: str = "") -> List[Dict[str, Any]]:
    ontology = get_financial_ontology()
    return [
        dict(spec)
        for spec in (ontology.concept_specs(query, topic, "comparison") or [])
        if dict(spec)
    ]


def _desired_statement_types(query: str, topic: str) -> List[str]:
    text = _normalise_spaces(f"{query} {topic}")
    desired: List[str] = []
    for policy in (*FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES, *FINANCIAL_NUMERIC_STATEMENT_HINT_POLICIES):
        markers = tuple(str(item) for item in (policy.get("markers") or ()) if str(item))
        if any(marker in text for marker in markers):
            desired.extend(str(item).strip() for item in (policy.get("statement_types") or ()) if str(item).strip())
    for spec in _matched_ontology_concept_specs(query, topic):
        desired.extend(str(item).strip() for item in (spec.get("preferred_statement_types") or []) if str(item).strip())
        for member_spec in (spec.get("member_specs") or []):
            desired.extend(
                str(item).strip()
                for item in (dict(member_spec).get("preferred_statement_types") or [])
                if str(item).strip()
            )
    return list(dict.fromkeys(desired))


def _infer_statement_and_section_hints(query: str) -> tuple[List[str], List[str]]:
    text = _normalise_spaces(query)
    ontology = get_financial_ontology()
    statement_types = _desired_statement_types(query, query)
    preferred_sections: List[str] = []
    for policy in FINANCIAL_DOCUMENT_STATEMENT_HINT_POLICIES:
        markers = tuple(str(item) for item in (policy.get("markers") or ()) if str(item))
        if not any(marker in text for marker in markers):
            continue
        preferred_sections.extend(str(item).strip() for item in (policy.get("preferred_sections") or ()) if str(item).strip())
        for statement_type in policy.get("statement_types") or ():
            if str(statement_type) not in statement_types:
                statement_types.append(str(statement_type))
    segment_markers = tuple(str(item) for item in (FINANCIAL_SEGMENT_SECTION_HINT_POLICY.get("markers") or ()) if str(item))
    if any(marker in text for marker in segment_markers):
        preferred_sections.extend(
            str(item).strip()
            for item in (FINANCIAL_SEGMENT_SECTION_HINT_POLICY.get("preferred_sections") or ())
            if str(item).strip()
        )
        for statement_type in FINANCIAL_SEGMENT_SECTION_HINT_POLICY.get("statement_types") or ():
            if str(statement_type) not in statement_types:
                statement_types.append(str(statement_type))
    preferred_sections.extend(ontology.preferred_sections(query, query, "comparison"))
    numeric_hint_policies = active_numeric_section_hint_policies(text)
    preferred_sections.extend(numeric_section_policy_preferred_sections(numeric_hint_policies))
    for statement_type in numeric_section_policy_statement_types(numeric_hint_policies):
        if statement_type not in statement_types:
            statement_types.append(statement_type)
    active_policies = active_narrative_policies(text)
    preferred_sections.extend(narrative_policy_preferred_sections(active_policies))
    for statement_type in narrative_policy_terms(active_policies, "statement_types"):
        if statement_type not in statement_types:
            statement_types.append(statement_type)
    return list(dict.fromkeys(statement_types)), list(dict.fromkeys(preferred_sections))


def _preferred_calc_sections(query: str, topic: str, intent: str) -> List[str]:
    if intent not in {"comparison", "trend"}:
        return []
    return get_financial_ontology().preferred_sections(query, topic, intent)


def _supplement_section_terms_for_query(query: str, topic: str, intent: str) -> List[str]:
    sections: List[str] = []
    if intent not in {"comparison", "trend"}:
        return list(dict.fromkeys(sections))
    sections.extend(get_financial_ontology().supplement_sections(query, topic, intent))
    return list(dict.fromkeys(sections))


def _active_preferred_sections(state: Dict[str, Any], query: str, topic: str, intent: str) -> List[str]:
    """Resolve section hints for the active task or top-level query."""
    _statement_types, query_sections = _infer_statement_and_section_hints(query)
    active_sections = [
        str(item).strip()
        for item in (dict(state.get("active_subtask") or {}).get("preferred_sections") or [])
        if str(item).strip()
    ]
    narrative_policies = active_narrative_policies(" ".join(part for part in (query, topic) if part))
    if active_sections:
        query_surface = _normalise_spaces(str(query or "")).lower()
        query_section_hints = [
            section
            for section in query_sections
            if (
                _normalise_spaces(str(section or "")).lower() in query_surface
                or (
                    len(_normalise_spaces(str(section or "")).lower()) >= 4
                    and any(
                        token
                        and len(token) >= 4
                        and token in _normalise_spaces(str(section or "")).lower()
                        for token in re.split(r"\s+|>|/", query_surface)
                    )
                )
            )
        ]
    else:
        query_section_hints = list(query_sections)
    sections = list(query_section_hints)
    sections.extend(active_sections)
    if not active_sections:
        sections.extend(_preferred_calc_sections(query, topic, intent))
    if narrative_policies:
        sections.extend(narrative_policy_preferred_sections(narrative_policies))
    return list(dict.fromkeys(sections))


def _active_preferred_statement_types(state: Dict[str, Any], query: str, topic: str) -> List[str]:
    types = [
        str(item).strip()
        for item in (dict(state.get("active_subtask") or {}).get("preferred_statement_types") or [])
        if str(item).strip()
    ]
    types.extend(_desired_statement_types(query, topic))
    return list(dict.fromkeys(types))


def _retrieval_hint_from_topic(query: str, topic: str, intent: str) -> str:
    hints: List[str] = []
    narrative_policies = active_narrative_policies(" ".join(part for part in (query, topic) if part))
    if narrative_policies:
        hints.extend(narrative_policy_terms(narrative_policies, "retrieval_query_suffixes"))
        hints.extend(narrative_policy_terms(narrative_policies, "focus_terms"))
    if intent in {"comparison", "trend"}:
        hints.extend(get_financial_ontology().query_hints(query, topic, intent))
    return " ".join(dict.fromkeys(hints))
