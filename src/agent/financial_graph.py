"""
LangGraph-based DART financial analysis agent.
"""

import logging
import os
import re
import time
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

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


class FinancialAgentState(TypedDict):
    query: str
    query_type: str
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    retrieved_docs: List
    evidence_bullets: List[str]
    evidence_items: List[Dict[str, Any]]
    evidence_status: str
    compressed_answer: str
    answer: str
    citations: List[str]


class QueryClassification(BaseModel):
    query_type: Literal["numeric_fact", "business_overview", "risk", "comparison", "trend", "qa"] = Field(
        description=(
            "numeric_fact=특정 수치·금액·비율을 묻는 질의 (매출, 영업이익, 부채비율, R&D 비용 등), "
            "business_overview=사업 구조·주요 사업·서비스·제품·고객군 등 기업 개요 설명 질의, "
            "risk=리스크 요인·위험 관리·파생거래 등 리스크 분석 질의, "
            "comparison=두 기업 또는 두 항목 간 비교 질의, "
            "trend=시계열 변화·추이·성장률 등 기간 분석 질의, "
            "qa=위 유형에 해당하지 않는 일반 사실·설명 질의"
        )
    )


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


class FinancialAgent:
    _SECTION_BIAS_BY_QUERY_TYPE = {
        "numeric_fact": (
            ("매출 및 수주상황", 0.08),
            ("요약재무정보", 0.06),
            ("연결재무제표", 0.06),
            ("연결재무제표 주석", 0.06),
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

    def __init__(self, vector_store_manager, k: int = 8):
        self.vsm = vector_store_manager
        self.k = k

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is required.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.graph = self._build_graph()

    def _classify_query(self, state: FinancialAgentState) -> Dict[str, Any]:
        structured_llm = self.llm.with_structured_output(QueryClassification)
        prompt = ChatPromptTemplate.from_template(
            """다음 기업 공시 질문의 유형을 분류하세요.

유형 판별 기준:
- numeric_fact : 특정 수치·금액·비율을 묻는 질의. 답이 단일 숫자 또는 명확한 수치 목록으로 귀결됨.
  핵심 구별 기준: 수치 자체가 목적인가? 사업 구조 이해가 목적인가?
  numeric_fact 예) "연결 매출액은?", "영업이익률은?", "R&D 비용은 얼마?", "부채비율은?", "EPS는?"
  business_overview로 분류해야 할 수치 질문 예) "사업부문 간 내부거래 규모·비중은?" (사업 구조 파악 목적),
    "자회사는 몇 개?" (사업 구조 파악 목적), "각 부문별 매출 비중은?" (부문 구성 이해 목적)
- business_overview : 사업 구조·주요 제품·서비스·고객군·사업 부문 구성 등 기업 개요를 묻는 질의.
  수치를 포함하더라도 사업 구조 파악이 목적이면 business_overview.
  예) "주요 사업은?", "어떤 제품을 생산하나?", "사업 부문 구성은?", "주요 고객군은?",
    "사업부문 간 매출 비중은?", "몇 개의 자회사를 통해 사업을 영위하나?"
- risk : 리스크 요인·위험 관리 방식·파생거래 등을 묻는 질의.
  예) "주요 재무 리스크는?", "환율 위험 관리 방식은?", "사업 리스크 요인은?"
- comparison : 두 기업 또는 두 항목을 명시적으로 비교하는 질의.
  예) "삼성전자 vs SK하이닉스 매출 비교", "DX 부문과 DS 부문 매출 차이는?"
- trend : 시계열 변화·추이·성장률·전년 대비 변화를 묻는 질의.
  예) "최근 3년 영업이익 추이는?", "매출 성장률 변화는?"
- qa : 위 유형에 해당하지 않는 일반 사실·설명 질의.

질문: {query}"""
        )
        result: QueryClassification = (prompt | structured_llm).invoke({"query": state["query"]})
        logger.info("[classify] query_type=%s", result.query_type)
        return {"query_type": result.query_type}

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

    # query_type별 표 청크 선호 여부
    _TABLE_PREFERRED_TYPES = frozenset(["numeric_fact", "trend"])
    _PARAGRAPH_PREFERRED_TYPES = frozenset(["business_overview", "risk", "qa"])

    def _section_bias(self, query_type: str, section_path: str) -> float:
        lowered = (section_path or "").lower()
        bias = 0.0
        for needle, weight in self._SECTION_BIAS_BY_QUERY_TYPE.get(query_type, ()):
            if needle.lower() in lowered:
                bias += weight
        return bias

    def _rerank_docs(self, docs, state: FinancialAgentState):
        companies = {company.lower() for company in state.get("companies", [])}
        years = {int(year) for year in state.get("years", [])}
        topic_terms = _tokenize_terms(state.get("topic") or state["query"])
        section_filter = (state.get("section_filter") or "").strip()
        query_type = state.get("query_type", "qa")

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

            boosted += self._section_bias(query_type, section_path)

            # block_type 보정: query_type 기반으로 표/단락 선호도 반영
            if query_type in self._PARAGRAPH_PREFERRED_TYPES and block_type == "table":
                boosted -= 0.08
            elif query_type in self._TABLE_PREFERRED_TYPES and block_type == "paragraph":
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

        # query_type에 따라 표/단락 비율 보장
        query_type = state.get("query_type", "qa")
        if query_type in self._TABLE_PREFERRED_TYPES:
            # 수치·추이 쿼리: 표 우선, 단락 최소 2개 보장
            tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
            min_para = min(2, len(paras))
            docs = (tables[: self.k - min_para] + paras[:min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        elif query_type in self._PARAGRAPH_PREFERRED_TYPES:
            # 개요·리스크·일반 쿼리: 단락 최소 절반 보장
            tables = [(d, s) for d, s in reranked if d.metadata.get("block_type") == "table"]
            paras = [(d, s) for d, s in reranked if d.metadata.get("block_type") != "table"]
            min_para = min(self.k // 2, len(paras))
            docs = (paras[:min_para] + tables[: self.k - min_para])
            docs.sort(key=lambda x: x[1], reverse=True)
        else:
            docs = reranked

        docs = docs[: self.k]
        logger.info("[retrieve] query_type=%s final %s chunks returned", query_type, len(docs))
        return {"retrieved_docs": docs}

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

            header = (
                f"[{company} | {year} | {report_type} | {section_path} | score={score:.3f}]"
            )

            # 부모 청크 우선 사용
            if parent_id and parent_id not in seen_parents:
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
        return (
            f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
            f"{metadata.get('section_path', metadata.get('section', '?'))}]"
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
                "chunk_uid": metadata.get("chunk_uid"),
                "parent_id": metadata.get("parent_id"),
            }

            parent_id = metadata.get("parent_id")
            if parent_id and parent_id not in seen_parents:
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

    def _compression_guidance(self, query_type: str, query: str, coverage: str) -> Dict[str, str]:
        lowered_query = query.lower()
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
        if query_type == "numeric_fact" and any(token in lowered_query for token in ("얼마", "몇", "금액", "규모")):
            output_styles["numeric_fact"] = "반드시 1문장."
        if query_type == "business_overview" and any(
            token in lowered_query for token in ("몇 개", "몇개의", "몇 개의", "몇개", "종속기업", "자회사 수")
        ):
            output_styles["business_overview"] = "반드시 1~2문장."

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
                "compressed_answer": (
                    "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
                    "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
                )
            }

        coverage = state.get("evidence_status", "sparse")
        query = state["query"]
        query_type = state.get("query_type", "qa")
        selected_evidence = self._select_evidence_for_compression(evidence_items)
        evidence_text = self._format_evidence_for_prompt(selected_evidence, evidence_bullets)
        guidance = self._compression_guidance(query_type, query, coverage)

        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 분석 전문가입니다.
아래 structured evidence를 질문 범위에 맞게 압축해 답변 초안을 작성하세요.

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

답변 초안:"""
        )

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
        logger.info("[compress] compressed answer generated")
        return {"compressed_answer": compressed_answer}

    def _validate_answer(self, state: FinancialAgentState) -> Dict[str, Any]:
        compressed_answer = state.get("compressed_answer", "")
        if not compressed_answer:
            return {"answer": compressed_answer}

        evidence_items = state.get("evidence_items", [])
        evidence_bullets = state.get("evidence_bullets", [])
        evidence_text = self._format_evidence_for_prompt(
            self._select_evidence_for_compression(evidence_items),
            evidence_bullets,
        )
        query_type = state.get("query_type", "qa")

        validator_prompt = ChatPromptTemplate.from_template(
            """다음 답변 초안을 structured evidence와 대조해 검증하세요.

Validator 규칙:
- 새 정보는 절대 추가하지 마세요.
- 근거로 뒷받침되지 않는 문장, 구, 세부사항만 삭제하거나 더 짧게 축소하세요.
- 질문에 직접 필요하지 않은 배경 설명은 삭제하세요.
- 숫자, 단위, 비율은 evidence의 quote_span 또는 claim 표기를 그대로 유지하세요.
- risk: evidence에 없는 상위 taxonomy나 재분류를 만들지 마세요.
- duplicated claim은 하나만 남기세요.
- 가능한 한 기존 source_anchor는 유지하세요.
- 최종 답변만 출력하세요.

질문 유형: {query_type}
질문: {query}

Structured Evidence:
{evidence}

초안 답변:
{answer}"""
        )
        validated_answer = (validator_prompt | self.llm | StrOutputParser()).invoke(
            {
                "query_type": query_type,
                "query": state["query"],
                "evidence": evidence_text,
                "answer": compressed_answer,
            }
        )
        logger.info("[validate] answer validated")
        return {"answer": validated_answer}

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
        graph.add_node("evidence", self._extract_evidence)
        graph.add_node("compress", self._compress_answer)
        graph.add_node("validate", self._validate_answer)
        graph.add_node("cite", self._format_citations)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "extract")
        graph.add_edge("extract", "retrieve")
        graph.add_edge("retrieve", "evidence")
        graph.add_edge("evidence", "compress")
        graph.add_edge("compress", "validate")
        graph.add_edge("validate", "cite")
        graph.add_edge("cite", END)

        return graph.compile()

    def run(self, query: str) -> Dict[str, Any]:
        initial: FinancialAgentState = {
            "query": query,
            "query_type": "",
            "companies": [],
            "years": [],
            "topic": "",
            "section_filter": None,
            "retrieved_docs": [],
            "evidence_bullets": [],
            "evidence_items": [],
            "evidence_status": "missing",
            "compressed_answer": "",
            "answer": "",
            "citations": [],
        }
        final = self.graph.invoke(initial)
        return {
            "query": final["query"],
            "query_type": final["query_type"],
            "companies": final["companies"],
            "years": final["years"],
            "answer": final["answer"],
            "citations": final["citations"],
            "retrieved_docs": final["retrieved_docs"],
            "evidence_items": final.get("evidence_items", []),
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
