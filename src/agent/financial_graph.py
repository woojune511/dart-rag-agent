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


class FinancialAgentState(TypedDict):
    query: str
    query_type: str
    companies: List[str]
    years: List[int]
    topic: str
    section_filter: Optional[str]
    retrieved_docs: List
    evidence_bullets: List[str]
    evidence_status: str
    answer: str
    citations: List[str]


class QueryClassification(BaseModel):
    query_type: Literal["qa", "comparison", "trend", "risk"] = Field(
        description=(
            "qa=단일 기업 중심의 사실/설명 질의, "
            "comparison=기업 또는 항목 간 비교, "
            "trend=시계열 변화 분석, "
            "risk=리스크 요인 분석"
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


class EvidenceExtraction(BaseModel):
    coverage: Literal["sufficient", "sparse", "conflicting", "missing"]
    evidence: List[EvidenceItem] = Field(default_factory=list)


class FinancialAgent:
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
            "다음 기업 공시 질문의 유형을 분류하세요.\n\n질문: {query}"
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

    def _rerank_docs(self, docs, state: FinancialAgentState):
        companies = {company.lower() for company in state.get("companies", [])}
        years = {int(year) for year in state.get("years", [])}
        topic_terms = _tokenize_terms(state.get("topic") or state["query"])
        section_filter = (state.get("section_filter") or "").strip()

        reranked = []
        for doc, score in docs:
            metadata = doc.metadata or {}
            company = str(metadata.get("company", "")).lower()
            year = metadata.get("year")
            section = str(metadata.get("section", ""))
            section_path = str(metadata.get("section_path", section))
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

        docs = self._rerank_docs(docs, state)[: self.k]
        logger.info("[retrieve] final %s chunks returned", len(docs))
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

    def _extract_evidence(self, state: FinancialAgentState) -> Dict[str, Any]:
        docs = state.get("retrieved_docs", [])
        if not docs:
            return {"evidence_bullets": [], "evidence_status": "missing"}

        structured_llm = self.llm.with_structured_output(EvidenceExtraction)
        prompt = ChatPromptTemplate.from_template(
            """당신은 기업 공시 분석 보조자입니다.
질문에 답하기 전에, 아래 검색 결과에서 질문과 직접적으로 관련된 근거만 뽑아주세요.

규칙:
- 제공된 컨텍스트 밖의 정보를 추가하지 마세요.
- 각 근거는 반드시 출처 앵커를 포함하세요.
- 숫자, 기간, 조건이 보이면 그대로 유지하세요.
- 근거가 부족하면 coverage를 sparse로, 서로 충돌하면 conflicting으로 설정하세요.
- 아예 답할 근거가 없으면 coverage를 missing으로 두고 evidence는 비우세요.

질문: {query}
핵심 주제: {topic}

컨텍스트:
{context}
"""
        )

        try:
            result: EvidenceExtraction = (prompt | structured_llm).invoke(
                {
                    "query": state["query"],
                    "topic": state.get("topic") or state["query"],
                    "context": self._format_context(docs[: min(6, len(docs))]),
                }
            )
            evidence_bullets = [
                f"- {item.source_anchor} {item.claim} ({item.support_level})"
                for item in result.evidence
            ]
            logger.info("[evidence] coverage=%s bullets=%s", result.coverage, len(evidence_bullets))
            return {"evidence_bullets": evidence_bullets, "evidence_status": result.coverage}
        except Exception as exc:
            logger.warning("Evidence extraction failed, using deterministic fallback: %s", exc)
            fallback = []
            for doc, _score in docs[: min(4, len(docs))]:
                metadata = doc.metadata or {}
                anchor = (
                    f"[{metadata.get('company', '?')} | {metadata.get('year', '?')} | "
                    f"{metadata.get('section_path', metadata.get('section', '?'))}]"
                )
                snippet = re.sub(r"\s+", " ", doc.page_content).strip()[:220]
                fallback.append(f"- {anchor} {snippet}")
            return {
                "evidence_bullets": fallback,
                "evidence_status": "sparse" if fallback else "missing",
            }

    def _analyze(self, state: FinancialAgentState) -> Dict[str, Any]:
        evidence_bullets = state.get("evidence_bullets", [])
        if not evidence_bullets:
            return {
                "answer": (
                    "관련 공시 문서에서 질문에 직접 답할 수 있는 근거를 찾지 못했습니다. "
                    "공시 문서에 정보가 없거나, 현재 검색 결과만으로는 확인하기 어렵습니다."
                )
            }

        coverage = state.get("evidence_status", "sparse")
        instructions = {
            "qa": "근거를 바탕으로 핵심 사실을 정확하게 설명하세요.",
            "comparison": "근거를 항목별로 정리해 비교하세요.",
            "trend": "근거를 시간 흐름에 따라 정리하고 변화 원인을 설명하세요.",
            "risk": "주요 리스크를 항목별로 정리하고 배경과 잠재 영향을 설명하세요.",
        }
        instruction = instructions.get(state.get("query_type", "qa"), instructions["qa"])
        evidence_text = "\n".join(evidence_bullets)

        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 분석 전문가입니다.
아래 근거 목록만 사용해 답변을 작성하세요.

답변 규칙:
- 제공된 근거 밖의 내용은 쓰지 마세요.
- 핵심 주장마다 근거 앵커를 자연스럽게 반영하세요.
- coverage 상태가 sparse이면 "현재 공시 근거가 제한적이다"는 점을 분명히 밝히세요.
- coverage 상태가 conflicting이면 공시 근거가 상충한다고 명시하세요.
- 질문에 필요한 정보가 충분하지 않으면 "공시 문서에서 확인되지 않는다"는 식으로 답하세요.

질문 유형 지침:
{instruction}

coverage: {coverage}

근거 목록:
{evidence}

질문: {query}

답변:"""
        )

        chain = prompt | self.llm | StrOutputParser()
        answer = chain.invoke(
            {
                "instruction": instruction,
                "coverage": coverage,
                "evidence": evidence_text,
                "query": state["query"],
            }
        )
        logger.info("[analyze] answer generated")
        return {"answer": answer}

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
        graph.add_node("analyze", self._analyze)
        graph.add_node("cite", self._format_citations)

        graph.set_entry_point("classify")
        graph.add_edge("classify", "extract")
        graph.add_edge("extract", "retrieve")
        graph.add_edge("retrieve", "evidence")
        graph.add_edge("evidence", "analyze")
        graph.add_edge("analyze", "cite")
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
            "evidence_status": "missing",
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

        return {
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
