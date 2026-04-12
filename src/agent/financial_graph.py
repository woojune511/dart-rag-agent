"""
LangGraph 기반 재무공시 분석 AI Agent.

파이프라인:
  query_classifier → entity_extractor → retrieval → analyst → citation_formatter

지원 쿼리 유형:
  - qa:         단순 사실 질문  ("삼성전자 2023년 영업이익은?")
  - comparison: 기업 간 비교    ("삼성전자 vs SK하이닉스 부채비율 비교")
  - trend:      시계열 트렌드   ("삼성전자 최근 3년 매출 트렌드")
  - risk:       리스크 분석     ("삼성전자의 주요 리스크 요인은?")
"""

import os
import logging
from typing import Any, Dict, List, Literal, Optional, TypedDict

from dotenv import load_dotenv
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

load_dotenv()
logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------
# 그래프 상태
# --------------------------------------------------------------------------

class FinancialAgentState(TypedDict):
    query:          str
    query_type:     str            # "qa" | "comparison" | "trend" | "risk"
    companies:      List[str]      # 추출된 기업명
    years:          List[int]      # 추출된 연도
    topic:          str            # 핵심 주제 키워드
    section_filter: Optional[str]  # 우선 검색할 섹션 레이블
    retrieved_docs: List           # (Document, score) 튜플
    answer:         str
    citations:      List[str]


# --------------------------------------------------------------------------
# 구조화 출력 스키마
# --------------------------------------------------------------------------

class QueryClassification(BaseModel):
    query_type: Literal["qa", "comparison", "trend", "risk"] = Field(
        description=(
            "qa=단순 사실 질문, "
            "comparison=기업 간 수치·전략 비교, "
            "trend=시계열 변화, "
            "risk=리스크 요인 분석"
        )
    )


class EntityExtraction(BaseModel):
    companies: List[str] = Field(description="언급된 기업명 목록 (한글, 없으면 빈 리스트)")
    years: List[int] = Field(description="언급된 연도 목록 (없으면 빈 리스트)")
    topic: str = Field(description="질문의 핵심 주제 (영업이익, 부채비율, 리스크 등)")
    section_filter: Optional[str] = Field(
        default=None,
        description=(
            "관련 섹션 레이블 1개. 선택지: "
            "리스크 / 재무제표 / 연결재무제표 / 요약재무 / 재무주석 / "
            "사업개요 / 주요제품 / 원재료 / 매출현황 / 연구개발 / "
            "경영진단 / 임원현황 / 이사회 / 주주현황 / 계열회사. "
            "없으면 null"
        ),
    )


# --------------------------------------------------------------------------
# Agent
# --------------------------------------------------------------------------

class FinancialAgent:
    """
    DART 공시 분석 LangGraph Agent.

    Usage:
        from storage.vector_store import VectorStoreManager
        from agent.financial_graph import FinancialAgent

        vsm = VectorStoreManager(collection_name="dart_reports")
        agent = FinancialAgent(vsm)

        # 인덱싱
        agent.ingest(chunks)  # List[DocumentChunk]

        # 질의
        result = agent.run("삼성전자 2023년 주요 리스크 요인은?")
        print(result["answer"])
        print(result["citations"])
    """

    def __init__(self, vector_store_manager, k: int = 8):
        self.vsm = vector_store_manager
        self.k = k

        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY 환경변수가 설정되지 않았습니다.")

        self.llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0)
        self.graph = self._build_graph()

    # ------------------------------------------------------------------
    # 노드 함수
    # ------------------------------------------------------------------

    def _classify_query(self, state: FinancialAgentState) -> Dict[str, Any]:
        """쿼리 유형 분류 (qa / comparison / trend / risk)."""
        structured_llm = self.llm.with_structured_output(QueryClassification)
        prompt = ChatPromptTemplate.from_template(
            "다음 금융 공시 관련 질문의 유형을 분류하세요.\n\n질문: {query}"
        )
        result: QueryClassification = (prompt | structured_llm).invoke(
            {"query": state["query"]}
        )
        logger.info(f"[classify] query_type={result.query_type}")
        return {"query_type": result.query_type}

    def _extract_entities(self, state: FinancialAgentState) -> Dict[str, Any]:
        """기업명, 연도, 핵심 주제, 관련 섹션 추출."""
        structured_llm = self.llm.with_structured_output(EntityExtraction)
        prompt = ChatPromptTemplate.from_template(
            "다음 질문에서 기업명, 연도, 핵심 주제, 관련 섹션을 추출하세요.\n\n질문: {query}"
        )
        result: EntityExtraction = (prompt | structured_llm).invoke(
            {"query": state["query"]}
        )
        logger.info(
            f"[extract] companies={result.companies}, years={result.years}, "
            f"topic={result.topic}, section_filter={result.section_filter}"
        )
        return {
            "companies":      result.companies,
            "years":          result.years,
            "topic":          result.topic,
            "section_filter": result.section_filter,
        }

    def _retrieve(self, state: FinancialAgentState) -> Dict[str, Any]:
        """하이브리드 검색 + 메타데이터 필터링.

        회사/연도 필터를 ChromaDB 쿼리 시점(where_filter)에 적용해
        벡터 검색 단계부터 범위를 좁힌다.
        BM25 결과는 post-filter로 동일 조건을 적용한다.
        """
        query          = state["query"]
        companies      = state.get("companies", [])
        years          = state.get("years", [])
        section_filter = state.get("section_filter")

        # ── ChromaDB where 필터 구성 ──────────────────────────────────────
        # 기업·연도를 벡터 검색 시점에 적용 → 다른 기업 청크가 상위에 올 가능성 차단
        conditions: list = []
        if companies:
            if len(companies) == 1:
                conditions.append({"company": companies[0]})
            else:
                conditions.append({"company": {"$in": companies}})
        if years:
            int_years = [int(y) for y in years]
            if len(int_years) == 1:
                conditions.append({"year": int_years[0]})
            else:
                conditions.append({"year": {"$in": int_years}})

        if len(conditions) == 0:
            where_filter = None
        elif len(conditions) == 1:
            where_filter = conditions[0]
        else:
            where_filter = {"$and": conditions}

        # ── 검색 ─────────────────────────────────────────────────────────
        enriched = f"{' '.join(companies)} {query}" if companies else query
        docs = self.vsm.search(enriched, k=self.k * 3, where_filter=where_filter)
        logger.info(
            f"[retrieve] companies={companies}, years={years}, "
            f"where={where_filter} → {len(docs)}개 후보"
        )

        # ── 섹션 필터 (post) ──────────────────────────────────────────────
        if section_filter:
            filtered = [(d, s) for d, s in docs if d.metadata.get("section") == section_filter]
            if len(filtered) >= 2:
                docs = filtered

        # ── BM25 포함 후보에 대한 안전망 post-filter (기업·연도) ──────────
        # where_filter가 있더라도 BM25 경로는 ChromaDB 필터를 거치지 않으므로
        # 여기서 한 번 더 정제한다.
        if companies:
            filtered = [
                (d, s) for d, s in docs
                if any(c in d.metadata.get("company", "") for c in companies)
            ]
            if len(filtered) >= 2:
                docs = filtered
        if years:
            int_years = [int(y) for y in years]
            filtered = [
                (d, s) for d, s in docs
                if int(d.metadata.get("year", 0)) in int_years
            ]
            if len(filtered) >= 2:
                docs = filtered

        docs = docs[: self.k]
        logger.info(f"[retrieve] 최종 {len(docs)}개 청크 반환")
        return {"retrieved_docs": docs}

    def _analyze(self, state: FinancialAgentState) -> Dict[str, Any]:
        """컨텍스트 기반 LLM 분석 답변 생성."""
        docs = state.get("retrieved_docs", [])
        if not docs:
            return {
                "answer": (
                    "관련 공시 문서를 찾지 못했습니다. "
                    "먼저 `agent.ingest(chunks)`로 보고서를 인덱싱하세요."
                )
            }

        instructions = {
            "qa": (
                "제공된 공시 문서를 바탕으로 질문에 정확하게 답하세요. "
                "수치는 반드시 단위와 출처 연도를 함께 명시하세요."
            ),
            "comparison": (
                "두 기업 이상의 수치·전략을 항목별로 구조적으로 비교하세요. "
                "가능하면 표 형식을 활용하세요."
            ),
            "trend": (
                "시간 흐름에 따른 변화를 연도별로 정리하고 "
                "트렌드의 원인과 의미를 해석하세요."
            ),
            "risk": (
                "주요 리스크 요인을 항목별로 나열하고, "
                "각 리스크의 배경과 잠재적 영향을 설명하세요."
            ),
        }
        instruction = instructions.get(state.get("query_type", "qa"), instructions["qa"])
        context = self._format_context(docs)

        prompt = ChatPromptTemplate.from_template(
            """당신은 한국 기업 공시(DART) 분석 전문가입니다.
{instruction}

규칙:
- 제공된 컨텍스트 문서만 사용하세요.
- 컨텍스트에 없는 정보는 "공시 문서에서 확인되지 않습니다"라고 명시하세요.
- 각 주요 주장에는 [기업명/연도/섹션] 형식으로 인용을 달아주세요.

컨텍스트:
{context}

질문: {query}

답변:"""
        )

        chain = prompt | self.llm | StrOutputParser()
        answer = chain.invoke(
            {"instruction": instruction, "context": context, "query": state["query"]}
        )
        logger.info("[analyze] 답변 생성 완료")
        return {"answer": answer}

    def _format_citations(self, state: FinancialAgentState) -> Dict[str, Any]:
        """검색된 청크에서 중복 제거한 인용 출처 목록 생성."""
        seen: set = set()
        citations: List[str] = []
        for doc, score in state.get("retrieved_docs", []):
            m = doc.metadata
            key = (m.get("company"), m.get("year"), m.get("section_title"))
            if key not in seen:
                seen.add(key)
                citations.append(
                    f"[{m.get('company', '?')}] {m.get('year', '?')}년 "
                    f"{m.get('report_type', '?')} — "
                    f"{m.get('section_title', m.get('section', '?'))} "
                    f"(관련도: {score:.3f})"
                )
        return {"citations": citations}

    # ------------------------------------------------------------------
    # 헬퍼
    # ------------------------------------------------------------------

    def _format_context(self, docs) -> str:
        parts = []
        for doc, score in docs:
            m = doc.metadata
            header = (
                f"[{m.get('company', '?')} | {m.get('year', '?')}년 | "
                f"{m.get('report_type', '?')} | "
                f"{m.get('section_title', m.get('section', '?'))}]"
            )
            parts.append(f"{header}\n{doc.page_content}")
        return "\n\n---\n\n".join(parts)

    # ------------------------------------------------------------------
    # 그래프 구성
    # ------------------------------------------------------------------

    def _build_graph(self):
        g = StateGraph(FinancialAgentState)

        g.add_node("classify", self._classify_query)
        g.add_node("extract",  self._extract_entities)
        g.add_node("retrieve", self._retrieve)
        g.add_node("analyze",  self._analyze)
        g.add_node("cite",     self._format_citations)

        g.set_entry_point("classify")
        g.add_edge("classify", "extract")
        g.add_edge("extract",  "retrieve")
        g.add_edge("retrieve", "analyze")
        g.add_edge("analyze",  "cite")
        g.add_edge("cite",     END)

        return g.compile()

    # ------------------------------------------------------------------
    # 공개 인터페이스
    # ------------------------------------------------------------------

    def run(self, query: str) -> Dict[str, Any]:
        """
        질문 → 분석 결과 반환.

        Returns:
            {
                "query":      str,
                "query_type": str,
                "companies":  List[str],
                "years":      List[int],
                "answer":     str,
                "citations":  List[str],
            }
        """
        initial: FinancialAgentState = {
            "query":          query,
            "query_type":     "",
            "companies":      [],
            "years":          [],
            "topic":          "",
            "section_filter": None,
            "retrieved_docs": [],
            "answer":         "",
            "citations":      [],
        }
        final = self.graph.invoke(initial)
        return {
            "query":         final["query"],
            "query_type":    final["query_type"],
            "companies":     final["companies"],
            "years":         final["years"],
            "answer":        final["answer"],
            "citations":     final["citations"],
            "retrieved_docs": final["retrieved_docs"],  # 평가 파이프라인에서 활용
        }

    def ingest(self, chunks: List) -> None:
        """
        DocumentChunk 리스트를 벡터 스토어에 인덱싱.

        Args:
            chunks: FinancialParser.process_document() 반환값
        """
        if not chunks:
            logger.warning("[ingest] 청크가 비어있습니다.")
            return
        texts     = [c.content  for c in chunks]
        metadatas = [c.metadata for c in chunks]
        self.vsm.add_documents(texts, metadatas)
        logger.info(f"[ingest] {len(chunks)}개 청크 인덱싱 완료")


# --------------------------------------------------------------------------
# 스모크 테스트  (파이프라인 전체: 파싱 → 인덱싱 → 질의)
# --------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    import os

    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    logging.basicConfig(level=logging.INFO)

    from processing.financial_parser import FinancialParser
    from storage.vector_store import VectorStoreManager

    _PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reports_dir   = os.path.join(_PROJECT_ROOT, "data", "reports")
    chroma_dir    = os.path.join(_PROJECT_ROOT, "data", "chroma_dart")

    # 1) 보고서 파일 탐색
    target = None
    for root_d, _, files in os.walk(reports_dir):
        for f in files:
            if f.endswith(".html"):
                target = os.path.join(root_d, f)
                break
        if target:
            break

    if not target:
        print("[SKIP] data/reports/ 에 .html 파일 없음. dart_fetcher.py를 먼저 실행하세요.")
        sys.exit(0)

    print(f"\n=== 스모크 테스트: {os.path.basename(target)} ===\n")

    # 2) 파싱
    parser = FinancialParser()
    meta   = {
        "company":     "삼성전자",
        "stock_code":  "005930",
        "year":        2023,
        "report_type": "사업보고서",
        "rcept_no":    "20230307000542",
    }
    chunks = parser.process_document(target, meta)
    print(f"[1] 파싱 완료: {len(chunks)}개 청크")

    # 3) 인덱싱
    vsm   = VectorStoreManager(
        persist_directory=chroma_dir,
        collection_name="dart_reports",
    )
    agent = FinancialAgent(vsm)
    agent.ingest(chunks)
    print(f"[2] 인덱싱 완료")

    # 4) 질의 테스트
    test_queries = [
        "삼성전자의 주요 리스크 요인은 무엇인가요?",
        "삼성전자 2023년 사업의 개요를 설명해주세요.",
    ]

    for q in test_queries:
        print(f"\n{'='*60}")
        print(f"Q: {q}")
        result = agent.run(q)
        print(f"유형: {result['query_type']}")
        print(f"기업: {result['companies']}  연도: {result['years']}")
        print(f"\nA: {result['answer'][:500]}...")
        print(f"\n[인용 출처]")
        for c in result["citations"]:
            print(f"  - {c}")
