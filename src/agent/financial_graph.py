"""
LangGraph-based DART financial analysis agent.
"""

import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field
from src.routing import QueryRouter, default_format_preference

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_CONTEXT_MAX_WORKERS = max(4, min(12, (os.cpu_count() or 4) * 2))
DEFAULT_CONTEXT_BATCH_SIZE = max(8, DEFAULT_CONTEXT_MAX_WORKERS * 2)


def _extract_usage_counts(response: Any) -> Dict[str, int]:
    usage = getattr(response, "usage_metadata", None) or {}
    response_metadata = getattr(response, "response_metadata", None) or {}
    token_usage = response_metadata.get("token_usage") or {}

    prompt_tokens = (
        usage.get("input_tokens")
        or usage.get("prompt_token_count")
        or token_usage.get("input_tokens")
        or token_usage.get("prompt_token_count")
        or 0
    )
    output_tokens = (
        usage.get("output_tokens")
        or usage.get("candidates_token_count")
        or token_usage.get("output_tokens")
        or token_usage.get("candidates_token_count")
        or 0
    )
    total_tokens = (
        usage.get("total_tokens")
        or usage.get("total_token_count")
        or token_usage.get("total_tokens")
        or token_usage.get("total_token_count")
        or (prompt_tokens + output_tokens)
    )

    return {
        "prompt_tokens": int(prompt_tokens or 0),
        "output_tokens": int(output_tokens or 0),
        "total_tokens": int(total_tokens or 0),
    }


def _tokenize_terms(text: str) -> set[str]:
    tokens = re.findall(r"[가-힣A-Za-z0-9]+", text or "")
    return {token.lower() for token in tokens if len(token) >= 2}


def _normalise_spaces(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _split_sentences(text: str) -> List[str]:
    cleaned = _normalise_spaces(text)
    if not cleaned:
        return []
    parts = re.split(r"(?<=[.!?])\s+|(?<=다)\s+", cleaned)
    return [part.strip() for part in parts if part.strip()]


def _strip_anchor_text(text: str) -> str:
    cleaned = re.sub(r"\[[^\]]+\]", " ", text or "")
    cleaned = re.sub(r"^[*\-\u2022]+\s*", "", cleaned)
    return _normalise_spaces(cleaned)


class FinancialAgentState(TypedDict):
    query: str
    query_type: str
    intent: str
    format_preference: str
    routing_source: str
    routing_confidence: float
    routing_scores: Dict[str, float]
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    seed_retrieved_docs: List
    retrieved_docs: List
    evidence_bullets: List[str]
    evidence_items: List[Dict[str, Any]]
    evidence_status: str
    selected_claim_ids: List[str]
    draft_points: List[str]
    compressed_answer: str
    kept_claim_ids: List[str]
    dropped_claim_ids: List[str]
    unsupported_sentences: List[str]
    sentence_checks: List[Dict[str, Any]]
    answer: str
    citations: List[str]


class EntityExtraction(BaseModel):
    companies: List[str] = Field(default_factory=list, description="질문에 등장한 기업명 목록")
    years: List[int] = Field(default_factory=list, description="질문에 등장한 연도 목록")
    topic: str = Field(description="질문의 핵심 분석 주제")
    section_filter: Optional[str] = Field(
        default=None,
        description=(
            "관련 섹션 레이블 하나. 예: 리스크, 재무제표, 연결재무제표, 요약재무, 재무주석, "
            "사업개요, 주요제품, 원재료, 매출현황, 연구개발, 경영진단, 임원현황, 이사회, 주주현황, 계열회사"
        ),
    )


class EvidenceItem(BaseModel):
    source_anchor: str = Field(description="근거 출처 앵커. 예: [삼성전자 | 2023 | 사업의 개요]")
    claim: str = Field(description="질문에 직접적으로 도움이 되는 근거 진술")
    support_level: Literal["direct", "partial", "context"] = Field(
        description="direct=직접 근거, partial=부분 근거, context=배경 설명"
    )
    quote_span: str = Field(
        default="",
        description="원문에서 발췌한 짧은 근거 구간",
    )
    question_relevance: Literal["high", "medium", "low"] = Field(
        default="medium",
        description="질문과의 직접 관련도",
    )
    allowed_terms: List[str] = Field(
        default_factory=list,
        description="최종 답변에서 사용해도 되는 핵심 용어 목록",
    )


class EvidenceExtraction(BaseModel):
    coverage: Literal["sufficient", "sparse", "conflicting", "missing"]
    evidence: List[EvidenceItem] = Field(default_factory=list)


class CompressionOutput(BaseModel):
    selected_claim_ids: List[str] = Field(
        default_factory=list,
        description="답변 초안에 실제로 사용한 evidence_id 목록",
    )
    draft_points: List[str] = Field(
        default_factory=list,
        description="최종 초안으로 압축하기 전 핵심 포인트 목록",
    )
    draft_answer: str = Field(
        description="structured evidence만으로 압축한 답변 초안",
    )


class ValidationOutput(BaseModel):
    kept_claim_ids: List[str] = Field(
        default_factory=list,
        description="검증 후 최종 답변에 남긴 evidence_id 목록",
    )
    dropped_claim_ids: List[str] = Field(
        default_factory=list,
        description="검증 과정에서 제거한 evidence_id 목록",
    )
    unsupported_sentences: List[str] = Field(
        default_factory=list,
        description="근거 부족 또는 과잉 설명으로 제거한 문장 목록",
    )
    sentence_checks: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="문장별 검증 결과. sentence, verdict, reason, supporting_claim_ids를 포함",
    )
    final_answer: str = Field(
        description="검증을 거친 최종 답변",
    )


class FinancialAgent:
    _SECTION_BIAS_BY_QUERY_TYPE = {
        "numeric_fact": (
            ("손익계산서", 0.08),
            ("매출 및 수주상황", 0.08),
            ("요약재무정보", 0.06),
            ("연결재무제표", 0.06),
        ),
        "business_overview": (
            ("II. 사업의 내용 > 1. 사업의 개요", 0.14),
            ("II. 사업의 내용 > 2. 주요 제품 및 서비스", 0.10),
            ("사업의 개요", 0.06),
        ),
        "risk": (
            ("위험관리 및 파생거래", 0.18),
            ("리스크", 0.10),
        ),
    }

    def __init__(self, vector_store_manager, k: int = 8, graph_expansion_config: Optional[Dict[str, Any]] = None):
        self.vsm = vector_store_manager
        self.k = k
        self.graph_expansion_config = {
            "enabled": False,
            "include_parent_context": True,
            "include_section_lead": True,
            "include_described_by_paragraph": True,
            "include_table_context": True,
            "include_sibling_prev": True,
            "include_sibling_next": False,
            "table_sibling_prev_paragraph_only": True,
            "sibling_window": 1,
            "max_docs": k,
        }
        if graph_expansion_config:
            self.graph_expansion_config.update(graph_expansion_config)

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.query_router = QueryRouter(embeddings=self.vsm.embeddings, llm=self.llm)
        self.graph = self._build_graph()

    def _default_format_preference(self, intent: str) -> str:
        return default_format_preference(intent)

    def _classify_query(self, state: FinancialAgentState) -> Dict[str, Any]:
        result = self.query_router.route(state["query"])
        return {
            "query_type": result.intent,
            "intent": result.intent,
            "format_preference": result.format_preference,
            "routing_source": result.routing_source,
            "routing_confidence": float(result.routing_confidence or 0.0),
            "routing_scores": dict(result.routing_scores or {}),
        }

    def _extract_entities(self, state: FinancialAgentState) -> Dict[str, Any]:
        structured_llm = self.llm.with_structured_output(EntityExtraction)
        prompt = ChatPromptTemplate.from_template(
            "다음 질문에서 기업명, 연도, 핵심 주제, 관련 섹션을 추출하세요.\n\n질문: {query}"
        )
        result: EntityExtraction = (prompt | structured_llm).invoke({"query": state["query"]})
        logger.info(
            "[extract] companies=%s years=%s topic=%s section_filter=%s",
            result.companies,
            result.years,
            result.topic,
            result.section_filter,
        )
        return {
            "companies": result.companies,
            "years": result.years,
            "topic": result.topic,
            "section_filter": result.section_filter,
        }

    def _apply_strict_filter(self, docs, predicate):
        filtered = [item for item in docs if predicate(item[0])]
        return filtered if filtered else docs

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

        reranked = []
        for doc, score in docs:
            metadata = doc.metadata or {}
            company = str(metadata.get("company", "")).lower()
            year = metadata.get("year")
            section = str(metadata.get("section", ""))
            section_path = str(metadata.get("section_path", section))
            block_type = metadata.get("block_type", "")
            document_terms = _tokenize_terms(
                " ".join(
                    [
                        doc.page_content,
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
        query = state["query"]
        companies = state.get("companies", [])
        years = state.get("years", [])
        section_filter = state.get("section_filter")

        conditions = []
        if companies:
            if len(companies) == 1:
                conditions.append({"company": companies[0]})
            else:
                conditions.append({"company": {"$in": companies}})
        if years:
            int_years = [int(year) for year in years]
            if len(int_years) == 1:
                conditions.append({"year": int_years[0]})
            else:
                conditions.append({"year": {"$in": int_years}})

        if not conditions:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        enriched_query = f"{' '.join(companies)} {query}" if companies else query
        docs = self.vsm.search(enriched_query, k=self.k * 4, where_filter=where_filter)

        logger.info(
            "[retrieve] companies=%s years=%s topic=%s where=%s -> %s candidates",
            companies,
            years,
            state.get("topic"),
            where_filter,
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
            docs = (tables[: self.k - min_para] + paras[:min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        elif format_preference == "paragraph":
            # 개요·리스크·일반 쿼리: 단락 최소 절반 보장
            tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
            min_para = min(self.k // 2, len(paras))
            docs = (paras[:min_para] + tables[: self.k - min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        else:
            docs = reranked

        docs = docs[: self.k]
        logger.info(
            "[retrieve] intent=%s format=%s final %s chunks returned",
            intent,
            format_preference,
            len(docs),
        )
        return {"seed_retrieved_docs": docs, "retrieved_docs": docs}

    def _expand_via_structure_graph(self, state: FinancialAgentState) -> Dict[str, Any]:
        config = dict(self.graph_expansion_config or {})
        if not config.get("enabled"):
            return {}

        seed_docs = list(state.get("retrieved_docs", []) or [])
        if not seed_docs:
            return {}

        include_parent_context = bool(config.get("include_parent_context", True))
        include_section_lead = bool(config.get("include_section_lead", True))
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
            "[graph_expand] seed=%s expanded=%s parent=%s sibling_prev=%s sibling_next=%s sibling_window=%s table_context=%s max_docs=%s",
            len(seed_docs),
            len(expanded),
            include_parent_context,
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

        return {
            "evidence_id": f"ev_{index:03d}",
            "source_anchor": item.source_anchor,
            "claim": item.claim,
            "quote_span": item.quote_span,
            "support_level": item.support_level,
            "question_relevance": item.question_relevance,
            "allowed_terms": allowed_terms,
            "metadata": metadata,
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
                    f"  claim: {item.get('claim', '')}",
                ]
                if quote_span:
                    lines.append(f"  quote_span: {quote_span}")
                if allowed_terms:
                    lines.append(f"  allowed_terms: {allowed_terms}")
                parts.append("\n".join(lines))
            return "\n\n".join(parts)
        return "\n".join(evidence_bullets)

    def _select_evidence_for_compression(self, evidence_items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not evidence_items:
            return []
        ranked = self._sort_evidence_items(evidence_items)
        high_priority = [item for item in ranked if item.get("question_relevance") == "high"]
        medium_priority = [item for item in ranked if item.get("question_relevance") == "medium"]
        low_priority = [item for item in ranked if item.get("question_relevance") == "low"]

        selected: List[Dict[str, Any]] = []
        for pool in (high_priority, medium_priority, low_priority):
            for item in pool:
                selected.append(item)
                if len(selected) >= 6:
                    return selected
        return selected[:6]

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
                "질문에 직접 필요한 사업 구조만 간단히 정리하세요. 같은 사실을 반복하지 말고, "
                "질문이 묻지 않은 배경 설명이나 예시는 빼세요."
            ),
            "risk": (
                "근거에 있는 리스크 항목만 나열하세요. 새 taxonomy를 만들거나 상위 범주로 재구성하지 마세요."
            ),
            "comparison": "각 항목을 나란히 비교하되, evidence에 직접 있는 차이만 정리하세요.",
            "trend": "시계열 변화와 근거에 직접 있는 원인만 짧게 정리하세요.",
            "qa": "질문에 직접 답하는 핵심 사실만 짧게 답하세요.",
        }
        output_styles = {
            "numeric_fact": "최대 1문장.",
            "business_overview": "최대 3개 bullet 또는 2문장.",
            "risk": "bullet 위주, 항목 수는 evidence 범위를 넘기지 말 것.",
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
        docs = state.get("retrieved_docs", [])
        if not docs:
            return {"evidence_bullets": [], "evidence_items": [], "evidence_status": "missing"}

        structured_llm = self.llm.with_structured_output(EvidenceExtraction)
        query_type = state.get("query_type", "qa")
        evidence_context = self._build_evidence_context(docs[: min(8, len(docs))])
        anchor_lookup = evidence_context["anchor_lookup"]
        extra_rules = (
            "\n- 리스크 유형명은 컨텍스트에 명시된 단어만 사용하세요. "
            "컨텍스트에 없는 리스크 카테고리(예: '운영위험', '규제위험' 등)를 새로 만들지 마세요."
        ) if query_type == "risk" else ""
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
        selected_evidence = self._select_evidence_for_compression(evidence_items)
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
- 핵심 주장에는 source_anchor를 자연스럽게 반영하세요.
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
        compressed_answer = state.get("compressed_answer", "")
        if not compressed_answer:
            return {
                "kept_claim_ids": [],
                "dropped_claim_ids": [],
                "unsupported_sentences": [],
                "sentence_checks": [],
                "answer": compressed_answer,
            }

        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        selected_claim_ids = state.get("selected_claim_ids", [])
        selected_evidence = self._filter_evidence_by_ids(evidence_items, selected_claim_ids)
        if not selected_evidence:
            selected_evidence = self._select_evidence_for_compression(evidence_items)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)
        query_type = state.get("query_type", "qa")

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

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        seen = set()
        citations: List[str] = []
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

    def _build_graph(self):
        graph = StateGraph(FinancialAgentState)

        graph.add_node("classify", self._classify_query)
        graph.add_node("extract", self._extract_entities)
        graph.add_node("retrieve", self._retrieve)
        graph.add_node("expand", self._expand_via_structure_graph)
        graph.add_node("evidence", self._extract_evidence)
        graph.add_node("compress", self._compress_answer)
        graph.add_node("validate", self._validate_answer)
        graph.add_node("cite", self._format_citations)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "extract")
        graph.add_edge("extract", "retrieve")
        graph.add_edge("retrieve", "expand")
        graph.add_edge("expand", "evidence")
        graph.add_edge("evidence", "compress")
        graph.add_edge("compress", "validate")
        graph.add_edge("validate", "cite")
        graph.add_edge("cite", END)

        return graph.compile()

    def run(self, query: str) -> Dict[str, Any]:
        initial: FinancialAgentState = {
            "query": query,
            "query_type": "",
            "intent": "",
            "format_preference": "",
            "routing_source": "",
            "routing_confidence": 0.0,
            "routing_scores": {},
            "companies": [],
            "years": [],
            "topic": "",
            "section_filter": None,
            "seed_retrieved_docs": [],
            "retrieved_docs": [],
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
        }
        final = self.graph.invoke(initial)
        return {
            "query": final["query"],
            "query_type": final["query_type"],
            "intent": final.get("intent", final["query_type"]),
            "format_preference": final.get("format_preference", ""),
            "routing_source": final.get("routing_source", ""),
            "routing_confidence": final.get("routing_confidence", 0.0),
            "routing_scores": final.get("routing_scores", {}),
            "companies": final["companies"],
            "years": final["years"],
            "answer": final["answer"],
            "citations": final["citations"],
            "seed_retrieved_docs": final.get("seed_retrieved_docs", []),
            "retrieved_docs": final["retrieved_docs"],
            "evidence_items": final.get("evidence_items", []),
            "selected_claim_ids": final.get("selected_claim_ids", []),
            "draft_points": final.get("draft_points", []),
            "kept_claim_ids": final.get("kept_claim_ids", []),
            "dropped_claim_ids": final.get("dropped_claim_ids", []),
            "unsupported_sentences": final.get("unsupported_sentences", []),
            "sentence_checks": final.get("sentence_checks", []),
        }

    def ingest(self, chunks: List) -> None:
        if not chunks:
            logger.warning("[ingest] chunks are empty.")
            return
        texts = [chunk.content for chunk in chunks]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)
        logger.info("[ingest] indexed %s chunks", len(chunks))

    # ------------------------------------------------------------------
    # Contextual Retrieval + Parent-child ingest
    # ------------------------------------------------------------------

    def _generate_context(self, text: str, metadata: dict) -> str:
        """청크 1개에 대해 LLM으로 1문장 컨텍스트 설명 생성.

        생성된 컨텍스트는 청크 텍스트 앞에 붙여 인덱싱함으로써
        BM25·벡터 검색 양쪽에서 섹션/주제 신호를 강화한다.
        """
        company      = metadata.get("company", "?")
        year         = metadata.get("year", "?")
        section_path = metadata.get("section_path", metadata.get("section", "?"))
        block_type   = "표" if metadata.get("block_type") == "table" else "단락"
        preview      = re.sub(r"\s+", " ", text[:400]).strip()

        prompt = (
            f"다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션에서 발췌한 {block_type}입니다.\n"
            f"이 내용이 전체 문서 맥락에서 어떤 정보를 담고 있는지 한국어로 한 문장(50자 이내)으로만 설명하세요.\n\n"
            f"내용:\n{preview}"
        )
        try:
            response = self.llm.invoke(prompt)
            return response.content.strip()
        except Exception as e:
            logger.warning("Context generation failed: %s", e)
            return f"{company} {year}년 사업보고서 / {section_path} / {block_type}"

    def _fallback_context(self, metadata: dict) -> str:
        company = metadata.get("company", "?")
        year = metadata.get("year", "?")
        section_path = metadata.get("section_path", metadata.get("section", "?"))
        block_type = "표" if metadata.get("block_type") == "table" else "단락"
        return f"{company} {year}년 사업보고서 / {section_path} / {block_type}"

    def _build_context_prompt(self, text: str, metadata: dict) -> str:
        company = metadata.get("company", "?")
        year = metadata.get("year", "?")
        section_path = metadata.get("section_path", metadata.get("section", "?"))
        block_type = "표" if metadata.get("block_type") == "table" else "단락"
        preview = re.sub(r"\s+", " ", text[:400]).strip()
        return (
            f"다음은 {company} {year}년 사업보고서의 [{section_path}] 섹션에서 발췌한 {block_type}입니다.\n"
            f"이 내용이 전체 문서 맥락에서 어떤 정보를 담고 있는지 한국어로 한 문장(50자 이내)으로만 설명하세요.\n\n"
            f"내용:\n{preview}"
        )

    def _build_index_prefix(self, metadata: dict, context: str) -> str:
        company = metadata.get("company", "?")
        year = metadata.get("year", "?")
        report_type = metadata.get("report_type", "?")
        section = metadata.get("section", "?")
        section_path = metadata.get("section_path", section)
        block_type = "표" if metadata.get("block_type") == "table" else "단락"
        return "\n".join(
            [
                context.strip(),
                f"{company} {year} {report_type}",
                f"섹션: {section_path}",
                f"분류: {section} / {block_type}",
            ]
        )

    def _resolve_context_workers(self, max_workers: Optional[int], total: int) -> int:
        if total <= 0:
            return 1

        configured = max_workers or int(
            os.environ.get("CONTEXTUAL_INGEST_MAX_WORKERS", DEFAULT_CONTEXT_MAX_WORKERS)
        )
        return max(1, min(configured, total))

    def _resolve_context_batch_size(self, batch_size: Optional[int], workers: int) -> int:
        configured = batch_size or int(
            os.environ.get("CONTEXTUAL_INGEST_BATCH_SIZE", DEFAULT_CONTEXT_BATCH_SIZE)
        )
        return max(workers, configured)

    def contextual_ingest(
        self,
        chunks: List,
        on_progress=None,
        max_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
    ) -> None:
        """Contextual Retrieval + Parent-child 방식으로 청크를 인덱싱한다.

        1. 섹션 단위 부모 청크를 생성해 VectorStoreManager에 저장
        2. 각 자식 청크에 대해 LLM으로 컨텍스트 문장 생성 (병렬 처리)
        3. '컨텍스트 + 원문'을 ChromaDB·BM25에 인덱싱

        Args:
            chunks:       FinancialParser.process_document() 반환값
            on_progress:  진행 콜백 (completed: int, total: int) → None
            max_workers:  LLM 병렬 호출 수
            batch_size:   한 번에 LLM.batch()로 보내는 요청 수
        """
        if not chunks:
            logger.warning("[contextual_ingest] chunks are empty.")
            return {
                "mode": "contextual",
                "chunks": 0,
                "stored_parent_chunks": 0,
                "api_calls": 0,
                "fallback_count": 0,
                "prompt_chars": 0,
                "response_chars": 0,
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "max_workers": 0,
                "batch_size": 0,
                "elapsed_sec": 0.0,
            }

        from processing.financial_parser import FinancialParser

        # 1) 부모 청크 저장
        parents = FinancialParser.build_parents(chunks)
        self.vsm.add_parents(parents)
        logger.info("[contextual_ingest] stored %s parent chunks", len(parents))

        # 2) 배치 병렬 컨텍스트 생성
        total = len(chunks)
        contexts: Dict[int, str] = {}
        workers = self._resolve_context_workers(max_workers, total)
        request_batch_size = self._resolve_context_batch_size(batch_size, workers)
        completed_count = 0

        logger.info(
            "[contextual_ingest] generating contexts with max_workers=%s batch_size=%s",
            workers,
            request_batch_size,
        )

        for start in range(0, total, request_batch_size):
            batch_items = list(enumerate(chunks[start : start + request_batch_size], start=start))
            prompts = [self._build_context_prompt(chunk.content, chunk.metadata) for _, chunk in batch_items]

            try:
                responses = self.llm.batch(
                    prompts,
                    config={"max_concurrency": workers},
                    return_exceptions=True,
                )
            except Exception as exc:
                logger.warning("Context batch generation failed, falling back to per-item mode: %s", exc)
                responses = [exc] * len(batch_items)

            for (idx, chunk), response in zip(batch_items, responses):
                if isinstance(response, Exception):
                    logger.warning("Context generation failed for chunk %s: %s", idx, response)
                    contexts[idx] = self._fallback_context(chunk.metadata)
                else:
                    content = getattr(response, "content", "") or ""
                    contexts[idx] = content.strip() or self._fallback_context(chunk.metadata)

                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)

        # 3) 컨텍스트 prefix를 붙여 인덱싱
        texts = [
            f"{self._build_index_prefix(chunks[i].metadata, contexts[i])}\n\n{chunks[i].content}"
            for i in range(total)
        ]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)
        logger.info("[contextual_ingest] indexed %s contextualized chunks", total)

    def benchmark_contextual_ingest(
        self,
        chunks: List,
        on_progress=None,
        max_workers: Optional[int] = None,
        batch_size: Optional[int] = None,
        return_artifacts: bool = False,
    ) -> Dict[str, Any]:
        """Contextual ingest variant that returns timing and usage metrics."""
        if not chunks:
            return {
                "mode": "contextual",
                "chunks": 0,
                "stored_parent_chunks": 0,
                "api_calls": 0,
                "fallback_count": 0,
                "prompt_chars": 0,
                "response_chars": 0,
                "prompt_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "max_workers": 0,
                "batch_size": 0,
                "elapsed_sec": 0.0,
            }

        from processing.financial_parser import FinancialParser

        started_at = time.perf_counter()
        parents = FinancialParser.build_parents(chunks)
        self.vsm.add_parents(parents)

        total = len(chunks)
        contexts: Dict[int, str] = {}
        workers = self._resolve_context_workers(max_workers, total)
        request_batch_size = self._resolve_context_batch_size(batch_size, workers)
        completed_count = 0
        prompt_chars = 0
        response_chars = 0
        prompt_tokens = 0
        output_tokens = 0
        total_tokens = 0
        fallback_count = 0

        logger.info(
            "[benchmark_contextual_ingest] generating contexts with max_workers=%s batch_size=%s",
            workers,
            request_batch_size,
        )

        for start in range(0, total, request_batch_size):
            batch_items = list(enumerate(chunks[start : start + request_batch_size], start=start))
            prompts = [self._build_context_prompt(chunk.content, chunk.metadata) for _, chunk in batch_items]
            prompt_chars += sum(len(prompt) for prompt in prompts)

            try:
                responses = self.llm.batch(
                    prompts,
                    config={"max_concurrency": workers},
                    return_exceptions=True,
                )
            except Exception as exc:
                logger.warning("Context batch generation failed, falling back to per-item mode: %s", exc)
                responses = [exc] * len(batch_items)

            for (idx, chunk), response in zip(batch_items, responses):
                if isinstance(response, Exception):
                    contexts[idx] = self._fallback_context(chunk.metadata)
                    fallback_count += 1
                else:
                    content = getattr(response, "content", "") or ""
                    contexts[idx] = content.strip() or self._fallback_context(chunk.metadata)
                    usage = _extract_usage_counts(response)
                    prompt_tokens += usage["prompt_tokens"]
                    output_tokens += usage["output_tokens"]
                    total_tokens += usage["total_tokens"]

                response_chars += len(contexts[idx])
                completed_count += 1
                if on_progress:
                    on_progress(completed_count, total)

        texts = [
            f"{self._build_index_prefix(chunks[i].metadata, contexts[i])}\n\n{chunks[i].content}"
            for i in range(total)
        ]
        metadatas = [chunk.metadata for chunk in chunks]
        self.vsm.add_documents(texts, metadatas)

        result = {
            "mode": "contextual",
            "chunks": total,
            "stored_parent_chunks": len(parents),
            "api_calls": total,
            "fallback_count": fallback_count,
            "prompt_chars": prompt_chars,
            "response_chars": response_chars,
            "prompt_tokens": prompt_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "max_workers": workers,
            "batch_size": request_batch_size,
            "elapsed_sec": time.perf_counter() - started_at,
        }
        if return_artifacts:
            result["artifacts"] = {
                "texts": texts,
                "metadatas": metadatas,
                "parents": parents,
            }
        return result


if __name__ == "__main__":
    import os
    import sys

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.INFO)

    from processing.financial_parser import FinancialParser
    from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager

    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reports_dir = os.path.join(project_root, "data", "reports")
    chroma_dir = os.path.join(project_root, "data", "chroma_dart")

    target = None
    for root_dir, _dirs, files in os.walk(reports_dir):
        for filename in files:
            if filename.endswith(".html"):
                target = os.path.join(root_dir, filename)
                break
        if target:
            break

    if not target:
        print("[SKIP] data/reports/ 아래에 .html 파일이 없습니다. dart_fetcher.py를 먼저 실행하세요.")
        sys.exit(0)

    parser = FinancialParser()
    metadata = {
        "company": "삼성전자",
        "stock_code": "005930",
        "year": 2023,
        "report_type": "사업보고서",
        "rcept_no": "20230307000542",
    }
    chunks = parser.process_document(target, metadata)
    print(f"[1] parsed {len(chunks)} chunks")

    vsm = VectorStoreManager(persist_directory=chroma_dir, collection_name=DEFAULT_COLLECTION_NAME)
    agent = FinancialAgent(vsm)
    agent.ingest(chunks)
    print("[2] indexing complete")

    for question in [
        "삼성전자의 주요 리스크 요인을 알려줘.",
        "삼성전자 2023년 매출과 영업이익은?",
    ]:
        result = agent.run(question)
        print(f"\nQ: {question}")
        print(f"type: {result['query_type']} | companies: {result['companies']} | years: {result['years']}")
        print(result["answer"][:500])
        print(result["citations"][:3])
