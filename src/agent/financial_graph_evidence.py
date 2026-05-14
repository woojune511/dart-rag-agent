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
from src.agent.financial_graph_models import CompressionOutput, EvidenceExtraction, EvidenceItem, FinancialAgentState, NumericExtraction, ValidationOutput
from src.config import get_financial_ontology

logger = logging.getLogger(__name__)

class FinancialAgentEvidenceMixin:
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
        companies = {company.lower() for company in state.get("companies", [])}
        years = {int(year) for year in state.get("years", [])}
        topic_terms = _tokenize_terms(state.get("topic") or state["query"])
        section_filter = (state.get("section_filter") or "").strip()
        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = state.get("format_preference") or self._default_format_preference(intent)
        metric_terms = _metric_terms_from_topic(state.get("topic") or state["query"])
        preferred_sections = _active_preferred_sections(state, state["query"], state.get("topic") or "", intent)
        desired_statement_types = set(_active_preferred_statement_types(state, state["query"], state.get("topic") or ""))
        desired_consolidation = _desired_consolidation_scope(state["query"], dict(state.get("report_scope") or {}))
        query_years = sorted(years)

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

            reranked.append((doc, boosted))

        reranked.sort(key=lambda item: item[1], reverse=True)
        return reranked

    def _retrieve(self, state: FinancialAgentState) -> Dict[str, Any]:
        """Retrieve top candidate chunks and rerank them for the active task."""
        query = state["query"]
        retrieval_queries = [str(item).strip() for item in (state.get("retrieval_queries") or []) if str(item).strip()]
        report_scope = dict(state.get("report_scope") or {})
        companies = list(state.get("companies", []) or [])
        years = list(state.get("years", []) or [])
        scope_company = str(report_scope.get("company") or "").strip()
        if scope_company and scope_company not in companies:
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
        scope_consolidation = str(report_scope.get("consolidation") or "").strip()
        section_filter = state.get("section_filter")
        intent = state.get("intent") or state.get("query_type", "qa")
        reflection_count = int(state.get("reflection_count") or 0)
        retry_queries = [str(item).strip() for item in (state.get("retry_queries") or []) if str(item).strip()]
        effective_k = self.k if reflection_count <= 0 else max(self.k * 2, 4)

        conditions = []
        if companies:
            if len(companies) == 1:
                conditions.append({"company": companies[0]})
            else:
                conditions.append({"company": {"$in": companies}})
        if years:
            int_years = [int(year) for year in years]
            if intent in {"comparison", "trend"} and len(int_years) > 1:
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
        if scope_rcept_no:
            conditions.append({"rcept_no": scope_rcept_no})

        if not conditions:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        retrieval_hint = _retrieval_hint_from_topic(query, state.get("topic") or query, intent)
        preferred_sections = _active_preferred_sections(state, query, state.get("topic") or "", intent)
        query_bundle = retrieval_queries or [query]
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
            batch_docs = self.vsm.search(enriched_query, k=effective_k * 4, where_filter=where_filter)
            docs = batch_docs if not docs else self._merge_retry_candidates(docs, batch_docs)
        if retry_queries:
            retry_docs: List[tuple[Document, float]] = []
            for retry_query in retry_queries[:3]:
                retry_docs.extend(self.vsm.search(retry_query, k=max(effective_k * 2, 8), where_filter=where_filter))
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

        if companies:
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

        if years:
            valid_years = {int(year) for year in years}
            docs = self._apply_strict_filter(
                docs,
                lambda doc: int(doc.metadata.get("year", 0)) in valid_years,
            )

        reranked = self._rerank_docs(docs, state)

        # format_preference에 따라 표/단락 비율 보장
        intent = state.get("intent") or state.get("query_type", "qa")
        format_preference = state.get("format_preference") or self._default_format_preference(intent)
        if format_preference == "table":
            # 수치·추이 쿼리: 표 우선, 단락 최소 2개 보장
            tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
            min_para = min(2, len(paras))
            docs = (tables[: effective_k - min_para] + paras[:min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
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
        logger.info(
            "[retrieve] intent=%s format=%s final %s chunks returned",
            intent,
            format_preference,
            len(docs),
        )
        return {"seed_retrieved_docs": seed_docs, "retrieved_docs": docs}

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
        anchor_lookup: Dict[str, Dict[str, Any]] = {}
        seen_parents: set = set()

        for doc, _score in docs:
            metadata = doc.metadata or {}
            anchor = self._build_source_anchor(metadata)
            anchor_lookup[anchor] = {
                "company": metadata.get("company"),
                "year": metadata.get("year"),
                "report_type": metadata.get("report_type"),
                "section": metadata.get("section"),
                "section_path": metadata.get("section_path", metadata.get("section")),
                "block_type": metadata.get("block_type"),
                "graph_relation": metadata.get("graph_relation"),
                "chunk_uid": metadata.get("chunk_uid"),
                "parent_id": metadata.get("parent_id"),
            }

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

    def _build_runtime_evidence_item(
        self,
        item: EvidenceItem,
        index: int,
        anchor_lookup: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        metadata = dict(anchor_lookup.get(item.source_anchor) or {})
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
            label_name = str(operand.get("label") or "").strip()
            if not label_name:
                continue
            for item in prioritized_items:
                raw_row = _normalise_spaces(str(item.get("raw_row_text") or item.get("claim") or ""))
                if not raw_row or not _operand_text_match(raw_row, operand):
                    continue

                period = ""
                context_text = _normalise_spaces(f"{item.get('source_context') or ''} {raw_row}")
                for token in query_years or year_pattern.findall(context_text):
                    period = token
                    break

                raw_value = _normalise_spaces(str(item.get("matched_value") or ""))
                raw_unit = str(item.get("matched_unit") or "")

                if not raw_value:
                    metadata = dict(item.get("metadata") or {})
                    parsed_cells = _parse_unstructured_table_row_cells(raw_row, metadata)
                    if parsed_cells:
                        target_years = [int(token.replace("년", "")) for token in query_years] if query_years else []
                        ranked_cells = sorted(
                            parsed_cells,
                            key=lambda cell: _score_structured_cell(
                                cell,
                                query_years=target_years,
                                period_focus="unknown",
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
                    raw_value = _extract_numeric_value_after_operand_text(raw_row, operand)
                    if raw_value and not raw_unit:
                        if "조" in raw_value or "억" in raw_value:
                            raw_unit = "원"
                        elif "백만원" in context_text:
                            raw_unit = "백만원"

                if not raw_value:
                    continue

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
            "trend": "시계열 변화와 근거에 직접 있는 원인만 짧게 정리하세요.",
            "qa": "질문에 직접 답하는 핵심 사실만 짧게 답하세요.",
        }
        output_styles = {
            "numeric_fact": "최대 1문장.",
            "business_overview": "각 부문의 구체적 제품/역할이 포함된 3~5개의 bullet.",
            "risk": "항목별로 이름과 짧은 설명(1~2줄)이 함께 있는 bullet. 항목 수는 evidence 범위를 넘기지 말 것.",
            "comparison": "짧은 bullet 비교.",
            "trend": "2~4문장.",
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

        def _deterministic_fallback(doc_list) -> tuple[List[str], List[Dict[str, Any]]]:
            bullets = []
            items = []
            for doc, _score in doc_list[: min(6, len(doc_list))]:
                metadata = doc.metadata or {}
                anchor = self._build_source_anchor(metadata)
                snippet = re.sub(r"\s+", " ", doc.page_content).strip()[:220]
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
                        "metadata": dict(anchor_lookup.get(anchor) or {}),
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
            evidence_bullets = [
                f"- {item.source_anchor} {item.claim} ({item.support_level})"
                for item in result.evidence
            ]
            logger.info("[evidence] coverage=%s bullets=%s", result.coverage, len(evidence_bullets))

            # structured output이 missing을 반환했지만 docs는 있는 경우:
            # hard abstain 대신 deterministic fallback으로 sparse 답변 시도
            if not evidence_bullets and result.coverage == "missing":
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
            logger.info("[compress] typed compression generated")
            return {
                "selected_claim_ids": compressed.selected_claim_ids,
                "draft_points": compressed.draft_points,
                "compressed_answer": compressed.draft_answer,
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
            return {
                "selected_claim_ids": [item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")],
                "draft_points": [item.get("claim", "") for item in selected_evidence if item.get("claim")][:4],
                "compressed_answer": compressed_answer,
            }

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
            return self._normalise_sentence_checks(
                query_type=query_type,
                compressed_answer=validated.final_answer or compressed_answer,
                sentence_checks=validated.sentence_checks,
                selected_claim_ids=[item.get("evidence_id", "") for item in selected_evidence if item.get("evidence_id")],
                evidence_items=selected_evidence,
            )
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
            return self._normalise_sentence_checks(
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

