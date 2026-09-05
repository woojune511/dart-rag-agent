"""
Evidence mixin for the financial graph agent.

This module owns evidence shaping after retrieval:
- optionally expand selected hits with nearby structural context
- transform docs into evidence items
- run the narrative answer path for non-calculation questions
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.agent.financial_graph_model_loaders import (
    compression_output_model,
    evidence_extraction_model,
    validate_answer_slots_payload,
    validation_output_model,
)
from src.agent.financial_langchain_loaders import (
    chat_prompt_template_from_template,
    str_output_parser,
)
from src.agent.financial_retrieval_pipeline import (
    make_document,
)
from src.agent.financial_retrieval_hints import (
    _desired_statement_types,
    compression_guidance,
    evidence_extraction_focus_terms,
    preferred_section_evidence_subset,
)
from src.agent.financial_surface_contracts import (
    text_has_negative_surface,
    text_has_positive_surface,
    scoped_surface_affinity_priority,
)
if TYPE_CHECKING:
    from src.agent.financial_graph_models import EvidenceItem
    from src.agent.financial_graph_state import FinancialAgentState, NarrativeInput, NarrativeResultPhase
from src.agent.financial_operation_policies import (
    query_requests_narrative_context,
)
from src.agent.financial_runtime_normalization import (
    _normalise_operand_value,
    _normalise_spaces,
    _parse_number_text,
)
from src.agent.financial_scope_policies import (
    desired_consolidation_scope,
    metadata_period_match_strength,
)
from src.agent.financial_text_surface import (
    split_sentences,
    strip_anchor_text,
    strip_rerank_metadata,
    tokenize_terms,
    query_focus_marker_groups,
    query_focus_markers,
)
from src.config.retrieval_policy import (
    ENTITY_TABLE_SUMMARY_ASSEMBLY_POLICY,
    DIVIDEND_POLICY_ASSEMBLY_POLICY,
    EVIDENCE_COMPRESSION_GUIDANCE_POLICY,
    EVIDENCE_EXTRACTION_POLICY,
    EVIDENCE_RUNTIME_POLICY,
    QUERY_FOCUS_MARKER_POLICY,
    SENTENCE_NORMALISATION_POLICY,
    STRUCTURED_CELL_AFFINITY_POLICY,
    VALUE_NEAR_MATCH_POLICY,
    narrative_policy_driver_groups,
    narrative_policy_slot_groups,
    narrative_policy_terms,
)
if TYPE_CHECKING:
    from langchain_core.documents import Document

logger = logging.getLogger(__name__)


def _prioritize_candidate_items(
    candidate_items: List[Dict[str, Any]],
    query: str,
    topic: str,
    report_scope: Dict[str, Any],
    query_years: List[int],
) -> List[Dict[str, Any]]:
    desired_statement_types = set(_desired_statement_types(query, topic))
    desired_consolidation = desired_consolidation_scope(query, report_scope)
    table_counts: Dict[str, int] = {}
    for item in candidate_items:
        metadata = dict(item.get("metadata") or {})
        table_source_id = str(metadata.get("table_source_id") or "").strip()
        if table_source_id:
            table_counts[table_source_id] = table_counts.get(table_source_id, 0) + 1

    def score(item: Dict[str, Any]) -> tuple[float, int]:
        metadata = dict(item.get("metadata") or {})
        points = 0.0
        statement_type = str(metadata.get("statement_type") or "unknown").strip()
        if desired_statement_types:
            if statement_type in desired_statement_types:
                points += 3.0
            elif statement_type != "unknown":
                points -= 1.0
        consolidation_scope = str(metadata.get("consolidation_scope") or "unknown").strip()
        if desired_consolidation != "unknown":
            if consolidation_scope == desired_consolidation:
                points += 2.0
            elif consolidation_scope != "unknown":
                points -= 2.0
        period_strength = metadata_period_match_strength(list(metadata.get("period_labels") or []), query_years)
        points += period_strength * 1.5
        affinity_policy = dict(STRUCTURED_CELL_AFFINITY_POLICY)
        metric_terms = tuple(str(term) for term in (affinity_policy.get("metric_terms") or ()) if str(term))
        query_surface = _normalise_spaces(f"{query} {topic}")
        if statement_type == "segment_note" and any(term in query_surface for term in metric_terms):
            points += scoped_surface_affinity_priority(
                [item],
                query=query,
                topic=topic,
                direct_weight=2.5,
                adjustment_weight=-1.5,
            )
        table_source_id = str(metadata.get("table_source_id") or "").strip()
        return points, table_counts.get(table_source_id, 0)

    return sorted(candidate_items, key=score, reverse=True)



def _extract_value_near_match(text: str, start: int, end: int) -> tuple[Optional[str], str]:
    tail = text[end : min(len(text), end + 120)]
    if not tail:
        return None, ""
    tail = _normalise_spaces(tail)
    value_policy = dict(VALUE_NEAR_MATCH_POLICY)
    match = re.search(str(value_policy.get("value_pattern") or r"$^"), tail)
    if not match:
        return None, ""
    raw_value = _normalise_spaces(match.group(1))
    percent_markers = tuple(str(item) for item in (value_policy.get("percent_markers") or ()) if str(item))
    million_krw_unit = str(value_policy.get("million_krw_unit") or "")
    composite_markers = tuple(str(item) for item in (value_policy.get("composite_krw_markers") or ()) if str(item))
    composite_unit = str(value_policy.get("composite_krw_unit") or "")
    if any(marker in raw_value for marker in percent_markers):
        return raw_value, percent_markers[0] if percent_markers else ""
    if million_krw_unit and million_krw_unit in raw_value:
        return raw_value.replace(million_krw_unit, "").strip(), million_krw_unit
    if any(marker in raw_value for marker in composite_markers):
        return raw_value, composite_unit
    return raw_value, ""


class FinancialAgentEvidenceMixin:
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
            add_doc(make_document(page_content=doc.page_content, metadata=seed_metadata), float(score), relation="seed")

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
                    add_doc(
                        make_document(page_content=parent_text, metadata=parent_metadata),
                        float(score) - 0.005,
                        "parent_context",
                    )

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
                    add_doc(
                        make_document(page_content=table_context, metadata=table_metadata),
                        float(score) - 0.007,
                        "table_context",
                    )

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





    def _build_source_anchor(self, metadata: Dict[str, Any]) -> str:
        relation = str(metadata.get("graph_relation") or "").strip()
        relation_suffix = f" | {relation}" if relation else ""
        return (
            f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
            f"{metadata.get('section_path', metadata.get('section', '?'))}{relation_suffix}]"
        )

    def _build_evidence_context(self, docs, *, focus_terms: Optional[List[str]] = None) -> Dict[str, Any]:
        parts = []
        anchor_lookup: Dict[str, List[Dict[str, Any]]] = {}
        seen_parents: set = set()
        focus_terms_lower = [
            _normalise_spaces(str(term or "")).lower()
            for term in (focus_terms or [])
            if _normalise_spaces(str(term or ""))
        ]

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
            child_content = str(doc.page_content or "")
            child_matches_focus = bool(
                focus_terms_lower
                and any(term in child_content.lower() for term in focus_terms_lower)
            )
            if graph_relation:
                parts.append(f"{anchor}\n{child_content}")
                continue

            if parent_id and not child_matches_focus and not skip_auto_parent and parent_id not in seen_parents:
                parent_text = self.vsm.get_parent(parent_id)
                if parent_text:
                    seen_parents.add(parent_id)
                    parts.append(f"{anchor}\n{parent_text}")
                    continue

            if parent_id in seen_parents:
                continue

            table_context = metadata.get("table_context")
            body = f"[table_context] {table_context}\n{child_content}" if table_context else child_content
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
        if not lookup_value and anchor:
            anchor_norm = _normalise_spaces(str(anchor or "")).strip("[]").lower()
            fuzzy_entries: List[Dict[str, Any]] = []
            for candidate_anchor, candidate_value in anchor_lookup.items():
                candidate_norm = _normalise_spaces(str(candidate_anchor or "")).strip("[]").lower()
                if not anchor_norm or not candidate_norm:
                    continue
                if anchor_norm in candidate_norm or candidate_norm in anchor_norm:
                    if isinstance(candidate_value, dict):
                        fuzzy_entries.append(dict(candidate_value))
                    else:
                        fuzzy_entries.extend(
                            dict(item)
                            for item in list(candidate_value or [])
                            if isinstance(item, dict)
                        )
            lookup_value = fuzzy_entries
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
        if quote_surface and text_has_negative_surface(quote_surface, operand):
            return True

        claim_surface = str(item.get("claim") or "").strip()
        if claim_surface and text_has_negative_surface(claim_surface, operand) and not text_has_positive_surface(claim_surface, operand):
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
        if query_requests_narrative_context(merged):
            return True
        return block_type in {"paragraph", "parent_context", "section_lead", "described_by_paragraph"} or graph_relation in {
            "parent_context",
            "section_lead",
            "described_by_paragraph",
        }


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





    # enumeration 질문은 항목이 많아 기본 cap=6이 부족할 수 있음
    _EVIDENCE_CAP_BY_QUERY_TYPE: Dict[str, int] = {
        "risk": 10,
        "business_overview": 8,
        "comparison": 8,
    }

    def _select_evidence_for_compression(
        self,
        evidence_items: List[Dict[str, Any]],
        query_type: str = "qa",
        state: Optional[FinancialAgentState] = None,
    ) -> List[Dict[str, Any]]:
        if not evidence_items:
            return []
        limit = self._EVIDENCE_CAP_BY_QUERY_TYPE.get(query_type, 6)
        ranked = self._sort_evidence_items(evidence_items)
        if state:
            preferred_ranked = preferred_section_evidence_subset(ranked, state)
            if preferred_ranked:
                ranked = preferred_ranked
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
        for focus_group in query_focus_marker_groups(query):
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
        surface = re.sub(r"(?<=[.!?。])\s*(?=[\-ㆍ•·*]\s*)", " ", surface)
        surface = re.sub(r"(?<=[.!?。])(?=[\uac00-\ud7a3])", " ", surface)

        fragments = [
            _normalise_spaces(fragment)
            for fragment in re.split(r"(?<=[.!?。])\s+|\n+", surface)
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
                            "allowed_terms": sorted(tokenize_terms((snippet or amount_surface)))[:8],
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
                            "allowed_terms": sorted(tokenize_terms(snippet))[:8],
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

    def _supplement_policy_realized_evidence(
        self,
        evidence_items: List[Dict[str, Any]],
        docs,
        *,
        query: str,
        anchor_lookup: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        if not docs:
            return evidence_items

        active_policies = self._active_narrative_policies_for_query(query)
        query_focus_terms = query_focus_markers(query)
        if not active_policies:
            return evidence_items
        exclusive_narrative_policy = any(bool(policy.get("exclusive_narrative_task")) for policy in active_policies)
        if not exclusive_narrative_policy and not query_requests_narrative_context(query):
            return evidence_items

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
        existing_surface = _normalise_spaces(
            " ".join(
                part
                for item in supplemented
                for part in (
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                    str(item.get("raw_row_text") or ""),
                )
                if part
            )
        ).lower()

        def _candidate_for_policy(policy: Dict[str, Any]) -> Optional[Dict[str, Any]]:
            focus_terms = list(
                dict.fromkeys(
                    [
                        *query_focus_terms,
                        *narrative_policy_terms([policy], "focus_terms"),
                    ]
                )
            )
            realized_terms = narrative_policy_terms([policy], "realized_terms")
            causal_terms = narrative_policy_terms([policy], "causal_terms")
            required_realized_terms = narrative_policy_terms([policy], "required_realized_terms")
            if required_realized_terms and any(term.lower() in existing_surface for term in required_realized_terms):
                return None
            if not focus_terms or not (realized_terms or causal_terms):
                return None

            best_candidate: Optional[Dict[str, Any]] = None
            best_score = float("-inf")

            for item in docs:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                block_type = str(metadata.get("block_type") or "").strip().lower()
                if block_type not in {"paragraph", "table"}:
                    continue
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
                surface = strip_rerank_metadata(surface) or surface
                if not surface:
                    continue
                lowered_surface = surface.lower()
                required_hits = [
                    term for term in required_realized_terms if term and term.lower() in lowered_surface
                ]
                if required_realized_terms and not required_hits:
                    continue
                focus_hits = [term for term in focus_terms if term and term.lower() in lowered_surface]
                if not focus_hits:
                    continue
                realized_hits = [term for term in realized_terms if term and term.lower() in lowered_surface]
                causal_hits = [term for term in causal_terms if term and term.lower() in lowered_surface]
                if realized_terms and not realized_hits:
                    continue
                if causal_terms and not causal_hits and not realized_hits:
                    continue

                driver_terms = list(dict.fromkeys([*required_hits, *realized_hits, *focus_hits, *causal_hits]))
                snippet = self._extract_driver_snippet(surface, driver_terms) or surface[:220]
                score = float(
                    len(required_hits) * 8
                    + len(realized_hits) * 4
                    + len(focus_hits) * 2
                    + len(causal_hits)
                )
                if block_type == "table":
                    score += 2.0
                elif block_type == "paragraph":
                    score += 1.0
                try:
                    score += min(float(item[1] or 0.0), 1.0) if isinstance(item, (tuple, list)) and len(item) > 1 else 0.0
                except (TypeError, ValueError):
                    pass
                if score <= best_score:
                    continue

                anchor = self._build_source_anchor(metadata)
                best_score = score
                best_candidate = {
                    "evidence_id": f"ev_{len(supplemented) + 1:03d}",
                    "source_anchor": anchor,
                    "claim": snippet,
                    "quote_span": snippet,
                    "support_level": "direct",
                    "question_relevance": "high",
                    "allowed_terms": sorted(tokenize_terms(snippet))[:8],
                    "metadata": self._resolve_anchor_metadata(
                        anchor_lookup,
                        anchor,
                        quote_surface=snippet,
                        claim_surface=snippet,
                    ),
                }
            return best_candidate

        for policy in active_policies:
            best_candidate = _candidate_for_policy(policy)
            if not best_candidate:
                continue
            dedupe_key = _normalise_spaces(
                " ".join(
                    part
                    for part in (
                        str(best_candidate.get("source_anchor") or ""),
                        str(best_candidate.get("quote_span") or best_candidate.get("claim") or ""),
                    )
                    if part
                )
            )
            if dedupe_key and dedupe_key in seen_keys:
                continue
            if dedupe_key:
                seen_keys.add(dedupe_key)
            best_candidate["evidence_id"] = f"ev_{len(supplemented) + 1:03d}"
            supplemented.append(best_candidate)
        return supplemented

    def _supplement_missing_focus_context_evidence(
        self,
        evidence_items: List[Dict[str, Any]],
        docs,
        *,
        query: str,
        anchor_lookup: Dict[str, Any],
        coverage: str,
    ) -> List[Dict[str, Any]]:
        if not docs or str(coverage or "").strip().lower() != "missing":
            return evidence_items

        active_policies = self._active_narrative_policies_for_query(query)
        if not any(bool(policy.get("exclusive_narrative_task")) for policy in active_policies):
            return evidence_items

        query_focus_terms = query_focus_markers(query)
        if not query_focus_terms:
            return evidence_items

        marker_policy = dict(QUERY_FOCUS_MARKER_POLICY)
        trailing_particle_pattern = str(marker_policy.get("trailing_particle_pattern") or r"$^")

        def _normalise_focus_term(term: str) -> str:
            cleaned = _normalise_spaces(str(term or "")).strip()
            cleaned = re.sub(trailing_particle_pattern, "", cleaned)
            return cleaned.strip()

        focus_terms = list(
            dict.fromkeys(
                term
                for term in (_normalise_focus_term(term) for term in query_focus_terms)
                if term
            )
        )
        strong_focus_terms = {
            term.lower()
            for term in focus_terms
            if len(term) >= 3 or re.search(r"[A-Za-z0-9]", term)
        }
        if len(strong_focus_terms) < 2:
            return evidence_items

        supplemented = [dict(item) for item in evidence_items]
        existing_surface = _normalise_spaces(
            " ".join(
                part
                for item in supplemented
                for part in (
                    str(item.get("source_anchor") or ""),
                    str(item.get("claim") or ""),
                    str(item.get("quote_span") or ""),
                    str(item.get("raw_row_text") or ""),
                )
                if part
            )
        ).lower()
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

        scored_candidates: List[tuple[float, int, Dict[str, Any]]] = []
        for rank, item in enumerate(docs):
            doc = item[0] if isinstance(item, (tuple, list)) else item
            metadata = getattr(doc, "metadata", {}) or {}
            block_type = str(metadata.get("block_type") or "").strip().lower()
            if block_type not in {"paragraph", "table"}:
                continue

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
            surface = strip_rerank_metadata(surface) or surface
            if not surface:
                continue

            lowered_surface = surface.lower()
            focus_hits = [
                term
                for term in focus_terms
                if term and term.lower() in lowered_surface
            ]
            if len(focus_hits) < 2:
                continue
            strong_focus_hits = {term.lower() for term in focus_hits if term.lower() in strong_focus_terms}
            if len(strong_focus_hits) < 2:
                continue
            if not any(term.lower() not in existing_surface for term in focus_hits):
                continue

            driver_terms = [term for term in focus_hits if term.lower() in strong_focus_terms]
            snippet = self._extract_driver_snippet(surface, driver_terms) or surface[:220]
            snippet_lower = snippet.lower()
            snippet_strong_hits = {
                term.lower()
                for term in driver_terms
                if term and term.lower() in snippet_lower
            }
            if len(snippet_strong_hits) < 2:
                continue
            anchor = self._build_source_anchor(metadata)
            dedupe_key = _normalise_spaces(f"{anchor} {snippet}")
            if dedupe_key and dedupe_key in seen_keys:
                continue

            score = float(len(set(term.lower() for term in focus_hits)) * 4)
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
                        "question_relevance": "high",
                        "allowed_terms": sorted(tokenize_terms(snippet))[:8],
                        "metadata": self._resolve_anchor_metadata(
                            anchor_lookup,
                            anchor,
                            quote_surface=snippet,
                            claim_surface=snippet,
                        ),
                    },
                )
            )

        scored_candidates.sort(key=lambda row: (-row[0], row[1]))
        for _score, _rank, candidate in scored_candidates[:2]:
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
        if not draft or not selected_evidence:
            return draft
        active_policies = self._active_narrative_policies_for_query(query)
        exclusive_policies = [policy for policy in active_policies if bool(policy.get("exclusive_narrative_task"))]
        narrative_context_query = query_requests_narrative_context(query)
        if exclusive_policies:
            draft_lower = draft.lower()
            for policy in exclusive_policies:
                policy_terms = list(
                    dict.fromkeys(
                        [
                            *narrative_policy_terms([policy], "focus_terms"),
                            *narrative_policy_terms([policy], "realized_terms"),
                            *narrative_policy_terms([policy], "causal_terms"),
                        ]
                    )
                )
                if any(term and term.lower() in draft_lower for term in policy_terms):
                    continue
                best_snippet = ""
                best_score = 0
                for item in selected_evidence:
                    claim = strip_rerank_metadata(
                        _normalise_spaces(
                            " ".join(
                                part
                                for part in (
                                    str(item.get("claim") or ""),
                                    str(item.get("quote_span") or ""),
                                )
                                if part
                            )
                        )
                    )
                    if not claim:
                        continue
                    claim_lower = claim.lower()
                    hits = sum(1 for term in policy_terms if term and term.lower() in claim_lower)
                    if hits <= best_score:
                        continue
                    best_score = hits
                    best_snippet = self._extract_driver_snippet(claim, policy_terms) or claim[:220]
                if not best_snippet:
                    continue
                support_sentence = best_snippet.rstrip(" .")
                template = str(policy.get("support_answer_template") or "{support_sentence}")
                addition = _normalise_spaces(template.format(support_sentence=support_sentence))
                if addition and addition not in draft:
                    draft = _normalise_spaces(f"{draft} {addition}")
                    draft_lower = draft.lower()
        if not narrative_context_query:
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

        guidance_policy = dict(EVIDENCE_COMPRESSION_GUIDANCE_POLICY)
        if len(phrases) == 1:
            clause = phrases[0]
        elif len(phrases) == 2:
            clause = f"{phrases[0]}{guidance_policy.get('driver_pair_joiner') or ''} {phrases[1]}"
        else:
            phrase_joiner = str(guidance_policy.get("driver_phrase_joiner") or ", ")
            final_joiner = str(guidance_policy.get("driver_final_joiner") or ", ")
            clause = phrase_joiner.join(phrases[:-1]) + f"{final_joiner}{phrases[-1]}"
        addition = str(guidance_policy.get("driver_addition_template") or "{clause}").format(clause=clause)
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
        for group in query_focus_marker_groups(query_text):
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
            policy = dict(ENTITY_TABLE_SUMMARY_ASSEMBLY_POLICY)
            return re.findall(str(policy.get("number_pattern") or r"$^"), text)

        def _clean_amount(value: str) -> str:
            return value.strip()

        policy = dict(ENTITY_TABLE_SUMMARY_ASSEMBLY_POLICY)
        requested_consolidated = any(
            str(term) in query_text
            for term in (policy.get("consolidated_query_terms") or ())
        )
        investment_candidates: List[tuple[tuple[int, int, float, int], str, str, str, str, str]] = []
        summary_candidates: List[tuple[tuple[int, int], str, str, str, str]] = []
        supporting_anchors: List[str] = []

        def _section_score(section_path: str, text: str) -> int:
            score = 0
            for rule in policy.get("section_score_rules") or ():
                marker = str((rule or {}).get("text") or "")
                field = str((rule or {}).get("field") or "")
                if not marker:
                    continue
                haystack = section_path if field == "section_path" else text
                if marker in haystack:
                    score += int((rule or {}).get("score") or 0)
            text_terms, text_score = policy.get("text_score_terms") or ((), 0)
            if any(str(marker) in text for marker in text_terms):
                score += int(text_score or 0)
            negative_rule = dict(policy.get("negative_text_terms_without_anchor") or {})
            negative_terms = tuple(str(marker) for marker in (negative_rule.get("terms") or ()))
            negative_anchor = str(negative_rule.get("anchor") or "")
            if any(marker in text for marker in negative_terms) and negative_anchor not in text:
                score += int(negative_rule.get("score") or 0)
            penalty_rule = dict(policy.get("non_consolidated_section_penalty") or {})
            penalty_marker = str(penalty_rule.get("section_marker") or "")
            if not requested_consolidated and penalty_marker and penalty_marker in section_path:
                score += int(penalty_rule.get("score") or 0)
            return score

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
            section_score = _section_score(section_path, text)
            period_score = 1 if str(period_focus or "").lower() == "current" else 0
            for line, display_line in entity_lines:
                line_numbers = _numbers(line)
                if "%" in line and any(marker in text for marker in (policy.get("investment_metric_terms") or ())):
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
                if any(marker in text for marker in (policy.get("summary_metric_terms") or ())):
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
        role_labels = dict(policy.get("role_labels") or {})
        part_templates = dict(policy.get("part_templates") or {})
        default_unit = str(policy.get("default_unit") or "")
        sentences: List[str] = []
        if percent or amount:
            parts = []
            if percent:
                if prior_percent:
                    prior_label = str(role_labels.get("prior_ownership_ratio") or "prior_ownership_ratio")
                    current_label = str(role_labels.get("ownership_ratio") or "ownership_ratio")
                    parts.append(
                        str(part_templates.get("prior_current_ratio") or "{prior_label} {prior_percent} {current_label} {percent}").format(
                            prior_label=prior_label,
                            prior_percent=prior_percent,
                            current_label=current_label,
                            percent=percent,
                        )
                    )
                else:
                    current_label = str(role_labels.get("ownership_ratio") or "ownership_ratio")
                    parts.append(
                        str(part_templates.get("current_ratio") or "{current_label} {percent}").format(
                            current_label=current_label,
                            percent=percent,
                        )
                    )
            if amount:
                amount_label = str(role_labels.get("investment_carrying_amount") or "investment_carrying_amount")
                parts.append(
                    str(part_templates.get("amount") or "{amount_label} {amount}{unit}").format(
                        amount_label=amount_label,
                        amount=amount,
                        unit=default_unit,
                    )
                )
            sentence_template = str(policy.get("investment_sentence_template") or "{entity_label}: {parts}")
            sentences.append(sentence_template.format(entity_label=entity_label, parts=", ".join(parts)))
        if continuing or total_comprehensive:
            parts = []
            if continuing:
                role_key = "continuing_loss" if str(continuing).strip().startswith("(") else "continuing_profit_loss"
                continuing_label = str(role_labels.get(role_key) or role_key)
                parts.append(f"{continuing_label} {continuing}{default_unit}")
            if total_comprehensive:
                role_key = "total_comprehensive_loss" if str(total_comprehensive).strip().startswith("(") else "total_comprehensive_profit_loss"
                comprehensive_label = str(role_labels.get(role_key) or role_key)
                parts.append(f"{comprehensive_label} {total_comprehensive}{default_unit}")
            sentence_template = str(policy.get("summary_sentence_template") or "{parts}")
            sentences.append(sentence_template.format(entity_label=entity_label, parts=", ".join(parts)))
        answer = _normalise_spaces(" ".join(sentences))
        if not answer:
            return None

        selected_ids = [
            str(item.get("evidence_id") or "").strip()
            for item in evidence_items
            if str(item.get("source_anchor") or "").strip() in set(supporting_anchors)
            and str(item.get("evidence_id") or "").strip()
        ]

        def _resolved_period() -> str:
            candidates: List[Any] = [*re.findall(r"20\d{2}", query_text)]
            for item in docs or []:
                doc = item[0] if isinstance(item, (tuple, list)) else item
                metadata = getattr(doc, "metadata", {}) or {}
                candidates.append(metadata.get("year"))
            for item in evidence_items or []:
                metadata = dict((item or {}).get("metadata") or {})
                candidates.append(metadata.get("year"))
            for candidate in candidates:
                match = re.search(r"20\d{2}", str(candidate or ""))
                if match:
                    return match.group(0)
            return str(policy.get("period_fallback") or "")

        period = _resolved_period()

        def _operand_row(label: str, raw_value: str, raw_unit: str, role: str, anchor: str) -> Dict[str, Any]:
            normalized_value, normalized_unit = _normalise_operand_value(raw_value, raw_unit)
            source_row_id = f"{anchor}::{role}" if anchor else ""
            return {
                "operand_id": role,
                "matched_operand_role": role,
                "label": label,
                "concept": role,
                "period": period,
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
            calculation_operands.append(_operand_row(f"{entity_label} {role_labels.get('prior_ownership_ratio') or 'prior_ownership_ratio'}", prior_percent.replace("%", ""), "%", "prior_ownership_ratio", primary_anchor))
        if percent:
            calculation_operands.append(_operand_row(f"{entity_label} {role_labels.get('ownership_ratio') or 'ownership_ratio'}", percent.replace("%", ""), "%", "ownership_ratio", primary_anchor))
        if amount:
            calculation_operands.append(_operand_row(f"{entity_label} {role_labels.get('investment_carrying_amount') or 'investment_carrying_amount'}", amount, default_unit, "investment_carrying_amount", primary_anchor))
        if continuing:
            role_key = "continuing_loss" if str(continuing).strip().startswith("(") else "continuing_profit_loss"
            calculation_operands.append(_operand_row(f"{entity_label} {role_labels.get(role_key) or role_key}", continuing, default_unit, role_key, summary_anchor))
        if total_comprehensive:
            role_key = "total_comprehensive_loss" if str(total_comprehensive).strip().startswith("(") else "total_comprehensive_profit_loss"
            calculation_operands.append(_operand_row(f"{entity_label} {role_labels.get(role_key) or role_key}", total_comprehensive, default_unit, role_key, summary_anchor))
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
        policy = dict(DIVIDEND_POLICY_ASSEMBLY_POLICY)
        patterns = tuple(str(pattern) for pattern in (policy.get("amount_patterns") or ()) if str(pattern))
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
        policy = dict(DIVIDEND_POLICY_ASSEMBLY_POLICY)
        rank_patterns = dict(policy.get("rank_patterns") or {})
        jo_match = re.search(str(rank_patterns.get("trillion_eok") or r"$^"), surface)
        if jo_match:
            jo = int(jo_match.group(1))
            eok = int((jo_match.group(2) or "0").replace(",", ""))
            return float(jo * float(policy.get("trillion_to_eok_multiplier") or 10000) + eok)
        eok_match = re.search(str(rank_patterns.get("eok") or r"$^"), surface)
        if eok_match:
            return float(int(eok_match.group(1).replace(",", "")))
        million_match = re.search(str(rank_patterns.get("million_krw") or r"$^"), surface)
        if million_match:
            return float(int(million_match.group(1).replace(",", "")) / float(policy.get("million_krw_to_eok_divisor") or 100.0))
        return float("-inf")

    def _extract_dividend_policy_clause(self, text: str, *, preferred_markers: Optional[List[str]] = None) -> str:
        surface = _normalise_spaces(str(text or ""))
        if not surface:
            return ""
        policy = dict(DIVIDEND_POLICY_ASSEMBLY_POLICY)
        clause_max_chars = int(policy.get("clause_max_chars") or 240)
        fragments = [
            _normalise_spaces(fragment)
            for fragment in re.split(str(policy.get("clause_split_pattern") or r"$^"), surface)
            if _normalise_spaces(fragment)
        ]
        if preferred_markers:
            for fragment in fragments:
                if any(marker in fragment for marker in preferred_markers):
                    return fragment[:clause_max_chars]
        preferred_period_markers = tuple(str(item) for item in (policy.get("preferred_policy_period_markers") or ()) if str(item))
        for fragment in fragments:
            if preferred_period_markers and all(marker in fragment for marker in preferred_period_markers):
                return fragment[:clause_max_chars]
        return surface[:clause_max_chars]

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
        dividend_policy = dict(DIVIDEND_POLICY_ASSEMBLY_POLICY)
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
                    if any(term.lower() in section_hint for term in (dividend_policy.get("payout_priority_section_terms") or ())):
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
                    preferred_period_markers = tuple(str(item) for item in (dividend_policy.get("preferred_policy_period_markers") or ()) if str(item))
                    stale_period_markers = tuple(str(item) for item in (dividend_policy.get("stale_policy_period_markers") or ()) if str(item))
                    preferred_period_hit = bool(preferred_period_markers) and all(marker in clause for marker in preferred_period_markers)
                    if preferred_period_hit:
                        policy_score += 5.0
                    if stale_period_markers and all(marker in clause for marker in stale_period_markers) and not preferred_period_hit:
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

        year_match = re.search(str(dividend_policy.get("year_pattern") or r"$^"), _normalise_spaces(query))
        year = year_match.group(1) if year_match else ""
        year_prefix = str(dividend_policy.get("year_prefix_template") or "{year} ").format(year=year) if year else ""
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
        if not selected or not evidence_items or not query_requests_narrative_context(query):
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
        intro_patterns = tuple(str(item) for item in (SENTENCE_NORMALISATION_POLICY.get("intro_patterns") or ()))
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
                for sentence in split_sentences(compressed_answer)
            ]

        seen_sentences: set[str] = set()
        previous_keep_signature: Optional[tuple] = None
        previous_keep_tokens: set[str] = set()

        for index, entry in enumerate(raw_checks):
            sentence = _normalise_spaces(str(entry.get("sentence", "")))
            if not sentence or sentence in seen_sentences:
                continue
            seen_sentences.add(sentence)
            normalized_sentence = strip_anchor_text(sentence)

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
                reason = reason or str(SENTENCE_NORMALISATION_POLICY.get("missing_support_reason") or "")

            support_text = self._sentence_support_text(supporting_claim_ids, evidence_lookup)
            support_tokens = tokenize_terms(support_text)
            sentence_tokens = tokenize_terms(normalized_sentence)
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
                    reason = reason or str(SENTENCE_NORMALISATION_POLICY.get("summary_intro_reason") or "")
                else:
                    verdict = "drop_redundant"
                    reason = reason or str(SENTENCE_NORMALISATION_POLICY.get("redundant_intro_reason") or "")

            if verdict == "keep" and previous_keep_signature and tuple(supporting_claim_ids) == previous_keep_signature:
                overlap = len(sentence_tokens & previous_keep_tokens) / max(len(sentence_tokens | previous_keep_tokens), 1)
                if overlap >= 0.6:
                    verdict = "drop_redundant"
                    reason = reason or str(EVIDENCE_RUNTIME_POLICY.get("duplicate_claim_reason") or "")

            if verdict in {"drop_overextended", "drop_unsupported"} and aggregate_supported:
                verdict = "keep"
                reason = reason or str(EVIDENCE_RUNTIME_POLICY.get("aggregate_supported_reason") or "")

            if verdict == "drop_redundant" and query_type in {"business_overview", "risk"} and self._is_intro_sentence(sentence) and supporting_claim_ids:
                verdict = "keep"
                reason = reason or str(SENTENCE_NORMALISATION_POLICY.get("summary_intro_reason") or "")

            if verdict == "keep" and query_type in {"business_overview", "risk"} and support_tokens:
                if overlap_ratio < 0.2 and len(sentence_tokens) >= 5 and len(supporting_claim_ids) <= 1:
                    verdict = "drop_overextended"
                    reason = reason or str(EVIDENCE_RUNTIME_POLICY.get("overextended_reason") or "")

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
            final_answer = str(EVIDENCE_RUNTIME_POLICY.get("no_direct_evidence_answer") or "")

        return {
            "kept_claim_ids": kept_claim_ids,
            "dropped_claim_ids": dropped_claim_ids,
            "unsupported_sentences": unsupported_sentences,
            "sentence_checks": normalized,
            "answer": final_answer,
        }

    def _extract_evidence(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Convert retrieved docs into claim-level evidence items."""
        docs = state.get("retrieved_docs", [])
        if not docs:
            return {"evidence_bullets": [], "evidence_items": [], "evidence_status": "missing"}
        narrative_path = not bool(
            dict(state.get("semantic_plan") or {}).get("program_required")
        )

        EvidenceExtraction = evidence_extraction_model()
        structured_llm = self._llm_for_phase("evidence_extraction").with_structured_output(EvidenceExtraction)
        query_type = state.get("query_type", "qa")
        focus_terms = evidence_extraction_focus_terms(str(state.get("query") or ""))
        evidence_context = self._build_evidence_context(docs[: min(8, len(docs))], focus_terms=focus_terms)
        anchor_lookup = evidence_context["anchor_lookup"]
        extraction_policy = dict(EVIDENCE_EXTRACTION_POLICY)
        extra_rules = str(dict(extraction_policy.get("extra_rules_by_query_type") or {}).get(query_type) or "")
        if not extra_rules and narrative_path:
            extra_rules = str(
                dict(extraction_policy.get("extra_rules_by_answer_mode") or {}).get(
                    "narrative_summary"
                )
                or ""
            )
        prompt = chat_prompt_template_from_template(str(extraction_policy.get("prompt_template") or ""))

        try:
            result: EvidenceExtraction = (prompt | structured_llm).invoke(
                {
                    "query": state["query"],
                    "topic": state.get("topic") or state["query"],
                    "focus_terms": ", ".join(focus_terms),
                    "available_anchors": "\n".join(evidence_context["available_anchors"]),
                    "context": evidence_context["context"],
                    "extra_rules": extra_rules,
                }
            )
            evidence_items = [
                self._build_runtime_evidence_item(item, index, anchor_lookup)
                for index, item in enumerate(result.evidence, start=1)
            ]
            if narrative_path:
                evidence_items = self._supplement_dividend_policy_evidence(
                    evidence_items,
                    docs,
                    query=str(state.get("query") or ""),
                    anchor_lookup=anchor_lookup,
                )
                evidence_items = self._supplement_policy_realized_evidence(
                    evidence_items,
                    docs,
                    query=str(state.get("query") or ""),
                    anchor_lookup=anchor_lookup,
                )
                evidence_items = self._supplement_missing_focus_context_evidence(
                    evidence_items,
                    docs,
                    query=str(state.get("query") or ""),
                    anchor_lookup=anchor_lookup,
                    coverage=result.coverage,
                )
            evidence_bullets = [
                f"- {item.get('source_anchor', '?')} {item.get('claim', '')} ({item.get('support_level', 'context')})"
                for item in evidence_items
            ]
            if result.evidence and not evidence_items:
                logger.info("[evidence] filtered all extracted evidence items due to operand binding conflicts")
            logger.info("[evidence] coverage=%s bullets=%s", result.coverage, len(evidence_bullets))

            if not evidence_bullets and result.coverage == "missing":
                logger.info("[evidence] structured output returned missing with docs present")
                return {
                    "evidence_bullets": [],
                    "evidence_items": [],
                    "evidence_status": "missing",
                }

            return {
                "evidence_bullets": evidence_bullets,
                "evidence_items": evidence_items,
                "evidence_status": result.coverage,
            }
        except Exception as exc:
            logger.warning("Evidence extraction failed; preserving missing evidence: %s", exc)
            return {
                "evidence_bullets": [],
                "evidence_items": [],
                "evidence_status": "missing",
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
        selected_evidence = self._select_evidence_for_compression(evidence_items, query_type, state)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)
        guidance = compression_guidance(query_type, query, coverage)

        compression_llm = self._llm_for_phase("compression")
        CompressionOutput = compression_output_model()
        structured_llm = compression_llm.with_structured_output(CompressionOutput)
        prompt = chat_prompt_template_from_template(
            str(EVIDENCE_RUNTIME_POLICY.get("compression_prompt_template") or "")
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
                selected_evidence = self._select_evidence_for_compression(evidence_items, query_type, state)
                if not selected_claim_ids:
                    selected_claim_ids = [
                        str(item.get("evidence_id") or "")
                        for item in selected_evidence
                        if str(item.get("evidence_id") or "").strip()
                    ]
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
            chain = prompt | compression_llm | str_output_parser()
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


    def _validate_answer(self, state: NarrativeInput) -> NarrativeResultPhase:
        """Check whether the drafted narrative answer is supported by evidence."""
        compressed_answer = state.get("compressed_answer", "")
        if not compressed_answer:
            return {
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "validated_sentences": [],
            }

        query_type = state.get("query_type", "qa")
        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        selected_claim_ids = state.get("selected_claim_ids", [])
        selected_evidence = self._filter_evidence_by_ids(evidence_items, selected_claim_ids)
        if not selected_evidence:
            selected_evidence = self._select_evidence_for_compression(evidence_items, query_type, state)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)

        validation_llm = self._llm_for_phase("validation")
        ValidationOutput = validation_output_model()
        structured_llm = validation_llm.with_structured_output(ValidationOutput)
        validator_prompt = chat_prompt_template_from_template(
            str(EVIDENCE_RUNTIME_POLICY.get("validation_prompt_template") or "")
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
                    "validated_sentences": [str(deterministic_dividend_answer.get("answer") or "")],
                }
            augmented_answer = self._augment_narrative_answer_with_supported_drivers(
                str(normalized_result.get("answer") or ""),
                selected_evidence,
                query=str(state.get("query") or ""),
            )
            if augmented_answer:
                normalized_result["answer"] = augmented_answer
            validated_text = str(normalized_result.pop("answer", "") or "")
            normalized_result["validated_sentences"] = [validated_text] if validated_text else []
            return normalized_result
        except Exception as exc:
            logger.warning("Validation structured output failed, using fallback text output: %s", exc)
            validated_answer = (validator_prompt | validation_llm | str_output_parser()).invoke(
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
                    "validated_sentences": [str(deterministic_dividend_answer.get("answer") or "")],
                }
            augmented_answer = self._augment_narrative_answer_with_supported_drivers(
                str(normalized_result.get("answer") or ""),
                selected_evidence,
                query=str(state.get("query") or ""),
            )
            if augmented_answer:
                normalized_result["answer"] = augmented_answer
            validated_text = str(normalized_result.pop("answer", "") or "")
            normalized_result["validated_sentences"] = [validated_text] if validated_text else []
            return normalized_result
