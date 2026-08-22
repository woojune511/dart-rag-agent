"""Retrieval and statement hint helpers for financial graph runtime."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any, Dict, List

from src.agent.financial_operation_policies import query_requests_narrative_context
from src.agent.financial_runtime_normalization import _normalise_spaces
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    EVIDENCE_COMPRESSION_GUIDANCE_POLICY,
    EVIDENCE_EXTRACTION_POLICY,
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
if TYPE_CHECKING:
    from src.agent.financial_graph_state import FinancialAgentState


def section_hint_alias(section: str) -> str:
    text = _normalise_spaces(section)
    if not text:
        return ""
    if ">" in text:
        text = text.split(">")[-1].strip()
    text = re.sub(r"^\d+\.\s*", "", text)
    return text


def matched_ontology_concept_specs(query: str, topic: str = "") -> List[Dict[str, Any]]:
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
    for spec in matched_ontology_concept_specs(query, topic):
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


def preferred_calc_sections(query: str, topic: str, intent: str) -> List[str]:
    if intent not in {"comparison", "trend"}:
        return []
    return get_financial_ontology().preferred_sections(query, topic, intent)


def supplement_section_terms_for_query(query: str, topic: str, intent: str) -> List[str]:
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
        sections.extend(preferred_calc_sections(query, topic, intent))
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


def retrieval_hint_from_topic(query: str, topic: str, intent: str) -> str:
    hints: List[str] = []
    narrative_policies = active_narrative_policies(" ".join(part for part in (query, topic) if part))
    if narrative_policies:
        hints.extend(narrative_policy_terms(narrative_policies, "retrieval_query_suffixes"))
        hints.extend(narrative_policy_terms(narrative_policies, "focus_terms"))
    if intent in {"comparison", "trend"}:
        hints.extend(get_financial_ontology().query_hints(query, topic, intent))
    return " ".join(dict.fromkeys(hints))


def evidence_extraction_focus_terms(query: str) -> List[str]:
    extraction_policy = dict(EVIDENCE_EXTRACTION_POLICY)
    stopwords = {
        _normalise_spaces(str(item))
        for item in (extraction_policy.get("focus_term_stopwords") or ())
        if _normalise_spaces(str(item))
    }
    max_terms = int(extraction_policy.get("max_focus_terms") or 12)
    token_pattern = str(extraction_policy.get("focus_term_token_pattern") or r"\S+")
    particle_suffix_pattern = str(extraction_policy.get("focus_term_particle_suffix_pattern") or r"$^")
    terms: List[str] = []

    def _add(term: str) -> None:
        cleaned = _normalise_spaces(str(term or "")).strip()
        if not cleaned:
            return
        variants = [cleaned]
        variants.extend(
            _normalise_spaces(match)
            for match in re.findall(r"\(([^)]+)\)", cleaned)
            if _normalise_spaces(match)
        )
        outside_parentheses = _normalise_spaces(re.sub(r"\([^)]*\)", " ", cleaned))
        if outside_parentheses and outside_parentheses != cleaned:
            variants.append(outside_parentheses)
        for variant in variants:
            normalized = _normalise_spaces(variant).strip()
            normalized = re.sub(particle_suffix_pattern, "", normalized)
            if len(normalized) < 2 or normalized in stopwords:
                continue
            if re.fullmatch(r"\d+(?:\.\d+)?", normalized):
                continue
            if normalized not in terms:
                terms.append(normalized)

    for token in re.findall(token_pattern, _normalise_spaces(str(query or ""))):
        _add(token)
        if len(terms) >= max_terms:
            break
    return terms[:max_terms]


def preferred_section_evidence_subset(
    evidence_items: List[Dict[str, Any]],
    state: FinancialAgentState,
) -> List[Dict[str, Any]]:
    """Prefer section-aligned narrative evidence when it is already sufficient."""
    if not evidence_items:
        return []
    active_subtask = dict(state.get("active_subtask") or {})
    operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
    query_type = str(state.get("query_type") or "").strip().lower()
    format_preference = str(
        active_subtask.get("format_preference_override")
        or state.get("format_preference")
        or ""
    ).strip().lower()
    narrative_like = operation_family == "narrative_summary" or query_type in {
        "qa",
        "business_overview",
        "risk",
    }
    if not narrative_like or format_preference == "table":
        return []
    query = str(state.get("query") or "")
    preferred_sections = _active_preferred_sections(
        state,
        query,
        str(state.get("topic") or query),
        str(active_subtask.get("intent_override") or state.get("intent") or state.get("query_type") or "qa"),
    )
    preferred_markers = [str(item).strip().lower() for item in preferred_sections if str(item).strip()]
    if not preferred_markers:
        return []

    def _section_surface(item: Dict[str, Any]) -> str:
        metadata = dict(item.get("metadata") or {})
        return _normalise_spaces(
            " ".join(
                part
                for part in (
                    str(metadata.get("section_path") or ""),
                    str(metadata.get("section") or ""),
                    str(item.get("source_anchor") or ""),
                )
                if part
            )
        ).lower()

    for marker in preferred_markers:
        marker_items = [item for item in evidence_items if marker in _section_surface(item)]
        direct_high_preferred = [
            item
            for item in marker_items
            if str(item.get("question_relevance") or "").strip().lower() == "high"
            and str(item.get("support_level") or "").strip().lower() == "direct"
        ]
        if len(direct_high_preferred) >= 2:
            return marker_items
    return []


def compression_guidance(query_type: str, query: str, coverage: str) -> Dict[str, str]:
    policy = dict(EVIDENCE_COMPRESSION_GUIDANCE_POLICY)
    trend_instruction = str(policy.get("trend_instruction") or "")
    trend_output_style = str(policy.get("trend_output_style") or "")
    if query_requests_narrative_context(query):
        trend_instruction = str(policy.get("trend_context_instruction") or trend_instruction)
        trend_output_style = str(policy.get("trend_context_output_style") or trend_output_style)
    instructions = dict(policy.get("instructions") or {})
    instructions["trend"] = trend_instruction
    output_styles = dict(policy.get("output_styles") or {})
    output_styles["trend"] = trend_output_style
    coverage_notes = dict(policy.get("coverage_notes") or {})

    return {
        "instruction": str(instructions.get(query_type) or instructions.get("qa") or ""),
        "output_style": str(output_styles.get(query_type) or output_styles.get("qa") or ""),
        "coverage_note": str(coverage_notes.get(coverage) or ""),
    }


def query_mentions_metric(query: str, metric: Dict[str, Any]) -> bool:
    combined = _normalise_spaces(query)
    aliases = [str(metric.get("display_name") or "").strip()]
    aliases.extend(metric.get("aliases", []) or [])
    aliases.extend(metric.get("intent_keywords", []) or [])
    return any(_normalise_spaces(alias) in combined for alias in aliases if str(alias).strip())


def query_component_match_count(
    query: str,
    operand_specs: List[Dict[str, Any]],
) -> int:
    combined = _normalise_spaces(query)
    matched_labels: List[str] = []
    for spec in operand_specs:
        label = str(spec.get("label") or "").strip()
        aliases = [label]
        aliases.extend(spec.get("aliases", []) or [])
        aliases.extend(spec.get("keywords", []) or [])
        if any(_normalise_spaces(alias) in combined for alias in aliases if str(alias).strip()):
            matched_labels.append(label or str(spec.get("concept") or "").strip())
    return len(dict.fromkeys(item for item in matched_labels if item))
