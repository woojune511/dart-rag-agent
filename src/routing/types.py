from __future__ import annotations

from typing import Dict, Literal, Optional

from pydantic import BaseModel, Field


QueryIntent = Literal["numeric_fact", "business_overview", "risk", "comparison", "trend", "qa"]
FormatPreference = Literal["table", "paragraph", "mixed"]


class QueryRoutingDecision(BaseModel):
    intent: QueryIntent = Field(
        description=(
            "numeric_fact=특정 수치·금액·비율을 묻는 질의 (매출, 영업이익, 부채비율, R&D 비용 등), "
            "business_overview=사업 구조·주요 사업·서비스·제품·고객군 등 기업 개요 설명 질의, "
            "risk=리스크 요인·위험 관리·파생거래 등 리스크 분석 질의, "
            "comparison=두 기업 또는 두 항목 간 비교 질의, "
            "trend=시계열 변화·추이·성장률·전년 대비 변화 질의, "
            "qa=위 유형에 해당하지 않는 일반 사실·설명 질의"
        )
    )
    format_preference: FormatPreference = Field(
        description="retrieval 및 reranking에서 우선할 evidence 형식"
    )
    confidence: Optional[float] = Field(default=None, description="0.0~1.0 범위의 분류 확신도")


class QueryRouteResult(BaseModel):
    intent: QueryIntent
    format_preference: FormatPreference
    routing_source: Literal["semantic_fast_path", "llm_fallback"]
    routing_confidence: float = Field(description="최종 routing confidence")
    routing_scores: Dict[str, float] = Field(default_factory=dict)
    second_intent: Optional[QueryIntent] = None
    margin: float = 0.0
    required_margin: float = 0.0
