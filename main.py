"""
FastAPI 애플리케이션 진입점.

실행:
    uvicorn main:app --reload --port 8000

Swagger UI: http://localhost:8000/docs
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.financial_router import get_router
from src.api.services import build_app_services, resolve_app_settings

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


def create_app(*, project_root: Path | None = None) -> FastAPI:
    root = project_root or Path(__file__).resolve().parent
    settings = resolve_app_settings(root)

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        """애플리케이션 시작/종료 수명 주기."""
        _configure_logging()
        logger.info("서버 시작 — 컴포넌트 초기화 중...")
        application.state.services = build_app_services(project_root=root)
        yield
        logger.info("서버 종료")

    application = FastAPI(
        title="DART 공시 분석 AI Agent API",
        description=(
            "DART(전자공시시스템) 공시 문서를 기반으로 "
            "자연어 질문에 답하는 기업 분석 AI Agent."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    cors_origins = tuple(
        origin.strip()
        for origin in settings.get("DART_CORS_ALLOW_ORIGINS", "").split(",")
        if origin.strip()
    )
    if cors_origins:
        application.add_middleware(
            CORSMiddleware,
            allow_origins=list(cors_origins),
            allow_methods=["*"],
            allow_headers=["*"],
        )

    application.include_router(get_router())

    @application.get("/")
    async def root():
        return {
            "service": "DART Financial Analysis AI",
            "docs": "/docs",
            "health": "/api/health",
        }

    return application


app = create_app()
