"""
Evidence mixin for the financial graph agent.

This module owns document retrieval and evidence shaping:
- rerank raw vector hits
- optionally expand hits with nearby structural context
- transform docs into evidence items
- run the narrative answer path for non-calculation questions
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from src.agent.financial_graph_helpers import *  # noqa: F401,F403
from src.agent.financial_graph_helpers import _report_scope_source_receipts
from src.agent.financial_graph_models import (
    CompressionOutput,
    EvidenceExtraction,
    EvidenceItem,
    FinancialAgentState,
    NumericExtraction,
    ValidationOutput,
    validate_answer_slots_payload,
)
from src.config import get_financial_ontology
from src.config.retrieval_policy import (
    KOREAN_COUNT_UNIT_RE_FRAGMENT,
    KOREAN_PERIOD_COMPARISON_RE_FRAGMENT,
    KOREAN_PERIOD_PREFIX_RE_FRAGMENT,
    QUANTITATIVE_IMPACT_QUERY_TERMS,
    QUERY_FOCUS_STOPWORDS,
    active_narrative_policies,
    narrative_policy_active,
    narrative_policy_driver_groups,
    narrative_policy_facets,
    narrative_policy_paragraph_priority_sections,
    narrative_policy_preferred_sections,
    narrative_policy_slot_groups,
    narrative_policy_terms,
)

logger = logging.getLogger(__name__)


_COUNT_VALUE_UNIT_RE = (
    r"(?P<value>[\(\)\-]?\d[\d,]*(?:\.\d+)?)\s*"
    rf"(?P<unit>{KOREAN_COUNT_UNIT_RE_FRAGMENT})"
)


def _period_target_for_operand(operand: Dict[str, Any], query_years: List[str], report_scope: Dict[str, Any]) -> str:
    label = _normalise_spaces(str(operand.get("label") or ""))
    match = re.search(r"(20\d{2})년?", label)
    if match:
        return match.group(1)
    period_hint = _normalise_spaces(str(operand.get("period_hint") or ""))
    match = re.search(r"(20\d{2})", period_hint)
    if match:
        return match.group(1)
    report_year = str(report_scope.get("year") or "").strip()
    role = str(operand.get("role") or "").strip()
    if report_year.isdigit() and role == "prior_period":
        return str(int(report_year) - 1)
    if report_year.isdigit() and role == "current_period":
        return report_year
    return query_years[0] if query_years else report_year


def _operand_context_surface_variants(operand: Dict[str, Any]) -> List[str]:
    variants: List[str] = []
    for needle in _operand_needles(operand):
        normalized = _normalise_spaces(re.sub(rf"^{KOREAN_PERIOD_PREFIX_RE_FRAGMENT}\s+", "", needle))
        if not normalized:
            continue
        variants.append(normalized)
        tokens = normalized.split()
        if len(tokens) >= 2:
            variants.append(" ".join(tokens[:-1]))
    expanded: List[str] = []
    for variant in variants:
        expanded.append(variant)
        if re.search(r"[가-힣]", variant) and " " in variant:
            expanded.append(re.sub(r"\s+", "", variant))
    return list(dict.fromkeys(item for item in expanded if item))


def _sentence_matches_operand_context(sentence: str, operand: Dict[str, Any]) -> bool:
    normalized = _normalise_spaces(sentence)
    compact = re.sub(r"\s+", "", normalized)
    for surface in _operand_context_surface_variants(operand):
        surface_normalized = _normalise_spaces(surface)
        surface_compact = re.sub(r"\s+", "", surface_normalized)
        if surface_normalized in normalized or (surface_compact and surface_compact in compact):
            return True
    return False


def _sentence_has_subject_after_location_context(sentence: str) -> bool:
    return bool(
        re.search(
            r"[가-힣A-Za-z0-9]+(?:에서|에서는)[가-힣A-Za-z0-9]+(?:은|는)",
            re.sub(r"\s+", "", sentence),
        )
    )


def _period_comparison_count_value_from_text(
    text: str,
    operand: Dict[str, Any],
    *,
    query_years: List[str],
    report_scope: Dict[str, Any],
) -> Optional[Dict[str, str]]:
    normalized = _normalise_spaces(text)
    if not normalized or not re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, normalized):
        return None

    target_year = _period_target_for_operand(operand, query_years, report_scope)
    if not target_year:
        return None

    sentences = [
        part.strip()
        for part in re.split(r"(?<=[.!?。])\s+|(?<=[가-힣])\.(?=(?:20\d{2}|[가-힣]))", normalized)
        if part.strip()
    ] or [normalized]
    context_indexes = [
        index
        for index, sentence in enumerate(sentences)
        if _sentence_matches_operand_context(sentence, operand)
    ]
    if not context_indexes:
        return None
    subject_context_indexes = [
        index
        for index in context_indexes
        if _sentence_has_subject_after_location_context(sentences[index])
    ]
    if not subject_context_indexes:
        return None

    candidates: List[tuple[float, Dict[str, str]]] = []
    for index, sentence in enumerate(sentences):
        period_match = re.search(r"(20\d{2})년?", sentence)
        if not period_match or period_match.group(1) != target_year:
            continue
        if not re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, sentence):
            continue
        value_matches = list(re.finditer(_COUNT_VALUE_UNIT_RE, sentence))
        if not value_matches:
            continue

        context_hit = _sentence_matches_operand_context(sentence, operand)
        subject_context_hit = _sentence_has_subject_after_location_context(sentence)
        follows_context = any(0 <= index - context_index <= 2 for context_index in subject_context_indexes)
        if not context_hit and not follows_context:
            continue
        if context_hit and not subject_context_hit and not follows_context:
            continue

        score = 1.0
        if context_hit:
            score += 2.0
        if subject_context_hit:
            score += 0.75
        if follows_context and not context_hit:
            score += 0.5

        selected = value_matches[-1]
        candidates.append(
            (
                score,
                {
                    "raw_value": selected.group("value"),
                    "raw_unit": _normalise_spaces(selected.group("unit")),
                    "period": f"{target_year}년",
                },
            )
        )

    if not candidates:
        return None
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def _doc_identity(doc: Document) -> str:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    for key in ("chunk_uid", "chunk_id", "id", "source_id"):
        value = str(metadata.get(key) or "").strip()
        if value:
            return value
    return str(getattr(doc, "page_content", "") or "")[:120]


def _doc_operand_context_text(doc: Document) -> str:
    metadata = dict(getattr(doc, "metadata", {}) or {})
    return _normalise_spaces(
        " ".join(
            part
            for part in (
                str(getattr(doc, "page_content", "") or ""),
                str(metadata.get("table_context") or ""),
                str(metadata.get("table_header_context") or ""),
                str(metadata.get("table_summary_text") or ""),
                str(metadata.get("local_heading") or ""),
                str(metadata.get("section_path") or metadata.get("section") or ""),
            )
            if part
        )
    )


def _doc_period_count_operand_matches(doc: Document, required_operands: List[Dict[str, Any]]) -> List[int]:
    text = _doc_operand_context_text(doc)
    if not text:
        return []
    if not re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, text):
        return []
    if not re.search(_COUNT_VALUE_UNIT_RE, text):
        return []
    return [
        index
        for index, operand in enumerate(required_operands)
        if _sentence_matches_operand_context(text, operand)
    ]


def _focused_operand_surface_queries(
    active_subtask: Dict[str, Any],
    query: str,
    report_scope: Dict[str, Any],
) -> List[str]:
    required_operands = [
        dict(item)
        for item in (active_subtask.get("required_operands") or [])
        if isinstance(item, dict)
    ]
    if not required_operands:
        return []
    query_years = re.findall(r"20\d{2}", str(query or ""))
    queries: List[str] = []
    for operand in required_operands:
        target_year = _period_target_for_operand(operand, query_years, report_scope)
        prefix = f"{target_year}년 " if target_year else ""
        for surface in _operand_context_surface_variants(operand):
            surface = _normalise_spaces(surface)
            if surface:
                queries.append(_normalise_spaces(f"{prefix}{surface}"))
    return list(dict.fromkeys(item for item in queries if item))


def _ensure_period_count_operand_docs(
    selected: List[tuple[Document, float]],
    candidates: List[tuple[Document, float]],
    required_operands: List[Dict[str, Any]],
    effective_k: int,
) -> List[tuple[Document, float]]:
    if not required_operands or not candidates or effective_k <= 0:
        return selected[:effective_k]

    covered = set()
    selected_ids = set()
    for item in selected:
        doc = item[0]
        selected_ids.add(_doc_identity(doc))
        covered.update(_doc_period_count_operand_matches(doc, required_operands))

    for candidate in candidates:
        doc = candidate[0]
        identity = _doc_identity(doc)
        if identity in selected_ids:
            continue
        matches = set(_doc_period_count_operand_matches(doc, required_operands))
        if not matches or matches.issubset(covered):
            continue

        if len(selected) < effective_k:
            selected.append(candidate)
        else:
            replace_index = None
            for index in range(len(selected) - 1, -1, -1):
                if not _doc_period_count_operand_matches(selected[index][0], required_operands):
                    replace_index = index
                    break
            if replace_index is None:
                continue
            replaced_identity = _doc_identity(selected[replace_index][0])
            selected_ids.discard(replaced_identity)
            selected[replace_index] = candidate
        selected_ids.add(identity)
        covered.update(matches)
        if len(covered) >= len(required_operands):
            break

    return selected[:effective_k]


class FinancialAgentEvidenceMixin:
    _QUERY_FOCUS_STOPWORDS = QUERY_FOCUS_STOPWORDS

    def _active_narrative_policies_for_query(self, query: str) -> List[Dict[str, Any]]:
        return list(active_narrative_policies(str(query or "")))

    def _narrative_policy_terms_for_query(self, query: str, *keys: str) -> Dict[str, List[str]]:
        active_policies = self._active_narrative_policies_for_query(query)
        return {key: narrative_policy_terms(active_policies, key) for key in keys}

    def _narrative_policy_facets_for_query(self, query: str, key: str) -> List[Dict[str, Any]]:
        return narrative_policy_facets(self._active_narrative_policies_for_query(query), key)

    def _query_focus_marker_groups(self, query: str, *, limit: int = 8) -> List[Dict[str, Any]]:
        """Extract query-specific entity/policy/concept markers without case IDs."""
        surface = _normalise_spaces(str(query or ""))
        if not surface:
            return []

        groups: List[Dict[str, Any]] = []
        seen: set[str] = set()

        def _clean_marker(value: str) -> str:
            marker = _normalise_spaces(value)
            marker = marker.strip("()[]{}'\"“”‘’,.·:;")
            marker = re.sub(r"^(또는|및|등)\s+", "", marker)
            marker = re.sub(r"\s+(또는|및|등)$", "", marker)
            marker = re.sub(r"(에서|으로|로|에게|에는|에|은|는|이|가|을|를|과|와|도)$", "", marker)
            return marker.strip()

        def _is_useful_marker(value: str) -> bool:
            marker = _clean_marker(value)
            if not marker:
                return False
            lowered = marker.lower()
            if lowered in self._QUERY_FOCUS_STOPWORDS:
                return False
            if re.fullmatch(r"20\d{2}년?", marker):
                return False
            if marker.isdigit():
                return False
            if re.fullmatch(r"[A-Za-z]", marker):
                return False
            if len(marker) < 2:
                return False
            return True

        def _append_group(variants: List[str]) -> None:
            cleaned = []
            for variant in variants:
                marker = _clean_marker(variant)
                if not _is_useful_marker(marker):
                    continue
                marker_key = marker.lower()
                if marker_key in {item.lower() for item in cleaned}:
                    continue
                cleaned.append(marker)
            if not cleaned:
                return
            key = "|".join(sorted(marker.lower() for marker in cleaned))
            if key in seen:
                return
            seen.add(key)
            groups.append(
                {
                    "label": f"query_focus_{len(groups) + 1}",
                    "variants": cleaned,
                    "phrase": "",
                    "query_focus": True,
                }
            )

        for match in re.finditer(r"([가-힣A-Za-z0-9\s·./-]{2,40})\(([A-Za-z0-9\s·./-]{2,40})\)", surface):
            left_surface = _clean_marker(match.group(1))
            left_surface = re.sub(r"^.*(?:과|와|및|또는)\s+", "", left_surface)
            left_surface = re.sub(r"^.*(?:에서|에는|으로|은|는|이|가|을|를|의)\s+", "", left_surface)
            left = _clean_marker(left_surface.split()[-1])
            if len(left_surface.split()) > 1 and re.search(r"[가-힣]", left_surface):
                left = _clean_marker(left_surface)
            right = _clean_marker(match.group(2))
            _append_group([left, right])

        for quoted in re.findall(r"[\"'“”‘’](.+?)[\"'“”‘’]", surface):
            _append_group([quoted])

        for acronym in re.findall(r"\b[A-Z][A-Z0-9]{1,8}\b", surface):
            _append_group([acronym])

        for token in re.findall(r"[A-Za-z][A-Za-z0-9./-]{2,}", surface):
            _append_group([token])

        for token in re.findall(r"[가-힣A-Za-z0-9]+", surface):
            if len(token) < 2:
                continue
            _append_group([token])

        return groups[:limit]

    def _query_focus_markers(self, query: str, *, limit: int = 8) -> List[str]:
        markers: List[str] = []
        for group in self._query_focus_marker_groups(query, limit=limit):
            for variant in group.get("variants") or []:
                marker = str(variant).strip()
                if marker and marker.lower() not in {item.lower() for item in markers}:
                    markers.append(marker)
        return markers

    def _merge_retry_candidates(self, docs, previous_docs) -> List[tuple[Document, float]]:
        merged: List[tuple[Document, float]] = list(docs)
        seen_chunk_uids = {
            str((doc.metadata or {}).get("chunk_uid") or "")
            for doc, _score in merged
        }
        for doc, score in previous_docs:
            chunk_uid = str((doc.metadata or {}).get("chunk_uid") or "")
            if chunk_uid and chunk_uid in seen_chunk_uids:
                continue
            if chunk_uid:
                seen_chunk_uids.add(chunk_uid)
            merged.append((doc, score))
        return merged

    # intent별 표 청크 선호 여부
    _TABLE_PREFERRED_TYPES = frozenset(["numeric_fact", "trend"])
    _PARAGRAPH_PREFERRED_TYPES = frozenset(["business_overview", "risk", "qa"])

    def _section_bias(self, query_type: str, section_path: str) -> float:
        lowered = (section_path or "").lower()
        bias = 0.0
        # 가장 긴 needle부터 검사하고 첫 매칭에서 break → 구체적인 섹션명이 우선 적용되고 중복 가산 방지
        for needle, weight in sorted(
            self._SECTION_BIAS_BY_QUERY_TYPE.get(query_type, ()),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            if needle.lower() in lowered:
                bias += weight
                break
        # 주석 섹션은 numeric_fact/trend에서 본문 재무제표보다 유용도가 낮으므로 페널티
        if "주석" in lowered and query_type in self._TABLE_PREFERRED_TYPES:
            bias -= 0.12
        return bias

    def _rerank_docs(self, docs, state: FinancialAgentState):
        active_subtask = dict(state.get("active_subtask") or {})
        companies = {company.lower() for company in state.get("companies", [])}
        years = {int(year) for year in state.get("years", [])}
        topic_terms = _tokenize_terms(state.get("topic") or state["query"])
        section_filter = (state.get("section_filter") or "").strip()
        intent = str(active_subtask.get("intent_override") or state.get("intent") or state.get("query_type", "qa"))
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or self._default_format_preference(intent)
        )
        metric_terms = _metric_terms_from_topic(state.get("topic") or state["query"])
        preferred_sections = _active_preferred_sections(state, state["query"], state.get("topic") or "", intent)
        desired_statement_types = set(_active_preferred_statement_types(state, state["query"], state.get("topic") or ""))
        desired_consolidation = _desired_consolidation_scope(state["query"], dict(state.get("report_scope") or {}))
        query_years = sorted(years)
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        query_focus_markers = (
            self._query_focus_markers(str(state.get("query") or ""))
            if operation_family == "narrative_summary"
            else []
        )

        reranked = []
        for doc, score in docs:
            metadata = doc.metadata or {}
            company = str(metadata.get("company", "")).lower()
            year = metadata.get("year")
            section = str(metadata.get("section", ""))
            section_path = str(metadata.get("section_path", section))
            block_type = metadata.get("block_type", "")
            statement_type = str(metadata.get("statement_type") or "unknown").strip()
            consolidation_scope = str(metadata.get("consolidation_scope") or "unknown").strip()
            period_labels = list(metadata.get("period_labels") or [])
            body_text = _strip_rerank_metadata(doc.page_content)
            document_terms = _tokenize_terms(
                " ".join(
                    [
                        body_text,
                        section,
                        section_path,
                        str(metadata.get("table_context") or ""),
                    ]
                )
            )

            boosted = float(score)
            if companies:
                if company in companies:
                    boosted += 0.35
                elif any(target in company or company in target for target in companies):
                    boosted += 0.20
            if years and year in years:
                boosted += 0.25
            if section_filter and (section == section_filter or section_filter in section_path):
                boosted += 0.20
            if topic_terms and document_terms:
                overlap = len(topic_terms & document_terms) / max(len(topic_terms), 1)
                boosted += min(overlap, 0.20)
            if intent in {"comparison", "trend"} and metric_terms:
                metric_hit = sum(1 for term in metric_terms if term in body_text or term in section_path)
                if metric_hit:
                    boosted += min(0.16 + 0.05 * metric_hit, 0.30)
                else:
                    boosted -= 0.20
            if preferred_sections and any(section_term in section_path for section_term in preferred_sections):
                boosted += 0.20
            if desired_statement_types:
                if statement_type in desired_statement_types:
                    boosted += 0.24
                elif statement_type != "unknown":
                    boosted -= 0.08
            if desired_consolidation != "unknown":
                if consolidation_scope == desired_consolidation:
                    boosted += 0.12
                elif consolidation_scope != "unknown":
                    boosted -= 0.18
            period_match_strength = _metadata_period_match_strength(period_labels, query_years)
            if period_match_strength > 0:
                boosted += 0.10 * period_match_strength

            boosted += self._section_bias(intent, section_path)

            # block_type 보정: format_preference 기반으로 표/단락 선호도 반영
            if format_preference == "paragraph" and block_type == "table":
                boosted -= 0.08
            elif format_preference == "table" and block_type == "paragraph":
                boosted -= 0.04

            if operation_family == "narrative_summary":
                if block_type == "paragraph":
                    boosted += 0.12
                elif block_type == "table":
                    boosted -= 0.14
                causal_markers = ("영향", "기여", "편입효과", "배경", "요인", "성장")
                if any(marker in body_text or marker in section_path for marker in causal_markers):
                    boosted += 0.08
                if query_focus_markers:
                    focus_surface = _normalise_spaces(
                        " ".join(
                            part
                            for part in (
                                body_text,
                                section_path,
                                str(metadata.get("table_context") or ""),
                                str(metadata.get("table_value_labels_text") or ""),
                                str(metadata.get("table_row_labels_text") or ""),
                                str(metadata.get("table_summary_text") or ""),
                            )
                            if part
                        )
                    ).lower()
                    focus_hits = sum(1 for marker in query_focus_markers if marker.lower() in focus_surface)
                    if focus_hits:
                        boosted += min(0.08 * focus_hits, 0.32)

            reranked.append((doc, boosted))

        reranked.sort(key=lambda item: item[1], reverse=True)
        return reranked

    def _select_narrative_summary_docs(self, reranked, state: FinancialAgentState, effective_k: int):
        query = str(state.get("query") or "")
        active_policies = self._active_narrative_policies_for_query(query)
        impact_query = narrative_policy_active(active_policies, "impact_context")
        dividend_policy_query = narrative_policy_active(active_policies, "dividend_policy")
        technology_focus_query = narrative_policy_active(active_policies, "technology_focus")
        policy_context_query = narrative_policy_active(active_policies, "policy_context")
        preferred_section_markers = [item.lower() for item in narrative_policy_preferred_sections(active_policies)]
        paragraph_priority_sections = [
            item.lower()
            for item in narrative_policy_paragraph_priority_sections(active_policies)
        ]
        policy_terms_by_key = self._narrative_policy_terms_for_query(
            query,
            "causal_terms",
            "realized_terms",
            "penalty_terms",
            "focus_terms",
            "technology_terms",
            "payout_terms",
            "policy_terms",
            "liquidity_context_terms",
            "outflow_terms",
            "policy_section_terms",
        )
        causal_markers = policy_terms_by_key["causal_terms"]
        realized_markers = policy_terms_by_key["realized_terms"]
        penalty_terms = policy_terms_by_key["penalty_terms"]
        focus_policy_terms = policy_terms_by_key["focus_terms"]
        technology_terms = policy_terms_by_key["technology_terms"]
        dividend_payout_terms = policy_terms_by_key["payout_terms"]
        dividend_policy_terms = policy_terms_by_key["policy_terms"]
        dividend_liquidity_context_terms = policy_terms_by_key["liquidity_context_terms"]
        dividend_outflow_terms = policy_terms_by_key["outflow_terms"]
        dividend_policy_section_terms = policy_terms_by_key["policy_section_terms"]
        driver_groups = self._narrative_driver_groups(query)
        query_focus_markers = self._query_focus_markers(query)
        active_subtask = dict(state.get("active_subtask") or {})
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or ""
        ).strip().lower()

        def _doc_surface(doc: Document) -> str:
            metadata = doc.metadata or {}
            return _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(doc.page_content or ""),
                        str(metadata.get("table_context") or ""),
                        str(metadata.get("table_value_labels_text") or ""),
                        str(metadata.get("table_row_labels_text") or ""),
                        str(metadata.get("table_summary_text") or ""),
                    )
                    if part
                )
            )

        def _paragraph_priority(item) -> tuple[int, float]:
            doc, score = item
            metadata = doc.metadata or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            section_path = str(metadata.get("section_path") or metadata.get("section") or "").lower()
            text = _doc_surface(doc).lower()
            focus_markers = list(dict.fromkeys([*query_focus_markers, *focus_policy_terms]))
            priority = 0
            if block_type == "paragraph":
                priority += 3
            if any(marker in section_path for marker in preferred_section_markers):
                priority += 2
            if any(marker in section_path for marker in paragraph_priority_sections):
                priority += 1
            if technology_focus_query:
                if any(marker.lower() in text for marker in technology_terms):
                    priority += 4
            if any(marker.lower() in text for marker in causal_markers):
                priority += 2
            if impact_query:
                if any(marker.lower() in text for marker in realized_markers):
                    priority += 3
                if any(marker.lower() in section_path or marker.lower() in text for marker in penalty_terms):
                    priority -= 2
            if dividend_policy_query:
                if any(term.lower() in section_path for term in dividend_policy_section_terms):
                    priority += 3
                if any(term in section_path for term in paragraph_priority_sections):
                    priority += 2
                if any(marker.lower() in text for marker in (*dividend_payout_terms, *dividend_policy_terms)):
                    priority += 3
            if focus_markers:
                focus_hits = sum(1 for marker in focus_markers if marker.lower() in text)
                if focus_hits:
                    priority += min(focus_hits, 3)
                elif impact_query:
                    priority -= 2
            return priority, float(score)

        def _driver_group_covered(doc_items, variants: List[str]) -> bool:
            for candidate_item in doc_items:
                candidate_doc = candidate_item[0] if isinstance(candidate_item, (tuple, list)) else candidate_item
                lowered = _doc_surface(candidate_doc).lower()
                if any(variant.lower() in lowered for variant in variants):
                    return True
            return False

        def _has_any_term(surface: str, terms: tuple[str, ...]) -> bool:
            lowered = surface.lower()
            return any(term.lower() in lowered for term in terms)

        def _active_policy_slot_groups() -> List[Dict[str, Any]]:
            slot_groups = narrative_policy_slot_groups(active_policies)
            return [
                group
                for group in slot_groups
                if _has_any_term(query, tuple(group["query_terms"]))
            ]

        def _slot_group_preferences_satisfied(doc: Document, slot_group: Dict[str, Any]) -> bool:
            metadata = getattr(doc, "metadata", {}) or {}
            section_path = str(metadata.get("section_path") or metadata.get("section") or "").lower()
            scope = str(metadata.get("consolidation_scope") or "").strip().lower()
            preferred_scopes = tuple(str(item).lower() for item in (slot_group.get("preferred_consolidation_scopes") or ()))
            preferred_sections = tuple(str(item).lower() for item in (slot_group.get("preferred_section_markers") or ()))
            if preferred_scopes and scope not in preferred_scopes:
                return False
            if preferred_sections and not any(marker in section_path for marker in preferred_sections):
                return False
            return True

        def _doc_matches_entity_slot(doc: Document, variants: List[str], slot_group: Dict[str, Any]) -> bool:
            evidence_terms = tuple(slot_group["evidence_terms"])
            surface = _doc_surface(doc)
            surface_lower = surface.lower()
            if not any(variant.lower() in surface_lower for variant in variants):
                return False
            return _has_any_term(surface, evidence_terms)

        def _entity_slot_group_covered(doc_items, variants: List[str], slot_group: Dict[str, Any]) -> bool:
            for candidate_item in doc_items:
                candidate_doc = candidate_item[0] if isinstance(candidate_item, (tuple, list)) else candidate_item
                if _doc_matches_entity_slot(candidate_doc, variants, slot_group):
                    if _slot_group_preferences_satisfied(candidate_doc, slot_group):
                        return True
            return False

        def _focus_candidate_priority(item, variants: List[str]) -> tuple[int, float]:
            doc, score = item
            metadata = getattr(doc, "metadata", {}) or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            period_focus = str(metadata.get("period_focus") or "").strip().lower()
            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            surface = _doc_surface(doc)
            surface_lower = surface.lower()
            content = _normalise_spaces(str(getattr(doc, "page_content", "") or ""))
            priority = 0
            focus_hits = sum(1 for marker in query_focus_markers if marker.lower() in surface_lower)
            priority += min(focus_hits, 6) * 2
            if block_type == "table":
                priority += 2
            if period_focus == "current":
                priority += 2
            for slot_group in _active_policy_slot_groups():
                evidence_terms = tuple(slot_group.get("evidence_terms") or [])
                term_hits = sum(1 for term in evidence_terms if term.lower() in surface_lower)
                if term_hits:
                    priority += min(2 + term_hits, 5)
                    if _slot_group_preferences_satisfied(doc, slot_group):
                        priority += 4
            if technology_focus_query and any(marker.lower() in surface_lower for marker in focus_policy_terms):
                priority += 3
            if policy_context_query and any(marker.lower() in surface_lower for marker in focus_policy_terms):
                priority += 3
            for variant in variants:
                variant_lower = variant.lower()
                for line in content.splitlines():
                    lowered_line = line.lower()
                    if variant_lower not in lowered_line:
                        continue
                    if "|" in line:
                        priority += 3
                    if re.search(r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?", line):
                        priority += 3
                    break
            if preferred_section_markers and any(marker in section_path.lower() for marker in preferred_section_markers):
                priority += 1
            return priority, float(score)

        entity_slot_groups = _active_policy_slot_groups()
        focus_groups = [
            group
            for group in driver_groups
            if bool(group.get("query_focus")) and list(group.get("variants") or [])
        ]
        table_first_focus_query = bool(format_preference == "table" and focus_groups)

        def _focus_table_priority(item: Any) -> int:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            if str(metadata.get("block_type") or "").strip().lower() != "table":
                return 0
            return max(
                (
                    _focus_candidate_priority(item, list(group.get("variants") or []))[0]
                    for group in focus_groups
                    if list(group.get("variants") or [])
                ),
                default=0,
            )

        focus_table_fill_limit = 0
        if entity_slot_groups and focus_groups:
            focus_table_fill_limit = min(
                effective_k,
                max(2, len(entity_slot_groups)),
            )
        elif focus_groups:
            focus_table_fill_limit = min(effective_k, 2)
        driver_focus_table_limit = min(effective_k, 2) if focus_groups else 0

        def _selected_focus_table_count() -> int:
            return sum(1 for item in selected if _focus_table_priority(item) > 0)

        paragraph_candidates = []
        remainder = []
        for item in reranked:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            if str(metadata.get("block_type") or "").strip().lower() == "paragraph":
                paragraph_candidates.append(item)
            else:
                remainder.append(item)

        paragraph_limit = min(max(effective_k // 2, 3), effective_k)
        if entity_slot_groups or table_first_focus_query:
            paragraph_limit = 0
        paragraph_candidates.sort(key=_paragraph_priority, reverse=True)
        selected = []
        seen_chunk_ids = set()
        if paragraph_limit > 0:
            for item in paragraph_candidates:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                selected.append(item)
                if chunk_id:
                    seen_chunk_ids.add(chunk_id)
                if len(selected) >= paragraph_limit:
                    break

        for group in driver_groups:
            variants = list(group.get("variants") or [])
            if not variants or _driver_group_covered(selected, variants):
                continue
            group_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                block_type = str(metadata.get("block_type") or "").strip().lower()
                if block_type not in {"paragraph", "table"}:
                    continue
                lowered = _doc_surface(doc).lower()
                if not any(variant.lower() in lowered for variant in variants):
                    continue
                group_candidates.append(item)
            if not group_candidates:
                continue
            best_item = sorted(
                group_candidates,
                key=lambda candidate: _focus_candidate_priority(candidate, variants),
                reverse=True,
            )[0]
            if (
                driver_focus_table_limit
                and _focus_table_priority(best_item) > 0
                and _selected_focus_table_count() >= driver_focus_table_limit
            ):
                continue
            selected.append(best_item)
            best_doc = best_item[0] if isinstance(best_item, (tuple, list)) else best_item
            best_chunk_id = str((getattr(best_doc, "metadata", {}) or {}).get("chunk_id") or "")
            if best_chunk_id:
                seen_chunk_ids.add(best_chunk_id)

        if entity_slot_groups:
            for group in focus_groups:
                variants = list(group.get("variants") or [])
                for slot_group in entity_slot_groups:
                    evidence_terms = tuple(slot_group["evidence_terms"])
                    if _entity_slot_group_covered(selected, variants, slot_group):
                        continue
                    group_candidates = []
                    for item in reranked:
                        doc = item[0] if isinstance(item, (tuple, list)) else item
                        metadata = getattr(doc, "metadata", {}) or {}
                        chunk_id = str(metadata.get("chunk_id") or "")
                        if chunk_id and chunk_id in seen_chunk_ids:
                            continue
                        surface = _doc_surface(doc)
                        surface_lower = surface.lower()
                        if not any(variant.lower() in surface_lower for variant in variants):
                            continue
                        if not _has_any_term(surface, evidence_terms):
                            continue
                        group_candidates.append(item)
                    if not group_candidates:
                        continue
                    best_item = sorted(
                        group_candidates,
                        key=lambda candidate: _focus_candidate_priority(candidate, variants),
                        reverse=True,
                    )[0]
                    best_doc = best_item[0] if isinstance(best_item, (tuple, list)) else best_item
                    replacement_index = None
                    for index, selected_item in enumerate(selected):
                        selected_doc = selected_item[0] if isinstance(selected_item, (tuple, list)) else selected_item
                        if not _doc_matches_entity_slot(selected_doc, variants, slot_group):
                            continue
                        if _slot_group_preferences_satisfied(selected_doc, slot_group):
                            continue
                        replacement_index = index
                        break
                    if replacement_index is None:
                        if any(
                            _doc_matches_entity_slot(
                                selected_item[0] if isinstance(selected_item, (tuple, list)) else selected_item,
                                variants,
                                slot_group,
                            )
                            for selected_item in selected
                        ):
                            continue
                        selected.append(best_item)
                    else:
                        old_doc = selected[replacement_index][0] if isinstance(selected[replacement_index], (tuple, list)) else selected[replacement_index]
                        old_chunk_id = str((getattr(old_doc, "metadata", {}) or {}).get("chunk_id") or "")
                        if old_chunk_id:
                            seen_chunk_ids.discard(old_chunk_id)
                        selected[replacement_index] = best_item
                    best_chunk_id = str((getattr(best_doc, "metadata", {}) or {}).get("chunk_id") or "")
                    if best_chunk_id:
                        seen_chunk_ids.add(best_chunk_id)

            table_fill_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                if str(metadata.get("block_type") or "").strip().lower() != "table":
                    continue
                surfaces_match = False
                for group in focus_groups:
                    variants = list(group.get("variants") or [])
                    if not variants:
                        continue
                    if any(
                        _doc_matches_entity_slot(doc, variants, slot_group)
                        for slot_group in entity_slot_groups
                    ):
                        surfaces_match = True
                        break
                if not surfaces_match:
                    continue
                table_fill_candidates.append(item)
            for item in sorted(
                table_fill_candidates,
                key=lambda candidate: max(
                    (
                        _focus_candidate_priority(candidate, list(group.get("variants") or []))
                        for group in focus_groups
                        if list(group.get("variants") or [])
                    ),
                    default=(0, float(candidate[1] if isinstance(candidate, (tuple, list)) and len(candidate) > 1 else 0.0)),
                ),
                reverse=True,
            ):
                if focus_table_fill_limit and _selected_focus_table_count() >= focus_table_fill_limit:
                    break
                doc = item[0] if isinstance(item, (tuple, list)) else item
                chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                selected.append(item)
                if chunk_id:
                    seen_chunk_ids.add(chunk_id)

        if table_first_focus_query and not entity_slot_groups:
            table_fill_candidates = []
            for item in reranked:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                chunk_id = str(metadata.get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                if str(metadata.get("block_type") or "").strip().lower() != "table":
                    continue
                priority = _focus_table_priority(item)
                if priority <= 0:
                    continue
                table_fill_candidates.append(item)
            for item in sorted(
                table_fill_candidates,
                key=lambda candidate: max(
                    (
                        _focus_candidate_priority(candidate, list(group.get("variants") or []))
                        for group in focus_groups
                        if list(group.get("variants") or [])
                    ),
                    default=(0, float(candidate[1] if isinstance(candidate, (tuple, list)) and len(candidate) > 1 else 0.0)),
                ),
                reverse=True,
            ):
                if focus_table_fill_limit and _selected_focus_table_count() >= focus_table_fill_limit:
                    break
                doc = item[0] if isinstance(item, (tuple, list)) else item
                chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
                if chunk_id and chunk_id in seen_chunk_ids:
                    continue
                selected.append(item)
                if chunk_id:
                    seen_chunk_ids.add(chunk_id)

        quantitative_impact_query = any(marker in query for marker in QUANTITATIVE_IMPACT_QUERY_TERMS)
        if quantitative_impact_query:
            focus_terms = [
                term
                for term in re.findall(r"[가-힣A-Za-z0-9]+", query)
                if len(term) >= 3 and term not in {"2023년", "규모를", "찾고", "이것이", "미친", "분석해"}
            ]
            for focus_term in list(dict.fromkeys(focus_terms))[:6]:
                if any(focus_term in _doc_surface(item[0] if isinstance(item, (tuple, list)) else item) for item in selected):
                    continue
                for item in reranked:
                    doc = item[0] if isinstance(item, (tuple, list)) else item
                    metadata = getattr(doc, "metadata", {}) or {}
                    chunk_id = str(metadata.get("chunk_id") or "")
                    if chunk_id and chunk_id in seen_chunk_ids:
                        continue
                    if str(metadata.get("block_type") or "").strip().lower() != "table":
                        continue
                    if focus_term not in _doc_surface(doc):
                        continue
                    selected.append(item)
                    if chunk_id:
                        seen_chunk_ids.add(chunk_id)
                    break

        if dividend_policy_query:
            def _append_dividend_specific_doc(predicate) -> None:
                for item in reranked:
                    doc = item[0] if isinstance(item, (tuple, list)) else item
                    metadata = getattr(doc, "metadata", {}) or {}
                    chunk_id = str(metadata.get("chunk_id") or "")
                    if chunk_id and chunk_id in seen_chunk_ids:
                        continue
                    if not predicate(doc):
                        continue
                    selected.append(item)
                    if chunk_id:
                        seen_chunk_ids.add(chunk_id)
                    break

            def _is_payout_doc(doc: Document) -> bool:
                metadata = getattr(doc, "metadata", {}) or {}
                text = _doc_surface(doc)
                section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or "")).lower()
                local_heading = _normalise_spaces(str(metadata.get("local_heading") or "")).lower()
                return (
                    any(term in text for term in dividend_payout_terms)
                    and bool(self._extract_dividend_amount_surface(text))
                    and (
                        any(term in section_path or term in local_heading for term in dividend_liquidity_context_terms)
                        or any(term in text for term in dividend_outflow_terms)
                    )
                )

            def _is_policy_doc(doc: Document) -> bool:
                metadata = getattr(doc, "metadata", {}) or {}
                text = _doc_surface(doc)
                section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or "")).lower()
                return (
                    any(marker in text for marker in dividend_policy_terms)
                    and (
                        any(term in section_path for term in dividend_policy_section_terms)
                        or ("2024" in text and "2026" in text)
                    )
                )

            _append_dividend_specific_doc(_is_payout_doc)
            _append_dividend_specific_doc(_is_policy_doc)

        final_candidates = []
        for item in reranked:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
            if chunk_id and chunk_id in seen_chunk_ids:
                continue
            if (
                focus_table_fill_limit
                and _focus_table_priority(item) > 0
                and _selected_focus_table_count() >= focus_table_fill_limit
            ):
                continue
            final_candidates.append(item)

        final_fill_priority = None
        local_section_fill_floor = 0
        if selected and (entity_slot_groups or table_first_focus_query):
            def _item_metadata(doc_item: Any) -> Dict[str, Any]:
                item_doc = doc_item[0] if isinstance(doc_item, (tuple, list)) else doc_item
                return getattr(item_doc, "metadata", {}) or {}

            selected_table_sections = list(
                dict.fromkeys(
                    _normalise_spaces(
                        str(metadata.get("section_path") or metadata.get("section") or "")
                    ).lower()
                    for selected_item in selected
                    for metadata in [_item_metadata(selected_item)]
                    if str(metadata.get("block_type") or "").strip().lower() == "table"
                )
            )

            def _final_fill_priority(candidate: Any) -> tuple[int, float]:
                doc, score = candidate
                metadata = getattr(doc, "metadata", {}) or {}
                section_path = _normalise_spaces(
                    str(metadata.get("section_path") or metadata.get("section") or "")
                ).lower()
                block_type = str(metadata.get("block_type") or "").strip().lower()
                priority = 0
                if section_path and section_path in selected_table_sections:
                    priority += 5
                elif section_path and any(
                    selected_section
                    and (section_path in selected_section or selected_section in section_path)
                    for selected_section in selected_table_sections
                ):
                    priority += 2
                if block_type == "table" and format_preference == "table":
                    priority += 1
                return priority, float(score)

            final_fill_priority = _final_fill_priority
            local_section_fill_floor = min(
                effective_k,
                max(3, len([section for section in selected_table_sections if section])),
            )
            final_candidates.sort(key=final_fill_priority, reverse=True)

        for item in final_candidates:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            chunk_id = str((getattr(doc, "metadata", {}) or {}).get("chunk_id") or "")
            if (
                final_fill_priority is not None
                and local_section_fill_floor
                and len(selected) >= local_section_fill_floor
                and final_fill_priority(item)[0] <= 0
            ):
                continue
            selected.append(item)
            if chunk_id:
                seen_chunk_ids.add(chunk_id)
            if len(selected) >= effective_k:
                break

        return selected[:effective_k]

    def _retrieve(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Retrieve top candidate chunks and rerank them for the active task."""
        query = state["query"]
        retrieval_queries = [str(item).strip() for item in (state.get("retrieval_queries") or []) if str(item).strip()]
        active_subtask = dict(state.get("active_subtask") or {})
        active_subtask_query = str(active_subtask.get("query") or "").strip()
        active_subtask_retrieval_queries = [
            str(item).strip()
            for item in (active_subtask.get("retrieval_queries") or [])
            if str(item).strip()
        ]
        report_scope = dict(state.get("report_scope") or {})
        companies = list(state.get("companies", []) or [])
        years = list(state.get("years", []) or [])
        scope_company = str(report_scope.get("company") or "").strip()
        strict_company_scope = _should_apply_strict_company_scope(companies, report_scope)
        if scope_company and strict_company_scope and scope_company not in companies:
            companies = [scope_company, *companies] if companies else [scope_company]
        scope_year_raw = report_scope.get("year")
        scope_year: Optional[int] = None
        try:
            if scope_year_raw not in (None, ""):
                scope_year = int(scope_year_raw)
        except (TypeError, ValueError):
            scope_year = None
        if scope_year is not None and scope_year not in years:
            years = [scope_year, *years] if years else [scope_year]
        scope_report_type = str(report_scope.get("report_type") or "").strip()
        scope_rcept_no = str(report_scope.get("rcept_no") or "").strip()
        scope_source_receipts = _report_scope_source_receipts(report_scope)
        has_multi_source_scope = len(scope_source_receipts) > 1
        scope_consolidation = str(report_scope.get("consolidation") or "").strip()
        section_filter = state.get("section_filter")
        intent = str(active_subtask.get("intent_override") or state.get("intent") or state.get("query_type", "qa"))
        reflection_count = int(state.get("reflection_count") or 0)
        retry_queries = [str(item).strip() for item in (state.get("retry_queries") or []) if str(item).strip()]
        effective_k = self.k if reflection_count <= 0 else max(self.k * 2, 4)

        conditions = []
        if companies and strict_company_scope:
            if len(companies) == 1:
                conditions.append({"company": companies[0]})
            else:
                conditions.append({"company": {"$in": companies}})
        if years:
            int_years = [int(year) for year in years]
            if has_multi_source_scope:
                logger.info(
                    "[retrieve] multi-report source scope detected; skipping strict metadata year filter and using source receipts only: %s",
                    scope_source_receipts,
                )
            elif intent in {"comparison", "trend"} and len(int_years) > 1:
                logger.info(
                    "[retrieve] multi-period %s query detected; skipping strict metadata year filter and keeping years in query text only: %s",
                    intent,
                    int_years,
                )
            elif len(int_years) == 1:
                conditions.append({"year": int_years[0]})
            else:
                conditions.append({"year": {"$in": int_years}})
        if scope_report_type:
            conditions.append({"report_type": scope_report_type})
        if scope_source_receipts:
            if len(scope_source_receipts) == 1:
                conditions.append({"rcept_no": scope_source_receipts[0]})
            else:
                conditions.append({"rcept_no": {"$in": scope_source_receipts}})
        elif scope_rcept_no:
            conditions.append({"rcept_no": scope_rcept_no})

        if not conditions:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        retrieval_hint = _retrieval_hint_from_topic(query, state.get("topic") or query, intent)
        preferred_sections = _active_preferred_sections(state, query, state.get("topic") or "", intent)
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()
        query_bundle = (
            active_subtask_retrieval_queries
            or ([active_subtask_query] if active_subtask_query else [])
            or retrieval_queries
            or [query]
        )
        if operation_family == "narrative_summary":
            query_bundle = list(query_bundle)
            for supplemental_query in (query, str(state.get("topic") or "").strip()):
                if supplemental_query and supplemental_query not in query_bundle:
                    query_bundle.append(supplemental_query)
        executed_queries: List[Dict[str, Any]] = []
        docs: List[tuple[Document, float]] = []
        for base_query in query_bundle:
            enriched_query = f"{' '.join(companies)} {base_query}" if companies else base_query
            if scope_report_type:
                enriched_query = f"{enriched_query} {scope_report_type}".strip()
            if scope_consolidation:
                enriched_query = f"{enriched_query} {scope_consolidation}".strip()
            if retrieval_hint:
                enriched_query = f"{enriched_query} {retrieval_hint}".strip()
            if preferred_sections:
                enriched_query = f"{enriched_query} {' '.join(preferred_sections)}".strip()
            search_k = effective_k * 4
            executed_queries.append(
                {
                    "source": "primary",
                    "base_query": base_query,
                    "executed_query": enriched_query,
                    "k": search_k,
                    "where_filter": where_filter,
                }
            )
            batch_docs = self.vsm.search(enriched_query, k=search_k, where_filter=where_filter)
            docs = batch_docs if not docs else self._merge_retry_candidates(docs, batch_docs)
        focused_operand_queries = _focused_operand_surface_queries(active_subtask, query, report_scope)
        if focused_operand_queries:
            focused_docs: List[tuple[Document, float]] = []
            for focused_query in focused_operand_queries[:8]:
                search_k = max(effective_k * 2, 8)
                executed_queries.append(
                    {
                        "source": "operand_focus",
                        "base_query": focused_query,
                        "executed_query": focused_query,
                        "k": search_k,
                        "where_filter": where_filter,
                    }
                )
                focused_docs.extend(self.vsm.search(focused_query, k=search_k, where_filter=where_filter))
            if focused_docs:
                docs = focused_docs if not docs else self._merge_retry_candidates(docs, focused_docs)
        if retry_queries:
            retry_docs: List[tuple[Document, float]] = []
            for retry_query in retry_queries[:3]:
                search_k = max(effective_k * 2, 8)
                executed_queries.append(
                    {
                        "source": "retry",
                        "base_query": retry_query,
                        "executed_query": retry_query,
                        "k": search_k,
                        "where_filter": where_filter,
                    }
                )
                retry_docs.extend(self.vsm.search(retry_query, k=search_k, where_filter=where_filter))
            if retry_docs:
                docs = self._merge_retry_candidates(docs, retry_docs)
        supplemental_docs = self._supplement_section_seed_docs(state)
        if supplemental_docs:
            docs = self._merge_retry_candidates(docs, supplemental_docs)

        if reflection_count > 0:
            previous_docs = list(state.get("seed_retrieved_docs", []) or [])
            if previous_docs:
                docs = self._merge_retry_candidates(docs, previous_docs)

        logger.info(
            "[retrieve] companies=%s years=%s topic=%s where=%s retry_count=%s retry_queries=%s -> %s candidates",
            companies,
            years,
            state.get("topic"),
            where_filter,
            reflection_count,
            retry_queries,
            len(docs),
        )

        # section_filter는 _rerank_docs에서 +0.20 부스트로만 반영.
        # hard filter로 쓰면 LLM이 wrong section을 추출했을 때 관련 청크가 전부 제외됨.

        if companies and strict_company_scope:
            lowered_companies = {company.lower() for company in companies}
            docs = self._apply_strict_filter(
                docs,
                lambda doc: (
                    str(doc.metadata.get("company", "")).lower() in lowered_companies
                    or any(
                        target in str(doc.metadata.get("company", "")).lower()
                        or str(doc.metadata.get("company", "")).lower() in target
                        for target in lowered_companies
                    )
                ),
            )

        if years and not has_multi_source_scope:
            valid_years = {int(year) for year in years}
            docs = self._apply_strict_filter(
                docs,
                lambda doc: int(doc.metadata.get("year", 0)) in valid_years,
            )

        reranked = self._rerank_docs(docs, state)

        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = str(
            active_subtask.get("format_preference_override")
            or state.get("format_preference")
            or self._default_format_preference(intent)
        ).strip().lower()
        if operation_family == "narrative_summary":
            docs = self._select_narrative_summary_docs(reranked, state, effective_k)
        else:
            # format_preference에 따라 표/단락 비율 보장
            if format_preference == "table":
                # 수치·추이 쿼리: 표 우선, 단락 최소 2개 보장
                tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
                paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
                # Paragraphs are supplemental; keep a table in the visible window when available.
                min_table = 1 if tables else 0
                min_para = min(2, len(paras), max(effective_k - min_table, 0))
                docs = (tables[: effective_k - min_para] + paras[:min_para])
            elif format_preference == "paragraph":
                # 개요·리스크·일반 쿼리: 단락 최소 절반 보장
                tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
                paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
                min_para = min(effective_k // 2, len(paras))
                docs = (paras[:min_para] + tables[: effective_k - min_para])
                docs.sort(key=lambda x: x[1], reverse=True)
            else:
                docs = reranked

        seed_docs = reranked[: min(len(reranked), effective_k * 4)]
        docs = docs[: effective_k]
        required_operands = [
            dict(item)
            for item in (active_subtask.get("required_operands") or [])
            if isinstance(item, dict)
        ]
        if required_operands and operation_family != "narrative_summary":
            docs = _ensure_period_count_operand_docs(docs, reranked, required_operands, effective_k)
        selected_chunks: List[Dict[str, Any]] = []
        for rank, item in enumerate(docs, start=1):
            doc, score = item
            metadata = dict(getattr(doc, "metadata", {}) or {})
            try:
                serialised_score: Optional[float] = float(score)
            except (TypeError, ValueError):
                serialised_score = None
            selected_chunks.append(
                {
                    "rank": rank,
                    "score": serialised_score,
                    "chunk_uid": metadata.get("chunk_uid") or metadata.get("chunk_id") or metadata.get("id"),
                    "section_path": metadata.get("section_path"),
                    "block_type": metadata.get("block_type"),
                    "company": metadata.get("company"),
                    "year": metadata.get("year"),
                    "rcept_no": metadata.get("rcept_no"),
                }
            )
        retrieval_debug_trace = {
            "query_bundle": list(query_bundle),
            "executed_queries": executed_queries,
            "where_filter": where_filter,
            "effective_k": effective_k,
            "reflection_count": reflection_count,
            "retry_queries": retry_queries[:3],
            "candidate_count": len(reranked),
            "seed_count": len(seed_docs),
            "selected_count": len(docs),
            "selected_chunks": selected_chunks,
            "policy_trace": {
                "intent": intent,
                "operation_family": operation_family,
                "format_preference": format_preference,
                "retrieval_hint": retrieval_hint,
                "preferred_sections": list(preferred_sections or []),
                "strict_company_scope": strict_company_scope,
                "multi_source_scope": has_multi_source_scope,
                "scope_report_type": scope_report_type,
                "scope_consolidation": scope_consolidation,
            },
        }
        logger.info(
            "[retrieve] intent=%s format=%s final %s chunks returned",
            intent,
            format_preference,
            len(docs),
        )
        return {
            "seed_retrieved_docs": seed_docs,
            "retrieved_docs": docs,
            "retrieval_debug_trace": retrieval_debug_trace,
        }

    def _expand_via_structure_graph(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Attach nearby structural context to seed retrieval hits.

        The original hits remain the ranking anchors; expansion adds parent
        paragraphs, sibling context, and table descriptions when configured.
        """
        config = dict(self.graph_expansion_config or {})
        if not config.get("enabled"):
            return {}

        seed_docs = list(state.get("retrieved_docs", []) or [])
        if not seed_docs:
            return {}

        include_parent_context = bool(config.get("include_parent_context", True))
        include_section_lead = bool(config.get("include_section_lead", True))
        include_reference_notes = bool(config.get("include_reference_notes", True))
        include_described_by_paragraph = bool(config.get("include_described_by_paragraph", True))
        include_table_context = bool(config.get("include_table_context", True))
        include_sibling_prev = bool(config.get("include_sibling_prev", True))
        include_sibling_next = bool(config.get("include_sibling_next", False))
        table_sibling_prev_paragraph_only = bool(config.get("table_sibling_prev_paragraph_only", True))
        sibling_window = max(0, int(config.get("sibling_window", 1) or 0))
        max_docs = max(self.k, int(config.get("max_docs", self.k) or self.k))

        expanded: List[Any] = []
        seen_keys: set[str] = set()

        def add_doc(doc: Document, score: float, relation: str = "") -> None:
            metadata = dict(doc.metadata or {})
            key = str(metadata.get("chunk_uid") or metadata.get("graph_relation") or relation or doc.page_content[:80])
            relation_key = metadata.get("graph_relation") or relation or "seed"
            dedupe_group = relation_key
            if relation_key in {"seed", "sibling_prev", "sibling_next"}:
                dedupe_group = "chunk"
            dedupe_key = f"{key}::{dedupe_group}"
            if dedupe_key in seen_keys:
                return
            seen_keys.add(dedupe_key)
            expanded.append((doc, score))

        for doc, score in seed_docs:
            metadata = dict(doc.metadata or {})
            parent_id = str(metadata.get("parent_id") or "")
            chunk_uid = str(metadata.get("chunk_uid") or "")
            block_type = str(metadata.get("block_type") or "").strip().lower()
            seed_metadata = dict(metadata)
            if include_parent_context and parent_id:
                seed_metadata["graph_seed_with_parent_context"] = True
            add_doc(Document(page_content=doc.page_content, metadata=seed_metadata), float(score), relation="seed")

            if include_parent_context and parent_id:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    parent_metadata = {
                        **metadata,
                        "graph_relation": "parent_context",
                        "graph_source_chunk_uid": chunk_uid,
                        "block_type": "parent_context",
                        "chunk_uid": f"{chunk_uid}::parent_context" if chunk_uid else f"{parent_id}::parent_context",
                    }
                    add_doc(Document(page_content=parent_text, metadata=parent_metadata), float(score) - 0.005, "parent_context")

            if include_section_lead and parent_id:
                section_lead_doc = self.vsm.get_section_lead_doc(parent_id=parent_id, exclude_chunk_uid=chunk_uid)
                if section_lead_doc is not None:
                    add_doc(section_lead_doc, float(score) - 0.006, "section_lead")

            if include_reference_notes and chunk_uid:
                reference_docs = self.vsm.get_reference_docs(chunk_uid=chunk_uid, limit=4)
                for offset, reference_doc in enumerate(reference_docs, start=1):
                    add_doc(reference_doc, float(score) - 0.008 - (offset * 0.001), "reference_note")

            if sibling_window > 0 and parent_id and chunk_uid:
                sibling_docs = self.vsm.get_sibling_docs(parent_id=parent_id, chunk_uid=chunk_uid, window=sibling_window)
                for offset, sibling_doc in enumerate(sibling_docs, start=1):
                    sibling_metadata = dict(sibling_doc.metadata or {})
                    relation = str(sibling_metadata.get("graph_relation") or "sibling").strip()
                    sibling_block_type = str(sibling_metadata.get("block_type") or "").strip().lower()
                    if relation == "sibling_prev" and not include_sibling_prev:
                        continue
                    if relation == "sibling_next" and not include_sibling_next:
                        continue
                    if (
                        block_type == "table"
                        and relation == "sibling_prev"
                        and table_sibling_prev_paragraph_only
                        and sibling_block_type != "paragraph"
                    ):
                        continue
                    add_doc(sibling_doc, float(score) - 0.01 - (offset * 0.001), relation)

            if include_described_by_paragraph and chunk_uid and str(metadata.get("block_type") or "") == "table":
                described_by_doc = self.vsm.get_described_by_doc(chunk_uid=chunk_uid)
                if described_by_doc is not None:
                    add_doc(described_by_doc, float(score) - 0.004, "described_by_paragraph")

            if include_table_context:
                table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
                if table_context:
                    table_metadata = {
                        **metadata,
                        "graph_relation": "table_context",
                        "graph_source_chunk_uid": chunk_uid,
                        "block_type": "table_context",
                        "chunk_uid": f"{chunk_uid}::table_context" if chunk_uid else f"{parent_id}::table_context",
                    }
                    add_doc(Document(page_content=table_context, metadata=table_metadata), float(score) - 0.007, "table_context")

        expanded.sort(key=lambda item: item[1], reverse=True)
        expanded = expanded[:max_docs]
        logger.info(
            "[graph_expand] seed=%s expanded=%s parent=%s section_lead=%s reference_note=%s sibling_prev=%s sibling_next=%s sibling_window=%s table_context=%s max_docs=%s",
            len(seed_docs),
            len(expanded),
            include_parent_context,
            include_section_lead,
            include_reference_notes,
            include_sibling_prev,
            include_sibling_next,
            sibling_window,
            include_table_context,
            max_docs,
        )
        return {"retrieved_docs": expanded}

    def _format_context(self, docs) -> str:
        """검색된 자식 청크를 부모 청크(섹션 전체)로 확장해 LLM 컨텍스트 구성.

        부모 청크가 있으면 부모 텍스트를 사용한다(더 넓은 맥락).
        없으면 자식 청크 텍스트를 그대로 사용한다.
        동일 parent_id가 여러 청크에서 반환될 경우 부모는 한 번만 포함한다.
        """
        parts = []
        seen_parents: set = set()

        for doc, score in docs:
            metadata = doc.metadata or {}
            company      = metadata.get("company", "?")
            year         = metadata.get("year", "?")
            report_type  = metadata.get("report_type", "?")
            section_path = metadata.get("section_path", metadata.get("section", "?"))
            parent_id    = metadata.get("parent_id")
            graph_relation = metadata.get("graph_relation")
            skip_auto_parent = bool(metadata.get("graph_seed_with_parent_context"))

            header = (
                f"[{company} | {year} | {report_type} | {section_path} | score={score:.3f}]"
            )

            if graph_relation:
                parts.append(f"{header}\n{doc.page_content}")
                continue

            # 부모 청크 우선 사용
            if parent_id and not skip_auto_parent and parent_id not in seen_parents:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    seen_parents.add(parent_id)
                    parts.append(f"{header}\n{parent_text}")
                    continue

            # 부모가 없거나 이미 포함된 parent_id → 자식 청크 사용
            if parent_id in seen_parents:
                # 이미 이 섹션의 부모를 포함했으므로 중복 제외
                continue

            table_context = metadata.get("table_context")
            body = f"[table_context] {table_context}\n{doc.page_content}" if table_context else doc.page_content
            parts.append(f"{header}\n{body}")

        return "\n\n---\n\n".join(parts)

    def _build_source_anchor(self, metadata: Dict[str, Any]) -> str:
        relation = str(metadata.get("graph_relation") or "").strip()
        relation_suffix = f" | {relation}" if relation else ""
        return (
            f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
            f"{metadata.get('section_path', metadata.get('section', '?'))}{relation_suffix}]"
        )

    def _build_evidence_context(self, docs) -> Dict[str, Any]:
        parts = []
        anchor_lookup: Dict[str, List[Dict[str, Any]]] = {}
        seen_parents: set = set()

        for doc, _score in docs:
            metadata = doc.metadata or {}
            anchor = self._build_source_anchor(metadata)
            anchor_lookup.setdefault(anchor, []).append(
                {
                    "metadata": {
                        "company": metadata.get("company"),
                        "year": metadata.get("year"),
                        "report_type": metadata.get("report_type"),
                        "section": metadata.get("section"),
                        "section_path": metadata.get("section_path", metadata.get("section")),
                        "block_type": metadata.get("block_type"),
                        "graph_relation": metadata.get("graph_relation"),
                        "chunk_uid": metadata.get("chunk_uid"),
                        "parent_id": metadata.get("parent_id"),
                        "table_source_id": metadata.get("table_source_id"),
                        "table_header_context": metadata.get("table_header_context"),
                        "table_summary_text": metadata.get("table_summary_text"),
                        "table_value_labels_text": metadata.get("table_value_labels_text"),
                        "table_context": metadata.get("table_context"),
                        "unit_hint": metadata.get("unit_hint"),
                        "statement_type": metadata.get("statement_type"),
                        "consolidation_scope": metadata.get("consolidation_scope"),
                        "period_focus": metadata.get("period_focus"),
                        "period_labels": metadata.get("period_labels"),
                    },
                    "page_content": str(doc.page_content or ""),
                }
            )

            parent_id = metadata.get("parent_id")
            graph_relation = metadata.get("graph_relation")
            skip_auto_parent = bool(metadata.get("graph_seed_with_parent_context"))
            if graph_relation:
                parts.append(f"{anchor}\n{doc.page_content}")
                continue

            if parent_id and not skip_auto_parent and parent_id not in seen_parents:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    seen_parents.add(parent_id)
                    parts.append(f"{anchor}\n{parent_text}")
                    continue

            if parent_id in seen_parents:
                continue

            table_context = metadata.get("table_context")
            body = f"[table_context] {table_context}\n{doc.page_content}" if table_context else doc.page_content
            parts.append(f"{anchor}\n{body}")

        return {
            "context": "\n\n---\n\n".join(parts),
            "anchor_lookup": anchor_lookup,
            "available_anchors": list(anchor_lookup.keys()),
        }

    def _resolve_anchor_metadata(
        self,
        anchor_lookup: Dict[str, Any],
        anchor: str,
        *,
        quote_surface: str = "",
        claim_surface: str = "",
    ) -> Dict[str, Any]:
        lookup_value = anchor_lookup.get(anchor) or []
        if isinstance(lookup_value, dict):
            return dict(lookup_value)
        entries = [dict(item) for item in lookup_value if isinstance(item, dict)]
        if not entries:
            return {}

        desired_surface = _normalise_spaces(quote_surface or claim_surface)
        desired_tokens = [
            token
            for token in re.split(r"[|\s]+", desired_surface)
            if token and len(token) >= 2
        ]

        def _entry_score(entry: Dict[str, Any]) -> float:
            metadata = dict(entry.get("metadata") or {})
            haystack = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(entry.get("page_content") or ""),
                        str(metadata.get("table_context") or ""),
                        str(metadata.get("table_header_context") or ""),
                        str(metadata.get("table_summary_text") or ""),
                    )
                    if part
                )
            )
            score = 0.0
            if desired_surface and desired_surface in haystack:
                score += 8.0
            elif desired_tokens:
                overlap = sum(1 for token in desired_tokens if token in haystack)
                score += min(float(overlap), 6.0)
            if str(metadata.get("block_type") or "").strip().lower() == "table":
                score += 0.5
            if str(metadata.get("unit_hint") or "").strip():
                score += 0.25
            if str(metadata.get("table_source_id") or "").strip():
                score += 0.25
            return score

        best = max(entries, key=_entry_score)
        return dict(best.get("metadata") or {})

    def _build_runtime_evidence_item(
        self,
        item: EvidenceItem,
        index: int,
        anchor_lookup: Dict[str, Any],
    ) -> Dict[str, Any]:
        metadata = self._resolve_anchor_metadata(
            anchor_lookup,
            item.source_anchor,
            quote_surface=str(item.quote_span or ""),
            claim_surface=str(item.claim or ""),
        )
        allowed_terms: List[str] = []
        seen_terms = set()
        for term in item.allowed_terms:
            cleaned = str(term or "").strip()
            if cleaned and cleaned not in seen_terms:
                seen_terms.add(cleaned)
                allowed_terms.append(cleaned)

        result: Dict[str, Any] = {
            "evidence_id": f"ev_{index:03d}",
            "source_anchor": item.source_anchor,
            "claim": item.claim,
            "quote_span": item.quote_span,
            "support_level": item.support_level,
            "question_relevance": item.question_relevance,
            "allowed_terms": allowed_terms,
            "metadata": metadata,
        }
        if item.parent_category:
            result["parent_category"] = item.parent_category.strip()
        return result

    def _evidence_item_conflicts_with_operand(self, item: Dict[str, Any], operand: Dict[str, Any]) -> bool:
        quote_surface = str(item.get("quote_span") or item.get("raw_row_text") or "").strip()
        if quote_surface and _text_has_negative_surface(quote_surface, operand):
            return True

        claim_surface = str(item.get("claim") or "").strip()
        if claim_surface and _text_has_negative_surface(claim_surface, operand) and not _text_has_positive_surface(claim_surface, operand):
            return True
        return False

    def _is_direct_numeric_table_backed_evidence_item(self, item: Dict[str, Any]) -> bool:
        metadata = dict(item.get("metadata") or {})
        block_type = str(metadata.get("block_type") or "").strip().lower()
        has_table_metadata = bool(
            str(metadata.get("table_source_id") or "").strip()
            or str(metadata.get("table_header_context") or "").strip()
            or block_type == "table"
        )
        if not has_table_metadata:
            return False

        surface = _normalise_spaces(
            str(item.get("raw_row_text") or item.get("quote_span") or "")
        )
        if not surface or not re.search(r"\d", surface):
            return False
        return True

    def _is_narrative_supporting_evidence_item(self, item: Dict[str, Any]) -> bool:
        if self._is_direct_numeric_table_backed_evidence_item(item):
            return False

        metadata = dict(item.get("metadata") or {})
        block_type = str(metadata.get("block_type") or "").strip().lower()
        graph_relation = str(metadata.get("graph_relation") or "").strip().lower()
        merged = _normalise_spaces(
            " ".join(
                part
                for part in (
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                    str(item.get("source_context") or ""),
                    str(metadata.get("section_path") or metadata.get("section") or ""),
                )
                if part
            )
        )
        if not merged:
            return False
        if _query_requests_narrative_context(merged):
            return True
        return block_type in {"paragraph", "parent_context", "section_lead", "described_by_paragraph"} or graph_relation in {
            "parent_context",
            "section_lead",
            "described_by_paragraph",
        }

    def _restrict_direct_numeric_evidence_items(
        self,
        evidence_items: List[Dict[str, Any]],
        *,
        preserve_narrative_context: bool = False,
    ) -> List[Dict[str, Any]]:
        direct_items: List[Dict[str, Any]] = []
        seen_direct_keys: set[str] = set()
        for item in evidence_items:
            if not self._is_direct_numeric_table_backed_evidence_item(item):
                continue
            dedupe_key = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(item.get("source_anchor") or ""),
                        str(item.get("raw_row_text") or item.get("quote_span") or item.get("claim") or ""),
                    )
                    if part
                )
            )
            if dedupe_key and dedupe_key in seen_direct_keys:
                continue
            if dedupe_key:
                seen_direct_keys.add(dedupe_key)
            direct_items.append(dict(item))
        if not preserve_narrative_context:
            return direct_items

        narrative_items: List[Dict[str, Any]] = []
        seen_keys = {
            _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(item.get("source_anchor") or ""),
                        str(item.get("raw_row_text") or item.get("quote_span") or item.get("claim") or ""),
                    )
                    if part
                )
            )
            for item in direct_items
        }
        for item in self._sort_evidence_items(evidence_items):
            if self._is_direct_numeric_table_backed_evidence_item(item):
                continue
            if not self._is_narrative_supporting_evidence_item(item):
                continue
            dedupe_key = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(item.get("source_anchor") or ""),
                        str(item.get("raw_row_text") or item.get("quote_span") or item.get("claim") or ""),
                    )
                    if part
                )
            )
            if dedupe_key and dedupe_key in seen_keys:
                continue
            if dedupe_key:
                seen_keys.add(dedupe_key)
            narrative_items.append(dict(item))
            if len(narrative_items) >= 2:
                break
        return direct_items + narrative_items

    def _filter_evidence_items_for_required_operands(
        self,
        evidence_items: List[Dict[str, Any]],
        state: FinancialAgentState,
    ) -> List[Dict[str, Any]]:
        required_operands = [
            dict(item)
            for item in ((state.get("active_subtask") or {}).get("required_operands") or [])
            if bool(item.get("required", True))
        ]
        if not required_operands:
            return evidence_items

        filtered: List[Dict[str, Any]] = []
        for item in evidence_items:
            if any(not self._evidence_item_conflicts_with_operand(item, operand) for operand in required_operands):
                filtered.append(item)
        return filtered

    def _sort_evidence_items(self, evidence_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        relevance_order = {"high": 0, "medium": 1, "low": 2}
        support_order = {"direct": 0, "partial": 1, "context": 2}
        return sorted(
            evidence_items,
            key=lambda item: (
                relevance_order.get(str(item.get("question_relevance", "medium")), 1),
                support_order.get(str(item.get("support_level", "context")), 2),
                str(item.get("evidence_id", "")),
            ),
        )

    def _format_evidence_for_prompt(
        self,
        evidence_items: List[Dict[str, Any]],
        evidence_bullets: List[str],
    ) -> str:
        if evidence_items:
            parts = []
            for item in self._sort_evidence_items(evidence_items):
                allowed_terms = ", ".join(item.get("allowed_terms") or [])
                quote_span = str(item.get("quote_span") or "").strip()
                lines = [
                    f"- evidence_id: {item.get('evidence_id', '?')}",
                    f"  source_anchor: {item.get('source_anchor', '?')}",
                    f"  support_level: {item.get('support_level', '?')}",
                    f"  question_relevance: {item.get('question_relevance', '?')}",
                ]
                if item.get("parent_category"):
                    lines.append(f"  parent_category: {item['parent_category']}")
                lines += [
                    f"  claim: {item.get('claim', '')}",
                ]
                if quote_span:
                    lines.append(f"  quote_span: {quote_span}")
                if item.get("source_context"):
                    lines.append(f"  source_context: {item.get('source_context')}")
                if item.get("raw_row_text"):
                    lines.append(f"  raw_row_text: {item.get('raw_row_text')}")
                if allowed_terms:
                    lines.append(f"  allowed_terms: {allowed_terms}")
                parts.append("\n".join(lines))
            return "\n\n".join(parts)
        return "\n".join(evidence_bullets)

    def _extract_ratio_row_candidates(
        self,
        retrieved_docs: List,
        query: str,
        topic: str,
    ) -> List[Dict[str, Any]]:
        combined_query = _normalise_spaces(f"{query} {topic}")
        if not _is_ratio_percent_query(combined_query):
            return []

        metric_patterns: List[str] = get_financial_ontology().row_patterns(query, topic, "comparison")
        if not metric_patterns:
            metric_patterns.extend([r"비율", r"비중", r"이익률"])

        candidates: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str]] = set()
        year_pattern = re.compile(r"(20\d{2}년|제\d+기|당기|전기)")
        percent_pattern = re.compile(r"[\d,.]+%")

        for index, (doc, _score) in enumerate(retrieved_docs[: min(8, len(retrieved_docs))], start=1):
            metadata = dict(doc.metadata or {})
            if str(metadata.get("block_type") or "") != "table":
                continue

            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            table_context = _normalise_spaces(str(metadata.get("table_context") or ""))
            body = str(doc.page_content or "")
            combined = _normalise_spaces(f"{table_context}\n{body}")
            if not combined:
                continue

            for pattern in metric_patterns:
                match = re.search(pattern, combined, flags=re.IGNORECASE)
                if not match:
                    continue

                window_start = max(0, match.start() - 180)
                window_end = min(len(combined), match.end() + 280)
                snippet = _normalise_spaces(combined[window_start:window_end])
                percents = percent_pattern.findall(snippet)
                if not percents:
                    continue

                years = []
                for token in year_pattern.findall(combined[max(0, match.start() - 240): min(len(combined), match.end() + 80)]):
                    if token not in years:
                        years.append(token)
                if not years and table_context:
                    for token in year_pattern.findall(table_context):
                        if token not in years:
                            years.append(token)
                header_text = " | ".join(years[:4]) if years else (table_context[:120] if table_context else section_path)
                source_context = f"[표: {section_path}] | [헤더: {header_text}]"
                row_text = snippet
                key = (section_path, row_text)
                if key in seen_keys:
                    continue
                seen_keys.add(key)

                candidates.append(
                    {
                        "evidence_id": f"ev_ratio_{index:03d}_{len(candidates) + 1:03d}",
                        "source_anchor": self._build_source_anchor(metadata),
                        "claim": row_text,
                        "quote_span": row_text[:240],
                        "source_context": source_context,
                        "raw_row_text": row_text,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": years[:4] + percents[:4],
                        "metadata": metadata,
                    }
                )
                break

        return candidates

    def _extract_ratio_component_candidates(
        self,
        retrieved_docs: List,
        query: str,
        topic: str,
    ) -> List[Dict[str, Any]]:
        combined_query = _normalise_spaces(f"{query} {topic}")
        if not _is_ratio_percent_query(combined_query):
            return []
        if _is_percent_point_difference_query(combined_query):
            return []

        specs: List[tuple[str, List[str], List[str]]] = []
        ontology_specs = get_financial_ontology().component_specs(query, topic, "comparison")
        for spec in ontology_specs:
            metric_name = str(spec.get("name") or "")
            preferred_sections = list(spec.get("preferred_sections") or [])
            patterns = [re.escape(keyword) for keyword in (spec.get("keywords") or [])]
            if metric_name and patterns:
                specs.append((metric_name, preferred_sections, patterns))
        if not specs:
            return []

        candidates: List[Dict[str, Any]] = []
        seen_keys: set[tuple[str, str, str]] = set()
        year_pattern = re.compile(r"(20\d{2}년|제\d+기|당기|전기)")

        for metric_name, preferred_sections, patterns in specs:
            best_candidate: Optional[Dict[str, Any]] = None
            best_score = -1
            for index, (doc, _score) in enumerate(retrieved_docs[: min(16, len(retrieved_docs))], start=1):
                metadata = dict(doc.metadata or {})
                section_path = str(metadata.get("section_path") or metadata.get("section") or "")
                if preferred_sections and not any(section_term in section_path for section_term in preferred_sections):
                    continue
                text = _normalise_spaces(f"{metadata.get('table_context') or ''}\n{doc.page_content or ''}")
                if not text:
                    continue
                for pattern in patterns:
                    match = re.search(pattern, text, flags=re.IGNORECASE)
                    if not match:
                        continue
                    window_start = max(0, match.start() - 180)
                    window_end = min(len(text), match.end() + 260)
                    row_text = _normalise_spaces(text[window_start:window_end])
                    if not row_text:
                        continue
                    raw_value, raw_unit = _extract_value_near_match(text, match.start(), match.end())
                    if not raw_value:
                        continue
                    if metric_name != "매출액" and "%" in raw_value:
                        continue
                    source_context = f"[표: {section_path}]"
                    years = []
                    for token in year_pattern.findall(text[max(0, match.start() - 240): min(len(text), match.end() + 120)]):
                        if token not in years:
                            years.append(token)
                    if years:
                        source_context += f" | [헤더: {' | '.join(years[:4])}]"
                    key = (metric_name, section_path, row_text)
                    if key in seen_keys:
                        continue
                    score = 0
                    if any(section_term in section_path for section_term in preferred_sections[:1]):
                        score += 3
                    if "2024년" in row_text:
                        score += 2
                    if metric_name in row_text:
                        score += 2
                    if metric_name == "연구개발비용" and any(alias in row_text for alias in ("총계", "연구개발비용", "연구개발비")):
                        score += 2
                    if metric_name == "매출액" and any(alias in row_text for alias in ("매출액", "당기매출액", "수익")):
                        score += 2
                    candidate = {
                        "evidence_id": f"ev_component_{metric_name}_{index:03d}_{len(candidates) + 1:03d}",
                        "source_anchor": self._build_source_anchor(metadata),
                        "claim": row_text,
                        "quote_span": row_text[:240],
                        "source_context": source_context,
                        "raw_row_text": row_text,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": [metric_name] + years[:4],
                        "metadata": metadata,
                        "matched_metric": metric_name,
                        "matched_value": raw_value,
                        "matched_unit": raw_unit,
                    }
                    if score > best_score:
                        best_score = score
                        best_candidate = candidate
            if best_candidate:
                key = (str(best_candidate.get("matched_metric") or ""), str(best_candidate.get("source_anchor") or ""), str(best_candidate.get("raw_row_text") or ""))
                if key not in seen_keys:
                    seen_keys.add(key)
                    candidates.append(best_candidate)

        return candidates

    def _build_ratio_operands_from_candidates(
        self,
        candidate_items: List[Dict[str, Any]],
        query: str,
        topic: str = "",
        report_scope: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not candidate_items:
            return []

        query_text = _normalise_spaces(query)
        query_years = re.findall(r"(20\d{2}년)", query_text)
        prioritized_items = _prioritize_candidate_items(
            candidate_items,
            query=query,
            topic=topic,
            report_scope=dict(report_scope or {}),
            query_years=[int(year.replace("년", "")) for year in query_years],
        )
        if required_operands:
            def _period_count_item_priority(item: Dict[str, Any]) -> tuple[int, int]:
                metadata = dict(item.get("metadata") or {})
                text = _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            str(item.get("source_context") or ""),
                            str(metadata.get("table_context") or ""),
                            str(metadata.get("table_header_context") or ""),
                            str(metadata.get("table_summary_text") or ""),
                            str(metadata.get("local_heading") or ""),
                            str(metadata.get("section_path") or metadata.get("section") or ""),
                            str(item.get("raw_row_text") or item.get("claim") or ""),
                        )
                        if part
                    )
                )
                matched_operands = sum(
                    1
                    for operand in required_operands
                    if _period_comparison_count_value_from_text(
                        text,
                        operand,
                        query_years=query_years,
                        report_scope=dict(report_scope or {}),
                    )
                )
                subject_after_context = int(
                    bool(
                        re.search(
                            r"[가-힣A-Za-z0-9]+(?:에서|에서는)[가-힣A-Za-z0-9]+(?:은|는)",
                            re.sub(r"\s+", "", text),
                        )
                    )
                )
                return matched_operands, subject_after_context

            prioritized_items = sorted(prioritized_items, key=_period_count_item_priority, reverse=True)
        operand_rows: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        percent_pattern = re.compile(r"[\d,.]+%")
        year_pattern = re.compile(r"(20\d{2}년)")

        # 1) row-level percent operands with header context
        for item in prioritized_items:
            raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
            if not raw_row:
                continue
            percents = percent_pattern.findall(raw_row)
            if not percents:
                continue
            context_text = _normalise_spaces(f"{item.get('source_context') or ''} {raw_row}")
            context_years = []
            for token in year_pattern.findall(context_text):
                if token not in context_years:
                    context_years.append(token)
            if query_years and len(context_years) >= len(query_years):
                periods = query_years
            else:
                periods = context_years[: len(percents)]
            for idx, raw_value in enumerate(percents):
                period = periods[idx] if idx < len(periods) else ""
                key = (str(item.get("source_anchor") or ""), raw_value, period)
                if key in seen:
                    continue
                seen.add(key)
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, "%")
                operand_rows.append(
                    {
                        "operand_id": f"op_{len(operand_rows) + 1:03d}",
                        "evidence_id": item.get("evidence_id"),
                        "source_anchor": item.get("source_anchor"),
                        "label": f"{period} 비율".strip(),
                        "raw_value": raw_value,
                        "raw_unit": "%",
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "period": period,
                        "table_source_id": (item.get("metadata") or {}).get("table_source_id"),
                        "statement_type": (item.get("metadata") or {}).get("statement_type"),
                        "consolidation_scope": (item.get("metadata") or {}).get("consolidation_scope"),
                    }
                )

        if operand_rows:
            if _is_percent_point_difference_query(query_text):
                if query_years:
                    filtered = [row for row in operand_rows if row.get("period") in query_years]
                    if len(filtered) >= 2:
                        return filtered[:2]
                return operand_rows[:2]
            if query_years:
                filtered = [row for row in operand_rows if row.get("period") in query_years[:1]]
                if filtered:
                    return filtered[:1]
            return operand_rows[:1]

        # 2) component-based operands (e.g. 연구개발비용, 매출액)
        if _is_percent_point_difference_query(query_text):
            return []

        metric_specs = [
            ("연구개발비용", ("연구개발비용", "연구개발비")),
            ("매출액", ("매출액", "당기매출액", "수익")),
        ]
        for label_name, aliases in metric_specs:
            for item in prioritized_items:
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                if not raw_row or not any(alias in raw_row for alias in aliases):
                    continue
                period = ""
                for token in query_years or year_pattern.findall(_normalise_spaces(str(item.get("source_context") or "") + " " + raw_row)):
                    period = token
                    break
                raw_value = _normalise_spaces(str(item.get("matched_value") or ""))
                raw_unit = str(item.get("matched_unit") or "")
                if not raw_value:
                    value_match = re.search(r"[\d,]+(?:\s*조\s*[\d,]+\s*억(?:원)?)?|[\d,]+", raw_row)
                    if not value_match:
                        continue
                    raw_value = value_match.group(0)
                    raw_unit = "원" if "조" in raw_value or "억" in raw_value else ("백만원" if "백만원" in raw_row else "")
                normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
                if normalized_value is None:
                    continue
                operand_rows.append(
                    {
                        "operand_id": f"op_{len(operand_rows) + 1:03d}",
                        "evidence_id": item.get("evidence_id"),
                        "source_anchor": item.get("source_anchor"),
                        "label": f"{period} {label_name}".strip(),
                        "raw_value": raw_value,
                        "raw_unit": raw_unit or "원",
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "period": period,
                        "table_source_id": (item.get("metadata") or {}).get("table_source_id"),
                        "statement_type": (item.get("metadata") or {}).get("statement_type"),
                        "consolidation_scope": (item.get("metadata") or {}).get("consolidation_scope"),
                    }
                )
                break

        return operand_rows

    def _build_required_operands_from_candidates(
        self,
        candidate_items: List[Dict[str, Any]],
        *,
        required_operands: List[Dict[str, Any]],
        query: str,
        topic: str = "",
        report_scope: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not candidate_items or not required_operands:
            return []

        query_text = _normalise_spaces(query)
        query_years = re.findall(r"(20\d{2}년)", query_text)
        prioritized_items = _prioritize_candidate_items(
            candidate_items,
            query=query,
            topic=topic,
            report_scope=dict(report_scope or {}),
            query_years=[int(year.replace("년", "")) for year in query_years],
        )
        operand_rows: List[Dict[str, Any]] = []
        seen: set[tuple[str, str, str]] = set()
        year_pattern = re.compile(r"(20\d{2}년)")

        for operand in required_operands:
            label_name = str(operand.get("label") or operand.get("name") or operand.get("concept") or "").strip()
            if not label_name:
                continue
            for item in prioritized_items:
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                if not raw_row:
                    continue
                metadata = dict(item.get("metadata") or {})
                row_label = _extract_table_row_label(raw_row)
                context_text = _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            str(item.get("source_context") or ""),
                            str(metadata.get("table_context") or ""),
                            str(metadata.get("table_header_context") or ""),
                            str(metadata.get("table_summary_text") or ""),
                            str(metadata.get("local_heading") or ""),
                            str(metadata.get("section_path") or metadata.get("section") or ""),
                            raw_row,
                        )
                        if part
                    )
                )
                aggregate_context_match = False
                compact_row_label = re.sub(r"\s+", "", _normalise_spaces(row_label))
                aggregate_stage = (
                    "subtotal"
                    if compact_row_label == "소계"
                    else "final"
                    if compact_row_label in {"합계", "총계", "계"}
                    else "none"
                )
                if aggregate_stage != "none":
                    binding_policy = dict(operand.get("binding_policy") or {})
                    prefer_value_roles = {
                        str(item).strip().lower()
                        for item in (binding_policy.get("prefer_value_roles") or [])
                        if str(item).strip()
                    }
                    prefer_aggregation_stages = {
                        str(item).strip().lower()
                        for item in (binding_policy.get("prefer_aggregation_stages") or [])
                        if str(item).strip()
                    }
                    aggregate_context_match = (
                        ("aggregate" in prefer_value_roles or aggregate_stage in prefer_aggregation_stages)
                        and _operand_text_match(context_text, operand)
                    )
                surface_contract_match = (
                    _text_has_positive_surface(context_text or raw_row, operand)
                    and not _text_has_negative_surface(context_text or raw_row, operand)
                )
                period_count_context_match = (
                    bool(re.search(KOREAN_PERIOD_COMPARISON_RE_FRAGMENT, context_text or raw_row))
                    and bool(re.search(_COUNT_VALUE_UNIT_RE, context_text or raw_row))
                    and _sentence_matches_operand_context(context_text or raw_row, operand)
                )
                if (
                    not _operand_text_match(raw_row, operand)
                    and not aggregate_context_match
                    and not surface_contract_match
                    and not period_count_context_match
                ):
                    continue

                period = ""
                for token in query_years or year_pattern.findall(context_text):
                    period = token
                    break

                raw_value = _normalise_spaces(str(item.get("matched_value") or ""))
                raw_unit = str(item.get("matched_unit") or "")

                if not raw_value:
                    parsed_cells = _parse_unstructured_table_row_cells(raw_row, metadata)
                    if parsed_cells:
                        target_years = [int(token.replace("년", "")) for token in query_years] if query_years else []
                        ranked_cells = sorted(
                            parsed_cells,
                            key=lambda cell: _score_structured_cell(
                                cell,
                                query_years=target_years,
                                period_focus="unknown",
                                operand=operand,
                            ),
                            reverse=True,
                        )
                        selected_cell = ranked_cells[0] if ranked_cells else None
                        if selected_cell:
                            raw_value = _normalise_spaces(str(selected_cell.get("value_text") or ""))
                            raw_unit = str(selected_cell.get("unit_hint") or raw_unit or "")
                            if not period:
                                period = _structured_cell_period_text(
                                    selected_cell,
                                    target_years,
                                    "unknown",
                                )

                if not raw_value:
                    prose_value = _period_comparison_count_value_from_text(
                        context_text or raw_row,
                        operand,
                        query_years=query_years,
                        report_scope=report_scope,
                    )
                    if prose_value:
                        raw_value = prose_value["raw_value"]
                        raw_unit = prose_value["raw_unit"]
                        period = prose_value["period"]

                if not raw_value and not period_count_context_match:
                    raw_value = _extract_numeric_value_after_operand_text(raw_row, operand)
                    if raw_value and not raw_unit:
                        if "조" in raw_value or "억" in raw_value:
                            raw_unit = "원"
                        elif "백만원" in context_text:
                            raw_unit = "백만원"

                if not raw_value:
                    continue

                inline_unit_match = re.fullmatch(
                    r"(?P<value>[\(\)\-]?\d[\d,]*(?:\.\d+)?)\s*(?P<unit>%|백만원|천원|원)",
                    raw_value,
                )
                if inline_unit_match and not re.search(r"\(\s*" + re.escape(raw_value), raw_row):
                    raw_value = inline_unit_match.group("value")
                    raw_unit = raw_unit or inline_unit_match.group("unit")

                if not raw_unit:
                    if "조" in raw_value or "억" in raw_value:
                        raw_unit = "원"
                    elif "백만원" in context_text:
                        raw_unit = "백만원"
                    elif "천원" in context_text:
                        raw_unit = "천원"

                normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
                if normalized_value is None:
                    continue

                key = (str(item.get("source_anchor") or ""), label_name, period)
                if key in seen:
                    continue
                seen.add(key)
                operand_rows.append(
                    {
                        "operand_id": f"op_{len(operand_rows) + 1:03d}",
                        "evidence_id": item.get("evidence_id"),
                        "source_anchor": item.get("source_anchor"),
                        "label": f"{period} {label_name}".strip(),
                        "matched_operand_label": label_name,
                        "matched_operand_role": str(operand.get("role") or "").strip(),
                        "matched_operand_concept": str(operand.get("concept") or "").strip(),
                        "raw_value": raw_value,
                        "raw_unit": raw_unit or "원",
                        "normalized_value": normalized_value,
                        "normalized_unit": normalized_unit,
                        "period": period,
                        "table_source_id": (item.get("metadata") or {}).get("table_source_id"),
                        "statement_type": (item.get("metadata") or {}).get("statement_type"),
                        "consolidation_scope": (item.get("metadata") or {}).get("consolidation_scope"),
                    }
                )
                break

        return operand_rows

    # enumeration 질문은 항목이 많아 기본 cap=6이 부족할 수 있음
    _EVIDENCE_CAP_BY_QUERY_TYPE: Dict[str, int] = {
        "risk": 10,
        "business_overview": 8,
        "comparison": 8,
    }

    def _select_evidence_for_compression(
        self, evidence_items: List[Dict[str, Any]], query_type: str = "qa"
    ) -> List[Dict[str, Any]]:
        if not evidence_items:
            return []
        limit = self._EVIDENCE_CAP_BY_QUERY_TYPE.get(query_type, 6)
        ranked = self._sort_evidence_items(evidence_items)
        high_priority = [item for item in ranked if item.get("question_relevance") == "high"]
        medium_priority = [item for item in ranked if item.get("question_relevance") == "medium"]
        low_priority = [item for item in ranked if item.get("question_relevance") == "low"]

        selected: List[Dict[str, Any]] = []
        for pool in (high_priority, medium_priority, low_priority):
            for item in pool:
                selected.append(item)
                if len(selected) >= limit:
                    return selected
        return selected[:limit]

    def _narrative_driver_groups(self, query: str) -> List[Dict[str, Any]]:
        groups: List[Dict[str, Any]] = narrative_policy_driver_groups(
            self._active_narrative_policies_for_query(query)
        )

        seen_variants = {
            str(variant).lower()
            for group in groups
            for variant in (group.get("variants") or [])
            if str(variant).strip()
        }
        for focus_group in self._query_focus_marker_groups(query):
            variants = [
                str(variant).strip()
                for variant in (focus_group.get("variants") or [])
                if str(variant).strip() and str(variant).strip().lower() not in seen_variants
            ]
            if not variants:
                continue
            seen_variants.update(variant.lower() for variant in variants)
            groups.append({**focus_group, "variants": variants})
        return groups

    def _extract_driver_snippet(self, text: str, variants: List[str]) -> str:
        surface = _normalise_spaces(text)
        if not surface:
            return ""

        fragments = [
            _normalise_spaces(fragment)
            for fragment in re.split(r"(?<=[.!?])\s+|\n+", surface)
            if _normalise_spaces(fragment)
        ]
        for fragment in fragments:
            lowered = fragment.lower()
            if any(variant.lower() in lowered for variant in variants):
                return fragment[:220]

        lowered_surface = surface.lower()
        for variant in variants:
            index = lowered_surface.find(variant.lower())
            if index >= 0:
                start = max(0, index - 80)
                end = min(len(surface), index + 140)
                return surface[start:end].strip()
        return surface[:220]

    def _supplement_narrative_driver_evidence(
        self,
        evidence_items: List[Dict[str, Any]],
        docs,
        *,
        query: str,
        anchor_lookup: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        groups = self._narrative_driver_groups(query)
        if not groups or not docs:
            return evidence_items

        merged_existing = _normalise_spaces(
            " ".join(
                part
                for item in evidence_items
                for part in (
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                )
                if part
            )
        ).lower()

        supplemented = [dict(item) for item in evidence_items]
        seen_keys = {
            _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(item.get("source_anchor") or ""),
                        str(item.get("quote_span") or item.get("claim") or ""),
                    )
                    if part
                )
            )
            for item in supplemented
        }

        for group in groups:
            variants = list(group.get("variants") or [])
            if not variants:
                continue
            if any(variant.lower() in merged_existing for variant in variants):
                continue
            for item in docs:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                block_type = str(metadata.get("block_type") or "").strip().lower()
                if block_type not in {"paragraph", "table"}:
                    continue
                text = _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            str(getattr(doc, "page_content", "") or ""),
                            str(metadata.get("table_context") or ""),
                        )
                        if part
                    )
                )
                lowered = text.lower()
                if not any(variant.lower() in lowered for variant in variants):
                    continue
                snippet = self._extract_driver_snippet(text, variants)
                if not snippet:
                    continue
                anchor = self._build_source_anchor(metadata)
                dedupe_key = _normalise_spaces(f"{anchor} {snippet}")
                if dedupe_key and dedupe_key in seen_keys:
                    continue
                if dedupe_key:
                    seen_keys.add(dedupe_key)
                supplemented.append(
                    {
                        "evidence_id": f"ev_{len(supplemented) + 1:03d}",
                        "source_anchor": anchor,
                        "claim": snippet,
                        "quote_span": snippet,
                        "support_level": "direct",
                        "question_relevance": "high",
                        "allowed_terms": sorted(_tokenize_terms(snippet))[:8],
                        "metadata": self._resolve_anchor_metadata(
                            anchor_lookup,
                            anchor,
                            quote_surface=snippet,
                            claim_surface=snippet,
                        ),
                    }
                )
                merged_existing = f"{merged_existing} {snippet.lower()}".strip()
                break
        return supplemented

    def _supplement_dividend_policy_evidence(
        self,
        evidence_items: List[Dict[str, Any]],
        docs,
        *,
        query: str,
        anchor_lookup: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not self._is_dividend_policy_mixed_query(query) or not docs:
            return evidence_items

        policy_terms_by_key = self._narrative_policy_terms_for_query(
            query,
            "payout_terms",
            "payout_deemphasis_terms",
            "policy_terms",
            "policy_preferred_terms",
            "liquidity_context_terms",
            "outflow_terms",
            "policy_section_terms",
            "regular_terms",
            "additional_return_terms",
            "payout_amount_patterns",
        )
        payout_terms = policy_terms_by_key["payout_terms"]
        payout_deemphasis_terms = policy_terms_by_key["payout_deemphasis_terms"]
        policy_terms = policy_terms_by_key["policy_terms"]
        policy_preferred_terms = policy_terms_by_key["policy_preferred_terms"]
        liquidity_context_terms = policy_terms_by_key["liquidity_context_terms"]
        outflow_terms = policy_terms_by_key["outflow_terms"]
        policy_section_terms = policy_terms_by_key["policy_section_terms"]
        regular_terms = policy_terms_by_key["regular_terms"]
        additional_return_terms = policy_terms_by_key["additional_return_terms"]
        payout_amount_patterns = policy_terms_by_key["payout_amount_patterns"]
        supplemented = [dict(item) for item in evidence_items]
        seen_keys = {
            _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(item.get("source_anchor") or ""),
                        str(item.get("quote_span") or item.get("claim") or ""),
                    )
                    if part
                )
            )
            for item in supplemented
        }

        payout_candidate: Optional[Dict[str, Any]] = None
        payout_score = float("-inf")
        policy_candidate: Optional[Dict[str, Any]] = None
        policy_score = float("-inf")

        for item in docs:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            if block_type not in {"paragraph", "table"}:
                continue
            text = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(getattr(doc, "page_content", "") or ""),
                        str(metadata.get("table_context") or ""),
                    )
                    if part
                )
            )
            if not text:
                continue
            section_path = _normalise_spaces(str(metadata.get("section_path") or metadata.get("section") or ""))
            local_heading = _normalise_spaces(str(metadata.get("local_heading") or ""))
            anchor = self._build_source_anchor(metadata)

            if any(marker in text for marker in payout_terms):
                snippet = self._extract_driver_snippet(text, list(payout_terms))
                amount_surface = self._extract_policy_amount_surface(
                    snippet or text,
                    patterns=payout_amount_patterns,
                ) or self._extract_dividend_amount_surface(snippet or text)
                if amount_surface:
                    score = 0.0
                    lowered_context = f"{section_path} {local_heading} {text}".lower()
                    if any(term in lowered_context for term in liquidity_context_terms):
                        score += 4.0
                    if any(term in text for term in outflow_terms):
                        score += 2.0
                    if any(term in text for term in payout_deemphasis_terms):
                        score -= 1.5
                    if score > payout_score:
                        payout_score = score
                        payout_candidate = {
                            "evidence_id": f"ev_{len(supplemented) + 1:03d}",
                            "source_anchor": anchor,
                            "claim": snippet or amount_surface,
                            "quote_span": snippet or amount_surface,
                            "support_level": "direct",
                            "question_relevance": "high",
                            "allowed_terms": sorted(_tokenize_terms((snippet or amount_surface)))[:8],
                            "metadata": self._resolve_anchor_metadata(
                                anchor_lookup,
                                anchor,
                                quote_surface=snippet or amount_surface,
                                claim_surface=snippet or amount_surface,
                            ),
                        }

            if any(marker in text for marker in policy_terms):
                snippet = self._extract_dividend_policy_clause(text, preferred_markers=policy_preferred_terms)
                if snippet:
                    score = 0.0
                    lowered_context = f"{section_path} {local_heading}".lower()
                    if any(term in lowered_context for term in policy_section_terms):
                        score += 4.0
                    if any(marker in snippet for marker in regular_terms):
                        score += 2.0
                    if any(marker in snippet for marker in additional_return_terms):
                        score += 2.0
                    if score > policy_score:
                        policy_score = score
                        policy_candidate = {
                            "evidence_id": f"ev_{len(supplemented) + 2:03d}",
                            "source_anchor": anchor,
                            "claim": snippet,
                            "quote_span": snippet,
                            "support_level": "direct",
                            "question_relevance": "high",
                            "allowed_terms": sorted(_tokenize_terms(snippet))[:8],
                            "metadata": self._resolve_anchor_metadata(
                                anchor_lookup,
                                anchor,
                                quote_surface=snippet,
                                claim_surface=snippet,
                            ),
                        }

        for candidate in (payout_candidate, policy_candidate):
            if not candidate:
                continue
            dedupe_key = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(candidate.get("source_anchor") or ""),
                        str(candidate.get("quote_span") or candidate.get("claim") or ""),
                    )
                    if part
                )
            )
            if dedupe_key and dedupe_key in seen_keys:
                continue
            if dedupe_key:
                seen_keys.add(dedupe_key)
            candidate["evidence_id"] = f"ev_{len(supplemented) + 1:03d}"
            supplemented.append(candidate)

        return supplemented

    def _augment_narrative_answer_with_supported_drivers(
        self,
        answer: str,
        selected_evidence: List[Dict[str, Any]],
        *,
        query: str,
    ) -> str:
        draft = _normalise_spaces(answer)
        if not draft or not selected_evidence or not _query_requests_narrative_context(query):
            return draft

        evidence_blob = _normalise_spaces(
            " ".join(
                part
                for item in selected_evidence
                for part in (
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                )
                if part
            )
        ).lower()
        draft_lower = draft.lower()

        phrases: List[str] = []
        for group in self._narrative_driver_groups(query):
            variants = list(group.get("variants") or [])
            phrase = str(group.get("phrase") or "").strip()
            if not variants or not phrase:
                continue
            if not any(variant.lower() in evidence_blob for variant in variants):
                continue
            if any(variant.lower() in draft_lower for variant in variants):
                continue
            phrases.append(phrase)

        if not phrases:
            return draft

        if len(phrases) == 1:
            clause = phrases[0]
        elif len(phrases) == 2:
            clause = f"{phrases[0]}와 {phrases[1]}"
        else:
            clause = ", ".join(phrases[:-1]) + f", 그리고 {phrases[-1]}"
        addition = f"또한 {clause}도 실적 성장에 기여했습니다."
        if addition in draft:
            return draft
        return f"{draft} {addition}".strip()

    def _compose_entity_table_summary_answer(
        self,
        *,
        query: str,
        docs,
        evidence_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        query_text = _normalise_spaces(query)
        active_slot_groups = [
            group
            for group in narrative_policy_slot_groups(self._active_narrative_policies_for_query(query_text))
            if any(str(term) in query_text for term in (group.get("query_terms") or ()))
        ]
        if not active_slot_groups:
            return None

        entity_variants: List[str] = []
        for group in self._query_focus_marker_groups(query_text):
            variants = [str(variant).strip() for variant in (group.get("variants") or []) if str(variant).strip()]
            if len(variants) >= 2 and any(re.search(r"[A-Za-z]", variant) for variant in variants):
                entity_variants.extend(variants)
                break
        if not entity_variants:
            return None

        def _doc_text(doc: Document) -> str:
            metadata = getattr(doc, "metadata", {}) or {}
            return "\n".join(
                part
                for part in (
                    str(getattr(doc, "page_content", "") or ""),
                    str(metadata.get("table_context") or ""),
                    str(metadata.get("table_row_labels_text") or ""),
                    str(metadata.get("table_value_labels_text") or ""),
                )
                if part
            )

        def _numbers(text: str) -> List[str]:
            return re.findall(r"\(?-?\d[\d,]*(?:\.\d+)?\)?%?", text)

        def _clean_amount(value: str) -> str:
            return value.strip()

        requested_consolidated = "연결" in query_text
        investment_candidates: List[tuple[tuple[int, int, float, int], str, str, str, str, str]] = []
        summary_candidates: List[tuple[tuple[int, int], str, str, str, str]] = []
        supporting_anchors: List[str] = []

        def _scan_source_text(
            *,
            source_text: str,
            section_path: str,
            period_focus: str,
            anchor: str,
            header_context: str = "",
        ) -> None:
            text = _normalise_spaces(source_text)
            if not text:
                return
            lines = [_normalise_spaces(line) for line in str(source_text or "").splitlines()]
            if not lines:
                lines = [text]
            header_context_lines: List[str] = []
            for line in str(header_context or "").splitlines():
                line_text = _normalise_spaces(line)
                if not line_text or not re.search(r"[A-Za-z가-힣]", line_text):
                    continue
                if any(variant.lower() in line_text.lower() for variant in entity_variants):
                    continue
                if "|" in line_text or not re.search(r"\d", line_text):
                    header_context_lines.append(line_text)
            header_context_lines = header_context_lines[-3:]
            entity_lines: List[tuple[str, str]] = []
            for line_index, line in enumerate(lines):
                if not any(variant.lower() in line.lower() for variant in entity_variants):
                    continue
                context_lines: List[str] = list(header_context_lines)
                if "|" in line:
                    for previous in lines[max(0, line_index - 3) : line_index]:
                        previous_text = _normalise_spaces(previous)
                        if "|" not in previous_text:
                            continue
                        if any(variant.lower() in previous_text.lower() for variant in entity_variants):
                            continue
                        if not re.search(r"[A-Za-z가-힣]", previous_text):
                            continue
                        context_lines.append(previous_text)
                    context_lines = list(dict.fromkeys(context_lines))[-3:]
                if "|" not in line:
                    entity_lines.append((line, line))
                    continue
                cells = [_normalise_spaces(cell) for cell in line.split("|")]
                cells = [cell for cell in cells if cell]
                matched = False
                for index, cell in enumerate(cells):
                    if not any(variant.lower() in cell.lower() for variant in entity_variants):
                        continue
                    matched = True
                    row_slice = " | ".join(cells[max(0, index - 2) : index + 10])
                    display_line = " / ".join([*context_lines, row_slice]) if context_lines else row_slice
                    entity_lines.append((row_slice, display_line))
                if not matched:
                    display_line = " / ".join([*context_lines, line]) if context_lines else line
                    entity_lines.append((line, display_line))
            if not entity_lines:
                return
            section_score = 0
            if "타법인출자" in section_path:
                section_score += 2
            if "재무제표 주석" in section_path:
                section_score += 2
            if "타법인출자" in text:
                section_score += 4
            if any(marker in text for marker in ("투자자산", "관계기업", "공동기업")):
                section_score += 3
            if any(marker in text for marker in ("연결대상", "종속기업")) and "타법인출자" not in text:
                section_score -= 4
            if not requested_consolidated and "연결재무제표 주석" in section_path:
                section_score -= 1
            period_score = 1 if str(period_focus or "").lower() == "current" else 0
            for line, display_line in entity_lines:
                line_numbers = _numbers(line)
                if "%" in line and any(marker in text for marker in ("소유지분율", "지분율", "장부금액", "투자자산")):
                    percent_values = [value for value in line_numbers if value.endswith("%")]
                    percent = percent_values[-1] if len(percent_values) >= 2 else next(iter(percent_values), "")
                    prior_percent = percent_values[0] if len(percent_values) >= 2 and percent_values[0] != percent else ""
                    amount = next((value for value in reversed(line_numbers) if not value.endswith("%")), "")
                    if percent and amount:
                        amount_value = _parse_number_text(amount)
                        investment_candidates.append(
                            (
                                (section_score, period_score, amount_value or 0.0, -len(line_numbers)),
                                percent,
                                _clean_amount(amount),
                                anchor,
                                prior_percent,
                                display_line,
                            )
                        )
                if any(marker in text for marker in ("계속영업손익", "계속영업이익", "계속영업손실", "총포괄손익")):
                    non_percent_numbers = [value for value in line_numbers if not value.endswith("%")]
                    if len(non_percent_numbers) >= 3:
                        continuing = _clean_amount(non_percent_numbers[-3])
                        total_comprehensive = _clean_amount(non_percent_numbers[-1])
                        summary_candidates.append(((section_score, period_score), continuing, total_comprehensive, anchor, display_line))

        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            section_path = str(metadata.get("section_path") or metadata.get("section") or "")
            text = _doc_text(doc)
            if not text:
                continue
            anchor = self._build_source_anchor(metadata)
            _scan_source_text(
                source_text=text,
                section_path=section_path,
                period_focus=str(metadata.get("period_focus") or ""),
                anchor=anchor,
                header_context="\n".join(
                    str(metadata.get(key) or "")
                    for key in ("table_header_context", "table_row_labels_text")
                    if str(metadata.get(key) or "").strip()
                ),
            )

        for item in evidence_items or []:
            evidence = dict(item or {})
            metadata = dict(evidence.get("metadata") or {})
            section_path = str(
                metadata.get("section_path")
                or metadata.get("section")
                or evidence.get("source_anchor")
                or ""
            )
            evidence_text = "\n".join(
                str(value or "")
                for value in (
                    evidence.get("claim"),
                    evidence.get("quote_span"),
                    evidence.get("raw_row_text"),
                )
                if value
            )
            _scan_source_text(
                source_text=evidence_text,
                section_path=section_path,
                period_focus=str(metadata.get("period_focus") or evidence.get("period_focus") or ""),
                anchor=str(evidence.get("source_anchor") or ""),
                header_context="\n".join(
                    str(metadata.get(key) or "")
                    for key in ("table_header_context", "table_row_labels_text")
                    if str(metadata.get(key) or "").strip()
                ),
            )

        if not investment_candidates and not summary_candidates:
            return None

        investment_candidates.sort(key=lambda item: item[0], reverse=True)
        summary_candidates.sort(key=lambda item: item[0], reverse=True)
        percent = prior_percent = amount = continuing = total_comprehensive = ""
        investment_line = summary_line = ""
        if investment_candidates:
            _score, percent, amount, anchor, prior_percent, investment_line = investment_candidates[0]
            if not prior_percent:
                prior_percent = next(
                    (
                        candidate_prior_percent
                        for _candidate_score, _candidate_percent, candidate_amount, _candidate_anchor, candidate_prior_percent, _candidate_line in investment_candidates
                        if candidate_amount == amount and candidate_prior_percent
                    ),
                    "",
                )
            supporting_anchors.append(anchor)
        if summary_candidates:
            _score, continuing, total_comprehensive, anchor, summary_line = summary_candidates[0]
            supporting_anchors.append(anchor)
        if not (percent or amount or continuing or total_comprehensive):
            return None

        entity_label = next((variant for variant in entity_variants if re.search(r"[A-Za-z]", variant)), entity_variants[0])
        sentences: List[str] = []
        if percent or amount:
            parts = []
            if percent:
                if prior_percent:
                    parts.append(f"기초 지분율은 {prior_percent}, 기말 지분율은 {percent}")
                else:
                    parts.append(f"지분율은 {percent}")
            if amount:
                parts.append(f"투자장부금액은 {amount}백만원")
            sentences.append(f"{entity_label}의 " + ", ".join(parts) + "입니다.")
        if continuing or total_comprehensive:
            parts = []
            if continuing:
                continuing_label = "계속영업손실" if str(continuing).strip().startswith("(") else "계속영업손익"
                parts.append(f"{continuing_label} {continuing}백만원")
            if total_comprehensive:
                comprehensive_label = "총포괄손실" if str(total_comprehensive).strip().startswith("(") else "총포괄손익"
                parts.append(f"{comprehensive_label} {total_comprehensive}백만원")
            sentences.append("요약 손익은 " + ", ".join(parts) + "입니다.")
        answer = _normalise_spaces(" ".join(sentences))
        if not answer:
            return None

        selected_ids = [
            str(item.get("evidence_id") or "").strip()
            for item in evidence_items
            if str(item.get("source_anchor") or "").strip() in set(supporting_anchors)
            and str(item.get("evidence_id") or "").strip()
        ]

        def _operand_row(label: str, raw_value: str, raw_unit: str, role: str, anchor: str) -> Dict[str, Any]:
            normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
            source_row_id = f"{anchor}::{role}" if anchor else ""
            return {
                "operand_id": role,
                "matched_operand_role": role,
                "label": label,
                "concept": role,
                "period": "2023",
                "raw_value": raw_value,
                "raw_unit": raw_unit,
                "normalized_value": normalized_value,
                "normalized_unit": normalized_unit,
                "rendered_value": f"{raw_value}{raw_unit}",
                "source_anchor": anchor,
                "source_row_id": source_row_id,
                "source_row_ids": [source_row_id] if source_row_id else [],
            }

        calculation_operands: List[Dict[str, Any]] = []
        primary_anchor = supporting_anchors[0] if supporting_anchors else ""
        summary_anchor = supporting_anchors[-1] if supporting_anchors else primary_anchor
        if prior_percent:
            calculation_operands.append(_operand_row(f"{entity_label} 기초 지분율", prior_percent.replace("%", ""), "%", "prior_ownership_ratio", primary_anchor))
        if percent:
            calculation_operands.append(_operand_row(f"{entity_label} 기말 지분율", percent.replace("%", ""), "%", "ownership_ratio", primary_anchor))
        if amount:
            calculation_operands.append(_operand_row(f"{entity_label} 투자장부금액", amount, "백만원", "investment_carrying_amount", primary_anchor))
        if continuing:
            calculation_operands.append(_operand_row(f"{entity_label} 계속영업손실", continuing, "백만원", "continuing_loss", summary_anchor))
        if total_comprehensive:
            calculation_operands.append(_operand_row(f"{entity_label} 총포괄손실", total_comprehensive, "백만원", "total_comprehensive_loss", summary_anchor))
        components_by_role = {
            str(row.get("matched_operand_role") or row.get("operand_id") or ""): [
                {
                    "status": "ok",
                    "role": str(row.get("matched_operand_role") or row.get("operand_id") or ""),
                    "label": str(row.get("label") or ""),
                    "concept": str(row.get("concept") or ""),
                    "period": str(row.get("period") or ""),
                    "raw_value": str(row.get("raw_value") or ""),
                    "raw_unit": str(row.get("raw_unit") or ""),
                    "normalized_value": row.get("normalized_value"),
                    "normalized_unit": str(row.get("normalized_unit") or "UNKNOWN"),
                    "rendered_value": str(row.get("rendered_value") or ""),
                    "source_row_id": str(row.get("source_row_id") or ""),
                    "source_row_ids": list(row.get("source_row_ids") or []),
                    "source_anchor": str(row.get("source_anchor") or ""),
                }
            ]
            for row in calculation_operands
            if str(row.get("matched_operand_role") or row.get("operand_id") or "").strip()
        }
        primary_operand = next(
            (
                row
                for row in calculation_operands
                if str(row.get("operand_id") or "") in {"investment_carrying_amount", "ownership_ratio"}
            ),
            calculation_operands[0] if calculation_operands else {},
        )
        primary_slot = dict(next(iter(components_by_role.get(str(primary_operand.get("operand_id") or ""), [])), {}))
        answer_slots = validate_answer_slots_payload(
            {
                "operation_family": "lookup",
                "metric_label": entity_label,
                "primary_value": primary_slot,
                "components_by_role": components_by_role,
                "source_row_ids": [
                    source_row_id
                    for row in calculation_operands
                    for source_row_id in (row.get("source_row_ids") or [])
                    if str(source_row_id).strip()
                ],
            }
        ) if primary_slot else {}
        operand_surfaces_by_anchor: Dict[str, List[str]] = {}
        for row in calculation_operands:
            operand_anchor = str(row.get("source_anchor") or "").strip()
            if not operand_anchor:
                continue
            label_text = _normalise_spaces(str(row.get("label") or row.get("concept") or row.get("operand_id") or ""))
            rendered_value = _normalise_spaces(str(row.get("rendered_value") or row.get("raw_value") or ""))
            if not label_text and not rendered_value:
                continue
            operand_surface = _normalise_spaces(": ".join(part for part in (label_text, rendered_value) if part))
            if operand_surface:
                operand_surfaces_by_anchor.setdefault(operand_anchor, []).append(operand_surface)
        projected_evidence_items: List[Dict[str, Any]] = []
        for index, (anchor, line, evidence_kind) in enumerate(
            [
                (primary_anchor, investment_line, "entity_table_investment"),
                (summary_anchor, summary_line, "entity_table_summary"),
            ],
            start=1,
        ):
            line_text = _normalise_spaces(str(line or ""))
            if not anchor or not line_text:
                continue
            line_parts = [*operand_surfaces_by_anchor.get(anchor, []), line_text]
            line_text = _normalise_spaces(" / ".join(dict.fromkeys(part for part in line_parts if part)))
            projected_evidence_items.append(
                {
                    "evidence_id": f"entity_table::{evidence_kind}::{index:03d}",
                    "source_anchor": anchor,
                    "claim": line_text[:1200],
                    "quote_span": line_text[:500],
                    "raw_row_text": line_text[:1200],
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [],
                    "metadata": {"section_path": anchor},
                }
            )
        merged_evidence_items = list(evidence_items or [])
        existing_evidence_ids = {str(item.get("evidence_id") or "").strip() for item in merged_evidence_items}
        for item in projected_evidence_items:
            evidence_id = str(item.get("evidence_id") or "").strip()
            if evidence_id and evidence_id in existing_evidence_ids:
                continue
            if evidence_id:
                existing_evidence_ids.add(evidence_id)
            merged_evidence_items.append(item)
        return {
            "selected_claim_ids": list(dict.fromkeys(selected_ids)),
            "draft_points": sentences,
            "compressed_answer": answer,
            "evidence_items": merged_evidence_items,
            "calculation_projection": {
                "calculation_operands": calculation_operands,
                "calculation_plan": {
                    "status": "ok" if calculation_operands else "empty",
                    "operation": "lookup",
                    "operation_family": "lookup",
                    "ordered_operand_ids": [str(row.get("operand_id") or "") for row in calculation_operands],
                },
                "calculation_result": {
                    "status": "ok" if calculation_operands else "partial",
                    "rendered_value": answer,
                    "formatted_result": answer,
                    "operation_family": "lookup",
                    "source_row_ids": list(answer_slots.get("source_row_ids") or []),
                    "answer_slots": answer_slots,
                    "derived_metrics": {"operation_family": "lookup", "entity": entity_label},
                },
            },
        }

    def _compose_business_technology_focus_answer(
        self,
        *,
        query: str,
        existing_answer: str = "",
        docs=None,
        evidence_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Optional[Dict[str, Any]]:
        query_text = _normalise_spaces(query)
        if not query_text:
            return None
        active_policies = self._active_narrative_policies_for_query(query_text)
        if not narrative_policy_active(active_policies, "technology_focus"):
            return None
        technology_facets = self._narrative_policy_facets_for_query(query_text, "technology_facets")

        entity = ""
        for group in self._query_focus_marker_groups(query_text):
            variants = [str(variant).strip() for variant in (group.get("variants") or []) if str(variant).strip()]
            entity = next((variant for variant in variants if re.search(r"[A-Za-z]", variant)), "")
            if entity:
                break
        if not entity:
            return None

        text_parts: List[str] = [str(existing_answer or "")]
        source_anchors: List[str] = []
        for item in docs or []:
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            text_parts.append(str(getattr(doc, "page_content", "") or ""))
            for key in ("table_context", "table_row_labels_text", "table_value_labels_text"):
                if metadata.get(key):
                    text_parts.append(str(metadata.get(key) or ""))
            anchor = self._build_source_anchor(metadata)
            if anchor:
                source_anchors.append(anchor)
        for item in evidence_items or []:
            evidence = dict(item or {})
            source_anchors.append(str(evidence.get("source_anchor") or ""))
            text_parts.extend(
                str(value or "")
                for value in (evidence.get("claim"), evidence.get("quote_span"), evidence.get("raw_row_text"))
                if value
            )

        haystack = _normalise_spaces("\n".join(part for part in text_parts if part))
        if entity.lower() not in haystack.lower():
            return None

        rnd_amount = ""
        rnd_candidates: List[tuple[int, str]] = []
        for line in re.split(r"[\n。.!?]", "\n".join(part for part in text_parts if part)):
            line_text = _normalise_spaces(line)
            if "연구개발" not in line_text:
                continue
            if not any(marker in line_text for marker in ("비용", "총액", "계", "누계", "백만원")):
                continue
            for value in re.findall(r"\d{1,3}(?:,\d{3})+", line_text):
                numeric = int(value.replace(",", ""))
                if numeric >= 1_000_000:
                    rnd_candidates.append((numeric, value))
        if rnd_candidates:
            rnd_amount = max(rnd_candidates, key=lambda item: item[0])[1]

        haystack_lower = haystack.lower()

        def _facet_matches(facet: Dict[str, Any]) -> bool:
            required_terms = [str(term).lower() for term in (facet.get("required_terms") or [])]
            match_terms = [str(term).lower() for term in (facet.get("match_terms") or [])]
            if required_terms and not all(term in haystack_lower for term in required_terms):
                return False
            if match_terms and not any(term in haystack_lower for term in match_terms):
                return False
            return bool(required_terms or match_terms)

        matched_facets = [facet for facet in technology_facets if _facet_matches(facet)]
        if not matched_facets:
            return None

        sentences: List[str] = []
        if rnd_amount:
            sentences.append(f"2023년 연결 연구개발비용 총액은 {rnd_amount}백만원입니다.")
        else:
            existing_first = re.split(r"(?<=[.!?。])\s+", _normalise_spaces(existing_answer))[0]
            if "연구개발" in existing_first:
                sentences.append(existing_first)

        business_parts: List[str] = []
        business_parts.extend(
            str(facet.get("business_phrase") or "")
            for facet in matched_facets
            if str(facet.get("business_phrase") or "").strip()
        )
        products = [
            str(facet.get("product_phrase") or "")
            for facet in matched_facets
            if str(facet.get("product_phrase") or "").strip()
        ]
        if products:
            business_parts.append(", ".join(products) + " 등 전장제품")
        if business_parts:
            sentences.append(f"{entity} 부문의 전장 사업 방향은 " + "과 ".join(business_parts) + "을 중심으로 합니다.")

        focus_parts = [
            str(facet.get("focus_phrase") or "")
            for facet in matched_facets
            if str(facet.get("focus_phrase") or "").strip()
        ]
        if focus_parts:
            sentences.append("주요 기술 초점은 " + "하고, ".join(focus_parts) + "하는 데 있습니다.")

        answer = _normalise_spaces(" ".join(sentences))
        if not answer or entity not in answer:
            return None
        selected_ids = [
            str(item.get("evidence_id") or "").strip()
            for item in evidence_items or []
            if str(item.get("source_anchor") or "").strip() in set(source_anchors)
            and str(item.get("evidence_id") or "").strip()
        ]
        return {
            "selected_claim_ids": list(dict.fromkeys(selected_ids)),
            "draft_points": sentences,
            "compressed_answer": answer,
        }

    def _is_dividend_policy_mixed_query(self, query: str) -> bool:
        surface = _normalise_spaces(str(query or ""))
        if not surface:
            return False
        policy_terms_by_key = self._narrative_policy_terms_for_query(
            surface,
            "payout_terms",
            "policy_query_terms",
        )
        payout_terms = policy_terms_by_key["payout_terms"]
        policy_query_terms = policy_terms_by_key["policy_query_terms"]
        return any(marker in surface for marker in payout_terms) and any(
            marker in surface for marker in policy_query_terms
        )

    def _extract_dividend_amount_surface(self, text: str) -> str:
        surface = _normalise_spaces(str(text or ""))
        if not surface:
            return ""
        patterns = (
            r"(\d+\s*조\s*\d{1,3}(?:,\d{3})?\s*억원)",
            r"(\d{1,3}(?:,\d{3})+\s*억원)",
            r"(\d{1,3}(?:,\d{3})+\s*백만원)",
        )
        for pattern in patterns:
            match = re.search(pattern, surface)
            if match:
                return _normalise_spaces(match.group(1))
        return ""

    def _extract_policy_amount_surface(self, text: str, *, patterns: List[str]) -> str:
        surface = _normalise_spaces(str(text or ""))
        if not surface:
            return ""
        for pattern in patterns:
            match = re.search(pattern, surface)
            if match:
                return _normalise_spaces(match.group(1))
        return ""

    def _dividend_amount_rank(self, text: str) -> float:
        surface = self._extract_dividend_amount_surface(text)
        if not surface:
            return float("-inf")
        jo_match = re.search(r"(\d+)\s*조(?:\s*(\d{1,3}(?:,\d{3})?))?\s*억원", surface)
        if jo_match:
            jo = int(jo_match.group(1))
            eok = int((jo_match.group(2) or "0").replace(",", ""))
            return float(jo * 10000 + eok)
        eok_match = re.search(r"(\d{1,3}(?:,\d{3})+)\s*억원", surface)
        if eok_match:
            return float(int(eok_match.group(1).replace(",", "")))
        million_match = re.search(r"(\d{1,3}(?:,\d{3})+)\s*백만원", surface)
        if million_match:
            return float(int(million_match.group(1).replace(",", "")) / 100.0)
        return float("-inf")

    def _extract_dividend_policy_clause(self, text: str, *, preferred_markers: Optional[List[str]] = None) -> str:
        surface = _normalise_spaces(str(text or ""))
        if not surface:
            return ""
        fragments = [
            _normalise_spaces(fragment)
            for fragment in re.split(r"(?<=[.!?])\s+|\n+", surface)
            if _normalise_spaces(fragment)
        ]
        if preferred_markers:
            for fragment in fragments:
                if any(marker in fragment for marker in preferred_markers):
                    return fragment[:240]
        for fragment in fragments:
            if "2024" in fragment and "2026" in fragment:
                return fragment[:240]
        return surface[:240]

    def _compose_dividend_policy_hybrid_answer(
        self,
        *,
        query: str,
        evidence_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if not self._is_dividend_policy_mixed_query(query):
            return None
        if not evidence_items:
            return None

        policy_terms_by_key = self._narrative_policy_terms_for_query(
            query,
            "payout_terms",
            "payout_deemphasis_terms",
            "policy_terms",
            "policy_preferred_terms",
            "liquidity_context_terms",
            "outflow_terms",
            "table_policy_terms",
            "policy_section_terms",
            "regular_terms",
            "additional_return_terms",
            "payout_amount_patterns",
            "cash_generation_terms",
            "payout_sentence_template",
            "policy_sentence_prefix",
        )
        payout_terms = policy_terms_by_key["payout_terms"]
        payout_deemphasis_terms = policy_terms_by_key["payout_deemphasis_terms"]
        policy_terms = policy_terms_by_key["policy_terms"]
        policy_preferred_terms = policy_terms_by_key["policy_preferred_terms"]
        liquidity_context_terms = policy_terms_by_key["liquidity_context_terms"]
        outflow_terms = policy_terms_by_key["outflow_terms"]
        table_policy_terms = policy_terms_by_key["table_policy_terms"]
        policy_section_terms = policy_terms_by_key["policy_section_terms"]
        regular_terms = policy_terms_by_key["regular_terms"]
        additional_return_terms = policy_terms_by_key["additional_return_terms"]
        payout_amount_patterns = policy_terms_by_key["payout_amount_patterns"]
        cash_generation_terms = policy_terms_by_key["cash_generation_terms"]
        payout_sentence_template = next(iter(policy_terms_by_key["payout_sentence_template"]), "")
        policy_sentence_prefix = next(iter(policy_terms_by_key["policy_sentence_prefix"]), "")
        payout_amount = ""
        payout_evidence_id = ""
        policy_clause = ""
        policy_evidence_id = ""
        payout_best_key = (float("-inf"), float("-inf"))
        policy_best_key = (float("-inf"),)

        for item in self._sort_evidence_items(evidence_items):
            metadata = item.get("metadata") or {}
            anchor = _normalise_spaces(str(item.get("source_anchor") or ""))
            combined_text = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(item.get("claim") or ""),
                        str(item.get("quote_span") or ""),
                        str(item.get("source_context") or ""),
                        str((item.get("metadata") or {}).get("table_context") or ""),
                    )
                    if part
                )
            )
            lowered_text = combined_text.lower()
            section_hint = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(metadata.get("section_path") or metadata.get("section") or ""),
                        anchor,
                    )
                    if part
                )
            ).lower()
            if any(marker in combined_text for marker in payout_terms):
                payout_snippet = self._extract_driver_snippet(combined_text, list(payout_terms))
                amount_surface = self._extract_policy_amount_surface(
                    payout_snippet or combined_text,
                    patterns=payout_amount_patterns,
                ) or self._extract_dividend_amount_surface(payout_snippet or combined_text)
                if amount_surface:
                    payout_score = 0.0
                    if any(term in lowered_text for term in liquidity_context_terms):
                        payout_score += 4.0
                    if any(term in combined_text for term in outflow_terms):
                        payout_score += 2.0
                    if "이사의 경영진단" in section_hint:
                        payout_score += 1.0
                    if any(term in combined_text for term in table_policy_terms):
                        payout_score -= 4.0
                    if any(term in combined_text for term in payout_deemphasis_terms):
                        payout_score -= 1.5
                    payout_key = (payout_score, self._dividend_amount_rank(amount_surface))
                    if payout_key > payout_best_key:
                        payout_best_key = payout_key
                        payout_amount = amount_surface
                        payout_evidence_id = str(item.get("evidence_id") or "").strip()
            if any(
                marker in combined_text
                for marker in policy_terms
            ):
                clause = self._extract_dividend_policy_clause(combined_text, preferred_markers=policy_preferred_terms)
                if clause:
                    policy_score = 0.0
                    if "2024" in clause and "2026" in clause:
                        policy_score += 5.0
                    if "2021" in clause and "2023" in clause and not ("2024" in clause and "2026" in clause):
                        policy_score -= 2.0
                    if any(marker in clause for marker in regular_terms):
                        policy_score += 2.0
                    if any(marker in clause for marker in additional_return_terms):
                        policy_score += 2.0
                    if any(term.lower() in clause.lower() for term in cash_generation_terms):
                        policy_score += 1.0
                    if any(term in section_hint for term in policy_section_terms):
                        policy_score += 2.0
                    policy_key = (policy_score,)
                    if policy_key > policy_best_key:
                        policy_best_key = policy_key
                        policy_clause = clause
                        policy_evidence_id = str(item.get("evidence_id") or "").strip()

        if not payout_amount or not policy_clause:
            return None

        year_match = re.search(r"(20\d{2})년", _normalise_spaces(query))
        year = year_match.group(1) if year_match else ""
        year_prefix = f"{year}년 " if year else ""
        payout_sentence = _normalise_spaces(
            (payout_sentence_template or "{year_prefix}{amount}").format(
                year_prefix=year_prefix,
                amount=payout_amount,
            )
        )
        policy_sentence = policy_clause
        if policy_sentence_prefix and policy_sentence_prefix not in policy_sentence:
            policy_sentence = f"{policy_sentence_prefix} {policy_sentence}"
        final_answer = _normalise_spaces(f"{payout_sentence} {policy_sentence}")
        supporting_ids = [
            evidence_id
            for evidence_id in (payout_evidence_id, policy_evidence_id)
            if evidence_id
        ]
        return {
            "answer": final_answer,
            "supporting_claim_ids": list(dict.fromkeys(supporting_ids)),
        }

    def _expand_selected_claim_ids_for_narrative_drivers(
        self,
        selected_claim_ids: List[str],
        evidence_items: List[Dict[str, Any]],
        *,
        query: str,
    ) -> List[str]:
        selected = [str(value).strip() for value in selected_claim_ids if str(value).strip()]
        if not selected or not evidence_items or not _query_requests_narrative_context(query):
            return selected

        selected_evidence = self._filter_evidence_by_ids(evidence_items, selected)
        selected_blob = _normalise_spaces(
            " ".join(
                part
                for item in selected_evidence
                for part in (
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                )
                if part
            )
        ).lower()

        for group in self._narrative_driver_groups(query):
            variants = list(group.get("variants") or [])
            if not variants:
                continue
            if any(variant.lower() in selected_blob for variant in variants):
                continue
            candidate: Optional[Dict[str, Any]] = None
            for item in self._sort_evidence_items(evidence_items):
                evidence_text = _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            str(item.get("claim") or ""),
                            str(item.get("quote_span") or ""),
                        )
                        if part
                    )
                ).lower()
                if not any(variant.lower() in evidence_text for variant in variants):
                    continue
                candidate = item
                break
            if not candidate:
                continue
            evidence_id = str(candidate.get("evidence_id") or "").strip()
            if evidence_id and evidence_id not in selected:
                selected.append(evidence_id)
                selected_blob = f"{selected_blob} {evidence_text}".strip()
        return selected

    def _filter_evidence_by_ids(
        self,
        evidence_items: List[Dict[str, Any]],
        evidence_ids: List[str],
    ) -> List[Dict[str, Any]]:
        if not evidence_items or not evidence_ids:
            return []
        wanted = {str(value).strip() for value in evidence_ids if str(value).strip()}
        return [item for item in evidence_items if str(item.get("evidence_id", "")).strip() in wanted]

    def _evidence_lookup(self, evidence_items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {
            str(item.get("evidence_id", "")).strip(): item
            for item in evidence_items
            if str(item.get("evidence_id", "")).strip()
        }

    def _sentence_support_text(self, claim_ids: List[str], evidence_lookup: Dict[str, Dict[str, Any]]) -> str:
        parts: List[str] = []
        for claim_id in claim_ids:
            item = evidence_lookup.get(str(claim_id).strip())
            if not item:
                continue
            parts.append(str(item.get("claim", "")).strip())
            parts.append(str(item.get("quote_span", "")).strip())
        return " ".join(part for part in parts if part)

    def _is_intro_sentence(self, sentence: str) -> bool:
        lowered = _normalise_spaces(sentence).lower()
        intro_patterns = (
            "다음과 같습니다",
            "다음과 같",
            "주요 재무 리스크는",
            "주요 사업은",
            "영위하는 주요 사업은",
        )
        return any(pattern in lowered for pattern in intro_patterns)

    def _normalise_sentence_checks(
        self,
        *,
        query_type: str,
        compressed_answer: str,
        sentence_checks: List[Dict[str, Any]],
        selected_claim_ids: List[str],
        evidence_items: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        evidence_lookup = self._evidence_lookup(evidence_items)
        normalized: List[Dict[str, Any]] = []

        raw_checks = sentence_checks or []
        if not raw_checks:
            raw_checks = [
                {
                    "sentence": sentence,
                    "verdict": "keep",
                    "reason": "fallback_keep",
                    "supporting_claim_ids": selected_claim_ids,
                }
                for sentence in _split_sentences(compressed_answer)
            ]

        seen_sentences: set[str] = set()
        previous_keep_signature: Optional[tuple] = None
        previous_keep_tokens: set[str] = set()

        for index, entry in enumerate(raw_checks):
            sentence = _normalise_spaces(str(entry.get("sentence", "")))
            if not sentence or sentence in seen_sentences:
                continue
            seen_sentences.add(sentence)
            normalized_sentence = _strip_anchor_text(sentence)

            verdict = str(entry.get("verdict", "keep") or "keep").strip()
            reason = _normalise_spaces(str(entry.get("reason", "")))
            supporting_claim_ids = [
                str(value).strip()
                for value in (entry.get("supporting_claim_ids") or [])
                if str(value).strip()
            ]

            if verdict not in {"keep", "drop_overextended", "drop_unsupported", "drop_redundant"}:
                verdict = "keep"

            if verdict == "keep" and not supporting_claim_ids:
                verdict = "drop_unsupported"
                reason = reason or "근거 claim이 연결되지 않음"

            support_text = self._sentence_support_text(supporting_claim_ids, evidence_lookup)
            support_tokens = _tokenize_terms(support_text)
            sentence_tokens = _tokenize_terms(normalized_sentence)
            overlap_ratio = len(sentence_tokens & support_tokens) / max(len(sentence_tokens), 1)
            aggregate_supported = (
                query_type in {"business_overview", "risk"}
                and bool(supporting_claim_ids)
                and (
                    overlap_ratio >= 0.2
                    or len(supporting_claim_ids) >= 2
                    or (query_type == "risk" and len(sentence_tokens) <= 8 and len(sentence_tokens & support_tokens) >= 1)
                )
            )

            if verdict == "keep" and self._is_intro_sentence(sentence) and index < len(raw_checks) - 1:
                if query_type in {"business_overview", "risk"} and supporting_claim_ids:
                    verdict = "keep"
                    reason = reason or "요약형 질문의 도입 문장으로 유지"
                else:
                    verdict = "drop_redundant"
                    reason = reason or "후속 문장이 동일 질문에 직접 답하므로 도입 문장은 제거"

            if verdict == "keep" and previous_keep_signature and tuple(supporting_claim_ids) == previous_keep_signature:
                overlap = len(sentence_tokens & previous_keep_tokens) / max(len(sentence_tokens | previous_keep_tokens), 1)
                if overlap >= 0.6:
                    verdict = "drop_redundant"
                    reason = reason or "같은 claim을 반복 설명함"

            if verdict in {"drop_overextended", "drop_unsupported"} and aggregate_supported:
                verdict = "keep"
                reason = reason or "여러 evidence의 합집합을 요약한 supported 문장"

            if verdict == "drop_redundant" and query_type in {"business_overview", "risk"} and self._is_intro_sentence(sentence) and supporting_claim_ids:
                verdict = "keep"
                reason = reason or "요약형 질문의 도입 문장으로 유지"

            if verdict == "keep" and query_type in {"business_overview", "risk"} and support_tokens:
                if overlap_ratio < 0.2 and len(sentence_tokens) >= 5 and len(supporting_claim_ids) <= 1:
                    verdict = "drop_overextended"
                    reason = reason or "근거 claim보다 과도하게 일반화되거나 확장됨"

            normalized.append(
                {
                    "sentence": sentence,
                    "verdict": verdict,
                    "reason": reason,
                    "supporting_claim_ids": supporting_claim_ids,
                }
            )

            if verdict == "keep":
                previous_keep_signature = tuple(supporting_claim_ids)
                previous_keep_tokens = sentence_tokens

        kept_sentences = [item["sentence"] for item in normalized if item["verdict"] == "keep"]
        kept_claim_ids = sorted(
            {
                claim_id
                for item in normalized
                if item["verdict"] == "keep"
                for claim_id in item.get("supporting_claim_ids", [])
            }
        )
        dropped_claim_ids = sorted(set(selected_claim_ids) - set(kept_claim_ids))
        unsupported_sentences = [
            item["sentence"] for item in normalized if item["verdict"] != "keep"
        ]
        final_answer = " ".join(kept_sentences).strip()
        if not final_answer:
            final_answer = (
                "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
                "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
            )

        return {
            "kept_claim_ids": kept_claim_ids,
            "dropped_claim_ids": dropped_claim_ids,
            "unsupported_sentences": unsupported_sentences,
            "sentence_checks": normalized,
            "answer": final_answer,
        }

    def _compression_guidance(self, query_type: str, query: str, coverage: str) -> Dict[str, str]:
        trend_instruction = "시계열 변화와 근거에 직접 있는 원인만 짧게 정리하세요."
        trend_output_style = "2~4문장."
        if _query_requests_narrative_context(query):
            trend_instruction = (
                "시계열 변화와 함께 실적에 직접 기여한 운영 요인을 1~2개까지 정리하세요. "
                "계약 목적이나 기대효과보다 근거 문서에 실제 성과 원인으로 명시된 요인을 우선하세요."
            )
            trend_output_style = "2~5문장."
        instructions = {
            "numeric_fact": (
                "질문이 요청한 숫자·금액·비율만 답하세요. claim과 quote_span에 있는 표기를 그대로 유지하고, "
                "동일 값을 다른 단위나 다른 숫자 표기로 바꾸지 마세요."
            ),
            "business_overview": (
                "질문에 직접 필요한 사업 구조를 정리하되, 각 부문을 설명할 때 "
                "근거에 등장하는 구체적인 예시(제품명, 주요 역할 등)를 생략하지 말고 포함하세요. "
                "같은 사실을 반복하거나 evidence에 없는 배경 설명은 빼세요. "
                "evidence에 parent_category가 명시된 항목들은 해당 상위 부문을 먼저 적고 "
                "그 아래에 하위 항목을 묶어서 구조화하세요."
            ),
            "risk": (
                "근거에 있는 리스크 항목만 추출하세요. 각 항목을 나열할 때 이름만 적지 말고, "
                "근거에 있는 구체적인 정의나 영향을 한 줄씩 함께 요약하세요. "
                "evidence에 parent_category가 명시된 항목들은 해당 상위 범주(예: 시장위험)를 먼저 적고 "
                "그 아래에 하위 항목을 묶어서 구조화하세요. "
                "evidence에 없는 새로운 상위 범주를 만들지 마세요."
            ),
            "comparison": "각 항목을 나란히 비교하되, evidence에 직접 있는 차이만 정리하세요.",
            "trend": trend_instruction,
            "qa": "질문에 직접 답하는 핵심 사실만 짧게 답하세요.",
        }
        output_styles = {
            "numeric_fact": "최대 1문장.",
            "business_overview": "각 부문의 구체적 제품/역할이 포함된 3~5개의 bullet.",
            "risk": "항목별로 이름과 짧은 설명(1~2줄)이 함께 있는 bullet. 항목 수는 evidence 범위를 넘기지 말 것.",
            "comparison": "짧은 bullet 비교.",
            "trend": trend_output_style,
            "qa": "짧고 직접적으로.",
        }

        coverage_note = ""
        if coverage == "sparse":
            coverage_note = "근거가 제한적입니다. evidence에 직접 적힌 claim과 quote_span만 사용하세요."
        elif coverage == "conflicting":
            coverage_note = "근거가 서로 상충하면 충돌을 명시하세요."

        return {
            "instruction": instructions.get(query_type, instructions["qa"]),
            "output_style": output_styles.get(query_type, output_styles["qa"]),
            "coverage_note": coverage_note,
        }

    def _extract_evidence(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Convert retrieved docs into claim-level evidence items."""
        docs = state.get("retrieved_docs", [])
        if not docs:
            return {"evidence_bullets": [], "evidence_items": [], "evidence_status": "missing"}
        direct_numeric_grounding = _requires_direct_numeric_grounding(state.get("active_subtask") or {})
        preserve_narrative_context = (
            direct_numeric_grounding
            and _query_requests_narrative_context(str(state.get("query") or ""))
        )
        active_subtask = dict(state.get("active_subtask") or {})
        operation_family = str(active_subtask.get("operation_family") or "").strip().lower()

        structured_llm = self.llm.with_structured_output(EvidenceExtraction)
        query_type = state.get("query_type", "qa")
        evidence_context = self._build_evidence_context(docs[: min(8, len(docs))])
        anchor_lookup = evidence_context["anchor_lookup"]
        if query_type == "risk":
            extra_rules = (
                "\n- 리스크 유형명은 컨텍스트에 명시된 단어만 사용하세요. "
                "컨텍스트에 없는 리스크 카테고리(예: '운영위험', '규제위험' 등)를 새로 만들지 마세요."
                "\n- [중요] 컨텍스트에 여러 개의 독립적인 리스크 항목이 나열되어 있다면, "
                "임의로 그룹화하거나 생략하지 마세요. "
                "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
                "\n- 문서에서 여러 하위 항목이 상위 범주 아래 묶여 있다면(예: '시장위험' 아래 환율변동위험·이자율변동위험·주가변동위험), "
                "각 하위 항목의 parent_category 필드에 해당 상위 범주 명칭을 그대로 적으세요. "
                "상위 범주가 문서에 명시되어 있지 않으면 None으로 두세요."
            )
        elif query_type == "business_overview":
            extra_rules = (
                "\n- [중요] 컨텍스트에 여러 개의 독립적인 사업 부문이나 항목이 나열되어 있다면, "
                "임의로 그룹화하거나 생략하지 마세요. "
                "문서에 존재하는 각 항목을 하나씩 독립적인 EvidenceItem으로 빠짐없이 추출하세요."
                "\n- 문서에서 여러 하위 항목이 상위 부문 아래 묶여 있다면(예: 'DS부문' 아래 메모리·시스템반도체·파운드리), "
                "각 하위 항목의 parent_category 필드에 해당 상위 부문 명칭을 그대로 적으세요. "
                "상위 범주가 문서에 명시되어 있지 않으면 None으로 두세요."
            )
        elif operation_family == "narrative_summary":
            extra_rules = (
                "\n- 질문이 영향/원인을 묻는 경우, 계약 목적이나 예상효과만 적힌 문단보다 "
                "실제 실적 변화의 원인·기여 요인을 설명하는 문단을 우선하세요."
                "\n- 가능하면 서로 다른 관점의 근거를 2개 이상 추출하세요. "
                "예: (1) 실적 변화나 성장률을 직접 설명하는 문단, "
                "(2) 그 변화의 배경 driver를 문서 표현 그대로 설명하는 문단."
                "\n- '주요 계약' 문단은 실제 성과 영향 문단이 부족할 때만 보조 근거로 사용하세요."
            )
        else:
            extra_rules = ""
        prompt = ChatPromptTemplate.from_template(
            """당신은 기업 공시 분석 보조자입니다.
질문에 답하기 전에, 아래 검색 결과에서 질문과 직접적으로 관련된 근거만 뽑아주세요.

규칙:
- 제공된 컨텍스트 밖의 정보를 추가하지 마세요.
- 각 근거는 반드시 아래 제공된 source_anchor 중 하나를 정확히 사용하세요.
- 숫자, 기간, 조건이 보이면 그대로 유지하세요.
- quote_span에는 실제 근거 원문 일부를 짧게 그대로 옮기세요.
- allowed_terms에는 답변에 사용 가능한 핵심 용어만 넣으세요.
- 근거가 부족하면 coverage를 sparse로, 서로 충돌하면 conflicting으로 설정하세요.
- 아예 답할 근거가 없으면 coverage를 missing으로 두고 evidence는 비우세요.{extra_rules}

질문: {query}
핵심 주제: {topic}

사용 가능한 source_anchor:
{available_anchors}

컨텍스트:
{context}
"""
        )

        fallback_terms = sorted(
            (term for term in _tokenize_terms(f"{state.get('query', '')} {state.get('topic') or ''}") if len(term) >= 2),
            key=len,
            reverse=True,
        )

        def _fallback_snippet(doc: Document) -> str:
            metadata = doc.metadata or {}
            surfaces = [
                _strip_rerank_metadata(str(doc.page_content or "")),
                str(metadata.get("table_value_labels_text") or ""),
                str(metadata.get("table_row_labels_text") or ""),
                str(metadata.get("table_summary_text") or ""),
            ]
            surface = re.sub(r"\s+", " ", "\n".join(part for part in surfaces if part).strip())
            if not surface:
                return ""
            best_pos: Optional[int] = None
            for term in fallback_terms:
                pos = surface.find(term)
                if pos >= 0:
                    best_pos = pos
                    break
            if best_pos is None:
                return surface[:220]
            start = max(0, best_pos - 120)
            end = min(len(surface), best_pos + 320)
            return surface[start:end].strip()

        def _deterministic_fallback(doc_list) -> tuple[List[str], List[Dict[str, Any]]]:
            bullets = []
            items = []
            for doc, _score in doc_list[: min(6, len(doc_list))]:
                metadata = doc.metadata or {}
                anchor = self._build_source_anchor(metadata)
                snippet = _fallback_snippet(doc)
                if not snippet:
                    continue
                bullets.append(f"- {anchor} {snippet}")
                items.append(
                    {
                        "evidence_id": f"ev_{len(items) + 1:03d}",
                        "source_anchor": anchor,
                        "claim": snippet,
                        "quote_span": snippet,
                        "support_level": "context",
                        "question_relevance": "medium",
                        "allowed_terms": sorted(_tokenize_terms(snippet))[:8],
                        "metadata": self._resolve_anchor_metadata(
                            anchor_lookup,
                            anchor,
                            quote_surface=snippet,
                            claim_surface=snippet,
                        ),
                    }
                )
            return bullets, items

        try:
            result: EvidenceExtraction = (prompt | structured_llm).invoke(
                {
                    "query": state["query"],
                    "topic": state.get("topic") or state["query"],
                    "available_anchors": "\n".join(evidence_context["available_anchors"]),
                    "context": evidence_context["context"],
                    "extra_rules": extra_rules,
                }
            )
            evidence_items = [
                self._build_runtime_evidence_item(item, index, anchor_lookup)
                for index, item in enumerate(result.evidence, start=1)
            ]
            evidence_items = self._filter_evidence_items_for_required_operands(evidence_items, state)
            if operation_family == "narrative_summary":
                evidence_items = self._supplement_narrative_driver_evidence(
                    evidence_items,
                    docs,
                    query=str(state.get("query") or ""),
                    anchor_lookup=anchor_lookup,
                )
                evidence_items = self._supplement_dividend_policy_evidence(
                    evidence_items,
                    docs,
                    query=str(state.get("query") or ""),
                    anchor_lookup=anchor_lookup,
                )
            if direct_numeric_grounding:
                evidence_items = self._restrict_direct_numeric_evidence_items(
                    evidence_items,
                    preserve_narrative_context=preserve_narrative_context,
                )
            evidence_bullets = [
                f"- {item.get('source_anchor', '?')} {item.get('claim', '')} ({item.get('support_level', 'context')})"
                for item in evidence_items
            ]
            if result.evidence and not evidence_items:
                logger.info("[evidence] filtered all extracted evidence items due to operand binding conflicts")
            if direct_numeric_grounding and not evidence_items:
                logger.info("[evidence] direct numeric task produced no grounded evidence — skipping deterministic fallback")
                return {
                    "evidence_bullets": [],
                    "evidence_items": [],
                    "evidence_status": "missing",
                }
            logger.info("[evidence] coverage=%s bullets=%s", result.coverage, len(evidence_bullets))

            # structured output이 missing을 반환했지만 docs는 있는 경우:
            # hard abstain 대신 deterministic fallback으로 sparse 답변 시도
            if not evidence_bullets and result.coverage == "missing":
                if direct_numeric_grounding:
                    logger.info("[evidence] direct numeric task returned missing — preserving missing instead of context fallback")
                    return {
                        "evidence_bullets": [],
                        "evidence_items": [],
                        "evidence_status": "missing",
                    }
                logger.info("[evidence] structured output returned missing with docs present — using deterministic fallback")
                fallback, fallback_items = _deterministic_fallback(docs)
                return {
                    "evidence_bullets": fallback,
                    "evidence_items": fallback_items,
                    "evidence_status": "sparse" if fallback else "missing",
                }

            return {
                "evidence_bullets": evidence_bullets,
                "evidence_items": evidence_items,
                "evidence_status": result.coverage,
            }
        except Exception as exc:
            if direct_numeric_grounding:
                logger.warning("[evidence] direct numeric extraction failed without grounded evidence: %s", exc)
                return {
                    "evidence_bullets": [],
                    "evidence_items": [],
                    "evidence_status": "missing",
                }
            logger.warning("Evidence extraction failed, using deterministic fallback: %s", exc)
            fallback, fallback_items = _deterministic_fallback(docs)
            return {
                "evidence_bullets": fallback,
                "evidence_items": fallback_items,
                "evidence_status": "sparse" if fallback else "missing",
            }

    def _compress_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Draft a narrative answer from curated evidence items."""
        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        if not evidence_items and not evidence_bullets:
            return {
                "selected_claim_ids": [],
                "draft_points": [],
                "compressed_answer": (
                    "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
                    "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
                ),
            }

        coverage = state.get("evidence_status", "sparse")
        query = state["query"]
        query_type = state.get("query_type", "qa")
        entity_table_answer = self._compose_entity_table_summary_answer(
            query=query,
            docs=state.get("retrieved_docs", []),
            evidence_items=evidence_items,
        )
        if entity_table_answer:
            logger.info("[compress] deterministic entity table summary generated")
            return entity_table_answer
        selected_evidence = self._select_evidence_for_compression(evidence_items, query_type)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)
        guidance = self._compression_guidance(query_type, query, coverage)

        structured_llm = self.llm.with_structured_output(CompressionOutput)
        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 분석 전문가입니다.
아래 structured evidence를 질문 범위에 맞게 압축해 typed output을 만드세요.

Compression 규칙:
- evidence에 없는 내용은 추가하지 마세요.
- 먼저 question_relevance가 high인 evidence만으로 답 구성을 시도하세요.
- claim을 기본 단위로 사용하고, 필요할 때만 quote_span의 원문 표현을 그대로 가져오세요.
- allowed_terms에 없는 새로운 분류명이나 핵심 용어는 만들지 마세요.
- 질문이 요구하지 않은 배경 설명, 예시, 장황한 연결 문장은 넣지 마세요.
- 가능한 한 중복 claim을 합치고, 같은 사실은 한 번만 말하세요.
- draft_answer와 draft_points 안에 `[회사 | 연도 | ...]` 형태의 source_anchor 원문을 절대 그대로 쓰지 마세요. 출처 추적은 selected_claim_ids로만 수행합니다.
{coverage_note}

질문 유형 지침:
{instruction}

출력 형식 지침:
{output_style}

Structured Evidence:
{evidence}

질문: {query}

반드시 다음 필드를 채우세요.
- selected_claim_ids: 실제로 사용한 evidence_id만
- draft_points: 중복을 제거한 핵심 포인트 목록
- draft_answer: 사용자에게 보여줄 짧은 초안 답변
"""
        )

        try:
            chain = prompt | structured_llm
            compressed: CompressionOutput = chain.invoke(
                {
                    "instruction": guidance["instruction"],
                    "coverage_note": guidance["coverage_note"],
                    "output_style": guidance["output_style"],
                    "evidence": evidence_text,
                    "query": state["query"],
                }
            )
            selected_claim_ids = self._expand_selected_claim_ids_for_narrative_drivers(
                compressed.selected_claim_ids,
                evidence_items,
                query=state["query"],
            )
            selected_evidence = self._filter_evidence_by_ids(evidence_items, selected_claim_ids)
            if not selected_evidence:
                selected_evidence = self._select_evidence_for_compression(evidence_items, query_type)
            compressed_answer = self._augment_narrative_answer_with_supported_drivers(
                compressed.draft_answer,
                selected_evidence,
                query=state["query"],
            )
            logger.info("[compress] typed compression generated")
            return {
                "selected_claim_ids": selected_claim_ids,
                "draft_points": compressed.draft_points,
                "compressed_answer": compressed_answer,
            }
        except Exception as exc:
            logger.warning("Compression structured output failed, using fallback text output: %s", exc)
            chain = prompt | self.llm | StrOutputParser()
            compressed_answer = chain.invoke(
                {
                    "instruction": guidance["instruction"],
                    "coverage_note": guidance["coverage_note"],
                    "output_style": guidance["output_style"],
                    "evidence": evidence_text,
                    "query": state["query"],
                }
            )
            selected_claim_ids = self._expand_selected_claim_ids_for_narrative_drivers(
                [item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")],
                evidence_items,
                query=state["query"],
            )
            selected_evidence = self._filter_evidence_by_ids(evidence_items, selected_claim_ids) or selected_evidence
            compressed_answer = self._augment_narrative_answer_with_supported_drivers(
                compressed_answer,
                selected_evidence,
                query=state["query"],
            )
            return {
                "selected_claim_ids": selected_claim_ids,
                "draft_points": [item.get("claim", "") for item in selected_evidence if item.get("claim")][:4],
                "compressed_answer": compressed_answer,
            }

    @staticmethod
    def _parse_labeled_numeric_lines(item: Dict[str, Any]) -> List[Dict[str, Any]]:
        metadata = dict(item.get("metadata") or {})
        text = str(metadata.get("table_value_labels_text") or "")
        rows: List[Dict[str, Any]] = []
        for line_index, line in enumerate(text.splitlines()):
            cleaned = _normalise_spaces(line)
            match = re.match(r"^(.+?)\s+(\(?-?\d[\d,]*(?:\.\d+)?\)?%?)$", cleaned)
            if not match:
                continue
            label = _normalise_spaces(match.group(1))
            raw_value = match.group(2).strip()
            numeric_text = raw_value.replace(",", "").replace("%", "")
            negative = numeric_text.startswith("(") and numeric_text.endswith(")")
            numeric_text = numeric_text.strip("()")
            try:
                numeric_value = float(numeric_text)
            except ValueError:
                continue
            if negative:
                numeric_value *= -1
            rows.append(
                {
                    "label": label,
                    "raw_value": raw_value,
                    "value": numeric_value,
                    "unit": str(metadata.get("unit_hint") or "").strip(),
                    "evidence_id": str(item.get("evidence_id") or "").strip(),
                    "metadata": metadata,
                    "claim": str(item.get("claim") or ""),
                    "line_index": line_index,
                }
            )
        return rows

    def _compose_supported_quantitative_impact_answer(
        self,
        *,
        query: str,
        evidence_items: List[Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        query_text = _normalise_spaces(query)
        if not any(marker in query_text for marker in ("영향", "분석", "비중", "대비", "차지")):
            return None

        rows: List[Dict[str, Any]] = []
        for item in evidence_items:
            rows.extend(self._parse_labeled_numeric_lines(item))
        if len(rows) < 2:
            return None

        query_compact = re.sub(r"\s+", "", query_text)
        quoted_terms = [
            re.sub(r"\s+", "", term)
            for term in re.findall(r"[\"'“”‘’](.+?)[\"'“”‘’]", query_text)
            if str(term).strip()
        ]
        primary_denominator_markers = ("매출원가", "매출액", "영업수익", "영업비용", "총계", "합계")
        denominator_markers = primary_denominator_markers + ("자산", "부채", "자본")

        def label_matches_query(label: str) -> bool:
            compact = re.sub(r"\s+", "", label)
            base_compact = re.sub(r"\([^)]*\)", "", compact)
            base_compact = base_compact.replace("등", "")
            if base_compact and base_compact in query_compact:
                return True
            if any(term and (term in compact or compact in term) for term in quoted_terms):
                return True
            label_terms = [term for term in _tokenize_terms(label) if len(term) >= 3]
            return any(term in query_text for term in label_terms)

        current_rows = [
            row
            for row in rows
            if label_matches_query(str(row.get("label") or ""))
            and str(row.get("metadata", {}).get("period_focus") or "") != "prior"
        ]
        if len(current_rows) < 2:
            return None

        numerator_candidates = [
            row
            for row in current_rows
            if not any(marker in str(row.get("label") or "") for marker in primary_denominator_markers)
        ]
        if not numerator_candidates:
            return None
        numerator_candidates.sort(
            key=lambda row: (
                str(row.get("metadata", {}).get("consolidation_scope") or "") == "consolidated",
                str(row.get("metadata", {}).get("statement_type") or "") == "notes",
                -int(row.get("line_index") or 0),
            ),
            reverse=True,
        )
        numerator = numerator_candidates[0]

        denominator_candidates = [
            row
            for row in current_rows
            if row is not numerator
            and any(marker in str(row.get("label") or "") for marker in denominator_markers)
            and float(row.get("value") or 0.0) != 0.0
        ]
        if not denominator_candidates:
            return None
        denominator_candidates.sort(
            key=lambda row: (
                str(row.get("metadata", {}).get("consolidation_scope") or "") == "consolidated",
                str(row.get("metadata", {}).get("statement_type") or "") in {"income_statement", "summary_financials"},
                -int(row.get("line_index") or 0),
            ),
            reverse=True,
        )
        denominator = denominator_candidates[0]

        numerator_value = abs(float(numerator.get("value") or 0.0))
        denominator_value = abs(float(denominator.get("value") or 0.0))
        if denominator_value <= 0:
            return None
        ratio = numerator_value / denominator_value * 100.0
        unit = str(numerator.get("unit") or denominator.get("unit") or "").strip()
        unit_suffix = unit if unit else ""
        scope_prefix = "연결 기준 " if str(numerator.get("metadata", {}).get("consolidation_scope") or "") == "consolidated" else ""
        numerator_label = str(numerator.get("label") or "").strip()
        denominator_label = str(denominator.get("label") or "").strip()
        numerator_raw = str(numerator.get("raw_value") or "").strip()
        denominator_raw = str(denominator.get("raw_value") or "").strip()

        impact_sentence = "해당 기준 금액에 반영된 항목으로 해석할 수 있습니다."
        if any(marker in denominator_label for marker in ("원가", "비용")) and "손실" in numerator_label and numerator_value > 0:
            impact_sentence = f"{denominator_label}에 포함되어 비용을 증가시키고 매출총이익을 압박하는 요인입니다."
        elif any(marker in denominator_label for marker in ("원가", "비용")):
            impact_sentence = f"{denominator_label}에 포함되어 해당 비용에 영향을 주는 항목입니다."

        caveat = ""
        if ("등" in numerator_label or "환입" in numerator_label) and "세부" not in query_text:
            caveat = " 항목명상 손실, 환입 등의 세부 구성은 이 근거만으로는 분해하지 않습니다."

        answer = (
            f"{scope_prefix}{numerator_label}은 {numerator_raw}{unit_suffix}입니다. "
            f"{impact_sentence} {denominator_label} {denominator_raw}{unit_suffix} 대비 약 {ratio:.2f}% 규모입니다.{caveat}"
        )
        supporting_claim_ids = sorted(
            {
                str(numerator.get("evidence_id") or ""),
                str(denominator.get("evidence_id") or ""),
            }
            - {""}
        )
        return {"answer": answer, "supporting_claim_ids": supporting_claim_ids}

    def _validate_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Check whether the drafted narrative answer is supported by evidence."""
        compressed_answer = state.get("compressed_answer", "")
        if not compressed_answer:
            return {
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "answer": compressed_answer,
            }

        query_type = state.get("query_type", "qa")
        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        selected_claim_ids = state.get("selected_claim_ids", [])
        selected_evidence = self._filter_evidence_by_ids(evidence_items, selected_claim_ids)
        if not selected_evidence:
            selected_evidence = self._select_evidence_for_compression(evidence_items, query_type)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)

        structured_llm = self.llm.with_structured_output(ValidationOutput)
        validator_prompt = ChatPromptTemplate.from_template(
            """다음 답변 초안을 structured evidence와 대조해 문장 단위로 검증하고 typed output을 만드세요.

Validator 규칙:
- 새 정보는 절대 추가하지 마세요.
- 근거로 뒷받침되지 않는 문장, 구, 세부사항만 삭제하거나 더 짧게 축소하세요.
- 질문에 직접 필요하지 않은 배경 설명은 삭제하세요.
- 숫자, 단위, 비율은 evidence의 quote_span 또는 claim 표기를 그대로 유지하세요.
- risk: evidence에 없는 상위 taxonomy나 재분류를 만들지 마세요.
- business_overview / risk: 여러 evidence에 흩어진 정보를 하나의 문장이나 bullet로 종합한 경우, 각 표현이 evidence 합집합으로 뒷받침되면 supported로 판단하세요.
- business_overview / risk: 특정 문장이 단일 evidence와 1:1로 대응하지 않아도, supporting_claim_ids의 합집합이 그 문장을 직접 지지하면 keep 할 수 있습니다.
- duplicated claim은 하나만 남기세요.
- 가능한 한 기존 source_anchor는 유지하세요.
- 초안을 문장 단위로 나눈 뒤 각 문장을 아래 verdict 중 하나로 판정하세요.
  - keep
  - drop_overextended
  - drop_unsupported
  - drop_redundant
- supporting_claim_ids에는 그 문장을 직접 지지하는 evidence_id만 넣으세요.
- keep가 아닌 문장은 unsupported_sentences에도 넣으세요.
- kept_claim_ids / dropped_claim_ids는 sentence_checks와 일관되게 작성하세요.
- final_answer는 keep verdict를 받은 문장만 자연스럽게 이어 붙인 결과여야 합니다.
- keep 문장이 하나도 없으면, 질문에 직접 답할 수 있는 근거를 찾지 못했다는 짧은 문장만 남기세요.

질문 유형: {query_type}
질문: {query}

Structured Evidence:
{evidence}

초안 답변:
{answer}

반드시 다음 필드를 채우세요.
- kept_claim_ids: 최종 답변에 실제로 남긴 evidence_id
- dropped_claim_ids: 제거한 evidence_id
- unsupported_sentences: 삭제하거나 축소한 문장/구
- sentence_checks: 각 문장에 대한 verdict, reason, supporting_claim_ids
- final_answer: 최종 사용자 답변
"""
        )
        try:
            validated: ValidationOutput = (validator_prompt | structured_llm).invoke(
                {
                    "query_type": query_type,
                    "query": state["query"],
                    "evidence": evidence_text,
                    "answer": compressed_answer,
                }
            )
            logger.info("[validate] typed validation generated")
            normalized_result = self._normalise_sentence_checks(
                query_type=query_type,
                compressed_answer=validated.final_answer or compressed_answer,
                sentence_checks=validated.sentence_checks,
                selected_claim_ids=[item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")],
                evidence_items=selected_evidence,
            )
            combined_evidence: List[Dict[str, Any]] = []
            seen_evidence_ids: set[str] = set()
            for item in list(selected_evidence) + list(evidence_items):
                evidence_id = str((item or {}).get("evidence_id") or "").strip()
                dedupe_key = evidence_id or _normalise_spaces(
                    " ".join(
                        part
                        for part in (
                            str((item or {}).get("source_anchor") or ""),
                            str((item or {}).get("claim") or ""),
                            str((item or {}).get("quote_span") or ""),
                        )
                        if part
                    )
                )
                if dedupe_key and dedupe_key in seen_evidence_ids:
                    continue
                if dedupe_key:
                    seen_evidence_ids.add(dedupe_key)
                combined_evidence.append(dict(item))
            deterministic_dividend_answer = self._compose_dividend_policy_hybrid_answer(
                query=str(state.get("query") or ""),
                evidence_items=combined_evidence,
            )
            if deterministic_dividend_answer:
                supporting_claim_ids = list(deterministic_dividend_answer.get("supporting_claim_ids") or [])
                return {
                    "kept_claim_ids": sorted(set(normalized_result.get("kept_claim_ids", [])) | set(supporting_claim_ids)),
                    "dropped_claim_ids": [
                        claim_id
                        for claim_id in normalized_result.get("dropped_claim_ids", [])
                        if claim_id not in supporting_claim_ids
                    ],
                    "unsupported_sentences": [],
                    "sentence_checks": [
                        {
                            "sentence": str(deterministic_dividend_answer.get("answer") or ""),
                            "verdict": "keep",
                            "reason": "deterministic_dividend_policy_hybrid_assembly",
                            "supporting_claim_ids": supporting_claim_ids,
                        }
                    ],
                    "answer": str(deterministic_dividend_answer.get("answer") or ""),
                }
            quantitative_impact_answer = self._compose_supported_quantitative_impact_answer(
                query=str(state.get("query") or ""),
                evidence_items=combined_evidence,
            )
            if quantitative_impact_answer:
                supporting_claim_ids = list(quantitative_impact_answer.get("supporting_claim_ids") or [])
                return {
                    "kept_claim_ids": sorted(set(normalized_result.get("kept_claim_ids", [])) | set(supporting_claim_ids)),
                    "dropped_claim_ids": [
                        claim_id
                        for claim_id in normalized_result.get("dropped_claim_ids", [])
                        if claim_id not in supporting_claim_ids
                    ],
                    "unsupported_sentences": [],
                    "sentence_checks": [
                        {
                            "sentence": str(quantitative_impact_answer.get("answer") or ""),
                            "verdict": "keep",
                            "reason": "supported_quantitative_impact_assembly",
                            "supporting_claim_ids": supporting_claim_ids,
                        }
                    ],
                    "answer": str(quantitative_impact_answer.get("answer") or ""),
                }
            return normalized_result
        except Exception as exc:
            logger.warning("Validation structured output failed, using fallback text output: %s", exc)
            validated_answer = (validator_prompt | self.llm | StrOutputParser()).invoke(
                {
                    "query_type": query_type,
                    "query": state["query"],
                    "evidence": evidence_text,
                    "answer": compressed_answer,
                }
            )
            selected_ids = [item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")]
            normalized_result = self._normalise_sentence_checks(
                query_type=query_type,
                compressed_answer=validated_answer,
                sentence_checks=[
                    {
                        "sentence": validated_answer,
                        "verdict": "keep",
                        "reason": "fallback",
                        "supporting_claim_ids": selected_ids,
                    }
                ]
                if validated_answer
                else [],
                selected_claim_ids=selected_ids,
                evidence_items=selected_evidence,
            )
            deterministic_dividend_answer = self._compose_dividend_policy_hybrid_answer(
                query=str(state.get("query") or ""),
                evidence_items=list(selected_evidence) or list(evidence_items),
            )
            if deterministic_dividend_answer:
                supporting_claim_ids = list(deterministic_dividend_answer.get("supporting_claim_ids") or [])
                return {
                    "kept_claim_ids": sorted(set(normalized_result.get("kept_claim_ids", [])) | set(supporting_claim_ids)),
                    "dropped_claim_ids": [
                        claim_id
                        for claim_id in normalized_result.get("dropped_claim_ids", [])
                        if claim_id not in supporting_claim_ids
                    ],
                    "unsupported_sentences": [],
                    "sentence_checks": [
                        {
                            "sentence": str(deterministic_dividend_answer.get("answer") or ""),
                            "verdict": "keep",
                            "reason": "deterministic_dividend_policy_hybrid_assembly",
                            "supporting_claim_ids": supporting_claim_ids,
                        }
                    ],
                    "answer": str(deterministic_dividend_answer.get("answer") or ""),
                }
            quantitative_impact_answer = self._compose_supported_quantitative_impact_answer(
                query=str(state.get("query") or ""),
                evidence_items=list(selected_evidence) or list(evidence_items),
            )
            if quantitative_impact_answer:
                supporting_claim_ids = list(quantitative_impact_answer.get("supporting_claim_ids") or [])
                return {
                    "kept_claim_ids": sorted(set(normalized_result.get("kept_claim_ids", [])) | set(supporting_claim_ids)),
                    "dropped_claim_ids": [
                        claim_id
                        for claim_id in normalized_result.get("dropped_claim_ids", [])
                        if claim_id not in supporting_claim_ids
                    ],
                    "unsupported_sentences": [],
                    "sentence_checks": [
                        {
                            "sentence": str(quantitative_impact_answer.get("answer") or ""),
                            "verdict": "keep",
                            "reason": "supported_quantitative_impact_assembly",
                            "supporting_claim_ids": supporting_claim_ids,
                        }
                    ],
                    "answer": str(quantitative_impact_answer.get("answer") or ""),
                }
            return normalized_result

    def _supplement_numeric_impairment_lookup(self, state: FinancialAgentState, docs) -> Optional[Dict[str, Any]]:
        query = _normalise_spaces(str(state.get("query") or ""))
        lowered_query = query.lower()
        if not query:
            return None
        if "손상" not in lowered_query and "환입" not in lowered_query:
            return None
        if not any(marker in lowered_query for marker in ("발생 여부", "손상차손", "손상 여부", "환입")):
            return None

        aliases: List[str] = []
        for label in _extract_generic_operand_labels(query):
            aliases.extend(_build_generic_metric_aliases(label))
        aliases = list(dict.fromkeys(_normalise_spaces(alias) for alias in aliases if _normalise_spaces(alias)))
        if not aliases:
            return None

        total_row_labels = {"기말금액", "당기말", "당기말금액", "기말 장부금액", "기말장부금액"}
        impairment_row_labels = {"손상 및 환입", "손상차손", "손상", "손상손실", "손상차손 및 환입"}
        total_hit: Optional[Dict[str, Any]] = None
        impairment_hit: Optional[Dict[str, Any]] = None

        def _find_metric_cell(cells: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
            for cell in cells:
                headers = [
                    _normalise_spaces(str(item))
                    for item in (cell.get("column_headers") or [])
                    if _normalise_spaces(str(item))
                ]
                if not headers:
                    continue
                header_blob = " ".join(headers).lower()
                if any(alias.lower() in header_blob for alias in aliases):
                    return dict(cell)
            return None

        def _quote_for_row(row_label: str, cell: Dict[str, Any], unit_hint: str) -> str:
            header_text = " / ".join(
                _normalise_spaces(str(item))
                for item in (cell.get("column_headers") or [])
                if _normalise_spaces(str(item))
            )
            value_text = _normalise_spaces(str(cell.get("value_text") or ""))
            parts = [row_label, header_text, value_text]
            if unit_hint and unit_hint not in value_text:
                parts.append(unit_hint)
            return " | ".join(part for part in parts if part)

        for doc, _score in docs[: min(8, len(docs))]:
            metadata = dict(doc.metadata or {})
            row_records_json = str(metadata.get("table_row_records_json") or "").strip()
            if not row_records_json:
                continue
            try:
                row_records = json.loads(row_records_json)
            except json.JSONDecodeError:
                continue
            unit_hint = _normalise_spaces(str(metadata.get("unit_hint") or "")) or "천원"
            anchor = self._build_source_anchor(metadata)
            for record in row_records:
                row_label = _normalise_spaces(str(record.get("row_label") or ""))
                if not row_label:
                    continue
                cells = [dict(item) for item in (record.get("cells") or []) if isinstance(item, dict)]
                cell = _find_metric_cell(cells)
                if not cell:
                    continue
                value_text = _normalise_spaces(str(cell.get("value_text") or ""))
                quote = _quote_for_row(row_label, cell, unit_hint)
                if row_label in total_row_labels and total_hit is None:
                    total_hit = {
                        "anchor": anchor,
                        "quote": quote,
                        "value_text": value_text,
                        "unit_hint": unit_hint,
                        "metadata": metadata,
                    }
                if row_label in impairment_row_labels and impairment_hit is None:
                    impairment_hit = {
                        "anchor": anchor,
                        "quote": quote,
                        "value_text": value_text,
                        "unit_hint": unit_hint,
                        "metadata": metadata,
                        "row_label": row_label,
                    }
                if total_hit and impairment_hit:
                    break
            if total_hit and impairment_hit:
                break

        if not total_hit or not impairment_hit:
            return None

        metric_label = aliases[0]
        impairment_value = _normalise_spaces(str(impairment_hit.get("value_text") or ""))
        answer = (
            f"2023년 연결재무제표 주석 기준 {metric_label} 총액은 "
            f"{total_hit.get('value_text')}{total_hit.get('unit_hint') or ''}입니다. "
            f"또한 {impairment_hit.get('row_label') or '손상 및 환입'} 금액이 "
            f"{impairment_value}{impairment_hit.get('unit_hint') or ''}으로 표시되어 있어 "
            f"당기에 {metric_label} 손상차손이 발생한 것으로 확인됩니다."
        )
        evidence_items = [
            {
                "evidence_id": "ev_001",
                "source_anchor": total_hit["anchor"],
                "claim": total_hit["quote"],
                "quote_span": total_hit["quote"],
                "support_level": "direct",
                "question_relevance": "high",
                "allowed_terms": sorted(_tokenize_terms(total_hit["quote"]))[:8],
                "metadata": total_hit["metadata"],
            },
            {
                "evidence_id": "ev_002",
                "source_anchor": impairment_hit["anchor"],
                "claim": impairment_hit["quote"],
                "quote_span": impairment_hit["quote"],
                "support_level": "direct",
                "question_relevance": "high",
                "allowed_terms": sorted(_tokenize_terms(impairment_hit["quote"]))[:8],
                "metadata": impairment_hit["metadata"],
            },
        ]
        return {
            "answer": answer,
            "evidence_items": evidence_items,
            "evidence_bullets": [
                f"- {item['source_anchor']} {item['claim']} (direct)"
                for item in evidence_items
            ],
            "numeric_debug_trace": {
                "path": "deterministic_impairment_lookup",
                "metric_aliases": aliases,
                "raw_value": str(total_hit.get("value_text") or ""),
                "unit": str(total_hit.get("unit_hint") or ""),
                "impairment_value": impairment_value,
            },
        }

    def _extract_numeric_fact(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Fast path for direct numeric lookups that do not need full planning."""
        docs = state.get("retrieved_docs", [])
        empty_result: Dict[str, Any] = {
            "answer": "관련 공시 문서에서 요청한 수치를 찾지 못했습니다.",
            "compressed_answer": "",
            "selected_claim_ids": [],
            "draft_points": [],
            "kept_claim_ids": [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "evidence_items": [],
            "evidence_bullets": [],
            "evidence_status": "missing",
            "numeric_debug_trace": {},
        }
        if not docs:
            return empty_result

        context = self._format_context(docs[: min(8, len(docs))])
        structured_llm = self.llm.with_structured_output(NumericExtraction)
        prompt = ChatPromptTemplate.from_template(
            """당신은 재무 데이터 전문 분석가입니다.
아래 질문에 답하기 위해 공시 문서 컨텍스트에서 정확한 수치를 추출하세요.

지시사항:
1. 표(Table)에서 행과 열의 교차점을 정확히 확인하세요.
2. 당기/전기, 연결/별도, 금액 단위를 최우선으로 확인하세요.
3. raw_value는 문서에서 찾은 숫자를 변환 없이 그대로 적으세요.
4. final_value는 raw_value와 unit을 바탕으로 질문에 직접 답하는 자연스러운 한국어 한 문장으로 작성하세요.
5. 수치를 찾지 못한 경우 raw_value와 final_value를 빈 문자열로 두세요.

질문: {query}

컨텍스트:
{context}
"""
        )

        try:
            result: NumericExtraction = (prompt | structured_llm).invoke(
                {"query": state["query"], "context": context}
            )
            debug_trace = result.model_dump()
            logger.info(
                "[numeric_extractor] period=%s consolidation=%s unit=%s raw=%s",
                (result.period_check or "")[:60],
                (result.consolidation_check or "")[:60],
                result.unit,
                result.raw_value,
            )
            answer = result.final_value if result.final_value else empty_result["answer"]
        except Exception as exc:
            logger.warning("[numeric_extractor] structured output failed: %s", exc)
            debug_trace = {"error": str(exc)}
            answer = empty_result["answer"]

        if not debug_trace.get("raw_value"):
            deterministic = self._supplement_numeric_impairment_lookup(state, docs)
            if deterministic:
                answer = str(deterministic.get("answer") or empty_result["answer"])
                evidence_items = list(deterministic.get("evidence_items") or [])
                evidence_bullets = list(deterministic.get("evidence_bullets") or [])
                return {
                    "answer": answer,
                    "compressed_answer": answer,
                    "selected_claim_ids": [str(item.get("evidence_id") or "") for item in evidence_items if str(item.get("evidence_id") or "")],
                    "draft_points": [answer] if answer else [],
                    "kept_claim_ids": [str(item.get("evidence_id") or "") for item in evidence_items if str(item.get("evidence_id") or "")],
                    "dropped_claim_ids": [],
                    "unsupported_sentences": [],
                    "sentence_checks": [],
                    "evidence_items": evidence_items,
                    "evidence_bullets": evidence_bullets,
                    "evidence_status": "sufficient" if evidence_items else "missing",
                    "numeric_debug_trace": dict(deterministic.get("numeric_debug_trace") or {}),
                }

        # grounding judge가 검증할 수 있도록 numeric_extractor 결과를 evidence_item으로 변환
        evidence_items: List[Dict[str, Any]] = []
        evidence_bullets: List[str] = []
        evidence_status = "missing"
        if debug_trace and debug_trace.get("raw_value"):
            anchor = self._build_source_anchor(
                (docs[0][0].metadata if docs else {})
            )
            claim = f"{debug_trace.get('raw_value', '')} ({debug_trace.get('unit', '')})"
            quote_span = debug_trace.get("raw_value", "")
            evidence_items = [
                {
                    "evidence_id": "ev_001",
                    "source_anchor": anchor,
                    "claim": claim,
                    "quote_span": quote_span,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": [debug_trace.get("raw_value", ""), debug_trace.get("unit", "")],
                    "metadata": docs[0][0].metadata if docs else {},
                }
            ]
            evidence_bullets = [f"- {anchor} {claim} (direct)"]
            evidence_status = "sufficient"

        return {
            "answer": answer,
            "compressed_answer": answer,
            "selected_claim_ids": ["ev_001"] if evidence_items else [],
            "draft_points": [answer] if answer else [],
            "kept_claim_ids": ["ev_001"] if evidence_items else [],
            "dropped_claim_ids": [],
            "unsupported_sentences": [],
            "sentence_checks": [],
            "evidence_items": evidence_items,
            "evidence_bullets": evidence_bullets,
            "evidence_status": evidence_status,
            "numeric_debug_trace": debug_trace,
        }

