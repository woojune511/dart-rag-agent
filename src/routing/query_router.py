from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate

from .types import FormatPreference, QueryIntent, QueryRouteResult, QueryRoutingDecision


logger = logging.getLogger(__name__)

ROUTER_INTENTS: tuple[str, ...] = ("numeric_fact", "business_overview", "risk", "comparison", "trend", "qa")
FORMAT_PREFERENCE_BY_INTENT: Dict[str, str] = {
    "numeric_fact": "table",
    "business_overview": "mixed",
    "risk": "paragraph",
    "comparison": "table",
    "trend": "table",
    "qa": "paragraph",
}
SEMANTIC_FASTPATH_THRESHOLD = 0.76
SEMANTIC_FASTPATH_MARGIN = 0.04
SEMANTIC_CONFUSION_PAIR_MARGIN = 0.10
SEMANTIC_CONFUSION_PAIRS = {
    frozenset({"business_overview", "risk"}),
    frozenset({"business_overview", "numeric_fact"}),
    frozenset({"numeric_fact", "comparison"}),
}


def default_canonical_queries_path() -> Path:
    override = os.environ.get("QUERY_ROUTING_CANONICAL_PATH")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[2] / "benchmarks" / "golden" / "query_routing_canonical_v1.json"


def default_format_preference(intent: str) -> str:
    return FORMAT_PREFERENCE_BY_INTENT.get(intent, "mixed")


def cosine_similarity(left: List[float], right: List[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(float(a) * float(b) for a, b in zip(left, right))
    left_norm = math.sqrt(sum(float(a) * float(a) for a in left))
    right_norm = math.sqrt(sum(float(b) * float(b) for b in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)


def load_canonical_routing_examples(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"canonical query file not found: {path}")

    payload = json.loads(path.read_text(encoding="utf-8"))
    examples: List[Dict[str, Any]] = []
    for entry in payload:
        intent = str(entry.get("id") or "").strip()
        if intent not in ROUTER_INTENTS:
            continue
        queries = [str(query).strip() for query in entry.get("queries", []) if str(query).strip()]
        for query in queries:
            examples.append(
                {
                    "intent": intent,
                    "query": query,
                    "format_preference": default_format_preference(intent),
                }
            )
    return examples


class QueryRouter:
    def __init__(
        self,
        embeddings: Any,
        llm: Any,
        canonical_queries_path: Optional[Path] = None,
    ) -> None:
        self.embeddings = embeddings
        self.llm = llm
        self.canonical_queries_path = canonical_queries_path or default_canonical_queries_path()
        self._semantic_router = self._build_semantic_router()

    def _build_semantic_router(self) -> Dict[str, Any]:
        try:
            examples = load_canonical_routing_examples(self.canonical_queries_path)
        except Exception as exc:
            logger.warning("[routing] failed to load canonical routing examples: %s", exc)
            return {"enabled": False, "examples": []}

        if not examples:
            logger.warning("[routing] no canonical routing examples loaded from %s", self.canonical_queries_path)
            return {"enabled": False, "examples": []}

        queries = [entry["query"] for entry in examples]
        try:
            embeddings = self.embeddings.embed_documents(queries)
        except Exception as exc:
            logger.warning("[routing] failed to embed canonical routing queries: %s", exc)
            return {"enabled": False, "examples": []}

        enriched: List[Dict[str, Any]] = []
        for entry, embedding in zip(examples, embeddings):
            enriched.append({**entry, "embedding": embedding})

        logger.info("[routing] semantic router loaded %s canonical queries", len(enriched))
        return {"enabled": True, "examples": enriched}

    def semantic_route(self, query: str) -> Dict[str, Any]:
        router = self._semantic_router or {}
        examples = router.get("examples") or []
        if not router.get("enabled") or not examples:
            return {
                "intent": None,
                "format_preference": None,
                "confidence": 0.0,
                "margin": 0.0,
                "required_margin": SEMANTIC_FASTPATH_MARGIN,
                "second_intent": "",
                "scores": {},
                "fast_path": False,
            }

        try:
            query_embedding = self.embeddings.embed_query(query)
        except Exception as exc:
            logger.warning("[routing] semantic router embed_query failed: %s", exc)
            return {
                "intent": None,
                "format_preference": None,
                "confidence": 0.0,
                "margin": 0.0,
                "required_margin": SEMANTIC_FASTPATH_MARGIN,
                "second_intent": "",
                "scores": {},
                "fast_path": False,
            }

        scores: Dict[str, float] = {}
        best_example_by_intent: Dict[str, Dict[str, Any]] = {}
        for example in examples:
            score = cosine_similarity(query_embedding, example["embedding"])
            intent = example["intent"]
            if score > scores.get(intent, -1.0):
                scores[intent] = score
                best_example_by_intent[intent] = example

        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        if not ranked:
            return {
                "intent": None,
                "format_preference": None,
                "confidence": 0.0,
                "margin": 0.0,
                "required_margin": SEMANTIC_FASTPATH_MARGIN,
                "second_intent": "",
                "scores": {},
                "fast_path": False,
            }

        top_intent, top_score = ranked[0]
        second_intent, second_score = ranked[1] if len(ranked) > 1 else ("", 0.0)
        margin = top_score - second_score
        confusion_pair = frozenset({top_intent, second_intent})
        required_margin = (
            SEMANTIC_CONFUSION_PAIR_MARGIN
            if confusion_pair in SEMANTIC_CONFUSION_PAIRS
            else SEMANTIC_FASTPATH_MARGIN
        )
        fast_path = top_score >= SEMANTIC_FASTPATH_THRESHOLD and margin >= required_margin
        best_example = best_example_by_intent.get(top_intent, {})
        return {
            "intent": top_intent,
            "format_preference": best_example.get("format_preference") or default_format_preference(top_intent),
            "confidence": float(top_score),
            "margin": float(margin),
            "required_margin": float(required_margin),
            "second_intent": second_intent,
            "scores": {intent: round(score, 4) for intent, score in ranked},
            "fast_path": fast_path,
        }

    def route(self, query: str) -> QueryRouteResult:
        semantic_result = self.semantic_route(query)
        logger.info(
            "[routing] semantic intent=%s second=%s confidence=%.3f margin=%.3f required_margin=%.3f fast_path=%s scores=%s",
            semantic_result.get("intent"),
            semantic_result.get("second_intent"),
            semantic_result.get("confidence", 0.0),
            semantic_result.get("margin", 0.0),
            semantic_result.get("required_margin", SEMANTIC_FASTPATH_MARGIN),
            semantic_result.get("fast_path"),
            semantic_result.get("scores", {}),
        )

        # 계산이 필요한 질문은 numeric_fact fast-path를 차단해 LLM slow-path에서 comparison으로 분류
        # 임베딩 공간 분리가 메인 방어선이나, margin이 threshold를 넘는 경우의 최후 안전장치
        _CALC_GUARDRAIL_KEYWORDS = frozenset({"이익률", "비중", "합계", "합산", "비율"})
        _numeric_fast_path_blocked = (
            semantic_result.get("fast_path")
            and semantic_result.get("intent") == "numeric_fact"
            and any(kw in query for kw in _CALC_GUARDRAIL_KEYWORDS)
        )
        if _numeric_fast_path_blocked:
            logger.info("[routing] fast-path blocked by calc guardrail; forcing slow-path LLM")

        if semantic_result.get("fast_path") and semantic_result.get("intent") and not _numeric_fast_path_blocked:
            intent = str(semantic_result["intent"])
            format_preference = str(
                semantic_result.get("format_preference") or default_format_preference(intent)
            )
            logger.info(
                "[routing] fast-path intent=%s format=%s confidence=%.3f",
                intent,
                format_preference,
                semantic_result.get("confidence", 0.0),
            )
            return QueryRouteResult(
                intent=intent,  # type: ignore[arg-type]
                format_preference=format_preference,  # type: ignore[arg-type]
                routing_source="semantic_fast_path",
                routing_confidence=float(semantic_result.get("confidence") or 0.0),
                routing_scores=dict(semantic_result.get("scores") or {}),
                second_intent=semantic_result.get("second_intent") or None,  # type: ignore[arg-type]
                margin=float(semantic_result.get("margin") or 0.0),
                required_margin=float(semantic_result.get("required_margin") or SEMANTIC_FASTPATH_MARGIN),
            )

        structured_llm = self.llm.with_structured_output(QueryRoutingDecision)
        prompt = ChatPromptTemplate.from_template(
            """다음 기업 공시 질문을 `intent`와 `format_preference`로 분류하세요.

intent 정의:
- numeric_fact : 문서에 수치가 직접 기재되어 있어 조회만으로 답할 수 있는 질의. 계산 없이 단일 숫자를 찾으면 됨.
- business_overview : 사업 구조·주요 제품·서비스·고객군·사업 부문 구성 등 기업 개요를 묻는 질의.
- risk : 리스크 요인·위험 관리 방식·파생거래 등을 묻는 질의.
- comparison : 두 수치를 더하거나 빼거나 나눠서 계산해야 답할 수 있는 질의. 합계·차이·비중·이익률 계산 포함.
- trend : 시계열 변화·추이·성장률·전년 대비 변화를 묻는 질의.
- qa : 위 유형에 해당하지 않는 일반 사실·설명 질의.

[핵심 구분 규칙]
- 두 항목을 더한 합계 → comparison
- 두 수치를 나눠 비중·비율·이익률을 계산 → comparison
- 문서에 수치가 이미 기재된 단일 값 조회 → numeric_fact

format_preference 정의:
- table : 표 기반 수치 근거를 우선해야 함
- paragraph : 설명 문단 근거를 우선해야 함
- mixed : 표와 문단을 함께 볼 수 있음

[Few-shot 예시]
Q: 삼성전자의 주요 재무 리스크는 무엇인가요?
A: intent=risk, format_preference=paragraph

Q: 환율 위험 관리 방식은 어떻게 설명하나요?
A: intent=risk, format_preference=paragraph

Q: 회사가 영위하는 주요 사업은 무엇인가요?
A: intent=business_overview, format_preference=mixed

Q: 삼성전자는 어떤 제품과 서비스를 제공하나요?
A: intent=business_overview, format_preference=mixed

Q: 삼성전자는 몇 개의 종속기업으로 구성된 글로벌 전자 기업이라고 설명하나요?
A: intent=business_overview, format_preference=mixed

Q: 삼성전자의 연결대상 종속기업은 총 몇 개인가요?
A: intent=business_overview, format_preference=mixed

Q: 삼성전자의 연결 기준 매출액은 얼마인가요?
A: intent=numeric_fact, format_preference=table

Q: 각 부문별 매출 비중은 어떻게 되나요?
A: intent=numeric_fact, format_preference=table

Q: 회사의 임직원 수는 총 몇 명인가요?
A: intent=qa, format_preference=paragraph

Q: DX와 DS 부문의 매출 차이는 얼마인가요?
A: intent=comparison, format_preference=table

Q: SDC와 Harman 부문의 매출 합계는 얼마인가요?
A: intent=comparison, format_preference=table

Q: 연결 기준 영업이익률은 얼마인가요?
A: intent=comparison, format_preference=table

Q: 연구개발비용이 전체 매출에서 차지하는 비중은 얼마인가요?
A: intent=comparison, format_preference=table

Q: 최근 3년 영업이익 추이는 어떻게 변했나요?
A: intent=trend, format_preference=table

Q: 삼성전자의 설립일은 언제인가요?
A: intent=qa, format_preference=paragraph

참고 semantic prior:
- top_intent: {semantic_intent}
- semantic_confidence: {semantic_confidence}

질문: {query}"""
        )
        result: QueryRoutingDecision = (prompt | structured_llm).invoke(
            {
                "query": query,
                "semantic_intent": semantic_result.get("intent") or "unknown",
                "semantic_confidence": f"{float(semantic_result.get('confidence') or 0.0):.3f}",
            }
        )
        logger.info(
            "[routing] slow-path intent=%s format=%s confidence=%s semantic_scores=%s",
            result.intent,
            result.format_preference,
            result.confidence,
            semantic_result.get("scores", {}),
        )
        return QueryRouteResult(
            intent=result.intent,
            format_preference=result.format_preference,
            routing_source="llm_fallback",
            routing_confidence=float(result.confidence or semantic_result.get("confidence") or 0.0),
            routing_scores=dict(semantic_result.get("scores") or {}),
            second_intent=semantic_result.get("second_intent") or None,  # type: ignore[arg-type]
            margin=float(semantic_result.get("margin") or 0.0),
            required_margin=float(semantic_result.get("required_margin") or SEMANTIC_FASTPATH_MARGIN),
        )
