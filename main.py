"""
FastAPI 애플리케이션 진입점.

실행:
    uvicorn main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
"""

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from api.financial_router import init_components, router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 시작/종료 수명 주기."""
    logger.info("서버 시작 — 컴포넌트 초기화 중...")
    init_components()
    yield
    logger.info("서버 종료")


app = FastAPI(
    title="DART 공시 분석 AI Agent API",
    description=(
        "DART(전자공시시스템) 공시 문서를 기반으로 "
        "자연어 질문에 답하는 기업 분석 AI Agent."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "DART Financial Analysis AI",
        "docs":    "/docs",
        "health":  "/api/health",
    }