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
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from src.agent.financial_run_result import FinancialRunResultV1

logger = logging.getLogger(__name__)

_SCHEMA_MODELS: Optional[Dict[str, type]] = None
_SCHEMA_EXPORTS = {
    "CompaniesResponse",
    "CompanyInfo",
    "HealthResponse",
    "IngestRequest",
    "IngestResponse",
    "QueryRequest",
    "QueryResponse",
    "ReportScope",
}


def _services(request: Any):
    from fastapi import HTTPException

    services = getattr(request.app.state, "services", None)
    if services is None:
        raise HTTPException(status_code=503, detail="application services are not initialized")
    return services


def _schema_models() -> Dict[str, type]:
    """Create API Pydantic schemas only when the API layer needs them."""
    global _SCHEMA_MODELS
    if _SCHEMA_MODELS is not None:
        return _SCHEMA_MODELS

    from pydantic import BaseModel, ConfigDict, Field

    class _DeferredBaseModel(BaseModel):
        model_config = ConfigDict(defer_build=True)

    class IngestRequest(_DeferredBaseModel):
        company: str = Field(..., examples=["삼성전자"])
        years: List[int] = Field(..., examples=[[2023]])

    class IngestResponse(_DeferredBaseModel):
        company: str
        years: List[int]
        files_fetched: int
        chunks_added: int
        message: str

    class ReportScope(_DeferredBaseModel):
        company: Optional[str] = None
        corp_name: Optional[str] = None
        year: Optional[int] = None
        report_type: Optional[str] = None
        rcept_no: Optional[str] = None
        consolidation: Optional[str] = None
        source_companies: List[str] = Field(default_factory=list)
        source_receipts: List[str] = Field(default_factory=list)
        source_reports: List[Dict[str, Any]] = Field(default_factory=list)

    class QueryRequest(_DeferredBaseModel):
        question: str = Field(..., examples=["삼성전자 2023년 주요 리스크는 무엇인가요?"])
        report_scope: Optional[ReportScope] = None
        include_review_trace: bool = Field(default=False)
        include_debug_bundle: bool = Field(default=False)

    class QueryResponse(_DeferredBaseModel):
        question: str
        answer: str
        query_type: str
        companies: List[str]
        years: List[int]
        citations: List[str]
        structured_result: Dict[str, Any] = Field(default_factory=dict)
        resolved_calculation_trace: Dict[str, Any] = Field(default_factory=dict)
        review_trace: Optional[Dict[str, Any]] = None
        debug_bundle: Optional[Dict[str, Any]] = None
        retrieval_readiness: Optional[Dict[str, Any]] = None

    class CompanyInfo(_DeferredBaseModel):
        name: str
        years: List[int]
        chunk_count: int

    class CompaniesResponse(_DeferredBaseModel):
        companies: List[CompanyInfo]
        total_chunks: int

    class HealthResponse(_DeferredBaseModel):
        status: str
        indexed_docs: int
        ready: bool = False
        degraded: bool = False
        reason: str = ""

    _SCHEMA_MODELS = {
        "CompaniesResponse": CompaniesResponse,
        "CompanyInfo": CompanyInfo,
        "HealthResponse": HealthResponse,
        "IngestRequest": IngestRequest,
        "IngestResponse": IngestResponse,
        "QueryRequest": QueryRequest,
        "QueryResponse": QueryResponse,
        "ReportScope": ReportScope,
    }
    return _SCHEMA_MODELS


def _query_response_from_agent_result(
    question: str,
    result: FinancialRunResultV1,
    *,
    include_review_trace: bool = False,
    include_debug_bundle: bool = False,
    retrieval_readiness: Optional[Dict[str, Any]] = None,
) -> QueryResponse:
    QueryResponse = _schema_models()["QueryResponse"]
    answer_payload = dict(result.agent_answer)
    query_retrieval_status = dict(
        answer_payload.get("retrieval_status") or {}
    )
    effective_readiness = dict(retrieval_readiness or {})
    if bool(query_retrieval_status.get("degraded")):
        store_status = str(effective_readiness.get("status") or "")
        if store_status and store_status != "degraded":
            effective_readiness["store_status"] = store_status
        effective_readiness.update(
            {
                "status": "degraded",
                "ready": bool(effective_readiness.get("ready", True)),
                "degraded": True,
                "reason": "query used BM25 fallback",
                "query_retrieval": query_retrieval_status,
            }
        )
    response = QueryResponse(
        question=question,
        answer=str(answer_payload.get("answer") or ""),
        query_type=str(answer_payload.get("query_type") or "unknown"),
        companies=list(answer_payload.get("companies") or []),
        years=list(answer_payload.get("years") or []),
        citations=list(answer_payload.get("citations") or []),
        structured_result=dict(answer_payload.get("structured_result") or {}),
        resolved_calculation_trace=dict(
            answer_payload.get("resolved_calculation_trace") or {}
        ),
    )
    if include_review_trace and result.review_trace is not None:
        response.review_trace = dict(result.review_trace)
    if include_debug_bundle and result.debug_bundle is not None:
        response.debug_bundle = dict(result.debug_bundle)
    if effective_readiness and bool(effective_readiness.get("degraded")):
        response.retrieval_readiness = effective_readiness
    return response


# --------------------------------------------------------------------------
# 엔드포인트
# --------------------------------------------------------------------------

def get_router():
    """Build the FastAPI router only when the API application asks for it."""
    from fastapi import APIRouter, HTTPException, Request, Response
    from starlette.concurrency import run_in_threadpool

    # Route annotations are evaluated against this module even though FastAPI is
    # imported lazily to keep importing the contract module side-effect free.
    globals()["Request"] = Request
    globals()["Response"] = Response

    schemas = _schema_models()
    globals().update(schemas)
    CompaniesResponse = schemas["CompaniesResponse"]
    CompanyInfo = schemas["CompanyInfo"]
    HealthResponse = schemas["HealthResponse"]
    IngestRequest = schemas["IngestRequest"]
    IngestResponse = schemas["IngestResponse"]
    QueryRequest = schemas["QueryRequest"]
    QueryResponse = schemas["QueryResponse"]

    router = APIRouter(prefix="/api", tags=["financial"])

    @router.get("/health/live", response_model=HealthResponse)
    async def health_live():
        return HealthResponse(
            status="live",
            indexed_docs=0,
            ready=False,
        )

    async def readiness_response(request: Request, response: Response):
        services = _services(request)
        readiness = services.readiness
        count = (
            len(getattr(services.store, "bm25_docs", []) or [])
            if services.store is not None
            else 0
        )
        if not readiness.ready:
            response.status_code = 503
        return HealthResponse(
            status=readiness.status,
            indexed_docs=count,
            ready=readiness.ready,
            degraded=readiness.degraded,
            reason=readiness.reason,
        )

    router.add_api_route(
        "/health/ready",
        readiness_response,
        methods=["GET"],
        response_model=HealthResponse,
    )
    router.add_api_route(
        "/health",
        readiness_response,
        methods=["GET"],
        response_model=HealthResponse,
    )

    @router.get("/companies", response_model=CompaniesResponse)
    async def get_companies(request: Request):
        """
        현재 벡터 DB에 인덱싱된 기업·연도 목록 반환.
        ChromaDB 메타데이터에서 집계.
        """
        services = _services(request)
        vsm = services.store
        if vsm is None:
            raise HTTPException(status_code=503, detail=services.readiness.reason)

        def load_companies():
            data = vsm.vector_store.get(include=["metadatas"])
            metadatas = data.get("metadatas") or []
            company_years: Dict[str, set] = {}
            company_counts: Dict[str, int] = {}
            for meta in metadatas:
                company = meta.get("company", "unknown")
                year = meta.get("year")
                company_years.setdefault(company, set())
                company_counts[company] = company_counts.get(company, 0) + 1
                if year:
                    company_years[company].add(int(year))
            companies = [
                CompanyInfo(name=name, years=sorted(years), chunk_count=company_counts[name])
                for name, years in sorted(company_years.items())
            ]
            return CompaniesResponse(companies=companies, total_chunks=len(metadatas))

        try:
            async with services.operation_lock:
                return await run_in_threadpool(load_companies)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"DB 조회 실패: {e}")

    @router.post("/ingest", response_model=IngestResponse)
    async def ingest(req: IngestRequest, request: Request):
        """
        기업 공시 문서를 DART에서 수집하고 벡터 DB에 인덱싱.

        - DART API로 사업보고서 다운로드
        - FinancialParser로 파싱 (섹션 분류 + 2-level 청킹)
        - ChromaDB + BM25에 인덱싱
        """
        services = _services(request)
        ingest_service = services.ingest_service
        if ingest_service is None:
            raise HTTPException(status_code=503, detail=services.readiness.reason)

        def ingest_and_refresh():
            try:
                return ingest_service.ingest_company(
                    req.company, req.years,
                    max_workers=services.contextual_ingest_max_workers,
                )
            finally:
                services.refresh_readiness()

        try:
            async with services.operation_lock:
                result = await run_in_threadpool(ingest_and_refresh)
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"수집·인덱싱 실패: {e}")

        if not int(result.get("files_fetched") or 0):
            raise HTTPException(
                status_code=404,
                detail=f"'{req.company}'의 {req.years} 공시 문서를 찾을 수 없습니다.",
            )
        total_chunks = int(result.get("chunks_added") or 0)
        processed = int(result.get("reports_processed") or 0)
        skipped = int(result.get("reports_skipped") or 0)
        if total_chunks == 0 and processed == 0 and skipped == 0:
            raise HTTPException(status_code=422, detail="파싱된 청크가 없습니다. 파일 형식을 확인하세요.")
        msg = f"'{req.company}' {req.years} 처리 완료"
        if total_chunks:
            msg += f" — {total_chunks}청크 신규 인덱싱"
        if skipped:
            msg += f" — {skipped}건 이미 존재하여 건너뜀"

        return IngestResponse(
            company=req.company,
            years=req.years,
            files_fetched=int(result.get("files_fetched") or 0),
            chunks_added=total_chunks,
            message=msg,
        )

    @router.post("/query", response_model=QueryResponse, response_model_exclude_none=True)
    async def query(req: QueryRequest, request: Request):
        """
        자연어 질문을 FinancialAgent로 처리하여 분석 답변 반환.

        LangGraph 5-노드 파이프라인:
        classify → extract → retrieve → analyze → cite
        """
        services = _services(request)
        if not req.question.strip():
            raise HTTPException(status_code=422, detail="질문이 비어있습니다.")

        try:
            report_scope = (
                req.report_scope.model_dump(
                    exclude_none=True,
                    exclude_unset=True,
                )
                if req.report_scope is not None
                else None
            )
            async with services.operation_lock:
                if not services.readiness.ready:
                    raise HTTPException(status_code=503, detail=services.readiness.reason)
                agent = services.agent
                if agent is None:
                    raise HTTPException(status_code=503, detail="FinancialAgent is unavailable")
                result = await run_in_threadpool(
                    agent.run,
                    req.question,
                    report_scope=report_scope,
                    include_review_trace=req.include_review_trace,
                    include_debug_bundle=req.include_debug_bundle,
                )
                readiness_snapshot = services.readiness.to_projection()
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"agent.run 실패: {e}")
            raise HTTPException(status_code=500, detail=f"분석 실패: {e}")

        return _query_response_from_agent_result(
            req.question,
            result,
            include_review_trace=req.include_review_trace,
            include_debug_bundle=req.include_debug_bundle,
            retrieval_readiness=readiness_snapshot,
        )

    return router


def __getattr__(name: str) -> Any:
    if name == "router":
        return get_router()
    if name in _SCHEMA_EXPORTS:
        return _schema_models()[name]
    raise AttributeError(name)


__all__ = [
    "CompaniesResponse",
    "CompanyInfo",
    "HealthResponse",
    "IngestRequest",
    "IngestResponse",
    "QueryRequest",
    "QueryResponse",
    "ReportScope",
    "get_router",
    "router",
]
