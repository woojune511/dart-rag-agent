"""
FastAPI 라우터 — DART 공시 분석 AI Agent REST API.

엔드포인트:
  POST /api/ingest     기업 공시 문서 수집 → 파싱 → 벡터 DB 인덱싱
  POST /api/query      자연어 질문 → FinancialAgent 실행 → 답변 반환
  GET  /api/companies  현재 인덱싱된 기업·연도 목록 조회
  GET  /api/health     서버 상태 확인
"""

from __future__ import annotations

import logging
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

load_dotenv()
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from ingestion.dart_fetcher import DARTFetcher
from processing.financial_parser import FinancialParser
from storage.vector_store import DEFAULT_COLLECTION_NAME, VectorStoreManager
from agent.financial_graph import FinancialAgent

logger = logging.getLogger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_CHROMA_PATH   = str(_PROJECT_ROOT / "data" / "chroma_dart")
_REPORTS_DIR   = str(_PROJECT_ROOT / "data" / "reports")

router = APIRouter(prefix="/api", tags=["financial"])


# --------------------------------------------------------------------------
# 컴포넌트 싱글턴 (FastAPI 수명 주기에서 초기화)
# --------------------------------------------------------------------------

_vsm:     Optional[VectorStoreManager] = None
_agent:   Optional[FinancialAgent]     = None
_parser:  Optional[FinancialParser]    = None
_fetcher: Optional[DARTFetcher]        = None


def init_components() -> None:
    """애플리케이션 시작 시 한 번만 호출. 모든 컴포넌트를 초기화."""
    global _vsm, _agent, _parser, _fetcher
    _vsm     = VectorStoreManager(persist_directory=_CHROMA_PATH, collection_name=DEFAULT_COLLECTION_NAME)
    _agent   = FinancialAgent(_vsm, k=8)
    _parser  = FinancialParser(chunk_size=1500, chunk_overlap=200)
    _fetcher = DARTFetcher(download_dir=_REPORTS_DIR)
    logger.info("컴포넌트 초기화 완료")


def _require(component, name: str):
    if component is None:
        raise HTTPException(status_code=503, detail=f"{name} not initialized. Call init_components() on startup.")
    return component


# --------------------------------------------------------------------------
# 요청/응답 스키마
# --------------------------------------------------------------------------

class IngestRequest(BaseModel):
    company: str = Field(..., examples=["삼성전자"])
    years: List[int] = Field(..., examples=[[2023]])


class IngestResponse(BaseModel):
    company:      str
    years:        List[int]
    files_fetched: int
    chunks_added: int
    message:      str


class QueryRequest(BaseModel):
    question: str = Field(..., examples=["삼성전자 2023년 주요 리스크는 무엇인가요?"])


class QueryResponse(BaseModel):
    question:   str
    answer:     str
    query_type: str
    companies:  List[str]
    years:      List[int]
    citations:  List[str]


class CompanyInfo(BaseModel):
    name:        str
    years:       List[int]
    chunk_count: int


class CompaniesResponse(BaseModel):
    companies:   List[CompanyInfo]
    total_chunks: int


class HealthResponse(BaseModel):
    status:      str
    indexed_docs: int


# --------------------------------------------------------------------------
# 엔드포인트
# --------------------------------------------------------------------------

@router.get("/health", response_model=HealthResponse)
async def health():
    """서버 및 벡터 DB 상태 확인."""
    vsm = _vsm
    count = len(vsm.bm25_docs) if vsm else 0
    return HealthResponse(status="ok", indexed_docs=count)


@router.get("/companies", response_model=CompaniesResponse)
async def get_companies():
    """
    현재 벡터 DB에 인덱싱된 기업·연도 목록 반환.
    ChromaDB 메타데이터에서 집계.
    """
    vsm = _require(_vsm, "VectorStoreManager")

    try:
        data = vsm.vector_store.get(include=["metadatas"])
        metadatas = data.get("metadatas") or []
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"DB 조회 실패: {e}")

    company_years: Dict[str, set] = {}
    company_counts: Dict[str, int] = {}

    for meta in metadatas:
        company = meta.get("company", "unknown")
        year    = meta.get("year")
        company_years.setdefault(company, set())
        company_counts[company] = company_counts.get(company, 0) + 1
        if year:
            company_years[company].add(int(year))

    companies = [
        CompanyInfo(
            name=name,
            years=sorted(years),
            chunk_count=company_counts[name],
        )
        for name, years in sorted(company_years.items())
    ]
    return CompaniesResponse(companies=companies, total_chunks=len(metadatas))


@router.post("/ingest", response_model=IngestResponse)
async def ingest(req: IngestRequest):
    """
    기업 공시 문서를 DART에서 수집하고 벡터 DB에 인덱싱.

    - DART API로 사업보고서 다운로드
    - FinancialParser로 파싱 (섹션 분류 + 2-level 청킹)
    - ChromaDB + BM25에 인덱싱
    """
    fetcher = _require(_fetcher, "DARTFetcher")
    parser  = _require(_parser,  "FinancialParser")
    agent   = _require(_agent,   "FinancialAgent")

    try:
        reports = fetcher.fetch_company_reports(req.company, req.years)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"DART 수집 실패: {e}")

    if not reports:
        raise HTTPException(
            status_code=404,
            detail=f"'{req.company}'의 {req.years} 공시 문서를 찾을 수 없습니다.",
        )

    vsm = _require(_vsm, "VectorStoreManager")
    total_chunks = 0
    skipped = 0
    for report in reports:
        if not report.file_path or not Path(report.file_path).exists():
            logger.warning(f"파일 없음 건너뜀: {report}")
            continue

        if vsm.is_indexed(report.rcept_no):
            logger.info(f"이미 인덱싱됨 건너뜀: {report.corp_name} {report.year} ({report.rcept_no})")
            skipped += 1
            continue

        meta = {
            "company":     report.corp_name,
            "stock_code":  report.stock_code or "unknown",
            "year":        report.year,
            "report_type": report.report_type,
            "rcept_no":    report.rcept_no,
        }
        chunks = parser.process_document(report.file_path, meta)
        if chunks:
            agent.ingest(chunks)
            total_chunks += len(chunks)
            logger.info(f"인덱싱: {report.corp_name} {report.year} → {len(chunks)}청크")

    if total_chunks == 0 and skipped == 0:
        raise HTTPException(status_code=422, detail="파싱된 청크가 없습니다. 파일 형식을 확인하세요.")

    msg = f"'{req.company}' {req.years} 처리 완료"
    if total_chunks:
        msg += f" — {total_chunks}청크 신규 인덱싱"
    if skipped:
        msg += f" — {skipped}건 이미 존재하여 건너뜀"

    return IngestResponse(
        company=req.company,
        years=req.years,
        files_fetched=len(reports),
        chunks_added=total_chunks,
        message=msg,
    )


@router.post("/query", response_model=QueryResponse)
async def query(req: QueryRequest):
    """
    자연어 질문을 FinancialAgent로 처리하여 분석 답변 반환.

    LangGraph 5-노드 파이프라인:
    classify → extract → retrieve → analyze → cite
    """
    agent = _require(_agent, "FinancialAgent")

    if not req.question.strip():
        raise HTTPException(status_code=422, detail="질문이 비어있습니다.")

    try:
        result = agent.run(req.question)
    except Exception as e:
        logger.error(f"agent.run 실패: {e}")
        raise HTTPException(status_code=500, detail=f"분석 실패: {e}")

    return QueryResponse(
        question=req.question,
        answer=result.get("answer", ""),
        query_type=result.get("query_type", "unknown"),
        companies=result.get("companies", []),
        years=result.get("years", []),
        citations=result.get("citations", []),
    )
